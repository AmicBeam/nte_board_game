from __future__ import annotations

import random
from copy import deepcopy

from app.content.loader import get_duel_card
from app.engine.application.build_service import card_by_id as _card_by_id
from app.engine.ai.player import AiRules, run_ai_turn as _run_ai_turn_impl
from app.engine.rules.declarations import (
    ensure_required_target_before_play as _ensure_required_target_before_play,
    find_target_card as _find_target_card,
    prepare_declaration_selection as _prepare_declaration_selection,
    prepare_declaration_target as _prepare_declaration_target,
    resolve_declaration_selection as _resolve_declaration_selection,
    target_rule as _target_rule,
)
from app.engine.event_bus import dispatch_event
from app.engine.events import GameEvent
from app.engine.rules.materials import (
    cards_by_instance_ids as _cards_by_instance_ids,
    esper_material_cost as _esper_material_cost,
    esper_material_filter_text as _esper_material_filter_text,
    esper_material_requirement_text as _esper_material_requirement_text,
    is_valid_esper_material as _is_valid_esper_material,
    location_has_room_after_materials as _location_has_room_after_materials,
    material_absorb_power as _material_absorb_power,
    material_attribute as _material_attribute,
    material_cards_for_esper as _material_cards_for_esper,
    material_tags_for_card as _material_tags_for_card,
    release_material_reservations as _release_material_reservations,
    reserve_materials as _reserve_materials,
)
from app.engine.setup.snapshot_factory import (
    card_instance as _card_instance_impl,
)
from app.engine.state.types import JsonDict
from app.errors import RuleValidationError

GAME_ID = 'anomaly_snap_duel'
SCHEMA_VERSION = 1
SIDE_A = 'a'
SIDE_B = 'b'
SIDE_KEYS = (SIDE_A, SIDE_B)
MAX_TURNS = 6
MAX_ENERGY = 6
MAX_HAND_SIZE = 10
LOCATION_CARD_LIMIT = 16
LOG_LIMIT = 28

TAG_MURK = 'murk'
TAG_DELAY = 'delay'
TAG_DARKSTAR = 'darkstar'
TAG_GENESIS = 'genesis'
TAG_SURPLUS = 'surplus'
TAG_DISCORD = 'discord'
TAG_COLLAPSING = 'collapsing'
TAG_ZHUE_HUCHI = 'zhue_huchi'
TAG_NIGHTMARE = 'nightmare'
TAG_PANYU_QIU = 'panyu_qiu'
TAG_MATERIAL = 'material'
TAG_HARMONY = 'harmony'
CARD_TYPE_ESPER = 'esper'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'
CARD_TYPE_TOKEN = 'token'
CARD_BACK_IMAGE = '/static/images/cards/card-back.svg'
HARMONY_TAGS = frozenset({TAG_GENESIS, TAG_MURK, TAG_DELAY, TAG_DARKSTAR, TAG_SURPLUS, TAG_DISCORD, TAG_COLLAPSING})
DECAYING_HARMONY_TAGS = (TAG_GENESIS, TAG_MURK, TAG_DELAY, TAG_SURPLUS, TAG_DISCORD, TAG_ZHUE_HUCHI, TAG_NIGHTMARE, TAG_PANYU_QIU)
LOCATION_MARK_NAMES = {
    TAG_GENESIS: '创生',
    TAG_MURK: '浊燃',
    TAG_DELAY: '延滞',
    TAG_DARKSTAR: '黯星',
    TAG_DISCORD: '失谐',
    TAG_SURPLUS: '盈蓄',
    TAG_COLLAPSING: '倾陷',
    TAG_ZHUE_HUCHI: '诛恶护持',
    TAG_NIGHTMARE: '噩梦',
    TAG_PANYU_QIU: '判予秋',
}

def _card_instance(definition: JsonDict, side: str, suffix: str) -> JsonDict:
    return _card_instance_impl(definition, side, suffix)



def _resolve_opening_selection(snapshot: JsonDict, side: str, selected_ids: list[str]) -> None:
    selection = snapshot['sides'][side].get('selection') or {}
    if selection.get('kind') != 'opening':
        return
    available = {str(card.get('instance_id')): card for card in selection.get('cards', [])}
    chosen_ids = [str(card_id) for card_id in selected_ids if str(card_id) in available]
    if not chosen_ids:
        chosen_ids = [str(card.get('instance_id')) for card in selection.get('cards', [])[:int(selection.get('pick_count') or 0)]]
    snapshot['sides'][side]['selection'] = None
    # Legacy opening selections are already represented in zones for current snapshots; keep this path as a no-op resolver.


def _resolve_draw_selection(snapshot: JsonDict, side: str, selected_ids: list[str]) -> None:
    _resolve_legacy_draw_selection_as_auto_draw(snapshot, side)


def _resolve_legacy_draw_selection_as_auto_draw(snapshot: JsonDict, side: str) -> bool:
    side_state = snapshot['sides'][side]
    selection = side_state.get('selection') or {}
    if selection.get('kind') != 'draw':
        return False
    side_state['selection'] = None
    _draw_cards(snapshot, side, 1, reason='回合补牌')
    return True


def _clear_legacy_draw_selections(snapshot: JsonDict, *, auto_draw: bool = False) -> bool:
    changed = False
    for side in SIDE_KEYS:
        selection = snapshot['sides'][side].get('selection') or {}
        if selection.get('kind') != 'draw':
            continue
        if auto_draw:
            changed = _resolve_legacy_draw_selection_as_auto_draw(snapshot, side) or changed
        else:
            snapshot['sides'][side]['selection'] = None
            changed = True
    return changed


def _resolve_ai_pending_choices(snapshot: JsonDict, side: str) -> None:
    while snapshot['sides'][side].get('selection'):
        selection = snapshot['sides'][side]['selection']
        if selection.get('kind') == 'draw':
            _resolve_legacy_draw_selection_as_auto_draw(snapshot, side)
        elif selection.get('kind') == 'declaration':
            selected_ids = _ai_selection_ids(snapshot['sides'][side], selection)
            _resolve_declaration_selection(snapshot, side, selected_ids)
        else:
            selected_ids = _ai_selection_ids(snapshot['sides'][side], selection)
            snapshot['sides'][side]['selection'] = None


def _ai_selection_ids(side_state: JsonDict, selection: JsonDict) -> list[str]:
    cards = list(selection.get('cards', []))
    priority = _ai_priority(side_state)
    cards.sort(
        key=lambda card: (
            priority.get(card.get('definition_id'), -99),
            int(card.get('cost', 0)),
            int(card.get('base_power', 0)),
        ),
        reverse=True,
    )
    pick_count = int(selection.get('pick_count', 1))
    return [card['instance_id'] for card in cards[:pick_count]]


def _ai_priority(side_state: JsonDict) -> dict[str, int]:
    priority_ids = list(side_state.get('ai_plan', {}).get('priority_card_ids', []))
    return {str(card_id): len(priority_ids) - index for index, card_id in enumerate(priority_ids)}


def _sync_planning_phase(snapshot: JsonDict) -> None:
    if snapshot['status'] != 'playing':
        return
    _clear_legacy_draw_selections(snapshot)
    snapshot['phase'] = 'selecting' if any(snapshot['sides'][side].get('selection') for side in SIDE_KEYS) else 'planning'


def _next_play_sequence(snapshot: JsonDict) -> int:
    counter = int(snapshot.get('play_sequence_counter', 0)) + 1
    snapshot['play_sequence_counter'] = counter
    return counter


