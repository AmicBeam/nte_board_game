from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_water_hesitation(context: 'EventContext') -> None:
    card = context.payload['card']
    target = _selected_or_highest_opponent(context)
    if target is None:
        _add_log(context.state, f"{card['name']} 没有可影响的对手道具。")
        return
    amount = -2
    _boost_card(target, amount, card['name'])
    _add_log(context.state, f"{card['name']} 使 {target['name']} {amount}。")


ITEM = {'id': 'delay_water_hesitation',
 'name': '水波的迟疑',
 'cost': 2,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/水波的迟疑.webp',
 'description': '宣言：选择 1 张对手道具。揭示：宣言道具 -2。',
 'effect_key': 'delay_water_hesitation',
 'tags': ['delay', 'tool', 'material', 'mat_device'],
 'archetype': 'delay',
 'category': '材料',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': ['mat_device'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'board',
                            'scope': 'opponent_same_location',
                            'prompt': '选择 1 张对手道具。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM}]},
 'icon': '/static/images/item/水波的迟疑.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_water_hesitation}
