import random
from typing import TYPE_CHECKING

from app.content.items.common import add_item_log, add_item_popup
from app.engine.events import GameEvent
from app.errors import RuleValidationError

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def silver_chequer_played(context: 'EventContext') -> None:
    old_dice = context.state.get('pending_dice') or context.state.get('pending_die')
    if old_dice is None:
        raise RuleValidationError('当前没有可重掷的骰子。')
    rerolled_dice = {'a': random.randint(1, 6), 'b': random.randint(1, 6)}
    context.state['pending_dice'] = rerolled_dice
    context.state['pending_die'] = max(rerolled_dice['a'], rerolled_dice['b'])
    item_instance = next(
        (item for item in context.state.get('hand', []) if item.get('instance_id') == context.payload.get('item_instance_id')),
        None,
    )
    if item_instance is not None:
        item_instance['cooldown_until_turn'] = int(context.state.get('turn', 1)) + 5
    message = f"银棋子生效：蓝骰由 {old_dice} 重掷为 {rerolled_dice['a']} / {rerolled_dice['b']}，5 回合后充能。"
    add_item_log(context, message)
    add_item_popup(context, '银棋子', message, '/static/images/item/silver_chequer.webp')
    context.payload['resolved'] = True


ITEM = {
    'id': 'silver_chequer',
    'name': '银棋子',
    'type': 'dice',
    'rarity': 'common',
    'icon': '/static/images/item/silver_chequer.webp',
    'description': '重掷当前两个蓝色骰子一次，使用后 5 回合充能。',
    'consume_on_play': False,
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: silver_chequer_played,
    },
}
