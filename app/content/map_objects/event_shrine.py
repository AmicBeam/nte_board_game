from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_PASS, add_action_step, add_map_log, add_tile_update_step, get_map_object_player_state
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def shrine_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    player_state = get_map_object_player_state(context)
    if tile.get('resolved'):
        return
    tile['resolved'] = True
    player_state['hp'] = min(player_state['max_hp'], player_state['hp'] + 4)
    message = '神龛事件：回复 4 点生命。'
    add_map_log(context, message)
    add_action_step(context.state, {
        'type': 'popup',
        'icon': 'event',
        'title': '神龛',
        'message': message,
    })
    add_tile_update_step(context.state, tile)
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'event', 'stat': 'hp'})
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'event_kind': 'shrine',
    })


MAP_OBJECT = {
    'id': 'event_shrine',
    'icon': 'event',
    'block_type': BLOCK_TYPE_PASS,
    'tooltip': '事件：神龛，可回复生命。',
    'event_hooks': {
        GameEvent.MOVE_THROUGH.value: shrine_tile_enter,
    },
}
