from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def delay_first_wish(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    drawn = _draw_one_from_deck(context.state, side)
    if drawn is None:
        _add_log(context.state, f"{card['name']} 没有可抽的牌。")
    own_cards = [item for item in _revealed_cards(context.payload['location'], side) if item.get('type') != CARD_TYPE_TOKEN]
    opponent_cards = [item for item in _revealed_cards(context.payload['location'], opponent) if item.get('type') != CARD_TYPE_TOKEN]
    if len(opponent_cards) >= len(own_cards):
        target = min(opponent_cards, key=_raw_card_power) if opponent_cards else None
        if target is not None:
            _boost_card(target, -1, card['name'])
            _add_log(context.state, f"{card['name']} 在对手场上卡牌不少于己方时，使 {target['name']} -1。")


ITEM = {'id': 'delay_first_wish',
 'name': '初次的期许',
 'cost': 1,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/初次的期许.webp',
 'description': '揭示：抽 1 张牌；若场上对手的卡牌不少于己方，则使对手当前战力最低的表侧卡牌 -1。',
 'effect_key': 'delay_first_wish',
 'tags': ['delay', 'tool', 'material', 'mat_coin'],
 'archetype': 'delay',
 'category': '材料',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_coin'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/初次的期许.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_first_wish}
