from __future__ import annotations

from copy import deepcopy

from app.content.common.constants import LOCATION_CARD_LIMIT
from app.content.loader import get_duel_card
from app.engine.rules.declarations import target_rule
from app.engine.rules.materials import release_material_reservations
from app.engine.state.types import JsonDict
from app.errors import RuleValidationError

GAME_ID = 'anomaly_snap_duel'
SCHEMA_VERSION = 1
SIDE_A = 'a'
SIDE_B = 'b'
SIDE_KEYS = (SIDE_A, SIDE_B)
MAX_TURNS = 6
MAX_ENERGY = 6
MAX_HAND_SIZE = 10
LOG_LIMIT = 28

CARD_TYPE_ESPER = 'esper'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'
CARD_TYPE_TOKEN = 'token'
CARD_BACK_IMAGE = '/static/images/cards/card-back.svg'


def opponent_side(side: str) -> str:
    return SIDE_B if side == SIDE_A else SIDE_A


def is_snap_snapshot(snapshot: JsonDict) -> bool:
    return snapshot.get('game_id') == GAME_ID


def side_name(snapshot: JsonDict, side: str) -> str:
    return str(snapshot['sides'][side].get('nickname') or side)


def add_log(snapshot: JsonDict, message: str) -> None:
    snapshot.setdefault('log', [])
    snapshot['log'].insert(0, message)
    del snapshot['log'][LOG_LIMIT:]


def turn_energy(snapshot: JsonDict) -> int:
    return min(MAX_ENERGY, int(snapshot.get('turn', 1)))


def energy_remaining(snapshot: JsonDict, side: str) -> int:
    return max(0, turn_energy(snapshot) - int(snapshot['sides'][side].get('energy_used', 0)))


def effective_cost(card: JsonDict) -> int:
    return int(card.get('cost', 0)) + int(card.get('cost_modifier', 0))


def raw_card_power(card: JsonDict) -> int:
    return int(card.get('base_power', 0)) + int(card.get('bonus_power', 0))


def add_buff_source(card: JsonDict, source_name: str, amount: int, *, replace_key: str = '') -> None:
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


def boost_card(card: JsonDict, amount: int, source_name: str = '效果') -> None:
    card['bonus_power'] = int(card.get('bonus_power', 0)) + int(amount)
    card['computed_power'] = raw_card_power(card)
    add_buff_source(card, source_name, int(amount))


def reset_card_stats_from_definition(card: JsonDict) -> None:
    definition = get_duel_card(str(card.get('definition_id', ''))) or {}
    card['base_power'] = int(definition.get('power', card.get('base_power', 0)) or 0)
    card['bonus_power'] = 0
    card['computed_power'] = int(card['base_power'])
    card['buff_sources'] = []


def action_card(card: JsonDict, *, own: bool = True) -> JsonDict:
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
            'material_attributes': list(card.get('material_attributes', [])),
            'material_cost': card.get('material_cost', 0),
            'required_material_attribute': card.get('required_material_attribute', ''),
            'material_requirements': deepcopy(card.get('material_requirements') or []),
            'material_requirement_text': card.get('material_requirement_text', ''),
            'material_tags': list(card.get('material_tags', [])),
            'buff_sources': [],
        }
    return {
        'instance_id': card['instance_id'],
        'definition_id': card['definition_id'],
        'hidden': False,
        'revealed': card.get('revealed', False),
        'staged': bool(card.get('staged')),
        'name': card['name'],
        'cost': effective_cost(card),
        'base_cost': card['cost'],
        'original_cost': card['cost'],
        'power': int(card.get('computed_power', raw_card_power(card))),
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
        'material_attributes': list(card.get('material_attributes', [])),
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
        'target_rule': target_rule(card) or None,
        'selected_target_instance_id': card.get('selected_target_instance_id'),
        'selected_target_name': card.get('selected_target_name', ''),
        'declared_card_names': list(card.get('declared_card_names', [])),
        'declared_card_instance_ids': list(card.get('declared_card_instance_ids', [])),
        'pending_material_ids': list(card.get('pending_material_ids', [])),
        'reserved_as_material_for': card.get('reserved_as_material_for'),
    }


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
        'side': side,
        'revealed': False,
        'played_turn': None,
        'location_id': None,
        'tags': list(definition.get('tags', [])),
    }


def counts_as_location_slot(card: JsonDict) -> bool:
    return not card.get('reserved_as_material_for')


def is_location_revealed(snapshot: JsonDict, location: JsonDict) -> bool:
    return bool(location.get('revealed')) and int(location.get('reveal_turn', 1)) <= int(snapshot['turn'])


def location_occupied_card_count(
    location: JsonDict,
    side: str,
    *,
    excluding_instance_ids: set[str] | None = None,
) -> int:
    excluded = excluding_instance_ids or set()
    return sum(
        1
        for card in location.get('cards', {}).get(side, [])
        if str(card.get('instance_id') or '') not in excluded and counts_as_location_slot(card)
    )


def location_capacity(location: JsonDict) -> int:
    return int(location.get('capacity') or LOCATION_CARD_LIMIT)


def open_locations(snapshot: JsonDict, side: str) -> list[JsonDict]:
    return [
        location
        for location in snapshot['locations']
        if is_location_revealed(snapshot, location) and location_occupied_card_count(location, side) < location_capacity(location)
    ]


