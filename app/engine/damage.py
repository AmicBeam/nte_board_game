from __future__ import annotations

from app.engine.event_bus import dispatch_event
from app.engine.event_context import EventContext, JsonDict
from app.engine.events import GameEvent
from app.utils.logger import get_logger

logger = get_logger('nte.damage')
LOG_LIMIT = 18
PLAYER_TARGET_ID = 'player'


def build_damage_package(
    *,
    source_name: str,
    source_id: str | None = None,
    target_type: str,
    target_id: str,
    amount: int,
    attack_kind: str,
    source_type: str = 'effect',
    target_name: str | None = None,
    target_player_uid: str | None = None,
    allow_block: bool = True,
) -> JsonDict:
    normalized_amount = max(0, amount)
    return {
        'source_type': source_type,
        'source_name': source_name,
        'source_id': source_id,
        'target_type': target_type,
        'target_id': target_id,
        'target_name': target_name,
        'target_player_uid': target_player_uid,
        'base_amount': normalized_amount,
        'amount': normalized_amount,
        'bonus_damage': 0,
        'reduced_damage': 0,
        'attack_kind': attack_kind,
        'allow_block': allow_block,
        'blocked_damage': 0,
        'reflected_damage': 0,
        'final_damage': 0,
        'target_defeated': False,
        'tags': [],
        'meta': {},
    }


def apply_damage_bonus(damage_package: JsonDict, bonus: int) -> int:
    applied_bonus = max(0, int(bonus))
    if applied_bonus <= 0:
        return 0
    damage_package['amount'] = max(0, int(damage_package.get('amount', 0))) + applied_bonus
    damage_package['bonus_damage'] = int(damage_package.get('bonus_damage', 0)) + applied_bonus
    return applied_bonus


def apply_damage_reduction(damage_package: JsonDict, reduction: int) -> int:
    current_amount = max(0, int(damage_package.get('amount', 0)))
    reduced = min(current_amount, max(0, int(reduction)))
    if reduced <= 0:
        return 0
    damage_package['amount'] = current_amount - reduced
    damage_package['blocked_damage'] = int(damage_package.get('blocked_damage', 0)) + reduced
    damage_package['reduced_damage'] = int(damage_package.get('reduced_damage', 0)) + reduced
    return reduced


def queue_reflected_damage(damage_package: JsonDict, reflected_damage: int) -> int:
    reflected = max(0, int(reflected_damage))
    if reflected <= 0:
        return 0
    damage_package['reflected_damage'] = int(damage_package.get('reflected_damage', 0)) + reflected
    return reflected


def resolve_damage_package(state: JsonDict, damage_package: JsonDict) -> JsonDict:
    created_package = dispatch_event(state, GameEvent.CREATE_DAMAGE_PACKAGE, damage_package)
    resolved_package = dispatch_event(
        state,
        GameEvent.APPLY_DAMAGE_PACKAGE,
        created_package,
        default_handler=_default_apply_damage_package,
    )
    dispatch_event(state, GameEvent.DAMAGE_APPLIED, resolved_package)
    return resolved_package


def _default_apply_damage_package(context: EventContext) -> None:
    damage_package = context.payload
    target = _resolve_target(
        context.state,
        str(damage_package['target_type']),
        str(damage_package['target_id']),
        target_player_uid=damage_package.get('target_player_uid'),
    )
    if target is None:
        logger.warning('Damage package target not found: %s', damage_package)
        damage_package['final_damage'] = 0
        return
    amount = max(0, int(damage_package.get('amount', 0)))
    blocked_damage = int(damage_package.get('blocked_damage', 0))
    final_damage = max(0, amount)
    target['hp'] = max(0, int(target['hp']) - final_damage)
    damage_package['target_name'] = damage_package.get('target_name') or target.get('name', damage_package['target_id'])
    damage_package['blocked_damage'] = blocked_damage
    damage_package['final_damage'] = final_damage
    damage_package['target_hp'] = target['hp']
    damage_package['target_defeated'] = target['hp'] == 0
    _add_damage_log(context.state, damage_package)


def _resolve_target(state: JsonDict, target_type: str, target_id: str, target_player_uid: object | None = None) -> JsonDict | None:
    if target_type == 'player':
        resolved_target_uid = str(target_player_uid or state.get('current_actor_uid', ''))
        players = state.get('players', {})
        if resolved_target_uid in players:
            return players[resolved_target_uid].get('player')
        return state.get('player')
    if target_type != 'enemy':
        return None
    boss = state['map']['boss']
    if boss['id'] == target_id:
        return boss
    for monster in state['map']['monsters']:
        if monster['id'] == target_id:
            return monster
    return None


def _add_damage_log(state: JsonDict, damage_package: JsonDict) -> None:
    source_name = str(damage_package.get('source_name', '未知来源'))
    target_name = str(damage_package.get('target_name', '未知目标'))
    final_damage = int(damage_package.get('final_damage', 0))
    attack_kind = str(damage_package.get('attack_kind', '攻击'))
    if str(damage_package.get('target_type')) == 'player':
        if not damage_package.get('target_name'):
            target_player_uid = str(damage_package.get('target_player_uid', state.get('current_actor_uid', '')))
            players = state.get('players', {})
            if target_player_uid in players:
                target_name = str(players[target_player_uid].get('profile', {}).get('nickname', target_player_uid))
        blocked_damage = int(damage_package.get('blocked_damage', 0))
        blocked_suffix = f'，格挡 {blocked_damage} 点' if blocked_damage > 0 else ''
        message = f'{source_name} 对 {target_name} 发动{attack_kind}，造成 {final_damage} 点伤害{blocked_suffix}。'
    else:
        message = f'{source_name} 对 {target_name} 造成 {final_damage} 点伤害。'
    state.setdefault('log', [])
    state['log'].insert(0, message)
    del state['log'][LOG_LIMIT:]
    logger.info(message)
