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
    load_characters,
    load_items,
    resolve_map_object_id,
)
from app.dao import clear_run, get_build, get_current_room, get_run, list_room_members, update_room_status, upsert_build, upsert_run
from app.db import atomic_transaction
from app.engine.damage import PLAYER_TARGET_ID, build_damage_package, resolve_damage_package
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
from app.engine.runtime import (
    build_character_instance,
    build_item_instances,
    serialize_item_definition,
    serialize_item_instance,
)
from app.errors import RuleValidationError
from app.models import Player, Room
from app.utils.logger import get_logger

DEFAULT_ITEM_COUNT = 6
LOG_LIMIT = 18
DEFAULT_ROUTE_HINT = '前往地图底层，靠近 Boss 区域并多回合作战。'
DIRECTIONS = {
    'up': (0, -1),
    'down': (0, 1),
    'left': (-1, 0),
    'right': (1, 0),
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

logger = get_logger('nte.game_service')


def get_catalog_payload(player: Player) -> JsonDict:
    return {
        'characters': load_characters(),
        'items': [serialize_item_definition(item_definition) for item_definition in load_items()],
        'build_size': DEFAULT_ITEM_COUNT,
        'saved_build': get_build(player),
    }


def save_build(player: Player, character_id: str, item_ids: list[str]) -> JsonDict | None:
    _ensure(get_character(character_id) is not None, '角色不存在。')
    _ensure(len(item_ids) == DEFAULT_ITEM_COUNT, f'必须选择 {DEFAULT_ITEM_COUNT} 个道具。')
    for item_id in item_ids:
        _ensure(get_item(item_id) is not None, f'未知道具：{item_id}')
    with atomic_transaction():
        upsert_build(player, character_id, item_ids)
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


def play_item(player: Player, item_instance_id: str) -> JsonDict:
    with atomic_transaction():
        state = _load_state(player)
        _ensure(state['phase'] == 'action', '当前不是行动阶段。')
        _ensure(not state['has_played_item'], '每回合只能使用 1 个道具。')
        item_instance = _find_item_instance(state['hand'], item_instance_id)
        _ensure(item_instance is not None, '该道具实例不在手牌中。')
        item = get_item(item_instance['definition_id'])
        _ensure(item is not None, '道具定义不存在。')
        event_payload = {
            'item_id': item['id'],
            'item_name': item['name'],
            'item_instance_id': item_instance_id,
            'target_instance_id': item_instance_id,
            'resolved': False,
        }

        _remove_item_instance(state['hand'], item_instance_id)
        state['discard_pile'].append(item_instance)
        _set_item_zone(state, item_instance, 'discard_pile', reason='play_item')
        state['has_played_item'] = True
        result_payload = dispatch_event(state, GameEvent.ITEM_PLAYED, event_payload)
        _ensure(result_payload.get('resolved') is True, '该道具未声明可执行的事件效果。')
        return _save_and_serialize(player, state)


def move_player(player: Player, direction: str) -> JsonDict:
    with atomic_transaction():
        state = _load_state(player)
        _ensure(state['phase'] in {'action', 'movement'}, '当前不能移动。')
        _ensure(state['pending_die'] is not None, '请先掷骰。')
        _ensure(direction in DIRECTIONS, '方向非法。')

        actor = state['player']
        steps_remaining = int(state['pending_die']) + sum_runtime_effect_bonus(state, 'move_bonus')
        steps_remaining += consume_runtime_effect_bonus(state, 'stored_next_turn_move', 'consume_on_move')
        move_phase_payload = dispatch_event(
            state,
            GameEvent.MOVE_PHASE_BEGIN,
            {
                'direction': direction,
                'steps': steps_remaining,
            },
            default_handler=build_scoped_default_handler(state, _default_move_phase_begin),
        )
        steps_remaining = max(0, int(move_phase_payload.get('steps', steps_remaining)))
        active_direction = str(move_phase_payload.get('direction', direction))
        loop_counter = 0

        while steps_remaining > 0:
            loop_counter += 1
            if loop_counter > MOVE_STEP_LIMIT:
                add_log(state, '移动循环达到安全上限，已强制终止本次移动。')
                logger.error('move loop exceeded limit player_uid=%s', player.player_uid)
                break
            next_x, next_y = step_position(actor['x'], actor['y'], active_direction)
            block_reason = get_block_reason(state, next_x, next_y)
            if block_reason:
                add_log(state, f'移动停止：{block_reason}')
                break
            actor['x'], actor['y'] = next_x, next_y
            steps_remaining -= 1
            add_log(state, f"移动至 ({actor['x']}, {actor['y']})。")
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
    member_order = [member.player.player_uid for member in room_members]
    _ensure(member_order, '初始化配置失败。')
    players: dict[str, JsonDict] = {}
    for member in room_members:
        build = builds_by_player_uid[member.player.player_uid]
        character_definition = deepcopy(get_character(build['character_id']))
        _ensure(character_definition is not None, '初始化配置失败。')
        item_instances = build_item_instances(build['item_ids'], turn=1)
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
                'x': game_map['start']['x'],
                'y': game_map['start']['y'],
                'max_hp': character_instance['max_hp'],
                'hp': character_instance['max_hp'],
                'attack': character_instance['attack'],
                'defense': character_instance['defense'],
                'keys': 0,
            },
            'discard_pile': [],
            'hand': item_instances,
            'active_effects': [],
            'pending_die': None,
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
    current_profile = payload['players'][payload['current_actor_uid']]['profile']
    payload['computed_stats'] = {
        'attack': current_attack(state),
        'defense': current_defense(state),
    }
    payload['board'] = build_board_overlay(state)
    payload['available_directions'] = list(DIRECTIONS.keys())
    payload['hand_details'] = [item for item in (serialize_item_instance(item_instance) for item_instance in state['hand']) if item is not None]
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
    return _save_and_serialize_for_room(room, state)


