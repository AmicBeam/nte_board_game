from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_first_wish(context: 'EventContext') -> None:
    card = context.payload['card']
    names = {'思维的同频', '水波的迟疑'}
    added = _declared_deck_item(context, lambda item: str(item.get('name') or '') in names)
    if added is None:
        added = _tutor_named_item(context, names, card['name'])
    else:
        _add_card_to_hand(context, added, card['name'])
    if _has_turn_deployed(context, str(context.payload['side']), lambda item: str(item.get('attribute') or '') == '相'):
        _boost_card(card, 1, card['name'])
    if added is None:
        _add_log(context.state, f"{card['name']} 没有找到可加入手牌的延滞起点。")
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'delay_first_wish',
 'name': '初次的期许',
 'cost': 1,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/初次的期许.webp',
 'description': '宣言：检视牌库，选择 1 张「思维的同频」或「水波的迟疑」。揭示：将宣言牌加入手牌；若本回合已经部署过相属性道具，自身 +1。',
 'effect_key': 'delay_first_wish',
 'tags': ['delay', 'tool', 'material', 'mat_coin'],
 'archetype': 'delay',
 'category': '材料',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_coin'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck'],
                            'title': '初次的期许 检视牌库',
                            'description': '宣言「思维的同频」或「水波的迟疑」；揭示时加入手牌。',
                            'predicate': lambda item, context: str(item.get('name') or '') in {'思维的同频', '水波的迟疑'}}]},
 'icon': '/static/images/item/初次的期许.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_first_wish}
