from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def discord_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    if _definition_id(card) == 'discord_tomato':
        _tutor_named_item(context, {'番茄百分百'}, card['name'])
        card.setdefault('material_attributes', [])
        if '咒' not in card['material_attributes']:
            card['material_attributes'].append('咒')
        if TAG_MAT_FIRE not in card.setdefault('material_tags', []):
            card['material_tags'].append(TAG_MAT_FIRE)
        _add_log(context.state, f"{card['name']} 也可视为咒属性素材。")
        return
    if _definition_id(card) == 'discord_tomato_100':
        _tutor_named_item(context, {'番茄全家桶'}, card['name'])
        if _own_esper_consumed_tag_this_turn(context, TAG_MAT_FIRE):
            target = _lowest_opponent(context)
            if target is not None:
                _boost_card(target, -1, card['name'])
        return
    _add_card_to_hand(context, _tutor_item(context, 'discord'), card['name'])


ITEM = {'id': 'discord_tomato_100',
 'name': '番茄百分百',
 'cost': 2,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/番茄百分百.webp',
 'description': '揭示：从牌库将「番茄全家桶」加入手牌；若本回合素材消耗阶段有咒属性材料进入墓地，对手当前战力最低的表侧道具 -1。',
 'effect_key': 'discord_tutor',
 'tags': ['discord', 'tool', 'material', 'mat_dust'],
 'archetype': 'discord',
 'category': '食物',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/番茄百分百.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: discord_tutor}
