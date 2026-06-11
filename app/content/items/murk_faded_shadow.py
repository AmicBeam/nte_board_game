from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


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


ITEM = {'id': 'murk_faded_shadow',
 'name': '褪色掠影',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/褪色掠影.webp',
 'description': '揭示：使对手当前战力最低的表侧道具 -2。',
 'effect_key': 'murk_pressure',
 'tags': ['murk', 'tool', 'material', 'mat_dust'],
 'archetype': 'murk',
 'category': '材料',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/褪色掠影.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_pressure}
