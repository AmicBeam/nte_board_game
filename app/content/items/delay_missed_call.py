from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_missed_call(context: 'EventContext') -> None:
    card = context.payload['card']
    side_state = context.state['sides'][str(context.payload['side'])]
    opponent_state = context.state['sides'][str(context.payload['opponent_side'])]
    amount = min(3, max(0, len(opponent_state.get('hand', [])) - len(side_state.get('hand', []))))
    if amount <= 0:
        _add_log(context.state, f"{card['name']} 检查对手手牌没有多于己方，未压低战力。")
        return
    targets = [
        item
        for item in _revealed_cards(context.payload['location'], str(context.payload['opponent_side']))
        if item.get('type') != CARD_TYPE_TOKEN
    ]
    for target in targets:
        _boost_card(target, -amount, card['name'])
    _add_log(context.state, f"{card['name']} 依据对手手牌多出的数量，使对手所有表侧卡牌 -{amount}。")


ITEM = {'id': 'delay_missed_call',
 'name': '无人来电',
 'cost': 4,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/无人来电.webp',
 'description': '揭示：对手所有表侧卡牌 -X，X 为对手手牌比己方手牌多的数量，至多为 3。',
 'effect_key': 'delay_missed_call',
 'tags': ['delay', 'tool', 'material', 'mat_signal'],
 'archetype': 'delay',
 'category': '家具',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': ['mat_signal'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/无人来电.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_missed_call}
