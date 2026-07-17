from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def genesis_muscle_faith(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    has_big_unit = any(
        _raw_card_power(item) >= 8
        for location in context.state.get('locations', [])
        for item in location.get('cards', {}).get(side, [])
        if item.get('revealed')
    )
    if not has_big_unit:
        _add_log(context.state, f"{card['name']} 没有找到战力 >=8 的己方单位。")
        return
    if _create_token_at_location(context, 'muscle_plush', side=side):
        token = context.payload['location']['cards'][side][-1]
        returned = int(context.state['sides'][side].setdefault('combo', {}).get('returned_items', 0))
        bonus = min(4, returned)
        if bonus:
            _boost_card(token, bonus, card['name'])
        _add_log(context.state, f"{card['name']} 部署棉绒绒衍生物，并按 {returned} 次回手使其 +{bonus}。")


ITEM = {'id': 'genesis_muscle_faith',
 'name': '暴走棉绒绒-肌肉信仰',
 'cost': 5,
 'power': 7,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/暴走棉绒绒-肌肉信仰.webp',
 'description': '揭示：若己方有战力 >=8 的单位，部署 1 个灵属性材料类别、3 战力的棉绒绒衍生物；本局对战中每有 1 张己方道具被返回手牌，该衍生物 +1，最多 +4。',
 'effect_key': 'genesis_muscle_faith',
 'tags': ['genesis', 'tool', 'material', 'mat_fons'],
 'archetype': 'genesis',
 'category': '重要',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_fons'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/暴走棉绒绒-肌肉信仰.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_muscle_faith}
