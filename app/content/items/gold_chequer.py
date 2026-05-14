from typing import TYPE_CHECKING

from app.content.items.common import add_item_log, add_item_popup
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def gold_chequer_played(context: 'EventContext') -> None:
    value = 6
    old_dice = context.state.get('pending_dice') or context.state.get('pending_die')
    context.state['pending_dice'] = {'a': value, 'b': value}
    context.state['pending_die'] = value
    message = f'金棋子生效：蓝骰由 {old_dice} 改为 {value} / {value}。'
    add_item_log(context, message)
    add_item_popup(context, '金棋子', message, '/static/images/item/gold_chequer.webp')
    context.payload['resolved'] = True


ITEM = {
    'id': 'gold_chequer',
    'name': '金棋子',
    'type': 'dice',
    'rarity': 'r',
    'icon': '/static/images/item/gold_chequer.webp',
    'description': '使当前两个蓝色骰子都变为 6 点。',
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: gold_chequer_played,
    },
}
