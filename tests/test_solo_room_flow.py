import importlib
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


DEFAULT_ITEMS = [
    'genesis_urban_energy',
    'genesis_urban_energy',
    'genesis_urban_energy',
    'genesis_refresh_charge',
    'genesis_refresh_charge',
    'genesis_refresh_charge',
    'genesis_breakfast_bag',
    'genesis_breakfast_bag',
    'genesis_breakfast_bag',
    'genesis_marble_soda',
    'genesis_marble_soda',
    'genesis_eborn_cake',
    'genesis_eborn_cake',
    'genesis_eborn_cake',
    'genesis_chip_washer',
    'genesis_chip_washer',
    'genesis_nest_shard',
    'genesis_nest_shard',
    'genesis_muscle_faith',
    'genesis_muscle_faith',
]

DEFAULT_ESPERS = [
    'nanali',
    'bohe',
    'xun',
    'jiuyuan',
]


def _purge_app_modules() -> None:
    stale_modules = [
        module_name
        for module_name in sys.modules
        if module_name == 'app' or module_name.startswith('app.')
    ]
    for module_name in stale_modules:
        sys.modules.pop(module_name, None)


class RoomFlowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ['NTE_DATABASE_PATH'] = str(Path(self.temp_dir.name) / 'test.db')
        os.environ['NTE_LOG_DIR'] = str(Path(self.temp_dir.name) / 'logs')
        _purge_app_modules()

        self.app_module = importlib.import_module('app')
        self.dao_module = importlib.import_module('app.dao')
        self.db_module = importlib.import_module('app.db')
        self.app = self.app_module.create_app()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        if not self.db_module.db.is_closed():
            self.db_module.db.close()
        self.temp_dir.cleanup()
        _purge_app_modules()

    def _issue_login_and_get_token(self, player_uid: str) -> str:
        with self.db_module.atomic_transaction():
            self.dao_module.issue_mock_login(player_uid, player_uid, '654321')
        payload = self._post('/api/auth/login', {
            'player_uid': player_uid,
            'code': '654321',
        })
        return payload['token']

    def _save_default_build(self, token: str) -> None:
        self._post('/api/build/save', {
            'character_id': 'nanali',
            'item_ids': DEFAULT_ITEMS,
            'esper_card_ids': DEFAULT_ESPERS,
        }, token=token)

    def _choose_selection(self, state: dict, token: str) -> dict:
        selection = state.get('selection')
        self.assertIsInstance(selection, dict)
        pick_count = int(selection['pick_count'])
        return self._post('/api/game/choose-cards', {
            'card_instance_ids': [card['instance_id'] for card in selection['cards'][:pick_count]],
        }, token=token)

    def _choose_if_needed(self, state: dict, token: str) -> dict:
        if state.get('selection'):
            return self._choose_selection(state, token)
        return state

    def _post_error(
        self,
        path: str,
        payload: dict | None = None,
        *,
        token: str | None = None,
        expected_status: int = 400,
    ) -> dict:
        headers = self._auth_headers(token)
        response = self.client.post(path, json=payload, headers=headers)
        self.assertEqual(response.status_code, expected_status, response.get_data(as_text=True))
        data = response.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn('error', data)
        return data

    def _post(self, path: str, payload: dict | None = None, *, token: str | None = None, expected_status: int = 200) -> dict:
        headers = self._auth_headers(token)
        response = self.client.post(path, json=payload, headers=headers)
        self.assertEqual(response.status_code, expected_status, response.get_data(as_text=True))
        data = response.get_json()
        self.assertIsInstance(data, dict)
        return data

    def _get(self, path: str, *, token: str | None = None, expected_status: int = 200) -> dict:
        headers = self._auth_headers(token)
        response = self.client.get(path, headers=headers)
        self.assertEqual(response.status_code, expected_status, response.get_data(as_text=True))
        data = response.get_json()
        self.assertIsInstance(data, dict)
        return data

    def _auth_headers(self, token: str | None) -> dict[str, str]:
        if token is None:
            return {}
        return {'Authorization': f'Bearer {token}'}

    def _solo_test_run_context(self) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch('app.engine.setup.snapshot_factory.random.shuffle', side_effect=lambda value: None))
        return stack