def _save_and_serialize_for_room(room: Room, state: JsonDict) -> JsonDict:
    _capture_player_scope(state)
    validate_state(state)
    _persist_room_snapshot(room, state)
    return serialize_snapshot(state)


def validate_state(state: JsonDict) -> None:
    required_top_keys = {'turn', 'status', 'room', 'players', 'current_actor_uid', 'phase', 'character_instance', 'player', 'map', 'discard_pile', 'hand', 'active_effects', 'pending_die', 'has_played_item', 'route_hint', 'log'}
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
    _project_player_scope(normalized, str(normalized['current_actor_uid']))
    _initialize_item_zones(normalized, emit_initial_events=False)
    return normalized


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


def step_position(x: int, y: int, direction: str) -> tuple[int, int]:
    dx, dy = DIRECTIONS[direction]
    return x + dx, y + dy


def tile_at(state: JsonDict, x: int, y: int) -> JsonDict | None:
    for tile in state['map']['tiles']:
        if tile['x'] == x and tile['y'] == y:
            return tile
    return None


def monster_at(state: JsonDict, x: int, y: int) -> JsonDict | None:
    for monster in state['map']['monsters']:
        if monster['hp'] > 0 and monster['x'] == x and monster['y'] == y:
            return monster
    return None


def boss_on_tile(state: JsonDict, x: int, y: int) -> bool:
    boss = state['map']['boss']
    return boss['hp'] > 0 and any(pos['x'] == x and pos['y'] == y for pos in boss['positions'])


def get_block_reason(state: JsonDict, x: int, y: int) -> str | None:
    if x < 0 or y < 0 or x >= state['map']['width'] or y >= state['map']['height']:
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
    if is_adjacent_to_boss(state, actor['x'], actor['y']):
        battle_end_payload = dispatch_event(
            state,
            GameEvent.DIRECT_ATTACK,
            _build_direct_attack_payload(state['map']['boss'], attack_kind='反击'),
            default_handler=build_scoped_default_handler(state, _default_direct_attack),
        )
        if state['map']['boss']['hp'] <= 0:
            state['status'] = 'victory'
            state['phase'] = 'victory'
            battle_end_payload['status'] = state['status']
            add_log(state, 'Abyss Core 被击破，获得胜利。')
            dispatch_event(state, GameEvent.RUN_VICTORY, {'target': 'boss'})
    else:
        adjacent = []
        ranged = []
        for monster in state['map']['monsters']:
            if monster['hp'] <= 0:
                continue
            distance = manhattan(actor['x'], actor['y'], monster['x'], monster['y'])
            if distance == 1:
                adjacent.append(monster)
            elif distance <= monster['range']:
                ranged.append(monster)
        if adjacent:
            target = sorted(adjacent, key=lambda m: (m['hp'], m['id']))[0]
            battle_end_payload = dispatch_event(
                state,
                GameEvent.DIRECT_ATTACK,
                _build_direct_attack_payload(target, attack_kind='反击'),
                default_handler=build_scoped_default_handler(state, _default_direct_attack),
            )
        elif ranged:
            target = sorted(ranged, key=lambda m: (manhattan(actor['x'], actor['y'], m['x'], m['y']), m['id']))[0]
            battle_end_payload = dispatch_event(
                state,
                GameEvent.RANGED_ATTACK,
                _build_enemy_attack_payload(target),
                default_handler=build_scoped_default_handler(state, _default_ranged_attack),
            )
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
    outgoing = max(1, current_attack(state) - enemy['defense'])
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
    context.payload['incoming_damage'] = incoming_result['final_damage']
    dispatch_event(state, GameEvent.DIRECT_ATTACK_RESOLVED, {
        'enemy_id': enemy['id'],
        'enemy_name': enemy['name'],
        'incoming_damage': incoming_result['final_damage'],
    })


def _default_ranged_attack(context: EventContext, state: JsonDict) -> None:
    enemy = _find_enemy_by_id(state, str(context.payload['enemy_id']))
    _ensure(enemy is not None, f"未找到远程目标：{context.payload['enemy_id']}")
    actor_profile = state['players'][str(state['current_actor_uid'])]['profile']
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
    context.payload['incoming_damage'] = damage_result['final_damage']
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


