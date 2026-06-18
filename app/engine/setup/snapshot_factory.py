from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from app.content.loader import default_duel_deck_id, get_duel_deck, load_duel_decks, validate_duel_deck_card_ids
from app.content.common.constants import LOCATION_CARD_LIMIT
from app.dao import get_build
from app.engine.application.build_service import (
    card_by_id,
    card_type,
    normalize_build_payload,
    unique_known_ids,
)
from app.engine.setup.battlefields import BATTLEFIELD_TRAITS
from app.engine.setup.tutorial_scripts import (
    TUTORIAL_BASICS_SCENARIO,
    TUTORIAL_OPPONENT_DECK,
    TUTORIAL_OPPONENT_HAND,
    TUTORIAL_PLAYER_DECK,
    TUTORIAL_PLAYER_ESPERS,
    TUTORIAL_PLAYER_HAND,
    normalize_tutorial_scenario,
    tutorial_locations,
)
from app.engine.state.types import JsonDict
from app.errors import RuleValidationError
from app.models import Player, Room

GAME_ID = 'anomaly_snap_duel'
SCHEMA_VERSION = 1
SIDE_A = 'a'
SIDE_B = 'b'
MAX_TURNS = 6
OPENING_HAND_SIZE = 4
MIN_BUILD_ITEM_COUNT = 10
MAX_BUILD_ITEM_COUNT = 20
MAX_BUILD_ESPER_COUNT = 4
CARD_BACK_IMAGE = '/static/images/cards/card-back.svg'
CARD_TYPE_ESPER = 'esper'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'


@dataclass(frozen=True)
class SnapshotFactoryRules:
    reveal_locations_for_turn: Callable[[JsonDict], None]
    sync_planning_phase: Callable[[JsonDict], None]
    recompute_scores: Callable[[JsonDict], None]
    lock_settlement_initiative: Callable[..., None]
    add_log: Callable[[JsonDict, str], None]


def create_initial_snapshot(
    room: Room,
    members: list[Any],
    rules: SnapshotFactoryRules,
    options: JsonDict | None = None,
) -> JsonDict:
    options = options or {}
    host_member = next((member for member in members if member.is_host), members[0] if members else None)
    if host_member is None:
        raise RuleValidationError('房间缺少玩家。')
    guest_member = next((member for member in members if member.player_id != host_member.player_id), None)
    scenario = normalize_scenario(options.get('scenario'))
    initial_log = '战场显现，双方已从牌组随机抽取起始手牌。'
    locations = _initial_locations()

    if scenario == TUTORIAL_BASICS_SCENARIO:
        if room.mode != 'solo':
            raise RuleValidationError('新手教学模式只支持单人房间。')
        host_side = _build_tutorial_player_side(host_member.player)
        opponent_side = _build_tutorial_ai_side()
        locations = tutorial_locations()
        initial_log = '教学演习开始：本局没有随机牌序，按固定步骤学习基础机制。'
    else:
        player_deck_id = str(options.get('player_deck_id') or '').strip()
        enemy_deck_id = str(options.get('enemy_deck_id') or '').strip()
        if scenario == 'trial':
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
        'scenario_label': scenario_label(scenario),
        'status': 'playing',
        'phase': 'planning',
        'turn': 1,
        'max_turns': MAX_TURNS,
        'locations': locations,
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
    if scenario == TUTORIAL_BASICS_SCENARIO:
        snapshot['tutorial'] = {'id': 'basics', 'version': 1}
    rules.reveal_locations_for_turn(snapshot)
    rules.sync_planning_phase(snapshot)
    rules.recompute_scores(snapshot)
    rules.lock_settlement_initiative(snapshot, emit_action=False)
    rules.add_log(snapshot, initial_log)
    return snapshot


def card_instance(definition: JsonDict, side: str, suffix: str) -> JsonDict:
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
        'material_attributes': list(definition.get('material_attributes', [])),
        'material_tags': list(definition.get('material_tags', [])),
        'material_cost': int(definition.get('material_cost') or 0),
        'required_material_attribute': definition.get('required_material_attribute', ''),
        'material_requirements': deepcopy(definition.get('material_requirements') or []),
        'material_requirement_text': definition.get('material_requirement_text', ''),
        'ai_material_reserved_for': list(definition.get('ai_material_reserved_for', [])),
        'display_tags': list(definition.get('display_tags', [])),
        'deck_buildable': definition.get('deck_buildable') is not False,
        'side': side,
        'revealed': False,
        'played_turn': None,
        'location_id': None,
        'tags': list(definition.get('tags', [])),
    }


