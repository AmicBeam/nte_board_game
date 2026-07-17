from __future__ import annotations

import re
from copy import deepcopy

from app.modules.card_game.content.common.constants import *


def _esper(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    element: str,
    rarity: str,
    art: str,
    description: str,
    effect_key: str = '',
    tags: list[str] | None = None,
    target_rule: JsonDict | None = None,
    material_cost: int | None = None,
    material_attribute: str | None = None,
    material_requirements: list[JsonDict] | None = None,
    material_requirement_text: str = '',
) -> JsonDict:
    required_materials = material_cost if material_cost is not None else _material_requirement_count(material_requirements) or _default_esper_material_cost(cost)
    required_attribute = material_attribute or element
    return _card(
        card_id,
        name,
        0,
        power,
        CARD_TYPE_ESPER,
        element,
        rarity,
        art,
        description,
        effect_key,
        ['esper', *(tags or [])],
        target_rule=target_rule,
        material_cost=required_materials,
        required_material_attribute=required_attribute,
        material_requirements=material_requirements,
        material_requirement_text=material_requirement_text,
        attribute=element,
    )


def _item(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    archetype: str,
    art: str,
    description: str,
    effect_key: str,
    tags: list[str] | None = None,
    target_rule: JsonDict | None = None,
    category: str = '器物',
    attribute: str = '相',
    material_tags: list[str] | None = None,
) -> JsonDict:
    resolved_material_tags = material_tags or []
    return _card(
        card_id,
        name,
        cost,
        power,
        CARD_TYPE_ANOMALY_ITEM,
        '异象',
        'r',
        art,
        _attribute_only_description(description, attribute),
        effect_key,
        [archetype, 'tool', TAG_MATERIAL, *resolved_material_tags, *(tags or [])],
        archetype=archetype,
        target_rule=target_rule,
        category=category,
        attribute=attribute,
        material_tags=resolved_material_tags,
    )


def _token(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    art: str,
    description: str,
    tags: list[str],
    effect_key: str = '',
) -> JsonDict:
    return _card(
        card_id,
        name,
        cost,
        power,
        CARD_TYPE_TOKEN,
        '环合',
        'token',
        art,
        _attribute_only_description(description, _attribute_from_material_tags(tags)),
        effect_key,
        ['token', *tags],
        attribute=_attribute_from_material_tags(tags),
        material_tags=[tag for tag in tags if tag.startswith('mat_')],
        category='材料' if TAG_MATERIAL in tags else '',
    )


def _card(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    card_type: str,
    element: str,
    rarity: str,
    art: str,
    description: str,
    effect_key: str,
    tags: list[str],
    *,
    archetype: str = '',
    target_rule: JsonDict | None = None,
    category: str = '',
    attribute: str = '',
    material_tags: list[str] | None = None,
    material_cost: int | None = None,
    required_material_attribute: str = '',
    material_requirements: list[JsonDict] | None = None,
    material_requirement_text: str = '',
) -> JsonDict:
    hooks = {}
    return {
        'id': card_id,
        'name': name,
        'cost': cost,
        'power': power,
        'type': card_type,
        'element': element,
        'rarity': rarity,
        'art': art,
        'description': description,
        'effect_key': effect_key,
        'tags': tags,
        'archetype': archetype,
        'category': category,
        'attribute': attribute,
        'attribute_icon': _element_icon(attribute),
        'material_tags': list(material_tags or []),
        'material_cost': material_cost,
        'required_material_attribute': required_material_attribute,
        'material_requirements': deepcopy(material_requirements or []),
        'material_requirement_text': material_requirement_text,
        'target_rule': deepcopy(target_rule) if target_rule else {},
        'event_hooks': hooks,
    }


def _default_esper_material_cost(cost: int) -> int:
    if cost <= 4:
        return 2
    return 3


def _attribute_from_material_tags(tags: list[str]) -> str:
    for tag in tags:
        attribute = MATERIAL_TAG_ATTRIBUTES.get(str(tag))
        if attribute:
            return attribute
    return ''


def _material_requirement_count(requirements: list[JsonDict] | None) -> int:
    return sum(int(requirement.get('count') or 1) for requirement in requirements or [])


def _attr_req(attribute: str, count: int = 1) -> JsonDict:
    return {'attribute': attribute, 'count': count}


def _cat_req(category: str, count: int = 1) -> JsonDict:
    return {'category': category, 'count': count}


def _name_req(name: str, count: int = 1) -> JsonDict:
    return {'name': name, 'count': count}


def _attribute_only_description(description: str, attribute: str) -> str:
    if not attribute:
        return description
    text = re.sub(r'自身作为[^；。]+素材；?', '', description)
    text = re.sub(r'素材。[^，。]*类素材，', f'素材。{attribute}属性素材，', text)
    return text.strip()


__all__ = [
    '_esper',
    '_item',
    '_token',
    '_card',
    '_attr_req',
    '_cat_req',
    '_name_req',
    '_attribute_only_description',
]
