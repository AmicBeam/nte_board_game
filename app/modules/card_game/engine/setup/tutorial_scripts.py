from __future__ import annotations

from copy import deepcopy

from app.modules.card_game.engine.state.types import JsonDict

SIDE_A = 'a'
SIDE_B = 'b'
SIDE_KEYS = (SIDE_A, SIDE_B)
TUTORIAL_BASICS_SCENARIO = 'tutorial_basics'
TUTORIAL_SCENARIO_ALIASES = {'tutorial', TUTORIAL_BASICS_SCENARIO}

TUTORIAL_PLAYER_HAND = [
    'tutorial_refresh_charge',
]

TUTORIAL_PLAYER_DECK = [
    'tutorial_urban_energy',
    'tutorial_water_hesitation',
    'tutorial_fons',
    'tutorial_lost_wallet',
    'tutorial_marble_soda',
    'tutorial_breakfast_bag',
    'tutorial_eborn_cake',
    'tutorial_fons',
    'tutorial_urban_energy',
    'tutorial_breakfast_bag',
]

TUTORIAL_PLAYER_ESPERS = [
    'tutorial_appraiser',
    'tutorial_bohe',
]

TUTORIAL_OPPONENT_HAND = [
    'tutorial_tomato_dummy',
    'tutorial_recruit_fear',
]

TUTORIAL_OPPONENT_DECK = [
    'tutorial_tomato_dummy',
    'tutorial_recruit_fear',
    'tutorial_tomato_dummy',
    'tutorial_recruit_fear',
    'tutorial_tomato_dummy',
    'tutorial_recruit_fear',
]

TUTORIAL_OPPONENT_ACTIONS_BY_TURN = {
    2: ['tutorial_tomato_dummy'],
    3: ['tutorial_recruit_fear'],
}

TUTORIAL_EXPECTED_ACTIONS_BY_TURN = {
    1: [
        {'kind': 'play_card', 'definition_id': 'tutorial_refresh_charge'},
    ],
    2: [
        {'kind': 'play_card', 'definition_id': 'tutorial_urban_energy'},
    ],
    3: [
        {
            'kind': 'play_esper',
            'definition_id': 'tutorial_appraiser',
            'material_definition_ids': {'tutorial_refresh_charge', 'tutorial_urban_energy'},
        },
        {
            'kind': 'play_card',
            'definition_id': 'tutorial_water_hesitation',
            'target_definition_id': 'tutorial_tomato_dummy',
        },
        {'kind': 'play_card', 'definition_id': 'tutorial_breakfast_bag'},
    ],
    4: [
        {'kind': 'play_card', 'definition_id': 'tutorial_fons'},
        {'kind': 'play_card', 'definition_id': 'tutorial_eborn_cake'},
    ],
    5: [
        {
            'kind': 'play_esper',
            'definition_id': 'tutorial_appraiser',
            'material_definition_ids': {'tutorial_fons', 'tutorial_eborn_cake'},
        },
        {'kind': 'play_card', 'definition_id': 'tutorial_lost_wallet'},
    ],
    6: [
        {
            'kind': 'play_esper',
            'definition_id': 'tutorial_bohe',
            'material_definition_ids': {'tutorial_lost_wallet'},
        },
    ],
}

TUTORIAL_EXPECTED_DECLARATIONS_BY_TURN = {
    2: {
        'tutorial_urban_energy': {'tutorial_breakfast_bag'},
    },
    3: {
        'tutorial_breakfast_bag': {'tutorial_eborn_cake'},
    },
}


def is_tutorial_basics(snapshot_or_scenario: JsonDict | object) -> bool:
    if isinstance(snapshot_or_scenario, dict):
        scenario = str(snapshot_or_scenario.get('scenario') or '')
    else:
        scenario = str(snapshot_or_scenario or '')
    return scenario == TUTORIAL_BASICS_SCENARIO


def normalize_tutorial_scenario(scenario: str) -> str:
    return TUTORIAL_BASICS_SCENARIO if scenario in TUTORIAL_SCENARIO_ALIASES else scenario


def tutorial_visible_esper_ids(snapshot: JsonDict, side: str) -> set[str]:
    if not is_tutorial_basics(snapshot) or side != SIDE_A:
        return set()
    turn = int(snapshot.get('turn') or 1)
    if turn >= 4:
        return {'tutorial_appraiser', 'tutorial_bohe'}
    if turn >= 3:
        return {'tutorial_appraiser'}
    return set()


