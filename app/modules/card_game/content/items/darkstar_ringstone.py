from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def darkstar_ringstone_currency(context: 'EventContext') -> None:
    card = context.payload['card']
    added = _tutor_named_item(context, {'本性像素'}, card['name'])
    if added is not None:
        _add_log(context.state, f"{card['name']} 辅助获取本性像素。")
        return
    _boost_card(card, 1, card['name'])
    _add_log(context.state, f"{card['name']} 没有找到本性像素，自身 +1。")


ITEM = {'id': 'darkstar_ringstone',
 'name': '环石',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/环石.webp',
 'description': '揭示：从牌库将 1 张「本性像素」加入手牌；若没有可加入的「本性像素」，自身 +1。',
 'effect_key': 'darkstar_ringstone_currency',
 'tags': ['darkstar', 'tool', 'material', 'mat_oracle'],
 'archetype': 'darkstar',
 'category': '货币',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': ['mat_oracle'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/环石.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_ringstone_currency}
