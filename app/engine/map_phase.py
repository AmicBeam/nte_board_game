from __future__ import annotations

from copy import deepcopy

from app.engine.event_context import JsonDict

ACTION_QUEUE_KEY = '_action_queue'
LOG_LIMIT = 18
DEFAULT_PHASE_SIZE = 50
DEFAULT_MAX_PHASE = 4
MAP_PHASE_ICON = '/static/images/monster/compass.svg'


def initialize_map_phase(game_map: JsonDict) -> JsonDict | None:
    phase_state = game_map.get('map_phase')
    if not isinstance(phase_state, dict):
        return None
    phase_state.setdefault('name', '地图阶段')
    phase_state.setdefault('current', 0)
    phase_state.setdefault('progress', 0)
    phase_state.setdefault('phase_size', DEFAULT_PHASE_SIZE)
    phase_state.setdefault('progress_per_turn', 1)
    phase_state.setdefault('safe_progress', 0)
    phase_state.setdefault('large_safe_progress', 0)
    phase_state.setdefault('max_phase', DEFAULT_MAX_PHASE)
    phase_state.setdefault('spawned_phases', [])
    phase_state['current'] = _bounded_phase(phase_state.get('current', 0), phase_state)
    phase_state['progress'] = max(0, int(phase_state.get('progress', 0) or 0))
    phase_state['spawned_phases'] = sorted({
        _bounded_phase(phase, phase_state)
        for phase in phase_state.get('spawned_phases', [])
        if int(phase or 0) > 0
    })
    return phase_state


def advance_map_phase_for_turn(state: JsonDict) -> None:
    phase_state = initialize_map_phase(state.get('map', {}))
    if phase_state is None:
        return
    advance_map_phase(
        state,
        int(phase_state.get('progress_per_turn', 1) or 0),
        reason='turn',
    )


def advance_map_phase_for_safe(state: JsonDict, object_id: object) -> None:
    phase_state = initialize_map_phase(state.get('map', {}))
    if phase_state is None:
        return
    object_key = str(object_id or '')
    amount_key = 'large_safe_progress' if object_key == 'large_safe' else 'safe_progress'
    advance_map_phase(
        state,
        int(phase_state.get(amount_key, 0) or 0),
        reason='safe',
    )


def advance_map_phase(state: JsonDict, amount: int, *, reason: str) -> None:
    phase_state = initialize_map_phase(state.get('map', {}))
    if phase_state is None or amount <= 0:
        return
    old_phase = int(phase_state.get('current', 0) or 0)
    phase_size = max(1, int(phase_state.get('phase_size', DEFAULT_PHASE_SIZE) or DEFAULT_PHASE_SIZE))
    max_phase = _max_phase(phase_state)
    phase_state['progress'] = min(
        max_phase * phase_size,
        max(0, int(phase_state.get('progress', 0) or 0)) + int(amount),
    )
    target_phase = min(max_phase, max(old_phase, phase_state['progress'] // phase_size))
    if target_phase <= old_phase:
        return

    for phase in range(old_phase + 1, target_phase + 1):
        phase_state['current'] = phase
        spawned_count = _spawn_phase_enemies(state, phase)
        phase_name = _phase_name(phase_state, phase)
        suffix = f'，增援 {spawned_count} 名敌人' if spawned_count else ''
        _add_log(state, f'地图阶段提升至 {phase}：{phase_name}{suffix}。')
        _add_action_step(state, {
            'type': 'popup',
            'icon': MAP_PHASE_ICON,
            'title': '地图阶段',
            'message': f'警戒提升至阶段 {phase}：{phase_name}{suffix}。',
        })


def _spawn_phase_enemies(state: JsonDict, phase: int) -> int:
    game_map = state.setdefault('map', {})
    phase_state = initialize_map_phase(game_map)
    if phase_state is None:
        return 0
    spawned_phases = set(int(item) for item in phase_state.get('spawned_phases', []))
    if phase in spawned_phases:
        return 0
    monsters = game_map.setdefault('monsters', [])
    existing_ids = {str(monster.get('id')) for monster in monsters}
    spawned_count = 0
    for spawn in game_map.get('phase_enemy_spawns', []):
        if int(spawn.get('phase', 0) or 0) != phase:
            continue
        monster = _build_phase_enemy(spawn)
        if not monster or str(monster.get('id')) in existing_ids:
            continue
        existing_ids.add(str(monster['id']))
        monsters.append(monster)
        spawned_count += 1
    phase_state['spawned_phases'] = sorted(spawned_phases | {phase})
    return spawned_count


def _build_phase_enemy(spawn: JsonDict) -> JsonDict:
    monster = deepcopy({
        key: value
        for key, value in spawn.items()
        if key not in {'phase'}
    })
    monster_id = str(monster.get('id') or '')
    if not monster_id:
        return {}
    monster.setdefault('definition_id', monster_id)
    monster.setdefault('name', monster_id)
    monster.setdefault('kind', 'monster')
    monster.setdefault('layer', 1)
    monster.setdefault('max_hp', monster.get('hp', 1))
    monster['max_hp'] = max(1, int(monster.get('max_hp', 1) or 1))
    monster['hp'] = monster['max_hp']
    monster['attack'] = max(0, int(monster.get('attack', 0) or 0))
    monster['defense'] = max(0, int(monster.get('defense', 0) or 0))
    monster['range'] = max(1, int(monster.get('range', 1) or 1))
    return monster


def _phase_name(phase_state: JsonDict, phase: int) -> str:
    names = phase_state.get('phase_names', {})
    if isinstance(names, dict):
        value = names.get(str(phase), names.get(phase))
        if value:
            return str(value)
    return f'阶段 {phase}'


def _bounded_phase(value: object, phase_state: JsonDict) -> int:
    return max(0, min(_max_phase(phase_state), int(value or 0)))


def _max_phase(phase_state: JsonDict) -> int:
    return max(0, int(phase_state.get('max_phase', DEFAULT_MAX_PHASE) or DEFAULT_MAX_PHASE))


def _add_log(state: JsonDict, message: str) -> None:
    state.setdefault('log', []).insert(0, message)
    del state['log'][LOG_LIMIT:]


def _add_action_step(state: JsonDict, step: JsonDict) -> None:
    state.setdefault(ACTION_QUEUE_KEY, []).append(step)
