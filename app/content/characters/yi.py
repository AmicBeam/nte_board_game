from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def yi_delay_support(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    if card.get('yi_delay_support_used'):
        _add_log(context.state, f"{card['name']} 已经触发过延滞支援。")
        return
    if _location_mark_count(context.payload['location'], side, TAG_DELAY) <= 0:
        _add_log(context.state, f"{card['name']} 检查己方没有延滞，未设置延滞。")
        return
    created = _create_tokens_at_location(context, 'harmony_delay', side=side, count=1)
    if created:
        card['yi_delay_support_used'] = True
    _add_log(context.state, f"{card['name']} 因己方已有延滞，设置环合：延滞 {created} 层。")


CHARACTER = {'id': 'yi',
 'name': '翳',
 'cost': 0,
 'power': 3,
 'type': 'esper',
 'element': '相',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/翳.webp',
 'description': '共鸣：【限1次】若己方已有延滞，设置环合：延滞 1 层。',
 'effect_key': 'yi_delay_support',
 'tags': ['esper', 'delay'],
 'archetype': '',
 'category': '',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': [],
 'material_cost': 1,
 'required_material_attribute': '相',
 'material_requirements': [{'attribute': '相', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/翳.webp',
 'avatar_image': '/static/images/characters/avatar/翳.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: yi_delay_support}
