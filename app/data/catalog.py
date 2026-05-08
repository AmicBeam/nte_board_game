from copy import deepcopy
from typing import Any

DEFAULT_DECK_SIZE = 6
STARTING_HAND_SIZE = 3
LOG_LIMIT = 16

CHARACTERS = [
    {
        'id': 'signal_runner',
        'name': 'Signal Runner',
        'title': 'Urban Route Hacker',
        'max_hp': 42,
        'attack': 11,
        'defense': 4,
        'passive': 'Gain 1 defense when opening a chest.',
    },
    {
        'id': 'phase_striker',
        'name': 'Phase Striker',
        'title': 'Close-Range Duel Specialist',
        'max_hp': 36,
        'attack': 14,
        'defense': 3,
        'passive': 'Deal +1 damage in every direct battle exchange.',
    },
    {
        'id': 'vault_mender',
        'name': 'Vault Mender',
        'title': 'Sustain and Utility Expert',
        'max_hp': 48,
        'attack': 9,
        'defense': 5,
        'passive': 'Recover 2 HP after event tiles trigger.',
    },
    {
        'id': 'vector_scout',
        'name': 'Vector Scout',
        'title': 'Route Planning Navigator',
        'max_hp': 38,
        'attack': 10,
        'defense': 4,
        'passive': 'Gain +1 move whenever a turn belt redirects movement.',
    },
]

CARDS = [
    {
        'id': 'blaze_drive',
        'name': 'Blaze Drive',
        'type': 'Attack',
        'rarity': 'Rare',
        'description': 'Gain +3 attack this turn.',
    },
    {
        'id': 'guard_matrix',
        'name': 'Guard Matrix',
        'type': 'Defense',
        'rarity': 'Common',
        'description': 'Gain +2 defense this turn.',
    },
    {
        'id': 'pulse_repair',
        'name': 'Pulse Repair',
        'type': 'Recovery',
        'rarity': 'Common',
        'description': 'Recover 6 HP immediately.',
    },
    {
        'id': 'dash_patch',
        'name': 'Dash Patch',
        'type': 'Mobility',
        'rarity': 'Common',
        'description': 'Gain +2 move this turn.',
    },
    {
        'id': 'key_fabricator',
        'name': 'Key Fabricator',
        'type': 'Utility',
        'rarity': 'Rare',
        'description': 'Create 1 key for locked doors.',
    },
    {
        'id': 'remote_charge',
        'name': 'Remote Charge',
        'type': 'Utility',
        'rarity': 'Rare',
        'description': 'Deal 5 damage to the nearest enemy within 2 tiles.',
    },
    {
        'id': 'emergency_roll',
        'name': 'Emergency Roll',
        'type': 'Dice',
        'rarity': 'Epic',
        'description': 'Reroll the current die once.',
    },
    {
        'id': 'route_scan',
        'name': 'Route Scan',
        'type': 'Intel',
        'rarity': 'Common',
        'description': 'Reveal a route hint and gain 1 move this turn.',
    },
    {
        'id': 'phase_shield',
        'name': 'Phase Shield',
        'type': 'Defense',
        'rarity': 'Epic',
        'description': 'Block the next 4 incoming damage this turn.',
    },
]

SAMPLE_MAP = {
    'name': 'Lower Relay District',
    'width': 8,
    'height': 6,
    'start': {'x': 0, 'y': 0},
    'tiles': [
        {'x': 2, 'y': 0, 'type': 'turn_belt', 'direction': 'down', 'label': 'Belt'},
        {'x': 1, 'y': 1, 'type': 'wall', 'label': 'Wall'},
        {'x': 5, 'y': 1, 'type': 'portal', 'target': {'x': 0, 'y': 4}, 'label': 'Portal A'},
        {'x': 0, 'y': 4, 'type': 'portal', 'target': {'x': 5, 'y': 1}, 'label': 'Portal B'},
        {'x': 2, 'y': 2, 'type': 'chest', 'loot_table': ['heal', 'attack', 'key'], 'label': 'Chest'},
        {'x': 4, 'y': 2, 'type': 'event', 'event_kind': 'shrine', 'label': 'Shrine'},
        {'x': 1, 'y': 3, 'type': 'turn_belt', 'direction': 'right', 'label': 'Belt'},
        {'x': 3, 'y': 3, 'type': 'door', 'locked': True, 'label': 'Locked Door'},
        {'x': 7, 'y': 3, 'type': 'wall', 'label': 'Wall'},
        {'x': 2, 'y': 4, 'type': 'event', 'event_kind': 'forge', 'label': 'Forge'},
        {'x': 5, 'y': 5, 'type': 'boss_tile', 'label': 'Boss Zone'},
        {'x': 6, 'y': 5, 'type': 'boss_tile', 'label': 'Boss Zone'},
        {'x': 5, 'y': 4, 'type': 'boss_tile', 'label': 'Boss Zone'},
        {'x': 6, 'y': 4, 'type': 'boss_tile', 'label': 'Boss Zone'},
    ],
    'monsters': [
        {
            'id': 'sweeper_alpha',
            'name': 'Sweeper Alpha',
            'x': 3,
            'y': 1,
            'max_hp': 18,
            'hp': 18,
            'attack': 8,
            'defense': 2,
            'range': 1,
            'kind': 'monster',
        },
        {
            'id': 'watcher_beta',
            'name': 'Watcher Beta',
            'x': 1,
            'y': 4,
            'max_hp': 16,
            'hp': 16,
            'attack': 7,
            'defense': 1,
            'range': 2,
            'kind': 'monster',
        },
        {
            'id': 'crusher_gamma',
            'name': 'Crusher Gamma',
            'x': 4,
            'y': 4,
            'max_hp': 24,
            'hp': 24,
            'attack': 10,
            'defense': 3,
            'range': 1,
            'kind': 'monster',
        },
    ],
    'boss': {
        'id': 'abyss_core',
        'name': 'Abyss Core',
        'positions': [
            {'x': 5, 'y': 4},
            {'x': 6, 'y': 4},
            {'x': 5, 'y': 5},
            {'x': 6, 'y': 5},
        ],
        'max_hp': 60,
        'hp': 60,
        'attack': 12,
        'defense': 4,
        'range': 1,
        'kind': 'boss',
    },
}


def get_character_catalog() -> list[dict[str, Any]]:
    return deepcopy(CHARACTERS)


def get_card_catalog() -> list[dict[str, Any]]:
    return deepcopy(CARDS)


def get_character(character_id: str) -> dict[str, Any] | None:
    return next((deepcopy(item) for item in CHARACTERS if item['id'] == character_id), None)


def get_card(card_id: str) -> dict[str, Any] | None:
    return next((deepcopy(item) for item in CARDS if item['id'] == card_id), None)


def get_sample_map() -> dict[str, Any]:
    return deepcopy(SAMPLE_MAP)
