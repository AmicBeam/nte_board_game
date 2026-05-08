from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def key_fabricator_item_played(context: 'EventContext') -> None:
    context.state['player']['keys'] += 1
    add_item_log(context, '使用 Key Fabricator，获得 1 把钥匙。')
    context.payload['resolved'] = True


ITEM = {
    'id': 'key_fabricator',
    'name': 'Key Fabricator',
    'type': 'utility',
    'rarity': 'rare',
    'description': '获得 1 把钥匙。',
    'effect': {'kind': 'key', 'value': 1},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: key_fabricator_item_played,
    },
}
