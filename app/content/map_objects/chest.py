import random
from typing import TYPE_CHECKING

from app.content.map_objects.common import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def chest_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    player_state = get_map_object_player_state(context)
    if tile.get('opened'):
        return
    tile['opened'] = True
    reward = random.choice(tile['loot_table'])
    if reward == 'heal':
        player_state['hp'] = min(player_state['max_hp'], player_state['hp'] + 8)
        message = '宝箱奖励：回复 8 点生命。'
        add_map_log(context, message)
        context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'chest', 'stat': 'hp'})
    elif reward == 'attack':
        player_state['attack'] += 1
        message = '宝箱奖励：永久攻击 +1。'
        add_map_log(context, message)
        context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'chest', 'stat': 'attack'})
    elif reward == 'key':
        player_state['keys'] += 1
        message = '宝箱奖励：获得 1 把钥匙。'
        add_map_log(context, message)
    else:
        message = '宝箱已开启。'
    add_action_step(context.state, {
        'type': 'popup',
        'icon': 'chest',
        'title': '宝箱',
        'message': message,
    })
    add_tile_update_step(context.state, tile)
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'reward': reward,
    })


MAP_OBJECT = {
    'id': 'chest',
    'icon': 'chest',
    'block_type': BLOCK_TYPE_PASS,
    'tooltip': '宝箱：随机获得回复、攻击或钥匙奖励。',
    'event_hooks': {
        GameEvent.MOVE_THROUGH.value: chest_tile_enter,
    },
}
