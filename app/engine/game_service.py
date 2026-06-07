from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.async_persistence import discard_cached_room_run, get_cached_room_run, queue_room_snapshot_persist
from app.content.loader import (
    default_duel_deck_id,
    get_duel_card,
    get_duel_deck,
    load_characters,
    load_duel_cards,
    load_duel_decks,
    validate_duel_deck_card_ids,
)
from app.dao import (
    clear_run,
    get_build,
    get_run,
    list_room_members,
    serialize_room,
    update_room_status,
    upsert_build,
    upsert_run,
)
from app.db import atomic_transaction
from app.engine.event_bus import dispatch_event
from app.engine.events import GameEvent
from app.errors import RuleValidationError
from app.models import Player, Room

JsonDict = dict[str, Any]

GAME_ID = 'anomaly_snap_duel'
SCHEMA_VERSION = 1
SIDE_A = 'a'
SIDE_B = 'b'
SIDE_KEYS = (SIDE_A, SIDE_B)
MAX_TURNS = 6
MAX_ENERGY = 6
OPENING_SELECTION_SIZE = 4
TURN_SELECTION_SIZE = 2
TURN_SELECTION_PICK_COUNT = 1
MAX_HAND_SIZE = 10
LOCATION_CARD_LIMIT = 16
MIN_BUILD_ITEM_COUNT = 10
MAX_BUILD_ITEM_COUNT = 20
MAX_BUILD_ESPER_COUNT = 4
MAX_COPIES_PER_ITEM_CARD = 3
MAP_LOCKED_ITEM_IDS: tuple[str, ...] = ()
LOG_LIMIT = 28

CARD_BACK_IMAGE = '/static/images/cards/card-back.svg'
TAG_MURK = 'murk'
TAG_DELAY = 'delay'
TAG_DARKSTAR = 'darkstar'
TAG_GENESIS = 'genesis'
TAG_SURPLUS = 'surplus'
TAG_DISCORD = 'discord'
TAG_COLLAPSING = 'collapsing'
TAG_MATERIAL = 'material'
TAG_HARMONY = 'harmony'
CARD_TYPE_ESPER = 'esper'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'
CARD_TYPE_TOKEN = 'token'
HARMONY_TAGS = frozenset({TAG_GENESIS, TAG_MURK, TAG_DELAY, TAG_DARKSTAR, TAG_SURPLUS, TAG_DISCORD, TAG_COLLAPSING})
LOCATION_MARK_NAMES = {
    TAG_GENESIS: '创生',
    TAG_MURK: '浊燃',
    TAG_DELAY: '延滞',
    TAG_DARKSTAR: '黯星',
    TAG_DISCORD: '失谐',
    TAG_SURPLUS: '盈蓄',
    TAG_COLLAPSING: '倾陷',
}

SPECIAL_TARGET_RULES: dict[str, JsonDict] = {
    'genesis_chip_washer': {
        'scope': 'ally_item_same_location',
        'prompt': '选择 1 张己方道具。',
    },
}

CARD_LIBRARY: list[JsonDict] = load_duel_cards()

BATTLEFIELD_TRAITS: list[JsonDict] = [
    {
        'id': 'mirror_archive',
        'name': '镜像档案馆',
        'short_name': '档案馆',
        'reveal_turn': 1,
        'art': '/static/images/locations/mirror-archive.svg',
        'description': '每边在此空间揭示的第一张牌 +2 战力。',
        'effect': 'first_card_plus_two',
    },
    {
        'id': 'tide_platform',
        'name': '潮汐站台',
        'short_name': '站台',
        'reveal_turn': 2,
        'art': '/static/images/locations/tide-platform.svg',
        'description': '揭示前本方不领先时，每方每回合前 3 张在此空间揭示的牌永久 +1 战力。',
        'effect': 'revealed_cards_plus_one',
    },
    {
        'id': 'hollow_theater',
        'name': '空洞剧场',
        'short_name': '剧场',
        'reveal_turn': 3,
        'art': '/static/images/locations/hollow-theater.svg',
        'description': '如果一边只有 1 张牌在此空间，那张牌 +4 战力。',
        'effect': 'solo_card_plus_four',
    },
]

LOCATION_LIBRARY: list[JsonDict] = BATTLEFIELD_TRAITS


@dataclass(frozen=True)
class SidePerspective:
    own: str
    opponent: str


def get_catalog_payload(player: Player) -> JsonDict:
    saved_build = get_build(player)
    cards = _card_catalog()
    return {
        'characters': _leader_catalog(cards),
        'items': cards,
        'min_build_size': MIN_BUILD_ITEM_COUNT,
        'build_size': MAX_BUILD_ITEM_COUNT,
        'opening_hand_size': OPENING_SELECTION_SIZE,
        'max_esper_cards': MAX_BUILD_ESPER_COUNT,
        'locked_item_ids': list(MAP_LOCKED_ITEM_IDS),
        'decks': _deck_catalog(),
        'default_deck_id': default_duel_deck_id(),
        'saved_build': normalize_build_payload(saved_build) if saved_build is not None else None,
        'copy': {
            'build_title': '异象牌组',
            'character_label': '领队',
            'item_label': '异象卡牌',
        },
    }


def get_encyclopedia_payload() -> JsonDict:
    return {
        'game': {
            'id': GAME_ID,
            'name': '异象逆转',
            'description': '每局 6 回合，双方争夺 3 个异象空间，赢下至少 2 个空间即可获胜。',
        },
        'locations': [deepcopy(location) for location in LOCATION_LIBRARY],
        'cards': _card_catalog(),
        'decks': _deck_catalog(),
        'map': {
            'id': GAME_ID,
            'name': '三重异象空间',
            'total_layers': 1,
        },
        'map_objects': [],
        'items': _card_catalog(),
        'loot_items': [],
        'enemies': [],
    }


def save_build(player: Player, character_id: str, item_ids: list[str]) -> JsonDict:
    known_item_ids = _known_card_ids(item_ids or [], card_type=CARD_TYPE_ANOMALY_ITEM)
    return save_build_with_starters(
        player,
        character_id,
        known_item_ids[:OPENING_SELECTION_SIZE],
        known_item_ids[OPENING_SELECTION_SIZE:MAX_BUILD_ITEM_COUNT],
        [],
    )


def save_build_with_starters(
    player: Player,
    character_id: str,
    starter_item_ids: list[str],
    reserve_item_ids: list[str],
    esper_card_ids: list[str] | None = None,
) -> JsonDict:
    starter_ids = _sort_card_ids(_known_card_ids(starter_item_ids or [], card_type=CARD_TYPE_ANOMALY_ITEM))[:OPENING_SELECTION_SIZE]
    reserve_ids = _sort_card_ids(_known_card_ids(reserve_item_ids or [], card_type=CARD_TYPE_ANOMALY_ITEM))[:MAX_BUILD_ITEM_COUNT - OPENING_SELECTION_SIZE]
    selected_item_ids = [*starter_ids, *reserve_ids]
    selected_esper_ids = _unique_known_ids(esper_card_ids or [])
    _validate_custom_build_sections(selected_item_ids, selected_esper_ids)
    leader_id = str(character_id or '').strip() or (selected_esper_ids[0] if selected_esper_ids else 'protagonist')
    if leader_id not in _card_by_id() or _card_type(leader_id) != CARD_TYPE_ESPER:
        leader_id = selected_esper_ids[0] if selected_esper_ids else 'protagonist'
    is_valid, validation_error = validate_duel_deck_card_ids([*selected_item_ids, *selected_esper_ids])
    if not is_valid:
        raise RuleValidationError(validation_error)
    build_payload = {
        'starter_item_ids': selected_item_ids[:OPENING_SELECTION_SIZE],
        'reserve_item_ids': selected_item_ids[OPENING_SELECTION_SIZE:MAX_BUILD_ITEM_COUNT],
        'item_ids': selected_item_ids[:MAX_BUILD_ITEM_COUNT],
        'esper_card_ids': selected_esper_ids[:MAX_BUILD_ESPER_COUNT],
    }
    build = upsert_build(player, leader_id, build_payload)
    return {
        'ok': True,
        'build': normalize_build_payload({
            'character_id': build.character_id,
            **build_payload,
            'updated_at': build.updated_at.isoformat(),
        }),
    }


def normalize_build_payload(build: JsonDict) -> JsonDict:
    starter_ids = _known_card_ids(build.get('starter_item_ids', []), card_type=CARD_TYPE_ANOMALY_ITEM)
    reserve_ids = _known_card_ids(build.get('reserve_item_ids', []), card_type=CARD_TYPE_ANOMALY_ITEM)
    item_ids = _known_card_ids(build.get('item_ids', []), card_type=CARD_TYPE_ANOMALY_ITEM)
    esper_ids = _unique_known_ids(build.get('esper_card_ids', []))
    if not starter_ids and not reserve_ids:
        starter_ids = item_ids[:OPENING_SELECTION_SIZE]
        reserve_ids = item_ids[OPENING_SELECTION_SIZE:MAX_BUILD_ITEM_COUNT]
    starter_ids = _sort_card_ids(starter_ids)[:OPENING_SELECTION_SIZE]
    reserve_ids = _sort_card_ids(reserve_ids)[:MAX_BUILD_ITEM_COUNT - OPENING_SELECTION_SIZE]
    item_ids = [*starter_ids, *reserve_ids][:MAX_BUILD_ITEM_COUNT]
    legacy_espers = [card_id for card_id in item_ids if _card_type(card_id) == CARD_TYPE_ESPER]
    esper_ids = _unique_ids([*esper_ids, *legacy_espers])
    return {
        'character_id': str(build.get('character_id') or ''),
        'item_ids': item_ids,
        'starter_item_ids': starter_ids[:OPENING_SELECTION_SIZE],
        'reserve_item_ids': reserve_ids[:MAX_BUILD_ITEM_COUNT - OPENING_SELECTION_SIZE],
        'esper_card_ids': [card_id for card_id in esper_ids if _card_type(card_id) == CARD_TYPE_ESPER][:MAX_BUILD_ESPER_COUNT],
        'updated_at': build.get('updated_at'),
    }


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
        return _public_state(snapshot, room, actor)

    members = list_room_members(room)
    if room.mode == 'duo' and len(members) < 2:
        raise RuleValidationError('未来 1v1 房间需要两名玩家都进入后才能开始。')

    snapshot = _create_initial_snapshot(room, members, options)
    with atomic_transaction():
        upsert_run(room, GAME_ID, snapshot['status'], snapshot)
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
    return _public_state(snapshot, room, player)


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
    if len(location['cards'][side]) >= LOCATION_CARD_LIMIT:
        raise RuleValidationError('这个空间已满。')
    hand = snapshot['sides'][side]['hand']
    card = _find_card_in_zone(hand, str(card_instance_id), '手牌中没有这张牌。')
    delay_tax = _delay_tax(snapshot, side, location)
    cost = _effective_cost(card) + delay_tax
    if cost > _energy_remaining(snapshot, side):
        raise RuleValidationError('能量不足。')
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
    target_rule = _target_rule(card)
    if target_rule:
        snapshot['sides'][side]['pending_target'] = {
            'source_instance_id': card['instance_id'],
            'location_id': location['id'],
            'scope': target_rule.get('scope', ''),
            'prompt': target_rule.get('prompt', '请选择一个目标。'),
        }
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
    target_rule = _target_rule(card)
    if target_rule:
        snapshot['sides'][side]['pending_target'] = {
            'source_instance_id': card['instance_id'],
            'location_id': location['id'],
            'scope': target_rule.get('scope', ''),
            'prompt': target_rule.get('prompt', '请选择一个目标。'),
        }
        _add_log(snapshot, f"{card['name']} 等待选择目标。")
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
    elif len(target_location['cards'][side]) >= LOCATION_CARD_LIMIT:
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
    target = _find_target_card(snapshot, side, source_location, str(target_instance_id), str(pending.get('scope', '')))
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


def _create_initial_snapshot(room: Room, members: list[Any], options: JsonDict | None = None) -> JsonDict:
    options = options or {}
    host_member = next((member for member in members if member.is_host), members[0] if members else None)
    if host_member is None:
        raise RuleValidationError('房间缺少玩家。')
    guest_member = next((member for member in members if member.player_id != host_member.player_id), None)
    scenario = _normalize_scenario(options.get('scenario'))
    player_deck_id = str(options.get('player_deck_id') or '').strip()
    enemy_deck_id = str(options.get('enemy_deck_id') or '').strip()
    if scenario == 'tutorial':
        player_deck_id = player_deck_id or 'genesis_bloom'
        enemy_deck_id = enemy_deck_id or 'murk_burn'
    elif scenario == 'trial':
        player_deck_id = player_deck_id or default_duel_deck_id()
        enemy_deck_id = enemy_deck_id or player_deck_id
    elif scenario == 'random_ai':
        enemy_deck_id = enemy_deck_id or 'random'

    host_side = _build_side(host_member.player, SIDE_A, is_ai=False, deck_id=player_deck_id)
    if room.mode == 'solo':
        opponent_side = _build_ai_side(enemy_deck_id)
    elif guest_member is not None:
        opponent_side = _build_side(guest_member.player, SIDE_B, is_ai=False, deck_id='')
    else:
        raise RuleValidationError('未来 1v1 房间需要两名玩家都进入后才能开始。')

    snapshot: JsonDict = {
        'schema_version': SCHEMA_VERSION,
        'game_id': GAME_ID,
        'mode': room.mode,
        'scenario': scenario,
        'scenario_label': _scenario_label(scenario),
        'status': 'playing',
        'phase': 'planning',
        'turn': 1,
        'max_turns': 4 if scenario == 'tutorial' else MAX_TURNS,
        'locations': _initial_locations(),
        'sides': {
            SIDE_A: host_side,
            SIDE_B: opponent_side,
        },
        'winner_side': None,
        'log': [],
        'action_queue': [],
        'banner_queue': [{'kind': 'turn', 'title': '第 1 回合', 'subtitle': '双方开始置入'}],
        'play_sequence_counter': 0,
        'turn_undo_checkpoints': {},
    }
    _reveal_locations_for_turn(snapshot)
    _sync_planning_phase(snapshot)
    _recompute_scores(snapshot)
    _lock_settlement_initiative(snapshot, emit_action=False)
    _add_log(snapshot, '主战场显现，首发手牌已按构筑载入。')
    return snapshot


