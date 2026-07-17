from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.modules.card_game.engine.ai.scoring import (
    Contribution,
    card_play_contribution,
    esper_contribution,
    target_contribution,
)
from app.modules.card_game.engine.rules.declarations import (
    has_required_target_before_play,
    prepare_declaration_selection,
    target_candidates,
    target_rule_internal,
)
from app.modules.card_game.engine.rules.materials import (
    location_has_room_after_materials,
    material_cards_for_esper,
    reserve_materials,
)
from app.modules.card_game.engine.state.types import JsonDict
from app.errors import RuleValidationError

CARD_TYPE_ESPER = 'esper'
MIN_AI_ACTION_SCORE = 0.25


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


@dataclass(frozen=True)
class AiCardOption:
    card: JsonDict
    location: JsonDict
    cost: int
    target: JsonDict | None
    contribution: Contribution


@dataclass(frozen=True)
class AiEsperOption:
    card: JsonDict
    location: JsonDict
    material_cards: list[JsonDict]
    target: JsonDict | None
    contribution: Contribution
    is_reactivation: bool = False


def run_ai_turn(snapshot: JsonDict, side: str, rules: AiRules) -> None:
    rules.resolve_pending_choices(snapshot, side)
    if snapshot['sides'][side]['ended_turn']:
        return
    while True:
        action = _best_ai_action(snapshot, side, rules)
        if action is None:
            break
        kind, option = action
        if kind == 'card':
            _stage_card_option(snapshot, side, rules, option)  # type: ignore[arg-type]
        elif option.is_reactivation:  # type: ignore[union-attr]
            _stage_reactivation_option(snapshot, side, rules, option)  # type: ignore[arg-type]
        else:
            _stage_esper_option(snapshot, side, rules, option)  # type: ignore[arg-type]
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 完成置入。")


def _best_ai_action(
    snapshot: JsonDict,
    side: str,
    rules: AiRules,
) -> tuple[str, AiCardOption | AiEsperOption] | None:
    card_option = _best_card_option(snapshot, side, rules)
    standby_option = _best_standby_esper_option(snapshot, side, rules)
    reactivation_option = _best_reactivation_option(snapshot, side, rules)
    options: list[tuple[str, AiCardOption | AiEsperOption, float]] = []
    if card_option is not None:
        options.append(('card', card_option, card_option.contribution.total))
    if standby_option is not None:
        options.append(('esper', standby_option, standby_option.contribution.total))
    if reactivation_option is not None:
        options.append(('esper', reactivation_option, reactivation_option.contribution.total))
    if not options:
        return None
    kind, option, score = max(options, key=lambda item: item[2])
    if score < MIN_AI_ACTION_SCORE:
        return None
    return kind, option


def _ai_play_one_card(snapshot: JsonDict, side: str, rules: AiRules) -> bool:
    option = _best_card_option(snapshot, side, rules)
    if option is None or option.contribution.total < MIN_AI_ACTION_SCORE:
        return False
    _stage_card_option(snapshot, side, rules, option)
    return True


def _best_card_option(snapshot: JsonDict, side: str, rules: AiRules) -> AiCardOption | None:
    hand = snapshot['sides'][side]['hand']
    energy_remaining = rules.energy_remaining(snapshot, side)
    open_locations = rules.open_locations(snapshot, side)
    options: list[AiCardOption] = []
    rules.recompute_scores(snapshot)
    for card in hand:
        for location in open_locations:
            if not has_required_target_before_play(snapshot, side, location, card):
                continue
            cost = rules.cost_to_play(snapshot, side, card, location)
            if cost <= energy_remaining:
                target_rule = target_rule_internal(card)
                target = _ai_target_for_card(snapshot, side, location, card, target_rule) if target_rule else None
                contribution = card_play_contribution(
                    snapshot,
                    side,
                    location,
                    card,
                    cost=cost,
                    target=target,
                )
                options.append(AiCardOption(card, location, cost, target, contribution))
    if not options:
        return None
    return max(
        options,
        key=lambda option: (
            option.contribution.total,
            option.location['power'][rules.opponent_side(side)] - option.location['power'][side],
            rules.raw_card_power(option.card),
            -int(option.cost),
        ),
    )


