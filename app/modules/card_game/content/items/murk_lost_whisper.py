from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def murk_pressure(context: 'EventContext') -> None:
    card = context.payload['card']
    if _definition_id(card) == 'murk_faded_shadow':
        target = _lowest_opponent(context)
        if target is not None:
            _boost_card(target, -2, card['name'])
            _add_log(context.state, f"{card['name']} 压低 {target['name']} 2 点战力。")
            return
        _add_log(context.state, f"{card['name']} 没有可影响的对手道具。")
        return
    target = _selected_or_highest_opponent(context)
    if target is not None:
        amount = -1 if _definition_id(card) == 'murk_lost_whisper' else -2
        _boost_card(target, amount, card['name'])
        _add_log(context.state, f"{card['name']} 压低 {target['name']} {abs(amount)} 点战力。")


ITEM = {'id': 'murk_lost_whisper',
 'name': '失落絮语',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/失落絮语.webp',
 'description': '从牌库置入墓地时：对手当前战力最低的表侧道具 -1。宣言：选择 1 张对手表侧道具。揭示：宣言道具 -1。',
 'effect_key': 'murk_pressure',
 'tags': ['murk', 'tool', 'material', 'mat_fire'],
 'archetype': 'murk',
 'category': '材料',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': ['mat_fire'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'board',
                            'scope': 'opponent_same_location',
                            'prompt': '选择 1 张对手表侧道具。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM}]},
 'icon': '/static/images/item/失落絮语.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_pressure}