def _lock_settlement_initiative(snapshot: JsonDict, *, emit_action: bool = True) -> None:
    _recompute_scores(snapshot)
    totals = {side: _stable_total_power(snapshot, side) for side in SIDE_KEYS}
    if totals[SIDE_A] > totals[SIDE_B]:
        first_side = SIDE_A
        leader_side: str | None = SIDE_A
        reason = '战力领先'
    elif totals[SIDE_B] > totals[SIDE_A]:
        first_side = SIDE_B
        leader_side = SIDE_B
        reason = '战力领先'
    else:
        first_side = random.choice(list(SIDE_KEYS))
        leader_side = None
        reason = '战力持平，随机决定'
    snapshot['settlement'] = {
        'turn': int(snapshot.get('turn', 1)),
        'first_side': first_side,
        'leader_side': leader_side,
        'reason': reason,
        'totals': totals,
    }
    snapshot['settlement_first_side'] = first_side
    _add_log(snapshot, f"第 {snapshot.get('turn', 1)} 回合结算先手：{_side_name(snapshot, first_side)}（{reason}，{totals[SIDE_A]}-{totals[SIDE_B]}）。")
    if not emit_action:
        return
    snapshot.setdefault('action_queue', []).append({
        'kind': 'initiative_decided',
        'side': first_side,
        'leader_side': leader_side,
        'title': '结算先手',
        'subtitle': f"{_side_name(snapshot, first_side)} 先揭示（{totals[SIDE_A]}-{totals[SIDE_B]}）",
    })


def _stable_total_power(snapshot: JsonDict, side: str) -> int:
    return sum(int(location.get('power', {}).get(side, 0) or 0) for location in snapshot.get('locations', []))


def _begin_turn(snapshot: JsonDict) -> None:
    snapshot['turn_undo_checkpoints'] = {}
    _clear_legacy_draw_selections(snapshot)
    _reset_turn_flags(snapshot)
    _decay_harmony_layers_at_turn_start(snapshot)
    _sweep_broken_cards(snapshot)
    _recompute_scores(snapshot)
    _lock_settlement_initiative(snapshot, emit_action=False)
    for side in SIDE_KEYS:
        snapshot['sides'][side]['energy_used'] = 0
        snapshot['sides'][side]['ended_turn'] = False
        _draw_cards(snapshot, side, 1, reason='回合补牌')
    _sync_planning_phase(snapshot)


def _snapshot_for_turn_undo(snapshot: JsonDict) -> JsonDict:
    checkpoint = deepcopy(snapshot)
    checkpoint.pop('turn_undo_checkpoints', None)
    return checkpoint


def _turn_undo_checkpoint(snapshot: JsonDict, side: str) -> JsonDict | None:
    checkpoint = snapshot.get('turn_undo_checkpoints', {}).get(side)
    if not isinstance(checkpoint, dict):
        return None
    if int(checkpoint.get('turn') or 0) != int(snapshot.get('turn') or 0):
        return None
    return checkpoint


def _can_undo_turn(snapshot: JsonDict, side: str) -> bool:
    if snapshot.get('status') != 'playing' or snapshot.get('phase') != 'planning':
        return False
    if snapshot.get('sides', {}).get(side, {}).get('ended_turn'):
        return False
    return _turn_undo_checkpoint(snapshot, side) is not None


def _ensure_turn_undo_checkpoint(snapshot: JsonDict, side: str) -> None:
    if snapshot.get('status') != 'playing' or snapshot.get('phase') != 'planning':
        return
    if snapshot.get('sides', {}).get(side, {}).get('ended_turn'):
        return
    checkpoints = snapshot.setdefault('turn_undo_checkpoints', {})
    if _turn_undo_checkpoint(snapshot, side) is not None:
        return
    checkpoints[side] = {
        'turn': int(snapshot.get('turn') or 0),
        'snapshot': _snapshot_for_turn_undo(snapshot),
    }


def _restore_side_from_turn_undo(snapshot: JsonDict, side: str, restored_snapshot: JsonDict) -> None:
    snapshot['sides'][side] = deepcopy(restored_snapshot['sides'][side])
    restored_locations = {
        str(location.get('id')): location
        for location in restored_snapshot.get('locations', [])
    }
    for location in snapshot.get('locations', []):
        restored_location = restored_locations.get(str(location.get('id')))
        if restored_location is None:
            continue
        location.setdefault('cards', {})[side] = deepcopy(restored_location.get('cards', {}).get(side, []))
        current_marks = location.setdefault('marks', {})
        restored_marks = deepcopy(restored_location.get('marks', {}).get(side, {}))
        if restored_marks:
            current_marks[side] = restored_marks
        else:
            current_marks.pop(side, None)


def _reset_turn_flags(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in location.get('cards', {}).get(side, []):
                card.pop('moved_this_turn', None)
    for side in SIDE_KEYS:
        combo = snapshot['sides'][side].setdefault('combo', {})
        if combo.get('movement_locked_turn') != snapshot.get('turn'):
            combo.pop('movement_locked_turn', None)
        if combo.get('extension_tax') != snapshot.get('turn'):
            combo.pop('extension_tax', None)


def _location_mark_count(location: JsonDict, side: str, tag: str) -> int:
    return int(location.get('marks', {}).get(side, {}).get(tag, 0) or 0)


def _consume_location_mark(location: JsonDict, side: str, tag: str, amount: int = 1) -> int:
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    current = int(mark_bucket.get(tag, 0) or 0)
    consumed = min(current, max(0, amount))
    if consumed <= 0:
        return 0
    remaining = current - consumed
    if remaining:
        mark_bucket[tag] = remaining
    else:
        mark_bucket.pop(tag, None)
    return consumed


def _legacy_harmony_cards(location: JsonDict, side: str, tag: str) -> list[JsonDict]:
    return [
        card
        for card in list(location.get('cards', {}).get(side, []))
        if card.get('revealed') and tag in card.get('tags', []) and TAG_HARMONY in card.get('tags', [])
    ]


def _decay_harmony_layers_at_turn_start(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        marks = location.setdefault('marks', {})
        for side in SIDE_KEYS:
            mark_bucket = marks.setdefault(side, {})
            for tag in DECAYING_HARMONY_TAGS:
                current = int(mark_bucket.get(tag, 0) or 0)
                if current <= 0:
                    continue
                if current <= 1:
                    mark_bucket.pop(tag, None)
                else:
                    mark_bucket[tag] = current - 1


def _resolve_harmony_end_of_turn(snapshot: JsonDict, *, final_turn: bool = False) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            _resolve_genesis_end_of_turn(snapshot, location, side)
            _resolve_murk_end_of_turn(snapshot, location, side)
            _resolve_nightmare_end_of_turn(snapshot, location, side)
            _resolve_panyu_qiu_end_of_turn(snapshot, location, side)
            if final_turn:
                _resolve_darkstar_end_of_turn(snapshot, location, side)


def _resolve_genesis_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    count = _location_mark_count(location, side, TAG_GENESIS)
    if count <= 0:
        return
    candidates = [
        card
        for card in location['cards'][side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    if not candidates:
        return
    target = random.choice(candidates)
    power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
    _boost_card(target, count, '创生')
    power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
    snapshot.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_location_id': location['id'],
        'target_instance_id': target['instance_id'],
        'title': '创生',
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} + {count} = {power_after}',
    })
    _add_log(snapshot, f"{location['name']} 的创生标记使 {target['name']} +{count} 战力。")


def _resolve_murk_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    murk_count = _location_mark_count(location, side, TAG_MURK) + len(_legacy_harmony_cards(location, side, TAG_MURK))
    target_side = _opponent_side(side)
    for _ in range(murk_count):
        candidates = [
            card
            for card in location['cards'][target_side]
            if card.get('revealed')
            and TAG_COLLAPSING not in card.get('tags', [])
            and card.get('type') != 'token'
        ]
        if not candidates:
            break
        non_negative = [
            card
            for card in candidates
            if int(card.get('computed_power', _raw_card_power(card))) >= 0
        ]
        target = max(non_negative or candidates, key=lambda item: int(item.get('computed_power', _raw_card_power(item))))
        power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
        _boost_card(target, -1, '浊燃')
        power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'side': side,
            'target_instance_id': target['instance_id'],
            'title': '浊燃',
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} - 1 = {power_after}',
        })
        _add_log(snapshot, f"{location['name']} 的浊燃使 {target['name']} -1 战力。")


