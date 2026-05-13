import random
from typing import TYPE_CHECKING

from app.content.items.common import add_item_log, add_item_popup
from app.engine.events import GameEvent
from app.errors import RuleValidationError

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def silver_chequer_played(context: 'EventContext') -> None:
    old_die = context.state.get('pending_die')
    if old_die is None:
        raise RuleValidationError('当前没有可重掷的骰子。')
    rerolled_die = random.randint(1, 6)
    context.state['pending_die'] = rerolled_die
    item_instance = next(
        (item for item in context.state.get('hand', []) if item.get('instance_id') == context.payload.get('item_instance_id')),
        None,
    )
    if item_instance is not None:
        item_instance['cooldown_until_turn'] = int(context.state.get('turn', 1)) + 5
    message = f'银棋子生效：骰子由 {old_die} 点重掷为 {rerolled_die} 点，5 回合后充能。'
    add_item_log(context, message)
    add_item_popup(context, '银棋子', message, '/static/images/item/silver_chequer.webp')
    context.payload['resolved'] = True


ITEM = {
    'id': 'silver_chequer',
    'name': '银棋子',
    'type': 'dice',
    'rarity': 'common',
    'icon': '/static/images/item/silver_chequer.webp',
    'description': '重掷当前骰子一次，使用后 5 回合充能。',
    'consume_on_play': False,
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: silver_chequer_played,
    },
}
