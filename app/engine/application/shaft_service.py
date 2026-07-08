from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.db import atomic_transaction
from app.errors import RuleValidationError
from app.models import Player, ShaftAxis, ShaftAxisCharacter, ShaftAxisFavorite, ShaftAxisLike
from app.shaft.catalog import get_record_map, load_shaft_catalog
from app.shaft.simulator import ELEMENTS, calculate_axis_hash, simulate_axis
from app.utils.logger import get_logger


logger = get_logger('nte.shaft')
MAX_AXIS_TITLE_LENGTH = 80
MAX_AXIS_DESCRIPTION_LENGTH = 800
MAX_AXIS_STEPS = 240
MAX_BUFF_RULES = 48
VISIBILITIES = frozenset({'private', 'public'})
MARKET_SORTS = frozenset({'dps', 'likes', 'favorites', 'new'})
SUBSTAT_KEYS = (
    'all_dmg',
    'crit_rate',
    'crit_dmg',
    'harmony_strength',
    'stagger_strength',
    'atk_pct',
    'flat_atk',
    'hp_pct',
    'flat_hp',
    'def_pct',
    'flat_def',
)
MODIFIER_KEYS = (
    'all_dmg',
    'crit_rate',
    'crit_dmg',
    'atk_pct',
    'flat_atk',
    'hp_pct',
    'flat_hp',
    'def_pct',
    'flat_def',
    'def_down',
    'def_ignore',
    'res_down',
    'energy_recharge',
    'harmony_strength',
    'stagger_strength',
    'basic_dmg',
    'dodge_counter_dmg',
    'element_dmg',
    'follow_dmg',
    'mind_dmg',
    'attach_dmg',
    'skill_dmg',
    'ultimate_dmg',
    'final_dmg',
)
TEAM_PANEL_BONUS_DEFAULTS = {
    'version': 2.0,
    'furniture_crit_dmg': 0.04,
    'furniture_flat_atk': 20.0,
    'furniture_flat_def': 30.0,
    'small_flat_atk': 420.0,
    'small_flat_hp': 5200.0,
}
SKILL_LEVEL_KEYS = ('basic', 'skill', 'ultimate', 'support')
SKILL_LEVEL_DEFAULTS = {
    'basic': 10,
    'skill': 10,
    'ultimate': 10,
    'support': 10,
}
CURTAIN_PASSIVE_TYPES = ('type2', 'type3', 'type4')


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _safe_json_loads(payload: str, fallback: Any) -> Any:
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return fallback


def _clean_text(value: Any, max_length: int) -> str:
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    return text[:max_length]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    return int(round(_num(value, default)))


def _axis_body(payload: dict[str, Any]) -> dict[str, Any]:
    body = payload.get('axis')
    if isinstance(body, dict):
        return dict(body)
    return dict(payload)


def _normalize_enemy(raw: Any, catalog: dict[str, Any]) -> dict[str, Any]:
    defaults = catalog['formula_constants'].get('default_enemy') or {}
    enemy = raw if isinstance(raw, dict) else {}
    weakness = enemy.get('weakness_elements')
    if not isinstance(weakness, list):
        weakness = defaults.get('weakness_elements') or []
    debuffs = enemy.get('debuffs') if isinstance(enemy.get('debuffs'), dict) else {}
    hp_ratio = enemy.get('hp_ratio')
    if hp_ratio is None and enemy.get('hp_percent') is not None:
        hp_ratio = _num(enemy.get('hp_percent'), 100) / 100
    return {
        'level': max(1, min(120, _int(enemy.get('level'), _int(defaults.get('level'), 90)))),
        'track_outside': bool(enemy.get('track_outside', defaults.get('track_outside', False))),
        'weakness_elements': [str(item) for item in weakness if str(item) in ELEMENTS],
        'debuffs': {
            str(name): max(0, min(6000, _int(end_tick)))
            for name, end_tick in debuffs.items()
            if str(name) in {'延滞', '黯星', '浸染', '覆纹', '浊燃'}
        },
        'hp_ratio': max(0.0, min(1.0, _num(hp_ratio, 1.0))),
    }


def _normalize_substat_counts(raw: Any) -> dict[str, int]:
    counts = raw if isinstance(raw, dict) else {}
    return {key: max(0, min(30, _int(counts.get(key)))) for key in SUBSTAT_KEYS}


