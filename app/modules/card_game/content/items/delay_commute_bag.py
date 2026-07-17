from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def delay_commute_bag(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    turn = int(context.state.get('turn') or 0)
    if int(card.get('commute_bag_buffed_turn') or 0) == turn:
        return
    revealed_this_turn = [
        item
        for item in context.payload['location'].get('cards', {}).get(side, [])
        if item.get('revealed') and int(item.get('played_turn') or 0) == turn
    ]
    if len(revealed_this_turn) < 2:
        return
    for item in revealed_this_turn:
        _boost_card(item, 1, card['name'])
    card['commute_bag_buffed_turn'] = turn
    names = '、'.join(item.get('name', '卡牌') for item in revealed_this_turn)
    _add_log(context.state, f"{card['name']} 在回合结束时使本回合揭示的 {names} +1。")


ITEM = {'id': 'delay_commute_bag',
 'name': '通勤公文包',
 'cost': 2,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/通勤公文包.webp',
 'description': '诱发：回合结束时，若本回合已揭示了至少 2 张己方卡牌，则使本回合揭示的那些己方卡牌 +1。',
 'effect_key': 'delay_commute_bag',
 'tags': ['genesis', 'tool', 'material', 'mat_archive'],
 'archetype': 'genesis',
 'category': '耗材',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_archive'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/通勤公文包.webp'}

ITEM['event_hooks'] = {GameEvent.TURN_END.value: delay_commute_bag}
