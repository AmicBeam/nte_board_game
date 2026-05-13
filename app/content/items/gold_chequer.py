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
    old_die = context.state.get('pending_die')
    context.state['pending_die'] = value
    message = f'金棋子生效：骰子由 {old_die} 点改为 {value} 点。'
    add_item_log(context, message)
    add_item_popup(context, '金棋子', message, '/static/images/item/gold_chequer.webp')
    context.payload['resolved'] = True


ITEM = {
    'id': 'gold_chequer',
    'name': '金棋子',
    'type': 'dice',
    'rarity': 'rare',
    'icon': '/static/images/item/gold_chequer.webp',
    'description': '宣言 1 到 6，使当前骰子变为指定点数。',
    'requires_die_choice': True,
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: gold_chequer_played,
    },
}
