from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def murk_other_side_page(context: 'EventContext') -> None:
    card = context.payload['card']
    moved = _declared_deck_item(
        context,
        lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料',
    )
    if moved is not None:
        moved = _reset_card_for_zone(moved, revealed=True)
        context.state['sides'][str(context.payload['side'])].setdefault('discard', []).append(moved)
        _append_effect_discard_action(context, moved, card['name'])
        _resolve_deck_to_discard_trigger(context, moved, card['name'])
        _trigger_reveal_effect_as_copy(context, moved, source_card=card, source_name=card['name'])
        _add_log(context.state, f"{card['name']} 将宣言材料置入墓地。")
    else:
        moved = _move_deck_item_to_discard(
            context,
            lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料',
            card['name'],
        )
        if moved is not None:
            _trigger_reveal_effect_as_copy(context, moved, source_card=card, source_name=card['name'])
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'murk_other_side_page',
 'name': '妄想彼端的一页',
 'cost': 4,
 'power': 5,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/妄想彼端的一页.webp',
 'description': '宣言：检视牌库，选择 1 张材料道具。揭示：将宣言材料置入墓地，并额外触发其揭示时效果，宣言目标随机。',
 'effect_key': 'murk_other_side_page',
 'tags': ['murk', 'tool', 'material', 'mat_archive'],
 'archetype': 'murk',
 'category': '材料',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_archive'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck'],
                            'title': '妄想彼端的一页 检视牌库',
                            'description': '宣言 1 张材料道具；揭示时将其从牌库置入墓地，并额外触发其揭示效果。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料'}]},
 'icon': '/static/images/item/妄想彼端的一页.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_other_side_page}
