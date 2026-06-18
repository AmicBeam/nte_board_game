from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def delay_hamster_ball_material_bonus(context: 'EventContext') -> None:
    if str(context.payload.get('material_instance_id') or '') != str(context.instance_id or ''):
        return
    side = str(context.payload.get('side') or '')
    location = context.payload.get('location') if isinstance(context.payload.get('location'), dict) else None
    if not side or location is None:
        return
    opponent = 'b' if side == 'a' else 'a'
    candidates = [
        card
        for card in _revealed_cards(location, opponent)
        if card.get('type') != CARD_TYPE_TOKEN
    ]
    if not candidates:
        _add_log(context.state, f"{context.payload['material_card']['name']} 被消耗，但没有可压低的对手表侧卡牌。")
        return
    target = random.choice(candidates)
    power_before = int(target.get('computed_power', _raw_card_power(target)) or 0)
    _boost_card(target, -1, context.payload['material_card']['name'])
    power_after = int(target.get('computed_power', _raw_card_power(target)) or 0)
    context.state.setdefault('action_queue', []).append({
        'kind': 'impact_arrow',
        'source_instance_id': str(context.payload.get('material_instance_id') or ''),
        'location_id': location['id'],
        'side': opponent,
        'target_instance_id': target['instance_id'],
        'title': context.payload['material_card']['name'],
        'power_before': power_before,
        'power_after': power_after,
        'power_delta': power_after - power_before,
        'subtitle': f'{power_before} - 1 = {power_after}',
    })
    _add_log(context.state, f"{context.payload['material_card']['name']} 被当作素材消耗，使对手 {target['name']} -1。")


ITEM = {'id': 'delay_hamster_ball',
 'name': '仓鼠球',
 'cost': 1,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/仓鼠球.webp',
 'description': '被当作素材消耗时：随机使对手 1 张表侧卡牌 -1。',
 'effect_key': 'delay_hamster_ball_material_bonus',
 'tags': ['delay', 'tool', 'material', 'mat_signal'],
 'display_tags': ['不可构筑'],
 'deck_buildable': False,
 'archetype': 'delay',
 'category': '家具',
 'attribute': '相',
 'attribute_icon': '/static/images/elements/相.png',
 'material_tags': ['mat_signal'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/仓鼠球.webp'}

ITEM['event_hooks'] = {GameEvent.MATERIAL_CONSUMED.value: delay_hamster_ball_material_bonus}
