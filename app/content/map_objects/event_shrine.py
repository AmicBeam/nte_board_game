from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_PASS, add_map_log
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def shrine_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if tile.get('resolved'):
        return
    tile['resolved'] = True
    context.state['player']['hp'] = min(context.state['player']['max_hp'], context.state['player']['hp'] + 4)
    add_map_log(context, '神龛事件：回复 4 点生命。')
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
