#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import ssl
import sys
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / 'app' / 'static' / 'data' / 'kongmu'
CHARACTER_DIR = DATA_DIR / 'characters'
IMAGE_DIR = PROJECT_ROOT / 'app' / 'static' / 'images' / 'kongmu'
SHARED_AVATAR_DIR = PROJECT_ROOT / 'app' / 'static' / 'images' / 'characters' / 'avatar'

STATIC_BASE = 'https://static.nanoka.cc'
GAME_KEY = 'nte'
DEFAULT_LOCALE = 'zh'

GEOMETRY_SHAPES: dict[str, list[list[int]]] = {
    'EquipmentGeometry_Hen2': [[0, 0], [1, 0]],
    'EquipmentGeometry_Shu2': [[0, 0], [0, 1]],
    'EquipmentGeometry_Hen3': [[0, 0], [1, 0], [2, 0]],
    'EquipmentGeometry_Shu3': [[0, 0], [0, 1], [0, 2]],
    'EquipmentGeometry_ZhiJiao1': [[0, 0], [0, 1], [1, 1]],
    'EquipmentGeometry_ZhiJiao2': [[0, 0], [1, 0], [0, 1]],
    'EquipmentGeometry_ZhiJiao3': [[0, 0], [1, 0], [1, 1]],
    'EquipmentGeometry_ZhiJiao4': [[1, 0], [0, 1], [1, 1]],
    'EquipmentGeometry_Hen4': [[0, 0], [1, 0], [2, 0], [3, 0]],
    'EquipmentGeometry_Shu4': [[0, 0], [0, 1], [0, 2], [0, 3]],
    'EquipmentGeometry_Z3': [[1, 0], [2, 0], [0, 1], [1, 1]],
    'EquipmentGeometry_Z4': [[1, 0], [0, 1], [1, 1], [0, 2]],
}

GEOMETRY_LABELS: dict[str, str] = {
    'EquipmentGeometry_Hen2': 'II横',
    'EquipmentGeometry_Shu2': 'II竖',
    'EquipmentGeometry_Hen3': 'III横',
    'EquipmentGeometry_Shu3': 'III竖',
    'EquipmentGeometry_ZhiJiao1': 'III角1',
    'EquipmentGeometry_ZhiJiao2': 'III角2',
    'EquipmentGeometry_ZhiJiao3': 'III角3',
    'EquipmentGeometry_ZhiJiao4': 'III角4',
    'EquipmentGeometry_Hen4': 'IV横',
    'EquipmentGeometry_Shu4': 'IV竖',
    'EquipmentGeometry_Z3': 'IVZ横',
    'EquipmentGeometry_Z4': 'IVZ竖',
}


def display_name_without_quotes(value: str | None) -> str:
    return str(value or '').strip().strip('「」『』"\'` ')


def source_url(version: str, locale: str, path: str) -> str:
    return f'{STATIC_BASE}/{GAME_KEY}/{version}/{locale}/{path.lstrip("/")}'


def version_root_url(version: str, path: str) -> str:
    return f'{STATIC_BASE}/{GAME_KEY}/{version}/{path.lstrip("/")}'


def asset_url(icon_path: str | None) -> str:
    path = str(icon_path or '').strip()
    if not path:
        return ''
    return f'{STATIC_BASE}/assets/{GAME_KEY}/{path.lstrip("/")}.webp'


def icon_stem(icon_path: str | None) -> str:
    path = str(icon_path or '').strip().rstrip('/')
    if not path:
        return ''
    return path.rsplit('/', 1)[-1]


def fetch_json(url: str, insecure: bool = False) -> Any:
    request = urllib.request.Request(url, headers={'User-Agent': 'nte-board-game-kongmu/1.0'})
    context = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return json.load(response)


def fetch_bytes(url: str, insecure: bool = False) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': 'nte-board-game-kongmu/1.0'})
    context = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return response.read()


def resolve_version(version: str, insecure: bool = False) -> str:
    if version != 'latest':
        return version
    manifest = fetch_json(f'{STATIC_BASE}/manifest.json', insecure=insecure)
    resolved = manifest.get(GAME_KEY, {}).get('latest')
    if not resolved:
        raise RuntimeError('Unable to resolve latest NTE data version from manifest.')
    return str(resolved)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def valid_cells_from_slots(slots: list[list[int]]) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    for y, row in enumerate(slots):
        for x, value in enumerate(row):
            if value != -1:
                cells.append((x, y))
    return cells


