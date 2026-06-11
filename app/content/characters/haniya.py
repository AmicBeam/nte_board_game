from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def haniya_darkstar_support(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    bonus = min(4, _count_board_tag(context.state, side, TAG_DARKSTAR))
    boosted = _boost_allied_espers(context, bonus)
    _add_log(context.state, f"{context.payload['card']['name']} 根据黯星层数，使 {boosted} 名己方异能者 +{bonus}。")


CHARACTER = {'id': 'haniya',
 'name': '哈尼娅',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '魂',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/哈尼娅.png',
 'description': '共鸣：根据黯星层数，使全部我方异能者 +X，X 最高为 4。',
 'effect_key': 'haniya_darkstar_support',
 'tags': ['esper', 'darkstar'],
 'archetype': '',
 'category': '',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '魂',
 'material_requirements': [{'attribute': '魂', 'count': 1}, {'category': '货币', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/哈尼娅.png',
 'avatar_image': '/static/images/characters/portrait/哈尼娅.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: haniya_darkstar_support}
