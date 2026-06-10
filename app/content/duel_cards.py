from __future__ import annotations

import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from app.engine.events import GameEvent

if TYPE_CHECKING:
    from app.engine.event_context import EventContext

JsonDict = dict[str, Any]

LOG_LIMIT = 28
MAX_HAND_SIZE = 10
MIN_DECK_SIZE = 10
MAX_DECK_SIZE = 20
MAX_ESPER_CARDS_PER_DECK = 4
LOCATION_CARD_LIMIT = 4

CARD_TYPE_ESPER = 'esper'
CARD_TYPE_ANOMALY_ITEM = 'anomaly_item'
CARD_TYPE_TOKEN = 'token'

CARD_BACK_IMAGE = '/static/images/cards/card-back.svg'
LUMINOUS_TOOL_ART = '/static/images/cards/luminous-tool.svg'
ARCHIVE_TOOL_ART = '/static/images/cards/archive-tool.svg'
CURSE_TOOL_ART = '/static/images/cards/curse-tool.svg'
TIDE_TOOL_ART = '/static/images/cards/tide-tool.svg'
GENERATED_CARD_ART_BASE = '/static/images/cards/generated'
ITEM_IMAGE_BASE = '/static/images/item'
ELEMENT_ICON_BASE = '/static/images/elements'

ART_NANALI = '/static/images/characters/portrait/娜娜莉.png'
ART_XUN = '/static/images/characters/portrait/浔.png'
ART_JIUYUAN = '/static/images/characters/portrait/九原.png'
ART_BOHE = '/static/images/characters/portrait/薄荷.png'
ART_PROTAGONIST = '/static/images/characters/portrait/鉴定师.png'
ART_XIAOZHI = '/static/images/characters/portrait/小吱.png'
ART_EDGAR = '/static/images/characters/portrait/埃德嘉.png'
ART_BAICANG = '/static/images/characters/portrait/白藏.png'
ART_ADLER = '/static/images/characters/portrait/阿德勒.png'
ART_ZAOWU = '/static/images/characters/portrait/早雾.png'
ART_DAFUTIER = '/static/images/characters/portrait/达芙蒂尔.png'
ART_HAIYUE = '/static/images/characters/portrait/海月.png'
ART_FATIYA = '/static/images/characters/portrait/法帝娅.png'
ART_HANIYA = '/static/images/characters/portrait/哈尼娅.png'
ART_HASUOER = '/static/images/characters/portrait/哈索尔.png'
ART_YI = '/static/images/characters/portrait/翳.png'

TAG_GENESIS = 'genesis'
TAG_MURK = 'murk'
TAG_DELAY = 'delay'
TAG_DARKSTAR = 'darkstar'
TAG_SURPLUS = 'surplus'
TAG_DISCORD = 'discord'
TAG_COLLAPSING = 'collapsing'
TAG_MATERIAL = 'material'
TAG_HARMONY = 'harmony'
TAG_MAT_FONS = 'mat_fons'
TAG_MAT_COIN = 'mat_coin'
TAG_MAT_ARCHIVE = 'mat_archive'
TAG_MAT_DEVICE = 'mat_device'
TAG_MAT_FIRE = 'mat_fire'
TAG_MAT_DUST = 'mat_dust'
TAG_MAT_ORACLE = 'mat_oracle'
TAG_MAT_RELIC = 'mat_relic'
TAG_MAT_SIGNAL = 'mat_signal'

MATERIAL_TAG_ATTRIBUTES = {
    TAG_MAT_FONS: '灵',
    TAG_MAT_COIN: '光',
    TAG_MAT_ARCHIVE: '灵',
    TAG_MAT_DEVICE: '相',
    TAG_MAT_FIRE: '咒',
    TAG_MAT_DUST: '暗',
    TAG_MAT_ORACLE: '魂',
    TAG_MAT_RELIC: '魂',
    TAG_MAT_SIGNAL: '相',
}

LOCATION_MARK_TOKENS = {
    'harmony_genesis': TAG_GENESIS,
    'harmony_murk': TAG_MURK,
    'harmony_delay': TAG_DELAY,
    'harmony_darkstar': TAG_DARKSTAR,
    'harmony_surplus': TAG_SURPLUS,
    'discordance': TAG_DISCORD,
    'collapsing_card': TAG_COLLAPSING,
}

LOCATION_MARK_NAMES = {
    TAG_GENESIS: '创生',
    TAG_MURK: '浊燃',
    TAG_DELAY: '延滞',
    TAG_DARKSTAR: '黯星',
    TAG_SURPLUS: '盈蓄',
    TAG_DISCORD: '失谐',
    TAG_COLLAPSING: '倾陷',
}


def _card_art(card_id: str) -> str:
    return f'{GENERATED_CARD_ART_BASE}/{card_id}.svg'


def _item_art(filename: str) -> str:
    return f'{ITEM_IMAGE_BASE}/{filename}'


def _element_icon(attribute: str) -> str:
    return f'{ELEMENT_ICON_BASE}/{attribute}.png' if attribute else ''


ITEM_ART_FILES = {
    '都市活力',
    '畅爽焕能',
    '速食早餐袋',
    '彩色波子汽水',
    '来自「伊波恩」的蛋糕',
    '吃薯片专用洗指机',
    '护巢残片',
    '暴走棉绒绒-肌肉信仰',
    '初次的期许',
    '思维的同频',
    '水波的迟疑',
    '新兵的怯懦',
    '雏鸟的希冀',
    '通勤公文包',
    '无人来电',
    '万花筒',
    '失落絮语',
    '褪色掠影',
    '模糊数符',
    '悬想幻妄',
    '上膛骑士火花塞',
    '妄想彼端的一页',
    '斑斓的票根',
    '初级异象材料自选箱',
    '「异晶开采凭证」',
    '环石',
    '本性像素',
    '去噪底液',
    '谕石',
    '聆谕水晶',
    '织梦结',
    '何人的头盔',
    '方斯',
    '甲硬币',
    '嗯硬币',
    '无名刃',
    '西红柿',
    '番茄百分百',
    '番茄全家桶',
}


def _known_item_art(name: str, fallback: str) -> str:
    return _item_art(f'{name}.webp') if name in ITEM_ART_FILES else fallback


def card_revealed(context: 'EventContext') -> None:
    card = context.payload['card']
    definition = _definition_by_id(str(card.get('definition_id', '')))
    effect_key = str(definition.get('effect_key') or '')
    handler = CARD_EFFECTS.get(effect_key)
    if handler is not None:
        handler(context)


def nanali_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_FONS, TAG_MAT_COIN, TAG_MAT_ORACLE])
    created = _create_tokens_at_location(context, 'harmony_genesis', count=min(2, material))
    if created > 0:
        _add_combo_counter(context.state, str(context.payload['side']), 'genesis_created', 1)
        _add_log(context.state, f"{context.payload['card']['name']} 读取 {material} 个灵/光属性素材，生成 {created} 个创生。")
    if created >= 2 or _count_location_tag(context.payload['location'], side, TAG_GENESIS) > 0:
        added = _add_token_to_hand(context, 'surplus_charge')
        if added:
            _add_log(context.state, f"{context.payload['card']['name']} 借创生回流，将 1 张盈蓄加入手牌。")
    if created <= 0:
        _add_log(context.state, f"{context.payload['card']['name']} 没有读到可创生素材。")


