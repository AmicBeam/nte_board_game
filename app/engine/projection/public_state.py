from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from app.content.common.constants import LOCATION_CARD_LIMIT
from app.engine.rules.declarations import target_candidates, target_rule, target_rule_internal
from app.engine.state.types import JsonDict
from app.models import Player, Room

SIDE_A = 'a'
SIDE_B = 'b'
SIDE_KEYS = (SIDE_A, SIDE_B)
CARD_BACK_IMAGE = '/static/images/cards/card-back.svg'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'


@dataclass(frozen=True)
class SidePerspective:
    own: str
    opponent: str


@dataclass(frozen=True)
class ProjectionRules:
    clear_legacy_draw_selections: Callable[..., bool]
    sync_planning_phase: Callable[[JsonDict], None]
    side_for_player: Callable[[JsonDict, Player], str | None]
    opponent_side: Callable[[str], str]
    scenario_label: Callable[[object], str]
    turn_energy: Callable[[JsonDict], int]
    energy_remaining: Callable[[JsonDict, str], int]
    can_undo_turn: Callable[[JsonDict, str], bool]
    room_payload: Callable[[Room], JsonDict]
    find_card_on_board: Callable[[JsonDict, str], JsonDict | None]
    find_location: Callable[[JsonDict, str], JsonDict]
    location_occupied_card_count: Callable[[JsonDict, str], int]
    effective_cost: Callable[[JsonDict], int]
    raw_card_power: Callable[[JsonDict], int]
    side_name: Callable[[JsonDict, str], str]


def public_state(
    snapshot: JsonDict,
    room: Room,
    viewer: Player,
    rules: ProjectionRules,
    *,
    include_queues: bool = True,
) -> JsonDict:
    rules.clear_legacy_draw_selections(snapshot, auto_draw=True)
    rules.sync_planning_phase(snapshot)
    perspective = _perspective_for_player(snapshot, viewer, rules)
    own = snapshot['sides'][perspective.own]
    opponent = snapshot['sides'][perspective.opponent]
    public_status = _public_status(snapshot, perspective.own)
    room_payload = rules.room_payload(room)
    room_payload['status'] = public_status if public_status in {'victory', 'defeat', 'draw'} else room.status
    return {
        'schema_version': snapshot['schema_version'],
        'game_id': snapshot['game_id'],
        'mode': snapshot['mode'],
        'scenario': snapshot.get('scenario', 'standard'),
        'scenario_label': snapshot.get('scenario_label', rules.scenario_label(snapshot.get('scenario'))),
        'status': public_status,
        'phase': _public_phase(snapshot, perspective.own),
        'turn': snapshot['turn'],
        'max_turns': snapshot['max_turns'],
        'turn_energy': rules.turn_energy(snapshot),
        'energy_remaining': rules.energy_remaining(snapshot, perspective.own),
        'can_undo_turn': rules.can_undo_turn(snapshot, perspective.own),
        'room': room_payload,
        'player_seat': perspective.own,
        'opponent_seat': perspective.opponent,
        'current_actor_uid': own['uid'] if not own.get('ended_turn') else opponent['uid'],
        'player': _public_side(own, reveal_hand=True, rules=rules),
        'opponent': _public_side(opponent, reveal_hand=False, rules=rules),
        'selection': _public_selection(own, rules),
        'pending_target': _public_pending_target(own, rules, snapshot),
        'players_overview': [_side_overview(snapshot['sides'][side]) for side in SIDE_KEYS],
        'locations': [_public_location(location, perspective, rules) for location in snapshot['locations']],
        'score': _public_score(snapshot, perspective),
        'initiative': _public_initiative(snapshot, perspective),
        'winner': _public_winner(snapshot, perspective),
        'route_hint': _route_hint(snapshot, perspective.own, rules),
        'log': _public_log(snapshot, perspective, rules),
        'action_queue': list(snapshot.get('action_queue', [])) if include_queues else [],
        'banner_queue': list(snapshot.get('banner_queue', [])) if include_queues else [],
    }


