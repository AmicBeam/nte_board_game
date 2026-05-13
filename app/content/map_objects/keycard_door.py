from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_BLOCK, BLOCK_TYPE_PASS, add_action_step, add_map_log, add_tile_update_step, consume_item_from_hand
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def keycard_door_block_check(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if not tile.get('locked', True):
        context.payload['block_type'] = BLOCK_TYPE_PASS
        return
    context.payload['block_type'] = BLOCK_TYPE_BLOCK
    context.payload['blocked_reason'] = '暗门尚未开启，需要先鉴别。'


def keycard_door_identify(context: 'EventContext') -> None:
    tile = context.payload['tile']
    if not tile.get('locked', True):
        return
    if not consume_item_from_hand(context.state, 'keycard'):
        if tile.get('identified_requires_keycard'):
            return
        tile['identified_requires_keycard'] = True
        add_map_log(context, '鉴别出经理办公室暗门需要门禁卡。')
        add_action_step(context.state, {
            'type': 'popup',
            'icon': '/static/images/map_object/door-line.svg',
            'title': '经理办公室暗门',
            'message': '鉴别完成：这道暗门需要经理门禁卡。',
        })
        return
    tile['locked'] = False
    add_map_log(context, '鉴别并刷门禁卡打开了经理办公室暗门。')
    add_tile_update_step(context.state, tile)
    add_action_step(context.state, {
        'type': 'popup',
        'icon': '/static/images/map_object/door-line.svg',
        'title': '经理办公室暗门',
        'message': '门禁卡验证通过，暗门已打开，现在可以直接通过。',
    })


MAP_OBJECT = {
    'id': 'keycard_door',
    'icon': '/static/images/map_object/door-line.svg',
    'block_type': BLOCK_TYPE_BLOCK,
    'tooltip': '经理办公室暗门：鉴别后确认门禁卡并开启。',
    'event_hooks': {
        GameEvent.MOVE_BLOCK_CHECK.value: keycard_door_block_check,
        GameEvent.IDENTIFY.value: keycard_door_identify,
    },
}


def build_tooltip(tile: dict) -> str:
    if not tile.get('locked', True):
        return '已开启的经理办公室暗门：不会阻挡移动。'
    return '经理办公室暗门：鉴别后确认门禁卡并开启。'
