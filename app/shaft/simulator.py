from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from app.errors import RuleValidationError
from app.shaft.buffs import (
    active_buff_applies,
    active_buff_resets_on_action_start,
    activate_buff,
    buff_effects,
    buff_summary,
    event_matches_rule,
    legacy_buff_rules_from_axis,
    registered_buff_rules,
    stack_gain_for_rule,
    trigger_cooldown_ticks,
)
from app.shaft.catalog import get_record_map, load_shaft_catalog


ELEMENTS = ('光', '灵', '咒', '暗', '魂', '相')
ZERO_ACTION_VISUAL_TICKS = 2
ENEMY_DEBUFF_DURATIONS = {
    '延滞': 50,
    '黯星': 50,
    '浸染': 120,
    '覆纹': 120,
    '浊燃': 150,
}
TEAM_PANEL_BONUS_DEFAULTS = {
    'version': 2.0,
    'furniture_crit_dmg': 0.04,
    'furniture_flat_atk': 20.0,
    'furniture_flat_def': 30.0,
    'small_flat_atk': 420.0,
    'small_flat_hp': 5200.0,
}
SKILL_LEVEL_DEFAULTS = {
    'basic': 10,
    'skill': 10,
    'ultimate': 10,
    'support': 10,
}
CURTAIN_PASSIVE_TYPES = ('type2', 'type3', 'type4')
SUBSTAT_EFFECT_KEYS = {
    'all_dmg': 'all_dmg',
    'crit_rate': 'crit_rate',
    'crit_dmg': 'crit_dmg',
    'harmony_strength': 'harmony_strength',
    'stagger_strength': 'stagger_strength',
    'atk_pct': 'atk_pct',
    'flat_atk': 'flat_atk',
    'hp_pct': 'hp_pct',
    'flat_hp': 'flat_hp',
    'def_pct': 'def_pct',
    'flat_def': 'flat_def',
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    return int(round(_num(value, default)))


def _mods() -> dict[str, float]:
    return {
        'crit_rate': 0,
        'crit_dmg': 0,
        'atk_pct': 0,
        'flat_atk': 0,
        'hp_pct': 0,
        'flat_hp': 0,
        'def_pct': 0,
        'flat_def': 0,
        'def_ignore': 0,
        'def_down': 0,
        'res_down': 0,
        'energy_recharge': 0,
        'harmony_strength': 0,
        'stagger_strength': 0,
        'basic_dmg': 0,
        'dodge_counter_dmg': 0,
        'element_dmg': 0,
        'follow_dmg': 0,
        'mind_dmg': 0,
        'attach_dmg': 0,
        'skill_dmg': 0,
        'ultimate_dmg': 0,
        'all_dmg': 0,
        'final_dmg': 0,
    }


def _merge_mods(base: dict[str, float], delta: dict[str, Any] | None, factor: float = 1.0) -> dict[str, float]:
    if not delta:
        return base
    for key, value in delta.items():
        if key not in base:
            continue
        base[key] += _num(value) * factor
    return base


def _substat_mods(counts: dict[str, Any], constants: dict[str, Any]) -> dict[str, float]:
    out = _mods()
    units = constants.get('substat_units') or {}
    for key, effect_key in SUBSTAT_EFFECT_KEYS.items():
        count = max(0, _num(counts.get(key) if isinstance(counts, dict) else 0))
        unit = units.get(key) or {}
        out[effect_key] += count * _num(unit.get('unit_value'))
    return out


def _team_panel_bonus(raw: Any, catalog: dict[str, Any]) -> dict[str, float]:
    starter_bonus = (catalog.get('starter_axis') or {}).get('team_panel_bonus')
    defaults = dict(TEAM_PANEL_BONUS_DEFAULTS)
    if isinstance(starter_bonus, dict):
        for key in defaults:
            defaults[key] = _num(starter_bonus.get(key), defaults[key])
    source = raw if isinstance(raw, dict) else {}
    bonus = {key: _num(source.get(key), default) for key, default in defaults.items()}
    if _int(source.get('version')) < 2 and bonus['furniture_flat_atk'] == 20.0 and bonus['small_flat_atk'] == 440.0:
        bonus['small_flat_atk'] = 420.0
    bonus['version'] = 2.0
    return bonus


def _team_panel_bonus_mods(raw: Any, catalog: dict[str, Any]) -> dict[str, float]:
    bonus = _team_panel_bonus(raw, catalog)
    out = _mods()
    out['crit_dmg'] += bonus['furniture_crit_dmg']
    out['flat_atk'] += bonus['furniture_flat_atk'] + bonus['small_flat_atk']
    out['flat_def'] += bonus['furniture_flat_def']
    out['flat_hp'] += bonus['small_flat_hp']
    return out


def _default_build_options(character_id: str, constants: dict[str, Any]) -> dict[str, Any]:
    defaults = constants.get('default_build_options') if isinstance(constants.get('default_build_options'), dict) else {}
    return defaults.get(character_id) if isinstance(defaults.get(character_id), dict) else {}


def _normalize_stat_name(value: Any) -> str:
    text = str(value or '').strip()
    return '精通' if text == '环合强度' else text


def _cartridge_main_stat(team_member: dict[str, Any], constants: dict[str, Any]) -> str:
    character_id = str(team_member.get('character_id') or '')
    options = constants.get('cartridge_main_stat_options') if isinstance(constants.get('cartridge_main_stat_options'), dict) else {}
    default = _normalize_stat_name(_default_build_options(character_id, constants).get('cartridge_main_stat')) or next(iter(options), '')
    selected = _normalize_stat_name(team_member.get('cartridge_main_stat')) or default
    return selected if selected in options else default


def _curtain_bonus(team_member: dict[str, Any], constants: dict[str, Any]) -> dict[str, Any]:
    character_id = str(team_member.get('character_id') or '')
    defaults = _default_build_options(character_id, constants).get('curtain_bonus')
    default_bonus = defaults if isinstance(defaults, dict) else {}
    raw = team_member.get('curtain_bonus') if isinstance(team_member.get('curtain_bonus'), dict) else {}
    stat_options = constants.get('curtain_bonus_stat_options') if isinstance(constants.get('curtain_bonus_stat_options'), dict) else {}
    default_stat = _normalize_stat_name(default_bonus.get('stat')) or next(iter(stat_options), '')
    stat = _normalize_stat_name(raw.get('stat')) or default_stat
    passive_type = str(raw.get('passive_type') or default_bonus.get('passive_type') or 'type3')
    if passive_type not in CURTAIN_PASSIVE_TYPES:
        passive_type = 'type3'
    return {
        'value': max(0.0, min(100.0, _num(raw.get('value'), _num(default_bonus.get('value'), 0)))),
        'stat': stat if stat in stat_options else default_stat,
        'passive_type': passive_type,
    }


def _cartridge_passive_layers(cartridge: dict[str, Any] | None, passive_type: str) -> int:
    if passive_type not in CURTAIN_PASSIVE_TYPES:
        passive_type = 'type3'
    return max(0, _int(((cartridge or {}).get('passive_counts') or {}).get(passive_type)))


def _main_stat_mods(main_stat: str, constants: dict[str, Any]) -> dict[str, float]:
    out = _mods()
    options = constants.get('cartridge_main_stat_options') if isinstance(constants.get('cartridge_main_stat_options'), dict) else {}
    option = options.get(main_stat) if isinstance(options.get(main_stat), dict) else {}
    modifier_key = str(option.get('modifier_key') or '')
    if modifier_key in out:
        out[modifier_key] += _num(option.get('unit_value'))
    return out


def _curtain_bonus_mods(curtain_bonus: dict[str, Any], cartridge: dict[str, Any] | None, constants: dict[str, Any]) -> tuple[dict[str, float], int]:
    out = _mods()
    stat_options = constants.get('curtain_bonus_stat_options') if isinstance(constants.get('curtain_bonus_stat_options'), dict) else {}
    stat = _normalize_stat_name(curtain_bonus.get('stat'))
    option = stat_options.get(stat) if isinstance(stat_options.get(stat), dict) else {}
    modifier_key = str(option.get('modifier_key') or '')
    layers = _cartridge_passive_layers(cartridge, str(curtain_bonus.get('passive_type') or 'type3'))
    if modifier_key in out:
        value = _num(curtain_bonus.get('value')) / 100 * layers
        out[modifier_key] += value
    return out, layers


def _skill_levels(raw: Any) -> dict[str, int]:
    source = raw if isinstance(raw, dict) else {}
    return {
        key: max(1, min(10, _int(source.get(key), default)))
        for key, default in SKILL_LEVEL_DEFAULTS.items()
    }


def _skill_level_bonus(team_member: dict[str, Any]) -> int:
    return 1 if _int(team_member.get('awakening')) >= 3 else 0


def _skill_level_category(action: dict[str, Any]) -> str:
    action_type = str(action.get('action_type') or '')
    damage_type = str(action.get('damage_type') or '')
    if damage_type in {'无', ''} or action_type == '无':
        return ''
    if action_type == '普攻' or damage_type == '普攻' or action_type in {'闪反', '下落'} or damage_type in {'闪反', '下落'}:
        return 'basic'
    if action_type == 'E' or damage_type == 'E':
        return 'skill'
    if action_type == 'Q' or damage_type == 'Q':
        return 'ultimate'
    if action_type == '援护' or damage_type == '援护':
        return 'support'
    return ''


def _skill_level_multiplier(snapshot: dict[str, Any], action: dict[str, Any]) -> tuple[str, int, float]:
    category = _skill_level_category(action)
    if not category:
        return '', 0, 1.0
    levels = snapshot.get('skill_levels') if isinstance(snapshot.get('skill_levels'), dict) else {}
    base_level = max(1, _int(levels.get(category), SKILL_LEVEL_DEFAULTS[category]))
    effective_level = max(1, base_level + _int(snapshot.get('skill_level_bonus')))
    return category, effective_level, 1.08 ** (effective_level - 1)


def _action_type_bonus(action: dict[str, Any], mods: dict[str, float]) -> float:
    action_type = str(action.get('action_type') or '')
    damage_type = str(action.get('damage_type') or '')
    extra_tag = str(action.get('extra_tag') or '')
    total = mods['all_dmg']
    if action_type == '普攻' or damage_type == '普攻':
        total += mods['basic_dmg']
    if action_type == '闪反' or damage_type == '闪反':
        total += mods['dodge_counter_dmg']
    if action_type == 'E' or damage_type == 'E':
        total += mods['skill_dmg']
    if action_type == 'Q' or damage_type == 'Q':
        total += mods['ultimate_dmg']
    if extra_tag == '追击':
        total += mods['follow_dmg']
    if extra_tag == '心灵':
        total += mods['mind_dmg']
    if extra_tag == '附着':
        total += mods['attach_dmg']
    return total


def _character_element_bonus(character: dict[str, Any], arc: dict[str, Any] | None, cartridge: dict[str, Any] | None) -> float:
    element = str(character.get('element') or '')
    total = 0.0
    if arc:
        total += _num((arc.get('element_dmg') or {}).get(element))
    return total


def _build_snapshot(team_member: dict[str, Any], catalog: dict[str, Any], team_panel_bonus: dict[str, Any] | None = None) -> dict[str, Any]:
    characters = get_record_map(catalog['characters'])
    arcs = get_record_map(catalog['arcs'])
    cartridges = get_record_map(catalog['cartridges'])
    constants = catalog['formula_constants']
    character = characters.get(str(team_member.get('character_id') or ''))
    if not character:
        raise RuleValidationError('队伍中存在未知角色。')
    arc = arcs.get(str(team_member.get('arc_id') or ''))
    cartridge = cartridges.get(str(team_member.get('cartridge_id') or ''))
    mods = _mods()
    main_stat = _cartridge_main_stat(team_member, constants)
    curtain_bonus = _curtain_bonus(team_member, constants)
    curtain_mods, curtain_layers = _curtain_bonus_mods(curtain_bonus, cartridge, constants)
    _merge_mods(mods, character.get('modifiers'))
    if bool(team_member.get('bond_full')) or _int(team_member.get('bond_level')) > 0:
        _merge_mods(mods, (character.get('bond_bonus') or {}).get('modifiers'))
    if arc:
        _merge_mods(mods, arc.get('modifiers'))
    if cartridge:
        _merge_mods(mods, cartridge.get('modifiers'))
    _merge_mods(mods, _main_stat_mods(main_stat, constants))
    _merge_mods(mods, curtain_mods)
    _merge_mods(mods, _substat_mods(team_member.get('substat_counts') or {}, constants))
    _merge_mods(mods, _team_panel_bonus_mods(team_panel_bonus, catalog))
    mods['element_dmg'] += _character_element_bonus(character, arc, cartridge)

    base_stats = character.get('base_stats') or {}
    base_atk = _num(base_stats.get('atk')) + _num((arc or {}).get('base_atk'))
    base_hp = _num(base_stats.get('hp'))
    base_def = _num(base_stats.get('def'))
    stats = {
        'atk': base_atk * (1 + mods['atk_pct']) + mods['flat_atk'],
        'hp': base_hp * (1 + mods['hp_pct']) + mods['flat_hp'],
        'def': base_def * (1 + mods['def_pct']) + mods['flat_def'],
        'harmony_strength': mods['harmony_strength'],
        'stagger_strength': mods['stagger_strength'],
        'crit_rate': mods['crit_rate'],
        'crit_dmg': mods['crit_dmg'],
    }
    return {
        'slot': _int(team_member.get('slot')),
        'character': character,
        'arc': arc,
        'cartridge': cartridge,
        'mods': mods,
        'base_stats': {
            'atk': base_atk,
            'hp': base_hp,
            'def': base_def,
        },
        'stats': stats,
        'skill_levels': _skill_levels(team_member.get('skill_levels')),
        'skill_level_bonus': _skill_level_bonus(team_member),
        'build_options': {
            'cartridge_main_stat': main_stat,
            'curtain_bonus': {
                'value': _num(curtain_bonus.get('value')),
                'stat': curtain_bonus.get('stat') or '',
                'passive_type': curtain_bonus.get('passive_type') or 'type3',
                'layers': curtain_layers,
            },
        },
        'personal_resources': {},
    }


def _build_panel_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    character = snapshot.get('character') or {}
    mods = snapshot.get('mods') or {}
    base_stats = snapshot.get('base_stats') or {}
    stats = snapshot.get('stats') or {}
    build_options = snapshot.get('build_options') if isinstance(snapshot.get('build_options'), dict) else {}
    return {
        'slot': _int(snapshot.get('slot')),
        'character_id': character.get('id') or '',
        'character_name': character.get('name') or '',
        'base_stats': {
            'atk': _num(base_stats.get('atk')),
            'hp': _num(base_stats.get('hp')),
            'def': _num(base_stats.get('def')),
        },
        'zones': {
            'atk_pct': _num(mods.get('atk_pct')),
            'flat_atk': _num(mods.get('flat_atk')),
            'hp_pct': _num(mods.get('hp_pct')),
            'flat_hp': _num(mods.get('flat_hp')),
            'def_pct': _num(mods.get('def_pct')),
            'flat_def': _num(mods.get('flat_def')),
        },
        'panel': {
            'atk': _num(stats.get('atk')),
            'hp': _num(stats.get('hp')),
            'def': _num(stats.get('def')),
            'crit_rate': _num(stats.get('crit_rate')),
            'crit_dmg': _num(stats.get('crit_dmg')),
            'element_dmg': _num(mods.get('element_dmg')),
            'energy_recharge': _num(mods.get('energy_recharge')),
            'harmony_strength': _num(stats.get('harmony_strength')),
            'stagger_strength': _num(stats.get('stagger_strength')),
            'all_dmg': _num(mods.get('all_dmg')),
        },
        'build_options': build_options,
    }


def _normalize_enemy(enemy: dict[str, Any] | None) -> dict[str, Any]:
    raw = enemy or {}
    weakness = raw.get('weakness_elements')
    if not isinstance(weakness, list):
        weakness = []
    debuffs = raw.get('debuffs') if isinstance(raw.get('debuffs'), dict) else {}
    hp_ratio = raw.get('hp_ratio')
    if hp_ratio is None and raw.get('hp_percent') is not None:
        hp_ratio = _num(raw.get('hp_percent'), 100) / 100
    return {
        'level': max(1, min(120, _int(raw.get('level'), 90))),
        'track_outside': bool(raw.get('track_outside')),
        'weakness_elements': [str(item) for item in weakness if str(item) in ELEMENTS],
        'debuffs': {
            str(name): max(0, _int(end_tick))
            for name, end_tick in debuffs.items()
            if str(name) in ENEMY_DEBUFF_DURATIONS
        },
        'hp_ratio': max(0.0, min(1.0, _num(hp_ratio, 1.0))),
    }


def _resistance_multiplier(character: dict[str, Any], enemy: dict[str, Any], mods: dict[str, float]) -> float:
    base_res = 0.3
    element = str(character.get('element') or '')
    weakness_down = 0.2 if element in set(enemy.get('weakness_elements') or []) else 0
    value = 1 - base_res + weakness_down + mods['res_down']
    if value < 1:
        return max(0.05, value)
    return max(0.05, 2 - 1 / max(value, 0.01))


def _defense_multiplier(enemy: dict[str, Any], mods: dict[str, float]) -> float:
    actor_level_factor = 6 * 80 + 600
    enemy_factor = 6 * _int(enemy.get('level'), 90) + 600 - (60 if enemy.get('track_outside') else 0)
    defense_left = enemy_factor * max(0, 1 - min(1, mods['def_ignore'])) * max(0, 1 - min(1, mods['def_down']))
    return actor_level_factor / max(actor_level_factor + defense_left, 1)


def _crit_multiplier(action: dict[str, Any], mods: dict[str, float]) -> float:
    extra_tag = str(action.get('extra_tag') or '')
    rate = 0.5 if extra_tag == 'DOT' else min(1, max(0, mods['crit_rate']))
    return max(1, 1 + rate * max(0, mods['crit_dmg']))


def _calculate_action_damage(
    snapshot: dict[str, Any],
    action: dict[str, Any],
    enemy: dict[str, Any],
    extra_modifiers: dict[str, Any] | None = None,
) -> dict[str, float]:
    mods = deepcopy(snapshot['mods'])
    _merge_mods(mods, extra_modifiers)
    _merge_mods(mods, action.get('self_modifiers'))
    base_stats = snapshot.get('base_stats') or {}
    stats = {
        'atk': _num(base_stats.get('atk')) * (1 + mods['atk_pct']) + mods['flat_atk'],
        'hp': _num(base_stats.get('hp')) * (1 + mods['hp_pct']) + mods['flat_hp'],
        'def': _num(base_stats.get('def')) * (1 + mods['def_pct']) + mods['flat_def'],
        'harmony_strength': mods['harmony_strength'],
        'stagger_strength': mods['stagger_strength'],
        'crit_rate': mods['crit_rate'],
        'crit_dmg': mods['crit_dmg'],
    }
    multipliers = action.get('multipliers') or {}
    scaling_base = (
        stats['atk'] * _num(multipliers.get('atk')) +
        stats['hp'] * _num(multipliers.get('hp')) +
        stats['def'] * _num(multipliers.get('def'))
    )
    skill_category, skill_level, skill_multiplier = _skill_level_multiplier(snapshot, action)
    base = scaling_base * skill_multiplier + _num(multipliers.get('flat'))
    if str(action.get('damage_type') or '') in {'无', ''}:
        base = 0
        skill_category = ''
        skill_level = 0
        skill_multiplier = 1.0
    dmg_bonus = _action_type_bonus(action, mods) + mods['element_dmg']
    crit = _crit_multiplier(action, mods)
    resistance = _resistance_multiplier(snapshot['character'], enemy, mods)
    defense = _defense_multiplier(enemy, mods)
    direct = max(0, base * (1 + dmg_bonus) * crit * resistance * defense * (1 + mods['final_dmg']))
    stagger_amount = max(0, _num(action.get('stagger')) * (1 + mods['stagger_strength'] / 300))
    return {
        'direct_damage': direct,
        'stagger_amount': stagger_amount,
        'harmony': _num(action.get('harmony')),
        'energy_gain': _num(action.get('energy_gain')) * (1 + mods['energy_recharge']),
        'panel': {
            'atk': stats['atk'],
            'hp': stats['hp'],
            'def': stats['def'],
            'harmony_strength': stats['harmony_strength'],
            'stagger_strength': stats['stagger_strength'],
            'crit_rate': stats['crit_rate'],
            'crit_dmg': stats['crit_dmg'],
        },
        'formula_parts': {
            'base': base,
            'raw_base': scaling_base + _num(multipliers.get('flat')),
            'skill_level_category': skill_category,
            'skill_level': skill_level,
            'skill_level_multiplier': skill_multiplier,
            'dmg_bonus': dmg_bonus,
            'crit': crit,
            'resistance': resistance,
            'defense': defense,
        },
    }


def _is_background_action(action: dict[str, Any]) -> bool:
    marker_text = f'{action.get("name") or ""} {action.get("extra_tag") or ""}'
    return bool(action.get('is_background_damage')) or '后台' in marker_text


def _is_basic_action(action: dict[str, Any]) -> bool:
    return str(action.get('action_type') or '') == '普攻' or str(action.get('damage_type') or '') == '普攻'


def _can_background_override(action: dict[str, Any]) -> bool:
    return bool(action.get('can_background_override')) and _is_basic_action(action)


def _is_basic_background_override(step: dict[str, Any], action: dict[str, Any]) -> bool:
    return not _is_background_action(action) and _can_background_override(action) and str(step.get('placement') or '') == 'background'


def _is_step_background(step: dict[str, Any], action: dict[str, Any]) -> bool:
    return _is_background_action(action) or _is_basic_background_override(step, action)


def _starts_foreground(step: dict[str, Any], action: dict[str, Any]) -> bool:
    return not _is_step_background(step, action)


def _blocks_slot_overlap(step: dict[str, Any], action: dict[str, Any]) -> bool:
    return _starts_foreground(step, action) or _is_basic_background_override(step, action)


def _is_support_action(action: dict[str, Any]) -> bool:
    return str(action.get('action_type') or '') == '援护'


def _is_q_action(action: dict[str, Any]) -> bool:
    return str(action.get('action_type') or '') == 'Q' or str(action.get('damage_type') or '') == 'Q'


def _action_tags(action: dict[str, Any]) -> set[str]:
    tags = {str(tag) for tag in (action.get('tags') if isinstance(action.get('tags'), list) else []) if str(tag)}
    extra_tag = str(action.get('extra_tag') or '')
    if extra_tag:
        tags.add(extra_tag)
    return tags


def _action_hit_count(action: dict[str, Any]) -> int:
    return max(0, _int(action.get('hit_count')))


def _action_enemy_debuffs(action: dict[str, Any]) -> set[str]:
    tags = _action_tags(action)
    debuffs = {
        tag.split(':', 1)[1]
        for tag in tags
        if tag.startswith('enemy_debuff:') and tag.split(':', 1)[1] in ENEMY_DEBUFF_DURATIONS
    }
    debuffs.update(tag for tag in tags if tag in ENEMY_DEBUFF_DURATIONS)
    return debuffs


def _active_enemy_debuffs(enemy_debuffs: dict[str, int], tick: int) -> dict[str, int]:
    return {
        name: end_tick
        for name, end_tick in enemy_debuffs.items()
        if tick < _int(end_tick)
    }


def _apply_enemy_debuffs(enemy_debuffs: dict[str, int], action: dict[str, Any], tick: int) -> list[str]:
    applied = []
    for debuff in sorted(_action_enemy_debuffs(action)):
        end_tick = tick + ENEMY_DEBUFF_DURATIONS[debuff]
        enemy_debuffs[debuff] = max(_int(enemy_debuffs.get(debuff)), end_tick)
        applied.append(debuff)
    return applied


def _expected_critical_hits(action: dict[str, Any], calc: dict[str, Any]) -> float:
    hit_count = _action_hit_count(action)
    if hit_count <= 0:
        return 0.0
    panel = calc.get('panel') if isinstance(calc.get('panel'), dict) else {}
    rate = 0.5 if str(action.get('extra_tag') or '') == 'DOT' else min(1.0, max(0.0, _num(panel.get('crit_rate'))))
    return hit_count * rate


def _validate_steps(steps: list[dict[str, Any]], actions_by_id: dict[str, dict[str, Any]]) -> None:
    q_anchor_ticks = {
        _int(step.get('start_tick'))
        for step in steps
        if (action := actions_by_id.get(str(step.get('action_id') or ''))) is not None and _starts_foreground(step, action) and _is_q_action(action)
    }
    used_starts: set[int] = set()
    blocking_steps: list[tuple[int, int, dict[str, Any], dict[str, Any]]] = []
    for step in steps:
        start_tick = _int(step.get('start_tick'))
        action = actions_by_id.get(str(step.get('action_id') or ''))
        if action is None:
            raise RuleValidationError('轴中存在未知动作。')
        if _starts_foreground(step, action):
            if start_tick in used_starts and start_tick not in q_anchor_ticks:
                raise RuleValidationError('同一时刻不能有两个前台动作开始节点。')
            used_starts.add(start_tick)
        if _starts_foreground(step, action) or _blocks_slot_overlap(step, action):
            blocking_steps.append((start_tick, _int(step.get('slot')), action, step))
    slot_foreground_end: dict[int, int] = {}
    support_blocks: list[tuple[int, int]] = []
    for start_tick, slot, action, step in sorted(blocking_steps, key=lambda item: (item[0], item[1])):
        foreground_start = _starts_foreground(step, action)
        slot_blocking = _blocks_slot_overlap(step, action)
        if slot_blocking and start_tick < slot_foreground_end.get(slot, 0):
            raise RuleValidationError('同一角色的前台动作不能重叠。')
        if (
            foreground_start and
            start_tick not in q_anchor_ticks and
            any(block_start <= start_tick < block_end for block_start, block_end in support_blocks)
        ):
            raise RuleValidationError('援护技范围内不能有其他前台动作开始节点。')
        end_tick = start_tick + max(1, _int(action.get('duration_ticks')))
        if slot_blocking:
            slot_foreground_end[slot] = end_tick
        if foreground_start and _is_support_action(action):
            support_blocks.append((start_tick, end_tick))


def _rule_matches_trigger(rule: dict[str, Any], step: dict[str, Any], action: dict[str, Any]) -> bool:
    trigger = rule.get('trigger') if isinstance(rule.get('trigger'), dict) else {}
    trigger_slot = trigger.get('slot')
    if trigger_slot not in (None, '') and _int(trigger_slot) != _int(step.get('slot')):
        return False
    action_id = str(trigger.get('action_id') or '')
    if action_id and action_id != str(action.get('id') or ''):
        return False
    action_type = str(trigger.get('action_type') or '')
    if action_type and action_type != str(action.get('action_type') or ''):
        return False
    return bool(action_id or action_type or trigger_slot not in (None, ''))


def _rule_applies_to_step(rule: dict[str, Any], step: dict[str, Any], action: dict[str, Any]) -> bool:
    targets = rule.get('targets') if isinstance(rule.get('targets'), dict) else {}
    slots = targets.get('slots') if isinstance(targets.get('slots'), list) else []
    if slots and _int(step.get('slot')) not in {_int(item) for item in slots}:
        return False
    action_ids = {str(item) for item in (targets.get('action_ids') if isinstance(targets.get('action_ids'), list) else [])}
    if action_ids and str(action.get('id') or '') not in action_ids:
        return False
    action_types = {str(item) for item in (targets.get('action_types') if isinstance(targets.get('action_types'), list) else [])}
    if action_types and str(action.get('action_type') or '') not in action_types:
        return False
    return bool(slots or action_ids or action_types)


def _resource_map(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): _num(value) for key, value in raw.items() if _num(value) != 0}


