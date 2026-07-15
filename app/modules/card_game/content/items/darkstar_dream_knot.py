from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def darkstar_dream_pixel_link(context: 'EventContext') -> None:
    card = context.payload['card']
    hand_count = _add_generated_card_to_hand(context, 'darkstar_nature_pixel', count=1)
    discard_card = _add_generated_card_to_discard(context, 'darkstar_nature_pixel')
    deck_card = _add_generated_card_to_deck_bottom(context, 'darkstar_nature_pixel')
    generated_count = hand_count + (1 if discard_card is not None else 0) + (1 if deck_card is not None else 0)
    _add_log(context.state, f"{card['name']} 生成 {generated_count} 张本性像素，分别连接手牌、墓地和牌库。")


ITEM = {'id': 'darkstar_dream_knot',
 'name': '织梦结',
 'cost': 3,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/织梦结.webp',
 'description': '揭示：生成 3 张「本性像素」，分别置入手牌、墓地和牌库。',
 'effect_key': 'darkstar_dream_pixel_link',
 'tags': ['darkstar', 'tool', 'material', 'mat_dust'],
 'archetype': 'darkstar',
 'category': '家具',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/织梦结.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_dream_pixel_link}
