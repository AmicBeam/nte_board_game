from typing import TYPE_CHECKING

from app.content.items.common import add_item_log, apply_direct_damage, find_nearest_enemy
from app.engine.events import GameEvent
from app.errors import RuleValidationError

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def remote_charge_item_played(context: 'EventContext') -> None:
    target = find_nearest_enemy(context.state, max_distance=2)
    if target is None:
        raise RuleValidationError('范围内没有可攻击目标。')
    add_item_log(context, f"使用 Remote Charge，锁定 {target['name']}。")
    apply_direct_damage(context, target, damage=5, source='Remote Charge')
    context.payload['resolved'] = True


ITEM = {
    'id': 'remote_charge',
    'name': '遥控充能',
    'type': 'utility',
    'rarity': 'rare',
    'description': '对 2 格内最近敌人造成 5 点伤害。',
    'effect': {'kind': 'direct_damage', 'value': 5, 'range': 2},
    'event_hooks': {
        GameEvent.ITEM_PLAYED.value: remote_charge_item_played,
    },
}
