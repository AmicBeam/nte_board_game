from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def _lowest_enemy_unit(context: 'EventContext', opponent: str) -> JsonDict | None:
    candidates = [
        card
        for location in context.state.get('locations', [])
        for card in _revealed_cards(location, opponent)
        if card.get('type') != CARD_TYPE_TOKEN
    ]
    return min(candidates, key=_raw_card_power) if candidates else None


def jiuyuan_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    count = _count_board_tag(context.state, side, TAG_GENESIS)
    repeats = min(4, max(1, count))
    applied = 0
    for _ in range(repeats):
        target = _lowest_enemy_unit(context, opponent)
        if target is None:
            break
        _boost_card(target, -1, context.payload['card']['name'])
        applied += 1
    _add_log(context.state, f"{context.payload['card']['name']} 依据 {count} 层创生，重复 {applied}/{repeats} 次使对手当前战力最低的表侧单位 -1。")


CHARACTER = {'id': 'jiuyuan',
 'name': '九原',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '灵',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/九原.webp',
 'description': '共鸣：依据己方创生层数，使对手战力最低的表侧单位 -1，重复 X 次，X 至少为 1，至多为 4。',
 'effect_key': 'jiuyuan_genesis',
 'tags': ['esper', 'genesis'],
 'archetype': '',
 'category': '',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '灵',
 'material_requirements': [{'attribute': '灵', 'count': 2}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/九原.webp',
 'avatar_image': '/static/images/characters/avatar/九原.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: jiuyuan_genesis}
