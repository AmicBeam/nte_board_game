from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def discord_lock(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    count = int(context.state['sides'][side].setdefault('combo', {}).get('discord_triggered', 0))
    target = _selected_or_highest_opponent(context)
    if target is None:
        _add_log(context.state, f"{card['name']} 没有可控制的对手卡牌。")
        return
    if count > 0:
        target['bonus_power'] = 0
        target['computed_power'] = int(target.get('base_power') or 0)
        target['buff_sources'] = []
        _boost_card(target, -3, card['name'])
        _add_log(context.state, f"{card['name']} 因本局对战中触发过失谐，使 {target['name']} 变为原始战力并 -3。")
    else:
        _boost_card(target, -2, card['name'])
        _add_log(context.state, f"{card['name']} 未读到失谐，使 {target['name']} -2。")


ITEM = {'id': 'discord_nameless_blade',
 'name': '无名刃',
 'cost': 6,
 'power': 6,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/无名刃.webp',
 'description': '揭示：若本局对战中触发过失谐，将当前战力最高的对手表侧卡牌变为原始战力并 -3；否则使其 -2。',
 'effect_key': 'discord_lock',
 'tags': ['discord', 'tool', 'material', 'mat_dust'],
 'archetype': 'discord',
 'category': '材料',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/无名刃.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: discord_lock}