class SoloRoomFlowTest(RoomFlowTestCase):
    def test_legacy_starter_fields_are_saved_as_plain_deck(self) -> None:
        token = self._issue_login_and_get_token('legacy-starter-build')

        self._post('/api/build/save', {
            'character_id': 'nanali',
            'starter_item_ids': DEFAULT_ITEMS[:4],
            'reserve_item_ids': DEFAULT_ITEMS[4:],
            'esper_card_ids': DEFAULT_ESPERS,
        }, token=token)

        catalog = self._get('/api/catalog', token=token)
        saved_build = catalog['saved_build']
        self.assertEqual(catalog['min_build_size'], 10)
        self.assertEqual(catalog['build_size'], 20)
        self.assertFalse(catalog['fixed_opening_hand_enabled'])
        self.assertEqual(saved_build['item_ids'], DEFAULT_ITEMS)
        self.assertEqual(saved_build['starter_item_ids'], [])
        self.assertEqual(saved_build['reserve_item_ids'], DEFAULT_ITEMS)
        self.assertEqual(saved_build['esper_card_ids'], DEFAULT_ESPERS)

    def test_legacy_starter_fields_do_not_fix_opening_hand(self) -> None:
        token = self._issue_login_and_get_token('legacy-starter-random')
        self._post('/api/build/save', {
            'character_id': 'nanali',
            'starter_item_ids': DEFAULT_ITEMS[:4],
            'reserve_item_ids': DEFAULT_ITEMS[4:],
            'esper_card_ids': DEFAULT_ESPERS,
        }, token=token)
        self._post('/api/room/create', {'mode': 'solo'}, token=token)

        def reverse_shuffle(value: list) -> None:
            value.reverse()

        with patch('app.engine.setup.snapshot_factory.random.shuffle', side_effect=reverse_shuffle):
            state = self._post('/api/room/start', token=token)

        hand_ids = [card['definition_id'] for card in state['player']['hand']]
        self.assertEqual(len(hand_ids), 4)
        self.assertEqual(hand_ids, list(reversed(DEFAULT_ITEMS[-4:])))
        self.assertNotEqual(hand_ids, DEFAULT_ITEMS[:4])

    def test_ten_card_build_starts_with_random_opening_hand(self) -> None:
        token = self._issue_login_and_get_token('ten-card-build')
        ten_card_items = DEFAULT_ITEMS[:10]
        self._post('/api/build/save', {
            'character_id': 'nanali',
            'item_ids': ten_card_items,
            'esper_card_ids': DEFAULT_ESPERS,
        }, token=token)
        self._post('/api/room/create', {'mode': 'solo'}, token=token)

        with self._solo_test_run_context():
            state = self._post('/api/room/start', token=token)

        self.assertEqual(len(state['player']['hand']), 4)
        self.assertEqual(state['player']['deck_count'], 6)

    def test_create_solo_room_and_start_run(self) -> None:
        token = self._issue_login_and_get_token('solo-room-start')
        self._save_default_build(token)

        room_payload = self._post('/api/room/create', {'mode': 'solo'}, token=token)
        room_code = room_payload['room_code']
        self.assertEqual(room_payload['mode'], 'solo')
        self.assertEqual(room_payload['status'], 'ready')
        self.assertEqual(len(room_payload['members']), 1)
        self.assertTrue(room_payload['members'][0]['is_host'])
        self.assertTrue(room_payload['members'][0]['is_ready'])

        with self._solo_test_run_context():
            run_payload = self._post('/api/room/start', token=token)

        self.assertEqual(run_payload['status'], 'playing')
        self.assertEqual(run_payload['game_id'], 'anomaly_snap_duel')
        self.assertEqual(run_payload['room']['mode'], 'solo')
        self.assertEqual(run_payload['room']['room_code'], room_code)
        self.assertEqual(run_payload['turn'], 1)
        self.assertEqual(run_payload['phase'], 'planning')
        self.assertIsNone(run_payload['selection'])
        self.assertEqual(len(run_payload['player']['hand']), 4)
        self.assertEqual(run_payload['player']['deck_count'], 16)
        self.assertEqual(run_payload['turn_energy'], 1)
        self.assertEqual(run_payload['energy_remaining'], 1)
        self.assertFalse(run_payload['can_undo_turn'])
        self.assertEqual(run_payload['player_seat'], 'a')
        self.assertTrue(run_payload['opponent']['is_ai'])
        self.assertEqual(len(run_payload['locations']), 1)
        self.assertEqual(run_payload['locations'][0]['id'], 'main_battlefield')
        constants = importlib.import_module('app.content.common.constants')
        self.assertEqual(constants.LOCATION_CARD_LIMIT, 10)
        self.assertEqual(run_payload['locations'][0]['capacity'], constants.LOCATION_CARD_LIMIT)
        self.assertEqual(run_payload['current_actor_uid'], 'solo-room-start')

        room_state = self._get('/api/room/state', token=token)
        self.assertEqual(room_state['room_code'], room_code)
        self.assertEqual(room_state['status'], 'playing')
        self.assertEqual(room_state['run_status'], 'playing')

    def test_chip_washer_requires_ally_item_target_before_deploying(self) -> None:
        token = self._issue_login_and_get_token('solo-chip-washer-target')
        self._post('/api/build/save', {
            'character_id': 'nanali',
            'item_ids': DEFAULT_ITEMS,
            'esper_card_ids': DEFAULT_ESPERS,
        }, token=token)
        self._post('/api/room/create', {'mode': 'solo'}, token=token)

        def chip_washer_first(value: list) -> None:
            value.sort(key=lambda card: 0 if card.get('definition_id') == 'genesis_chip_washer' else 1)

        with patch('app.engine.setup.snapshot_factory.random.shuffle', side_effect=chip_washer_first):
            self._post('/api/room/start', token=token)
            state = self._post('/api/game/end-turn', token=token)

        washer = next(
            card for card in state['player']['hand']
            if card.get('definition_id') == 'genesis_chip_washer'
        )
        error = self._post_error('/api/game/play-card', {
            'card_instance_id': washer['instance_id'],
            'location_id': state['locations'][0]['id'],
        }, token=token)

        self.assertIn('需要可选择的己方道具', error['error'])
        state_after = self._get('/api/game/state', token=token)
        self.assertTrue(any(card['instance_id'] == washer['instance_id'] for card in state_after['player']['hand']))
        self.assertEqual(state_after['energy_remaining'], 2)
        self.assertFalse(state_after['locations'][0]['slots']['player'])
        self.assertIsNone(state_after.get('pending_target'))

    def test_declaration_previews_are_prefetched_only_during_planning(self) -> None:
        token = self._issue_login_and_get_token('solo-declaration-preview')
        self._save_default_build(token)
        self._post('/api/room/create', {'mode': 'solo'}, token=token)

        with self._solo_test_run_context():
            state = self._post('/api/room/start', token=token)

        location_id = state['locations'][0]['id']
        source = next(card for card in state['player']['hand'] if card['definition_id'] == 'genesis_urban_energy')
        preview_payload = self._get('/api/game/declaration-previews', token=token)
        preview_key = f"{source['instance_id']}:{location_id}"

        self.assertEqual(preview_payload['phase'], 'planning')
        self.assertIn(preview_key, preview_payload['previews'])
        preview = preview_payload['previews'][preview_key]
        self.assertEqual(preview['kind'], 'declaration')
        self.assertTrue(preview['cards'])

        selection_state = self._post('/api/game/play-card', {
            'card_instance_id': source['instance_id'],
            'location_id': location_id,
        }, token=token)
        self.assertEqual(selection_state['phase'], 'selecting')
        self.assertIsNotNone(selection_state['selection'])

        blocked_payload = self._get('/api/game/declaration-previews', token=token)
        self.assertEqual(blocked_payload['previews'], {})

    def test_solo_room_can_finish_run_and_reset(self) -> None:
        token = self._issue_login_and_get_token('solo-room-victory')
        self._save_default_build(token)
        room_payload = self._post('/api/room/create', {'mode': 'solo'}, token=token)

        with self._solo_test_run_context():
            state = self._post('/api/room/start', token=token)
            self.assertEqual(state['status'], 'playing')
            self.assertEqual(state['phase'], 'planning')
            self.assertEqual(len(state['player']['hand']), 4)
            first_card = next(card for card in state['player']['hand'] if card['definition_id'] == 'genesis_refresh_charge')
            first_location = state['locations'][0]
            state = self._post('/api/game/play-card', {
                'card_instance_id': first_card['instance_id'],
                'location_id': first_location['id'],
            }, token=token)
            self.assertEqual(state['energy_remaining'], 0)

            state = self._post('/api/game/end-turn', token=token)
            self.assertEqual(state['turn'], 2)
            self.assertEqual(state['phase'], 'planning')
            self.assertIsNone(state['selection'])
            self.assertTrue(any('标记' in line or '战力' in line for line in state['log']))
            self.assertTrue(any(action['kind'] == 'reveal_phase_begin' for action in state['action_queue']))
            self.assertTrue(any(action['kind'] == 'draw_card' for action in state['action_queue']))
            refreshed_state = self._get('/api/game/state', token=token)
            self.assertEqual(refreshed_state['action_queue'], [])
            self.assertEqual(refreshed_state['banner_queue'], [])

            for _ in range(5):
                state = self._post('/api/game/end-turn', token=token)
                state = self._choose_if_needed(state, token)

        self.assertIn(state['status'], {'victory', 'defeat', 'draw'})
        self.assertIn(state['phase'], {'victory', 'defeat', 'draw'})

        game_state = self._get('/api/game/state', token=token)
        self.assertEqual(game_state['status'], state['status'])
        self.assertEqual(game_state['room']['room_code'], room_payload['room_code'])

        room_state = self._get('/api/room/state', token=token)
        self.assertEqual(room_state['status'], state['status'])
        self.assertEqual(room_state['run_status'], state['status'])

        reset_payload = self._post('/api/game/reset', token=token)
        self.assertTrue(reset_payload['ok'])

        reset_room_state = self._get('/api/room/state', token=token)
        self.assertEqual(reset_room_state['status'], 'ready')
        self.assertIsNone(reset_room_state['run_status'])

    def test_undo_turn_reverts_current_planning_actions(self) -> None:
        token = self._issue_login_and_get_token('solo-room-undo')
        self._save_default_build(token)
        self._post('/api/room/create', {'mode': 'solo'}, token=token)

        with self._solo_test_run_context():
            state = self._post('/api/room/start', token=token)
            first_card = next(card for card in state['player']['hand'] if card['definition_id'] == 'genesis_refresh_charge')
            first_location = state['locations'][0]
            self.assertFalse(state['can_undo_turn'])

            state = self._post('/api/game/play-card', {
                'card_instance_id': first_card['instance_id'],
                'location_id': first_location['id'],
            }, token=token)
            self.assertTrue(state['can_undo_turn'])
            self.assertEqual(state['energy_remaining'], 0)
            self.assertEqual(len(state['player']['hand']), 3)
            self.assertEqual(len(state['locations'][0]['slots']['player']), 1)

            state = self._post('/api/game/undo-turn', token=token)
            self.assertFalse(state['can_undo_turn'])
            self.assertEqual(state['phase'], 'planning')
            self.assertEqual(state['energy_remaining'], 1)
            self.assertEqual(len(state['player']['hand']), 4)
            self.assertEqual(len(state['locations'][0]['slots']['player']), 0)
            self.assertTrue(any('撤销了本回合全部操作' in line for line in state['log']))

            error_payload = self._post_error('/api/game/undo-turn', token=token)
            self.assertIn('本回合没有可以撤销的操作', error_payload['error'])


