from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def _revealed_hasuoer_for_side(context: 'EventContext', side: str) -> JsonDict | None:
    listener_id = str(context.instance_id or '')
    for location in context.state.get('locations', []):
        for card in location.get('cards', {}).get(side, []):
            if (
                str(card.get('instance_id') or '') == listener_id
                and card.get('revealed')
                and _definition_id(card) == 'hasuoer'
            ):
                return card
    return None


def hasuoer_hamster_ball(context: 'EventContext') -> None:
    if str(context.payload.get('tag') or '') != TAG_DELAY:
        return
    side = str(context.payload.get('side') or '')
    card = _revealed_hasuoer_for_side(context, side)
    if card is None:
        return
    previous_source_id = context.state.get('_active_reveal_source_instance_id')
    previous_source_name = context.state.get('_active_reveal_source_name')
    context.state['_active_reveal_source_instance_id'] = card['instance_id']
    context.state['_active_reveal_source_name'] = card['name']
    try:
        generated = _deploy_generated_card_face_up(context, 'delay_hamster_ball', card['name'], side=side)
    finally:
        if previous_source_id is None:
            context.state.pop('_active_reveal_source_instance_id', None)
        else:
            context.state['_active_reveal_source_instance_id'] = previous_source_id
        if previous_source_name is None:
            context.state.pop('_active_reveal_source_name', None)
        else:
            context.state['_active_reveal_source_name'] = previous_source_name
    if generated is not None:
        _add_log(context.state, f"{card['name']} 因己方设置延滞，生成 {generated['name']}。")


CHARACTER = {'id': 'hasuoer',
 'name': '哈索尔',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '相',
 'rarity': 'r',
 'art': '/static/images/characters/portrait/哈索尔.webp',
 'description': '持续效果：每当己方设置延滞，将 1 张「仓鼠球」表侧置入战场。',
 'effect_key': 'hasuoer_hamster_ball',
 'tags': ['esper', 'delay'],
 'archetype': '',
 'category': '',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': [],
 'material_cost': 2,
 'required_material_attribute': '相',
 'material_requirements': [{'attribute': '相', 'count': 1}, {'attribute': '光', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/哈索尔.webp',
 'avatar_image': '/static/images/characters/avatar/哈索尔.webp'}

CHARACTER['event_hooks'] = {GameEvent.HARMONY_MARK_ADDED.value: hasuoer_hamster_ball}
