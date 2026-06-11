from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def discord_control(context: 'EventContext') -> None:
    card = context.payload['card']
    if _definition_id(card) == 'discord_tomato_bucket':
        _tutor_named_item(context, {'西红柿', '番茄百分百'}, card['name'])
    else:
        _trigger_discord_mark(context)
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -2, card['name'])
        _add_log(context.state, f"{card['name']} 抹除 {target['name']} 2 点战力。")


ITEM = {'id': 'discord_tomato_bucket',
 'name': '番茄全家桶',
 'cost': 3,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/番茄全家桶.webp',
 'description': '揭示：从牌库将 1 张「西红柿」或「番茄百分百」加入手牌；对手最高战力道具 -2。',
 'effect_key': 'discord_control',
 'tags': ['discord', 'tool', 'material', 'mat_dust'],
 'archetype': 'discord',
 'category': '礼物',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/番茄全家桶.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: discord_control}
