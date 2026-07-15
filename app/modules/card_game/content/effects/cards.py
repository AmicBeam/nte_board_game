from __future__ import annotations

import random
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from app.modules.card_game.content.common.card_factory import *
from app.modules.card_game.content.common.constants import *
from app.modules.card_game.content.common.tokens import *
from app.modules.card_game.content.common.zone_ops import *
from app.modules.card_game.engine.event_bus import dispatch_event
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def _highest_own_harmony(context: 'EventContext') -> tuple[JsonDict, str]:
    side = str(context.payload['side'])
    current_location = context.payload['location']
    priority_tags = (TAG_GENESIS, TAG_DELAY, TAG_MURK, TAG_DARKSTAR)
    best_location = current_location
    best_tag = TAG_GENESIS
    best_count = 0
    best_priority = 0
    for location in context.state.get('locations', []):
        for priority, tag in enumerate(priority_tags):
            count = _location_mark_count(location, side, tag)
            if count > best_count or (count == best_count and count > 0 and priority < best_priority):
                best_location = location
                best_tag = tag
                best_count = count
                best_priority = priority
    return best_location, best_tag


def _trigger_immediate_genesis(context: 'EventContext', location: JsonDict) -> bool:
    side = str(context.payload['side'])
    count = _location_mark_count(location, side, TAG_GENESIS)
    if count <= 0:
        return False
    candidates = [
        card
        for card in _revealed_cards(location, side)
        if card.get('type') != CARD_TYPE_TOKEN
    ]
    if not candidates:
        return False
    target = random.choice(candidates)
    power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
    _boost_card(target, 1, '创生')
    power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
    context.state.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_instance_id': context.payload['card']['instance_id'],
        'source_location_id': location['id'],
        'target_instance_id': target['instance_id'],
        'title': '创生',
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} + 1 = {power_after}',
    })
    _add_log(context.state, f"{location['name']} 的创生标记使 {target['name']} +1 战力。")
    return True


def surplus_vanish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    context.payload['card']['vanish_after_reveal'] = True
    _add_combo_counter(context.state, side, 'surplus_revealed', 1)
    _add_log(context.state, f"{context.payload['card']['name']} 回流能量后消失。")


def _current_turn(context: 'EventContext') -> int:
    return int(context.state.get('turn') or 0)


def _definition_id(card: JsonDict) -> str:
    return str(card.get('definition_id') or '')


def _turn_deployed_cards(context: 'EventContext', side: str) -> list[JsonDict]:
    turn = _current_turn(context)
    return [
        card
        for location in context.state.get('locations', [])
        for card in location.get('cards', {}).get(side, [])
        if int(card.get('played_turn') or 0) == turn
    ]


def _has_turn_deployed(context: 'EventContext', side: str, predicate: Any) -> bool:
    return any(predicate(card) for card in _turn_deployed_cards(context, side))


def _zone_contains_definition(context: 'EventContext', definition_id: str, *zone_names: str) -> bool:
    side_state = context.state['sides'][str(context.payload['side'])]
    for zone_name in zone_names:
        if any(_definition_id(card) == definition_id for card in side_state.get(zone_name, [])):
            return True
    return False


def _board_contains_definition(context: 'EventContext', definition_id: str) -> bool:
    side = str(context.payload['side'])
    return any(
        _definition_id(card) == definition_id
        for location in context.state.get('locations', [])
        for card in location.get('cards', {}).get(side, [])
        if card.get('revealed')
    )


def _reduce_hand_card_cost(context: 'EventContext', attributes: set[str], source_name: str) -> JsonDict | None:
    side_state = context.state['sides'][str(context.payload['side'])]
    for card in side_state.get('hand', []):
        if card.get('type') != CARD_TYPE_ANOMALY_ITEM or str(card.get('attribute') or '') not in attributes:
            continue
        card['cost_modifier'] = max(-1, int(card.get('cost_modifier') or 0) - 1)
        _add_log(context.state, f"{source_name} 使手牌中的 {card['name']} 下次部署费用 -1。")
        return card
    return None


def _recover_discard_item(context: 'EventContext', predicate: Any, source_name: str) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, source_name)
        return None
    for index, card in enumerate(list(side_state.get('discard', []))):
        if card.get('type') != CARD_TYPE_ANOMALY_ITEM or not predicate(card):
            continue
        recovered = side_state['discard'].pop(index)
        recovered = _reset_card_for_zone(recovered, revealed=False)
        recovered['_animation_source_zone'] = 'discard'
        _add_card_to_hand(context, recovered, source_name)
        return recovered
    return None


def _tutor_named_item(context: 'EventContext', names: set[str], source_name: str) -> JsonDict | None:
    card = _declared_deck_item(
        context,
        lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('name') or '') in names,
    )
    if card is None:
        card = _tutor_deck_item(
            context,
            lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('name') or '') in names,
        )
    _add_card_to_hand(context, card, source_name)
    return card


def _pop_deck_item(context: 'EventContext', predicate: Any) -> JsonDict | None:
    side_state = context.state['sides'][str(context.payload['side'])]
    for index, card in enumerate(list(side_state.get('deck', []))):
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and predicate(card):
            return side_state['deck'].pop(index)
    return None


def _move_deck_item_to_discard(context: 'EventContext', predicate: Any, source_name: str) -> JsonDict | None:
    moved = _pop_deck_item(context, predicate)
    if moved is None:
        return None
    return _move_popped_deck_item_to_discard(context, moved, source_name)


def _move_popped_deck_item_to_discard(context: 'EventContext', moved: JsonDict, source_name: str) -> JsonDict:
    moved = _reset_card_for_zone(moved, revealed=True)
    side = str(context.payload['side'])
    context.state['sides'][side].setdefault('discard', []).append(moved)
    _append_effect_discard_action(context, moved, source_name)
    _add_log(context.state, f"{source_name} 将 {moved['name']} 从牌库置入墓地。")
    _add_turn_combo_counter(context.state, side, 'deck_to_discard_this_turn', 1)
    _resolve_deck_to_discard_trigger(context, moved, source_name)
    return moved


