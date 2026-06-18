from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

ANALYTICS_DATA_PATH = Path(__file__).resolve().parents[2] / 'static' / 'data' / 'duel_analytics_latest.json'


def get_duel_analytics_payload() -> JsonDict:
    if not ANALYTICS_DATA_PATH.exists():
        return {
            'available': False,
            'data_path': str(ANALYTICS_DATA_PATH),
            'message': '尚未生成评测数据。请先运行 python3 scripts/duel_balance_eval.py；脚本会默认执行三角看板评测并写入看板数据。',
        }
    try:
        data = json.loads(ANALYTICS_DATA_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            'available': False,
            'data_path': str(ANALYTICS_DATA_PATH),
            'message': f'评测数据读取失败：{exc}',
        }
    return {
        'available': True,
        'data_path': str(ANALYTICS_DATA_PATH),
        'data': data,
    }