def _stage_card_option(snapshot: JsonDict, side: str, rules: AiRules, option: AiCardOption) -> None:
    card = option.card
    location = option.location
    cost = option.cost
    hand = snapshot['sides'][side]['hand']
    hand.remove(card)
    card['played_turn'] = snapshot['turn']
    card['location_id'] = location['id']
    card['revealed'] = False
    card['staged'] = True
    card['paid_cost'] = cost
    card['play_sequence'] = rules.next_play_sequence(snapshot)
    card['ai_contribution'] = option.contribution.rounded()
    snapshot['sides'][side]['energy_used'] += cost
    location['cards'][side].append(card)
    if rules.delay_tax(snapshot, side, location):
        rules.consume_delay_tax(snapshot, side, location)
    target_rule = target_rule_internal(card)
    if target_rule:
        target = option.target or _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            prepare_declaration_selection(snapshot, side, location, card, target)
            rules.resolve_pending_choices(snapshot, side)
    else:
        prepare_declaration_selection(snapshot, side, location, card)
        rules.resolve_pending_choices(snapshot, side)
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 将一张牌置入 {location['name']}。")


def _ai_play_one_esper(snapshot: JsonDict, side: str, rules: AiRules) -> bool:
    option = _best_standby_esper_option(snapshot, side, rules)
    if option is None or option.contribution.total < MIN_AI_ACTION_SCORE:
        return False
    _stage_esper_option(snapshot, side, rules, option)
    return True


def _best_standby_esper_option(snapshot: JsonDict, side: str, rules: AiRules) -> AiEsperOption | None:
    options = _ai_standby_esper_options(snapshot, side, rules)
    return _best_esper_option(snapshot, side, rules, options, is_reactivation=False)


def _best_esper_option(
    snapshot: JsonDict,
    side: str,
    rules: AiRules,
    options: list[tuple[JsonDict, JsonDict, list[JsonDict]]],
    *,
    is_reactivation: bool,
) -> AiEsperOption | None:
    if not options:
        return None
    rules.recompute_scores(snapshot)
    scored_options: list[AiEsperOption] = []
    for card, location, material_cards in options:
        target_rule = target_rule_internal(card)
        target = _ai_target_for_card(snapshot, side, location, card, target_rule) if target_rule else None
        contribution = esper_contribution(
            snapshot,
            side,
            location,
            card,
            material_cards,
            target=target,
            is_reactivation=is_reactivation,
        )
        scored_options.append(AiEsperOption(card, location, material_cards, target, contribution, is_reactivation))
    return max(
        scored_options,
        key=lambda option: (
            option.contribution.total,
            rules.raw_card_power(option.card),
        ),
    )


def _stage_esper_option(snapshot: JsonDict, side: str, rules: AiRules, option: AiEsperOption) -> None:
    card = option.card
    location = option.location
    material_cards = option.material_cards
    snapshot['sides'][side].setdefault('esper_standby', []).remove(card)
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
    card['ai_contribution'] = option.contribution.rounded()
    location['cards'][side].append(card)
    target_rule = target_rule_internal(card)
    if target_rule:
        target = option.target or _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            prepare_declaration_selection(snapshot, side, location, card, target)
            rules.resolve_pending_choices(snapshot, side)
    else:
        prepare_declaration_selection(snapshot, side, location, card)
        rules.resolve_pending_choices(snapshot, side)
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 准备让一名异能者登场于 {location['name']}。")


def _ai_reactivate_one_esper(snapshot: JsonDict, side: str, rules: AiRules) -> bool:
    option = _best_reactivation_option(snapshot, side, rules)
    if option is None or option.contribution.total < MIN_AI_ACTION_SCORE:
        return False
    _stage_reactivation_option(snapshot, side, rules, option)
    return True


