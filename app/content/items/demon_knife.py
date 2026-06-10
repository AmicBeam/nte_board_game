import random
from typing import TYPE_CHECKING

from app.content.items.common import add_item_log
from app.engine.effects import get_runtime_effect
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


POST_BATTLE_ACTION_QUEUE_KEY = '_post_battle_action_queue'
DEMON_KNIFE_ICON = '/static/images/item/DemonKnife_256.webp'
WHETSTONE_CHANCE_BY_QUALITY = {
    'common': 0.12,
    'phase_1': 0.20,
    'phase_2': 0.32,
    'phase_3': 0.48,
    'phase_4': 0.65,
    'elite': 0.36,
    'rare': 0.48,
    'boss': 1.0,
}


def demon_knife_after_damage(context: 'EventContext') -> None:
    damage_package = context.payload
    if damage_package.get('source_type') not in {'player', 'item'}:
        return
    if damage_package.get('target_type') != 'enemy':
        return
    if not damage_package.get('target_defeated'):
        return
    effect = get_runtime_effect(context.state, str(context.instance_id))
    if effect is None:
        return
    enemy = _find_enemy(context, str(damage_package.get('target_id', '')))
    chance = _whetstone_chance(enemy)
    if random.random() >= chance:
        return
    data = effect.setdefault('data', {})
    stacks = max(0, int(data.get('stacks', 0) or 0)) + 1
    data['stacks'] = stacks
    data['attack_bonus'] = stacks
    enemy_name = str((enemy or {}).get('name') or damage_package.get('target_name') or '敌人')
    chance_percent = int(chance * 100)
    message = f'击败 {enemy_name} 后获得磨刀石（{chance_percent}%），妖刀自动吸收，攻击永久 +1。当前妖刀层数：{stacks}。'
    add_item_log(context, message)
    context.state.setdefault(POST_BATTLE_ACTION_QUEUE_KEY, []).append({
        'type': 'popup',
        'title': '妖刀',
        'message': message,
        'icon': DEMON_KNIFE_ICON,
    })


def _find_enemy(context: 'EventContext', enemy_id: str) -> dict | None:
    boss = context.state.get('map', {}).get('boss', {})
    if str(boss.get('id')) == enemy_id:
        return boss
    for monster in context.state.get('map', {}).get('monsters', []):
        if str(monster.get('id')) == enemy_id:
            return monster
    return None


def _whetstone_chance(enemy: dict | None) -> float:
    if not enemy:
        return WHETSTONE_CHANCE_BY_QUALITY['common']
    if enemy.get('kind') == 'boss':
        return WHETSTONE_CHANCE_BY_QUALITY['boss']
    quality = str(enemy.get('quality') or f"phase_{int(enemy.get('phase', 0) or 0)}")
    return WHETSTONE_CHANCE_BY_QUALITY.get(quality, WHETSTONE_CHANCE_BY_QUALITY['common'])


ITEM = {
    'id': 'demon_knife',
    'name': '妖刀',
    'type': 'attack',
    'rarity': 'sr',
    'icon': DEMON_KNIFE_ICON,
    'description': '被动：携带时，击败敌人后根据敌人品质有概率获得磨刀石；磨刀石会被妖刀自动吸收，使妖刀永久攻击 +1。',
    'can_play': False,
    'zone_effects': {
        'hand': ['demon_knife_growth'],
    },
    'runtime_effects': {
        'demon_knife_growth': {
            'initial_data': {
                'stacks': 0,
                'attack_bonus': 0,
            },
            'event_hooks': {
                GameEvent.DAMAGE_APPLIED.value: demon_knife_after_damage,
            },
        },
    },
}
