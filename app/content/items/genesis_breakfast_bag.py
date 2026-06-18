from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def genesis_grow(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    linked = _has_turn_deployed(context, side, lambda item: _definition_id(item) in {'genesis_urban_energy', 'genesis_refresh_charge'})
    recovered = _declared_deck_item(
        context,
        lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') == '食物',
    )
    if recovered is not None:
        if linked:
            recovered['cost_modifier'] = max(-1, int(recovered.get('cost_modifier') or 0) - 1)
        _add_card_to_hand(context, recovered, card['name'])
        return
    _add_log(context.state, f"{card['name']} 的宣言食物道具已不合法。")


ITEM = {'id': 'genesis_breakfast_bag',
 'name': '速食早餐袋',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/速食早餐袋.webp',
 'description': '宣言：检视牌库，选择 1 张食物道具。揭示：将宣言道具加入手牌；若本回合部署过「都市活力」或「畅爽焕能」，额外使其下次部署费用 -1。',
 'effect_key': 'genesis_grow',
 'tags': ['genesis', 'tool', 'material', 'mat_fons'],
 'archetype': 'genesis',
 'category': '耗材',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_fons'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck'],
                            'title': '速食早餐袋 检视牌库',
                            'description': '宣言 1 张食物道具；揭示时加入手牌。',
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and str(item.get('category') or '') == '食物'
                            )}]},
 'icon': '/static/images/item/速食早餐袋.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_grow}
