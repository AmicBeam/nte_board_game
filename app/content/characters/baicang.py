from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def baicang_murk_finish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    amount = min(2, _count_board_tag(context.state, side, TAG_MURK))
    created = _create_tokens_at_location(context, 'harmony_murk', side=side, count=amount)
    _reset_location_mark(context, context.payload['location'], side, TAG_PANYU_QIU, 3)
    _add_log(context.state, f"{context.payload['card']['name']} 根据浊燃层数设置浊燃 {created} 层，并将判予秋重置为 3 层。")


CHARACTER = {'id': 'baicang',
 'name': '白藏',
 'cost': 0,
 'power': 10,
 'type': 'esper',
 'element': '咒',
 'rarity': 'ur',
 'art': '/static/images/characters/portrait/白藏.png',
 'description': '共鸣：根据己方浊燃层数设置环合：浊燃，最多 2 层；将判予秋重置为 3 层。',
 'effect_key': 'baicang_murk_finish',
 'tags': ['esper', 'murk'],
 'archetype': '',
 'category': '',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '咒',
 'material_requirements': [{'attribute': '咒', 'count': 2}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/白藏.png',
 'avatar_image': '/static/images/characters/portrait/白藏.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: baicang_murk_finish}