def _best_reactivation_option(snapshot: JsonDict, side: str, rules: AiRules) -> AiEsperOption | None:
    if rules.side_reactivation_used(snapshot, side):
        return None
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
                material_cards = _ai_material_cards_for_esper(snapshot, side, location, card)
            except RuleValidationError:
                continue
            revealed_espers.append((card, location, material_cards))
    if not revealed_espers:
        return None
    return _best_esper_option(snapshot, side, rules, revealed_espers, is_reactivation=True)


def _stage_reactivation_option(snapshot: JsonDict, side: str, rules: AiRules, option: AiEsperOption) -> None:
    card = option.card
    location = option.location
    material_cards = option.material_cards
    material_ids = [item['instance_id'] for item in material_cards]
    reserve_materials(material_cards, card['instance_id'])
    card['pending_material_ids'] = material_ids
    card['reactivating_turn'] = snapshot['turn']
    card['ai_contribution'] = option.contribution.rounded()
    rules.mark_side_reactivation(snapshot, side)
    target_rule = target_rule_internal(card)
    if target_rule:
        target = option.target or _ai_target_for_card(snapshot, side, location, card, target_rule)
        if target is not None:
            card['selected_target_instance_id'] = target['instance_id']
            card['selected_target_name'] = target.get('name', '')
            prepare_declaration_selection(snapshot, side, location, card, target)
            rules.resolve_pending_choices(snapshot, side)
    else:
        prepare_declaration_selection(snapshot, side, location, card)
        rules.resolve_pending_choices(snapshot, side)
    rules.add_log(snapshot, f"{rules.side_name(snapshot, side)} 准备让 {card['name']} 再共鸣。")


def _ai_standby_esper_options(snapshot: JsonDict, side: str, rules: AiRules) -> list[tuple[JsonDict, JsonDict, list[JsonDict]]]:
    standby = snapshot['sides'][side].setdefault('esper_standby', [])
    if not standby:
        return []
    open_locations = [location for location in snapshot['locations'] if rules.is_location_revealed(snapshot, location)]
    options: list[tuple[JsonDict, JsonDict, list[JsonDict]]] = []
    for card in standby:
        for location in open_locations:
            try:
                material_cards = _ai_material_cards_for_esper(snapshot, side, location, card)
            except RuleValidationError:
                continue
            if location_has_room_after_materials(location, side, material_cards):
                options.append((card, location, material_cards))
    return options


def _ai_material_cards_for_esper(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> list[JsonDict]:
    default_materials = material_cards_for_esper(snapshot, side, location, card)
    avoided_ids = _ai_selected_ally_target_ids(location, side)
    if not avoided_ids or not any(str(material.get('instance_id') or '') in avoided_ids for material in default_materials):
        return default_materials
    filtered_cards = [
        candidate
        for candidate in location.get('cards', {}).get(side, [])
        if str(candidate.get('instance_id') or '') not in avoided_ids
    ]
    filtered_location = {
        **location,
        'cards': {
            **location.get('cards', {}),
            side: filtered_cards,
        },
    }
    try:
        return material_cards_for_esper(snapshot, side, filtered_location, card)
    except RuleValidationError:
        return default_materials


def _ai_selected_ally_target_ids(location: JsonDict, side: str) -> set[str]:
    board_ids = {str(card.get('instance_id') or '') for card in location.get('cards', {}).get(side, [])}
    return {
        str(card.get('selected_target_instance_id') or '')
        for card in location.get('cards', {}).get(side, [])
        if card.get('staged')
        and not card.get('revealed')
        and str(card.get('selected_target_instance_id') or '') in board_ids
    }


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
        return max(
            candidates,
            key=lambda item: (
                target_contribution(snapshot, side, card, item),
                int(item.get('computed_power', item.get('base_power', 0)) or 0),
            ),
        )
    return max(
        candidates,
        key=lambda item: (
            target_contribution(snapshot, side, card, item),
            -int(item.get('computed_power', item.get('base_power', 0)) or 0),
        ),
    )
