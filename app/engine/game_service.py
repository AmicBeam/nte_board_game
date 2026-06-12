from __future__ import annotations

from copy import deepcopy

from app.async_persistence import discard_cached_room_run, get_cached_room_run
from app.dao import clear_run, get_run, list_room_members, update_room_status, upsert_run
from app.db import atomic_transaction
from app.engine.application.build_service import (
    get_catalog_payload,
    get_encyclopedia_payload,
    save_build,
    save_build_with_starters,
)
from app.engine.application.run_state import (
    create_initial_snapshot as _create_initial_snapshot,
    load_mutable_player_run as _load_mutable_player_run,
    persist_room_snapshot as _persist_room_snapshot,
    public_state as _public_state,
    should_show_initial_banner as _should_show_initial_banner,
)
from app.engine.event_bus import dispatch_event
from app.engine.events import GameEvent
from app.engine.state.types import JsonDict
from app.models import Player, Room
from app.engine.flow.turn_flow import (
    SIDE_A,
    SIDE_B,
    SIDE_KEYS,
    CARD_TYPE_ESPER,
    RuleValidationError,
    _add_log,
    _clear_pending_target_for_source,
    _consume_delay_tax,
    _delay_tax,
    _effective_cost,
    _energy_remaining,
    _ensure_not_ended,
    _ensure_playing,
    _ensure_required_target_before_play,
    _ensure_selection_resolved,
    _ensure_turn_undo_checkpoint,
    _find_card_in_zone,
    _find_card_in_zone_or_none,
    _find_card_on_board,
    _find_location,
    _find_pending_source_card,
    _find_revealed_esper_on_board,
    _find_staged_card,
    _find_target_card,
    _is_location_revealed,
    _is_snap_snapshot,
    _location_capacity,
    _location_has_room_after_materials,
    _location_index,
    _location_occupied_card_count,
    _mark_side_reactivation,
    _material_cards_for_esper,
    _next_play_sequence,
    _opponent_side,
    _prepare_declaration_selection,
    _prepare_declaration_target,
    _recompute_scores,
    _refund_card_cost,
    _release_material_reservations,
    _reserve_materials,
    _resolve_ai_pending_choices,
    _resolve_declaration_selection,
    _resolve_draw_selection,
    _resolve_opening_selection,
    _resolve_turn,
    _restore_side_from_turn_undo,
    _run_ai_turn,
    _side_name,
    _side_reactivation_used,
    _sync_planning_phase,
    _turn_undo_checkpoint,
)
from app.engine.rules.declarations import (
    declaration_selection_preview as _declaration_selection_preview,
    target_rule_internal as _target_rule_internal,
)

def start_or_resume_run_for_room(room: Room, actor: Player, options: JsonDict | None = None) -> JsonDict:
    options = options or {}
    force_new = bool(options.get('force_new'))
    if force_new:
        discard_cached_room_run(room.id)
        clear_run(room)

    cached = get_cached_room_run(room.id)
    run = cached or get_run(room)
    if run is not None and _is_snap_snapshot(run.get('snapshot', {})):
        snapshot = deepcopy(run['snapshot'])
        return _public_state(snapshot, room, actor, include_queues=_should_show_initial_banner(snapshot))

    members = list_room_members(room)
    if room.mode == 'duo' and len(members) < 2:
        raise RuleValidationError('未来 1v1 房间需要两名玩家都进入后才能开始。')

    snapshot = _create_initial_snapshot(room, members, options)
    with atomic_transaction():
        upsert_run(room, snapshot['status'], snapshot)
        update_room_status(room, snapshot['status'])
    discard_cached_room_run(room.id)
    return _public_state(snapshot, room, actor)


def get_run_state_for_room(room: Room, player: Player) -> JsonDict | None:
    run = get_cached_room_run(room.id) or get_run(room)
    if run is None:
        return None
    snapshot = deepcopy(run['snapshot'])
    if not _is_snap_snapshot(snapshot):
        return None
    return _public_state(snapshot, room, player, include_queues=_should_show_initial_banner(snapshot))


