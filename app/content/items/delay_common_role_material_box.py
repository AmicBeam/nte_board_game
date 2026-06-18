from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


DELAY_ROLE_MATERIAL_NAMES = {'初次的期许', '思维的同频', '水波的迟疑', '新兵的怯懦', '雏鸟的希冀'}


def delay_common_role_material_box(context: 'EventContext') -> None:
    card = context.payload['card']
    selected = _declared_deck_or_discard_item(
        context,
        lambda item: str(item.get('name') or '') in DELAY_ROLE_MATERIAL_NAMES,
    )
    if selected is None:
        _add_log(context.state, f"{card['name']} 的宣言牌已不合法。")
        return
    _add_card_to_hand(context, selected, card['name'])


ITEM = {'id': 'delay_common_role_material_box',
 'name': '初级角色异能材料自选箱',
 'cost': 0,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/初级角色异能材料自选箱.webp',
 'description': '宣言：检视牌库与墓地，选择 1 张「初次的期许」「思维的同频」「水波的迟疑」「新兵的怯懦」或「雏鸟的希冀」。揭示：将宣言牌加入手牌。',
 'effect_key': 'delay_common_role_material_box',
 'tags': ['delay', 'tool', 'material', 'mat_coin'],
 'display_tags': ['不可构筑'],
 'deck_buildable': False,
 'archetype': 'delay',
 'category': '耗材',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_coin'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck', 'discard'],
                            'title': '初级角色异能材料自选箱 检视牌库与墓地',
                            'description': '宣言 1 张延滞个人材料；揭示时加入手牌。',
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and str(item.get('name') or '') in DELAY_ROLE_MATERIAL_NAMES
                            )}]},
 'icon': '/static/images/item/初级角色异能材料自选箱.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_common_role_material_box}
