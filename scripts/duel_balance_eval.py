from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


JsonDict = dict[str, Any]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


PAIRINGS = [
    ('genesis_bloom', 'delay_lock'),
    ('delay_lock', 'murk_burn'),
    ('murk_burn', 'darkstar_bomb'),
    ('darkstar_bomb', 'surplus_combo'),
    ('surplus_combo', 'discord_control'),
    ('discord_control', 'genesis_bloom'),
]

BASIC_PAIRINGS = [
    ('genesis_bloom', 'delay_lock'),
    ('delay_lock', 'murk_burn'),
    ('murk_burn', 'darkstar_bomb'),
    ('darkstar_bomb', 'genesis_bloom'),
]


DECK_LABELS = {
    'genesis_bloom': '创生',
    'delay_lock': '延滞',
    'murk_burn': '浊燃',
    'darkstar_bomb': '黯星',
    'surplus_combo': '盈蓄',
    'discord_control': '失谐',
}


def build_eval_side(game_service: Any, deck_id: str, side: str) -> JsonDict:
    deck_payload = game_service._resolve_deck_payload(deck_id)
    hand, deck = game_service._build_hand_and_deck_instances(deck_payload['card_ids'], side, deck_payload)
    esper_standby = game_service._build_deck_instances(
        game_service._esper_ids_for_deck_payload(deck_payload),
        side,
        prefix='esper',
    )
    return {
        'side': side,
        'uid': f'eval-{deck_id}',
        'nickname': DECK_LABELS.get(deck_id, deck_payload.get('short_name') or deck_payload['name']),
        'is_ai': True,
        'deck_id': deck_payload['id'],
        'deck_name': deck_payload['name'],
        'deck_description': deck_payload.get('description', ''),
        'ai_plan': deepcopy(deck_payload.get('ai_plan', {})),
        'deck': deck,
        'hand': hand,
        'esper_standby': esper_standby,
        'discard': [],
        'selection': None,
        'pending_target': None,
        'combo': {},
        'energy_used': 0,
        'ended_turn': False,
    }


def build_snapshot(game_service: Any, player_deck_id: str, opponent_deck_id: str, seed: int) -> JsonDict:
    random.seed(seed)
    snapshot = {
        'schema_version': game_service.SCHEMA_VERSION,
        'game_id': game_service.GAME_ID,
        'mode': 'eval',
        'scenario': 'trial',
        'scenario_label': '平衡评估',
        'status': 'playing',
        'phase': 'planning',
        'turn': 1,
        'max_turns': game_service.MAX_TURNS,
        'locations': game_service._initial_locations(),
        'sides': {
            game_service.SIDE_A: build_eval_side(game_service, player_deck_id, game_service.SIDE_A),
            game_service.SIDE_B: build_eval_side(game_service, opponent_deck_id, game_service.SIDE_B),
        },
        'winner_side': None,
        'log': [],
        'action_queue': [],
        'banner_queue': [],
        'play_sequence_counter': 0,
    }
    game_service._reveal_locations_for_turn(snapshot)
    game_service._sync_planning_phase(snapshot)
    game_service._recompute_scores(snapshot)
    game_service._lock_settlement_initiative(snapshot, emit_action=False)
    game_service._add_log(snapshot, '平衡评估对局开始。')
    return snapshot


def resolve_choices(game_service: Any, snapshot: JsonDict) -> None:
    for side in game_service.SIDE_KEYS:
        game_service._resolve_ai_pending_choices(snapshot, side)
    game_service._sync_planning_phase(snapshot)


def run_match(game_service: Any, player_deck_id: str, opponent_deck_id: str, seed: int) -> JsonDict:
    snapshot = build_snapshot(game_service, player_deck_id, opponent_deck_id, seed)
    turn_summaries: list[JsonDict] = []
    while snapshot['status'] == 'playing':
        resolve_choices(game_service, snapshot)
        turn_before = snapshot['turn']
        log_start = len(snapshot.get('log', []))
        for side in game_service.SIDE_KEYS:
            game_service._run_ai_turn(snapshot, side)
            snapshot['sides'][side]['ended_turn'] = True
        game_service._resolve_turn(snapshot)
        new_count = max(0, len(snapshot.get('log', [])) - log_start)
        new_logs = snapshot.get('log', [])[:new_count]
        turn_summaries.append({
            'turn': turn_before,
            'logs': new_logs,
            'player_power': snapshot['locations'][0]['power'][game_service.SIDE_A],
            'opponent_power': snapshot['locations'][0]['power'][game_service.SIDE_B],
        })
    return {
        'player_deck_id': player_deck_id,
        'opponent_deck_id': opponent_deck_id,
        'winner_side': snapshot.get('winner_side'),
        'status': snapshot.get('status'),
        'battlefield': snapshot['locations'][0].get('name', ''),
        'final_power': {
            'player': snapshot['locations'][0]['power'][game_service.SIDE_A],
            'opponent': snapshot['locations'][0]['power'][game_service.SIDE_B],
        },
        'metrics': collect_metrics(game_service, snapshot, turn_summaries),
        'turns': turn_summaries,
        'log_tail': snapshot.get('log', [])[-20:],
    }


