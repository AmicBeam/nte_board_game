from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_BLOCK, BLOCK_TYPE_PASS, add_action_step, add_map_log, add_tile_update_step
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def door_move_block_check(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if not tile.get('locked', False):
        context.payload['block_type'] = BLOCK_TYPE_PASS
        return
    context.payload['block_type'] = BLOCK_TYPE_BLOCK
    context.payload['blocked_reason'] = '门尚未开启，需要先鉴别。'


def door_identify(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if not tile.get('locked', False):
        return
    layer = tile.get('layer', context.state.get('map', {}).get('current_layer', 1))
    x = tile['x']
    y = tile['y']
    hidden_zone = tile.get('hidden_zone')
    tile.clear()
    tile.update({
        'type': 'open_door',
        'object_id': 'open_door',
        'layer': layer,
        'x': x,
        'y': y,
    })
    if hidden_zone:
        tile['hidden_zone'] = hidden_zone
    add_map_log(context, '鉴别门体结构，门已开启。')
    add_tile_update_step(context.state, tile)
    add_action_step(context.state, {
        'type': 'popup',
        'icon': '/static/images/map_object/push-door.svg',
        'title': '门',
        'message': '鉴别完成，门已开启，现在可以直接通过。',
    })
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'action': 'identify_unlock',
        'x': context.payload['x'],
        'y': context.payload['y'],
    })


MAP_OBJECT = {
    'id': 'door',
    'icon': '/static/images/map_object/door-line.svg',
    'block_type': BLOCK_TYPE_BLOCK,
    'tooltip': '门：鉴别后开启，开启后不会阻挡移动。',
    'event_hooks': {
        GameEvent.MOVE_BLOCK_CHECK.value: door_move_block_check,
        GameEvent.IDENTIFY.value: door_identify,
    },
}


def build_tooltip(tile: dict) -> str:
    if not tile.get('locked', False):
        return '已开启的门：不会阻挡移动。'
    return '门：鉴别后开启，开启后不会阻挡移动。'
