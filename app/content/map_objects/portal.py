from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_INTERCEPT, add_action_step, add_map_log, get_map_object_player_state
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def portal_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    target = tile['target']
    player_state = get_map_object_player_state(context)
    player_state['x'] = target['x']
    player_state['y'] = target['y']
    if 'layer' in target:
        context.state['map']['current_layer'] = target['layer']
    layer_text = f"第 {target['layer']} 层 " if 'layer' in target else ''
    message = f"传送至 {layer_text}({target['x']}, {target['y']})。"
    add_map_log(context, message)
    add_action_step(context.state, {
        'type': 'move',
        'x': target['x'],
        'y': target['y'],
        'layer': target.get('layer', context.state['map'].get('current_layer', 1)),
        'teleport': True,
    })
    add_action_step(context.state, {
        'type': 'popup',
        'icon': '/static/images/map_object/传送门.webp',
        'title': '传送门',
        'message': message,
    })
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'target': target,
    })


MAP_OBJECT = {
    'id': 'portal',
    'icon': '/static/images/map_object/传送门.webp',
    'block_type': BLOCK_TYPE_INTERCEPT,
    'tooltip': '传送门：进入后会传送到另一层的传送点。',
    'event_hooks': {
        GameEvent.MOVE_STOP.value: portal_tile_enter,
    },
}