def _resolve_nightmare_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    if _location_mark_count(location, side, TAG_NIGHTMARE) <= 0:
        return
    target_side = _opponent_side(side)
    targets = [
        card
        for card in location['cards'][target_side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    for target in targets:
        power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
        _boost_card(target, -1, '噩梦')
        power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'side': side,
            'target_instance_id': target['instance_id'],
            'title': '噩梦',
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} - 1 = {power_after}',
        })
    if targets:
        _add_log(snapshot, f"{location['name']} 的噩梦使 {len(targets)} 张敌方牌 -1 战力。")


def _resolve_panyu_qiu_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    if _location_mark_count(location, side, TAG_PANYU_QIU) <= 0:
        return
    target_side = _opponent_side(side)
    targets = [
        card
        for card in list(location['cards'][target_side])
        if card.get('revealed')
        and card.get('type') != CARD_TYPE_TOKEN
        and int(card.get('computed_power', _raw_card_power(card)) or 0) <= 3
    ]
    for target in targets:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'discard_card',
            'source_location_id': location['id'],
            'location_id': location['id'],
            'side': target_side,
            'title': '判予秋',
            'subtitle': f'{target["name"]} 被斩杀。',
            'card': _public_card(target, own=True),
        })
        if target.get('type') == CARD_TYPE_ESPER:
            location['cards'][target_side].remove(target)
            _release_material_reservations(snapshot, target_side, target['instance_id'])
            _reset_esper_to_standby(snapshot, target_side, target)
        else:
            _release_material_reservations(snapshot, target_side, target['instance_id'])
            _remove_board_card(snapshot, target_side, location, target)
    if targets:
        _add_log(snapshot, f"{location['name']} 的判予秋斩杀 {len(targets)} 张战力不高于 3 的敌方牌。")


def _resolve_darkstar_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    darkstar_count = _location_mark_count(location, side, TAG_DARKSTAR)
    legacy_darkstars = _legacy_harmony_cards(location, side, TAG_DARKSTAR)
    if darkstar_count <= 0 and not legacy_darkstars:
        return
    _consume_location_mark(location, side, TAG_DARKSTAR, darkstar_count)
    for darkstar in legacy_darkstars:
        _remove_board_card(snapshot, side, location, darkstar)
    amount = max(1, darkstar_count + len(legacy_darkstars))
    damage = min(6, 2 * amount)
    target_side = _opponent_side(side)
    targets = [
        card
        for card in location['cards'][target_side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    for target in targets:
        power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
        _boost_card(target, -damage, '黯星')
        power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'side': side,
            'target_instance_id': target['instance_id'],
            'title': '黯星',
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} - {damage} = {power_after}',
        })
    removed_murk = _consume_location_mark(location, side, TAG_MURK, _location_mark_count(location, side, TAG_MURK))
    replaced = _collapse_remaining_murks(location, side)
    _add_log(snapshot, f"{location['name']} 的黯星标记爆发，使 {len(targets)} 张牌 -{damage} 战力，并清理 {removed_murk + replaced} 个浊燃。")


def _collapse_remaining_murks(location: JsonDict, side: str) -> int:
    replaced = 0
    for card in location['cards'][side]:
        if not card.get('revealed') or TAG_MURK not in card.get('tags', []) or TAG_HARMONY not in card.get('tags', []):
            continue
        current_power = int(card.get('computed_power', _raw_card_power(card)))
        card['definition_id'] = 'collapsing_card'
        card['name'] = '倾陷中的卡牌'
        card['type'] = 'token'
        card['cost'] = 0
        card['cost_modifier'] = 0
        card['base_power'] = current_power
        card['bonus_power'] = 0
        card['computed_power'] = current_power
        card['description'] = '被黯星封存后的卡牌，只保留当前战力，不再拥有持续型效果。'
        card['tags'] = ['token', TAG_COLLAPSING]
        replaced += 1
    return replaced


def _resolve_turn(snapshot: JsonDict) -> None:
    snapshot['phase'] = 'revealing'
    snapshot['banner_queue'] = []
    first_side = _settlement_first_side(snapshot)
    second_side = _opponent_side(first_side)
    snapshot['action_queue'] = [{
        'kind': 'reveal_phase_begin',
        'title': '揭示阶段开始',
        'subtitle': '双方覆盖卡牌进入结算。',
    }]
    _append_covered_card_messages(snapshot)
    _resolve_pending_material_consumption(snapshot)
    for side in (first_side, second_side):
        snapshot.setdefault('action_queue', []).append({
            'kind': 'reveal_side_begin',
            'side': side,
            'title': f"{_side_name(snapshot, side)} 揭示",
        })
        revealed_ids: set[str] = set()
        while True:
            staged = [
                (location, card)
                for location, card in _staged_cards_for_side(snapshot, side)
                if str(card.get('instance_id') or '') not in revealed_ids
            ]
            if not staged:
                break
            location, card = staged[0]
            revealed_ids.add(str(card.get('instance_id') or ''))
            _reveal_card(snapshot, side, location, card)
            _sweep_broken_cards(snapshot)
    _recompute_scores(snapshot)
    is_final_turn = int(snapshot['turn']) >= int(snapshot.get('max_turns', MAX_TURNS))
    _dispatch_revealed_card_turn_end(snapshot)
    _resolve_harmony_end_of_turn(snapshot, final_turn=is_final_turn)
    _sweep_broken_cards(snapshot)
    _recompute_scores(snapshot)

    if is_final_turn:
        _finish_game(snapshot)
        return

    snapshot['turn'] += 1
    snapshot.setdefault('action_queue', []).append({
        'kind': 'turn_begin',
        'title': f'第 {snapshot["turn"]} 回合开始',
        'subtitle': f'获得 {_turn_energy(snapshot)} 点能量',
    })
    _begin_turn(snapshot)
    _reveal_locations_for_turn(snapshot)
    _recompute_scores(snapshot)
    _add_log(snapshot, f'第 {snapshot["turn"]} 回合开始，双方获得 {_turn_energy(snapshot)} 点能量。')


def _dispatch_revealed_card_turn_end(snapshot: JsonDict) -> None:
    revealed_cards = [
        (side, location, card)
        for location in snapshot.get('locations', [])
        for side in SIDE_KEYS
        for card in list(location.get('cards', {}).get(side, []))
        if card.get('revealed')
    ]
    for side, location, card in revealed_cards:
        if card not in location.get('cards', {}).get(side, []):
            continue
        opponent = _opponent_side(side)
        snapshot['_active_reveal_source_instance_id'] = card['instance_id']
        snapshot['_active_reveal_source_name'] = card['name']
        try:
            dispatch_event(snapshot, GameEvent.TURN_END, {
                'target_instance_id': card['instance_id'],
                'card_instance_id': card['instance_id'],
                'card': card,
                'side': side,
                'opponent_side': opponent,
                'location': location,
                'location_id': location['id'],
                'location_index': _location_index(snapshot, location['id']),
            })
        finally:
            snapshot.pop('_active_reveal_source_instance_id', None)
            snapshot.pop('_active_reveal_source_name', None)


