from typing import TYPE_CHECKING

from app.engine.effects import build_runtime_effect, remove_runtime_effect, register_runtime_effect
from app.engine.events import GameEvent

from app.content.items.common import add_item_log

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def dash_patch_item_played(context: 'EventContext') -> None:
    register_runtime_effect(context.state, build_runtime_effect(
        definition_id='dash_patch',
        effect_id='dash_patch_move_bonus',
        source_instance_id=str(context.payload['item_instance_id']),
        data={'move_bonus': 2},
    ))
    add_item_log(context, '使用 Dash Patch，本回合移动 +2。')
    context.payload['resolved'] = True


def dash_patch_on_turn_end(context: 'EventContext') -> None:
    effect = remove_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    add_item_log(context, 'Dash Patch 的移动加成在回合结束时消失。')


ITEM = {
    'id': 'dash_patch',
    'name': 'Dash Patch',
    'type': 'mobility',
    'rarity': 'common',
    'description': '本回合移动 +2。',
    'effect': {'kind': 'move_buff', 'value': 2},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: dash_patch_item_played,
    },
    'runtime_effects': {
        'dash_patch_move_bonus': {
            'event_hooks': {
                GameEvent.TURN_END.value: dash_patch_on_turn_end,
            },
        },
    },
}
