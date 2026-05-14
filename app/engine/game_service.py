import random
from collections.abc import Callable
from copy import deepcopy

from app.config import DEFAULT_MAP_ID, MOVE_STEP_LIMIT
from app.content.loader import (
    get_character,
    get_item,
    get_map,
    get_map_object,
    get_map_object_tooltip,
    load_map_object_modules,
    load_characters,
    load_items,
    resolve_map_object_id,
)
from app.content.map_objects.common import choose_loot_from_table, choose_loot_table_entry
from app.dao import clear_run, get_build, get_current_room, get_run, list_room_members, update_room_status, upsert_build, upsert_run
from app.db import atomic_transaction
from app.engine.damage import PLAYER_TARGET_ID, build_damage_package, resolve_damage_package
from app.engine.enemy_drop import spawn_enemy_drop
from app.engine.effects import (
    build_runtime_effect,
    consume_runtime_effect_bonus,
    find_runtime_effect_by_source,
    register_runtime_effect,
    remove_runtime_effect_by_source,
    sum_runtime_effect_bonus,
)
from app.engine.event_bus import dispatch_event, run_phase_sequence
from app.engine.event_context import EventContext, EventHook, JsonDict
from app.engine.events import GameEvent, TURN_CLOSING_SEQUENCE, TURN_OPENING_SEQUENCE
from app.engine.identification import (
    identification_progress,
    initialize_identification_state,
    mark_battle_step,
    reset_turn_flags,
    settle_combo_for_turn,
)
from app.engine.runtime import (
    build_character_instance,
    build_item_instances,
    serialize_item_definition,
    serialize_item_instance,
)
from app.errors import RuleValidationError
from app.models import Player, Room
from app.utils.logger import get_logger

MAX_BUILD_ITEM_COUNT = 6
MAP_LOCKED_ITEM_IDS: tuple[str, ...] = ()
XIAOZHI_FONS_ATTACK_STEP = 1000
XIAOZHI_FONS_ATTACK_CAP = 5
MAMEN_FONS_DEFENSE_STEP = 10000
MAMEN_FONS_DAMAGE_TAX_PERCENT = 10
MIN_IDENTIFICATION_LEVEL = 1
MAX_IDENTIFICATION_LEVEL = 4
LOG_LIMIT = 18
DEFAULT_ROUTE_HINT = '搜刮办公室资源，找到传送门后进入 Boss 房间。'
ACTION_QUEUE_KEY = '_action_queue'
DIRECTIONS = {
    'up': (0, -1),
    'down': (0, 1),
    'left': (-1, 0),
    'right': (1, 0),
}
DIRECTION_LABELS = {
    'up': '上',
    'down': '下',
    'left': '左',
    'right': '右',
}
TURN_BELT_DIRECTIONS = {
    'turn_belt_up': 'up',
    'turn_belt_down': 'down',
    'turn_belt_left': 'left',
    'turn_belt_right': 'right',
}
IDENTIFICATION_OFFSETS = {
    1: ((0, -1), (-1, 0), (1, 0), (0, 1)),
    2: tuple(
        (dx, dy)
        for dy in range(-1, 2)
        for dx in range(-1, 2)
        if dx != 0 or dy != 0
    ),
    3: tuple(
        (dx, dy)
        for dy in range(-1, 2)
        for dx in range(-1, 2)
        if dx != 0 or dy != 0
    ) + ((0, -2), (-2, 0), (2, 0), (0, 2)),
    4: tuple(
        (dx, dy)
        for dy in range(-2, 3)
        for dx in range(-2, 3)
        if dx != 0 or dy != 0
    ),
}
ICONS = {
    'player': 'player',
    'monster': 'monster',
    'boss': 'boss',
    'turn_belt': 'turn_belt',
    'chest': 'chest',
    'portal': 'portal',
    'door': 'door',
    'wall': 'wall',
    'event': 'event',
    'boss_tile': 'boss',
}
MONSTER_KIND_ICONS = {
    'camera': '/static/images/monster/compass.svg',
    'boss': '/static/images/monster/mamen.webp',
}

logger = get_logger('nte.game_service')


def _monster_icon(monster: JsonDict) -> str:
    return str(
        monster.get('avatar_image')
        or monster.get('image')
        or MONSTER_KIND_ICONS.get(str(monster.get('id', '')))
        or MONSTER_KIND_ICONS.get(str(monster.get('kind', 'monster')), ICONS['monster'])
    )


def _boss_icon(boss: JsonDict) -> str:
    return str(
        boss.get('avatar_image')
        or boss.get('image')
        or MONSTER_KIND_ICONS.get(str(boss.get('id', '')))
        or MONSTER_KIND_ICONS.get(str(boss.get('kind', 'boss')), ICONS['boss'])
    )


def get_catalog_payload(player: Player) -> JsonDict:
    saved_build = get_build(player)
    catalog_item_ids = _catalog_visible_item_ids()
    return {
        'characters': [
            serialize_character_definition(character_definition)
            for character_definition in _selectable_characters()
        ],
        'items': [
            serialize_item_definition(item_definition)
            for item_definition in load_items()
            if not item_definition.get('hidden_from_build') or item_definition['id'] in catalog_item_ids
        ],
        'build_size': MAX_BUILD_ITEM_COUNT,
        'locked_item_ids': list(MAP_LOCKED_ITEM_IDS),
        'saved_build': normalize_build_payload(saved_build) if saved_build is not None else None,
    }


def get_encyclopedia_payload() -> JsonDict:
    game_map = deepcopy(get_map(DEFAULT_MAP_ID))
    _ensure(game_map is not None, '地图配置不存在。')
    map_object_ids = _collect_map_object_ids(game_map)
    map_object_modules = load_map_object_modules()
    map_objects = []
    for object_id in sorted(map_object_ids):
        definition = map_object_modules.get(object_id, {}).get('definition')
        if definition is None:
            continue
        sample_tile = next(
            (tile for tile in game_map.get('tiles', []) if resolve_map_object_id(tile) == object_id),
            {'type': object_id, 'object_id': object_id},
        )
        map_objects.append({
            'id': object_id,
            'name': _map_object_display_name(object_id),
            'icon': definition.get('icon', ICONS.get(object_id, 'event')),
            'description': get_map_object_tooltip(sample_tile),
            'block_type': definition.get('block_type', ''),
            'tags': map_object_tags(definition),
        })
    exclusive_item_ids = _exclusive_item_ids()
    codex_items = []
    loot_items = []
    for item in load_items():
        if item.get('type') in {'loot', 'key'}:
            loot_items.append(serialize_item_definition(item))
            continue
        if not _is_codex_item(item, exclusive_item_ids):
            continue
        serialized_item = serialize_item_definition(item)
        if item['id'] in exclusive_item_ids:
            _append_tag(serialized_item, '专属')
        codex_items.append(serialized_item)
    enemies = []
    seen_enemy_ids: set[str] = set()
    for monster in game_map.get('monsters', []):
        enemy_id = str(monster.get('definition_id') or monster.get('id') or monster.get('kind') or '')
        if enemy_id in seen_enemy_ids:
            continue
        seen_enemy_ids.add(enemy_id)
        enemies.append({
            'id': enemy_id,
            'name': monster['name'],
            'kind': monster.get('kind', 'monster'),
            'icon': _monster_icon(monster),
            'hp': monster.get('max_hp', monster.get('hp', 0)),
            'attack': monster.get('attack', 0),
            'defense': monster.get('defense', 0),
            'range': monster.get('range', 1),
            'description': f"HP {monster.get('max_hp', monster.get('hp', 0))} / 攻击 {monster.get('attack', 0)} / 防御 {monster.get('defense', 0)} / 射程 {monster.get('range', 1)}",
        })
    boss = game_map.get('boss', {})
    if boss:
        boss_description = f"HP {boss.get('max_hp', boss.get('hp', 0))} / 攻击 {boss.get('attack', 0)} / 防御 {boss.get('defense', 0)} / 射程 {boss.get('range', 1)}"
        if boss.get('id') == 'mamen':
            boss_description += '。玛门会被方斯刺激：玩家每持有 10000 方斯，玛门防御 -1，最低为 0；玛门造成伤害时会吞噬玩家当前 10% 方斯。'
        enemies.append({
            'id': boss.get('id', 'boss'),
            'name': boss.get('name', 'Boss'),
            'kind': 'boss',
            'icon': _boss_icon(boss),
            'hp': boss.get('max_hp', boss.get('hp', 0)),
            'attack': boss.get('attack', 0),
            'defense': boss.get('defense', 0),
            'range': boss.get('range', 1),
            'description': boss_description,
        })
    return {
        'map': {
            'id': game_map['id'],
            'name': game_map['name'],
            'total_layers': game_map.get('total_layers', 1),
        },
        'map_objects': map_objects,
        'items': codex_items,
        'loot_items': loot_items,
        'enemies': enemies,
    }