def current_attack(state: JsonDict) -> int:
    _project_player_scope(state, str(state['current_actor_uid']))
    return state['player']['attack'] + sum_runtime_effect_bonus(state, 'attack_bonus')


def current_defense(state: JsonDict) -> int:
    _project_player_scope(state, str(state['current_actor_uid']))
    return state['player']['defense'] + sum_runtime_effect_bonus(state, 'defense_bonus')


def is_adjacent_to_boss(state: JsonDict, x: int, y: int) -> bool:
    return any(manhattan(x, y, pos['x'], pos['y']) == 1 for pos in state['map']['boss']['positions'] if state['map']['boss']['hp'] > 0)


def manhattan(x1: int, y1: int, x2: int, y2: int) -> int:
    return abs(x1 - x2) + abs(y1 - y2)

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
            continue
        _project_player_scope(state, actor_uid)
        state['pending_die'] = None
        state['phase'] = 'dice'
        state['has_played_item'] = False
        state['route_hint'] = DEFAULT_ROUTE_HINT
        state['acted_this_turn'] = False
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
    }
    if event_name == GameEvent.TURN_BEGIN:
        payload.pop('die')
    return payload


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
    state['pending_die'] = random.randint(1, 6)
    add_log(state, f"第 {state['turn']} 回合自动掷出 {state['pending_die']} 点。")
    context.payload['die'] = state['pending_die']


def _default_action_phase_begin(context: EventContext, state: JsonDict) -> None:
    # 行动阶段默认会切换 phase 并重置本回合道具使用标记。
    state['phase'] = 'action'
    state['has_played_item'] = False
    context.payload['die'] = state['pending_die']


def _default_turn_begin(context: EventContext, state: JsonDict) -> None:
    context.payload['turn'] = state['turn']
    add_log(state, f"第 {state['turn']} 回合开始。")


def _default_move_phase_begin(context: EventContext, state: JsonDict) -> None:
    state['phase'] = 'movement'
    add_log(state, f"开始向 {context.payload.get('direction', 'unknown')} 移动，共 {context.payload.get('steps', 0)} 步。")


def build_board_overlay(state: JsonDict) -> JsonDict:
    width = state['map']['width']
    height = state['map']['height']
    overlays = []
    for tile in state['map']['tiles']:
        display_type = tile['type']
        if tile['type'] == 'chest' and tile.get('opened'):
            display_type = 'floor'
        if tile['type'] == 'event' and tile.get('resolved'):
            display_type = 'floor'
        if tile['type'] == 'door' and not tile.get('locked', True):
            display_type = 'floor'
        if display_type != 'floor':
            object_id = resolve_map_object_id(tile)
            map_object = get_map_object(object_id) or {}
            overlays.append(_overlay(
                tile['x'],
                tile['y'],
                width,
                height,
                map_object.get('icon', ICONS.get(tile['type'], 'event')),
                get_map_object_tooltip(tile),
                tile['type'],
            ))
    for monster in state['map']['monsters']:
        if monster['hp'] > 0:
            overlays.append(_overlay(monster['x'], monster['y'], width, height, ICONS['monster'], f"{monster['name']}：HP {monster['hp']}/{monster['max_hp']}，攻击 {monster['attack']}，射程 {monster['range']}", 'monster'))
    boss = state['map']['boss']
    if boss['hp'] > 0:
        for pos in boss['positions']:
            overlays.append(_overlay(pos['x'], pos['y'], width, height, ICONS['boss'], f"{boss['name']}：HP {boss['hp']}/{boss['max_hp']}，攻击 {boss['attack']}", 'boss'))
    for player_scope in state['players'].values():
        profile = player_scope['profile']
        player_state = player_scope['player']
        overlays.append(_overlay(
            player_state['x'],
            player_state['y'],
            width,
            height,
            ICONS['player'],
            f"{profile['nickname']}：({player_state['x']}, {player_state['y']})，HP {player_state['hp']}/{player_state['max_hp']}",
            'player',
        ))
    return {
        'width': width,
        'height': height,
        'background_image': state['map']['background_image'],
        'icons': overlays,
    }


def _overlay(x: int, y: int, width: int, height: int, icon: str, tooltip: str, entity_type: str) -> JsonDict:
    return {
        'x': x,
        'y': y,
        'left_percent': ((x + 0.5) / width) * 100,
        'top_percent': ((y + 0.5) / height) * 100,
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
    state['phase'] = player_scope['phase']
    state['has_played_item'] = player_scope['has_played_item']
    state['route_hint'] = player_scope['route_hint']
    state['acted_this_turn'] = player_scope['acted_this_turn']


def _capture_player_scope(state: JsonDict) -> None:
    player_scope = state['players'][str(state['current_actor_uid'])]
    player_scope['pending_die'] = state['pending_die']
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
