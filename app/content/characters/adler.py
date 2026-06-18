from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def adler_murk_pressure(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    created = _create_tokens_at_location(context, 'harmony_murk', side=side, count=1)
    _reset_location_mark(context, context.payload['location'], side, TAG_ZHUE_HUCHI, 3)
    _add_log(context.state, f"{context.payload['card']['name']} 设置环合：浊燃 {created} 层，并将诛恶护持重置为 3 层。")


CHARACTER = {'id': 'adler',
 'name': '阿德勒',
 'cost': 0,
 'power': 4,
 'type': 'esper',
 'element': '咒',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/阿德勒.webp',
 'description': '共鸣：设置环合：浊燃 1 层，并将诛恶护持重置为 3 层。',
 'effect_key': 'adler_murk_pressure',
 'tags': ['esper', 'murk'],
 'archetype': '',
 'category': '',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '咒',
 'material_requirements': [{'attribute': '咒', 'count': 1}, {'attribute': '暗', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/阿德勒.webp',
 'avatar_image': '/static/images/characters/avatar/阿德勒.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: adler_murk_pressure}
