import random
from copy import deepcopy
from typing import TYPE_CHECKING
from uuid import uuid4

from app.engine.identification import grant_identification_success

LOG_LIMIT = 18
ACTION_QUEUE_KEY = '_action_queue'

BLOCK_TYPE_BLOCK = '阻挡'
BLOCK_TYPE_INTERCEPT = '拦截'
BLOCK_TYPE_PASS = '可通过'

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def build_loot_payload(definition_id: str, overrides: dict | None = None) -> dict | None:
    from app.content.loader import get_item
    from app.engine.runtime import resolve_item_description

    item_definition = get_item(definition_id)
    if item_definition is None:
        return None
    payload = {
        'definition_id': definition_id,
        'name': item_definition.get('name', definition_id),
        'icon': item_definition.get('icon', 'event'),
        'description': resolve_item_description(item_definition),
        'value': int(item_definition.get('fons_value', 0) or 0),
    }
    if overrides:
        payload.update(overrides)
    return payload


def resolve_loot_table_entries(container: dict, table_ref: object) -> list[dict]:
    game_map = container.get('map', container)
    loot_tables = game_map.get('loot_tables', {}) if isinstance(game_map, dict) else {}
    if isinstance(table_ref, str):
        raw_entries = loot_tables.get(table_ref, [])
    elif isinstance(table_ref, list):
        raw_entries = table_ref
    else:
        raw_entries = []
    resolved_entries = []
    for raw_entry in raw_entries:
        if isinstance(raw_entry, str):
            item_id = raw_entry
            weight = 1
            overrides = {}
        elif isinstance(raw_entry, dict):
            item_id = str(raw_entry.get('item_id') or raw_entry.get('definition_id') or '')
            weight = max(0, int(raw_entry.get('weight', 1) or 0))
            if isinstance(raw_entry.get('result'), dict):
                if weight > 0:
                    resolved_entries.append({'result': deepcopy(raw_entry['result']), 'weight': weight})
                continue
            overrides = {
                key: value
                for key, value in raw_entry.items()
                if key not in {'item_id', 'definition_id', 'weight'}
            }
        else:
            continue
        if not item_id or weight <= 0:
            continue
        loot = build_loot_payload(item_id, overrides)
        if loot is not None:
            resolved_entries.append({'loot': loot, 'weight': weight})
    return resolved_entries


def resolve_loot_table(container: dict, table_ref: object) -> list[dict]:
    return [entry for entry in resolve_loot_table_entries(container, table_ref) if entry.get('loot') is not None]


def choose_loot_table_entry(container: dict, table_ref: object, fallback: object = None) -> dict | None:
    entries = resolve_loot_table_entries(container, table_ref)
    if not entries and fallback is not None:
        entries = resolve_loot_table_entries(container, fallback)
    if not entries:
        return None
    return deepcopy(random.choices(entries, weights=[entry['weight'] for entry in entries], k=1)[0])


def choose_loot_from_table(container: dict, table_ref: object, fallback: object = None) -> dict | None:
    entries = resolve_loot_table(container, table_ref)
    if not entries and fallback is not None:
        entries = resolve_loot_table(container, fallback)
    if not entries:
        return None
    return deepcopy(random.choices(
        [entry['loot'] for entry in entries],
        weights=[entry['weight'] for entry in entries],
        k=1,
    )[0])


def get_map_object_player_state(context: 'EventContext') -> dict:
    return context.state['player']


def get_map_object_actor_nickname(context: 'EventContext') -> str:
    return str(context.payload.get('actor_nickname', '当前玩家'))


def add_map_log(context: 'EventContext', message: str) -> None:
    context.state.setdefault('log', [])
    actor_nickname = get_map_object_actor_nickname(context)
    context.state['log'].insert(0, f'[{actor_nickname}] {message}')
    del context.state['log'][LOG_LIMIT:]


def add_action_step(state: dict, step: dict) -> None:
    state.setdefault(ACTION_QUEUE_KEY, []).append(step)


def add_fons(state: dict, amount: int) -> int:
    player_state = state.setdefault('player', {})
    player_state['fons_amount'] = int(player_state.get('fons_amount', 0)) + int(amount)
    for item in state.get('hand', []):
        if item.get('definition_id') == 'fons':
            item['amount'] = int(player_state['fons_amount'])
            break
    return int(player_state['fons_amount'])


def convert_identified_loot_to_fons(
    context: 'EventContext',
    loot: dict | None = None,
    quantity: int = 1,
    log_prefix: str = '鉴别发现',
) -> int:
    from app.content.loader import get_item

    loot_payload = loot or context.payload.get('tile', {}).get('loot', {})
    definition_id = str(loot_payload.get('definition_id', ''))
    item_definition = get_item(definition_id) or {}
    fons_value = int(loot_payload.get('value') or item_definition.get('fons_value', 0) or 0)
    if fons_value <= 0:
        return 0
    count = max(1, int(loot_payload.get('quantity', quantity) or 1))
    gained = fons_value * count
    total = add_fons(context.state, gained)
    loot_name = str(loot_payload.get('name') or item_definition.get('name') or '物品')
    add_map_log(context, f'{log_prefix}{loot_name}，转化为 {gained} 方斯。当前方斯：{total}。')
    context.payload['resolved'] = True
    context.payload['fons_gained'] = gained
    context.payload['fons_total'] = total
    grant_identification_success(
        context,
        definition_id=definition_id,
        source_name=log_prefix,
        quantity=count,
    )
    return gained


