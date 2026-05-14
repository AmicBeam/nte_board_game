from typing import TYPE_CHECKING

from app.content.map_objects.common import (
    BLOCK_TYPE_BLOCK,
    BLOCK_TYPE_PASS,
    add_action_step,
    add_tile_update_step,
    choose_loot_from_table,
    convert_identified_loot_to_fons,
)
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


DEFAULT_LOOT_TABLE_ID = 'safe'
DEFAULT_SAFE_ICON = '/static/images/map_object/safe.svg'
LARGE_SAFE_OBJECT_ID = 'large_safe'
LARGE_SAFE_ICON = '/static/images/map_object/safe-large.svg'


def safe_block_check(context: 'EventContext') -> None:
    if context.payload['tile'].get('opened'):
        context.payload['block_type'] = BLOCK_TYPE_PASS
        return
    context.payload['block_type'] = BLOCK_TYPE_BLOCK
    context.payload['blocked_reason'] = '保险箱挡住了道路。'


def _safe_title(object_id: object) -> str:
    if object_id == LARGE_SAFE_OBJECT_ID:
        return '大型保险箱'
    return '保险箱'


def _safe_icon(object_id: object) -> str:
    if object_id == LARGE_SAFE_OBJECT_ID:
        return LARGE_SAFE_ICON
    return DEFAULT_SAFE_ICON


def safe_identify(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if tile.get('opened'):
        return
    loot = choose_loot_from_table(
        context.state,
        tile.get('loot_table_id'),
        DEFAULT_LOOT_TABLE_ID,
    )
    if loot is None:
        return
    tile['opened'] = True
    gained = convert_identified_loot_to_fons(context, loot, log_prefix='鉴别打开保险箱，发现')
    add_tile_update_step(context.state, tile)
    add_action_step(context.state, {
        'type': 'popup',
        'icon': _safe_icon(context.payload.get('object_id')),
        'title': _safe_title(context.payload.get('object_id')),
        'message': f"鉴别打开保险箱，{loot['name']}转化为 {gained} 方斯。",
    })
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'loot': loot,
        'fons_gained': gained,
    })


MAP_OBJECT = {
    'id': 'safe',
    'icon': DEFAULT_SAFE_ICON,
    'block_type': BLOCK_TYPE_BLOCK,
    'tooltip': '保险箱：阻挡移动；进入鉴别范围后开启并获得战利品。',
    'event_hooks': {
        GameEvent.MOVE_BLOCK_CHECK.value: safe_block_check,
        GameEvent.IDENTIFY.value: safe_identify,
    },
}


def build_tooltip(tile: dict) -> str:
    if tile.get('object_id') == LARGE_SAFE_OBJECT_ID or tile.get('type') == LARGE_SAFE_OBJECT_ID:
        return '大型保险箱：占地 2x2，阻挡移动；鉴别后开启，更容易获得高价值战利品。'
    return MAP_OBJECT['tooltip']
