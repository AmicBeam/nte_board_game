from typing import TYPE_CHECKING

from app.engine.damage import build_damage_package, resolve_damage_package
from app.engine.enemy_drop import spawn_enemy_drop
from app.engine.events import GameEvent
from app.utils.logger import get_logger

logger = get_logger('nte.items')
LOG_LIMIT = 18
ACTION_QUEUE_KEY = '_action_queue'

if TYPE_CHECKING:
    from app.engine.event_context import EventContext, JsonDict


def get_item_player_state(context: 'EventContext') -> dict:
    return context.state['player']


def get_item_actor_nickname(context: 'EventContext') -> str:
    return str(context.payload.get('actor_nickname', '当前玩家'))


def add_item_log(context: 'EventContext', message: str) -> None:
    context.state.setdefault('log', [])
    actor_nickname = get_item_actor_nickname(context)
    context.state['log'].insert(0, f'[{actor_nickname}] {message}')
    del context.state['log'][LOG_LIMIT:]
    logger.info('[%s] %s', actor_nickname, message)


def add_action_step(state: dict, step: dict) -> None:
    state.setdefault(ACTION_QUEUE_KEY, []).append(step)


def add_item_popup(context: 'EventContext', title: str, message: str, icon: str = 'event') -> None:
    add_action_step(context.state, {
        'type': 'popup',
        'title': title,
        'message': message,
        'icon': icon,
    })


def add_fons(state: dict, amount: int) -> int:
    player_state = state.setdefault('player', {})
    player_state['fons_amount'] = int(player_state.get('fons_amount', 0)) + int(amount)
    for item in state.get('hand', []):
        if item.get('definition_id') == 'fons':
            item['amount'] = int(player_state['fons_amount'])
            break
    return int(player_state['fons_amount'])


def manhattan(x1: int, y1: int, x2: int, y2: int) -> int:
    return abs(x1 - x2) + abs(y1 - y2)


def find_nearest_enemy(state: 'JsonDict', max_distance: int) -> dict | None:
    actor = state['player']
    current_layer = int(state['map'].get('current_layer', 1))
    candidates = []
    for monster in state['map']['monsters']:
        if monster['hp'] <= 0 or int(monster.get('layer', 1)) != current_layer:
            continue
        distance = manhattan(actor['x'], actor['y'], monster['x'], monster['y'])
        if distance <= max_distance:
            candidates.append((distance, monster))
    boss = state['map']['boss']
    boss_positions = [pos for pos in boss['positions'] if int(pos.get('layer', 1)) == current_layer]
    if boss['hp'] > 0 and boss_positions:
        distance = min(manhattan(actor['x'], actor['y'], pos['x'], pos['y']) for pos in boss_positions)
        if distance <= max_distance:
            candidates.append((distance, boss))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]['id']))
    return candidates[0][1]


def apply_direct_damage(context: 'EventContext', target: dict, damage: int, source: str) -> None:
    damage_result = resolve_damage_package(context.state, build_damage_package(
        source_name=source,
        source_id=str(context.payload.get('item_instance_id', source)),
        source_type='item',
        target_type='enemy',
        target_id=str(target['id']),
        target_name=str(target['name']),
        amount=damage,
        attack_kind='直伤',
        allow_block=False,
    ))
    context.emit(GameEvent.DIRECT_ATTACK_RESOLVED, {
        'enemy_id': target['id'],
        'enemy_name': target['name'],
        'outgoing_damage': damage_result['final_damage'],
        'source': source,
    })
    if damage_result['target_defeated']:
        add_item_log(context, f"{target['name']} 被 {source} 击毁。")
        spawn_enemy_drop(context.state, target)
        if target['kind'] == 'boss':
            context.state['status'] = 'victory'
            context.state['phase'] = 'victory'
            add_item_log(context, 'Abyss Core 被击破，获得胜利。')
            context.emit(GameEvent.RUN_VICTORY, {'target': 'boss', 'source': source})
