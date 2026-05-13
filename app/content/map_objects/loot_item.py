from typing import TYPE_CHECKING

from app.content.map_objects.common import BLOCK_TYPE_PASS, identified_loot_to_fons
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


MAP_OBJECT = {
    'id': 'loot_item',
    'icon': 'event',
    'block_type': BLOCK_TYPE_PASS,
    'identify_on_pass': True,
    'tooltip': '可鉴别物品：经过或停留鉴别范围覆盖后发现。',
    'event_hooks': {
        GameEvent.IDENTIFY.value: identified_loot_to_fons,
    },
}


def build_tooltip(tile: dict) -> str:
    loot = tile.get('loot', {})
    return f"{loot.get('name', '可鉴别物品')}：{loot.get('description', '鉴别后自动转化为方斯。')}"