def _resolve_deck_to_discard_trigger(context: 'EventContext', moved: JsonDict, source_name: str) -> None:
    definition_id = _definition_id(moved)
    if definition_id == 'murk_lost_whisper':
        target = _lowest_opponent_item(context)
        if target is not None:
            _boost_card(target, -1, source_name)
            _add_log(context.state, f"{moved['name']} 被送入墓地，压低 {target['name']} 1 点战力。")
    elif definition_id == 'murk_faded_shadow':
        target = _highest_opponent_item(context)
        if target is not None:
            _boost_card(target, -1, source_name)
            _add_log(context.state, f"{moved['name']} 被送入墓地，压低 {target['name']} 1 点战力。")
    elif definition_id == 'murk_blur_number':
        side_state = context.state['sides'][str(context.payload['side'])]
        if side_state.get('deck'):
            top_card = side_state['deck'].pop(0)
            _move_popped_deck_item_to_discard(context, top_card, moved['name'])
        else:
            _add_log(context.state, f"{moved['name']} 被送入墓地，但己方牌库没有可置入墓地的牌。")
    elif definition_id == 'murk_fantasy_delusion':
        if _location_occupied_count(context.payload['location'], str(context.payload['side'])) >= _location_capacity(context.payload['location']):
            _add_log(context.state, f"{moved['name']} 被送入墓地，但战场已满，未能表侧置入战场。")
            return
        side = str(context.payload['side'])
        context.state['sides'][side].setdefault('discard', []).remove(moved)
        moved = _reset_card_for_zone(moved, revealed=True)
        moved['played_turn'] = _current_turn(context)
        moved['location_id'] = context.payload['location']['id']
        context.payload['location']['cards'][side].append(moved)
        _append_spawn_action(context.state, context.payload['location'], side, moved)
        _add_log(context.state, f"{moved['name']} 被送入墓地，改为表侧置入战场。")


def _lowest_opponent(context: 'EventContext') -> JsonDict | None:
    opponent = str(context.payload['opponent_side'])
    candidates = _revealed_cards(context.payload['location'], opponent)
    return min(candidates, key=_raw_card_power) if candidates else None


def _lowest_opponent_item(context: 'EventContext') -> JsonDict | None:
    opponent = str(context.payload['opponent_side'])
    candidates = [
        card
        for card in _revealed_cards(context.payload['location'], opponent)
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM
    ]
    return min(candidates, key=_raw_card_power) if candidates else None


def _highest_opponent_item(context: 'EventContext') -> JsonDict | None:
    opponent = str(context.payload['opponent_side'])
    candidates = [
        card
        for card in _revealed_cards(context.payload['location'], opponent)
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM
    ]
    return max(candidates, key=_raw_card_power) if candidates else None


def _highest_ally_item_with_attributes(context: 'EventContext', attributes: set[str]) -> JsonDict | None:
    side = str(context.payload['side'])
    candidates = [
        card
        for card in _revealed_cards(context.payload['location'], side)
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and str(card.get('attribute') or '') in attributes
    ]
    return max(candidates, key=_raw_card_power) if candidates else None


def _highest_ally(context: 'EventContext') -> JsonDict | None:
    side = str(context.payload['side'])
    candidates = _revealed_cards(context.payload['location'], side)
    return max(candidates, key=_raw_card_power) if candidates else None


def _opponent_esper_consumed_material_this_turn(context: 'EventContext') -> bool:
    opponent = str(context.payload['opponent_side'])
    turn = _current_turn(context)
    return any(
        card.get('type') == CARD_TYPE_ESPER
        and card.get('revealed')
        and int(card.get('played_turn') or turn) == turn
        and bool(card.get('consumed_material_names') or card.get('consumed_material_tags'))
        for location in context.state.get('locations', [])
        for card in location.get('cards', {}).get(opponent, [])
    )


def _own_esper_consumed_tag_this_turn(context: 'EventContext', tag: str) -> bool:
    side = str(context.payload['side'])
    turn = _current_turn(context)
    return any(
        card.get('type') == CARD_TYPE_ESPER
        and card.get('revealed')
        and int(card.get('played_turn') or turn) == turn
        and tag in card.get('consumed_material_tags', [])
        for location in context.state.get('locations', [])
        for card in location.get('cards', {}).get(side, [])
    )


def _tutor_deck_item(context: 'EventContext', predicate: Any) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    for index, card in enumerate(list(side_state.get('deck', []))):
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and predicate(card):
            tutored = side_state['deck'].pop(index)
            tutored['_animation_source_zone'] = 'deck'
            return _reset_card_for_zone(tutored, revealed=False)
    return None


def _pop_discard_definition(context: 'EventContext', definition_id: str) -> JsonDict | None:
    side_state = context.state['sides'][str(context.payload['side'])]
    for index, card in enumerate(list(side_state.get('discard', []))):
        if str(card.get('definition_id') or '') == definition_id:
            return side_state['discard'].pop(index)
    return None


def _deploy_discard_definition_to_current_location(context: 'EventContext', definition_id: str, source_name: str) -> JsonDict | None:
    side = str(context.payload['side'])
    if _location_occupied_count(context.payload['location'], side) >= _location_capacity(context.payload['location']):
        _add_log(context.state, f"{source_name} 想部署墓地中的卡牌，但战场已满。")
        return None
    card = _pop_discard_definition(context, definition_id)
    if card is None:
        _add_log(context.state, f"{source_name} 没有找到可部署的本性像素。")
        return None
    _deploy_card_to_current_location(context, card, source_name)
    return card


def _append_effect_discard_action(context: 'EventContext', card: JsonDict, source_name: str) -> None:
    context.state.setdefault('action_queue', []).append({
        'kind': 'discard_card',
        'source_instance_id': card['instance_id'],
        'side': str(context.payload['side']),
        'title': f'{source_name} 置入墓地',
        'subtitle': f'{card["name"]} 从牌库进入墓地。',
        'card': _action_card_payload(card),
    })


def _resolve_nature_pixel_sent_from_deck(context: 'EventContext', source_name: str) -> None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    deck = side_state.setdefault('deck', [])
    if not deck:
        _add_log(context.state, f"{source_name} 没有可查看的牌库顶牌。")
        return
    inspected: list[JsonDict] = []
    selected: JsonDict | None = None
    for _ in range(min(3, len(deck))):
        top_card = deck.pop(0)
        if top_card.get('type') == CARD_TYPE_ANOMALY_ITEM and str(top_card.get('attribute') or '') in {'暗', '魂'}:
            selected = top_card
            break
        inspected.append(top_card)
    if selected is not None and len(side_state.get('hand', [])) < MAX_HAND_SIZE:
        selected['_animation_source_zone'] = 'deck'
        _add_card_to_hand(context, selected, source_name)
    elif selected is not None:
        inspected.append(selected)
        _add_log(context.state, f"{source_name} 翻到暗或魂属性道具，但手牌已满。")
    else:
        _add_log(context.state, f"{source_name} 翻看牌库顶至多 3 张，没有可加入手牌的暗或魂属性道具。")
    side_state.setdefault('deck', []).extend(_reset_card_for_zone(card, revealed=False) for card in inspected)


