from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def bohe_genesis_support(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    target = _lowest_ally(context) or card
    _boost_card(target, 2, card['name'])
    repeated = False
    if _count_board_tag(context.state, side, TAG_GENESIS) > 0:
        repeated = True
        second_target = _lowest_ally(context) or card
        _boost_card(second_target, 2, card['name'])
    suffix = '；若有创生，重复一次判定。' if repeated else '。'
    _add_log(context.state, f"{card['name']} 使己方当前战力最低的表侧单位 +2{suffix}")


CHARACTER = {'id': 'bohe',
 'name': '薄荷',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '灵',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/薄荷.png',
 'description': '共鸣：选择己方当前战力最低的表侧单位 +2；若有创生，重复一次判定。',
 'effect_key': 'bohe_genesis_support',
 'tags': ['esper', 'genesis'],
 'archetype': '',
 'category': '',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '灵',
 'material_requirements': [{'attribute': '灵', 'count': 1}, {'attribute': '光', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/薄荷.png',
 'avatar_image': '/static/images/characters/portrait/薄荷.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: bohe_genesis_support}
