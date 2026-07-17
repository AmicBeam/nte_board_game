from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


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
    if target is None or target.get('side') != str(context.payload['side']) or str(target.get('category') or '') not in {'食物', '饮料'}:
        _add_log(context.state, f"{card['name']} 的宣言食物或饮料道具已不在战场。")
        card.pop('declared_card_instance_ids', None)
        return
    if _return_target_to_hand(context, target):
        opponent = str(context.payload['opponent_side'])
        candidates = [
            item
            for item in _revealed_cards(context.payload['location'], opponent)
            if item.get('type') == CARD_TYPE_ANOMALY_ITEM
        ]
        if candidates:
            returned = random.choice(candidates)
            context.payload['location']['cards'][opponent].remove(returned)
            returned = _reset_card_for_zone(returned, revealed=False)
            returned['_animation_source_zone'] = 'board'
            context.state['sides'][opponent].setdefault('hand', []).append(returned)
            _add_log(context.state, f"{card['name']} 随机使对手的 {returned['name']} 返回手牌。")
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'genesis_chip_washer',
 'name': '吃薯片专用洗指机',
 'cost': 2,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/吃薯片专用洗指机.webp',
 'description': '宣言：选择 1 张己方表侧食物或饮料道具。揭示：将宣言道具返回手牌并使其下次部署费用 -1；随后随机使对手 1 张表侧道具返回手牌。',
 'effect_key': 'genesis_recover',
 'tags': ['genesis', 'tool', 'material', 'mat_device'],
 'archetype': 'genesis',
 'category': '耗材',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_device'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'board',
                            'scope': 'ally_item_same_location',
                            'prompt': '选择 1 张己方表侧食物或饮料道具。',
                            'required_before_play': True,
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and str(item.get('category') or '') in {'食物', '饮料'}
                            )}]},
 'icon': '/static/images/item/吃薯片专用洗指机.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_recover}