def _add_card_to_hand(context: 'EventContext', card: JsonDict | None, source_name: str) -> None:
    if card is None:
        return
    side = str(context.payload['side'])
    if len(context.state['sides'][side].get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, source_name)
        return
    source_zone = str(card.pop('_animation_source_zone', '') or '')
    card['played_turn'] = None
    card['location_id'] = None
    card['revealed'] = False
    card.pop('staged', None)
    card.pop('paid_cost', None)
    card.pop('reserved_as_material_for', None)
    card.pop('reserved_material_power', None)
    card.pop('pending_material_ids', None)
    card.pop('declared_card_instance_ids', None)
    context.state['sides'][side].setdefault('hand', []).append(card)
    if source_zone == 'deck':
        _append_draw_action(context.state, side, card, source_name)
    _add_log(context.state, f"{source_name} 将 {card['name']} 加入手牌。")


def _deploy_card_to_current_location(context: 'EventContext', card: JsonDict | None, source_name: str) -> bool:
    if card is None:
        return False
    side = str(context.payload['side'])
    location = context.payload['location']
    if _location_occupied_count(location, side) >= _location_capacity(location):
        _add_log(context.state, f"{source_name} 想部署 {card['name']}，但战场已满。")
        return False
    card = _reset_card_for_zone(card, revealed=False)
    card['played_turn'] = _current_turn(context)
    card['location_id'] = location['id']
    card['staged'] = True
    card['paid_cost'] = 0
    card['play_sequence'] = _next_effect_play_sequence(context.state)
    location['cards'][side].append(card)
    _append_spawn_action(context.state, location, side, card)
    _add_log(context.state, f"{source_name} 将 {card['name']} 部署到战场。")
    return True


def _deploy_generated_card_face_up(context: 'EventContext', definition_id: str, source_name: str, *, side: str | None = None) -> JsonDict | None:
    target_side = side or str(context.payload['side'])
    location = context.payload['location']
    if _location_occupied_count(location, target_side) >= _location_capacity(location):
        _add_log(context.state, f"{source_name} 想生成卡牌，但战场已满。")
        return None
    generated = _build_generated_definition_instance(context.state, target_side, definition_id)
    if generated is None:
        return None
    generated = _reset_card_for_zone(generated, revealed=True)
    generated['played_turn'] = _current_turn(context)
    generated['location_id'] = location['id']
    location['cards'][target_side].append(generated)
    _append_spawn_action(context.state, location, target_side, generated)
    _add_log(context.state, f"{source_name} 将 {generated['name']} 表侧置入战场。")
    return generated


def _restore_consumed_material_face_up(context: 'EventContext', predicate: Any, source_name: str) -> JsonDict | None:
    side = str(context.payload['side'])
    location = context.payload['location']
    if _location_occupied_count(location, side) >= _location_capacity(location):
        _add_log(context.state, f"{source_name} 想将素材置回战场，但战场已满。")
        return None
    consumed_ids = {str(item_id) for item_id in context.payload['card'].get('consumed_material_instance_ids', []) if str(item_id)}
    if not consumed_ids:
        return None
    discard = context.state['sides'][side].setdefault('discard', [])
    for index, card in enumerate(list(discard)):
        if str(card.get('instance_id') or '') not in consumed_ids or not predicate(card):
            continue
        restored = discard.pop(index)
        restored = _reset_card_for_zone(restored, revealed=True)
        restored['played_turn'] = _current_turn(context)
        restored['location_id'] = location['id']
        location['cards'][side].append(restored)
        _append_spawn_action(context.state, location, side, restored)
        _add_log(context.state, f"{source_name} 将消耗过的 {restored['name']} 表侧置回战场。")
        return restored
    return None


def _next_effect_play_sequence(state: JsonDict) -> int:
    counter = int(state.get('play_sequence_counter', 0)) + 1
    state['play_sequence_counter'] = counter
    return counter


def _location_capacity(location: JsonDict) -> int:
    return int(location.get('capacity') or LOCATION_CARD_LIMIT)


def _location_occupied_count(location: JsonDict, side: str) -> int:
    return sum(
        1
        for card in location.get('cards', {}).get(side, [])
        if not card.get('reserved_as_material_for')
    )


def _return_target_to_hand(context: 'EventContext', target: JsonDict) -> bool:
    side = str(context.payload['side'])
    if len(context.state['sides'][side].get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, context.payload['card']['name'])
        return False
    for location in context.state.get('locations', []):
        cards = location.get('cards', {}).get(side, [])
        if target not in cards:
            continue
        cards.remove(target)
        target['played_turn'] = None
        target['location_id'] = None
        target['revealed'] = False
        target['cost_modifier'] = max(-1, int(target.get('cost_modifier') or 0) - 1)
        target.pop('staged', None)
        target.pop('paid_cost', None)
        target.pop('play_sequence', None)
        target.pop('reserved_as_material_for', None)
        target.pop('reserved_material_power', None)
        target.pop('pending_material_ids', None)
        target.pop('declared_card_instance_ids', None)
        context.state['sides'][side].setdefault('hand', []).append(target)
        _add_combo_counter(context.state, side, 'returned_items', 1)
        _add_log(context.state, f"{context.payload['card']['name']} 回收 {target['name']}，其下次部署费用 -1。")
        return True
    return False






















































































