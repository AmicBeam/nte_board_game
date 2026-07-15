from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


JsonDict = dict[str, Any]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modules.card_game.engine.flow import turn_flow
from app.modules.card_game.engine.rules import board_state, declarations
from app.modules.card_game.engine.setup import snapshot_factory
from app.modules.card_game.engine.application.build_service import card_by_id
from app.modules.card_game.content.effects import cards as card_effects
from app.modules.card_game.content.duel_decks import DUEL_DECKS


TRIAD_PAIRINGS = [
    ('genesis_bloom', 'delay_lock'),
    ('delay_lock', 'genesis_bloom'),
    ('genesis_bloom', 'murk_burn'),
    ('murk_burn', 'genesis_bloom'),
    ('delay_lock', 'murk_burn'),
    ('murk_burn', 'delay_lock'),
]
TRIAD_DECK_IDS = {'genesis_bloom', 'delay_lock', 'murk_burn'}


DECK_LABELS = {
    'genesis_bloom': '创生',
    'delay_lock': '延滞',
    'murk_burn': '浊燃',
    'darkstar_bomb': '黯星',
    'surplus_combo': '盈蓄',
    'discord_control': '失谐',
}

ANALYTICS_OUTPUT_PATH = PROJECT_ROOT / 'app' / 'modules' / 'card_game' / 'static' / 'data' / 'duel_analytics_latest.json'


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
            'actions': deepcopy(snapshot.get('action_queue', [])),
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
    revealed_esper_ids_by_side: dict[str, set[str]] = {side: set() for side in turn_flow.SIDE_KEYS}
    for turn in turn_summaries:
        for action in turn.get('actions', []):
            if not isinstance(action, dict) or action.get('kind') != 'reveal_card':
                continue
            side = str(action.get('side') or '')
            card = action.get('card') if isinstance(action.get('card'), dict) else {}
            if side in revealed_esper_ids_by_side and card.get('type') == turn_flow.CARD_TYPE_ESPER:
                esper_id = str(card.get('definition_id') or card.get('id') or '')
                if esper_id:
                    revealed_esper_ids_by_side[side].add(esper_id)
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
        esper_ids = {
            str(card.get('definition_id') or '')
            for card in [
                *board_cards,
                *side_state.get('esper_standby', []),
                *side_state.get('discard', []),
            ]
            if card.get('type') == turn_flow.CARD_TYPE_ESPER and str(card.get('definition_id') or '')
        }
        revealed_esper_ids = revealed_esper_ids_by_side.get(side, set())
        total_esper_count = len(esper_ids) or len(revealed_esper_ids)
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
            'unique_revealed_esper_count': len(revealed_esper_ids),
            'unique_revealed_esper_ids': sorted(revealed_esper_ids),
            'total_esper_count': total_esper_count,
            'all_espers_revealed': bool(total_esper_count and len(revealed_esper_ids) >= total_esper_count),
            'standby_esper_count': len(side_state.get('esper_standby', [])),
            'first_esper_turn': first_esper_turn,
            'play_actions': sum(1 for line in side_logs if '置入' in line),
            'esper_awaken_actions': sum(1 for line in side_logs if '唤醒' in line),
            'esper_reactivation_actions': sum(1 for line in side_logs if '再共鸣' in line),
            'ending_power': snapshot['locations'][0]['power'][side],
            'final_espers': [
                {
                    'id': str(card.get('definition_id') or ''),
                    'name': str(card.get('name') or ''),
                    'computed_power': int(card.get('computed_power') or 0),
                    'base_power': int(card.get('base_power') or 0),
                    'absorbed_material_power': int(card.get('absorbed_material_power') or 0),
                }
                for card in revealed_espers
            ],
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


def summarize(matches: list[JsonDict]) -> JsonDict:
    return {'matches': matches}


def _side_won(match: JsonDict, side: str) -> bool:
    return str(match.get('winner_side') or '') == side


def _pct(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) * 100 / float(denominator), 1)


def _avg(values: list[int | float]) -> float | None:
    if not values:
        return None
    return round(sum(float(value) for value in values) / len(values), 2)


def _all_match_logs(match: JsonDict) -> list[str]:
    return [line for turn in match.get('turns', []) for line in turn.get('logs', [])]


def _all_match_actions(match: JsonDict) -> list[tuple[int, JsonDict]]:
    actions: list[tuple[int, JsonDict]] = []
    for turn in match.get('turns', []):
        turn_number = int(turn.get('turn') or 0)
        for action in turn.get('actions', []):
            if isinstance(action, dict):
                actions.append((turn_number, action))
    return actions


def _line_impact_score(line: str) -> float:
    score = 0.0
    if any(token in line for token in ('压低', '造成', '伤害', '战力归零')):
        score += 2.0
    if any(token in line for token in ('破碎', '斩杀', '返回牌库', '交换控制权', '共鸣取消', '素材不足')):
        score += 3.0
    if any(token in line for token in ('设置环合', '生成', '加入手牌', '置于牌库顶', '部署到战场', '回收')):
        score += 1.0
    if any(token in line for token in ('保护', '护盾', '再重复', '爆发')):
        score += 2.0
    for value in re.findall(r'(?<!\d)([+-]\d+)', line):
        score += min(6, abs(int(value))) * 0.35
    return round(score, 2)


def _deck_cards_by_id() -> dict[str, set[str]]:
    deck_cards: dict[str, set[str]] = {}
    for deck in DUEL_DECKS:
        deck_cards[str(deck['id'])] = {
            *[str(card_id) for card_id in deck.get('card_ids', [])],
            *[str(card_id) for card_id in deck.get('esper_card_ids', [])],
        }
    return deck_cards


def _deck_item_ids_by_id() -> dict[str, list[str]]:
    return {
        str(deck['id']): [str(card_id) for card_id in deck.get('card_ids', [])]
        for deck in DUEL_DECKS
    }


def _deck_esper_ids_by_id() -> dict[str, list[str]]:
    return {
        str(deck['id']): [str(card_id) for card_id in deck.get('esper_card_ids', [])]
        for deck in DUEL_DECKS
    }


def _active_deck_ids(matches: list[JsonDict]) -> set[str]:
    deck_ids: set[str] = set()
    for match in matches:
        for metric in match.get('metrics', {}).get('by_side', {}).values():
            deck_id = str(metric.get('deck_id') or '')
            if deck_id:
                deck_ids.add(deck_id)
    return deck_ids


