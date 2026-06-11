from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def genesis_grow(context: 'EventContext') -> None:
    card = context.payload['card']
    target = _lowest_ally(context) or card
    side = str(context.payload['side'])
    linked = _has_turn_deployed(context, side, lambda item: _definition_id(item) in {'genesis_urban_energy', 'genesis_refresh_charge'})
    amount = 3 if linked else 2
    _boost_card(target, amount, card['name'])
    _add_log(context.state, f"{card['name']} 使 {target['name']} +{amount}。")


ITEM = {'id': 'genesis_breakfast_bag',
 'name': '速食早餐袋',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/速食早餐袋.webp',
 'description': '揭示：使己方当前战力最低的表侧道具 +2。若本回合部署过「都市活力」或「畅爽焕能」，改为 +3。',
 'effect_key': 'genesis_grow',
 'tags': ['genesis', 'tool', 'material', 'mat_fons'],
 'archetype': 'genesis',
 'category': '食物',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_fons'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/速食早餐袋.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_grow}
