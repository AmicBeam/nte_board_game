import importlib
import json
import pkgutil
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

from app.content import characters, items, map_objects, maps


def _load_from_package(package: ModuleType, attribute_name: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for module_info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f'{package.__name__}.{module_info.name}')
        payload = getattr(module, attribute_name, None)
        if payload is not None:
            results.append(payload)
    return results


def load_characters() -> list[dict[str, Any]]:
    return sorted(_load_from_package(characters, 'CHARACTER'), key=lambda item: item['id'])


def load_items() -> list[dict[str, Any]]:
    return sorted(_load_from_package(items, 'ITEM'), key=lambda item: item['id'])


def load_maps() -> list[dict[str, Any]]:
    return sorted(_load_json_maps(), key=lambda item: item['id'])


def _load_json_maps() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for package_path in maps.__path__:
        for map_path in sorted(Path(package_path).glob('*.json')):
            with map_path.open(encoding='utf-8') as file:
                payload = json.load(file)
            if isinstance(payload, dict):
                results.append(_normalize_map_payload(payload))
    return results


def _normalize_map_payload(payload: dict[str, Any]) -> dict[str, Any]:
    _reject_map_icon_fields(payload, str(payload.get('id', '<unknown>')))
    normalized = deepcopy(payload)
    if _is_compact_tile_layers(normalized.get('tiles')):
        expansion = _expand_compact_tile_layers(normalized)
        _apply_hidden_room_zones(expansion)
        normalized['tiles'] = expansion['tiles']
        normalized['layers'] = expansion['layers']
        normalized['entries'] = expansion['entries']
        normalized['total_layers'] = len(expansion['layers'])
        normalized['hidden_cells'] = expansion['hidden_cells']
        if expansion['layers']:
            first_layer = expansion['layers'][0]
            normalized['width'] = first_layer['width']
            normalized['height'] = first_layer['height']
        if expansion['entries']:
            normalized['current_layer'] = expansion['entries'][0]['layer']
        normalized['monsters'] = _expand_monster_spawns(normalized.get('monsters', []), expansion['monster_spawns'])
        if expansion['boss_positions']:
            normalized.setdefault('boss', {})['positions'] = expansion['boss_positions']
    return normalized


def _reject_map_icon_fields(value: Any, map_id: str, path: str = '$') -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f'{path}.{key}'
            if key == 'icon':
                raise ValueError(f'地图 JSON 不允许配置 icon：{map_id} {child_path}')
            _reject_map_icon_fields(child, map_id, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_map_icon_fields(child, map_id, f'{path}[{index}]')


def _is_compact_tile_layers(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(layer, list) for layer in value)
        and any(isinstance(row, str) for layer in value for row in layer)
    )


