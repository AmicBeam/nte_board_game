from __future__ import annotations

from app.content.common.constants import LOCATION_CARD_LIMIT
from app.engine.state.types import JsonDict
from app.errors import RuleValidationError

TAG_MATERIAL = 'material'
TAG_HARMONY = 'harmony'
CARD_TYPE_ESPER = 'esper'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'
CARD_TYPE_TOKEN = 'token'


def esper_material_cost(card: JsonDict) -> int:
    requirements = esper_material_requirements(card)
    if requirements:
        return sum(int(requirement.get('count') or 1) for requirement in requirements)
    return max(2, min(3, int(card.get('material_cost') or 2)))


def material_cards_for_esper(
    snapshot: JsonDict,
    side: str,
    location: JsonDict,
    esper_card: JsonDict,
    material_instance_ids: list[str] | None = None,
) -> list[JsonDict]:
    required = esper_material_cost(esper_card)
    requirements = esper_material_requirements(esper_card)
    candidates = [
        card
        for card in location.get('cards', {}).get(side, [])
        if card.get('instance_id') != esper_card.get('instance_id')
        and is_valid_esper_material(card, current_turn=int(snapshot.get('turn') or 0))
        and (
            material_matches_esper_requirement(card, esper_card)
            if not requirements
            else material_matches_any_requirement(card, requirements)
        )
    ]
    if material_instance_ids is not None:
        selected_ids = unique_ids(material_instance_ids)
        if len(selected_ids) != required:
            raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要指定 {esper_material_requirement_text(esper_card)}。")
        candidates_by_id = {str(card.get('instance_id')): card for card in candidates}
        selected_cards = [candidates_by_id.get(instance_id) for instance_id in selected_ids]
        if any(card is None for card in selected_cards):
            raise RuleValidationError(f"只能选择{esper_material_filter_text(esper_card)}。")
        if requirements and not materials_satisfy_requirements([card for card in selected_cards if card is not None], requirements):
            raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要{esper_material_requirement_text(esper_card)}。")
        return [card for card in selected_cards if card is not None]
    candidates.sort(key=lambda card: (
        0 if card.get('type') == CARD_TYPE_TOKEN else 1,
        int(card.get('computed_power', card.get('base_power', 0)) or 0),
        str(card.get('name', '')),
    ))
    if requirements:
        selected = select_materials_for_requirements(candidates, requirements)
        if len(selected) < required:
            raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要同区域 {esper_material_requirement_text(esper_card)}。")
        return selected
    if len(candidates) < required:
        raise RuleValidationError(f"{esper_card.get('name', '异能者')} 需要同区域 {esper_material_requirement_text(esper_card)}。")
    return candidates[:required]


def is_valid_esper_material(card: JsonDict, *, current_turn: int | None = None) -> bool:
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
    if int(card.get('computed_power', raw_card_power(card)) or 0) <= 0:
        return False
    return card.get('type') == CARD_TYPE_ANOMALY_ITEM


def material_tags_for_card(card: JsonDict) -> list[str]:
    material_tags = [str(tag) for tag in card.get('material_tags', []) if str(tag).startswith('mat_')]
    if material_tags:
        return material_tags
    return [str(tag) for tag in card.get('tags', []) if str(tag).startswith('mat_')]


def esper_required_material_attribute(card: JsonDict) -> str:
    return str(card.get('required_material_attribute') or card.get('attribute') or card.get('element') or '指定')


def is_wildcard_material_attribute(attribute: str) -> bool:
    return attribute in {'', '任意', '指定'}


def esper_material_requirement_text(card: JsonDict) -> str:
    if card.get('material_requirement_text'):
        return str(card.get('material_requirement_text'))
    requirements = esper_material_requirements(card)
    if requirements:
        return '+'.join(material_requirement_fragment(requirement) for requirement in requirements)
    required = esper_material_cost(card)
    attribute = esper_required_material_attribute(card)
    return f"{required} 个{attribute + '属性' if not is_wildcard_material_attribute(attribute) else ''}素材"


def esper_material_filter_text(card: JsonDict) -> str:
    requirements = esper_material_requirements(card)
    if requirements:
        return f"同区域、已揭示、未被预定、战力为正且满足{esper_material_requirement_text(card)}的异象道具素材"
    attribute = esper_required_material_attribute(card)
    attribute_text = '' if is_wildcard_material_attribute(attribute) else f"{attribute}属性、"
    return f"同区域、已揭示、未被预定、{attribute_text}战力为正的异象道具素材"


def esper_material_requirements(card: JsonDict) -> list[JsonDict]:
    requirements = card.get('material_requirements') or []
    if not isinstance(requirements, list):
        return []
    return [requirement for requirement in requirements if isinstance(requirement, dict)]


def material_requirement_fragment(requirement: JsonDict) -> str:
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


def material_matches_any_requirement(material: JsonDict, requirements: list[JsonDict]) -> bool:
    return any(material_matches_requirement(material, requirement) for requirement in requirements)


