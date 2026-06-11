from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def murk_delusion_pressure(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    count = _count_board_tag(context.state, side, TAG_MURK)
    if count:
        _boost_card(card, 2, card['name'])
        target = _selected_or_highest_opponent(context)
        if target is not None:
            _boost_card(target, -1, card['name'])
    _add_log(context.state, f"{card['name']} 借 {count} 个浊燃形成单点压制。")


ITEM = {'id': 'murk_fantasy_delusion',
 'name': '悬想幻妄',
 'cost': 3,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/悬想幻妄.webp',
 'description': '揭示：若己方有浊燃，自身 +2，并使对手最高战力道具 -1。',
 'effect_key': 'murk_delusion_pressure',
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
 'icon': '/static/images/item/悬想幻妄.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_delusion_pressure}
