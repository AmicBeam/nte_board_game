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
                    and str(hand_card.get('category') or '') == '耗材'
                )
            ]
            if candidates:
                index, _ = random.choice(candidates)
                _deploy_card_to_current_location(context, side_state['hand'].pop(index), card['name'])
                return
        _boost_card(card, 1, card['name'])
        _add_log(context.state, f"{card['name']} 未能部署费用 <=1 的耗材，自身 +1。")
        return
    declared = _declared_deck_item(
        context,
        lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') in {'饮料', '耗材'},
    )
    if declared is not None:
        if str(declared.get('definition_id') or '') == 'genesis_refresh_charge':
            _boost_card(card, 1, card['name'])
        _add_card_to_hand(context, declared, card['name'])
        card.pop('declared_card_instance_ids', None)
        return
    _add_log(context.state, f"{card['name']} 的宣言牌已不合法。")
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'genesis_refresh_charge',
 'name': '畅爽焕能',
 'cost': 1,
 'power': 1,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/畅爽焕能.webp',
 'description': '揭示：若「都市活力」在己方场上或墓地，随机选择手牌中 1 张费用 <=1 的耗材并部署；若不能部署，使自身 +1。',
 'effect_key': 'genesis_tutor',
 'tags': ['genesis', 'tool', 'material', 'mat_fons'],
 'archetype': 'genesis',
 'category': '饮料',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_fons'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/畅爽焕能.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_tutor}