def tutorial_opponent_action_ids(snapshot: JsonDict) -> list[str]:
    if not is_tutorial_basics(snapshot):
        return []
    return list(TUTORIAL_OPPONENT_ACTIONS_BY_TURN.get(int(snapshot.get('turn') or 0), []))


def tutorial_plan_error(
    snapshot: JsonDict,
    side: str,
    planning_actions: list[JsonDict] | None,
    declaration_choices: list[JsonDict] | None,
) -> str:
    if not is_tutorial_basics(snapshot) or side != SIDE_A:
        return ''
    turn = int(snapshot.get('turn') or 1)
    expected_actions = TUTORIAL_EXPECTED_ACTIONS_BY_TURN.get(turn, [])
    actions = [action for action in (planning_actions or []) if isinstance(action, dict)]
    if len(actions) != len(expected_actions):
        return tutorial_turn_action_hint(turn)
    for index, expected in enumerate(expected_actions):
        action = actions[index]
        if str(action.get('kind') or '') != expected['kind']:
            return tutorial_turn_action_hint(turn)
        source_definition_id = _tutorial_action_definition_id(snapshot, side, action)
        if source_definition_id != expected['definition_id']:
            return tutorial_turn_action_hint(turn)
        expected_materials = expected.get('material_definition_ids')
        if expected_materials is not None:
            actual_materials = {
                _tutorial_card_definition_id(snapshot, str(material_id))
                for material_id in action.get('material_instance_ids', [])
                if str(material_id)
            }
            if actual_materials != set(expected_materials):
                return tutorial_turn_action_hint(turn)
        expected_target = expected.get('target_definition_id')
        if expected_target:
            actual_target = _tutorial_card_definition_id(snapshot, str(action.get('selected_target_instance_id') or ''))
            if actual_target != expected_target:
                return tutorial_turn_action_hint(turn)
    return _tutorial_declaration_error(snapshot, side, turn, declaration_choices)


def tutorial_turn_action_hint(turn: int) -> str:
    hints = {
        1: '教学第 1 回合请只部署「畅爽焕能」，然后点击完成部署。',
        2: '教学第 2 回合请部署「都市活力」，并宣言「速食早餐袋」。',
        3: '教学第 3 回合请依次让鉴定师共鸣、部署「水波的迟疑」指向西红柿，再部署「速食早餐袋」宣言蛋糕。',
        4: '教学第 4 回合请部署「方斯」和来自「伊波恩」的蛋糕，等待它们稳定入场。',
        5: '教学第 5 回合请再次让鉴定师共鸣，消耗「方斯」和蛋糕，再部署「遗失的钱包」。',
        6: '教学第 6 回合请让薄荷消耗「遗失的钱包」登场。',
    }
    return hints.get(turn, '请按照当前教学提示完成固定操作。')


def _tutorial_declaration_error(
    snapshot: JsonDict,
    side: str,
    turn: int,
    declaration_choices: list[JsonDict] | None,
) -> str:
    expected = TUTORIAL_EXPECTED_DECLARATIONS_BY_TURN.get(turn, {})
    choices = [choice for choice in (declaration_choices or []) if isinstance(choice, dict)]
    if len(choices) != len(expected):
        return tutorial_turn_action_hint(turn)
    for choice in choices:
        source_definition_id = _tutorial_card_definition_id(snapshot, str(choice.get('source_instance_id') or ''))
        expected_selected = expected.get(source_definition_id)
        if expected_selected is None:
            return tutorial_turn_action_hint(turn)
        actual_selected = {
            _tutorial_card_definition_id(snapshot, str(card_id))
            for card_id in choice.get('card_instance_ids', [])
            if str(card_id)
        }
        if actual_selected != set(expected_selected):
            return tutorial_turn_action_hint(turn)
    return ''


def _tutorial_action_definition_id(snapshot: JsonDict, side: str, action: JsonDict) -> str:
    card_id = str(action.get('card_instance_id') or '')
    return _tutorial_card_definition_id(snapshot, card_id, side=side)


def _tutorial_card_definition_id(snapshot: JsonDict, instance_id: str, *, side: str | None = None) -> str:
    wanted = str(instance_id or '')
    if not wanted:
        return ''
    sides = [side] if side else SIDE_KEYS
    for current_side in sides:
        side_state = snapshot.get('sides', {}).get(current_side, {})
        zones = [
            side_state.get('hand', []),
            side_state.get('deck', []),
            side_state.get('discard', []),
            side_state.get('esper_standby', []),
        ]
        for zone in zones:
            for card in zone or []:
                if str(card.get('instance_id') or '') == wanted:
                    return str(card.get('definition_id') or '')
    for location in snapshot.get('locations', []):
        for current_side in sides:
            for card in location.get('cards', {}).get(current_side, []) or []:
                if str(card.get('instance_id') or '') == wanted:
                    return str(card.get('definition_id') or '')
    return ''