def _build_side(player: Player, side: str, *, is_ai: bool, deck_id: str = '') -> JsonDict:
    deck_card_ids, esper_card_ids, deck_payload = _deck_card_ids_for_player(player, deck_id)
    hand, deck = _build_hand_and_deck_instances(deck_card_ids, side, deck_payload)
    esper_standby = _build_deck_instances(esper_card_ids, side, prefix='esper')
    return {
        'side': side,
        'uid': player.player_uid,
        'nickname': player.nickname or player.player_uid,
        'is_ai': is_ai,
        'deck_id': deck_payload['id'],
        'deck_name': deck_payload['name'],
        'deck_description': deck_payload.get('description', ''),
        'ai_plan': deepcopy(deck_payload.get('ai_plan', {})),
        'deck': deck,
        'hand': hand,
        'esper_standby': esper_standby,
        'discard': [],
        'selection': None,
        'pending_target': None,
        'combo': {},
        'energy_used': 0,
        'ended_turn': False,
    }


def _build_ai_side(deck_id: str = '') -> JsonDict:
    deck_payload = _resolve_deck_payload(deck_id or default_duel_deck_id())
    hand, deck = _build_hand_and_deck_instances(deck_payload['card_ids'], SIDE_B, deck_payload)
    esper_standby = _build_deck_instances(_esper_ids_for_deck_payload(deck_payload), SIDE_B, prefix='esper')
    return {
        'side': SIDE_B,
        'uid': 'ai',
        'nickname': deck_payload.get('ai_nickname') or '幻象对手',
        'is_ai': True,
        'deck_id': deck_payload['id'],
        'deck_name': deck_payload['name'],
        'deck_description': deck_payload.get('description', ''),
        'ai_plan': deepcopy(deck_payload.get('ai_plan', {})),
        'deck': deck,
        'hand': hand,
        'esper_standby': esper_standby,
        'discard': [],
        'selection': None,
        'pending_target': None,
        'combo': {},
        'energy_used': 0,
        'ended_turn': False,
    }


def _deck_card_ids_for_player(player: Player, deck_id: str = '') -> tuple[list[str], list[str], JsonDict]:
    if deck_id:
        deck_payload = _resolve_deck_payload(deck_id)
        return list(deck_payload['card_ids']), _esper_ids_for_deck_payload(deck_payload), deck_payload

    build = get_build(player)
    normalized_build = normalize_build_payload(build or {})
    selected_ids = [
        card_id
        for card_id in normalized_build.get('item_ids', [])
        if card_id in _card_by_id() and _card_type(card_id) == CARD_TYPE_ANOMALY_ITEM
    ]
    selected_esper_ids = [
        card_id
        for card_id in normalized_build.get('esper_card_ids', [])
        if card_id in _card_by_id() and _card_type(card_id) == CARD_TYPE_ESPER
    ]
    default_deck = _resolve_deck_payload(default_duel_deck_id())
    default_ids = list(default_deck['card_ids'])
    default_esper_ids = _esper_ids_for_deck_payload(default_deck)
    if selected_ids:
        is_valid, _ = validate_duel_deck_card_ids(selected_ids)
        if is_valid and len(selected_ids) >= MIN_BUILD_ITEM_COUNT:
            return selected_ids[:MAX_BUILD_ITEM_COUNT], (selected_esper_ids or default_esper_ids)[:MAX_BUILD_ESPER_COUNT], {
                'id': 'custom',
                'name': '自建牌组',
                'description': '玩家保存的异象对决构筑。',
                'card_ids': selected_ids[:MAX_BUILD_ITEM_COUNT],
                'esper_card_ids': (selected_esper_ids or default_esper_ids)[:MAX_BUILD_ESPER_COUNT],
                'ai_plan': {},
            }
    filled = selected_ids[:]
    for card_id in default_ids:
        if card_id not in filled:
            filled.append(card_id)
        if len(filled) >= MAX_BUILD_ITEM_COUNT:
            break
    is_valid, _ = validate_duel_deck_card_ids(filled)
    if not is_valid or len(filled) < MAX_BUILD_ITEM_COUNT:
        filled = default_ids[:MAX_BUILD_ITEM_COUNT]
    resolved_esper_ids = (selected_esper_ids or default_esper_ids)[:MAX_BUILD_ESPER_COUNT]
    return filled[:MAX_BUILD_ITEM_COUNT], resolved_esper_ids, {
        'id': 'custom' if selected_ids else default_deck['id'],
        'name': '自建牌组' if selected_ids else default_deck['name'],
        'description': '玩家保存的异象对决构筑。' if selected_ids else default_deck.get('description', ''),
        'card_ids': filled[:MAX_BUILD_ITEM_COUNT],
        'esper_card_ids': resolved_esper_ids,
        'ai_plan': default_deck.get('ai_plan', {}),
    }


def _build_deck_instances(card_ids: list[str], side: str, *, prefix: str = 'deck') -> list[JsonDict]:
    deck = []
    for index, card_id in enumerate(card_ids):
        definition = _card_by_id()[card_id]
        deck.append(_card_instance(definition, side, f'{prefix}-{side}-{index + 1:02d}'))
    return deck


def _build_hand_and_deck_instances(card_ids: list[str], side: str, deck_payload: JsonDict) -> tuple[list[JsonDict], list[JsonDict]]:
    starter_ids = _starter_card_ids(card_ids, deck_payload)
    ordered_ids = starter_ids + _remaining_card_ids_after_consuming(card_ids, starter_ids)
    instances = _build_deck_instances(ordered_ids[:MAX_BUILD_ITEM_COUNT], side)
    hand = instances[:OPENING_SELECTION_SIZE]
    deck = instances[OPENING_SELECTION_SIZE:]
    random.shuffle(deck)
    return hand, deck


def _starter_card_ids(card_ids: list[str], deck_payload: JsonDict) -> list[str]:
    planned_ids = [
        str(card_id)
        for card_id in [
            *deck_payload.get('starter_card_ids', []),
            *deck_payload.get('ai_plan', {}).get('opening_card_ids', []),
        ]
    ]
    available = _card_count_bucket(card_ids)
    starters: list[str] = []
    for card_id in planned_ids:
        if int(available.get(card_id, 0)) > 0:
            starters.append(card_id)
            available[card_id] = int(available.get(card_id, 0)) - 1
        if len(starters) >= OPENING_SELECTION_SIZE:
            return starters
    for card_id in card_ids:
        if int(available.get(card_id, 0)) > 0:
            starters.append(card_id)
            available[card_id] = int(available.get(card_id, 0)) - 1
        if len(starters) >= OPENING_SELECTION_SIZE:
            break
    return starters


def _card_instance(definition: JsonDict, side: str, suffix: str) -> JsonDict:
    return {
        'instance_id': f'{definition["id"]}-{suffix}',
        'definition_id': definition['id'],
        'name': definition['name'],
        'type': definition.get('type', 'esper'),
        'cost': int(definition['cost']),
        'cost_modifier': 0,
        'base_power': int(definition['power']),
        'bonus_power': 0,
        'computed_power': int(definition['power']),
        'element': definition.get('element', ''),
        'rarity': definition.get('rarity', 'n'),
        'art': definition.get('art', CARD_BACK_IMAGE),
        'description': definition.get('description', ''),
        'archetype': definition.get('archetype', ''),
        'category': definition.get('category', ''),
        'attribute': definition.get('attribute', ''),
        'attribute_icon': definition.get('attribute_icon', ''),
        'material_tags': list(definition.get('material_tags', [])),
        'material_cost': int(definition.get('material_cost') or 0),
        'required_material_attribute': definition.get('required_material_attribute', ''),
        'material_requirements': deepcopy(definition.get('material_requirements') or []),
        'material_requirement_text': definition.get('material_requirement_text', ''),
        'side': side,
        'revealed': False,
        'played_turn': None,
        'location_id': None,
        'tags': list(definition.get('tags', [])),
    }


def _initial_locations() -> list[JsonDict]:
    trait = deepcopy(random.choice(BATTLEFIELD_TRAITS))
    return [{
        'id': 'main_battlefield',
        'trait_id': trait['id'],
        'name': f"主战场：{trait['name']}",
        'short_name': '主战场',
        'description': trait['description'],
        'art': trait['art'],
        'reveal_turn': 1,
        'effect': trait['effect'],
        'revealed': False,
        'cards': {SIDE_A: [], SIDE_B: []},
        'marks': {SIDE_A: {}, SIDE_B: {}},
        'power': {SIDE_A: 0, SIDE_B: 0},
        'winner_side': None,
    }]


def _normalize_scenario(value: object) -> str:
    scenario = str(value or 'standard').strip().lower()
    if scenario in {'tutorial', 'trial', 'standard', 'random_ai'}:
        return scenario
    return 'standard'


def _scenario_label(scenario: object) -> str:
    normalized = _normalize_scenario(scenario)
    if normalized == 'tutorial':
        return '新手教学关'
    if normalized == 'trial':
        return '套牌试用关'
    if normalized == 'random_ai':
        return '随机人机对局'
    return '标准单人对局'


def _resolve_deck_payload(deck_id: str) -> JsonDict:
    if str(deck_id or '').strip() == 'random':
        decks = load_duel_decks()
        if not decks:
            raise RuleValidationError('当前没有可用的人机套牌。')
        return deepcopy(random.choice(decks))
    deck = get_duel_deck(deck_id) or get_duel_deck(default_duel_deck_id())
    if deck is None:
        raise RuleValidationError('当前没有可用的试用套牌。')
    card_ids = [str(card_id) for card_id in deck.get('card_ids', [])]
    if len(card_ids) < MIN_BUILD_ITEM_COUNT or len(card_ids) > MAX_BUILD_ITEM_COUNT:
        raise RuleValidationError(f"{deck.get('name', '套牌')} 必须配置 {MIN_BUILD_ITEM_COUNT} 到 {MAX_BUILD_ITEM_COUNT} 张牌。")
    for card_id in card_ids:
        if _card_type(card_id) != CARD_TYPE_ANOMALY_ITEM:
            raise RuleValidationError(f"{deck.get('name', '套牌')} 的牌组区域只能配置异象道具。")
    esper_ids = _esper_ids_for_deck_payload(deck)
    is_valid, validation_error = validate_duel_deck_card_ids([*card_ids, *esper_ids])
    if not is_valid:
        raise RuleValidationError(f"{deck.get('name', '套牌')} 配置非法：{validation_error}")
    return deck


def _esper_ids_for_deck_payload(deck_payload: JsonDict) -> list[str]:
    return [
        card_id
        for card_id in _unique_known_ids(deck_payload.get('esper_card_ids', []))
        if _card_type(card_id) == CARD_TYPE_ESPER
    ][:MAX_BUILD_ESPER_COUNT]


def _prepare_draw_selection(snapshot: JsonDict, side: str) -> None:
    snapshot['sides'][side]['selection'] = None
    _draw_cards(snapshot, side, 1, reason='回合补牌')


def _resolve_draw_selection(snapshot: JsonDict, side: str, selected_ids: list[str]) -> None:
    _resolve_legacy_draw_selection_as_auto_draw(snapshot, side)


def _resolve_legacy_draw_selection_as_auto_draw(snapshot: JsonDict, side: str) -> bool:
    side_state = snapshot['sides'][side]
    selection = side_state.get('selection') or {}
    if selection.get('kind') != 'draw':
        return False
    side_state['selection'] = None
    _draw_cards(snapshot, side, 1, reason='回合补牌')
    return True


def _clear_legacy_draw_selections(snapshot: JsonDict, *, auto_draw: bool = False) -> bool:
    changed = False
    for side in SIDE_KEYS:
        selection = snapshot['sides'][side].get('selection') or {}
        if selection.get('kind') != 'draw':
            continue
        if auto_draw:
            changed = _resolve_legacy_draw_selection_as_auto_draw(snapshot, side) or changed
        else:
            snapshot['sides'][side]['selection'] = None
            changed = True
    return changed


def _resolve_ai_pending_choices(snapshot: JsonDict, side: str) -> None:
    while snapshot['sides'][side].get('selection'):
        selection = snapshot['sides'][side]['selection']
        if selection.get('kind') == 'draw':
            _resolve_legacy_draw_selection_as_auto_draw(snapshot, side)
        elif selection.get('kind') == 'declaration':
            selected_ids = _ai_selection_ids(snapshot['sides'][side], selection)
            _resolve_declaration_selection(snapshot, side, selected_ids)
        else:
            selected_ids = _ai_selection_ids(snapshot['sides'][side], selection)
            snapshot['sides'][side]['selection'] = None


def _ai_selection_ids(side_state: JsonDict, selection: JsonDict) -> list[str]:
    cards = list(selection.get('cards', []))
    priority = _ai_priority(side_state)
    cards.sort(
        key=lambda card: (
            priority.get(card.get('definition_id'), -99),
            int(card.get('cost', 0)),
            int(card.get('base_power', 0)),
        ),
        reverse=True,
    )
    pick_count = int(selection.get('pick_count', 1))
    return [card['instance_id'] for card in cards[:pick_count]]


def _ai_priority(side_state: JsonDict) -> dict[str, int]:
    priority_ids = list(side_state.get('ai_plan', {}).get('priority_card_ids', []))
    return {str(card_id): len(priority_ids) - index for index, card_id in enumerate(priority_ids)}


def _sync_planning_phase(snapshot: JsonDict) -> None:
    if snapshot['status'] != 'playing':
        return
    _clear_legacy_draw_selections(snapshot)
    snapshot['phase'] = 'selecting' if any(snapshot['sides'][side].get('selection') for side in SIDE_KEYS) else 'planning'


