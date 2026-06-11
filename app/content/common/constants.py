from __future__ import annotations

from typing import Any

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
TAG_ZHUE_HUCHI = 'zhue_huchi'
TAG_NIGHTMARE = 'nightmare'
TAG_PANYU_QIU = 'panyu_qiu'
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
    TAG_ZHUE_HUCHI: '诛恶护持',
    TAG_NIGHTMARE: '噩梦',
    TAG_PANYU_QIU: '判予秋',
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


__all__ = [name for name in globals() if not name.startswith('__') and name != 'Any']