def _active_card_ids(active_deck_ids: set[str], deck_cards: dict[str, set[str]]) -> set[str]:
    card_ids: set[str] = set()
    for deck_id in active_deck_ids:
        card_ids.update(deck_cards.get(deck_id, set()))
    return card_ids


def _material_requirement_fragment(requirement: JsonDict, *, include_count: bool = True) -> str:
    count = max(1, int(requirement.get('count') or 1))
    if requirement.get('attribute'):
        base = f"{requirement.get('attribute')}属性素材"
    else:
        attributes = requirement.get('attributes')
        if isinstance(attributes, list):
            options = [str(attribute) for attribute in attributes if str(attribute)]
            if options:
                base = f"{'/'.join(options)}属性素材"
            else:
                base = '任意素材'
        elif requirement.get('category'):
            base = f"{requirement.get('category')}素材"
        elif requirement.get('name'):
            base = f"「{requirement.get('name')}」"
        else:
            base = '任意素材'
    if include_count and count > 1:
        return f"{base}*{count}"
    return base


def _expanded_requirements(requirements: list[JsonDict]) -> list[JsonDict]:
    expanded: list[JsonDict] = []
    for requirement in requirements:
        count = max(1, int(requirement.get('count') or 1))
        expanded.extend(requirement for _ in range(count))
    return expanded


def _requirement_specificity(requirement: JsonDict) -> int:
    if requirement.get('name'):
        return 4
    if requirement.get('category'):
        return 3
    if requirement.get('attribute') or requirement.get('attributes'):
        return 2
    return 1


def _definition_attributes(definition: JsonDict) -> set[str]:
    attributes = {str(definition.get('attribute') or definition.get('element') or '')}
    attributes.update(str(attribute) for attribute in definition.get('material_attributes', []) if str(attribute))
    attributes.discard('')
    return attributes


def _definition_matches_requirement(definition: JsonDict, requirement: JsonDict) -> bool:
    attribute = str(requirement.get('attribute') or '')
    attributes = requirement.get('attributes')
    category = str(requirement.get('category') or '')
    name = str(requirement.get('name') or '')
    material_attributes = _definition_attributes(definition)
    if attribute and attribute not in material_attributes:
        return False
    if isinstance(attributes, list):
        options = {str(option) for option in attributes if str(option)}
        if options and not material_attributes.intersection(options):
            return False
    if category and str(definition.get('category') or '') != category:
        return False
    if name and str(definition.get('name') or '') != name:
        return False
    return True


def _material_gap_for_esper(
    deck_id: str,
    esper_id: str,
    catalog: dict[str, JsonDict],
    deck_item_ids: dict[str, list[str]],
) -> JsonDict:
    esper = catalog.get(esper_id, {})
    requirements = [requirement for requirement in esper.get('material_requirements', []) if isinstance(requirement, dict)]
    requirement_text = '+'.join(_material_requirement_fragment(requirement) for requirement in requirements) or str(esper.get('material_requirement_text') or '')
    candidates = [
        catalog.get(card_id, {})
        for card_id in deck_item_ids.get(deck_id, [])
        if catalog.get(card_id, {}).get('type') != turn_flow.CARD_TYPE_ESPER
    ]
    expanded = sorted(_expanded_requirements(requirements), key=_requirement_specificity, reverse=True)
    used_candidate_indexes: set[int] = set()
    missing: list[JsonDict] = []
    for requirement in expanded:
        matched_index = None
        for index, candidate in enumerate(candidates):
            if index in used_candidate_indexes:
                continue
            if _definition_matches_requirement(candidate, requirement):
                matched_index = index
                break
        if matched_index is None:
            missing.append(requirement)
        else:
            used_candidate_indexes.add(matched_index)
    missing_counts: dict[str, int] = {}
    for requirement in missing:
        fragment = _material_requirement_fragment(requirement, include_count=False)
        missing_counts[fragment] = missing_counts.get(fragment, 0) + 1
    missing_text = '、'.join(f"缺少{fragment}*{count}" for fragment, count in missing_counts.items())
    return {
        'requirement_text': requirement_text,
        'material_gap': missing_text,
        'material_gap_count': len(missing),
    }


def _definition_id_from_instance_id(instance_id: str) -> str:
    for marker in ('-deck-', '-esper-', '-token-'):
        if marker in instance_id:
            return instance_id.split(marker, 1)[0]
    return ''


def _side_from_instance_id(instance_id: str) -> str:
    match = re.search(r'-(?:deck|esper|token)-([ab])-', instance_id)
    return match.group(1) if match else ''


def _card_entry(card_id: str, definition: JsonDict | None, deck_cards: dict[str, set[str]]) -> JsonDict:
    definition = definition or {}
    return {
        'id': card_id,
        'name': str(definition.get('name') or card_id),
        'type': str(definition.get('type') or ''),
        'art': str(definition.get('art') or definition.get('icon') or ''),
        'icon': str(definition.get('icon') or definition.get('art') or ''),
        'attribute': str(definition.get('attribute') or definition.get('element') or ''),
        'attribute_icon': str(definition.get('attribute_icon') or ''),
        'category': str(definition.get('category') or ''),
        'rarity': str(definition.get('rarity') or ''),
        'cost': int(definition.get('cost') or 0),
        'power': int(definition.get('power') or 0),
        'description': str(definition.get('description') or ''),
        'material_requirement_text': str(definition.get('material_requirement_text') or ''),
        'decks': sorted(deck_id for deck_id, ids in deck_cards.items() if card_id in ids),
        'reveals': 0,
        'matches_seen': 0,
        'wins_when_seen': 0,
        'material_uses': 0,
        'effect_logs': 0,
        'impact_events': 0,
        'impact_score': 0.0,
        '_seen_match_keys': set(),
    }