def _prepare_declaration_selection(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    selected_target: JsonDict | None = None,
) -> bool:
    if snapshot['sides'][side].get('selection'):
        return False
    candidates = _declaration_candidates(snapshot, side, card, selected_target)
    if not candidates:
        return False
    card_id = str(card.get('definition_id') or '')
    title = f"{card.get('name', '卡牌')} 检视牌库"
    description = '宣言 1 张合法卡牌；揭示时执行。'
    if card_id == 'genesis_urban_energy':
        description = '宣言 1 张饮料或食物；揭示时加入手牌。'
    elif card_id == 'genesis_chip_washer':
        description = '若目标为食物，宣言 1 张费用 1 以下的光、灵或相属性道具；揭示时加入手牌。'
    snapshot['sides'][side]['selection'] = {
        'kind': 'declaration',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'title': title,
        'description': description,
        'pick_count': 1,
        'min_count': 1,
        'max_count': 1,
        'cards': candidates,
    }
    return True


def _declaration_candidates(
    snapshot: JsonDict,
    side: str,
    card: JsonDict,
    selected_target: JsonDict | None = None,
) -> list[JsonDict]:
    definition_id = str(card.get('definition_id') or '')
    deck = list(snapshot['sides'][side].get('deck', []))
    if definition_id == 'genesis_urban_energy':
        return [
            item
            for item in deck
            if item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') in {'饮料', '食物'}
        ]
    if definition_id == 'genesis_chip_washer':
        target = selected_target or _find_card_on_board(snapshot, str(card.get('selected_target_instance_id') or ''))
        if not target or str(target.get('category') or '') != '食物':
            return []
        return [
            item
            for item in deck
            if (
                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                and int(item.get('cost') or 0) <= 1
                and str(item.get('attribute') or '') in {'光', '灵', '相'}
            )
        ]
    return []


def _resolve_declaration_selection(snapshot: JsonDict, side: str, selected_ids: list[str]) -> None:
    selection = snapshot['sides'][side].get('selection') or {}
    if selection.get('kind') != 'declaration':
        raise RuleValidationError('当前没有需要宣言的卡牌。')
    source_id = str(selection.get('source_instance_id') or '')
    source = _find_card_on_board(snapshot, source_id)
    if source is None:
        snapshot['sides'][side]['selection'] = None
        raise RuleValidationError('宣言来源已不在战场。')
    legal_ids = {str(card.get('instance_id') or '') for card in selection.get('cards', [])}
    pick_count = int(selection.get('pick_count') or 1)
    chosen: list[str] = []
    for card_id in selected_ids:
        if card_id in legal_ids and card_id not in chosen:
            chosen.append(card_id)
        if len(chosen) >= pick_count:
            break
    min_count = int(selection.get('min_count') or pick_count)
    if len(chosen) < min_count:
        raise RuleValidationError('请选择合法的宣言卡牌。')
    source['declared_card_instance_ids'] = chosen
    names = [
        str(card.get('name') or '卡牌')
        for card in selection.get('cards', [])
        if str(card.get('instance_id') or '') in set(chosen)
    ]
    source['declared_card_names'] = names
    snapshot['sides'][side]['selection'] = None
    _add_log(snapshot, f"{source['name']} 宣言了 {'、'.join(names) if names else '卡牌'}。")


def _next_play_sequence(snapshot: JsonDict) -> int:
    counter = int(snapshot.get('play_sequence_counter', 0)) + 1
    snapshot['play_sequence_counter'] = counter
    return counter


def _lock_settlement_initiative(snapshot: JsonDict, *, emit_action: bool = True) -> None:
    _recompute_scores(snapshot)
    totals = {side: _stable_total_power(snapshot, side) for side in SIDE_KEYS}
    if totals[SIDE_A] > totals[SIDE_B]:
        first_side = SIDE_A
        leader_side: str | None = SIDE_A
        reason = '战力领先'
    elif totals[SIDE_B] > totals[SIDE_A]:
        first_side = SIDE_B
        leader_side = SIDE_B
        reason = '战力领先'
    else:
        first_side = random.choice(list(SIDE_KEYS))
        leader_side = None
        reason = '战力持平，随机决定'
    snapshot['settlement'] = {
        'turn': int(snapshot.get('turn', 1)),
        'first_side': first_side,
        'leader_side': leader_side,
        'reason': reason,
        'totals': totals,
    }
    snapshot['settlement_first_side'] = first_side
    _add_log(snapshot, f"第 {snapshot.get('turn', 1)} 回合结算先手：{_side_name(snapshot, first_side)}（{reason}，{totals[SIDE_A]}-{totals[SIDE_B]}）。")
    if not emit_action:
        return
    snapshot.setdefault('action_queue', []).append({
        'kind': 'initiative_decided',
        'side': first_side,
        'leader_side': leader_side,
        'title': '结算先手',
        'subtitle': f"{_side_name(snapshot, first_side)} 先揭示（{totals[SIDE_A]}-{totals[SIDE_B]}）",
    })


def _stable_total_power(snapshot: JsonDict, side: str) -> int:
    return sum(int(location.get('power', {}).get(side, 0) or 0) for location in snapshot.get('locations', []))


def _begin_turn(snapshot: JsonDict) -> None:
    snapshot['turn_undo_checkpoints'] = {}
    _clear_legacy_draw_selections(snapshot)
    _reset_turn_flags(snapshot)
    _resolve_harmony_upkeep(snapshot)
    _sweep_broken_cards(snapshot)
    _recompute_scores(snapshot)
    _lock_settlement_initiative(snapshot, emit_action=False)
    for side in SIDE_KEYS:
        snapshot['sides'][side]['energy_used'] = 0
        snapshot['sides'][side]['ended_turn'] = False
        _draw_cards(snapshot, side, 1, reason='回合补牌')
    _sync_planning_phase(snapshot)


def _snapshot_for_turn_undo(snapshot: JsonDict) -> JsonDict:
    checkpoint = deepcopy(snapshot)
    checkpoint.pop('turn_undo_checkpoints', None)
    return checkpoint


def _turn_undo_checkpoint(snapshot: JsonDict, side: str) -> JsonDict | None:
    checkpoint = snapshot.get('turn_undo_checkpoints', {}).get(side)
    if not isinstance(checkpoint, dict):
        return None
    if int(checkpoint.get('turn') or 0) != int(snapshot.get('turn') or 0):
        return None
    return checkpoint


def _can_undo_turn(snapshot: JsonDict, side: str) -> bool:
    if snapshot.get('status') != 'playing' or snapshot.get('phase') != 'planning':
        return False
    if snapshot.get('sides', {}).get(side, {}).get('ended_turn'):
        return False
    return _turn_undo_checkpoint(snapshot, side) is not None


def _ensure_turn_undo_checkpoint(snapshot: JsonDict, side: str) -> None:
    if snapshot.get('status') != 'playing' or snapshot.get('phase') != 'planning':
        return
    if snapshot.get('sides', {}).get(side, {}).get('ended_turn'):
        return
    checkpoints = snapshot.setdefault('turn_undo_checkpoints', {})
    if _turn_undo_checkpoint(snapshot, side) is not None:
        return
    checkpoints[side] = {
        'turn': int(snapshot.get('turn') or 0),
        'snapshot': _snapshot_for_turn_undo(snapshot),
    }


def _restore_side_from_turn_undo(snapshot: JsonDict, side: str, restored_snapshot: JsonDict) -> None:
    snapshot['sides'][side] = deepcopy(restored_snapshot['sides'][side])
    restored_locations = {
        str(location.get('id')): location
        for location in restored_snapshot.get('locations', [])
    }
    for location in snapshot.get('locations', []):
        restored_location = restored_locations.get(str(location.get('id')))
        if restored_location is None:
            continue
        location.setdefault('cards', {})[side] = deepcopy(restored_location.get('cards', {}).get(side, []))
        current_marks = location.setdefault('marks', {})
        restored_marks = deepcopy(restored_location.get('marks', {}).get(side, {}))
        if restored_marks:
            current_marks[side] = restored_marks
        else:
            current_marks.pop(side, None)


def _reset_turn_flags(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in location.get('cards', {}).get(side, []):
                card.pop('moved_this_turn', None)
    for side in SIDE_KEYS:
        combo = snapshot['sides'][side].setdefault('combo', {})
        if combo.get('movement_locked_turn') != snapshot.get('turn'):
            combo.pop('movement_locked_turn', None)
        if combo.get('extension_tax') != snapshot.get('turn'):
            combo.pop('extension_tax', None)


def _location_mark_count(location: JsonDict, side: str, tag: str) -> int:
    return int(location.get('marks', {}).get(side, {}).get(tag, 0) or 0)


def _consume_location_mark(location: JsonDict, side: str, tag: str, amount: int = 1) -> int:
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    current = int(mark_bucket.get(tag, 0) or 0)
    consumed = min(current, max(0, amount))
    if consumed <= 0:
        return 0
    remaining = current - consumed
    if remaining:
        mark_bucket[tag] = remaining
    else:
        mark_bucket.pop(tag, None)
    return consumed


def _legacy_harmony_cards(location: JsonDict, side: str, tag: str) -> list[JsonDict]:
    return [
        card
        for card in list(location.get('cards', {}).get(side, []))
        if card.get('revealed') and tag in card.get('tags', []) and TAG_HARMONY in card.get('tags', [])
    ]


def _resolve_harmony_upkeep(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            _resolve_genesis_upkeep(snapshot, location, side)
            _resolve_murk_upkeep(snapshot, location, side)
            _resolve_darkstar_upkeep(snapshot, location, side)


def _resolve_genesis_upkeep(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    count = _location_mark_count(location, side, TAG_GENESIS)
    if count <= 0:
        return
    candidates = [
        card
        for card in location['cards'][side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    if not candidates:
        return
    target = random.choice(candidates)
    power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
    _boost_card(target, count, '创生')
    power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
    snapshot.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_location_id': location['id'],
        'target_instance_id': target['instance_id'],
        'title': '创生',
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} + {count} = {power_after}',
    })
    _add_log(snapshot, f"{location['name']} 的创生标记使 {target['name']} +{count} 战力。")


def _resolve_murk_upkeep(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    murk_count = _location_mark_count(location, side, TAG_MURK) + len(_legacy_harmony_cards(location, side, TAG_MURK))
    for _ in range(murk_count):
        candidates = [
            card
            for card in location['cards'][side]
            if card.get('revealed')
            and TAG_COLLAPSING not in card.get('tags', [])
            and card.get('type') != 'token'
        ]
        if not candidates:
            break
        non_negative = [
            card
            for card in candidates
            if int(card.get('computed_power', _raw_card_power(card))) >= 0
        ]
        target = max(non_negative or candidates, key=lambda item: int(item.get('computed_power', _raw_card_power(item))))
        power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
        _boost_card(target, -1, '浊燃')
        power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'target_instance_id': target['instance_id'],
            'title': '浊燃',
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} - 1 = {power_after}',
        })
        _add_log(snapshot, f"{location['name']} 的浊燃使 {target['name']} -1 战力。")


def _resolve_darkstar_upkeep(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    darkstar_count = _location_mark_count(location, side, TAG_DARKSTAR)
    legacy_darkstars = _legacy_harmony_cards(location, side, TAG_DARKSTAR)
    if darkstar_count <= 0 and not legacy_darkstars:
        return
    _consume_location_mark(location, side, TAG_DARKSTAR, darkstar_count)
    for darkstar in legacy_darkstars:
        _remove_board_card(snapshot, side, location, darkstar)
    amount = max(1, darkstar_count + len(legacy_darkstars))
    damage = min(2, amount) if int(snapshot.get('turn') or 0) < 5 else min(6, 2 * amount)
    targets = [
        card
        for card in location['cards'][side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    for target in targets:
        power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
        _boost_card(target, -damage, '黯星')
        power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'target_instance_id': target['instance_id'],
            'title': '黯星',
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} - {damage} = {power_after}',
        })
    removed_murk = _consume_location_mark(location, side, TAG_MURK, _location_mark_count(location, side, TAG_MURK))
    replaced = _collapse_remaining_murks(location, side)
    _add_log(snapshot, f"{location['name']} 的黯星标记爆发，使 {len(targets)} 张牌 -{damage} 战力，并清理 {removed_murk + replaced} 个浊燃。")


def _collapse_remaining_murks(location: JsonDict, side: str) -> int:
    replaced = 0
    for card in location['cards'][side]:
        if not card.get('revealed') or TAG_MURK not in card.get('tags', []) or TAG_HARMONY not in card.get('tags', []):
            continue
        current_power = int(card.get('computed_power', _raw_card_power(card)))
        card['definition_id'] = 'collapsing_card'
        card['name'] = '倾陷中的卡牌'
        card['type'] = 'token'
        card['cost'] = 0
        card['cost_modifier'] = 0
        card['base_power'] = current_power
        card['bonus_power'] = 0
        card['computed_power'] = current_power
        card['description'] = '被黯星封存后的卡牌，只保留当前战力，不再拥有持续型效果。'
        card['tags'] = ['token', TAG_COLLAPSING]
        replaced += 1
    return replaced


def _unique_ids(instance_ids: list[str]) -> list[str]:
    unique: list[str] = []
    for instance_id in instance_ids:
        if instance_id not in unique:
            unique.append(instance_id)
    return unique


def _unique_known_ids(card_ids: list[Any]) -> list[str]:
    unique: list[str] = []
    cards = _card_by_id()
    for raw_id in card_ids:
        card_id = str(raw_id).strip()
        if not card_id or card_id in unique or card_id not in cards:
            continue
        unique.append(card_id)
    return unique


def _known_card_ids(card_ids: list[Any], *, card_type: str = '') -> list[str]:
    cards = _card_by_id()
    known: list[str] = []
    for raw_id in card_ids:
        card_id = str(raw_id).strip()
        if not card_id or card_id not in cards:
            continue
        if card_type and _card_type(card_id) != card_type:
            continue
        known.append(card_id)
    return known


def _sort_card_ids(card_ids: list[str]) -> list[str]:
    return sorted(card_ids, key=_card_sort_key)


def _card_sort_key(card_id: str) -> tuple[int, int, int, str]:
    card = _card_by_id().get(str(card_id), {})
    attribute_order = {'灵': 0, '光': 1, '相': 2, '咒': 3, '暗': 4, '魂': 5}
    attribute = str(card.get('attribute') or card.get('required_material_attribute') or card.get('element') or '')
    cost = int(card.get('material_cost') or card.get('cost') or 0)
    power = int(card.get('power') or 0)
    return (attribute_order.get(attribute, 99), cost, power, str(card.get('name') or card_id))


