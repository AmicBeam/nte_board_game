from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def genesis_nest_shard(context: 'EventContext') -> None:
    card = context.payload['card']
    target = _highest_ally(context) or card
    target['survive_non_positive_once'] = True
    if int(target.get('played_turn') or 0) == _current_turn(context):
        _boost_card(target, 1, card['name'])
    _add_log(context.state, f"{card['name']} 保护 {target['name']}，其第一次将被减为非正时保留 1 战力。")


ITEM = {'id': 'genesis_nest_shard',
 'name': '护巢残片',
 'cost': 3,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/护巢残片.webp',
 'description': '揭示：选择己方战力最高的 1 张道具，使其获得护盾，持续一回合；若该道具是本回合部署的道具，它额外 +1 战力。',
 'effect_key': 'genesis_nest_shard',
 'tags': ['genesis', 'tool', 'material', 'mat_relic'],
 'archetype': 'genesis',
 'category': '材料',
 'attribute': '灵',
 'attribute_icon': '/static/images/elements/灵.png',
 'material_tags': ['mat_relic'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/护巢残片.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: genesis_nest_shard}
