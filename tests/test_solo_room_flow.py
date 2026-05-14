import importlib
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


DEFAULT_ITEMS = [
    'blaze_drive',
    'phase_shield',
    'guard_matrix',
    'pulse_repair',
    'route_scan',
    'dash_patch',
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
            'character_id': 'appraiser',
            'item_ids': DEFAULT_ITEMS,
        }, token=token)

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
        stack.enter_context(patch('app.engine.game_service.random.randint', return_value=1))
        stack.enter_context(patch('app.engine.game_service.get_map', return_value=self._build_test_map()))
        return stack

    def _build_test_map(self) -> dict:
        return deepcopy({
            'id': 'solo_test_map',
            'name': 'Solo Test Map',
            'width': 2,
            'height': 2,
            'background_image': '/static/images/maps/lower_relay_district.png',
            'start': {'x': 0, 'y': 0},
            'tiles': [],
            'monsters': [],
            'boss': {
                'id': 'abyss_core',
                'name': 'Abyss Core',
                'positions': [
                    {'x': 1, 'y': 1},
                ],
                'max_hp': 7,
                'hp': 7,
                'attack': 12,
                'defense': 4,
                'range': 1,
                'kind': 'boss',
            },
        })


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
        self.assertEqual(run_payload['room']['mode'], 'solo')
        self.assertEqual(run_payload['room']['room_code'], room_code)
        self.assertEqual(run_payload['turn'], 1)
        self.assertEqual(run_payload['phase'], 'action')
        self.assertEqual(run_payload['pending_die'], 1)
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
            start_payload = self._post('/api/room/start', token=token)
            self.assertEqual(start_payload['status'], 'playing')

            victory_payload = self._post('/api/game/move', {'direction': 'down'}, token=token)

        self.assertEqual(victory_payload['status'], 'victory')
        self.assertEqual(victory_payload['phase'], 'victory')
        self.assertEqual(victory_payload['map']['boss']['hp'], 0)
        self.assertIn('Abyss Core 被击破，获得胜利。', victory_payload['log'])

        game_state = self._get('/api/game/state', token=token)
        self.assertEqual(game_state['status'], 'victory')
        self.assertEqual(game_state['room']['room_code'], room_payload['room_code'])

        room_state = self._get('/api/room/state', token=token)
        self.assertEqual(room_state['status'], 'victory')
        self.assertEqual(room_state['run_status'], 'victory')

        reset_payload = self._post('/api/game/reset', token=token)
        self.assertTrue(reset_payload['ok'])

        reset_room_state = self._get('/api/room/state', token=token)
        self.assertEqual(reset_room_state['status'], 'ready')
        self.assertIsNone(reset_room_state['run_status'])


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
            self.assertEqual(start_payload['room']['room_code'], room_code)
            self.assertEqual(start_payload['room']['mode'], 'duo')
            self.assertEqual(start_payload['turn'], 1)
            self.assertEqual(start_payload['current_actor_uid'], 'duo-host-start')
            self.assertEqual(len(start_payload['players_overview']), 2)

            room_state = self._get('/api/room/state', token=host_token)
            self.assertEqual(room_state['status'], 'playing')
            self.assertEqual(room_state['run_status'], 'playing')

            host_after_move = self._post('/api/game/move', {'direction': 'down'}, token=host_token)
            self.assertEqual(host_after_move['turn'], 1)
            self.assertEqual(host_after_move['phase'], 'completed')
            self.assertEqual(host_after_move['player']['x'], 0)
            self.assertEqual(host_after_move['player']['y'], 1)

            guest_view_before_move = self._get('/api/game/state', token=guest_token)
            self.assertEqual(guest_view_before_move['turn'], 1)
            self.assertEqual(guest_view_before_move['phase'], 'action')
            self.assertEqual(guest_view_before_move['pending_die'], 1)
            self.assertEqual(guest_view_before_move['current_actor_uid'], 'duo-guest-start')

            guest_after_move = self._post('/api/game/move', {'direction': 'down'}, token=guest_token)
            self.assertEqual(guest_after_move['turn'], 2)
            self.assertEqual(guest_after_move['phase'], 'action')
            self.assertEqual(guest_after_move['pending_die'], 1)
            self.assertEqual(guest_after_move['current_actor_uid'], 'duo-guest-start')

        host_view_next_turn = self._get('/api/game/state', token=host_token)
        self.assertEqual(host_view_next_turn['turn'], 2)
        self.assertEqual(host_view_next_turn['phase'], 'action')
        self.assertEqual(host_view_next_turn['pending_die'], 1)
        self.assertEqual(host_view_next_turn['current_actor_uid'], 'duo-host-start')

    def _duo_test_run_context(self) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch('app.engine.game_service.random.randint', return_value=1))
        stack.enter_context(patch('app.engine.game_service.get_map', return_value=self._build_duo_test_map()))
        return stack

    def _build_duo_test_map(self) -> dict:
        return deepcopy({
            'id': 'duo_test_map',
            'name': 'Duo Test Map',
            'width': 3,
            'height': 3,
            'background_image': '/static/images/maps/lower_relay_district.png',
            'start': {'x': 0, 'y': 0},
            'tiles': [],
            'monsters': [],
            'boss': {
                'id': 'abyss_core',
                'name': 'Abyss Core',
                'positions': [
                    {'x': 2, 'y': 2},
                ],
                'max_hp': 60,
                'hp': 60,
                'attack': 12,
                'defense': 4,
                'range': 1,
                'kind': 'boss',
            },
        })


if __name__ == '__main__':
    unittest.main()
