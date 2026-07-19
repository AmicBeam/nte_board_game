import json
import shutil
import subprocess
import unittest
from pathlib import Path

from app.modules.shaft.domain.catalog import load_shaft_catalog


ROOT = Path(__file__).resolve().parents[1]
SELF_CHECK_JS = ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'js' / 'shaft_self_check.js'


@unittest.skipUnless(shutil.which('node'), 'node is required for shaft frontend self-check tests')
class ShaftSelfCheckTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_shaft_catalog()

    def inspect(self, steps: list[dict]) -> list[str]:
        script = """
const selfCheck = require(process.argv[1]);
const payload = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(selfCheck.inspectAxis(payload.axis, payload.catalog)));
"""
        payload = {'axis': {'steps': steps}, 'catalog': {'actions': self.catalog['actions']}}
        completed = subprocess.run(
            ['node', '-e', script, str(SELF_CHECK_JS), json.dumps(payload, ensure_ascii=False)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def action(self, character: str, name: str) -> dict:
        return next(
            action for action in self.catalog['actions']
            if action.get('character_name') == character and action.get('name') == name
        )

    def step(self, action: dict, tick: int, slot: int = 0) -> dict:
        return {'id': f"{action['id']}-{tick}", 'action_id': action['id'], 'slot': slot, 'start_tick': tick}

    def test_warns_for_adjacent_descending_basic_stages_except_reset_to_first_stage(self) -> None:
        a4 = self.action('真红', 'a4')
        a2 = self.action('真红', 'a2')
        a1 = self.action('真红', 'a1')

        self.assertEqual(self.inspect([self.step(a4, 0), self.step(a2, 2)]), ['真红存在普攻段数异常'])
        self.assertEqual(self.inspect([self.step(a4, 0), self.step(a1, 2)]), [])

    def test_other_action_between_basic_stages_prevents_warning(self) -> None:
        a4 = self.action('真红', 'a4')
        a2 = self.action('真红', 'a2')
        q = self.action('真红', 'q')

        self.assertEqual(self.inspect([self.step(a4, 0), self.step(q, 2), self.step(a2, 4)]), [])

    def test_requiem_does_not_require_manual_nightmare_action(self) -> None:
        actions = [
            self.action('安魂曲', 'a1近'),
            self.action('安魂曲', 'e'),
            self.action('安魂曲', 'q'),
        ]
        steps = [self.step(action, index * 10) for index, action in enumerate(actions)]
        self.assertEqual(self.inspect(steps), [])


if __name__ == '__main__':
    unittest.main()
