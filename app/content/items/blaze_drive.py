from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.effects import build_runtime_effect, remove_runtime_effect, register_runtime_effect
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def blaze_drive_item_played(context: 'EventContext') -> None:
    register_runtime_effect(context.state, build_runtime_effect(
        definition_id='blaze_drive',
        effect_id='blaze_drive_attack_bonus',
        source_instance_id=str(context.payload['item_instance_id']),
        data={'attack_bonus': 3},
    ))
    add_item_log(context, '使用 Blaze Drive，本回合攻击 +3。')
    context.payload['resolved'] = True
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'blaze_drive', 'stat': 'combat_temp'})


def blaze_drive_on_turn_end(context: 'EventContext') -> None:
    effect = remove_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    add_item_log(context, 'Blaze Drive 的攻击加成在回合结束时消失。')
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'blaze_drive', 'stat': 'combat_temp'})


ITEM = {
    'id': 'blaze_drive',
    'name': '烈焰驱动',
    'type': 'attack',
    'rarity': 'rare',
    'description': '在手牌区时攻击 +1；打出后本回合额外攻击 +3。',
    'effect': {'kind': 'stat_buff', 'attack': 3},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: blaze_drive_item_played,
    },
    'zone_effects': {
        'hand': ['blaze_drive_hand_attack_bonus'],
    },
    'runtime_effects': {
        'blaze_drive_hand_attack_bonus': {
            'initial_data': {
                'attack_bonus': 1,
            },
        },
        'blaze_drive_attack_bonus': {
            'event_hooks': {
                GameEvent.TURN_END.value: blaze_drive_on_turn_end,
            },
        },
    },
}
