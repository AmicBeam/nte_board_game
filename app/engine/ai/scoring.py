from __future__ import annotations

import re
from dataclasses import dataclass

from app.engine.rules.materials import (
    CARD_TYPE_ANOMALY_ITEM,
    CARD_TYPE_ESPER,
    TAG_MATERIAL,
    esper_material_cost,
    esper_material_requirements,
    expanded_material_requirements,
    is_valid_esper_material,
    material_attributes_for_card,
    material_matches_esper_requirement,
    material_matches_requirement,
)
from app.engine.state.types import JsonDict

SIDE_A = 'a'
SIDE_B = 'b'
CARD_TYPE_TOKEN = 'token'
ACE_ESPER_TURNS = {5, 6}
CARD_PLAN_BIAS_SCALE = 0.12
ESPER_PLAN_BIAS_SCALE = 0.18
SELECTION_PLAN_BIAS_SCALE = 0.08
MURK_MATERIAL_BOX_ID = 'murk_basic_material_box'
MURK_BOX_MATERIAL_IDS = frozenset({
    'murk_lost_whisper',
    'murk_faded_shadow',
    'murk_blur_number',
    'murk_fantasy_delusion',
})


@dataclass(frozen=True)
class Contribution:
    total: float
    breakdown: dict[str, float]

    def rounded(self) -> JsonDict:
        return {
            'score': round(self.total, 2),
            'breakdown': {
                key: round(value, 2)
                for key, value in self.breakdown.items()
                if abs(value) >= 0.01
            },
        }


def card_plan_bias(side_state: JsonDict, card: JsonDict) -> float:
    priority_ids = list(side_state.get('ai_plan', {}).get('priority_card_ids', []))
    if not priority_ids:
        return 0.0
    definition_id = str(card.get('definition_id') or '')
    try:
        index = priority_ids.index(definition_id)
    except ValueError:
        return 0.0
    return max(0.0, len(priority_ids) - index) * CARD_PLAN_BIAS_SCALE


def esper_plan_bias(side_state: JsonDict, card: JsonDict) -> float:
    priority_ids = list(side_state.get('ai_plan', {}).get('esper_priority_ids', []))
    if not priority_ids:
        return 0.0
    definition_id = str(card.get('definition_id') or '')
    try:
        index = priority_ids.index(definition_id)
    except ValueError:
        return 0.0
    return max(0.0, len(priority_ids) - index) * ESPER_PLAN_BIAS_SCALE


def selection_plan_bias(side_state: JsonDict, card: JsonDict) -> float:
    priority_ids = list(side_state.get('ai_plan', {}).get('priority_card_ids', []))
    if not priority_ids:
        return 0.0
    definition_id = str(card.get('definition_id') or '')
    try:
        index = priority_ids.index(definition_id)
    except ValueError:
        return 0.0
    return max(0.0, len(priority_ids) - index) * SELECTION_PLAN_BIAS_SCALE


def is_ace_esper(snapshot: JsonDict, side: str, card: JsonDict) -> bool:
    side_state = snapshot['sides'][side]
    ace_ids = {str(card_id) for card_id in side_state.get('ai_plan', {}).get('ace_esper_ids', [])}
    if ace_ids:
        return str(card.get('definition_id') or '') in ace_ids
    return bool(card.get('ai_ace')) or 'ace' in list(card.get('tags', []))


def card_play_contribution(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    *,
    cost: int,
    target: JsonDict | None = None,
) -> Contribution:
    turn = _turn(snapshot)
    raw_power = _raw_power(card)
    gap = _total_power(snapshot, side) - _total_power(snapshot, _opponent_side(side))
    tempo_weight = 0.85 + (0.25 if gap < 0 else 0.0) + (0.2 if turn >= 5 else 0.0)
    setup_weight = max(0.35, 1.35 - turn * 0.14)
    tempo = raw_power * tempo_weight
    efficiency = max(-1.5, raw_power - cost * 0.75) * 0.35
    if cost < 0:
        efficiency += abs(cost) * 2.4 + 1.0
    material = _future_material_value(snapshot, side, location, card) * setup_weight
    effect = _effect_value(snapshot, side, location, card, target=target)
    slot_penalty = _slot_pressure_penalty(location, side, card)
    plan = card_plan_bias(snapshot['sides'][side], card)
    total = tempo + efficiency + material + effect + plan - slot_penalty
    return Contribution(total, {
        'tempo': tempo,
        'efficiency': efficiency,
        'future_material': material,
        'effect': effect,
        'plan_hint': plan,
        'slot_penalty': -slot_penalty,
    })