def _public_card_stats(stats: JsonDict) -> JsonDict:
    seen = int(stats.get('matches_seen') or 0)
    reveals = int(stats.get('reveals') or 0)
    return {
        'id': stats['id'],
        'name': stats['name'],
        'type': stats['type'],
        'art': stats.get('art', ''),
        'icon': stats.get('icon', ''),
        'attribute': stats['attribute'],
        'attribute_icon': stats.get('attribute_icon', ''),
        'category': stats['category'],
        'rarity': stats['rarity'],
        'cost': stats.get('cost', 0),
        'power': stats.get('power', 0),
        'description': stats.get('description', ''),
        'material_requirement_text': stats.get('material_requirement_text', ''),
        'decks': stats['decks'],
        'reveals': reveals,
        'matches_seen': seen,
        'win_rate_when_seen': _pct(int(stats.get('wins_when_seen') or 0), seen),
        'material_uses': int(stats.get('material_uses') or 0),
        'effect_logs': int(stats.get('effect_logs') or 0),
        'impact_events': int(stats.get('impact_events') or 0),
        'impact_score': round(float(stats.get('impact_score') or 0), 2),
        'impact_per_reveal': round(float(stats.get('impact_score') or 0) / reveals, 2) if reveals else 0,
    }


def build_analytics(result: JsonDict, *, seed: int, samples: int, focus: str) -> JsonDict:
    matches = list(result.get('matches', []))
    catalog = card_by_id()
    deck_cards = _deck_cards_by_id()
    deck_item_ids = _deck_item_ids_by_id()
    deck_esper_ids = _deck_esper_ids_by_id()
    active_decks = _active_deck_ids(matches)
    active_cards = _active_card_ids(active_decks, deck_cards)
    name_to_ids: dict[str, list[str]] = defaultdict(list)
    for card_id, definition in catalog.items():
        name_to_ids[str(definition.get('name') or card_id)].append(str(card_id))

    card_stats: dict[str, JsonDict] = {
        str(card_id): _card_entry(str(card_id), definition, deck_cards)
        for card_id, definition in catalog.items()
    }
    deck_stats: dict[str, JsonDict] = {
        deck_id: {
            'id': deck_id,
            'label': DECK_LABELS.get(deck_id, deck_id),
            'games': 0,
            'wins': 0,
            'first_esper_turns': [],
            'ending_powers': [],
            'esper_blocks': 0,
            'interactions': 0,
            'play_actions': 0,
            'esper_actions': 0,
            'unique_esper_counts': [],
            'all_esper_games': 0,
        }
        for deck_id in DECK_LABELS
    }
    matchup_stats: dict[tuple[str, str], JsonDict] = {}
    delay_records: list[JsonDict] = []
    delay_tool_stats: dict[str, JsonDict] = {}
    delay_break_stats: dict[str, JsonDict] = {}
    esper_stats: dict[str, JsonDict] = {}

    for match_index, match in enumerate(matches):
        logs = _all_match_logs(match)
        joined_logs = '\n'.join(logs)
        actions = _all_match_actions(match)
        instance_to_card_id: dict[str, str] = {}
        match_key_prefix = f"{match.get('pairing_index', match_index)}:{match.get('sample_index', 0)}"
        side_metrics = match.get('metrics', {}).get('by_side', {})
        global_metrics = match.get('metrics', {}).get('global', {})

        for side, metric in side_metrics.items():
            deck_id = str(metric.get('deck_id') or '')
            opponent_side = turn_flow.SIDE_B if side == turn_flow.SIDE_A else turn_flow.SIDE_A
            opponent_deck_id = str(side_metrics.get(opponent_side, {}).get('deck_id') or '')
            won = _side_won(match, side)
            deck_stat = deck_stats.setdefault(deck_id, {
                'id': deck_id,
                'label': DECK_LABELS.get(deck_id, deck_id),
                'games': 0,
                'wins': 0,
                'first_esper_turns': [],
                'ending_powers': [],
                'esper_blocks': 0,
                'interactions': 0,
                'play_actions': 0,
                'esper_actions': 0,
                'unique_esper_counts': [],
                'all_esper_games': 0,
            })
            deck_stat['games'] += 1
            deck_stat['wins'] += 1 if won else 0
            first_turn = metric.get('first_esper_turn')
            if first_turn is not None:
                deck_stat['first_esper_turns'].append(int(first_turn))
            deck_stat['ending_powers'].append(int(metric.get('ending_power') or 0))
            deck_stat['esper_blocks'] += int(global_metrics.get('esper_blocked') or 0)
            deck_stat['interactions'] += int(global_metrics.get('interactions') or 0)
            deck_stat['play_actions'] += int(metric.get('play_actions') or 0)
            deck_stat['esper_actions'] += int(metric.get('esper_awaken_actions') or 0) + int(metric.get('esper_reactivation_actions') or 0)
            deck_stat['unique_esper_counts'].append(int(metric.get('unique_revealed_esper_count') or 0))
            if metric.get('all_espers_revealed'):
                deck_stat['all_esper_games'] += 1

            matchup_key = (deck_id, opponent_deck_id)
            matchup = matchup_stats.setdefault(matchup_key, {
                'deck_id': deck_id,
                'deck_label': DECK_LABELS.get(deck_id, deck_id),
                'opponent_deck_id': opponent_deck_id,
                'opponent_label': DECK_LABELS.get(opponent_deck_id, opponent_deck_id),
                'games': 0,
                'wins': 0,
                'first_esper_turns': [],
                'ending_powers': [],
                'blocked_games': 0,
                'unique_esper_counts': [],
                'all_esper_games': 0,
            })
            matchup['games'] += 1
            matchup['wins'] += 1 if won else 0
            if first_turn is not None:
                matchup['first_esper_turns'].append(int(first_turn))
            matchup['ending_powers'].append(int(metric.get('ending_power') or 0))
            if int(global_metrics.get('esper_blocked') or 0) > 0:
                matchup['blocked_games'] += 1
            matchup['unique_esper_counts'].append(int(metric.get('unique_revealed_esper_count') or 0))
            if metric.get('all_espers_revealed'):
                matchup['all_esper_games'] += 1

        for turn_number, action in actions:
            card = action.get('card') if isinstance(action.get('card'), dict) else {}
            card_id = str(card.get('definition_id') or '')
            source_instance_id = str(action.get('source_instance_id') or '')
            if card_id and source_instance_id:
                instance_to_card_id[source_instance_id] = card_id
            side = str(action.get('side') or '')
            metric = side_metrics.get(side, {})
            won = _side_won(match, side)
            side_match_key = f'{match_key_prefix}:{side}'
            if action.get('kind') == 'reveal_card' and card_id in card_stats:
                stats = card_stats[card_id]
                stats['reveals'] += 1
                if side_match_key not in stats['_seen_match_keys']:
                    stats['_seen_match_keys'].add(side_match_key)
                    stats['matches_seen'] += 1
                    stats['wins_when_seen'] += 1 if won else 0
            elif action.get('kind') == 'consume_material' and card_id in card_stats:
                card_stats[card_id]['material_uses'] += 1

            if action.get('kind') == 'impact_arrow':
                source_card_id = instance_to_card_id.get(source_instance_id)
                if source_card_id is None:
                    title = str(action.get('title') or '')
                    ids = name_to_ids.get(title, [])
                    source_card_id = ids[0] if len(ids) == 1 else None
                if source_card_id in card_stats:
                    delta = abs(int(action.get('power_delta') or 0))
                    card_stats[source_card_id]['impact_events'] += 1
                    card_stats[source_card_id]['impact_score'] += max(1, delta)
            elif action.get('kind') == 'spawn_mark':
                source_card_id = instance_to_card_id.get(source_instance_id)
                if source_card_id in card_stats:
                    card_stats[source_card_id]['impact_events'] += 1
                    card_stats[source_card_id]['impact_score'] += max(1, int(action.get('amount') or 1))

        for line in logs:
            for card_name, card_ids in name_to_ids.items():
                if not card_name or not line.startswith(card_name):
                    continue
                score = _line_impact_score(line)
                for card_id in card_ids:
                    if card_id not in card_stats:
                        continue
                    card_stats[card_id]['effect_logs'] += 1
                    card_stats[card_id]['impact_score'] += score

        _collect_delay_analytics(match, actions, joined_logs, delay_records, delay_tool_stats, delay_break_stats, catalog, deck_cards)
        _collect_esper_analytics(match, actions, logs, esper_stats, catalog, deck_item_ids, deck_esper_ids)

    public_decks = []
    for deck_id, stats in deck_stats.items():
        games = int(stats.get('games') or 0)
        if games <= 0:
            continue
        public_decks.append({
            'id': deck_id,
            'label': stats.get('label', deck_id),
            'games': games,
            'wins': int(stats.get('wins') or 0),
            'win_rate': _pct(int(stats.get('wins') or 0), games),
            'avg_first_esper_turn': _avg(stats.get('first_esper_turns', [])),
            'avg_ending_power': _avg(stats.get('ending_powers', [])),
            'interaction_events': int(stats.get('interactions') or 0),
            'play_actions': int(stats.get('play_actions') or 0),
            'esper_actions': int(stats.get('esper_actions') or 0),
            'avg_unique_espers': _avg(stats.get('unique_esper_counts', [])),
            'all_esper_games': int(stats.get('all_esper_games') or 0),
            'all_esper_rate': _pct(int(stats.get('all_esper_games') or 0), games),
        })

    public_matchups = []
    for stats in matchup_stats.values():
        games = int(stats.get('games') or 0)
        public_matchups.append({
            'deck_id': stats['deck_id'],
            'deck_label': stats['deck_label'],
            'opponent_deck_id': stats['opponent_deck_id'],
            'opponent_label': stats['opponent_label'],
            'games': games,
            'wins': int(stats.get('wins') or 0),
            'win_rate': _pct(int(stats.get('wins') or 0), games),
            'avg_first_esper_turn': _avg(stats.get('first_esper_turns', [])),
            'avg_ending_power': _avg(stats.get('ending_powers', [])),
            'blocked_game_rate': _pct(int(stats.get('blocked_games') or 0), games),
            'avg_unique_espers': _avg(stats.get('unique_esper_counts', [])),
            'all_esper_games': int(stats.get('all_esper_games') or 0),
            'all_esper_rate': _pct(int(stats.get('all_esper_games') or 0), games),
        })

    public_cards = sorted(
        (
            _public_card_stats(stats)
            for card_id, stats in card_stats.items()
            if card_id in active_cards or int(stats.get('reveals') or 0) or int(stats.get('effect_logs') or 0)
        ),
        key=lambda item: (item['impact_score'], item['reveals'], item['win_rate_when_seen']),
        reverse=True,
    )
    public_items = [item for item in public_cards if item['type'] != turn_flow.CARD_TYPE_ESPER]
    public_espers = _public_esper_stats(esper_stats)
    public_delay_tools = sorted(
        (
            {
                **stats,
                'impact_score': round(float(stats.get('impact_score') or 0), 2),
                'delay_success_rate': _pct(int(stats.get('successes') or 0), int(stats.get('matches') or 0)),
            }
            for stats in delay_tool_stats.values()
        ),
        key=lambda item: (item['successes'], item['events'], item['impact_score']),
        reverse=True,
    )
    public_delay_breaks = _public_delay_break_stats(delay_break_stats)
    observations = _build_observations(public_decks, public_matchups, delay_records, public_espers, public_cards)
    acceptance = _build_acceptance(public_decks, public_matchups, public_espers, public_delay_breaks, samples)

    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'seed': seed,
        'samples': samples,
        'focus': 'triad',
        'method': 'triad_dashboard',
        'pairings': [
            {
                'player_deck_id': match.get('player_deck_id'),
                'opponent_deck_id': match.get('opponent_deck_id'),
                'winner_side': match.get('winner_side'),
                'status': match.get('status'),
            }
            for match in matches
        ],
        'acceptance': acceptance,
        'decks': sorted(public_decks, key=lambda item: item['win_rate'], reverse=True),
        'matchups': sorted(public_matchups, key=lambda item: (item['deck_id'], item['opponent_deck_id'])),
        'cards': public_cards,
        'items': public_items,
        'espers': public_espers,
        'delay': {
            'records': delay_records,
            'tools': public_delay_tools,
            'breaks': public_delay_breaks,
        },
        'aces': [],
        'hot_decks': sorted(public_decks, key=lambda item: (item['games'], item['win_rate'], item.get('avg_unique_espers') or 0), reverse=True),
        'observations': observations,
    }