def _card_count_bucket(card_ids: list[str]) -> dict[str, int]:
    bucket: dict[str, int] = {}
    for card_id in card_ids:
        bucket[card_id] = int(bucket.get(card_id, 0)) + 1
    return bucket


def _remaining_card_ids_after_consuming(card_ids: list[str], consumed_ids: list[str]) -> list[str]:
    remaining_consumed = _card_count_bucket(consumed_ids)
    rest: list[str] = []
    for card_id in card_ids:
        if int(remaining_consumed.get(card_id, 0)) > 0:
            remaining_consumed[card_id] = int(remaining_consumed.get(card_id, 0)) - 1
            continue
        rest.append(card_id)
    return rest


def _card_type(card_id: str) -> str:
    return str((_card_by_id().get(str(card_id)) or {}).get('type', ''))


def _validate_custom_build_sections(item_ids: list[str], esper_ids: list[str]) -> None:
    if len(item_ids) < MIN_BUILD_ITEM_COUNT or len(item_ids) > MAX_BUILD_ITEM_COUNT:
        raise RuleValidationError(f'构筑需要选择 {MIN_BUILD_ITEM_COUNT} 到 {MAX_BUILD_ITEM_COUNT} 张异象道具。')
    if len(esper_ids) > MAX_BUILD_ESPER_COUNT:
        raise RuleValidationError(f'异能者最多选择 {MAX_BUILD_ESPER_COUNT} 张。')
    copy_count = _card_count_bucket(item_ids)
    too_many = [card_id for card_id, count in copy_count.items() if count > MAX_COPIES_PER_ITEM_CARD]
    if too_many:
        raise RuleValidationError(f'同名异象道具最多携带 {MAX_COPIES_PER_ITEM_CARD} 张。')
    for card_id in item_ids:
        if _card_type(card_id) != CARD_TYPE_ANOMALY_ITEM:
            raise RuleValidationError('牌组区域只能放入异象道具。')
    for card_id in esper_ids:
        if _card_type(card_id) != CARD_TYPE_ESPER:
            raise RuleValidationError('异能者区域只能放入异能者卡牌。')


def _resolve_turn(snapshot: JsonDict) -> None:
    snapshot['phase'] = 'revealing'
    snapshot['banner_queue'] = []
    first_side = _settlement_first_side(snapshot)
    second_side = _opponent_side(first_side)
    snapshot['action_queue'] = [{
        'kind': 'reveal_phase_begin',
        'title': '揭示阶段开始',
        'subtitle': '双方覆盖卡牌进入结算。',
    }]
    _append_covered_card_messages(snapshot)
    _resolve_pending_material_consumption(snapshot)
    for side in (first_side, second_side):
        snapshot.setdefault('action_queue', []).append({
            'kind': 'reveal_side_begin',
            'side': side,
            'title': f"{_side_name(snapshot, side)} 揭示",
        })
        for location, card in _staged_cards_for_side(snapshot, side):
            _reveal_card(snapshot, side, location, card)
            _sweep_broken_cards(snapshot)
    _recompute_scores(snapshot)

    if snapshot['turn'] >= int(snapshot.get('max_turns', MAX_TURNS)):
        _finish_game(snapshot)
        return

    snapshot['turn'] += 1
    snapshot.setdefault('action_queue', []).append({
        'kind': 'turn_begin',
        'title': f'第 {snapshot["turn"]} 回合开始',
        'subtitle': f'获得 {_turn_energy(snapshot)} 点能量',
    })
    _begin_turn(snapshot)
    _reveal_locations_for_turn(snapshot)
    _recompute_scores(snapshot)
    _add_log(snapshot, f'第 {snapshot["turn"]} 回合开始，双方获得 {_turn_energy(snapshot)} 点能量。')


def _append_covered_card_messages(snapshot: JsonDict) -> None:
    for side in SIDE_KEYS:
        names = [card['name'] for _, card in _staged_cards_for_side(snapshot, side)]
        snapshot.setdefault('action_queue', []).append({
            'kind': 'message',
            'side': side,
            'title': f"{_side_name(snapshot, side)} 成功覆盖",
            'subtitle': '、'.join(names) if names else '没有覆盖新牌。',
        })


def _settlement_first_side(snapshot: JsonDict) -> str:
    first_side = str(snapshot.get('settlement', {}).get('first_side') or snapshot.get('settlement_first_side') or '')
    if first_side in SIDE_KEYS:
        return first_side
    _lock_settlement_initiative(snapshot, emit_action=False)
    return str(snapshot.get('settlement', {}).get('first_side') or SIDE_A)


def _staged_cards_for_side(snapshot: JsonDict, side: str) -> list[tuple[JsonDict, JsonDict]]:
    staged: list[tuple[int, int, int, JsonDict, JsonDict]] = []
    turn = int(snapshot.get('turn') or 0)
    for location_index, location in enumerate(snapshot.get('locations', [])):
        for card_index, card in enumerate(location.get('cards', {}).get(side, [])):
            if not card.get('revealed') and int(card.get('played_turn') or 0) == turn:
                sequence = int(card.get('play_sequence') or 0)
                staged.append((sequence if sequence > 0 else 10_000 + card_index, location_index, card_index, location, card))
    staged.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(location, card) for _, _, _, location, card in staged]


def _resolve_pending_material_consumption(snapshot: JsonDict) -> None:
    _sweep_broken_cards(snapshot)
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            espers = [
                card
                for card in list(location.get('cards', {}).get(side, []))
                if (
                    _is_pending_esper_entry(snapshot, card)
                    or _is_pending_esper_reactivation(snapshot, card)
                )
            ]
            for esper in espers:
                is_reactivation = _is_pending_esper_reactivation(snapshot, esper)
                material_ids = [str(card_id) for card_id in esper.get('pending_material_ids', [])]
                materials = [
                    card
                    for card in list(location['cards'][side])
                    if str(card.get('instance_id')) in material_ids and _is_valid_reserved_material(card, esper['instance_id'])
                ]
                required = _esper_material_cost(esper)
                if len(materials) < required:
                    _release_material_reservations(snapshot, side, esper['instance_id'])
                    if is_reactivation:
                        esper.pop('pending_material_ids', None)
                        esper.pop('reactivating_turn', None)
                        _add_log(snapshot, f"{esper['name']} 的共鸣素材不足，共鸣取消。")
                    else:
                        _add_log(snapshot, f"{esper['name']} 的素材不足，返回异能者编队。")
                        location['cards'][side].remove(esper)
                        _reset_esper_to_standby(snapshot, side, esper)
                    continue
                consumed_material_tags: list[str] = []
                consumed_material_names: list[str] = []
                consumed_material_attributes: list[str] = []
                absorbed_power = 0
                for material in materials[:required]:
                    material_power = _material_absorb_power(material)
                    absorbed_power += material_power
                    consumed_material_tags.extend(_material_tags_for_card(material))
                    consumed_material_names.append(str(material.get('name') or '素材'))
                    if _material_attribute(material):
                        consumed_material_attributes.append(_material_attribute(material))
                    snapshot.setdefault('action_queue', []).append({
                        'kind': 'consume_material',
                        'source_instance_id': material['instance_id'],
                        'target_instance_id': esper['instance_id'],
                        'location_id': location['id'],
                        'side': side,
                        'title': f"{material['name']} -> {esper['name']}",
                        'subtitle': f"吸收 {material_power} 战力",
                        'material_power': material_power,
                    })
                    _remove_board_card(snapshot, side, location, material)
                    _add_log(snapshot, f"{esper['name']} 消耗 {material['name']} 作为共鸣素材，吸收 {material_power} 战力。")
                if absorbed_power:
                    _boost_card(esper, absorbed_power, '素材吸收')
                if consumed_material_tags:
                    esper.setdefault('consumed_material_tags', [])
                    esper['consumed_material_tags'].extend(consumed_material_tags)
                if consumed_material_names:
                    esper.setdefault('consumed_material_names', [])
                    esper['consumed_material_names'].extend(consumed_material_names)
                if consumed_material_attributes:
                    esper.setdefault('consumed_material_attributes', [])
                    esper['consumed_material_attributes'].extend(consumed_material_attributes)
                esper['absorbed_material_power'] = int(esper.get('absorbed_material_power', 0)) + absorbed_power
                esper.pop('pending_material_ids', None)
                esper.pop('summoned_from', None)
                if is_reactivation:
                    esper.pop('reactivating_turn', None)
                    _resolve_esper_reactivation(snapshot, side, location, esper)
    _sweep_broken_cards(snapshot)


def _is_valid_reserved_material(card: JsonDict, esper_instance_id: str) -> bool:
    return _is_valid_esper_material({**card, 'reserved_as_material_for': ''}) and card.get('reserved_as_material_for') == esper_instance_id


def _is_pending_esper_entry(snapshot: JsonDict, card: JsonDict) -> bool:
    return bool(
        _is_staged_card(snapshot, card)
        and (card.get('summoned_from') == 'esper_standby' or card.get('type') == CARD_TYPE_ESPER)
    )


def _is_pending_esper_reactivation(snapshot: JsonDict, card: JsonDict) -> bool:
    return bool(
        card.get('type') == CARD_TYPE_ESPER
        and card.get('revealed')
        and int(card.get('reactivating_turn') or 0) == int(snapshot.get('turn', 0))
        and card.get('pending_material_ids')
    )


def _resolve_esper_reactivation(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    opponent = _opponent_side(side)
    logs_before_effect = list(snapshot.get('log', []))
    target_card = _find_card_on_board(snapshot, str(card.get('selected_target_instance_id', ''))) if card.get('selected_target_instance_id') else None
    power_before = _revealed_board_power_snapshot(snapshot)
    snapshot.setdefault('action_queue', []).append({
        'kind': 'esper_reactivation',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': f"{card['name']} 共鸣",
    })
    snapshot['_active_reveal_source_instance_id'] = card['instance_id']
    snapshot['_active_reveal_source_name'] = card['name']
    try:
        dispatch_event(snapshot, GameEvent.CARD_REVEALED, {
            'target_instance_id': card['instance_id'],
            'card_instance_id': card['instance_id'],
            'card': card,
            'side': side,
            'opponent_side': opponent,
            'location': location,
            'location_id': location['id'],
            'location_index': _location_index(snapshot, location['id']),
            'pre_location_gap': int(location['power'][side]) - int(location['power'][opponent]),
            'losing_locations_before': sum(1 for item in snapshot['locations'] if item.get('winner_side') == opponent),
            'selected_target_instance_id': card.get('selected_target_instance_id'),
            'target_card': target_card,
            'reactivated': True,
        })
    finally:
        snapshot.pop('_active_reveal_source_instance_id', None)
        snapshot.pop('_active_reveal_source_name', None)
    changed_ids = _append_power_change_arrows(snapshot, card['instance_id'], card['name'], power_before)
    if target_card is not None and target_card['instance_id'] not in changed_ids:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_instance_id': card['instance_id'],
            'target_instance_id': target_card['instance_id'],
            'title': card['name'],
        })
    effect_summary = _reveal_effect_summary(card['name'], _new_log_entries(snapshot, logs_before_effect))
    if effect_summary:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'effect_summary',
            'source_instance_id': card['instance_id'],
            'location_id': location['id'],
            'side': side,
            'title': card['name'],
            'effect_summary': effect_summary,
        })
    card.pop('selected_target_instance_id', None)
    card.pop('selected_target_name', None)


def _reset_esper_to_standby(snapshot: JsonDict, side: str, card: JsonDict) -> None:
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
    card.pop('summoned_from', None)
    card.pop('consumed_material_tags', None)
    card.pop('consumed_material_names', None)
    card.pop('consumed_material_attributes', None)
    card.pop('absorbed_material_power', None)
    card.pop('reactivating_turn', None)
    card.pop('reserved_as_material_for', None)
    _reset_card_stats_from_definition(card)
    snapshot['sides'][side].setdefault('esper_standby', []).append(card)


def _consume_reveal_bonus_charge(snapshot: JsonDict, location: JsonDict, side: str, *, limit: int) -> bool:
    turn = int(snapshot.get('turn') or 0)
    trait_uses = location.setdefault('trait_uses', {}).setdefault(side, {})
    if int(trait_uses.get('turn') or 0) != turn:
        trait_uses.clear()
        trait_uses['turn'] = turn
        trait_uses['count'] = 0
    count = int(trait_uses.get('count') or 0)
    if count >= limit:
        return False
    trait_uses['count'] = count + 1
    return True


def _reveal_card(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    _recompute_scores(snapshot)
    opponent = _opponent_side(side)
    pre_location_gap = int(location['power'][side]) - int(location['power'][opponent])
    losing_locations_before = sum(1 for item in snapshot['locations'] if item.get('winner_side') == opponent)
    card['revealed'] = True
    card.pop('staged', None)
    _recompute_scores(snapshot)
    power_before = _revealed_board_power_snapshot(snapshot)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 揭示 {card['name']}。")
    reveal_action = {
        'kind': 'reveal_card',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': card['name'],
        'card': _public_card(card, own=True),
    }
    snapshot.setdefault('action_queue', []).append(reveal_action)
    logs_before_effect = list(snapshot.get('log', []))
    target_card = _find_card_on_board(snapshot, str(card.get('selected_target_instance_id', ''))) if card.get('selected_target_instance_id') else None
    snapshot['_active_reveal_source_instance_id'] = card['instance_id']
    snapshot['_active_reveal_source_name'] = card['name']
    try:
        dispatch_event(snapshot, GameEvent.CARD_REVEALED, {
            'target_instance_id': card['instance_id'],
            'card_instance_id': card['instance_id'],
            'card': card,
            'side': side,
            'opponent_side': opponent,
            'location': location,
            'location_id': location['id'],
            'location_index': _location_index(snapshot, location['id']),
            'pre_location_gap': pre_location_gap,
            'losing_locations_before': losing_locations_before,
            'selected_target_instance_id': card.get('selected_target_instance_id'),
            'target_card': target_card,
        })
    finally:
        snapshot.pop('_active_reveal_source_instance_id', None)
        snapshot.pop('_active_reveal_source_name', None)
    changed_ids = _append_power_change_arrows(snapshot, card['instance_id'], card['name'], power_before)
    if target_card is not None and target_card['instance_id'] not in changed_ids:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_instance_id': card['instance_id'],
            'target_instance_id': target_card['instance_id'],
            'title': card['name'],
        })
    if (
        location['effect'] == 'revealed_cards_plus_one'
        and pre_location_gap <= 0
        and _consume_reveal_bonus_charge(snapshot, location, side, limit=3)
    ):
        power_before = int(card.get('computed_power', _raw_card_power(card)) or 0)
        card['bonus_power'] += 1
        _add_buff_source(card, location['name'], 1)
        _recompute_scores(snapshot)
        power_after = int(card.get('computed_power', _raw_card_power(card)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'target_instance_id': card['instance_id'],
            'title': location['name'],
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} + 1 = {power_after}',
        })
        _add_log(snapshot, f"{location['name']} 的潮汐让 {card['name']} +1 战力。")
    _vanish_revealed_card_if_needed(snapshot, side, location, card)
    effect_summary = _reveal_effect_summary(card['name'], _new_log_entries(snapshot, logs_before_effect))
    if effect_summary:
        reveal_action['effect_summary'] = effect_summary
    _sweep_broken_cards(snapshot)
    _recompute_scores(snapshot)