def find_location(snapshot: JsonDict, location_id: str) -> JsonDict:
    for location in snapshot['locations']:
        if location['id'] == location_id:
            return location
    raise RuleValidationError('未知的异象空间。')


def find_card_on_board(snapshot: JsonDict, instance_id: str) -> JsonDict | None:
    for location in snapshot['locations']:
        for side in SIDE_KEYS:
            for card in location['cards'][side]:
                if card['instance_id'] == instance_id:
                    return card
    return None


def find_card_in_zone(zone: list[JsonDict], instance_id: str, error_message: str) -> JsonDict:
    card = find_card_in_zone_or_none(zone, instance_id)
    if card is None:
        raise RuleValidationError(error_message)
    return card


def find_card_in_zone_or_none(zone: list[JsonDict], instance_id: str) -> JsonDict | None:
    for card in zone:
        if card['instance_id'] == instance_id:
            return card
    return None


def location_power_bonus(location: JsonDict, side: str, card: JsonDict) -> int:
    if not card.get('revealed') or not counts_as_location_slot(card):
        return 0
    if location['effect'] == 'first_card_plus_two':
        revealed = [
            item
            for item in location['cards'][side]
            if item.get('revealed') and counts_as_location_slot(item)
        ]
        if revealed and revealed[0]['instance_id'] == card['instance_id']:
            add_buff_source(card, location['name'], 2, replace_key=f'location:{location["id"]}')
            return 2
    if location['effect'] == 'solo_card_plus_four':
        revealed = [
            item
            for item in location['cards'][side]
            if item.get('revealed') and counts_as_location_slot(item)
        ]
        if len(revealed) == 1 and revealed[0]['instance_id'] == card['instance_id']:
            add_buff_source(card, location['name'], 4, replace_key=f'location:{location["id"]}')
            return 4
    return 0


def recompute_scores(snapshot: JsonDict) -> None:
    for location in snapshot['locations']:
        for side in SIDE_KEYS:
            revealed_cards = [
                card
                for card in location['cards'][side]
                if card.get('revealed') and counts_as_location_slot(card)
            ]
            for card in location['cards'][side]:
                card['computed_power'] = raw_card_power(card) + location_power_bonus(location, side, card)
            location['power'][side] = sum(int(card['computed_power']) for card in revealed_cards)
        if location['power'][SIDE_A] > location['power'][SIDE_B]:
            location['winner_side'] = SIDE_A
        elif location['power'][SIDE_B] > location['power'][SIDE_A]:
            location['winner_side'] = SIDE_B
        else:
            location['winner_side'] = None
    snapshot['turn_energy'] = turn_energy(snapshot)


def remove_board_card(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
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


def reset_esper_to_standby(snapshot: JsonDict, side: str, card: JsonDict) -> None:
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
    reset_card_stats_from_definition(card)
    snapshot['sides'][side].setdefault('esper_standby', []).append(card)


def sweep_broken_cards(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in list(location.get('cards', {}).get(side, [])):
                if not card.get('revealed'):
                    continue
                card['computed_power'] = raw_card_power(card) + location_power_bonus(location, side, card)
                if card.get('type') == CARD_TYPE_ANOMALY_ITEM and int(card.get('computed_power', 0)) <= 0:
                    release_material_reservations(snapshot, side, card['instance_id'])
                    remove_board_card(snapshot, side, location, card)
                    add_log(snapshot, f"{card['name']} 战力归零，破碎进入墓地。")
                elif card.get('type') == CARD_TYPE_ESPER and int(card.get('computed_power', 0)) <= 0:
                    if card.pop('survive_non_positive_once', None):
                        boost_card(card, 1 - int(card.get('computed_power', 0)), card['name'])
                        card['computed_power'] = 1
                        add_log(snapshot, f"{card['name']} 抵住致命压制，保留 1 战力。")
                        continue
                    location['cards'][side].remove(card)
                    release_material_reservations(snapshot, side, card['instance_id'])
                    reset_esper_to_standby(snapshot, side, card)
                    add_log(snapshot, f"{card['name']} 战力归零，返回异能者编队。")


def add_generated_card_to_hand(snapshot: JsonDict, side: str, card_id: str) -> JsonDict | None:
    side_state = snapshot['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    definition = get_duel_card(card_id)
    if definition is None:
        return None
    token_index = int(snapshot.setdefault('token_counter', 0)) + 1
    snapshot['token_counter'] = token_index
    card = card_instance(definition, side, f'generated-{side}-{snapshot.get("turn", 0)}-{token_index}')
    side_state['hand'].append(card)
    return card


def has_revealed_tag(location: JsonDict, side: str, tag: str) -> bool:
    from app.engine.rules.harmony import location_mark_count

    return location_mark_count(location, side, tag) > 0 or any(
        card.get('revealed') and tag in card.get('tags', [])
        for card in location['cards'][side]
    )


def reveal_locations_for_turn(snapshot: JsonDict) -> None:
    for location in snapshot['locations']:
        if not location['revealed'] and int(location['reveal_turn']) <= int(snapshot['turn']):
            location['revealed'] = True
            add_log(snapshot, f"{location['name']} 显现：{location['description']}")


__all__ = [name for name in globals() if not name.startswith('__')]
