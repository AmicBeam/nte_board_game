from typing import TYPE_CHECKING

from app.modules.card_game.content.effects import *
from app.modules.card_game.engine.events import GameEvent

if TYPE_CHECKING:
    from app.modules.card_game.engine.event_context import EventContext


def murk_material_box(context: 'EventContext') -> None:
    card = context.payload['card']
    fixed_names = {'失落絮语', '褪色掠影', '模糊数符', '悬想幻妄'}
    declared_ids = [str(card_id) for card_id in card.get('declared_card_instance_ids', [])]
    sent: JsonDict | None = None
    added: JsonDict | None = None
    if declared_ids:
        first_id = declared_ids[0]
        sent = _move_deck_item_to_discard(
            context,
            lambda item: str(item.get('instance_id') or '') == first_id and str(item.get('name') or '') in fixed_names,
            card['name'],
        )
    if len(declared_ids) >= 2:
        second_id = declared_ids[1]
        added = _declared_deck_item(
            context,
            lambda item: str(item.get('instance_id') or '') == second_id and str(item.get('name') or '') in fixed_names,
        )
        _add_card_to_hand(context, added, card['name'])
    if sent is None:
        sent = _move_deck_item_to_discard(context, lambda item: str(item.get('name') or '') in fixed_names, card['name'])
    if added is None:
        _add_card_to_hand(
            context,
            _tutor_deck_item(context, lambda item: str(item.get('name') or '') in fixed_names and item.get('name') != (sent or {}).get('name')),
            card['name'],
        )
    card.pop('declared_card_instance_ids', None)


ITEM = {'id': 'murk_basic_material_box',
 'name': '初级异象材料自选箱',
 'cost': 1,
 'power': 0,
 'type': 'anomaly_item',
 'element': '异象',
 'rarity': 'r',
 'art': '/static/images/item/初级异象材料自选箱.webp',
 'description': '宣言：选择 2 张不同名的「失落絮语」「褪色掠影」「模糊数符」或「悬想幻妄」。揭示：将第一次宣言的牌置入墓地，将第二次宣言的牌加入手牌。',
 'effect_key': 'murk_material_box',
 'tags': ['murk', 'tool', 'material', 'mat_dust'],
 'archetype': 'murk',
 'category': '耗材',
 'attribute': '暗',
 'attribute_icon': '/static/images/elements/暗.png',
 'material_tags': ['mat_dust'],
 'material_cost': None,
 'required_material_attribute': '',
 'material_requirements': [],
 'material_requirement_text': '',
 'target_rule': {},
 'declaration': {'steps': [{'kind': 'cards',
                            'zones': ['deck'],
                            'title': '初级异象材料自选箱 检视牌库',
                            'description': '先宣言 1 张送入墓地的固定材料，再宣言 1 张不同名的固定材料加入手牌。',
                            'pick_count': 2,
                            'min_count': 2,
                            'predicate': lambda item, context: (
                                item.get('type') == CARD_TYPE_ANOMALY_ITEM
                                and str(item.get('name') or '') in {'失落絮语', '褪色掠影', '模糊数符', '悬想幻妄'}
                            )}]},
 'icon': '/static/images/item/初级异象材料自选箱.webp'}

ITEM['event_hooks'] = {GameEvent.CARD_REVEALED.value: murk_material_box}
