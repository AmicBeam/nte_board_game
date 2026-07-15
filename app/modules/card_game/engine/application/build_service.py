from __future__ import annotations

from copy import deepcopy
from app.modules.card_game.content.loader import (
    default_duel_deck_id,
    load_duel_cards,
    load_duel_decks,
    validate_duel_deck_card_ids,
)
from app.dao import get_build, upsert_build
from app.modules.card_game.engine.rules.materials import esper_material_requirement_text
from app.modules.card_game.engine.setup.battlefields import LOCATION_LIBRARY
from app.modules.card_game.engine.state.types import JsonDict
from app.errors import RuleValidationError
from app.models import Player

GAME_ID = 'anomaly_snap_duel'
OPENING_HAND_SIZE = 4
MIN_BUILD_ITEM_COUNT = 10
MAX_BUILD_ITEM_COUNT = 20
MAX_BUILD_ESPER_COUNT = 4
MAX_COPIES_PER_ITEM_CARD = 3
MAP_LOCKED_ITEM_IDS: tuple[str, ...] = ()
PUBLIC_PREBUILT_DECK_IDS: tuple[str, ...] = ('genesis_bloom', 'delay_lock', 'murk_burn')

CARD_TYPE_ESPER = 'esper'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'

CARD_LIBRARY: list[JsonDict] = load_duel_cards()


def get_catalog_payload(player: Player) -> JsonDict:
    saved_build = get_build(player)
    cards = card_catalog()
    return {
        'characters': leader_catalog(cards),
        'items': cards,
        'min_build_size': MIN_BUILD_ITEM_COUNT,
        'build_size': MAX_BUILD_ITEM_COUNT,
        'opening_hand_size': OPENING_HAND_SIZE,
        'fixed_opening_hand_enabled': False,
        'max_esper_cards': MAX_BUILD_ESPER_COUNT,
        'locked_item_ids': list(MAP_LOCKED_ITEM_IDS),
        'decks': deck_catalog(),
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
        'cards': card_catalog(),
        'decks': deck_catalog(),
        'map': {
            'id': GAME_ID,
            'name': '三重异象空间',
            'total_layers': 1,
        },
        'items': card_catalog(),
    }


def save_build(
    player: Player,
    character_id: str,
    item_ids: list[str],
    esper_card_ids: list[str] | None = None,
) -> JsonDict:
    known_item_ids = known_card_ids(item_ids or [], required_type=CARD_TYPE_ANOMALY_ITEM)
    return save_build_with_starters(
        player,
        character_id,
        [],
        known_item_ids[:MAX_BUILD_ITEM_COUNT],
        esper_card_ids or [],
    )