def _collect_delay_analytics(
    match: JsonDict,
    actions: list[tuple[int, JsonDict]],
    joined_logs: str,
    delay_records: list[JsonDict],
    delay_tool_stats: dict[str, JsonDict],
    delay_break_stats: dict[str, JsonDict],
    catalog: dict[str, JsonDict],
    deck_cards: dict[str, set[str]],
) -> None:
    side_metrics = match.get('metrics', {}).get('by_side', {})
    delay_card_ids = deck_cards.get('delay_lock', set())
    delay_card_names = {
        card_id: str(catalog.get(card_id, {}).get('name') or card_id)
        for card_id in delay_card_ids
    }
    for side, metric in side_metrics.items():
        if str(metric.get('deck_id') or '') != 'delay_lock':
            continue
        opponent_side = turn_flow.SIDE_B if side == turn_flow.SIDE_A else turn_flow.SIDE_A
        opponent_metric = side_metrics.get(opponent_side, {})
        opponent_deck_id = str(opponent_metric.get('deck_id') or '')
        first_turn = opponent_metric.get('first_esper_turn')
        blocker_lines = [
            line
            for line in joined_logs.splitlines()
            if any(token in line for token in ('素材不足', '共鸣取消', '返回牌库', '交换控制权', '压低', '破碎进入墓地'))
        ][:12]
        success = first_turn is None or int(first_turn) >= 5 or any(token in joined_logs for token in ('素材不足', '共鸣取消'))
        delay_records.append({
            'delay_side': side,
            'target_deck_id': opponent_deck_id,
            'target_label': DECK_LABELS.get(opponent_deck_id, opponent_deck_id),
            'target_first_esper_turn': first_turn,
            'success': bool(success),
            'evidence': blocker_lines,
            'battlefield': match.get('battlefield', ''),
        })
        for card_id, name in delay_card_names.items():
            card_lines = [line for line in joined_logs.splitlines() if line.startswith(name)]
            if not card_lines:
                continue
            definition = catalog.get(card_id, {})
            stats = delay_tool_stats.setdefault(card_id, {
                'id': card_id,
                'name': name,
                'type': str(definition.get('type') or ''),
                'art': str(definition.get('art') or definition.get('icon') or ''),
                'icon': str(definition.get('icon') or definition.get('art') or ''),
                'attribute': str(definition.get('attribute') or definition.get('element') or ''),
                'category': str(definition.get('category') or ''),
                'cost': int(definition.get('cost') or 0),
                'power': int(definition.get('power') or 0),
                'description': str(definition.get('description') or ''),
                'events': 0,
                'matches': 0,
                'successes': 0,
                'impact_score': 0.0,
                'sample_lines': [],
            })
            stats['events'] += len(card_lines)
            stats['matches'] += 1
            stats['successes'] += 1 if success else 0
            stats['impact_score'] += sum(_line_impact_score(line) for line in card_lines)
            stats['sample_lines'].extend(card_lines[:2])
            del stats['sample_lines'][6:]
        _collect_delay_material_breaks(
            match,
            actions,
            side,
            opponent_side,
            opponent_deck_id,
            success,
            delay_break_stats,
            catalog,
            delay_card_ids,
        )


