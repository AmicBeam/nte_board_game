from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def protagonist_harmony_copy(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    card = context.payload['card']
    attributes = set(str(attribute) for attribute in card.get('consumed_material_attributes', []) if str(attribute))
    created_genesis = 0
    created_delay = 0
    if '相' in attributes:
        created_delay = _create_tokens_at_location(context, 'harmony_delay', side=side, count=1)
    if '灵' in attributes:
        created_genesis = _create_tokens_at_location(context, 'harmony_genesis', side=side, count=1)
        if created_genesis:
            _add_combo_counter(context.state, side, 'genesis_created', created_genesis)
    _add_log(context.state, f"{card['name']} 依据消耗素材设置环合：创生 {created_genesis} 层、延滞 {created_delay} 层。")


CHARACTER = {'id': 'protagonist',
 'name': '鉴定师',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '光',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/鉴定师.webp',
 'description': '共鸣：若消耗灵属性素材，设置环合：创生 1 层；若消耗相属性素材，设置环合：延滞 1 层。',
 'effect_key': 'protagonist_harmony_copy',
 'tags': ['esper', 'genesis', 'delay', 'surplus'],
 'archetype': '',
 'category': '',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '光',
 'material_requirements': [{'attribute': '光', 'count': 1}, {'attributes': ['灵', '相'], 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/鉴定师.webp',
 'avatar_image': '/static/images/characters/avatar/鉴定师.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: protagonist_harmony_copy}
