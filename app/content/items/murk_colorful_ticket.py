from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def murk_ticket_finish(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    count = _count_board_tag(context.state, side, TAG_MURK)
    bonus = 3 if count else 0
    if bonus:
        _boost_card(card, bonus, card['name'])
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -2, card['name'])
    _add_log(context.state, f"{card['name']} 以 {count} 个浊燃收束终端，自身 +{bonus}，压低最高战力目标。")


ITEM = {'id': 'murk_colorful_ticket',
 'name': '斑斓的票根',
 'cost': 5,
 'power': 7,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/斑斓的票根.webp',
 'description': '揭示：若己方有浊燃，自身 +3；使对手最高战力道具 -2。',
 'effect_key': 'murk_ticket_finish',
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
 'icon': '/static/images/item/斑斓的票根.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_ticket_finish}
