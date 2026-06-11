from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.content.loader import get_duel_card
from app.engine.state.types import JsonDict
from app.errors import RuleValidationError

SIDE_A = 'a'
SIDE_B = 'b'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'
CARD_TYPE_TOKEN = 'token'
LOG_LIMIT = 28

SPECIAL_TARGET_RULES: dict[str, JsonDict] = {
    'genesis_marble_soda': {
        'scope': 'ally_item_same_location',
        'prompt': '选择 1 张己方战力不高于 2 的道具。',
    },
    'genesis_chip_washer': {
        'scope': 'ally_damaged_food_same_location',
        'prompt': '选择 1 张己方当前战力低于基础战力的食物道具。',
    },
    'delay_mind_sync': {
        'scope': 'opponent_power_lte_3_same_location',
        'prompt': '选择 1 张对手战力不高于 3 的卡牌。',
    },
    'delay_water_hesitation': {
        'scope': 'opponent_same_location',
        'prompt': '选择 1 张对手道具。',
    },
    'delay_nestling_hope': {
        'scope': 'ally_xiang_item_same_location',
        'prompt': '选择 1 张己方相属性道具。',
    },
    'murk_lost_whisper': {
        'scope': 'opponent_same_location',
        'prompt': '选择 1 张对手道具。',
    },
}
REQUIRED_TARGET_BEFORE_PLAY_IDS = frozenset({
    'genesis_chip_washer',
    'delay_mind_sync',
})


def prepare_declaration_selection(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    selected_target: JsonDict | None = None,
) -> bool:
    if snapshot['sides'][side].get('selection'):
        return False
    step = _declaration_card_step(card)
    if not step:
        return False
    candidates = _declaration_candidates(snapshot, side, location, card, step, selected_target)
    if not candidates:
        return False
    title = str(step.get('title') or f"{card.get('name', '卡牌')} 检视牌库")
    description = str(step.get('description') or '宣言 1 张合法卡牌；揭示时执行。')
    pick_count = int(step.get('pick_count') or 1)
    min_count = int(step.get('min_count') if step.get('min_count') is not None else pick_count)
    snapshot['sides'][side]['selection'] = {
        'kind': 'declaration',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'title': title,
        'description': description,
        'pick_count': pick_count,
        'min_count': min_count,
        'max_count': pick_count,
        'cards': candidates,
    }
    return True


