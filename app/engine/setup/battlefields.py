from __future__ import annotations

from app.engine.state.types import JsonDict

BATTLEFIELD_TRAITS: list[JsonDict] = [
    {
        'id': 'mirror_archive',
        'name': '镜像档案馆',
        'short_name': '档案馆',
        'reveal_turn': 1,
        'description': '每边在此空间揭示的第一张牌 +2 战力。',
        'effect': 'first_card_plus_two',
    },
    {
        'id': 'tide_platform',
        'name': '潮汐站台',
        'short_name': '站台',
        'reveal_turn': 2,
        'description': '揭示前本方不领先时，每方每回合前 3 张在此空间揭示的牌永久 +1 战力。',
        'effect': 'revealed_cards_plus_one',
    },
    {
        'id': 'hollow_theater',
        'name': '空洞剧场',
        'short_name': '剧场',
        'reveal_turn': 3,
        'description': '如果一边只有 1 张牌在此空间，那张牌 +4 战力。',
        'effect': 'solo_card_plus_four',
    },
]

LOCATION_LIBRARY: list[JsonDict] = BATTLEFIELD_TRAITS