def _append_covered_card_messages(snapshot: JsonDict) -> None:
    for side in SIDE_KEYS:
        names = [card['name'] for _, card in _staged_cards_for_side(snapshot, side)]
        snapshot.setdefault('action_queue', []).append({
            'kind': 'message',
            'side': side,
            'title': f"{_side_name(snapshot, side)} 成功覆盖",
            'subtitle': '、'.join(names) if names else '没有覆盖新牌。',
        })


def _settlement_first_side(snapshot: JsonDict) -> str:
    first_side = str(snapshot.get('settlement', {}).get('first_side') or snapshot.get('settlement_first_side') or '')
    if first_side in SIDE_KEYS:
        return first_side
    _lock_settlement_initiative(snapshot, emit_action=False)
    return str(snapshot.get('settlement', {}).get('first_side') or SIDE_A)


def _staged_cards_for_side(snapshot: JsonDict, side: str) -> list[tuple[JsonDict, JsonDict]]:
    staged: list[tuple[int, int, int, JsonDict, JsonDict]] = []
    turn = int(snapshot.get('turn') or 0)
    for location_index, location in enumerate(snapshot.get('locations', [])):
        for card_index, card in enumerate(location.get('cards', {}).get(side, [])):
            if not card.get('revealed') and int(card.get('played_turn') or 0) == turn:
                sequence = int(card.get('play_sequence') or 0)
                staged.append((sequence if sequence > 0 else 10_000 + card_index, location_index, card_index, location, card))
    staged.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(location, card) for _, _, _, location, card in staged]


def _resolve_pending_material_consumption(snapshot: JsonDict) -> None:
    _sweep_broken_cards(snapshot)
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            espers = [
                card
                for card in list(location.get('cards', {}).get(side, []))
                if (
                    _is_pending_esper_entry(snapshot, card)
                    or _is_pending_esper_reactivation(snapshot, card)
                )
            ]
            for esper in espers:
                is_reactivation = _is_pending_esper_reactivation(snapshot, esper)
                material_ids = [str(card_id) for card_id in esper.get('pending_material_ids', [])]
                materials = [
                    card
                    for card in list(location['cards'][side])
                    if str(card.get('instance_id')) in material_ids and _is_valid_reserved_material(card, esper['instance_id'])
                ]
                required = _esper_material_cost(esper)
                if len(materials) < required:
                    _release_material_reservations(snapshot, side, esper['instance_id'])
                    if is_reactivation:
                        esper.pop('pending_material_ids', None)
                        esper.pop('reactivating_turn', None)
                        _add_log(snapshot, f"{esper['name']} 的共鸣素材不足，共鸣取消。")
                    else:
                        _add_log(snapshot, f"{esper['name']} 的素材不足，返回异能者编队。")
                        location['cards'][side].remove(esper)
                        _reset_esper_to_standby(snapshot, side, esper)
                    continue
                consumed_material_tags: list[str] = []
                consumed_material_names: list[str] = []
                consumed_material_attributes: list[str] = []
                absorbed_power = 0
                for material in materials[:required]:
                    material_power = _material_absorb_power(material)
                    absorbed_power += material_power
                    consumed_material_tags.extend(_material_tags_for_card(material))
                    consumed_material_names.append(str(material.get('name') or '素材'))
                    if _material_attribute(material):
                        consumed_material_attributes.append(_material_attribute(material))
                    snapshot.setdefault('action_queue', []).append({
                        'kind': 'consume_material',
                        'source_instance_id': material['instance_id'],
                        'target_instance_id': esper['instance_id'],
                        'location_id': location['id'],
                        'side': side,
                        'title': f"{material['name']} -> {esper['name']}",
                        'subtitle': f"吸收 {material_power} 战力",
                        'material_power': material_power,
                        'card': _public_card(material, own=True),
                    })
                    _remove_board_card(snapshot, side, location, material)
                    _add_log(snapshot, f"{esper['name']} 消耗 {material['name']} 作为共鸣素材，吸收 {material_power} 战力。")
                if absorbed_power:
                    _boost_card(esper, absorbed_power, '素材吸收')
                if consumed_material_tags:
                    esper.setdefault('consumed_material_tags', [])
                    esper['consumed_material_tags'].extend(consumed_material_tags)
                if consumed_material_names:
                    esper.setdefault('consumed_material_names', [])
                    esper['consumed_material_names'].extend(consumed_material_names)
                if consumed_material_attributes:
                    esper.setdefault('consumed_material_attributes', [])
                    esper['consumed_material_attributes'].extend(consumed_material_attributes)
                esper['absorbed_material_power'] = int(esper.get('absorbed_material_power', 0)) + absorbed_power
                esper.pop('pending_material_ids', None)
                esper.pop('summoned_from', None)
                if is_reactivation:
                    esper.pop('reactivating_turn', None)
                    _resolve_esper_reactivation(snapshot, side, location, esper)
    _sweep_broken_cards(snapshot)


def _is_valid_reserved_material(card: JsonDict, esper_instance_id: str) -> bool:
    return _is_valid_esper_material({**card, 'reserved_as_material_for': ''}) and card.get('reserved_as_material_for') == esper_instance_id


def _is_pending_esper_entry(snapshot: JsonDict, card: JsonDict) -> bool:
    return bool(
        _is_staged_card(snapshot, card)
        and (card.get('summoned_from') == 'esper_standby' or card.get('type') == CARD_TYPE_ESPER)
    )


def _is_pending_esper_reactivation(snapshot: JsonDict, card: JsonDict) -> bool:
    return bool(
        card.get('type') == CARD_TYPE_ESPER
        and card.get('revealed')
        and int(card.get('reactivating_turn') or 0) == int(snapshot.get('turn', 0))
        and card.get('pending_material_ids')
    )


def _resolve_esper_reactivation(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    opponent = _opponent_side(side)
    logs_before_effect = list(snapshot.get('log', []))
    target_card = _find_card_on_board(snapshot, str(card.get('selected_target_instance_id', ''))) if card.get('selected_target_instance_id') else None
    power_before = _revealed_board_power_snapshot(snapshot)
    snapshot.setdefault('action_queue', []).append({
        'kind': 'esper_reactivation',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': f"{card['name']} 共鸣",
    })
    snapshot['_active_reveal_source_instance_id'] = card['instance_id']
    snapshot['_active_reveal_source_name'] = card['name']
    try:
        dispatch_event(snapshot, GameEvent.CARD_REVEALED, {
            'target_instance_id': card['instance_id'],
            'card_instance_id': card['instance_id'],
            'card': card,
            'side': side,
            'opponent_side': opponent,
            'location': location,
            'location_id': location['id'],
            'location_index': _location_index(snapshot, location['id']),
            'pre_location_gap': int(location['power'][side]) - int(location['power'][opponent]),
            'losing_locations_before': sum(1 for item in snapshot['locations'] if item.get('winner_side') == opponent),
            'selected_target_instance_id': card.get('selected_target_instance_id'),
            'target_card': target_card,
            'reactivated': True,
        })
    finally:
        snapshot.pop('_active_reveal_source_instance_id', None)
        snapshot.pop('_active_reveal_source_name', None)
    changed_ids = _append_power_change_arrows(snapshot, card['instance_id'], card['name'], power_before)
    if target_card is not None and target_card['instance_id'] not in changed_ids:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_instance_id': card['instance_id'],
            'target_instance_id': target_card['instance_id'],
            'title': card['name'],
        })
    effect_summary = _reveal_effect_summary(card['name'], _new_log_entries(snapshot, logs_before_effect))
    if effect_summary:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'effect_summary',
            'source_instance_id': card['instance_id'],
            'location_id': location['id'],
            'side': side,
            'title': card['name'],
            'effect_summary': effect_summary,
        })
    card.pop('selected_target_instance_id', None)
    card.pop('selected_target_name', None)


