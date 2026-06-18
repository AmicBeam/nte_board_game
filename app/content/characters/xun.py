from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def xun_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    card = context.payload['card']
    target_location, target_tag = _highest_own_harmony(context)
    before = _location_mark_count(target_location, side, target_tag)
    after = _add_location_mark(context.state, target_location, side, target_tag, 1, context=context)
    mark_name = LOCATION_MARK_NAMES.get(target_tag, target_tag)
    _add_log(context.state, f"{card['name']} 复制己方最高层数环合，设置环合：{mark_name} 1 层。")
    if target_tag == TAG_GENESIS and after > before:
        _add_combo_counter(context.state, side, 'genesis_created', 1)
        if card.get('xun_light_restore_used'):
            _add_log(context.state, f"{card['name']} 已经置回过光属性素材。")
            return
        restored = _restore_consumed_material_face_up(
            context,
            lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('attribute') or '') == '光',
            card['name'],
        )
        if restored is not None:
            card['xun_light_restore_used'] = True


CHARACTER = {'id': 'xun',
 'name': '浔',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '光',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/浔.webp',
 'description': '共鸣：将己方层数最高的环合额外设置 1 层，若并列优先选择创生；若成功设置创生，限 1 次，将消耗的光属性素材表侧置回战场。',
 'effect_key': 'xun_genesis',
 'tags': ['esper', 'genesis'],
 'archetype': '',
 'category': '',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '光',
 'material_requirements': [{'attribute': '光', 'count': 1},
                           {'category': '饮料', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/浔.webp',
 'avatar_image': '/static/images/characters/avatar/浔.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: xun_genesis}
