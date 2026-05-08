import random
from typing import TYPE_CHECKING

from app.content.map_objects.common import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def chest_tile_enter(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if tile.get('opened'):
        return
    tile['opened'] = True
    reward = random.choice(tile['loot_table'])
    if reward == 'heal':
        context.state['player']['hp'] = min(context.state['player']['max_hp'], context.state['player']['hp'] + 8)
        add_map_log(context, '宝箱奖励：回复 8 点生命。')
        context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'chest', 'stat': 'hp'})
    elif reward == 'attack':
        context.state['player']['attack'] += 1
        add_map_log(context, '宝箱奖励：永久攻击 +1。')
        context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'chest', 'stat': 'attack'})
    elif reward == 'key':
        context.state['player']['keys'] += 1
        add_map_log(context, '宝箱奖励：获得 1 把钥匙。')
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
