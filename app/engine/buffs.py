from __future__ import annotations

from copy import deepcopy

from app.engine.effects import build_runtime_effect, register_runtime_effect
from app.engine.event_context import JsonDict

PLAYER_BUFF_DEFINITION_TYPE = 'buff'
IDENTIFICATION_BUFF_DEFINITION_ID = 'identification_growth'
SAFE_BONUS_ROLL_BUFF_ID = 'safe_bonus_roll'
SAFE_OPEN_TRIGGER = 'safe_open'
SAFE_BONUS_ROLL_TEXT = '下次开宝箱：追加判定'
SAFE_BONUS_ROLL_ICON = '/static/images/ui/identification-growth.svg'


def register_safe_bonus_roll_buff(state: JsonDict, stacks: int = 1) -> JsonDict:
    return register_player_buff(
        state,
        effect_id=SAFE_BONUS_ROLL_BUFF_ID,
        trigger=SAFE_OPEN_TRIGGER,
        display_text=SAFE_BONUS_ROLL_TEXT,
        icon=SAFE_BONUS_ROLL_ICON,
        stacks=stacks,
    )


def register_player_buff(
    state: JsonDict,
    *,
    effect_id: str,
    trigger: str,
    display_text: str,
    icon: str = 'event',
    stacks: int = 1,
) -> JsonDict:
    stack_count = max(1, int(stacks))
    existing = _find_stackable_buff(state, effect_id, trigger)
    if existing is not None:
        data = existing.setdefault('data', {})
        data['stacks'] = max(1, int(data.get('stacks', 1) or 1)) + stack_count
        _refresh_buff_display_text(data)
        return existing
    effect = build_runtime_effect(
        definition_type=PLAYER_BUFF_DEFINITION_TYPE,
        definition_id=IDENTIFICATION_BUFF_DEFINITION_ID,
        effect_id=effect_id,
        source_instance_id=f'{IDENTIFICATION_BUFF_DEFINITION_ID}:{effect_id}',
        data={
            'kind': 'player_buff',
            'show_in_buff_bar': True,
            'trigger': trigger,
            'base_display_text': display_text,
            'display_text': display_text,
            'icon': icon,
            'stacks': stack_count,
        },
    )
    _refresh_buff_display_text(effect['data'])
    return register_runtime_effect(state, effect)


def trigger_player_buffs(
    state: JsonDict,
    trigger: str,
    *,
    effect_id: str | None = None,
    consume_one: bool = True,
) -> list[JsonDict]:
    consumed: list[JsonDict] = []
    effects = state.setdefault('active_effects', [])
    retained: list[JsonDict] = []
    for effect in effects:
        if not _matches_trigger(effect, trigger, effect_id) or (consume_one and consumed):
            retained.append(effect)
            continue
        consumed.append(deepcopy(effect))
        data = effect.setdefault('data', {})
        stacks = max(1, int(data.get('stacks', 1) or 1))
        if stacks > 1:
            data['stacks'] = stacks - 1
            _refresh_buff_display_text(data)
            retained.append(effect)
    effects[:] = retained
    return consumed


def serialize_player_buffs(state: JsonDict) -> list[JsonDict]:
    buffs: list[JsonDict] = []
    for effect in state.get('active_effects', []):
        data = effect.get('data', {})
        if not data.get('show_in_buff_bar'):
            continue
        display_text = str(data.get('display_text') or '').strip()
        if not display_text:
            continue
        buffs.append({
            'instance_id': effect.get('instance_id'),
            'effect_id': effect.get('effect_id'),
            'display_text': display_text,
            'icon': data.get('icon', 'event'),
            'stacks': max(1, int(data.get('stacks', 1) or 1)),
            'trigger': data.get('trigger'),
        })
    return buffs


def migrate_legacy_safe_bonus_rolls(player_scope: JsonDict) -> None:
    player_state = player_scope.setdefault('player', {})
    legacy_stacks = int(player_state.pop('safe_bonus_rolls', 0) or 0)
    if legacy_stacks <= 0:
        return
    state_view = {'active_effects': player_scope.setdefault('active_effects', [])}
    register_safe_bonus_roll_buff(state_view, legacy_stacks)


def _find_stackable_buff(state: JsonDict, effect_id: str, trigger: str) -> JsonDict | None:
    for effect in state.setdefault('active_effects', []):
        if _matches_trigger(effect, trigger, effect_id):
            return effect
    return None


def _matches_trigger(effect: JsonDict, trigger: str, effect_id: str | None) -> bool:
    if effect.get('definition_type') != PLAYER_BUFF_DEFINITION_TYPE:
        return False
    if effect_id is not None and effect.get('effect_id') != effect_id:
        return False
    return effect.get('data', {}).get('trigger') == trigger


def _refresh_buff_display_text(data: JsonDict) -> None:
    stacks = max(1, int(data.get('stacks', 1) or 1))
    base_text = str(data.get('base_display_text') or data.get('display_text') or '').strip()
    data['display_text'] = f'{base_text} x{stacks}' if stacks > 1 else base_text
