from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def genesis_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    if _definition_id(card) == 'genesis_refresh_charge':
        has_urban = _zone_contains_definition(context, 'genesis_urban_energy', 'discard') or _board_contains_definition(context, 'genesis_urban_energy')
        if has_urban:
            side_state = context.state['sides'][str(context.payload['side'])]
            candidates = [
                (index, hand_card)
                for index, hand_card in enumerate(list(side_state.get('hand', [])))
                if (
                    hand_card.get('type') == CARD_TYPE_ANOMALY_ITEM
                    and int(hand_card.get('cost') or 0) <= 1
                    and str(hand_card.get('category') or '') in {'食物', '耗材'}
                )
            ]
            if candidates:
                index, _ = random.choice(candidates)
                _deploy_card_to_current_location(context, side_state['hand'].pop(index), card['name'])
                return
        _tutor_named_item(context, {'都市活力'}, card['name'])
        return
    declared = _declared_deck_item(
        context,
        lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') in {'饮料', '食物'},
    )
    if declared is not None:
        if str(declared.get('definition_id') or '') == 'genesis_refresh_charge':
            _boost_card(card, 1, card['name'])
        _add_card_to_hand(context, declared, card['name'])
        card.pop('declared_card_instance_ids', None)
        return
    _boost_card(card, 1, card['name'])
    _add_card_to_hand(context, _tutor_item(context, 'genesis'), card['name'])
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'genesis_urban_energy',
 'name': '都市活力',
 'cost': 1,
 'power': 2,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/都市活力.webp',
 'description': '宣言：检视牌库，选择 1 张饮料或食物。揭示：将宣言牌加入手牌；若宣言牌为「畅爽焕能」，自身 +1。',
 'effect_key': 'genesis_tutor',
 'tags': ['genesis', 'tool', 'material', 'mat_coin'],
 'archetype': 'genesis',
 'category': '耗材',
 'attribute': '光',
 'attribute_icon': '/static/images/elements/光.png',
 'material_tags': ['mat_coin'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck'],
                            'title': '都市活力 检视牌库',
                            'description': '宣言 1 张饮料或食物；揭示时加入手牌。',
                            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') in {'饮料', '食物'}}]},
 'icon': '/static/images/item/都市活力.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_tutor}
