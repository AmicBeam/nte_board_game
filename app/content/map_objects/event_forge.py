from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_PASS, add_map_log, get_map_object_player_state
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def forge_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    player_state = get_map_object_player_state(context)
    if tile.get('resolved'):
        return
    tile['resolved'] = True
    player_state['attack'] += 1
    add_map_log(context, '锻炉事件：永久攻击 +1。')
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'event', 'stat': 'attack'})
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'event_kind': 'forge',
    })


MAP_OBJECT = {
    'id': 'event_forge',
    'icon': 'event',
    'block_type': BLOCK_TYPE_PASS,
    'tooltip': '事件：锻炉，永久获得 1 点攻击。',
    'event_hooks': {
        GameEvent.MOVE_THROUGH.value: forge_tile_enter,
    },
}
