from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def zaowu_murk_spread(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    marker_types = _own_damage_marker_type_count(context)
    boosted = _boost_allied_espers(context, marker_types)
    _add_log(context.state, f"{context.payload['card']['name']} 依据 {marker_types} 种持续伤害标记，使 {boosted} 名己方异能者 +{marker_types}。")


CHARACTER = {'id': 'zaowu',
 'name': '早雾',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '咒',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/早雾.png',
 'description': '共鸣：根据我方持续伤害标记的种类数，使我方全体异能者 +X；浊燃也算 1 种。',
 'effect_key': 'zaowu_murk_spread',
 'tags': ['esper', 'murk'],
 'archetype': '',
 'category': '',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '咒',
 'material_requirements': [{'attribute': '咒', 'count': 1}, {'category': '材料', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/早雾.png',
 'avatar_image': '/static/images/characters/portrait/早雾.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: zaowu_murk_spread}