def public_card(card: JsonDict, *, own: bool, rules: ProjectionRules) -> JsonDict:
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
    card_target_rule = target_rule(card)
    return {
        'instance_id': card['instance_id'],
        'definition_id': card['definition_id'],
        'hidden': False,
        'revealed': card.get('revealed', False),
        'staged': bool(card.get('staged')),
        'name': card['name'],
        'cost': rules.effective_cost(card),
        'base_cost': card['cost'],
        'original_cost': card['cost'],
        'power': int(card.get('computed_power', rules.raw_card_power(card))),
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
        'target_rule': card_target_rule or None,
        'selected_target_instance_id': card.get('selected_target_instance_id'),
        'selected_target_name': card.get('selected_target_name', ''),
        'declared_card_names': list(card.get('declared_card_names', [])),
        'declared_card_instance_ids': list(card.get('declared_card_instance_ids', [])),
        'pending_material_ids': list(card.get('pending_material_ids', [])),
        'reserved_as_material_for': card.get('reserved_as_material_for'),
    }


def public_pending_target(side: JsonDict, rules: ProjectionRules, snapshot: JsonDict | None = None) -> JsonDict | None:
    return _public_pending_target(side, rules, snapshot)


def public_location(location: JsonDict, perspective: SidePerspective, rules: ProjectionRules) -> JsonDict:
    return _public_location(location, perspective, rules)


def _perspective_for_player(snapshot: JsonDict, player: Player, rules: ProjectionRules) -> SidePerspective:
    side = rules.side_for_player(snapshot, player) or SIDE_A
    return SidePerspective(own=side, opponent=rules.opponent_side(side))


def _public_side(side: JsonDict, *, reveal_hand: bool, rules: ProjectionRules) -> JsonDict:
    return {
        'uid': side['uid'],
        'nickname': side['nickname'],
        'is_ai': side['is_ai'],
        'deck_id': side.get('deck_id', ''),
        'deck_name': side.get('deck_name', ''),
        'deck_description': side.get('deck_description', ''),
        'energy_used': side['energy_used'],
        'ended_turn': side['ended_turn'],
        'deck_count': len(side['deck']),
        'hand_count': len(side['hand']),
        'discard_count': len(side.get('discard', [])),
        'esper_standby_count': len(side.get('esper_standby', [])),
        'combo': deepcopy(side.get('combo', {})),
        'pending_target': _public_pending_target(side, rules),
        'hand': [public_card(card, own=True, rules=rules) for card in side['hand']] if reveal_hand else [_public_hidden_hand_card(card) for card in side['hand']],
        'esper_standby': [public_card(card, own=True, rules=rules) for card in side.get('esper_standby', [])] if reveal_hand else [],
        'discard': [public_card(card, own=True, rules=rules) for card in side.get('discard', [])],
    }


def _public_hidden_hand_card(card: JsonDict) -> JsonDict:
    return {
        'instance_id': card['instance_id'],
        'hidden': True,
        'revealed': False,
        'staged': False,
        'name': '对手手牌',
        'cost': None,
        'base_cost': None,
        'original_cost': None,
        'power': None,
        'base_power': None,
        'original_power': None,
        'art': CARD_BACK_IMAGE,
        'description': '对手手牌，内容不可见。',
        'type': card.get('type', CARD_TYPE_ANOMALY_ITEM),
        'archetype': '',
        'category': '',
        'attribute': '',
        'attribute_icon': '',
        'material_cost': 0,
        'required_material_attribute': '',
        'material_tags': [],
        'buff_sources': [],
    }


def _public_log(snapshot: JsonDict, perspective: SidePerspective, rules: ProjectionRules) -> list[str]:
    own_name = rules.side_name(snapshot, perspective.own)
    opponent_name = rules.side_name(snapshot, perspective.opponent)
    lines: list[str] = []
    for line in snapshot.get('log', []):
        public_line = str(line)
        if own_name:
            public_line = public_line.replace(own_name, '我')
        if opponent_name:
            public_line = public_line.replace(opponent_name, '对手')
        lines.append(public_line)
    return lines


