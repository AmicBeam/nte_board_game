from __future__ import annotations

from app.engine.state.types import JsonDict

BATTLEFIELD_TRAITS: list[JsonDict] = [
    {
        'id': 'mirror_archive',
        'name': '本初环线',
        'short_name': '本初',
        'reveal_turn': 1,
        'description': '每边在此环线揭示的第一张牌 +2 战力。',
        'effect': 'first_card_plus_two',
    },
    {
        'id': 'tide_platform',
        'name': '未明环线',
        'short_name': '未明',
        'reveal_turn': 2,
        'description': '揭示前本方不领先时，每方每回合前 3 张在此环线揭示的牌永久 +1 战力。',
        'effect': 'revealed_cards_plus_one',
    },
    {
        'id': 'hollow_theater',
        'name': '呼啸环线',
        'short_name': '呼啸',
        'reveal_turn': 3,
        'description': '如果一边只有 1 张牌在此环线，那张牌 +4 战力。',
        'effect': 'solo_card_plus_four',
    },
]

LOCATION_LIBRARY: list[JsonDict] = BATTLEFIELD_TRAITS
