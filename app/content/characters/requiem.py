from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def requiem_murk_finish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    _damage_all_enemies(context, 2, source_name=context.payload['card']['name'])
    _reset_location_mark(context, context.payload['location'], side, TAG_NIGHTMARE, 3)
    _add_log(context.state, f"{context.payload['card']['name']} 对所有敌人造成 2 点伤害，并将噩梦重置为 3 层。")


CHARACTER = {'id': 'requiem',
 'name': '安魂曲',
 'cost': 0,
 'power': 8,
 'type': 'esper',
 'element': '咒',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/白藏.png',
 'description': '共鸣：对所有敌人造成 2 点伤害，并将噩梦重置为 3 层。',
 'effect_key': 'requiem_murk_finish',
 'tags': ['esper', 'murk'],
 'archetype': '',
 'category': '',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': [],
 'material_cost': 3,
 'required_material_attribute': '咒',
 'material_requirements': [{'attribute': '暗', 'count': 2}, {'name': '番茄全家桶', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/白藏.png',
 'avatar_image': '/static/images/characters/portrait/白藏.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: requiem_murk_finish}
