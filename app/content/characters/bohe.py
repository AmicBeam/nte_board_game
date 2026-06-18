from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def bohe_genesis_support(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    if card.get('bohe_genesis_boost_used'):
        _add_log(context.state, f"{card['name']} 已经触发过创生加成。")
        return
    if _count_harmony_mark(context.state, side, TAG_GENESIS) <= 0:
        _add_log(context.state, f"{card['name']} 检查己方没有创生，未获得加成。")
        return
    _boost_card(card, 3, card['name'])
    card['bohe_genesis_boost_used'] = True
    _add_log(context.state, f"{card['name']} 因己方存在创生，使自身 +3。")


CHARACTER = {'id': 'bohe',
 'name': '薄荷',
 'cost': 0,
 'power': 3,
 'type': 'esper',
 'element': '灵',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/薄荷.webp',
 'description': '共鸣：【限1次】若己方存在创生，使自身 +3。',
 'effect_key': 'bohe_genesis_support',
 'tags': ['esper', 'genesis'],
 'archetype': '',
 'category': '',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': [],
 'material_cost': 1,
 'required_material_attribute': '灵',
 'material_requirements': [{'attribute': '灵', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/薄荷.webp',
 'avatar_image': '/static/images/characters/avatar/薄荷.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: bohe_genesis_support}
