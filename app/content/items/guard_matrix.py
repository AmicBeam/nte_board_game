from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.damage import apply_damage_reduction
from app.engine.effects import build_runtime_effect, get_runtime_effect, remove_runtime_effect, register_runtime_effect
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def guard_matrix_hand_aura_on_create_damage_package(context: 'EventContext') -> None:
    if context.payload.get('target_type') != 'player':
        return
    if not context.payload.get('allow_block', True):
        return
    effect = get_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    amount = int(context.payload.get('amount', 0))
    if amount <= 0:
        return
    blocked = apply_damage_reduction(context.payload, int(effect.get('data', {}).get('block_bonus', 0)))
    if blocked <= 0:
        return
    add_item_log(context, f'Guard Matrix 的手牌区光环额外格挡了 {blocked} 点伤害。')


def guard_matrix_item_played(context: 'EventContext') -> None:
    register_runtime_effect(context.state, build_runtime_effect(
        definition_id='guard_matrix',
        effect_id='guard_matrix_defense_bonus',
        source_instance_id=str(context.payload['item_instance_id']),
        data={'defense_bonus': 2},
    ))
    add_item_log(context, '使用 Guard Matrix，本回合防御 +2。')
    context.payload['resolved'] = True
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'guard_matrix', 'stat': 'combat_temp'})


def guard_matrix_on_turn_end(context: 'EventContext') -> None:
    effect = remove_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    add_item_log(context, 'Guard Matrix 的防御加成在回合结束时消失。')
    context.emit(GameEvent.PLAYER_STATS_CHANGED, {'source': 'guard_matrix', 'stat': 'combat_temp'})


ITEM = {
    'id': 'guard_matrix',
    'name': '守护矩阵',
    'type': 'defense',
    'rarity': 'common',
    'description': '在手牌区时形成防御光环：每次受击额外格挡 1 点；打出后本回合额外防御 +2。',
    'effect': {'kind': 'stat_buff', 'defense': 2},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: guard_matrix_item_played,
    },
    'zone_effects': {
        'hand': ['guard_matrix_hand_guard_aura'],
    },
    'runtime_effects': {
        'guard_matrix_hand_guard_aura': {
            'initial_data': {
                'block_bonus': 1,
            },
            'event_hooks': {
                GameEvent.CREATE_DAMAGE_PACKAGE.value: guard_matrix_hand_aura_on_create_damage_package,
            },
        },
        'guard_matrix_defense_bonus': {
            'event_hooks': {
                GameEvent.TURN_END.value: guard_matrix_on_turn_end,
            },
        },
    },
}
