from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_nestling_hope(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent_state = context.state['sides'][str(context.payload['opponent_side'])]
    declared_ids = [str(card_id) for card_id in card.get('declared_card_instance_ids', [])]
    exiled = None
    for declared_id in declared_ids:
        for index, candidate in enumerate(list(opponent_state.get('discard', []))):
            if str(candidate.get('instance_id') or '') == declared_id:
                exiled = opponent_state['discard'].pop(index)
                break
        if exiled is not None:
            break
    if exiled is not None:
        _add_log(context.state, f"{card['name']} 将对手墓地的 {exiled['name']} 除外。")
    else:
        _add_log(context.state, f"{card['name']} 的宣言墓地卡牌已不合法。")
    if _opponent_esper_consumed_material_this_turn(context):
        added = _add_generated_card_to_hand(context, 'delay_common_role_material_box')
        if added:
            _add_log(context.state, f"{card['name']} 生成 1 张「初级角色异能材料自选箱」加入手牌。")
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'delay_nestling_hope',
 'name': '老旧信箱',
 'cost': 2,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/老旧信箱.webp',
 'description': '宣言：检视对手墓地，选择 1 张卡牌。揭示：将宣言卡牌除外；若对手本回合素材消耗阶段共鸣过异能者，生成 1 张「初级角色异能材料自选箱」加入手牌。',
 'effect_key': 'delay_nestling_hope',
 'tags': ['delay', 'tool', 'material', 'mat_coin'],
 'archetype': 'delay',
 'category': '家具',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_coin'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['discard'],
                            'owner': 'opponent',
                            'title': '老旧信箱 检视对手墓地',
                            'description': '宣言对手墓地 1 张卡牌；揭示时除外。',
                            'predicate': lambda item, context: True}]},
 'icon': '/static/images/item/老旧信箱.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_nestling_hope}
