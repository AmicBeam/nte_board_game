from pathlib import Path

from tests.test_solo_room_flow import RoomFlowTestCase


ROOT = Path(__file__).resolve().parents[1]


class ModuleRoutesTest(RoomFlowTestCase):
    def _assert_asset(self, path: str) -> None:
        response = self.client.get(path)
        try:
            self.assertEqual(response.status_code, 200)
        finally:
            response.close()

    def test_card_game_module_page_and_asset(self) -> None:
        page = self.client.get('/card-game')
        self.assertEqual(page.status_code, 200)
        self.assertIn('异象对决', page.get_data(as_text=True))
        self._assert_asset('/static/card_game/js/home.js')

    def test_kongmu_module_page_catalog_and_asset(self) -> None:
        self.assertEqual(self.client.get('/kongmu').status_code, 200)
        catalog = self.client.get('/api/kongmu/catalog')
        self.assertEqual(catalog.status_code, 200)
        self.assertTrue(catalog.is_json)
        zero = next(character for character in catalog.get_json()['characters'] if character['name'] == '「零」')
        self.assertIn('player_009_256.webp', zero['avatar'])
        frontend = (
            ROOT / 'app' / 'modules' / 'kongmu' / 'static' / 'js' / 'kongmu.js'
        ).read_text(encoding='utf-8')
        self.assertNotIn('pickCharacterAvatar', frontend)
        self.assertNotIn('avatarChoiceIndexes', frontend)
        self._assert_asset('/static/kongmu/js/kongmu.js')

    def test_preteam_module_page_and_asset(self) -> None:
        page = self.client.get('/preteam')
        self.assertEqual(page.status_code, 200)
        self.assertIn('异环预配队', page.get_data(as_text=True))
        self._assert_asset('/static/preteam/单位.jpg')

    def test_shaft_module_page_catalog_and_asset(self) -> None:
        self.assertEqual(self.client.get('/shaft/rotation').status_code, 200)
        catalog = self.client.get('/api/shaft/catalog')
        self.assertEqual(catalog.status_code, 200)
        self.assertTrue(catalog.is_json)
        self._assert_asset('/static/shaft/js/shaft.js')

    def test_module_owned_files_are_not_left_in_legacy_directories(self) -> None:
        for legacy_path in (
            ROOT / 'app' / 'content',
            ROOT / 'app' / 'engine',
            ROOT / 'app' / 'shaft',
            ROOT / 'app' / 'templates' / 'card_game',
            ROOT / 'app' / 'templates' / 'kongmu',
            ROOT / 'app' / 'templates' / 'preteam',
            ROOT / 'app' / 'templates' / 'shaft',
            ROOT / 'app' / 'static' / 'card_game',
            ROOT / 'app' / 'static' / 'kongmu',
            ROOT / 'app' / 'static' / 'preteam',
            ROOT / 'app' / 'static' / 'shaft',
        ):
            self.assertFalse(legacy_path.exists(), str(legacy_path))
