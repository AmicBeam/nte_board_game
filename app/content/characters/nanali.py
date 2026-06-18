from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def nanali_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    card = context.payload['card']
    remaining = sum(_location_mark_count(location, side, TAG_GENESIS) for location in context.state.get('locations', []))
    consumed = 0
    for location in context.state.get('locations', []):
        if remaining <= 0:
            break
        used = _consume_location_mark(location, side, TAG_GENESIS, remaining)
        consumed += used
        remaining -= used
    if consumed > 0:
        _boost_card(card, consumed * 2, card['name'])
    _add_log(context.state, f"{card['name']} 消耗 {consumed} 层创生，自身 +{consumed * 2}。")


CHARACTER = {'id': 'nanali',
 'name': '娜娜莉',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '灵',
 'rarity': 'n',
 'art': '/static/images/characters/portrait/娜娜莉.webp',
 'description': '共鸣：消耗所有创生层数，每层使自身 +2。',
 'effect_key': 'nanali_genesis',
 'tags': ['esper', 'genesis'],
 'archetype': '',
 'category': '',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': [],
 'material_cost': 3,
 'required_material_attribute': '灵',
 'material_requirements': [{'attribute': '灵', 'count': 2}, {'name': '来自「伊波恩」的蛋糕', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/娜娜莉.webp',
 'avatar_image': '/static/images/characters/avatar/娜娜莉.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: nanali_genesis}