def _collect_delay_material_breaks(
    match: JsonDict,
    actions: list[tuple[int, JsonDict]],
    delay_side: str,
    opponent_side: str,
    opponent_deck_id: str,
    success: bool,
    delay_break_stats: dict[str, JsonDict],
    catalog: dict[str, JsonDict],
    delay_card_ids: set[str],
) -> None:
    instance_to_card_id: dict[str, str] = {}
    for _, action in actions:
        card = action.get('card') if isinstance(action.get('card'), dict) else {}
        instance_id = str(action.get('source_instance_id') or card.get('instance_id') or '')
        card_id = str(card.get('definition_id') or '')
        if instance_id and card_id:
            instance_to_card_id[instance_id] = card_id
        target_instance_id = str(action.get('target_instance_id') or '')
        target_card = action.get('target_card') if isinstance(action.get('target_card'), dict) else {}
        target_card_id = str(target_card.get('definition_id') or '')
        if target_instance_id and target_card_id:
            instance_to_card_id[target_instance_id] = target_card_id

    match_key = f"{match.get('pairing_index', '')}:{match.get('sample_index', '')}:{delay_side}"
    seen_sources: set[str] = set()
    for turn_number, action in actions:
        if action.get('kind') != 'impact_arrow':
            continue
        delta = int(action.get('power_delta') or 0)
        if delta >= 0:
            continue
        source_instance_id = str(action.get('source_instance_id') or '')
        target_instance_id = str(action.get('target_instance_id') or '')
        if _side_from_instance_id(source_instance_id) != delay_side:
            continue
        if _side_from_instance_id(target_instance_id) != opponent_side:
            continue
        source_card_id = instance_to_card_id.get(source_instance_id) or _definition_id_from_instance_id(source_instance_id)
        target_card_id = instance_to_card_id.get(target_instance_id) or _definition_id_from_instance_id(target_instance_id)
        if source_card_id not in delay_card_ids:
            continue
        target_definition = catalog.get(target_card_id, {})
        if target_definition.get('type') != turn_flow.CARD_TYPE_ANOMALY_ITEM:
            continue
        if 'material' not in target_definition.get('tags', []):
            continue
        source_definition = catalog.get(source_card_id, {})
        source_name = str(source_definition.get('name') or action.get('title') or source_card_id)
        action_title = str(action.get('title') or source_name)
        action_label = source_name if action_title == source_name else f"{source_name}（复制{action_title}）"
        target_name = str(target_definition.get('name') or target_card_id)
        power_before = int(action.get('power_before') or 0)
        power_after = int(action.get('power_after') or 0)
        destroyed = power_after <= 0
        stats = delay_break_stats.setdefault(source_card_id, {
            'id': source_card_id,
            'name': source_name,
            'type': str(source_definition.get('type') or ''),
            'art': str(source_definition.get('art') or source_definition.get('icon') or ''),
            'icon': str(source_definition.get('icon') or source_definition.get('art') or ''),
            'attribute': str(source_definition.get('attribute') or source_definition.get('element') or ''),
            'category': str(source_definition.get('category') or ''),
            'cost': int(source_definition.get('cost') or 0),
            'power': int(source_definition.get('power') or 0),
            'description': str(source_definition.get('description') or ''),
            'games': 0,
            'events': 0,
            'material_hits': 0,
            'destroyed_targets': 0,
            'blocked_matches': 0,
            'impact_score': 0.0,
            'target_decks': [],
            'target_names': {},
            'target_cards': {},
            'sample_lines': [],
        })
        if source_card_id not in seen_sources:
            seen_sources.add(source_card_id)
            stats['games'] += 1
            stats['blocked_matches'] += 1 if success else 0
        if opponent_deck_id not in stats['target_decks']:
            stats['target_decks'].append(opponent_deck_id)
        stats['events'] += 1
        stats['material_hits'] += 1
        stats['destroyed_targets'] += 1 if destroyed else 0
        stats['impact_score'] += abs(delta) + (3 if destroyed else 0)
        target_names = stats.setdefault('target_names', {})
        target_names[target_name] = int(target_names.get(target_name) or 0) + 1
        target_cards = stats.setdefault('target_cards', {})
        target_stats = target_cards.setdefault(target_card_id, {
            'id': target_card_id,
            'name': target_name,
            'art': str(target_definition.get('art') or target_definition.get('icon') or ''),
            'icon': str(target_definition.get('icon') or target_definition.get('art') or ''),
            'type': str(target_definition.get('type') or ''),
            'attribute': str(target_definition.get('attribute') or target_definition.get('element') or ''),
            'category': str(target_definition.get('category') or ''),
            'cost': int(target_definition.get('cost') or 0),
            'power': int(target_definition.get('power') or 0),
            'description': str(target_definition.get('description') or ''),
            'count': 0,
        })
        target_stats['count'] = int(target_stats.get('count') or 0) + 1
        material_label = '/'.join(sorted(_definition_attributes(target_definition))) or str(target_definition.get('attribute') or '-')
        category = str(target_definition.get('category') or '-')
        outcome = '破碎' if destroyed else '保留'
        stats['sample_lines'].append(
            f"第 {turn_number} 回合：{action_label} 命中 {target_name}（{material_label}/{category}素材）"
            f" {power_before}->{power_after}，{outcome}。"
        )
        del stats['sample_lines'][6:]


