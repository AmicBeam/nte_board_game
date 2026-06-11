from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.engine.rules.declarations import (
    has_required_target_before_play,
    prepare_declaration_selection,
    target_candidates,
    target_rule_internal,
)
from app.engine.rules.materials import (
    location_has_room_after_materials,
    material_cards_for_esper,
    reserve_materials,
)
from app.engine.state.types import JsonDict
from app.errors import RuleValidationError

CARD_TYPE_ESPER = 'esper'


@dataclass(frozen=True)
class AiRules:
    resolve_pending_choices: Callable[[JsonDict, str], None]
    energy_remaining: Callable[[JsonDict, str], int]
    open_locations: Callable[[JsonDict, str], list[JsonDict]]
    cost_to_play: Callable[[JsonDict, str, JsonDict, JsonDict], int]
    opponent_side: Callable[[str], str]
    recompute_scores: Callable[[JsonDict], None]
    raw_card_power: Callable[[JsonDict], int]
    next_play_sequence: Callable[[JsonDict], int]
    delay_tax: Callable[[JsonDict, str, JsonDict], int]
    consume_delay_tax: Callable[[JsonDict, str, JsonDict], None]
    add_log: Callable[[JsonDict, str], None]
    side_name: Callable[[JsonDict, str], str]
    is_location_revealed: Callable[[JsonDict, JsonDict], bool]
    side_reactivation_used: Callable[[JsonDict, str], bool]
    mark_side_reactivation: Callable[[JsonDict, str], None]
    location_occupied_card_count: Callable[[JsonDict, str], int]


def run_ai_turn(snapshot: JsonDict, side: str, rules: AiRules) -> None:
    rules.resolve_pending_choices(snapshot, side)
    if snapshot['sides'][side]['ended_turn']:
        return
    playable = True
    while playable:
        playable = _ai_play_one_card(snapshot, side, rules)
    esper_playable = True
    while esper_playable:
        esper_playable = _ai_play_one_esper(snapshot, side, rules)
    esper_reactivated = True
    while esper_reactivated:
        esper_reactivated = _ai_reactivate_one_esper(snapshot, side, rules)
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 完成置入。")


