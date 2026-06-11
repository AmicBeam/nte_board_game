from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def darkstar_mining_permit_end(context: 'EventContext') -> None:
    card = context.payload['card']
    _tutor_named_item(context, {'环石'}, card['name'])


ITEM = {'id': 'darkstar_mining_permit',
 'name': '「异晶开采凭证」',
 'cost': 1,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/「异晶开采凭证」.webp',
 'description': '诱发：回合结束时，将 1 张「环石」从牌库加入手牌。',
 'effect_key': 'darkstar_mining_permit_end',
 'tags': ['darkstar', 'tool', 'material', 'mat_dust'],
 'archetype': 'darkstar',
 'category': '耗材',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/「异晶开采凭证」.webp'}

ITEM['event_hooks'] = {GameEvent.TURN_END.value: darkstar_mining_permit_end}
