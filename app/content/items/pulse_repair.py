from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def pulse_repair_item_played(context: 'EventContext') -> None:
    player_state = context.state['player']
    player_state['hp'] = min(player_state['max_hp'], player_state['hp'] + 6)
    add_item_log(context, '使用 Pulse Repair，回复 6 点生命。')
    context.payload['resolved'] = True
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'pulse_repair', 'stat': 'hp'})


ITEM = {
    'id': 'pulse_repair',
    'name': 'Pulse Repair',
    'type': 'recovery',
    'rarity': 'common',
    'description': '立即回复 6 点生命。',
    'effect': {'kind': 'heal', 'value': 6},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: pulse_repair_item_played,
    },
}
