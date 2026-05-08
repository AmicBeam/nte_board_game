from typing import TYPE_CHECKING

LOG_LIMIT = 18

BLOCK_TYPE_BLOCK = '阻挡'
BLOCK_TYPE_INTERCEPT = '拦截'
BLOCK_TYPE_PASS = '可通过'

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def add_map_log(context: 'EventContext', message: str) -> None:
    context.state.setdefault('log', [])
    context.state['log'].insert(0, message)
    del context.state['log'][LOG_LIMIT:]
