from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def murk_pressure(context: 'EventContext') -> None:
    card = context.payload['card']
    side_state = context.state['sides'][str(context.payload['side'])]
    declared_ids = [str(card_id) for card_id in card.get('declared_card_instance_ids', [])]
    selected = None
    for declared_id in declared_ids:
        for index, candidate in enumerate(list(side_state.get('discard', []))):
            if (
                str(candidate.get('instance_id') or '') == declared_id
                and candidate.get('type') == CARD_TYPE_ANOMALY_ITEM
                and str(candidate.get('attribute') or '') == '咒'
                and str(candidate.get('category') or '') == '材料'
            ):
                selected = side_state['discard'].pop(index)
                break
        if selected is not None:
            break
    if selected is None:
        _add_log(context.state, f"{card['name']} 的宣言墓地材料已不合法。")
        return
    side_state.setdefault('deck', []).append(_reset_card_for_zone(selected, revealed=False))
    _add_log(context.state, f"{card['name']} 将墓地中的 {selected['name']} 返回牌库。")
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'murk_faded_shadow',
 'name': '褪色掠影',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/褪色掠影.webp',
 'description': '从牌库置入墓地时：对手当前战力最高的表侧道具 -1。宣言：检视己方墓地，选择 1 张咒属性材料道具。揭示：宣言道具返回牌库。',
 'effect_key': 'murk_pressure',
 'tags': ['murk', 'tool', 'material', 'mat_dust'],
 'archetype': 'murk',
 'category': '材料',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['discard'],
                            'title': '褪色掠影 检视墓地',
                            'description': '宣言 1 张己方墓地咒属性材料道具；揭示时返回牌库。',
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and str(item.get('attribute') or '') == '咒'
                                and str(item.get('category') or '') == '材料'
                            )}]},
 'icon': '/static/images/item/褪色掠影.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_pressure}
