from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def requiem_murk_finish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    _reset_location_mark(context, context.payload['location'], side, TAG_NIGHTMARE, 2)
    _add_log(context.state, f"{context.payload['card']['name']} 将噩梦重置为 2 层。")


CHARACTER = {'id': 'requiem',
 'name': '安魂曲',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '咒',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/安魂曲.webp',
 'description': '共鸣：将噩梦重置为 2 层。噩梦会在己方结束阶段对所有敌方单位造成 1 点伤害。',
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
 'portrait_image': '/static/images/characters/portrait/安魂曲.webp',
 'avatar_image': '/static/images/characters/avatar/安魂曲.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: requiem_murk_finish}
