from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def fatiya_darkstar_seed(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    created = _create_tokens_at_location(context, 'harmony_darkstar', side=side, count=1)
    moved = _move_declared_or_first_deck_item_to_top(context, lambda card: card.get('type') == CARD_TYPE_ANOMALY_ITEM and str(card.get('attribute') or '') == '魂', context.payload['card']['name'])
    moved_name = str((moved or {}).get('name') or '魂属性道具')
    context.payload['card'].pop('declared_card_instance_ids', None)
    _add_log(context.state, f"{context.payload['card']['name']} 设置环合：黯星 {created} 层，并将宣言的 {moved_name} 置于牌库顶。")


CHARACTER = {'id': 'fatiya',
 'name': '法帝娅',
 'cost': 0,
 'power': 4,
 'type': 'esper',
 'element': '魂',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/法帝娅.webp',
 'description': '宣言：检视牌库，选择 1 张魂属性道具。共鸣：设置环合：黯星 1 层，将宣言卡牌置于牌库顶。',
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
                            'description': '宣言 1 张魂属性道具；共鸣时置于牌库顶。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('attribute') or '') == '魂'}]},
 'portrait_image': '/static/images/characters/portrait/法帝娅.webp',
 'avatar_image': '/static/images/characters/avatar/法帝娅.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: fatiya_darkstar_seed}
