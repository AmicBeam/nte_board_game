from typing import TYPE_CHECKING

from app.engine.damage import build_damage_package, resolve_damage_package
from app.engine.events import GameEvent
from app.utils.logger import get_logger

logger = get_logger('nte.items')
LOG_LIMIT = 18

if TYPE_CHECKING:
    from app.engine.event_context import EventContext, JsonDict


def add_item_log(context: 'EventContext', message: str) -> None:
    context.state.setdefault('log', [])
    context.state['log'].insert(0, message)
    del context.state['log'][LOG_LIMIT:]
    logger.info(message)


def manhattan(x1: int, y1: int, x2: int, y2: int) -> int:
    return abs(x1 - x2) + abs(y1 - y2)


def find_nearest_enemy(state: 'JsonDict', max_distance: int) -> dict | None:
    actor = state['player']
    candidates = []
    for monster in state['map']['monsters']:
        if monster['hp'] <= 0:
            continue
        distance = manhattan(actor['x'], actor['y'], monster['x'], monster['y'])
        if distance <= max_distance:
            candidates.append((distance, monster))
    boss = state['map']['boss']
    if boss['hp'] > 0:
        distance = min(manhattan(actor['x'], actor['y'], pos['x'], pos['y']) for pos in boss['positions'])
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
        if target['kind'] == 'boss':
            context.state['status'] = 'victory'
            context.state['phase'] = 'victory'
            add_item_log(context, 'Abyss Core 被击破，获得胜利。')
            context.emit(GameEvent.RUN_VICTORY, {'target': 'boss', 'source': source})
