from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def darkstar_listening_crystal(context: 'EventContext') -> None:
    card = context.payload['card']
    if _deploy_card_to_current_location(
        context,
        _pop_deck_item(context, lambda item: _definition_id(item) == 'darkstar_oracle_stone'),
        card['name'],
    ):
        _add_log(context.state, f"{card['name']} 从牌库部署 1 张谕石。")


ITEM = {'id': 'darkstar_listening_crystal',
 'name': '聆谕水晶',
 'cost': 3,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/聆谕水晶.webp',
 'description': '揭示：从牌库部署 1 张「谕石」。',
 'effect_key': 'darkstar_listening_crystal',
 'tags': ['darkstar', 'tool', 'material', 'mat_oracle'],
 'archetype': 'darkstar',
 'category': '其他',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': ['mat_oracle'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/聆谕水晶.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_listening_crystal}
