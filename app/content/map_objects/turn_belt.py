from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_PASS, add_map_log
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


_DIRECTION_NAMES = {
    'up': '上',
    'down': '下',
    'left': '左',
    'right': '右',
}


def turn_belt_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if context.payload.get('steps_remaining', 0) <= 0:
        return
    direction = tile['direction']
    add_map_log(context, f'转向带生效，方向改为 {direction}。')
    context.payload['next_direction'] = direction
    context.emit(GameEvent.MOVE_REDIRECTED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'direction': direction,
    })


MAP_OBJECT = {
    'id': 'turn_belt',
    'icon': 'turn_belt',
    'block_type': BLOCK_TYPE_PASS,
    'event_hooks': {
        GameEvent.MOVE_THROUGH.value: turn_belt_tile_enter,
    },
}


def build_tooltip(tile: dict) -> str:
    direction = _DIRECTION_NAMES.get(tile.get('direction'), tile.get('direction', '未知'))
    return f'转向带：经过后将剩余步数转为向{direction}移动。'
