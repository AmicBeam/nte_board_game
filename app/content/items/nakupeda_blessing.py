from typing import TYPE_CHECKING

from app.engine.effects import remove_runtime_effect
from app.engine.events import GameEvent
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


LOG_LIMIT = 18
POST_BATTLE_ACTION_QUEUE_KEY = '_post_battle_action_queue'
BLESSING_ICON = '/static/images/map_object/RobBankItem_030.webp'

logger = get_logger('nte.items.nakupeda_blessing')


def _add_log(context: 'EventContext', message: str) -> None:
    actor_nickname = str(context.payload.get('actor_nickname', '当前玩家'))
    context.state.setdefault('log', []).insert(0, f'[{actor_nickname}] {message}')
    del context.state['log'][LOG_LIMIT:]
    logger.info('[%s] %s', actor_nickname, message)


def _defer_popup(context: 'EventContext', message: str) -> None:
    context.state.setdefault(POST_BATTLE_ACTION_QUEUE_KEY, []).append({
        'type': 'popup',
        'title': '纳库佩达的祝福',
        'message': message,
        'icon': BLESSING_ICON,
    })


def _consume_source_item(context: 'EventContext') -> bool:
    effect = next(
        (item for item in context.state.get('active_effects', []) if item.get('instance_id') == context.instance_id),
        None,
    )
    source_instance_id = str(effect.get('source_instance_id', '')) if effect else ''
    if not source_instance_id:
        return False
    for index, item_instance in enumerate(context.state.get('hand', [])):
        if str(item_instance.get('instance_id')) != source_instance_id:
            continue
        item_instance['zone'] = 'discard_pile'
        context.state.setdefault('discard_pile', []).append(context.state['hand'].pop(index))
        remove_runtime_effect(context.state, str(context.instance_id))
        return True
    remove_runtime_effect(context.state, str(context.instance_id))
    return False


def blessing_after_damage(context: 'EventContext') -> None:
    damage_package = context.payload
    if damage_package.get('target_type') != 'player':
        return
    if int(damage_package.get('final_damage', 0) or 0) <= 0:
        return
    player_state = context.state['player']
    max_hp = max(1, int(player_state.get('max_hp', 1) or 1))
    current_hp = max(0, int(player_state.get('hp', 0) or 0))
    if current_hp * 100 >= max_hp * 30:
        return
    if not _consume_source_item(context):
        return
    heal_amount = max(1, max_hp // 2)
    healed_to = min(max_hp, current_hp + heal_amount)
    actual_heal = healed_to - current_hp
    player_state['hp'] = healed_to
    message = f'伤害后生命低于 30%，消耗本道具并回复 {actual_heal} 点生命。'
    _add_log(context, message)
    _defer_popup(context, message)


ITEM = {
    'id': 'nakupeda_blessing',
    'name': '纳库佩达的祝福',
    'type': 'recovery',
    'rarity': 'sr',
    'icon': BLESSING_ICON,
    'description': '被动：受到伤害后，若生命低于 30%，消耗本道具并回复 50% 最大生命。',
    'can_play': False,
    'zone_effects': {
        'hand': ['nakupeda_blessing_hand_trigger'],
    },
    'runtime_effects': {
        'nakupeda_blessing_hand_trigger': {
            'event_hooks': {
                GameEvent.DAMAGE_APPLIED.value: blessing_after_damage,
            },
        },
    },
}