def tutorial_locations() -> list[JsonDict]:
    return [{
        'id': 'main_battlefield',
        'trait_id': 'tutorial_training_ground',
        'name': '战场：教学演习场',
        'short_name': '战场',
        'description': '教学固定战场：没有额外战场特性，专注学习部署、揭示、宣言、素材、共鸣与战力结算。',
        'reveal_turn': 1,
        'effect': 'none',
        'revealed': False,
        'capacity': 10,
        'cards': {SIDE_A: [], SIDE_B: []},
        'marks': {SIDE_A: {}, SIDE_B: {}},
        'power': {SIDE_A: 0, SIDE_B: 0},
        'winner_side': None,
    }]


def tutorial_public_prompt(snapshot: JsonDict, side: str) -> JsonDict | None:
    if not is_tutorial_basics(snapshot) or side != SIDE_A:
        return None
    if snapshot.get('status') != 'playing':
        return {
            'title': '教学完成',
            'body': '查看战场总战力。你已经用部署、宣言、解场、共鸣、创生和薄荷爆发赢下固定对局。',
            'spotlights': ['.locations-board', '.right-resource-grid'],
        }
    side_state = snapshot.get('sides', {}).get(side, {})
    if side_state.get('selection'):
        selection = side_state.get('selection') or {}
        return {
            'title': '完成宣言',
            'body': str(selection.get('description') or '选择本次宣言牌；揭示阶段会执行已经锁定的选择。'),
            'spotlights': ['#selection-overlay'],
        }
    if side_state.get('pending_target'):
        pending = side_state.get('pending_target') or {}
        return {
            'title': '选择目标',
            'body': str(pending.get('prompt') or '选择一个表侧目标；背面和未揭示的牌不能成为目标。'),
            'spotlights': ['.opponent-slots', '#selection-overlay'],
        }
    if side_state.get('ended_turn'):
        return {
            'title': '等待揭示',
            'body': '你已经完成部署。双方完成部署后，本回合会按回合开始锁定的结算先手依次揭示。',
            'spotlights': ['#end-turn-btn', '.locations-board'],
        }
    turn = int(snapshot.get('turn') or 1)
    prompts = {
        1: {
            'title': '第 1 回合：部署与揭示',
            'body': '拖动唯一手牌「畅爽焕能」到战场，然后点击「完成部署」。它会先盖放，双方完成部署后再揭示。',
            'spotlights': ['#hand-list', '.locations-board', '#end-turn-btn'],
        },
        2: {
            'title': '第 2 回合：宣言检视',
            'body': '部署「都市活力」，在宣言窗口选择「速食早餐袋」。宣言会先锁定，揭示时才把牌加入手牌。',
            'spotlights': ['#hand-list', '#selection-overlay', '#end-turn-btn'],
        },
        3: {
            'title': '第 3 回合：鉴定师共鸣',
            'body': '先让鉴定师在战场共鸣，选择「畅爽焕能」和「都市活力」作为素材；再部署「水波的迟疑」解掉西红柿，并部署「速食早餐袋」宣言蛋糕。',
            'spotlights': ['#esper-standby-list', '.locations-board', '#hand-list'],
        },
        4: {
            'title': '第 4 回合：被拖慢一回合',
            'body': '薄荷已经可见，但场上没有稳定灵属性素材。先部署「方斯」和「来自「伊波恩」的蛋糕」，等它们揭示后再继续。',
            'spotlights': ['#esper-standby-list', '#hand-list', '.locations-board'],
        },
        5: {
            'title': '第 5 回合：鉴定师共鸣',
            'body': '再次让场上的鉴定师共鸣，消耗「方斯」和蛋糕设置第二层创生；随后部署「遗失的钱包」给薄荷准备灵属性素材。',
            'spotlights': ['.player-slots', '#hand-list', '#end-turn-btn'],
        },
        6: {
            'title': '第 6 回合：薄荷终结',
            'body': '让薄荷登场，消耗「遗失的钱包」作为素材。揭示时薄荷会一次性消耗两个创生并大幅提高战力。',
            'spotlights': ['#esper-standby-list', '.location-marks', '#end-turn-btn'],
        },
    }
    return deepcopy(prompts.get(turn) or prompts[6])