def material_matches_requirement(material: JsonDict, requirement: JsonDict) -> bool:
    attribute = str(requirement.get('attribute') or '')
    attributes = requirement.get('attributes')
    category = str(requirement.get('category') or '')
    name = str(requirement.get('name') or '')
    material_attributes = material_attributes_for_card(material)
    if attribute and attribute not in material_attributes:
        return False
    if isinstance(attributes, list):
        options = {str(option) for option in attributes if str(option)}
        if options and not material_attributes.intersection(options):
            return False
    if category and str(material.get('category') or '') != category:
        return False
    if name and str(material.get('name') or '') != name:
        return False
    return True


def material_requirement_count(requirement: JsonDict) -> int:
    return max(1, int(requirement.get('count') or 1))


def expanded_material_requirements(requirements: list[JsonDict]) -> list[JsonDict]:
    expanded: list[JsonDict] = []
    for requirement in requirements:
        expanded.extend(requirement for _ in range(material_requirement_count(requirement)))
    return expanded


def select_materials_for_requirements(candidates: list[JsonDict], requirements: list[JsonDict]) -> list[JsonDict]:
    expanded_requirements = expanded_material_requirements(requirements)
    if not expanded_requirements:
        return []
    matches_by_requirement = [
        [index for index, card in enumerate(candidates) if material_matches_requirement(card, requirement)]
        for requirement in expanded_requirements
    ]
    if any(not matches for matches in matches_by_requirement):
        return []
    requirement_order = sorted(
        range(len(expanded_requirements)),
        key=lambda index: (len(matches_by_requirement[index]), index),
    )
    assignments: dict[int, int] = {}
    used_candidate_indexes: set[int] = set()

    def assign_next(order_index: int) -> bool:
        if order_index >= len(requirement_order):
            return True
        requirement_index = requirement_order[order_index]
        for candidate_index in matches_by_requirement[requirement_index]:
            if candidate_index in used_candidate_indexes:
                continue
            used_candidate_indexes.add(candidate_index)
            assignments[requirement_index] = candidate_index
            if assign_next(order_index + 1):
                return True
            used_candidate_indexes.remove(candidate_index)
            assignments.pop(requirement_index, None)
        return False

    if not assign_next(0):
        return []
    return [candidates[index] for index in sorted(assignments.values())]


def materials_satisfy_requirements(materials: list[JsonDict], requirements: list[JsonDict]) -> bool:
    expected_count = sum(material_requirement_count(requirement) for requirement in requirements)
    return len(select_materials_for_requirements(materials, requirements)) == expected_count


def material_attribute(card: JsonDict) -> str:
    return str(card.get('attribute') or card.get('element') or next(iter(material_attributes_for_card(card)), ''))


def material_attributes_for_card(card: JsonDict) -> set[str]:
    attributes = {str(card.get('attribute') or card.get('element') or '')}
    attributes.update(str(attribute) for attribute in card.get('material_attributes', []) if str(attribute))
    attributes.discard('')
    return attributes


def material_matches_esper_requirement(material: JsonDict, esper_card: JsonDict) -> bool:
    required_attribute = esper_required_material_attribute(esper_card)
    return is_wildcard_material_attribute(required_attribute) or required_attribute in material_attributes_for_card(material)


def material_absorb_power(card: JsonDict) -> int:
    return int(card.get('computed_power', raw_card_power(card)) or 0)


def location_has_room_after_materials(location: JsonDict, side: str, material_cards: list[JsonDict]) -> bool:
    material_ids = {str(card.get('instance_id') or '') for card in material_cards}
    future_count = location_occupied_card_count(location, side, excluding_instance_ids=material_ids) + 1
    return future_count <= location_capacity(location)


def location_capacity(location: JsonDict) -> int:
    return int(location.get('capacity') or LOCATION_CARD_LIMIT)


def reserve_materials(material_cards: list[JsonDict], esper_instance_id: str) -> None:
    for card in material_cards:
        card['reserved_as_material_for'] = esper_instance_id


def release_material_reservations(snapshot: JsonDict, side: str, esper_instance_id: str) -> None:
    for location in snapshot.get('locations', []):
        for card in location.get('cards', {}).get(side, []):
            if card.get('reserved_as_material_for') == esper_instance_id:
                card.pop('reserved_as_material_for', None)


def cards_by_instance_ids(snapshot: JsonDict, side: str, instance_ids: list[str]) -> list[JsonDict]:
    ids = set(str(instance_id) for instance_id in instance_ids)
    cards: list[JsonDict] = []
    for location in snapshot.get('locations', []):
        for card in location.get('cards', {}).get(side, []):
            if card.get('instance_id') in ids:
                cards.append(card)
    return cards


def unique_ids(instance_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for instance_id in instance_ids:
        normalized = str(instance_id)
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def counts_as_location_slot(card: JsonDict) -> bool:
    return not card.get('reserved_as_material_for')


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


def raw_card_power(card: JsonDict) -> int:
    return int(card.get('base_power', 0)) + int(card.get('bonus_power', 0))
