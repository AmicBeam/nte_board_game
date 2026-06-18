from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def chaos_delay_finish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    consumed = 0
    for location in context.state.get('locations', []):
        count = _location_mark_count(location, side, TAG_DELAY)
        if count > 0:
            consumed += _consume_location_mark(location, side, TAG_DELAY, count)
    bonus = consumed * 3
    if bonus:
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    side_state = context.state['sides'][side]
    discarded_count = 0
    while side_state.get('hand'):
        discarded = _reset_card_for_zone(side_state['hand'].pop(0), revealed=True)
        side_state.setdefault('discard', []).append(discarded)
        _append_effect_discard_action(context, discarded, context.payload['card']['name'])
        discarded_count += 1
    _add_log(context.state, f"{context.payload['card']['name']} 消耗 {consumed} 层延滞，自身 +{bonus}，并将 {discarded_count} 张手牌置入墓地。")


CHARACTER = {'id': 'chaos',
 'name': '卡厄斯',
 'cost': 0,
 'power': 6,
 'type': 'esper',
 'element': '相',
 'rarity': 'ur',
 'art': '/static/images/characters/portrait/卡厄斯.webp',
 'description': '共鸣：消耗所有延滞层数，每层使自身 +3。将所有手牌置入墓地。',
 'effect_key': 'chaos_delay_finish',
 'tags': ['esper', 'delay'],
 'archetype': '',
 'category': '',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': [],
 'material_cost': 3,
 'required_material_attribute': '相',
 'material_requirements': [{'attribute': '相', 'count': 2}, {'category': '材料', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/卡厄斯.webp',
 'avatar_image': '/static/images/characters/avatar/卡厄斯.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: chaos_delay_finish}
