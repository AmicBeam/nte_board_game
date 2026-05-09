from typing import TYPE_CHECKING

from app.content.characters.common import add_character_log
from app.engine.effects import build_runtime_effect, register_runtime_effect
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def vector_scout_turn_belt_redirect(context: 'EventContext') -> None:
    if context.payload.get('object_id') != 'turn_belt':
        return
    register_runtime_effect(context.state, build_runtime_effect(
        definition_type='character',
        definition_id='vector_scout',
        effect_id='vector_scout_next_turn_move',
        source_instance_id=str(context.instance_id or 'vector_scout'),
        data={'stored_next_turn_move': 1, 'consume_on_move': True},
    ))
    add_character_log(context, 'Vector Scout 被动生效：下回合移动 +1。')


CHARACTER = {
    'id': 'vector_scout',
    'name': 'Vector Scout',
    'title': 'Route Planning Navigator',
    'max_hp': 38,
    'attack': 10,
    'defense': 4,
    'passive': '每次被转向带改变方向后，下回合额外获得 1 点移动。',
    'passive_events': {
        GameEvent.MOVE_REDIRECTED.value: vector_scout_turn_belt_redirect,
    },
    'runtime_effects': {
        'vector_scout_next_turn_move': {
            'event_hooks': {},
        },
    },
}
