from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.effects import build_runtime_effect, remove_runtime_effect, register_runtime_effect
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def route_scan_item_played(context: 'EventContext') -> None:
    register_runtime_effect(context.state, build_runtime_effect(
        definition_id='route_scan',
        effect_id='route_scan_move_bonus',
        source_instance_id=str(context.payload['item_instance_id']),
        data={'move_bonus': 1},
    ))
    add_item_log(context, '使用 Route Scan，本回合移动 +1。')
    context.payload['resolved'] = True


def route_scan_on_turn_end(context: 'EventContext') -> None:
    effect = remove_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    add_item_log(context, 'Route Scan 的移动加成在回合结束时消失。')


ITEM = {
    'id': 'route_scan',
    'name': 'Route Scan',
    'type': 'intel',
    'rarity': 'common',
    'description': '在手牌区时显示路线提示；打出后本回合移动 +1。',
    'effect': {'kind': 'route_scan', 'value': 1},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: route_scan_item_played,
    },
    'zone_effects': {
        'hand': ['route_scan_route_hint'],
    },
    'runtime_effects': {
        'route_scan_route_hint': {
            'initial_data': {
                'route_hint': '路线扫描：使用传送门可绕开中央上锁门。',
            },
        },
        'route_scan_move_bonus': {
            'event_hooks': {
                GameEvent.TURN_END.value: route_scan_on_turn_end,
            },
        },
    },
}
