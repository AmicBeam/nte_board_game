from typing import TYPE_CHECKING

from app.content.map_objects.common import (
    BLOCK_TYPE_PASS,
    add_action_step,
    choose_loot_from_table,
    convert_identified_loot_to_fons,
)
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


DEFAULT_LOOT_TABLE_ID = 'desk'


def desk_loot_identify(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if tile.get('resolved'):
        return
    chance = float(tile.get('chance', 0.16))
    tile['resolved'] = True
    import random

    if random.random() > chance:
        return
    loot = choose_loot_from_table(
        context.state,
        tile.get('loot_table_id'),
        DEFAULT_LOOT_TABLE_ID,
    )
    if loot is None:
        return
    gained = convert_identified_loot_to_fons(context, loot, log_prefix='鉴别办公桌附近发现')
    add_action_step(context.state, {
        'type': 'popup',
        'icon': loot.get('icon', 'event'),
        'title': '桌面搜索',
        'message': f"{loot['name']}转化为 {gained} 方斯。",
    })
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'loot': loot,
        'fons_gained': gained,
    })


MAP_OBJECT = {
    'id': 'desk_loot',
    'icon': 'event',
    'hidden_overlay': True,
    'block_type': BLOCK_TYPE_PASS,
    'identify_on_pass': True,
    'tooltip': '办公桌：鉴别后低概率发现可折算为方斯的物品。',
    'event_hooks': {
        GameEvent.IDENTIFY.value: desk_loot_identify,
    },
}
