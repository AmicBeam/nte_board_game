from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def delay_mind_sync(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    target = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if target is None or target.get('side') != opponent or target.get('type') != CARD_TYPE_ANOMALY_ITEM or _raw_card_power(target) > 3:
        _add_log(context.state, f"{card['name']} 没有可交换的对手战力 <=3 卡牌。")
        return
    location = context.payload['location']
    own_cards = location['cards'][side]
    opponent_cards = location['cards'][opponent]
    if card not in own_cards or target not in opponent_cards:
        _add_log(context.state, f"{card['name']} 的交换目标已不在战场。")
        return
    own_index = own_cards.index(card)
    opponent_index = opponent_cards.index(target)
    own_cards[own_index] = target
    opponent_cards[opponent_index] = card
    card['side'] = opponent
    target['side'] = side
    _add_log(context.state, f"{card['name']} 与 {target['name']} 交换控制权。")


ITEM = {'id': 'delay_mind_sync',
 'name': '思维的同频',
 'cost': 2,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/思维的同频.webp',
 'description': '宣言：选择对手 1 个战力 <=3 的表侧道具。揭示：与其交换控制权。',
 'effect_key': 'delay_mind_sync',
 'tags': ['delay', 'tool', 'material', 'mat_signal'],
 'archetype': 'delay',
 'category': '材料',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': ['mat_signal'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'board',
                            'scope': 'opponent_power_lte_3_same_location',
                            'prompt': '选择 1 张对手战力不高于 3 的表侧道具。',
                            'required_before_play': True,
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM and int(item.get('computed_power', item.get('base_power', 0)) or 0) <= 3}]},
 'icon': '/static/images/item/思维的同频.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_mind_sync}
