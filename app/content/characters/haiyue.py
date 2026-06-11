from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def haiyue_darkstar_finish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    consumed = _consume_location_mark(context.payload['location'], side, TAG_DARKSTAR, 1)
    if consumed:
        _add_combo_counter(context.state, side, 'darkstar_exploded', consumed)
    repeat_count = _count_board_or_discard_items(context.state, side, lambda card: str(card.get('category') or '') == '耗材' or _definition_id(card) == 'darkstar_ringstone')
    hits = _random_enemy_hits(context, repeat_count, 1)
    _add_log(context.state, f"{context.payload['card']['name']} 立刻结算并消耗 {consumed} 层黯星，按耗材与环石数量随机造成 {hits} 次 1 点伤害。")


CHARACTER = {'id': 'haiyue',
 'name': '海月',
 'cost': 0,
 'power': 8,
 'type': 'esper',
 'element': '魂',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/海月.png',
 'description': '共鸣：立刻结算并消耗 1 层黯星；随机对 1 个敌人造成 1 点伤害，重复 X 次，X 为战场和墓地的耗材与环石数量之和。',
 'effect_key': 'haiyue_darkstar_finish',
 'tags': ['esper', 'darkstar'],
 'archetype': '',
 'category': '',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': [],
 'material_cost': 3,
 'required_material_attribute': '魂',
 'material_requirements': [{'attribute': '魂', 'count': 2}, {'category': '耗材', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/海月.png',
 'avatar_image': '/static/images/characters/portrait/海月.png'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: haiyue_darkstar_finish}