def _reset_esper_to_standby(snapshot: JsonDict, side: str, card: JsonDict) -> None:
    card['played_turn'] = None
    card['location_id'] = None
    card['revealed'] = False
    card.pop('staged', None)
    card.pop('paid_cost', None)
    card.pop('play_sequence', None)
    card.pop('pending_material_ids', None)
    card.pop('selected_target_instance_id', None)
    card.pop('selected_target_name', None)
    card.pop('declared_card_instance_ids', None)
    card.pop('declared_card_names', None)
    card.pop('summoned_from', None)
    card.pop('consumed_material_tags', None)
    card.pop('consumed_material_names', None)
    card.pop('consumed_material_attributes', None)
    card.pop('absorbed_material_power', None)
    card.pop('reactivating_turn', None)
    card.pop('reserved_as_material_for', None)
    _reset_card_stats_from_definition(card)
    snapshot['sides'][side].setdefault('esper_standby', []).append(card)


def _consume_reveal_bonus_charge(snapshot: JsonDict, location: JsonDict, side: str, *, limit: int) -> bool:
    turn = int(snapshot.get('turn') or 0)
    trait_uses = location.setdefault('trait_uses', {}).setdefault(side, {})
    if int(trait_uses.get('turn') or 0) != turn:
        trait_uses.clear()
        trait_uses['turn'] = turn
        trait_uses['count'] = 0
    count = int(trait_uses.get('count') or 0)
    if count >= limit:
        return False
    trait_uses['count'] = count + 1
    return True


def _reveal_card(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    _recompute_scores(snapshot)
    opponent = _opponent_side(side)
    pre_location_gap = int(location['power'][side]) - int(location['power'][opponent])
    losing_locations_before = sum(1 for item in snapshot['locations'] if item.get('winner_side') == opponent)
    card['revealed'] = True
    card.pop('staged', None)
    _recompute_scores(snapshot)
    power_before = _revealed_board_power_snapshot(snapshot)
    _add_log(snapshot, f"{_side_name(snapshot, side)} 揭示 {card['name']}。")
    reveal_action = {
        'kind': 'reveal_card',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': card['name'],
        'card': _public_card(card, own=True),
    }
    snapshot.setdefault('action_queue', []).append(reveal_action)
    logs_before_effect = list(snapshot.get('log', []))
    target_card = _find_card_on_board(snapshot, str(card.get('selected_target_instance_id', ''))) if card.get('selected_target_instance_id') else None
    snapshot['_active_reveal_source_instance_id'] = card['instance_id']
    snapshot['_active_reveal_source_name'] = card['name']
    try:
        dispatch_event(snapshot, GameEvent.CARD_REVEALED, {
            'target_instance_id': card['instance_id'],
            'card_instance_id': card['instance_id'],
            'card': card,
            'side': side,
            'opponent_side': opponent,
            'location': location,
            'location_id': location['id'],
            'location_index': _location_index(snapshot, location['id']),
            'pre_location_gap': pre_location_gap,
            'losing_locations_before': losing_locations_before,
            'selected_target_instance_id': card.get('selected_target_instance_id'),
            'target_card': target_card,
        })
    finally:
        snapshot.pop('_active_reveal_source_instance_id', None)
        snapshot.pop('_active_reveal_source_name', None)
    changed_ids = _append_power_change_arrows(snapshot, card['instance_id'], card['name'], power_before)
    if target_card is not None and target_card['instance_id'] not in changed_ids:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_instance_id': card['instance_id'],
            'target_instance_id': target_card['instance_id'],
            'title': card['name'],
        })
    if (
        location['effect'] == 'revealed_cards_plus_one'
        and pre_location_gap <= 0
        and _consume_reveal_bonus_charge(snapshot, location, side, limit=3)
    ):
        power_before = int(card.get('computed_power', _raw_card_power(card)) or 0)
        card['bonus_power'] += 1
        _add_buff_source(card, location['name'], 1)
        _recompute_scores(snapshot)
        power_after = int(card.get('computed_power', _raw_card_power(card)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'target_instance_id': card['instance_id'],
            'title': location['name'],
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} + 1 = {power_after}',
        })
        _add_log(snapshot, f"{location['name']} 的潮汐让 {card['name']} +1 战力。")
    _vanish_revealed_card_if_needed(snapshot, side, location, card)
    effect_summary = _reveal_effect_summary(card['name'], _new_log_entries(snapshot, logs_before_effect))
    if effect_summary:
        reveal_action['effect_summary'] = effect_summary
    _sweep_broken_cards(snapshot)
    _recompute_scores(snapshot)


def _revealed_board_power_snapshot(snapshot: JsonDict) -> dict[str, int]:
    powers: dict[str, int] = {}
    _recompute_scores(snapshot)
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in location.get('cards', {}).get(side, []):
                if card.get('revealed'):
                    powers[str(card.get('instance_id'))] = int(card.get('computed_power', _raw_card_power(card)) or 0)
    return powers


def _append_power_change_arrows(
    snapshot: JsonDict,
    source_instance_id: str,
    source_name: str,
    power_before: dict[str, int],
) -> set[str]:
    changed_ids: set[str] = set()
    _recompute_scores(snapshot)
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in location.get('cards', {}).get(side, []):
                target_id = str(card.get('instance_id') or '')
                if not target_id or target_id == source_instance_id or not card.get('revealed'):
                    continue
                if target_id not in power_before:
                    continue
                current_power = int(card.get('computed_power', _raw_card_power(card)) or 0)
                if current_power == power_before[target_id]:
                    continue
                changed_ids.add(target_id)
                snapshot.setdefault('action_queue', []).append({
                    'kind': 'impact_arrow',
                    'source_instance_id': source_instance_id,
                    'target_instance_id': target_id,
                    'title': source_name,
                    'power_before': power_before[target_id],
                    'power_after': current_power,
                    'power_delta': current_power - power_before[target_id],
                    'subtitle': f"{power_before[target_id]} {'+' if current_power > power_before[target_id] else '-'} {abs(current_power - power_before[target_id])} = {current_power}",
                })
    return changed_ids


def _run_ai_turn(snapshot: JsonDict, side: str) -> None:
    _run_ai_turn_impl(
        snapshot,
        side,
        AiRules(
            resolve_pending_choices=_resolve_ai_pending_choices,
            energy_remaining=_energy_remaining,
            open_locations=_open_locations,
            cost_to_play=_cost_to_play,
            opponent_side=_opponent_side,
            recompute_scores=_recompute_scores,
            raw_card_power=_raw_card_power,
            next_play_sequence=_next_play_sequence,
            delay_tax=_delay_tax,
            consume_delay_tax=_consume_delay_tax,
            add_log=_add_log,
            side_name=_side_name,
            is_location_revealed=_is_location_revealed,
            side_reactivation_used=_side_reactivation_used,
            mark_side_reactivation=_mark_side_reactivation,
            location_occupied_card_count=_location_occupied_card_count,
        ),
    )


