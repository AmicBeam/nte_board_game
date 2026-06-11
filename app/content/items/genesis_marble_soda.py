from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def genesis_marble_soda(context: 'EventContext') -> None:
    card = context.payload['card']
    target = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if target is not None and target.get('side') == str(context.payload['side']) and _raw_card_power(target) <= 2:
        returned_category = str(target.get('category') or '')
        if _return_target_to_hand(context, target) and returned_category == '食物':
            candidates = [
                item
                for item in _turn_deployed_cards(context, str(context.payload['side']))
                if item.get('revealed') and str(item.get('category') or '') == '食物'
            ]
            if candidates:
                boosted = random.choice(candidates)
                _boost_card(boosted, 1, card['name'])
                _add_log(context.state, f"{card['name']} 随机让本回合部署过的 {boosted['name']} +1。")
        return
    _add_log(context.state, f"{card['name']} 没有合法的己方当前战力 <=2 的表侧道具可返回。")


ITEM = {'id': 'genesis_marble_soda',
 'name': '彩色波子汽水',
 'cost': 2,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/彩色波子汽水.webp',
 'description': '宣言：选择 1 张己方战力 <=2 的道具。揭示：将宣言道具返回手牌；若返回的是食物，随机使己方本回合部署过的 1 张食物 +1。',
 'effect_key': 'genesis_marble_soda',
 'tags': ['genesis', 'tool', 'material', 'mat_coin'],
 'archetype': 'genesis',
 'category': '饮料',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_coin'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'board',
                            'scope': 'ally_item_same_location',
                            'prompt': '选择 1 张己方战力不高于 2 的道具。',
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and int(item.get('computed_power', item.get('base_power', 0)) or 0) <= 2
                            )}]},
 'icon': '/static/images/item/彩色波子汽水.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_marble_soda}
