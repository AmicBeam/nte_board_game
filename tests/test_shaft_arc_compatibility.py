import unittest
from pathlib import Path

from app.modules.shaft.service import normalize_axis_payload
from app.errors import RuleValidationError
from app.modules.shaft.domain.catalog import get_record_map, load_shaft_catalog


ROOT = Path(__file__).resolve().parents[1]
SHAFT_JS = ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'js' / 'shaft.js'
ADAPTATIONS = {'固态', '液态', '气态', '等离子', '聚合'}
EXPECTED_CHARACTER_ADAPTATIONS = {
    '主角': '固态',
    '真红': '聚合',
    '浔': '固态',
    '小吱': '气态',
    '埃德嘉': '液态',
    '伊洛伊': '液态',
    '娜娜莉': '等离子',
    '九原': '固态',
    '薄荷': '液态',
    '白藏': '聚合',
    '早雾': '气态',
    '阿德勒': '聚合',
    '安魂曲': '液态',
    '达芙蒂尔': '液态',
    '法帝娅': '聚合',
    '海月': '等离子',
    '哈尼娅': '固态',
    '卡厄斯': '聚合',
    '哈索尔': '等离子',
    '翳': '气态',
}


class ShaftArcCompatibilityTestCase(unittest.TestCase):
    def test_all_characters_and_arcs_have_known_adaptation(self) -> None:
        catalog = load_shaft_catalog()

        self.assertTrue(catalog['characters'])
        self.assertTrue(catalog['arcs'])
        self.assertTrue(all(character.get('adaptation') in ADAPTATIONS for character in catalog['characters']))
        self.assertTrue(all(arc.get('adaptation') in ADAPTATIONS for arc in catalog['arcs']))
        self.assertEqual(
            {character['name']: character['adaptation'] for character in catalog['characters']},
            EXPECTED_CHARACTER_ADAPTATIONS,
        )

    def test_starter_build_arcs_match_character_adaptation(self) -> None:
        catalog = load_shaft_catalog()
        characters = get_record_map(catalog['characters'])
        arcs = get_record_map(catalog['arcs'])

        for character_id, raw_build in catalog['starter_axis']['character_builds'].items():
            build = raw_build[0] if isinstance(raw_build, list) else raw_build
            arc = arcs.get(str(build.get('arc_id') or ''))
            if arc:
                self.assertEqual(characters[character_id]['adaptation'], arc['adaptation'])

    def test_backend_rejects_active_incompatible_arc(self) -> None:
        catalog = load_shaft_catalog()
        axis = dict(catalog['starter_axis'])
        axis['team'] = [dict(member) for member in catalog['starter_axis']['team']]
        member = axis['team'][0]
        character = get_record_map(catalog['characters'])[member['character_id']]
        incompatible_arc = next(
            arc for arc in catalog['arcs']
            if arc['adaptation'] != character['adaptation']
        )
        member['arc_id'] = incompatible_arc['id']

        with self.assertRaisesRegex(RuleValidationError, '适配类型不一致'):
            normalize_axis_payload(axis)

    def test_frontend_filters_arc_options_and_repairs_character_switch(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function arcsForCharacter(characterId)', source)
        self.assertIn("String(arc.adaptation || '') === adaptation", source)
        self.assertIn('optionHtml(compatibleArcs, member.arc_id)', source)
        self.assertIn('ensureMemberCompatibleArc(member);', source)


if __name__ == '__main__':
    unittest.main()