def _side_reactivation_used(snapshot: JsonDict, side: str) -> bool:
    combo = snapshot['sides'][side].setdefault('combo', {})
    return int(combo.get('esper_reactivation_turn') or 0) == int(snapshot.get('turn') or 0)


def _mark_side_reactivation(snapshot: JsonDict, side: str) -> None:
    snapshot['sides'][side].setdefault('combo', {})['esper_reactivation_turn'] = int(snapshot.get('turn') or 0)


def _finish_game(snapshot: JsonDict) -> None:
    _recompute_scores(snapshot)
    wins = {SIDE_A: 0, SIDE_B: 0}
    total_power = {SIDE_A: 0, SIDE_B: 0}
    for location in snapshot['locations']:
        total_power[SIDE_A] += location['power'][SIDE_A]
        total_power[SIDE_B] += location['power'][SIDE_B]
        if location['winner_side'] in SIDE_KEYS:
            wins[location['winner_side']] += 1
    if wins[SIDE_A] > wins[SIDE_B]:
        winner = SIDE_A
    elif wins[SIDE_B] > wins[SIDE_A]:
        winner = SIDE_B
    elif total_power[SIDE_A] > total_power[SIDE_B]:
        winner = SIDE_A
    elif total_power[SIDE_B] > total_power[SIDE_A]:
        winner = SIDE_B
    else:
        winner = None

    snapshot['winner_side'] = winner
    snapshot['phase'] = 'complete'
    if winner is None:
        snapshot['status'] = 'draw'
        _add_log(snapshot, '双方空间与总战力完全持平，对局平局。')
    elif winner == SIDE_A:
        snapshot['status'] = 'victory'
        _add_log(snapshot, f"{_side_name(snapshot, SIDE_A)} 赢下对局。")
    else:
        snapshot['status'] = 'defeat'
        _add_log(snapshot, f"{_side_name(snapshot, SIDE_B)} 赢下对局。")
    snapshot.setdefault('banner_queue', []).append({
        'kind': 'result',
        'title': '胜利' if snapshot['status'] == 'victory' else '失败' if snapshot['status'] == 'defeat' else '平局',
        'subtitle': '对局结束',
    })


def _reveal_locations_for_turn(snapshot: JsonDict) -> None:
    for location in snapshot['locations']:
        if not location['revealed'] and int(location['reveal_turn']) <= int(snapshot['turn']):
            location['revealed'] = True
            _add_log(snapshot, f"{location['name']} 显现：{location['description']}")


def _recompute_scores(snapshot: JsonDict) -> None:
    for location in snapshot['locations']:
        for side in SIDE_KEYS:
            revealed_cards = [
                card
                for card in location['cards'][side]
                if card.get('revealed') and _counts_as_location_slot(card)
            ]
            for card in location['cards'][side]:
                card['computed_power'] = _raw_card_power(card) + _location_power_bonus(location, side, card)
            location['power'][side] = sum(int(card['computed_power']) for card in revealed_cards)
        if location['power'][SIDE_A] > location['power'][SIDE_B]:
            location['winner_side'] = SIDE_A
        elif location['power'][SIDE_B] > location['power'][SIDE_A]:
            location['winner_side'] = SIDE_B
        else:
            location['winner_side'] = None
    snapshot['turn_energy'] = _turn_energy(snapshot)


def _location_power_bonus(location: JsonDict, side: str, card: JsonDict) -> int:
    if not card.get('revealed') or not _counts_as_location_slot(card):
        return 0
    if location['effect'] == 'first_card_plus_two':
        revealed = [
            item
            for item in location['cards'][side]
            if item.get('revealed') and _counts_as_location_slot(item)
        ]
        if revealed and revealed[0]['instance_id'] == card['instance_id']:
            _add_buff_source(card, location['name'], 2, replace_key=f'location:{location["id"]}')
            return 2
    if location['effect'] == 'solo_card_plus_four':
        revealed = [
            item
            for item in location['cards'][side]
            if item.get('revealed') and _counts_as_location_slot(item)
        ]
        if len(revealed) == 1 and revealed[0]['instance_id'] == card['instance_id']:
            _add_buff_source(card, location['name'], 4, replace_key=f'location:{location["id"]}')
            return 4
    return 0


def _draw_cards(snapshot: JsonDict, side: str, count: int, *, reason: str = '抽牌') -> list[JsonDict]:
    drawn: list[JsonDict] = []
    for _ in range(count):
        if not snapshot['sides'][side]['deck'] or len(snapshot['sides'][side]['hand']) >= MAX_HAND_SIZE:
            break
        card = snapshot['sides'][side]['deck'].pop(0)
        snapshot['sides'][side]['hand'].append(card)
        drawn.append(card)
        action: JsonDict = {
            'kind': 'draw_card',
            'side': side,
            'card_instance_id': card['instance_id'],
            'title': reason,
            'subtitle': '从牌库加入手牌',
            'reason': reason,
            'silent': reason == '回合补牌',
            'card': _public_card(card, own=True),
        }
        source_instance_id = str(snapshot.get('_active_reveal_source_instance_id') or '')
        if source_instance_id:
            action['source_instance_id'] = source_instance_id
        snapshot.setdefault('action_queue', []).append(action)
        _add_log(snapshot, f"{_side_name(snapshot, side)} 从牌库抽取 1 张牌。")
    return drawn


def _public_card(card: JsonDict, *, own: bool) -> JsonDict:
    if not own and not card.get('revealed'):
        return {
            'instance_id': card['instance_id'],
            'hidden': True,
            'revealed': False,
            'staged': bool(card.get('staged')),
            'name': '未揭示',
            'cost': None,
            'base_cost': None,
            'original_cost': None,
            'power': None,
            'base_power': None,
            'original_power': None,
            'art': CARD_BACK_IMAGE,
            'description': '对手本回合置入的牌，将在回合结束时揭示。',
            'type': card.get('type', 'esper'),
            'archetype': card.get('archetype', ''),
            'category': card.get('category', ''),
            'attribute': card.get('attribute', ''),
            'attribute_icon': card.get('attribute_icon', ''),
            'material_attributes': list(card.get('material_attributes', [])),
            'material_cost': card.get('material_cost', 0),
            'required_material_attribute': card.get('required_material_attribute', ''),
            'material_requirements': deepcopy(card.get('material_requirements') or []),
            'material_requirement_text': card.get('material_requirement_text', ''),
            'material_tags': list(card.get('material_tags', [])),
            'buff_sources': [],
        }
    return {
        'instance_id': card['instance_id'],
        'definition_id': card['definition_id'],
        'hidden': False,
        'revealed': card.get('revealed', False),
        'staged': bool(card.get('staged')),
        'name': card['name'],
        'cost': _effective_cost(card),
        'base_cost': card['cost'],
        'original_cost': card['cost'],
        'power': int(card.get('computed_power', _raw_card_power(card))),
        'base_power': card['base_power'],
        'original_power': card['base_power'],
        'bonus_power': card['bonus_power'],
        'element': card.get('element', ''),
        'rarity': card.get('rarity', 'n'),
        'art': card.get('art', CARD_BACK_IMAGE),
        'description': card.get('description', ''),
        'archetype': card.get('archetype', ''),
        'category': card.get('category', ''),
        'attribute': card.get('attribute', ''),
        'attribute_icon': card.get('attribute_icon', ''),
        'material_attributes': list(card.get('material_attributes', [])),
        'material_cost': int(card.get('material_cost') or 0),
        'required_material_attribute': card.get('required_material_attribute', ''),
        'material_requirements': deepcopy(card.get('material_requirements') or []),
        'material_requirement_text': card.get('material_requirement_text', ''),
        'material_tags': list(card.get('material_tags', [])),
        'consumed_material_tags': list(card.get('consumed_material_tags', [])),
        'consumed_material_names': list(card.get('consumed_material_names', [])),
        'consumed_material_attributes': list(card.get('consumed_material_attributes', [])),
        'absorbed_material_power': int(card.get('absorbed_material_power', 0)),
        'played_turn': card.get('played_turn'),
        'location_id': card.get('location_id'),
        'type': card.get('type', 'esper'),
        'tags': list(card.get('tags', [])),
        'buff_sources': [deepcopy(source) for source in card.get('buff_sources', [])],
        'target_rule': _target_rule(card) or None,
        'selected_target_instance_id': card.get('selected_target_instance_id'),
        'selected_target_name': card.get('selected_target_name', ''),
        'declared_card_names': list(card.get('declared_card_names', [])),
        'declared_card_instance_ids': list(card.get('declared_card_instance_ids', [])),
        'pending_material_ids': list(card.get('pending_material_ids', [])),
        'reserved_as_material_for': card.get('reserved_as_material_for'),
    }


