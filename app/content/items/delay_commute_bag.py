from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_commute_bag(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    material = _declared_hand_item(
        context,
        lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料',
    )
    if material is not None:
        moved = _reset_card_for_zone(material, revealed=False)
        side_state.setdefault('deck', []).append(moved)
        _add_log(context.state, f"{card['name']} 展示 {moved['name']} 并置于牌库底。")
        _draw_one_from_deck(context.state, side)
    else:
        _add_log(context.state, f"{card['name']} 的宣言材料已不在手牌。")
    card.pop('declared_card_instance_ids', None)
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -2, card['name'])
        _add_log(context.state, f"{card['name']} 使对手最高战力道具 {target['name']} -2。")


ITEM = {'id': 'delay_commute_bag',
 'name': '通勤公文包',
 'cost': 2,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/通勤公文包.webp',
 'description': '宣言：选择 1 张手牌中的材料道具。揭示：展示宣言牌并置于牌库底，随后抽 1 张；使对手表侧表示的最高战力道具 -2。',
 'effect_key': 'delay_commute_bag',
 'tags': ['delay', 'tool', 'material', 'mat_archive'],
 'archetype': 'delay',
 'category': '其他',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_archive'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['hand'],
                            'title': '通勤公文包 检视手牌',
                            'description': '宣言 1 张手牌中的材料道具；揭示时展示并置于牌库底。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料'}]},
 'icon': '/static/images/item/通勤公文包.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_commute_bag}
