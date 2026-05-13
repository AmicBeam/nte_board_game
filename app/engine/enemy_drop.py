from app.content.map_objects.common import ACTION_QUEUE_KEY, choose_loot_from_table
from app.engine.event_context import JsonDict

LOG_LIMIT = 18


def spawn_enemy_drop(state: JsonDict, enemy: JsonDict) -> None:
    if enemy.get('drop_resolved'):
        return
    table_ref = enemy.get('drop_table_id')
    if not table_ref:
        table_ref = state.get('map', {}).get('boss_drop_table_id' if enemy.get('kind') == 'boss' else 'enemy_drop_table_id')
    if not table_ref:
        enemy['drop_resolved'] = True
        return
    loot = choose_loot_from_table(state, table_ref)
    if loot is None:
        enemy['drop_resolved'] = True
        return
    layer, x, y = _enemy_drop_position(state, enemy)
    tile = {
        'layer': layer,
        'x': x,
        'y': y,
        'type': 'loot_item',
        'object_id': 'loot_item',
        'loot': loot,
        'spawn_id': f"enemy_drop_{enemy['id']}",
    }
    state['map'].setdefault('tiles', []).append(tile)
    enemy['drop_resolved'] = True
    _add_log(state, f"{enemy['name']} 掉落了 {loot.get('name', '战利品')}。")
    state.setdefault(ACTION_QUEUE_KEY, []).append({
        'type': 'tile_update',
        'layer': layer,
        'x': x,
        'y': y,
        'tile': dict(tile),
        'display_type': 'loot_item',
    })


def _enemy_drop_position(state: JsonDict, enemy: JsonDict) -> tuple[int, int, int]:
    if enemy.get('kind') == 'boss':
        positions = [pos for pos in enemy.get('positions', []) if _is_on_current_layer(state, pos)]
        if not positions:
            positions = list(enemy.get('positions', []))
        if positions:
            position = positions[0]
            return int(position.get('layer', _current_map_layer(state))), int(position['x']), int(position['y'])
    return int(enemy.get('layer', _current_map_layer(state))), int(enemy.get('x', 0)), int(enemy.get('y', 0))


def _current_map_layer(state: JsonDict) -> int:
    return int(state.get('map', {}).get('current_layer', 1))


def _is_on_current_layer(state: JsonDict, entity: JsonDict) -> bool:
    return int(entity.get('layer', 1)) == _current_map_layer(state)


def _add_log(state: JsonDict, message: str) -> None:
    state.setdefault('log', []).insert(0, message)
    del state['log'][LOG_LIMIT:]
