from __future__ import annotations

import random

from app.engine.rules.board_state import (
    CARD_TYPE_ESPER,
    CARD_TYPE_TOKEN,
    SIDE_KEYS,
    action_card,
    add_generated_card_to_hand,
    add_log,
    boost_card,
    has_revealed_tag,
    opponent_side,
    raw_card_power,
    remove_board_card,
    reset_esper_to_standby,
    side_name,
)
from app.engine.rules.materials import release_material_reservations
from app.engine.event_bus import dispatch_event
from app.engine.events import GameEvent
from app.engine.state.types import JsonDict

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
TAG_HARMONY = 'harmony'

HARMONY_TAGS = frozenset({TAG_GENESIS, TAG_MURK, TAG_DELAY, TAG_DARKSTAR, TAG_SURPLUS, TAG_DISCORD, TAG_COLLAPSING})
DAMAGE_MARK_TAGS = (TAG_ZHUE_HUCHI, TAG_NIGHTMARE, TAG_PANYU_QIU)
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


def location_mark_count(location: JsonDict, side: str, tag: str) -> int:
    return int(location.get('marks', {}).get(side, {}).get(tag, 0) or 0)


def consume_location_mark(location: JsonDict, side: str, tag: str, amount: int = 1) -> int:
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
    clamp_fusion_marks_after_harmony_change(location, side, tag)
    return consumed


def clamp_fusion_marks_after_harmony_change(location: JsonDict, side: str, tag: str) -> None:
    if tag in {TAG_GENESIS, TAG_DELAY}:
        clamp_location_mark(
            location,
            side,
            TAG_SURPLUS,
            min(location_mark_count(location, side, TAG_GENESIS), location_mark_count(location, side, TAG_DELAY)),
        )
    if tag in {TAG_MURK, TAG_DARKSTAR}:
        clamp_location_mark(
            location,
            side,
            TAG_DISCORD,
            min(location_mark_count(location, side, TAG_MURK), location_mark_count(location, side, TAG_DARKSTAR)),
        )


def clamp_location_mark(location: JsonDict, side: str, tag: str, cap: int) -> None:
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    current = int(mark_bucket.get(tag, 0) or 0)
    if current <= max(0, cap):
        return
    if cap <= 0:
        mark_bucket.pop(tag, None)
    else:
        mark_bucket[tag] = int(cap)


def legacy_harmony_cards(location: JsonDict, side: str, tag: str) -> list[JsonDict]:
    return [
        card
        for card in list(location.get('cards', {}).get(side, []))
        if card.get('revealed') and tag in card.get('tags', []) and TAG_HARMONY in card.get('tags', [])
    ]


def decay_harmony_layers_at_turn_start(snapshot: JsonDict) -> None:
    for location in snapshot.get('locations', []):
        marks = location.setdefault('marks', {})
        for side in SIDE_KEYS:
            mark_bucket = marks.setdefault(side, {})
            for tag in DAMAGE_MARK_TAGS:
                current = int(mark_bucket.get(tag, 0) or 0)
                if current <= 0:
                    continue
                if current <= 1:
                    mark_bucket.pop(tag, None)
                else:
                    mark_bucket[tag] = current - 1


def resolve_harmony_end_of_turn(snapshot: JsonDict, *, final_turn: bool = False) -> None:
    for location in snapshot.get('locations', []):
        for side in SIDE_KEYS:
            resolve_nightmare_end_of_turn(snapshot, location, side)
            resolve_panyu_qiu_end_of_turn(snapshot, location, side)


def resolve_genesis_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    if location_mark_count(location, side, TAG_GENESIS) <= 0:
        return
    candidates = [
        card
        for card in location['cards'][side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    if not candidates:
        return
    target = random.choice(candidates)
    power_before = int(target.get('computed_power', raw_card_power(target)) or 0)
    boost_card(target, 1, '创生')
    power_after = int(target.get('computed_power', raw_card_power(target)) or 0)
    snapshot.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_location_id': location['id'],
        'target_instance_id': target['instance_id'],
        'title': '创生',
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} + 1 = {power_after}',
    })
    add_log(snapshot, f"{location['name']} 的创生标记使 {target['name']} +1 战力。")


def resolve_damage_packet_amount(
    snapshot: JsonDict,
    *,
    side: str,
    location: JsonDict,
    target: JsonDict,
    amount: int,
    source_name: str,
    timing: str,
) -> int:
    amount = max(0, int(amount))
    payload = dispatch_event(snapshot, GameEvent.DAMAGE_PACKET, {
        'side': side,
        'opponent_side': opponent_side(side),
        'location': location,
        'location_id': location['id'],
        'source_card': None,
        'source_instance_id': '',
        'damage_target_card': target,
        'damage_target_instance_id': str(target.get('instance_id') or ''),
        'source_name': source_name,
        'base_amount': amount,
        'amount': amount,
        'timing': timing,
    })
    return max(0, int(payload.get('amount') or 0))


def resolve_murk_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    murk_count = location_mark_count(location, side, TAG_MURK) + len(legacy_harmony_cards(location, side, TAG_MURK))
    if murk_count <= 0:
        return
    target_side = opponent_side(side)
    candidates = [
        card
        for card in location['cards'][target_side]
        if card.get('revealed')
        and TAG_COLLAPSING not in card.get('tags', [])
        and card.get('type') != 'token'
    ]
    if not candidates:
        return
    non_negative = [
        card
        for card in candidates
        if int(card.get('computed_power', raw_card_power(card))) >= 0
    ]
    target = max(non_negative or candidates, key=lambda item: int(item.get('computed_power', raw_card_power(item))))
    damage = resolve_damage_packet_amount(
        snapshot,
        side=side,
        location=location,
        target=target,
        amount=1,
        source_name='浊燃',
        timing='end_phase',
    )
    if damage <= 0:
        return
    power_before = int(target.get('computed_power', raw_card_power(target)) or 0)
    boost_card(target, -damage, '浊燃')
    power_after = int(target.get('computed_power', raw_card_power(target)) or 0)
    snapshot.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_location_id': location['id'],
        'side': side,
        'target_instance_id': target['instance_id'],
        'title': '浊燃',
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} - {damage} = {power_after}',
    })
    add_log(snapshot, f"{location['name']} 的浊燃使 {target['name']} -{damage} 战力。")