def compact_family(entry: dict[str, Any]) -> list[dict[str, Any]]:
    family = entry.get('family') or []
    compacted: list[dict[str, Any]] = []
    for item in family:
        if not isinstance(item, dict):
            continue
        compacted.append(
            {
                'id': item.get('id'),
                'quality': item.get('quality'),
                'rarity': item.get('rarity'),
                'icon': item.get('icon'),
            }
        )
    return compacted


def build_console_data(raw: dict[str, Any], version: str, locale: str) -> tuple[dict[str, Any], dict[str, Any]]:
    drives: list[dict[str, Any]] = []
    cartridges: list[dict[str, Any]] = []

    for key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        entry_type = entry.get('type')
        if entry_type == 'drive':
            geometry = str(entry.get('type_geometry') or '')
            shape = GEOMETRY_SHAPES.get(geometry)
            if not shape:
                continue
            drives.append(
                {
                    'id': entry.get('id') or key,
                    'name': entry.get('name'),
                    'geometry': geometry,
                    'label': GEOMETRY_LABELS.get(geometry, geometry),
                    'grid_count': entry.get('own_grid_num'),
                    'shape': shape,
                    'icon': entry.get('icon'),
                    'family': compact_family(entry),
                }
            )
        elif entry_type == 'cartridge':
            set_effect = entry.get('set_effect') or {}
            geometry_entries = set_effect.get('geometry') or []
            synergy_geometry = [
                geometry.get('id')
                for geometry in geometry_entries
                if isinstance(geometry, dict) and geometry.get('id')
            ]
            name = str(entry.get('name') or '')
            cartridges.append(
                {
                    'id': entry.get('id') or key,
                    'name': name,
                    'aliases': sorted({name, display_name_without_quotes(name), str(entry.get('id') or key)}),
                    'icon': entry.get('icon'),
                    'synergy_geometry': synergy_geometry,
                    'synergy': [
                        {
                            'id': geometry.get('id'),
                            'name': geometry.get('name'),
                            'label': GEOMETRY_LABELS.get(str(geometry.get('id')), str(geometry.get('id'))),
                            'icon': geometry.get('icon'),
                        }
                        for geometry in geometry_entries
                        if isinstance(geometry, dict)
                    ],
                    'conditions': set_effect.get('conditions') or [],
                    'set_icon': set_effect.get('set_icon'),
                    'family': compact_family(entry),
                }
            )

    drives.sort(key=lambda item: list(GEOMETRY_SHAPES).index(item['geometry']))
    cartridges.sort(key=lambda item: str(item['id']))
    common = {
        'source': 'nanoka.cc',
        'game': GAME_KEY,
        'version': version,
        'locale': locale,
        'updated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'source_url': source_url(version, locale, 'console.json'),
    }
    return {**common, 'drives': drives}, {**common, 'cartridges': cartridges}


def build_character_index(raw: dict[str, Any], version: str) -> dict[str, Any]:
    characters: list[dict[str, Any]] = []
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        character_id = str(entry.get('id') or key)
        names = {
            locale: entry.get(locale)
            for locale in ('zh', 'en', 'ja', 'ko')
            if entry.get(locale)
        }
        characters.append(
            {
                'id': character_id,
                'name': names.get('zh') or names.get('en') or character_id,
                'names': names,
                'element': entry.get('element'),
                'element_id': entry.get('element_id'),
                'rarity': entry.get('rarity'),
                'icon': entry.get('icon'),
            }
        )
    characters.sort(key=lambda item: item['id'])
    return {
        'source': 'nanoka.cc',
        'game': GAME_KEY,
        'version': version,
        'updated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'source_url': version_root_url(version, 'character.json'),
        'characters': characters,
    }


def extract_character(raw: dict[str, Any], version: str, locale: str) -> dict[str, Any]:
    equip_slots = raw.get('equip_slots') or {}
    slots = equip_slots.get('slots') or []
    return {
        'source': 'nanoka.cc',
        'game': GAME_KEY,
        'version': version,
        'locale': locale,
        'updated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        'source_url': source_url(version, locale, f'character/{raw.get("id")}.json'),
        'id': str(raw.get('id') or ''),
        'name': raw.get('name'),
        'element': raw.get('element'),
        'element_id': raw.get('element_id'),
        'rarity': raw.get('rarity'),
        'icon': raw.get('icon'),
        'equip_slots': {
            'type_name': equip_slots.get('type_name'),
            'description_template': equip_slots.get('desc'),
            'special_desc': equip_slots.get('special_desc'),
            'owner_grid_count': equip_slots.get('owner_grid_count'),
            'stats': equip_slots.get('stats') or [],
            'slots': slots,
            'valid_cell_count': len(valid_cells_from_slots(slots)),
        },
    }


