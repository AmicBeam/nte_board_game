from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def baicang_murk_finish(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    if card.get('baicang_panyu_qiu_used'):
        _add_log(context.state, f"{card['name']} 已经触发过判予秋重置。")
        return
    if _count_harmony_mark(context.state, side, TAG_MURK) <= 0:
        _add_log(context.state, f"{card['name']} 检查己方没有浊燃，未重置判予秋。")
        return
    _reset_location_mark(context, context.payload['location'], side, TAG_PANYU_QIU, 2)
    card['baicang_panyu_qiu_used'] = True
    _add_log(context.state, f"{card['name']} 在己方已有浊燃时将判予秋重置为 2 层。")


CHARACTER = {'id': 'baicang',
 'name': '白藏',
 'cost': 0,
 'power': 3,
 'type': 'esper',
 'element': '咒',
 'rarity': 'ur',
 'art': '/static/images/characters/portrait/白藏.webp',
 'description': '共鸣：【限1次】若己方已有浊燃，将判予秋重置为 2 层。判予秋在每个结束阶段斩杀战力 <=2 的敌方牌。',
 'effect_key': 'baicang_murk_finish',
 'tags': ['esper', 'murk'],
 'archetype': '',
 'category': '',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': [],
 'material_cost': 1,
 'required_material_attribute': '咒',
 'material_requirements': [{'attribute': '咒', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/白藏.webp',
 'avatar_image': '/static/images/characters/avatar/白藏.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: baicang_murk_finish}
