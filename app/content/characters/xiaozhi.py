from typing import TYPE_CHECKING

from app.content.characters.common import add_character_log
from app.content.items.common import add_fons
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def xiaozhi_damage_applied(context: 'EventContext') -> None:
    if context.payload.get('source_type') != 'player':
        return
    if context.payload.get('target_type') != 'enemy':
        return
    final_damage = int(context.payload.get('final_damage', 0))
    if final_damage <= 0:
        return
    gained = final_damage * 1000
    total = add_fons(context.state, gained)
    add_character_log(context, f'小吱造成 {final_damage} 点伤害，获得 {gained} 方斯。当前方斯：{total}。')


CHARACTER = {
    'id': 'xiaozhi',
    'name': '小吱',
    'max_hp': 38,
    'attack': 10,
    'defense': 4,
    'portrait_image': '/static/images/characters/portrait/小吱.png',
    'avatar_image': '/static/images/characters/avatar/小吱.png',
    'passive': '每次造成伤害都会获得方斯，每点伤害获得 1000 方斯；每 10000 方斯获得 1 点攻击力，最多 +50。',
    'exclusive_item_ids': ['fons'],
    'passive_events': {
        GameEvent.DAMAGE_APPLIED.value: xiaozhi_damage_applied,
    },
}