def _public_delay_break_stats(delay_break_stats: dict[str, JsonDict]) -> list[JsonDict]:
    public = []
    for stats in delay_break_stats.values():
        games = int(stats.get('games') or 0)
        target_cards = stats.get('target_cards') if isinstance(stats.get('target_cards'), dict) else {}
        if target_cards:
            top_targets = sorted(target_cards.values(), key=lambda item: int(item.get('count') or 0), reverse=True)[:5]
        else:
            target_names = stats.get('target_names') if isinstance(stats.get('target_names'), dict) else {}
            top_targets = [{'name': name, 'count': count} for name, count in sorted(target_names.items(), key=lambda item: item[1], reverse=True)[:5]]
        public.append({
            'id': stats['id'],
            'name': stats['name'],
            'type': stats.get('type', ''),
            'art': stats.get('art', ''),
            'icon': stats.get('icon', ''),
            'attribute': stats.get('attribute', ''),
            'category': stats.get('category', ''),
            'cost': int(stats.get('cost') or 0),
            'power': int(stats.get('power') or 0),
            'description': stats.get('description', ''),
            'deck_id': 'delay_lock',
            'deck_label': DECK_LABELS.get('delay_lock', '延滞'),
            'games': games,
            'events': int(stats.get('events') or 0),
            'material_hits': int(stats.get('material_hits') or 0),
            'destroyed_targets': int(stats.get('destroyed_targets') or 0),
            'blocked_matches': int(stats.get('blocked_matches') or 0),
            'block_rate': _pct(int(stats.get('blocked_matches') or 0), games),
            'impact_score': round(float(stats.get('impact_score') or 0), 2),
            'target_decks': sorted(stats.get('target_decks') or []),
            'top_targets': top_targets,
            'sample_lines': stats.get('sample_lines', []),
        })
    return sorted(public, key=lambda item: (item['blocked_matches'], item['destroyed_targets'], item['events']), reverse=True)


def _collect_esper_analytics(
    match: JsonDict,
    actions: list[tuple[int, JsonDict]],
    logs: list[str],
    esper_stats: dict[str, JsonDict],
    catalog: dict[str, JsonDict],
    deck_item_ids: dict[str, list[str]],
    deck_esper_ids: dict[str, list[str]],
) -> None:
    side_metrics = match.get('metrics', {}).get('by_side', {})
    for side, metric in side_metrics.items():
        deck_id = str(metric.get('deck_id') or '')
        if not deck_id:
            continue
        won = _side_won(match, side)
        for esper_id in deck_esper_ids.get(deck_id, []):
            definition = catalog.get(esper_id, {})
            gap = _material_gap_for_esper(deck_id, esper_id, catalog, deck_item_ids)
            key = f'{deck_id}:{esper_id}'
            stats = esper_stats.setdefault(key, {
                'deck_id': deck_id,
                'deck_label': DECK_LABELS.get(deck_id, deck_id),
                'card_id': esper_id,
                'name': str(definition.get('name') or esper_id),
                'art': str(definition.get('art') or definition.get('icon') or ''),
                'icon': str(definition.get('icon') or definition.get('art') or ''),
                'attribute': str(definition.get('attribute') or definition.get('element') or ''),
                'attribute_icon': str(definition.get('attribute_icon') or ''),
                'category': str(definition.get('category') or ''),
                'rarity': str(definition.get('rarity') or ''),
                'cost': int(definition.get('cost') or 0),
                'power': int(definition.get('power') or 0),
                'description': str(definition.get('description') or ''),
                'requirement_text': gap['requirement_text'],
                'material_gap': gap['material_gap'],
                'material_gap_count': gap['material_gap_count'],
                'games': 0,
                'appearances': 0,
                'wins_when_appeared': 0,
                'first_turns': [],
                'material_counts': [],
                'absorbed_powers': [],
                'final_powers': [],
                'effect_scores': [],
                'blocked': 0,
                'sample_lines': [],
            })
            stats['games'] += 1
            esper_name = stats['name']
            esper_instance_ids: set[str] = set()
            first_turn = None
            for turn_number, action in actions:
                if str(action.get('side') or '') != side or action.get('kind') != 'reveal_card':
                    continue
                card = action.get('card') if isinstance(action.get('card'), dict) else {}
                if str(card.get('definition_id') or '') != esper_id:
                    continue
                esper_instance_ids.add(str(action.get('source_instance_id') or card.get('instance_id') or ''))
                first_turn = turn_number if first_turn is None else min(first_turn, turn_number)
            if first_turn is not None:
                stats['appearances'] += 1
                stats['wins_when_appeared'] += 1 if won else 0
                stats['first_turns'].append(first_turn)
            material_count = 0
            material_power = 0
            for _, action in actions:
                if action.get('kind') != 'consume_material':
                    continue
                title = str(action.get('title') or '')
                if esper_name not in title and str(action.get('target_instance_id') or '') not in esper_instance_ids:
                    continue
                material_count += 1
                material_power += int(action.get('material_power') or 0)
            if material_count:
                stats['material_counts'].append(material_count)
                stats['absorbed_powers'].append(material_power)
            for final_esper in metric.get('final_espers', []):
                if str(final_esper.get('id') or '') == esper_id:
                    stats['final_powers'].append(int(final_esper.get('computed_power') or 0))
            effect_lines = [line for line in logs if line.startswith(esper_name)]
            if effect_lines:
                score = sum(_line_impact_score(line) for line in effect_lines)
                stats['effect_scores'].append(score)
                stats['sample_lines'].extend(effect_lines[:3])
                del stats['sample_lines'][8:]
            if any(esper_name in line and any(token in line for token in ('素材不足', '共鸣取消', '返回异能者编队')) for line in logs):
                stats['blocked'] += 1