def _public_selection(side: JsonDict, rules: ProjectionRules) -> JsonDict | None:
    selection = side.get('selection')
    if not selection:
        return None
    if selection.get('kind') == 'draw':
        return None
    cards = []
    for card in selection.get('cards', []):
        selection_card = public_card(card, own=True, rules=rules)
        source_zone, source_label = _selection_card_source(side, card)
        if source_label:
            selection_card['selection_source_zone'] = source_zone
            selection_card['selection_source_label'] = source_label
        cards.append(selection_card)
    return {
        'kind': selection.get('kind'),
        'title': selection.get('title', '选择卡牌'),
        'description': selection.get('description', ''),
        'pick_count': int(selection.get('pick_count', 1)),
        'min_count': int(selection.get('min_count', selection.get('pick_count', 1))),
        'max_count': int(selection.get('max_count', selection.get('pick_count', 1))),
        'cards': cards,
    }


def _selection_card_source(side: JsonDict, card: JsonDict) -> tuple[str, str]:
    instance_id = str(card.get('instance_id') or '')
    for zone_name, label in (('deck', '牌库'), ('discard', '墓地'), ('hand', '手牌')):
        if any(str(candidate.get('instance_id') or '') == instance_id for candidate in side.get(zone_name, [])):
            return zone_name, label
    return '', ''


def _public_pending_target(side: JsonDict, rules: ProjectionRules, snapshot: JsonDict | None = None) -> JsonDict | None:
    pending = side.get('pending_target')
    if not pending:
        return None
    payload = {
        'source_instance_id': pending.get('source_instance_id'),
        'location_id': pending.get('location_id'),
        'scope': pending.get('scope', ''),
        'prompt': pending.get('prompt', '请选择一个目标。'),
    }
    if snapshot is not None:
        source = rules.find_card_on_board(snapshot, str(pending.get('source_instance_id') or ''))
        source_location = rules.find_location(snapshot, str(pending.get('location_id') or '')) if source else None
        if source is not None and source_location is not None:
            payload['target_instance_ids'] = [
                card['instance_id']
                for card in target_candidates(snapshot, str(side.get('side') or ''), source_location, target_rule_internal(source), source_card=source)
                if card.get('instance_id') != source.get('instance_id')
            ]
    return payload


def _public_location(location: JsonDict, perspective: SidePerspective, rules: ProjectionRules) -> JsonDict:
    own_cards = [
        public_card(card, own=True, rules=rules)
        for card in location['cards'][perspective.own]
        if _is_visible_own_board_card(card)
    ]
    opponent_cards = [public_card(card, own=False, rules=rules) for card in location['cards'][perspective.opponent]]
    winner_side = location.get('winner_side')
    if winner_side == perspective.own:
        winner = 'player'
    elif winner_side == perspective.opponent:
        winner = 'opponent'
    else:
        winner = 'tie'
    return {
        'id': location['id'],
        'name': location['name'] if location['revealed'] else '未显现异象',
        'short_name': location['short_name'] if location['revealed'] else '未知',
        'description': location['description'] if location['revealed'] else '将在后续回合显现规则。',
        'revealed': location['revealed'],
        'reveal_turn': location['reveal_turn'],
        'power': {
            'player': location['power'][perspective.own],
            'opponent': location['power'][perspective.opponent],
        },
        'marks': {
            'player': deepcopy(location.get('marks', {}).get(perspective.own, {})),
            'opponent': deepcopy(location.get('marks', {}).get(perspective.opponent, {})),
        },
        'winner': winner,
        'slots': {
            'player': own_cards,
            'opponent': opponent_cards,
        },
        'occupied': {
            'player': rules.location_occupied_card_count(location, perspective.own),
            'opponent': rules.location_occupied_card_count(location, perspective.opponent),
        },
        'capacity': int(location.get('capacity') or LOCATION_CARD_LIMIT),
    }


def _is_visible_own_board_card(card: JsonDict) -> bool:
    return not card.get('reserved_as_material_for')


