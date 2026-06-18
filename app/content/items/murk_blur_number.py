from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def murk_blur_number(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    if _has_turn_deployed(context, side, lambda item: item.get('type') == CARD_TYPE_ESPER and str(item.get('attribute') or '') == '咒'):
        _add_card_to_hand(
            context,
            _declared_deck_item(
                context,
                lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料' and int(item.get('cost') or 0) <= 2,
            ) or _tutor_deck_item(
                context,
                lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料' and int(item.get('cost') or 0) <= 2,
            ),
            card['name'],
        )
    else:
        _move_declared_or_first_deck_item_to_top(
            context,
            lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '材料' and int(item.get('cost') or 0) <= 2,
            card['name'],
        )


ITEM = {'id': 'murk_blur_number',
 'name': '模糊数符',
 'cost': 2,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/模糊数符.webp',
 'description': '从牌库置入墓地时：将己方牌库顶 1 张牌置入墓地。宣言：检视牌库，选择 1 张费用 <=2 的材料道具。揭示：若本回合己方咒属性异能者共鸣过，将宣言材料加入手牌；否则将宣言材料置入牌库顶。',
 'effect_key': 'murk_blur_number',
 'tags': ['murk', 'tool', 'material', 'mat_signal'],
 'archetype': 'murk',
 'category': '材料',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': ['mat_signal'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck'],
                            'title': '模糊数符 检视牌库',
                            'description': '宣言 1 张费用 <=2 的材料道具；若本回合己方咒属性异能者共鸣过，揭示时加入手牌。',
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and str(item.get('category') or '') == '材料'
                                and int(item.get('cost') or 0) <= 2
                            )}]},
 'icon': '/static/images/item/模糊数符.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_blur_number}