def esper_contribution(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    material_cards: list[JsonDict],
    *,
    target: JsonDict | None = None,
    is_reactivation: bool = False,
) -> Contribution:
    turn = _turn(snapshot)
    raw_power = _raw_power(card)
    material_power = sum(max(0, _current_power(material)) for material in material_cards)
    late_weight = 1.0 + (0.18 if turn >= 5 else 0.0)
    body = raw_power * late_weight + material_power * 0.12
    effect = _effect_value(snapshot, side, location, card, target=target, is_esper=True)
    ace = _ace_window_value(snapshot, side, card)
    material_cost = _material_opportunity_cost(snapshot, side, location, card, material_cards)
    lineup = _lineup_progress_value(snapshot, side, location, card, is_reactivation=is_reactivation)
    condition = _conditional_esper_value(snapshot, side, location, card)
    reactivation_penalty = 1.75 if is_reactivation else 0.0
    plan = esper_plan_bias(snapshot['sides'][side], card)
    total = body + effect + ace + plan + lineup + condition - material_cost - reactivation_penalty
    return Contribution(total, {
        'body': body,
        'effect': effect,
        'ace_window': ace,
        'plan_hint': plan,
        'lineup_progress': lineup,
        'condition': condition,
        'material_cost': -material_cost,
        'reactivation_penalty': -reactivation_penalty,
    })


def selection_card_contribution(
    snapshot: JsonDict,
    side: str,
    card: JsonDict,
    *,
    location: JsonDict | None = None,
) -> Contribution:
    location = location or _best_own_location(snapshot, side)
    turn = _turn(snapshot)
    raw_power = _raw_power(card)
    cost = int(card.get('cost', 0) or 0)
    material = _future_material_value(snapshot, side, location, card) if location else 0.0
    effect = _effect_value(snapshot, side, location, card, target=None) if location else _text_value(card)
    curve = 1.6 if cost <= max(1, turn + 1) else -1.0
    plan = selection_plan_bias(snapshot['sides'][side], card)
    total = raw_power * 0.45 + material * 1.1 + effect * 0.75 + curve + plan
    return Contribution(total, {
        'power': raw_power * 0.45,
        'future_material': material * 1.1,
        'effect': effect * 0.75,
        'curve': curve,
        'plan_hint': plan,
    })


def declaration_selection_ids(
    snapshot: JsonDict,
    side: str,
    selection: JsonDict,
    *,
    location: JsonDict | None = None,
) -> list[str] | None:
    source = _find_card_by_instance_id(snapshot, str(selection.get('source_instance_id') or ''))
    if _definition_id(source) != MURK_MATERIAL_BOX_ID:
        return None
    return _murk_material_box_selection_ids(snapshot, side, selection, location=location)


def target_contribution(snapshot: JsonDict, side: str, card: JsonDict, target: JsonDict) -> float:
    return _target_value(snapshot, side, card, target)


