from typing import TYPE_CHECKING

from app.content.items.common import add_item_log, add_item_popup, manhattan
from app.engine.effects import build_runtime_effect, register_runtime_effect, remove_runtime_effect
from app.engine.events import GameEvent
from app.errors import RuleValidationError

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


DIRECTIONS = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _current_layer(state: dict) -> int:
    return int(state.get('map', {}).get('current_layer', 1))


def _current_layer_dimensions(state: dict) -> tuple[int, int]:
    current_layer = _current_layer(state)
    for layer_meta in state.get('map', {}).get('layers', []):
        if int(layer_meta.get('layer', 1)) == current_layer:
            return int(layer_meta.get('width', 0)), int(layer_meta.get('height', 0))
    return int(state.get('map', {}).get('width', 0)), int(state.get('map', {}).get('height', 0))


def _nearby_free_tile(state: dict) -> tuple[int, int] | None:
    actor = state['player']
    width, height = _current_layer_dimensions(state)
    occupied = {
        (monster['x'], monster['y'])
        for monster in state['map'].get('monsters', [])
        if monster.get('hp', 0) > 0 and not monster.get('captured') and int(monster.get('layer', 1)) == _current_layer(state)
    }
    boss_positions = {
        (pos['x'], pos['y'])
        for pos in state['map'].get('boss', {}).get('positions', [])
        if int(pos.get('layer', 1)) == _current_layer(state)
    }
    blocked = {
        (tile['x'], tile['y'])
        for tile in state['map'].get('tiles', [])
        if int(tile.get('layer', 1)) == _current_layer(state)
        and tile.get('type') in {'wall', 'boss_tile'}
    }
    for dx, dy in DIRECTIONS:
        x = actor['x'] + dx
        y = actor['y'] + dy
        if x < 0 or y < 0 or x >= width or y >= height:
            continue
        if (x, y) in occupied or (x, y) in boss_positions or (x, y) in blocked:
            continue
        return x, y
    return None


def containment_jar_played(context: 'EventContext') -> None:
    actor = context.state['player']
    current_layer = _current_layer(context.state)
    candidates = [
        (manhattan(actor['x'], actor['y'], monster['x'], monster['y']), monster)
        for monster in context.state['map'].get('monsters', [])
        if monster.get('hp', 0) > 0
        and not monster.get('captured')
        and int(monster.get('layer', 1)) == current_layer
    ]
    candidates = [item for item in candidates if item[0] <= 2]
    if not candidates:
        raise RuleValidationError('附近没有可收容的非 Boss 敌人。')
    candidates.sort(key=lambda item: (item[0], item[1]['id']))
    monster = candidates[0][1]
    monster['captured'] = True
    monster['stored_x'] = monster['x']
    monster['stored_y'] = monster['y']
    monster['x'] = -100
    monster['y'] = -100
    release_turn = int(context.state.get('turn', 1)) + 10
    register_runtime_effect(context.state, build_runtime_effect(
        definition_id='containment_jar',
        effect_id='release_captured_enemy',
        source_instance_id=str(context.payload['item_instance_id']),
        data={'enemy_id': monster['id'], 'release_turn': release_turn},
    ))
    message = f'临时收容罐收容了 {monster["name"]}，将在第 {release_turn} 回合重新释放。'
    add_item_log(context, message)
    add_item_popup(context, '临时收容罐', message, '/static/images/item/containment_jar.webp')
    context.payload['resolved'] = True


def release_captured_enemy(context: 'EventContext') -> None:
    effect = next(
        (item for item in context.state.get('active_effects', []) if item.get('instance_id') == context.instance_id),
        None,
    )
    if effect is None:
        return
    data = effect.get('data', {})
    if int(context.state.get('turn', 1)) < int(data.get('release_turn', 0)):
        return
    monster = next((item for item in context.state['map'].get('monsters', []) if item.get('id') == data.get('enemy_id')), None)
    if monster is None:
        remove_runtime_effect(context.state, str(context.instance_id))
        return
    tile = _nearby_free_tile(context.state)
    if tile is None:
        return
    monster['captured'] = False
    monster['x'], monster['y'] = tile
    monster['layer'] = _current_layer(context.state)
    message = f'临时收容罐释放了 {monster["name"]}。'
    add_item_log(context, message)
    add_item_popup(context, '临时收容罐', message, '/static/images/item/containment_jar.webp')
    remove_runtime_effect(context.state, str(context.instance_id))


ITEM = {
    'id': 'containment_jar',
    'name': '临时收容罐',
    'type': 'utility',
    'rarity': 'ur',
    'icon': '/static/images/item/containment_jar.webp',
    'description': '主动使用：将附近最近的一个非 Boss 敌人收入道具栏，10 回合后在附近释放。',
    'consume_on_play': False,
    'hidden_from_build': True,
    'tags': ['专属'],
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: containment_jar_played,
    },
    'runtime_effects': {
        'release_captured_enemy': {
            'event_hooks': {
                GameEvent.TURN_BEGIN.value: release_captured_enemy,
            },
        },
    },
}
