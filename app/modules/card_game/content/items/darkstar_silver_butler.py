from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def _is_nature_pixel(card: JsonDict) -> bool:
    return _definition_id(card) == 'darkstar_nature_pixel' or str(card.get('name') or '') == '本性像素'


def _nature_pixel_count(context: 'EventContext', side: str) -> int:
    side_state = context.state['sides'][side]
    hand_count = sum(1 for card in side_state.get('hand', []) if _is_nature_pixel(card))
    discard_count = sum(1 for card in side_state.get('discard', []) if _is_nature_pixel(card))
    board_count = sum(
        1
        for location in context.state.get('locations', [])
        for card in location.get('cards', {}).get(side, [])
        if card.get('revealed') and _is_nature_pixel(card)
    )
    return min(6, hand_count + discard_count + board_count)


def darkstar_silver_butler(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    amount = _nature_pixel_count(context, side)
    if amount <= 0:
        _add_log(context.state, f"{card['name']} 没有统计到「本性像素」。")
        return
    repeat = 2 if amount >= 3 else 1
    affected: list[str] = []
    for _ in range(repeat):
        target = _selected_or_highest_opponent(context)
        if target is None:
            break
        _boost_card(target, -amount, card['name'])
        affected.append(target['name'])
    if affected:
        _add_log(context.state, f"{card['name']} 统计 {amount} 张「本性像素」，使 {'、'.join(affected)} 各 -{amount}。")
        return
    _add_log(context.state, f"{card['name']} 没有可影响的对手表侧单位。")


ITEM = {'id': 'darkstar_silver_butler',
 'name': '银边管家',
 'cost': 4,
 'power': 7,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/银边管家.webp',
 'description': '揭示：统计己方手牌、墓地和战场中的「本性像素」数量 X，X 至多为 6。使对手当前战力最高的表侧单位 -X。若 X >=3，再重复一次。',
 'effect_key': 'darkstar_silver_butler',
 'tags': ['darkstar', 'tool', 'material', 'mat_relic'],
 'archetype': 'darkstar',
 'category': '材料',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': ['mat_relic'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/银边管家.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_silver_butler}
