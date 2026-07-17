from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def discord_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    if _definition_id(card) == 'discord_tomato':
        _tutor_named_item(context, {'番茄百分百'}, card['name'])
        _add_log(context.state, f"{card['name']} 也可视为咒属性素材。")
        return
    if _definition_id(card) == 'discord_tomato_100':
        _tutor_named_item(context, {'番茄全家桶'}, card['name'])
        side = str(context.payload['side'])
        if _turn_combo_count(context.state, side, 'deck_to_discard_this_turn') > 0 or _own_esper_consumed_tag_this_turn(context, TAG_MAT_FIRE):
            target = _lowest_opponent_item(context)
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
 'description': '揭示：从牌库将「番茄全家桶」加入手牌；若本回合有己方道具从牌库置入墓地，或咒属性材料作为素材进入墓地，对手当前战力最低的表侧道具 -1。',
 'effect_key': 'discord_tutor',
 'tags': ['discord', 'tool', 'material', 'mat_dust'],
 'archetype': 'discord',
 'category': '食物',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'ai_material_reserved_for': ['requiem'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/番茄百分百.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: discord_tutor}
