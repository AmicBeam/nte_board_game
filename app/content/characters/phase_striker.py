from typing import TYPE_CHECKING

from app.engine.damage import apply_damage_bonus
from app.engine.events import GameEvent
from app.utils.logger import get_logger

logger = get_logger('nte.character.phase_striker')

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def phase_striker_modify_damage_package(context: 'EventContext') -> None:
    if context.payload.get('source_type') != 'player':
        return
    if context.payload.get('target_type') != 'enemy':
        return
    if context.payload.get('attack_kind') != '直接攻击':
        return
    if apply_damage_bonus(context.payload, 1) <= 0:
        return
    logger.info('Phase Striker passive grants outgoing bonus damage through damage package.')


CHARACTER = {
    'id': 'phase_striker',
    'name': '相位突击手',
    'title': 'Close-Range Duel Specialist',
    'max_hp': 36,
    'attack': 14,
    'defense': 3,
    'passive': '直接交战时额外造成 1 点伤害。',
    'passive_events': {
        GameEvent.CREATE_DAMAGE_PACKAGE.value: phase_striker_modify_damage_package,
    },
}