def _trigger_discord_mark(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    _add_combo_counter(context.state, side, 'discord_triggered', 1)
    _trigger_dafutier_discord_passive(context)
    _add_log(context.state, f"{card['name']} 触发失谐。")










def _load_duel_card_definition(card_id: str) -> JsonDict | None:
    from app.modules.card_game.content.loader import get_duel_card

    return get_duel_card(card_id)


def _definition_by_id(card_id: str) -> JsonDict:
    return _load_duel_card_definition(card_id) or {}


def _build_token_instance(state: JsonDict, side: str, token_id: str, *, revealed: bool) -> JsonDict:
    definition = TOKEN_CARDS[token_id]
    token_index = int(state.setdefault('token_counter', 0)) + 1
    state['token_counter'] = token_index
    return {
        'instance_id': f'{token_id}-{side}-{state.get("turn", 0)}-{token_index}',
        'definition_id': definition['id'],
        'name': definition['name'],
        'type': definition.get('type', CARD_TYPE_TOKEN),
        'cost': int(definition['cost']),
        'cost_modifier': 0,
        'base_power': int(definition['power']),
        'bonus_power': 0,
        'computed_power': int(definition['power']),
        'element': definition.get('element', ''),
        'rarity': definition.get('rarity', 'token'),
        'art': definition.get('art', CARD_BACK_IMAGE),
        'side': side,
        'revealed': revealed,
        'played_turn': state.get('turn') if revealed else None,
        'location_id': None,
        'description': definition.get('description', ''),
        'category': definition.get('category', ''),
        'attribute': definition.get('attribute', ''),
        'attribute_icon': definition.get('attribute_icon', ''),
        'material_attributes': list(definition.get('material_attributes', [])),
        'material_tags': list(definition.get('material_tags', [])),
        'material_cost': int(definition.get('material_cost') or 0),
        'display_tags': list(definition.get('display_tags', [])),
        'deck_buildable': definition.get('deck_buildable') is not False,
        'tags': list(definition.get('tags', [])),
    }


def _create_token_at_location(context: 'EventContext', token_id: str, *, side: str | None = None) -> bool:
    return _create_token_in_location(
        context.state,
        context.payload['location'],
        side or str(context.payload['side']),
        token_id,
        context=context,
    )


def _create_tokens_at_location(context: 'EventContext', token_id: str, *, count: int, side: str | None = None) -> int:
    created = 0
    for _ in range(max(0, count)):
        if not _create_token_at_location(context, token_id, side=side):
            break
        created += 1
    return created


def _create_token_in_location(state: JsonDict, location: JsonDict, side: str, token_id: str, *, context: 'EventContext' | None = None) -> bool:
    mark_tag = LOCATION_MARK_TOKENS.get(token_id)
    if mark_tag:
        _add_location_mark(state, location, side, mark_tag, context=context)
        return True
    if _location_occupied_count(location, side) >= _location_capacity(location):
        return False
    token = _build_token_instance(state, side, token_id, revealed=True)
    token['location_id'] = location['id']
    location['cards'][side].append(token)
    _append_spawn_action(state, location, side, token)
    return True


def _append_spawn_action(state: JsonDict, location: JsonDict, side: str, token: JsonDict) -> None:
    source_instance_id = str(state.get('_active_reveal_source_instance_id') or '')
    if not source_instance_id:
        return
    source_name = str(state.get('_active_reveal_source_name') or '效果')
    state.setdefault('action_queue', []).append({
        'kind': 'spawn_card',
        'source_instance_id': source_instance_id,
        'target_instance_id': token['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': f'{source_name} 生成 {token["name"]}',
        'subtitle': f'{token["name"]} 进入 {location["name"]}',
    })


def _add_location_mark(state: JsonDict, location: JsonDict, side: str, tag: str, amount: int = 1, *, context: 'EventContext' | None = None) -> int:
    if amount <= 0:
        return _location_mark_count(location, side, tag)
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    before = int(mark_bucket.get(tag, 0) or 0)
    mark_bucket[tag] = max(0, before + amount)
    gained = max(0, int(mark_bucket[tag]) - before)
    if tag == TAG_DELAY:
        _add_combo_counter(state, side, 'delay_set_total', amount)
    _append_mark_action(state, location, side, tag, amount)
    _sync_fusion_mark_after_harmony_gain(state, location, side, tag, gained, context=context)
    if gained > 0 and context is not None and tag in {TAG_GENESIS, TAG_MURK, TAG_DELAY, TAG_DARKSTAR}:
        dispatch_event(state, GameEvent.HARMONY_MARK_ADDED, {
            'source_instance_id': context.payload.get('card_instance_id') or context.payload.get('source_instance_id') or '',
            'source_card': context.payload.get('card'),
            'source_name': str((context.payload.get('card') or {}).get('name') or context.payload.get('source_name') or '效果'),
            'side': side,
            'opponent_side': context.payload.get('opponent_side'),
            'location': location,
            'location_id': location.get('id'),
            'tag': tag,
            'amount': gained,
            'mark_count': int(mark_bucket.get(tag, 0) or 0),
        })
    return int(mark_bucket[tag])


def _reset_location_mark(context: 'EventContext', location: JsonDict, side: str, tag: str, amount: int) -> int:
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    before = int(mark_bucket.get(tag, 0) or 0)
    if amount <= 0:
        mark_bucket.pop(tag, None)
        _clamp_fusion_marks_after_harmony_change(location, side, tag)
        return 0
    mark_bucket[tag] = int(amount)
    _append_mark_action(context.state, location, side, tag, int(amount))
    _sync_fusion_mark_after_harmony_gain(context.state, location, side, tag, max(0, int(amount) - before), context=context)
    _clamp_fusion_marks_after_harmony_change(location, side, tag)
    return int(amount)


def _sync_fusion_mark_after_harmony_gain(
    state: JsonDict,
    location: JsonDict,
    side: str,
    gained_tag: str,
    gained_amount: int,
    *,
    context: 'EventContext' | None = None,
) -> None:
    if gained_amount <= 0:
        return
    if gained_tag == TAG_GENESIS:
        _add_capped_fusion_mark(
            state,
            location,
            side,
            fusion_tag=TAG_SURPLUS,
            cap=min(_location_mark_count(location, side, TAG_GENESIS), _location_mark_count(location, side, TAG_DELAY)),
            gained_amount=gained_amount,
            context=context,
        )
    elif gained_tag in {TAG_MURK, TAG_DARKSTAR}:
        _add_capped_fusion_mark(
            state,
            location,
            side,
            fusion_tag=TAG_DISCORD,
            cap=min(_location_mark_count(location, side, TAG_MURK), _location_mark_count(location, side, TAG_DARKSTAR)),
            gained_amount=gained_amount,
            context=context,
        )


def _add_capped_fusion_mark(
    state: JsonDict,
    location: JsonDict,
    side: str,
    *,
    fusion_tag: str,
    cap: int,
    gained_amount: int,
    context: 'EventContext' | None = None,
) -> int:
    if cap <= 0:
        return 0
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    current = int(mark_bucket.get(fusion_tag, 0) or 0)
    added = min(max(0, gained_amount), max(0, cap - current))
    if added <= 0:
        return 0
    mark_bucket[fusion_tag] = current + added
    _append_mark_action(state, location, side, fusion_tag, added)
    if fusion_tag == TAG_DISCORD and context is not None:
        _trigger_dafutier_discord_passive(context)
    return added


def _clamp_fusion_marks_after_harmony_change(location: JsonDict, side: str, tag: str) -> None:
    if tag in {TAG_GENESIS, TAG_DELAY}:
        _clamp_location_mark(
            location,
            side,
            TAG_SURPLUS,
            min(_location_mark_count(location, side, TAG_GENESIS), _location_mark_count(location, side, TAG_DELAY)),
        )
    if tag in {TAG_MURK, TAG_DARKSTAR}:
        _clamp_location_mark(
            location,
            side,
            TAG_DISCORD,
            min(_location_mark_count(location, side, TAG_MURK), _location_mark_count(location, side, TAG_DARKSTAR)),
        )


def _clamp_location_mark(location: JsonDict, side: str, tag: str, cap: int) -> None:
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    current = int(mark_bucket.get(tag, 0) or 0)
    if current <= max(0, cap):
        return
    if cap <= 0:
        mark_bucket.pop(tag, None)
    else:
        mark_bucket[tag] = int(cap)


def _consume_location_mark(location: JsonDict, side: str, tag: str, amount: int = 1) -> int:
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    current = int(mark_bucket.get(tag, 0))
    consumed = min(current, max(0, amount))
    if consumed <= 0:
        return 0
    remaining = current - consumed
    if remaining:
        mark_bucket[tag] = remaining
    else:
        mark_bucket.pop(tag, None)
    _clamp_fusion_marks_after_harmony_change(location, side, tag)
    return consumed


def _location_mark_count(location: JsonDict, side: str, tag: str) -> int:
    return int(location.get('marks', {}).get(side, {}).get(tag, 0) or 0)


def _append_mark_action(state: JsonDict, location: JsonDict, side: str, tag: str, amount: int) -> None:
    source_instance_id = str(state.get('_active_reveal_source_instance_id') or '')
    if not source_instance_id:
        return
    source_name = str(state.get('_active_reveal_source_name') or '效果')
    mark_name = LOCATION_MARK_NAMES.get(tag, tag)
    title_action = '设置环合' if tag in {TAG_GENESIS, TAG_MURK, TAG_DELAY, TAG_DARKSTAR} else '生成标记'
    state.setdefault('action_queue', []).append({
        'kind': 'spawn_mark',
        'source_instance_id': source_instance_id,
        'source_location_id': location['id'],
        'location_id': location['id'],
        'side': side,
        'mark': tag,
        'amount': amount,
        'mark_count': _location_mark_count(location, side, tag),
        'title': f'{source_name} {title_action} {mark_name}',
        'subtitle': f'{mark_name} x{_location_mark_count(location, side, tag)}',
    })


def _add_token_to_hand(context: 'EventContext', token_id: str, *, side: str | None = None, count: int = 1) -> int:
    target_side = side or str(context.payload['side'])
    side_state = context.state['sides'][target_side]
    added = 0
    for _ in range(max(0, count)):
        if len(side_state['hand']) >= MAX_HAND_SIZE:
            _add_hand_limit_log(context.state, target_side, context.payload.get('card', {}).get('name') or '效果')
            break
        side_state['hand'].append(_build_token_instance(context.state, target_side, token_id, revealed=False))
        added += 1
    return added


def _build_generated_definition_instance(state: JsonDict, side: str, definition_id: str) -> JsonDict | None:
    definition = _load_duel_card_definition(definition_id)
    if definition is None:
        return None
    token_index = int(state.setdefault('token_counter', 0)) + 1
    state['token_counter'] = token_index
    return {
        'instance_id': f'{definition_id}-generated-{side}-{state.get("turn", 0)}-{token_index}',
        'definition_id': definition['id'],
        'name': definition['name'],
        'type': definition.get('type', CARD_TYPE_ANOMALY_ITEM),
        'cost': int(definition['cost']),
        'cost_modifier': 0,
        'base_power': int(definition['power']),
        'bonus_power': 0,
        'computed_power': int(definition['power']),
        'element': definition.get('element', ''),
        'rarity': definition.get('rarity', 'r'),
        'art': definition.get('art', CARD_BACK_IMAGE),
        'description': definition.get('description', ''),
        'archetype': definition.get('archetype', ''),
        'category': definition.get('category', ''),
        'attribute': definition.get('attribute', ''),
        'attribute_icon': definition.get('attribute_icon', ''),
        'material_attributes': list(definition.get('material_attributes', [])),
        'material_tags': list(definition.get('material_tags', [])),
        'material_cost': int(definition.get('material_cost') or 0),
        'required_material_attribute': definition.get('required_material_attribute', ''),
        'material_requirements': deepcopy(definition.get('material_requirements') or []),
        'material_requirement_text': definition.get('material_requirement_text', ''),
        'ai_material_reserved_for': list(definition.get('ai_material_reserved_for', [])),
        'display_tags': list(definition.get('display_tags', [])),
        'deck_buildable': definition.get('deck_buildable') is not False,
        'side': side,
        'revealed': False,
        'played_turn': None,
        'location_id': None,
        'tags': list(definition.get('tags', [])),
    }


def _add_generated_card_to_hand(context: 'EventContext', definition_id: str, *, count: int = 1, side: str | None = None) -> int:
    target_side = side or str(context.payload['side'])
    side_state = context.state['sides'][target_side]
    added = 0
    for _ in range(max(0, count)):
        if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
            _add_hand_limit_log(context.state, target_side, context.payload.get('card', {}).get('name') or '效果')
            break
        generated = _build_generated_definition_instance(context.state, target_side, definition_id)
        if generated is None:
            break
        side_state.setdefault('hand', []).append(generated)
        added += 1
    return added


def _add_generated_card_to_discard(context: 'EventContext', definition_id: str, *, side: str | None = None) -> JsonDict | None:
    target_side = side or str(context.payload['side'])
    generated = _build_generated_definition_instance(context.state, target_side, definition_id)
    if generated is None:
        return None
    context.state['sides'][target_side].setdefault('discard', []).append(_reset_card_for_zone(generated, revealed=True))
    return generated


def _add_generated_card_to_deck_bottom(context: 'EventContext', definition_id: str, *, side: str | None = None) -> JsonDict | None:
    target_side = side or str(context.payload['side'])
    generated = _build_generated_definition_instance(context.state, target_side, definition_id)
    if generated is None:
        return None
    context.state['sides'][target_side].setdefault('deck', []).append(_reset_card_for_zone(generated, revealed=False))
    return generated


def _random_deck_item(context: 'EventContext', predicate: Any) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, context.payload.get('card', {}).get('name') or '效果')
        return None
    candidates = [
        (index, card)
        for index, card in enumerate(list(side_state.get('deck', [])))
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and predicate(card)
    ]
    if not candidates:
        return None
    index, card = random.choice(candidates)
    side_state['deck'].pop(index)
    card['_animation_source_zone'] = 'deck'
    return _reset_card_for_zone(card, revealed=False)


def _move_declared_or_first_deck_item_to_top(context: 'EventContext', predicate: Any, source_name: str) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    declared_ids = [str(card_id) for card_id in context.payload['card'].get('declared_card_instance_ids', [])]
    for declared_id in declared_ids:
        for index, card in enumerate(list(side_state.get('deck', []))):
            if str(card.get('instance_id') or '') == declared_id and card.get('type') == CARD_TYPE_ANOMALY_ITEM and predicate(card):
                moved = _reset_card_for_zone(side_state['deck'].pop(index), revealed=False)
                side_state.setdefault('deck', []).insert(0, moved)
                _add_log(context.state, f"{source_name} 将 {moved['name']} 置于牌库顶。")
                return moved
    for index, card in enumerate(list(side_state.get('deck', []))):
        if card.get('type') != CARD_TYPE_ANOMALY_ITEM or not predicate(card):
            continue
        moved = _reset_card_for_zone(side_state['deck'].pop(index), revealed=False)
        side_state.setdefault('deck', []).insert(0, moved)
        _add_log(context.state, f"{source_name} 将 {moved['name']} 置于牌库顶。")
        return moved
    return None


def _consume_hand_card_with_tag(context: 'EventContext', side: str, tag: str) -> bool:
    hand = context.state['sides'][side].setdefault('hand', [])
    for index, card in enumerate(list(hand)):
        if tag not in card.get('tags', []):
            continue
        consumed = hand.pop(index)
        _add_log(context.state, f"{context.payload['card']['name']} 消耗手牌中的 {consumed['name']}。")
        return True
    return False


def _revealed_cards(location: JsonDict, side: str) -> list[JsonDict]:
    return [card for card in location['cards'][side] if card.get('revealed')]


def _previous_revealed_item(context: 'EventContext') -> JsonDict | None:
    location = context.payload['location']
    side = str(context.payload['side'])
    source = context.payload['card']
    turn = int(context.state.get('turn') or 0)
    cards = location['cards'][side]
    source_index = next(
        (index for index, card in enumerate(cards) if card.get('instance_id') == source.get('instance_id')),
        len(cards),
    )
    for candidate in reversed(cards[:source_index]):
        if not candidate.get('revealed') or candidate.get('type') != CARD_TYPE_ANOMALY_ITEM:
            continue
        if int(candidate.get('played_turn') or 0) != turn:
            continue
        if _definition_id(candidate) == 'delay_kaleidoscope':
            continue
        return candidate
    return None


def _lowest_ally(context: 'EventContext') -> JsonDict | None:
    allies = [
        card
        for card in _revealed_cards(context.payload['location'], str(context.payload['side']))
        if card['instance_id'] != context.payload['card']['instance_id']
    ]
    return min(allies, key=_raw_card_power) if allies else None


def _selected_or_highest_opponent(context: 'EventContext') -> JsonDict | None:
    opponent = str(context.payload['opponent_side'])
    selected_target = context.payload.get('target_card')
    if isinstance(selected_target, dict) and selected_target.get('side') == opponent:
        return selected_target
    candidates = _revealed_cards(context.payload['location'], opponent)
    return max(candidates, key=_raw_card_power) if candidates else None


def _random_target_for_rule(context: 'EventContext', target_rule: JsonDict) -> JsonDict | None:
    scope = str(target_rule.get('scope') or '')
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    location = context.payload['location']
    if scope == 'opponent_same_location':
        candidates = [card for card in _revealed_cards(location, opponent) if card.get('type') != CARD_TYPE_TOKEN]
    elif scope == 'opponent_power_lte_3_same_location':
        candidates = [
            card for card in _revealed_cards(location, opponent)
            if card.get('type') != CARD_TYPE_TOKEN and _raw_card_power(card) <= 3
        ]
    elif scope == 'opponent_any':
        candidates = [
            card
            for current_location in context.state.get('locations', [])
            for card in _revealed_cards(current_location, opponent)
            if card.get('type') != CARD_TYPE_TOKEN
        ]
    elif scope == 'ally_item_same_location':
        candidates = [
            card
            for card in _revealed_cards(location, side)
            if card.get('type') == CARD_TYPE_ANOMALY_ITEM and card.get('instance_id') != context.payload['card'].get('instance_id')
        ]
    elif scope == 'ally_xiang_item_same_location':
        candidates = [
            card
            for card in _revealed_cards(location, side)
            if (
                card.get('type') == CARD_TYPE_ANOMALY_ITEM
                and card.get('instance_id') != context.payload['card'].get('instance_id')
                and str(card.get('attribute') or '') == '相'
            )
        ]
    elif scope == 'ally_damaged_food_same_location':
        candidates = [
            card
            for card in _revealed_cards(location, side)
            if (
                card.get('type') == CARD_TYPE_ANOMALY_ITEM
                and card.get('instance_id') != context.payload['card'].get('instance_id')
                and str(card.get('category') or '') == '食物'
                and _raw_card_power(card) < int(card.get('base_power') or 0)
            )
        ]
    elif scope == 'ally_same_location':
        candidates = [
            card
            for card in _revealed_cards(location, side)
            if card.get('instance_id') != context.payload['card'].get('instance_id')
        ]
    elif scope == 'ally_any':
        candidates = [
            card
            for current_location in context.state.get('locations', [])
            for card in _revealed_cards(current_location, side)
            if card.get('instance_id') != context.payload['card'].get('instance_id')
        ]
    else:
        candidates = []
    return random.choice(candidates) if candidates else None


def _trigger_reveal_effect_as_copy(
    context: 'EventContext',
    copied_card: JsonDict,
    *,
    source_card: JsonDict,
    source_name: str,
    randomize_target: bool = True,
) -> bool:
    copied_definition = _definition_by_id(str(copied_card.get('definition_id', '')))
    copied_handler = copied_definition.get('event_hooks', {}).get(GameEvent.CARD_REVEALED.value)
    if (
        not callable(copied_handler)
        or str(copied_definition.get('effect_key') or '') == 'delay_kaleidoscope_copy'
        or str(copied_card.get('definition_id') or '') == str(source_card.get('definition_id') or '')
    ):
        return False
    target_rule = copied_definition.get('target_rule') or {}
    copied_target = _random_target_for_rule(context, target_rule) if randomize_target and target_rule else None
    original_card = context.payload.get('card')
    original_target = context.payload.get('target_card')
    original_selected_target_id = context.payload.get('selected_target_instance_id')
    original_fields = {
        key: source_card.get(key)
        for key in ('definition_id', 'description', 'effect_key', 'archetype', 'category', 'attribute', 'attribute_icon', 'material_attributes', 'material_tags', 'display_tags', 'deck_buildable', 'tags')
    }
    try:
        for key in original_fields:
            if key in copied_definition:
                source_card[key] = deepcopy(copied_definition[key])
        context.payload['card'] = source_card
        if copied_target is not None:
            context.payload['target_card'] = copied_target
            context.payload['selected_target_instance_id'] = copied_target.get('instance_id')
        else:
            context.payload.pop('target_card', None)
            context.payload.pop('selected_target_instance_id', None)
        copied_handler(context)
    finally:
        for key, value in original_fields.items():
            if value is None:
                source_card.pop(key, None)
            else:
                source_card[key] = value
        context.payload['card'] = original_card
        if original_target is None:
            context.payload.pop('target_card', None)
        else:
            context.payload['target_card'] = original_target
        if original_selected_target_id is None:
            context.payload.pop('selected_target_instance_id', None)
        else:
            context.payload['selected_target_instance_id'] = original_selected_target_id
    _add_log(context.state, f"{source_name} 额外触发 {copied_card['name']} 的揭示效果。")
    return True


def _boost_allied_espers(context: 'EventContext', amount: int) -> int:
    if amount <= 0:
        return 0
    side = str(context.payload['side'])
    boosted = 0
    for location in context.state.get('locations', []):
        for card in _revealed_cards(location, side):
            if card.get('type') != CARD_TYPE_ESPER:
                continue
            _boost_card(card, amount, context.payload['card']['name'])
            boosted += 1
    return boosted


def _resolve_damage_packet_amount(
    context: 'EventContext',
    target: JsonDict,
    amount: int,
    source_name: str,
    *,
    timing: str = 'effect',
) -> int:
    amount = max(0, int(amount))
    payload = dispatch_event(context.state, GameEvent.DAMAGE_PACKET, {
        'side': str(context.payload['side']),
        'opponent_side': str(context.payload.get('opponent_side') or ''),
        'location': context.payload['location'],
        'location_id': context.payload['location']['id'],
        'source_card': context.payload.get('card'),
        'source_instance_id': str((context.payload.get('card') or {}).get('instance_id') or ''),
        'damage_target_card': target,
        'damage_target_instance_id': str(target.get('instance_id') or ''),
        'source_name': source_name,
        'base_amount': amount,
        'amount': amount,
        'timing': timing,
    })
    return max(0, int(payload.get('amount') or 0))


def _impact_damage(
    context: 'EventContext',
    target: JsonDict,
    amount: int,
    source_name: str,
    *,
    timing: str = 'effect',
) -> bool:
    amount = _resolve_damage_packet_amount(context, target, amount, source_name, timing=timing)
    if amount <= 0:
        return False
    power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
    _boost_card(target, -amount, source_name)
    power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
    context.state.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_instance_id': context.payload['card']['instance_id'],
        'source_location_id': context.payload['location']['id'],
        'target_instance_id': target['instance_id'],
        'title': source_name,
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} - {amount} = {power_after}',
    })
    return power_before > 0 and power_after <= 0


