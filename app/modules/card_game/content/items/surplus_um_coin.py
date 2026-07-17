from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def surplus_coin_ramp(context: 'EventContext') -> None:
    card = context.payload['card']
    definition_id = _definition_id(card)
    if definition_id == 'surplus_fons':
        attributes = {'光', '灵'}
        boost_attribute = ''
    elif definition_id == 'surplus_a_coin':
        attributes = {'光', '相'}
        boost_attribute = '光'
    else:
        attributes = {'灵', '相'}
        boost_attribute = '灵'
    reduced = _reduce_hand_card_cost(context, attributes, card['name'])
    if reduced is None:
        _add_log(context.state, f"{card['name']} 没有找到可降费的手牌。")
    bonus = 0
    side = str(context.payload['side'])
    if boost_attribute and _has_turn_deployed(context, side, lambda item: str(item.get('attribute') or '') == boost_attribute):
        bonus += 1
    if _has_turn_deployed(context, side, lambda item: TAG_SURPLUS in item.get('tags', [])):
        bonus += 2 if definition_id == 'surplus_fons' else 1
    if bonus:
        _boost_card(card, bonus, card['name'])
    _add_log(context.state, f"{card['name']} 调度 {','.join(sorted(attributes))} 属性费用，自身 +{bonus}。")


ITEM = {'id': 'surplus_um_coin',
 'name': '嗯硬币',
 'cost': 0,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/嗯硬币.webp',
 'description': '揭示：手牌中 1 张灵或相属性道具下次部署费用 -1；若本回合部署过灵属性道具，自身 +1；若本回合部署过盈蓄，额外 +1。',
 'effect_key': 'surplus_coin_ramp',
 'tags': ['surplus', 'tool', 'material', 'mat_fons'],
 'archetype': 'surplus',
 'category': '货币',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_fons'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/嗯硬币.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: surplus_coin_ramp}
