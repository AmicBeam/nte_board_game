from typing import TYPE_CHECKING

from app.content.characters.common import add_character_log, get_character_player_state
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def signal_runner_chest_opened(context: 'EventContext') -> None:
    if context.payload.get('object_id') != 'chest':
        return
    player_state = get_character_player_state(context)
    player_state['defense'] += 1
    add_character_log(context, 'Signal Runner 被动生效：永久防御 +1。')
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'signal_runner', 'stat': 'defense'})


CHARACTER = {
    'id': 'signal_runner',
    'name': '讯号疾行者',
    'title': 'Urban Route Hacker',
    'max_hp': 42,
    'attack': 11,
    'defense': 4,
    'passive': '开启宝箱后额外获得 1 点防御。',
    'passive_events': {
        GameEvent.MAP_OBJECT_TRIGGERED.value: signal_runner_chest_opened,
    },
}