def save_build_with_starters(
    player: Player,
    character_id: str,
    starter_item_ids: list[str],
    reserve_item_ids: list[str],
    esper_card_ids: list[str] | None = None,
) -> JsonDict:
    selected_item_ids = known_card_ids(
        [*(starter_item_ids or []), *(reserve_item_ids or [])],
        required_type=CARD_TYPE_ANOMALY_ITEM,
    )[:MAX_BUILD_ITEM_COUNT]
    selected_esper_ids = unique_known_ids(esper_card_ids or [])
    validate_custom_build_sections(selected_item_ids, selected_esper_ids)
    leader_id = str(character_id or '').strip() or (selected_esper_ids[0] if selected_esper_ids else 'protagonist')
    if leader_id not in card_by_id() or card_type(leader_id) != CARD_TYPE_ESPER:
        leader_id = selected_esper_ids[0] if selected_esper_ids else 'protagonist'
    is_valid, validation_error = validate_duel_deck_card_ids([*selected_item_ids, *selected_esper_ids])
    if not is_valid:
        raise RuleValidationError(validation_error)
    build_payload = {
        'starter_item_ids': [],
        'reserve_item_ids': selected_item_ids[:MAX_BUILD_ITEM_COUNT],
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
    starter_ids = known_card_ids(build.get('starter_item_ids', []), required_type=CARD_TYPE_ANOMALY_ITEM)
    reserve_ids = known_card_ids(build.get('reserve_item_ids', []), required_type=CARD_TYPE_ANOMALY_ITEM)
    item_ids = known_card_ids(build.get('item_ids', []), required_type=CARD_TYPE_ANOMALY_ITEM)
    esper_ids = unique_known_ids(build.get('esper_card_ids', []))
    if not item_ids:
        item_ids = [*starter_ids, *reserve_ids]
    legacy_espers = [card_id for card_id in item_ids if card_type(card_id) == CARD_TYPE_ESPER]
    if legacy_espers:
        item_ids = [card_id for card_id in item_ids if card_type(card_id) == CARD_TYPE_ANOMALY_ITEM]
        esper_ids = unique_known_ids([*esper_ids, *legacy_espers])
    item_ids = [card_id for card_id in item_ids if card_is_deck_buildable(card_id)]
    esper_ids = [card_id for card_id in esper_ids if card_is_deck_buildable(card_id)]
    return {
        'character_id': str(build.get('character_id') or ''),
        'starter_item_ids': [],
        'reserve_item_ids': item_ids[:MAX_BUILD_ITEM_COUNT],
        'item_ids': item_ids[:MAX_BUILD_ITEM_COUNT],
        'esper_card_ids': [card_id for card_id in esper_ids if card_type(card_id) == CARD_TYPE_ESPER][:MAX_BUILD_ESPER_COUNT],
        'updated_at': build.get('updated_at'),
    }


def card_by_id() -> dict[str, JsonDict]:
    return {card['id']: card for card in CARD_LIBRARY}


def unique_known_ids(card_ids: list[Any]) -> list[str]:
    unique: list[str] = []
    cards = card_by_id()
    for raw_id in card_ids:
        card_id = str(raw_id).strip()
        if not card_id or card_id in unique or card_id not in cards:
            continue
        unique.append(card_id)
    return unique


def known_card_ids(card_ids: list[Any], *, required_type: str = '') -> list[str]:
    cards = card_by_id()
    known: list[str] = []
    for raw_id in card_ids:
        card_id = str(raw_id).strip()
        if not card_id or card_id not in cards:
            continue
        if required_type and card_type(card_id) != required_type:
            continue
        known.append(card_id)
    return known


def sort_card_ids(card_ids: list[str]) -> list[str]:
    return sorted(card_ids, key=card_sort_key)


def card_sort_key(card_id: str) -> tuple[int, int, int, int, str]:
    card = card_by_id().get(str(card_id), {})
    type_order = {CARD_TYPE_ESPER: 0, CARD_TYPE_ANOMALY_ITEM: 1}
    attribute_order = {'灵': 0, '光': 1, '相': 2, '咒': 3, '暗': 4, '魂': 5}
    attribute = str(card.get('attribute') or card.get('required_material_attribute') or card.get('element') or '')
    cost = int(card.get('material_cost') or card.get('cost') or 0)
    power = int(card.get('power') or 0)
    card_type = str(card.get('type') or '')
    return (type_order.get(card_type, 99), cost, attribute_order.get(attribute, 99), power, str(card.get('name') or card_id))


def card_count_bucket(card_ids: list[str]) -> dict[str, int]:
    bucket: dict[str, int] = {}
    for card_id in card_ids:
        bucket[card_id] = int(bucket.get(card_id, 0)) + 1
    return bucket


def card_type(card_id: str) -> str:
    return str((card_by_id().get(str(card_id)) or {}).get('type', ''))


def card_is_deck_buildable(card_id: str) -> bool:
    card = card_by_id().get(str(card_id)) or {}
    return card.get('deck_buildable') is not False


def validate_custom_build_sections(item_ids: list[str], esper_ids: list[str]) -> None:
    if len(item_ids) < MIN_BUILD_ITEM_COUNT or len(item_ids) > MAX_BUILD_ITEM_COUNT:
        raise RuleValidationError(f'构筑需要选择 {MIN_BUILD_ITEM_COUNT} 到 {MAX_BUILD_ITEM_COUNT} 张异象道具。')
    if len(esper_ids) > MAX_BUILD_ESPER_COUNT:
        raise RuleValidationError(f'异能者最多选择 {MAX_BUILD_ESPER_COUNT} 张。')
    copy_count = card_count_bucket(item_ids)
    too_many = [card_id for card_id, count in copy_count.items() if count > MAX_COPIES_PER_ITEM_CARD]
    if too_many:
        raise RuleValidationError(f'同名异象道具最多携带 {MAX_COPIES_PER_ITEM_CARD} 张。')
    for card_id in item_ids:
        if card_type(card_id) != CARD_TYPE_ANOMALY_ITEM:
            raise RuleValidationError('牌组区域只能放入异象道具。')
        if not card_is_deck_buildable(card_id):
            card = card_by_id().get(card_id) or {}
            raise RuleValidationError(f"「{card.get('name', '该卡牌')}」不能放入构筑。")
    for card_id in esper_ids:
        if card_type(card_id) != CARD_TYPE_ESPER:
            raise RuleValidationError('异能者区域只能放入异能者卡牌。')
        if not card_is_deck_buildable(card_id):
            card = card_by_id().get(card_id) or {}
            raise RuleValidationError(f"「{card.get('name', '该异能者')}」不能放入构筑。")


def card_catalog() -> list[JsonDict]:
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
            'display_tags': list(card.get('display_tags', [])),
            'deck_buildable': card.get('deck_buildable') is not False,
            'hidden_from_build': card.get('deck_buildable') is False,
            'archetype': card.get('archetype', ''),
            'category': card.get('category', ''),
            'attribute': card.get('attribute', ''),
            'attribute_icon': card.get('attribute_icon', ''),
            'material_attributes': list(card.get('material_attributes', [])),
            'material_tags': list(card.get('material_tags', [])),
            'material_cost': int(card.get('material_cost') or 0),
            'required_material_attribute': card.get('required_material_attribute', ''),
            'material_requirements': deepcopy(card.get('material_requirements') or []),
            'material_requirement_text': card.get('material_requirement_text', ''),
            'target_rule': deepcopy(card.get('target_rule') or {}),
        }
        for card in CARD_LIBRARY
    ]