def _expand_compact_tile_layers(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    legend = payload.get('legend', {})
    if not isinstance(legend, dict):
        return {'tiles': [], 'monster_spawns': [], 'boss_positions': [], 'entries': [], 'layers': []}
    expanded_tiles: list[dict[str, Any]] = []
    monster_spawns: list[dict[str, Any]] = []
    boss_positions: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    layers: list[dict[str, Any]] = []
    for layer_index, rows in enumerate(payload.get('tiles', []), start=1):
        if not isinstance(rows, list):
            continue
        row_widths = [len(row) for row in rows if isinstance(row, str)]
        layers.append({
            'layer': layer_index,
            'width': max(row_widths, default=0),
            'height': len(rows),
        })
        for y, row in enumerate(rows):
            if not isinstance(row, str):
                continue
            for x, symbol in enumerate(row):
                tile_definition = legend.get(symbol)
                if not isinstance(tile_definition, dict):
                    continue
                tile = deepcopy(tile_definition)
                tile_type = str(tile.get('type', 'floor'))
                if tile_type == 'floor':
                    continue
                if tile_type == 'entry':
                    entries.append({'layer': layer_index, 'x': x, 'y': y})
                    continue
                if tile_type == 'monster':
                    if tile.get('kind') == 'boss':
                        boss_positions.append({'layer': layer_index, 'x': x, 'y': y})
                        expanded_tiles.append({
                            'type': 'boss_tile',
                            'object_id': 'boss_tile',
                            'layer': layer_index,
                            'x': x,
                            'y': y,
                        })
                    else:
                        tile['layer'] = layer_index
                        tile['x'] = x
                        tile['y'] = y
                        monster_spawns.append(tile)
                    continue
                tile['type'] = tile_type
                tile.setdefault('object_id', tile_type)
                tile['layer'] = layer_index
                tile['x'] = x
                tile['y'] = y
                expanded_tiles.append(tile)
    return {
        'tiles': expanded_tiles,
        'monster_spawns': monster_spawns,
        'boss_positions': boss_positions,
        'entries': entries,
        'layers': layers,
        'hidden_cells': [],
    }


def _apply_hidden_room_zones(expansion: dict[str, list[dict[str, Any]]]) -> None:
    hidden_cells = _infer_hidden_room_cells(
        expansion.get('layers', []),
        expansion.get('tiles', []),
        expansion.get('entries', []),
    )
    if not hidden_cells:
        expansion['hidden_cells'] = []
        return

    expansion['hidden_cells'] = hidden_cells
    hidden_zone_by_cell = {
        (int(cell['layer']), int(cell['x']), int(cell['y'])): str(cell['hidden_zone'])
        for cell in hidden_cells
    }

    for tile in expansion.get('tiles', []):
        hidden_zone = _resolve_hidden_zone_for_footprint(tile, hidden_zone_by_cell)
        if hidden_zone:
            tile['hidden_zone'] = hidden_zone

    for monster in expansion.get('monster_spawns', []):
        hidden_zone = hidden_zone_by_cell.get((
            int(monster.get('layer', 1)),
            int(monster.get('x', 0)),
            int(monster.get('y', 0)),
        ))
        if hidden_zone:
            monster['hidden_zone'] = hidden_zone

    for position in expansion.get('boss_positions', []):
        hidden_zone = hidden_zone_by_cell.get((
            int(position.get('layer', 1)),
            int(position.get('x', 0)),
            int(position.get('y', 0)),
        ))
        if hidden_zone:
            position['hidden_zone'] = hidden_zone


def _infer_hidden_room_cells(
    layers: list[dict[str, Any]],
    tiles: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hidden_cells: list[dict[str, Any]] = []

    for layer in layers:
        layer_id = int(layer.get('layer', 1))
        width = max(0, int(layer.get('width', 0) or 0))
        height = max(0, int(layer.get('height', 0) or 0))
        if width <= 0 or height <= 0:
            continue

        blockers = _hidden_room_blockers_for_layer(layer_id, tiles)
        hidden_doors = [
            tile
            for tile in tiles
            if int(tile.get('layer', 1)) == layer_id and str(tile.get('object_id') or tile.get('type') or '') == 'hidden_door'
        ]
        if not hidden_doors:
            continue
        layer_entries = [
            (int(entry.get('x', 0)), int(entry.get('y', 0)))
            for entry in entries
            if int(entry.get('layer', 1)) == layer_id
        ]
        queue = [
            (entry_x, entry_y)
            for entry_x, entry_y in layer_entries
            if 0 <= entry_x < width and 0 <= entry_y < height and (entry_x, entry_y) not in blockers
        ]
        if not queue:
            continue

        seen = {(x, y) for x, y in queue}
        visible_cells: set[tuple[int, int]] = set()
        while queue:
            x, y = queue.pop(0)
            visible_cells.add((x, y))
            for next_x, next_y in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (
                    next_x < 0
                    or next_y < 0
                    or next_x >= width
                    or next_y >= height
                    or (next_x, next_y) in blockers
                    or (next_x, next_y) in seen
                ):
                    continue
                seen.add((next_x, next_y))
                queue.append((next_x, next_y))

        component_cache: dict[tuple[int, int], list[tuple[int, int]]] = {}
        hidden_components: list[list[tuple[int, int]]] = []
        for door in hidden_doors:
            door_x = int(door.get('x', 0))
            door_y = int(door.get('y', 0))
            for next_x, next_y in ((door_x + 1, door_y), (door_x - 1, door_y), (door_x, door_y + 1), (door_x, door_y - 1)):
                if (
                    next_x < 0
                    or next_y < 0
                    or next_x >= width
                    or next_y >= height
                    or (next_x, next_y) in blockers
                ):
                    continue
                component = component_cache.get((next_x, next_y))
                if component is None:
                    component = _collect_hidden_component(next_x, next_y, width, height, blockers)
                    for cell in component:
                        component_cache[cell] = component
                if any(cell in visible_cells for cell in component):
                    continue
                if component not in hidden_components:
                    hidden_components.append(component)

        for index, component in enumerate(hidden_components, start=1):
            hidden_zone = f'layer_{layer_id}_hidden_{index}'
            for x, y in component:
                hidden_cells.append({
                    'layer': layer_id,
                    'x': x,
                    'y': y,
                    'hidden_zone': hidden_zone,
                })

    return hidden_cells


def _hidden_room_blockers_for_layer(layer_id: int, tiles: list[dict[str, Any]]) -> set[tuple[int, int]]:
    blockers: set[tuple[int, int]] = set()
    for tile in tiles:
        if int(tile.get('layer', 1)) != layer_id:
            continue
        if str(tile.get('object_id') or tile.get('type') or '') not in {'wall', 'hidden_door'}:
            continue
        width = max(1, int(tile.get('width', 1) or 1))
        height = max(1, int(tile.get('height', 1) or 1))
        start_x = int(tile.get('x', 0))
        start_y = int(tile.get('y', 0))
        for offset_y in range(height):
            for offset_x in range(width):
                blockers.add((start_x + offset_x, start_y + offset_y))
    return blockers


def _collect_hidden_component(
    start_x: int,
    start_y: int,
    width: int,
    height: int,
    blockers: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    component: list[tuple[int, int]] = []
    queue = [(start_x, start_y)]
    seen = {(start_x, start_y)}
    while queue:
        x, y = queue.pop(0)
        if (x, y) in blockers:
            continue
        component.append((x, y))
        for next_x, next_y in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (
                next_x < 0
                or next_y < 0
                or next_x >= width
                or next_y >= height
                or (next_x, next_y) in blockers
                or (next_x, next_y) in seen
            ):
                continue
            seen.add((next_x, next_y))
            queue.append((next_x, next_y))
    return component


def _resolve_hidden_zone_for_footprint(
    tile: dict[str, Any],
    hidden_zone_by_cell: dict[tuple[int, int, int], str],
) -> str | None:
    layer = int(tile.get('layer', 1))
    width = max(1, int(tile.get('width', 1) or 1))
    height = max(1, int(tile.get('height', 1) or 1))
    start_x = int(tile.get('x', 0))
    start_y = int(tile.get('y', 0))
    for offset_y in range(height):
        for offset_x in range(width):
            hidden_zone = hidden_zone_by_cell.get((layer, start_x + offset_x, start_y + offset_y))
            if hidden_zone:
                return hidden_zone
    return None


def _expand_monster_spawns(definitions: Any, spawns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not spawns:
        return definitions if isinstance(definitions, list) else []
    definition_by_id = {
        str(definition.get('id')): definition
        for definition in definitions
        if isinstance(definition, dict) and definition.get('id')
    } if isinstance(definitions, list) else {}
    expanded: list[dict[str, Any]] = []
    used_ids: dict[str, int] = {}
    for spawn in spawns:
        definition_id = str(spawn.get('monster_id') or spawn.get('id') or spawn.get('kind') or '')
        definition = deepcopy(definition_by_id.get(definition_id, {}))
        monster = {**definition, **{key: value for key, value in spawn.items() if key not in {'type', 'monster_id'}}}
        base_id = str(monster.get('id') or definition_id or 'monster')
        used_ids[base_id] = used_ids.get(base_id, 0) + 1
        if used_ids[base_id] > 1:
            monster['id'] = f'{base_id}_{used_ids[base_id]}'
            monster.setdefault('definition_id', base_id)
        else:
            monster['id'] = base_id
        monster.setdefault('name', base_id)
        monster.setdefault('kind', 'monster')
        monster.setdefault('max_hp', monster.get('hp', 1))
        monster['hp'] = int(monster.get('max_hp', monster.get('hp', 1)))
        monster.setdefault('attack', 0)
        monster.setdefault('defense', 0)
        monster.setdefault('range', 1)
        expanded.append(monster)
    return expanded


def get_character(character_id: str) -> dict[str, Any] | None:
    return next((item for item in load_characters() if item['id'] == character_id), None)


def get_item(item_id: str) -> dict[str, Any] | None:
    return next((item for item in load_items() if item['id'] == item_id), None)


def get_map(map_id: str) -> dict[str, Any] | None:
    return next((item for item in load_maps() if item['id'] == map_id), None)


def resolve_map_object_id(tile: dict[str, Any]) -> str | None:
    object_id = tile.get('object_id')
    if object_id:
        return object_id
    if tile.get('type') == 'event' and tile.get('event_kind'):
        return f"event_{tile['event_kind']}"
    return tile.get('type')


def get_map_object(object_id: str | None) -> dict[str, Any] | None:
    if object_id is None:
        return None
    return load_map_object_modules().get(object_id, {}).get('definition')

def get_map_object_tooltip(tile: dict[str, Any]) -> str:
    object_id = resolve_map_object_id(tile)
    module_payload = load_map_object_modules().get(object_id)
    if module_payload is None:
        return tile.get('type', 'unknown')
    tooltip_builder = module_payload.get('tooltip_builder')
    if tooltip_builder is not None:
        return tooltip_builder(tile)
    definition = module_payload['definition']
    return definition.get('tooltip', object_id)


def load_map_object_modules() -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for module_info in pkgutil.iter_modules(map_objects.__path__):
        module = importlib.import_module(f'{map_objects.__name__}.{module_info.name}')
        payload = getattr(module, 'MAP_OBJECT', None)
        if payload is not None:
            results[payload['id']] = {
                'definition': payload,
                'tooltip_builder': getattr(module, 'build_tooltip', None),
            }
    return results
