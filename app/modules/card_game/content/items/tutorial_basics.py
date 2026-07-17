from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def tutorial_refresh_charge(context: 'EventContext') -> None:
    card = context.payload['card']
    _boost_card(card, 1, card['name'])
    _add_log(context.state, f"{card['name']} 揭示后自身 +1。")


def tutorial_tutor_declared_item(context: 'EventContext') -> None:
    card = context.payload['card']
    definition_id = _definition_id(card)
    if definition_id == 'tutorial_urban_energy':
        expected_ids = {'tutorial_breakfast_bag'}
    elif definition_id == 'tutorial_breakfast_bag':
        expected_ids = {'tutorial_eborn_cake'}
    else:
        expected_ids = set()
    declared = _declared_deck_item(
        context,
        lambda item: (
            item.get('type') == CARD_TYPE_ANOMALY_ITEM
            and _definition_id(item) in expected_ids
        ),
    )
    if declared is None:
        _add_log(context.state, f"{card['name']} 的宣言牌已不合法。")
        card.pop('declared_card_instance_ids', None)
        return
    _add_card_to_hand(context, declared, card['name'])
    card.pop('declared_card_instance_ids', None)


def tutorial_water_hesitation(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent = str(context.payload['opponent_side'])
    selected = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if selected is not None and selected.get('side') == opponent and selected.get('type') == CARD_TYPE_ANOMALY_ITEM:
        target = selected
    else:
        target = _highest_opponent_item(context)
    if target is None:
        _add_log(context.state, f"{card['name']} 没有可影响的对手道具。")
        return
    _boost_card(target, -3, card['name'])
    _add_log(context.state, f"{card['name']} 使 {target['name']} -3。")


def tutorial_recruit_fear(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent = str(context.payload['opponent_side'])
    candidates = [
        item
        for item in _revealed_cards(context.payload['location'], opponent)
        if item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('attribute') or '') == '灵'
    ]
    if not candidates:
        _add_log(context.state, f"{card['name']} 没有找到可压制的灵属性道具。")
        return
    target = min(candidates, key=lambda item: (int(item.get('computed_power', _raw_card_power(item)) or 0), str(item.get('name') or '')))
    _boost_card(target, -2, card['name'])
    _add_log(context.state, f"{card['name']} 使 {target['name']} -2，拖慢薄荷的登场准备。")


def _tutorial_item(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    *,
    art_name: str | None = None,
    description: str = '教学专用道具。',
    effect_key: str = '',
    archetype: str = 'tutorial',
    category: str = '耗材',
    attribute: str = '',
    material_tags: list[str] | None = None,
    declaration: dict | None = None,
) -> JsonDict:
    material_tags = material_tags or []
    return {
        'id': card_id,
        'name': name,
        'cost': cost,
        'power': power,
        'type': CARD_TYPE_ANOMALY_ITEM,
        'element': '异象',
        'rarity': 'n',
        'art': f"/static/images/item/{art_name or name}.webp",
        'description': description,
        'effect_key': effect_key,
        'tags': ['tutorial', 'tool', 'material', *material_tags],
        'archetype': archetype,
        'category': category,
        'attribute': attribute,
        'attribute_icon': _element_icon(attribute),
        'material_tags': material_tags,
        'material_cost': None,
        'required_material_attribute': '',
        'material_requirements': [],
        'material_requirement_text': '',
        'target_rule': {},
        'declaration': declaration or {'steps': []},
        'icon': f"/static/images/item/{art_name or name}.webp",
        'deck_buildable': False,
    }


ITEM = [
    _tutorial_item(
        'tutorial_refresh_charge',
        '畅爽焕能',
        1,
        1,
        description='揭示：自身 +1。教学中用于掌握部署、揭示和稳定入场。',
        effect_key='tutorial_refresh_charge',
        attribute='灵',
        material_tags=[TAG_MAT_FONS],
    ),
    _tutorial_item(
        'tutorial_urban_energy',
        '都市活力',
        1,
        2,
        description='宣言：检视牌库，选择「速食早餐袋」。揭示：将宣言牌加入手牌。',
        effect_key='tutorial_tutor_declared_item',
        attribute='光',
        material_tags=[TAG_MAT_COIN],
        declaration={'steps': [{
            'kind': 'cards',
            'zones': ['deck'],
            'title': '都市活力 检视牌库',
            'description': '宣言「速食早餐袋」；揭示时加入手牌。',
            'predicate': lambda item, context: _definition_id(item) == 'tutorial_breakfast_bag',
        }]},
    ),
    _tutorial_item(
        'tutorial_water_hesitation',
        '水波的迟疑',
        2,
        2,
        description='宣言：选择 1 张对手表侧道具。揭示：宣言道具 -3。',
        effect_key='tutorial_water_hesitation',
        category='材料',
        attribute='相',
        material_tags=[TAG_MAT_DEVICE],
        declaration={'steps': [{
            'kind': 'board',
            'scope': 'opponent_same_location',
            'prompt': '选择 1 张对手表侧道具。',
            'predicate': lambda item, context: item.get('type') == CARD_TYPE_ANOMALY_ITEM,
        }]},
    ),
    _tutorial_item(
        'tutorial_breakfast_bag',
        '速食早餐袋',
        1,
        2,
        description='宣言：检视牌库，选择「来自「伊波恩」的蛋糕」。揭示：将宣言牌加入手牌。',
        effect_key='tutorial_tutor_declared_item',
        attribute='灵',
        material_tags=[TAG_MAT_FONS],
        declaration={'steps': [{
            'kind': 'cards',
            'zones': ['deck'],
            'title': '速食早餐袋 检视牌库',
            'description': '宣言「来自「伊波恩」的蛋糕」；揭示时加入手牌。',
            'predicate': lambda item, context: _definition_id(item) == 'tutorial_eborn_cake',
        }]},
    ),
    _tutorial_item(
        'tutorial_fons',
        '方斯',
        0,
        1,
        description='无揭示效果。教学中作为光属性共鸣素材。',
        category='货币',
        attribute='光',
        material_tags=[TAG_MAT_COIN],
    ),
    _tutorial_item(
        'tutorial_eborn_cake',
        '来自「伊波恩」的蛋糕',
        3,
        4,
        description='无揭示效果。教学中作为灵属性共鸣素材。',
        category='食物',
        attribute='灵',
        material_tags=[TAG_MAT_ARCHIVE],
    ),
    _tutorial_item(
        'tutorial_lost_wallet',
        '遗失的钱包',
        1,
        1,
        description='无揭示效果。教学中作为薄荷登场素材。',
        category='重要',
        attribute='灵',
        material_tags=[TAG_MAT_ARCHIVE],
    ),
    _tutorial_item(
        'tutorial_marble_soda',
        '彩色波子汽水',
        2,
        3,
        description='无揭示效果。教学中作为第 6 回合的备用手牌。',
        category='食物',
        attribute='光',
        material_tags=[TAG_MAT_COIN],
    ),
    _tutorial_item(
        'tutorial_tomato_dummy',
        '西红柿',
        1,
        1,
        description='教学对手道具：用于演示选择目标和解场。',
        archetype='tutorial_opponent',
        category='材料',
        attribute='相',
        material_tags=[TAG_MAT_SIGNAL],
    ),
    _tutorial_item(
        'tutorial_recruit_fear',
        '新兵的怯懦',
        1,
        1,
        description='揭示：对方当前战力最低的灵属性表侧道具 -2。',
        effect_key='tutorial_recruit_fear',
        archetype='tutorial_opponent',
        art_name='新兵的怯懦',
        category='材料',
        attribute='相',
        material_tags=[TAG_MAT_SIGNAL],
    ),
]

for _item in ITEM:
    if _item['id'] == 'tutorial_refresh_charge':
        _item['event_hooks'] = {GameEvent.CARD_REVEALED.value: tutorial_refresh_charge}
    elif _item['id'] in {'tutorial_urban_energy', 'tutorial_breakfast_bag'}:
        _item['event_hooks'] = {GameEvent.CARD_REVEALED.value: tutorial_tutor_declared_item}
    elif _item['id'] == 'tutorial_water_hesitation':
        _item['event_hooks'] = {GameEvent.CARD_REVEALED.value: tutorial_water_hesitation}
    elif _item['id'] == 'tutorial_recruit_fear':
        _item['event_hooks'] = {GameEvent.CARD_REVEALED.value: tutorial_recruit_fear}
