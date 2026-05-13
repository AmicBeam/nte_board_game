from app.content.map_objects.safe import (
    BLOCK_TYPE_BLOCK,
    LARGE_SAFE_ICON,
    LARGE_SAFE_OBJECT_ID,
    safe_block_check,
    safe_identify,
)
from app.engine.events import GameEvent


MAP_OBJECT = {
    'id': LARGE_SAFE_OBJECT_ID,
    'icon': LARGE_SAFE_ICON,
    'block_type': BLOCK_TYPE_BLOCK,
    'tooltip': '大型保险箱：阻挡移动；鉴别后开启，更容易获得高价值战利品。',
    'event_hooks': {
        GameEvent.MOVE_BLOCK_CHECK.value: safe_block_check,
        GameEvent.IDENTIFY.value: safe_identify,
    },
}
