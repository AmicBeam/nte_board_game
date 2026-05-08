from typing import TYPE_CHECKING

from app.content.map_objects.common import add_map_log
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def portal_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    target = tile['target']
    context.state['player']['x'] = target['x']
    context.state['player']['y'] = target['y']
    add_map_log(context, f"传送至 ({target['x']}, {target['y']})。")
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'target': target,
    })


MAP_OBJECT = {
    'id': 'portal',
    'icon': 'portal',
    'block_type': '拦截',
    'tooltip': '传送门：进入后会传送到另一处传送点。',
    'event_hooks': {
        GameEvent.MOVE_STOP.value: portal_tile_enter,
    },
}
