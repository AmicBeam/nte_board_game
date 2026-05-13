from typing import TYPE_CHECKING

from app.content.map_objects.common import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def chest_identify(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if tile.get('opened'):
        return
    loot = choose_loot_from_table(context.state, tile.get('loot_table_id'))
    if loot is None:
        return
    tile['opened'] = True
    gained = convert_identified_loot_to_fons(context, loot, log_prefix='鉴别开启宝箱，发现')
    message = f"{loot['name']}转化为 {gained} 方斯。"
    add_map_log(context, f'鉴别开启宝箱，{message}')
    add_action_step(context.state, {
        'type': 'popup',
        'icon': '/static/images/map_object/woodbox_256.webp',
        'title': '宝箱',
        'message': message,
    })
    add_tile_update_step(context.state, tile)
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'loot': loot,
        'fons_gained': gained,
    })


MAP_OBJECT = {
    'id': 'chest',
    'icon': '/static/images/map_object/woodbox_256.webp',
    'block_type': BLOCK_TYPE_PASS,
    'tooltip': '宝箱：进入鉴别范围后开启，并按战利品表转化为方斯。',
    'event_hooks': {
        GameEvent.IDENTIFY.value: chest_identify,
    },
}