def _public_esper_stats(esper_stats: dict[str, JsonDict]) -> list[JsonDict]:
    public = []
    for stats in esper_stats.values():
        appearances = int(stats.get('appearances') or 0)
        games = int(stats.get('games') or 0)
        public.append({
            'deck_id': stats['deck_id'],
            'deck_label': stats['deck_label'],
            'card_id': stats['card_id'],
            'name': stats['name'],
            'type': turn_flow.CARD_TYPE_ESPER,
            'id': stats['card_id'],
            'art': stats.get('art', ''),
            'icon': stats.get('icon', ''),
            'attribute': stats.get('attribute', ''),
            'attribute_icon': stats.get('attribute_icon', ''),
            'category': stats.get('category', ''),
            'rarity': stats.get('rarity', ''),
            'cost': int(stats.get('cost') or 0),
            'power': int(stats.get('power') or 0),
            'description': stats.get('description', ''),
            'games': games,
            'appearances': appearances,
            'appearance_rate': _pct(appearances, games),
            'win_rate_when_appeared': _pct(int(stats.get('wins_when_appeared') or 0), appearances),
            'avg_first_turn': _avg(stats.get('first_turns', [])),
            'avg_material_count': _avg(stats.get('material_counts', [])),
            'avg_absorbed_power': _avg(stats.get('absorbed_powers', [])),
            'avg_final_power': _avg(stats.get('final_powers', [])),
            'avg_effect_score': _avg(stats.get('effect_scores', [])),
            'blocked': int(stats.get('blocked') or 0),
            'requirement_text': stats.get('requirement_text', ''),
            'material_gap': stats.get('material_gap', ''),
            'material_gap_count': int(stats.get('material_gap_count') or 0),
            'sample_lines': stats.get('sample_lines', []),
        })
    return sorted(public, key=lambda item: (item['appearance_rate'], item['avg_effect_score'] or 0), reverse=True)


def _build_observations(
    decks: list[JsonDict],
    matchups: list[JsonDict],
    delay_records: list[JsonDict],
    espers: list[JsonDict],
    cards: list[JsonDict],
) -> list[str]:
    observations: list[str] = []
    if decks:
        best = max(decks, key=lambda item: item['win_rate'])
        worst = min(decks, key=lambda item: item['win_rate'])
        observations.append(f"当前样本胜率最高为 {best['label']}（{best['win_rate']}%），最低为 {worst['label']}（{worst['win_rate']}%）。")
        weakest_full_esper = min(decks, key=lambda item: item.get('all_esper_rate', 0))
        observations.append(f"{weakest_full_esper['label']} 的 4 名异能者全登场率为 {weakest_full_esper.get('all_esper_rate', 0)}%，平均登场 {weakest_full_esper.get('avg_unique_espers') or 0} 名。")
    delay_successes = [record for record in delay_records if record.get('success')]
    if delay_records:
        observations.append(f"延滞相关对局中，成功拖延或阻断异能者登场 {len(delay_successes)}/{len(delay_records)} 次。")
    slow_matchups = [
        item for item in matchups
        if item.get('avg_first_esper_turn') is not None and float(item['avg_first_esper_turn']) >= 5
    ]
    if slow_matchups:
        sample = slow_matchups[0]
        observations.append(f"{sample['deck_label']} 对 {sample['opponent_label']} 的首个异能者平均登场到 {sample['avg_first_esper_turn']} 回合，需要重点复盘素材链。")
    material_gap_espers = [item for item in espers if item.get('material_gap')]
    if material_gap_espers:
        sample = sorted(material_gap_espers, key=lambda item: item.get('material_gap_count', 0), reverse=True)[0]
        observations.append(f"{sample['deck_label']} 的 {sample['name']} 存在素材缺口：{sample['material_gap']}。")
    low_appearance_espers = [
        item for item in espers
        if item.get('appearance_rate', 0) < 25 or (item.get('avg_first_turn') is not None and float(item['avg_first_turn']) >= 6)
    ]
    if low_appearance_espers:
        sample = sorted(low_appearance_espers, key=lambda item: (item.get('appearance_rate', 0), item.get('avg_first_turn') or 99))[0]
        avg_turn = sample['avg_first_turn'] if sample.get('avg_first_turn') is not None else '无'
        observations.append(f"异能者 {sample['name']} 登场率/时机偏紧：登场率 {sample['appearance_rate']}%，平均回合 {avg_turn}。")
    if cards:
        top = cards[0]
        observations.append(f"按当前启发式影响分，最高影响卡为 {top['name']}（影响分 {top['impact_score']}，揭示 {top['reveals']} 次）。")
    return observations


def _acceptance_check(name: str, passed: bool, detail: str, value: Any = None) -> JsonDict:
    return {
        'name': name,
        'passed': bool(passed),
        'detail': detail,
        'value': value,
    }


