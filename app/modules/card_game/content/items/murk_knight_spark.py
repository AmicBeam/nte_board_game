from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def murk_spark_relay(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    count = _count_harmony_mark(context.state, side, TAG_MURK)
    bonus = 2 if count else 0
    if bonus:
        _boost_card(card, bonus, card['name'])
    recovered = _recover_discard_item(
        context,
        lambda item: str(item.get('category') or '') == '材料' and int(item.get('cost') or 0) <= 2,
        card['name'],
    )
    _add_log(context.state, f"{card['name']} 读取 {count} 个浊燃，自身 +{bonus}，{'回收材料' if recovered else '未回收材料'}。")


ITEM = {'id': 'murk_knight_spark',
 'name': '上膛骑士火花塞',
 'cost': 3,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/上膛骑士火花塞.webp',
 'description': '揭示：若己方有浊燃，自身 +2；从墓地将 1 张费用 <=2 的材料道具返回手牌。',
 'effect_key': 'murk_spark_relay',
 'tags': ['murk', 'tool', 'material', 'mat_fire'],
 'archetype': 'murk',
 'category': '材料',
 'attribute': '咒',
 'attribute_icon': '/static/images/elements/咒.png',
 'material_tags': ['mat_fire'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/上膛骑士火花塞.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_spark_relay}
