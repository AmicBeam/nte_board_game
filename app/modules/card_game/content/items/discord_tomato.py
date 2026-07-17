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


ITEM = {'id': 'discord_tomato',
 'name': '西红柿',
 'cost': 1,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/西红柿.webp',
 'description': '揭示：从牌库将「番茄百分百」加入手牌；「西红柿」也视为咒属性素材。',
 'effect_key': 'discord_tutor',
 'tags': ['discord', 'tool', 'material', 'mat_fire'],
 'archetype': 'discord',
 'category': '食材',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_attributes': ['咒'],
 'material_tags': ['mat_dust', 'mat_fire'],
 'ai_material_reserved_for': ['requiem'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/西红柿.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: discord_tutor}