def normalize_scenario(value: object) -> str:
    scenario = str(value or 'standard').strip().lower()
    scenario = normalize_tutorial_scenario(scenario)
    if scenario in {TUTORIAL_BASICS_SCENARIO, 'trial', 'standard', 'random_ai'}:
        return scenario
    return 'standard'


def scenario_label(scenario: object) -> str:
    normalized = normalize_scenario(scenario)
    if normalized == TUTORIAL_BASICS_SCENARIO:
        return '新手教学关'
    if normalized == 'trial':
        return '套牌试用关'
    if normalized == 'random_ai':
        return '随机人机对局'
    return '标准单人对局'


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


def _build_tutorial_player_side(player: Player) -> JsonDict:
    hand = _build_deck_instances(TUTORIAL_PLAYER_HAND, SIDE_A, prefix='hand')
    deck = _build_deck_instances(TUTORIAL_PLAYER_DECK, SIDE_A, prefix='deck')
    esper_standby = _build_deck_instances(TUTORIAL_PLAYER_ESPERS, SIDE_A, prefix='esper')
    return {
        'side': SIDE_A,
        'uid': player.player_uid,
        'nickname': player.nickname or player.player_uid,
        'is_ai': False,
        'deck_id': 'tutorial_basics',
        'deck_name': '新手教学套牌',
        'deck_description': '固定教学套牌，只在新手教学模式中使用。',
        'ai_plan': {},
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


def _build_tutorial_ai_side() -> JsonDict:
    hand = _build_deck_instances(TUTORIAL_OPPONENT_HAND, SIDE_B, prefix='hand')
    deck = _build_deck_instances(TUTORIAL_OPPONENT_DECK, SIDE_B, prefix='deck')
    return {
        'side': SIDE_B,
        'uid': 'tutorial_ai',
        'nickname': '教学对手',
        'is_ai': True,
        'deck_id': 'tutorial_opponent',
        'deck_name': '教学对手脚本',
        'deck_description': '固定教学对手，只在新手教学模式中使用。',
        'ai_plan': {},
        'deck': deck,
        'hand': hand,
        'esper_standby': [],
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
        if card_id in card_by_id() and card_type(card_id) == CARD_TYPE_ANOMALY_ITEM
    ]
    selected_esper_ids = [
        card_id
        for card_id in normalized_build.get('esper_card_ids', [])
        if card_id in card_by_id() and card_type(card_id) == CARD_TYPE_ESPER
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
    cards = card_by_id()
    for index, card_id in enumerate(card_ids):
        definition = cards[card_id]
        deck.append(card_instance(definition, side, f'{prefix}-{side}-{index + 1:02d}'))
    return deck


def _build_hand_and_deck_instances(card_ids: list[str], side: str, deck_payload: JsonDict) -> tuple[list[JsonDict], list[JsonDict]]:
    instances = _build_deck_instances(card_ids[:MAX_BUILD_ITEM_COUNT], side)
    random.shuffle(instances)
    hand = instances[:OPENING_HAND_SIZE]
    deck = instances[OPENING_HAND_SIZE:]
    random.shuffle(deck)
    return hand, deck


def _initial_locations() -> list[JsonDict]:
    trait = deepcopy(random.choice(BATTLEFIELD_TRAITS))
    return [{
        'id': 'main_battlefield',
        'trait_id': trait['id'],
        'name': f"战场：{trait['name']}",
        'short_name': '战场',
        'description': trait['description'],
        'reveal_turn': 1,
        'effect': trait['effect'],
        'revealed': False,
        'capacity': LOCATION_CARD_LIMIT,
        'cards': {SIDE_A: [], SIDE_B: []},
        'marks': {SIDE_A: {}, SIDE_B: {}},
        'power': {SIDE_A: 0, SIDE_B: 0},
        'winner_side': None,
    }]


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
        if card_type(card_id) != CARD_TYPE_ANOMALY_ITEM:
            raise RuleValidationError(f"{deck.get('name', '套牌')} 的牌组区域只能配置异象道具。")
    esper_ids = _esper_ids_for_deck_payload(deck)
    is_valid, validation_error = validate_duel_deck_card_ids([*card_ids, *esper_ids])
    if not is_valid:
        raise RuleValidationError(f"{deck.get('name', '套牌')} 配置非法：{validation_error}")
    return deck


def _esper_ids_for_deck_payload(deck_payload: JsonDict) -> list[str]:
    return [
        card_id
        for card_id in unique_known_ids(deck_payload.get('esper_card_ids', []))
        if card_type(card_id) == CARD_TYPE_ESPER
    ][:MAX_BUILD_ESPER_COUNT]
