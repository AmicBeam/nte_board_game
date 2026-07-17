from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def darkstar_nature_pixel_link(context: 'EventContext') -> None:
    card = context.payload['card']
    _resolve_nature_pixel_sent_from_deck(context, card['name'])


ITEM = {'id': 'darkstar_nature_pixel',
 'name': '本性像素',
 'cost': 2,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/本性像素.webp',
 'description': '揭示：从牌库顶依次翻看，直到翻到 1 张暗或魂属性道具，或已经翻看 3 张；将翻到的第一张暗或魂属性道具加入手牌，其余已翻看的牌置于牌库底。若未翻到，已翻看的牌全部置于牌库底。',
 'effect_key': 'darkstar_nature_pixel_link',
 'tags': ['darkstar', 'tool', 'material', 'mat_relic'],
 'archetype': 'darkstar',
 'category': '耗材',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': ['mat_relic'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/本性像素.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_nature_pixel_link}
