from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.errors import AppError


APP_ROOT = Path(__file__).resolve().parents[1]
SHAFT_DATA_DIR = APP_ROOT / 'static' / 'shaft' / 'data'


def _load_json(filename: str) -> Any:
    path = SHAFT_DATA_DIR / filename
    if not path.exists():
        raise AppError(f'缺少 shaft 数据文件：{filename}')
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_shaft_catalog() -> dict[str, Any]:
    characters = _load_json('characters.json')
    actions = _load_json('actions.json')
    arcs = _load_json('arcs.json')
    cartridges = _load_json('cartridges.json')
    formula_constants = _load_json('formula_constants.json')
    source_meta = _load_json('source_meta.json')
    starter_axis = _load_json('starter_axis.json')
    actions_by_character: dict[str, list[dict[str, Any]]] = {}
    for action in actions:
        actions_by_character.setdefault(str(action.get('character_id') or ''), []).append(action)
    for items in actions_by_character.values():
        items.sort(key=lambda item: (str(item.get('action_type') or ''), str(item.get('name') or '')))
    return {
        'characters': characters,
        'actions': actions,
        'actions_by_character': actions_by_character,
        'arcs': arcs,
        'cartridges': cartridges,
        'formula_constants': formula_constants,
        'source_meta': source_meta,
        'starter_axis': starter_axis,
    }


def get_record_map(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get('id') or ''): record for record in records}
