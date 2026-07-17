from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def genesis_nest_shard(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    turn = int(context.state.get('turn') or 0)
    has_other_revealed = any(
        other.get('instance_id') != card.get('instance_id')
        and other.get('revealed')
        and int(other.get('played_turn') or 0) == turn
        for other in context.payload['location'].get('cards', {}).get(side, [])
    )
    if not has_other_revealed:
        _add_log(context.state, f"{card['name']} 本回合没有其他己方已揭示卡牌，未生成「方斯」。")
        return
    added = _add_generated_card_to_hand(context, 'surplus_fons')
    if added:
        _add_log(context.state, f"{card['name']} 将 1 张「方斯」加入手牌。")
    else:
        _add_log(context.state, f"{card['name']} 想生成「方斯」，但手牌已满。")


ITEM = {'id': 'genesis_nest_shard',
 'name': '遗失的钱包',
 'cost': 2,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/遗失的钱包.webp',
 'description': '揭示：若本回合已揭示过其他己方卡牌，则将 1 张「方斯」加入手牌。',
 'effect_key': 'genesis_nest_shard',
 'tags': ['genesis', 'tool', 'material', 'mat_relic'],
 'archetype': 'genesis',
 'category': '耗材',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_relic'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/遗失的钱包.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_nest_shard}