def prepare_declaration_target(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> bool:
    target_rule = target_rule_internal(card)
    if not target_rule:
        return False
    scope = str(target_rule.get('scope', ''))
    candidates = [
        candidate
        for candidate in target_candidates(snapshot, side, location, target_rule, source_card=card)
        if candidate.get('instance_id') != card.get('instance_id')
    ]
    if not candidates:
        return False
    snapshot['sides'][side]['pending_target'] = {
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'scope': scope,
        'prompt': target_rule.get('prompt', '请选择一个目标。'),
    }
    return True


def resolve_declaration_selection(snapshot: JsonDict, side: str, selected_ids: list[str]) -> None:
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


def target_rule(card: JsonDict) -> JsonDict:
    return _public_target_rule(target_rule_internal(card))


def target_rule_internal(card: JsonDict) -> JsonDict:
    definition = get_duel_card(str(card.get('definition_id', ''))) or {}
    rule = definition.get('target_rule') or _declaration_board_step(card) or SPECIAL_TARGET_RULES.get(str(card.get('definition_id', '')), {}) or {}
    return deepcopy(rule)


def requires_target_before_play(card: JsonDict) -> bool:
    rule = target_rule_internal(card)
    return bool(rule.get('required_before_play')) or str(card.get('definition_id') or '') in REQUIRED_TARGET_BEFORE_PLAY_IDS


def has_required_target_before_play(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> bool:
    if not requires_target_before_play(card):
        return True
    rule = target_rule_internal(card)
    if not rule:
        return True
    candidates = [
        candidate
        for candidate in target_candidates(snapshot, side, location, rule, source_card=card)
        if candidate.get('instance_id') != card.get('instance_id')
    ]
    return bool(candidates)


def ensure_required_target_before_play(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    if not has_required_target_before_play(snapshot, side, location, card):
        raise RuleValidationError('需要可选择的己方道具。')


def find_target_card(
    snapshot: JsonDict,
    side: str,
    source_location: JsonDict,
    source_card: JsonDict,
    target_instance_id: str,
) -> JsonDict:
    rule = target_rule_internal(source_card)
    candidates = target_candidates(snapshot, side, source_location, rule, source_card=source_card)
    for card in candidates:
        if card['instance_id'] == target_instance_id:
            return card
    raise RuleValidationError('请选择合法的战场目标。')


def target_candidates(
    snapshot: JsonDict,
    side: str,
    source_location: JsonDict,
    scope_or_rule: str | JsonDict,
    *,
    source_card: JsonDict | None = None,
) -> list[JsonDict]:
    if isinstance(scope_or_rule, dict):
        scope = str(scope_or_rule.get('scope', ''))
        predicate = scope_or_rule.get('predicate')
    else:
        scope = str(scope_or_rule)
        predicate = None
    opponent = _opponent_side(side)
    if scope == 'opponent_same_location':
        candidates = [card for card in source_location['cards'][opponent] if card.get('revealed')]
    elif scope == 'opponent_power_lte_3_same_location':
        candidates = [
            card
            for card in source_location['cards'][opponent]
            if card.get('revealed')
            and card.get('type') != CARD_TYPE_TOKEN
            and int(card.get('computed_power', _raw_card_power(card)) or 0) <= 3
        ]
    elif scope == 'opponent_any':
        candidates = [
            card
            for location in snapshot['locations']
            for card in location['cards'][opponent]
            if card.get('revealed')
        ]
    elif scope == 'ally_any':
        candidates = [
            card
            for location in snapshot['locations']
            for card in location['cards'][side]
            if card.get('revealed')
        ]
    elif scope == 'ally_same_location':
        candidates = [card for card in source_location['cards'][side] if card.get('revealed')]
    elif scope == 'ally_item_same_location':
        candidates = [
            card
            for card in source_location['cards'][side]
            if card.get('revealed') and card.get('type') == CARD_TYPE_ANOMALY_ITEM
        ]
    elif scope == 'ally_xiang_item_same_location':
        candidates = [
            card
            for card in source_location['cards'][side]
            if (
                card.get('revealed')
                and card.get('type') == CARD_TYPE_ANOMALY_ITEM
                and str(card.get('attribute') or '') == '相'
            )
        ]
    elif scope == 'ally_damaged_food_same_location':
        candidates = [
            card
            for card in source_location['cards'][side]
            if card.get('revealed')
            and card.get('type') == CARD_TYPE_ANOMALY_ITEM
            and str(card.get('category') or '') == '食物'
            and int(card.get('computed_power', _raw_card_power(card)) or 0) < int(card.get('base_power') or 0)
        ]
    else:
        raise RuleValidationError('这张牌的目标规则无效。')
    context = {
        'snapshot': snapshot,
        'side': side,
        'opponent_side': opponent,
        'source': source_card,
        'location': source_location,
        'zone': 'board',
    }
    return [candidate for candidate in candidates if _declaration_predicate_matches(predicate, candidate, context)]


def _declaration_candidates(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    card: JsonDict,
    step: JsonDict,
    selected_target: JsonDict | None = None,
) -> list[JsonDict]:
    side_state = snapshot['sides'][side]
    zones = _declaration_zones(step)
    if not zones:
        return []
    predicate = step.get('predicate')
    selected_target = selected_target or _find_card_on_board(snapshot, str(card.get('selected_target_instance_id') or ''))
    context = {
        'snapshot': snapshot,
        'side': side,
        'opponent_side': _opponent_side(side),
        'source': card,
        'location': location,
        'selected_target': selected_target,
    }
    candidates: list[JsonDict] = []
    for zone_name in zones:
        for candidate in side_state.get(zone_name, []):
            zone_context = {**context, 'zone': zone_name}
            if _declaration_predicate_matches(predicate, candidate, zone_context):
                candidates.append(candidate)
    if any(zone_name in {'deck', 'discard'} for zone_name in zones):
        candidates = _dedupe_declaration_cards(candidates) if bool(step.get('dedupe', True)) else list(candidates)
        candidates.sort(key=_card_instance_sort_key)
    return candidates


def _declaration_zones(step: JsonDict) -> list[str]:
    raw_zones = step.get('zones', step.get('zone', step.get('source', [])))
    if isinstance(raw_zones, str):
        raw_zones = [raw_zones]
    zones: list[str] = []
    for zone_name in raw_zones or []:
        normalized = str(zone_name or '').strip()
        if normalized in {'hand', 'deck', 'discard'} and normalized not in zones:
            zones.append(normalized)
    return zones


def _dedupe_declaration_cards(cards: list[JsonDict]) -> list[JsonDict]:
    deduped: list[JsonDict] = []
    seen: set[str] = set()
    for card in cards:
        key = str(card.get('definition_id') or card.get('name') or card.get('instance_id') or '')
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
    return deduped


def _card_instance_sort_key(card: JsonDict) -> tuple[int, int, int, str, str]:
    definition_id = str(card.get('definition_id') or '')
    return (
        *_card_sort_key(definition_id),
        str(card.get('instance_id') or ''),
    )


def _card_sort_key(card_id: str) -> tuple[int, int, int, str]:
    card = get_duel_card(str(card_id)) or {}
    attribute_order = {'灵': 0, '光': 1, '相': 2, '咒': 3, '暗': 4, '魂': 5}
    attribute = str(card.get('attribute') or card.get('required_material_attribute') or card.get('element') or '')
    cost = int(card.get('material_cost') or card.get('cost') or 0)
    power = int(card.get('power') or 0)
    return (attribute_order.get(attribute, 99), cost, power, str(card.get('name') or card_id))


def _declaration_predicate_matches(predicate: Any, candidate: JsonDict, context: JsonDict) -> bool:
    if predicate is None:
        return True
    if not callable(predicate):
        return bool(predicate)
    try:
        return bool(predicate(candidate, context))
    except TypeError:
        return bool(predicate(candidate))


def _declaration_steps(card: JsonDict) -> list[JsonDict]:
    definition = get_duel_card(str(card.get('definition_id', ''))) or {}
    declaration = definition.get('declaration') or {}
    if isinstance(declaration, list):
        raw_steps = declaration
    elif isinstance(declaration, dict):
        raw_steps = declaration.get('steps') if isinstance(declaration.get('steps'), list) else [declaration]
    else:
        raw_steps = []
    return [step for step in raw_steps if isinstance(step, dict)]


def _declaration_board_step(card: JsonDict) -> JsonDict:
    for step in _declaration_steps(card):
        if str(step.get('kind') or step.get('type') or '').strip() == 'board':
            return step
    return {}


def _declaration_card_step(card: JsonDict) -> JsonDict:
    for step in _declaration_steps(card):
        kind = str(step.get('kind') or step.get('type') or '').strip()
        if kind in {'cards', 'card', 'hand', 'deck', 'discard'} or _declaration_zones(step):
            return step
    return {}


def _public_target_rule(target_rule: JsonDict) -> JsonDict:
    if not target_rule:
        return {}
    public_rule = {
        'scope': target_rule.get('scope', ''),
        'prompt': target_rule.get('prompt', '请选择一个目标。'),
    }
    if target_rule.get('required_before_play'):
        public_rule['required_before_play'] = True
    return public_rule


def _find_card_on_board(snapshot: JsonDict, instance_id: str) -> JsonDict | None:
    for location in snapshot['locations']:
        for side in snapshot.get('sides', {}):
            for card in location['cards'].get(side, []):
                if card['instance_id'] == instance_id:
                    return card
    return None


def _opponent_side(side: str) -> str:
    return SIDE_B if side == SIDE_A else SIDE_A


def _raw_card_power(card: JsonDict) -> int:
    return int(card.get('base_power', 0)) + int(card.get('bonus_power', 0))


def _add_log(snapshot: JsonDict, message: str) -> None:
    snapshot.setdefault('log', []).insert(0, message)
    del snapshot['log'][LOG_LIMIT:]
