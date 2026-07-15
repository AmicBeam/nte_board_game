from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def darkstar_denoise_base(context: 'EventContext') -> None:
    card = context.payload['card']
    deployed = _deploy_discard_definition_to_current_location(context, 'darkstar_nature_pixel', card['name'])
    if deployed is not None:
        _add_log(context.state, f"{card['name']} 从墓地部署本性像素。")


ITEM = {'id': 'darkstar_denoise_base',
 'name': '去噪底液',
 'cost': 2,
 'power': 3,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/去噪底液.webp',
 'description': '揭示：从墓地部署 1 张「本性像素」。',
 'effect_key': 'darkstar_denoise_base',
 'tags': ['darkstar', 'tool', 'material', 'mat_dust'],
 'archetype': 'darkstar',
 'category': '耗材',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/去噪底液.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: darkstar_denoise_base}
