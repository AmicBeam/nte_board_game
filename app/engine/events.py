from enum import Enum


class GameEvent(str, Enum):
    # 这里统一声明“引擎感知到的规则时机”。
    # 业务层和内容层都应尽量引用这些常量，而不是在各处手写裸字符串。
    # 回合与牌桌推进
    TURN_BEGIN = 'turn_begin'
    TURN_END = 'turn_end'
    CARD_PLAYED = 'card_played'
    CARD_REVEALED = 'card_revealed'
    ESPER_RESONATED = 'esper_resonated'
    MATERIAL_CONSUMED = 'material_consumed'
    LOCATION_REVEALED = 'location_revealed'
    LOCATION_SCORED = 'location_scored'
    HARMONY_MARK_ADDED = 'harmony_mark_added'
    # 对局内数值包
    DAMAGE_PACKET = 'damage_packet'
    # 对局结果
    RUN_VICTORY = 'run_victory'
    RUN_DEFEAT = 'run_defeat'


REPLACEABLE_EVENTS = frozenset({
    GameEvent.TURN_BEGIN.value,
})
