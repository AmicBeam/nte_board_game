from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def tutorial_appraiser_resonance(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    card = context.payload['card']
    created = _create_tokens_at_location(context, 'harmony_genesis', side=side, count=1)
    if created:
        _add_combo_counter(context.state, side, 'genesis_created', created)
    _add_log(context.state, f"{card['name']} 设置环合：创生 {created} 层。")


def tutorial_bohe_genesis_bloom(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    location = context.payload['location']
    card = context.payload['card']
    consumed = _consume_location_mark(location, side, TAG_GENESIS, 2)
    if consumed <= 0:
        _add_log(context.state, f"{card['name']} 没有可消耗的创生。")
        return
    _boost_card(card, consumed * 3, card['name'])
    _add_log(context.state, f"{card['name']} 消耗 {consumed} 层创生，自身 +{consumed * 3}。")


def _tutorial_esper(
    card_id: str,
    name: str,
    power: int,
    *,
    attribute: str,
    description: str,
    effect_key: str,
    material_requirements: list[JsonDict],
    material_requirement_text: str = '',
    art_name: str | None = None,
) -> JsonDict:
    art = f"/static/images/characters/portrait/{art_name or name}.webp"
    avatar = f"/static/images/characters/avatar/{art_name or name}.webp"
    return {
        'id': card_id,
        'name': name,
        'cost': 0,
        'power': power,
        'type': CARD_TYPE_ESPER,
        'element': attribute,
        'rarity': 'r',
        'art': art,
        'description': description,
        'effect_key': effect_key,
        'tags': ['tutorial', 'esper', 'genesis'],
        'archetype': 'tutorial',
        'category': '',
        'attribute': attribute,
        'attribute_icon': _element_icon(attribute),
        'material_tags': [],
        'material_cost': sum(int(requirement.get('count') or 1) for requirement in material_requirements),
        'required_material_attribute': '',
        'material_requirements': material_requirements,
        'material_requirement_text': material_requirement_text,
        'target_rule': {},
        'portrait_image': art,
        'avatar_image': avatar,
        'deck_buildable': False,
    }


CHARACTER = [
    _tutorial_esper(
        'tutorial_appraiser',
        '鉴定师',
        5,
        attribute='光',
        description='共鸣：设置环合：创生 1 层。',
        effect_key='tutorial_appraiser_resonance',
        material_requirements=[{'attribute': '光', 'count': 1}, {'attribute': '灵', 'count': 1}],
        material_requirement_text='光属性素材*1+灵属性素材*1',
    ),
    _tutorial_esper(
        'tutorial_bohe',
        '薄荷',
        2,
        attribute='灵',
        description='共鸣：消耗至多 2 层创生；每消耗 1 层，自身 +3。',
        effect_key='tutorial_bohe_genesis_bloom',
        material_requirements=[{'attribute': '灵', 'count': 1}],
        material_requirement_text='灵属性素材*1',
    ),
]

for _character in CHARACTER:
    if _character['id'] == 'tutorial_appraiser':
        _character['event_hooks'] = {GameEvent.CARD_REVEALED.value: tutorial_appraiser_resonance}
    elif _character['id'] == 'tutorial_bohe':
        _character['event_hooks'] = {GameEvent.CARD_REVEALED.value: tutorial_bohe_genesis_bloom}
