from __future__ import annotations

from app.dao import (
    ROOM_OPEN_STATUSES,
    add_room_member,
    create_room,
    get_current_room,
    get_room_by_code,
    get_room_member,
    get_run,
    list_room_members,
    serialize_room,
    set_room_member_ready,
    update_room_status,
)
from app.db import atomic_transaction
from app.modules.card_game.engine.game_service import get_run_state_for_room, reset_run_for_room, start_or_resume_run_for_room
from app.errors import RuleValidationError
from app.models import Player, Room

SUPPORTED_ROOM_MODES = frozenset({'solo', 'duo'})


def get_current_room_state(player: Player) -> dict | None:
    room = get_current_room(player)
    if room is None:
        return None
    return _serialize_room_state(room)


def create_room_for_player(player: Player, mode: str) -> dict:
    with atomic_transaction():
        normalized_mode = _normalize_room_mode(mode)
        existing_room = get_current_room(player, ROOM_OPEN_STATUSES)
        if existing_room is not None:
            raise RuleValidationError('当前已有进行中的房间，请先完成或离开当前房间。')
        room = create_room(player, normalized_mode)
        add_room_member(
            room,
            player,
            seat='host',
            is_host=True,
            is_ready=normalized_mode == 'solo',
        )
        if normalized_mode == 'solo':
            update_room_status(room, 'ready')
        return _serialize_room_state(room)


def join_room_by_code(player: Player, room_code: str) -> dict:
    with atomic_transaction():
        existing_room = get_current_room(player, ROOM_OPEN_STATUSES)
        if existing_room is not None:
            raise RuleValidationError('当前已有进行中的房间，请先完成或离开当前房间。')
        room = get_room_by_code(str(room_code).strip())
        if room is None:
            raise RuleValidationError('房间不存在。')
        if room.mode == 'solo':
            raise RuleValidationError('单人房间不支持加入。')
        if room.status not in {'waiting', 'ready'}:
            raise RuleValidationError('该房间当前不可加入。')
        members = list_room_members(room)
        if len(members) >= 2:
            raise RuleValidationError('房间已满。')
        if any(member.player_id == player.id for member in members):
            raise RuleValidationError('当前玩家已在该房间中。')
        add_room_member(
            room,
            player,
            seat='guest',
            is_host=False,
            is_ready=False,
        )
        update_room_status(room, 'waiting')
        return _serialize_room_state(room)


def set_room_ready(player: Player, is_ready: bool) -> dict:
    with atomic_transaction():
        room = _require_room(player)
        if room.mode == 'solo':
            raise RuleValidationError('单人房间会自动准备。')
        set_room_member_ready(room, player, is_ready)
        members = list_room_members(room)
        next_status = 'ready' if len(members) >= 2 and all(member.is_ready for member in members) else 'waiting'
        update_room_status(room, next_status)
        return _serialize_room_state(room)


def start_room_game(player: Player) -> dict:
    with atomic_transaction():
        room = _require_room(player)
        member = get_room_member(room, player)
        if member is None or not member.is_host:
            raise RuleValidationError('只有房主可以开始游戏。')
        members = list_room_members(room)
        if room.mode == 'solo':
            if len(members) != 1 or not members[0].is_ready:
                raise RuleValidationError('单人房间尚未完成初始化。')
            return start_or_resume_run_for_room(room, player)
        if len(members) < 2:
            raise RuleValidationError('房间人数不足，无法开始游戏。')
        if not all(current_member.is_ready for current_member in members):
            raise RuleValidationError('仍有玩家未准备，无法开始游戏。')
        return start_or_resume_run_for_room(room, player)


def create_or_resume_solo_room(player: Player, options: dict | None = None) -> dict:
    options = options or {}
    with atomic_transaction():
        room = get_current_room(player, ROOM_OPEN_STATUSES | frozenset({'victory', 'defeat', 'draw'}))
        if room is None:
            room = create_room(player, 'solo')
            add_room_member(room, player, seat='host', is_host=True, is_ready=True)
            update_room_status(room, 'ready')
        elif room.mode != 'solo':
            raise RuleValidationError('当前已在多人房间中，无法直接启动单人房间。')
        else:
            set_room_member_ready(room, player, True)
            if room.status == 'waiting':
                update_room_status(room, 'ready')
        return start_or_resume_run_for_room(room, player, options)


def reset_current_room_run(player: Player) -> dict:
    with atomic_transaction():
        room = _require_room(player)
        reset_run_for_room(room)
        return _serialize_room_state(room)


def get_current_room_run_state(player: Player) -> dict | None:
    room = get_current_room(player)
    if room is None:
        return None
    return get_run_state_for_room(room, player)


def _serialize_room_state(room: Room) -> dict:
    members = list_room_members(room)
    payload = serialize_room(room, members)
    run = get_run(room)
    payload['run_status'] = run['status'] if run is not None else None
    return payload


def _require_room(player: Player) -> Room:
    room = get_current_room(player)
    if room is None:
        raise RuleValidationError('当前没有房间，请先创建或加入房间。')
    return room


def _normalize_room_mode(mode: str) -> str:
    normalized_mode = str(mode or 'solo').strip().lower()
    if normalized_mode not in SUPPORTED_ROOM_MODES:
        raise RuleValidationError('房间模式非法。')
    return normalized_mode