def _revealed_board_power_snapshot(snapshot: JsonDict) -> dict[str, int]:
    powers: dict[str, int] = {}
    _recompute_scores(snapshot)
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in location.get('cards', {}).get(side, []):
                if card.get('revealed'):
                    powers[str(card.get('instance_id'))] = int(card.get('computed_power', _raw_card_power(card)) or 0)
    return powers


def _append_power_change_arrows(
    snapshot: JsonDict,
    source_instance_id: str,
    source_name: str,
    power_before: dict[str, int],
) -> set[str]:
    changed_ids: set[str] = set()
    _recompute_scores(snapshot)
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in location.get('cards', {}).get(side, []):
                target_id = str(card.get('instance_id') or '')
                if not target_id or target_id == source_instance_id or not card.get('revealed'):
                    continue
                if target_id not in power_before:
                    continue
                current_power = int(card.get('computed_power', _raw_card_power(card)) or 0)
                if current_power == power_before[target_id]:
                    continue
                changed_ids.add(target_id)
                snapshot.setdefault('action_queue', []).append({
                    'kind': 'impact_arrow',
                    'source_instance_id': source_instance_id,
                    'target_instance_id': target_id,
                    'title': source_name,
                    'power_before': power_before[target_id],
                    'power_after': current_power,
                    'power_delta': current_power - power_before[target_id],
                    'subtitle': f"{power_before[target_id]} {'+' if current_power > power_before[target_id] else '-'} {abs(current_power - power_before[target_id])} = {current_power}",
                })
    return changed_ids


def _run_ai_turn(snapshot: JsonDict, side: str) -> None:
    _resolve_ai_pending_choices(snapshot, side)
    if snapshot['sides'][side]['ended_turn']:
        return
    playable = True
    while playable:
        playable = _ai_play_one_card(snapshot, side)
    esper_playable = True
    while esper_playable:
        esper_playable = _ai_play_one_esper(snapshot, side)
    esper_reactivated = True
    while esper_reactivated:
        esper_reactivated = _ai_reactivate_one_esper(snapshot, side)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 完成置入。")


def _ai_play_one_card(snapshot: JsonDict, side: str) -> bool:
    hand = snapshot['sides'][side]['hand']
    energy_remaining = _energy_remaining(snapshot, side)
    open_locations = _open_locations(snapshot, side)
    options: list[tuple[JsonDict, JsonDict, int]] = []
    for card in hand:
        for location in open_locations:
            cost = _cost_to_play(snapshot, side, card, location)
            if cost <= energy_remaining:
                options.append((card, location, cost))
    if not options:
        return False
    priority = _ai_priority(snapshot['sides'][side])
    opponent = _opponent_side(side)
    _recompute_scores(snapshot)
    options.sort(
        key=lambda option: (
            priority.get(option[0].get('definition_id'), -99),
            option[1]['power'][opponent] - option[1]['power'][side],
            _raw_card_power(option[0]),
            -int(option[2]),
        ),
        reverse=True,
    )
    card, location, cost = options[0]
    hand.remove(card)
    card['played_turn'] = snapshot['turn']
    card['location_id'] = location['id']
    card['revealed'] = False
    card['staged'] = True
    card['paid_cost'] = cost
    card['play_sequence'] = _next_play_sequence(snapshot)
    snapshot['sides'][side]['energy_used'] += cost
    location['cards'][side].append(card)
    if _delay_tax(snapshot, side, location):
        _consume_delay_tax(snapshot, side, location)
    target_rule = _target_rule(card)
    if target_rule:
        target = _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            _prepare_declaration_selection(snapshot, side, location, card, target)
            _resolve_ai_pending_choices(snapshot, side)
    else:
        _prepare_declaration_selection(snapshot, side, location, card)
        _resolve_ai_pending_choices(snapshot, side)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 将一张牌置入 {location['name']}。")
    return True


def _ai_play_one_esper(snapshot: JsonDict, side: str) -> bool:
    standby = snapshot['sides'][side].setdefault('esper_standby', [])
    if not standby:
        return False
    open_locations = [location for location in snapshot['locations'] if _is_location_revealed(snapshot, location)]
    options: list[tuple[JsonDict, JsonDict, list[JsonDict]]] = []
    for card in standby:
        for location in open_locations:
            try:
                material_cards = _material_cards_for_esper(snapshot, side, location, card)
            except RuleValidationError:
                continue
            if _location_has_room_after_materials(location, side, material_cards):
                options.append((card, location, material_cards))
    if not options:
        return False
    priority_ids = list(snapshot['sides'][side].get('ai_plan', {}).get('esper_priority_ids', []))
    priority = {str(card_id): len(priority_ids) - index for index, card_id in enumerate(priority_ids)}
    opponent = _opponent_side(side)
    _recompute_scores(snapshot)
    options.sort(
        key=lambda option: (
            priority.get(option[0].get('definition_id'), -99),
            option[1]['power'][opponent] - option[1]['power'][side],
            _raw_card_power(option[0]),
        ),
        reverse=True,
    )
    card, location, material_cards = options[0]
    standby.remove(card)
    material_ids = [item['instance_id'] for item in material_cards]
    _reserve_materials(material_cards, card['instance_id'])
    card['played_turn'] = snapshot['turn']
    card['location_id'] = location['id']
    card['revealed'] = False
    card['staged'] = True
    card['play_sequence'] = _next_play_sequence(snapshot)
    card['summoned_from'] = 'esper_standby'
    card['pending_material_ids'] = material_ids
    card['paid_cost'] = 0
    location['cards'][side].append(card)
    target_rule = _target_rule(card)
    if target_rule:
        target = _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            _prepare_declaration_selection(snapshot, side, location, card, target)
            _resolve_ai_pending_choices(snapshot, side)
    else:
        _prepare_declaration_selection(snapshot, side, location, card)
        _resolve_ai_pending_choices(snapshot, side)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 唤醒一名异能者于 {location['name']}。")
    return True


def _ai_reactivate_one_esper(snapshot: JsonDict, side: str) -> bool:
    if _side_reactivation_used(snapshot, side):
        return False
    revealed_espers: list[tuple[JsonDict, JsonDict, list[JsonDict]]] = []
    for location in snapshot['locations']:
        if not _is_location_revealed(snapshot, location):
            continue
        for card in location['cards'][side]:
            if (
                card.get('type') != CARD_TYPE_ESPER
                or not card.get('revealed')
                or card.get('pending_material_ids')
                or int(card.get('reactivating_turn') or 0) == int(snapshot.get('turn') or 0)
            ):
                continue
            try:
                material_cards = _material_cards_for_esper(snapshot, side, location, card)
            except RuleValidationError:
                continue
            revealed_espers.append((card, location, material_cards))
    if not revealed_espers:
        return False
    priority_ids = list(snapshot['sides'][side].get('ai_plan', {}).get('esper_priority_ids', []))
    priority = {str(card_id): len(priority_ids) - index for index, card_id in enumerate(priority_ids)}
    opponent = _opponent_side(side)
    _recompute_scores(snapshot)
    revealed_espers.sort(
        key=lambda option: (
            priority.get(option[0].get('definition_id'), -99),
            option[1]['power'][opponent] - option[1]['power'][side],
            _raw_card_power(option[0]),
        ),
        reverse=True,
    )
    card, location, material_cards = revealed_espers[0]
    material_ids = [item['instance_id'] for item in material_cards]
    _reserve_materials(material_cards, card['instance_id'])
    card['pending_material_ids'] = material_ids
    card['reactivating_turn'] = snapshot['turn']
    _mark_side_reactivation(snapshot, side)
    target_rule = _target_rule(card)
    if target_rule:
        target = _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            _prepare_declaration_selection(snapshot, side, location, card, target)
            _resolve_ai_pending_choices(snapshot, side)
    else:
        _prepare_declaration_selection(snapshot, side, location, card)
        _resolve_ai_pending_choices(snapshot, side)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 准备让 {card['name']} 再共鸣。")
    return True


def _side_reactivation_used(snapshot: JsonDict, side: str) -> bool:
    combo = snapshot['sides'][side].setdefault('combo', {})
    return int(combo.get('esper_reactivation_turn') or 0) == int(snapshot.get('turn') or 0)


def _mark_side_reactivation(snapshot: JsonDict, side: str) -> None:
    snapshot['sides'][side].setdefault('combo', {})['esper_reactivation_turn'] = int(snapshot.get('turn') or 0)


def _best_ai_location(snapshot: JsonDict, side: str, card: JsonDict) -> JsonDict | None:
    opponent = _opponent_side(side)
    options = _open_locations(snapshot, side)
    if not options:
        return None
    _recompute_scores(snapshot)
    options.sort(
        key=lambda location: (
            location['power'][opponent] - location['power'][side],
            -len(location['cards'][side]),
            location['id'],
        ),
        reverse=True,
    )
    return options[0]


def _ai_target_for_card(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    target_rule: JsonDict,
) -> JsonDict | None:
    scope = str(target_rule.get('scope', ''))
    candidates = _target_candidates(snapshot, side, location, scope)
    candidates = [candidate for candidate in candidates if candidate.get('instance_id') != card.get('instance_id')]
    if not candidates:
        return None
    if scope.startswith('opponent'):
        return max(candidates, key=lambda item: int(item.get('computed_power', item.get('base_power', 0)) or 0))
    return min(candidates, key=lambda item: int(item.get('computed_power', item.get('base_power', 0)) or 0))


def _finish_game(snapshot: JsonDict) -> None:
    _recompute_scores(snapshot)
    wins = {SIDE_A: 0, SIDE_B: 0}
    total_power = {SIDE_A: 0, SIDE_B: 0}
    for location in snapshot['locations']:
        total_power[SIDE_A] += location['power'][SIDE_A]
        total_power[SIDE_B] += location['power'][SIDE_B]
        if location['winner_side'] in SIDE_KEYS:
            wins[location['winner_side']] += 1
    if wins[SIDE_A] > wins[SIDE_B]:
        winner = SIDE_A
    elif wins[SIDE_B] > wins[SIDE_A]:
        winner = SIDE_B
    elif total_power[SIDE_A] > total_power[SIDE_B]:
        winner = SIDE_A
    elif total_power[SIDE_B] > total_power[SIDE_A]:
        winner = SIDE_B
    else:
        winner = None

    snapshot['winner_side'] = winner
    snapshot['phase'] = 'complete'
    if winner is None:
        snapshot['status'] = 'draw'
        _add_log(snapshot, '双方空间与总战力完全持平，对局平局。')
    elif winner == SIDE_A:
        snapshot['status'] = 'victory'
        _add_log(snapshot, f"{_side_name(snapshot, SIDE_A)} 赢下对局。")
    else:
        snapshot['status'] = 'defeat'
        _add_log(snapshot, f"{_side_name(snapshot, SIDE_B)} 赢下对局。")
    snapshot.setdefault('banner_queue', []).append({
        'kind': 'result',
        'title': '胜利' if snapshot['status'] == 'victory' else '失败' if snapshot['status'] == 'defeat' else '平局',
        'subtitle': '对局结束',
    })


def _reveal_locations_for_turn(snapshot: JsonDict) -> None:
    for location in snapshot['locations']:
        if not location['revealed'] and int(location['reveal_turn']) <= int(snapshot['turn']):
            location['revealed'] = True
            _add_log(snapshot, f"{location['name']} 显现：{location['description']}")


def _recompute_scores(snapshot: JsonDict) -> None:
    for location in snapshot['locations']:
        for side in SIDE_KEYS:
            revealed_cards = [card for card in location['cards'][side] if card.get('revealed')]
            for card in location['cards'][side]:
                card['computed_power'] = _raw_card_power(card) + _location_power_bonus(location, side, card)
            location['power'][side] = sum(int(card['computed_power']) for card in revealed_cards)
        if location['power'][SIDE_A] > location['power'][SIDE_B]:
            location['winner_side'] = SIDE_A
        elif location['power'][SIDE_B] > location['power'][SIDE_A]:
            location['winner_side'] = SIDE_B
        else:
            location['winner_side'] = None
    snapshot['turn_energy'] = _turn_energy(snapshot)


def _location_power_bonus(location: JsonDict, side: str, card: JsonDict) -> int:
    if not card.get('revealed'):
        return 0
    if location['effect'] == 'first_card_plus_two':
        revealed = [item for item in location['cards'][side] if item.get('revealed')]
        if revealed and revealed[0]['instance_id'] == card['instance_id']:
            _add_buff_source(card, location['name'], 2, replace_key=f'location:{location["id"]}')
            return 2
    if location['effect'] == 'solo_card_plus_four':
        revealed = [item for item in location['cards'][side] if item.get('revealed')]
        if len(revealed) == 1 and revealed[0]['instance_id'] == card['instance_id']:
            _add_buff_source(card, location['name'], 4, replace_key=f'location:{location["id"]}')
            return 4
    return 0