def _public_score(snapshot: JsonDict, perspective: SidePerspective) -> JsonDict:
    won = 0
    lost = 0
    tied = 0
    total_player = 0
    total_opponent = 0
    for location in snapshot['locations']:
        total_player += location['power'][perspective.own]
        total_opponent += location['power'][perspective.opponent]
        if location['winner_side'] == perspective.own:
            won += 1
        elif location['winner_side'] == perspective.opponent:
            lost += 1
        else:
            tied += 1
    if total_player > total_opponent:
        leader = 'player'
    elif total_opponent > total_player:
        leader = 'opponent'
    else:
        leader = 'tie'
    return {
        'locations_won': won,
        'locations_lost': lost,
        'locations_tied': tied,
        'total_power_player': total_player,
        'total_power_opponent': total_opponent,
        'leader': leader,
    }


def _public_initiative(snapshot: JsonDict, perspective: SidePerspective) -> JsonDict:
    settlement = snapshot.get('settlement') or {}
    totals = settlement.get('totals') or {}
    first_side = str(settlement.get('first_side') or snapshot.get('settlement_first_side') or '')
    leader_side = settlement.get('leader_side')
    return {
        'turn': int(settlement.get('turn') or snapshot.get('turn') or 1),
        'first': _public_side_key(first_side, perspective),
        'leader_at_turn_start': _public_side_key(str(leader_side), perspective) if leader_side in SIDE_KEYS else 'tie',
        'reason': settlement.get('reason', ''),
        'player_power_at_turn_start': int(totals.get(perspective.own, 0) or 0),
        'opponent_power_at_turn_start': int(totals.get(perspective.opponent, 0) or 0),
    }


def _public_side_key(side: str, perspective: SidePerspective) -> str:
    if side == perspective.own:
        return 'player'
    if side == perspective.opponent:
        return 'opponent'
    return 'tie'


def _public_winner(snapshot: JsonDict, perspective: SidePerspective) -> str | None:
    winner_side = snapshot.get('winner_side')
    if winner_side is None:
        return None
    return 'player' if winner_side == perspective.own else 'opponent'


def _side_overview(side: JsonDict) -> JsonDict:
    return {
        'side': side['side'],
        'uid': side['uid'],
        'nickname': side['nickname'],
        'is_ai': side['is_ai'],
        'deck_id': side.get('deck_id', ''),
        'deck_name': side.get('deck_name', ''),
        'ended_turn': side['ended_turn'],
    }


def _route_hint(snapshot: JsonDict, side: str, rules: ProjectionRules) -> str:
    if snapshot['status'] != 'playing':
        if snapshot.get('winner_side') is None:
            return '主战场战力持平，这局没有输家。'
        return '你赢下了主战场。' if snapshot['winner_side'] == side else '对手赢下了主战场。'
    selection = snapshot['sides'][side].get('selection')
    if selection and selection.get('kind') != 'draw':
        return str(selection.get('description') or '先完成本次卡牌选择。')
    if snapshot.get('phase') == 'selecting':
        return '等待对手完成卡牌选择。'
    if snapshot['sides'][side].get('ended_turn'):
        return '你已结束回合，等待对手完成置入。'
    pending = snapshot['sides'][side].get('pending_target')
    if pending:
        return str(pending.get('prompt') or '请选择一个目标。')
    return f'拖动手牌置入异象道具，或从待命区唤醒/共鸣异能者消耗同区域素材；剩余 {rules.energy_remaining(snapshot, side)} 点能量。'


def _public_status(snapshot: JsonDict, viewer_side: str) -> str:
    status = snapshot['status']
    if status == 'playing' or status == 'draw':
        return status
    if viewer_side == SIDE_A:
        return status
    if status == 'victory':
        return 'defeat'
    if status == 'defeat':
        return 'victory'
    return status


def _public_phase(snapshot: JsonDict, side: str) -> str:
    if snapshot['status'] != 'playing':
        return _public_status(snapshot, side)
    selection = snapshot['sides'][side].get('selection')
    if selection and selection.get('kind') != 'draw':
        return 'selecting'
    if snapshot.get('phase') == 'selecting':
        return 'waiting'
    if snapshot['sides'][side].get('ended_turn'):
        return 'waiting'
    return snapshot.get('phase', 'planning')