def identified_loot_to_fons(context: 'EventContext') -> None:
    from app.engine.events import GameEvent

    tile = context.payload['tile']
    if tile.get('collected'):
        return
    loot = tile.get('loot', {})
    definition_id = str(loot.get('definition_id', ''))
    if _is_collectible_loot(definition_id):
        count = max(1, int(loot.get('quantity', 1) or 1))
        item = add_item_to_hand(context.state, definition_id, count)
        if item is None:
            return
        loot_name = str(loot.get('name') or definition_id)
        add_map_log(context, f'鉴别发现{loot_name}，已收入道具栏。')
        grant_identification_success(context, definition_id=definition_id, source_name='鉴别发现', quantity=count)
        tile['collected'] = True
        tile['display_type'] = 'floor'
        add_tile_update_step(context.state, tile)
        add_action_step(context.state, {
            'type': 'popup',
            'icon': loot.get('icon', 'event'),
            'title': loot_name,
            'message': f'鉴别获得 {loot_name}。',
        })
        context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
            'object_id': context.payload['object_id'],
            'object_type': context.payload['tile_type'],
            'loot': loot,
            'item_instance_id': item.get('instance_id'),
            'quantity': count,
        })
        return
    gained = convert_identified_loot_to_fons(context)
    if gained <= 0:
        return
    tile['collected'] = True
    tile['display_type'] = 'floor'
    add_tile_update_step(context.state, tile)
    add_action_step(context.state, {
        'type': 'popup',
        'icon': loot.get('icon', 'event'),
        'title': loot.get('name', '鉴别物'),
        'message': f'鉴别后转化为 {gained} 方斯。',
    })
    context.emit(GameEvent.MAP_OBJECT_TRIGGERED, {
        'object_id': context.payload['object_id'],
        'object_type': context.payload['tile_type'],
        'loot': loot,
        'fons_gained': gained,
    })


def _is_collectible_loot(definition_id: str) -> bool:
    from app.content.loader import get_item

    item_definition = get_item(definition_id) or {}
    return bool(item_definition) and str(item_definition.get('type', '')) != 'loot'


def add_item_to_hand(state: dict, definition_id: str, quantity: int = 1) -> dict | None:
    from app.content.loader import get_item
    from app.engine.event_bus import dispatch_event
    from app.engine.events import GameEvent

    item_definition = get_item(definition_id)
    if item_definition is None:
        return None
    if item_definition.get('stackable') and not item_definition.get('fons_value'):
        for item in state.setdefault('hand', []):
            if item.get('definition_id') == definition_id:
                item['quantity'] = int(item.get('quantity', 1)) + int(quantity)
                return item
    item_instance = {
        'instance_id': uuid4().hex,
        'definition_id': definition_id,
        'zone': 'hand',
        'created_turn': int(state.get('turn', 1)),
    }
    if item_definition.get('stackable'):
        item_instance['quantity'] = int(quantity)
    state.setdefault('hand', []).append(item_instance)
    dispatch_event(state, GameEvent.ITEM_ZONE_CHANGED, {
        'item_instance_id': item_instance['instance_id'],
        'definition_id': definition_id,
        'from_zone': None,
        'to_zone': 'hand',
        'reason': 'map_identify',
        'quantity': int(quantity),
        'target_instance_id': item_instance['instance_id'],
    })
    return item_instance


def consume_item_from_hand(state: dict, definition_id: str, quantity: int = 1) -> bool:
    remaining = int(quantity)
    for item in list(state.get('hand', [])):
        if item.get('definition_id') != definition_id:
            continue
        count = int(item.get('quantity', 1))
        if count > remaining:
            item['quantity'] = count - remaining
            return True
        remaining -= count
        state['hand'].remove(item)
        if remaining <= 0:
            return True
    return False


def add_tile_update_step(state: dict, tile: dict) -> None:
    display_type = tile['type']
    if tile['type'] == 'chest' and tile.get('opened'):
        display_type = 'floor'
    if tile['type'] == 'event' and tile.get('resolved'):
        display_type = 'floor'
    if tile.get('object_id') in {'safe', 'large_safe'} and tile.get('opened'):
        display_type = 'floor'
    if tile['type'] == 'door' and not tile.get('locked', True):
        display_type = 'floor'
    if tile['type'] == 'keycard_door' and not tile.get('locked', True):
        display_type = 'floor'
    if tile['type'] == 'loot_item' and tile.get('collected'):
        display_type = 'floor'
    add_action_step(state, {
        'type': 'tile_update',
        'layer': tile.get('layer', state.get('map', {}).get('current_layer', 1)),
        'x': tile['x'],
        'y': tile['y'],
        'tile': dict(tile),
        'display_type': display_type,
    })