def _build_acceptance(
    decks: list[JsonDict],
    matchups: list[JsonDict],
    espers: list[JsonDict],
    delay_breaks: list[JsonDict],
    samples: int,
) -> JsonDict:
    checks: list[JsonDict] = []
    deck_by_id = {str(deck.get('id') or ''): deck for deck in decks}
    triad_decks = [deck_by_id.get(deck_id) for deck_id in sorted(TRIAD_DECK_IDS)]
    expected_deck_games = int(samples) * 4
    expected_matchup_games = int(samples) * 2
    coverage_ok = all(deck and int(deck.get('games') or 0) == expected_deck_games for deck in triad_decks)
    matchup_games = {
        f"{item.get('deck_id')}->{item.get('opponent_deck_id')}": int(item.get('games') or 0)
        for item in matchups
        if str(item.get('deck_id') or '') in TRIAD_DECK_IDS
        and str(item.get('opponent_deck_id') or '') in TRIAD_DECK_IDS
    }
    expected_matchups = {
        f"{player_deck_id}->{opponent_deck_id}"
        for player_deck_id, opponent_deck_id in TRIAD_PAIRINGS
    }
    matchup_coverage_ok = all(matchup_games.get(key) == expected_matchup_games for key in expected_matchups)
    checks.append(_acceptance_check(
        '三角样本覆盖',
        coverage_ok and matchup_coverage_ok,
        f"创生、延滞、浊燃各应有 {expected_deck_games} 个侧样本；每个有向对局应有 {expected_matchup_games} 局。",
        {
            'decks': {
                str(deck.get('id')): int(deck.get('games') or 0)
                for deck in triad_decks
                if deck
            },
            'matchups': matchup_games,
        },
    ))

    win_rates = [float(deck.get('win_rate') or 0) for deck in triad_decks if deck]
    win_spread = round(max(win_rates) - min(win_rates), 1) if win_rates else 0.0
    checks.append(_acceptance_check(
        '三角胜率差',
        bool(win_rates) and win_spread <= 25.0,
        '最高胜率与最低胜率差不超过 25 个百分点；超过时优先复盘最高胜率套牌。',
        win_spread,
    ))

    first_turn_values = [
        float(deck.get('avg_first_esper_turn') or 99)
        for deck in triad_decks
        if deck
    ]
    checks.append(_acceptance_check(
        '首个异能者节奏',
        bool(first_turn_values) and max(first_turn_values) <= 4.5,
        '三套牌平均首个异能者应不晚于 4.5 回合。',
        {
            str(deck.get('label')): deck.get('avg_first_esper_turn')
            for deck in triad_decks
            if deck
        },
    ))

    unique_values = [
        float(deck.get('avg_unique_espers') or 0)
        for deck in triad_decks
        if deck
    ]
    checks.append(_acceptance_check(
        '异能者参与度',
        bool(unique_values) and min(unique_values) >= 2.0,
        '每套牌平均至少有 2 名不同异能者登场或再共鸣。',
        {
            str(deck.get('label')): deck.get('avg_unique_espers')
            for deck in triad_decks
            if deck
        },
    ))

    low_appearance_aces = [
        {
            'deck': item.get('deck_label'),
            'name': item.get('name'),
            'appearance_rate': item.get('appearance_rate'),
            'avg_first_turn': item.get('avg_first_turn'),
        }
        for item in espers
        if str(item.get('deck_id') or '') in TRIAD_DECK_IDS
        and (float(item.get('appearance_rate') or 0) < 25 or float(item.get('avg_first_turn') or 0) >= 6)
    ]
    checks.append(_acceptance_check(
        '低登场异能者排查',
        not low_appearance_aces,
        '登场率低于 25% 或平均登场不早于 6 回合的异能者需要进入下一轮问题列表。',
        low_appearance_aces,
    ))

    material_hits = sum(int(item.get('material_hits') or 0) for item in delay_breaks)
    checks.append(_acceptance_check(
        '延滞破坏素材证据',
        material_hits > 0,
        '延滞页必须记录成功命中素材组合的卡牌、目标和样例日志。',
        material_hits,
    ))

    return {
        'status': 'passed' if all(check['passed'] for check in checks) else 'attention',
        'checks': checks,
    }


def write_dashboard_data(result: JsonDict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result.get('analytics', {}), ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the fixed triad dashboard evaluation.')
    parser.add_argument('--seed', type=int, default=60606)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--focus', choices=('triad',), default='triad', help='固定为 triad，仅保留向后兼容的参数。')
    parser.add_argument('--samples', type=int, default=4)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dashboard-output', type=Path, default=ANALYTICS_OUTPUT_PATH)
    parser.add_argument('--write-dashboard', dest='write_dashboard', action='store_true', default=True)
    parser.add_argument('--no-write-dashboard', dest='write_dashboard', action='store_false')
    args = parser.parse_args()
    configure_eval_runtime()
    pairings = TRIAD_PAIRINGS
    samples = max(1, int(args.samples or 1))
    matches = []
    for sample_index in range(samples):
        for pairing_index, (player_deck_id, opponent_deck_id) in enumerate(pairings):
            match = run_match(player_deck_id, opponent_deck_id, args.seed + sample_index * 1000 + pairing_index)
            match['sample_index'] = sample_index
            match['pairing_index'] = pairing_index
            match['seed'] = args.seed + sample_index * 1000 + pairing_index
            matches.append(match)
    result = summarize(matches)
    result['analytics'] = build_analytics(result, seed=args.seed, samples=samples, focus='triad')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.write_dashboard:
        write_dashboard_data(result, args.dashboard_output)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    analytics = result['analytics']
    for deck in sorted(analytics.get('decks', []), key=lambda item: str(item.get('id') or '')):
        print(
            f"{deck['label']}: 胜率 {deck['win_rate']}% / "
            f"首异能者 {deck.get('avg_first_esper_turn') or '-'} / "
            f"平均登场 {deck.get('avg_unique_espers') or '-'} / "
            f"全登场 {deck.get('all_esper_rate') or 0}%"
        )
    acceptance = analytics.get('acceptance', {})
    print(f"看板验收: {acceptance.get('status', 'unknown')}")
    if args.write_dashboard:
        print(f"看板数据: {args.dashboard_output}")


if __name__ == '__main__':
    main()