def _apply_q_instant_release(scheduled_steps: list[dict[str, Any]]) -> None:
    q_events = [
        scheduled
        for scheduled in scheduled_steps
        if not scheduled.get('is_background') and _is_q_action(scheduled.get('action') or {})
    ]
    q_events.sort(key=lambda item: (_int(item.get('start_tick')), _int(item.get('slot'))))
    for q_event in q_events:
        q_start_tick = _int(q_event.get('start_tick'))
        q_visual_end_tick = _int(q_event.get('visual_end_tick'))
        q_anchor_tick = (
            q_start_tick
            if max(0, _int(q_event.get('duration_ticks'))) == 0
            else q_start_tick + (max(q_start_tick + 1, q_visual_end_tick) - q_start_tick) / 2
        )
        q_step_id = str((q_event.get('step') or {}).get('id') or '')
        q_slot = _int(q_event.get('slot'))
        for scheduled in scheduled_steps:
            if scheduled is q_event or scheduled.get('q_instant_release'):
                continue
            start_tick = _int(scheduled.get('start_tick'))
            end_tick = _int(scheduled.get('end_tick'))
            duration_ticks = max(0, _int(scheduled.get('duration_ticks')))
            in_q_column = _int(scheduled.get('slot')) != q_slot and (
                start_tick <= q_start_tick < end_tick or start_tick == q_start_tick
            )
            ongoing_foreground = (
                not scheduled.get('is_background') and
                duration_ticks > 0 and
                start_tick < q_start_tick < end_tick
            )
            if not in_q_column and not ongoing_foreground:
                continue
            scheduled.setdefault('original_duration_ticks', duration_ticks)
            scheduled.setdefault('original_end_tick', end_tick)
            scheduled.setdefault('original_visual_end_tick', _int(scheduled.get('visual_end_tick')))
            scheduled['duration_ticks'] = max(0, q_start_tick - start_tick)
            scheduled['end_tick'] = max(start_tick, q_start_tick)
            scheduled['visual_end_tick'] = max(start_tick, q_start_tick)
            release_kind = 'column' if in_q_column else 'foreground'
            scheduled['q_instant_release'] = True
            scheduled['q_instant_release_kind'] = release_kind
            scheduled['q_instant_release_tick'] = q_start_tick
            scheduled['q_instant_release_anchor_tick'] = q_anchor_tick
            scheduled['q_instant_release_anchor_step_id'] = q_step_id


