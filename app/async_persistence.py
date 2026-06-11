import atexit
import queue
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from peewee import DoesNotExist

from app.dao import update_room_status, upsert_run
from app.db import atomic_transaction, db
from app.models import Room
from app.utils.logger import get_logger

logger = get_logger('nte.async_persistence')


@dataclass(frozen=True)
class RunPersistEvent:
    room_id: int
    sequence: int
    status: str
    snapshot: dict[str, Any]
    touch_room: bool
    update_room_status: bool
    attempts: int = 0


@dataclass
class CachedRun:
    sequence: int
    status: str
    snapshot: dict[str, Any]
    updated_at: datetime


_queue: queue.Queue[RunPersistEvent] = queue.Queue()
_lock = threading.Lock()
_write_lock = threading.Lock()
_worker_started = False
_room_sequences: dict[int, int] = {}
_cached_runs: dict[int, CachedRun] = {}
_MAX_RETRY_ATTEMPTS = 3


def queue_room_snapshot_persist(
    room_id: int,
    status: str,
    snapshot: dict[str, Any],
    *,
    touch_room: bool,
    update_room_status: bool,
) -> None:
    _ensure_worker_started()
    with _lock:
        sequence = _room_sequences.get(room_id, 0) + 1
        _room_sequences[room_id] = sequence
        _cached_runs[room_id] = CachedRun(
            sequence=sequence,
            status=status,
            snapshot=snapshot,
            updated_at=datetime.utcnow(),
        )
    _queue.put(RunPersistEvent(
        room_id=room_id,
        sequence=sequence,
        status=status,
        snapshot=snapshot,
        touch_room=touch_room,
        update_room_status=update_room_status,
    ))


def get_cached_room_run(room_id: int) -> dict[str, Any] | None:
    with _lock:
        cached = _cached_runs.get(room_id)
        if cached is None:
            return None
        return {
            'status': cached.status,
            'snapshot': deepcopy(cached.snapshot),
            'updated_at': cached.updated_at.isoformat(),
        }


def discard_cached_room_run(room_id: int) -> None:
    with _write_lock:
        with _lock:
            _room_sequences[room_id] = _room_sequences.get(room_id, 0) + 1
            _cached_runs.pop(room_id, None)


def flush_async_persistence(timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while _queue.unfinished_tasks > 0 and time.monotonic() < deadline:
        time.sleep(0.02)


def _ensure_worker_started() -> None:
    global _worker_started
    if _worker_started:
        return
    with _lock:
        if _worker_started:
            return
        thread = threading.Thread(target=_worker_loop, name='nte-run-persistence', daemon=True)
        thread.start()
        _worker_started = True


def _worker_loop() -> None:
    while True:
        event = _queue.get()
        try:
            _persist_event(event)
        except Exception:
            logger.exception('async persist failed room_id=%s sequence=%s', event.room_id, event.sequence)
            if event.attempts + 1 < _MAX_RETRY_ATTEMPTS and _is_latest_event(event.room_id, event.sequence):
                time.sleep(0.08 * (event.attempts + 1))
                _queue.put(RunPersistEvent(
                    room_id=event.room_id,
                    sequence=event.sequence,
                    status=event.status,
                    snapshot=event.snapshot,
                    touch_room=event.touch_room,
                    update_room_status=event.update_room_status,
                    attempts=event.attempts + 1,
                ))
        finally:
            _queue.task_done()


def _persist_event(event: RunPersistEvent) -> None:
    with _write_lock:
        if not _is_latest_event(event.room_id, event.sequence):
            return
        if db.is_closed():
            db.connect(reuse_if_open=True)
        with atomic_transaction():
            if not _is_latest_event(event.room_id, event.sequence):
                return
            try:
                room = Room.get_by_id(event.room_id)
            except DoesNotExist:
                return
            upsert_run(
                room,
                event.status,
                event.snapshot,
                touch_room=event.touch_room and not event.update_room_status,
            )
            if event.update_room_status:
                update_room_status(room, event.status)


def _is_latest_event(room_id: int, sequence: int) -> bool:
    with _lock:
        return _room_sequences.get(room_id) == sequence


atexit.register(flush_async_persistence)
