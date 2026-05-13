from enum import Enum


class GameEvent(str, Enum):
    # 这里统一声明“引擎感知到的规则时机”。
    # 业务层和内容层都应尽量引用这些常量，而不是在各处手写裸字符串。
    # 回合与阶段推进
    TURN_BEGIN = 'turn_begin'
    DICE_ROLLED = 'dice_rolled'
    ACTION_PHASE_BEGIN = 'action_phase_begin'
    ACTION_PHASE_END = 'action_phase_end'
    # 玩家主动行动
    ITEM_PLAYED = 'item_played'
    ITEM_ZONE_CHANGED = 'item_zone_changed'
    MOVE_PHASE_BEGIN = 'move_phase_begin'
    MOVE_STEP = 'move_step'
    MOVE_BLOCK_CHECK = 'move_block_check'
    MOVE_THROUGH = 'move_through'
    MOVE_STOP = 'move_stop'
    MOVE_REDIRECTED = 'move_redirected'
    # 地图交互
    IDENTIFY = 'identify'
    MAP_OBJECT_TRIGGERED = 'map_object_triggered'
    PLAYER_STATS_CHANGED = 'player_stats_changed'
    # 战斗流程
    BATTLE_PHASE_BEGIN = 'battle_phase_begin'
    DIRECT_ATTACK = 'direct_attack'
    BEFORE_DIRECT_ATTACK = 'before_direct_attack'
    CREATE_DAMAGE_PACKAGE = 'create_damage_package'
    APPLY_DAMAGE_PACKAGE = 'apply_damage_package'
    DAMAGE_APPLIED = 'damage_applied'
    DIRECT_ATTACK_RESOLVED = 'direct_attack_resolved'
    RANGED_ATTACK = 'ranged_attack'
    RANGED_ATTACK_RESOLVED = 'ranged_attack_resolved'
    BATTLE_PHASE_END = 'battle_phase_end'
    # 对局结果
    TURN_END = 'turn_end'
    RUN_VICTORY = 'run_victory'
    RUN_DEFEAT = 'run_defeat'


REPLACEABLE_EVENTS = frozenset({
    GameEvent.TURN_BEGIN.value,
    GameEvent.DICE_ROLLED.value,
    GameEvent.ACTION_PHASE_BEGIN.value,
    GameEvent.MOVE_PHASE_BEGIN.value,
    GameEvent.DIRECT_ATTACK.value,
    GameEvent.RANGED_ATTACK.value,
    GameEvent.APPLY_DAMAGE_PACKAGE.value,
})


# 回合开始固定按“回合开始 -> 掷骰完成 -> 行动阶段开启”推进。
TURN_OPENING_SEQUENCE = (
    GameEvent.TURN_BEGIN,
    GameEvent.DICE_ROLLED,
    GameEvent.ACTION_PHASE_BEGIN,
)


# 回合结束固定按“行动阶段结束 -> 回合结束”推进。
TURN_CLOSING_SEQUENCE = (
    GameEvent.ACTION_PHASE_END,
    GameEvent.TURN_END,
)