def collect_metrics(game_service: Any, snapshot: JsonDict, turn_summaries: list[JsonDict]) -> JsonDict:
    all_logs = snapshot.get('log', [])
    joined = '\n'.join(all_logs)
    side_metrics = {}
    for side in game_service.SIDE_KEYS:
        side_state = snapshot['sides'][side]
        nickname = side_state['nickname']
        board_cards = [
            card
            for location in snapshot['locations']
            for card in location['cards'][side]
        ]
        revealed_cards = [card for card in board_cards if card.get('revealed')]
        revealed_espers = [card for card in revealed_cards if card.get('type') == game_service.CARD_TYPE_ESPER]
        esper_names = {
            str(card.get('name'))
            for card in [
                *board_cards,
                *side_state.get('esper_standby', []),
                *side_state.get('discard', []),
            ]
            if card.get('type') == game_service.CARD_TYPE_ESPER and card.get('name')
        }
        side_logs = [line for line in all_logs if nickname in line]
        successful_esper_reveals = sum(
            1
            for line in side_logs
            if any(f'揭示 {name}' in line for name in esper_names)
        )
        first_esper_turn = None
        for turn in turn_summaries:
            if any('唤醒' in line or '再共鸣' in line for line in turn['logs'] if nickname in line):
                first_esper_turn = turn['turn']
                break
        side_metrics[side] = {
            'deck_id': side_state.get('deck_id', ''),
            'nickname': nickname,
            'cards_remaining_in_deck': len(side_state.get('deck', [])),
            'hand_count': len(side_state.get('hand', [])),
            'discard_count': len(side_state.get('discard', [])),
            'board_count': len(board_cards),
            'revealed_count': len(revealed_cards),
            'revealed_esper_count': max(len(revealed_espers), successful_esper_reveals),
            'final_revealed_esper_count': len(revealed_espers),
            'standby_esper_count': len(side_state.get('esper_standby', [])),
            'first_esper_turn': first_esper_turn,
            'play_actions': sum(1 for line in side_logs if '置入' in line),
            'esper_awaken_actions': sum(1 for line in side_logs if '唤醒' in line),
            'esper_reactivation_actions': sum(1 for line in side_logs if '再共鸣' in line),
            'ending_power': snapshot['locations'][0]['power'][side],
        }
    return {
        'by_side': side_metrics,
        'global': {
            'total_logs': len(all_logs),
            'material_consumed': joined.count('作为共鸣素材'),
            'esper_blocked': joined.count('素材不足') + joined.count('共鸣取消'),
            'tutor_or_recover': sum(joined.count(token) for token in ['加入手牌', '回收', '检索', '获得 1 张', '抽取']),
            'interactions': sum(joined.count(token) for token in ['压低', '抹除', '破碎', '额外消耗', '返回异能者编队', '共鸣取消', '浊燃使', '黯星标记爆发']),
            'big_swing_logs': sum(1 for line in all_logs if any(token in line for token in ['+6', '+8', '+10', '爆发', '终结', '清理'])),
        },
    }


def score_deck(metric: JsonDict, global_metrics: JsonDict) -> int:
    early = 15 if metric['play_actions'] >= 4 else 10 if metric['play_actions'] >= 2 else 5
    midgame = min(20, 8 + global_metrics['interactions'] * 2)
    esper = 6
    if metric['revealed_esper_count'] >= 1:
        esper += 8
    if metric['first_esper_turn'] is not None and metric['first_esper_turn'] <= 4:
        esper += 4
    if global_metrics['esper_blocked'] > 0:
        esper += 2
    late = min(20, 8 + max(0, metric['ending_power']) // 5 + global_metrics['big_swing_logs'] * 2)
    resource = min(15, 4 + global_metrics['tutor_or_recover'] + metric['esper_reactivation_actions'] * 2)
    clarity = 8
    return min(100, early + midgame + esper + late + resource + clarity)


def summarize(matches: list[JsonDict]) -> JsonDict:
    deck_scores: dict[str, list[int]] = {deck_id: [] for deck_id in DECK_LABELS}
    for match in matches:
        metrics = match['metrics']
        global_metrics = metrics['global']
        for side_key, side_metric in metrics['by_side'].items():
            deck_id = side_metric['deck_id']
            if deck_id in deck_scores:
                deck_scores[deck_id].append(score_deck(side_metric, global_metrics))
    return {
        'matches': matches,
        'scores': {
            deck_id: {
                'label': DECK_LABELS.get(deck_id, deck_id),
                'score': round(sum(scores) / len(scores), 1) if scores else 0,
                'samples': scores,
            }
            for deck_id, scores in deck_scores.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=60606)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--basic', action='store_true')
    args = parser.parse_args()
    game_service = importlib.import_module('app.engine.game_service')
    duel_cards = importlib.import_module('app.content.duel_cards')
    game_service.LOG_LIMIT = 1000
    duel_cards.LOG_LIMIT = 1000
    pairings = BASIC_PAIRINGS if args.basic else PAIRINGS
    matches = [
        run_match(game_service, player_deck_id, opponent_deck_id, args.seed + index)
        for index, (player_deck_id, opponent_deck_id) in enumerate(pairings)
    ]
    result = summarize(matches)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    for deck_id, score in result['scores'].items():
        print(f"{score['label']}: {score['score']} ({score['samples']})")


if __name__ == '__main__':
    main()
