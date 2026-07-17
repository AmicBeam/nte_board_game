from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def haniya_darkstar_support(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    if card.get('haniya_darkstar_support_used'):
        _add_log(context.state, f"{card['name']} 已经触发过黯星支援。")
        return
    bonus = min(4, _count_harmony_mark(context.state, side, TAG_DARKSTAR))
    if bonus <= 0:
        _add_log(context.state, f"{card['name']} 检查己方没有黯星，未获得加成。")
        return
    boosted = _boost_allied_espers(context, bonus)
    if boosted:
        card['haniya_darkstar_support_used'] = True
    _add_log(context.state, f"{card['name']} 依据黯星层数，使 {boosted} 名己方异能者 +{bonus}。")


CHARACTER = {'id': 'haniya',
 'name': '哈尼娅',
 'cost': 0,
 'power': 3,
 'type': 'esper',
 'element': '魂',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/哈尼娅.webp',
 'description': '共鸣：【限1次】依据己方黯星层数，使全部己方异能者 +X，X 至多为 4。',
 'effect_key': 'haniya_darkstar_support',
 'tags': ['esper', 'darkstar'],
 'archetype': '',
 'category': '',
 'attribute': '魂',
 'attribute_icon': '/static/images/elements/魂.png',
 'material_tags': [],
 'material_cost': 1,
 'required_material_attribute': '魂',
 'material_requirements': [{'attribute': '魂', 'count': 1}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/哈尼娅.webp',
 'avatar_image': '/static/images/characters/avatar/哈尼娅.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: haniya_darkstar_support}