def _effect_value(
    snapshot: JsonDict,
    side: str,
    location: JsonDict | None,
    card: JsonDict,
    *,
    target: JsonDict | None,
    is_esper: bool = False,
) -> float:
    value = _text_value(card)
    tags = set(str(tag) for tag in card.get('tags', []))
    own_board = _revealed_cards(snapshot, side, location)
    opponent = _opponent_side(side)
    opponent_board = _revealed_cards(snapshot, opponent, location)
    if 'genesis' in tags:
        value += 0.4 + len(own_board) * 0.25
    if 'delay' in tags:
        value += 0.6 + _opponent_esper_threat(snapshot, opponent, location) * 1.3
    if 'murk' in tags:
        value += 0.8 + len(opponent_board) * 0.35
    if 'discord' in tags:
        value += 1.0 + len(opponent_board) * 0.45
    if 'darkstar' in tags:
        value += 0.4 + max(0, _turn(snapshot) - 3) * 0.45
    if is_esper:
        value += 0.8
    text = str(card.get('description') or '')
    delay_setup_condition_unmet = _delay_setup_condition_unmet(snapshot, side, location, card)
    if '设置环合' in text:
        if not delay_setup_condition_unmet:
            value += max(0.0, 4 - _turn(snapshot)) * 0.35
        if (
            '延滞' in text
            and not delay_setup_condition_unmet
            and int((snapshot['sides'][side].get('combo') or {}).get('delay_set_total', 0) or 0) < 2
        ):
            value += 2.6
        if '浊燃' in text:
            value += 1.2
        if '创生' in text:
            value += 1.0 + len(own_board) * 0.15
    if '累计设置的延滞' in text:
        total_set = int((snapshot['sides'][side].get('combo') or {}).get('delay_set_total', 0) or 0)
        value += total_set * 0.55
        if total_set <= 0 and _turn(snapshot) < 5:
            value -= 2.5
    if '消耗所有延滞' in text:
        current_delay = _board_mark_count(snapshot, side, 'delay')
        value += current_delay * 2.2
        if current_delay <= 0:
            value -= 24.0 if _turn(snapshot) < 5 else 16.0
    if _definition_id(card) == MURK_MATERIAL_BOX_ID:
        value += _murk_material_box_effect_value(snapshot, side, location)
    if target is not None:
        value += _target_value(snapshot, side, card, target)
    return value


