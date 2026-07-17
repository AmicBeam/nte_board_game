from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.modules.card_game.content.common.constants import CARD_TYPE_ANOMALY_ITEM, MAX_HAND_SIZE, JsonDict

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def _reset_card_for_zone(card: JsonDict, *, revealed: bool = False) -> JsonDict:
    card['played_turn'] = None
    card['location_id'] = None
    card['revealed'] = revealed
    card['bonus_power'] = 0
    card['computed_power'] = int(card.get('base_power') or 0)
    card['cost_modifier'] = 0
    for key in (
        'staged',
        'paid_cost',
        'play_sequence',
        'reserved_as_material_for',
        'reserved_material_power',
        'pending_material_ids',
        'declared_card_instance_ids',
        'declared_card_names',
        'selected_target_name',
        'buff_sources',
    ):
        card.pop(key, None)
    return card


def _side_name(state: JsonDict, side: str) -> str:
    return str(state.get('sides', {}).get(side, {}).get('nickname') or side)


def _add_hand_limit_log(state: JsonDict, side: str, source_name: str) -> None:
    state.setdefault('log', [])
    state['log'].insert(0, f"{source_name} 想加入手牌，但 {_side_name(state, side)} 手牌已达上限 {MAX_HAND_SIZE}。")
    del state['log'][28:]


def _tutor_item(context: 'EventContext', archetype: str) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, '调度')
        return None
    for index, card in enumerate(list(side_state.get('deck', []))):
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and card.get('archetype') == archetype:
            tutored = side_state['deck'].pop(index)
            tutored['_animation_source_zone'] = 'deck'
            return tutored
    return None


def _declared_deck_item(context: 'EventContext', predicate: Any) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, context.payload.get('card', {}).get('name') or '效果')
        return None
    declared_ids = [str(card_id) for card_id in context.payload['card'].get('declared_card_instance_ids', [])]
    if not declared_ids:
        return None
    for declared_id in declared_ids:
        for index, card in enumerate(list(side_state.get('deck', []))):
            if str(card.get('instance_id') or '') != declared_id or not predicate(card):
                continue
            tutored = side_state['deck'].pop(index)
            tutored['_animation_source_zone'] = 'deck'
            return tutored
    return None


def _declared_deck_or_discard_item(context: 'EventContext', predicate: Any) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, context.payload.get('card', {}).get('name') or '效果')
        return None
    declared_ids = [str(card_id) for card_id in context.payload['card'].get('declared_card_instance_ids', [])]
    if not declared_ids:
        return None
    for declared_id in declared_ids:
        for zone_name in ('deck', 'discard'):
            for index, card in enumerate(list(side_state.get(zone_name, []))):
                if str(card.get('instance_id') or '') != declared_id or not predicate(card):
                    continue
                selected = side_state[zone_name].pop(index)
                if zone_name == 'discard':
                    selected = _reset_card_for_zone(selected, revealed=False)
                selected['_animation_source_zone'] = zone_name
                return selected
    return None


def _declared_hand_item(context: 'EventContext', predicate: Any) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    declared_ids = [str(card_id) for card_id in context.payload['card'].get('declared_card_instance_ids', [])]
    if not declared_ids:
        return None
    for declared_id in declared_ids:
        for index, card in enumerate(list(side_state.get('hand', []))):
            if str(card.get('instance_id') or '') != declared_id or not predicate(card):
                continue
            return side_state['hand'].pop(index)
    return None


def _recover_item(context: 'EventContext', archetype: str) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        _add_hand_limit_log(context.state, side, '回收')
        return None
    for index, card in enumerate(list(side_state.get('discard', []))):
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and card.get('archetype') == archetype:
            recovered = side_state['discard'].pop(index)
            recovered['_animation_source_zone'] = 'discard'
            return recovered
    return None


__all__ = [
    '_reset_card_for_zone',
    '_add_hand_limit_log',
    '_tutor_item',
    '_declared_deck_item',
    '_declared_deck_or_discard_item',
    '_declared_hand_item',
    '_recover_item',
]
