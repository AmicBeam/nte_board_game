from typing import TYPE_CHECKING

LOG_LIMIT = 18
ACTION_QUEUE_KEY = '_action_queue'

BLOCK_TYPE_BLOCK = '阻挡'
BLOCK_TYPE_INTERCEPT = '拦截'
BLOCK_TYPE_PASS = '可通过'

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def get_map_object_player_state(context: 'EventContext') -> dict:
    return context.state['player']


def get_map_object_actor_nickname(context: 'EventContext') -> str:
    return str(context.payload.get('actor_nickname', '当前玩家'))


def add_map_log(context: 'EventContext', message: str) -> None:
    context.state.setdefault('log', [])
    actor_nickname = get_map_object_actor_nickname(context)
    context.state['log'].insert(0, f'[{actor_nickname}] {message}')
    del context.state['log'][LOG_LIMIT:]


def add_action_step(state: dict, step: dict) -> None:
    state.setdefault(ACTION_QUEUE_KEY, []).append(step)


def add_tile_update_step(state: dict, tile: dict) -> None:
    display_type = tile['type']
    if tile['type'] == 'chest' and tile.get('opened'):
        display_type = 'floor'
    if tile['type'] == 'event' and tile.get('resolved'):
        display_type = 'floor'
    if tile['type'] == 'door' and not tile.get('locked', True):
        display_type = 'floor'
    add_action_step(state, {
        'type': 'tile_update',
        'layer': tile.get('layer', state.get('map', {}).get('current_layer', 1)),
        'x': tile['x'],
        'y': tile['y'],
        'tile': dict(tile),
        'display_type': display_type,
    })