def _draw_cards(snapshot: JsonDict, side: str, count: int, *, reason: str = '抽牌') -> list[JsonDict]:
    drawn: list[JsonDict] = []
    for _ in range(count):
        if not snapshot['sides'][side]['deck'] or len(snapshot['sides'][side]['hand']) >= MAX_HAND_SIZE:
            break
        card = snapshot['sides'][side]['deck'].pop(0)
        snapshot['sides'][side]['hand'].append(card)
        drawn.append(card)
        action: JsonDict = {
            'kind': 'draw_card',
            'side': side,
            'card_instance_id': card['instance_id'],
            'title': reason,
            'subtitle': '从牌库加入手牌',
            'reason': reason,
            'silent': reason == '回合补牌',
            'card': _public_card(card, own=True),
        }
        source_instance_id = str(snapshot.get('_active_reveal_source_instance_id') or '')
        if source_instance_id:
            action['source_instance_id'] = source_instance_id
        snapshot.setdefault('action_queue', []).append(action)
        _add_log(snapshot, f"{_side_name(snapshot, side)} 从牌库抽取 1 张牌。")
    return drawn


def _public_state(snapshot: JsonDict, room: Room, viewer: Player) -> JsonDict:
    _clear_legacy_draw_selections(snapshot, auto_draw=True)
    _sync_planning_phase(snapshot)
    perspective = _perspective_for_player(snapshot, viewer)
    own = snapshot['sides'][perspective.own]
    opponent = snapshot['sides'][perspective.opponent]
    public_status = _public_status(snapshot, perspective.own)
    room_payload = serialize_room(room, list_room_members(room))
    room_payload['status'] = public_status if public_status in {'victory', 'defeat', 'draw'} else room.status
    return {
        'schema_version': snapshot['schema_version'],
        'game_id': snapshot['game_id'],
        'mode': snapshot['mode'],
        'scenario': snapshot.get('scenario', 'standard'),
        'scenario_label': snapshot.get('scenario_label', _scenario_label(snapshot.get('scenario'))),
        'status': public_status,
        'phase': _public_phase(snapshot, perspective.own),
        'turn': snapshot['turn'],
        'max_turns': snapshot['max_turns'],
        'turn_energy': _turn_energy(snapshot),
        'energy_remaining': _energy_remaining(snapshot, perspective.own),
        'can_undo_turn': _can_undo_turn(snapshot, perspective.own),
        'room': room_payload,
        'player_seat': perspective.own,
        'opponent_seat': perspective.opponent,
        'current_actor_uid': own['uid'] if not own.get('ended_turn') else opponent['uid'],
        'player': _public_side(own, reveal_hand=True),
        'opponent': _public_side(opponent, reveal_hand=False),
        'selection': _public_selection(own),
        'pending_target': _public_pending_target(own),
        'players_overview': [_side_overview(snapshot['sides'][side]) for side in SIDE_KEYS],
        'locations': [_public_location(location, perspective) for location in snapshot['locations']],
        'score': _public_score(snapshot, perspective),
        'initiative': _public_initiative(snapshot, perspective),
        'winner': _public_winner(snapshot, perspective),
        'route_hint': _route_hint(snapshot, perspective.own),
        'log': _public_log(snapshot, perspective),
        'action_queue': list(snapshot.get('action_queue', [])),
        'banner_queue': list(snapshot.get('banner_queue', [])),
    }


def _public_side(side: JsonDict, *, reveal_hand: bool) -> JsonDict:
    return {
        'uid': side['uid'],
        'nickname': side['nickname'],
        'is_ai': side['is_ai'],
        'deck_id': side.get('deck_id', ''),
        'deck_name': side.get('deck_name', ''),
        'deck_description': side.get('deck_description', ''),
        'energy_used': side['energy_used'],
        'ended_turn': side['ended_turn'],
        'deck_count': len(side['deck']),
        'hand_count': len(side['hand']),
        'discard_count': len(side.get('discard', [])),
        'esper_standby_count': len(side.get('esper_standby', [])),
        'combo': deepcopy(side.get('combo', {})),
        'pending_target': _public_pending_target(side),
        'hand': [_public_card(card, own=True) for card in side['hand']] if reveal_hand else [_public_hidden_hand_card(card) for card in side['hand']],
        'esper_standby': [_public_card(card, own=True) for card in side.get('esper_standby', [])] if reveal_hand else [],
        'discard': [_public_card(card, own=True) for card in side.get('discard', [])],
    }


def _public_hidden_hand_card(card: JsonDict) -> JsonDict:
    return {
        'instance_id': card['instance_id'],
        'hidden': True,
        'revealed': False,
        'staged': False,
        'name': '对手手牌',
        'cost': None,
        'base_cost': None,
        'original_cost': None,
        'power': None,
        'base_power': None,
        'original_power': None,
        'art': CARD_BACK_IMAGE,
        'description': '对手手牌，内容不可见。',
        'type': card.get('type', CARD_TYPE_ANOMALY_ITEM),
        'archetype': '',
        'category': '',
        'attribute': '',
        'attribute_icon': '',
        'material_cost': 0,
        'required_material_attribute': '',
        'material_tags': [],
        'buff_sources': [],
    }


def _public_log(snapshot: JsonDict, perspective: SidePerspective) -> list[str]:
    own_name = _side_name(snapshot, perspective.own)
    opponent_name = _side_name(snapshot, perspective.opponent)
    lines: list[str] = []
    for line in snapshot.get('log', []):
        public_line = str(line)
        if own_name:
            public_line = public_line.replace(own_name, '我')
        if opponent_name:
            public_line = public_line.replace(opponent_name, '对手')
        lines.append(public_line)
    return lines


def _public_selection(side: JsonDict) -> JsonDict | None:
    selection = side.get('selection')
    if not selection:
        return None
    if selection.get('kind') == 'draw':
        return None
    return {
        'kind': selection.get('kind'),
        'title': selection.get('title', '选择卡牌'),
        'description': selection.get('description', ''),
        'pick_count': int(selection.get('pick_count', 1)),
        'min_count': int(selection.get('min_count', selection.get('pick_count', 1))),
        'max_count': int(selection.get('max_count', selection.get('pick_count', 1))),
        'cards': [_public_card(card, own=True) for card in selection.get('cards', [])],
    }


def _public_pending_target(side: JsonDict) -> JsonDict | None:
    pending = side.get('pending_target')
    if not pending:
        return None
    return {
        'source_instance_id': pending.get('source_instance_id'),
        'location_id': pending.get('location_id'),
        'scope': pending.get('scope', ''),
        'prompt': pending.get('prompt', '请选择一个目标。'),
    }


def _public_location(location: JsonDict, perspective: SidePerspective) -> JsonDict:
    own_cards = [_public_card(card, own=True) for card in location['cards'][perspective.own]]
    opponent_cards = [_public_card(card, own=False) for card in location['cards'][perspective.opponent]]
    winner_side = location.get('winner_side')
    if winner_side == perspective.own:
        winner = 'player'
    elif winner_side == perspective.opponent:
        winner = 'opponent'
    else:
        winner = 'tie'
    return {
        'id': location['id'],
        'name': location['name'] if location['revealed'] else '未显现异象',
        'short_name': location['short_name'] if location['revealed'] else '未知',
        'description': location['description'] if location['revealed'] else '将在后续回合显现规则。',
        'art': location['art'],
        'revealed': location['revealed'],
        'reveal_turn': location['reveal_turn'],
        'power': {
            'player': location['power'][perspective.own],
            'opponent': location['power'][perspective.opponent],
        },
        'marks': {
            'player': deepcopy(location.get('marks', {}).get(perspective.own, {})),
            'opponent': deepcopy(location.get('marks', {}).get(perspective.opponent, {})),
        },
        'winner': winner,
        'slots': {
            'player': own_cards,
            'opponent': opponent_cards,
        },
        'capacity': LOCATION_CARD_LIMIT,
    }


def _public_card(card: JsonDict, *, own: bool) -> JsonDict:
    if not own and not card.get('revealed'):
        return {
            'instance_id': card['instance_id'],
            'hidden': True,
            'revealed': False,
            'staged': bool(card.get('staged')),
            'name': '未揭示',
            'cost': None,
            'base_cost': None,
            'original_cost': None,
            'power': None,
            'base_power': None,
            'original_power': None,
            'art': CARD_BACK_IMAGE,
            'description': '对手本回合置入的牌，将在回合结束时揭示。',
            'type': card.get('type', 'esper'),
            'archetype': card.get('archetype', ''),
            'category': card.get('category', ''),
            'attribute': card.get('attribute', ''),
            'attribute_icon': card.get('attribute_icon', ''),
            'material_cost': card.get('material_cost', 0),
            'required_material_attribute': card.get('required_material_attribute', ''),
            'material_requirements': deepcopy(card.get('material_requirements') or []),
            'material_requirement_text': card.get('material_requirement_text', ''),
            'material_tags': list(card.get('material_tags', [])),
            'buff_sources': [],
        }
    target_rule = _target_rule(card)
    return {
        'instance_id': card['instance_id'],
        'definition_id': card['definition_id'],
        'hidden': False,
        'revealed': card.get('revealed', False),
        'staged': bool(card.get('staged')),
        'name': card['name'],
        'cost': _effective_cost(card),
        'base_cost': card['cost'],
        'original_cost': card['cost'],
        'power': int(card.get('computed_power', _raw_card_power(card))),
        'base_power': card['base_power'],
        'original_power': card['base_power'],
        'bonus_power': card['bonus_power'],
        'element': card.get('element', ''),
        'rarity': card.get('rarity', 'n'),
        'art': card.get('art', CARD_BACK_IMAGE),
        'description': card.get('description', ''),
        'archetype': card.get('archetype', ''),
        'category': card.get('category', ''),
        'attribute': card.get('attribute', ''),
        'attribute_icon': card.get('attribute_icon', ''),
        'material_cost': int(card.get('material_cost') or 0),
        'required_material_attribute': card.get('required_material_attribute', ''),
        'material_requirements': deepcopy(card.get('material_requirements') or []),
        'material_requirement_text': card.get('material_requirement_text', ''),
        'material_tags': list(card.get('material_tags', [])),
        'consumed_material_tags': list(card.get('consumed_material_tags', [])),
        'consumed_material_names': list(card.get('consumed_material_names', [])),
        'consumed_material_attributes': list(card.get('consumed_material_attributes', [])),
        'absorbed_material_power': int(card.get('absorbed_material_power', 0)),
        'played_turn': card.get('played_turn'),
        'location_id': card.get('location_id'),
        'type': card.get('type', 'esper'),
        'tags': list(card.get('tags', [])),
        'buff_sources': [deepcopy(source) for source in card.get('buff_sources', [])],
        'target_rule': target_rule or None,
        'selected_target_instance_id': card.get('selected_target_instance_id'),
        'selected_target_name': card.get('selected_target_name', ''),
        'declared_card_names': list(card.get('declared_card_names', [])),
        'declared_card_instance_ids': list(card.get('declared_card_instance_ids', [])),
        'pending_material_ids': list(card.get('pending_material_ids', [])),
        'reserved_as_material_for': card.get('reserved_as_material_for'),
    }


def _public_score(snapshot: JsonDict, perspective: SidePerspective) -> JsonDict:
    won = 0
    lost = 0
    tied = 0
    total_player = 0
    total_opponent = 0
    for location in snapshot['locations']:
        total_player += location['power'][perspective.own]
        total_opponent += location['power'][perspective.opponent]
        if location['winner_side'] == perspective.own:
            won += 1
        elif location['winner_side'] == perspective.opponent:
            lost += 1
        else:
            tied += 1
    if total_player > total_opponent:
        leader = 'player'
    elif total_opponent > total_player:
        leader = 'opponent'
    else:
        leader = 'tie'
    return {
        'locations_won': won,
        'locations_lost': lost,
        'locations_tied': tied,
        'total_power_player': total_player,
        'total_power_opponent': total_opponent,
        'leader': leader,
    }


def _public_initiative(snapshot: JsonDict, perspective: SidePerspective) -> JsonDict:
    settlement = snapshot.get('settlement') or {}
    totals = settlement.get('totals') or {}
    first_side = str(settlement.get('first_side') or snapshot.get('settlement_first_side') or '')
    leader_side = settlement.get('leader_side')
    return {
        'turn': int(settlement.get('turn') or snapshot.get('turn') or 1),
        'first': _public_side_key(first_side, perspective),
        'leader_at_turn_start': _public_side_key(str(leader_side), perspective) if leader_side in SIDE_KEYS else 'tie',
        'reason': settlement.get('reason', ''),
        'player_power_at_turn_start': int(totals.get(perspective.own, 0) or 0),
        'opponent_power_at_turn_start': int(totals.get(perspective.opponent, 0) or 0),
    }


def _public_side_key(side: str, perspective: SidePerspective) -> str:
    if side == perspective.own:
        return 'player'
    if side == perspective.opponent:
        return 'opponent'
    return 'tie'


def _public_winner(snapshot: JsonDict, perspective: SidePerspective) -> str | None:
    winner_side = snapshot.get('winner_side')
    if winner_side is None:
        return None
    return 'player' if winner_side == perspective.own else 'opponent'


def _side_overview(side: JsonDict) -> JsonDict:
    return {
        'side': side['side'],
        'uid': side['uid'],
        'nickname': side['nickname'],
        'is_ai': side['is_ai'],
        'deck_id': side.get('deck_id', ''),
        'deck_name': side.get('deck_name', ''),
        'ended_turn': side['ended_turn'],
    }


def _route_hint(snapshot: JsonDict, side: str) -> str:
    if snapshot['status'] != 'playing':
        if snapshot.get('winner_side') is None:
            return '主战场战力持平，这局没有输家。'
        return '你赢下了主战场。' if snapshot['winner_side'] == side else '对手赢下了主战场。'
    selection = snapshot['sides'][side].get('selection')
    if selection and selection.get('kind') != 'draw':
        return str(selection.get('description') or '先完成本次卡牌选择。')
    if snapshot.get('phase') == 'selecting':
        return '等待对手完成卡牌选择。'
    if snapshot['sides'][side].get('ended_turn'):
        return '你已结束回合，等待对手完成置入。'
    pending = snapshot['sides'][side].get('pending_target')
    if pending:
        return str(pending.get('prompt') or '请选择一个目标。')
    return f'拖动手牌置入异象道具，或从待命区唤醒/共鸣异能者消耗同区域素材；剩余 {_energy_remaining(snapshot, side)} 点能量。'


