from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def xiaozhi_surplus_link(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    count = 2 if _count_hand_tag(context.state, side, TAG_SURPLUS) > 0 else 1
    added = _add_generated_card_to_hand(context, 'surplus_fons', count=count)
    _add_log(context.state, f"{context.payload['card']['name']} 生成 {added} 张「方斯」加入手牌。")


CHARACTER = {'id': 'xiaozhi',
 'name': '小吱',
 'cost': 0,
 'power': 3,
 'type': 'esper',
 'element': '光',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/小吱.png',
 'description': '共鸣：生成 1 张「方斯」加入手牌；若手牌中有盈蓄，改为生成 2 张。',
 'effect_key': 'xiaozhi_surplus_link',
 'tags': ['esper', 'surplus'],
 'archetype': '',
 'category': '',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '光',
 'material_requirements': [{'attribute': '光', 'count': 1}, {'category': '货币', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/小吱.png',
 'avatar_image': '/static/images/characters/portrait/小吱.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: xiaozhi_surplus_link}
