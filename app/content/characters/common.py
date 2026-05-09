from typing import TYPE_CHECKING

LOG_LIMIT = 18

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def get_character_player_state(context: 'EventContext') -> dict:
    return context.state['player']


def get_character_actor_nickname(context: 'EventContext') -> str:
    return str(context.payload.get('actor_nickname', '当前玩家'))


def add_character_log(context: 'EventContext', message: str) -> None:
    context.state.setdefault('log', [])
    actor_nickname = get_character_actor_nickname(context)
    context.state['log'].insert(0, f'[{actor_nickname}] {message}')
    del context.state['log'][LOG_LIMIT:]
