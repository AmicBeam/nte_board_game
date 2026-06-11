from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def yi_delay_support(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    created = _create_tokens_at_location(context, 'harmony_delay', side=side, count=1)
    target = _lowest_ally(context)
    if target is not None:
        _boost_card(target, 2, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 设置环合：延滞 {created} 层，并使己方当前战力最低的表侧单位 +2。")


CHARACTER = {'id': 'yi',
 'name': '翳',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '相',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/翳.png',
 'description': '共鸣：设置环合：延滞 1 层，并选择己方当前战力最低的表侧单位 +2。',
 'effect_key': 'yi_delay_support',
 'tags': ['esper', 'delay'],
 'archetype': '',
 'category': '',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '相',
 'material_requirements': [{'attribute': '相', 'count': 1}, {'category': '材料', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/翳.png',
 'avatar_image': '/static/images/characters/portrait/翳.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: yi_delay_support}
