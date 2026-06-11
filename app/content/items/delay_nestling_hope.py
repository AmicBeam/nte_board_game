from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_nestling_hope(context: 'EventContext') -> None:
    card = context.payload['card']
    target = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if target is not None and target.get('side') == str(context.payload['side']):
        target['survive_non_positive_once'] = True
        _add_log(context.state, f"{card['name']} 保护 {target['name']}，持续一回合。")
    if _opponent_esper_consumed_material_this_turn(context):
        _add_card_to_hand(
            context,
            _random_deck_item(context, lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料'),
            card['name'],
        )


ITEM = {'id': 'delay_nestling_hope',
 'name': '雏鸟的希冀',
 'cost': 2,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/雏鸟的希冀.webp',
 'description': '宣言：选择 1 张己方相属性道具。揭示：宣言道具获得护盾，持续一回合；若对手本回合素材消耗阶段共鸣过异能者，随机从牌库将 1 张材料道具加入手牌。',
 'effect_key': 'delay_nestling_hope',
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
                            'scope': 'ally_xiang_item_same_location',
                            'prompt': '选择 1 张己方相属性道具。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('attribute') or '') == '相'}]},
 'icon': '/static/images/item/雏鸟的希冀.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_nestling_hope}
