from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def fatiya_darkstar_seed(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    created = _create_tokens_at_location(context, 'harmony_darkstar', side=side, count=2)
    added = _declared_deck_item(context, lambda card: card.get('type') == CARD_TYPE_ANOMALY_ITEM and str(card.get('attribute') or '') == '魂')
    if added is None:
        added = _tutor_deck_item(context, lambda card: card.get('type') == CARD_TYPE_ANOMALY_ITEM and str(card.get('attribute') or '') == '魂')
    _add_card_to_hand(context, added, context.payload['card']['name'])
    added_name = str((added or {}).get('name') or '魂属性道具')
    context.payload['card'].pop('declared_card_instance_ids', None)
    _add_log(context.state, f"{context.payload['card']['name']} 设置环合：黯星 {created} 层，并将宣言的 {added_name} 加入手牌。")


CHARACTER = {'id': 'fatiya',
 'name': '法帝娅',
 'cost': 0,
 'power': 4,
 'type': 'esper',
 'element': '魂',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/法帝娅.png',
 'description': '宣言：检视牌库，选择 1 张魂属性道具。共鸣：设置环合：黯星 2 层，将宣言卡牌加入手牌。',
 'effect_key': 'fatiya_darkstar_seed',
 'tags': ['esper', 'darkstar'],
 'archetype': '',
 'category': '',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '魂',
 'material_requirements': [{'attribute': '魂', 'count': 1}, {'attribute': '暗', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck'],
                            'title': '法帝娅 检视牌库',
                            'description': '宣言 1 张魂属性道具；共鸣时加入手牌。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('attribute') or '') == '魂'}]},
 'portrait_image': '/static/images/characters/portrait/法帝娅.png',
 'avatar_image': '/static/images/characters/portrait/法帝娅.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: fatiya_darkstar_seed}
