from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def darkstar_burst(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    count = _count_location_tag(context.payload['location'], side, TAG_DARKSTAR)
    if count > 0:
        target = _selected_or_highest_opponent(context)
        if target is not None:
            current_power = _raw_card_power(target)
            next_power = current_power // 2
            _boost_card(target, next_power - current_power, card['name'])
            _add_log(context.state, f"{card['name']} 借黯星使 {target['name']} 战力减半。")
        return
    _add_log(context.state, f"{card['name']} 没有可借用的黯星。")


ITEM = {'id': 'darkstar_someone_helmet',
 'name': '何人的头盔',
 'cost': 4,
 'power': 7,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/何人的头盔.webp',
 'description': '揭示：若己方有黯星，使对手最高战力目标的战力减半，向下取整。',
 'effect_key': 'darkstar_burst',
 'tags': ['darkstar', 'tool', 'material', 'mat_relic'],
 'archetype': 'darkstar',
 'category': '材料',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': ['mat_relic'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/何人的头盔.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_burst}
