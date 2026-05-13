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
        normalized['tiles'] = expansion['tiles']
        normalized['layers'] = expansion['layers']
        normalized['entries'] = expansion['entries']
        normalized['total_layers'] = len(expansion['layers'])
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
    }


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
