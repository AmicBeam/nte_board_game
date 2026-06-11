from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def hasuoer_delay_tax(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    created = _create_tokens_at_location(context, 'harmony_delay', side=side, count=2)
    _add_log(context.state, f"{context.payload['card']['name']} 设置环合：延滞 {created} 层。")


CHARACTER = {'id': 'hasuoer',
 'name': '哈索尔',
 'cost': 0,
 'power': 3,
 'type': 'esper',
 'element': '相',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/哈索尔.png',
 'description': '共鸣：设置环合：延滞 2 层；无其他效果。',
 'effect_key': 'hasuoer_delay_tax',
 'tags': ['esper', 'delay'],
 'archetype': '',
 'category': '',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '相',
 'material_requirements': [{'attribute': '相', 'count': 1}, {'attribute': '光', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/哈索尔.png',
 'avatar_image': '/static/images/characters/portrait/哈索尔.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: hasuoer_delay_tax}