def resolve_nightmare_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    if location_mark_count(location, side, TAG_NIGHTMARE) <= 0:
        return
    target_side = opponent_side(side)
    targets = [
        card
        for card in location['cards'][target_side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    for target in targets:
        damage = resolve_damage_packet_amount(
            snapshot,
            side=side,
            location=location,
            target=target,
            amount=1,
            source_name='噩梦',
            timing='end_phase',
        )
        if damage <= 0:
            continue
        power_before = int(target.get('computed_power', raw_card_power(target)) or 0)
        boost_card(target, -damage, '噩梦')
        power_after = int(target.get('computed_power', raw_card_power(target)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'side': side,
            'target_instance_id': target['instance_id'],
            'title': '噩梦',
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} - {damage} = {power_after}',
        })
    if targets:
        add_log(snapshot, f"{location['name']} 的噩梦使 {len(targets)} 张敌方牌受到结束阶段伤害。")


def resolve_panyu_qiu_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    if location_mark_count(location, side, TAG_PANYU_QIU) <= 0:
        return
    target_side = opponent_side(side)
    targets = [
        card
        for card in list(location['cards'][target_side])
        if card.get('revealed')
        and card.get('type') != CARD_TYPE_TOKEN
        and int(card.get('computed_power', raw_card_power(card)) or 0) <= 2
    ]
    for target in targets:
        snapshot.setdefault('action_queue', []).append({
            'kind': 'discard_card',
            'source_location_id': location['id'],
            'location_id': location['id'],
            'side': target_side,
            'title': '判予秋',
            'subtitle': f'{target["name"]} 被斩杀。',
            'card': action_card(target, own=True),
        })
        if target.get('type') == CARD_TYPE_ESPER:
            location['cards'][target_side].remove(target)
            release_material_reservations(snapshot, target_side, target['instance_id'])
            reset_esper_to_standby(snapshot, target_side, target)
        else:
            release_material_reservations(snapshot, target_side, target['instance_id'])
            remove_board_card(snapshot, target_side, location, target)
    if targets:
        add_log(snapshot, f"{location['name']} 的判予秋斩杀 {len(targets)} 张战力不高于 2 的敌方牌。")


def resolve_darkstar_end_of_turn(snapshot: JsonDict, location: JsonDict, side: str) -> None:
    darkstar_count = location_mark_count(location, side, TAG_DARKSTAR)
    legacy_darkstars = legacy_harmony_cards(location, side, TAG_DARKSTAR)
    if darkstar_count <= 0 and not legacy_darkstars:
        return
    consume_location_mark(location, side, TAG_DARKSTAR, darkstar_count)
    for darkstar in legacy_darkstars:
        remove_board_card(snapshot, side, location, darkstar)
    amount = max(1, darkstar_count + len(legacy_darkstars))
    damage = min(6, 2 * amount)
    target_side = opponent_side(side)
    targets = [
        card
        for card in location['cards'][target_side]
        if card.get('revealed') and card.get('type') != CARD_TYPE_TOKEN
    ]
    for target in targets:
        actual_damage = resolve_damage_packet_amount(
            snapshot,
            side=side,
            location=location,
            target=target,
            amount=damage,
            source_name='黯星',
            timing='end_phase',
        )
        if actual_damage <= 0:
            continue
        power_before = int(target.get('computed_power', raw_card_power(target)) or 0)
        boost_card(target, -actual_damage, '黯星')
        power_after = int(target.get('computed_power', raw_card_power(target)) or 0)
        snapshot.setdefault('action_queue', []).append({
            'kind': 'impact_arrow',
            'source_location_id': location['id'],
            'side': side,
            'target_instance_id': target['instance_id'],
            'title': '黯星',
            'power_before': power_before,
            'power_after': power_after,
            'power_delta': power_after - power_before,
            'subtitle': f'{power_before} - {actual_damage} = {power_after}',
        })
    removed_murk = consume_location_mark(location, side, TAG_MURK, location_mark_count(location, side, TAG_MURK))
    replaced = _collapse_remaining_murks(location, side)
    add_log(snapshot, f"{location['name']} 的黯星标记爆发，使 {len(targets)} 张牌 -{damage} 战力，并清理 {removed_murk + replaced} 个浊燃。")


def _collapse_remaining_murks(location: JsonDict, side: str) -> int:
    replaced = 0
    for card in location['cards'][side]:
        if not card.get('revealed') or TAG_MURK not in card.get('tags', []) or TAG_HARMONY not in card.get('tags', []):
            continue
        current_power = int(card.get('computed_power', raw_card_power(card)))
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


def first_delay_in_location(location: JsonDict, side: str) -> JsonDict | None:
    for card in location['cards'][side]:
        if card.get('revealed') and TAG_DELAY in card.get('tags', []) and TAG_HARMONY in card.get('tags', []):
            return card
    return None


def delay_tax(snapshot: JsonDict, side: str, location: JsonDict) -> int:
    return 0


def consume_delay_tax(snapshot: JsonDict, side: str, location: JsonDict) -> None:
    return None


__all__ = [name for name in globals() if not name.startswith('__')]
