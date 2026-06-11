from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def nanali_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    card = context.payload['card']
    material = sum(1 for attribute in card.get('consumed_material_attributes', []) if str(attribute) == '灵')
    created = _create_tokens_at_location(context, 'harmony_genesis', count=material)
    if created > 0:
        _add_combo_counter(context.state, side, 'genesis_created', created)
        _add_log(context.state, f"{card['name']} 依据消耗的灵属性素材数量，设置环合：创生 {created} 层。")
    if created <= 0:
        _add_log(context.state, f"{card['name']} 没有消耗灵属性素材，未设置创生。")


CHARACTER = {'id': 'nanali',
 'name': '娜娜莉',
 'cost': 0,
 'power': 3,
 'type': 'esper',
 'element': '灵',
 'rarity': 'n',
 'art': '/static/images/characters/portrait/娜娜莉.png',
 'description': '共鸣：依据消耗的灵属性素材数量设置环合：创生；无其他效果。',
 'effect_key': 'nanali_genesis',
 'tags': ['esper', 'genesis'],
 'archetype': '',
 'category': '',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '灵',
 'material_requirements': [{'attribute': '灵', 'count': 1}, {}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/娜娜莉.png',
 'avatar_image': '/static/images/characters/portrait/娜娜莉.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: nanali_genesis}
