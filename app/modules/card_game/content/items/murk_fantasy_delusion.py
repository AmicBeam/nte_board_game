from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def murk_delusion_pressure(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    count = _count_harmony_mark(context.state, side, TAG_MURK)
    if count:
        _boost_card(card, 4, card['name'])
        target = _highest_opponent_item(context)
        if target is not None:
            _boost_card(target, -2, card['name'])
    _add_log(context.state, f"{card['name']} 借 {count} 个浊燃形成单点压制。")


ITEM = {'id': 'murk_fantasy_delusion',
 'name': '悬想幻妄',
 'cost': 3,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/悬想幻妄.webp',
 'description': '从牌库置入墓地时：这张卡表侧置入战场。揭示：若己方有浊燃，自身 +4，并使对手当前战力最高的表侧道具 -2。',
 'effect_key': 'murk_delusion_pressure',
 'tags': ['murk', 'tool', 'material', 'mat_fire'],
 'archetype': 'murk',
 'category': '材料',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_fire'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/悬想幻妄.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_delusion_pressure}
