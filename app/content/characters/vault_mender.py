from typing import TYPE_CHECKING

from app.content.characters.common import add_character_log, get_character_player_state
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def vault_mender_event_resolved(context: 'EventContext') -> None:
    if context.payload.get('object_type') != 'event':
        return
    player = get_character_player_state(context)
    player['hp'] = min(player['max_hp'], player['hp'] + 2)
    add_character_log(context, '秘库修补师被动生效：额外回复 2 点生命。')
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'vault_mender', 'stat': 'hp'})


CHARACTER = {
    'id': 'vault_mender',
    'name': '秘库修补师',
    'title': '续航支援专家',
    'max_hp': 48,
    'attack': 9,
    'defense': 5,
    'passive': '触发事件格后额外回复 2 点生命。',
    'passive_events': {
        GameEvent.MAP_OBJECT_TRIGGERED.value: vault_mender_event_resolved,
    },
}
