from typing import TYPE_CHECKING

from app.content.items.common import add_item_log, add_item_popup
from app.engine.events import GameEvent
from app.errors import RuleValidationError

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def gold_chequer_played(context: 'EventContext') -> None:
    value = int(context.payload.get('declared_value') or 0)
    if value < 1 or value > 6:
        raise RuleValidationError('金棋子需要宣言 1 到 6 的点数。')
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
    'rarity': 'rare',
    'icon': '/static/images/item/gold_chequer.webp',
    'description': '宣言 1 到 6，使当前两个蓝色骰子都变为指定点数。',
    'requires_die_choice': True,
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: gold_chequer_played,
    },
}