def _normalize_skill_levels(raw: Any) -> dict[str, int]:
    levels = raw if isinstance(raw, dict) else {}
    return {
        key: max(1, min(10, _int(levels.get(key), SKILL_LEVEL_DEFAULTS[key])))
        for key in SKILL_LEVEL_KEYS
    }


def _default_build_options(character_id: str, catalog: dict[str, Any]) -> dict[str, Any]:
    constants = catalog.get('formula_constants') or {}
    defaults = constants.get('default_build_options') if isinstance(constants.get('default_build_options'), dict) else {}
    return defaults.get(character_id) if isinstance(defaults.get(character_id), dict) else {}


def _normalize_stat_name(value: Any) -> str:
    text = str(value or '').strip()
    return '精通' if text == '环合强度' else text


def _normalize_cartridge_main_stat(raw: Any, character_id: str, catalog: dict[str, Any]) -> str:
    constants = catalog.get('formula_constants') or {}
    options = constants.get('cartridge_main_stat_options') if isinstance(constants.get('cartridge_main_stat_options'), dict) else {}
    default = _normalize_stat_name(_default_build_options(character_id, catalog).get('cartridge_main_stat')) or next(iter(options), '')
    selected = _normalize_stat_name(raw) or default
    return selected if selected in options else default


def _normalize_curtain_bonus(raw: Any, character_id: str, catalog: dict[str, Any]) -> dict[str, Any]:
    constants = catalog.get('formula_constants') or {}
    stat_options = constants.get('curtain_bonus_stat_options') if isinstance(constants.get('curtain_bonus_stat_options'), dict) else {}
    defaults = _default_build_options(character_id, catalog).get('curtain_bonus')
    default_bonus = defaults if isinstance(defaults, dict) else {}
    source = raw if isinstance(raw, dict) else {}
    default_stat = _normalize_stat_name(default_bonus.get('stat')) or next(iter(stat_options), '')
    stat = _normalize_stat_name(source.get('stat')) or default_stat
    passive_type = str(source.get('passive_type') or default_bonus.get('passive_type') or 'type3')
    if passive_type not in CURTAIN_PASSIVE_TYPES:
        passive_type = 'type3'
    return {
        'value': max(0.0, min(100.0, _num(source.get('value'), _num(default_bonus.get('value'))))),
        'stat': stat if stat in stat_options else default_stat,
        'passive_type': passive_type,
    }


