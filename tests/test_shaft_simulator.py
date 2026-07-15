import unittest
from copy import deepcopy

from app.modules.shaft.service import normalize_axis_payload, simulate_shaft_axis
from app.modules.shaft.domain.buffs import registered_buff_rules
from app.modules.shaft.domain.catalog import load_shaft_catalog


class ShaftSimulatorValidationTestCase(unittest.TestCase):
    def test_team_furniture_bonus_uses_actual_caps(self) -> None:
        normalized = normalize_axis_payload({})

        self.assertEqual(
            normalized['team_panel_bonus'],
            {
                'version': 3,
                'furniture_crit_dmg': 0.04,
                'furniture_flat_atk': 20.0,
                'furniture_flat_def': 30.0,
                'small_flat_atk': 420.0,
                'small_flat_hp': 5200.0,
            },
        )

    def test_team_furniture_bonus_is_editable_and_clamped_to_caps(self) -> None:
        normalized = normalize_axis_payload({
            'team_panel_bonus': {
                'version': 3,
                'furniture_crit_dmg': 0.0264,
                'furniture_flat_atk': 12.8,
                'furniture_flat_def': 99,
            },
        })

        self.assertEqual(normalized['team_panel_bonus']['furniture_crit_dmg'], 0.026)
        self.assertEqual(normalized['team_panel_bonus']['furniture_flat_atk'], 13.0)
        self.assertEqual(normalized['team_panel_bonus']['furniture_flat_def'], 30.0)

        minimum = normalize_axis_payload({
            'team_panel_bonus': {
                'version': 3,
                'furniture_crit_dmg': -1,
                'furniture_flat_atk': -1,
                'furniture_flat_def': -1,
            },
        })['team_panel_bonus']
        self.assertEqual(minimum['furniture_crit_dmg'], 0.0)
        self.assertEqual(minimum['furniture_flat_atk'], 0.0)
        self.assertEqual(minimum['furniture_flat_def'], 0.0)

    def test_support_owner_can_chain_q_without_switch_loss(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'other_e', 'slot': 1, 'action_id': 'action_5870d8ba67', 'start_tick': 0},
                {'id': 'support', 'slot': 0, 'action_id': 'action_33c0ac631e', 'start_tick': 2},
                {'id': 'owner_q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 16},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['support']['visual_start_tick'], 2)
        self.assertEqual(details['support']['visual_end_tick'], 16)
        self.assertEqual(details['owner_q']['visual_start_tick'], 16)

    def test_support_blocks_foreground_starts_until_support_ends(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'support', 'slot': 0, 'action_id': 'action_33c0ac631e', 'start_tick': 0},
                {'id': 'intruding_e', 'slot': 1, 'action_id': 'action_5870d8ba67', 'start_tick': 5},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['support']['visual_start_tick'], 0)
        self.assertEqual(details['support']['visual_end_tick'], 14)
        self.assertEqual(details['intruding_e']['raw_start_tick'], 5)
        self.assertEqual(details['intruding_e']['visual_start_tick'], 14)

    def test_different_foreground_starts_with_short_gap_still_compute(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': 'arc_d75aa15b91',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'front_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'nanaly_e', 'slot': 1, 'action_id': 'action_5870d8ba67', 'start_tick': 1},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['details']), 2)

    def test_different_foreground_starts_allow_two_tick_gap(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': 'arc_d75aa15b91',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'front_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'nanaly_e', 'slot': 1, 'action_id': 'action_5870d8ba67', 'start_tick': 2},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['front_e']['start_tick'], 0)
        self.assertEqual(details['nanaly_e']['start_tick'], 2)

    def test_q_display_ticks_drive_forest_firefly_buff_line(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 2,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'main_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'nanaly_q', 'slot': 2, 'action_id': 'action_0f1e29b8ca', 'start_tick': 7},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        nanaly_q = details['nanaly_q']
        firefly_buffs = [
            buff for buff in nanaly_q['triggered_buffs']
            if buff.get('rule_id') == 'cartridge_forest_firefly_crit_stack'
        ]

        self.assertEqual(nanaly_q['raw_start_tick'], 7)
        self.assertEqual(nanaly_q['visual_start_tick'], 9)
        self.assertEqual(nanaly_q['display_start_tick'], nanaly_q['visual_start_tick'])
        self.assertEqual(nanaly_q['display_visual_end_tick'], nanaly_q['visual_end_tick'])
        self.assertEqual(nanaly_q['q_cover_target_step_ids'], ['main_e'])
        self.assertEqual(len(firefly_buffs), 1)
        self.assertEqual(firefly_buffs[0]['trigger_tick'], nanaly_q['display_start_tick'])
        self.assertEqual(firefly_buffs[0]['display_start_tick'], nanaly_q['display_start_tick'])
        self.assertEqual(firefly_buffs[0]['visual_start_tick'], nanaly_q['display_start_tick'])

    def test_foreground_starts_allow_two_internal_sequence_gap_at_same_real_time(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'main_q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 0},
                {'id': 'zhenhong_q', 'slot': 1, 'action_id': 'action_c32b4b9417', 'start_tick': 2},
                {'id': 'dragon_a1', 'slot': 1, 'action_id': 'action_40e3b63106', 'start_tick': 4},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['main_q']['start_tick'], 0)
        self.assertEqual(details['zhenhong_q']['start_tick'], 0)
        self.assertEqual(details['dragon_a1']['start_tick'], 0)
        self.assertEqual(details['dragon_a1']['end_tick'], 3)
        self.assertEqual(details['dragon_a1']['duration_ticks'], 3)

    def test_foreground_starts_same_visual_tick_with_q_still_compute(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'main_q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 0},
                {'id': 'dragon_a1', 'slot': 1, 'action_id': 'action_40e3b63106', 'start_tick': 0},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['details']), 2)

    def test_zero_duration_q_end_can_switch_character_without_switch_loss(self) -> None:
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
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': 'arc_d75aa15b91',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'zhenhong_q2', 'slot': 0, 'action_id': 'action_e3711f0cf5', 'start_tick': 0},
                {'id': 'nanaly_e', 'slot': 1, 'action_id': 'action_5870d8ba67', 'start_tick': 5},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['zhenhong_q2']['start_tick'], 0)
        self.assertEqual(details['zhenhong_q2']['end_tick'], 0)
        self.assertEqual(details['nanaly_e']['start_tick'], 0)

    def test_non_q_end_switches_character_with_switch_loss(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': 'arc_d75aa15b91',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'front_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'nanaly_e', 'slot': 1, 'action_id': 'action_5870d8ba67', 'start_tick': 15},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['front_e']['end_tick'], 15)
        self.assertEqual(details['nanaly_e']['start_tick'], 17)

    def test_q_starts_can_share_visual_column_for_tolerant_compute(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
            ],
            'steps': [
                {'id': 'main_q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 0},
                {'id': 'zhenhong_q', 'slot': 1, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['details']), 2)


class ShaftSimulatorQInstantReleaseTestCase(unittest.TestCase):
    def test_q_does_not_cover_other_foreground_support_or_q(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 2,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'main_support', 'slot': 0, 'action_id': 'action_33c0ac631e', 'start_tick': 0},
                {'id': 'zhenhong_q2', 'slot': 1, 'action_id': 'action_e3711f0cf5', 'start_tick': 0},
                {'id': 'nanaly_q', 'slot': 2, 'action_id': 'action_0f1e29b8ca', 'start_tick': 4},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertFalse(details['main_support']['q_instant_release'])
        self.assertEqual(details['main_support']['duration_ticks'], 14)
        self.assertFalse(details['zhenhong_q2']['q_instant_release'])
        self.assertEqual(details['zhenhong_q2']['duration_ticks'], 0)
        self.assertEqual(details['nanaly_q'].get('q_cover_target_step_ids', []), [])

    def test_zhenhong_traverse_is_an_ordinary_action_but_q2_has_q_cover(self) -> None:
        base_payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }
        traverse_payload = {
            **base_payload,
            'steps': [
                {'id': 'traverse', 'slot': 1, 'action_id': 'action_a17ac7c5b7', 'start_tick': 0},
                {'id': 'main_q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 2},
            ],
        }
        q2_payload = {
            **base_payload,
            'steps': [
                {'id': 'main_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'zhenhong_q2', 'slot': 1, 'action_id': 'action_e3711f0cf5', 'start_tick': 2},
            ],
        }
        q2_avoid_payload = {
            **base_payload,
            'steps': [
                {'id': 'zhenhong_q2', 'slot': 1, 'action_id': 'action_e3711f0cf5', 'start_tick': 0},
                {'id': 'main_q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 2},
            ],
        }

        traverse_result = simulate_shaft_axis(traverse_payload)['result']
        traverse_details = {detail['step_id']: detail for detail in traverse_result['details']}
        q2_result = simulate_shaft_axis(q2_payload)['result']
        q2_details = {detail['step_id']: detail for detail in q2_result['details']}
        q2_avoid_result = simulate_shaft_axis(q2_avoid_payload)['result']
        q2_avoid_details = {detail['step_id']: detail for detail in q2_avoid_result['details']}

        self.assertTrue(traverse_details['traverse']['q_instant_release'])
        self.assertEqual(traverse_details['traverse']['duration_ticks'], 2)
        self.assertFalse(q2_details['zhenhong_q2']['q_instant_release'])
        self.assertTrue(q2_details['main_e']['q_instant_release'])
        self.assertEqual(q2_details['zhenhong_q2']['q_cover_target_step_ids'], ['main_e'])
        self.assertFalse(q2_avoid_details['zhenhong_q2']['q_instant_release'])

    def test_q_instant_release_keeps_visual_length_and_elapsed_until_q(self) -> None:
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
                {'id': 'same_column_e', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 2},
                {'id': 'q_anchor', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 4},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        foreground = details['foreground_e']
        self.assertTrue(foreground['q_instant_release'])
        self.assertEqual(foreground['q_instant_release_kind'], 'column')
        self.assertEqual(foreground['end_tick'], 4)
        self.assertEqual(foreground['duration_ticks'], 4)
        self.assertEqual(foreground['calculation_start_sequence'], 0)
        self.assertEqual(foreground['calculation_end_sequence'], 1)
        self.assertEqual(foreground['visual_end_tick'], 10)
        self.assertEqual(foreground['original_duration_ticks'], 10)
        self.assertEqual(foreground['q_instant_release_calculation_tick'], 4)
        self.assertEqual(foreground['q_instant_release_anchor_tick'], 4)
        self.assertEqual(foreground['q_instant_release_anchor_step_id'], 'q_anchor')
        self.assertEqual(foreground['q_instant_release_start_sequence'], 0)
        self.assertEqual(foreground['q_instant_release_end_sequence'], 1)

        q_anchor = details['q_anchor']
        self.assertEqual(q_anchor['raw_start_tick'], 4)
        self.assertEqual(q_anchor['start_tick'], 4)
        self.assertEqual(q_anchor['duration_ticks'], 0)
        self.assertEqual(q_anchor['visual_end_tick'], 13)
        self.assertEqual(q_anchor['q_cover_visual_end_tick'], 13)
        self.assertEqual(q_anchor['q_cover_target_step_ids'], ['foreground_e', 'same_column_e'])

        same_column = details['same_column_e']
        self.assertTrue(same_column['q_instant_release'])
        self.assertEqual(same_column['q_instant_release_kind'], 'column')
        self.assertEqual(same_column['end_tick'], 4)
        self.assertEqual(same_column['duration_ticks'], 2)
        self.assertEqual(same_column['calculation_start_sequence'], 0)
        self.assertEqual(same_column['calculation_end_sequence'], 1)
        self.assertEqual(same_column['visual_end_tick'], 13)
        self.assertEqual(same_column['original_duration_ticks'], 11)
        self.assertEqual(same_column['q_instant_release_calculation_tick'], 4)
        self.assertEqual(same_column['q_instant_release_anchor_tick'], 4)
        self.assertEqual(same_column['q_instant_release_anchor_step_id'], 'q_anchor')
        self.assertEqual(same_column['q_instant_release_start_sequence'], 0)
        self.assertEqual(same_column['q_instant_release_end_sequence'], 1)

    def test_q_instant_release_keeps_q_visual_width(self) -> None:
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
                {'id': 'same_column_e', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 2},
                {'id': 'q_anchor', 'slot': 1, 'action_id': 'action_e3711f0cf5', 'start_tick': 4},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        q_anchor = details['q_anchor']
        self.assertEqual(q_anchor['start_tick'], 4)
        self.assertEqual(q_anchor['end_tick'], 4)
        self.assertEqual(q_anchor['duration_ticks'], 0)
        self.assertEqual(q_anchor['visual_end_tick'], 15)
        self.assertEqual(q_anchor['q_cover_visual_end_tick'], 15)
        self.assertEqual(q_anchor['q_cover_target_step_ids'], ['foreground_e', 'same_column_e'])
        self.assertFalse(q_anchor['q_instant_release'])

        foreground = details['foreground_e']
        self.assertEqual(foreground['q_instant_release_tick'], 4)
        self.assertEqual(foreground['end_tick'], 4)
        self.assertEqual(foreground['duration_ticks'], 4)
        self.assertEqual(foreground['calculation_start_sequence'], 0)
        self.assertEqual(foreground['calculation_end_sequence'], 1)
        self.assertEqual(foreground['visual_end_tick'], 15)
        self.assertEqual(foreground['q_instant_release_calculation_tick'], 4)
        self.assertEqual(foreground['q_instant_release_anchor_tick'], 4)
        self.assertEqual(foreground['q_instant_release_start_sequence'], 0)
        self.assertEqual(foreground['q_instant_release_end_sequence'], 1)

        same_column = details['same_column_e']
        self.assertEqual(same_column['q_instant_release_tick'], 4)
        self.assertEqual(same_column['end_tick'], 4)
        self.assertEqual(same_column['duration_ticks'], 2)
        self.assertEqual(same_column['calculation_start_sequence'], 0)
        self.assertEqual(same_column['calculation_end_sequence'], 1)
        self.assertEqual(same_column['visual_end_tick'], 13)
        self.assertEqual(same_column['q_instant_release_calculation_tick'], 4)
        self.assertEqual(same_column['q_instant_release_anchor_tick'], 4)
        self.assertEqual(same_column['q_instant_release_start_sequence'], 0)
        self.assertEqual(same_column['q_instant_release_end_sequence'], 1)

    def test_q_instant_release_covers_connected_basic_background_attacks(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_d38b672525',
                    'arc_id': 'arc_27dc4a7281',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
            ],
            'steps': [
                {'id': 'ka_a2', 'slot': 1, 'action_id': 'action_48204bed53', 'start_tick': 0, 'placement': 'background'},
                {'id': 'q_anchor', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 2},
                {'id': 'ka_a3', 'slot': 1, 'action_id': 'action_09bd76720d', 'start_tick': 6, 'placement': 'background'},
                {'id': 'ka_a4', 'slot': 1, 'action_id': 'action_90b1619681', 'start_tick': 11},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        q_anchor = details['q_anchor']
        self.assertEqual(q_anchor['visual_end_tick'], 21)
        self.assertEqual(q_anchor['q_cover_visual_end_tick'], 21)
        self.assertEqual(q_anchor['q_cover_target_step_ids'], ['ka_a2', 'ka_a3', 'ka_a4'])

        first_basic = details['ka_a2']
        self.assertTrue(first_basic['is_basic_background'])
        self.assertTrue(first_basic['q_instant_release'])
        self.assertEqual(first_basic['q_instant_release_kind'], 'column')
        self.assertEqual(first_basic['duration_ticks'], 2)
        self.assertEqual(first_basic['end_tick'], 2)
        self.assertEqual(first_basic['calculation_start_sequence'], 0)
        self.assertEqual(first_basic['calculation_end_sequence'], 1)
        self.assertEqual(first_basic['visual_end_tick'], 6)
        self.assertEqual(first_basic['q_instant_release_calculation_tick'], 2)
        self.assertEqual(first_basic['q_instant_release_start_sequence'], 0)
        self.assertEqual(first_basic['q_instant_release_end_sequence'], 1)

        chained_basic = details['ka_a3']
        self.assertTrue(chained_basic['is_basic_background'])
        self.assertTrue(chained_basic['q_instant_release'])
        self.assertEqual(chained_basic['q_instant_release_kind'], 'basic-background')
        self.assertEqual(chained_basic['duration_ticks'], 0)
        self.assertEqual(chained_basic['start_tick'], 2)
        self.assertEqual(chained_basic['end_tick'], 2)
        self.assertEqual(chained_basic['calculation_start_sequence'], 1)
        self.assertEqual(chained_basic['calculation_end_sequence'], 2)
        self.assertEqual(chained_basic['visual_start_tick'], 6)
        self.assertEqual(chained_basic['visual_end_tick'], 11)
        self.assertEqual(chained_basic['q_instant_release_calculation_tick'], 2)
        self.assertEqual(chained_basic['q_instant_release_start_sequence'], 1)
        self.assertEqual(chained_basic['q_instant_release_end_sequence'], 2)

        foreground_capable_basic = details['ka_a4']
        self.assertFalse(foreground_capable_basic['is_basic_background'])
        self.assertTrue(foreground_capable_basic['q_instant_release'])
        self.assertEqual(foreground_capable_basic['q_instant_release_kind'], 'basic-background')
        self.assertEqual(foreground_capable_basic['duration_ticks'], 0)
        self.assertEqual(foreground_capable_basic['start_tick'], 2)
        self.assertEqual(foreground_capable_basic['end_tick'], 2)
        self.assertEqual(foreground_capable_basic['calculation_start_sequence'], 2)
        self.assertEqual(foreground_capable_basic['calculation_end_sequence'], 3)
        self.assertEqual(foreground_capable_basic['visual_start_tick'], 11)
        self.assertEqual(foreground_capable_basic['visual_end_tick'], 21)
        self.assertEqual(foreground_capable_basic['q_instant_release_calculation_tick'], 2)
        self.assertEqual(foreground_capable_basic['q_instant_release_start_sequence'], 2)
        self.assertEqual(foreground_capable_basic['q_instant_release_end_sequence'], 3)

    def test_q_instant_release_uses_sequence_for_zhenhong_dragon_chain(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'dragon_a4', 'slot': 0, 'action_id': 'action_5cd7ad2380', 'start_tick': 0, 'placement': 'background'},
                {'id': 'teammate_q', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 2},
                {'id': 'dragon_a5', 'slot': 0, 'action_id': 'action_cf3b21dac1', 'start_tick': 8, 'placement': 'background'},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        dragon_a4 = details['dragon_a4']
        self.assertTrue(dragon_a4['q_instant_release'])
        self.assertEqual(dragon_a4['q_instant_release_kind'], 'column')
        self.assertEqual(dragon_a4['start_tick'], 0)
        self.assertEqual(dragon_a4['end_tick'], 2)
        self.assertEqual(dragon_a4['duration_ticks'], 2)
        self.assertEqual(dragon_a4['calculation_start_sequence'], 0)
        self.assertEqual(dragon_a4['calculation_end_sequence'], 1)
        self.assertEqual(dragon_a4['visual_start_tick'], 0)
        self.assertEqual(dragon_a4['visual_end_tick'], 8)
        self.assertEqual(dragon_a4['q_instant_release_calculation_tick'], 2)
        self.assertEqual(dragon_a4['q_instant_release_start_sequence'], 0)
        self.assertEqual(dragon_a4['q_instant_release_end_sequence'], 1)

        dragon_a5 = details['dragon_a5']
        self.assertTrue(dragon_a5['q_instant_release'])
        self.assertEqual(dragon_a5['q_instant_release_kind'], 'basic-background')
        self.assertEqual(dragon_a5['start_tick'], 2)
        self.assertEqual(dragon_a5['end_tick'], 2)
        self.assertEqual(dragon_a5['duration_ticks'], 0)
        self.assertEqual(dragon_a5['calculation_start_sequence'], 1)
        self.assertEqual(dragon_a5['calculation_end_sequence'], 2)
        self.assertEqual(dragon_a5['visual_start_tick'], 8)
        self.assertEqual(dragon_a5['visual_end_tick'], 18)
        self.assertEqual(dragon_a5['q_instant_release_calculation_tick'], 2)
        self.assertEqual(dragon_a5['q_instant_release_start_sequence'], 1)
        self.assertEqual(dragon_a5['q_instant_release_end_sequence'], 2)

        teammate_q = details['teammate_q']
        self.assertFalse(teammate_q['q_instant_release'])
        self.assertEqual(teammate_q['start_tick'], 2)
        self.assertEqual(teammate_q['end_tick'], 2)
        self.assertEqual(result['summary']['duration_ticks'], 2)

    def test_q_cover_width_expands_over_background_chain_and_keeps_followup_sequence(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'zhenhong_a4', 'slot': 0, 'action_id': 'action_5cd7ad2380', 'start_tick': 0},
                {'id': 'main_q', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 2},
                {'id': 'zhenhong_a5', 'slot': 0, 'action_id': 'action_cf3b21dac1', 'start_tick': 8, 'placement': 'background'},
                {'id': 'main_e', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 18},
                {'id': 'zhenhong_q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 20},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        main_q = details['main_q']
        self.assertFalse(main_q['q_instant_release'])
        self.assertEqual(main_q['start_tick'], 2)
        self.assertEqual(main_q['end_tick'], 2)
        self.assertEqual(main_q['visual_start_tick'], 2)
        self.assertEqual(main_q['visual_end_tick'], 18)
        self.assertEqual(main_q['q_cover_visual_end_tick'], 18)
        self.assertEqual(main_q['q_cover_target_step_ids'], ['zhenhong_a4', 'zhenhong_a5'])

        zhenhong_a4 = details['zhenhong_a4']
        self.assertTrue(zhenhong_a4['q_instant_release'])
        self.assertEqual(zhenhong_a4['end_tick'], 2)
        self.assertEqual(zhenhong_a4['duration_ticks'], 2)
        self.assertEqual(zhenhong_a4['calculation_start_sequence'], 0)
        self.assertEqual(zhenhong_a4['calculation_end_sequence'], 1)
        self.assertEqual(zhenhong_a4['visual_end_tick'], 8)

        zhenhong_a5 = details['zhenhong_a5']
        self.assertTrue(zhenhong_a5['q_instant_release'])
        self.assertEqual(zhenhong_a5['start_tick'], 2)
        self.assertEqual(zhenhong_a5['end_tick'], 2)
        self.assertEqual(zhenhong_a5['duration_ticks'], 0)
        self.assertEqual(zhenhong_a5['calculation_start_sequence'], 1)
        self.assertEqual(zhenhong_a5['calculation_end_sequence'], 2)
        self.assertEqual(zhenhong_a5['visual_end_tick'], 18)

        main_e = details['main_e']
        self.assertEqual(main_e['start_tick'], 2)
        self.assertTrue(main_e['q_instant_release'])
        self.assertEqual(main_e['q_instant_release_anchor_step_id'], 'zhenhong_q')
        self.assertEqual(main_e['end_tick'], 4)
        self.assertEqual(main_e['duration_ticks'], 2)

        zhenhong_q = details['zhenhong_q']
        self.assertFalse(zhenhong_q['q_instant_release'])
        self.assertEqual(zhenhong_q['start_tick'], 4)
        self.assertEqual(zhenhong_q['end_tick'], 4)
        self.assertEqual(zhenhong_q['visual_start_tick'], 20)
        self.assertGreaterEqual(zhenhong_q['visual_start_tick'], zhenhong_a5['visual_end_tick'])
        self.assertEqual(result['summary']['duration_ticks'], 4)

    def test_foreground_basic_starting_after_q_sequence_keeps_duration(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'zhenhong_q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
                {'id': 'other_q', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 2},
                {'id': 'dragon_a1', 'slot': 0, 'action_id': 'action_40e3b63106', 'start_tick': 4},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        dragon_a1 = details['dragon_a1']

        self.assertFalse(dragon_a1['q_instant_release'])
        self.assertEqual(dragon_a1['duration_ticks'], 3)
        self.assertEqual(dragon_a1['end_tick'], dragon_a1['start_tick'] + 3)
        self.assertEqual(dragon_a1['original_duration_ticks'], 3)

    def test_support_does_not_receive_switch_loss(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_f4282fad3f',
                },
                {
                    'slot': 1,
                    'character_id': 'char_bdc43f82c6',
                    'arc_id': 'arc_d75aa15b91',
                    'cartridge_id': 'cartridge_29793225a0',
                },
            ],
            'steps': [
                {'id': 'front_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'support', 'slot': 1, 'action_id': 'action_482b5d9df7', 'start_tick': 5},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['front_e']['start_tick'], 0)
        self.assertEqual(details['support']['start_tick'], 5)
        self.assertEqual(details['support']['duration_ticks'], 13)


class ShaftEquipmentBuffTestCase(unittest.TestCase):
    def test_arc_q_buff_is_not_constant_and_applies_from_q_start(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': 'arc_27dc4a7281',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'before_q_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 0},
                {'id': 'q_trigger', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 20},
                {'id': 'after_q_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 22},
            ],
            'initial_energy': 200,
        }

        baseline_payload = deepcopy(payload)
        baseline_payload['team'][0]['arc_id'] = ''
        baseline_details = {
            detail['step_id']: detail
            for detail in simulate_shaft_axis(baseline_payload)['result']['details']
        }
        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        before_q = details['before_q_e']
        self.assertEqual(before_q['applied_buffs'], [])
        self.assertAlmostEqual(before_q['formula_parts']['dmg_bonus'], 0.0)

        q_trigger = details['q_trigger']
        self.assertIn(
            'arc_crimson_mirage_q_light_def',
            {buff['rule_id'] for buff in q_trigger['triggered_buffs']},
        )
        self.assertIn(
            'arc_crimson_mirage_q_light_def',
            {buff['rule_id'] for buff in q_trigger['applied_buffs']},
        )
        self.assertAlmostEqual(
            q_trigger['formula_parts']['dmg_bonus'] - baseline_details['q_trigger']['formula_parts']['dmg_bonus'],
            0.32,
        )

        after_q = details['after_q_e']
        self.assertIn(
            'arc_crimson_mirage_q_light_def',
            {buff['rule_id'] for buff in after_q['applied_buffs']},
        )
        self.assertAlmostEqual(
            after_q['formula_parts']['dmg_bonus'] - baseline_details['after_q_e']['formula_parts']['dmg_bonus'],
            0.32,
        )

    def test_cartridge_e_buff_applies_from_e_start(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_097acfc8f6',
                },
            ],
            'steps': [
                {'id': 'first_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 0},
                {'id': 'second_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 16},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        first_e = details['first_e']
        second_e = details['second_e']
        self.assertIn(
            'cartridge_shadow_creed_e_atk',
            {buff['rule_id'] for buff in first_e['triggered_buffs']},
        )
        self.assertIn(
            'cartridge_shadow_creed_e_atk',
            {buff['rule_id'] for buff in first_e['applied_buffs']},
        )
        self.assertIn(
            'cartridge_shadow_creed_e_atk',
            {buff['rule_id'] for buff in second_e['applied_buffs']},
        )
        self.assertAlmostEqual(second_e['panel']['atk'], first_e['panel']['atk'])

    def test_bit_game_refine1_background_attack_applies_to_front_character(self) -> None:
        base_payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'zhenhong_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 0},
            ],
            'initial_energy': 200,
        }
        bit_game_payload = {
            **base_payload,
            'team': [
                base_payload['team'][0],
                {
                    **base_payload['team'][1],
                    'arc_id': 'arc_a5b483cca6',
                },
            ],
        }

        base_detail = simulate_shaft_axis(base_payload)['result']['details'][0]
        bit_game_detail = simulate_shaft_axis(bit_game_payload)['result']['details'][0]

        self.assertIn(
            'arc_bit_game_background_front_atk',
            {buff['rule_id'] for buff in bit_game_detail['triggered_buffs']},
        )
        self.assertIn(
            'arc_bit_game_background_front_atk',
            {buff['rule_id'] for buff in bit_game_detail['applied_buffs']},
        )
        self.assertGreater(bit_game_detail['direct_damage'], base_detail['direct_damage'])

    def test_zhenhong_q_matches_xlsx_low_bit_game_after_yi_q(self) -> None:
        catalog = load_shaft_catalog()
        starter = catalog['starter_axis']
        payload = {
            'team': deepcopy(starter['team']),
            'character_builds': deepcopy(starter.get('character_builds') or {}),
            'team_panel_bonus': deepcopy(starter.get('team_panel_bonus') or {}),
            'options': {'switch_loss_ticks': 0, 'front_state_enabled': True},
            'steps': [
                {'id': 'yi_q', 'slot': 3, 'action_id': 'action_6ece34aff8', 'start_tick': 0},
                {'id': 'zhenhong_q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 2},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        detail = next(item for item in result['details'] if item['step_id'] == 'zhenhong_q')

        self.assertAlmostEqual(detail['direct_damage'], 76297.39612343984)
        self.assertAlmostEqual(detail['formula_parts']['resistance'], 0.7)
        self.assertAlmostEqual(detail['formula_parts']['defense'], 0.6134969325153374)
        self.assertIn(
            'cartridge_lost_light_q_def_ignore',
            {buff['rule_id'] for buff in detail['applied_buffs']},
        )

    def test_def_down_is_reserved_for_sagiri_character_buff(self) -> None:
        catalog = load_shaft_catalog()
        def_down_buffs = [
            buff for buff in catalog['buffs']
            if (buff.get('effects') or {}).get('def_down')
        ]
        self.assertEqual(
            [buff['id'] for buff in def_down_buffs],
            ['character_sagiri_control_def_down'],
        )

        rules = registered_buff_rules(
            [
                {
                    'slot': 0,
                    'character_id': 'char_1895e259be',
                    'character_name': '早雾',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            catalog,
        )
        sagiri_rule = next(rule for rule in rules if rule['id'] == 'character_sagiri_control_def_down')
        self.assertEqual(sagiri_rule['provider_kind'], 'character')
        self.assertEqual(sagiri_rule['effects']['def_down'], 0.1)

    def test_bit_game_refine1_psyche_damage_stacks_and_resets_on_switch(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_e0a4292b4e',
                    'arc_id': 'arc_a5b483cca6',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'first_basic', 'slot': 0, 'action_id': 'action_519f3d978a', 'start_tick': 0},
                {'id': 'second_basic', 'slot': 0, 'action_id': 'action_519f3d978a', 'start_tick': 20},
                {'id': 'switch_to_zhenhong', 'slot': 1, 'action_id': 'action_3987d8ff2d', 'start_tick': 40},
                {'id': 'after_switch_basic', 'slot': 0, 'action_id': 'action_519f3d978a', 'start_tick': 60},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        panel = next(item for item in result['build_panels_by_slot'] if item['slot'] == 0)

        self.assertAlmostEqual(panel['panel']['element_dmg'], 0.0)
        self.assertIn(
            'arc_bit_game_foreground_psyche_dmg',
            {buff['rule_id'] for buff in details['first_basic']['applied_buffs']},
        )
        self.assertNotIn(
            'arc_bit_game_basic_psyche_stack',
            {buff['rule_id'] for buff in details['first_basic']['applied_buffs']},
        )
        self.assertAlmostEqual(details['first_basic']['formula_parts']['dmg_bonus'], 0.12)
        self.assertIn(
            'arc_bit_game_basic_psyche_stack',
            {buff['rule_id'] for buff in details['second_basic']['applied_buffs']},
        )
        self.assertAlmostEqual(details['second_basic']['formula_parts']['dmg_bonus'], 0.14)
        self.assertAlmostEqual(details['after_switch_basic']['formula_parts']['dmg_bonus'], 0.12)

    def test_legacy_axis_buff_rules_still_use_runtime_buff_path(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'first_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 0},
                {'id': 'second_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 16},
            ],
            'buff_rules': [
                {
                    'id': 'legacy_manual_atk',
                    'name': '旧手动攻击增益',
                    'trigger': {'slot': 0, 'action_id': 'action_3987d8ff2d'},
                    'targets': {'slots': [0]},
                    'duration_ticks': 100,
                    'modifiers': {'atk_pct': 0.5},
                },
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['first_e']['applied_buffs'], [])
        self.assertIn(
            'legacy_manual_atk',
            {buff['rule_id'] for buff in details['first_e']['triggered_buffs']},
        )
        self.assertIn(
            'legacy_manual_atk',
            {buff['rule_id'] for buff in details['second_e']['applied_buffs']},
        )
        self.assertGreater(details['second_e']['panel']['atk'], details['first_e']['panel']['atk'])

    def test_catalog_records_hit_count_for_every_action(self) -> None:
        catalog = load_shaft_catalog()
        self.assertTrue(catalog['actions'])
        self.assertTrue(all('hit_count' in action for action in catalog['actions']))
        xiaozhi_a4 = next(action for action in catalog['actions'] if action['id'] == 'action_bc6c8ca82b')
        self.assertEqual(xiaozhi_a4['hit_count'], 5)

    def test_zhenhong_ascendant_red_and_awakened_q1_resonance(self) -> None:
        catalog = load_shaft_catalog()
        actions = {
            action['id']: action
            for action in catalog['actions']
            if action.get('character_name') == '真红'
        }
        ascendant_red_action_ids = {
            'action_c32b4b9417',
            'action_40e3b63106',
            'action_c2c019771f',
            'action_f0625f9268',
            'action_5cd7ad2380',
            'action_cf3b21dac1',
            'action_7773821d79',
            'action_a17ac7c5b7',
            'action_e3711f0cf5',
        }
        self.assertEqual(
            {
                actions[action_id]['name']
                for action_id in ascendant_red_action_ids
            },
            {'q', '龙a1', '龙a2', '龙a3', '龙a4', '龙a5', '龙e', '穿梭', 'q2'},
        )
        for action_id in ascendant_red_action_ids:
            self.assertAlmostEqual(actions[action_id]['self_modifiers']['all_dmg'], 0.0)

        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'q1_trigger', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
                {'id': 'dragon_a', 'slot': 0, 'action_id': 'action_40e3b63106', 'start_tick': 2},
                {'id': 'q2_reset', 'slot': 0, 'action_id': 'action_e3711f0cf5', 'start_tick': 5},
                {'id': 'after_q2_dragon_a', 'slot': 0, 'action_id': 'action_40e3b63106', 'start_tick': 7},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        q1_triggered_buffs = {
            buff['rule_id']: buff
            for buff in details['q1_trigger']['triggered_buffs']
        }
        self.assertAlmostEqual(details['q1_trigger']['formula_parts']['dmg_bonus'], 0.3)
        self.assertIn(
            'character_zhenhong_ascendant_red',
            {buff['rule_id'] for buff in details['q1_trigger']['applied_buffs']},
        )
        self.assertFalse(q1_triggered_buffs['character_zhenhong_ascendant_red']['display_as_line'])
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in details['q1_trigger']['triggered_buffs']},
        )
        self.assertIn(
            'character_zhenhong_ascendant_red',
            {buff['rule_id'] for buff in details['dragon_a']['applied_buffs']},
        )
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in details['dragon_a']['applied_buffs']},
        )
        self.assertAlmostEqual(details['dragon_a']['formula_parts']['dmg_bonus'], 0.3)
        self.assertIn(
            'character_zhenhong_ascendant_red',
            {buff['rule_id'] for buff in details['q2_reset']['applied_buffs']},
        )
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in details['q2_reset']['applied_buffs']},
        )
        self.assertAlmostEqual(details['q2_reset']['formula_parts']['dmg_bonus'], 0.3)
        self.assertIn(
            'character_zhenhong_ascendant_red',
            {buff['rule_id'] for buff in details['after_q2_dragon_a']['applied_buffs']},
        )
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in details['after_q2_dragon_a']['applied_buffs']},
        )
        self.assertAlmostEqual(details['after_q2_dragon_a']['formula_parts']['dmg_bonus'], 0.3)

        awakening_payload = deepcopy(payload)
        awakening_payload['team'][0]['awakening'] = 3
        awakening_result = simulate_shaft_axis(awakening_payload)['result']
        awakening_details = {detail['step_id']: detail for detail in awakening_result['details']}
        awakening_q1_triggered_buffs = {
            buff['rule_id']: buff
            for buff in awakening_details['q1_trigger']['triggered_buffs']
        }
        self.assertIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in awakening_details['q1_trigger']['triggered_buffs']},
        )
        self.assertTrue(awakening_q1_triggered_buffs['character_zhenhong_q1_self_all_dmg']['display_as_line'])
        self.assertIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in awakening_details['dragon_a']['applied_buffs']},
        )
        self.assertIn(
            'character_zhenhong_ascendant_red',
            {buff['rule_id'] for buff in awakening_details['dragon_a']['applied_buffs']},
        )
        self.assertAlmostEqual(awakening_details['dragon_a']['formula_parts']['dmg_bonus'], 0.6)
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in awakening_details['q2_reset']['applied_buffs']},
        )
        self.assertAlmostEqual(awakening_details['q2_reset']['formula_parts']['dmg_bonus'], 0.3)
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in awakening_details['after_q2_dragon_a']['applied_buffs']},
        )
        self.assertAlmostEqual(awakening_details['after_q2_dragon_a']['formula_parts']['dmg_bonus'], 0.3)

        leave_front_payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'awakening': 3,
                    'arc_id': '',
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_dd034941ef',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'q1_trigger', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
                {'id': 'leave_front', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 2},
                {'id': 'after_leave_dragon_a', 'slot': 0, 'action_id': 'action_40e3b63106', 'start_tick': 4},
            ],
            'initial_energy': 200,
        }

        leave_front_result = simulate_shaft_axis(leave_front_payload)['result']
        leave_front_details = {detail['step_id']: detail for detail in leave_front_result['details']}
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in leave_front_details['after_leave_dragon_a']['applied_buffs']},
        )
        self.assertAlmostEqual(leave_front_details['after_leave_dragon_a']['formula_parts']['dmg_bonus'], 0.3)

        duration_payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'awakening': 3,
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'q1_trigger', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
                {'id': 'within_duration', 'slot': 0, 'action_id': 'action_40e3b63106', 'start_tick': 127},
                {'id': 'after_duration', 'slot': 0, 'action_id': 'action_5cd7ad2380', 'start_tick': 131},
            ],
            'initial_energy': 200,
        }

        duration_result = simulate_shaft_axis(duration_payload)['result']
        duration_details = {detail['step_id']: detail for detail in duration_result['details']}
        self.assertIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in duration_details['within_duration']['applied_buffs']},
        )
        self.assertIn(
            'character_zhenhong_ascendant_red',
            {buff['rule_id'] for buff in duration_details['within_duration']['applied_buffs']},
        )
        self.assertAlmostEqual(duration_details['within_duration']['formula_parts']['dmg_bonus'], 0.6)
        self.assertNotIn(
            'character_zhenhong_q1_self_all_dmg',
            {buff['rule_id'] for buff in duration_details['after_duration']['applied_buffs']},
        )
        self.assertIn(
            'character_zhenhong_ascendant_red',
            {buff['rule_id'] for buff in duration_details['after_duration']['applied_buffs']},
        )
        self.assertAlmostEqual(duration_details['after_duration']['formula_parts']['dmg_bonus'], 0.3)

    def test_fons_condition_defaults_to_full_stacks(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_4f917797cb',
                    'arc_id': 'arc_112b3492d8',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'light_e', 'slot': 0, 'action_id': 'action_09ad16cdd4', 'start_tick': 0},
            ],
            'initial_energy': 200,
        }

        baseline_payload = deepcopy(payload)
        baseline_payload['team'][0]['arc_id'] = ''
        baseline = simulate_shaft_axis(baseline_payload)['result']['details'][0]
        result = simulate_shaft_axis(payload)['result']
        detail = result['details'][0]
        self.assertIn(
            'arc_thinking_cat_fons_light',
            {buff['rule_id'] for buff in detail['triggered_buffs']},
        )
        self.assertIn(
            'arc_thinking_cat_fons_light',
            {buff['rule_id'] for buff in detail['applied_buffs']},
        )
        self.assertAlmostEqual(
            detail['formula_parts']['dmg_bonus'] - baseline['formula_parts']['dmg_bonus'],
            0.25,
        )

    def test_enemy_debuff_applied_triggers_team_reaction_buff(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_9229a5376c',
                },
                {
                    'slot': 1,
                    'character_id': 'char_d38b672525',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'delay_apply', 'slot': 1, 'action_id': 'action_be26cd6a7c', 'start_tick': 0},
                {'id': 'owner_after_delay', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 1},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertIn('延滞', details['delay_apply']['applied_enemy_debuffs'])
        self.assertIn(
            'cartridge_street_boxer_delay_reaction',
            {buff['rule_id'] for buff in details['delay_apply']['triggered_buffs']},
        )
        self.assertIn(
            'cartridge_street_boxer_delay_reaction',
            {buff['rule_id'] for buff in details['owner_after_delay']['applied_buffs']},
        )

    def test_self_hp_loss_tag_triggers_hp_loss_buff(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_caa6c2e5a8',
                    'arc_id': '',
                    'cartridge_id': 'cartridge_868dbc2c5c',
                },
            ],
            'steps': [
                {'id': 'hp_loss', 'slot': 0, 'action_id': 'action_bdc49de5c5', 'start_tick': 0},
                {'id': 'after_hp_loss', 'slot': 0, 'action_id': 'action_72051426d5', 'start_tick': 1},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertIn('self_hp_loss', details['hp_loss']['action_tags'])
        self.assertIn(
            'cartridge_little_adventure_hp_stack',
            {buff['rule_id'] for buff in details['hp_loss']['triggered_buffs']},
        )
        self.assertIn(
            'cartridge_little_adventure_hp_stack',
            {buff['rule_id'] for buff in details['after_hp_loss']['applied_buffs']},
        )
        self.assertGreater(details['after_hp_loss']['panel']['hp'], details['hp_loss']['panel']['hp'])

    def test_critical_hit_condition_uses_expected_stacks_from_hit_count(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': 'arc_1ddecc32f3',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'multi_hit', 'slot': 0, 'action_id': 'action_f0625f9268', 'start_tick': 0},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        detail = result['details'][0]
        triggered = {
            buff['rule_id']: buff
            for buff in detail['triggered_buffs']
        }
        self.assertEqual(detail['hit_count'], 6)
        self.assertGreater(detail['expected_critical_hits'], 0)
        self.assertIn('arc_fierce_cotton_crit', triggered)
        self.assertAlmostEqual(triggered['arc_fierce_cotton_crit']['stack_count'], detail['expected_critical_hits'])


if __name__ == '__main__':
    unittest.main()
