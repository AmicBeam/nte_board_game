from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.damage import apply_damage_reduction, queue_reflected_damage, resolve_damage_package, build_damage_package
from app.engine.effects import build_runtime_effect, get_runtime_effect, register_runtime_effect, remove_runtime_effect
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def phase_shield_hand_aura_on_turn_begin(context: 'EventContext') -> None:
    effect = get_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    shield_per_turn = int(effect['data'].get('shield_per_turn', 0))
    effect['data']['shield_remaining'] = shield_per_turn


def phase_shield_hand_aura_on_create_damage_package(context: 'EventContext') -> None:
    if context.payload.get('target_type') != 'player':
        return
    if not context.payload.get('allow_block', True):
        return
    effect = get_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    remaining = int(effect['data'].get('shield_remaining', 0))
    if remaining <= 0:
        return
    blocked = apply_damage_reduction(context.payload, remaining)
    if blocked <= 0:
        return
    effect['data']['shield_remaining'] = remaining - blocked
    add_item_log(context, f'Phase Shield 的手牌区光环吸收了 {blocked} 点伤害。')


def phase_shield_hand_aura_on_damage_applied(context: 'EventContext') -> None:
    if context.payload.get('target_type') != 'player':
        return
    if int(context.payload.get('final_damage', 0)) <= 0:
        return
    source_type = str(context.payload.get('source_type', ''))
    source_id = str(context.payload.get('source_id', ''))
    source_name = str(context.payload.get('source_name', '敌人'))
    if source_type != 'enemy' or not source_id:
        return
    reflected = queue_reflected_damage(context.payload, 1)
    if reflected <= 0:
        return
    add_item_log(context, f'Phase Shield 的手牌区光环反震 {source_name} {reflected} 点伤害。')
    resolve_damage_package(context.state, build_damage_package(
        source_name='Phase Shield',
        source_type='item',
        target_type='enemy',
        target_id=source_id,
        target_name=source_name,
        amount=reflected,
        attack_kind='反震',
        allow_block=False,
    ))


def phase_shield_item_played(context: 'EventContext') -> None:
    register_runtime_effect(context.state, build_runtime_effect(
        definition_id='phase_shield',
        effect_id='phase_shield_barrier',
        source_instance_id=str(context.payload['item_instance_id']),
        data={'shield_remaining': 4},
    ))
    add_item_log(context, '使用 Phase Shield，注册了本回合最多吸收 4 点伤害的护盾。')
    context.payload['resolved'] = True


def phase_shield_on_create_damage_package(context: 'EventContext') -> None:
    if context.payload.get('target_type') != 'player':
        return
    if not context.payload.get('allow_block', True):
        return
    effect = get_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    remaining = int(effect['data'].get('shield_remaining', 0))
    if remaining <= 0:
        remove_runtime_effect(context.state, str(context.instance_id))
        return
    blocked = apply_damage_reduction(context.payload, remaining)
    if blocked <= 0:
        return
    effect['data']['shield_remaining'] = remaining - blocked
    add_item_log(context, f'Phase Shield 吸收了 {blocked} 点伤害，剩余护盾 {effect["data"]["shield_remaining"]}。')
    if effect['data']['shield_remaining'] <= 0:
        remove_runtime_effect(context.state, str(context.instance_id))


def phase_shield_on_turn_end(context: 'EventContext') -> None:
    effect = remove_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    remaining = int(effect['data'].get('shield_remaining', 0))
    if remaining > 0:
        add_item_log(context, f'Phase Shield 在回合结束时消散，剩余护盾 {remaining}。')


ITEM = {
    'id': 'phase_shield',
    'name': 'Phase Shield',
    'type': 'defense',
    'rarity': 'epic',
    'description': '在手牌区时每回合获得 1 点预备护盾，受击后反震 1；打出后本回合抵挡最多 4 点伤害。',
    'effect': {'kind': 'damage_block', 'value': 4},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: phase_shield_item_played,
    },
    'zone_effects': {
        'hand': ['phase_shield_hand_aura'],
    },
    'runtime_effects': {
        'phase_shield_hand_aura': {
            'initial_data': {
                'shield_per_turn': 1,
                'shield_remaining': 1,
            },
            'event_hooks': {
                GameEvent.TURN_BEGIN.value: phase_shield_hand_aura_on_turn_begin,
                GameEvent.CREATE_DAMAGE_PACKAGE.value: phase_shield_hand_aura_on_create_damage_package,
                GameEvent.DAMAGE_APPLIED.value: phase_shield_hand_aura_on_damage_applied,
            },
        },
        'phase_shield_barrier': {
            'event_hooks': {
                GameEvent.CREATE_DAMAGE_PACKAGE.value: phase_shield_on_create_damage_package,
                GameEvent.TURN_END.value: phase_shield_on_turn_end,
            },
        },
    },
}
