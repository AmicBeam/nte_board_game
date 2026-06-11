from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def jiuyuan_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    count = _count_board_tag(context.state, side, TAG_GENESIS)
    target = _selected_or_highest_opponent(context)
    if target is None:
        _add_log(context.state, f"{context.payload['card']['name']} 读到 {count} 层创生，但没有可影响的敌方单位。")
        return
    amount = -max(1, count)
    _boost_card(target, amount, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 以 {count} 层创生缠绕 {target['name']}，使其 {amount} 战力。")


CHARACTER = {'id': 'jiuyuan',
 'name': '九原',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '灵',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/九原.png',
 'description': '共鸣：依据己方创生层数，使对手最高战力表侧单位 -X，X 至少为 1。',
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
 'portrait_image': '/static/images/characters/portrait/九原.png',
 'avatar_image': '/static/images/characters/portrait/九原.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: jiuyuan_genesis}
