from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from app.engine.event_context import JsonDict


def build_runtime_effect(
    *,
    definition_type: str = 'item',
    definition_id: str,
    effect_id: str,
    source_instance_id: str,
    data: JsonDict | None = None,
) -> JsonDict:
    return {
        'instance_id': uuid4().hex,
        'definition_type': definition_type,
        'definition_id': definition_id,
        'effect_id': effect_id,
        'source_instance_id': source_instance_id,
        'data': deepcopy(data or {}),
    }


def register_runtime_effect(state: JsonDict, effect: JsonDict) -> JsonDict:
    state.setdefault('active_effects', [])
    state['active_effects'].append(effect)
    return effect


def get_runtime_effect(state: JsonDict, effect_instance_id: str) -> JsonDict | None:
    for effect in state.get('active_effects', []):
        if effect.get('instance_id') == effect_instance_id:
            return effect
    return None


def remove_runtime_effect(state: JsonDict, effect_instance_id: str) -> JsonDict | None:
    for index, effect in enumerate(state.get('active_effects', [])):
        if effect.get('instance_id') == effect_instance_id:
            return state['active_effects'].pop(index)
    return None


def find_runtime_effect_by_source(
    state: JsonDict,
    *,
    definition_type: str,
    definition_id: str,
    effect_id: str,
    source_instance_id: str,
) -> JsonDict | None:
    for effect in state.get('active_effects', []):
        if effect.get('definition_type') != definition_type:
            continue
        if effect.get('definition_id') != definition_id:
            continue
        if effect.get('effect_id') != effect_id:
            continue
        if effect.get('source_instance_id') != source_instance_id:
            continue
        return effect
    return None


def remove_runtime_effect_by_source(
    state: JsonDict,
    *,
    definition_type: str,
    definition_id: str,
    effect_id: str,
    source_instance_id: str,
) -> JsonDict | None:
    effect = find_runtime_effect_by_source(
        state,
        definition_type=definition_type,
        definition_id=definition_id,
        effect_id=effect_id,
        source_instance_id=source_instance_id,
    )
    if effect is None:
        return None
    return remove_runtime_effect(state, str(effect['instance_id']))


def sum_runtime_effect_bonus(state: JsonDict, bonus_field: str) -> int:
    total_bonus = 0
    for effect in state.get('active_effects', []):
        total_bonus += int(effect.get('data', {}).get(bonus_field, 0))
    return total_bonus


def consume_runtime_effect_bonus(
    state: JsonDict,
    bonus_field: str,
    consume_flag: str,
) -> int:
    total_bonus = 0
    remaining_effects = []
    for effect in state.get('active_effects', []):
        effect_data = effect.get('data', {})
        total_bonus += int(effect_data.get(bonus_field, 0))
        if effect_data.get(consume_flag):
            continue
        remaining_effects.append(effect)
    state['active_effects'] = remaining_effects
    return total_bonus