def _collect_map_object_ids(game_map: JsonDict) -> set[str]:
    map_object_ids: set[str] = set()
    for tile in game_map.get('tiles', []):
        _append_map_object_id(map_object_ids, tile)
    for entries in game_map.get('loot_tables', {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get('result'), dict):
                _append_map_object_id(map_object_ids, entry['result'])
    return map_object_ids


def _append_map_object_id(map_object_ids: set[str], tile: JsonDict) -> None:
    object_id = resolve_map_object_id(tile)
    if object_id and object_id not in {'floor', 'random', 'wall', 'boss_tile', 'access_card_spot'}:
        map_object_ids.add(object_id)


def _map_object_display_name(object_id: str) -> str:
    labels = {
        'door': '门',
        'hidden_door': '隐藏门',
        'keycard_door': '经理办公室暗门',
        'large_safe': '大型保险箱',
        'open_door': '已开启的门',
        'portal': '传送门',
        'safe': '保险箱',
    }
    return labels.get(object_id, object_id)


def serialize_character_definition(character_definition: JsonDict) -> JsonDict:
    return {
        'id': character_definition['id'],
        'name': character_definition['name'],
        'max_hp': character_definition['max_hp'],
        'attack': character_definition['attack'],
        'defense': character_definition['defense'],
        'identification_level': int(character_definition.get('identification_level', 1)),
        'passive': character_definition['passive'],
        'exclusive_item_ids': list(character_definition.get('exclusive_item_ids', [])),
        'portrait_image': character_definition.get('portrait_image', f"/static/images/characters/portrait/{character_definition['name']}.png"),
        'avatar_image': character_definition.get('avatar_image', f"/static/images/characters/avatar/{character_definition['name']}.png"),
    }


def save_build(player: Player, character_id: str, item_ids: list[str]) -> JsonDict | None:
    character_definition = get_character(character_id)
    _ensure(character_definition is not None, '角色不存在。')
    _ensure(_is_character_selectable(character_definition), '该角色暂不可在构筑中选择。')
    selectable_item_ids = _selectable_item_ids(character_definition, item_ids)
    _ensure(len(selectable_item_ids) <= MAX_BUILD_ITEM_COUNT, f'最多选择 {MAX_BUILD_ITEM_COUNT} 个道具。')
    for item_id in selectable_item_ids:
        item = get_item(item_id)
        _ensure(item is not None, f'未知道具：{item_id}')
        _ensure(not item.get('hidden_from_build'), f'该道具不可在构筑中选择：{item_id}')
    with atomic_transaction():
        upsert_build(player, character_id, selectable_item_ids)
    logger.info('save_build player_uid=%s character_id=%s', player.player_uid, character_id)
    return get_build(player)


def start_or_resume_run(player: Player) -> JsonDict:
    room = _require_room(player)
    return start_or_resume_run_for_room(room, player)


def start_or_resume_run_for_room(room: Room, player: Player) -> JsonDict:
    with atomic_transaction():
        room_members = list_room_members(room)
        _ensure(room_members, '房间内没有成员，无法开始对局。')
        builds_by_player_uid: dict[str, JsonDict] = {}
        for member in room_members:
            build = get_build(member.player)
            if build is None:
                raise RuleValidationError(f'玩家 {member.player.player_uid} 尚未完成构筑。')
            build = normalize_build_payload(build)
            builds_by_player_uid[member.player.player_uid] = build
        existing_run = get_run(room)
        if existing_run and existing_run['status'] in {'playing', 'victory', 'defeat'}:
            existing_run['snapshot'] = _normalize_loaded_state(existing_run['snapshot'])
            validate_state(existing_run['snapshot'])
            _persist_room_snapshot(room, existing_run['snapshot'])
            logger.info('resume_run room_code=%s player_uid=%s status=%s', room.room_code, player.player_uid, existing_run['status'])
            return serialize_snapshot(existing_run['snapshot'])
        state = create_initial_state(room, room_members, builds_by_player_uid, DEFAULT_MAP_ID)
        validate_state(state)
        _persist_room_snapshot(room, state)
    logger.info('start_new_run room_code=%s player_uid=%s', room.room_code, player.player_uid)
    return serialize_snapshot(state)


def normalize_build_payload(build: JsonDict) -> JsonDict:
    characters = _selectable_characters()
    default_character_id = characters[0]['id'] if characters else ''
    character_id = build.get('character_id')
    character_definition = get_character(str(character_id))
    if character_definition is None or not _is_character_selectable(character_definition):
        character_id = default_character_id
        character_definition = get_character(str(character_id))
    item_ids = _selectable_item_ids(character_definition, build.get('item_ids', []))[:MAX_BUILD_ITEM_COUNT]
    return {'character_id': character_id, 'item_ids': item_ids}


def _selectable_characters() -> list[JsonDict]:
    return [
        character_definition
        for character_definition in load_characters()
        if _is_character_selectable(character_definition)
    ]


def _is_character_selectable(character_definition: JsonDict | None) -> bool:
    return bool(character_definition) and not character_definition.get('hidden_from_build')


def _locked_item_ids_for_character(character_definition: JsonDict | None) -> list[str]:
    locked_ids = list(MAP_LOCKED_ITEM_IDS)
    locked_ids.extend((character_definition or {}).get('exclusive_item_ids', []))
    return list(dict.fromkeys(locked_ids))


def _exclusive_item_ids() -> set[str]:
    item_ids = set(MAP_LOCKED_ITEM_IDS)
    for character_definition in load_characters():
        item_ids.update(str(item_id) for item_id in character_definition.get('exclusive_item_ids', []))
    return item_ids


def _catalog_visible_item_ids() -> set[str]:
    return _exclusive_item_ids()


def _is_codex_item(item_definition: JsonDict, exclusive_item_ids: set[str]) -> bool:
    if item_definition.get('type') in {'loot', 'key'}:
        return False
    return not item_definition.get('hidden_from_build') or item_definition['id'] in exclusive_item_ids


def _append_tag(payload: JsonDict, tag: str) -> None:
    tags = [str(item) for item in payload.get('tags', []) if str(item)]
    if tag not in tags:
        tags.append(tag)
    payload['tags'] = tags


def _selectable_item_ids(character_definition: JsonDict | None, item_ids: list[str]) -> list[str]:
    locked_ids = set(_locked_item_ids_for_character(character_definition))
    return [
        str(item_id)
        for item_id in item_ids
        if str(item_id) not in locked_ids
        and (item := get_item(str(item_id))) is not None
        and not item.get('hidden_from_build')
    ]


def get_run_state(player: Player) -> JsonDict | None:
    room = get_current_room(player)
    if room is None:
        return None
    return get_run_state_for_room(room, player)


def get_run_state_for_room(room: Room, player: Player | None = None) -> JsonDict | None:
    run = get_run(room)
    if run is None:
        return None
    run['snapshot'] = _normalize_loaded_state(run['snapshot'])
    if player is not None and player.player_uid in run['snapshot']['players']:
        _project_player_scope(run['snapshot'], player.player_uid)
    validate_state(run['snapshot'])
    return serialize_snapshot(run['snapshot'])


def reset_run(player: Player) -> None:
    room = _require_room(player)
    reset_run_for_room(room)


def reset_run_for_room(room: Room) -> None:
    with atomic_transaction():
        clear_run(room)
        update_room_status(room, 'ready' if room.mode == 'solo' else 'waiting')
    logger.info('reset_run room_code=%s', room.room_code)


def roll_dice(player: Player) -> JsonDict:
    with atomic_transaction():
        state = _load_state(player)
        _ensure(state['phase'] != 'dice', '骰子现在会在回合开始时自动结算。')
        return _save_and_serialize(player, state)


def play_item(player: Player, item_instance_id: str, declared_value: int | None = None) -> JsonDict:
    with atomic_transaction():
        state = _load_state(player)
        begin_action_queue(state)
        state['_declared_item_value'] = declared_value
        _ensure(state['phase'] == 'action', '当前不是行动阶段。')
        _ensure(not state['has_played_item'], '每回合只能使用 1 个道具。')
        item_instance = _find_item_instance(state['hand'], item_instance_id)
        _ensure(item_instance is not None, '该道具实例不在手牌中。')
        item = get_item(item_instance['definition_id'])
        _ensure(item is not None, '道具定义不存在。')
        _ensure(can_play_item_now(state, item), '该道具当前不能主动使用。')
        event_payload = {
            'item_id': item['id'],
            'item_name': item['name'],
            'item_instance_id': item_instance_id,
            'target_instance_id': item_instance_id,
            'declared_value': state.get('_declared_item_value'),
            'resolved': False,
        }

        if item.get('consume_on_play', True):
            if item.get('stackable') and int(item_instance.get('quantity', 1)) > 1:
                item_instance['quantity'] = int(item_instance.get('quantity', 1)) - 1
            else:
                _remove_item_instance(state['hand'], item_instance_id)
                state['discard_pile'].append(item_instance)
                _set_item_zone(state, item_instance, 'discard_pile', reason='play_item')
        state['has_played_item'] = True
        result_payload = dispatch_event(state, GameEvent.ITEM_PLAYED, event_payload)
        state.pop('_declared_item_value', None)
        _ensure(result_payload.get('resolved') is True, '该道具未声明可执行的事件效果。')
        return _save_and_serialize(player, state)


def move_player(player: Player, direction: str, path: list[str] | None = None) -> JsonDict:
    with atomic_transaction():
        state = _load_state(player)
        begin_action_queue(state)
        _ensure(state['phase'] in {'action', 'movement'}, '当前不能移动。')
        dice_values = pending_dice_values(state)
        _ensure(dice_values is not None, '请先掷骰。')
        path_directions = [str(item) for item in (path or [])]
        if path_directions:
            _ensure(all(item in DIRECTIONS for item in path_directions), '路径方向非法。')
            _ensure(_direction_turn_count(path_directions) <= 1, '移动路径最多只能转弯一次。')
            direction = path_directions[0]
        _ensure(direction in DIRECTIONS, '方向非法。')

        actor = state['player']
        move_bonus = sum_runtime_effect_bonus(state, 'move_bonus')
        move_bonus += consume_runtime_effect_bonus(state, 'stored_next_turn_move', 'consume_on_move')
        limit_a = max(0, int(dice_values[0]) + move_bonus)
        limit_b = max(0, int(dice_values[1]) + move_bonus)
        path_steps = len(path_directions) if path_directions else max(limit_a, limit_b)
        if path_directions:
            horizontal_steps, vertical_steps = _path_axis_steps(path_directions)
            _ensure(
                _axis_steps_within_dice_limits(horizontal_steps, vertical_steps, limit_a, limit_b),
                '目标超过当前骰子范围。',
            )
        move_phase_payload = dispatch_event(
            state,
            GameEvent.MOVE_PHASE_BEGIN,
            {
                'direction': direction,
                'steps': path_steps,
                'dice': {'a': int(dice_values[0]), 'b': int(dice_values[1])},
                'axis_limits': {'a': limit_a, 'b': limit_b},
            },
            default_handler=build_scoped_default_handler(state, _default_move_phase_begin),
        )
        steps_remaining = max(0, int(move_phase_payload.get('steps', path_steps)))
        if path_directions:
            _ensure(len(path_directions) <= steps_remaining, '目标超过当前骰子范围。')
            steps_remaining = len(path_directions)
        active_direction = str(move_phase_payload.get('direction', direction))
        active_direction = resolve_start_tile_redirect(state, active_direction, steps_remaining)
        loop_counter = 0
        path_index = 0

        while steps_remaining > 0:
            loop_counter += 1
            if loop_counter > MOVE_STEP_LIMIT:
                add_log(state, '移动循环达到安全上限，已强制终止本次移动。')
                logger.error('move loop exceeded limit player_uid=%s', player.player_uid)
                break
            if path_directions:
                if path_index >= len(path_directions):
                    break
                active_direction = path_directions[path_index]
            next_x, next_y = step_position(actor['x'], actor['y'], active_direction)
            block_reason = get_block_reason(state, next_x, next_y)
            if block_reason:
                add_log(state, f'移动停止：{block_reason}')
                break
            actor['x'], actor['y'] = next_x, next_y
            steps_remaining -= 1
            path_index += 1
            add_log(state, f"移动至 ({actor['x']}, {actor['y']})。")
            add_action_step(state, {
                'type': 'move',
                'x': actor['x'],
                'y': actor['y'],
                'layer': current_map_layer(state),
                'direction': active_direction,
            })
            # 每前进一步都派发一次事件，供“经过某格”“移动若干步后生效”等效果监听。
            dispatch_event(state, GameEvent.MOVE_STEP, {
                'x': actor['x'],
                'y': actor['y'],
                'direction': active_direction,
                'steps_remaining': steps_remaining,
            })
            active_direction, intercepted = resolve_tile_entry(state, active_direction, steps_remaining)
            if intercepted:
                add_log(state, '移动被当前格子拦截，剩余步数已结束。')
                break

        identify_tiles_in_range(state, source='move_stop', show_effect=True)
        state['phase'] = 'battle'
        resolve_battle(state)
        if state['status'] == 'playing':
            _finish_player_turn(state)
        return _save_and_serialize(player, state)


def create_initial_state(
    room: Room,
    room_members: list[object],
    builds_by_player_uid: dict[str, JsonDict],
    map_id: str,
) -> JsonDict:
    game_map = deepcopy(get_map(map_id))
    _ensure(game_map is not None, '初始化配置失败。')
    entry = map_entry_point(game_map)
    game_map['current_layer'] = int(entry.get('layer', game_map.get('current_layer', 1)))
    _materialize_random_tiles(game_map)
    member_order = [member.player.player_uid for member in room_members]
    _ensure(member_order, '初始化配置失败。')
    players: dict[str, JsonDict] = {}
    for member in room_members:
        build = builds_by_player_uid[member.player.player_uid]
        character_definition = deepcopy(get_character(build['character_id']))
        _ensure(character_definition is not None, '初始化配置失败。')
        initial_item_ids = _locked_item_ids_for_character(character_definition) + build['item_ids']
        item_instances = build_item_instances(list(dict.fromkeys(initial_item_ids)), turn=1)
        for item_instance in item_instances:
            if item_instance['definition_id'] == 'fons':
                item_instance['amount'] = 0
        character_instance = build_character_instance(character_definition)
        players[member.player.player_uid] = {
            'profile': {
                'player_uid': member.player.player_uid,
                'nickname': member.player.nickname or member.player.player_uid,
                'seat': member.seat,
                'is_host': member.is_host,
            },
            'character_instance': character_instance,
            'player': {
                'x': entry['x'],
                'y': entry['y'],
                'max_hp': character_instance['max_hp'],
                'hp': character_instance['max_hp'],
                'attack': character_instance['attack'],
                'defense': character_instance['defense'],
                'identification_level': int(character_instance.get('identification_level', 1)),
                'identification_exp_units': 0,
                'identification_combo': 0,
                'identification_identified_this_turn': False,
                'identification_battled_this_turn': False,
                'safe_bonus_rolls': 0,
                'keys': 0,
                'keycards': 0,
                'fons_amount': 0,
            },
            'discard_pile': [],
            'hand': item_instances,
            'active_effects': [],
            'pending_die': None,
            'pending_dice': None,
            'phase': 'dice',
            'has_played_item': False,
            'route_hint': DEFAULT_ROUTE_HINT,
            'acted_this_turn': False,
            'defeated': False,
        }
    state = {
        'turn': 1,
        'status': 'playing',
        'room': {
            'room_code': room.room_code,
            'mode': room.mode,
            'member_order': member_order,
        },
        'players': players,
        'current_actor_uid': member_order[0],
        'map': game_map,
        'log': [],
    }
    _project_player_scope(state, member_order[0])
    _initialize_item_zones(state, emit_initial_events=True)
    add_log(state, _build_start_log(state))
    _start_shared_turn(state, reason='start_game')
    return state


def serialize_snapshot(state: JsonDict) -> JsonDict:
    _project_player_scope(state, str(state['current_actor_uid']))
    payload = deepcopy(state)
    current_width, current_height = current_map_dimensions(state)
    payload['map']['width'] = current_width
    payload['map']['height'] = current_height
    current_profile = payload['players'][payload['current_actor_uid']]['profile']
    payload['computed_stats'] = {
        'attack': current_attack(state),
        'defense': current_defense(state),
        'identification_level': current_identification_level(state),
    }
    payload['identification_progress'] = identification_progress(state['player'])
    payload['identification_range'] = identification_range_cells(state)
    if not payload.get('map', {}).get('hidden_room_revealed'):
        for tile in payload.get('map', {}).get('tiles', []):
            if tile.get('hidden_zone') and tile.get('object_id') != 'hidden_door':
                tile['display_type'] = 'floor'
        payload['map']['monsters'] = [
            monster
            for monster in payload.get('map', {}).get('monsters', [])
            if not monster.get('hidden_zone')
        ]
        boss_payload = payload.get('map', {}).get('boss')
        if isinstance(boss_payload, dict):
            boss_payload['positions'] = [
                position
                for position in boss_payload.get('positions', [])
                if not position.get('hidden_zone')
            ]
    payload['board'] = build_board_overlay(state)
    payload['available_directions'] = list(DIRECTIONS.keys())
    payload['hand_details'] = [
        item
        for item in (serialize_hand_item_instance(state, item_instance) for item_instance in state['hand'])
        if item is not None
    ]
    payload['players_overview'] = [_serialize_player_overview(player_scope) for player_scope in state['players'].values()]
    payload['current_viewer'] = {
        'player_uid': current_profile['player_uid'],
        'nickname': current_profile['nickname'],
        'seat': current_profile['seat'],
    }
    payload['turn_progress'] = {
        'turn': payload['turn'],
        'acted_player_uids': [
            player_scope['profile']['player_uid']
            for player_scope in payload['players'].values()
            if player_scope.get('acted_this_turn', False)
        ],
        'alive_player_uids': [
            player_scope['profile']['player_uid']
            for player_scope in payload['players'].values()
            if player_scope['player']['hp'] > 0 and not player_scope.get('defeated', False)
        ],
    }
    return payload


def _materialize_random_tiles(game_map: JsonDict) -> None:
    materialized_tiles = []
    random_index = 0
    for tile in game_map.get('tiles', []):
        if tile.get('type') != 'random':
            materialized_tiles.append(tile)
            continue
        random_index += 1
        if random.random() > float(tile.get('chance', 1)):
            continue
        result_tile = _build_random_tile_result(game_map, tile, random_index)
        if result_tile is not None:
            normalize_tile_footprint(result_tile)
            materialized_tiles.append(result_tile)
    game_map['tiles'] = materialized_tiles


def normalize_tile_footprint(tile: JsonDict) -> None:
    object_id = resolve_map_object_id(tile)
    if object_id == 'large_safe':
        tile.setdefault('width', 2)
        tile.setdefault('height', 2)
    tile['width'] = max(1, int(tile.get('width', 1) or 1))
    tile['height'] = max(1, int(tile.get('height', 1) or 1))


def _build_random_tile_result(game_map: JsonDict, tile: JsonDict, random_index: int) -> JsonDict | None:
    entry = choose_loot_table_entry(game_map, tile.get('loot_table_id'))
    if entry is None:
        return None
    if entry.get('result') is not None:
        result = deepcopy(entry['result'])
        if result.get('type') == 'floor':
            return None
    else:
        loot = entry.get('loot')
        if loot is None:
            return None
        result = {
            'type': 'loot_item',
            'object_id': 'loot_item',
            'loot': loot,
        }
    result['layer'] = int(tile.get('layer', 1))
    result['x'] = int(tile['x'])
    result['y'] = int(tile['y'])
    result.setdefault('object_id', result.get('type'))
    result.setdefault('spawn_id', f"random_{random_index}")
    if tile.get('hidden_zone') and not result.get('hidden_zone'):
        result['hidden_zone'] = tile['hidden_zone']
    return result


def serialize_hand_item_instance(state: JsonDict, item_instance: JsonDict) -> JsonDict | None:
    item_payload = serialize_item_instance(item_instance)
    if item_payload is None:
        return None
    item_payload['can_play_this_turn'] = can_play_item_now(state, item_payload)
    return item_payload


def can_play_item_now(state: JsonDict, item_definition: JsonDict) -> bool:
    return (
        state.get('phase') == 'action'
        and state.get('has_played_item') is False
        and bool(item_definition.get('can_play', True))
        and int(item_definition.get('cooldown_until_turn', 0) or 0) <= int(state.get('turn', 1))
    )


def _load_state(player: Player) -> JsonDict:
    room = _require_room(player)
    run = get_run(room)
    if run is None or not run['snapshot']:
        raise RuleValidationError('当前没有进行中的对局，请先开始。')
    run['snapshot'] = _normalize_loaded_state(run['snapshot'])
    _project_player_scope(run['snapshot'], player.player_uid)
    validate_state(run['snapshot'])
    return run['snapshot']


def _save_and_serialize(player: Player, state: JsonDict) -> JsonDict:
    room = _require_room(player)
    action_queue = take_action_queue(state)
    payload = _save_and_serialize_for_room(room, state)
    payload['action_queue'] = action_queue
    return payload


def _save_and_serialize_for_room(room: Room, state: JsonDict) -> JsonDict:
    _capture_player_scope(state)
    validate_state(state)
    _persist_room_snapshot(room, state)
    return serialize_snapshot(state)


def validate_state(state: JsonDict) -> None:
    required_top_keys = {'turn', 'status', 'room', 'players', 'current_actor_uid', 'phase', 'character_instance', 'player', 'map', 'discard_pile', 'hand', 'active_effects', 'pending_die', 'pending_dice', 'has_played_item', 'route_hint', 'log'}
    missing = required_top_keys - set(state.keys())
    _ensure(not missing, f'状态缺少关键字段：{sorted(missing)}')
    _ensure(state['phase'] in {'dice', 'action', 'movement', 'battle', 'victory', 'defeat', 'completed'}, '状态中的 phase 非法。')
    _ensure(state['current_actor_uid'] in state['players'], '当前行动玩家不存在。')
    _ensure(state['player']['hp'] <= state['player']['max_hp'], '玩家生命值超过上限。')
    all_instances = []
    for player_scope in state['players'].values():
        _ensure(get_character(player_scope['character_instance']['definition_id']) is not None, '角色实例定义不存在。')
        _ensure(player_scope['player']['hp'] <= player_scope['player']['max_hp'], '玩家生命值超过上限。')
        all_instances.extend(player_scope['discard_pile'] + player_scope['hand'])
    instance_ids = [item['instance_id'] for item in all_instances]
    _ensure(len(instance_ids) == len(set(instance_ids)), '道具实例 ID 发生重复。')
    for instance in all_instances:
        _ensure(get_item(instance['definition_id']) is not None, f"未知的道具实例定义：{instance['definition_id']}")


def _normalize_loaded_state(state: JsonDict) -> JsonDict:
    normalized = deepcopy(state)
    map_definition = get_map(normalized.get('map', {}).get('id', DEFAULT_MAP_ID))
    map_replaced = False
    if map_definition is not None:
        if (
            normalized.get('map', {}).get('name') != map_definition.get('name')
            or int(normalized.get('map', {}).get('version', 0)) != int(map_definition.get('version', 0))
            or int(normalized.get('map', {}).get('total_layers', 1)) != int(map_definition.get('total_layers', 1))
            or normalized.get('map', {}).get('layers') != map_definition.get('layers')
            or normalized.get('map', {}).get('entries') != map_definition.get('entries')
        ):
            normalized['map'] = deepcopy(map_definition)
            entry = map_entry_point(normalized['map'])
            normalized['map']['current_layer'] = int(entry['layer'])
            _materialize_random_tiles(normalized['map'])
            map_replaced = True
        normalized['map']['name'] = map_definition.get('name', normalized['map'].get('name'))
        normalized['map']['background_image'] = map_definition.get('background_image', normalized['map'].get('background_image'))
        monster_definitions = {monster['id']: monster for monster in map_definition.get('monsters', [])}
        for monster in normalized['map'].get('monsters', []):
            monster_definition = monster_definitions.get(monster.get('id'))
            if monster_definition is None:
                continue
            monster['name'] = monster_definition.get('name', monster.get('name'))
            monster.pop('icon', None)
        boss_definition = map_definition.get('boss', {})
        if normalized['map'].get('boss', {}).get('id') == boss_definition.get('id'):
            normalized['map']['boss']['name'] = boss_definition.get('name', normalized['map']['boss'].get('name'))
        normalized['map'].get('boss', {}).pop('icon', None)
    for tile in normalized.get('map', {}).get('tiles', []):
        tile.pop('icon', None)
        if resolve_map_object_id(tile) == 'turn_belt' and str(tile.get('direction', '')) in DIRECTIONS:
            object_id = f"turn_belt_{tile['direction']}"
            tile['type'] = object_id
            tile['object_id'] = object_id
            tile.pop('direction', None)
        normalize_tile_footprint(tile)
    for player_scope in normalized.get('players', {}).values():
        character_instance = player_scope.get('character_instance', {})
        character_definition = get_character(character_instance.get('definition_id'))
        if character_definition is None:
            characters = load_characters()
            if not characters:
                continue
            character_definition = characters[0]
            rebuilt_character = build_character_instance(character_definition)
            rebuilt_character['instance_id'] = character_instance.get('instance_id', rebuilt_character['instance_id'])
            player_scope['character_instance'] = rebuilt_character
            character_instance = player_scope['character_instance']
            player_scope.setdefault('player', {})['max_hp'] = rebuilt_character['max_hp']
            player_scope['player']['hp'] = min(int(player_scope['player'].get('hp', rebuilt_character['max_hp'])), rebuilt_character['max_hp'])
            player_scope['player']['attack'] = rebuilt_character['attack']
            player_scope['player']['defense'] = rebuilt_character['defense']
        character_instance['name'] = character_definition.get('name', character_instance.get('name'))
        character_instance.pop('title', None)
        character_instance['passive'] = character_definition.get('passive', character_instance.get('passive'))
        character_instance['identification_level'] = int(character_definition.get('identification_level', character_instance.get('identification_level', 1)))
        serialized_character = serialize_character_definition(character_definition)
        character_instance['portrait_image'] = serialized_character['portrait_image']
        character_instance['avatar_image'] = serialized_character['avatar_image']
        player_state = player_scope.setdefault('player', {})
        player_state.setdefault('keycards', 0)
        player_state.setdefault('fons_amount', 0)
        base_identification_level = int(character_instance.get('identification_level', 1))
        player_state['identification_level'] = max(
            base_identification_level,
            int(player_state.get('identification_level', base_identification_level) or base_identification_level),
        )
        initialize_identification_state(player_state, base_identification_level)
        existing_fons = next((item for item in player_scope.get('hand', []) if item.get('definition_id') == 'fons'), None)
        if existing_fons is not None:
            player_state['fons_amount'] = max(
                int(player_state.get('fons_amount', 0)),
                int(existing_fons.get('amount', 0)),
            )
        _absorb_convertible_hand_items(player_scope)
        if map_replaced:
            entry = map_entry_point(normalized['map'])
            player_scope['player']['x'] = entry['x']
            player_scope['player']['y'] = entry['y']
        if 'pending_dice' not in player_scope:
            player_scope['pending_dice'] = _dice_pair_from_legacy_die(player_scope.get('pending_die'))
        dice_values = pending_dice_values({
            'pending_dice': player_scope.get('pending_dice'),
            'pending_die': player_scope.get('pending_die'),
        })
        if dice_values is None:
            player_scope['pending_dice'] = None
            player_scope['pending_die'] = None
        else:
            player_scope['pending_dice'] = {'a': int(dice_values[0]), 'b': int(dice_values[1])}
            player_scope['pending_die'] = max(dice_values)
        allowed_locked_ids = set(_locked_item_ids_for_character(character_definition))
        player_scope['hand'] = [
            item for item in player_scope.get('hand', [])
            if get_item(item.get('definition_id')) is not None
            and (item.get('definition_id') != 'fons' or item.get('definition_id') in allowed_locked_ids)
        ]
        player_scope['discard_pile'] = [
            item for item in player_scope.get('discard_pile', [])
            if get_item(item.get('definition_id')) is not None
            and (item.get('definition_id') != 'fons' or item.get('definition_id') in allowed_locked_ids)
        ]
        for item in player_scope.get('hand', []):
            if item.get('definition_id') == 'fons':
                item['amount'] = int(player_scope['player'].get('fons_amount', 0))
        existing_item_ids = {item.get('definition_id') for item in player_scope.get('hand', [])}
        missing_locked_items = [item_id for item_id in _locked_item_ids_for_character(character_definition) if item_id not in existing_item_ids]
        for item_instance in build_item_instances(missing_locked_items, turn=int(normalized.get('turn', 1))):
            if item_instance['definition_id'] == 'fons':
                item_instance['amount'] = int(player_scope['player'].get('fons_amount', 0))
            player_scope.setdefault('hand', []).insert(0, item_instance)
    _project_player_scope(normalized, str(normalized['current_actor_uid']))
    _initialize_item_zones(normalized, emit_initial_events=False)
    return normalized


def _absorb_convertible_hand_items(player_scope: JsonDict) -> None:
    retained_hand = []
    fons_total = int(player_scope.setdefault('player', {}).get('fons_amount', 0))
    for item in player_scope.get('hand', []):
        item_definition = get_item(item.get('definition_id')) or {}
        fons_value = int(item_definition.get('fons_value', 0) or 0)
        if fons_value <= 0:
            retained_hand.append(item)
            continue
        fons_total += fons_value * max(1, int(item.get('quantity', 1) or 1))
    player_scope['player']['fons_amount'] = fons_total
    player_scope['hand'] = retained_hand


def _persist_room_snapshot(room: Room, state: JsonDict) -> None:
    _capture_player_scope(state)
    upsert_run(room, state['map']['id'], state['status'], state)
    if state['status'] in {'playing', 'victory', 'defeat'}:
        update_room_status(room, state['status'])


def _require_room(player: Player) -> Room:
    room = get_current_room(player)
    if room is None:
        raise RuleValidationError('当前没有房间，请先创建或加入房间。')
    return room


def add_log(state: JsonDict, message: str) -> None:
    state['log'].insert(0, message)
    del state['log'][LOG_LIMIT:]
    logger.info(message)


def begin_action_queue(state: JsonDict) -> None:
    state[ACTION_QUEUE_KEY] = []


def add_action_step(state: JsonDict, step: JsonDict) -> None:
    state.setdefault(ACTION_QUEUE_KEY, []).append(step)


def take_action_queue(state: JsonDict) -> list[JsonDict]:
    return list(state.pop(ACTION_QUEUE_KEY, []))


def step_position(x: int, y: int, direction: str) -> tuple[int, int]:
    dx, dy = DIRECTIONS[direction]
    return x + dx, y + dy


def tile_at(state: JsonDict, x: int, y: int) -> JsonDict | None:
    for tile in reversed(state['map']['tiles']):
        if _is_on_current_layer(state, tile) and tile_contains_cell(tile, x, y):
            return tile
    return None


def tile_contains_cell(tile: JsonDict, x: int, y: int) -> bool:
    tile_x = int(tile.get('x', 0))
    tile_y = int(tile.get('y', 0))
    width = max(1, int(tile.get('width', 1) or 1))
    height = max(1, int(tile.get('height', 1) or 1))
    return tile_x <= int(x) < tile_x + width and tile_y <= int(y) < tile_y + height


def monster_at(state: JsonDict, x: int, y: int) -> JsonDict | None:
    for monster in state['map']['monsters']:
        if _is_on_current_layer(state, monster) and monster['hp'] > 0 and not monster.get('captured') and monster['x'] == x and monster['y'] == y:
            return monster
    return None


def boss_on_tile(state: JsonDict, x: int, y: int) -> bool:
    boss = state['map']['boss']
    return boss['hp'] > 0 and any(_is_on_current_layer(state, pos) and pos['x'] == x and pos['y'] == y for pos in boss['positions'])


def current_map_layer(state: JsonDict) -> int:
    return int(state['map'].get('current_layer', 1))


def map_entry_point(game_map: JsonDict) -> JsonDict:
    entries = game_map.get('entries', [])
    if isinstance(entries, list) and entries:
        entry = entries[0]
        return {
            'layer': int(entry.get('layer', 1)),
            'x': int(entry.get('x', 0)),
            'y': int(entry.get('y', 0)),
        }
    start = game_map.get('start', {})
    return {
        'layer': int(start.get('layer', game_map.get('current_layer', 1))),
        'x': int(start.get('x', 0)),
        'y': int(start.get('y', 0)),
    }


def map_layer_dimensions(game_map: JsonDict, layer: int) -> tuple[int, int]:
    for layer_meta in game_map.get('layers', []):
        if int(layer_meta.get('layer', 1)) == int(layer):
            return int(layer_meta.get('width', 0)), int(layer_meta.get('height', 0))
    return int(game_map.get('width', 0)), int(game_map.get('height', 0))


def map_layer_background_image(game_map: JsonDict, layer: int) -> str:
    fallback = str(game_map.get('background_image', ''))
    for layer_meta in game_map.get('layers', []):
        if int(layer_meta.get('layer', 1)) == int(layer):
            return str(layer_meta.get('background_image') or fallback)
    return fallback


def current_map_dimensions(state: JsonDict) -> tuple[int, int]:
    return map_layer_dimensions(state['map'], current_map_layer(state))


def in_current_layer_bounds(state: JsonDict, x: int, y: int) -> bool:
    width, height = current_map_dimensions(state)
    return 0 <= x < width and 0 <= y < height


def _is_on_current_layer(state: JsonDict, entity: JsonDict) -> bool:
    return int(entity.get('layer', 1)) == current_map_layer(state)


def is_hidden_from_player(state: JsonDict, tile: JsonDict) -> bool:
    return bool(tile.get('hidden_zone')) and not state['map'].get('hidden_room_revealed') and tile.get('object_id') != 'hidden_door'


def is_hidden_entity(state: JsonDict, entity: JsonDict) -> bool:
    return bool(entity.get('hidden_zone')) and not state['map'].get('hidden_room_revealed')


def should_identify_on_pass_through(map_object: JsonDict, block_type: object) -> bool:
    return str(block_type) == '可通过' and bool(map_object.get('identify_on_pass'))


def identify_tile(state: JsonDict, tile: JsonDict, source: str) -> JsonDict:
    object_id = resolve_map_object_id(tile)
    map_object = get_map_object(object_id) or {}
    return dispatch_event(state, GameEvent.IDENTIFY, {
        'tile_type': tile['type'],
        'tile': tile,
        'object_id': object_id,
        'x': tile['x'],
        'y': tile['y'],
        'source': source,
        'identification_level': current_identification_level(state),
        'block_type': map_object.get('block_type', '可通过'),
    })


def identify_tiles_in_range(state: JsonDict, source: str, show_effect: bool = False) -> None:
    cells = identification_range_cells(state)
    if show_effect:
        add_action_step(state, {
            'type': 'identify_range',
            'level': current_identification_level(state),
            'cells': cells,
            'x': state['player']['x'],
            'y': state['player']['y'],
            'layer': current_map_layer(state),
        })
    for cell in cells:
        tile = tile_at(state, int(cell['x']), int(cell['y']))
        if tile is None or is_hidden_from_player(state, tile):
            continue
        identify_tile(state, tile, source=source)


def turn_belt_direction_for_tile(tile: JsonDict | None) -> str | None:
    if tile is None:
        return None
    object_id = resolve_map_object_id(tile)
    if object_id in TURN_BELT_DIRECTIONS:
        return TURN_BELT_DIRECTIONS[object_id]
    if object_id == 'turn_belt':
        direction = str(tile.get('direction', ''))
        return direction if direction in DIRECTIONS else None
    return None


def is_turn_belt_tile(tile: JsonDict | None) -> bool:
    return turn_belt_direction_for_tile(tile) is not None


def get_block_reason(state: JsonDict, x: int, y: int) -> str | None:
    if not in_current_layer_bounds(state, x, y):
        return '超出地图边界'
    tile = tile_at(state, x, y)
    if monster_at(state, x, y):
        return '怪物阻挡了道路'
    if boss_on_tile(state, x, y):
        return 'Boss 本体占据该格子'
    if tile:
        object_id = resolve_map_object_id(tile)
        map_object = get_map_object(object_id) or {}
        block_payload = dispatch_event(state, GameEvent.MOVE_BLOCK_CHECK, {
            'tile_type': tile['type'],
            'tile': tile,
            'object_id': object_id,
            'x': x,
            'y': y,
            'block_type': map_object.get('block_type', '可通过'),
            'blocked_reason': None,
        })
        block_type = str(block_payload.get('block_type', map_object.get('block_type', '可通过')))
        if block_type == '阻挡':
            blocked_reason = block_payload.get('blocked_reason')
            if blocked_reason:
                return str(blocked_reason)
            return get_map_object_tooltip(tile)
    return None


def _can_enemy_attack_player(state: JsonDict, enemy: JsonDict, target_x: int, target_y: int) -> bool:
    attack_range = int(enemy.get('range', 1))
    if manhattan(enemy['x'], enemy['y'], target_x, target_y) > attack_range:
        return False
    queue = [(enemy['x'], enemy['y'], 0)]
    seen = {f"{enemy['x']}:{enemy['y']}"}
    while queue:
        x, y, distance = queue.pop(0)
        if distance >= attack_range:
            continue
        for dx, dy in DIRECTIONS.values():
            next_x = x + dx
            next_y = y + dy
            key = f'{next_x}:{next_y}'
            if (
                key in seen
                or next_x < 0
                or next_y < 0
                or not in_current_layer_bounds(state, next_x, next_y)
            ):
                continue
            if next_x == target_x and next_y == target_y:
                return True
            seen.add(key)
            if _is_attack_range_blocked(state, next_x, next_y):
                continue
            queue.append((next_x, next_y, distance + 1))
    return False


def _is_attack_range_blocked(state: JsonDict, x: int, y: int) -> bool:
    tile = tile_at(state, x, y)
    if tile is None:
        return False
    object_id = resolve_map_object_id(tile)
    if object_id in {'door', 'keycard_door'} and not tile.get('locked', True):
        return False
    if object_id in {'safe', 'large_safe'} and tile.get('opened'):
        return False
    map_object = get_map_object(object_id) or {}
    return str(map_object.get('block_type', '可通过')) == '阻挡'


def resolve_start_tile_redirect(state: JsonDict, active_direction: str, steps_remaining: int) -> str:
    actor = state['player']
    tile = tile_at(state, actor['x'], actor['y'])
    if tile is None or steps_remaining <= 0:
        return active_direction
    object_id = resolve_map_object_id(tile)
    if not is_turn_belt_tile(tile):
        return active_direction
    map_object = get_map_object(object_id) or {}
    through_payload = dispatch_event(state, GameEvent.MOVE_THROUGH, {
        'tile_type': tile['type'],
        'tile': tile,
        'object_id': object_id,
        'x': actor['x'],
        'y': actor['y'],
        'steps_remaining': steps_remaining,
        'block_type': map_object.get('block_type', '可通过'),
        'next_direction': active_direction,
    })
    return str(through_payload.get('next_direction', active_direction))


def _direction_turn_count(path_directions: list[str]) -> int:
    turns = 0
    previous = path_directions[0] if path_directions else ''
    for direction in path_directions[1:]:
        if direction != previous:
            turns += 1
            previous = direction
    return turns


def _path_axis_steps(path_directions: list[str]) -> tuple[int, int]:
    horizontal_steps = 0
    vertical_steps = 0
    for direction in path_directions:
        dx, dy = DIRECTIONS[direction]
        if dx:
            horizontal_steps += 1
        if dy:
            vertical_steps += 1
    return horizontal_steps, vertical_steps


def _axis_steps_within_dice_limits(horizontal_steps: int, vertical_steps: int, die_a: int, die_b: int) -> bool:
    return (
        (vertical_steps <= die_a and horizontal_steps <= die_b)
        or (vertical_steps <= die_b and horizontal_steps <= die_a)
    )


def resolve_tile_entry(state: JsonDict, active_direction: str, steps_remaining: int) -> tuple[str, bool]:
    actor = state['player']
    tile = tile_at(state, actor['x'], actor['y'])
    if tile is None:
        return active_direction, False
    tile_type = tile['type']
    object_id = resolve_map_object_id(tile)
    map_object = get_map_object(object_id) or {}
    block_type = map_object.get('block_type', '可通过')
    # 移动途径是最通用的进入格子事件，拾取、转向、事件格等都应优先挂在这里。
    through_payload = dispatch_event(state, GameEvent.MOVE_THROUGH, {
        'tile_type': tile_type,
        'tile': tile,
        'object_id': object_id,
        'x': actor['x'],
        'y': actor['y'],
        'steps_remaining': steps_remaining,
        'block_type': block_type,
        'next_direction': active_direction,
    })
    next_direction = through_payload.get('next_direction', active_direction)
    if should_identify_on_pass_through(map_object, block_type):
        identify_tile(state, tile, source='pass_through')
    # “移动停留”用于本次移动最终停在该格，或该格本身属于拦截型地块。
    if block_type == '拦截' or steps_remaining == 0:
        dispatch_event(state, GameEvent.MOVE_STOP, {
            'tile_type': tile_type,
            'tile': tile,
            'object_id': object_id,
            'x': actor['x'],
            'y': actor['y'],
            'steps_remaining': steps_remaining,
            'block_type': block_type,
            'next_direction': next_direction,
        })
    return next_direction, block_type == '拦截'


def resolve_battle(state: JsonDict) -> None:
    actor = state['player']
    # 战斗阶段先发开始事件，供内容层提前增减攻防、挂标记或记录战斗态。
    dispatch_event(state, GameEvent.BATTLE_PHASE_BEGIN, {
        'x': actor['x'],
        'y': actor['y'],
    })
    battle_end_payload = {'status': state['status']}
    fought = False
    if is_adjacent_to_boss(state, actor['x'], actor['y']):
        battle_end_payload = dispatch_event(
            state,
            GameEvent.DIRECT_ATTACK,
            _build_direct_attack_payload(state['map']['boss'], attack_kind='反击'),
            default_handler=build_scoped_default_handler(state, _default_direct_attack),
        )
        fought = True
        if state['map']['boss']['hp'] <= 0:
            state['status'] = 'victory'
            state['phase'] = 'victory'
            battle_end_payload['status'] = state['status']
            add_log(state, f"{state['map']['boss']['name']} 被击破，获得胜利。")
            dispatch_event(state, GameEvent.RUN_VICTORY, {'target': 'boss'})

    adjacent = []
    ranged = []
    if state['status'] == 'playing' and state['player']['hp'] > 0:
        for monster in state['map']['monsters']:
            if monster['hp'] <= 0 or monster.get('captured') or not _is_on_current_layer(state, monster):
                continue
            distance = manhattan(actor['x'], actor['y'], monster['x'], monster['y'])
            if distance == 1:
                adjacent.append(monster)
            elif _can_enemy_attack_player(state, monster, actor['x'], actor['y']):
                ranged.append(monster)

    for target in sorted(adjacent, key=lambda m: (m['hp'], m['id'])):
        if state['status'] != 'playing' or state['player']['hp'] <= 0 or target['hp'] <= 0:
            break
        battle_end_payload = dispatch_event(
            state,
            GameEvent.DIRECT_ATTACK,
            _build_direct_attack_payload(target, attack_kind='反击'),
            default_handler=build_scoped_default_handler(state, _default_direct_attack),
        )
        fought = True

    if not fought and state['status'] == 'playing' and state['player']['hp'] > 0:
        if ranged:
            target = sorted(ranged, key=lambda m: (manhattan(actor['x'], actor['y'], m['x'], m['y']), m['id']))[0]
            battle_end_payload = dispatch_event(
                state,
                GameEvent.RANGED_ATTACK,
                _build_enemy_attack_payload(target),
                default_handler=build_scoped_default_handler(state, _default_ranged_attack),
            )
            fought = True
        else:
            add_log(state, '战斗阶段没有可结算目标。')
    if state['player']['hp'] <= 0:
        state['player']['hp'] = 0
        _capture_player_scope(state)
        if _all_players_defeated(state):
            state['status'] = 'defeat'
            state['phase'] = 'defeat'
            battle_end_payload['status'] = state['status']
            add_log(state, '所有角色都已倒下，对局失败。')
            dispatch_event(state, GameEvent.RUN_DEFEAT, {'reason': 'battle'})
        else:
            add_log(state, '当前角色已倒下，本回合后将由其他玩家继续行动。')
    # 不论有没有目标，战斗阶段结束时都统一派发收尾事件，便于后续扩展“战后结算”效果。
    dispatch_event(state, GameEvent.BATTLE_PHASE_END, battle_end_payload)


def _build_direct_attack_payload(enemy: JsonDict, attack_kind: str) -> JsonDict:
    return {
        'enemy_id': enemy['id'],
        'enemy_name': enemy['name'],
        'attack_kind': attack_kind,
        'status': 'playing',
    }


def _build_enemy_attack_payload(enemy: JsonDict) -> JsonDict:
    return {
        'enemy_id': enemy['id'],
        'enemy_name': enemy['name'],
        'attack_kind': '远程攻击',
        'status': 'playing',
    }


def _default_direct_attack(context: EventContext, state: JsonDict) -> None:
    enemy = _find_enemy_by_id(state, str(context.payload['enemy_id']))
    _ensure(enemy is not None, f"未找到战斗目标：{context.payload['enemy_id']}")
    actor_profile = state['players'][str(state['current_actor_uid'])]['profile']
    mark_battle_step(state)
    outgoing = max(1, current_attack(state) - effective_enemy_defense(state, enemy))
    damage_result = resolve_damage_package(state, build_damage_package(
        source_name=str(actor_profile.get('nickname', '玩家')),
        source_id=PLAYER_TARGET_ID,
        source_type='player',
        target_type='enemy',
        target_id=str(enemy['id']),
        target_name=str(enemy['name']),
        amount=outgoing,
        attack_kind='直接攻击',
        allow_block=False,
    ))
    context.payload['outgoing_damage'] = damage_result['final_damage']
    dispatch_event(state, GameEvent.DIRECT_ATTACK_RESOLVED, {
        'enemy_id': enemy['id'],
        'enemy_name': enemy['name'],
        'outgoing_damage': damage_result['final_damage'],
    })
    if damage_result['target_defeated']:
        context.payload['status'] = 'enemy_defeated'
        add_log(state, f"{enemy['name']} 已被击败。")
        spawn_enemy_drop(state, enemy)
        add_action_step(state, {
            'type': 'battle',
            'enemy_name': enemy['name'],
            'enemy_hp': enemy['hp'],
            'enemy_max_hp': enemy['max_hp'],
            'enemy_lost_hp': damage_result['final_damage'],
            'player_lost_hp': 0,
        })
        return
    incoming_result = resolve_damage_package(state, build_damage_package(
        source_name=str(enemy['name']),
        source_id=str(enemy['id']),
        source_type='enemy',
        target_type='player',
        target_id=PLAYER_TARGET_ID,
        target_name=str(actor_profile.get('nickname', '玩家')),
        target_player_uid=str(state['current_actor_uid']),
        amount=max(0, enemy['attack'] - current_defense(state)),
        attack_kind=str(context.payload.get('attack_kind', '反击')),
        allow_block=True,
    ))
    _apply_mamen_fons_tax(state, enemy, incoming_result)
    context.payload['incoming_damage'] = incoming_result['final_damage']
    add_action_step(state, {
        'type': 'battle',
        'enemy_name': enemy['name'],
        'enemy_hp': enemy['hp'],
        'enemy_max_hp': enemy['max_hp'],
        'enemy_lost_hp': damage_result['final_damage'],
        'player_lost_hp': incoming_result['final_damage'],
    })
    dispatch_event(state, GameEvent.DIRECT_ATTACK_RESOLVED, {
        'enemy_id': enemy['id'],
        'enemy_name': enemy['name'],
        'incoming_damage': incoming_result['final_damage'],
    })


def _default_ranged_attack(context: EventContext, state: JsonDict) -> None:
    enemy = _find_enemy_by_id(state, str(context.payload['enemy_id']))
    _ensure(enemy is not None, f"未找到远程目标：{context.payload['enemy_id']}")
    actor_profile = state['players'][str(state['current_actor_uid'])]['profile']
    mark_battle_step(state)
    damage_result = resolve_damage_package(state, build_damage_package(
        source_name=str(enemy['name']),
        source_id=str(enemy['id']),
        source_type='enemy',
        target_type='player',
        target_id=PLAYER_TARGET_ID,
        target_name=str(actor_profile.get('nickname', '玩家')),
        target_player_uid=str(state['current_actor_uid']),
        amount=max(0, enemy['attack'] - current_defense(state)),
        attack_kind=str(context.payload.get('attack_kind', '远程攻击')),
        allow_block=True,
    ))
    _apply_mamen_fons_tax(state, enemy, damage_result)
    context.payload['incoming_damage'] = damage_result['final_damage']
    add_action_step(state, {
        'type': 'battle',
        'enemy_name': enemy['name'],
        'enemy_hp': enemy['hp'],
        'enemy_max_hp': enemy['max_hp'],
        'enemy_lost_hp': 0,
        'player_lost_hp': damage_result['final_damage'],
    })
    dispatch_event(state, GameEvent.RANGED_ATTACK_RESOLVED, {
        'enemy_id': enemy['id'],
        'enemy_name': enemy['name'],
        'incoming_damage': damage_result['final_damage'],
    })


def _find_enemy_by_id(state: JsonDict, enemy_id: str) -> JsonDict | None:
    boss = state['map']['boss']
    if boss['id'] == enemy_id:
        return boss
    for monster in state['map']['monsters']:
        if monster['id'] == enemy_id:
            return monster
    return None


def effective_enemy_defense(state: JsonDict, enemy: JsonDict) -> int:
    defense = int(enemy.get('defense', 0) or 0)
    if enemy.get('id') != 'mamen':
        return defense
    return max(0, defense - (fons_amount(state) // MAMEN_FONS_DEFENSE_STEP))


def _apply_mamen_fons_tax(state: JsonDict, enemy: JsonDict, damage_result: JsonDict) -> None:
    if enemy.get('id') != 'mamen' or int(damage_result.get('final_damage', 0) or 0) <= 0:
        return
    current_fons = fons_amount(state)
    if current_fons <= 0:
        return
    consumed = max(1, current_fons * MAMEN_FONS_DAMAGE_TAX_PERCENT // 100)
    set_fons_amount(state, max(0, current_fons - consumed))
    add_log(state, f"玛门吞噬了 {consumed} 方斯。")
    add_action_step(state, {
        'type': 'popup',
        'icon': _boss_icon(enemy),
        'title': '玛门',
        'message': f'玛门对富有者更加疯狂，造成伤害后吞噬了 {consumed} 方斯。',
    })


def current_attack(state: JsonDict) -> int:
    _project_player_scope(state, str(state['current_actor_uid']))
    return state['player']['attack'] + sum_runtime_effect_bonus(state, 'attack_bonus') + xiaozhi_fons_attack_bonus(state)


def xiaozhi_fons_attack_bonus(state: JsonDict) -> int:
    character_instance = state.get('character_instance', {})
    if character_instance.get('definition_id') != 'xiaozhi':
        return 0
    return min(XIAOZHI_FONS_ATTACK_CAP, fons_amount(state) // XIAOZHI_FONS_ATTACK_STEP)


def fons_amount(state: JsonDict) -> int:
    for item_instance in state.get('hand', []):
        if item_instance.get('definition_id') == 'fons':
            return int(item_instance.get('amount', 0))
    return int(state.get('player', {}).get('fons_amount', 0))


def set_fons_amount(state: JsonDict, amount: int) -> None:
    state.setdefault('player', {})['fons_amount'] = max(0, int(amount))
    for item_instance in state.get('hand', []):
        if item_instance.get('definition_id') == 'fons':
            item_instance['amount'] = int(state['player']['fons_amount'])
            break


def current_defense(state: JsonDict) -> int:
    _project_player_scope(state, str(state['current_actor_uid']))
    return state['player']['defense'] + sum_runtime_effect_bonus(state, 'defense_bonus')


def current_identification_level(state: JsonDict) -> int:
    _project_player_scope(state, str(state['current_actor_uid']))
    base_level = int(state['player'].get('identification_level', state['character_instance'].get('identification_level', 1)))
    bonus_level = sum_runtime_effect_bonus(state, 'identification_level_bonus')
    return max(MIN_IDENTIFICATION_LEVEL, min(MAX_IDENTIFICATION_LEVEL, base_level + bonus_level))


def identification_range_cells(state: JsonDict, x: int | None = None, y: int | None = None) -> list[JsonDict]:
    actor = state['player']
    origin_x = int(actor['x'] if x is None else x)
    origin_y = int(actor['y'] if y is None else y)
    level = current_identification_level(state)
    cells = []
    for dx, dy in IDENTIFICATION_OFFSETS[level]:
        cell_x = origin_x + dx
        cell_y = origin_y + dy
        if not in_current_layer_bounds(state, cell_x, cell_y):
            continue
        cells.append({
            'x': cell_x,
            'y': cell_y,
            'layer': current_map_layer(state),
        })
    return cells


def is_adjacent_to_boss(state: JsonDict, x: int, y: int) -> bool:
    return any(
        _is_on_current_layer(state, pos) and manhattan(x, y, pos['x'], pos['y']) == 1
        for pos in state['map']['boss']['positions']
        if state['map']['boss']['hp'] > 0
    )


def manhattan(x1: int, y1: int, x2: int, y2: int) -> int:
    return abs(x1 - x2) + abs(y1 - y2)


def roll_blue_dice() -> JsonDict:
    return {
        'a': random.randint(1, 6),
        'b': random.randint(1, 6),
    }


def pending_dice_values(state: JsonDict) -> tuple[int, int] | None:
    pending_dice = state.get('pending_dice')
    if isinstance(pending_dice, dict):
        try:
            return (
                max(0, int(pending_dice.get('a', pending_dice.get('vertical', 0)))),
                max(0, int(pending_dice.get('b', pending_dice.get('horizontal', 0)))),
            )
        except (TypeError, ValueError):
            return None
    if isinstance(pending_dice, (list, tuple)) and len(pending_dice) >= 2:
        try:
            return max(0, int(pending_dice[0])), max(0, int(pending_dice[1]))
        except (TypeError, ValueError):
            return None
    return _dice_pair_from_legacy_die(state.get('pending_die'))


def set_pending_dice(state: JsonDict, die_a: int | None, die_b: int | None) -> None:
    if die_a is None or die_b is None:
        state['pending_dice'] = None
        state['pending_die'] = None
        return
    dice = {
        'a': max(0, int(die_a)),
        'b': max(0, int(die_b)),
    }
    state['pending_dice'] = dice
    state['pending_die'] = max(dice['a'], dice['b'])


def _dice_pair_from_legacy_die(value: object) -> tuple[int, int] | None:
    if value is None:
        return None
    try:
        die = max(0, int(value))
    except (TypeError, ValueError):
        return None
    return die, die


def _finish_player_turn(state: JsonDict) -> None:
    state['phase'] = 'completed'
    state['acted_this_turn'] = True
    _capture_player_scope(state)
    if _all_active_players_completed(state):
        _advance_shared_turn(state)


def _advance_shared_turn(state: JsonDict) -> None:
    # 共享回合只在所有存活玩家都完成行动后统一推进。
    current_actor_uid = str(state['current_actor_uid'])
    _project_player_scope(state, current_actor_uid)
    run_phase_sequence(state, TURN_CLOSING_SEQUENCE, lambda event_name: {
        'turn': state['turn'],
        'phase': state['phase'],
        'event': event_name.value,
    })
    _capture_player_scope(state)
    _settle_identification_combos(state)
    state['turn'] += 1
    _start_shared_turn(state, reason='turn_end')


def _start_shared_turn(state: JsonDict, reason: str) -> None:
    # 共享回合开始时，为每个仍存活的玩家分别重置并自动掷骰。
    _ensure(state['status'] == 'playing', '只有进行中的对局可以自动掷骰。')
    original_actor_uid = str(state['current_actor_uid'])
    for actor_uid, player_scope in state['players'].items():
        if player_scope.get('defeated', False) or player_scope['player']['hp'] <= 0:
            player_scope['acted_this_turn'] = True
            player_scope['phase'] = 'defeat'
            player_scope['pending_die'] = None
            player_scope['pending_dice'] = None
            continue
        _project_player_scope(state, actor_uid)
        set_pending_dice(state, None, None)
        state['phase'] = 'dice'
        state['has_played_item'] = False
        state['route_hint'] = DEFAULT_ROUTE_HINT
        state['acted_this_turn'] = False
        reset_turn_flags(state['player'])
        run_phase_sequence(
            state,
            TURN_OPENING_SEQUENCE,
            lambda event_name: _build_turn_opening_payload(state, event_name, reason),
            lambda event_name: _build_turn_opening_default_handler(state, event_name),
        )
        _capture_player_scope(state)
    _project_player_scope(state, original_actor_uid if original_actor_uid in state['players'] else state['room']['member_order'][0])


def _build_turn_opening_payload(state: JsonDict, event_name: GameEvent, reason: str) -> JsonDict:
    # 阶段事件的基础入参由引擎统一组装，默认行为则由 default handler 承担。
    payload = {
        'turn': state['turn'],
        'reason': reason,
        'die': state['pending_die'],
        'dice': state.get('pending_dice'),
    }
    if event_name == GameEvent.TURN_BEGIN:
        payload.pop('die')
        payload.pop('dice')
    return payload


def _settle_identification_combos(state: JsonDict) -> None:
    for player_scope in state.get('players', {}).values():
        settle_combo_for_turn(player_scope.setdefault('player', {}))


def _build_turn_opening_default_handler(state: JsonDict, event_name: GameEvent) -> EventHook | None:
    if event_name == GameEvent.TURN_BEGIN:
        return build_scoped_default_handler(state, _default_turn_begin)
    if event_name == GameEvent.DICE_ROLLED:
        return build_scoped_default_handler(state, _default_dice_rolled)
    if event_name == GameEvent.ACTION_PHASE_BEGIN:
        return build_scoped_default_handler(state, _default_action_phase_begin)
    return None


def build_scoped_default_handler(
    state: JsonDict,
    handler: Callable[[EventContext, JsonDict], None],
) -> EventHook:
    def scoped_handler(context: EventContext) -> None:
        handler(context, state)

    return scoped_handler


def _default_dice_rolled(context: EventContext, state: JsonDict) -> None:
    # 掷骰是引擎默认行为；若未来存在 replace hook，可由内容层显式改写。
    dice = roll_blue_dice()
    set_pending_dice(state, dice['a'], dice['b'])
    add_log(state, f"第 {state['turn']} 回合自动掷出蓝骰 {dice['a']} / {dice['b']}。")
    context.payload['die'] = state['pending_die']
    context.payload['dice'] = state['pending_dice']


def _default_action_phase_begin(context: EventContext, state: JsonDict) -> None:
    # 行动阶段默认会切换 phase 并重置本回合道具使用标记。
    state['phase'] = 'action'
    state['has_played_item'] = False
    context.payload['die'] = state['pending_die']
    context.payload['dice'] = state.get('pending_dice')


def _default_turn_begin(context: EventContext, state: JsonDict) -> None:
    context.payload['turn'] = state['turn']
    add_log(state, f"第 {state['turn']} 回合开始。")


def _default_move_phase_begin(context: EventContext, state: JsonDict) -> None:
    state['phase'] = 'movement'
    direction = str(context.payload.get('direction', 'unknown'))
    add_log(state, f"开始向 {DIRECTION_LABELS.get(direction, direction)} 移动，共 {context.payload.get('steps', 0)} 步。")


def build_board_overlay(state: JsonDict) -> JsonDict:
    width, height = current_map_dimensions(state)
    overlays = []
    for tile in state['map']['tiles']:
        if not _is_on_current_layer(state, tile):
            continue
        if tile.get('hidden_zone') and not state['map'].get('hidden_room_revealed') and tile.get('object_id') != 'hidden_door':
            continue
        object_id = resolve_map_object_id(tile)
        display_type = tile['type']
        if tile['type'] == 'chest' and tile.get('opened'):
            display_type = 'floor'
        if tile['type'] == 'event' and tile.get('resolved'):
            display_type = 'floor'
        if object_id in {'safe', 'large_safe'} and tile.get('opened'):
            display_type = 'floor'
        if tile['type'] == 'loot_item' and tile.get('collected'):
            display_type = 'floor'
        if tile['type'] in {'wall', 'boss_tile'}:
            display_type = 'floor'
        if display_type != 'floor':
            map_object = get_map_object(object_id) or {}
            if map_object.get('hidden_overlay'):
                continue
            entity_type = 'turn_belt' if is_turn_belt_tile(tile) else tile['type']
            overlay = _tile_overlay(tile, width, height, _tile_overlay_icon(tile, map_object), get_map_object_tooltip(tile), entity_type, current_map_layer(state))
            direction = turn_belt_direction_for_tile(tile) or map_object.get('direction') or tile.get('direction')
            if direction:
                overlay['direction'] = direction
            overlay['object_id'] = object_id
            overlay['tags'] = map_object_tags(map_object)
            overlays.append(overlay)
    for monster in state['map']['monsters']:
        if _is_on_current_layer(state, monster) and monster['hp'] > 0 and not monster.get('captured') and not is_hidden_entity(state, monster):
            overlays.append(_overlay(monster['x'], monster['y'], width, height, _monster_icon(monster), f"{monster['name']}：HP {monster['hp']}/{monster['max_hp']}，攻击 {monster['attack']}，防御 {monster['defense']}，射程 {monster['range']}", 'monster', current_map_layer(state)))
    boss = state['map']['boss']
    boss_positions = [
        pos
        for pos in boss['positions']
        if _is_on_current_layer(state, pos) and not is_hidden_entity(state, pos)
    ]
    if boss['hp'] > 0 and boss_positions:
        overlays.append(_area_overlay(
            boss_positions,
            width,
            height,
            _boss_icon(boss),
            f"{boss['name']}：HP {boss['hp']}/{boss['max_hp']}，攻击 {boss['attack']}，防御 {boss['defense']}",
            'boss',
        ))
    for player_scope in state['players'].values():
        profile = player_scope['profile']
        player_state = player_scope['player']
        character_instance = player_scope.get('character_instance', {})
        player_overlay = _overlay(
            player_state['x'],
            player_state['y'],
            width,
            height,
            character_instance.get('avatar_image') or ICONS['player'],
            f"{profile['nickname']}：第 {current_map_layer(state)} 层 ({player_state['x']}, {player_state['y']})，HP {player_state['hp']}/{player_state['max_hp']}",
            'player',
            current_map_layer(state),
        )
        player_overlay['player_uid'] = profile['player_uid']
        player_overlay['is_current_player'] = profile['player_uid'] == state['current_actor_uid']
        player_overlay['identification_level'] = int(player_state.get('identification_level', 1))
        overlays.append(player_overlay)
    return {
        'width': width,
        'height': height,
        'current_layer': current_map_layer(state),
        'total_layers': int(state['map'].get('total_layers', 1)),
        'layers': state['map'].get('layers', []),
        'background_image': map_layer_background_image(state['map'], current_map_layer(state)),
        'icons': overlays,
    }


def _tile_overlay_icon(tile: JsonDict, map_object: JsonDict) -> str:
    if tile.get('type') == 'loot_item':
        return str(tile.get('loot', {}).get('icon', 'event'))
    return str(map_object.get('icon', ICONS.get(tile.get('type'), 'event')))


def _overlay(x: int, y: int, width: int, height: int, icon: str, tooltip: str, entity_type: str, layer: int = 1) -> JsonDict:
    return {
        'x': x,
        'y': y,
        'layer': layer,
        'left_percent': ((x + 0.5) / width) * 100,
        'top_percent': ((y + 0.5) / height) * 100,
        'width_percent': (1 / width) * 100,
        'height_percent': (1 / height) * 100,
        'icon': icon,
        'tooltip': tooltip,
        'entity_type': entity_type,
    }


def _tile_overlay(tile: JsonDict, width: int, height: int, icon: str, tooltip: str, entity_type: str, layer: int = 1) -> JsonDict:
    tile_width = max(1, int(tile.get('width', 1) or 1))
    tile_height = max(1, int(tile.get('height', 1) or 1))
    return {
        'x': tile['x'],
        'y': tile['y'],
        'layer': layer,
        'left_percent': ((tile['x'] + (tile_width / 2)) / width) * 100,
        'top_percent': ((tile['y'] + (tile_height / 2)) / height) * 100,
        'width_percent': (tile_width / width) * 100,
        'height_percent': (tile_height / height) * 100,
        'icon': icon,
        'tooltip': tooltip,
        'entity_type': entity_type,
    }


def map_object_tags(map_object: JsonDict) -> list[str]:
    tags = [str(tag) for tag in map_object.get('tags', []) if str(tag)]
    if (
        map_object.get('identify_on_pass')
        or GameEvent.IDENTIFY.value in map_object.get('event_hooks', {})
    ) and '可鉴别' not in tags:
        tags.append('可鉴别')
    return tags


def _area_overlay(positions: list[JsonDict], width: int, height: int, icon: str, tooltip: str, entity_type: str) -> JsonDict:
    min_x = min(pos['x'] for pos in positions)
    max_x = max(pos['x'] for pos in positions)
    min_y = min(pos['y'] for pos in positions)
    max_y = max(pos['y'] for pos in positions)
    return {
        'x': min_x,
        'y': min_y,
        'layer': int(positions[0].get('layer', 1)),
        'left_percent': ((min_x + max_x + 1) / 2 / width) * 100,
        'top_percent': ((min_y + max_y + 1) / 2 / height) * 100,
        'width_percent': ((max_x - min_x + 1) / width) * 100,
        'height_percent': ((max_y - min_y + 1) / height) * 100,
        'icon': icon,
        'tooltip': tooltip,
        'entity_type': entity_type,
    }


def _find_item_instance(collection: list[JsonDict], instance_id: str) -> JsonDict | None:
    for item_instance in collection:
        if item_instance['instance_id'] == instance_id:
            return item_instance
    return None


def _remove_item_instance(collection: list[JsonDict], instance_id: str) -> JsonDict | None:
    for index, item_instance in enumerate(collection):
        if item_instance['instance_id'] == instance_id:
            return collection.pop(index)
    return None


def _set_item_zone(state: JsonDict, item_instance: JsonDict, zone_name: str, reason: str, emit_event: bool = True) -> None:
    previous_zone = item_instance.get('zone')
    item_instance['zone'] = zone_name
    _reconcile_item_zone_effects(state, item_instance)
    if emit_event and previous_zone != zone_name:
        dispatch_event(state, GameEvent.ITEM_ZONE_CHANGED, {
            'item_instance_id': item_instance['instance_id'],
            'definition_id': item_instance['definition_id'],
            'from_zone': previous_zone,
            'to_zone': zone_name,
            'reason': reason,
            'target_instance_id': item_instance['instance_id'],
        })


def _initialize_item_zones(state: JsonDict, emit_initial_events: bool) -> None:
    original_actor_uid = str(state['current_actor_uid'])
    for actor_uid in state['players']:
        _project_player_scope(state, actor_uid)
        for item_instance in state.get('hand', []):
            _set_item_zone(state, item_instance, 'hand', reason='initial_place', emit_event=emit_initial_events)
        for item_instance in state.get('discard_pile', []):
            _set_item_zone(state, item_instance, 'discard_pile', reason='restore_zone', emit_event=False)
        _capture_player_scope(state)
    _project_player_scope(state, original_actor_uid)


def _reconcile_item_zone_effects(state: JsonDict, item_instance: JsonDict) -> None:
    item_definition = get_item(item_instance['definition_id']) or {}
    zone_effects = item_definition.get('zone_effects', {})
    if not zone_effects:
        _refresh_zone_derived_state(state)
        return
    current_zone = item_instance.get('zone')
    active_effect_ids = set(zone_effects.get(current_zone, []))
    all_effect_ids = {effect_id for effect_ids in zone_effects.values() for effect_id in effect_ids}
    for effect_id in all_effect_ids:
        if effect_id in active_effect_ids:
            _ensure_item_zone_effect_registered(state, item_instance, item_definition, effect_id)
            continue
        remove_runtime_effect_by_source(
            state,
            definition_type='item',
            definition_id=item_definition['id'],
            effect_id=effect_id,
            source_instance_id=item_instance['instance_id'],
        )
    _refresh_zone_derived_state(state)


def _ensure_item_zone_effect_registered(
    state: JsonDict,
    item_instance: JsonDict,
    item_definition: JsonDict,
    effect_id: str,
) -> None:
    existing_effect = find_runtime_effect_by_source(
        state,
        definition_type='item',
        definition_id=item_definition['id'],
        effect_id=effect_id,
        source_instance_id=item_instance['instance_id'],
    )
    if existing_effect is not None:
        return
    runtime_effect = item_definition.get('runtime_effects', {}).get(effect_id, {})
    register_runtime_effect(state, build_runtime_effect(
        definition_type='item',
        definition_id=item_definition['id'],
        effect_id=effect_id,
        source_instance_id=item_instance['instance_id'],
        data=runtime_effect.get('initial_data', {}),
    ))


def _refresh_zone_derived_state(state: JsonDict) -> None:
    # 某些区域效果会驱动 UI 提示等派生状态；这些值应由当前激活效果统一回推。
    state['route_hint'] = DEFAULT_ROUTE_HINT
    for effect in reversed(state.get('active_effects', [])):
        route_hint = effect.get('data', {}).get('route_hint')
        if route_hint:
            state['route_hint'] = str(route_hint)
            _capture_player_scope(state)
            return
    _capture_player_scope(state)


def _build_start_log(state: JsonDict) -> str:
    member_names = [player_scope['character_instance']['name'] for player_scope in state['players'].values()]
    if len(member_names) == 1:
        return f'已使用 {member_names[0]} 开始新对局。'
    return f"房间对局开始，出战角色：{' / '.join(member_names)}。"


def _serialize_player_overview(player_scope: JsonDict) -> JsonDict:
    profile = player_scope['profile']
    player = player_scope['player']
    return {
        'player_uid': profile['player_uid'],
        'nickname': profile['nickname'],
        'seat': profile['seat'],
        'is_host': profile['is_host'],
        'hp': player['hp'],
        'max_hp': player['max_hp'],
        'identification_level': int(player.get('identification_level', 1)),
        'x': player['x'],
        'y': player['y'],
        'phase': player_scope['phase'],
        'acted_this_turn': player_scope['acted_this_turn'],
        'defeated': player_scope.get('defeated', False),
    }


def _project_player_scope(state: JsonDict, player_uid: str) -> None:
    player_scope = state['players'][player_uid]
    state['current_actor_uid'] = player_uid
    state['character_instance'] = player_scope['character_instance']
    state['player'] = player_scope['player']
    state['discard_pile'] = player_scope['discard_pile']
    state['hand'] = player_scope['hand']
    state['active_effects'] = player_scope['active_effects']
    state['pending_die'] = player_scope['pending_die']
    state['pending_dice'] = player_scope.get('pending_dice')
    state['phase'] = player_scope['phase']
    state['has_played_item'] = player_scope['has_played_item']
    state['route_hint'] = player_scope['route_hint']
    state['acted_this_turn'] = player_scope['acted_this_turn']


def _capture_player_scope(state: JsonDict) -> None:
    player_scope = state['players'][str(state['current_actor_uid'])]
    player_scope['pending_die'] = state['pending_die']
    player_scope['pending_dice'] = state.get('pending_dice')
    player_scope['phase'] = state['phase']
    player_scope['has_played_item'] = state['has_played_item']
    player_scope['route_hint'] = state['route_hint']
    player_scope['acted_this_turn'] = state.get('acted_this_turn', False)
    player_scope['defeated'] = state['player']['hp'] <= 0


def _all_active_players_completed(state: JsonDict) -> bool:
    for player_scope in state['players'].values():
        if player_scope.get('defeated', False) or player_scope['player']['hp'] <= 0:
            continue
        if not player_scope.get('acted_this_turn', False):
            return False
    return True


def _all_players_defeated(state: JsonDict) -> bool:
    for player_scope in state['players'].values():
        if player_scope['player']['hp'] > 0 and not player_scope.get('defeated', False):
            return False
    return True


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuleValidationError(message)
