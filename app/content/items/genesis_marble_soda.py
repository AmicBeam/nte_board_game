from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def genesis_marble_soda(context: 'EventContext') -> None:
    card = context.payload['card']
    target = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if target is not None and target.get('side') == str(context.payload['side']) and str(target.get('category') or '') == '耗材':
        if _return_target_to_hand(context, target):
            _boost_card(card, 2, card['name'])
            _add_log(context.state, f"{card['name']} 成功回手，额外自身 +2。")
        return
    _add_log(context.state, f"{card['name']} 没有合法的己方表侧耗材道具可返回。")


ITEM = {'id': 'genesis_marble_soda',
 'name': '彩色波子汽水',
 'cost': 2,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/彩色波子汽水.webp',
 'description': '宣言：选择 1 张己方表侧耗材道具。揭示：将宣言道具返回手牌并使其下次部署费用 -1；若成功返回，自身 +2。',
 'effect_key': 'genesis_marble_soda',
 'tags': ['genesis', 'tool', 'material', 'mat_coin'],
 'archetype': 'genesis',
 'category': '食物',
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
                            'prompt': '选择 1 张己方表侧耗材道具。',
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and str(item.get('category') or '') == '耗材'
                            )}]},
 'icon': '/static/images/item/彩色波子汽水.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_marble_soda}
