import random
from typing import TYPE_CHECKING

from app.config import (
    IDENTIFICATION_COMBO_BONUS_PERCENT_PER_STACK,
    IDENTIFICATION_COMBO_MAX_BONUS_PERCENT,
    IDENTIFICATION_EXP_SCALE,
    IDENTIFICATION_LEVEL_EXP_REQUIREMENTS,
    IDENTIFICATION_POST_MAX_BUFF_EXP,
    IDENTIFICATION_RARITY_EXP,
)
from app.content.loader import get_item

if TYPE_CHECKING:
    from app.engine.event_context import EventContext, JsonDict


MAX_IDENTIFICATION_LEVEL = 4
RARITY_ALIASES = {
    'common': 'n',
    'normal': 'n',
    'n': 'n',
    'rare': 'r',
    'r': 'r',
    'epic': 'sr',
    'sr': 'sr',
    'legendary': 'ur',
    'ur': 'ur',
}
POST_MAX_BUFFS = ('safe_bonus_roll', 'stats_up', 'gold_chequer')
IDENTIFICATION_GROWTH_ICON = '/static/images/ui/identification-growth.svg'


def initialize_identification_state(player_state: 'JsonDict', base_level: int = 1) -> None:
    player_state['identification_level'] = min(
        MAX_IDENTIFICATION_LEVEL,
        max(int(player_state.get('identification_level', base_level) or base_level), int(base_level)),
    )
    player_state.setdefault('identification_exp_units', 0)
    player_state.setdefault('identification_combo', 0)
    player_state.setdefault('identification_identified_this_turn', False)
    player_state.setdefault('identification_battled_this_turn', False)
    player_state.setdefault('safe_bonus_rolls', 0)


def identification_progress(player_state: 'JsonDict') -> 'JsonDict':
    level = max(1, min(MAX_IDENTIFICATION_LEVEL, int(player_state.get('identification_level', 1) or 1)))
    threshold_units = _threshold_units_for_level(level)
    exp_units = max(0, int(player_state.get('identification_exp_units', 0) or 0))
    return {
        'level': level,
        'combo': max(0, int(player_state.get('identification_combo', 0) or 0)),
        'bonus_percent': _combo_bonus_percent(int(player_state.get('identification_combo', 0) or 0)),
        'progress_percent': _progress_percent(exp_units, threshold_units),
        'is_max_level': level >= MAX_IDENTIFICATION_LEVEL,
        'fire_combo': int(player_state.get('identification_combo', 0) or 0) >= 10,
    }


def grant_identification_success(
    context: 'EventContext',
    *,
    definition_id: str | None = None,
    rarity: str | None = None,
    source_name: str = '鉴别',
    quantity: int = 1,
) -> None:
    player_state = context.state.setdefault('player', {})
    initialize_identification_state(player_state, int(player_state.get('identification_level', 1) or 1))
    resolved_rarity = rarity
    if definition_id:
        item_definition = get_item(definition_id) or {}
        resolved_rarity = str(item_definition.get('rarity') or resolved_rarity or 'n')
    base_exp = _rarity_exp(resolved_rarity) * max(1, int(quantity))
    if base_exp <= 0:
        return

    combo = max(0, int(player_state.get('identification_combo', 0) or 0)) + 1
    player_state['identification_combo'] = combo
    player_state['identification_identified_this_turn'] = True
    player_state['identification_exp_units'] = max(0, int(player_state.get('identification_exp_units', 0) or 0)) + _scaled_combo_exp(base_exp, combo)

    level_messages = _settle_identification_exp(context.state)
    for message in level_messages:
        _add_identification_popup(context.state, '鉴别成长', message)
        _add_log(context.state, f'{source_name}触发鉴别成长：{message}')


def mark_battle_step(state: 'JsonDict') -> None:
    player_state = state.setdefault('player', {})
    initialize_identification_state(player_state, int(player_state.get('identification_level', 1) or 1))
    player_state['identification_battled_this_turn'] = True


def settle_combo_for_turn(player_state: 'JsonDict') -> None:
    initialize_identification_state(player_state, int(player_state.get('identification_level', 1) or 1))
    if not player_state.get('identification_identified_this_turn') and not player_state.get('identification_battled_this_turn'):
        player_state['identification_combo'] = max(0, int(player_state.get('identification_combo', 0) or 0) - 1)
    player_state['identification_identified_this_turn'] = False
    player_state['identification_battled_this_turn'] = False