def download_if_missing(url: str, path: Path, insecure: bool = False) -> bool:
    if not url or path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fetch_bytes(url, insecure=insecure))
    return True


def attach_drive_icons(drives_data: dict[str, Any], insecure: bool = False) -> int:
    count = 0
    for drive in drives_data.get('drives') or []:
        geometry = str(drive.get('geometry') or '')
        icon = str(drive.get('icon') or '')
        if not geometry or not icon:
            continue
        local_icon = Path('images') / 'kongmu' / 'drive_icons' / f'{geometry}.webp'
        output_path = PROJECT_ROOT / 'app' / 'static' / local_icon
        if download_if_missing(asset_url(icon), output_path, insecure=insecure):
            count += 1
        drive['local_icon'] = str(local_icon)
        drive['asset_url'] = asset_url(icon)
    return count


def attach_cartridge_icons(cartridges_data: dict[str, Any], insecure: bool = False) -> int:
    count = 0
    for cartridge in cartridges_data.get('cartridges') or []:
        cartridge_id = str(cartridge.get('id') or '')
        icon = str(cartridge.get('icon') or '')
        if not cartridge_id or not icon:
            continue
        output_path = IMAGE_DIR / 'cartridges' / f'{cartridge_id}.webp'
        if download_if_missing(asset_url(icon), output_path, insecure=insecure):
            count += 1
        cartridge['local_icon'] = f'images/kongmu/cartridges/{cartridge_id}.webp'
        cartridge['asset_url'] = asset_url(icon)
    return count


def download_missing_character_avatar(record: dict[str, Any], insecure: bool = False) -> bool:
    name = str(record.get('name') or '')
    clean_name = display_name_without_quotes(name)
    if clean_name and (SHARED_AVATAR_DIR / f'{clean_name}.webp').exists():
        return False
    stem = icon_stem(record.get('icon'))
    if not stem:
        return False
    output_path = IMAGE_DIR / 'characters' / f'{stem}.webp'
    return download_if_missing(asset_url(record.get('icon')), output_path, insecure=insecure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Refresh Kongmu planner data from nanoka.cc.')
    parser.add_argument('--version', default='latest', help='NTE data version, or latest.')
    parser.add_argument('--locale', default=DEFAULT_LOCALE, help='Nanoka locale directory.')
    parser.add_argument('--insecure', action='store_true', help='Skip TLS verification.')
    parser.add_argument('--skip-images', action='store_true', help='Only refresh JSON data.')
    parser.add_argument(
        '--download-character-avatars',
        action='store_true',
        help='Also download missing character avatars into the Kongmu image folder.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        version = resolve_version(args.version, insecure=args.insecure)
        console_raw = fetch_json(source_url(version, args.locale, 'console.json'), insecure=args.insecure)
        drives_data, cartridges_data = build_console_data(console_raw, version, args.locale)
        if not args.skip_images:
            drive_count = attach_drive_icons(drives_data, insecure=args.insecure)
            cartridge_count = attach_cartridge_icons(cartridges_data, insecure=args.insecure)
        else:
            drive_count = 0
            cartridge_count = 0
        write_json(DATA_DIR / 'drives.json', drives_data)
        write_json(DATA_DIR / 'cartridges.json', cartridges_data)

        character_raw = fetch_json(version_root_url(version, 'character.json'), insecure=args.insecure)
        character_index = build_character_index(character_raw, version)
        write_json(DATA_DIR / 'character_index.json', character_index)

        avatar_count = 0
        for record in character_index['characters']:
            detail = fetch_json(source_url(version, args.locale, f'character/{record["id"]}.json'), insecure=args.insecure)
            write_json(CHARACTER_DIR / f'{record["id"]}.json', extract_character(detail, version, args.locale))
            if (
                not args.skip_images
                and args.download_character_avatars
                and download_missing_character_avatar(record, insecure=args.insecure)
            ):
                avatar_count += 1

        write_json(
            DATA_DIR / 'source_meta.json',
            {
                'source': 'nanoka.cc',
                'game': GAME_KEY,
                'version': version,
                'locale': args.locale,
                'updated_at': dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
                'console_url': source_url(version, args.locale, 'console.json'),
                'character_url': version_root_url(version, 'character.json'),
            },
        )
    except Exception as exc:
        print(f'refresh_kongmu_data failed: {exc}', file=sys.stderr)
        return 1

    print(
        f'Refreshed Kongmu data: {len(drives_data["drives"])} drives, '
        f'{len(cartridges_data["cartridges"])} cartridges, '
        f'{len(character_index["characters"])} characters. '
        f'Downloaded {drive_count} drive icons, {cartridge_count} cartridge icons, '
        f'{avatar_count} missing avatars.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
