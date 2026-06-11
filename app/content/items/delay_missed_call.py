from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_missed_call(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent_state = context.state['sides'][str(context.payload['opponent_side'])]
    if not opponent_state.get('hand'):
        _add_log(context.state, f"{card['name']} 没有命中对手手牌。")
        return
    index = random.randrange(len(opponent_state['hand']))
    returned = _reset_card_for_zone(opponent_state['hand'].pop(index), revealed=False)
    opponent_state.setdefault('deck', []).append(returned)
    random.shuffle(opponent_state['deck'])
    _add_log(context.state, f"{card['name']} 将对手 1 张随机手牌返回牌库并洗切。")


ITEM = {'id': 'delay_missed_call',
 'name': '无人来电',
 'cost': 3,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/无人来电.webp',
 'description': '揭示：随机选择对手 1 张手牌，将其返回牌库并洗切；若对手没有手牌，该效果不结算。',
 'effect_key': 'delay_missed_call',
 'tags': ['delay', 'tool', 'material', 'mat_signal'],
 'archetype': 'delay',
 'category': '其他',
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
