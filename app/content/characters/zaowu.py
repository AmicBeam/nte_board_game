from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def _revealed_zaowu_for_side(context: 'EventContext', side: str) -> JsonDict | None:
    if not side:
        return None
    listener_id = str(context.instance_id or '')
    for location in context.state.get('locations', []):
        for card in location.get('cards', {}).get(side, []):
            if str(card.get('instance_id') or '') != listener_id:
                continue
            if card.get('revealed') and _definition_id(card) == 'zaowu':
                return card
    return None


def zaowu_other_esper_resonance(context: 'EventContext') -> None:
    side = str(context.payload.get('side') or '')
    card = _revealed_zaowu_for_side(context, side)
    if card is None:
        return
    resonated = context.payload.get('resonated_card') if isinstance(context.payload.get('resonated_card'), dict) else None
    if resonated is None or resonated.get('type') != CARD_TYPE_ESPER:
        return
    if str(resonated.get('instance_id') or '') == str(card.get('instance_id') or ''):
        return
    marker_types = _own_damage_marker_type_count(context)
    if marker_types <= 0:
        return
    power_before = int(resonated.get('computed_power', _raw_card_power(resonated)) or 0)
    _boost_card(resonated, marker_types, card['name'])
    power_after = int(resonated.get('computed_power', _raw_card_power(resonated)) or 0)
    context.state.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_instance_id': card['instance_id'],
        'location_id': context.payload.get('location_id'),
        'side': side,
        'target_instance_id': resonated['instance_id'],
        'title': card['name'],
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} + {marker_types} = {power_after}',
    })
    _add_log(context.state, f"{card['name']} 使 {resonated['name']} +{marker_types}。")


CHARACTER = {'id': 'zaowu',
 'name': '早雾',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '咒',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/早雾.webp',
 'description': '持续效果：其他己方异能者共鸣后，使其 +X，X 为己方持续伤害标记种类数；己方有浊燃时也算 1 种。',
 'effect_key': 'zaowu_other_esper_resonance',
 'tags': ['esper', 'murk'],
 'archetype': '',
 'category': '',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '咒',
 'material_requirements': [{'attribute': '咒', 'count': 1}, {'category': '材料', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/早雾.webp',
 'avatar_image': '/static/images/characters/avatar/早雾.webp'}

CHARACTER['event_hooks'] = {GameEvent.ESPER_RESONATED.value: zaowu_other_esper_resonance}
