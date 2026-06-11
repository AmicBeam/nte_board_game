from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


JsonDict = dict[str, Any]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.engine.flow import turn_flow
from app.engine.rules import board_state, declarations
from app.engine.setup import snapshot_factory
from app.content.effects import cards as card_effects


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


def configure_eval_runtime() -> None:
    logging.getLogger('nte.event_bus').setLevel(logging.WARNING)
    for module in (turn_flow, board_state, declarations, card_effects):
        module.LOG_LIMIT = 1000


def build_eval_side(deck_id: str, side: str) -> JsonDict:
    deck_payload = snapshot_factory._resolve_deck_payload(deck_id)
    hand, deck = snapshot_factory._build_hand_and_deck_instances(deck_payload['card_ids'], side, deck_payload)
    esper_standby = snapshot_factory._build_deck_instances(
        snapshot_factory._esper_ids_for_deck_payload(deck_payload),
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


def build_snapshot(player_deck_id: str, opponent_deck_id: str, seed: int) -> JsonDict:
    random.seed(seed)
    snapshot = {
        'schema_version': snapshot_factory.SCHEMA_VERSION,
        'game_id': snapshot_factory.GAME_ID,
        'mode': 'eval',
        'scenario': 'trial',
        'scenario_label': '平衡评估',
        'status': 'playing',
        'phase': 'planning',
        'turn': 1,
        'max_turns': snapshot_factory.MAX_TURNS,
        'locations': snapshot_factory._initial_locations(),
        'sides': {
            turn_flow.SIDE_A: build_eval_side(player_deck_id, turn_flow.SIDE_A),
            turn_flow.SIDE_B: build_eval_side(opponent_deck_id, turn_flow.SIDE_B),
        },
        'winner_side': None,
        'log': [],
        'action_queue': [],
        'banner_queue': [],
        'play_sequence_counter': 0,
    }
    turn_flow._reveal_locations_for_turn(snapshot)
    turn_flow._sync_planning_phase(snapshot)
    turn_flow._recompute_scores(snapshot)
    turn_flow._lock_settlement_initiative(snapshot, emit_action=False)
    turn_flow._add_log(snapshot, '平衡评估对局开始。')
    return snapshot


def resolve_choices(snapshot: JsonDict) -> None:
    for side in turn_flow.SIDE_KEYS:
        turn_flow._resolve_ai_pending_choices(snapshot, side)
    turn_flow._sync_planning_phase(snapshot)


def run_match(player_deck_id: str, opponent_deck_id: str, seed: int) -> JsonDict:
    snapshot = build_snapshot(player_deck_id, opponent_deck_id, seed)
    turn_summaries: list[JsonDict] = []
    while snapshot['status'] == 'playing':
        resolve_choices(snapshot)
        turn_before = snapshot['turn']
        previous_logs = list(snapshot.get('log', []))
        for side in turn_flow.SIDE_KEYS:
            turn_flow._run_ai_turn(snapshot, side)
            snapshot['sides'][side]['ended_turn'] = True
        turn_flow._resolve_turn(snapshot)
        new_logs = turn_flow._new_log_entries(snapshot, previous_logs)
        turn_summaries.append({
            'turn': turn_before,
            'logs': new_logs,
            'player_power': snapshot['locations'][0]['power'][turn_flow.SIDE_A],
            'opponent_power': snapshot['locations'][0]['power'][turn_flow.SIDE_B],
        })
    return {
        'player_deck_id': player_deck_id,
        'opponent_deck_id': opponent_deck_id,
        'winner_side': snapshot.get('winner_side'),
        'status': snapshot.get('status'),
        'battlefield': snapshot['locations'][0].get('name', ''),
        'final_power': {
            'player': snapshot['locations'][0]['power'][turn_flow.SIDE_A],
            'opponent': snapshot['locations'][0]['power'][turn_flow.SIDE_B],
        },
        'metrics': collect_metrics(snapshot, turn_summaries),
        'turns': turn_summaries,
        'log_tail': snapshot.get('log', [])[-20:],
    }


def collect_metrics(snapshot: JsonDict, turn_summaries: list[JsonDict]) -> JsonDict:
    all_logs = [line for turn in turn_summaries for line in turn.get('logs', [])]
    if not all_logs:
        all_logs = snapshot.get('log', [])
    joined = '\n'.join(all_logs)
    side_metrics = {}
    for side in turn_flow.SIDE_KEYS:
        side_state = snapshot['sides'][side]
        nickname = side_state['nickname']
        board_cards = [
            card
            for location in snapshot['locations']
            for card in location['cards'][side]
        ]
        revealed_cards = [card for card in board_cards if card.get('revealed')]
        revealed_espers = [card for card in revealed_cards if card.get('type') == turn_flow.CARD_TYPE_ESPER]
        esper_names = {
            str(card.get('name'))
            for card in [
                *board_cards,
                *side_state.get('esper_standby', []),
                *side_state.get('discard', []),
            ]
            if card.get('type') == turn_flow.CARD_TYPE_ESPER and card.get('name')
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
    configure_eval_runtime()
    pairings = BASIC_PAIRINGS if args.basic else PAIRINGS
    matches = [
        run_match(player_deck_id, opponent_deck_id, args.seed + index)
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
