from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def chaos_delay_finish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    total_set = int(context.state['sides'][side].setdefault('combo', {}).get('delay_set_total', 0))
    bonus = max(0, total_set)
    if bonus:
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 统计本局己方累计设置的 {total_set} 层延滞，自身 +{bonus}。")


CHARACTER = {'id': 'chaos',
 'name': '卡厄斯',
 'cost': 0,
 'power': 9,
 'type': 'esper',
 'element': '相',
 'rarity': 'ur',
 'art': '/static/images/characters/portrait/鉴定师.png',
 'description': '共鸣：依据本局己方累计设置的延滞层数，使自身 +X。',
 'effect_key': 'chaos_delay_finish',
 'tags': ['esper', 'delay'],
 'archetype': '',
 'category': '',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': [],
 'material_cost': 3,
 'required_material_attribute': '相',
 'material_requirements': [{'attribute': '相', 'count': 2}, {'category': '材料', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/鉴定师.png',
 'avatar_image': '/static/images/characters/portrait/鉴定师.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: chaos_delay_finish}
