from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.async_persistence import discard_cached_room_run, get_cached_room_run, queue_room_snapshot_persist
from app.dao import get_run, list_room_members, serialize_room, update_room_status, upsert_run
from app.db import atomic_transaction
from app.engine.flow import turn_flow
from app.engine.projection.public_state import (
    ProjectionRules,
    SidePerspective,
    public_card as _public_card_impl,
    public_location as _public_location_impl,
    public_pending_target as _public_pending_target_impl,
    public_state as _public_state_impl,
)
from app.engine.setup.snapshot_factory import (
    SnapshotFactoryRules,
    create_initial_snapshot as _create_initial_snapshot_impl,
    scenario_label as _scenario_label,
)
from app.engine.state.types import JsonDict
from app.errors import RuleValidationError
from app.models import Player, Room


def create_initial_snapshot(room: Room, members: list[Any], options: JsonDict | None = None) -> JsonDict:
    return _create_initial_snapshot_impl(room, members, snapshot_factory_rules(), options)


def snapshot_factory_rules() -> SnapshotFactoryRules:
    return SnapshotFactoryRules(
        reveal_locations_for_turn=turn_flow._reveal_locations_for_turn,
        sync_planning_phase=turn_flow._sync_planning_phase,
        recompute_scores=turn_flow._recompute_scores,
        lock_settlement_initiative=turn_flow._lock_settlement_initiative,
        draw_cards=turn_flow._draw_cards,
        add_log=turn_flow._add_log,
    )


def public_state(snapshot: JsonDict, room: Room, viewer: Player, *, include_queues: bool = True) -> JsonDict:
    return _public_state_impl(snapshot, room, viewer, projection_rules(), include_queues=include_queues)


def public_card(card: JsonDict, *, own: bool) -> JsonDict:
    return _public_card_impl(card, own=own, rules=projection_rules())


def public_pending_target(side: JsonDict, snapshot: JsonDict | None = None) -> JsonDict | None:
    return _public_pending_target_impl(side, projection_rules(), snapshot)


def public_location(location: JsonDict, perspective: SidePerspective) -> JsonDict:
    return _public_location_impl(location, perspective, projection_rules())


def projection_rules() -> ProjectionRules:
    return ProjectionRules(
        clear_legacy_draw_selections=turn_flow._clear_legacy_draw_selections,
        sync_planning_phase=turn_flow._sync_planning_phase,
        side_for_player=side_for_player,
        opponent_side=turn_flow._opponent_side,
        scenario_label=_scenario_label,
        turn_energy=turn_flow._turn_energy,
        energy_remaining=turn_flow._energy_remaining,
        can_undo_turn=turn_flow._can_undo_turn,
        room_payload=room_payload,
        find_card_on_board=turn_flow._find_card_on_board,
        find_location=turn_flow._find_location,
        location_occupied_card_count=turn_flow._location_occupied_card_count,
        effective_cost=turn_flow._effective_cost,
        raw_card_power=turn_flow._raw_card_power,
        side_name=turn_flow._side_name,
    )


def room_payload(room: Room) -> JsonDict:
    return serialize_room(room, list_room_members(room))


def load_mutable_player_run(player: Player) -> tuple[Room, JsonDict, str]:
    from app.dao import get_current_room

    room = get_current_room(player)
    if room is None:
        raise RuleValidationError('当前没有对局。')
    run = get_cached_room_run(room.id) or get_run(room)
    if run is None or not turn_flow._is_snap_snapshot(run.get('snapshot', {})):
        raise RuleValidationError('当前没有异象对局。')
    snapshot = deepcopy(run['snapshot'])
    turn_flow._clear_legacy_draw_selections(snapshot, auto_draw=True)
    clear_transient_presentation_queues(snapshot)
    side = side_for_player(snapshot, player)
    if side is None:
        raise RuleValidationError('当前玩家不在该对局中。')
    return room, snapshot, side


def clear_transient_presentation_queues(snapshot: JsonDict) -> None:
    snapshot['action_queue'] = []
    snapshot['banner_queue'] = []


def should_show_initial_banner(snapshot: JsonDict) -> bool:
    if int(snapshot.get('turn') or 0) != 1:
        return False
    if snapshot.get('action_queue'):
        return False
    if not snapshot.get('banner_queue'):
        return False
    for side_state in snapshot.get('sides', {}).values():
        if int(side_state.get('energy_used') or 0) > 0 or side_state.get('ended_turn'):
            return False
        if side_state.get('discard'):
            return False
    for location in snapshot.get('locations', []):
        for cards in location.get('cards', {}).values():
            if cards:
                return False
    return True


def persist_room_snapshot(room: Room, snapshot: JsonDict) -> None:
    if snapshot['status'] != 'playing':
        discard_cached_room_run(room.id)
        with atomic_transaction():
            upsert_run(room, snapshot['status'], snapshot)
            update_room_status(room, snapshot['status'])
        return
    queue_room_snapshot_persist(
        room.id,
        snapshot['status'],
        deepcopy(snapshot),
        touch_room=True,
        update_room_status=snapshot['status'] != 'playing',
    )


def side_for_player(snapshot: JsonDict, player: Player) -> str | None:
    for side in turn_flow.SIDE_KEYS:
        if snapshot['sides'][side]['uid'] == player.player_uid:
            return side
    return None