def _opponent_side(side: str) -> str:
    return SIDE_B if side == SIDE_A else SIDE_A


def _is_snap_snapshot(snapshot: JsonDict) -> bool:
    return snapshot.get('game_id') == GAME_ID


def _ensure_playing(snapshot: JsonDict) -> None:
    if snapshot['status'] != 'playing':
        raise RuleValidationError('对局已经结束。')


def _ensure_selection_resolved(snapshot: JsonDict, side: str) -> None:
    selection = snapshot['sides'][side].get('selection')
    if selection and selection.get('kind') == 'draw':
        _resolve_legacy_draw_selection_as_auto_draw(snapshot, side)
    elif selection:
        raise RuleValidationError('请先完成当前卡牌选择。')
    if snapshot['sides'][side].get('pending_target'):
        raise RuleValidationError('请先为本次置入选择目标，或取消这张牌。')


def _ensure_not_ended(snapshot: JsonDict, side: str) -> None:
    if snapshot['sides'][side].get('ended_turn'):
        raise RuleValidationError('你已经结束本回合。')


def _find_location(snapshot: JsonDict, location_id: str) -> JsonDict:
    for location in snapshot['locations']:
        if location['id'] == location_id:
            return location
    raise RuleValidationError('未知的异象空间。')


def _is_location_revealed(snapshot: JsonDict, location: JsonDict) -> bool:
    return bool(location.get('revealed')) and int(location.get('reveal_turn', 1)) <= int(snapshot['turn'])


def _open_locations(snapshot: JsonDict, side: str) -> list[JsonDict]:
    return [
        location
        for location in snapshot['locations']
        if _is_location_revealed(snapshot, location) and _location_occupied_card_count(location, side) < LOCATION_CARD_LIMIT
    ]


def _counts_as_location_slot(card: JsonDict) -> bool:
    return not card.get('reserved_as_material_for')


def _location_occupied_card_count(
    location: JsonDict,
    side: str,
    *,
    excluding_instance_ids: set[str] | None = None,
) -> int:
    excluded = excluding_instance_ids or set()
    return sum(
        1
        for card in location.get('cards', {}).get(side, [])
        if str(card.get('instance_id') or '') not in excluded and _counts_as_location_slot(card)
    )


def _find_staged_card(snapshot: JsonDict, side: str, instance_id: str) -> tuple[JsonDict, JsonDict]:
    for location in snapshot['locations']:
        for card in location['cards'][side]:
            if card['instance_id'] != instance_id:
                continue
            if not _is_staged_card(snapshot, card):
                raise RuleValidationError('只有本回合尚未揭示的临时置入牌可以调整。')
            return card, location
    raise RuleValidationError('战场上没有这张可调整的临时牌。')


def _find_pending_source_card(snapshot: JsonDict, side: str, instance_id: str) -> tuple[JsonDict, JsonDict]:
    for location in snapshot['locations']:
        for card in location['cards'][side]:
            if card['instance_id'] != instance_id:
                continue
            if _is_staged_card(snapshot, card) or _is_pending_esper_reactivation(snapshot, card):
                return card, location
    raise RuleValidationError('战场上没有这张等待选择目标的牌。')


def _is_staged_card(snapshot: JsonDict, card: JsonDict) -> bool:
    return bool(
        card.get('staged')
        and not card.get('revealed')
        and int(card.get('played_turn') or 0) == int(snapshot.get('turn', 0))
    )


def _refund_card_cost(snapshot: JsonDict, side: str, card: JsonDict) -> None:
    refund = int(card.get('paid_cost', _effective_cost(card)))
    snapshot['sides'][side]['energy_used'] = max(0, int(snapshot['sides'][side].get('energy_used', 0)) - refund)


def _cost_to_play(snapshot: JsonDict, side: str, card: JsonDict, location: JsonDict) -> int:
    return _effective_cost(card) + _delay_tax(snapshot, side, location)


def _delay_tax(snapshot: JsonDict, side: str, location: JsonDict) -> int:
    source_side = _opponent_side(side)
    return 1 if (
        _location_mark_count(location, source_side, TAG_DELAY) > 0
        or _location_mark_count(location, source_side, TAG_SURPLUS) > 0
        or _first_delay_in_location(location, source_side) is not None
    ) else 0


def _first_delay_in_location(location: JsonDict, side: str) -> JsonDict | None:
    for card in location['cards'][side]:
        if card.get('revealed') and TAG_DELAY in card.get('tags', []) and TAG_HARMONY in card.get('tags', []):
            return card
    return None


def _consume_delay_tax(snapshot: JsonDict, side: str, location: JsonDict) -> None:
    source_side = _opponent_side(side)
    delay_card = _first_delay_in_location(location, source_side)
    consumed_mark = _consume_location_mark(location, source_side, TAG_DELAY, 1)
    consumed_surplus = 0
    if delay_card is None and consumed_mark <= 0:
        consumed_surplus = _consume_location_mark(location, source_side, TAG_SURPLUS, 1)
    if delay_card is None and consumed_mark <= 0:
        if consumed_surplus <= 0:
            return
    if delay_card is not None and consumed_mark <= 0:
        _remove_board_card(snapshot, source_side, location, delay_card)
    snapshot['sides'][source_side].setdefault('combo', {})['delay_consumed_by_opponent'] = (
        int(snapshot['sides'][source_side].setdefault('combo', {}).get('delay_consumed_by_opponent', 0)) + 1
    )
    mark_name = '盈蓄' if consumed_surplus else '延滞'
    _add_log(snapshot, f"{location['name']} 的{mark_name}被触发，{_side_name(snapshot, side)} 本次置入额外消耗 1 点能量。")
    if (
        not consumed_surplus
        and _has_revealed_tag(location, source_side, TAG_GENESIS)
        and _add_generated_card_to_hand(snapshot, source_side, 'surplus_charge') is not None
    ):
        _add_log(snapshot, f"{location['name']} 的创生接住延滞反冲，{_side_name(snapshot, source_side)} 获得 1 张盈蓄。")