def declaration_previews(player: Player) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    side_state = snapshot['sides'][side]
    payload = {
        'turn': int(snapshot.get('turn') or 0),
        'phase': snapshot.get('phase', ''),
        'energy_remaining': _energy_remaining(snapshot, side),
        'previews': {},
    }
    if (
        snapshot.get('phase') != 'planning'
        or side_state.get('ended_turn')
        or side_state.get('selection')
        or side_state.get('pending_target')
    ):
        return payload

    previews: dict[str, JsonDict] = {}
    for card in side_state.get('hand', []):
        if _target_rule_internal(card):
            continue
        for location in snapshot.get('locations', []):
            if not _can_preview_declaration_for_location(snapshot, side, location, card):
                continue
            preview = _declaration_selection_preview(snapshot, side, location, card)
            if preview is None:
                continue
            public_preview = _public_declaration_preview(room, player, snapshot, side, preview)
            if public_preview:
                previews[f"{card['instance_id']}:{location['id']}"] = public_preview
    payload['previews'] = previews
    return payload


def _can_preview_declaration_for_location(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> bool:
    if not _is_location_revealed(snapshot, location):
        return False
    if _location_occupied_card_count(location, side) >= _location_capacity(location):
        return False
    cost = _effective_cost(card) + _delay_tax(snapshot, side, location)
    return cost <= _energy_remaining(snapshot, side)


def _public_declaration_preview(
    room: Room,
    player: Player,
    snapshot: JsonDict,
    side: str,
    preview: JsonDict,
) -> JsonDict | None:
    preview_snapshot = deepcopy(snapshot)
    preview_snapshot['action_queue'] = []
    preview_snapshot['banner_queue'] = []
    preview_snapshot['sides'][side]['selection'] = deepcopy(preview)
    public_payload = _public_state(preview_snapshot, room, player, include_queues=False)
    selection = public_payload.get('selection')
    return selection if isinstance(selection, dict) else None


def reset_run_for_room(room: Room) -> None:
    discard_cached_room_run(room.id)
    clear_run(room)
    update_room_status(room, 'ready' if room.mode == 'solo' else 'waiting')


def play_card(player: Player, card_instance_id: str, location_id: str) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    _ensure_selection_resolved(snapshot, side)
    _ensure_not_ended(snapshot, side)
    location = _find_location(snapshot, str(location_id))
    if not _is_location_revealed(snapshot, location):
        raise RuleValidationError('这个异象空间尚未显现，暂时不能出牌。')
    if _location_occupied_card_count(location, side) >= _location_capacity(location):
        raise RuleValidationError('这个空间已满。')
    hand = snapshot['sides'][side]['hand']
    card = _find_card_in_zone(hand, str(card_instance_id), '手牌中没有这张牌。')
    delay_tax = _delay_tax(snapshot, side, location)
    cost = _effective_cost(card) + delay_tax
    if cost > _energy_remaining(snapshot, side):
        raise RuleValidationError('能量不足。')
    _ensure_required_target_before_play(snapshot, side, location, card)
    _ensure_turn_undo_checkpoint(snapshot, side)
    hand.remove(card)
    card['played_turn'] = snapshot['turn']
    card['location_id'] = location['id']
    card['revealed'] = False
    card['staged'] = True
    card['paid_cost'] = cost
    card['play_sequence'] = _next_play_sequence(snapshot)
    card.pop('selected_target_instance_id', None)
    card.pop('selected_target_name', None)
    card.pop('declared_card_instance_ids', None)
    card.pop('declared_card_names', None)
    snapshot['sides'][side]['energy_used'] += cost
    location['cards'][side].append(card)
    if delay_tax:
        _consume_delay_tax(snapshot, side, location)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 将 {card['name']} 置入 {location['name']}。")
    dispatch_event(snapshot, GameEvent.CARD_PLAYED, {
        'target_instance_id': card['instance_id'],
        'card_instance_id': card['instance_id'],
        'card': card,
        'side': side,
        'opponent_side': _opponent_side(side),
        'location': location,
        'location_id': location['id'],
        'location_index': _location_index(snapshot, location['id']),
    })
    if _prepare_declaration_target(snapshot, side, location, card):
        _add_log(snapshot, f"{card['name']} 等待选择目标。")
    elif _prepare_declaration_selection(snapshot, side, location, card):
        _add_log(snapshot, f"{card['name']} 正在检视牌库。")
    _recompute_scores(snapshot)
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def play_esper(
    player: Player,
    card_instance_id: str,
    location_id: str,
    material_instance_ids: list[str] | None = None,
) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    _ensure_selection_resolved(snapshot, side)
    _ensure_not_ended(snapshot, side)
    location = _find_location(snapshot, str(location_id))
    if not _is_location_revealed(snapshot, location):
        raise RuleValidationError('这个异象空间尚未显现，暂时不能唤醒异能者。')
    standby = snapshot['sides'][side].setdefault('esper_standby', [])
    card = _find_card_in_zone_or_none(standby, str(card_instance_id))
    is_reactivation = False
    if card is None:
        card, current_location = _find_revealed_esper_on_board(snapshot, side, str(card_instance_id))
        if current_location['id'] != location['id']:
            raise RuleValidationError('场上的异能者只能在当前所在空间继续共鸣。')
        if card.get('pending_material_ids') or card.get('reactivating_turn') == snapshot.get('turn'):
            raise RuleValidationError('这名异能者本回合已经准备共鸣。')
        if _side_reactivation_used(snapshot, side):
            raise RuleValidationError('本回合已经准备过 1 次场上异能者共鸣。')
        is_reactivation = True
    selected_material_ids = None if material_instance_ids is None else [str(item) for item in material_instance_ids]
    try:
        material_cards = _material_cards_for_esper(
            snapshot,
            side,
            location,
            card,
            material_instance_ids=selected_material_ids,
        )
    except RuleValidationError:
        if not is_reactivation:
            standby.append(card)
        raise
    if not is_reactivation and not _location_has_room_after_materials(location, side, material_cards):
        raise RuleValidationError('这个空间在消耗素材后仍然会超出上限。')
    material_ids = [item['instance_id'] for item in material_cards]
    _ensure_turn_undo_checkpoint(snapshot, side)
    if not is_reactivation:
        standby.remove(card)
    _reserve_materials(material_cards, card['instance_id'])
    if is_reactivation:
        card['reactivating_turn'] = snapshot['turn']
        _mark_side_reactivation(snapshot, side)
    else:
        card['played_turn'] = snapshot['turn']
        card['location_id'] = location['id']
        card['revealed'] = False
        card['staged'] = True
        card['play_sequence'] = _next_play_sequence(snapshot)
        card['summoned_from'] = 'esper_standby'
        location['cards'][side].append(card)
    card['pending_material_ids'] = material_ids
    card['paid_cost'] = 0
    card.pop('selected_target_instance_id', None)
    card.pop('selected_target_name', None)
    card.pop('declared_card_instance_ids', None)
    card.pop('declared_card_names', None)
    verb = '准备共鸣' if is_reactivation else '唤醒'
    _add_log(snapshot, f"{_side_name(snapshot, side)} {verb} {card['name']} 于 {location['name']}，预定消耗 {len(material_ids)} 个素材。")
    dispatch_event(snapshot, GameEvent.CARD_PLAYED, {
        'target_instance_id': card['instance_id'],
        'card_instance_id': card['instance_id'],
        'card': card,
        'side': side,
        'opponent_side': _opponent_side(side),
        'location': location,
        'location_id': location['id'],
        'location_index': _location_index(snapshot, location['id']),
    })
    if _prepare_declaration_target(snapshot, side, location, card):
        _add_log(snapshot, f"{card['name']} 等待选择目标。")
    elif _prepare_declaration_selection(snapshot, side, location, card):
        _add_log(snapshot, f"{card['name']} 正在检视牌库。")
    _recompute_scores(snapshot)
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def return_staged_card(player: Player, card_instance_id: str) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    _ensure_not_ended(snapshot, side)
    card, location = _find_staged_card(snapshot, side, str(card_instance_id))
    if card.get('reserved_as_material_for'):
        raise RuleValidationError('这张牌已被异能者预定为素材，请先收回对应异能者。')
    _ensure_turn_undo_checkpoint(snapshot, side)
    location['cards'][side].remove(card)
    _refund_card_cost(snapshot, side, card)
    _release_material_reservations(snapshot, side, card['instance_id'])
    card['played_turn'] = None
    card['location_id'] = None
    card['revealed'] = False
    card.pop('staged', None)
    card.pop('paid_cost', None)
    card.pop('play_sequence', None)
    card.pop('pending_material_ids', None)
    card.pop('selected_target_instance_id', None)
    card.pop('selected_target_name', None)
    card.pop('declared_card_instance_ids', None)
    card.pop('declared_card_names', None)
    if card.get('summoned_from') == 'esper_standby' or card.get('type') == CARD_TYPE_ESPER:
        card.pop('summoned_from', None)
        snapshot['sides'][side].setdefault('esper_standby', []).append(card)
    else:
        snapshot['sides'][side]['hand'].append(card)
    _clear_pending_target_for_source(snapshot, side, card['instance_id'])
    _add_log(snapshot, f"{_side_name(snapshot, side)} 收回 {card['name']}。")
    _recompute_scores(snapshot)
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def move_staged_card(player: Player, card_instance_id: str, location_id: str) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    _ensure_not_ended(snapshot, side)
    card, source_location = _find_staged_card(snapshot, side, str(card_instance_id))
    if card.get('reserved_as_material_for'):
        raise RuleValidationError('这张牌已被异能者预定为素材，请先收回对应异能者。')
    target_location = _find_location(snapshot, str(location_id))
    if not _is_location_revealed(snapshot, target_location):
        raise RuleValidationError('这个异象空间尚未显现，暂时不能移动到这里。')
    if target_location['id'] == source_location['id']:
        return _public_state(snapshot, room, player)
    material_cards = []
    if card.get('summoned_from') == 'esper_standby' or card.get('type') == CARD_TYPE_ESPER:
        material_cards = _material_cards_for_esper(snapshot, side, target_location, card)
        if not _location_has_room_after_materials(target_location, side, material_cards):
            raise RuleValidationError('目标空间在消耗素材后仍然会超出上限。')
    elif _location_occupied_card_count(target_location, side) >= _location_capacity(target_location):
        raise RuleValidationError('目标空间已满。')
    _ensure_turn_undo_checkpoint(snapshot, side)
    if card.get('summoned_from') == 'esper_standby' or card.get('type') == CARD_TYPE_ESPER:
        _release_material_reservations(snapshot, side, card['instance_id'])
    source_location['cards'][side].remove(card)
    target_location['cards'][side].append(card)
    card['location_id'] = target_location['id']
    if card.get('summoned_from') == 'esper_standby' or card.get('type') == CARD_TYPE_ESPER:
        material_ids = [item['instance_id'] for item in material_cards]
        _reserve_materials(material_cards, card['instance_id'])
        card['pending_material_ids'] = material_ids
    pending = snapshot['sides'][side].get('pending_target')
    if pending and pending.get('source_instance_id') == card['instance_id']:
        pending['location_id'] = target_location['id']
    _add_log(snapshot, f"{_side_name(snapshot, side)} 将 {card['name']} 移至 {target_location['name']}。")
    _recompute_scores(snapshot)
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def choose_target(player: Player, target_instance_id: str) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    _ensure_not_ended(snapshot, side)
    pending = snapshot['sides'][side].get('pending_target')
    if not pending:
        raise RuleValidationError('当前没有需要指定目标的卡牌。')
    source, source_location = _find_pending_source_card(snapshot, side, str(pending.get('source_instance_id', '')))
    target = _find_target_card(snapshot, side, source_location, source, str(target_instance_id))
    _ensure_turn_undo_checkpoint(snapshot, side)
    source['selected_target_instance_id'] = target['instance_id']
    source['selected_target_name'] = target.get('name', '')
    snapshot['sides'][side]['pending_target'] = None
    _add_log(snapshot, f"{source['name']} 已指向 {target['name']}。")
    if _prepare_declaration_selection(snapshot, side, source_location, source, target):
        _add_log(snapshot, f"{source['name']} 正在检视牌库。")
    _recompute_scores(snapshot)
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def cancel_target(player: Player) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    pending = snapshot['sides'][side].get('pending_target')
    if not pending:
        return _public_state(snapshot, room, player)
    _ensure_turn_undo_checkpoint(snapshot, side)
    source_id = str(pending.get('source_instance_id', ''))
    snapshot['sides'][side]['pending_target'] = None
    source = _find_card_on_board(snapshot, source_id)
    if source is not None and source.get('reactivating_turn') == snapshot.get('turn'):
        _release_material_reservations(snapshot, side, source_id)
        source.pop('pending_material_ids', None)
        source.pop('reactivating_turn', None)
        _persist_room_snapshot(room, snapshot)
        return _public_state(snapshot, room, player)
    _persist_room_snapshot(room, snapshot)
    return return_staged_card(player, source_id)


def undo_turn(player: Player) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    if snapshot.get('phase') != 'planning':
        raise RuleValidationError('只能在部署阶段撤销本回合操作。')
    if snapshot['sides'][side].get('ended_turn'):
        raise RuleValidationError('已经结束回合，不能撤销本回合操作。')
    checkpoint = _turn_undo_checkpoint(snapshot, side)
    if checkpoint is None:
        raise RuleValidationError('本回合没有可以撤销的操作。')
    restored_snapshot = deepcopy(checkpoint.get('snapshot') or {})
    if not _is_snap_snapshot(restored_snapshot):
        raise RuleValidationError('本回合撤销点已失效。')
    _restore_side_from_turn_undo(snapshot, side, restored_snapshot)
    snapshot.setdefault('turn_undo_checkpoints', {}).pop(side, None)
    snapshot['action_queue'] = []
    _sync_planning_phase(snapshot)
    _recompute_scores(snapshot)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 撤销了本回合全部操作。")
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def choose_cards(player: Player, card_instance_ids: list[str]) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    selection = snapshot['sides'][side].get('selection')
    if not selection:
        raise RuleValidationError('当前没有需要选择的卡牌。')
    selected_ids = [str(card_id) for card_id in card_instance_ids if str(card_id)]
    if selection.get('kind') == 'opening':
        _resolve_opening_selection(snapshot, side, selected_ids)
    elif selection.get('kind') == 'draw':
        _resolve_draw_selection(snapshot, side, selected_ids)
    elif selection.get('kind') == 'declaration':
        _resolve_declaration_selection(snapshot, side, selected_ids)
    else:
        raise RuleValidationError('未知的选牌阶段。')
    if snapshot['mode'] == 'solo':
        _resolve_ai_pending_choices(snapshot, SIDE_B)
    _sync_planning_phase(snapshot)
    _recompute_scores(snapshot)
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def end_turn(player: Player) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    _ensure_playing(snapshot)
    _ensure_selection_resolved(snapshot, side)
    snapshot['sides'][side]['ended_turn'] = True
    _add_log(snapshot, f"{_side_name(snapshot, side)} 结束回合。")

    if snapshot['mode'] == 'solo':
        _run_ai_turn(snapshot, SIDE_B)
        snapshot['sides'][SIDE_B]['ended_turn'] = True

    if all(snapshot['sides'][current_side]['ended_turn'] for current_side in SIDE_KEYS):
        _resolve_turn(snapshot)
    else:
        _add_log(snapshot, '等待另一名玩家结束回合。')

    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)


def retreat(player: Player) -> JsonDict:
    room, snapshot, side = _load_mutable_player_run(player)
    if snapshot['status'] != 'playing':
        return _public_state(snapshot, room, player)
    snapshot['status'] = 'defeat' if side == SIDE_A else 'victory'
    snapshot['winner_side'] = _opponent_side(side)
    snapshot['phase'] = 'defeat'
    _add_log(snapshot, f"{_side_name(snapshot, side)} 撤退，对局结束。")
    snapshot.setdefault('banner_queue', []).append({
        'kind': 'result',
        'title': '失败' if side == SIDE_A else '胜利',
        'subtitle': '对局结束',
    })
    _persist_room_snapshot(room, snapshot)
    return _public_state(snapshot, room, player)
