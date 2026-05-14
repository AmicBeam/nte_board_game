#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def fail(message: str) -> None:
    raise SystemExit(f'[FAIL] {message}')


def walk(value: Any, path: str = '$'):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f'{path}.{key}'
            yield child_path, key, child
            yield from walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f'{path}[{index}]')


def main() -> None:
    if len(sys.argv) != 2:
        fail('usage: validate_tile_grid.py <map.json>')
    path = Path(sys.argv[1])
    payload = json.loads(path.read_text(encoding='utf-8'))
    layers = payload.get('tiles')
    legend = payload.get('legend')
    if not isinstance(layers, list) or not layers:
        fail('tiles must be a non-empty list of layers')
    if not isinstance(legend, dict):
        fail('legend must be a dict')
    if not any(isinstance(item, dict) and item.get('type') == 'entry' for item in legend.values()):
        fail('legend must contain at least one symbol with type=entry')
    for layer_index, rows in enumerate(layers, start=1):
        if not isinstance(rows, list):
            fail(f'layer {layer_index} is not a row list')
        widths = {len(row) for row in rows if isinstance(row, str)}
        if len(widths) != 1:
            fail(f'layer {layer_index} rows must share one width, got {sorted(widths)}')
        width = next(iter(widths), 0)
        height = len(rows)
        if height and rows[0].strip() == '':
            fail(f'layer {layer_index} has an all-space top row; trim outer blank margins')
        if height and rows[-1].strip() == '':
            fail(f'layer {layer_index} has an all-space bottom row; trim outer blank margins')
        if width and all(row[0] == ' ' for row in rows):
            fail(f'layer {layer_index} has an all-space left column; trim outer blank margins')
        if width and all(row[-1] == ' ' for row in rows):
            fail(f'layer {layer_index} has an all-space right column; trim outer blank margins')
        counts = Counter()
        for y, row in enumerate(rows):
            if not isinstance(row, str):
                fail(f'layer {layer_index} row {y} is not a string')
            for symbol in row:
                counts[symbol] += 1
                if symbol not in legend:
                    fail(f'layer {layer_index} row {y} contains symbol {symbol!r} missing from legend')
        shown = ', '.join(f'{key!r}:{value}' for key, value in sorted(counts.items()))
        print(f'[OK] layer {layer_index}: {height}x{width}; symbols {shown}')
    for child_path, key, _ in walk(payload):
        if key == 'icon':
            fail(f'map JSON should not contain icon at {child_path}')
    loot_tables = payload.get('loot_tables', {})
    if not isinstance(loot_tables, dict):
        fail('loot_tables must be a dict')
    for table_id, entries in loot_tables.items():
        if not isinstance(entries, list):
            fail(f'loot table {table_id!r} must be a list')
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                fail(f'loot table {table_id!r}[{index}] must be an object, not a bare id')
            if 'weight' in entry and int(entry.get('weight') or 0) < 0:
                fail(f'loot table {table_id!r}[{index}] has negative weight')
    for monster in payload.get('monsters', []):
        if isinstance(monster, dict) and ('x' in monster or 'y' in monster):
            fail(f'monster definition {monster.get("id", "<unknown>")!r} should not contain coordinates')
    print('[OK] compact tile map checks passed')


if __name__ == '__main__':
    main()