def xun_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    local_material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_FONS, TAG_MAT_ORACLE, TAG_MAT_RELIC])
    created = _create_tokens_at_location(context, 'harmony_genesis', count=min(1, local_material))
    count = _count_board_tag(context.state, side, TAG_GENESIS)
    material_count = _count_board_any_tag(context.state, side, [TAG_MAT_FONS, TAG_MAT_ORACLE, TAG_MAT_RELIC])
    bonus = min(8, max(1, count + material_count // 2))
    _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    if count >= 2 or material_count >= 3:
        _add_token_to_hand(context, 'surplus_charge')
    if created:
        _add_combo_counter(context.state, side, 'genesis_created', 1)
    _add_log(context.state, f"{context.payload['card']['name']} 串联 {count} 个创生与 {material_count} 个素材，自身 +{bonus} 战力。")


def jiuyuan_genesis(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    count = _count_board_any_tag(context.state, side, [TAG_MAT_ARCHIVE, TAG_MAT_FONS, TAG_MAT_COIN])
    added = _add_token_to_hand(context, 'surplus_charge', count=min(2, count))
    target = _lowest_ally(context)
    if target is not None and count:
        _boost_card(target, min(3, count), context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 清点档案/货币素材，将 {added} 张盈蓄加入手牌。")


def bohe_genesis_support(context: 'EventContext') -> None:
    card = context.payload['card']
    side = str(context.payload['side'])
    selected_target = context.payload.get('target_card')
    allies = [
        current_card
        for current_card in _revealed_cards(context.payload['location'], side)
        if current_card['instance_id'] != card['instance_id']
    ]
    if isinstance(selected_target, dict) and selected_target.get('side') == side:
        target = selected_target
    elif allies:
        target = min(allies, key=_raw_card_power)
    else:
        target = card
    has_support_material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_ARCHIVE, TAG_MAT_DEVICE, TAG_GENESIS]) > 0
    bonus = 2 + (2 if has_support_material else 0)
    _boost_card(target, bonus, card['name'])
    _add_log(context.state, f"{card['name']} 读取档案/器物素材稳定 {target['name']}，使其 +{bonus} 战力。")


def protagonist_harmony_copy(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    card = context.payload['card']
    attributes = set(str(attribute) for attribute in card.get('consumed_material_attributes', []) if str(attribute))
    created_genesis = 0
    created_delay = 0
    if '灵' in attributes:
        created_genesis = _create_tokens_at_location(context, 'harmony_genesis', side=side, count=1)
        if created_genesis:
            _add_combo_counter(context.state, side, 'genesis_created', 1)
    if '相' in attributes:
        created_delay = _create_tokens_at_location(context, 'harmony_delay', side=opponent, count=1)
    total = created_genesis + created_delay
    if total:
        _boost_card(card, total, card['name'])
    if created_genesis and _count_board_tag(context.state, opponent, TAG_DELAY):
        _add_token_to_hand(context, 'surplus_charge')
    _add_log(context.state, f"{card['name']} 按素材设置 {created_genesis} 个创生与 {created_delay} 个延滞，自身 +{total}。")


def xiaozhi_surplus_link(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    surplus = int(context.state['sides'][side].setdefault('combo', {}).get('surplus_revealed', 0))
    hand_surplus = _count_hand_tag(context.state, side, TAG_SURPLUS)
    fons = _count_location_tag(context.payload['location'], side, TAG_MAT_FONS) + _count_hand_tag(context.state, side, TAG_MAT_FONS)
    added = _add_token_to_hand(context, 'surplus_charge', count=min(2, fons))
    bonus = min(5, surplus + hand_surplus + fons)
    if bonus:
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    if surplus > 0 or added > 0:
        _create_token_at_location(context, 'harmony_genesis')
    _add_log(context.state, f"{context.payload['card']['name']} 将 {fons} 个灵属性素材结算为 {added} 张盈蓄，自身 +{bonus} 战力。")


def edgar_surplus_link(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    surplus = int(context.state['sides'][side].setdefault('combo', {}).get('surplus_revealed', 0))
    coins = _count_board_any_tag(context.state, side, [TAG_MAT_COIN, TAG_MAT_FONS])
    if surplus or coins:
        _boost_card(context.payload['card'], min(5, surplus * 2 + coins), context.payload['card']['name'])
    if coins:
        _add_token_to_hand(context, 'surplus_charge', count=min(1, coins))
    drawn = _draw_one_from_deck(context.state, side)
    if drawn is not None:
        _add_log(context.state, f"{context.payload['card']['name']} 借货币/盈蓄链路补入 {drawn['name']}。")
    else:
        _add_token_to_hand(context, 'surplus_charge')
        _add_log(context.state, f"{context.payload['card']['name']} 没有可抽牌，改为补入 1 张盈蓄。")


def adler_murk_pressure(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_FIRE, TAG_MAT_DUST, TAG_MAT_DEVICE])
    created = _create_tokens_at_location(context, 'harmony_murk', side=str(context.payload['opponent_side']), count=max(1, min(2, material)))
    tempo_bonus = min(4, max(0, material))
    if tempo_bonus:
        _boost_card(context.payload['card'], tempo_bonus, context.payload['card']['name'])
        context.payload['card']['survive_non_positive_once'] = True
    cleared_darkstar = _consume_location_mark(context.payload['location'], side, TAG_DARKSTAR, 1)
    if cleared_darkstar:
        _boost_card(context.payload['card'], 2, context.payload['card']['name'])
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -1 - min(1, material), context.payload['card']['name'])
        extra = '，并烧穿 1 个黯星' if cleared_darkstar else ''
        _add_log(context.state, f"{context.payload['card']['name']} 读取火种/失序素材，自身 +{tempo_bonus}，生成 {created} 个浊燃并压低 {target['name']}{extra}。")
    else:
        extra = '，并烧穿 1 个黯星' if cleared_darkstar else ''
        _add_log(context.state, f"{context.payload['card']['name']} 读取素材，自身 +{tempo_bonus}，在对手区域生成 {created} 个浊燃{extra}。")


def zaowu_murk_spread(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    index = int(context.payload.get('location_index', -1))
    material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_FIRE, TAG_MAT_SIGNAL])
    spread = 0
    adjacent_locations = _adjacent_locations(context.state, index)
    if not adjacent_locations:
        spread = _create_tokens_at_location(
            context,
            'harmony_murk',
            side=opponent,
            count=max(1, min(2, material)),
        )
    else:
        for location in adjacent_locations:
            if material <= 0:
                break
            if _create_token_in_location(context.state, location, opponent, 'harmony_murk'):
                spread += 1
                material -= 1
    if spread:
        _boost_card(context.payload['card'], spread, context.payload['card']['name'])
    target_text = '主战场' if not adjacent_locations else f'{spread} 个相邻区域'
    _add_log(context.state, f"{context.payload['card']['name']} 借火种/信号素材将浊燃压入{target_text}。")


def dafutier_discord_link(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    material_count = _count_board_any_tag(context.state, side, [TAG_MAT_DUST, TAG_MAT_SIGNAL, TAG_MAT_DEVICE])
    if material_count:
        _create_tokens_at_location(context, 'discordance', side=opponent, count=min(2, material_count))
    reaction_count = (
        material_count
        +
        _count_board_tag(context.state, side, TAG_DISCORD)
        + _count_board_tag(context.state, opponent, TAG_DISCORD)
        + _count_board_tag(context.state, opponent, TAG_MURK)
        + _count_board_tag(context.state, opponent, TAG_DARKSTAR)
    )
    bonus = min(6, reaction_count)
    if bonus:
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    if reaction_count:
        _add_token_to_hand(context, 'surplus_charge')
    _add_log(context.state, f"{context.payload['card']['name']} 收束失谐与负面素材，自身 +{bonus} 战力。")


def requiem_murk_finish(context: 'EventContext') -> None:
    opponent = str(context.payload['opponent_side'])
    murks = _count_board_tag(context.state, opponent, TAG_MURK) + _count_board_tag(context.state, opponent, TAG_DISCORD)
    bonus = min(10, murks * 2)
    if bonus:
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    debuffed = _boost_location_cards(context.payload['location'], opponent, -2, context.payload['card']['name'], ignore_tokens=True)
    _add_log(context.state, f"{context.payload['card']['name']} 根据 {murks} 个浊燃/失谐自身 +{bonus}，并削弱此区域 {debuffed} 张对手牌。")


def baicang_murk_finish(context: 'EventContext') -> None:
    opponent = str(context.payload['opponent_side'])
    local_pressure = (
        _count_location_tag(context.payload['location'], opponent, TAG_MURK)
        + _count_location_tag(context.payload['location'], opponent, TAG_DISCORD)
        + _count_location_tag(context.payload['location'], opponent, TAG_DARKSTAR)
    )
    all_pressure = local_pressure + _count_board_tag(context.state, opponent, TAG_MURK) + _count_board_tag(context.state, opponent, TAG_DISCORD)
    if local_pressure >= 2:
        bonus = min(14, all_pressure * 2)
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
        _boost_location_cards(context.payload['location'], opponent, -3, context.payload['card']['name'], ignore_tokens=True)
        _add_log(context.state, f"{context.payload['card']['name']} 在高压区域展开，自身 +{bonus} 并重压对手。")
    else:
        _add_log(context.state, f"{context.payload['card']['name']} 条件未完全成型，只以基础战力站场。")


def fatiya_darkstar_seed(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_ORACLE, TAG_MAT_RELIC, TAG_MAT_DUST])
    created = _create_tokens_at_location(context, 'harmony_darkstar', side=str(context.payload['opponent_side']), count=max(1, min(2, material)))
    if created > 0 and material >= 2:
        _add_token_to_hand(context, 'surplus_charge')
    _add_log(context.state, f"{context.payload['card']['name']} 读取 {material} 个魂属性素材，在对手侧设置 {created} 个黯星。")


def haniya_darkstar_support(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    index = int(context.payload.get('location_index', -1))
    material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_RELIC, TAG_MAT_ORACLE, TAG_MAT_ARCHIVE])
    created = 0
    target_locations = [context.payload['location'], *_adjacent_locations(context.state, index)]
    if len(target_locations) == 1:
        created = _create_tokens_at_location(
            context,
            'harmony_darkstar',
            side=opponent,
            count=max(1, min(2, material)),
        )
    else:
        for location in target_locations:
            if material <= 0:
                break
            if _create_token_in_location(context.state, location, opponent, 'harmony_darkstar'):
                created += 1
                material -= 1
            if created >= 2:
                break
    if created:
        _boost_card(context.payload['card'], created, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 将 {created} 个属性素材布置为黯星标记。")


def haiyue_darkstar_finish(context: 'EventContext') -> None:
    opponent = str(context.payload['opponent_side'])
    darkstars = _count_board_tag(context.state, opponent, TAG_DARKSTAR)
    bonus = min(10, darkstars * 2)
    if bonus:
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    debuffed = _boost_location_cards(context.payload['location'], opponent, -1 - min(2, darkstars), context.payload['card']['name'], ignore_tokens=True)
    _add_log(context.state, f"{context.payload['card']['name']} 借 {darkstars} 个黯星抢节奏，自身 +{bonus}，压低 {debuffed} 张牌。")


def hasuoer_delay_tax(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_DEVICE, TAG_MAT_ARCHIVE, TAG_MAT_SIGNAL])
    created = _create_tokens_at_location(context, 'harmony_delay', side=str(context.payload['opponent_side']), count=max(1, min(2, material)))
    if created > 0:
        _boost_card(context.payload['card'], 1, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 将 {material} 个相属性素材设置为 {created} 个延滞。")


def yi_delay_support(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    index = int(context.payload.get('location_index', -1))
    material = _count_location_any_tag(context.payload['location'], side, [TAG_MAT_SIGNAL, TAG_MAT_ARCHIVE, TAG_MAT_DEVICE])
    created = 0
    adjacent_locations = _adjacent_locations(context.state, index)
    if not adjacent_locations:
        created = _create_tokens_at_location(
            context,
            'harmony_delay',
            side=opponent,
            count=max(1, min(2, material)),
        )
    else:
        for location in adjacent_locations:
            if material <= 0:
                break
            if _create_token_in_location(context.state, location, opponent, 'harmony_delay'):
                created += 1
                break
    target = _lowest_ally(context)
    if target is not None:
        _boost_card(target, 2 + created, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 借相属性素材扩展延滞，并保护己方低战力牌。")


def chaos_delay_finish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    consumed = int(context.state['sides'][side].setdefault('combo', {}).get('delay_consumed_by_opponent', 0))
    active_delays = _count_board_tag(context.state, opponent, TAG_DELAY)
    chaos_material = _count_board_any_tag(context.state, side, [TAG_MAT_DUST, TAG_MAT_SIGNAL, TAG_MAT_RELIC])
    bonus = min(14, consumed * 3 + active_delays * 2 + chaos_material)
    if bonus:
        _boost_card(context.payload['card'], bonus, context.payload['card']['name'])
    created = 0
    for location in context.state.get('locations', []):
        if _create_token_in_location(context.state, location, opponent, 'harmony_delay'):
            created += 1
    _add_log(context.state, f"{context.payload['card']['name']} 统计 {consumed} 次延滞触发与 {chaos_material} 个失序素材，自身 +{bonus}，并追加 {created} 个延滞。")


def material_fons_field(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    opponent = str(context.payload['opponent_side'])
    _boost_card(context.payload['card'], 1, context.payload['card']['name'])
    support_text = ''
    if int(context.payload['location']['power'][side]) <= int(context.payload['location']['power'][opponent]):
        target = _lowest_ally(context) or context.payload['card']
        _boost_card(target, 1, context.payload['card']['name'])
        support_text = f"，并使 {target['name']} +1"
    _add_log(context.state, f"{context.payload['card']['name']} 自身 +1{support_text}。")


def material_fons_hand(context: 'EventContext') -> None:
    target = _lowest_ally(context) or context.payload['card']
    _boost_card(target, 2, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 稳住节奏，使 {target['name']} +2 战力。")


def material_coin_field(context: 'EventContext') -> None:
    _boost_card(context.payload['card'], 1, context.payload['card']['name'])
    drawn = _draw_one_from_deck(context.state, str(context.payload['side']))
    suffix = f"，并补入 {drawn['name']}。" if drawn is not None else '。'
    _add_log(context.state, f"{context.payload['card']['name']} 自身 +1{suffix}")


def material_archive_field(context: 'EventContext') -> None:
    drawn = _draw_one_from_deck(context.state, str(context.payload['side']))
    target = _lowest_ally(context) or context.payload['card']
    _boost_card(target, 1, context.payload['card']['name'])
    suffix = f"，并补入 {drawn['name']}。" if drawn is not None else '。'
    _add_log(context.state, f"{context.payload['card']['name']} 使 {target['name']} +1 战力{suffix}")


def material_device_field(context: 'EventContext') -> None:
    target = _lowest_ally(context) or context.payload['card']
    _boost_card(target, 2, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 稳定阵线，使 {target['name']} +2 战力。")


def material_fire_field(context: 'EventContext') -> None:
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -2, context.payload['card']['name'])
        _add_log(context.state, f"{context.payload['card']['name']} 压低 {target['name']} 2 点战力。")
    else:
        _add_log(context.state, f"{context.payload['card']['name']} 没有可压低的对手牌。")


def material_dust_field(context: 'EventContext') -> None:
    opponent = str(context.payload['opponent_side'])
    debuffed = _boost_location_cards(context.payload['location'], opponent, -1, context.payload['card']['name'], ignore_tokens=True)
    _add_log(context.state, f"{context.payload['card']['name']} 削弱此区域 {debuffed} 张对手牌。")


def material_oracle_field(context: 'EventContext') -> None:
    _boost_card(context.payload['card'], 1, context.payload['card']['name'])
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -1, context.payload['card']['name'])
        _add_log(context.state, f"{context.payload['card']['name']} 自身 +1，并压低 {target['name']} 1 点战力。")
    else:
        _add_log(context.state, f"{context.payload['card']['name']} 自身 +1。")


def material_relic_field(context: 'EventContext') -> None:
    target = _lowest_ally(context) or context.payload['card']
    _boost_card(context.payload['card'], 1, context.payload['card']['name'])
    if target['instance_id'] != context.payload['card']['instance_id']:
        _boost_card(target, 1, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 自身 +1，并支援 {target['name']}。")


def material_signal_field(context: 'EventContext') -> None:
    _boost_card(context.payload['card'], 1, context.payload['card']['name'])
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -1, context.payload['card']['name'])
        _add_log(context.state, f"{context.payload['card']['name']} 自身 +1，并干扰 {target['name']} -1 战力。")
    else:
        _add_log(context.state, f"{context.payload['card']['name']} 自身 +1。")


def add_genesis(context: 'EventContext') -> None:
    if _create_token_at_location(context, 'harmony_genesis'):
        _add_combo_counter(context.state, str(context.payload['side']), 'genesis_created', 1)
        _add_log(context.state, f"{context.payload['card']['name']} 生成 1 个创生。")


def add_two_genesis_to_hand(context: 'EventContext') -> None:
    for _ in range(2):
        _create_token_at_location(context, 'harmony_genesis')
    _add_log(context.state, f"{context.payload['card']['name']} 在此区域追加 2 个创生标记。")


def genesis_to_surplus(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    count = _count_location_tag(context.payload['location'], side, TAG_GENESIS)
    added = _add_token_to_hand(context, 'surplus_charge', count=max(1, min(2, count)))
    _add_log(context.state, f"{context.payload['card']['name']} 将创生转为 {added} 张盈蓄。")


def genesis_team_boost(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    boosted = 0
    for location in context.state.get('locations', []):
        if _count_location_tag(location, side, TAG_GENESIS) <= 0:
            continue
        boosted += _boost_location_cards(location, side, 1, context.payload['card']['name'])
    _add_log(context.state, f"{context.payload['card']['name']} 让创生区域的 {boosted} 张己方牌 +1。")


def add_murk_opponent(context: 'EventContext') -> None:
    if _create_token_at_location(context, 'harmony_murk', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{context.payload['card']['name']} 在对手区域生成浊燃。")


def add_discord_opponent(context: 'EventContext') -> None:
    if _create_token_at_location(context, 'discordance', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{context.payload['card']['name']} 在对手区域制造失谐。")


def murk_pulse(context: 'EventContext') -> None:
    opponent = str(context.payload['opponent_side'])
    debuffed = _boost_location_cards(context.payload['location'], opponent, -1, context.payload['card']['name'], ignore_tokens=True)
    _add_token_to_hand(context, 'surplus_charge')
    _add_log(context.state, f"{context.payload['card']['name']} 引爆浊燃前压，削弱 {debuffed} 张牌并补入盈蓄。")


def add_darkstar_opponent(context: 'EventContext') -> None:
    if _create_token_at_location(context, 'harmony_darkstar', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{context.payload['card']['name']} 在对手区域放置黯星。")


def darkstar_accelerate(context: 'EventContext') -> None:
    opponent = str(context.payload['opponent_side'])
    darkstars = _location_mark_count(context.payload['location'], opponent, TAG_DARKSTAR)
    if darkstars:
        _boost_location_cards(context.payload['location'], opponent, -1, context.payload['card']['name'], ignore_tokens=True)
    _add_token_to_hand(context, 'surplus_charge')
    _add_log(context.state, f"{context.payload['card']['name']} 借 {darkstars} 个黯星标记压低对手，并补入盈蓄。")


def add_delay_opponent(context: 'EventContext') -> None:
    if _create_token_at_location(context, 'harmony_delay', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{context.payload['card']['name']} 在对手区域设置延滞。")


def add_delay_and_surplus(context: 'EventContext') -> None:
    add_delay_opponent(context)
    _add_token_to_hand(context, 'surplus_charge')
    _add_log(context.state, f"{context.payload['card']['name']} 同时准备 1 张盈蓄用于反打。")


def surplus_cache(context: 'EventContext') -> None:
    added = _add_token_to_hand(context, 'surplus_charge', count=2)
    _add_log(context.state, f"{context.payload['card']['name']} 打开缓存，将 {added} 张盈蓄加入手牌。")


def surplus_vanish(context: 'EventContext') -> None:
    side = str(context.payload['side'])
    context.payload['card']['vanish_after_reveal'] = True
    _add_combo_counter(context.state, side, 'surplus_revealed', 1)
    _add_log(context.state, f"{context.payload['card']['name']} 回流能量后消失。")


def _tutor_item(context: 'EventContext', archetype: str) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    for index, card in enumerate(list(side_state.get('deck', []))):
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and card.get('archetype') == archetype:
            tutored = side_state['deck'].pop(index)
            tutored['_animation_source_zone'] = 'deck'
            return tutored
    return None


def _declared_deck_item(context: 'EventContext', predicate: Any) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    declared_ids = [str(card_id) for card_id in context.payload['card'].get('declared_card_instance_ids', [])]
    if not declared_ids:
        return None
    for declared_id in declared_ids:
        for index, card in enumerate(list(side_state.get('deck', []))):
            if str(card.get('instance_id') or '') != declared_id or not predicate(card):
                continue
            tutored = side_state['deck'].pop(index)
            tutored['_animation_source_zone'] = 'deck'
            return tutored
    return None


def _recover_item(context: 'EventContext', archetype: str) -> JsonDict | None:
    side = str(context.payload['side'])
    side_state = context.state['sides'][side]
    if len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    for index, card in enumerate(list(side_state.get('discard', []))):
        if card.get('type') == CARD_TYPE_ANOMALY_ITEM and card.get('archetype') == archetype:
            recovered = side_state['discard'].pop(index)
            recovered['_animation_source_zone'] = 'discard'
            return recovered
    return None


def _add_card_to_hand(context: 'EventContext', card: JsonDict | None, source_name: str) -> None:
    if card is None:
        return
    source_zone = str(card.pop('_animation_source_zone', '') or '')
    card['played_turn'] = None
    card['location_id'] = None
    card['revealed'] = False
    card.pop('staged', None)
    card.pop('paid_cost', None)
    card.pop('reserved_as_material_for', None)
    card.pop('pending_material_ids', None)
    card.pop('declared_card_instance_ids', None)
    context.state['sides'][str(context.payload['side'])].setdefault('hand', []).append(card)
    if source_zone == 'deck':
        _append_draw_action(context.state, str(context.payload['side']), card, source_name)
    _add_log(context.state, f"{source_name} 将 {card['name']} 加入手牌。")


def _return_target_to_hand(context: 'EventContext', target: JsonDict) -> bool:
    side = str(context.payload['side'])
    for location in context.state.get('locations', []):
        cards = location.get('cards', {}).get(side, [])
        if target not in cards:
            continue
        cards.remove(target)
        target['played_turn'] = None
        target['location_id'] = None
        target['revealed'] = False
        target['cost_modifier'] = max(-1, int(target.get('cost_modifier') or 0) - 1)
        target.pop('staged', None)
        target.pop('paid_cost', None)
        target.pop('play_sequence', None)
        target.pop('reserved_as_material_for', None)
        target.pop('pending_material_ids', None)
        target.pop('declared_card_instance_ids', None)
        context.state['sides'][side].setdefault('hand', []).append(target)
        _add_log(context.state, f"{context.payload['card']['name']} 回收 {target['name']}，其下次部署费用 -1。")
        return True
    return False


def genesis_grow(context: 'EventContext') -> None:
    card = context.payload['card']
    target = _lowest_ally(context) or card
    _boost_card(target, 2, card['name'])
    if _create_token_at_location(context, 'harmony_genesis'):
        _add_combo_counter(context.state, str(context.payload['side']), 'genesis_created', 1)
    _add_log(context.state, f"{card['name']} 生成创生并使 {target['name']} +2。")


def genesis_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    declared = _declared_deck_item(
        context,
        lambda item: item.get('type') == CARD_TYPE_ANOMALY_ITEM and str(item.get('category') or '') in {'饮料', '食物'},
    )
    if declared is not None:
        if str(declared.get('definition_id') or '') == 'genesis_refresh_charge':
            _boost_card(card, 1, card['name'])
        _add_card_to_hand(context, declared, card['name'])
        card.pop('declared_card_instance_ids', None)
        return
    _boost_card(card, 1, card['name'])
    _add_card_to_hand(context, _tutor_item(context, 'genesis'), card['name'])
    card.pop('declared_card_instance_ids', None)


def genesis_recover(context: 'EventContext') -> None:
    card = context.payload['card']
    target = context.payload.get('target_card') if isinstance(context.payload.get('target_card'), dict) else None
    if target is not None and target.get('side') == str(context.payload['side']):
        base_power = int(target.get('base_power') or 0)
        current_power = int(target.get('computed_power', _raw_card_power(target)) or 0)
        if current_power < base_power and _return_target_to_hand(context, target):
            if str(target.get('category') or '') == '食物':
                declared = _declared_deck_item(
                    context,
                    lambda item: (
                        item.get('type') == CARD_TYPE_ANOMALY_ITEM
                        and int(item.get('cost') or 0) <= 1
                        and str(item.get('attribute') or '') in {'光', '灵', '相'}
                    ),
                )
                _add_card_to_hand(context, declared, card['name'])
            card.pop('declared_card_instance_ids', None)
            return
    target = _lowest_ally(context) or card
    _boost_card(target, 3, card['name'])
    recovered = _recover_item(context, 'genesis')
    if recovered is not None:
        _add_card_to_hand(context, recovered, card['name'])
    card.pop('declared_card_instance_ids', None)


def genesis_guard(context: 'EventContext') -> None:
    card = context.payload['card']
    boosted = _boost_location_cards(context.payload['location'], str(context.payload['side']), 1, card['name'], ignore_tokens=True)
    if boosted <= 0:
        _boost_card(card, 2, card['name'])
    _add_log(context.state, f"{card['name']} 护住此区域 {max(1, boosted)} 张己方牌。")


def delay_mark(context: 'EventContext') -> None:
    card = context.payload['card']
    if _create_token_at_location(context, 'harmony_delay', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{card['name']} 设置延滞。")


def delay_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    _boost_card(card, 1, card['name'])
    _add_card_to_hand(context, _tutor_item(context, 'delay'), card['name'])


def delay_control(context: 'EventContext') -> None:
    card = context.payload['card']
    delay_mark(context)
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -2, card['name'])
        _add_log(context.state, f"{card['name']} 让 {target['name']} -2。")


def delay_lock(context: 'EventContext') -> None:
    card = context.payload['card']
    count = _count_board_tag(context.state, str(context.payload['opponent_side']), TAG_DELAY)
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -1 - min(2, count), card['name'])
    _add_log(context.state, f"{card['name']} 按 {count} 个延滞压制对手行动。")


def murk_mark(context: 'EventContext') -> None:
    card = context.payload['card']
    if _create_token_at_location(context, 'harmony_murk', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{card['name']} 施加浊燃。")


def murk_pressure(context: 'EventContext') -> None:
    card = context.payload['card']
    murk_mark(context)
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -2, card['name'])
        _add_log(context.state, f"{card['name']} 压低 {target['name']} 2 点战力。")


def murk_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    _boost_card(card, 1, card['name'])
    _add_card_to_hand(context, _tutor_item(context, 'murk'), card['name'])


def murk_snowball(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent = str(context.payload['opponent_side'])
    count = _count_board_tag(context.state, opponent, TAG_MURK)
    if count:
        _boost_card(card, min(8, count * 2), card['name'])
        pressure = -2 if count >= 3 else -1
        _boost_location_cards(context.payload['location'], opponent, pressure, card['name'], ignore_tokens=True)
    _add_log(context.state, f"{card['name']} 借 {count} 个浊燃扩大节奏。")


def darkstar_seed(context: 'EventContext') -> None:
    card = context.payload['card']
    if _create_token_at_location(context, 'harmony_darkstar', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{card['name']} 设置黯星。")


def darkstar_seed_shell(context: 'EventContext') -> None:
    darkstar_seed(context)
    card = context.payload['card']
    side = str(context.payload['side'])
    pressure = (
        _count_location_tag(context.payload['location'], side, TAG_MURK)
        + _count_location_tag(context.payload['location'], side, TAG_DISCORD)
    )
    if pressure:
        _boost_card(card, 2, card['name'])
        _add_log(context.state, f"{card['name']} 借星壳抵住 {pressure} 个负面标记，自身 +2。")


def darkstar_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    _boost_card(card, 1, card['name'])
    _add_card_to_hand(context, _tutor_item(context, 'darkstar'), card['name'])


def darkstar_store(context: 'EventContext') -> None:
    card = context.payload['card']
    darkstar_seed(context)
    count = _count_board_tag(context.state, str(context.payload['opponent_side']), TAG_DARKSTAR)
    if count >= 2:
        _add_card_to_hand(context, _tutor_item(context, 'darkstar'), card['name'])


def darkstar_burst(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent = str(context.payload['opponent_side'])
    count = _count_board_tag(context.state, opponent, TAG_DARKSTAR)
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -min(5, 1 + count), card['name'])
    _add_log(context.state, f"{card['name']} 借 {count} 个黯星准备爆发。")


def surplus_charge_effect(context: 'EventContext') -> None:
    card = context.payload['card']
    added = _add_token_to_hand(context, 'surplus_charge', count=1)
    _add_log(context.state, f"{card['name']} 调度费用，加入 {added} 张盈蓄。")


def surplus_mark(context: 'EventContext') -> None:
    card = context.payload['card']
    if _create_token_at_location(context, 'harmony_surplus', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{card['name']} 触发盈蓄费用压力。")


def surplus_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    _add_token_to_hand(context, 'surplus_charge')
    _add_card_to_hand(context, _tutor_item(context, 'surplus'), card['name'])


def surplus_recover(context: 'EventContext') -> None:
    card = context.payload['card']
    surplus_mark(context)
    _add_card_to_hand(context, _recover_item(context, 'surplus'), card['name'])


def discord_mark(context: 'EventContext') -> None:
    card = context.payload['card']
    if _create_token_at_location(context, 'discordance', side=str(context.payload['opponent_side'])):
        _add_log(context.state, f"{card['name']} 制造失谐。")


def discord_control(context: 'EventContext') -> None:
    card = context.payload['card']
    discord_mark(context)
    target = _selected_or_highest_opponent(context)
    if target is not None:
        _boost_card(target, -2, card['name'])
        _add_log(context.state, f"{card['name']} 抹除 {target['name']} 2 点战力。")


def discord_tutor(context: 'EventContext') -> None:
    card = context.payload['card']
    _add_card_to_hand(context, _tutor_item(context, 'discord'), card['name'])


def discord_lock(context: 'EventContext') -> None:
    card = context.payload['card']
    opponent = str(context.payload['opponent_side'])
    count = _count_board_tag(context.state, opponent, TAG_DISCORD)
    amount = -2 - min(3, count)
    debuffed = _boost_location_cards(context.payload['location'], opponent, amount, card['name'], ignore_tokens=True)
    if debuffed >= 6:
        _boost_location_cards(context.payload['location'], opponent, -4, card['name'], ignore_tokens=True)
        _add_log(context.state, f"{card['name']} 抓住过度铺场，追加全场 -4。")
    _add_log(context.state, f"{card['name']} 以 {count} 个失谐控制 {debuffed} 张牌。")


CARD_EFFECTS = {
    'nanali_genesis': nanali_genesis,
    'xun_genesis': xun_genesis,
    'jiuyuan_genesis': jiuyuan_genesis,
    'bohe_genesis_support': bohe_genesis_support,
    'protagonist_harmony_copy': protagonist_harmony_copy,
    'xiaozhi_surplus_link': xiaozhi_surplus_link,
    'edgar_surplus_link': edgar_surplus_link,
    'adler_murk_pressure': adler_murk_pressure,
    'zaowu_murk_spread': zaowu_murk_spread,
    'dafutier_discord_link': dafutier_discord_link,
    'requiem_murk_finish': requiem_murk_finish,
    'baicang_murk_finish': baicang_murk_finish,
    'fatiya_darkstar_seed': fatiya_darkstar_seed,
    'haniya_darkstar_support': haniya_darkstar_support,
    'haiyue_darkstar_finish': haiyue_darkstar_finish,
    'hasuoer_delay_tax': hasuoer_delay_tax,
    'yi_delay_support': yi_delay_support,
    'chaos_delay_finish': chaos_delay_finish,
    'material_fons_field': material_fons_field,
    'material_fons_hand': material_fons_hand,
    'material_coin_field': material_coin_field,
    'material_archive_field': material_archive_field,
    'material_device_field': material_device_field,
    'material_fire_field': material_fire_field,
    'material_dust_field': material_dust_field,
    'material_oracle_field': material_oracle_field,
    'material_relic_field': material_relic_field,
    'material_signal_field': material_signal_field,
    'add_genesis': add_genesis,
    'add_two_genesis_to_hand': add_two_genesis_to_hand,
    'genesis_to_surplus': genesis_to_surplus,
    'genesis_team_boost': genesis_team_boost,
    'add_murk_opponent': add_murk_opponent,
    'add_discord_opponent': add_discord_opponent,
    'murk_pulse': murk_pulse,
    'add_darkstar_opponent': add_darkstar_opponent,
    'darkstar_accelerate': darkstar_accelerate,
    'add_delay_opponent': add_delay_opponent,
    'add_delay_and_surplus': add_delay_and_surplus,
    'surplus_cache': surplus_cache,
    'surplus_vanish': surplus_vanish,
    'genesis_grow': genesis_grow,
    'genesis_tutor': genesis_tutor,
    'genesis_recover': genesis_recover,
    'genesis_guard': genesis_guard,
    'delay_mark': delay_mark,
    'delay_tutor': delay_tutor,
    'delay_control': delay_control,
    'delay_lock': delay_lock,
    'murk_mark': murk_mark,
    'murk_pressure': murk_pressure,
    'murk_tutor': murk_tutor,
    'murk_snowball': murk_snowball,
    'darkstar_seed': darkstar_seed,
    'darkstar_seed_shell': darkstar_seed_shell,
    'darkstar_tutor': darkstar_tutor,
    'darkstar_store': darkstar_store,
    'darkstar_burst': darkstar_burst,
    'surplus_charge_effect': surplus_charge_effect,
    'surplus_mark': surplus_mark,
    'surplus_tutor': surplus_tutor,
    'surplus_recover': surplus_recover,
    'discord_mark': discord_mark,
    'discord_control': discord_control,
    'discord_tutor': discord_tutor,
    'discord_lock': discord_lock,
}


def _esper(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    element: str,
    rarity: str,
    art: str,
    description: str,
    effect_key: str = '',
    tags: list[str] | None = None,
    target_rule: JsonDict | None = None,
    material_cost: int | None = None,
    material_attribute: str | None = None,
    material_requirements: list[JsonDict] | None = None,
    material_requirement_text: str = '',
) -> JsonDict:
    required_materials = material_cost if material_cost is not None else _material_requirement_count(material_requirements) or _default_esper_material_cost(cost)
    required_attribute = material_attribute or element
    return _card(
        card_id,
        name,
        0,
        power,
        CARD_TYPE_ESPER,
        element,
        rarity,
        art,
        description,
        effect_key,
        ['esper', *(tags or [])],
        target_rule=target_rule,
        material_cost=required_materials,
        required_material_attribute=required_attribute,
        material_requirements=material_requirements,
        material_requirement_text=material_requirement_text,
        attribute=element,
    )


def _item(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    archetype: str,
    art: str,
    description: str,
    effect_key: str,
    tags: list[str] | None = None,
    target_rule: JsonDict | None = None,
    category: str = '器物',
    attribute: str = '相',
    material_tags: list[str] | None = None,
) -> JsonDict:
    resolved_material_tags = material_tags or []
    return _card(
        card_id,
        name,
        cost,
        power,
        CARD_TYPE_ANOMALY_ITEM,
        '异象',
        'r',
        art,
        _attribute_only_description(description, attribute),
        effect_key,
        [archetype, 'tool', TAG_MATERIAL, *resolved_material_tags, *(tags or [])],
        archetype=archetype,
        target_rule=target_rule,
        category=category,
        attribute=attribute,
        material_tags=resolved_material_tags,
    )


def _token(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    art: str,
    description: str,
    tags: list[str],
    effect_key: str = '',
) -> JsonDict:
    return _card(
        card_id,
        name,
        cost,
        power,
        CARD_TYPE_TOKEN,
        '环合',
        'token',
        art,
        _attribute_only_description(description, _attribute_from_material_tags(tags)),
        effect_key,
        ['token', *tags],
        attribute=_attribute_from_material_tags(tags),
        material_tags=[tag for tag in tags if tag.startswith('mat_')],
    )


def _card(
    card_id: str,
    name: str,
    cost: int,
    power: int,
    card_type: str,
    element: str,
    rarity: str,
    art: str,
    description: str,
    effect_key: str,
    tags: list[str],
    *,
    archetype: str = '',
    target_rule: JsonDict | None = None,
    category: str = '',
    attribute: str = '',
    material_tags: list[str] | None = None,
    material_cost: int | None = None,
    required_material_attribute: str = '',
    material_requirements: list[JsonDict] | None = None,
    material_requirement_text: str = '',
) -> JsonDict:
    hooks = {GameEvent.CARD_REVEALED.value: card_revealed} if effect_key else {}
    return {
        'id': card_id,
        'name': name,
        'cost': cost,
        'power': power,
        'type': card_type,
        'element': element,
        'rarity': rarity,
        'art': art,
        'description': description,
        'effect_key': effect_key,
        'tags': tags,
        'archetype': archetype,
        'category': category,
        'attribute': attribute,
        'attribute_icon': _element_icon(attribute),
        'material_tags': list(material_tags or []),
        'material_cost': material_cost,
        'required_material_attribute': required_material_attribute,
        'material_requirements': deepcopy(material_requirements or []),
        'material_requirement_text': material_requirement_text,
        'target_rule': deepcopy(target_rule) if target_rule else {},
        'event_hooks': hooks,
    }


def _default_esper_material_cost(cost: int) -> int:
    if cost <= 4:
        return 2
    return 3


def _attribute_from_material_tags(tags: list[str]) -> str:
    for tag in tags:
        attribute = MATERIAL_TAG_ATTRIBUTES.get(str(tag))
        if attribute:
            return attribute
    return ''


def _material_requirement_count(requirements: list[JsonDict] | None) -> int:
    return sum(int(requirement.get('count') or 1) for requirement in requirements or [])


def _attr_req(attribute: str, count: int = 1) -> JsonDict:
    return {'attribute': attribute, 'count': count}


def _cat_req(category: str, count: int = 1) -> JsonDict:
    return {'category': category, 'count': count}


def _name_req(name: str, count: int = 1) -> JsonDict:
    return {'name': name, 'count': count}


def _attribute_only_description(description: str, attribute: str) -> str:
    if not attribute:
        return description
    text = re.sub(r'自身作为[^；。]+素材；?', '', description)
    text = re.sub(r'素材。[^，。]*类素材，', f'素材。{attribute}属性素材，', text)
    return text.strip()


TOKEN_CARDS: dict[str, JsonDict] = {
    'material_fons': _token(
        'material_fons',
        '方斯',
        0,
        0,
        LUMINOUS_TOOL_ART,
        '灵属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_FONS],
    ),
    'material_coin': _token(
        'material_coin',
        '甲虫币',
        0,
        0,
        LUMINOUS_TOOL_ART,
        '光属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_COIN],
    ),
    'material_archive': _token(
        'material_archive',
        '猎人档案',
        0,
        0,
        ARCHIVE_TOOL_ART,
        '灵属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_ARCHIVE],
    ),
    'material_device': _token(
        'material_device',
        '器物模块',
        0,
        0,
        ARCHIVE_TOOL_ART,
        '相属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_DEVICE],
    ),
    'material_fire': _token(
        'material_fire',
        '异火石',
        0,
        0,
        CURSE_TOOL_ART,
        '咒属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_FIRE],
    ),
    'material_dust': _token(
        'material_dust',
        '混沌尘',
        0,
        0,
        CURSE_TOOL_ART,
        '暗属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_DUST],
    ),
    'material_oracle': _token(
        'material_oracle',
        '星辉残响',
        0,
        0,
        TIDE_TOOL_ART,
        '魂属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_ORACLE],
    ),
    'material_relic': _token(
        'material_relic',
        '旧刃残响',
        0,
        0,
        TIDE_TOOL_ART,
        '魂属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_RELIC],
    ),
    'material_signal': _token(
        'material_signal',
        '干扰信号',
        0,
        0,
        ARCHIVE_TOOL_ART,
        '相属性素材。可被异能者登场吸收战力。',
        [TAG_MATERIAL, TAG_MAT_SIGNAL],
    ),
    'harmony_genesis': _token(
        'harmony_genesis',
        '创生',
        0,
        0,
        LUMINOUS_TOOL_ART,
        '区域标记。每回合开始随机使一个友方 +1 战力；不占据格子，也不能作为登场素材。',
        [TAG_HARMONY, TAG_GENESIS],
    ),
    'harmony_murk': _token(
        'harmony_murk',
        '浊燃',
        0,
        0,
        CURSE_TOOL_ART,
        '区域标记。每回合开始使同区域一张友方牌 -1 战力，优先非负战力牌；不占据格子。',
        [TAG_HARMONY, TAG_MURK],
    ),
    'harmony_delay': _token(
        'harmony_delay',
        '延滞',
        0,
        0,
        ARCHIVE_TOOL_ART,
        '区域标记。该区域下一张己方加入的牌额外需要 1 点能量，然后移除 1 个延滞；不占据格子。',
        [TAG_HARMONY, TAG_DELAY],
    ),
    'harmony_surplus': _token(
        'harmony_surplus',
        '盈蓄',
        0,
        0,
        LUMINOUS_TOOL_ART,
        '融合标记。己方下次部署阶段生成 -1 费盈蓄牌；不占据格子。',
        [TAG_HARMONY, TAG_SURPLUS],
    ),
    'harmony_darkstar': _token(
        'harmony_darkstar',
        '黯星',
        0,
        0,
        TIDE_TOOL_ART,
        '区域标记。回合开始爆发并移除，使同区域友方牌 -2；不占据格子。',
        [TAG_HARMONY, TAG_DARKSTAR],
    ),
    'surplus_charge': _token(
        'surplus_charge',
        '盈蓄',
        -1,
        0,
        LUMINOUS_TOOL_ART,
        '-1 费 0 战力。揭示后消失，用于返还能量并继续展开。',
        [TAG_HARMONY, TAG_SURPLUS],
        'surplus_vanish',
    ),
    'discordance': _token(
        'discordance',
        '失谐',
        0,
        0,
        CURSE_TOOL_ART,
        '区域标记。放大负面效果收益；不提供战力，不占据格子。',
        [TAG_HARMONY, TAG_DISCORD],
    ),
    'collapsing_card': _token(
        'collapsing_card',
        '倾陷中的卡牌',
        0,
        0,
        TIDE_TOOL_ART,
        '被黯星封存后的卡牌，只保留当前战力，不再拥有持续型效果。',
        [TAG_HARMONY, TAG_COLLAPSING],
    ),
}


GENESIS_ITEM_SPECS = [
    ('genesis_urban_energy', '都市活力', 1, 2, '宣言：检视牌库，选择 1 张饮料或食物。揭示：将宣言牌加入手牌；若宣言牌为「畅爽焕能」，自身 +1。', 'genesis_tutor', '光', TAG_MAT_COIN, '耗材'),
    ('genesis_refresh_charge', '畅爽焕能', 1, 1, '宣言：若「都市活力」在己方场上或墓地，选择 1 张手牌中费用 <=1 的食物或耗材。揭示：若已宣言手牌，将其部署；否则从牌库将 1 张「都市活力」加入手牌。', 'genesis_tutor', '灵', TAG_MAT_FONS, '饮料'),
    ('genesis_breakfast_bag', '速食早餐袋', 1, 2, '揭示：使己方最低战力道具 +2。若本回合部署过「都市活力」或「畅爽焕能」，改为 +3。', 'genesis_grow', '灵', TAG_MAT_FONS, '食物'),
    ('genesis_marble_soda', '彩色波子汽水', 2, 2, '宣言：选择 1 张己方战力 <=2 的道具。揭示：将宣言道具返回手牌；下次部署阶段第一张食物费用 -1。', 'genesis_guard', '光', TAG_MAT_COIN, '饮料'),
    ('genesis_eborn_cake', '来自「伊波恩」的蛋糕', 3, 4, '宣言：检视牌库与墓地，选择 1 张关联浔、娜娜莉、阿德勒、早雾、达芙蒂尔或埃德嘉的道具。揭示：将宣言牌加入手牌；若己方场上有 3 张以上道具，己方全体 +1。', 'genesis_recover', '灵', TAG_MAT_ARCHIVE, '食物'),
    ('genesis_chip_washer', '吃薯片专用洗指机', 2, 2, '宣言：选择 1 张己方道具；若其为食物，检视牌库并选择 1 张费用 <=1 的光、灵或相属性道具。揭示：若宣言道具当前战力低于基础战力，将其返回手牌并使其下次部署费用 -1；若返回的是食物，将宣言的低费道具加入手牌。', 'genesis_recover', '光', TAG_MAT_DEVICE, '其他'),
    ('genesis_nest_shard', '护巢残片', 3, 4, '揭示：设置“护巢残片”预警，自下个回合开始生效，持续到下个回合结束。生效期间，己方战力最高道具第一次将被减为非正时保留 1 战力；若它之后被异能者消耗，触发的共鸣额外 +1 战力。', 'genesis_guard', '灵', TAG_MAT_RELIC, '材料'),
    ('genesis_muscle_faith', '暴走棉绒绒-肌肉信仰', 5, 7, '揭示：若己方有战力 >=8 的单位，部署 1 个 0 费 3 战力棉绒绒衍生物；本局此前每有 1 张己方道具被返回手牌，该衍生物 +1，最多 +4。', 'genesis_guard', '灵', TAG_MAT_FONS, '重要'),
]

DELAY_ITEM_SPECS = [
    ('delay_first_wish', '初次的期许', 1, 1, '宣言：检视牌库，选择 1 张「思维的同频」或「水波的迟疑」。揭示：将宣言牌加入手牌；下次部署阶段第一张相属性道具费用 -1。', 'delay_tutor', '光', TAG_MAT_COIN, '材料'),
    ('delay_mind_sync', '思维的同频', 1, 2, '宣言：选择对手异能者编队中 1 名异能者，并宣言其素材条件中的 1 个属性或类别。揭示：设置“同频预判”，持续到下个回合结束；己方相属性道具或相属性异能者影响命中宣言属性或类别的对手道具时，额外 -1。', 'delay_mark', '相', TAG_MAT_SIGNAL, '材料'),
    ('delay_water_hesitation', '水波的迟疑', 2, 2, '宣言：选择 1 张对手道具。揭示：宣言道具到下个回合结束前不能作为异能者素材；若它命中己方“同频预判”宣言的属性或类别，额外 -1。', 'delay_control', '相', TAG_MAT_DEVICE, '材料'),
    ('delay_recruit_fear', '新兵的怯懦', 1, 2, '揭示：对手最低战力道具 -2；若其进入墓地，对手下次登场异能者不能消耗同名道具。', 'delay_control', '相', TAG_MAT_SIGNAL, '材料'),
    ('delay_nestling_hope', '雏鸟的希冀', 2, 3, '宣言：选择 1 张己方相属性道具，并检视牌库选择 1 张材料道具。揭示：宣言道具到下个回合结束前不能被对手效果返回手牌；若对手本回合素材消耗阶段登场异能者，将宣言材料加入手牌。', 'delay_tutor', '光', TAG_MAT_COIN, '材料'),
    ('delay_commute_bag', '通勤公文包', 2, 3, '宣言：选择 1 张手牌中的材料道具。揭示：展示宣言牌并置于牌库顶，随后抽 1 张；设置“通勤排程”预警，持续到下个回合结束。对手下一次从牌库加入牌后，其下次部署阶段第一张牌费用 +1。', 'delay_tutor', '光', TAG_MAT_ARCHIVE, '其他'),
    ('delay_missed_call', '无人来电', 3, 3, '揭示：设置“无人来电”预警，持续到下个回合结束。对手下一次从牌库加入牌后，使其最低战力道具 -2；若那张加入手牌的牌与其场上道具同名，额外使同名道具 -1。', 'delay_lock', '相', TAG_MAT_SIGNAL, '其他'),
    ('delay_kaleidoscope', '万花筒', 3, 4, '揭示：设置“万花筒”预警，从下个回合开始生效，持续到下个回合结束。己方下一张材料道具的揭示效果结算后，复制该效果；若被复制效果包含宣言目标，复制件自动作用于同一目标集合中战力最低的合法目标，没有合法目标则不复制。', 'delay_lock', '光', TAG_MAT_ARCHIVE, '其他'),
]

MURK_ITEM_SPECS = [
    ('murk_basic_material_box', '初级异象材料自选箱', 1, 1, '宣言：检视牌库，选择 1 张「失落絮语」、「褪色掠影」、「模糊数符」或「悬想幻妄」作为送墓牌，再选择 1 张不同名的上述道具作为加入手牌牌。揭示：将送墓宣言牌置入墓地，再将加入手牌宣言牌加入手牌。', 'murk_tutor', '暗', TAG_MAT_DUST, '耗材'),
    ('murk_lost_whisper', '失落絮语', 1, 2, '被效果从牌库置入墓地时：对手最低战力道具 -1。宣言：选择 1 张对手道具。揭示：宣言道具 -1。', 'murk_pressure', '咒', TAG_MAT_FIRE, '材料'),
    ('murk_faded_shadow', '褪色掠影', 1, 2, '揭示：设置“褪色掠影”预警，持续到下个回合结束。对手下一次从牌库加入牌后，使那张牌或其同属性场上道具 -2。', 'murk_pressure', '暗', TAG_MAT_DUST, '材料'),
    ('murk_blur_number', '模糊数符', 2, 2, '宣言：选择己方 1 张材料道具，并宣言 1 个基础属性。揭示：到下次异能者素材消耗前，宣言道具可视为宣言属性；若之后被咒属性异能者消耗，检视牌库，选择 1 张费用 <=2 的材料道具加入手牌。', 'murk_tutor', '咒', TAG_MAT_SIGNAL, '材料'),
    ('murk_fantasy_delusion', '悬想幻妄', 3, 3, '揭示：按对手浊燃数量自身 +2 到 +8；对手全体 -1，若对手有 3 个以上浊燃改为 -2。', 'murk_snowball', '咒', TAG_MAT_FIRE, '材料'),
    ('murk_knight_spark', '上膛骑士火花塞', 3, 4, '揭示：按对手浊燃数量自身 +2 到 +8；对手全体 -1，若对手有 3 个以上浊燃改为 -2。', 'murk_snowball', '咒', TAG_MAT_FIRE, '材料'),
    ('murk_other_side_page', '妄想彼端的一页', 4, 5, '宣言：选择本回合素材消耗阶段，或本局此前由效果送入己方墓地的 1 张材料道具；若没有可选目标，检视牌库并选择 1 张材料道具。揭示：若宣言了可复制目标，复制其墓地触发效果；否则将宣言牌从牌库置入墓地。', 'murk_tutor', '暗', TAG_MAT_ARCHIVE, '材料'),
    ('murk_colorful_ticket', '斑斓的票根', 5, 7, '揭示：按对手浊燃数量自身 +2 到 +8；对手全体 -1，若对手有 3 个以上浊燃改为 -2。', 'murk_snowball', '咒', TAG_MAT_FIRE, '材料'),
]

DARKSTAR_ITEM_SPECS = [
    ('darkstar_mining_permit', '「异晶开采凭证」', 1, 1, '宣言：若「环石」已在手牌、场上或墓地，检视牌库，选择 1 张魂属性道具。揭示：若「环石」已在手牌、场上或墓地，从牌库将 1 张「本性像素」置入墓地并将宣言魂属性道具加入手牌；否则从牌库将 1 张「环石」加入手牌。', 'darkstar_tutor', '暗', TAG_MAT_DUST, '耗材'),
    ('darkstar_ringstone', '环石', 1, 2, '宣言：选择 1 张己方道具。揭示：若己方场上或墓地有「异晶开采凭证」或「本性像素」，将「环石」附着到宣言道具上作为星壳；该道具第一次被减为非正时改为保留 1 战力。', 'darkstar_seed_shell', '魂', TAG_MAT_ORACLE, '货币'),
    ('darkstar_nature_pixel', '本性像素', 2, 2, '从牌库置入墓地时：查看牌库顶 3 张，将其中最上方的暗或魂属性道具加入手牌，其余置底。揭示：己方每有 1 个星壳，对手最高战力道具 -1，最多 -3。', 'darkstar_store', '魂', TAG_MAT_RELIC, '耗材'),
    ('darkstar_denoise_base', '去噪底液', 2, 3, '宣言：选择 1 张己方带有负向战力修正的道具和 1 张对手道具；若墓地有「本性像素」，检视牌库，选择 1 张魂属性道具。揭示：移除己方宣言道具上的 1 点负向战力，并使对手宣言道具 -1；若墓地有「本性像素」，将宣言魂属性道具加入手牌。', 'darkstar_tutor', '暗', TAG_MAT_DUST, '耗材'),
    ('darkstar_oracle_stone', '谕石', 1, 1, '揭示：展示对手异能者编队中当前素材最接近满足的 1 名异能者；下个回合该异能者准备共鸣时，素材检查前使其最低战力可用素材 -1。', 'darkstar_seed', '魂', TAG_MAT_ORACLE, '耗材'),
    ('darkstar_listening_crystal', '聆谕水晶', 3, 3, '宣言：检视牌库与墓地，选择最多 3 张「谕石」，并指定其中 1 张加入手牌、1 张部署。揭示：按宣言处理，剩余宣言牌置底；同名效果每局最多 3 次。', 'darkstar_tutor', '魂', TAG_MAT_ORACLE, '其他'),
    ('darkstar_dream_knot', '织梦结', 3, 4, '宣言：选择己方墓地 1 张「本性像素」或「环石」。揭示：己方星壳上限 +1；若本回合素材消耗阶段有黯星被设置或引爆，回收宣言牌。', 'darkstar_store', '暗', TAG_MAT_DUST, '家具'),
    ('darkstar_someone_helmet', '何人的头盔', 5, 7, '揭示：若己方有即将到期的黯星，引爆倒计时最短的 1 个；否则设置“头盔预兆”：下个回合开始时，对手最高战力单位 -3。', 'darkstar_burst', '魂', TAG_MAT_RELIC, '材料'),
]

SURPLUS_ITEM_SPECS = [
    ('surplus_fons', '方斯', 0, 1, '揭示：下次部署阶段第一张光、灵或相属性道具费用 -1；若本回合部署过盈蓄，自身 +2。', 'genesis_guard', '光', TAG_MAT_COIN, '货币'),
    ('surplus_a_coin', '甲硬币', 0, 1, '揭示：下次部署阶段第一张光、灵或相属性道具费用 -1；若本回合部署过盈蓄，自身 +2。', 'genesis_guard', '光', TAG_MAT_COIN, '货币'),
    ('surplus_um_coin', '嗯硬币', 0, 1, '揭示：下次部署阶段第一张光、灵或相属性道具费用 -1；若本回合部署过盈蓄，自身 +2。', 'genesis_guard', '灵', TAG_MAT_FONS, '货币'),
]

DISCORD_ITEM_SPECS = [
    ('discord_tomato', '西红柿', 1, 1, '揭示：从牌库将「番茄百分百」加入手牌；若「番茄全家桶」在墓地，「西红柿」也视为暗属性素材。', 'murk_tutor', '咒', TAG_MAT_FIRE, '食材'),
    ('discord_tomato_100', '番茄百分百', 2, 2, '揭示：从牌库将「番茄全家桶」加入手牌；若本回合素材消耗阶段有咒属性材料进入墓地，对手最低战力道具 -1。', 'murk_pressure', '暗', TAG_MAT_DUST, '食物'),
    ('discord_tomato_bucket', '番茄全家桶', 3, 3, '宣言：若异能者编队有「安魂曲」，检视牌库，选择 1 张「西红柿」或「番茄百分百」。揭示：若异能者编队有「安魂曲」，将宣言牌加入手牌；对手最高战力道具 -2。', 'discord_control', '暗', TAG_MAT_DUST, '礼物'),
    ('discord_nameless_blade', '无名刃', 5, 6, '揭示：若本局触发过失谐，清除对手最高战力单位的正向战力后使其 -3；否则使其 -2。', 'discord_lock', '暗', TAG_MAT_DUST, '材料'),
]


def _items_from_specs(archetype: str, art: str, specs: list[tuple[Any, ...]]) -> list[JsonDict]:
    items: list[JsonDict] = []
    for spec in specs:
        card_id, name, cost, power, description, effect_key, attribute, material_tag, *rest = spec
        category = str(rest[0]) if rest else '材料'
        items.append(_item(
            str(card_id),
            str(name),
            int(cost),
            int(power),
            archetype,
            _known_item_art(str(name), art),
            str(description),
            str(effect_key),
            attribute=str(attribute),
            material_tags=[str(material_tag)],
            category=category,
        ))
    return items


GENESIS_POOL_IDS = [str(item[0]) for item in GENESIS_ITEM_SPECS]
DELAY_POOL_IDS = [str(item[0]) for item in DELAY_ITEM_SPECS]
MURK_POOL_IDS = [str(item[0]) for item in MURK_ITEM_SPECS]
DARKSTAR_POOL_IDS = [str(item[0]) for item in DARKSTAR_ITEM_SPECS]
SURPLUS_POOL_IDS = [str(item[0]) for item in SURPLUS_ITEM_SPECS]
DISCORD_POOL_IDS = [str(item[0]) for item in DISCORD_ITEM_SPECS]

GENESIS_ITEM_IDS = [
    'genesis_urban_energy', 'genesis_urban_energy', 'genesis_urban_energy',
    'genesis_refresh_charge', 'genesis_refresh_charge', 'genesis_refresh_charge',
    'genesis_breakfast_bag', 'genesis_breakfast_bag', 'genesis_breakfast_bag',
    'genesis_marble_soda', 'genesis_marble_soda',
    'genesis_eborn_cake', 'genesis_eborn_cake', 'genesis_eborn_cake',
    'genesis_chip_washer', 'genesis_chip_washer',
    'genesis_nest_shard', 'genesis_nest_shard',
    'genesis_muscle_faith', 'genesis_muscle_faith',
]
DELAY_ITEM_IDS = [
    'delay_first_wish', 'delay_first_wish', 'delay_first_wish',
    'delay_mind_sync', 'delay_mind_sync', 'delay_mind_sync',
    'delay_water_hesitation', 'delay_water_hesitation', 'delay_water_hesitation',
    'delay_recruit_fear', 'delay_recruit_fear', 'delay_recruit_fear',
    'delay_nestling_hope', 'delay_nestling_hope',
    'delay_commute_bag', 'delay_commute_bag',
    'delay_missed_call', 'delay_missed_call',
    'delay_kaleidoscope', 'delay_kaleidoscope',
]
MURK_ITEM_IDS = [
    'murk_basic_material_box', 'murk_basic_material_box', 'murk_basic_material_box',
    'murk_lost_whisper', 'murk_lost_whisper', 'murk_lost_whisper',
    'murk_faded_shadow', 'murk_faded_shadow', 'murk_faded_shadow',
    'murk_blur_number', 'murk_blur_number', 'murk_blur_number',
    'murk_fantasy_delusion', 'murk_fantasy_delusion',
    'murk_knight_spark', 'murk_knight_spark',
    'murk_other_side_page', 'murk_other_side_page',
    'murk_colorful_ticket', 'murk_colorful_ticket',
]
DARKSTAR_ITEM_IDS = [
    'darkstar_mining_permit', 'darkstar_mining_permit', 'darkstar_mining_permit',
    'darkstar_ringstone', 'darkstar_ringstone', 'darkstar_ringstone',
    'darkstar_nature_pixel', 'darkstar_nature_pixel', 'darkstar_nature_pixel',
    'darkstar_denoise_base', 'darkstar_denoise_base',
    'darkstar_oracle_stone', 'darkstar_oracle_stone', 'darkstar_oracle_stone',
    'darkstar_listening_crystal', 'darkstar_listening_crystal',
    'darkstar_dream_knot', 'darkstar_dream_knot',
    'darkstar_someone_helmet', 'darkstar_someone_helmet',
]
SURPLUS_ITEM_IDS = [
    'genesis_urban_energy', 'genesis_urban_energy',
    'genesis_refresh_charge', 'genesis_refresh_charge',
    'genesis_breakfast_bag', 'genesis_breakfast_bag',
    'genesis_marble_soda',
    'genesis_eborn_cake',
    'genesis_chip_washer',
    'genesis_nest_shard',
    'delay_first_wish', 'delay_first_wish',
    'delay_mind_sync', 'delay_mind_sync',
    'delay_water_hesitation', 'delay_water_hesitation',
    'delay_recruit_fear',
    'delay_commute_bag',
    'surplus_fons',
    'surplus_a_coin',
]
DISCORD_ITEM_IDS = [
    'murk_basic_material_box', 'murk_basic_material_box',
    'murk_lost_whisper', 'murk_lost_whisper',
    'murk_faded_shadow', 'murk_faded_shadow',
    'murk_blur_number',
    'murk_fantasy_delusion',
    'murk_knight_spark',
    'darkstar_mining_permit', 'darkstar_mining_permit',
    'darkstar_ringstone', 'darkstar_ringstone',
    'darkstar_nature_pixel',
    'darkstar_oracle_stone',
    'darkstar_listening_crystal',
    'darkstar_someone_helmet',
    'discord_tomato',
    'discord_tomato_100',
    'discord_tomato_bucket',
]


CARD_DEFINITIONS: list[JsonDict] = [
    _esper('nanali', '娜娜莉', 2, 3, '灵', 'n', ART_NANALI, '共鸣：设置环合：创生。使己方最低战力单位 +3，并保护本回合关键素材。', 'nanali_genesis', [TAG_GENESIS], material_requirements=[_attr_req('灵'), _cat_req('饮料')]),
    _esper('bohe', '薄荷', 3, 5, '灵', 'r', ART_BOHE, '共鸣：设置环合：创生。保护己方低战力道具，场上已有创生时回收食物资源。', 'bohe_genesis_support', [TAG_GENESIS], material_requirements=[_attr_req('灵'), _attr_req('光')]),
    _esper('xun', '浔', 4, 6, '光', 'sr', ART_XUN, '共鸣：设置环合：创生。把创生转化为战力，并从墓地部署低费光/灵道具。', 'xun_genesis', [TAG_GENESIS], material_requirements=[_attr_req('灵'), _attr_req('光'), _cat_req('食物')]),
    _esper('jiuyuan', '九原', 4, 6, '灵', 'sr', ART_JIUYUAN, '共鸣：设置环合：创生。回收被消耗的素材，创生与延滞同时存在时回收不同类别资源。', 'jiuyuan_genesis', [TAG_GENESIS, TAG_SURPLUS], material_requirements=[_attr_req('灵'), _cat_req('食物')]),
    _esper('hasuoer', '哈索尔', 2, 3, '相', 'r', ART_HASUOER, '共鸣：设置环合：延滞。读取相属性素材，延长延滞并封住对手关键素材。', 'hasuoer_delay_tax', [TAG_DELAY], material_requirements=[_attr_req('相'), _attr_req('光')]),
    _esper('yi', '翳', 3, 5, '相', 'sr', ART_YI, '共鸣：设置环合：延滞。扩展延滞并保护己方低战力牌。', 'yi_delay_support', [TAG_DELAY, TAG_SURPLUS], material_requirements=[_attr_req('相', 2)]),
    _esper('protagonist', '鉴定师', 4, 6, '光', 'sr', ART_PROTAGONIST, '共鸣：根据消耗的灵/相素材设置创生或延滞，并把融合窗口转化为费用资源。', 'protagonist_harmony_copy', [TAG_GENESIS, TAG_DELAY, TAG_SURPLUS], material_requirements=[_attr_req('光'), {'attributes': ['灵', '相'], 'count': 1}]),
    _esper('chaos', '卡厄斯', 6, 9, '相', 'ur', ART_PROTAGONIST, '共鸣：设置环合：延滞。统计本局延滞成功拖慢的行动，压制对手整条行动线。', 'chaos_delay_finish', [TAG_DELAY], material_requirements=[_attr_req('相', 2), _cat_req('材料')]),
    _esper('adler', '阿德勒', 3, 5, '咒', 'sr', ART_ADLER, '共鸣：设置环合：浊燃。按火种/失序素材自身 +1 到 +4，压低对手关键素材；第一次将被减为非正时保留 1 战力。若己方承受黯星，清理 1 个并自身 +2。', 'adler_murk_pressure', [TAG_MURK], material_requirements=[_attr_req('咒'), _attr_req('暗')]),
    _esper('zaowu', '早雾', 3, 5, '咒', 'r', ART_ZAOWU, '共鸣：设置环合：浊燃。从墓地部署低费材料，补回被干扰后的素材线。', 'zaowu_murk_spread', [TAG_MURK, TAG_DISCORD], material_requirements=[_attr_req('咒'), _cat_req('材料')]),
    _esper('requiem', '安魂曲', 5, 8, '咒', 'sr', ART_BAICANG, '共鸣：设置环合：浊燃。按墓地材料数量扩大压制，并为失谐保留浊燃窗口。', 'requiem_murk_finish', [TAG_MURK, TAG_DISCORD], material_requirements=[_attr_req('咒'), _attr_req('暗'), _cat_req('材料')]),
    _esper('baicang', '白藏', 6, 10, '咒', 'ur', ART_BAICANG, '共鸣：设置环合：浊燃。终结被压低的对手场面并回收高费材料。', 'baicang_murk_finish', [TAG_MURK], material_requirements=[_attr_req('咒', 2), _cat_req('材料')]),
    _esper('fatiya', '法帝娅', 3, 4, '魂', 'r', ART_FATIYA, '共鸣：设置环合：黯星。把墓地「环石」变成星壳，准备后续爆发。', 'fatiya_darkstar_seed', [TAG_DARKSTAR], material_requirements=[_attr_req('魂'), _name_req('环石')]),
    _esper('haniya', '哈尼娅', 4, 6, '魂', 'sr', ART_HANIYA, '共鸣：设置环合：黯星。调度谕石与聆谕水晶，压缩爆发窗口。', 'haniya_darkstar_support', [TAG_DARKSTAR, TAG_DISCORD], material_requirements=[_attr_req('魂'), _name_req('谕石')]),
    _esper('haiyue', '海月', 5, 8, '魂', 'sr', ART_HAIYUE, '共鸣：引爆 1 个黯星。按星壳与已引爆黯星数量压低对手全场。', 'haiyue_darkstar_finish', [TAG_DARKSTAR], material_requirements=[_attr_req('魂'), _attr_req('暗'), _name_req('环石')]),
    _esper('dafutier', '达芙蒂尔', 3, 5, '暗', 'sr', ART_DAFUTIER, '共鸣：不设置基础环合。黯星与浊燃同时存在时立即触发失谐；否则回收咒/暗资源。', 'dafutier_discord_link', [TAG_DARKSTAR, TAG_DISCORD], material_requirements=[_attr_req('暗'), _attr_req('魂'), _cat_req('耗材')]),
    _esper('xiaozhi', '小吱', 2, 3, '光', 'r', ART_XIAOZHI, '共鸣：不设置基础环合。创生与延滞同时存在时触发盈蓄并继续部署低费道具。', 'xiaozhi_surplus_link', [TAG_SURPLUS], material_requirements=[_attr_req('光'), _attr_req('灵')]),
    _esper('edgar', '埃德嘉', 3, 5, '光', 'sr', ART_EDGAR, '共鸣：回收低费素材；本回合部署过盈蓄时，为下一次部署降低费用。', 'edgar_surplus_link', [TAG_SURPLUS], material_requirements=[_attr_req('光'), _cat_req('货币')]),
    *_items_from_specs('genesis', LUMINOUS_TOOL_ART, GENESIS_ITEM_SPECS),
    *_items_from_specs('delay', ARCHIVE_TOOL_ART, DELAY_ITEM_SPECS),
    *_items_from_specs('murk', CURSE_TOOL_ART, MURK_ITEM_SPECS),
    *_items_from_specs('darkstar', TIDE_TOOL_ART, DARKSTAR_ITEM_SPECS),
    *_items_from_specs('surplus', LUMINOUS_TOOL_ART, SURPLUS_ITEM_SPECS),
    *_items_from_specs('discord', CURSE_TOOL_ART, DISCORD_ITEM_SPECS),
]


DUEL_DECKS: list[JsonDict] = [
    {'id': 'genesis_bloom', 'name': '创生养成', 'short_name': '创生', 'description': '加身材、养大怪，用创生保护素材和异能者不被小伤害刮死。', 'difficulty': '新手推荐', 'ai_nickname': '创生试炼 AI', 'card_ids': GENESIS_ITEM_IDS, 'esper_card_ids': ['nanali', 'bohe', 'xun', 'jiuyuan'], 'ai_plan': {'opening_card_ids': GENESIS_ITEM_IDS[:8], 'priority_card_ids': GENESIS_ITEM_IDS, 'esper_priority_ids': ['nanali', 'bohe', 'xun', 'jiuyuan']}},
    {'id': 'delay_lock', 'name': '延滞锁控', 'short_name': '延滞', 'description': '拖延对手行动，用控制型异能者真正封住关键素材与登场窗口。', 'difficulty': '资源规划', 'ai_nickname': '延滞锁控 AI', 'card_ids': DELAY_ITEM_IDS, 'esper_card_ids': ['hasuoer', 'yi', 'protagonist', 'chaos'], 'ai_plan': {'opening_card_ids': DELAY_ITEM_IDS[:8], 'priority_card_ids': DELAY_ITEM_IDS, 'esper_priority_ids': ['hasuoer', 'yi', 'protagonist', 'chaos']}},
    {'id': 'murk_burn', 'name': '浊燃节奏', 'short_name': '浊燃', 'description': '用持续压制建立优势，打掉素材并在中期滚出节奏差。', 'difficulty': '节奏压制', 'ai_nickname': '浊燃节奏 AI', 'card_ids': MURK_ITEM_IDS, 'esper_card_ids': ['adler', 'zaowu', 'requiem', 'baicang'], 'ai_plan': {'opening_card_ids': ['murk_basic_material_box', 'murk_lost_whisper', 'murk_faded_shadow', 'murk_blur_number', 'murk_basic_material_box', 'murk_lost_whisper'], 'priority_card_ids': ['murk_lost_whisper', 'murk_faded_shadow', 'murk_blur_number', 'murk_basic_material_box', 'murk_fantasy_delusion', 'murk_knight_spark', 'murk_other_side_page', 'murk_colorful_ticket'], 'esper_priority_ids': ['adler', 'zaowu', 'requiem', 'baicang']}},
    {'id': 'darkstar_bomb', 'name': '黯星爆返', 'short_name': '黯星', 'description': '前期蓄星偏弱，后期依靠黯星引爆一波返场。', 'difficulty': '爆发反打', 'ai_nickname': '黯星爆返 AI', 'card_ids': DARKSTAR_ITEM_IDS, 'esper_card_ids': ['fatiya', 'haniya', 'haiyue', 'dafutier'], 'ai_plan': {'opening_card_ids': DARKSTAR_ITEM_IDS[:8], 'priority_card_ids': DARKSTAR_ITEM_IDS, 'esper_priority_ids': ['fatiya', 'haniya', 'haiyue', 'dafutier']}},
    {'id': 'surplus_combo', 'name': '盈蓄费用魔术', 'short_name': '盈蓄', 'description': '创生与延滞的进阶复合，用费用魔术大量出牌，并靠延滞拖慢对手。', 'difficulty': '高阶展开', 'ai_nickname': '盈蓄连锁 AI', 'card_ids': SURPLUS_ITEM_IDS, 'esper_card_ids': ['xiaozhi', 'edgar', 'jiuyuan', 'yi'], 'ai_plan': {'opening_card_ids': SURPLUS_ITEM_IDS[:8], 'priority_card_ids': SURPLUS_ITEM_IDS, 'esper_priority_ids': ['xiaozhi', 'edgar', 'jiuyuan', 'yi']}},
    {'id': 'discord_control', 'name': '失谐空场', 'short_name': '失谐', 'description': '浊燃与黯星的进阶复合，压到对手空场后用高费异象道具取胜。', 'difficulty': '高阶控制', 'ai_nickname': '失谐控制 AI', 'card_ids': DISCORD_ITEM_IDS, 'esper_card_ids': ['dafutier', 'haniya', 'zaowu', 'requiem'], 'ai_plan': {'opening_card_ids': DISCORD_ITEM_IDS[:8], 'priority_card_ids': DISCORD_ITEM_IDS, 'esper_priority_ids': ['zaowu', 'requiem', 'haniya', 'dafutier']}},
]

def load_duel_cards() -> list[JsonDict]:
    return sorted(
        (deepcopy(card) for card in CARD_DEFINITIONS),
        key=lambda card: (str(card.get('archetype', '')), int(card['cost']), str(card['name'])),
    )


def get_duel_card(card_id: str) -> JsonDict | None:
    if card_id in TOKEN_CARDS:
        return deepcopy(TOKEN_CARDS[card_id])
    for card in CARD_DEFINITIONS:
        if card['id'] == card_id:
            return deepcopy(card)
    return None


def load_duel_decks() -> list[JsonDict]:
    return [deepcopy(deck) for deck in DUEL_DECKS]


def get_duel_deck(deck_id: str) -> JsonDict | None:
    normalized = str(deck_id or '').strip()
    for deck in DUEL_DECKS:
        if deck['id'] == normalized:
            return deepcopy(deck)
    return None


def default_duel_deck_id() -> str:
    return str(DUEL_DECKS[0]['id'])


def count_esper_cards(card_ids: list[str]) -> int:
    return sum(1 for card_id in card_ids if (get_duel_card(card_id) or {}).get('type') == CARD_TYPE_ESPER)


def validate_deck_card_ids(card_ids: list[str]) -> tuple[bool, str]:
    item_count = 0
    esper_count = 0
    item_copies: dict[str, int] = {}
    seen_espers: set[str] = set()
    for card_id in card_ids:
        definition = get_duel_card(card_id)
        if definition is None:
            return False, '牌组中包含未知卡牌。'
        card_type = definition.get('type')
        if card_type == CARD_TYPE_ANOMALY_ITEM:
            item_count += 1
            item_copies[card_id] = int(item_copies.get(card_id, 0)) + 1
            if item_copies[card_id] > 3:
                return False, '同名异象道具最多携带 3 张。'
        elif card_type == CARD_TYPE_ESPER:
            if card_id in seen_espers:
                return False, '异能者编队不能携带重复角色。'
            seen_espers.add(card_id)
            esper_count += 1
        else:
            return False, '临时牌不能放入构筑。'
    if item_count < MIN_DECK_SIZE:
        return False, f'异象道具至少携带 {MIN_DECK_SIZE} 张。'
    if item_count > MAX_DECK_SIZE:
        return False, f'异象道具最多携带 {MAX_DECK_SIZE} 张。'
    if esper_count > MAX_ESPER_CARDS_PER_DECK:
        return False, f'一套卡组最多只能携带 {MAX_ESPER_CARDS_PER_DECK} 张异能者卡牌。'
    return True, ''


def _definition_by_id(card_id: str) -> JsonDict:
    return get_duel_card(card_id) or {}


def _build_token_instance(state: JsonDict, side: str, token_id: str, *, revealed: bool) -> JsonDict:
    definition = TOKEN_CARDS[token_id]
    token_index = int(state.setdefault('token_counter', 0)) + 1
    state['token_counter'] = token_index
    return {
        'instance_id': f'{token_id}-{side}-{state.get("turn", 0)}-{token_index}',
        'definition_id': definition['id'],
        'name': definition['name'],
        'type': definition.get('type', CARD_TYPE_TOKEN),
        'cost': int(definition['cost']),
        'cost_modifier': 0,
        'base_power': int(definition['power']),
        'bonus_power': 0,
        'computed_power': int(definition['power']),
        'element': definition.get('element', ''),
        'rarity': definition.get('rarity', 'token'),
        'art': definition.get('art', CARD_BACK_IMAGE),
        'side': side,
        'revealed': revealed,
        'played_turn': state.get('turn') if revealed else None,
        'location_id': None,
        'description': definition.get('description', ''),
        'category': definition.get('category', ''),
        'attribute': definition.get('attribute', ''),
        'attribute_icon': definition.get('attribute_icon', ''),
        'material_tags': list(definition.get('material_tags', [])),
        'material_cost': int(definition.get('material_cost') or 0),
        'tags': list(definition.get('tags', [])),
    }


def _create_token_at_location(context: 'EventContext', token_id: str, *, side: str | None = None) -> bool:
    return _create_token_in_location(
        context.state,
        context.payload['location'],
        side or str(context.payload['side']),
        token_id,
    )


def _create_tokens_at_location(context: 'EventContext', token_id: str, *, count: int, side: str | None = None) -> int:
    created = 0
    for _ in range(max(0, count)):
        if not _create_token_at_location(context, token_id, side=side):
            break
        created += 1
    return created


def _create_token_in_location(state: JsonDict, location: JsonDict, side: str, token_id: str) -> bool:
    mark_tag = LOCATION_MARK_TOKENS.get(token_id)
    if mark_tag:
        _add_location_mark(state, location, side, mark_tag)
        return True
    if len(location['cards'][side]) >= LOCATION_CARD_LIMIT:
        return False
    token = _build_token_instance(state, side, token_id, revealed=True)
    token['location_id'] = location['id']
    location['cards'][side].append(token)
    _append_spawn_action(state, location, side, token)
    return True


def _append_spawn_action(state: JsonDict, location: JsonDict, side: str, token: JsonDict) -> None:
    source_instance_id = str(state.get('_active_reveal_source_instance_id') or '')
    if not source_instance_id:
        return
    source_name = str(state.get('_active_reveal_source_name') or '效果')
    state.setdefault('action_queue', []).append({
        'kind': 'spawn_card',
        'source_instance_id': source_instance_id,
        'target_instance_id': token['instance_id'],
        'location_id': location['id'],
        'side': side,
        'title': f'{source_name} 生成 {token["name"]}',
        'subtitle': f'{token["name"]} 进入 {location["name"]}',
    })


def _add_location_mark(state: JsonDict, location: JsonDict, side: str, tag: str, amount: int = 1) -> int:
    if amount <= 0:
        return _location_mark_count(location, side, tag)
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    mark_bucket[tag] = max(0, int(mark_bucket.get(tag, 0)) + amount)
    _append_mark_action(state, location, side, tag, amount)
    return int(mark_bucket[tag])


def _consume_location_mark(location: JsonDict, side: str, tag: str, amount: int = 1) -> int:
    mark_bucket = location.setdefault('marks', {}).setdefault(side, {})
    current = int(mark_bucket.get(tag, 0))
    consumed = min(current, max(0, amount))
    if consumed <= 0:
        return 0
    remaining = current - consumed
    if remaining:
        mark_bucket[tag] = remaining
    else:
        mark_bucket.pop(tag, None)
    return consumed


def _location_mark_count(location: JsonDict, side: str, tag: str) -> int:
    return int(location.get('marks', {}).get(side, {}).get(tag, 0) or 0)


def _append_mark_action(state: JsonDict, location: JsonDict, side: str, tag: str, amount: int) -> None:
    source_instance_id = str(state.get('_active_reveal_source_instance_id') or '')
    if not source_instance_id:
        return
    source_name = str(state.get('_active_reveal_source_name') or '效果')
    mark_name = LOCATION_MARK_NAMES.get(tag, tag)
    state.setdefault('action_queue', []).append({
        'kind': 'spawn_mark',
        'source_instance_id': source_instance_id,
        'source_location_id': location['id'],
        'location_id': location['id'],
        'side': side,
        'mark': tag,
        'amount': amount,
        'mark_count': _location_mark_count(location, side, tag),
        'title': f'{source_name} 标记 {mark_name}',
        'subtitle': f'{mark_name} x{_location_mark_count(location, side, tag)}',
    })


def _add_token_to_hand(context: 'EventContext', token_id: str, *, side: str | None = None, count: int = 1) -> int:
    target_side = side or str(context.payload['side'])
    side_state = context.state['sides'][target_side]
    added = 0
    for _ in range(max(0, count)):
        if len(side_state['hand']) >= MAX_HAND_SIZE:
            break
        side_state['hand'].append(_build_token_instance(context.state, target_side, token_id, revealed=False))
        added += 1
    return added


def _revealed_cards(location: JsonDict, side: str) -> list[JsonDict]:
    return [card for card in location['cards'][side] if card.get('revealed')]


def _lowest_ally(context: 'EventContext') -> JsonDict | None:
    allies = [
        card
        for card in _revealed_cards(context.payload['location'], str(context.payload['side']))
        if card['instance_id'] != context.payload['card']['instance_id']
    ]
    return min(allies, key=_raw_card_power) if allies else None


def _selected_or_highest_opponent(context: 'EventContext') -> JsonDict | None:
    opponent = str(context.payload['opponent_side'])
    selected_target = context.payload.get('target_card')
    if isinstance(selected_target, dict) and selected_target.get('side') == opponent:
        return selected_target
    candidates = _revealed_cards(context.payload['location'], opponent)
    return max(candidates, key=_raw_card_power) if candidates else None


def _boost_location_cards(
    location: JsonDict,
    side: str,
    amount: int,
    source_name: str,
    *,
    ignore_tokens: bool = False,
) -> int:
    count = 0
    for card in _revealed_cards(location, side):
        if ignore_tokens and card.get('type') == CARD_TYPE_TOKEN:
            continue
        _boost_card(card, amount, source_name)
        count += 1
    return count


def _boost_card(card: JsonDict, amount: int, source_name: str = '效果') -> None:
    card['bonus_power'] = int(card.get('bonus_power', 0)) + amount
    card['computed_power'] = _raw_card_power(card)
    _add_buff_source(card, source_name, amount)


def _add_buff_source(card: JsonDict, source_name: str, amount: int) -> None:
    if amount == 0:
        return
    sources = card.setdefault('buff_sources', [])
    sources.append({
        'name': str(source_name or '效果'),
        'amount': int(amount),
        'key': '',
    })
    del sources[8:]


def _raw_card_power(card: JsonDict) -> int:
    return int(card.get('base_power', 0)) + int(card.get('bonus_power', 0))


def _adjacent_locations(state: JsonDict, index: int) -> list[JsonDict]:
    return [
        location
        for current_index, location in enumerate(state.get('locations', []))
        if abs(current_index - index) == 1
    ]


def _location_by_id(state: JsonDict, location_id: str) -> JsonDict | None:
    for location in state.get('locations', []):
        if location.get('id') == location_id:
            return location
    return None


def _count_location_tag(location: JsonDict, side: str, tag: str) -> int:
    base_count = _location_mark_count(location, side, tag) + sum(
        1
        for card in location['cards'][side]
        if card.get('revealed') and tag in card.get('tags', [])
    )
    if not tag.startswith('mat_'):
        return base_count
    consumed_count = sum(
        1
        for card in location['cards'][side]
        if card.get('revealed')
        for consumed_tag in card.get('consumed_material_tags', [])
        if consumed_tag == tag
    )
    return base_count + consumed_count


def _count_location_any_tag(location: JsonDict, side: str, tags: list[str]) -> int:
    target_tags = set(tags)
    base_count = sum(_location_mark_count(location, side, tag) for tag in target_tags) + sum(
        1
        for card in location['cards'][side]
        if card.get('revealed') and target_tags.intersection(card.get('tags', []))
    )
    material_tags = {tag for tag in target_tags if str(tag).startswith('mat_')}
    if not material_tags:
        return base_count
    consumed_count = sum(
        1
        for card in location['cards'][side]
        if card.get('revealed')
        for consumed_tag in card.get('consumed_material_tags', [])
        if consumed_tag in material_tags
    )
    return base_count + consumed_count


def _count_board_tag(state: JsonDict, side: str, tag: str) -> int:
    return sum(_count_location_tag(location, side, tag) for location in state.get('locations', []))


def _count_board_any_tag(state: JsonDict, side: str, tags: list[str]) -> int:
    return sum(_count_location_any_tag(location, side, tags) for location in state.get('locations', []))


def _count_hand_tag(state: JsonDict, side: str, tag: str) -> int:
    return sum(1 for card in state['sides'][side].get('hand', []) if tag in card.get('tags', []))


def _add_combo_counter(state: JsonDict, side: str, key: str, amount: int) -> int:
    combo = state['sides'][side].setdefault('combo', {})
    combo[key] = int(combo.get(key, 0)) + amount
    return int(combo[key])


def _draw_one_from_deck(state: JsonDict, side: str) -> JsonDict | None:
    side_state = state['sides'][side]
    if not side_state.get('deck') or len(side_state.get('hand', [])) >= MAX_HAND_SIZE:
        return None
    card = side_state['deck'].pop(0)
    side_state['hand'].append(card)
    _append_draw_action(state, side, card, '抽牌')
    return card


def _append_draw_action(state: JsonDict, side: str, card: JsonDict, title: str) -> None:
    action: JsonDict = {
        'kind': 'draw_card',
        'side': side,
        'card_instance_id': card['instance_id'],
        'title': title or '抽牌',
        'subtitle': '从牌库加入手牌',
        'reason': title or '抽牌',
        'silent': False,
        'card': _action_card_payload(card),
    }
    source_instance_id = str(state.get('_active_reveal_source_instance_id') or '')
    if source_instance_id:
        action['source_instance_id'] = source_instance_id
    state.setdefault('action_queue', []).append(action)


def _action_card_payload(card: JsonDict) -> JsonDict:
    return {
        'instance_id': card.get('instance_id'),
        'definition_id': card.get('definition_id'),
        'hidden': False,
        'revealed': card.get('revealed', False),
        'staged': bool(card.get('staged')),
        'name': card.get('name', ''),
        'type': card.get('type', CARD_TYPE_ANOMALY_ITEM),
        'cost': int(card.get('cost') or 0) + int(card.get('cost_modifier') or 0),
        'base_cost': int(card.get('cost') or 0),
        'original_cost': int(card.get('cost') or 0),
        'power': int(card.get('computed_power', _raw_card_power(card)) or 0),
        'base_power': int(card.get('base_power') or 0),
        'original_power': int(card.get('base_power') or 0),
        'bonus_power': int(card.get('bonus_power') or 0),
        'element': card.get('element', ''),
        'rarity': card.get('rarity', 'n'),
        'art': card.get('art', CARD_BACK_IMAGE),
        'description': card.get('description', ''),
        'archetype': card.get('archetype', ''),
        'category': card.get('category', ''),
        'attribute': card.get('attribute', ''),
        'attribute_icon': card.get('attribute_icon', ''),
        'material_cost': int(card.get('material_cost') or 0),
        'required_material_attribute': card.get('required_material_attribute', ''),
        'material_requirements': deepcopy(card.get('material_requirements') or []),
        'material_requirement_text': card.get('material_requirement_text', ''),
        'material_tags': list(card.get('material_tags', [])),
        'buff_sources': [deepcopy(source) for source in card.get('buff_sources', [])],
    }


def _add_log(state: JsonDict, message: str) -> None:
    state.setdefault('log', [])
    state['log'].insert(0, message)
    del state['log'][LOG_LIMIT:]
