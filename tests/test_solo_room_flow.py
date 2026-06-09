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
            'starter_item_ids': DEFAULT_ITEMS[:4],
            'reserve_item_ids': DEFAULT_ITEMS[4:],
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
        stack.enter_context(patch('app.engine.game_service.random.shuffle', side_effect=lambda value: None))
        return stack


class SoloRoomFlowTest(RoomFlowTestCase):
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
        self.assertEqual(run_payload['current_actor_uid'], 'solo-room-start')

        room_state = self._get('/api/room/state', token=token)
        self.assertEqual(room_state['room_code'], room_code)
        self.assertEqual(room_state['status'], 'playing')
        self.assertEqual(room_state['run_status'], 'playing')

    def test_solo_room_can_finish_run_and_reset(self) -> None:
        token = self._issue_login_and_get_token('solo-room-victory')
        self._save_default_build(token)
        room_payload = self._post('/api/room/create', {'mode': 'solo'}, token=token)

        with self._solo_test_run_context():
            state = self._post('/api/room/start', token=token)
            self.assertEqual(state['status'], 'playing')
            self.assertEqual(state['phase'], 'planning')
            self.assertEqual(len(state['player']['hand']), 4)
            first_card = state['player']['hand'][0]
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
            first_card = state['player']['hand'][0]
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


class DuelRuleTimingTest(RoomFlowTestCase):
    def _card_instance(self, definition_id: str, suffix: str, *, revealed: bool = True, turn: int = 1) -> dict:
        game_service = importlib.import_module('app.engine.game_service')
        definition = game_service._card_by_id()[definition_id]
        card = game_service._card_instance(definition, game_service.SIDE_A, suffix)
        card['revealed'] = revealed
        card['played_turn'] = turn
        card['location_id'] = 'mirror_archive'
        return card

    def _snapshot_with_cards(self, cards: list[dict]) -> dict:
        game_service = importlib.import_module('app.engine.game_service')
        return {
            'schema_version': game_service.SCHEMA_VERSION,
            'game_id': game_service.GAME_ID,
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
                'cards': {game_service.SIDE_A: cards, game_service.SIDE_B: []},
                'power': {game_service.SIDE_A: 0, game_service.SIDE_B: 0},
                'winner_side': None,
            }],
            'sides': {
                game_service.SIDE_A: {
                    'side': game_service.SIDE_A,
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
                game_service.SIDE_B: {
                    'side': game_service.SIDE_B,
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

    def test_broken_material_blocks_esper_entry_before_reveal(self) -> None:
        game_service = importlib.import_module('app.engine.game_service')
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

        game_service._resolve_pending_material_consumption(snapshot)

        side = snapshot['sides'][game_service.SIDE_A]
        self.assertEqual([card['definition_id'] for card in side['discard']], ['genesis_refresh_charge'])
        self.assertEqual([card['definition_id'] for card in side['esper_standby']], ['nanali'])
        self.assertEqual([card['definition_id'] for card in snapshot['locations'][0]['cards'][game_service.SIDE_A]], ['genesis_marble_soda'])

    def test_material_consumption_happens_before_new_cards_reveal(self) -> None:
        game_service = importlib.import_module('app.engine.game_service')
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

        game_service._resolve_pending_material_consumption(snapshot)

        remaining = [card['definition_id'] for card in snapshot['locations'][0]['cards'][game_service.SIDE_A]]
        self.assertEqual(remaining, ['nanali', 'genesis_breakfast_bag'])
        self.assertTrue(snapshot['locations'][0]['cards'][game_service.SIDE_A][0]['staged'])
        self.assertFalse(snapshot['locations'][0]['cards'][game_service.SIDE_A][1]['revealed'])

    def test_multi_requirement_esper_material_accepts_matching_anomaly_items(self) -> None:
        game_service = importlib.import_module('app.engine.game_service')
        material_a = self._card_instance('genesis_urban_energy', 'material-a')
        material_b = self._card_instance('genesis_refresh_charge', 'material-b')
        esper = self._card_instance('xiaozhi', 'esper-a', revealed=False, turn=2)
        snapshot = self._snapshot_with_cards([material_a, material_b])

        selected = game_service._material_cards_for_esper(
            snapshot,
            game_service.SIDE_A,
            snapshot['locations'][0],
            esper,
            [material_a['instance_id'], material_b['instance_id']],
        )

        self.assertEqual([card['definition_id'] for card in selected], ['genesis_urban_energy', 'genesis_refresh_charge'])

    def test_non_positive_anomaly_item_is_not_valid_esper_material(self) -> None:
        game_service = importlib.import_module('app.engine.game_service')
        material_a = self._card_instance('genesis_refresh_charge', 'material-a')
        material_b = self._card_instance('genesis_marble_soda', 'material-b')
        material_a['bonus_power'] = -2
        material_a['computed_power'] = 0
        esper = self._card_instance('nanali', 'esper-a', revealed=False, turn=2)
        snapshot = self._snapshot_with_cards([material_a, material_b])

        with self.assertRaisesRegex(game_service.RuleValidationError, '战力为正'):
            game_service._material_cards_for_esper(
                snapshot,
                game_service.SIDE_A,
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
        stack.enter_context(patch('app.engine.game_service.random.shuffle', side_effect=lambda value: None))
        return stack


if __name__ == '__main__':
    unittest.main()
