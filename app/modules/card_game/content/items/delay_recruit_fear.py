from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def delay_recruit_fear(context: 'EventContext') -> None:
    card = context.payload['card']
    target = _lowest_opponent(context)
    if target is None:
        _add_log(context.state, f"{card['name']} 没有可影响的对手道具。")
        return
    before = _raw_card_power(target)
    _boost_card(target, -2, card['name'])
    _add_log(context.state, f"{card['name']} 使 {target['name']} -2。")
    if before > 0 and _raw_card_power(target) <= 0:
        opponent = str(context.payload['opponent_side'])
        same_name_targets = [
            item
            for location in context.state.get('locations', [])
            for item in location.get('cards', {}).get(opponent, [])
            if (
                item is not target
                and item.get('revealed')
                and item.get('type') == CARD_TYPE_ANOMALY_ITEM
                and item.get('name') == target.get('name')
            )
        ]
        for same_name_target in same_name_targets:
            _boost_card(same_name_target, -1, card['name'])
        if same_name_targets:
            _add_log(context.state, f"{card['name']} 使对手场上 {len(same_name_targets)} 张同名道具 -1。")


ITEM = {'id': 'delay_recruit_fear',
 'name': '新兵的怯懦',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/新兵的怯懦.webp',
 'description': '揭示：对手当前战力最低的表侧道具 -2；若其进入墓地，使对手场上所有同名道具 -1。',
 'effect_key': 'delay_recruit_fear',
 'tags': ['delay', 'tool', 'material', 'mat_signal'],
 'archetype': 'delay',
 'category': '材料',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': ['mat_signal'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/新兵的怯懦.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: delay_recruit_fear}
