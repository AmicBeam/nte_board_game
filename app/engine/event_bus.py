from collections.abc import Callable

from app.content.loader import get_character, get_duel_card, get_item, get_map_object, resolve_map_object_id
from app.engine.event_context import EventContext, EventHook, JsonDict
from app.engine.events import REPLACEABLE_EVENTS
from app.utils.logger import get_logger

logger = get_logger('nte.event_bus')


def dispatch_event(
    state: JsonDict,
    event_name: object,
    payload: JsonDict | None = None,
    default_handler: EventHook | None = None,
) -> JsonDict:
    # 事件总线统一按队列顺序执行，避免 handler 递归直接套 handler。
    event_key = getattr(event_name, 'value', event_name)
    initial_payload = _enrich_payload_with_actor(state, payload or {})
    event_queue = [(event_key, initial_payload)]
    last_payload = initial_payload
    is_first_event = True
    while event_queue:
        queued_event_name, queued_payload = event_queue.pop(0)
        queued_default_handler = default_handler if is_first_event else None
        last_payload = _dispatch_single_event(state, queued_event_name, queued_payload, event_queue, queued_default_handler)
        is_first_event = False
    return last_payload


def run_phase_sequence(
    state: JsonDict,
    event_names: tuple[object, ...],
    payload_builder: Callable[[object], JsonDict] | None = None,
    default_handler_builder: Callable[[object], EventHook | None] | None = None,
) -> JsonDict:
    # 引擎按阶段预定义顺序逐个派发事件常量。
    last_payload = {}
    for event_name in event_names:
        payload = payload_builder(event_name) if payload_builder is not None else {}
        default_handler = default_handler_builder(event_name) if default_handler_builder is not None else None
        last_payload = dispatch_event(state, event_name, payload, default_handler=default_handler)
    return last_payload


def _dispatch_single_event(
    state: JsonDict,
    event_name: str,
    payload: JsonDict,
    event_queue: list[tuple[str, JsonDict]],
    default_handler: EventHook | None = None,
) -> JsonDict:
    # 单次派发只负责当前事件名对应的一批 listener。
    # 若某个 listener 继续 emit 新事件，新事件会被追加到总队列尾部，等待后续处理。
    payload = _enrich_payload_with_actor(state, payload)
    listeners = _collect_listeners(state, event_name, payload)
    replace_allowed = event_name in REPLACEABLE_EVENTS
    replace_listeners = [listener for listener in listeners if listener['mode'] == 'replace' and replace_allowed]
    append_listeners = [listener for listener in listeners if listener['mode'] != 'replace' or not replace_allowed]
    if not replace_allowed:
        for listener in listeners:
            if listener['mode'] == 'replace':
                logger.warning('Event %s does not allow replace mode, fallback to append listener %s', event_name, listener['hook_id'])
    if replace_listeners:
        logger.info('Dispatch event %s to %s replace listener(s)', event_name, len(replace_listeners))
        payload = _run_listeners(state, event_name, payload, event_queue, replace_listeners)
    elif default_handler is not None:
        payload = _run_default_handler(state, event_name, payload, event_queue, default_handler)
    if append_listeners:
        logger.info('Dispatch event %s to %s append listener(s)', event_name, len(append_listeners))
        payload = _run_listeners(state, event_name, payload, event_queue, append_listeners)
    return payload


