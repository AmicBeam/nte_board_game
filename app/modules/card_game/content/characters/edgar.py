from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def edgar_surplus_link(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    consumed = 0
    for location in context.state.get('locations', []):
        consumed = _consume_location_mark(location, side, TAG_SURPLUS, 1)
        if consumed:
            break
    if not consumed:
        _add_log(context.state, f"{context.payload['card']['name']} 没有可消耗的盈蓄。")
        return
    target = _highest_ally(context) or context.payload['card']
    _boost_card(target, 6, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 消耗 1 层盈蓄，使战力最高的己方单位 {target['name']} +6。")


CHARACTER = {'id': 'edgar',
 'name': '埃德嘉',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '光',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/埃德嘉.webp',
 'description': '共鸣：若己方有盈蓄标记，消耗 1 层，并使当前战力最高的己方表侧单位 +6。',
 'effect_key': 'edgar_surplus_link',
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
 'portrait_image': '/static/images/characters/portrait/埃德嘉.webp',
 'avatar_image': '/static/images/characters/avatar/埃德嘉.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: edgar_surplus_link}