def simulate_axis(axis_payload: dict[str, Any]) -> dict[str, Any]:
    catalog = load_shaft_catalog()
    actions_by_id = get_record_map(catalog['actions'])
    team_payload = axis_payload.get('team') if isinstance(axis_payload.get('team'), list) else []
    steps = axis_payload.get('steps') if isinstance(axis_payload.get('steps'), list) else catalog['starter_axis']['steps']
    if not team_payload:
        team_payload = catalog['starter_axis']['team']
    _validate_steps(steps, actions_by_id)

    raw_team_panel_bonus = axis_payload.get('team_panel_bonus')
    team_panel_bonus = _team_panel_bonus(raw_team_panel_bonus, catalog)
    snapshots = {
        snapshot['slot']: snapshot
        for snapshot in (_build_snapshot(member, catalog, team_panel_bonus) for member in team_payload)
    }
    enemy = _normalize_enemy(axis_payload.get('enemy'))
    options = axis_payload.get('options') if isinstance(axis_payload.get('options'), dict) else {}
    enemy_debuffs: dict[str, int] = {
        str(name): max(0, _int(end_tick))
        for name, end_tick in (enemy.get('debuffs') if isinstance(enemy.get('debuffs'), dict) else {}).items()
        if str(name) in ENEMY_DEBUFF_DURATIONS
    }
    fons_full = options.get('fons_full')
    fons_full = True if fons_full is None else bool(fons_full)
    switch_loss_ticks = max(0, _int(options.get('switch_loss_ticks'), _int(catalog['formula_constants'].get('switch_loss_ticks'), 2)))

    details = []
    front_events = []
    direct_damage = 0.0
    stagger_damage = 0.0
    total_stagger = 0.0
    initial_energy = _num(axis_payload.get('initial_energy'), 100)
    energy_by_slot: dict[int, float] = {slot: initial_energy for slot in snapshots}
    harmony_by_slot: dict[int, float] = {slot: 0.0 for slot in snapshots}
    cooldown_until: dict[tuple[int, str], int] = {}
    personal_resources: dict[int, dict[str, float]] = {slot: {} for slot in snapshots}
    initial_personal_resources = axis_payload.get('initial_personal_resources') if isinstance(axis_payload.get('initial_personal_resources'), dict) else {}
    for slot, resources in personal_resources.items():
        raw_resources = initial_personal_resources.get(str(slot), initial_personal_resources.get(slot, {}))
        resources.update(_resource_map(raw_resources))
    buff_rules = registered_buff_rules(team_payload, catalog) + legacy_buff_rules_from_axis(axis_payload.get('buff_rules'))
    ordered_steps = sorted(steps, key=lambda item: (_int(item.get('start_tick')), _int(item.get('slot'))))
    scheduled_steps: list[dict[str, Any]] = []
    schedule_front_slot: int | None = None
    schedule_previous_foreground_duration_ticks = 0
    scheduled_last_tick = 0
    for step in ordered_steps:
        slot = _int(step.get('slot'))
        snapshot = snapshots.get(slot)
        if snapshot is None:
            continue
        action = actions_by_id[str(step.get('action_id'))]
        start_tick = _int(step.get('start_tick'))
        is_background = _is_step_background(step, action)
        if (
            not is_background and
            schedule_front_slot is not None and
            schedule_front_slot != slot and
            schedule_previous_foreground_duration_ticks > 0
        ):
            start_tick += switch_loss_ticks
        duration_ticks = max(0, _int(action.get('duration_ticks')))
        end_tick = start_tick + duration_ticks
        visual_end_tick = start_tick + (duration_ticks if duration_ticks > 0 else ZERO_ACTION_VISUAL_TICKS)
        scheduled_steps.append({
            'step': step,
            'slot': slot,
            'action': action,
            'start_tick': start_tick,
            'is_background': is_background,
            'duration_ticks': duration_ticks,
            'end_tick': end_tick,
            'visual_end_tick': visual_end_tick,
            'original_duration_ticks': duration_ticks,
            'original_end_tick': end_tick,
            'original_visual_end_tick': visual_end_tick,
        })
        if not is_background:
            schedule_front_slot = slot
            schedule_previous_foreground_duration_ticks = duration_ticks
        scheduled_last_tick = max(scheduled_last_tick, end_tick, visual_end_tick, start_tick)

    _apply_q_instant_release(scheduled_steps)
    scheduled_last_tick = max(
        1,
        *[
            max(_int(item.get('end_tick')), _int(item.get('visual_end_tick')), _int(item.get('start_tick')))
            for item in scheduled_steps
        ] if scheduled_steps else [0],
    )

    loop_duration_ticks = max(scheduled_last_tick, 1)
    active_buffs: list[dict[str, Any]] = []
    buff_trigger_cooldowns: dict[tuple[int, str], int] = {}

    def trigger_tick_for_rule(rule: dict[str, Any], start_tick: int, end_tick: int) -> int:
        trigger = rule.get('trigger') if isinstance(rule.get('trigger'), dict) else {}
        event = str(trigger.get('event') or '')
        return end_tick if event == 'action_end' else start_tick

    def trigger_buffs_for_event(
        event: str,
        trigger_tick: int,
        step: dict[str, Any],
        action: dict[str, Any],
        snapshot: dict[str, Any],
        is_background: bool,
        extra_context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        triggered: list[dict[str, Any]] = []
        context = {
            'enemy': enemy,
            'snapshot': snapshot,
            'tick': trigger_tick,
            'action_tags': sorted(_action_tags(action)),
            'hit_count': _action_hit_count(action),
            'enemy_debuffs': _active_enemy_debuffs(enemy_debuffs, trigger_tick),
            'applied_enemy_debuffs': [],
            'fons_full': fons_full,
        }
        if extra_context:
            context.update(extra_context)
        for rule in buff_rules:
            if not event_matches_rule(rule, event, step, action, snapshot, is_background, context):
                continue
            cooldown_ticks = trigger_cooldown_ticks(rule)
            cooldown_key = (_int(rule.get('owner_slot')), str(rule.get('id') or ''))
            if cooldown_ticks > 0 and trigger_tick < buff_trigger_cooldowns.get(cooldown_key, 0):
                continue
            instance = activate_buff(active_buffs, rule, trigger_tick, stack_gain_for_rule(rule, context))
            if instance is not None:
                if cooldown_ticks > 0:
                    buff_trigger_cooldowns[cooldown_key] = trigger_tick + cooldown_ticks
                triggered.append(buff_summary(instance))
        return triggered

    if bool(options.get('loop_enabled')) and loop_duration_ticks > 0:
        for scheduled in scheduled_steps:
            step = scheduled['step']
            action = scheduled['action']
            slot = _int(scheduled.get('slot'))
            snapshot = snapshots.get(slot)
            if snapshot is None:
                continue
            start_tick = _int(scheduled.get('start_tick'))
            end_tick = _int(scheduled.get('end_tick'))
            is_background = bool(scheduled.get('is_background'))
            for rule in buff_rules:
                trigger = rule.get('trigger') if isinstance(rule.get('trigger'), dict) else {}
                event = str(trigger.get('event') or '')
                duration = rule.get('duration') if isinstance(rule.get('duration'), dict) else {}
                if not bool(duration.get('loop_carry')):
                    continue
                trigger_tick = trigger_tick_for_rule(rule, start_tick, end_tick)
                context = {
                    'enemy': enemy,
                    'snapshot': snapshot,
                    'tick': trigger_tick,
                    'action_tags': sorted(_action_tags(action)),
                    'hit_count': _action_hit_count(action),
                    'enemy_debuffs': _active_enemy_debuffs(enemy_debuffs, trigger_tick),
                    'applied_enemy_debuffs': [],
                    'fons_full': fons_full,
                }
                if not event_matches_rule(rule, event, step, action, snapshot, is_background, context):
                    continue
                carried_trigger_tick = trigger_tick - loop_duration_ticks
                instance = activate_buff(active_buffs, rule, carried_trigger_tick, stack_gain_for_rule(rule, context))
                if instance is not None:
                    instance['start_tick'] = max(0, _int(instance.get('start_tick')))
                    instance['looped'] = True

    last_tick = 0

    for scheduled in scheduled_steps:
        step = scheduled['step']
        slot = _int(scheduled.get('slot'))
        snapshot = snapshots.get(slot)
        if snapshot is None:
            continue
        action = scheduled['action']
        start_tick = _int(scheduled.get('start_tick'))
        is_background = bool(scheduled.get('is_background'))
        duration_ticks = max(0, _int(scheduled.get('duration_ticks')))
        end_tick = _int(scheduled.get('end_tick'))
        visual_end_tick = _int(scheduled.get('visual_end_tick'))
        cooldown_key = (slot, str(action.get('id')))
        available_tick = cooldown_until.get(cooldown_key, 0)
        warnings = []
        if start_tick < available_tick:
            warnings.append(f'动作 CD 尚未结束，需等到 {available_tick / 10:.1f}s。')
        energy_cost = _num(action.get('energy_cost'))
        slot_energy = energy_by_slot.get(slot, initial_energy)
        if energy_cost > slot_energy:
            warnings.append('终结技能量不足。')
        enemy_debuffs = _active_enemy_debuffs(enemy_debuffs, start_tick)
        active_buffs = [
            buff
            for buff in active_buffs
            if start_tick < _int(buff.get('end_tick')) and not active_buff_resets_on_action_start(buff, step, is_background)
        ]
        triggered_buffs = trigger_buffs_for_event('action_start', start_tick, step, action, snapshot, is_background)
        applied_buffs = []
        buff_modifiers = _mods()
        for buff in active_buffs:
            if start_tick < _int(buff.get('start_tick')) or start_tick >= _int(buff.get('end_tick')):
                continue
            if not active_buff_applies(buff, step, action, snapshot, is_background):
                continue
            _merge_mods(buff_modifiers, buff_effects(buff))
            applied_buffs.append(buff_summary(buff))
        slot_resources = personal_resources.setdefault(slot, {})
        for resource_key, cost in _resource_map(action.get('personal_resource_cost')).items():
            if slot_resources.get(resource_key, 0) < cost:
                warnings.append(f'个人资源 {resource_key} 不足。')
            slot_resources[resource_key] = max(0, slot_resources.get(resource_key, 0) - cost)
        for resource_key, gain in _resource_map(action.get('personal_resource_gain')).items():
            slot_resources[resource_key] = slot_resources.get(resource_key, 0) + gain
        slot_energy = max(0, slot_energy - energy_cost)
        calc = _calculate_action_damage(snapshot, action, enemy, buff_modifiers)
        expected_critical_hits = _expected_critical_hits(action, calc)
        applied_enemy_debuffs = _apply_enemy_debuffs(enemy_debuffs, action, start_tick)
        triggered_buffs.extend(trigger_buffs_for_event(
            'action_hit',
            start_tick,
            step,
            action,
            snapshot,
            is_background,
            {
                'expected_critical_hits': expected_critical_hits,
                'applied_enemy_debuffs': applied_enemy_debuffs,
                'enemy_debuffs': _active_enemy_debuffs(enemy_debuffs, start_tick),
            },
        ))
        direct_damage += calc['direct_damage']
        total_stagger += calc['stagger_amount']
        harmony_by_slot[slot] = harmony_by_slot.get(slot, 0.0) + calc['harmony']
        slot_energy += calc['energy_gain'] + _num(action.get('energy_return'))
        energy_by_slot[slot] = slot_energy
        while total_stagger >= 50:
            total_stagger -= 50
            reaction_strength = max(snap['stats']['harmony_strength'] for snap in snapshots.values())
            reaction_damage = 12000 * (1 + reaction_strength / 600) * _defense_multiplier(enemy, snapshot['mods'])
            stagger_damage += reaction_damage
        if duration_ticks > 0:
            cooldown_until[cooldown_key] = max(cooldown_until.get(cooldown_key, 0), start_tick + max(duration_ticks, _int(action.get('cooldown_ticks'))))
        elif _int(action.get('cooldown_ticks')) > 0:
            cooldown_until[cooldown_key] = max(cooldown_until.get(cooldown_key, 0), start_tick + _int(action.get('cooldown_ticks')))
        if not is_background:
            front_events.append({
                'slot': slot,
                'start_tick': start_tick,
                'end_tick': end_tick,
                'visual_end_tick': visual_end_tick,
                'order': len(front_events),
            })
        triggered_buffs.extend(trigger_buffs_for_event('action_end', end_tick, step, action, snapshot, is_background))
        last_tick = max(last_tick, end_tick, visual_end_tick, start_tick)
        details.append({
            'step_id': step.get('id') or '',
            'slot': slot,
            'character_id': snapshot['character']['id'],
            'character_name': snapshot['character']['name'],
            'action_id': action['id'],
            'action_name': action['name'],
            'action_type': action.get('action_type'),
            'raw_start_tick': _int(step.get('start_tick')),
            'start_tick': start_tick,
            'end_tick': end_tick,
            'duration_ticks': duration_ticks,
            'visual_end_tick': visual_end_tick,
            'original_duration_ticks': _int(scheduled.get('original_duration_ticks'), duration_ticks),
            'original_end_tick': _int(scheduled.get('original_end_tick'), end_tick),
            'original_visual_end_tick': _int(scheduled.get('original_visual_end_tick'), visual_end_tick),
            'q_instant_release': bool(scheduled.get('q_instant_release')),
            'q_instant_release_kind': scheduled.get('q_instant_release_kind') or '',
            'q_instant_release_tick': scheduled.get('q_instant_release_tick'),
            'q_instant_release_anchor_tick': scheduled.get('q_instant_release_anchor_tick'),
            'q_instant_release_anchor_step_id': scheduled.get('q_instant_release_anchor_step_id') or '',
            'is_background_damage': is_background,
            'is_basic_background': _is_basic_background_override(step, action),
            'action_tags': sorted(_action_tags(action)),
            'hit_count': _action_hit_count(action),
            'expected_critical_hits': expected_critical_hits,
            'applied_enemy_debuffs': applied_enemy_debuffs,
            'enemy_debuffs': _active_enemy_debuffs(enemy_debuffs, start_tick),
            'direct_damage': calc['direct_damage'],
            'stagger_amount': calc['stagger_amount'],
            'harmony': calc['harmony'],
            'energy_after': slot_energy,
            'harmony_after': harmony_by_slot.get(slot, 0.0),
            'personal_resources_after': dict(slot_resources),
            'nightmare_stacks': action.get('nightmare_stacks'),
            'sin_recovery': action.get('sin_recovery'),
            'applied_buffs': applied_buffs,
            'triggered_buffs': triggered_buffs,
            'panel': calc['panel'],
            'formula_parts': calc['formula_parts'],
            'warnings': warnings,
        })

    front_events.sort(key=lambda item: (_int(item.get('start_tick')), _int(item.get('order'))))
    deduped_front_events: list[dict[str, Any]] = []
    for event in front_events:
        if deduped_front_events and _int(deduped_front_events[-1].get('start_tick')) == _int(event.get('start_tick')):
            deduped_front_events[-1] = event
        else:
            deduped_front_events.append(event)
    front_windows: list[dict[str, Any]] = []
    for index, event in enumerate(deduped_front_events):
        start_tick = _int(event.get('start_tick'))
        if index + 1 < len(deduped_front_events):
            end_tick = _int(deduped_front_events[index + 1].get('start_tick'))
        else:
            end_tick = max(_int(event.get('end_tick')), _int(event.get('visual_end_tick')), start_tick + 1)
        if end_tick <= start_tick:
            continue
        if front_windows and _int(front_windows[-1].get('slot')) == _int(event.get('slot')) and start_tick <= _int(front_windows[-1].get('end_tick')):
            front_windows[-1]['end_tick'] = max(_int(front_windows[-1].get('end_tick')), end_tick)
            front_windows[-1]['visual_end_tick'] = front_windows[-1]['end_tick']
            continue
        front_windows.append({
            'slot': _int(event.get('slot')),
            'start_tick': start_tick,
            'end_tick': end_tick,
            'visual_end_tick': end_tick,
        })

    duration_ticks = max(last_tick, 1)
    total_damage = direct_damage + stagger_damage
    team_energy = sum(energy_by_slot.values())
    total_harmony = sum(harmony_by_slot.values())
    damage_by_slot: dict[int, float] = {}
    for detail in details:
        damage_by_slot[detail['slot']] = damage_by_slot.get(detail['slot'], 0) + detail['direct_damage']

    return {
        'ok': True,
        'summary': {
            'duration_ticks': duration_ticks,
            'duration_seconds': duration_ticks / 10,
            'direct_damage': direct_damage,
            'stagger_damage': stagger_damage,
            'total_damage': total_damage,
            'dps': total_damage / max(duration_ticks / 10, 0.1),
            'team_energy': team_energy,
            'total_harmony': total_harmony,
        },
        'damage_by_slot': [
            {
                'slot': slot,
                'character_id': snapshots[slot]['character']['id'],
                'character_name': snapshots[slot]['character']['name'],
                'damage': damage_by_slot.get(slot, 0),
                'percent': (damage_by_slot.get(slot, 0) / direct_damage * 100) if direct_damage > 0 else 0,
            }
            for slot in sorted(snapshots)
        ],
        'resources_by_slot': [
            {
                'slot': slot,
                'character_id': snapshots[slot]['character']['id'],
                'character_name': snapshots[slot]['character']['name'],
                'initial_energy': initial_energy,
                'energy': energy_by_slot.get(slot, initial_energy),
                'initial_harmony': 0,
                'harmony': harmony_by_slot.get(slot, 0.0),
                'personal_resources': personal_resources.get(slot, {}),
            }
            for slot in sorted(snapshots)
        ],
        'build_panels_by_slot': [
            _build_panel_projection(snapshots[slot])
            for slot in sorted(snapshots)
        ],
        'details': details,
        'front_windows': front_windows,
        'enemy': enemy,
    }


def normalize_axis_for_hash(axis_payload: dict[str, Any]) -> dict[str, Any]:
    team = []
    for member in axis_payload.get('team') or []:
        team.append({
            'slot': _int(member.get('slot')),
            'character_id': str(member.get('character_id') or ''),
            'arc_id': str(member.get('arc_id') or ''),
            'cartridge_id': str(member.get('cartridge_id') or ''),
        })
    steps = []
    for step in axis_payload.get('steps') or []:
        item = {
            'slot': _int(step.get('slot')),
            'action_id': str(step.get('action_id') or ''),
            'start_tick': _int(step.get('start_tick')),
            'repeat': max(1, _int(step.get('repeat'), 1)),
        }
        if str(step.get('placement') or '') == 'background':
            item['placement'] = 'background'
        steps.append(item)
    return {
        'team': sorted(team, key=lambda item: item['slot']),
        'steps': sorted(steps, key=lambda item: (item['start_tick'], item['slot'], item['action_id'])),
    }


def calculate_axis_hash(axis_payload: dict[str, Any]) -> str:
    normalized = normalize_axis_for_hash(axis_payload)
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