def deck_catalog() -> list[JsonDict]:
    public_deck_ids = set(PUBLIC_PREBUILT_DECK_IDS)
    return [
        {
            'id': deck['id'],
            'name': deck['name'],
            'short_name': deck.get('short_name', deck['name']),
            'description': deck.get('description', ''),
            'difficulty': deck.get('difficulty', ''),
            'card_ids': sort_card_ids(list(deck.get('card_ids', []))),
            'esper_card_ids': sort_card_ids(list(deck.get('esper_card_ids', []))),
            'esper_count': len(deck.get('esper_card_ids', [])),
        }
        for deck in load_duel_decks()
        if str(deck.get('id') or '') in public_deck_ids
    ]


def leader_catalog(cards: list[JsonDict]) -> list[JsonDict]:
    leaders = []
    for card in cards:
        if card.get('type') != CARD_TYPE_ESPER:
            continue
        leaders.append({
            'id': card['id'],
            'name': card['name'],
            'max_hp': 0,
            'attack': card['power'],
            'defense': card.get('material_cost') or 1,
            'portrait_image': card.get('portrait_image') or card['art'],
            'avatar_image': card.get('avatar_image') or card.get('portrait_image') or card['art'],
            'passive': f"素材需求 {esper_material_requirement_text(card)} / {card['power']} 战力。{card['description']}",
            'exclusive_item_ids': [],
        })
    return leaders
