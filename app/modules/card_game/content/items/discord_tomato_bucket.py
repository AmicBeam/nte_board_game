from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def discord_control(context: 'EventContext') -> None:
    card = context.payload['card']
    side_state = context.state['sides'][str(context.payload['side'])]
    if not side_state.get('deck'):
        _add_log(context.state, f"{card['name']} 没有可翻开的牌库顶牌。")
        return
    revealed_names: list[str] = []
    for _ in range(3):
        if not side_state.get('deck'):
            break
        top_card = side_state['deck'].pop(0)
        revealed_names.append(str(top_card.get('name') or '卡牌'))
        if str(top_card.get('name') or '') in {'西红柿', '番茄百分百'}:
            if _deploy_card_to_current_location(context, top_card, card['name']):
                _add_log(context.state, f"{card['name']} 翻到 {top_card['name']}，改为将其部署。")
            continue
        _move_popped_deck_item_to_discard(context, top_card, card['name'])
    _add_log(context.state, f"{card['name']} 翻开牌库顶 {len(revealed_names)} 张：{'、'.join(revealed_names)}。")


ITEM = {'id': 'discord_tomato_bucket',
 'name': '番茄全家桶',
 'cost': 4,
 'power': 4,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/番茄全家桶.webp',
 'description': '揭示：将牌库顶的 3 张卡牌置入墓地，并将其中的「西红柿」或「番茄百分百」改为部署到战场。',
 'effect_key': 'discord_control',
 'tags': ['discord', 'tool', 'material', 'mat_dust'],
 'archetype': 'discord',
 'category': '礼物',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'ai_material_reserved_for': ['requiem'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'icon': '/static/images/item/番茄全家桶.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: discord_control}