def _ai_play_one_card(snapshot: JsonDict, side: str, rules: AiRules) -> bool:
    hand = snapshot['sides'][side]['hand']
    energy_remaining = rules.energy_remaining(snapshot, side)
    open_locations = rules.open_locations(snapshot, side)
    options: list[tuple[JsonDict, JsonDict, int]] = []
    for card in hand:
        for location in open_locations:
            if not has_required_target_before_play(snapshot, side, location, card):
                continue
            cost = rules.cost_to_play(snapshot, side, card, location)
            if cost <= energy_remaining:
                options.append((card, location, cost))
    if not options:
        return False
    priority = _ai_priority(snapshot['sides'][side])
    opponent = rules.opponent_side(side)
    rules.recompute_scores(snapshot)
    options.sort(
        key=lambda option: (
            priority.get(option[0].get('definition_id'), -99),
            option[1]['power'][opponent] - option[1]['power'][side],
            rules.raw_card_power(option[0]),
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
    card['play_sequence'] = rules.next_play_sequence(snapshot)
    snapshot['sides'][side]['energy_used'] += cost
    location['cards'][side].append(card)
    if rules.delay_tax(snapshot, side, location):
        rules.consume_delay_tax(snapshot, side, location)
    target_rule = target_rule_internal(card)
    if target_rule:
        target = _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            prepare_declaration_selection(snapshot, side, location, card, target)
            rules.resolve_pending_choices(snapshot, side)
    else:
        prepare_declaration_selection(snapshot, side, location, card)
        rules.resolve_pending_choices(snapshot, side)
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 将一张牌置入 {location['name']}。")
    return True


def _ai_play_one_esper(snapshot: JsonDict, side: str, rules: AiRules) -> bool:
    standby = snapshot['sides'][side].setdefault('esper_standby', [])
    if not standby:
        return False
    open_locations = [location for location in snapshot['locations'] if rules.is_location_revealed(snapshot, location)]
    options: list[tuple[JsonDict, JsonDict, list[JsonDict]]] = []
    for card in standby:
        for location in open_locations:
            try:
                material_cards = material_cards_for_esper(snapshot, side, location, card)
            except RuleValidationError:
                continue
            if location_has_room_after_materials(location, side, material_cards):
                options.append((card, location, material_cards))
    if not options:
        return False
    priority_ids = list(snapshot['sides'][side].get('ai_plan', {}).get('esper_priority_ids', []))
    priority = {str(card_id): len(priority_ids) - index for index, card_id in enumerate(priority_ids)}
    opponent = rules.opponent_side(side)
    rules.recompute_scores(snapshot)
    options.sort(
        key=lambda option: (
            priority.get(option[0].get('definition_id'), -99),
            option[1]['power'][opponent] - option[1]['power'][side],
            rules.raw_card_power(option[0]),
        ),
        reverse=True,
    )
    card, location, material_cards = options[0]
    standby.remove(card)
    material_ids = [item['instance_id'] for item in material_cards]
    reserve_materials(material_cards, card['instance_id'])
    card['played_turn'] = snapshot['turn']
    card['location_id'] = location['id']
    card['revealed'] = False
    card['staged'] = True
    card['play_sequence'] = rules.next_play_sequence(snapshot)
    card['summoned_from'] = 'esper_standby'
    card['pending_material_ids'] = material_ids
    card['paid_cost'] = 0
    location['cards'][side].append(card)
    target_rule = target_rule_internal(card)
    if target_rule:
        target = _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            prepare_declaration_selection(snapshot, side, location, card, target)
            rules.resolve_pending_choices(snapshot, side)
    else:
        prepare_declaration_selection(snapshot, side, location, card)
        rules.resolve_pending_choices(snapshot, side)
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 唤醒一名异能者于 {location['name']}。")
    return True


def _ai_reactivate_one_esper(snapshot: JsonDict, side: str, rules: AiRules) -> bool:
    if rules.side_reactivation_used(snapshot, side):
        return False
    revealed_espers: list[tuple[JsonDict, JsonDict, list[JsonDict]]] = []
    for location in snapshot['locations']:
        if not rules.is_location_revealed(snapshot, location):
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
                material_cards = material_cards_for_esper(snapshot, side, location, card)
            except RuleValidationError:
                continue
            revealed_espers.append((card, location, material_cards))
    if not revealed_espers:
        return False
    priority_ids = list(snapshot['sides'][side].get('ai_plan', {}).get('esper_priority_ids', []))
    priority = {str(card_id): len(priority_ids) - index for index, card_id in enumerate(priority_ids)}
    opponent = rules.opponent_side(side)
    rules.recompute_scores(snapshot)
    revealed_espers.sort(
        key=lambda option: (
            priority.get(option[0].get('definition_id'), -99),
            option[1]['power'][opponent] - option[1]['power'][side],
            rules.raw_card_power(option[0]),
        ),
        reverse=True,
    )
    card, location, material_cards = revealed_espers[0]
    material_ids = [item['instance_id'] for item in material_cards]
    reserve_materials(material_cards, card['instance_id'])
    card['pending_material_ids'] = material_ids
    card['reactivating_turn'] = snapshot['turn']
    rules.mark_side_reactivation(snapshot, side)
    target_rule = target_rule_internal(card)
    if target_rule:
        target = _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            prepare_declaration_selection(snapshot, side, location, card, target)
            rules.resolve_pending_choices(snapshot, side)
    else:
        prepare_declaration_selection(snapshot, side, location, card)
        rules.resolve_pending_choices(snapshot, side)
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 准备让 {card['name']} 再共鸣。")
    return True


def _ai_target_for_card(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    target_rule: JsonDict,
) -> JsonDict | None:
    scope = str(target_rule.get('scope', ''))
    candidates = target_candidates(snapshot, side, location, target_rule, source_card=card)
    candidates = [candidate for candidate in candidates if candidate.get('instance_id') != card.get('instance_id')]
    if not candidates:
        return None
    if scope.startswith('opponent'):
        return max(candidates, key=lambda item: int(item.get('computed_power', item.get('base_power', 0)) or 0))
    return min(candidates, key=lambda item: int(item.get('computed_power', item.get('base_power', 0)) or 0))


def _ai_priority(side_state: JsonDict) -> dict[str, int]:
    priority_ids = list(side_state.get('ai_plan', {}).get('priority_card_ids', []))
    return {str(card_id): len(priority_ids) - index for index, card_id in enumerate(priority_ids)}
