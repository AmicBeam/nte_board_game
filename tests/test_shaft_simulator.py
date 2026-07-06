import unittest

from app.engine.application.shaft_service import simulate_shaft_axis


class ShaftSimulatorQInstantReleaseTestCase(unittest.TestCase):
    def test_q_instant_release_keeps_elapsed_time_before_q_release(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': 'arc_27dc4a7281',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_dd034941ef',
                    'arc_id': 'arc_a5b483cca6',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 2,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': 'arc_d75aa15b91',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'foreground_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 0},
                {'id': 'q_anchor', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 0},
                {'id': 'same_column_e', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 0},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        foreground = details['foreground_e']
        self.assertTrue(foreground['q_instant_release'])
        self.assertEqual(foreground['q_instant_release_kind'], 'column')
        self.assertEqual(foreground['end_tick'], 2)
        self.assertEqual(foreground['duration_ticks'], 2)
        self.assertEqual(foreground['q_instant_release_anchor_tick'], 2)
        self.assertEqual(foreground['q_instant_release_anchor_step_id'], 'q_anchor')

        q_anchor = details['q_anchor']
        self.assertEqual(q_anchor['raw_start_tick'], 0)
        self.assertEqual(q_anchor['start_tick'], 2)

        same_column = details['same_column_e']
        self.assertTrue(same_column['q_instant_release'])
        self.assertEqual(same_column['q_instant_release_kind'], 'column')
        self.assertEqual(same_column['end_tick'], 2)
        self.assertEqual(same_column['duration_ticks'], 2)
        self.assertEqual(same_column['q_instant_release_anchor_tick'], 2)
        self.assertEqual(same_column['q_instant_release_anchor_step_id'], 'q_anchor')

    def test_q_instant_release_visual_anchor_uses_q_midpoint(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': 'arc_a5b483cca6',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': 'arc_27dc4a7281',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 2,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': 'arc_d75aa15b91',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'foreground_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'q_anchor', 'slot': 1, 'action_id': 'action_a17ac7c5b7', 'start_tick': 0},
                {'id': 'same_column_e', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 0},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        q_anchor = details['q_anchor']
        self.assertEqual(q_anchor['start_tick'], 2)
        self.assertEqual(q_anchor['end_tick'], 10)
        self.assertEqual(q_anchor['duration_ticks'], 8)
        self.assertFalse(q_anchor['q_instant_release'])

        foreground = details['foreground_e']
        self.assertEqual(foreground['q_instant_release_tick'], 2)
        self.assertEqual(foreground['end_tick'], 2)
        self.assertEqual(foreground['duration_ticks'], 2)
        self.assertEqual(foreground['q_instant_release_anchor_tick'], 6)

        same_column = details['same_column_e']
        self.assertEqual(same_column['q_instant_release_tick'], 2)
        self.assertEqual(same_column['end_tick'], 2)
        self.assertEqual(same_column['duration_ticks'], 0)
        self.assertEqual(same_column['q_instant_release_anchor_tick'], 6)


if __name__ == '__main__':
    unittest.main()
