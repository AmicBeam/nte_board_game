import random
from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.events import GameEvent
from app.errors import RuleValidationError

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def emergency_roll_item_played(context: 'EventContext') -> None:
    pending_die = context.state.get('pending_die')
    if pending_die is None:
        raise RuleValidationError('当前没有可重掷的骰子。')
    rerolled_die = random.randint(1, 6)
    context.state['pending_die'] = rerolled_die
    add_item_log(context, f'使用 Emergency Roll，骰子由 {pending_die} 变为 {rerolled_die}。')
    context.payload['resolved'] = True


ITEM = {
    'id': 'emergency_roll',
    'name': '紧急重掷',
    'type': 'dice',
    'rarity': 'epic',
    'description': '将当前骰子重掷一次。',
    'effect': {'kind': 'reroll'},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: emergency_roll_item_played,
    },
}