def _load_mutable_player_run(player: Player) -> tuple[Room, JsonDict, str]:
    from app.dao import get_current_room

    room = get_current_room(player)
    if room is None:
        raise RuleValidationError('当前没有对局。')
    run = get_cached_room_run(room.id) or get_run(room)
    if run is None or not _is_snap_snapshot(run.get('snapshot', {})):
        raise RuleValidationError('当前没有异象对局。')
    snapshot = deepcopy(run['snapshot'])
    _clear_legacy_draw_selections(snapshot, auto_draw=True)
    side = _side_for_player(snapshot, player)
    if side is None:
        raise RuleValidationError('当前玩家不在该对局中。')
    return room, snapshot, side


def _persist_room_snapshot(room: Room, snapshot: JsonDict) -> None:
    if snapshot['status'] != 'playing':
        discard_cached_room_run(room.id)
        with atomic_transaction():
            upsert_run(room, GAME_ID, snapshot['status'], snapshot)
            update_room_status(room, snapshot['status'])
        return
    queue_room_snapshot_persist(
        room.id,
        GAME_ID,
        snapshot['status'],
        deepcopy(snapshot),
        touch_room=True,
        update_room_status=snapshot['status'] != 'playing',
    )


def _perspective_for_player(snapshot: JsonDict, player: Player) -> SidePerspective:
    side = _side_for_player(snapshot, player) or SIDE_A
    return SidePerspective(own=side, opponent=_opponent_side(side))


def _side_for_player(snapshot: JsonDict, player: Player) -> str | None:
    for side in SIDE_KEYS:
        if snapshot['sides'][side]['uid'] == player.player_uid:
            return side
    return None


def _opponent_side(side: str) -> str:
    return SIDE_B if side == SIDE_A else SIDE_A


def _public_status(snapshot: JsonDict, viewer_side: str) -> str:
    status = snapshot['status']
    if status == 'playing' or status == 'draw':
        return status
    if viewer_side == SIDE_A:
        return status
    if status == 'victory':
        return 'defeat'
    if status == 'defeat':
        return 'victory'
    return status


def _public_phase(snapshot: JsonDict, side: str) -> str:
    if snapshot['status'] != 'playing':
        return _public_status(snapshot, side)
    selection = snapshot['sides'][side].get('selection')
    if selection and selection.get('kind') != 'draw':
        return 'selecting'
    if snapshot.get('phase') == 'selecting':
        return 'waiting'
    if snapshot['sides'][side].get('ended_turn'):
        return 'waiting'
    return snapshot.get('phase', 'planning')


def _is_snap_snapshot(snapshot: JsonDict) -> bool:
    return snapshot.get('game_id') == GAME_ID


def _ensure_playing(snapshot: JsonDict) -> None:
    if snapshot['status'] != 'playing':
        raise RuleValidationError('对局已经结束。')


def _ensure_selection_resolved(snapshot: JsonDict, side: str) -> None:
    selection = snapshot['sides'][side].get('selection')
    if selection and selection.get('kind') == 'draw':
        _resolve_legacy_draw_selection_as_auto_draw(snapshot, side)
    elif selection:
        raise RuleValidationError('请先完成当前卡牌选择。')
    if snapshot['sides'][side].get('pending_target'):
        raise RuleValidationError('请先为本次置入选择目标，或取消这张牌。')


def _ensure_not_ended(snapshot: JsonDict, side: str) -> None:
    if snapshot['sides'][side].get('ended_turn'):
        raise RuleValidationError('你已经结束本回合。')


def _find_location(snapshot: JsonDict, location_id: str) -> JsonDict:
    for location in snapshot['locations']:
        if location['id'] == location_id:
            return location
    raise RuleValidationError('未知的异象空间。')


def _is_location_revealed(snapshot: JsonDict, location: JsonDict) -> bool:
    return bool(location.get('revealed')) and int(location.get('reveal_turn', 1)) <= int(snapshot['turn'])


def _open_locations(snapshot: JsonDict, side: str) -> list[JsonDict]:
    return [
        location
        for location in snapshot['locations']
        if _is_location_revealed(snapshot, location) and len(location['cards'][side]) < LOCATION_CARD_LIMIT
    ]


def _esper_material_cost(card: JsonDict) -> int:
    requirements = _esper_material_requirements(card)
    if requirements:
        return sum(int(requirement.get('count') or 1) for requirement in requirements)
    return max(2, min(3, int(card.get('material_cost') or 2)))


def _material_cards_for_esper(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    esper_card: JsonDict,
    material_instance_ids: list[str] | None = None,
) -> list[JsonDict]:
    required = _esper_material_cost(esper_card)
    requirements = _esper_material_requirements(esper_card)
    candidates = [
        card
        for card in location.get('cards', {}).get(side, [])
        if card.get('instance_id') != esper_card.get('instance_id')
        and _is_valid_esper_material(card, current_turn=int(snapshot.get('turn') or 0))
        and (
            _material_matches_esper_requirement(card, esper_card)
            if not requirements
            else _material_matches_any_requirement(card, requirements)
        )
    ]
    if material_instance_ids is not None:
        selected_ids = _unique_ids(material_instance_ids)
        if len(selected_ids) != required:
            raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要指定 {_esper_material_requirement_text(esper_card)}。")
        candidates_by_id = {str(card.get('instance_id')): card for card in candidates}
        selected_cards = [candidates_by_id.get(instance_id) for instance_id in selected_ids]
        if any(card is None for card in selected_cards):
            raise RuleValidationError(f"只能选择{_esper_material_filter_text(esper_card)}。")
        if requirements and not _materials_satisfy_requirements([card for card in selected_cards if card is not None], requirements):
            raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要{_esper_material_requirement_text(esper_card)}。")
        return [card for card in selected_cards if card is not None]
    candidates.sort(key=lambda card: (
        0 if card.get('type') == CARD_TYPE_TOKEN else 1,
        int(card.get('computed_power', card.get('base_power', 0)) or 0),
        str(card.get('name', '')),
    ))
    if requirements:
        selected = _select_materials_for_requirements(candidates, requirements)
        if len(selected) < required:
            raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要同区域 {_esper_material_requirement_text(esper_card)}。")
        return selected
    if len(candidates) < required:
        raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要同区域 {_esper_material_requirement_text(esper_card)}。")
    return candidates[:required]


def _is_valid_esper_material(card: JsonDict, *, current_turn: int | None = None) -> bool:
    tags = set(card.get('tags', []))
    if TAG_MATERIAL not in tags:
        return False
    if TAG_HARMONY in tags:
        return False
    if not card.get('revealed'):
        return False
    if card.get('staged'):
        return False
    if current_turn is not None and int(card.get('played_turn') or -1) == current_turn:
        return False
    if card.get('type') == CARD_TYPE_ESPER:
        return False
    if card.get('reserved_as_material_for'):
        return False
    if int(card.get('computed_power', _raw_card_power(card)) or 0) <= 0:
        return False
    return card.get('type') == CARD_TYPE_ANOMALY_ITEM


def _material_tags_for_card(card: JsonDict) -> list[str]:
    material_tags = [str(tag) for tag in card.get('material_tags', []) if str(tag).startswith('mat_')]
    if material_tags:
        return material_tags
    return [str(tag) for tag in card.get('tags', []) if str(tag).startswith('mat_')]


def _esper_required_material_attribute(card: JsonDict) -> str:
    return str(card.get('required_material_attribute') or card.get('attribute') or card.get('element') or '指定')


def _is_wildcard_material_attribute(attribute: str) -> bool:
    return attribute in {'', '任意', '指定'}


def _esper_material_requirement_text(card: JsonDict) -> str:
    if card.get('material_requirement_text'):
        return str(card.get('material_requirement_text'))
    requirements = _esper_material_requirements(card)
    if requirements:
        return '+'.join(_material_requirement_fragment(requirement) for requirement in requirements)
    required = _esper_material_cost(card)
    attribute = _esper_required_material_attribute(card)
    return f"{required} 个{attribute + '属性' if not _is_wildcard_material_attribute(attribute) else ''}素材"


def _esper_material_filter_text(card: JsonDict) -> str:
    requirements = _esper_material_requirements(card)
    if requirements:
        return f"同区域、已揭示、未被预定、战力为正且满足{_esper_material_requirement_text(card)}的异象道具素材"
    attribute = _esper_required_material_attribute(card)
    attribute_text = '' if _is_wildcard_material_attribute(attribute) else f"{attribute}属性、"
    return f"同区域、已揭示、未被预定、{attribute_text}战力为正的异象道具素材"


def _esper_material_requirements(card: JsonDict) -> list[JsonDict]:
    requirements = card.get('material_requirements') or []
    if not isinstance(requirements, list):
        return []
    return [requirement for requirement in requirements if isinstance(requirement, dict)]


def _material_requirement_fragment(requirement: JsonDict) -> str:
    count = int(requirement.get('count') or 1)
    if requirement.get('attribute'):
        return f"{requirement.get('attribute')}属性素材*{count}"
    attributes = requirement.get('attributes')
    if isinstance(attributes, list):
        options = [str(attribute) for attribute in attributes if str(attribute)]
        if options:
            return f"{'/'.join(options)}属性素材*{count}"
    if requirement.get('category'):
        return f"{requirement.get('category')}素材*{count}"
    if requirement.get('name'):
        return f"「{requirement.get('name')}」*{count}"
    return f"素材*{count}"


def _material_matches_any_requirement(material: JsonDict, requirements: list[JsonDict]) -> bool:
    return any(_material_matches_requirement(material, requirement) for requirement in requirements)


def _material_matches_requirement(material: JsonDict, requirement: JsonDict) -> bool:
    attribute = str(requirement.get('attribute') or '')
    attributes = requirement.get('attributes')
    category = str(requirement.get('category') or '')
    name = str(requirement.get('name') or '')
    if attribute and _material_attribute(material) != attribute:
        return False
    if isinstance(attributes, list):
        options = {str(option) for option in attributes if str(option)}
        if options and _material_attribute(material) not in options:
            return False
    if category and str(material.get('category') or '') != category:
        return False
    if name and str(material.get('name') or '') != name:
        return False
    return True


def _select_materials_for_requirements(candidates: list[JsonDict], requirements: list[JsonDict]) -> list[JsonDict]:
    selected: list[JsonDict] = []
    used_ids: set[str] = set()
    for requirement in requirements:
        needed = int(requirement.get('count') or 1)
        for card in candidates:
            if needed <= 0:
                break
            instance_id = str(card.get('instance_id') or '')
            if instance_id in used_ids or not _material_matches_requirement(card, requirement):
                continue
            selected.append(card)
            used_ids.add(instance_id)
            needed -= 1
        if needed > 0:
            return []
    return selected


def _materials_satisfy_requirements(materials: list[JsonDict], requirements: list[JsonDict]) -> bool:
    expected_count = sum(int(requirement.get('count') or 1) for requirement in requirements)
    return len(_select_materials_for_requirements(materials, requirements)) == expected_count


def _material_attribute(card: JsonDict) -> str:
    return str(card.get('attribute') or card.get('element') or '')


def _material_matches_esper_requirement(material: JsonDict, esper_card: JsonDict) -> bool:
    required_attribute = _esper_required_material_attribute(esper_card)
    return _is_wildcard_material_attribute(required_attribute) or _material_attribute(material) == required_attribute


def _material_absorb_power(card: JsonDict) -> int:
    return int(card.get('computed_power', _raw_card_power(card)) or 0)


def _location_has_room_after_materials(location: JsonDict, side: str, material_cards: list[JsonDict]) -> bool:
    future_count = len(location.get('cards', {}).get(side, [])) - len(material_cards) + 1
    return future_count <= LOCATION_CARD_LIMIT


def _reserve_materials(material_cards: list[JsonDict], esper_instance_id: str) -> None:
    for card in material_cards:
        card['reserved_as_material_for'] = esper_instance_id


def _release_material_reservations(snapshot: JsonDict, side: str, esper_instance_id: str) -> None:
    for location in snapshot.get('locations', []):
        for card in location.get('cards', {}).get(side, []):
            if card.get('reserved_as_material_for') == esper_instance_id:
                card.pop('reserved_as_material_for', None)


def _cards_by_instance_ids(snapshot: JsonDict, side: str, instance_ids: list[str]) -> list[JsonDict]:
    ids = set(str(instance_id) for instance_id in instance_ids)
    cards: list[JsonDict] = []
    for location in snapshot.get('locations', []):
        for card in location.get('cards', {}).get(side, []):
            if card.get('instance_id') in ids:
                cards.append(card)
    return cards


def _find_staged_card(snapshot: JsonDict, side: str, instance_id: str) -> tuple[JsonDict, JsonDict]:
    for location in snapshot['locations']:
        for card in location['cards'][side]:
            if card['instance_id'] != instance_id:
                continue
            if not _is_staged_card(snapshot, card):
                raise RuleValidationError('只有本回合尚未揭示的临时置入牌可以调整。')
            return card, location
    raise RuleValidationError('战场上没有这张可调整的临时牌。')


def _find_pending_source_card(snapshot: JsonDict, side: str, instance_id: str) -> tuple[JsonDict, JsonDict]:
    for location in snapshot['locations']:
        for card in location['cards'][side]:
            if card['instance_id'] != instance_id:
                continue
            if _is_staged_card(snapshot, card) or _is_pending_esper_reactivation(snapshot, card):
                return card, location
    raise RuleValidationError('战场上没有这张等待选择目标的牌。')


def _is_staged_card(snapshot: JsonDict, card: JsonDict) -> bool:
    return bool(
        card.get('staged')
        and not card.get('revealed')
        and int(card.get('played_turn') or 0) == int(snapshot.get('turn', 0))
    )


def _refund_card_cost(snapshot: JsonDict, side: str, card: JsonDict) -> None:
    refund = int(card.get('paid_cost', _effective_cost(card)))
    snapshot['sides'][side]['energy_used'] = max(0, int(snapshot['sides'][side].get('energy_used', 0)) - refund)


def _cost_to_play(snapshot: JsonDict, side: str, card: JsonDict, location: JsonDict) -> int:
    return _effective_cost(card) + _delay_tax(snapshot, side, location)