def _normalize_team(raw: Any, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    team = raw if isinstance(raw, list) and raw else catalog['starter_axis']['team']
    characters = get_record_map(catalog['characters'])
    arcs = get_record_map(catalog['arcs'])
    cartridges = get_record_map(catalog['cartridges'])
    normalized: list[dict[str, Any]] = []
    used_slots: set[int] = set()
    for index, member in enumerate(team[:4]):
        if not isinstance(member, dict):
            continue
        slot = max(0, min(3, _int(member.get('slot'), index)))
        if slot in used_slots:
            raise RuleValidationError('队伍中存在重复位置。')
        used_slots.add(slot)
        character_id = str(member.get('character_id') or '')
        if character_id not in characters:
            raise RuleValidationError('队伍中存在未知角色。')
        arc_id = str(member.get('arc_id') or '')
        cartridge_id = str(member.get('cartridge_id') or '')
        if arc_id and arc_id not in arcs:
            raise RuleValidationError('队伍中存在未知弧盘。')
        if cartridge_id and cartridge_id not in cartridges:
            raise RuleValidationError('队伍中存在未知卡带。')
        character = characters[character_id]
        arc = arcs.get(arc_id)
        cartridge = cartridges.get(cartridge_id)
        normalized.append({
            'slot': slot,
            'character_id': character_id,
            'character_name': character.get('name') or '',
            'arc_id': arc_id,
            'arc_name': (arc or {}).get('name') or '',
            'cartridge_id': cartridge_id,
            'cartridge_name': (cartridge or {}).get('name') or '',
            'awakening': max(0, min(6, _int(member.get('awakening')))),
            'bond_level': max(0, min(1, _int(member.get('bond_level'), 1 if member.get('bond_full') else 0))),
            'bond_full': bool(member.get('bond_full')) or _int(member.get('bond_level')) > 0,
            'skill_levels': _normalize_skill_levels(member.get('skill_levels')),
            'cartridge_main_stat': _normalize_cartridge_main_stat(member.get('cartridge_main_stat'), character_id, catalog),
            'curtain_bonus': _normalize_curtain_bonus(member.get('curtain_bonus'), character_id, catalog),
            'substat_counts': _normalize_substat_counts(member.get('substat_counts')),
        })
    if not normalized:
        raise RuleValidationError('队伍不能为空。')
    normalized.sort(key=lambda item: item['slot'])
    return normalized


def _normalize_character_builds(raw: Any, team: list[dict[str, Any]], catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    characters = get_record_map(catalog['characters'])
    arcs = get_record_map(catalog['arcs'])
    cartridges = get_record_map(catalog['cartridges'])
    source = raw if isinstance(raw, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}

    def normalize_one(character_id: str, value: Any) -> None:
        if character_id not in characters:
            return
        build = value if isinstance(value, dict) else {}
        arc_id = str(build.get('arc_id') or '')
        cartridge_id = str(build.get('cartridge_id') or '')
        normalized[character_id] = {
            'character_id': character_id,
            'character_name': characters[character_id].get('name') or '',
            'arc_id': arc_id if arc_id in arcs else '',
            'arc_name': (arcs.get(arc_id) or {}).get('name') or '',
            'cartridge_id': cartridge_id if cartridge_id in cartridges else '',
            'cartridge_name': (cartridges.get(cartridge_id) or {}).get('name') or '',
            'awakening': max(0, min(6, _int(build.get('awakening')))),
            'bond_level': max(0, min(1, _int(build.get('bond_level'), 1 if build.get('bond_full') else 0))),
            'bond_full': bool(build.get('bond_full')) or _int(build.get('bond_level')) > 0,
            'skill_levels': _normalize_skill_levels(build.get('skill_levels')),
            'cartridge_main_stat': _normalize_cartridge_main_stat(build.get('cartridge_main_stat'), character_id, catalog),
            'curtain_bonus': _normalize_curtain_bonus(build.get('curtain_bonus'), character_id, catalog),
            'substat_counts': _normalize_substat_counts(build.get('substat_counts')),
        }

    for character_id, build in source.items():
        normalize_one(str(character_id), build)
    for member in team:
        character_id = str(member.get('character_id') or '')
        if character_id not in normalized:
            normalize_one(character_id, member)
    return normalized


def _apply_character_builds_to_team(team: list[dict[str, Any]], character_builds: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged_team: list[dict[str, Any]] = []
    for member in team:
        character_id = str(member.get('character_id') or '')
        build = character_builds.get(character_id)
        if not build:
            merged_team.append(member)
            continue
        merged = dict(member)
        for key in (
            'arc_id',
            'arc_name',
            'cartridge_id',
            'cartridge_name',
            'awakening',
            'bond_level',
            'bond_full',
            'skill_levels',
            'cartridge_main_stat',
            'curtain_bonus',
            'substat_counts',
        ):
            if key in build:
                merged[key] = build[key]
        merged_team.append(merged)
    return merged_team


def _normalize_steps(raw: Any, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    steps = raw if isinstance(raw, list) else catalog['starter_axis']['steps']
    actions = get_record_map(catalog['actions'])
    normalized: list[dict[str, Any]] = []
    used_starts: set[int] = set()
    q_anchor_ticks: set[int] = {
        max(0, _int(step.get('start_tick')))
        for step in steps[:MAX_AXIS_STEPS]
        if isinstance(step, dict) and (action := actions.get(str(step.get('action_id') or ''))) and _starts_foreground(step, action) and _is_q_action(action)
    }
    for index, step in enumerate(steps[:MAX_AXIS_STEPS]):
        if not isinstance(step, dict):
            continue
        action_id = str(step.get('action_id') or '')
        action = actions.get(action_id)
        if not action:
            raise RuleValidationError('轴中存在未知动作。')
        start_tick = max(0, _int(step.get('start_tick')))
        placement = _normalize_step_placement(step, action)
        normalized_step = {
            'id': str(step.get('id') or f'step_{index + 1:03d}')[:40],
            'slot': max(0, min(3, _int(step.get('slot')))),
            'action_id': action_id,
            'action_name': action.get('name') or '',
            'start_tick': start_tick,
            'repeat': max(1, min(12, _int(step.get('repeat'), 1))),
            'tags': step.get('tags') if isinstance(step.get('tags'), list) else [],
        }
        if placement == 'background' and not _is_background_action(action):
            normalized_step['placement'] = 'background'
        if _starts_foreground(normalized_step, action):
            if start_tick in used_starts and start_tick not in q_anchor_ticks:
                raise RuleValidationError('同一时刻不能有两个前台动作开始节点。')
            used_starts.add(start_tick)
        normalized.append(normalized_step)
    normalized.sort(key=lambda item: (item['start_tick'], item['slot'], item['action_id']))
    slot_foreground_end: dict[int, int] = {}
    support_blocks: list[tuple[int, int]] = []
    for step in normalized:
        action = actions.get(str(step.get('action_id') or '')) or {}
        foreground_start = _starts_foreground(step, action)
        slot_blocking = _blocks_slot_overlap(step, action)
        if not foreground_start and not slot_blocking:
            continue
        slot = _int(step.get('slot'))
        start_tick = _int(step.get('start_tick'))
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
    return normalized


def _axis_duration_ticks(steps: list[dict[str, Any]], catalog: dict[str, Any]) -> int:
    actions = get_record_map(catalog['actions'])
    last_tick = 0
    for step in steps:
        action = actions.get(str(step.get('action_id') or '')) or {}
        start_tick = max(0, _int(step.get('start_tick')))
        last_tick = max(last_tick, start_tick + max(0, _int(action.get('duration_ticks'))), start_tick)
    return max(1, last_tick)


def _normalize_options(raw: Any, catalog: dict[str, Any]) -> dict[str, Any]:
    options = raw if isinstance(raw, dict) else {}
    return {
        'switch_loss_ticks': max(
            0,
            min(20, _int(options.get('switch_loss_ticks'), _int(catalog['formula_constants'].get('switch_loss_ticks'), 2))),
        ),
        'loop_enabled': bool(options.get('loop_enabled')),
    }


def _team_panel_bonus_defaults(catalog: dict[str, Any]) -> dict[str, float]:
    defaults = dict(TEAM_PANEL_BONUS_DEFAULTS)
    starter_bonus = (catalog.get('starter_axis') or {}).get('team_panel_bonus')
    if isinstance(starter_bonus, dict):
        for key in defaults:
            defaults[key] = _num(starter_bonus.get(key), defaults[key])
    return defaults


def _normalize_team_panel_bonus(raw: Any, catalog: dict[str, Any]) -> dict[str, float]:
    defaults = _team_panel_bonus_defaults(catalog)
    source = raw if isinstance(raw, dict) else {}
    version = max(0, _int(source.get('version')))
    furniture_flat_atk = max(0.0, min(5000.0, _num(source.get('furniture_flat_atk'), defaults['furniture_flat_atk'])))
    small_flat_atk = max(0.0, min(5000.0, _num(source.get('small_flat_atk'), defaults['small_flat_atk'])))
    if version < 2 and furniture_flat_atk == 20.0 and small_flat_atk == 440.0:
        small_flat_atk = 420.0
    return {
        'version': 2,
        'furniture_crit_dmg': max(0.0, min(5.0, _num(source.get('furniture_crit_dmg'), defaults['furniture_crit_dmg']))),
        'furniture_flat_atk': furniture_flat_atk,
        'furniture_flat_def': max(0.0, min(5000.0, _num(source.get('furniture_flat_def'), defaults['furniture_flat_def']))),
        'small_flat_atk': small_flat_atk,
        'small_flat_hp': max(0.0, min(100000.0, _num(source.get('small_flat_hp'), defaults['small_flat_hp']))),
    }


def _is_background_action(action: dict[str, Any]) -> bool:
    marker_text = f'{action.get("name") or ""} {action.get("extra_tag") or ""}'
    return bool(action.get('is_background_damage')) or '后台' in marker_text


def _is_basic_action(action: dict[str, Any]) -> bool:
    return str(action.get('action_type') or '') == '普攻' or str(action.get('damage_type') or '') == '普攻'


def _can_background_override(action: dict[str, Any]) -> bool:
    return bool(action.get('can_background_override')) and _is_basic_action(action)


def _normalize_step_placement(step: dict[str, Any], action: dict[str, Any]) -> str:
    if _is_background_action(action):
        return 'background'
    return 'background' if _can_background_override(action) and str(step.get('placement') or '') == 'background' else 'foreground'


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


def _normalize_modifiers(raw: Any) -> dict[str, float]:
    source = raw if isinstance(raw, dict) else {}
    return {
        key: max(-5.0, min(10.0, _num(source.get(key))))
        for key in MODIFIER_KEYS
        if key in source and _num(source.get(key)) != 0
    }


def _normalize_buff_rules(raw: Any, team: list[dict[str, Any]], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    rules = raw if isinstance(raw, list) else []
    actions = get_record_map(catalog['actions'])
    valid_slots = {member['slot'] for member in team}
    normalized: list[dict[str, Any]] = []
    for index, rule in enumerate(rules[:MAX_BUFF_RULES]):
        if not isinstance(rule, dict):
            continue
        trigger = rule.get('trigger') if isinstance(rule.get('trigger'), dict) else {}
        targets = rule.get('targets') if isinstance(rule.get('targets'), dict) else {}
        trigger_action_id = str(trigger.get('action_id') or '')
        target_action_ids = [
            str(action_id)
            for action_id in (targets.get('action_ids') if isinstance(targets.get('action_ids'), list) else [])
            if str(action_id) in actions
        ]
        trigger_slot = trigger.get('slot')
        target_slots = [
            slot for slot in (max(0, min(3, _int(item))) for item in (targets.get('slots') if isinstance(targets.get('slots'), list) else []))
            if slot in valid_slots
        ]
        normalized.append({
            'id': str(rule.get('id') or f'buff_{index + 1:03d}')[:40],
            'name': _clean_text(rule.get('name') or f'增益 {index + 1}', 60),
            'trigger': {
                'slot': max(0, min(3, _int(trigger_slot))) if trigger_slot not in (None, '') else None,
                'action_id': trigger_action_id if trigger_action_id in actions else '',
                'action_type': _clean_text(trigger.get('action_type'), 24),
            },
            'targets': {
                'slots': sorted(set(target_slots)),
                'action_ids': target_action_ids,
                'action_types': [
                    _clean_text(item, 24)
                    for item in (targets.get('action_types') if isinstance(targets.get('action_types'), list) else [])
                    if _clean_text(item, 24)
                ],
            },
            'delay_ticks': max(0, min(600, _int(rule.get('delay_ticks')))),
            'duration_ticks': max(0, min(6000, _int(rule.get('duration_ticks'), 100))),
            'modifiers': _normalize_modifiers(rule.get('modifiers')),
        })
    return [rule for rule in normalized if rule['duration_ticks'] > 0 and rule['modifiers']]


def _validate_step_team_actions(team: list[dict[str, Any]], steps: list[dict[str, Any]], catalog: dict[str, Any]) -> None:
    actions = get_record_map(catalog['actions'])
    character_by_slot = {member['slot']: member['character_id'] for member in team}
    for step in steps:
        if _int(step.get('slot')) not in character_by_slot:
            raise RuleValidationError('轴中存在不在队伍中的角色位置。')
        action = actions.get(str(step.get('action_id') or '')) or {}
        if str(action.get('character_id') or '') != character_by_slot[_int(step.get('slot'))]:
            raise RuleValidationError('轴中存在与角色不匹配的动作。')


def normalize_axis_payload(payload: dict[str, Any]) -> dict[str, Any]:
    catalog = load_shaft_catalog()
    body = _axis_body(payload)
    team = _normalize_team(body.get('team'), catalog)
    character_builds = _normalize_character_builds(body.get('character_builds'), team, catalog)
    team = _apply_character_builds_to_team(team, character_builds)
    steps = _normalize_steps(body.get('steps'), catalog)
    _validate_step_team_actions(team, steps, catalog)
    axis_payload = {
        'team': team,
        'character_builds': character_builds,
        'steps': steps,
        'enemy': _normalize_enemy(body.get('enemy'), catalog),
        'team_panel_bonus': _normalize_team_panel_bonus(body.get('team_panel_bonus'), catalog),
        'options': _normalize_options(body.get('options'), catalog),
        'duration_ticks': _axis_duration_ticks(steps, catalog),
        'initial_energy': max(0, min(1000, _num(body.get('initial_energy'), 100))),
        'buff_rules': _normalize_buff_rules(body.get('buff_rules'), team, catalog),
    }
    return axis_payload


def get_shaft_catalog_payload() -> dict[str, Any]:
    catalog = load_shaft_catalog()
    return {
        'characters': catalog['characters'],
        'actions': catalog['actions'],
        'actions_by_character': catalog['actions_by_character'],
        'arcs': catalog['arcs'],
        'buffs': catalog['buffs'],
        'cartridges': catalog['cartridges'],
        'formula_constants': catalog['formula_constants'],
        'source_meta': catalog['source_meta'],
        'starter_axis': catalog['starter_axis'],
    }


def simulate_shaft_axis(payload: dict[str, Any]) -> dict[str, Any]:
    axis_payload = normalize_axis_payload(payload)
    result = simulate_axis(axis_payload)
    return {
        'axis': axis_payload,
        'result': result,
    }


def _refresh_axis_character_index(axis: ShaftAxis, team: list[dict[str, Any]]) -> None:
    ShaftAxisCharacter.delete().where(ShaftAxisCharacter.axis == axis).execute()
    for member in team:
        ShaftAxisCharacter.create(
            axis=axis,
            character_id=str(member.get('character_id') or ''),
            slot=_int(member.get('slot')),
        )


def _axis_query_for_player(axis_id: int, player: Player) -> ShaftAxis | None:
    return ShaftAxis.select().where(
        (ShaftAxis.id == axis_id) &
        (ShaftAxis.owner == player)
    ).first()


def _visible_axis(axis_id: int, player: Player | None = None) -> ShaftAxis:
    axis = ShaftAxis.select(ShaftAxis, Player).join(Player).where(ShaftAxis.id == axis_id).first()
    if axis is None:
        raise RuleValidationError('排轴不存在。')
    if axis.visibility != 'public' and (player is None or axis.owner_id != player.id):
        raise RuleValidationError('没有查看这个排轴的权限。')
    return axis


def _is_liked(axis: ShaftAxis, player: Player | None) -> bool:
    if player is None:
        return False
    return ShaftAxisLike.select().where(
        (ShaftAxisLike.axis == axis) &
        (ShaftAxisLike.player == player)
    ).exists()


def _favorite_query(axis: ShaftAxis, player: Player | None, visitor_key: str):
    if player is not None:
        return ShaftAxisFavorite.select().where(
            (ShaftAxisFavorite.axis == axis) &
            (ShaftAxisFavorite.player == player)
        )
    return ShaftAxisFavorite.select().where(
        (ShaftAxisFavorite.axis == axis) &
        (ShaftAxisFavorite.player.is_null(True)) &
        (ShaftAxisFavorite.visitor_key == visitor_key)
    )


def _is_favorited(axis: ShaftAxis, player: Player | None, visitor_key: str) -> bool:
    visitor_key = _clean_visitor_key(visitor_key)
    if player is None and not visitor_key:
        return False
    return _favorite_query(axis, player, visitor_key).exists()


def _clean_visitor_key(value: Any) -> str:
    key = re.sub(r'[^a-zA-Z0-9_.:-]+', '', str(value or '').strip())
    return key[:96]


def _enrich_team(team: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog = load_shaft_catalog()
    characters = get_record_map(catalog['characters'])
    arcs = get_record_map(catalog['arcs'])
    cartridges = get_record_map(catalog['cartridges'])
    enriched = []
    for member in team:
        item = dict(member)
        character = characters.get(str(item.get('character_id') or '')) or {}
        arc = arcs.get(str(item.get('arc_id') or '')) or {}
        cartridge = cartridges.get(str(item.get('cartridge_id') or '')) or {}
        item['character_name'] = character.get('name') or item.get('character_name') or ''
        item['character_avatar'] = character.get('avatar') or ''
        item['character_element'] = character.get('element') or ''
        item['arc_name'] = arc.get('name') or item.get('arc_name') or ''
        item['cartridge_name'] = cartridge.get('name') or item.get('cartridge_name') or ''
        enriched.append(item)
    return enriched


def serialize_shaft_axis(
    axis: ShaftAxis,
    *,
    include_axis: bool = False,
    player: Player | None = None,
    visitor_key: str = '',
) -> dict[str, Any]:
    team = _safe_json_loads(axis.team_json, [])
    result = _safe_json_loads(axis.result_json, {})
    payload = {
        'id': axis.id,
        'title': axis.title,
        'description': axis.description,
        'visibility': axis.visibility,
        'owner': {
            'player_uid': axis.owner.player_uid,
            'nickname': axis.owner.nickname or axis.owner.player_uid,
        },
        'team': _enrich_team(team if isinstance(team, list) else []),
        'enemy': _safe_json_loads(axis.enemy_json, {}),
        'summary': result.get('summary') if isinstance(result, dict) else {},
        'duration_ticks': axis.duration_ticks,
        'direct_damage': axis.direct_damage,
        'stagger_damage': axis.stagger_damage,
        'total_damage': axis.total_damage,
        'dps': axis.dps_x100 / 100,
        'like_count': axis.like_count,
        'favorite_count': axis.favorite_count,
        'liked': _is_liked(axis, player),
        'favorited': _is_favorited(axis, player, visitor_key),
        'dedupe_hash': axis.dedupe_hash,
        'source_version': axis.source_version,
        'created_at': axis.created_at.isoformat(),
        'updated_at': axis.updated_at.isoformat(),
        'published_at': axis.published_at.isoformat() if axis.published_at else '',
    }
    if include_axis:
        payload['axis'] = _safe_json_loads(axis.axis_json, {})
        payload['result'] = result
    return payload


def save_shaft_axis(player: Player, payload: dict[str, Any], axis_id: int | None = None) -> dict[str, Any]:
    visibility = str(payload.get('visibility') or ('public' if payload.get('publish') else 'private')).strip().lower()
    if visibility not in VISIBILITIES:
        raise RuleValidationError('未知的发布状态。')
    axis_payload = normalize_axis_payload(payload)
    result = simulate_axis(axis_payload)
    axis_payload['enemy'] = result['enemy']
    axis_payload['duration_ticks'] = _int(result['summary'].get('duration_ticks'), axis_payload['duration_ticks'])
    dedupe_hash = calculate_axis_hash(axis_payload)
    now = datetime.utcnow()
    source_meta = load_shaft_catalog()['source_meta']
    summary = result['summary']
    title = _clean_text(payload.get('title') or '未命名排轴', MAX_AXIS_TITLE_LENGTH) or '未命名排轴'
    description = _clean_text(payload.get('description'), MAX_AXIS_DESCRIPTION_LENGTH)

    with atomic_transaction():
        record: ShaftAxis | None = None
        if axis_id is not None:
            record = _axis_query_for_player(axis_id, player)
            if record is None:
                raise RuleValidationError('没有保存这个排轴的权限。')
        if visibility == 'public':
            duplicate_query = ShaftAxis.select().where(
                (ShaftAxis.visibility == 'public') &
                (ShaftAxis.dedupe_hash == dedupe_hash)
            )
            if record is not None:
                duplicate_query = duplicate_query.where(ShaftAxis.id != record.id)
            if duplicate_query.exists():
                raise RuleValidationError('市场中已经存在相同角色、弧盘、卡带与动作轴的排轴。')
        if record is None:
            record = ShaftAxis.create(owner=player, created_at=now)
        record.title = title
        record.description = description
        record.visibility = visibility
        record.source_version = str(source_meta.get('version_label') or source_meta.get('source_hash') or '')
        record.team_json = _json_dumps(axis_payload['team'])
        record.axis_json = _json_dumps(axis_payload)
        record.enemy_json = _json_dumps(axis_payload['enemy'])
        record.result_json = _json_dumps(result)
        record.duration_ticks = _int(summary.get('duration_ticks'))
        record.direct_damage = _int(summary.get('direct_damage'))
        record.stagger_damage = _int(summary.get('stagger_damage'))
        record.total_damage = _int(summary.get('total_damage'))
        record.dps_x100 = _int(_num(summary.get('dps')) * 100)
        record.dedupe_hash = dedupe_hash
        record.updated_at = now
        record.published_at = now if visibility == 'public' else None
        record.save()
        _refresh_axis_character_index(record, axis_payload['team'])

    logger.info('save_shaft_axis player_uid=%s axis_id=%s visibility=%s', player.player_uid, record.id, visibility)
    return serialize_shaft_axis(record, include_axis=True, player=player)


def get_shaft_axis(axis_id: int, player: Player | None = None, visitor_key: str = '') -> dict[str, Any]:
    axis = _visible_axis(axis_id, player)
    return serialize_shaft_axis(axis, include_axis=True, player=player, visitor_key=visitor_key)


def delete_shaft_axis(player: Player, axis_id: int) -> dict[str, Any]:
    with atomic_transaction():
        axis = _axis_query_for_player(axis_id, player)
        if axis is None:
            raise RuleValidationError('没有删除这个排轴的权限。')
        axis.delete_instance(recursive=True)
    logger.info('delete_shaft_axis player_uid=%s axis_id=%s', player.player_uid, axis_id)
    return {'ok': True}


def list_shaft_market(
    *,
    character_id: str = '',
    sort: str = 'dps',
    page: int = 1,
    page_size: int = 20,
    player: Player | None = None,
    visitor_key: str = '',
) -> dict[str, Any]:
    page = max(1, min(200, page))
    page_size = max(1, min(60, page_size))
    sort = sort if sort in MARKET_SORTS else 'dps'
    query = ShaftAxis.select(ShaftAxis, Player).join(Player).where(ShaftAxis.visibility == 'public')
    if character_id:
        subquery = ShaftAxisCharacter.select(ShaftAxisCharacter.axis).where(
            ShaftAxisCharacter.character_id == character_id
        )
        query = query.where(ShaftAxis.id.in_(subquery))
    if sort == 'likes':
        query = query.order_by(ShaftAxis.like_count.desc(), ShaftAxis.dps_x100.desc(), ShaftAxis.updated_at.desc())
    elif sort == 'favorites':
        query = query.order_by(ShaftAxis.favorite_count.desc(), ShaftAxis.dps_x100.desc(), ShaftAxis.updated_at.desc())
    elif sort == 'new':
        query = query.order_by(ShaftAxis.published_at.desc(), ShaftAxis.updated_at.desc())
    else:
        query = query.order_by(ShaftAxis.dps_x100.desc(), ShaftAxis.like_count.desc(), ShaftAxis.updated_at.desc())
    items = list(query.paginate(page, page_size + 1))
    visible_items = items[:page_size]
    return {
        'items': [
            serialize_shaft_axis(axis, include_axis=False, player=player, visitor_key=visitor_key)
            for axis in visible_items
        ],
        'page': page,
        'page_size': page_size,
        'has_more': len(items) > page_size,
    }


def list_my_shaft_axes(player: Player) -> dict[str, Any]:
    axes = list(
        ShaftAxis
        .select(ShaftAxis, Player)
        .join(Player)
        .where(ShaftAxis.owner == player)
        .order_by(ShaftAxis.updated_at.desc())
        .limit(100)
    )
    return {
        'items': [serialize_shaft_axis(axis, include_axis=False, player=player) for axis in axes],
    }


def set_shaft_axis_like(player: Player, axis_id: int, liked: bool) -> dict[str, Any]:
    with atomic_transaction():
        axis = _visible_axis(axis_id, player)
        if axis.visibility != 'public':
            raise RuleValidationError('只能点赞公开排轴。')
        existing = ShaftAxisLike.select().where(
            (ShaftAxisLike.axis == axis) &
            (ShaftAxisLike.player == player)
        ).first()
        if liked and existing is None:
            ShaftAxisLike.create(axis=axis, player=player)
            axis.like_count += 1
            axis.save()
        elif not liked and existing is not None:
            existing.delete_instance()
            axis.like_count = max(0, axis.like_count - 1)
            axis.save()
    return serialize_shaft_axis(axis, include_axis=False, player=player)


def set_shaft_axis_favorite(
    *,
    axis_id: int,
    favorited: bool,
    player: Player | None = None,
    visitor_key: str = '',
) -> dict[str, Any]:
    visitor_key = _clean_visitor_key(visitor_key)
    if player is None and not visitor_key:
        raise RuleValidationError('缺少收藏标识。')
    with atomic_transaction():
        axis = _visible_axis(axis_id, player)
        if axis.visibility != 'public':
            raise RuleValidationError('只能收藏公开排轴。')
        existing = _favorite_query(axis, player, visitor_key).first()
        if favorited and existing is None:
            ShaftAxisFavorite.create(
                axis=axis,
                player=player,
                visitor_key='' if player is not None else visitor_key,
            )
            axis.favorite_count += 1
            axis.save()
        elif not favorited and existing is not None:
            existing.delete_instance()
            axis.favorite_count = max(0, axis.favorite_count - 1)
            axis.save()
    return serialize_shaft_axis(axis, include_axis=False, player=player, visitor_key=visitor_key)


def optional_player_from_token(token: str) -> Player | None:
    from app.dao import get_player_by_token

    return get_player_by_token(token)