class _RuleModules:
    def __init__(self) -> None:
        self.runtime = importlib.import_module('app.engine.flow.turn_flow')
        self.board = importlib.import_module('app.engine.rules.board_state')
        self.declarations = importlib.import_module('app.engine.rules.declarations')
        self.harmony = importlib.import_module('app.engine.rules.harmony')
        self.materials = importlib.import_module('app.engine.rules.materials')
        self.reveal = importlib.import_module('app.engine.flow.reveal_flow')
        self.build = importlib.import_module('app.engine.application.build_service')
        self.run_state = importlib.import_module('app.engine.application.run_state')
        self.factory = importlib.import_module('app.engine.setup.snapshot_factory')
        self.projection = importlib.import_module('app.engine.projection.public_state')
        self.errors = importlib.import_module('app.errors')

    def __getattr__(self, name: str):
        mapping = {
            '_card_by_id': self.build.card_by_id,
            '_card_instance': self.factory.card_instance,
            '_declaration_selection_preview': self.declarations.declaration_selection_preview,
            '_prepare_declaration_selection': self.declarations.prepare_declaration_selection,
            '_prepare_declaration_target': self.declarations.prepare_declaration_target,
            '_public_pending_target': self.run_state.public_pending_target,
            '_public_location': self.run_state.public_location,
            '_reveal_card': self.reveal.reveal_card,
            '_resolve_pending_material_consumption': self.reveal.resolve_pending_material_consumption,
            '_recompute_scores': self.board.recompute_scores,
            '_location_occupied_card_count': self.board.location_occupied_card_count,
            '_open_locations': self.board.open_locations,
            '_location_has_room_after_materials': self.materials.location_has_room_after_materials,
            '_material_cards_for_esper': self.materials.material_cards_for_esper,
            '_decay_harmony_layers_at_turn_start': self.harmony.decay_harmony_layers_at_turn_start,
            '_resolve_harmony_end_of_turn': self.harmony.resolve_harmony_end_of_turn,
            'SidePerspective': self.projection.SidePerspective,
            'RuleValidationError': self.errors.RuleValidationError,
        }
        if name in mapping:
            return mapping[name]
        return getattr(self.runtime, name)