def _damage_all_enemies(context: 'EventContext', amount: int, *, source_name: str, timing: str = 'effect') -> bool:
    opponent = str(context.payload['opponent_side'])
    destroyed = False
    targets = [
        card
        for card in _revealed_cards(context.payload['location'], opponent)
        if card.get('type') != CARD_TYPE_TOKEN
    ]
    for target in targets:
        destroyed = _impact_damage(context, target, amount, source_name, timing=timing) or destroyed
    return destroyed


def _trigger_dafutier_discord_passive(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    original_card = context.payload.get('card')
    original_location = context.payload.get('location')
    try:
        for location in context.state.get('locations', []):
            for card in _revealed_cards(location, side):
                if _definition_id(card) != 'dafutier':
                    continue
                context.payload['card'] = card
                context.payload['location'] = location
                _damage_all_enemies(context, 2, source_name=card['name'])
                _add_log(context.state, f"{card['name']} 因我方触发失谐，对所有敌人造成 2 点伤害。")
    finally:
        context.payload['card'] = original_card
        context.payload['location'] = original_location


def _random_enemy_hits(context: 'EventContext', hit_count: int, amount: int, *, timing: str = 'effect') -> int:
    opponent = str(context.payload['opponent_side'])
    hits = 0
    for _ in range(max(0, hit_count)):
        candidates = [
            card
            for card in _revealed_cards(context.payload['location'], opponent)
            if card.get('type') != CARD_TYPE_TOKEN and _raw_card_power(card) > 0
        ]
        if not candidates:
            break
        target = random.choice(candidates)
        _impact_damage(context, target, amount, context.payload['card']['name'], timing=timing)
        hits += 1
    return hits


def _boost_card(card: JsonDict, amount: int, source_name: str = '效果') -> None:
    card['bonus_power'] = int(card.get('bonus_power', 0)) + amount
    card['computed_power'] = _raw_card_power(card)
    _add_buff_source(card, source_name, amount)


def _add_buff_source(card: JsonDict, source_name: str, amount: int) -> None:
    if amount == 0:
        return
    sources = card.setdefault('buff_sources', [])
    sources.append({
        'name': str(source_name or '效果'),
        'amount': int(amount),
        'key': '',
    })
    del sources[8:]


def _raw_card_power(card: JsonDict) -> int:
    return int(card.get('base_power', 0)) + int(card.get('bonus_power', 0))


def _count_location_tag(location: JsonDict, side: str, tag: str) -> int:
    base_count = _location_mark_count(location, side, tag) + sum(
        1
        for card in location['cards'][side]
        if card.get('revealed') and tag in card.get('tags', [])
    )
    if not tag.startswith('mat_'):
        return base_count
    consumed_count = sum(
        1
        for card in location['cards'][side]
        if card.get('revealed')
        for consumed_tag in card.get('consumed_material_tags', [])
        if consumed_tag == tag
    )
    return base_count + consumed_count


def _count_board_tag(state: JsonDict, side: str, tag: str) -> int:
    return sum(_count_location_tag(location, side, tag) for location in state.get('locations', []))


def _count_harmony_mark(state: JsonDict, side: str, tag: str) -> int:
    return sum(
        _location_mark_count(location, side, tag) + sum(
            1
            for card in location['cards'][side]
            if card.get('revealed') and tag in card.get('tags', []) and TAG_HARMONY in card.get('tags', [])
        )
        for location in state.get('locations', [])
    )


def _own_damage_marker_type_count(context: 'EventContext') -> int:
    side = str(context.payload['side'])
    count = 1 if _count_harmony_mark(context.state, side, TAG_MURK) > 0 else 0
    for tag in (TAG_ZHUE_HUCHI, TAG_NIGHTMARE, TAG_PANYU_QIU):
        if _count_board_tag(context.state, side, tag) > 0:
            count += 1
    return count


def _count_board_or_discard_items(state: JsonDict, side: str, predicate: Any) -> int:
    board_count = sum(
        1
        for location in state.get('locations', [])
        for card in location.get('cards', {}).get(side, [])
        if card.get('revealed') and predicate(card)
    )
    discard_count = sum(1 for card in state['sides'][side].get('discard', []) if predicate(card))
    return board_count + discard_count


def _count_hand_tag(state: JsonDict, side: str, tag: str) -> int:
    return sum(1 for card in state['sides'][side].get('hand', []) if tag in card.get('tags', []))


def _add_combo_counter(state: JsonDict, side: str, key: str, amount: int) -> int:
    combo = state['sides'][side].setdefault('combo', {})
    combo[key] = int(combo.get(key, 0)) + amount
    return int(combo[key])


def _add_turn_combo_counter(state: JsonDict, side: str, key: str, amount: int) -> int:
    combo = state['sides'][side].setdefault('combo', {})
    turn = int(state.get('turn') or 0)
    turn_key = f'{key}_turn'
    if int(combo.get(turn_key) or 0) != turn:
        combo[key] = 0
        combo[turn_key] = turn
    combo[key] = int(combo.get(key, 0)) + amount
    return int(combo[key])


def _turn_combo_count(state: JsonDict, side: str, key: str) -> int:
    combo = state['sides'][side].setdefault('combo', {})
    if int(combo.get(f'{key}_turn') or 0) != int(state.get('turn') or 0):
        return 0
    return int(combo.get(key, 0))


def _schedule_next_turn_energy_penalty(context: 'EventContext', target_side: str, amount: int, source_name: str) -> None:
    penalty = max(0, int(amount))
    if penalty <= 0:
        return
    combo = context.state['sides'][target_side].setdefault('combo', {})
    next_turn = int(context.state.get('turn') or 0) + 1
    if int(combo.get('next_turn_energy_penalty_turn') or 0) != next_turn:
        combo['next_turn_energy_penalty'] = 0
    combo['next_turn_energy_penalty_turn'] = next_turn
    combo['next_turn_energy_penalty'] = int(combo.get('next_turn_energy_penalty') or 0) + penalty
    _add_log(context.state, f"{source_name} 使对手下回合可用能量 -{penalty}。")


def _draw_one_from_deck(state: JsonDict, side: str) -> JsonDict | None:
    side_state = state['sides'][side]
    if not side_state.get('deck'):
        return None
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(state, side, '抽牌')
        return None
    card = side_state['deck'].pop(0)
    side_state['hand'].append(card)
    _append_draw_action(state, side, card, '抽牌')
    return card


def _append_draw_action(state: JsonDict, side: str, card: JsonDict, title: str) -> None:
    action: JsonDict = {
        'kind': 'draw_card',
        'side': side,
        'card_instance_id': card['instance_id'],
        'title': title or '抽牌',
        'subtitle': '从牌库加入手牌',
        'reason': title or '抽牌',
        'silent': False,
        'card': _action_card_payload(card),
    }
    source_instance_id = str(state.get('_active_reveal_source_instance_id') or '')
    if source_instance_id:
        action['source_instance_id'] = source_instance_id
    state.setdefault('action_queue', []).append(action)


def _action_card_payload(card: JsonDict) -> JsonDict:
    return {
        'instance_id': card.get('instance_id'),
        'definition_id': card.get('definition_id'),
        'hidden': False,
        'revealed': card.get('revealed', False),
        'staged': bool(card.get('staged')),
        'name': card.get('name', ''),
        'type': card.get('type', CARD_TYPE_ANOMALY_ITEM),
        'cost': int(card.get('cost') or 0) + int(card.get('cost_modifier') or 0),
        'base_cost': int(card.get('cost') or 0),
        'original_cost': int(card.get('cost') or 0),
        'power': int(card.get('computed_power', _raw_card_power(card)) or 0),
        'base_power': int(card.get('base_power') or 0),
        'original_power': int(card.get('base_power') or 0),
        'bonus_power': int(card.get('bonus_power') or 0),
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
        'display_tags': list(card.get('display_tags', [])),
        'deck_buildable': card.get('deck_buildable') is not False,
        'buff_sources': [deepcopy(source) for source in card.get('buff_sources', [])],
    }


def _add_log(state: JsonDict, message: str) -> None:
    state.setdefault('log', [])
    state['log'].insert(0, message)
    del state['log'][LOG_LIMIT:]


TOKEN_CARDS['surplus_charge']['event_hooks'] = {GameEvent.CARD_REVEALED.value: surplus_vanish}

__all__ = [name for name in globals() if not name.startswith('__')]