def _has_revealed_tag(location: JsonDict, side: str, tag: str) -> bool:
    return _location_mark_count(location, side, tag) > 0 or any(card.get('revealed') and tag in card.get('tags', []) for card in location['cards'][side])


def _remove_board_card(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    try:
        location['cards'][side].remove(card)
    except ValueError:
        return
    card['location_id'] = None
    card.pop('staged', None)
    card.pop('paid_cost', None)
    card.pop('play_sequence', None)
    card.pop('reserved_as_material_for', None)
    card.pop('pending_material_ids', None)
    card.pop('selected_target_name', None)
    card.pop('declared_card_instance_ids', None)
    card.pop('declared_card_names', None)
    snapshot['sides'][side].setdefault('discard', []).append(card)


def _sweep_broken_cards(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            for card in list(location.get('cards', {}).get(side, [])):
                if not card.get('revealed'):
                    continue
                card['computed_power'] = _raw_card_power(card) + _location_power_bonus(location, side, card)
                if card.get('type') == CARD_TYPE_ANOMALY_ITEM and int(card.get('computed_power', 0)) <= 0:
                    _release_material_reservations(snapshot, side, card['instance_id'])
                    _remove_board_card(snapshot, side, location, card)
                    _add_log(snapshot, f"{card['name']} 战力归零，破碎进入墓地。")
                elif card.get('type') == CARD_TYPE_ESPER and int(card.get('computed_power', 0)) <= 0:
                    if card.pop('survive_non_positive_once', None):
                        _boost_card(card, 1 - int(card.get('computed_power', 0)), card['name'])
                        card['computed_power'] = 1
                        _add_log(snapshot, f"{card['name']} 抵住致命压制，保留 1 战力。")
                        continue
                    location['cards'][side].remove(card)
                    _release_material_reservations(snapshot, side, card['instance_id'])
                    _reset_esper_to_standby(snapshot, side, card)
                    _add_log(snapshot, f"{card['name']} 战力归零，返回异能者编队。")


def _vanish_revealed_card_if_needed(snapshot: JsonDict, side: str, location: JsonDict, card: JsonDict) -> None:
    if not card.get('vanish_after_reveal') and 'vanish_on_reveal' not in card.get('tags', []):
        return
    if card not in location['cards'][side]:
        return
    snapshot.setdefault('action_queue', []).append({
        'kind': 'discard_card',
        'source_instance_id': card['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': f"{card['name']} 进入墓地",
        'subtitle': '揭示后离开战场。',
        'card': _public_card(card, own=True),
    })
    _remove_board_card(snapshot, side, location, card)
    _add_log(snapshot, f"{card['name']} 离开战场。")


def _add_generated_card_to_hand(snapshot: JsonDict, side: str, card_id: str) -> JsonDict | None:
    side_state = snapshot['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    definition = get_duel_card(card_id)
    if definition is None:
        return None
    token_index = int(snapshot.setdefault('token_counter', 0)) + 1
    snapshot['token_counter'] = token_index
    card = _card_instance(definition, side, f'generated-{side}-{snapshot.get("turn", 0)}-{token_index}')
    side_state['hand'].append(card)
    return card


def _clear_pending_target_for_source(snapshot: JsonDict, side: str, source_instance_id: str) -> None:
    pending = snapshot['sides'][side].get('pending_target')
    if pending and pending.get('source_instance_id') == source_instance_id:
        snapshot['sides'][side]['pending_target'] = None


def _find_card_on_board(snapshot: JsonDict, instance_id: str) -> JsonDict | None:
    for location in snapshot['locations']:
        for side in SIDE_KEYS:
            for card in location['cards'][side]:
                if card['instance_id'] == instance_id:
                    return card
    return None


def _find_card_in_zone(zone: list[JsonDict], instance_id: str, error_message: str) -> JsonDict:
    card = _find_card_in_zone_or_none(zone, instance_id)
    if card is None:
        raise RuleValidationError(error_message)
    return card


def _find_card_in_zone_or_none(zone: list[JsonDict], instance_id: str) -> JsonDict | None:
    for card in zone:
        if card['instance_id'] == instance_id:
            return card
    return None


def _find_revealed_esper_on_board(snapshot: JsonDict, side: str, instance_id: str) -> tuple[JsonDict, JsonDict]:
    for location in snapshot['locations']:
        for card in location['cards'][side]:
            if card['instance_id'] == instance_id and card.get('type') == CARD_TYPE_ESPER and card.get('revealed'):
                return card, location
    raise RuleValidationError('异能者编队或战场上没有这名可共鸣的异能者。')


def _turn_energy(snapshot: JsonDict) -> int:
    return min(MAX_ENERGY, int(snapshot.get('turn', 1)))


def _energy_remaining(snapshot: JsonDict, side: str) -> int:
    return max(0, _turn_energy(snapshot) - int(snapshot['sides'][side].get('energy_used', 0)))


def _effective_cost(card: JsonDict) -> int:
    return int(card.get('cost', 0)) + int(card.get('cost_modifier', 0))


def _raw_card_power(card: JsonDict) -> int:
    return int(card.get('base_power', 0)) + int(card.get('bonus_power', 0))


def _reset_card_stats_from_definition(card: JsonDict) -> None:
    definition = get_duel_card(str(card.get('definition_id', ''))) or {}
    card['base_power'] = int(definition.get('power', card.get('base_power', 0)) or 0)
    card['bonus_power'] = 0
    card['computed_power'] = int(card['base_power'])
    card['buff_sources'] = []


def _boost_card(card: JsonDict, amount: int, source_name: str = '效果') -> None:
    card['bonus_power'] = int(card.get('bonus_power', 0)) + int(amount)
    card['computed_power'] = _raw_card_power(card)
    _add_buff_source(card, source_name, int(amount))


def _add_buff_source(card: JsonDict, source_name: str, amount: int, *, replace_key: str = '') -> None:
    if amount == 0:
        return
    sources = card.setdefault('buff_sources', [])
    normalized = {
        'name': str(source_name or '效果'),
        'amount': int(amount),
        'key': str(replace_key or ''),
    }
    if replace_key:
        for index, source in enumerate(sources):
            if source.get('key') == replace_key:
                sources[index] = normalized
                return
    sources.append(normalized)
    del sources[8:]


def _location_index(snapshot: JsonDict, location_id: str) -> int:
    for index, location in enumerate(snapshot['locations']):
        if location['id'] == location_id:
            return index
    return -1


def _side_name(snapshot: JsonDict, side: str) -> str:
    return str(snapshot['sides'][side].get('nickname') or side)


def _add_log(snapshot: JsonDict, message: str) -> None:
    snapshot.setdefault('log', [])
    snapshot['log'].insert(0, message)
    del snapshot['log'][LOG_LIMIT:]


def _new_log_entries(snapshot: JsonDict, previous_logs: list[str]) -> list[str]:
    current_logs = list(snapshot.get('log', []))
    if not previous_logs:
        return current_logs
    for index in range(len(current_logs)):
        comparable = min(len(current_logs) - index, len(previous_logs))
        if comparable > 0 and current_logs[index:index + comparable] == previous_logs[:comparable]:
            return current_logs[:index]
    return current_logs[:max(0, len(current_logs) - len(previous_logs))]


def _reveal_effect_summary(card_name: str, log_entries: list[str]) -> str:
    fragments: list[str] = []
    for entry in reversed(log_entries):
        text = str(entry or '').strip()
        if not text:
            continue
        for prefix in (f'{card_name} ', card_name):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                break
        text = text.rstrip('。')
        if text:
            fragments.append(text)
    return '；'.join(fragments)[:96]