def reset_turn_flags(player_state: 'JsonDict') -> None:
    initialize_identification_state(player_state, int(player_state.get('identification_level', 1) or 1))
    player_state['identification_identified_this_turn'] = False
    player_state['identification_battled_this_turn'] = False


def consume_safe_bonus_roll(state: 'JsonDict') -> bool:
    player_state = state.setdefault('player', {})
    remaining = int(player_state.get('safe_bonus_rolls', 0) or 0)
    if remaining <= 0:
        return False
    player_state['safe_bonus_rolls'] = remaining - 1
    return True


def _settle_identification_exp(state: 'JsonDict') -> list[str]:
    messages: list[str] = []
    player_state = state.setdefault('player', {})
    while int(player_state.get('identification_level', 1) or 1) < MAX_IDENTIFICATION_LEVEL:
        level = int(player_state.get('identification_level', 1) or 1)
        threshold_units = _threshold_units_for_level(level)
        if int(player_state.get('identification_exp_units', 0) or 0) < threshold_units:
            return messages
        player_state['identification_exp_units'] = int(player_state.get('identification_exp_units', 0) or 0) - threshold_units
        player_state['identification_level'] = level + 1
        messages.append(f"鉴别等级提升至 {player_state['identification_level']} 级。")

    post_max_threshold = _threshold_units_for_level(MAX_IDENTIFICATION_LEVEL)
    while int(player_state.get('identification_exp_units', 0) or 0) >= post_max_threshold:
        player_state['identification_exp_units'] = int(player_state.get('identification_exp_units', 0) or 0) - post_max_threshold
        messages.append(_apply_post_max_buff(state))
    return messages


def _apply_post_max_buff(state: 'JsonDict') -> str:
    buff_id = random.choice(POST_MAX_BUFFS)
    player_state = state.setdefault('player', {})
    if buff_id == 'safe_bonus_roll':
        player_state['safe_bonus_rolls'] = int(player_state.get('safe_bonus_rolls', 0) or 0) + 1
        return '获得保险箱追加判定：下次开启保险箱时额外产出一次。'
    if buff_id == 'stats_up':
        player_state['attack'] = int(player_state.get('attack', 0) or 0) + 1
        player_state['defense'] = int(player_state.get('defense', 0) or 0) + 1
        return '攻击与防御各提升 1 点。'

    from app.content.map_objects.common import add_item_to_hand

    add_item_to_hand(state, 'gold_chequer')
    return '获得道具：金棋子。'


def _scaled_combo_exp(base_exp: int, combo: int) -> int:
    return base_exp * IDENTIFICATION_EXP_SCALE * (100 + _combo_bonus_percent(combo)) // 100


def _combo_bonus_percent(combo: int) -> int:
    return min(
        IDENTIFICATION_COMBO_MAX_BONUS_PERCENT,
        max(0, int(combo)) * IDENTIFICATION_COMBO_BONUS_PERCENT_PER_STACK,
    )


def _rarity_exp(rarity: str | None) -> int:
    normalized = RARITY_ALIASES.get(str(rarity or 'n').lower(), 'n')
    return int(IDENTIFICATION_RARITY_EXP.get(normalized, IDENTIFICATION_RARITY_EXP['n']))


def _threshold_units_for_level(level: int) -> int:
    if level >= MAX_IDENTIFICATION_LEVEL:
        return int(IDENTIFICATION_POST_MAX_BUFF_EXP) * IDENTIFICATION_EXP_SCALE
    return int(IDENTIFICATION_LEVEL_EXP_REQUIREMENTS.get(level, IDENTIFICATION_POST_MAX_BUFF_EXP)) * IDENTIFICATION_EXP_SCALE


def _progress_percent(exp_units: int, threshold_units: int) -> int:
    if threshold_units <= 0:
        return 0
    return max(0, min(100, int(exp_units * 100 / threshold_units)))


def _add_identification_popup(state: 'JsonDict', title: str, message: str) -> None:
    from app.content.map_objects.common import add_action_step

    add_action_step(state, {
        'type': 'popup',
        'icon': IDENTIFICATION_GROWTH_ICON,
        'title': title,
        'message': message,
    })


def _add_log(state: 'JsonDict', message: str) -> None:
    state.setdefault('log', []).insert(0, message)
    del state['log'][18:]
