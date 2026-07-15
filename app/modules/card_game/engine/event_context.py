from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeAlias

from app.modules.card_game.engine.state.types import JsonDict

EventQueue: TypeAlias = list[tuple[str, JsonDict]]
EventHook: TypeAlias = Callable[['EventContext'], None]


@dataclass
class EventContext:
    # 每次事件派发时，都会为当前 listener 构造一个独立上下文。
    # 内容层通过它读取状态、读取入参、修改 payload，并压入后续事件。
    state: JsonDict
    event_name: str
    payload: JsonDict = field(default_factory=dict)
    origin: str = 'engine'
    instance_id: str | None = None
    hook_id: object | None = None
    queue: EventQueue = field(default_factory=list)

    def emit(self, event_name: object, payload: JsonDict | None = None) -> None:
        # handler 可以继续压入后续事件，形成链式触发。
        event_key = getattr(event_name, 'value', event_name)
        self.queue.append((event_key, payload or {}))
