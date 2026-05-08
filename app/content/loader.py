import importlib
import pkgutil
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
    return sorted(_load_from_package(maps, 'GAME_MAP'), key=lambda item: item['id'])


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