def _delay_tax(snapshot: JsonDict, side: str, location: JsonDict) -> int:
    return 1 if (
        _location_mark_count(location, side, TAG_DELAY) > 0
        or _location_mark_count(location, side, TAG_SURPLUS) > 0
        or _first_delay_in_location(location, side) is not None
    ) else 0


def _first_delay_in_location(location: JsonDict, side: str) -> JsonDict | None:
    for card in location['cards'][side]:
        if card.get('revealed') and TAG_DELAY in card.get('tags', []) and TAG_HARMONY in card.get('tags', []):
            return card
    return None


def _consume_delay_tax(snapshot: JsonDict, side: str, location: JsonDict) -> None:
    delay_card = _first_delay_in_location(location, side)
    consumed_mark = _consume_location_mark(location, side, TAG_DELAY, 1)
    consumed_surplus = 0
    if delay_card is None and consumed_mark <= 0:
        consumed_surplus = _consume_location_mark(location, side, TAG_SURPLUS, 1)
    if delay_card is None and consumed_mark <= 0:
        if consumed_surplus <= 0:
            return
    if delay_card is not None and consumed_mark <= 0:
        _remove_board_card(snapshot, side, location, delay_card)
    opponent = _opponent_side(side)
    owner_of_delay = opponent
    snapshot['sides'][owner_of_delay].setdefault('combo', {})['delay_consumed_by_opponent'] = (
        int(snapshot['sides'][owner_of_delay].setdefault('combo', {}).get('delay_consumed_by_opponent', 0)) + 1
    )
    mark_name = '盈蓄' if consumed_surplus else '延滞'
    _add_log(snapshot, f"{location['name']} 的{mark_name}被触发，{_side_name(snapshot, side)} 本次置入额外消耗 1 点能量。")
    if (
        not consumed_surplus
        and _has_revealed_tag(location, opponent, TAG_GENESIS)
        and _add_generated_card_to_hand(snapshot, opponent, 'surplus_charge') is not None
    ):
        _add_log(snapshot, f"{location['name']} 的创生接住延滞反冲，{_side_name(snapshot, opponent)} 获得 1 张盈蓄。")


def _has_revealed_tag(location: JsonDict, side: str, tag: str) -> bool:
    return _location_mark_count(location, side, tag) > 0 or any(card.get('revealed') and tag in card.get('tags', []) for card in location['cards'][side])


def _remove_board_card(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    try:
        location['cards'][side].remove(card)
    except ValueError:
        return
    card['location_id'] = None
    card.pop('staged', None)
    card.pop('paid_cost', None)
    card.pop('play_sequence', None)
    card.pop('reserved_as_material_for', None)
    card.pop('pending_material_ids', None)
    card.pop('selected_target_name', None)
    card.pop('declared_card_instance_ids', None)
    card.pop('declared_card_names', None)
    snapshot['sides'][side].setdefault('discard', []).append(card)


def _sweep_broken_cards(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in list(location.get('cards', {}).get(side, [])):
                if not card.get('revealed'):
                    continue
                card['computed_power'] = _raw_card_power(card) + _location_power_bonus(location, side, card)
                if card.get('type') == CARD_TYPE_ANOMALY_ITEM and int(card.get('computed_power', 0)) <= 0:
                    _release_material_reservations(snapshot, side, card['instance_id'])
                    _remove_board_card(snapshot, side, location, card)
                    _add_log(snapshot, f"{card['name']} 战力归零，破碎进入墓地。")
                elif card.get('type') == CARD_TYPE_ESPER and int(card.get('computed_power', 0)) <= 0:
                    if card.pop('survive_non_positive_once', None):
                        _boost_card(card, 1 - int(card.get('computed_power', 0)), card['name'])
                        card['computed_power'] = 1
                        _add_log(snapshot, f"{card['name']} 抵住致命压制，保留 1 战力。")
                        continue
                    location['cards'][side].remove(card)
                    _release_material_reservations(snapshot, side, card['instance_id'])
                    _reset_esper_to_standby(snapshot, side, card)
                    _add_log(snapshot, f"{card['name']} 战力归零，返回异能者编队。")


def _vanish_revealed_card_if_needed(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    if not card.get('vanish_after_reveal') and 'vanish_on_reveal' not in card.get('tags', []):
        return
    if card not in location['cards'][side]:
        return
    snapshot.setdefault('action_queue', []).append({
        'kind': 'discard_card',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': f"{card['name']} 进入消耗区",
        'subtitle': '揭示后离开战场。',
        'card': _public_card(card, own=True),
    })
    _remove_board_card(snapshot, side, location, card)
    _add_log(snapshot, f"{card['name']} 离开战场。")


def _add_generated_card_to_hand(snapshot: JsonDict, side: str, card_id: str) -> JsonDict | None:
    side_state = snapshot['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    definition = get_duel_card(card_id)
    if definition is None:
        return None
    token_index = int(snapshot.setdefault('token_counter', 0)) + 1
    snapshot['token_counter'] = token_index
    card = _card_instance(definition, side, f'generated-{side}-{snapshot.get("turn", 0)}-{token_index}')
    side_state['hand'].append(card)
    return card


def _target_rule(card: JsonDict) -> JsonDict:
    definition = get_duel_card(str(card.get('definition_id', ''))) or {}
    return deepcopy(definition.get('target_rule') or SPECIAL_TARGET_RULES.get(str(card.get('definition_id', '')), {}) or {})


def _clear_pending_target_for_source(snapshot: JsonDict, side: str, source_instance_id: str) -> None:
    pending = snapshot['sides'][side].get('pending_target')
    if pending and pending.get('source_instance_id') == source_instance_id:
        snapshot['sides'][side]['pending_target'] = None


def _find_target_card(
    snapshot: JsonDict,
    side: str,
    source_location: JsonDict,
    target_instance_id: str,
    scope: str,
) -> JsonDict:
    candidates = _target_candidates(snapshot, side, source_location, scope)
    for card in candidates:
        if card['instance_id'] == target_instance_id:
            return card
    raise RuleValidationError('请选择合法的战场目标。')


def _target_candidates(snapshot: JsonDict, side: str, source_location: JsonDict, scope: str) -> list[JsonDict]:
    opponent = _opponent_side(side)
    if scope == 'opponent_same_location':
        return [card for card in source_location['cards'][opponent] if card.get('revealed')]
    if scope == 'opponent_any':
        return [
            card
            for location in snapshot['locations']
            for card in location['cards'][opponent]
            if card.get('revealed')
        ]
    if scope == 'ally_any':
        return [
            card
            for location in snapshot['locations']
            for card in location['cards'][side]
            if card.get('revealed')
        ]
    if scope == 'ally_same_location':
        return [card for card in source_location['cards'][side] if card.get('revealed')]
    if scope == 'ally_item_same_location':
        return [
            card
            for card in source_location['cards'][side]
            if card.get('revealed') and card.get('type') == CARD_TYPE_ANOMALY_ITEM
        ]
    raise RuleValidationError('这张牌的目标规则无效。')


def _find_card_on_board(snapshot: JsonDict, instance_id: str) -> JsonDict | None:
    for location in snapshot['locations']:
        for side in SIDE_KEYS:
            for card in location['cards'][side]:
                if card['instance_id'] == instance_id:
                    return card
    return None


def _find_card_in_zone(zone: list[JsonDict], instance_id: str, error_message: str) -> JsonDict:
    card = _find_card_in_zone_or_none(zone, instance_id)
    if card is None:
        raise RuleValidationError(error_message)
    return card


def _find_card_in_zone_or_none(zone: list[JsonDict], instance_id: str) -> JsonDict | None:
    for card in zone:
        if card['instance_id'] == instance_id:
            return card
    return None


def _pop_card_from_zone(zone: list[JsonDict], instance_id: str, error_message: str) -> JsonDict:
    for index, card in enumerate(zone):
        if card['instance_id'] == instance_id:
            return zone.pop(index)
    raise RuleValidationError(error_message)


def _pop_card_from_zone_or_none(zone: list[JsonDict], instance_id: str) -> JsonDict | None:
    for index, card in enumerate(zone):
        if card['instance_id'] == instance_id:
            return zone.pop(index)
    return None


def _find_revealed_esper_on_board(snapshot: JsonDict, side: str, instance_id: str) -> tuple[JsonDict, JsonDict]:
    for location in snapshot['locations']:
        for card in location['cards'][side]:
            if card['instance_id'] == instance_id and card.get('type') == CARD_TYPE_ESPER and card.get('revealed'):
                return card, location
    raise RuleValidationError('异能者编队或战场上没有这名可共鸣的异能者。')


def _turn_energy(snapshot: JsonDict) -> int:
    return min(MAX_ENERGY, int(snapshot.get('turn', 1)))


def _energy_remaining(snapshot: JsonDict, side: str) -> int:
    return max(0, _turn_energy(snapshot) - int(snapshot['sides'][side].get('energy_used', 0)))


def _effective_cost(card: JsonDict) -> int:
    return int(card.get('cost', 0)) + int(card.get('cost_modifier', 0))


def _raw_card_power(card: JsonDict) -> int:
    return int(card.get('base_power', 0)) + int(card.get('bonus_power', 0))


def _reset_card_stats_from_definition(card: JsonDict) -> None:
    definition = get_duel_card(str(card.get('definition_id', ''))) or {}
    card['base_power'] = int(definition.get('power', card.get('base_power', 0)) or 0)
    card['bonus_power'] = 0
    card['computed_power'] = int(card['base_power'])
    card['buff_sources'] = []


def _boost_card(card: JsonDict, amount: int, source_name: str = '效果') -> None:
    card['bonus_power'] = int(card.get('bonus_power', 0)) + int(amount)
    card['computed_power'] = _raw_card_power(card)
    _add_buff_source(card, source_name, int(amount))


def _add_buff_source(card: JsonDict, source_name: str, amount: int, *, replace_key: str = '') -> None:
    if amount == 0:
        return
    sources = card.setdefault('buff_sources', [])
    normalized = {
        'name': str(source_name or '效果'),
        'amount': int(amount),
        'key': str(replace_key or ''),
    }
    if replace_key:
        for index, source in enumerate(sources):
            if source.get('key') == replace_key:
                sources[index] = normalized
                return
    sources.append(normalized)
    del sources[8:]


def _location_index(snapshot: JsonDict, location_id: str) -> int:
    for index, location in enumerate(snapshot['locations']):
        if location['id'] == location_id:
            return index
    return -1


def _adjacent_locations(snapshot: JsonDict, index: int) -> list[JsonDict]:
    return [
        location
        for current_index, location in enumerate(snapshot['locations'])
        if abs(current_index - index) == 1
    ]


def _side_name(snapshot: JsonDict, side: str) -> str:
    return str(snapshot['sides'][side].get('nickname') or side)


def _add_log(snapshot: JsonDict, message: str) -> None:
    snapshot.setdefault('log', [])
    snapshot['log'].insert(0, message)
    del snapshot['log'][LOG_LIMIT:]


def _new_log_entries(snapshot: JsonDict, previous_logs: list[str]) -> list[str]:
    current_logs = list(snapshot.get('log', []))
    if not previous_logs:
        return current_logs
    for index in range(len(current_logs)):
        comparable = min(len(current_logs) - index, len(previous_logs))
        if comparable > 0 and current_logs[index:index + comparable] == previous_logs[:comparable]:
            return current_logs[:index]
    return current_logs[:max(0, len(current_logs) - len(previous_logs))]


def _reveal_effect_summary(card_name: str, log_entries: list[str]) -> str:
    fragments: list[str] = []
    for entry in reversed(log_entries):
        text = str(entry or '').strip()
        if not text:
            continue
        for prefix in (f'{card_name} ', card_name):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                break
        text = text.rstrip('。')
        if text:
            fragments.append(text)
    return '；'.join(fragments)[:96]


def _card_by_id() -> dict[str, JsonDict]:
    return {card['id']: card for card in CARD_LIBRARY}


def _card_catalog() -> list[JsonDict]:
    return [
        {
            'id': card['id'],
            'name': card['name'],
            'cost': card['cost'],
            'power': card['power'],
            'type': card.get('type', 'esper'),
            'element': card['element'],
            'rarity': card['rarity'],
            'icon': card['art'],
            'art': card['art'],
            'description': card['description'],
            'tags': list(card.get('tags', [])),
            'archetype': card.get('archetype', ''),
            'category': card.get('category', ''),
            'attribute': card.get('attribute', ''),
            'attribute_icon': card.get('attribute_icon', ''),
            'material_tags': list(card.get('material_tags', [])),
            'material_cost': int(card.get('material_cost') or 0),
            'required_material_attribute': card.get('required_material_attribute', ''),
            'material_requirements': deepcopy(card.get('material_requirements') or []),
            'material_requirement_text': card.get('material_requirement_text', ''),
            'target_rule': deepcopy(card.get('target_rule') or {}),
        }
        for card in CARD_LIBRARY
    ]


def _deck_catalog() -> list[JsonDict]:
    return [
        {
            'id': deck['id'],
            'name': deck['name'],
            'short_name': deck.get('short_name', deck['name']),
            'description': deck.get('description', ''),
            'difficulty': deck.get('difficulty', ''),
            'card_ids': list(deck.get('card_ids', [])),
            'esper_card_ids': list(deck.get('esper_card_ids', [])),
            'esper_count': len(deck.get('esper_card_ids', [])),
        }
        for deck in load_duel_decks()
    ]


def _leader_catalog(cards: list[JsonDict]) -> list[JsonDict]:
    character_payloads = {character['id']: character for character in load_characters()}
    leaders = []
    for card in cards:
        if card.get('type') != 'esper':
            continue
        character = character_payloads.get(card['id'], {})
        leaders.append({
            'id': card['id'],
            'name': card['name'],
            'max_hp': 0,
            'attack': card['power'],
            'defense': card.get('material_cost') or 1,
            'identification_level': 0,
            'portrait_image': character.get('portrait_image') or card['art'],
            'avatar_image': character.get('avatar_image') or card['art'],
            'passive': f"素材需求 {_esper_material_requirement_text(card)} / {card['power']} 战力。{card['description']}",
            'exclusive_item_ids': [],
        })
    return leaders
