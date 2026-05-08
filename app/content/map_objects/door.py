from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_BLOCK, BLOCK_TYPE_PASS, add_map_log
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def door_move_block_check(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if not tile.get('locked', False):
        context.payload['block_type'] = BLOCK_TYPE_PASS
        return
    if context.state['player']['keys'] <= 0:
        context.payload['blocked_reason'] = '门被锁住，需要钥匙'
        return
    tile['locked'] = False
    context.state['player']['keys'] -= 1
    context.payload['block_type'] = BLOCK_TYPE_PASS
    add_map_log(context, '消耗 1 把钥匙打开了门。')
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'action': 'unlock',
        'x': context.payload['x'],
        'y': context.payload['y'],
    })


MAP_OBJECT = {
    'id': 'door',
    'icon': 'door',
    'block_type': BLOCK_TYPE_BLOCK,
    'tooltip': '上锁的门：消耗 1 把钥匙打开。',
    'event_hooks': {
        GameEvent.MOVE_BLOCK_CHECK.value: door_move_block_check,
    },
}
