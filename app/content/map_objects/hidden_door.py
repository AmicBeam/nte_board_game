from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_PASS, add_action_step, add_map_log
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def hidden_door_enter(context: 'EventContext') -> None:
    if context.state['map'].get('hidden_room_revealed'):
        return
    context.state['map']['hidden_room_revealed'] = True
    message = '发现隐藏门，内部空间已显示。'
    add_map_log(context, message)
    add_action_step(context.state, {
        'type': 'popup',
        'icon': '/static/images/map_object/push-door.svg',
        'title': '隐藏门',
        'message': message,
    })
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {'object_id': context.payload['object_id'], 'object_type': context.payload['tile_type']})


MAP_OBJECT = {
    'id': 'hidden_door',
    'icon': '/static/images/map_object/push-door.svg',
    'block_type': BLOCK_TYPE_PASS,
    'tooltip': '隐藏门：进入后才显示内部空间，不拦截移动。',
    'event_hooks': {
        GameEvent.MOVE_THROUGH.value: hidden_door_enter,
    },
}
