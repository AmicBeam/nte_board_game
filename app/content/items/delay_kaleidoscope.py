from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_kaleidoscope_copy(context: 'EventContext') -> None:
    card = context.payload['card']
    copied_card = _previous_revealed_item(context)
    if copied_card is None:
        _add_log(context.state, f"{card['name']} 没有可复制的揭示效果。")
        return
    if not _trigger_reveal_effect_as_copy(context, copied_card, source_card=card, source_name=card['name']):
        _add_log(context.state, f"{card['name']} 没有可复制的揭示效果。")
        return
    _add_log(context.state, f"{card['name']} 复制 {copied_card['name']} 的揭示效果。")


ITEM = {'id': 'delay_kaleidoscope',
 'name': '万花筒',
 'cost': 3,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/万花筒.webp',
 'description': '揭示：复制己方本回合已经揭示的上一张道具揭示效果；复制的宣言目标随机决定，若没有可复制的揭示效果，不复制。',
 'effect_key': 'delay_kaleidoscope_copy',
 'tags': ['delay', 'tool', 'material', 'mat_archive'],
 'archetype': 'delay',
 'category': '其他',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_archive'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/万花筒.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_kaleidoscope_copy}