def _conditional_esper_value(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> float:
    if _delay_setup_condition_unmet(snapshot, side, location, card):
        return -28.0
    return 0.0


def _delay_setup_condition_unmet(
    snapshot: JsonDict,
    side: str,
    location: JsonDict | None,
    card: JsonDict,
) -> bool:
    text = str(card.get('description') or '')
    if '若己方已有延滞' not in text or '设置环合' not in text or '延滞' not in text:
        return False
    if _location_mark_count(location, side, 'delay') > 0:
        return False
    return not _has_queued_delay_setup_before_candidate(snapshot, side, location, card)


def _has_queued_delay_setup_before_candidate(
    snapshot: JsonDict,
    side: str,
    location: JsonDict | None,
    candidate: JsonDict,
) -> bool:
    if location is None:
        return False
    cards = list(location.get('cards', {}).get(side, []))
    candidate_id = str(candidate.get('instance_id') or '')
    candidate_index = next(
        (
            index
            for index, card in enumerate(cards)
            if str(card.get('instance_id') or '') == candidate_id
        ),
        len(cards),
    )
    candidate_sequence = int(candidate.get('play_sequence') or 1_000_000)
    for index, card in enumerate(cards):
        if str(card.get('instance_id') or '') == candidate_id:
            continue
        if not _is_queued_esper_before_candidate(snapshot, card, index, candidate_sequence, candidate_index):
            continue
        if _queued_esper_sets_delay(snapshot, card):
            return True
    return False


def _is_queued_esper_before_candidate(
    snapshot: JsonDict,
    card: JsonDict,
    index: int,
    candidate_sequence: int,
    candidate_index: int,
) -> bool:
    if card.get('type') != CARD_TYPE_ESPER or not card.get('pending_material_ids'):
        return False
    turn = _turn(snapshot)
    if card.get('revealed'):
        if int(card.get('reactivating_turn') or 0) != turn:
            return False
        return index < candidate_index
    if int(card.get('played_turn') or 0) != turn:
        return False
    sequence = int(card.get('play_sequence') or 0)
    if sequence > 0:
        return sequence < candidate_sequence
    return index < candidate_index


def _queued_esper_sets_delay(snapshot: JsonDict, card: JsonDict) -> bool:
    text = str(card.get('description') or '')
    if '设置环合' not in text or '延滞' not in text:
        return False
    if '若己方已有延滞' in text:
        return False
    if '若消耗相属性素材' in text:
        return _pending_materials_include_attribute(snapshot, card, '相')
    return True


def _pending_materials_include_attribute(snapshot: JsonDict, card: JsonDict, attribute: str) -> bool:
    pending_ids = [str(card_id) for card_id in card.get('pending_material_ids', []) if str(card_id)]
    for instance_id in pending_ids:
        material = _find_card_by_instance_id(snapshot, instance_id)
        if material is not None and attribute in material_attributes_for_card(material):
            return True
    return False


def _lineup_progress_value(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    *,
    is_reactivation: bool,
) -> float:
    standby = list(snapshot['sides'][side].get('esper_standby', []))
    turn = _turn(snapshot)
    if not is_reactivation:
        in_lineup = any(
            str(item.get('instance_id') or '') == str(card.get('instance_id') or '')
            for item in standby
        )
        if not in_lineup:
            return 0.0
        remaining = len(standby)
        value = 2.0 + max(0, 5 - remaining) * 1.1
        if turn >= 5:
            value += 1.0 + max(0, 4 - remaining) * 0.45
        return value
    if not standby:
        return 0.0
    playable_standby = 0
    stable_materials = _stable_materials(snapshot, side, location)
    for esper in standby:
        current, required = _material_progress(stable_materials, esper)
        if required and current >= required:
            playable_standby += 1
    value = -(2.8 + len(standby) * 1.15 + playable_standby * 3.2)
    if turn >= 5:
        value -= 1.2
    return value


def _text_value(card: JsonDict) -> float:
    text = f"{card.get('description', '')} {card.get('effect_key', '')}"
    value = 0.0
    if any(token in text for token in ('从牌库', '加入手牌', '检视', '抽')):
        value += 2.1
    if any(token in text for token in ('墓地', '返回手牌', '回手', '回收')):
        value += 1.45
    if any(token in text for token in ('部署', '置入')):
        value += 1.2
    if '设置环合' in text:
        value += 2.0
    if any(token in text for token in ('压低', '伤害', '抹除', '-1', '-2', '-3')):
        value += 1.55
    if any(token in text for token in ('破碎', '返回异能者编队', '封锁')):
        value += 2.0
    if '噩梦' in text:
        value += 2.2
    if '诛恶护持' in text or '判予秋' in text:
        value += 1.8
    if '累计设置的延滞' in text:
        value += 0.8
    return value


def _murk_material_box_effect_value(snapshot: JsonDict, side: str, location: JsonDict | None) -> float:
    location = location or _best_own_location(snapshot, side)
    candidates = _murk_box_material_candidates(snapshot, side)
    if len(candidates) < 2:
        return -2.5
    pair = _best_murk_material_box_pair(snapshot, side, candidates, location=location)
    if pair is None:
        return -1.0
    sent, added, score = pair
    early_bonus = max(0.0, 3 - _turn(snapshot)) * 0.55
    distinct_bonus = 0.8 if str(sent.get('name') or '') != str(added.get('name') or '') else -1.6
    return min(8.0, score * 0.38 + early_bonus + distinct_bonus)


def _murk_material_box_selection_ids(
    snapshot: JsonDict,
    side: str,
    selection: JsonDict,
    *,
    location: JsonDict | None,
) -> list[str] | None:
    candidates = [
        card
        for card in selection.get('cards', [])
        if _definition_id(card) in MURK_BOX_MATERIAL_IDS
    ]
    if len(candidates) < int(selection.get('min_count') or 2):
        return None
    pair = _best_murk_material_box_pair(snapshot, side, candidates, location=location)
    if pair is None:
        return None
    sent, added, _ = pair
    return [str(sent['instance_id']), str(added['instance_id'])]


def _best_murk_material_box_pair(
    snapshot: JsonDict,
    side: str,
    candidates: list[JsonDict],
    *,
    location: JsonDict | None,
) -> tuple[JsonDict, JsonDict, float] | None:
    best: tuple[JsonDict, JsonDict, float] | None = None
    for sent in candidates:
        for added in candidates:
            if str(sent.get('instance_id') or '') == str(added.get('instance_id') or ''):
                continue
            same_name_penalty = 3.5 if str(sent.get('name') or '') == str(added.get('name') or '') else 0.0
            grave_value = _murk_box_grave_value(snapshot, side, sent, location=location)
            hand_value = _murk_box_hand_value(snapshot, side, added, location=location)
            score = grave_value + hand_value - same_name_penalty
            if best is None or score > best[2]:
                best = (sent, added, score)
    return best


def _murk_box_material_candidates(snapshot: JsonDict, side: str) -> list[JsonDict]:
    return [
        card
        for card in snapshot['sides'][side].get('deck', [])
        if _definition_id(card) in MURK_BOX_MATERIAL_IDS
    ]


def _murk_box_grave_value(
    snapshot: JsonDict,
    side: str,
    card: JsonDict,
    *,
    location: JsonDict | None,
) -> float:
    card_id = _definition_id(card)
    text = str(card.get('description') or '')
    value = 0.0
    if '从牌库置入墓地时' in text:
        value += 2.0
    if card_id == 'murk_fantasy_delusion':
        value += 4.2 + _raw_power(card) * 0.65
        value += _future_material_value(snapshot, side, location, card) * 0.45
        if _board_mark_count(snapshot, side, 'murk') > 0:
            value += 1.4
    elif card_id == 'murk_lost_whisper':
        value += 2.0 + _opponent_board_pressure_value(snapshot, side, card, location) * 0.45
    elif card_id == 'murk_faded_shadow':
        value += 2.2 + _opponent_board_pressure_value(snapshot, side, card, location) * 0.45
    elif card_id == 'murk_blur_number':
        value += 1.6 + _remaining_grave_trigger_density(snapshot, side) * 1.2
    return value


def _murk_box_hand_value(
    snapshot: JsonDict,
    side: str,
    card: JsonDict,
    *,
    location: JsonDict | None,
) -> float:
    value = selection_card_contribution(snapshot, side, card, location=location).total
    value += _future_material_value(snapshot, side, location, card) * 0.35
    if int(card.get('cost') or 0) <= max(1, _turn(snapshot) + 1):
        value += 0.6
    if _definition_id(card) == 'murk_blur_number' and _has_staged_or_revealed_murk_esper(snapshot, side):
        value += 1.2
    return value


def _opponent_board_pressure_value(
    snapshot: JsonDict,
    side: str,
    card: JsonDict,
    location: JsonDict | None,
) -> float:
    opponent = _opponent_side(side)
    candidates = _revealed_cards(snapshot, opponent, location)
    if not candidates:
        return 0.4
    return max(_target_value(snapshot, side, card, target) for target in candidates)


def _remaining_grave_trigger_density(snapshot: JsonDict, side: str) -> float:
    deck = snapshot['sides'][side].get('deck', [])
    if not deck:
        return 0.0
    trigger_count = sum(1 for card in deck if '从牌库置入墓地时' in str(card.get('description') or ''))
    return min(2.0, trigger_count / max(1, len(deck)) * 3)


def _has_staged_or_revealed_murk_esper(snapshot: JsonDict, side: str) -> bool:
    return any(
        card.get('type') == CARD_TYPE_ESPER and str(card.get('attribute') or '') == '咒'
        for location in snapshot.get('locations', [])
        for card in location.get('cards', {}).get(side, [])
        if card.get('staged') or card.get('revealed')
    )


def _target_value(snapshot: JsonDict, side: str, card: JsonDict, target: JsonDict) -> float:
    opponent = _opponent_side(side)
    target_side = str(target.get('side') or '')
    power = _current_power(target)
    amount = _estimated_negative_amount(card)
    if target_side == opponent:
        value = 1.0
        if target.get('type') == CARD_TYPE_ESPER:
            value += 3.0
        if TAG_MATERIAL in set(target.get('tags', [])):
            value += 1.5
        if amount > 0:
            value += min(3.0, amount * 0.9)
            if power > 0 and power - amount <= 0:
                value += 4.0
        if _material_feeds_any_standby(snapshot, opponent, target):
            value += 2.4
        return value
    value = 0.7
    if target.get('type') == CARD_TYPE_ANOMALY_ITEM:
        value += 0.5
    if _current_power(target) < int(target.get('base_power', 0) or 0):
        value += 1.8
    if _material_feeds_any_standby(snapshot, side, target):
        value += 1.1
    return value


def _estimated_negative_amount(card: JsonDict) -> int:
    text = f"{card.get('description', '')} {card.get('effect_key', '')}"
    matches = [int(match.group(1)) for match in re.finditer(r'[-－](\d+)', text)]
    if matches:
        return max(matches)
    if any(token in text for token in ('压低', '伤害', '抹除')):
        return 1
    return 0


def _future_material_value(snapshot: JsonDict, side: str, location: JsonDict | None, card: JsonDict) -> float:
    if card.get('type') != CARD_TYPE_ANOMALY_ITEM or TAG_MATERIAL not in set(card.get('tags', [])):
        return 0.0
    if location is None:
        return 0.6
    turn = _turn(snapshot)
    if turn >= int(snapshot.get('max_turns') or 6):
        window = 0.35
    elif turn >= 5:
        window = 0.75
    else:
        window = 1.0
    stable_materials = _stable_materials(snapshot, side, location)
    value = 0.65
    standby = list(snapshot['sides'][side].get('esper_standby', []))
    for esper in standby:
        fit = _material_fit_score(card, esper)
        if fit <= 0:
            continue
        current, required = _material_progress(stable_materials, esper)
        after, _ = _material_progress([*stable_materials, card], esper)
        ace_weight = 1.35 if is_ace_esper(snapshot, side, esper) else 1.0
        urgency = 1.0 + max(0, turn - 3) * 0.18
        value += min(3.0, fit) * ace_weight * urgency
        if current < required <= after:
            value += 3.0 * ace_weight
        elif after > current:
            value += 0.8 * ace_weight
    reserved_for = {str(card_id) for card_id in card.get('ai_material_reserved_for', []) if str(card_id)}
    if reserved_for:
        standby_ids = {str(esper.get('definition_id') or '') for esper in standby}
        if reserved_for.intersection(standby_ids):
            value += 1.1
    return value * window


def _ace_window_value(snapshot: JsonDict, side: str, card: JsonDict) -> float:
    if not is_ace_esper(snapshot, side, card):
        return 0.0
    turn = _turn(snapshot)
    if turn in ACE_ESPER_TURNS:
        return 4.5
    if turn == 4:
        return 1.0
    if turn <= 3:
        return 0.2
    return 1.0


def _material_opportunity_cost(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    esper: JsonDict,
    material_cards: list[JsonDict],
) -> float:
    standby = [
        card
        for card in snapshot['sides'][side].get('esper_standby', [])
        if str(card.get('instance_id') or '') != str(esper.get('instance_id') or '')
    ]
    cost = 0.0
    esper_id = str(esper.get('definition_id') or '')
    stable_materials = _stable_materials(snapshot, side, location)
    for material in material_cards:
        reserved_for = {str(card_id) for card_id in material.get('ai_material_reserved_for', []) if str(card_id)}
        if reserved_for and esper_id not in reserved_for:
            cost += 4.4
        remaining_materials = [
            item
            for item in stable_materials
            if str(item.get('instance_id') or '') != str(material.get('instance_id') or '')
        ]
        for other in standby:
            fit = _material_fit_score(material, other)
            if fit <= 0:
                continue
            current, required = _material_progress(stable_materials, other)
            after_removal, _ = _material_progress(remaining_materials, other)
            if current < required:
                cost += min(1.2, fit * 0.25)
                if is_ace_esper(snapshot, side, other):
                    cost += 0.8
            elif after_removal < current:
                cost += 1.8
                if is_ace_esper(snapshot, side, other):
                    cost += 3.2
                if fit >= 4:
                    cost += 2.0
    return cost


def _material_fit_score(card: JsonDict, esper: JsonDict) -> float:
    if card.get('type') != CARD_TYPE_ANOMALY_ITEM or TAG_MATERIAL not in set(card.get('tags', [])):
        return 0.0
    requirements = esper_material_requirements(esper)
    if requirements:
        best = 0.0
        for requirement in requirements:
            if not material_matches_requirement(card, requirement):
                continue
            if requirement.get('name'):
                best = max(best, 4.0)
            elif requirement.get('category'):
                best = max(best, 2.2)
            elif requirement.get('attribute') or requirement.get('attributes'):
                best = max(best, 2.6)
            else:
                best = max(best, 1.2)
        return best
    return 2.4 if material_matches_esper_requirement(card, esper) else 0.0


def _material_progress(cards: list[JsonDict], esper: JsonDict) -> tuple[int, int]:
    requirements = expanded_material_requirements(esper_material_requirements(esper))
    if not requirements:
        required = esper_material_cost(esper)
        count = sum(1 for card in cards if material_matches_esper_requirement(card, esper))
        return min(count, required), required
    used_indexes: set[int] = set()
    matches = 0
    ordered_requirements = sorted(
        requirements,
        key=lambda requirement: (
            0 if requirement.get('name') else 1,
            0 if requirement.get('category') else 1,
            str(requirement),
        ),
    )
    for requirement in ordered_requirements:
        for index, card in enumerate(cards):
            if index in used_indexes:
                continue
            if not material_matches_requirement(card, requirement):
                continue
            used_indexes.add(index)
            matches += 1
            break
    return matches, len(requirements)


def _material_feeds_any_standby(snapshot: JsonDict, side: str, card: JsonDict) -> bool:
    return any(_material_fit_score(card, esper) > 0 for esper in snapshot['sides'][side].get('esper_standby', []))


def _opponent_esper_threat(snapshot: JsonDict, opponent: str, location: JsonDict | None) -> int:
    if location is None:
        return 0
    materials = _stable_materials(snapshot, opponent, location)
    threat = 0
    for esper in snapshot['sides'][opponent].get('esper_standby', []):
        current, required = _material_progress(materials, esper)
        if current >= required:
            threat += 2
        elif current + 1 >= required:
            threat += 1
    return threat


def _board_mark_count(snapshot: JsonDict, side: str, tag: str) -> int:
    return sum(
        int(location.get('marks', {}).get(side, {}).get(tag, 0) or 0)
        for location in snapshot.get('locations', [])
    )


def _location_mark_count(location: JsonDict | None, side: str, tag: str) -> int:
    if location is None:
        return 0
    return int(location.get('marks', {}).get(side, {}).get(tag, 0) or 0)


def _stable_materials(snapshot: JsonDict, side: str, location: JsonDict) -> list[JsonDict]:
    turn = _turn(snapshot)
    return [
        card
        for card in location.get('cards', {}).get(side, [])
        if is_valid_esper_material(card, current_turn=turn)
    ]


def _revealed_cards(snapshot: JsonDict, side: str, location: JsonDict | None = None) -> list[JsonDict]:
    locations = [location] if location is not None else list(snapshot.get('locations', []))
    return [
        card
        for item in locations
        for card in item.get('cards', {}).get(side, [])
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]


def _best_own_location(snapshot: JsonDict, side: str) -> JsonDict | None:
    locations = list(snapshot.get('locations', []))
    if not locations:
        return None
    return max(
        locations,
        key=lambda location: int(location.get('power', {}).get(side, 0) or 0),
    )


def _slot_pressure_penalty(location: JsonDict, side: str, card: JsonDict) -> float:
    if card.get('type') == CARD_TYPE_ESPER:
        return 0.0
    capacity = max(1, int(location.get('capacity') or 7))
    occupied = sum(
        1
        for item in location.get('cards', {}).get(side, [])
        if not item.get('reserved_as_material_for')
    )
    if occupied < capacity - 1:
        return 0.0
    return 0.75


def _total_power(snapshot: JsonDict, side: str) -> int:
    return sum(int(location.get('power', {}).get(side, 0) or 0) for location in snapshot.get('locations', []))


def _current_power(card: JsonDict) -> int:
    return int(card.get('computed_power', _raw_power(card)) or 0)


def _raw_power(card: JsonDict) -> int:
    return int(card.get('base_power', card.get('power', 0)) or 0) + int(card.get('bonus_power', 0) or 0)


def _definition_id(card: JsonDict | None) -> str:
    if not isinstance(card, dict):
        return ''
    return str(card.get('definition_id') or card.get('id') or '')


def _find_card_by_instance_id(snapshot: JsonDict, instance_id: str) -> JsonDict | None:
    if not instance_id:
        return None
    for location in snapshot.get('locations', []):
        for side in (SIDE_A, SIDE_B):
            for card in location.get('cards', {}).get(side, []):
                if str(card.get('instance_id') or '') == instance_id:
                    return card
    return None


def _turn(snapshot: JsonDict) -> int:
    return int(snapshot.get('turn') or 1)


def _opponent_side(side: str) -> str:
    return SIDE_B if side == SIDE_A else SIDE_A
