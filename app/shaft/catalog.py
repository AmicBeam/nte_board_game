from __future__ import annotations

import json
import re
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


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _action_has_damage(action: dict[str, Any]) -> bool:
    if str(action.get('damage_type') or '') in {'', '无'}:
        return False
    multipliers = action.get('multipliers') if isinstance(action.get('multipliers'), dict) else {}
    return any(_num(multipliers.get(key)) != 0 for key in ('atk', 'hp', 'def', 'flat'))


def _formula_hit_count(source_formula: Any) -> int:
    formula = str(source_formula or '')
    if not formula:
        return 0
    total = 0
    for match in re.finditer(r'\{\d+\}\s*%?\s*(?:\*\s*(\d+(?:\.\d+)?))?', formula):
        total += max(1, int(round(_num(match.group(1), 1))))
    return total


def _normalize_action_tags(action: dict[str, Any]) -> list[str]:
    raw_tags = action.get('tags')
    if isinstance(raw_tags, str):
        tags = {raw_tags}
    elif isinstance(raw_tags, list):
        tags = {str(tag) for tag in raw_tags if str(tag)}
    else:
        tags = set()
    extra_tag = str(action.get('extra_tag') or '')
    if extra_tag:
        tags.add(extra_tag)
    marker = ' '.join(
        str(action.get(key) or '')
        for key in ('name', 'source_action_name', 'extra_tag')
    )
    if '治疗' in marker:
        tags.update({'heal', '治疗'})
    if any(text in marker for text in ('扣血', '降生命', '降低生命')):
        tags.update({'self_hp_loss', 'hp_loss', '扣血', '降低生命'})
    debuff_names = ('延滞', '黯星', '浸染', '覆纹', '浊燃')
    for debuff in debuff_names:
        if debuff in marker:
            tags.update({debuff, f'debuff:{debuff}', f'enemy_debuff:{debuff}'})
    return sorted(tags)


def _normalize_action(action: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(action)
    tags = _normalize_action_tags(action)
    if tags:
        normalized['tags'] = tags
    formula_hits = _formula_hit_count(action.get('source_formula'))
    nightmare_stacks = _num(action.get('nightmare_stacks'), -1)
    if formula_hits > 0:
        hit_count = formula_hits
    elif nightmare_stacks >= 0:
        hit_count = max(0, int(round(nightmare_stacks)))
    elif _action_has_damage(action):
        hit_count = 1
    else:
        hit_count = 0
    normalized['hit_count'] = hit_count
    return normalized


@lru_cache(maxsize=1)
def load_shaft_catalog() -> dict[str, Any]:
    characters = _load_json('characters.json')
    actions = [_normalize_action(action) for action in _load_json('actions.json')]
    arcs = _load_json('arcs.json')
    buffs = _load_json('buffs.json')
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
        'buffs': buffs,
        'cartridges': cartridges,
        'formula_constants': formula_constants,
        'source_meta': source_meta,
        'starter_axis': starter_axis,
    }


def get_record_map(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get('id') or ''): record for record in records}
