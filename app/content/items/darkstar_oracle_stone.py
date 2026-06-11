from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def darkstar_oracle_disrupt(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent_state = context.state['sides'][str(context.payload['opponent_side'])]
    candidates = [esper for esper in opponent_state.get('esper_standby', []) if esper.get('type') == CARD_TYPE_ESPER]
    if candidates:
        revealed = random.choice(candidates)
        _add_log(context.state, f"{card['name']} 随机展示未部署异能者 {revealed['name']}。")
    else:
        _add_log(context.state, f"{card['name']} 没有可展示的未部署异能者。")


ITEM = {'id': 'darkstar_oracle_stone',
 'name': '谕石',
 'cost': 1,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/谕石.webp',
 'description': '揭示：随机展示 1 张对手未部署的异能者编队卡牌。',
 'effect_key': 'darkstar_oracle_disrupt',
 'tags': ['darkstar', 'tool', 'material', 'mat_oracle'],
 'archetype': 'darkstar',
 'category': '耗材',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': ['mat_oracle'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/谕石.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_oracle_disrupt}