class DuelRuleTimingTest(RoomFlowTestCase):
    def _rules(self) -> _RuleModules:
        return _RuleModules()

    def _card_instance(self, definition_id: str, suffix: str, *, revealed: bool = True, turn: int = 1) -> dict:
        rules = self._rules()
        definition = rules._card_by_id()[definition_id]
        card = rules._card_instance(definition, rules.SIDE_A, suffix)
        card['revealed'] = revealed
        card['played_turn'] = turn
        card['location_id'] = 'mirror_archive'
        return card

    def _snapshot_with_cards(self, cards: list[dict]) -> dict:
        rules = self._rules()
        return {
            'schema_version': rules.SCHEMA_VERSION,
            'game_id': rules.GAME_ID,
            'mode': 'solo',
            'scenario': 'standard',
            'status': 'playing',
            'phase': 'revealing',
            'turn': 2,
            'max_turns': 6,
            'locations': [{
                'id': 'mirror_archive',
                'name': '镜像档案馆',
                'short_name': '档案馆',
                'reveal_turn': 1,
                'revealed': True,
                'art': '',
                'description': '',
                'effect': '',
                'cards': {rules.SIDE_A: cards, rules.SIDE_B: []},
                'power': {rules.SIDE_A: 0, rules.SIDE_B: 0},
                'winner_side': None,
            }],
            'sides': {
                rules.SIDE_A: {
                    'side': rules.SIDE_A,
                    'uid': 'rules-a',
                    'nickname': 'A',
                    'is_ai': False,
                    'deck': [],
                    'hand': [],
                    'esper_standby': [],
                    'discard': [],
                    'selection': None,
                    'pending_target': None,
                    'combo': {},
                    'energy_used': 0,
                    'ended_turn': False,
                },
                rules.SIDE_B: {
                    'side': rules.SIDE_B,
                    'uid': 'rules-b',
                    'nickname': 'B',
                    'is_ai': True,
                    'deck': [],
                    'hand': [],
                    'esper_standby': [],
                    'discard': [],
                    'selection': None,
                    'pending_target': None,
                    'combo': {},
                    'energy_used': 0,
                    'ended_turn': False,
                },
            },
            'winner_side': None,
            'log': [],
            'action_queue': [],
            'banner_queue': [],
        }

    def test_declaration_config_can_select_hand_cards(self) -> None:
        rules = self._rules()
        source = self._card_instance('delay_commute_bag', 'source', revealed=False, turn=2)
        source['staged'] = True
        material = self._card_instance('delay_first_wish', 'material')
        non_material = self._card_instance('genesis_urban_energy', 'non-material')
        snapshot = self._snapshot_with_cards([source])
        snapshot['phase'] = 'planning'
        snapshot['sides'][rules.SIDE_A]['hand'] = [non_material, material]

        prepared = rules._prepare_declaration_selection(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            source,
        )

        self.assertTrue(prepared)
        selection = snapshot['sides'][rules.SIDE_A]['selection']
        self.assertEqual(selection['kind'], 'declaration')
        self.assertEqual([card['instance_id'] for card in selection['cards']], [material['instance_id']])

    def test_declaration_preview_is_read_only_and_excludes_source_in_hand(self) -> None:
        rules = self._rules()
        source = self._card_instance('delay_commute_bag', 'source', revealed=False, turn=2)
        source['category'] = '材料'
        material = self._card_instance('delay_first_wish', 'material')
        snapshot = self._snapshot_with_cards([])
        snapshot['phase'] = 'planning'
        snapshot['sides'][rules.SIDE_A]['hand'] = [source, material]

        preview = rules._declaration_selection_preview(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            source,
        )

        self.assertIsNotNone(preview)
        self.assertIsNone(snapshot['sides'][rules.SIDE_A]['selection'])
        self.assertEqual([card['instance_id'] for card in preview['cards']], [material['instance_id']])

    def test_commute_bag_reveal_uses_declared_hand_card(self) -> None:
        rules = self._rules()
        source = self._card_instance('delay_commute_bag', 'source', revealed=False, turn=2)
        source['staged'] = True
        material = self._card_instance('delay_first_wish', 'material')
        drawn = self._card_instance('genesis_urban_energy', 'drawn')
        source['declared_card_instance_ids'] = [material['instance_id']]
        source['declared_card_names'] = [material['name']]
        snapshot = self._snapshot_with_cards([source])
        snapshot['sides'][rules.SIDE_A]['hand'] = [material]
        snapshot['sides'][rules.SIDE_A]['deck'] = [drawn]

        rules._reveal_card(snapshot, rules.SIDE_A, snapshot['locations'][0], source)

        self.assertEqual([card['definition_id'] for card in snapshot['sides'][rules.SIDE_A]['hand']], ['genesis_urban_energy'])
        self.assertEqual([card['definition_id'] for card in snapshot['sides'][rules.SIDE_A]['deck']], ['delay_first_wish'])
        self.assertNotIn('declared_card_instance_ids', source)

    def test_declaration_config_sorts_and_dedupes_deck_and_discard_cards(self) -> None:
        rules = self._rules()
        source = self._card_instance('genesis_eborn_cake', 'source', revealed=False, turn=2)
        source['staged'] = True
        urban_deck = self._card_instance('genesis_urban_energy', 'urban-deck')
        cake_deck = self._card_instance('genesis_eborn_cake', 'cake-deck')
        urban_discard = self._card_instance('genesis_urban_energy', 'urban-discard')
        soda_discard = self._card_instance('genesis_marble_soda', 'soda-discard')
        snapshot = self._snapshot_with_cards([source])
        snapshot['phase'] = 'planning'
        snapshot['sides'][rules.SIDE_A]['deck'] = [urban_deck, cake_deck]
        snapshot['sides'][rules.SIDE_A]['discard'] = [urban_discard, soda_discard]

        prepared = rules._prepare_declaration_selection(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            source,
        )

        self.assertTrue(prepared)
        selection = snapshot['sides'][rules.SIDE_A]['selection']
        self.assertEqual(
            [card['definition_id'] for card in selection['cards']],
            ['genesis_eborn_cake', 'genesis_urban_energy', 'genesis_marble_soda'],
        )
        self.assertEqual(
            len({card['definition_id'] for card in selection['cards']}),
            len(selection['cards']),
        )

    def test_board_declaration_uses_card_predicate_for_legal_targets(self) -> None:
        rules = self._rules()
        source = self._card_instance('genesis_marble_soda', 'source', revealed=False, turn=2)
        source['staged'] = True
        legal = self._card_instance('genesis_urban_energy', 'legal')
        illegal = self._card_instance('genesis_eborn_cake', 'illegal')
        illegal['computed_power'] = 4
        snapshot = self._snapshot_with_cards([source, legal, illegal])
        snapshot['phase'] = 'planning'

        prepared = rules._prepare_declaration_target(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            source,
        )

        self.assertTrue(prepared)
        pending = rules._public_pending_target(snapshot['sides'][rules.SIDE_A], snapshot)
        self.assertEqual(pending['target_instance_ids'], [legal['instance_id']])

    def test_broken_material_blocks_esper_entry_before_reveal(self) -> None:
        rules = self._rules()
        material_a = self._card_instance('genesis_refresh_charge', 'material-a')
        material_b = self._card_instance('genesis_marble_soda', 'material-b')
        material_a['bonus_power'] = -2
        material_a['computed_power'] = 0
        esper = self._card_instance('nanali', 'esper-a', revealed=False, turn=2)
        esper['staged'] = True
        esper['summoned_from'] = 'esper_standby'
        esper['pending_material_ids'] = [material_a['instance_id'], material_b['instance_id']]
        material_a['reserved_as_material_for'] = esper['instance_id']
        material_b['reserved_as_material_for'] = esper['instance_id']
        snapshot = self._snapshot_with_cards([material_a, material_b, esper])

        rules._resolve_pending_material_consumption(snapshot)

        side = snapshot['sides'][rules.SIDE_A]
        self.assertEqual([card['definition_id'] for card in side['discard']], ['genesis_refresh_charge'])
        self.assertEqual([card['definition_id'] for card in side['esper_standby']], ['nanali'])
        self.assertEqual([card['definition_id'] for card in snapshot['locations'][0]['cards'][rules.SIDE_A]], ['genesis_marble_soda'])

    def test_material_consumption_happens_before_new_cards_reveal(self) -> None:
        rules = self._rules()
        material_a = self._card_instance('genesis_refresh_charge', 'material-a')
        material_b = self._card_instance('genesis_marble_soda', 'material-b')
        esper = self._card_instance('nanali', 'esper-a', revealed=False, turn=2)
        esper['staged'] = True
        esper['summoned_from'] = 'esper_standby'
        esper['pending_material_ids'] = [material_a['instance_id'], material_b['instance_id']]
        material_a['reserved_as_material_for'] = esper['instance_id']
        material_b['reserved_as_material_for'] = esper['instance_id']
        new_card = self._card_instance('genesis_breakfast_bag', 'new-card', revealed=False, turn=2)
        new_card['staged'] = True
        snapshot = self._snapshot_with_cards([material_a, material_b, esper, new_card])

        rules._resolve_pending_material_consumption(snapshot)

        remaining = [card['definition_id'] for card in snapshot['locations'][0]['cards'][rules.SIDE_A]]
        self.assertEqual(remaining, ['nanali', 'genesis_breakfast_bag'])
        self.assertTrue(snapshot['locations'][0]['cards'][rules.SIDE_A][0]['staged'])
        self.assertFalse(snapshot['locations'][0]['cards'][rules.SIDE_A][1]['revealed'])
        consume_actions = [action for action in snapshot['action_queue'] if action['kind'] == 'consume_material']
        self.assertEqual([action['card']['definition_id'] for action in consume_actions], ['genesis_refresh_charge', 'genesis_marble_soda'])

    def test_reserved_materials_do_not_occupy_slots_or_score(self) -> None:
        rules = self._rules()
        materials = [
            self._card_instance('genesis_refresh_charge', f'material-{index}')
            for index in range(rules.LOCATION_CARD_LIMIT)
        ]
        esper = self._card_instance('nanali', 'esper-a', revealed=False, turn=2)
        esper['staged'] = True
        esper['summoned_from'] = 'esper_standby'
        esper['pending_material_ids'] = [materials[0]['instance_id'], materials[1]['instance_id']]
        materials[0]['reserved_as_material_for'] = esper['instance_id']
        materials[1]['reserved_as_material_for'] = esper['instance_id']
        snapshot = self._snapshot_with_cards([*materials, esper])

        rules._recompute_scores(snapshot)
        location = snapshot['locations'][0]
        public_location = rules._public_location(
            location,
            rules.SidePerspective(own=rules.SIDE_A, opponent=rules.SIDE_B),
        )

        self.assertEqual(rules._location_occupied_card_count(location, rules.SIDE_A), rules.LOCATION_CARD_LIMIT - 1)
        self.assertEqual(len(public_location['slots']['player']), rules.LOCATION_CARD_LIMIT - 1)
        self.assertEqual(public_location['occupied']['player'], rules.LOCATION_CARD_LIMIT - 1)
        self.assertNotIn(materials[0]['instance_id'], [card['instance_id'] for card in public_location['slots']['player']])
        self.assertTrue(rules._location_has_room_after_materials(location, rules.SIDE_A, materials[:2]))
        self.assertIn(location, rules._open_locations(snapshot, rules.SIDE_A))
        expected_power = sum(int(card['computed_power']) for card in materials[2:])
        self.assertEqual(location['power'][rules.SIDE_A], expected_power)

    def test_refresh_charge_effect_deploy_uses_shared_location_capacity(self) -> None:
        rules = self._rules()
        source = self._card_instance('genesis_refresh_charge', 'source', revealed=False, turn=2)
        source['staged'] = True
        urban = self._card_instance('genesis_urban_energy', 'urban')
        filler_a = self._card_instance('genesis_breakfast_bag', 'filler-a')
        filler_b = self._card_instance('genesis_marble_soda', 'filler-b')
        hand_card = self._card_instance('genesis_breakfast_bag', 'hand-card')
        snapshot = self._snapshot_with_cards([source, urban, filler_a, filler_b])
        snapshot['locations'][0]['capacity'] = rules.LOCATION_CARD_LIMIT
        snapshot['sides'][rules.SIDE_A]['hand'] = [hand_card]

        rules._reveal_card(snapshot, rules.SIDE_A, snapshot['locations'][0], source)

        self.assertEqual(len(snapshot['locations'][0]['cards'][rules.SIDE_A]), 5)
        self.assertEqual(snapshot['locations'][0]['cards'][rules.SIDE_A][-1]['definition_id'], 'genesis_breakfast_bag')
        self.assertFalse(snapshot['sides'][rules.SIDE_A]['hand'])
        self.assertFalse(any('战场已满' in line for line in snapshot['log']))

    def test_multi_requirement_esper_material_accepts_matching_anomaly_items(self) -> None:
        rules = self._rules()
        material_a = self._card_instance('genesis_urban_energy', 'material-a')
        material_b = self._card_instance('surplus_fons', 'material-b')
        esper = self._card_instance('xiaozhi', 'esper-a', revealed=False, turn=2)
        snapshot = self._snapshot_with_cards([material_a, material_b])

        selected = rules._material_cards_for_esper(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            esper,
            [material_a['instance_id'], material_b['instance_id']],
        )

        self.assertEqual([card['definition_id'] for card in selected], ['genesis_urban_energy', 'surplus_fons'])

    def test_material_matching_accepts_any_valid_assignment_order(self) -> None:
        rules = self._rules()
        flexible_material = self._card_instance('genesis_refresh_charge', 'material-a')
        attribute_material = self._card_instance('genesis_breakfast_bag', 'material-b')
        esper = self._card_instance('nanali', 'esper-a', revealed=False, turn=2)
        snapshot = self._snapshot_with_cards([flexible_material, attribute_material])

        selected = rules._material_cards_for_esper(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            esper,
            [flexible_material['instance_id'], attribute_material['instance_id']],
        )
        auto_selected = rules._material_cards_for_esper(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            esper,
        )

        self.assertEqual([card['definition_id'] for card in selected], ['genesis_refresh_charge', 'genesis_breakfast_bag'])
        self.assertEqual([card['definition_id'] for card in auto_selected], ['genesis_refresh_charge', 'genesis_breakfast_bag'])

    def test_continuous_damage_marks_decay_at_turn_start(self) -> None:
        rules = self._rules()
        snapshot = self._snapshot_with_cards([])
        location = snapshot['locations'][0]
        location['marks'] = {
            rules.SIDE_A: {
                rules.TAG_NIGHTMARE: 2,
                rules.TAG_ZHUE_HUCHI: 1,
            },
            rules.SIDE_B: {},
        }

        rules._decay_harmony_layers_at_turn_start(snapshot)

        self.assertEqual(location['marks'][rules.SIDE_A][rules.TAG_NIGHTMARE], 1)
        self.assertNotIn(rules.TAG_ZHUE_HUCHI, location['marks'][rules.SIDE_A])

    def test_genesis_and_murk_resolve_once_per_turn_regardless_of_layers(self) -> None:
        rules = self._rules()
        ally = self._card_instance('genesis_urban_energy', 'ally')
        enemy = self._card_instance('genesis_muscle_faith', 'enemy')
        enemy['side'] = rules.SIDE_B
        snapshot = self._snapshot_with_cards([ally])
        location = snapshot['locations'][0]
        location['cards'][rules.SIDE_B] = [enemy]
        location['marks'] = {
            rules.SIDE_A: {
                rules.TAG_GENESIS: 3,
                rules.TAG_MURK: 3,
            },
            rules.SIDE_B: {},
        }

        with patch('app.engine.rules.harmony.random.choice', side_effect=lambda cards: cards[0]):
            rules._resolve_harmony_end_of_turn(snapshot)

        self.assertEqual(ally['computed_power'], 3)
        self.assertEqual(enemy['computed_power'], 6)
        self.assertEqual([action['title'] for action in snapshot['action_queue']].count('创生'), 1)
        self.assertEqual([action['title'] for action in snapshot['action_queue']].count('浊燃'), 1)

    def test_nightmare_and_panyu_qiu_resolve_at_end_of_turn(self) -> None:
        rules = self._rules()
        high_enemy = self._card_instance('genesis_muscle_faith', 'enemy-high')
        low_enemy = self._card_instance('genesis_urban_energy', 'enemy-low')
        for card in (high_enemy, low_enemy):
            card['side'] = rules.SIDE_B
        snapshot = self._snapshot_with_cards([])
        location = snapshot['locations'][0]
        location['cards'][rules.SIDE_B] = [high_enemy, low_enemy]
        location['marks'] = {
            rules.SIDE_A: {
                rules.TAG_NIGHTMARE: 3,
                rules.TAG_PANYU_QIU: 3,
            },
            rules.SIDE_B: {},
        }

        rules._resolve_harmony_end_of_turn(snapshot)

        self.assertEqual(high_enemy['computed_power'], 6)
        self.assertEqual([card['definition_id'] for card in location['cards'][rules.SIDE_B]], ['genesis_muscle_faith'])
        self.assertEqual([card['definition_id'] for card in snapshot['sides'][rules.SIDE_B]['discard']], ['genesis_urban_energy'])
        self.assertTrue(any(action['title'] == '噩梦' for action in snapshot['action_queue']))
        self.assertTrue(any(action['title'] == '判予秋' for action in snapshot['action_queue']))

    def test_xun_copies_highest_harmony_prioritizing_genesis_and_triggers_it(self) -> None:
        rules = self._rules()
        xun = self._card_instance('xun', 'xun-a', revealed=False, turn=2)
        snapshot = self._snapshot_with_cards([xun])
        location = snapshot['locations'][0]
        location['marks'] = {
            rules.SIDE_A: {
                rules.TAG_GENESIS: 2,
                rules.TAG_DELAY: 2,
            },
            rules.SIDE_B: {},
        }

        with patch('app.content.effects.cards.random.choice', side_effect=lambda cards: cards[0]):
            rules._reveal_card(snapshot, rules.SIDE_A, location, xun)

        self.assertEqual(location['marks'][rules.SIDE_A][rules.TAG_GENESIS], 3)
        self.assertEqual(location['marks'][rules.SIDE_A][rules.TAG_DELAY], 2)
        self.assertEqual(xun['computed_power'], 7)
        self.assertTrue(any('令创生花在时停中生效' in line for line in snapshot['log']))

    def test_xun_requires_light_drink_and_eborn_cake_materials(self) -> None:
        rules = self._rules()
        light = self._card_instance('genesis_urban_energy', 'light-a')
        drink = self._card_instance('genesis_refresh_charge', 'drink-a')
        cake = self._card_instance('genesis_eborn_cake', 'cake-a')
        xun = self._card_instance('xun', 'xun-a', revealed=False, turn=2)
        snapshot = self._snapshot_with_cards([light, drink, cake])

        selected = rules._material_cards_for_esper(
            snapshot,
            rules.SIDE_A,
            snapshot['locations'][0],
            xun,
        )

        self.assertCountEqual(
            [card['definition_id'] for card in selected],
            ['genesis_urban_energy', 'genesis_refresh_charge', 'genesis_eborn_cake'],
        )

    def test_murk_item_pressure_does_not_create_murk_mark(self) -> None:
        rules = self._rules()
        murk_item = self._card_instance('murk_lost_whisper', 'murk-a', revealed=False, turn=2)
        target_definition = rules._card_by_id()['genesis_muscle_faith']
        target = rules._card_instance(target_definition, rules.SIDE_B, 'target-b')
        target['revealed'] = True
        target['played_turn'] = 1
        target['location_id'] = 'mirror_archive'
        snapshot = self._snapshot_with_cards([murk_item])
        location = snapshot['locations'][0]
        location['cards'][rules.SIDE_B].append(target)

        rules._reveal_card(snapshot, rules.SIDE_A, location, murk_item)

        self.assertEqual(location.get('marks', {}).get(rules.SIDE_B, {}).get(rules.TAG_MURK, 0), 0)
        self.assertEqual(target['bonus_power'], -1)
        self.assertFalse(any(action.get('kind') == 'spawn_mark' and action.get('mark') == rules.TAG_MURK for action in snapshot['action_queue']))

    def test_non_positive_anomaly_item_is_not_valid_esper_material(self) -> None:
        rules = self._rules()
        material_a = self._card_instance('genesis_refresh_charge', 'material-a')
        material_b = self._card_instance('genesis_marble_soda', 'material-b')
        material_a['bonus_power'] = -2
        material_a['computed_power'] = 0
        esper = self._card_instance('nanali', 'esper-a', revealed=False, turn=2)
        snapshot = self._snapshot_with_cards([material_a, material_b])

        with self.assertRaisesRegex(rules.RuleValidationError, '战力为正'):
            rules._material_cards_for_esper(
                snapshot,
                rules.SIDE_A,
                snapshot['locations'][0],
                esper,
                [material_a['instance_id'], material_b['instance_id']],
            )


