from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def delay_nestling_wish(context: 'EventContext') -> None:
    card = context.payload['card']
    target = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if target is None:
        _schedule_next_turn_energy_penalty(context, str(context.payload['opponent_side']), 1, card['name'])
        return
    _add_log(context.state, f"{card['name']} 的宣言目标仍在战场，效果不结算。")


ITEM = {'id': 'delay_nestling_wish',
 'name': '雏鸟的希冀',
 'cost': 2,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/雏鸟的希冀.webp',
 'description': '宣言：选择对手 1 张表侧道具。揭示：若宣言道具已不在战场，使对手下回合可用能量 -1。',
 'effect_key': 'delay_nestling_wish',
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
 'declaration': {'steps': [{'kind': 'board',
                            'scope': 'opponent_same_location',
                            'prompt': '选择 1 张对手表侧道具。',
                            'required_before_play': True,
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM}]},
 'icon': '/static/images/item/雏鸟的希冀.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_nestling_wish}
