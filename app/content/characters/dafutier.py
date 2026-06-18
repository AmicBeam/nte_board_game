from typing import TYPE_CHECKING

from app.content.effects import *
from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext


def dafutier_discord_link(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    max_repeats = _count_harmony_mark(context.state, side, TAG_DARKSTAR) + _count_harmony_mark(context.state, side, TAG_MURK)
    pulses = 1
    destroyed = _damage_all_enemies(context, 2, source_name=context.payload['card']['name'])
    repeats = 0
    while destroyed and repeats < max_repeats:
        repeats += 1
        pulses += 1
        destroyed = _damage_all_enemies(context, 2, source_name=context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 对所有敌方单位造成 2 点伤害，共结算 {pulses} 次。")


CHARACTER = {'id': 'dafutier',
 'name': '达芙蒂尔',
 'cost': 0,
 'power': 5,
 'type': 'esper',
 'element': '暗',
 'rarity': 'sr',
 'art': '/static/images/characters/portrait/达芙蒂尔.webp',
 'description': '共鸣：对所有敌方单位造成 2 点伤害；若有敌方单位因此破碎，则再重复，最多重复 X 次，X 为己方黯星与浊燃层数之和。持续效果：当己方失谐标记层数提升时，对所有敌方单位造成 2 点伤害。',
 'effect_key': 'dafutier_discord_link',
 'tags': ['esper', 'darkstar', 'discord'],
 'archetype': '',
 'category': '',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': [],
 'material_cost': 3,
 'required_material_attribute': '暗',
 'material_requirements': [{'attribute': '暗', 'count': 2}, {}],
 'material_requirement_text': '',
 'target_rule': {},
 'portrait_image': '/static/images/characters/portrait/达芙蒂尔.webp',
 'avatar_image': '/static/images/characters/avatar/达芙蒂尔.webp'}

CHARACTER['event_hooks'] = {GameEvent.CARD_REVEALED.value: dafutier_discord_link}