class DuoRoomFlowTest(RoomFlowTestCase):
    def test_duo_room_requires_both_players_ready_before_start(self) -> None:
        host_token = self._issue_login_and_get_token('duo-host-waiting')
        guest_token = self._issue_login_and_get_token('duo-guest-waiting')
        self._save_default_build(host_token)
        self._save_default_build(guest_token)

        room_payload = self._post('/api/room/create', {'mode': 'duo'}, token=host_token)
        room_code = room_payload['room_code']
        self.assertEqual(room_payload['status'], 'waiting')
        self.assertFalse(room_payload['members'][0]['is_ready'])

        joined_payload = self._post('/api/room/join', {'room_code': room_code}, token=guest_token)
        self.assertEqual(len(joined_payload['members']), 2)
        self.assertEqual(joined_payload['status'], 'waiting')

        start_error = self._post_error('/api/room/start', token=host_token)
        self.assertEqual(start_error['error'], '仍有玩家未准备，无法开始游戏。')

    def test_duo_room_only_host_can_start(self) -> None:
        host_token = self._issue_login_and_get_token('duo-host-only')
        guest_token = self._issue_login_and_get_token('duo-guest-only')
        self._save_default_build(host_token)
        self._save_default_build(guest_token)

        room_payload = self._post('/api/room/create', {'mode': 'duo'}, token=host_token)
        room_code = room_payload['room_code']
        self._post('/api/room/join', {'room_code': room_code}, token=guest_token)
        self._post('/api/room/ready', {'is_ready': True}, token=host_token)
        self._post('/api/room/ready', {'is_ready': True}, token=guest_token)

        guest_start_error = self._post_error('/api/room/start', token=guest_token)
        self.assertEqual(guest_start_error['error'], '只有房主可以开始游戏。')

    def test_duo_room_can_start_and_advance_after_both_players_act(self) -> None:
        host_token = self._issue_login_and_get_token('duo-host-start')
        guest_token = self._issue_login_and_get_token('duo-guest-start')
        self._save_default_build(host_token)
        self._save_default_build(guest_token)

        room_payload = self._post('/api/room/create', {'mode': 'duo'}, token=host_token)
        room_code = room_payload['room_code']
        self._post('/api/room/join', {'room_code': room_code}, token=guest_token)

        ready_payload = self._post('/api/room/ready', {'is_ready': True}, token=host_token)
        self.assertEqual(ready_payload['status'], 'waiting')
        ready_payload = self._post('/api/room/ready', {'is_ready': True}, token=guest_token)
        self.assertEqual(ready_payload['status'], 'ready')

        with self._duo_test_run_context():
            start_payload = self._post('/api/room/start', token=host_token)
            self.assertEqual(start_payload['status'], 'playing')
            self.assertEqual(start_payload['game_id'], 'anomaly_snap_duel')
            self.assertEqual(start_payload['room']['room_code'], room_code)
            self.assertEqual(start_payload['room']['mode'], 'duo')
            self.assertEqual(start_payload['turn'], 1)
            self.assertEqual(start_payload['phase'], 'planning')
            self.assertIsNone(start_payload['selection'])
            self.assertEqual(len(start_payload['player']['hand']), 4)
            self.assertEqual(start_payload['current_actor_uid'], 'duo-host-start')
            self.assertEqual(len(start_payload['players_overview']), 2)

            room_state = self._get('/api/room/state', token=host_token)
            self.assertEqual(room_state['status'], 'playing')
            self.assertEqual(room_state['run_status'], 'playing')

            guest_start_view = self._get('/api/game/state', token=guest_token)
            self.assertEqual(guest_start_view['phase'], 'planning')
            self.assertIsNone(guest_start_view['selection'])

            host_after_end = self._post('/api/game/end-turn', token=host_token)
            self.assertEqual(host_after_end['turn'], 1)
            self.assertEqual(host_after_end['phase'], 'waiting')
            self.assertTrue(host_after_end['player']['ended_turn'])

            guest_view_before_end = self._get('/api/game/state', token=guest_token)
            self.assertEqual(guest_view_before_end['turn'], 1)
            self.assertEqual(guest_view_before_end['phase'], 'planning')
            self.assertEqual(guest_view_before_end['current_actor_uid'], 'duo-guest-start')

            guest_after_end = self._post('/api/game/end-turn', token=guest_token)
            self.assertEqual(guest_after_end['turn'], 2)
            self.assertEqual(guest_after_end['phase'], 'planning')
            self.assertEqual(guest_after_end['current_actor_uid'], 'duo-guest-start')
            self.assertIsNone(guest_after_end['selection'])

        host_view_next_turn = self._get('/api/game/state', token=host_token)
        self.assertEqual(host_view_next_turn['turn'], 2)
        self.assertEqual(host_view_next_turn['phase'], 'planning')
        self.assertEqual(host_view_next_turn['current_actor_uid'], 'duo-host-start')

    def _duo_test_run_context(self) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch('app.engine.setup.snapshot_factory.random.shuffle', side_effect=lambda value: None))
        return stack


if __name__ == '__main__':
    unittest.main()