def _collect_listeners(state: JsonDict, event_name: str, payload: JsonDict) -> list[dict[str, object]]:
    # 当前会收集角色实例、道具实例、运行时效果，以及 payload 中指向的地图物件 hook。
    listeners = []
    character_instance = state.get('character_instance', {})
    character_definition = get_character(character_instance.get('definition_id', '')) or {}
    hook_id = character_definition.get('passive_events', {}).get(event_name)
    if hook_id:
        listeners.append({
            'hook_id': _resolve_hook_payload(hook_id, 'handler'),
            'mode': _resolve_hook_payload(hook_id, 'mode') or 'append',
            'origin': 'character',
            'instance_id': character_instance.get('instance_id'),
        })
    target_instance_id = payload.get('target_instance_id')
    for zone_name in ('hand', 'discard_pile'):
        for item_instance in state.get(zone_name, []):
            if target_instance_id is not None and item_instance.get('instance_id') != target_instance_id:
                continue
            item_definition = get_item(item_instance['definition_id']) or {}
            hook_id = item_definition.get('event_hooks', {}).get(event_name)
            if hook_id:
                listeners.append({
                    'hook_id': _resolve_hook_payload(hook_id, 'handler'),
                    'mode': _resolve_hook_payload(hook_id, 'mode') or 'append',
                    'origin': f'item:{zone_name}',
                    'instance_id': item_instance.get('instance_id'),
                })
    for effect_instance in state.get('active_effects', []):
        definition_type = effect_instance.get('definition_type', 'item')
        if definition_type == 'character':
            effect_definition = get_character(effect_instance.get('definition_id', '')) or {}
        else:
            effect_definition = get_item(effect_instance.get('definition_id', '')) or {}
        runtime_effect = effect_definition.get('runtime_effects', {}).get(effect_instance.get('effect_id'), {})
        hook_id = runtime_effect.get('event_hooks', {}).get(event_name)
        if hook_id:
            listeners.append({
                'hook_id': _resolve_hook_payload(hook_id, 'handler'),
                'mode': _resolve_hook_payload(hook_id, 'mode') or 'append',
                'origin': 'active_effect',
                'instance_id': effect_instance.get('instance_id'),
            })
    for card_instance in _iter_duel_card_instances(state):
        if target_instance_id is not None and card_instance.get('instance_id') != target_instance_id:
            continue
        card_definition = get_duel_card(str(card_instance.get('definition_id', ''))) or {}
        hook_id = card_definition.get('event_hooks', {}).get(event_name)
        if hook_id:
            listeners.append({
                'hook_id': _resolve_hook_payload(hook_id, 'handler'),
                'mode': _resolve_hook_payload(hook_id, 'mode') or 'append',
                'origin': 'duel_card',
                'instance_id': card_instance.get('instance_id'),
            })
    tile = payload.get('tile')
    if tile:
        object_id = payload.get('object_id') or resolve_map_object_id(tile)
        map_object = get_map_object(object_id) or {}
        hook_id = map_object.get('event_hooks', {}).get(event_name)
        if hook_id:
            listeners.append({
                'hook_id': _resolve_hook_payload(hook_id, 'handler'),
                'mode': _resolve_hook_payload(hook_id, 'mode') or 'append',
                'origin': 'map_object',
                'instance_id': object_id,
            })
    return listeners


def _iter_duel_card_instances(state: JsonDict) -> list[JsonDict]:
    instances: list[JsonDict] = []
    for side_state in state.get('sides', {}).values():
        for zone_name in ('hand', 'deck', 'discard'):
            zone = side_state.get(zone_name, [])
            if isinstance(zone, list):
                instances.extend(card for card in zone if isinstance(card, dict))
    for location in state.get('locations', []):
        cards_by_side = location.get('cards', {})
        if not isinstance(cards_by_side, dict):
            continue
        for zone in cards_by_side.values():
            if isinstance(zone, list):
                instances.extend(card for card in zone if isinstance(card, dict))
    return instances


def _run_default_handler(
    state: JsonDict,
    event_name: str,
    payload: JsonDict,
    event_queue: list[tuple[str, JsonDict]],
    default_handler: EventHook,
) -> JsonDict:
    logger.info('Dispatch event %s to default handler', event_name)
    context = EventContext(
        state=state,
        event_name=event_name,
        payload=payload,
        origin='engine:default',
        hook_id='__default__',
    )
    default_handler(context)
    event_queue.extend(context.queue)
    return context.payload


def _run_listeners(
    state: JsonDict,
    event_name: str,
    payload: JsonDict,
    event_queue: list[tuple[str, JsonDict]],
    listeners: list[dict[str, object]],
) -> JsonDict:
    for listener in listeners:
        hook = _resolve_hook(listener['hook_id'])
        if hook is None:
            logger.warning('No hook registered for %s', listener['hook_id'])
            continue
        context = EventContext(
            state=state,
            event_name=event_name,
            payload=payload,
            origin=listener['origin'],
            instance_id=listener['instance_id'],
            hook_id=listener['hook_id'],
        )
        hook(context)
        event_queue.extend(context.queue)
        payload = context.payload
    return payload


def _resolve_hook_payload(hook_id: object, field_name: str) -> object | None:
    if isinstance(hook_id, dict):
        return hook_id.get(field_name)
    if field_name == 'handler':
        return hook_id
    return None


def _resolve_hook(hook_id: object) -> EventHook | None:
    # 内容层统一允许直接把 callable 挂进定义；非 callable 一律视为无效 hook。
    if callable(hook_id):
        return hook_id
    return None


def _enrich_payload_with_actor(state: JsonDict, payload: JsonDict) -> JsonDict:
    actor_uid = state.get('current_actor_uid')
    players = state.get('players', {})
    if actor_uid not in players:
        return payload
    actor_scope = players[str(actor_uid)]
    profile = actor_scope.get('profile', {})
    payload.setdefault('actor_uid', str(actor_uid))
    payload.setdefault('actor_nickname', str(profile.get('nickname', actor_uid)))
    payload.setdefault('actor_seat', str(profile.get('seat', 'host')))
    return payload
