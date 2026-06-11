from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def genesis_recover(context: 'EventContext') -> None:
    card = context.payload['card']
    if _definition_id(card) == 'genesis_eborn_cake':
        predicate = lambda item: (
            item.get('type') == CARD_TYPE_ANOMALY_ITEM
            and int(item.get('cost') or 0) <= 3
            and str(item.get('category') or '') in {'食物', '饮料', '耗材', '礼物'}
        )
        added = _declared_deck_or_discard_item(context, predicate)
        if added is None:
            added = _recover_discard_item(context, predicate, card['name'])
            if added is not None:
                card.pop('declared_card_instance_ids', None)
        else:
            _add_card_to_hand(context, added, card['name'])
        side = str(context.payload['side'])
        own_revealed_items = [
            item
            for item in _revealed_cards(context.payload['location'], side)
            if item.get('type') == CARD_TYPE_ANOMALY_ITEM
        ]
        if len(own_revealed_items) >= 3:
            for item in own_revealed_items:
                _boost_card(item, 1, card['name'])
            _add_log(context.state, f"{card['name']} 让己方全体道具 +1。")
        card.pop('declared_card_instance_ids', None)
        return
    target = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if target is not None and target.get('side') == str(context.payload['side']):
        if _return_target_to_hand(context, target):
            declared = _declared_deck_item(
                context,
                lambda item: (
                    item.get('type') == CARD_TYPE_ANOMALY_ITEM
                    and int(item.get('cost') or 0) <= 1
                    and str(item.get('attribute') or '') in {'光', '灵', '相'}
                ),
            )
            _add_card_to_hand(context, declared, card['name'])
            card.pop('declared_card_instance_ids', None)
            return
    _add_log(context.state, f"{card['name']} 的宣言目标已不合法。")
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'genesis_eborn_cake',
 'name': '来自「伊波恩」的蛋糕',
 'cost': 3,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/来自「伊波恩」的蛋糕.webp',
 'description': '宣言：检视牌库与墓地，选择 1 张费用 <=3 的食物、饮料、耗材或礼物道具。揭示：将宣言牌加入手牌；若己方场上有 3 张以上道具，己方全体 +1。',
 'effect_key': 'genesis_recover',
 'tags': ['genesis', 'tool', 'material', 'mat_archive'],
 'archetype': 'genesis',
 'category': '食物',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_archive'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck', 'discard'],
                            'title': '来自「伊波恩」的蛋糕 检视牌库与墓地',
                            'description': '宣言 1 张费用 <=3 的食物、饮料、耗材或礼物道具；揭示时加入手牌。',
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and int(item.get('cost') or 0) <= 3
                                and str(item.get('category') or '') in {'食物', '饮料', '耗材', '礼物'}
                            )}]},
 'icon': '/static/images/item/来自「伊波恩」的蛋糕.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_recover}
