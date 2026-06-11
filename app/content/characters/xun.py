from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def xun_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    target_location, target_tag = _highest_own_harmony(context)
    before = _location_mark_count(target_location, side, target_tag)
    after = _add_location_mark(context.state, target_location, side, target_tag, 2)
    mark_name = LOCATION_MARK_NAMES.get(target_tag, target_tag)
    _add_log(context.state, f"{context.payload['card']['name']} 复制己方最高层数环合，设置环合：{mark_name} 2 层。")
    if target_tag == TAG_GENESIS and after > before:
        _add_combo_counter(context.state, side, 'genesis_created', 1)
        if _trigger_immediate_genesis(context, target_location):
            consumed = _consume_location_mark(target_location, side, TAG_GENESIS, 1)
            _add_log(context.state, f"{context.payload['card']['name']} 令创生花在时停中生效，随后创生层数 -{consumed}。")


CHARACTER = {'id': 'xun',
 'name': '浔',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '光',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/浔.png',
 'description': '共鸣：将己方层数最高的环合额外设置 2 层，若并列优先选择创生；若成功设置创生，立刻触发 1 次创生生效效果，随后创生层数 -1。',
 'effect_key': 'xun_genesis',
 'tags': ['esper', 'genesis'],
 'archetype': '',
 'category': '',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': [],
 'material_cost': 3,
 'required_material_attribute': '光',
 'material_requirements': [{'attribute': '光', 'count': 1},
                           {'category': '饮料', 'count': 1},
                           {'name': '来自「伊波恩」的蛋糕', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/浔.png',
 'avatar_image': '/static/images/characters/portrait/浔.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: xun_genesis}
