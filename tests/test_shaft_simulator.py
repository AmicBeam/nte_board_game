import unittest
from copy import deepcopy

from app.modules.shaft.service import normalize_axis_payload, simulate_shaft_axis
from app.modules.shaft.domain.buffs import activate_buff, registered_buff_rules
from app.modules.shaft.domain.catalog import load_shaft_catalog


class ShaftSimulatorValidationTestCase(unittest.TestCase):
    ZERO_TEAM_PANEL_BONUS = {
        'version': 3,
        'furniture_crit_dmg': 0,
        'furniture_flat_atk': 0,
        'furniture_flat_def': 0,
        'small_flat_atk': 0,
        'small_flat_hp': 0,
    }

    def test_character_sheet_modifiers_are_removed_and_base_crit_is_fixed(self) -> None:
        catalog = load_shaft_catalog()
        for character in catalog['characters']:
            with self.subTest(character=character['name']):
                modifiers = character['modifiers']
                self.assertEqual(modifiers['crit_rate'], 0.05)
                self.assertEqual(modifiers['crit_dmg'], 0.5)
                self.assertTrue(all(
                    value == 0
                    for key, value in modifiers.items()
                    if key not in {'crit_rate', 'crit_dmg'}
                ))

        result = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_701295143d', 'arc_id': '', 'cartridge_id': ''}],
            'steps': [{'id': 'q', 'slot': 0, 'action_id': 'action_9307778f01', 'start_tick': 0}],
            'team_panel_bonus': self.ZERO_TEAM_PANEL_BONUS,
            'initial_energy': 200,
        })['result']
        detail = result['details'][0]
        self.assertEqual(detail['panel']['crit_rate'], 0.05)
        self.assertEqual(detail['panel']['crit_dmg'], 0.5)
        self.assertAlmostEqual(detail['panel']['atk'], 644.0 * 1.2)
        passive = next(buff for buff in detail['applied_buffs'] if buff['rule_id'] == 'character_baizang_atk')
        self.assertEqual(passive['effects'], {'atk_pct': 0.2})
        self.assertFalse(passive['display_as_line'])
        self.assertEqual(passive['line_hidden_reason'], 'passive')

    def test_character_timed_buff_triggers_and_applies_to_later_action(self) -> None:
        result = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_dd034941ef',
                'arc_id': '',
                'cartridge_id': '',
                'awakening': 5,
            }],
            'steps': [
                {'id': 'support', 'slot': 0, 'action_id': 'action_33c0ac631e', 'start_tick': 0},
                {'id': 'q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 14},
            ],
            'team_panel_bonus': self.ZERO_TEAM_PANEL_BONUS,
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertIn(
            'character_protagonist_a5_support_atk',
            {buff['rule_id'] for buff in details['support']['triggered_buffs']},
        )
        applied = {
            buff['rule_id']: buff
            for buff in details['q']['applied_buffs']
        }
        self.assertEqual(applied['character_protagonist_a5_support_atk']['effects'], {'atk_pct': 0.1})

    def test_support_consumes_previous_front_harmony_and_creates_reaction_damage(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'gain', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'support', 'slot': 1, 'action_id': 'action_482b5d9df7', 'start_tick': 20},
            ],
            'team_panel_bonus': self.ZERO_TEAM_PANEL_BONUS,
        })['result']

        details = {detail['step_id']: detail for detail in result['details']}
        effect = details['support']['triggered_reaction']
        self.assertEqual(effect['reaction'], '创生')
        self.assertEqual(effect['support_slot'], 1)
        self.assertEqual(effect['trigger_slot'], effect['contributor_slot'])
        self.assertEqual(effect['trigger_character_name'], effect['contributor_character_name'])
        self.assertEqual(effect['start_tick'], details['support']['visual_end_tick'] - 2)
        self.assertEqual(details['support']['warnings'], [])
        self.assertEqual(result['resources_by_slot'][0]['harmony'], 0)
        self.assertEqual([event['tick'] for event in result['reaction_damage_events']], [51, 71, 91, 111, 131])
        self.assertTrue(all(event['damage'] > 0 for event in result['reaction_damage_events']))
        self.assertEqual(result['summary']['duration_ticks'], 131)

    def test_invalid_or_underfunded_support_is_reported_without_reaction(self) -> None:
        underfunded = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 0},
                {'id': 'support', 'slot': 1, 'action_id': 'action_482b5d9df7', 'start_tick': 20},
            ],
        })['result']
        self.assertFalse(underfunded['reaction_effects'])
        self.assertIn('环合值不足', underfunded['details'][-1]['warnings'][0])

        invalid_pair = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_701295143d', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'gain', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'support', 'slot': 1, 'action_id': 'action_222f577087', 'start_tick': 20},
            ],
        })['result']
        self.assertFalse(invalid_pair['reaction_effects'])
        self.assertIn('无法产生异能环合', invalid_pair['details'][-1]['warnings'][0])

    def test_all_element_pairs_resolve_to_documented_reactions(self) -> None:
        cases = [
            ('延滞', 'char_dd034941ef', 'action_982c67944f', 1, 'char_912dbfe17c', 'action_f229587fd2', 0),
            ('覆纹', 'char_b2e3b2bf7a', 'action_39d4605011', 4, 'char_701295143d', 'action_222f577087', 0),
            ('浊燃', 'char_1895e259be', 'action_4c5142a40f', 4, 'char_c78f7a08d5', 'action_2635f721a8', 15),
            ('黯星', 'char_c78f7a08d5', 'action_6d2645f71e', 7, 'char_caa6c2e5a8', 'action_b0e5fd6662', 1),
            ('浸染', 'char_caa6c2e5a8', 'action_441d3aa300', 4, 'char_912dbfe17c', 'action_f229587fd2', 0),
        ]
        for reaction, previous_character, gain_action, repeats, support_character, support_action, damage_events in cases:
            with self.subTest(reaction=reaction):
                steps = [
                    {'id': f'gain_{index}', 'slot': 0, 'action_id': gain_action, 'start_tick': index * 2}
                    for index in range(repeats)
                ]
                steps.append({'id': 'support', 'slot': 1, 'action_id': support_action, 'start_tick': 40})
                result = simulate_shaft_axis({
                    'team': [
                        {'slot': 0, 'character_id': previous_character, 'arc_id': '', 'cartridge_id': ''},
                        {'slot': 1, 'character_id': support_character, 'arc_id': '', 'cartridge_id': ''},
                    ],
                    'steps': steps,
                })['result']
                self.assertEqual(result['details'][-1]['triggered_reaction']['reaction'], reaction)
                self.assertEqual(len(result['reaction_damage_events']), damage_events)

    def test_loop_axis_primes_previous_reaction_without_extending_loop_height(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'gain', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'support', 'slot': 1, 'action_id': 'action_482b5d9df7', 'start_tick': 20},
            ],
            'options': {'loop_enabled': True},
            'team_panel_bonus': self.ZERO_TEAM_PANEL_BONUS,
        })['result']

        primed = [effect for effect in result['reaction_effects'] if effect['loop_primed']]
        self.assertEqual(len(primed), 1)
        self.assertEqual(primed[0]['start_tick'], -2)
        self.assertEqual(result['summary']['duration_ticks'], 33)
        self.assertEqual([event['tick'] for event in result['reaction_damage_events']], [18])

    def test_passive_damage_actions_do_not_scale_with_skill_level(self) -> None:
        payload = {
            'team': [{
                'slot': 0,
                'character_id': 'char_c78f7a08d5',
                'arc_id': '',
                'cartridge_id': '',
                'skill_levels': {'basic': 1, 'skill': 1, 'ultimate': 1, 'support': 1},
            }],
            'steps': [{'id': 'dissonance', 'slot': 0, 'action_id': 'action_b9b3237c74', 'start_tick': 0}],
            'team_panel_bonus': self.ZERO_TEAM_PANEL_BONUS,
        }
        low = simulate_shaft_axis(payload)['result']['details'][0]
        payload['team'][0]['skill_levels'] = {'basic': 10, 'skill': 10, 'ultimate': 10, 'support': 10}
        high = simulate_shaft_axis(payload)['result']['details'][0]

        self.assertEqual(low['formula_parts']['raw_base'], low['panel']['atk'] * 4)
        self.assertEqual(low['formula_parts']['skill_level_category'], '')
        self.assertEqual(low['formula_parts']['skill_level_multiplier'], 1)
        self.assertAlmostEqual(low['direct_damage'], high['direct_damage'])

    def test_iloy_actions_and_b_awakening_gate_are_available(self) -> None:
        catalog = load_shaft_catalog()
        iloy_actions = {
            action['name']: action
            for action in catalog['actions']
            if action['character_id'] == 'char_a01c39f576'
        }
        self.assertEqual(iloy_actions['援护']['duration_ticks'], 15)
        self.assertEqual(iloy_actions['e']['duration_ticks'], 15)
        self.assertEqual(iloy_actions['q']['duration_ticks'], 0)
        self.assertEqual(iloy_actions['B觉']['multipliers']['atk'], 1.5)
        self.assertEqual(iloy_actions['B觉']['action_type'], '被动')

        base_payload = {
            'team': [{
                'slot': 0,
                'character_id': 'char_a01c39f576',
                'arc_id': '',
                'cartridge_id': '',
                'awakening': 0,
            }],
            'steps': [{'id': 'b', 'slot': 0, 'action_id': 'action_0b76fe2aaa', 'start_tick': 0}],
            'team_panel_bonus': self.ZERO_TEAM_PANEL_BONUS,
        }
        locked = simulate_shaft_axis(base_payload)['result']['details'][0]
        self.assertIn('动作需要 B 觉醒节点。', locked['warnings'])
        base_payload['team'][0]['awakening_nodes'] = [2]
        unlocked = simulate_shaft_axis(base_payload)['result']['details'][0]
        self.assertNotIn('动作需要 B 觉醒节点。', unlocked['warnings'])
        base_payload['team'][0]['awakening_nodes'] = [1]
        wrong_node = simulate_shaft_axis(base_payload)['result']['details'][0]
        self.assertIn('动作需要 B 觉醒节点。', wrong_node['warnings'])

    def test_native_background_action_multiplier_overlaps_damage_at_same_tick(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_4f917797cb',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {
                    'id': 'background',
                    'slot': 0,
                    'action_id': 'action_ed6a3e3c26',
                    'start_tick': 0,
                    'repeat': 3,
                },
            ],
        }

        multiplied = simulate_shaft_axis(payload)
        single = simulate_shaft_axis({
            **payload,
            'steps': [{**payload['steps'][0], 'repeat': 1}],
        })
        detail = multiplied['result']['details'][0]
        single_detail = single['result']['details'][0]

        self.assertEqual(multiplied['axis']['steps'][0]['repeat'], 3)
        self.assertEqual(detail['action_multiplier'], 3)
        self.assertEqual(detail['start_tick'], single_detail['start_tick'])
        self.assertEqual(detail['end_tick'], single_detail['end_tick'])
        self.assertEqual(detail['hit_count'], single_detail['hit_count'] * 3)
        self.assertAlmostEqual(detail['direct_damage'], single_detail['direct_damage'] * 3)

    def test_manual_background_basic_cannot_keep_action_multiplier(self) -> None:
        normalized = normalize_axis_payload({
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_d38b672525',
                    'arc_id': '',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {
                    'id': 'manual_background_basic',
                    'slot': 0,
                    'action_id': 'action_48204bed53',
                    'start_tick': 0,
                    'placement': 'background',
                    'repeat': 7,
                },
            ],
        })

        self.assertEqual(normalized['steps'][0]['placement'], 'background')
        self.assertEqual(normalized['steps'][0]['repeat'], 1)

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

    def test_different_character_can_start_when_support_ends_without_switch_loss(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_7578b18979',
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
                {'id': 'yi_support', 'slot': 0, 'action_id': 'action_31c54a4e71', 'start_tick': 0},
                {'id': 'main_q', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 15},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['yi_support']['visual_end_tick'], 15)
        self.assertEqual(details['main_q']['raw_start_tick'], 15)
        self.assertEqual(details['main_q']['visual_start_tick'], 15)
        self.assertEqual(details['main_q']['start_tick'], 15)

    def test_different_character_zero_duration_q_does_not_pay_switch_loss(self) -> None:
        payload = {
            'team': [
                {'slot': 0, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_7578b18979', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'main_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'yi_q', 'slot': 1, 'action_id': 'action_6ece34aff8', 'start_tick': 15},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(details['yi_q']['raw_start_tick'], 15)
        self.assertEqual(details['yi_q']['visual_start_tick'], 15)
        self.assertEqual(details['yi_q']['start_tick'], 15)

    def test_zhenhong_opening_places_yi_q_at_three_point_two_seconds(self) -> None:
        payload = {
            'team': [
                {'slot': 1, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 2, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 3, 'character_id': 'char_7578b18979', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'yi_support', 'slot': 3, 'action_id': 'action_31c54a4e71', 'start_tick': 0},
                {'id': 'main_q', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 15},
                {'id': 'main_e', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 20},
                {'id': 'nanali_support', 'slot': 2, 'action_id': 'action_482b5d9df7', 'start_tick': 22},
                {'id': 'nanali_q', 'slot': 2, 'action_id': 'action_0f1e29b8ca', 'start_tick': 35},
                {'id': 'nanali_e', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 40},
                {'id': 'yi_q', 'slot': 3, 'action_id': 'action_6ece34aff8', 'start_tick': 42},
            ],
            'options': {'switch_loss_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        yi_q = next(detail for detail in result['details'] if detail['step_id'] == 'yi_q')

        self.assertEqual(yi_q['visual_start_tick'], 42)
        self.assertEqual(yi_q['start_tick'], 32)

    def test_support_locks_other_characters_until_its_end_without_post_lock_loss(self) -> None:
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
        self.assertEqual(details['intruding_e']['foreground_lock_ticks'], 9)
        self.assertEqual(details['intruding_e']['switch_gap_ticks'], 0)

    def test_zero_duration_q_locks_other_characters_for_its_visual_ticks(self) -> None:
        payload = {
            'team': [
                {'slot': 0, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 0},
                {'id': 'same_character', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 2},
                {'id': 'other_character', 'slot': 1, 'action_id': 'action_5870d8ba67', 'start_tick': 2},
            ],
            'options': {'switch_gap_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertEqual(details['same_character']['visual_start_tick'], 5)
        self.assertEqual(details['same_character']['foreground_lock_ticks'], 3)
        self.assertEqual(details['other_character']['visual_start_tick'], 7)
        self.assertEqual(details['other_character']['foreground_lock_ticks'], 3)
        self.assertEqual(details['other_character']['switch_gap_ticks'], 2)

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
        self.assertEqual(nanaly_q['visual_start_tick'], 7)
        self.assertEqual(nanaly_q['display_start_tick'], nanaly_q['visual_start_tick'])
        self.assertEqual(nanaly_q['display_visual_end_tick'], nanaly_q['visual_end_tick'])
        self.assertEqual(nanaly_q['q_cover_target_step_ids'], ['main_e'])
        self.assertEqual(len(firefly_buffs), 1)
        self.assertEqual(firefly_buffs[0]['trigger_tick'], nanaly_q['start_tick'])
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
        self.assertEqual(details['dragon_a1']['visual_start_tick'], details['zhenhong_q']['visual_end_tick'])
        self.assertEqual(details['dragon_a1']['visual_end_tick'] - details['dragon_a1']['visual_start_tick'], 3)

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
        self.assertEqual(details['nanaly_e']['start_tick'], 15)
        self.assertEqual(details['nanaly_e']['visual_start_tick'], 15)
        self.assertEqual(details['nanaly_e']['switch_gap_ticks'], 0)

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
    def test_frozen_q_interval_has_one_real_time_and_preserves_action_tick_lengths(self) -> None:
        payload = {
            'team': [
                {'slot': 0, 'character_id': 'char_b52cc8f160', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'covered_e', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'zhenhong_q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 7},
            ],
            'options': {'switch_gap_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        covered_e = details['covered_e']
        q_interval = result['time_axis']['frozen_intervals'][0]

        self.assertEqual(covered_e['visual_end_tick'] - covered_e['visual_start_tick'], covered_e['original_duration_ticks'])
        self.assertEqual(details['zhenhong_q']['visual_end_tick'], covered_e['visual_end_tick'])
        frozen_start = q_interval['start_tick']
        frozen_end = q_interval['end_tick']

        def real_tick(visual_tick: int) -> int:
            frozen_ticks = sum(
                max(0, min(visual_tick, interval['end_tick']) - interval['start_tick'])
                for interval in result['time_axis']['frozen_intervals']
                if visual_tick > interval['start_tick']
            )
            return visual_tick - frozen_ticks

        self.assertTrue(all(
            real_tick(visual_tick) == real_tick(frozen_start)
            for visual_tick in range(frozen_start, frozen_end + 1)
        ))
        self.assertEqual(covered_e['start_tick'], real_tick(covered_e['visual_start_tick']))
        self.assertEqual(covered_e['end_tick'], real_tick(covered_e['visual_end_tick']))

    def test_expanded_q_lock_delays_switch_and_carries_the_character_sequence(self) -> None:
        payload = {
            'team': [
                {'slot': 0, 'character_id': 'char_b52cc8f160', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 2, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'covered_e', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 7},
                {'id': 'switched_e', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 12},
                {'id': 'same_character_next', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 23},
            ],
            'options': {'switch_gap_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertEqual(details['q']['visual_end_tick'], 15)
        self.assertEqual(details['q']['visual_end_tick'], details['switched_e']['visual_start_tick'])
        self.assertEqual(details['switched_e']['visual_start_tick'], 15)
        self.assertEqual(details['switched_e']['foreground_lock_ticks'], 3)
        self.assertEqual(details['same_character_next']['visual_start_tick'], 26)
        self.assertEqual(details['switched_e']['start_tick'], 7)

    def test_true_red_opening_yi_e_starts_at_expanded_q_right_edge(self) -> None:
        payload = {
            'team': [
                {'slot': 0, 'character_id': 'char_b52cc8f160', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 2, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 3, 'character_id': 'char_7578b18979', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'main_q', 'slot': 1, 'action_id': 'action_b356b46da2', 'start_tick': 15},
                {'id': 'nanaly_q', 'slot': 2, 'action_id': 'action_0f1e29b8ca', 'start_tick': 35},
                {'id': 'nanaly_e', 'slot': 2, 'action_id': 'action_5870d8ba67', 'start_tick': 40},
                {'id': 'yi_q', 'slot': 3, 'action_id': 'action_6ece34aff8', 'start_tick': 42},
                {'id': 'yi_e', 'slot': 3, 'action_id': 'action_2e072f2b0b', 'start_tick': 47},
                {'id': 'true_red_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 49},
            ],
            'options': {'switch_gap_ticks': 2},
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertEqual((details['yi_q']['visual_start_tick'], details['yi_q']['visual_end_tick']), (42, 51))
        self.assertEqual(details['yi_q']['start_tick'], 32)
        self.assertEqual(details['yi_e']['visual_start_tick'], details['yi_q']['visual_end_tick'])
        self.assertEqual(details['yi_e']['visual_start_tick'], 51)
        self.assertEqual(details['yi_e']['start_tick'], 32)
        self.assertEqual(details['true_red_e']['visual_start_tick'], 53)

    def test_buff_duration_and_cooldown_use_real_time_across_q_freeze(self) -> None:
        payload = {
            'team': [
                {'slot': 0, 'character_id': 'char_b52cc8f160', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'first_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 0},
                {'id': 'q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 16},
                {'id': 'inside_real_duration', 'slot': 0, 'action_id': 'action_40e3b63106', 'start_tick': 24},
                {'id': 'too_early_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 32},
                {'id': 'ready_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 35},
            ],
            'buff_rules': [
                {
                    'id': 'real_time_buff',
                    'name': '真实时间增益',
                    'trigger': {'slot': 0, 'action_id': 'action_3987d8ff2d'},
                    'targets': {'slots': [0]},
                    'duration_ticks': 20,
                    'modifiers': {'atk_pct': 0.5},
                },
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertEqual(details['inside_real_duration']['start_tick'], 19)
        self.assertIn('real_time_buff', {
            buff['rule_id'] for buff in details['inside_real_duration']['applied_buffs']
        })
        self.assertEqual(details['too_early_e']['start_tick'], 27)
        self.assertTrue(any('CD' in warning for warning in details['too_early_e']['warnings']))

        payload['steps'] = [
            step for step in payload['steps']
            if step['id'] != 'too_early_e'
        ]
        ready_result = simulate_shaft_axis(payload)['result']
        ready_e = next(detail for detail in ready_result['details'] if detail['step_id'] == 'ready_e')
        self.assertEqual(ready_e['start_tick'], 30)
        self.assertFalse(any('CD' in warning for warning in ready_e['warnings']))

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
        self.assertEqual(details['main_support']['original_duration_ticks'], 14)
        self.assertEqual(details['main_support']['visual_end_tick'] - details['main_support']['visual_start_tick'], 14)
        self.assertEqual(details['main_support']['duration_ticks'], 14)
        self.assertEqual(details['zhenhong_q2']['visual_start_tick'], 14)
        self.assertFalse(details['zhenhong_q2']['q_instant_release'])
        self.assertEqual(details['zhenhong_q2']['duration_ticks'], 0)
        self.assertEqual(details['nanaly_q']['visual_start_tick'], 19)
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
        self.assertEqual(dragon_a1['visual_end_tick'] - dragon_a1['visual_start_tick'], 3)
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
    def test_speed_cotton_stacks_each_front_second_and_clears_on_leave(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_c78f7a08d5',
                    'arc_id': 'arc_126824ee1b',
                    'arc_refinement': 1,
                    'cartridge_id': '',
                },
                {'slot': 1, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'start', 'slot': 0, 'action_id': 'action_00edea34a8', 'start_tick': 0},
                {'id': 'one_second', 'slot': 0, 'action_id': 'action_00edea34a8', 'start_tick': 10},
                {'id': 'five_seconds', 'slot': 0, 'action_id': 'action_00edea34a8', 'start_tick': 50},
                {'id': 'leave', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 60},
                {'id': 'return', 'slot': 0, 'action_id': 'action_00edea34a8', 'start_tick': 80},
            ],
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertNotIn('arc_speed_cotton_front_atk', {buff['rule_id'] for buff in details['start']['applied_buffs']})
        one_stack = next(buff for buff in details['one_second']['applied_buffs'] if buff['rule_id'] == 'arc_speed_cotton_front_atk')
        five_stacks = next(buff for buff in details['five_seconds']['applied_buffs'] if buff['rule_id'] == 'arc_speed_cotton_front_atk')
        self.assertEqual(one_stack['effects'], {'atk_pct': 0.05})
        self.assertEqual(five_stacks['stack_count'], 5)
        self.assertEqual(five_stacks['effects'], {'atk_pct': 0.25})
        self.assertNotIn('arc_speed_cotton_front_atk', {buff['rule_id'] for buff in details['return']['applied_buffs']})

    def test_new_arc_note_conditions_for_sagiri_shield_and_front_action(self) -> None:
        good_dog = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_1895e259be',
                'arc_id': 'arc_5167a86a24',
                'arc_refinement': 5,
                'cartridge_id': '',
            }],
            'steps': [{'id': 'q', 'slot': 0, 'action_id': 'action_0db78d1f01', 'start_tick': 0}],
            'initial_energy': 200,
        })['result']['details'][0]
        triggered = {buff['rule_id']: buff for buff in good_dog['triggered_buffs']}
        self.assertEqual(triggered['arc_good_dog_q_team_atk']['effects'], {'atk_pct': 0.16})
        self.assertEqual(triggered['arc_good_dog_q_control_extra_atk']['effects'], {'atk_pct': 0.1})

        thinking_cat = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_4f917797cb',
                'arc_id': 'arc_112b3492d8',
                'arc_refinement': 1,
                'cartridge_id': '',
            }],
            'steps': [{'id': 'basic', 'slot': 0, 'action_id': 'action_605c800d26', 'start_tick': 0}],
            'initial_energy': 200,
        })['result']['details'][0]
        thinking_buff = next(
            buff for buff in thinking_cat['applied_buffs']
            if buff['rule_id'] == 'arc_thinking_cat_fons_light'
        )

        self.assertEqual(thinking_buff['effects'], {'element_dmg': 0.25})

        spring = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_6f46705fd1',
                'arc_id': 'arc_5fdc5b1847',
                'arc_refinement': 1,
                'cartridge_id': '',
            }],
            'steps': [{'id': 'e', 'slot': 0, 'action_id': 'action_25fea9f7cb', 'start_tick': 0}],
            'initial_energy': 200,
        })['result']['details'][0]
        spring_triggered = {buff['rule_id'] for buff in spring['triggered_buffs']}
        self.assertIn('character_adler_e_shield', spring_triggered)
        self.assertIn('character_adler_e_team_curse', spring_triggered)
        self.assertIn('arc_spring_shield_atk', spring_triggered)
        spring_buff = next(buff for buff in spring['triggered_buffs'] if buff['rule_id'] == 'arc_spring_shield_atk')
        self.assertEqual(spring_buff['effects'], {'atk_pct': 0.18})

        danger = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_6f46705fd1',
                'arc_id': 'arc_18855bc4f1',
                'arc_refinement': 1,
                'cartridge_id': '',
            }],
            'steps': [
                {'id': 'first', 'slot': 0, 'action_id': 'action_25fea9f7cb', 'start_tick': 0},
                {'id': 'cooldown', 'slot': 0, 'action_id': 'action_55c8843d1c', 'start_tick': 100},
                {'id': 'ready', 'slot': 0, 'action_id': 'action_25fea9f7cb', 'start_tick': 200},
            ],
            'initial_energy': 200,
        })['result']
        danger_details = {detail['step_id']: detail for detail in danger['details']}
        self.assertIn('arc_danger_game_stagger', {buff['rule_id'] for buff in danger_details['first']['triggered_buffs']})
        self.assertNotIn('arc_danger_game_stagger', {buff['rule_id'] for buff in danger_details['cooldown']['triggered_buffs']})
        self.assertIn('arc_danger_game_stagger', {buff['rule_id'] for buff in danger_details['ready']['triggered_buffs']})

    def test_team_unique_buff_keeps_independent_triggers_and_applies_highest_value_once(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_7578b18979',
                    'arc_id': 'arc_5167a86a24',
                    'arc_refinement': 1,
                    'cartridge_id': '',
                },
                {
                    'slot': 1,
                    'character_id': 'char_1895e259be',
                    'arc_id': 'arc_5167a86a24',
                    'arc_refinement': 5,
                    'cartridge_id': '',
                },
                {'slot': 2, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'low_q', 'slot': 0, 'action_id': 'action_6ece34aff8', 'start_tick': 0},
                {'id': 'high_q', 'slot': 1, 'action_id': 'action_0db78d1f01', 'start_tick': 20},
                {'id': 'inspect', 'slot': 2, 'action_id': 'action_982c67944f', 'start_tick': 40},
            ],
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertIn(
            'arc_good_dog_q_team_atk',
            {buff['rule_id'] for buff in details['low_q']['triggered_buffs']},
        )
        self.assertIn(
            'arc_good_dog_q_team_atk',
            {buff['rule_id'] for buff in details['high_q']['triggered_buffs']},
        )
        applied = [
            buff
            for buff in details['inspect']['applied_buffs']
            if buff['rule_id'] == 'arc_good_dog_q_team_atk'
        ]
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]['owner_slot'], 1)
        self.assertEqual(applied[0]['effects'], {'atk_pct': 0.16})

    def test_declared_team_unique_sources_have_unique_keys(self) -> None:
        catalog = load_shaft_catalog()
        rules = {rule['id']: rule for rule in catalog['buffs']}
        expected_rule_ids = {
            'arc_wrong_door_heal_team_damage',
            'arc_bit_game_background_front_atk',
            'arc_bit_game_background_damage_front_atk_stack',
            'arc_bit_game_foreground_psyche_dmg',
            'arc_bit_game_basic_psyche_stack',
            'arc_good_dog_q_team_atk',
            'arc_good_dog_q_control_extra_atk',
            'cartridge_sonic_q_team_atk',
        }

        for rule_id in expected_rule_ids:
            with self.subTest(rule_id=rule_id):
                self.assertIn(rule_id, rules)
                self.assertEqual(
                    rules[rule_id]['calculation']['team_unique_key'],
                    rule_id,
                )

    def test_time_outside_records_team_actions_and_q_consumes_three_stacks(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': 'arc_7d0ca08e3d',
                    'arc_refinement': 1,
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
                {'id': 'owner_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'team_e_1', 'slot': 1, 'action_id': 'action_3987d8ff2d', 'start_tick': 20},
                {'id': 'team_e_2', 'slot': 1, 'action_id': 'action_3987d8ff2d', 'start_tick': 40},
                {'id': 'team_support', 'slot': 1, 'action_id': 'action_e98dde3662', 'start_tick': 60},
                {'id': 'owner_q', 'slot': 0, 'action_id': 'action_b356b46da2', 'start_tick': 80},
                {'id': 'after_q_team_e', 'slot': 1, 'action_id': 'action_3987d8ff2d', 'start_tick': 100},
            ],
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}

        q_buff = next(
            buff
            for buff in details['owner_q']['triggered_buffs']
            if buff['rule_id'] == 'arc_time_outside_recorded_crit_def'
        )
        self.assertAlmostEqual(q_buff['effects']['crit_dmg'], 0.48)
        self.assertEqual(q_buff['effects']['def_ignore'], 0.12)
        self.assertNotIn(
            'arc_time_outside_stack',
            {buff['rule_id'] for buff in details['after_q_team_e']['triggered_buffs']},
        )

    def test_time_outside_buffs_are_not_registered_without_its_arc(self) -> None:
        catalog = load_shaft_catalog()
        rules = registered_buff_rules(
            [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
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
            catalog,
        )

        self.assertFalse(any(str(rule['id']).startswith('arc_time_outside_') for rule in rules))

    def test_xun_records_each_teammate_once_and_q_consumes_records(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_15f458f7ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 2, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'xun_e', 'slot': 0, 'action_id': 'action_0c4da30973', 'start_tick': 0},
                {'id': 'main_e_1', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 10},
                {'id': 'main_e_2', 'slot': 1, 'action_id': 'action_982c67944f', 'start_tick': 20},
                {'id': 'nanali_support', 'slot': 2, 'action_id': 'action_482b5d9df7', 'start_tick': 30},
                {'id': 'xun_q', 'slot': 0, 'action_id': 'action_50de5ed4be', 'start_tick': 40},
            ],
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertNotIn(
            'character_xun_record_stack',
            {buff['rule_id'] for buff in details['main_e_2']['triggered_buffs']},
        )
        q_buff = next(
            buff
            for buff in details['xun_q']['triggered_buffs']
            if buff['rule_id'] == 'character_xun_q_record_damage'
        )
        self.assertEqual(q_buff['effects'], {'all_dmg': 0.44, 'def_ignore': 0.3})

    def test_zhenhong_yingxu_passive_stacks_solitary(self) -> None:
        result = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_b52cc8f160', 'arc_id': '', 'cartridge_id': ''}],
            'steps': [
                {'id': 'yingxu_1', 'slot': 0, 'action_id': 'action_5e62f427cb', 'start_tick': 0},
                {'id': 'yingxu_2', 'slot': 0, 'action_id': 'action_5e62f427cb', 'start_tick': 10},
                {'id': 'e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 20},
            ],
            'initial_energy': 200,
        })['result']
        e_detail = next(detail for detail in result['details'] if detail['step_id'] == 'e')
        solitary = next(buff for buff in e_detail['applied_buffs'] if buff['rule_id'] == 'character_zhenhong_solitary_stack')
        self.assertEqual(solitary['stack_count'], 2)
        self.assertEqual(solitary['effects'], {'atk_pct': 0.1})

    def test_character_buff_can_trigger_from_reaction_event(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_dd034941ef', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'main_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
                {'id': 'nanali_support', 'slot': 1, 'action_id': 'action_482b5d9df7', 'start_tick': 20},
                {'id': 'nanali_basic', 'slot': 1, 'action_id': 'action_7d6ec164ca', 'start_tick': 40},
            ],
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertIn(
            'character_protagonist_light_reaction_team_atk',
            {buff['rule_id'] for buff in details['nanali_support']['triggered_buffs']},
        )
        team_atk = next(
            buff for buff in details['nanali_basic']['applied_buffs']
            if buff['rule_id'] == 'character_protagonist_light_reaction_team_atk'
        )
        self.assertEqual(team_atk['effects'], {'atk_pct': 0.12})

    def test_enemy_resistances_are_element_specific_and_xiaozhi_reduces_only_light(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_4f917797cb', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_b52cc8f160', 'arc_id': '', 'cartridge_id': ''},
            ],
            'enemy': {
                'weakness_elements': [],
                'resistances': {'光': 0.5, '灵': 0.1, '咒': 0.2, '暗': 0.3, '魂': 0.4, '相': 0.6, '心灵': 0.7},
            },
            'steps': [
                {'id': 'xiaozhi_hit', 'slot': 0, 'action_id': 'action_605c800d26', 'start_tick': 0},
                {'id': 'zhenhong_hit', 'slot': 1, 'action_id': 'action_c5f19361cb', 'start_tick': 5},
            ],
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertAlmostEqual(details['xiaozhi_hit']['formula_parts']['resistance'], 0.5)
        self.assertAlmostEqual(details['zhenhong_hit']['formula_parts']['resistance'], 0.6)
        light_down = next(
            buff for buff in details['zhenhong_hit']['applied_buffs']
            if buff['rule_id'] == 'character_xiaozhi_light_res_down'
        )
        self.assertEqual(light_down['effects'], {'res_down_光': 0.1})

    def test_chaos_license_and_state_action_buffs_follow_notes(self) -> None:
        chaos = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_d38b672525', 'arc_id': '', 'cartridge_id': ''}],
            'steps': [
                {'id': 'e', 'slot': 0, 'action_id': 'action_2d3f8642dd', 'start_tick': 0},
                {'id': 'basic', 'slot': 0, 'action_id': 'action_40d0576f80', 'start_tick': 10},
            ],
            'initial_energy': 200,
        })['result']
        basic = next(detail for detail in chaos['details'] if detail['step_id'] == 'basic')
        license_buff = next(buff for buff in basic['applied_buffs'] if buff['rule_id'] == 'character_chaos_pursuit_license')
        self.assertEqual(license_buff['effects'], {'all_dmg': 0.2, 'def_ignore': 0.2, 'res_down_相': 0.1})

        fadia = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_caa6c2e5a8', 'arc_id': '', 'cartridge_id': ''}],
            'steps': [{'id': 'q5a', 'slot': 0, 'action_id': 'action_441d3aa300', 'start_tick': 0}],
            'initial_energy': 200,
        })['result']['details'][0]
        self.assertIn('character_fadia_enemy_slayer_crit', {buff['rule_id'] for buff in fadia['applied_buffs']})

        haiyue = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_699966e2e7', 'arc_id': '', 'cartridge_id': ''}],
            'steps': [
                {'id': 'q', 'slot': 0, 'action_id': 'action_952b4b561f', 'start_tick': 0},
                {'id': 'e', 'slot': 0, 'action_id': 'action_36a6d1d153', 'start_tick': 20},
            ],
            'initial_energy': 200,
        })['result']
        haiyue_e = next(detail for detail in haiyue['details'] if detail['step_id'] == 'e')
        self.assertIn('character_haiyue_huacai', {buff['rule_id'] for buff in haiyue_e['applied_buffs']})

    def test_arc_refinement_overrides_new_nanoka_buff_values(self) -> None:
        catalog = load_shaft_catalog()
        team = [{
            'slot': 0,
            'character_id': 'char_b52cc8f160',
            'arc_id': 'arc_f317782734',
            'arc_refinement': 5,
            'cartridge_id': '',
        }]

        rule = next(
            rule
            for rule in registered_buff_rules(team, catalog)
            if rule['id'] == 'arc_reality_shelter_q_attach'
        )

        self.assertEqual(rule['effects'], {'attach_dmg': 0.15})
        self.assertEqual(rule['duration']['ticks'], 60)

    def test_last_rose_e_and_dot_share_one_ten_layer_buff(self) -> None:
        catalog = load_shaft_catalog()
        rules = registered_buff_rules(
            [{
                'slot': 0,
                'character_id': 'char_b52cc8f160',
                'arc_id': 'arc_dcd5900afc',
                'arc_refinement': 5,
                'cartridge_id': '',
            }],
            catalog,
        )
        e_rule = next(rule for rule in rules if rule['id'] == 'arc_last_rose_e_full_stack')
        dot_rule = next(rule for rule in rules if rule['id'] == 'arc_last_rose_crit_stack')
        active_buffs = []

        e_instance = activate_buff(active_buffs, e_rule, 0, 10)
        dot_instance = activate_buff(active_buffs, dot_rule, 10)

        self.assertIs(dot_instance, e_instance)
        self.assertEqual(len(active_buffs), 1)
        self.assertEqual(dot_instance['stack_count'], 10)
        self.assertEqual(dot_instance['end_tick'], 40)
        self.assertEqual(dot_instance['rule']['id'], 'arc_last_rose_crit_stack')
        self.assertEqual(dot_instance['rule']['effects'], {'crit_dmg': 0.12})

    def test_last_rose_shared_stack_runs_in_browser_engine(self) -> None:
        result = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_c78f7a08d5',
                'arc_id': 'arc_dcd5900afc',
                'arc_refinement': 5,
                'cartridge_id': '',
            }],
            'steps': [
                {'id': 'e', 'slot': 0, 'action_id': 'action_2745f804a5', 'start_tick': 0},
                {'id': 'dot', 'slot': 0, 'action_id': 'action_0220e65a17', 'start_tick': 10},
                {'id': 'basic', 'slot': 0, 'action_id': 'action_00edea34a8', 'start_tick': 11},
            ],
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}

        e_buff = next(buff for buff in details['e']['triggered_buffs'] if buff['rule_id'] == 'arc_last_rose_e_full_stack')
        dot_buff = next(buff for buff in details['dot']['triggered_buffs'] if buff['rule_id'] == 'arc_last_rose_crit_stack')
        rose_buffs = [
            buff
            for buff in details['basic']['applied_buffs']
            if buff['rule_id'] in {'arc_last_rose_e_full_stack', 'arc_last_rose_crit_stack'}
        ]
        self.assertEqual(e_buff['stack_count'], 10)
        self.assertEqual(dot_buff['stack_count'], 10)
        self.assertEqual(dot_buff['effects'], {'crit_dmg': 1.2})
        self.assertEqual(len(rose_buffs), 1)

    def test_independent_buff_drops_oldest_layer_at_cap(self) -> None:
        catalog = load_shaft_catalog()
        rule = next(
            rule
            for rule in registered_buff_rules(
                [{
                    'slot': 0,
                    'character_id': 'char_b52cc8f160',
                    'arc_id': 'arc_4d19ef5194',
                    'arc_refinement': 1,
                    'cartridge_id': '',
                }],
                catalog,
            )
            if rule['id'] == 'arc_ora_basic_stack'
        )
        active_buffs = []

        for tick in range(11):
            activate_buff(active_buffs, rule, tick)

        self.assertEqual(len(active_buffs), 10)
        self.assertEqual([instance['start_tick'] for instance in active_buffs], list(range(1, 11)))
        self.assertTrue(all(instance['end_tick'] - instance['start_tick'] == 100 for instance in active_buffs))

    def test_independent_buff_creates_one_timer_per_layer_and_evicts_earliest_expiry(self) -> None:
        base_rule = {
            'id': 'independent_test',
            'name': '独立层测试',
            'owner_slot': 0,
            'duration': {'type': 'time', 'ticks': 100},
            'stacking': {'key': 'independent_test_stack', 'mode': 'independent', 'max_stacks': 2},
            'effects': {'atk_pct': 0.1},
        }
        active_buffs = []

        activate_buff(active_buffs, base_rule, 0)
        short_rule = deepcopy(base_rule)
        short_rule['duration']['ticks'] = 10
        activate_buff(active_buffs, short_rule, 1)
        replacement_rule = deepcopy(base_rule)
        replacement_rule['duration']['ticks'] = 50
        activate_buff(active_buffs, replacement_rule, 2)

        self.assertEqual([(buff['start_tick'], buff['end_tick']) for buff in active_buffs], [(0, 100), (2, 52)])

        active_buffs.clear()
        latest = activate_buff(active_buffs, base_rule, 5, 10)
        self.assertEqual(len(active_buffs), 2)
        self.assertTrue(all(buff['stack_count'] == 1 for buff in active_buffs))
        self.assertIs(latest, active_buffs[-1])

    def test_little_adventure_q_creates_ten_independent_hp_layers(self) -> None:
        result = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_caa6c2e5a8',
                'arc_id': '',
                'cartridge_id': 'cartridge_868dbc2c5c',
            }],
            'steps': [
                {'id': 'q', 'slot': 0, 'action_id': 'action_122b6bf962', 'start_tick': 0},
                {'id': 'e', 'slot': 0, 'action_id': 'action_72051426d5', 'start_tick': 1},
            ],
            'initial_energy': 200,
        })['result']
        detail = next(item for item in result['details'] if item['step_id'] == 'e')
        layers = [
            buff
            for buff in detail['applied_buffs']
            if buff['definition_id'] == 'cartridge_little_adventure_hp'
        ]

        self.assertEqual(len(layers), 10)
        self.assertTrue(all(layer['stack_count'] == 1 for layer in layers))
        self.assertTrue(all(layer['effects'] == {'hp_pct': 0.04} for layer in layers))

    def test_nanali_authority_delay_preserves_pre_start_switch_but_resets_after_start(self) -> None:
        team = [
            {'slot': 0, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            {'slot': 1, 'character_id': 'char_caa6c2e5a8', 'arc_id': '', 'cartridge_id': ''},
        ]
        before_start = simulate_shaft_axis({
            'team': team,
            'steps': [
                {'id': 'e', 'slot': 0, 'action_id': 'action_5870d8ba67', 'start_tick': 0},
                {'id': 'switch', 'slot': 1, 'action_id': 'action_122b6bf962', 'start_tick': 2},
                {'id': 'pursuit', 'slot': 0, 'action_id': 'action_8510ca415f', 'start_tick': 13},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        })['result']
        before_pursuit = next(item for item in before_start['details'] if item['step_id'] == 'pursuit')
        self.assertFalse(any('一代目的权柄' in warning for warning in before_pursuit['warnings']))

        after_start = simulate_shaft_axis({
            'team': team,
            'steps': [
                {'id': 'e', 'slot': 0, 'action_id': 'action_5870d8ba67', 'start_tick': 0},
                {'id': 'switch', 'slot': 1, 'action_id': 'action_122b6bf962', 'start_tick': 5},
                {'id': 'pursuit', 'slot': 0, 'action_id': 'action_8510ca415f', 'start_tick': 10},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        })['result']
        after_pursuit = next(item for item in after_start['details'] if item['step_id'] == 'pursuit')
        self.assertTrue(any('一代目的权柄' in warning for warning in after_pursuit['warnings']))

    def test_haiyue_haniya_and_hathor_new_character_buffs(self) -> None:
        haiyue = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_699966e2e7', 'arc_id': '', 'cartridge_id': '', 'awakening': 6}],
            'steps': [
                {'id': 'e', 'slot': 0, 'action_id': 'action_36a6d1d153', 'start_tick': 0},
                {'id': 'basic', 'slot': 0, 'action_id': 'action_18cf1ad6b6', 'start_tick': 10},
            ],
            'initial_energy': 200,
        })['result']
        haiyue_basic = next(item for item in haiyue['details'] if item['step_id'] == 'basic')
        jianqiang = next(buff for buff in haiyue_basic['applied_buffs'] if buff['definition_id'] == 'character_haiyue_jianqiang')
        self.assertEqual(jianqiang['stack_count'], 10)
        self.assertEqual(jianqiang['effects'], {'atk_pct': 0.1})

        haniya = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_e0a4292b4e', 'arc_id': '', 'cartridge_id': '', 'awakening': 6},
                {'slot': 1, 'character_id': 'char_caa6c2e5a8', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'q', 'slot': 0, 'action_id': 'action_3529c3d915', 'start_tick': 0},
                {'id': 'ensemble', 'slot': 0, 'action_id': 'action_8cadfa76a4', 'start_tick': 1},
                {'id': 'first', 'slot': 1, 'action_id': 'action_72051426d5', 'start_tick': 2},
                {'id': 'second', 'slot': 1, 'action_id': 'action_72051426d5', 'start_tick': 3},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        })['result']
        haniya_details = {item['step_id']: item for item in haniya['details']}
        self.assertIn('character_haniya_ace_team_crit_dmg', {
            buff['rule_id'] for buff in haniya_details['first']['applied_buffs']
        })
        self.assertIn('character_haniya_ace_ensemble_next_attack', {
            buff['rule_id'] for buff in haniya_details['first']['applied_buffs']
        })
        self.assertNotIn('character_haniya_ace_ensemble_next_attack', {
            buff['rule_id'] for buff in haniya_details['second']['applied_buffs']
        })

        hathor = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_912dbfe17c', 'arc_id': '', 'cartridge_id': '', 'awakening': 6}],
            'steps': [
                {'id': 'q', 'slot': 0, 'action_id': 'action_cc530277d3', 'start_tick': 0},
                {'id': 'e1', 'slot': 0, 'action_id': 'action_0dfd7dfab8', 'start_tick': 1},
                {'id': 'e2', 'slot': 0, 'action_id': 'action_85ee761950', 'start_tick': 20},
            ],
            'initial_energy': 200,
        })['result']
        hathor_details = {item['step_id']: item for item in hathor['details']}
        self.assertIn('character_hathor_emergency_delivery', {
            buff['rule_id'] for buff in hathor_details['e1']['applied_buffs']
        })
        self.assertNotIn('character_hathor_next_e_crit', {
            buff['rule_id'] for buff in hathor_details['e1']['applied_buffs']
        })
        self.assertIn('character_hathor_next_e_crit', {
            buff['rule_id'] for buff in hathor_details['e2']['applied_buffs']
        })

    def test_adler_karma_consumption_and_expected_murk_debuff(self) -> None:
        karma = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_6f46705fd1',
                'arc_id': '',
                'cartridge_id': '',
                'awakening': 2,
            }],
            'steps': [
                {'id': 'karma_1', 'slot': 0, 'action_id': 'action_adler_karma_2', 'start_tick': 0},
                {'id': 'karma_2', 'slot': 0, 'action_id': 'action_adler_karma_2', 'start_tick': 1},
                {'id': 'karma_3', 'slot': 0, 'action_id': 'action_adler_karma_2', 'start_tick': 2},
                {'id': 'e', 'slot': 0, 'action_id': 'action_25fea9f7cb', 'start_tick': 3},
                {'id': 'after', 'slot': 0, 'action_id': 'action_95733904eb', 'start_tick': 20},
            ],
            'initial_energy': 200,
        })['result']
        karma_details = {item['step_id']: item for item in karma['details']}
        consumed = next(
            buff for buff in karma_details['e']['applied_buffs']
            if buff['rule_id'] == 'character_adler_a2_e_consume_karma'
        )
        self.assertEqual(consumed['effects'], {'all_dmg': 0.18})
        self.assertNotIn('character_adler_karma', {
            buff['definition_id'] for buff in karma_details['after']['applied_buffs']
        })

        murk = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_c78f7a08d5', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_6f46705fd1', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                *[
                    {'id': f'gain_{index}', 'slot': 0, 'action_id': 'action_6d2645f71e', 'start_tick': index}
                    for index in range(15)
                ],
                {'id': 'support', 'slot': 1, 'action_id': 'action_55c8843d1c', 'start_tick': 20},
                {'id': 'after_murk', 'slot': 1, 'action_id': 'action_25fea9f7cb', 'start_tick': 33},
            ],
            'initial_energy': 200,
        })['result']
        after_murk = next(item for item in murk['details'] if item['step_id'] == 'after_murk')
        expected = next(
            buff for buff in after_murk['applied_buffs']
            if buff['rule_id'] == 'character_adler_murk_expected_debuff'
        )
        self.assertAlmostEqual(expected['effects']['res_down'], 1 / 30)
        self.assertAlmostEqual(expected['effects']['stagger_multiplier'], 1 / 30)

    def test_requiem_nightmare_has_independent_three_second_layers_and_settlement(self) -> None:
        result = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_c78f7a08d5',
                'arc_id': '',
                'cartridge_id': '',
                'awakening': 2,
            }],
            'steps': [
                {'id': 'first', 'slot': 0, 'action_id': 'action_00edea34a8', 'start_tick': 0},
                {'id': 'second', 'slot': 0, 'action_id': 'action_00edea34a8', 'start_tick': 15},
                {'id': 'inspect', 'slot': 0, 'action_id': 'action_0220e65a17', 'start_tick': 16},
            ],
            'initial_energy': 200,
        })['result']
        inspect = next(item for item in result['details'] if item['step_id'] == 'inspect')
        layers = [
            buff for buff in inspect['applied_buffs']
            if buff['definition_id'] == 'character_requiem_nightmare'
        ]
        self.assertEqual(len(layers), 4)
        self.assertTrue(all(layer['stack_count'] == 1 for layer in layers))
        self.assertEqual(
            sorted(event['tick'] for event in result['periodic_damage_events']),
            [10, 10, 20, 20, 25, 25, 30, 30, 35, 35, 45, 45],
        )

        settlement = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': 'char_c78f7a08d5',
                'arc_id': '',
                'cartridge_id': '',
                'awakening': 3,
            }],
            'steps': [
                {'id': 'gain', 'slot': 0, 'action_id': 'action_2745f804a5', 'start_tick': 0},
                {'id': 'settle', 'slot': 0, 'action_id': 'action_a7443f657f', 'start_tick': 5},
                {'id': 'inspect', 'slot': 0, 'action_id': 'action_0220e65a17', 'start_tick': 6},
            ],
            'initial_energy': 200,
        })['result']
        settlement_events = [
            event for event in settlement['periodic_damage_events']
            if event['kind'] == 'buff_periodic_settlement'
        ]
        self.assertEqual(len(settlement_events), 9)
        inspect_after = next(item for item in settlement['details'] if item['step_id'] == 'inspect')
        self.assertNotIn('character_requiem_nightmare', {
            buff['definition_id'] for buff in inspect_after['applied_buffs']
        })

    def test_fadia_darkstar_background_action_adds_capped_team_flat_hp(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_caa6c2e5a8', 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_bdc43f82c6', 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                *[
                    {'id': f'drain_{index}', 'slot': 0, 'action_id': 'action_bdc49de5c5', 'start_tick': index}
                    for index in range(6)
                ],
                {'id': 'inspect', 'slot': 1, 'action_id': 'action_7d6ec164ca', 'start_tick': 10},
            ],
            'initial_energy': 200,
        })['result']
        inspect = next(item for item in result['details'] if item['step_id'] == 'inspect')
        drain = next(
            buff for buff in inspect['applied_buffs']
            if buff['rule_id'] == 'character_fadia_darkstar_hp_drain'
        )
        self.assertEqual(drain['stack_count'], 5)
        self.assertAlmostEqual(drain['effects']['flat_hp'], 5160.5)

    def test_arc_refinement_uses_nanoka_panel_and_buff_values(self) -> None:
        payload = {
            'team': [{
                'slot': 0,
                'character_id': 'char_b52cc8f160',
                'arc_id': 'arc_27dc4a7281',
                'arc_refinement': 1,
                'cartridge_id': '',
            }],
            'steps': [
                {'id': 'q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
            ],
            'initial_energy': 200,
        }

        refined_one = simulate_shaft_axis(payload)['result']['details'][0]
        payload['team'][0]['arc_refinement'] = 5
        refined_five = simulate_shaft_axis(payload)['result']['details'][0]
        payload['team'][0]['arc_refinement'] = 0
        current_default = simulate_shaft_axis(payload)['result']['details'][0]

        buff_one = next(buff for buff in refined_one['applied_buffs'] if buff['rule_id'] == 'arc_crimson_mirage_q_light_def')
        buff_five = next(buff for buff in refined_five['applied_buffs'] if buff['rule_id'] == 'arc_crimson_mirage_q_light_def')
        self.assertEqual(buff_one['effects'], {'element_dmg': 0.32, 'def_ignore': 0.12})
        self.assertEqual(buff_five['effects'], {'element_dmg': 0.512, 'def_ignore': 0.192})
        self.assertGreater(refined_five['panel']['atk'], refined_one['panel']['atk'])
        self.assertAlmostEqual(current_default['panel']['atk'], refined_one['panel']['atk'])

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
                {'id': 'after_duration', 'slot': 0, 'action_id': 'action_5cd7ad2380', 'start_tick': 136},
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

    def test_true_red_dragon_e_cooldown_is_one_second(self) -> None:
        catalog = load_shaft_catalog()
        action = next(action for action in catalog['actions'] if action['id'] == 'action_7773821d79')
        self.assertEqual(action['cooldown_ticks'], 10)

    def test_true_red_normal_e_cooldown_is_three_seconds(self) -> None:
        catalog = load_shaft_catalog()
        action = next(action for action in catalog['actions'] if action['id'] == 'action_3987d8ff2d')
        self.assertEqual(action['cooldown_ticks'], 30)

    def test_jiuyuan_rose_transitions_and_settlement_bonuses(self) -> None:
        result = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_b2e3b2bf7a', 'awakening': 6, 'arc_id': '', 'cartridge_id': ''}],
            'steps': [
                {'id': 'mark', 'slot': 0, 'action_id': 'action_39d4605011', 'start_tick': 0},
                {'id': 'marked_dot', 'slot': 0, 'action_id': 'action_d8430d0b9e', 'start_tick': 20},
                {'id': 'settlement', 'slot': 0, 'action_id': 'action_4edb91866d', 'start_tick': 60},
            ],
            'team_panel_bonus': ShaftSimulatorValidationTestCase.ZERO_TEAM_PANEL_BONUS,
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}
        marked = {buff['rule_id']: buff for buff in details['marked_dot']['applied_buffs']}
        settlement = {buff['rule_id']: buff for buff in details['settlement']['applied_buffs']}
        self.assertEqual(marked['character_jiuyuan_rose_a2_mark_damage']['effects'], {'all_dmg': 1})
        self.assertIn('character_jiuyuan_deadly_rose_mark', marked)
        self.assertNotIn('character_jiuyuan_deadly_rose_mark', settlement)
        self.assertIn('character_jiuyuan_deadly_rose_settle_window', settlement)
        self.assertEqual(settlement['character_jiuyuan_rose_a4_settlement']['effects'], {'all_dmg': 0.5})

    def test_baizang_words_are_consumed_by_q_and_empower_next_e(self) -> None:
        result = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_701295143d', 'awakening': 2, 'arc_id': '', 'cartridge_id': ''}],
            'steps': [
                {'id': 'jin', 'slot': 0, 'action_id': 'action_c234af7127', 'start_tick': 0},
                {'id': 'q', 'slot': 0, 'action_id': 'action_9307778f01', 'start_tick': 20},
                {'id': 'next_e', 'slot': 0, 'action_id': 'action_9166cd44f2', 'start_tick': 40},
            ],
            'team_panel_bonus': ShaftSimulatorValidationTestCase.ZERO_TEAM_PANEL_BONUS,
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}
        q_triggered = {buff['rule_id']: buff for buff in details['q']['triggered_buffs']}
        next_e = {buff['rule_id']: buff for buff in details['next_e']['applied_buffs']}
        self.assertEqual(q_triggered['character_baizang_a1_next_skill']['effects'], {'all_dmg': 0.3})
        self.assertEqual(next_e['character_baizang_a1_next_skill']['effects'], {'all_dmg': 0.3})
        self.assertEqual(next_e['character_baizang_a2_word_atk']['effects'], {})

    def test_sagiri_counts_only_registered_negative_states_and_converts_base_atk(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_1895e259be', 'awakening': 6, 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_701295143d', 'awakening': 0, 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'baizang_dot', 'slot': 1, 'action_id': 'action_10c15dd4d1', 'start_tick': 0},
                {'id': 'second_dot', 'slot': 1, 'action_id': 'action_10c15dd4d1', 'start_tick': 20},
                {'id': 'sagiri_q', 'slot': 0, 'action_id': 'action_0db78d1f01', 'start_tick': 40},
                {'id': 'teammate_after_q', 'slot': 1, 'action_id': 'action_c234af7127', 'start_tick': 60},
            ],
            'team_panel_bonus': ShaftSimulatorValidationTestCase.ZERO_TEAM_PANEL_BONUS,
            'initial_energy': 200,
        })['result']
        details = {detail['step_id']: detail for detail in result['details']}
        dot_buffs = {buff['rule_id']: buff for buff in details['second_dot']['applied_buffs']}
        sagiri_buffs = {buff['rule_id']: buff for buff in details['sagiri_q']['applied_buffs']}
        teammate_buffs = {buff['rule_id']: buff for buff in details['teammate_after_q']['applied_buffs']}
        self.assertEqual(dot_buffs['character_sagiri_dot_amplification']['effects'], {'all_dmg': 0.25})
        self.assertEqual(sagiri_buffs['character_sagiri_a6_negative_damage']['effects'], {'all_dmg': 0.03})
        self.assertAlmostEqual(teammate_buffs['character_sagiri_q_team_flat_atk']['effects']['flat_atk'], 186)

    def test_requiem_a6_e_window_reuses_pre_e_front_for_reaction(self) -> None:
        result = simulate_shaft_axis({
            'team': [
                {'slot': 0, 'character_id': 'char_1895e259be', 'awakening': 0, 'arc_id': '', 'cartridge_id': ''},
                {'slot': 1, 'character_id': 'char_c78f7a08d5', 'awakening': 6, 'arc_id': '', 'cartridge_id': ''},
            ],
            'steps': [
                {'id': 'previous_front', 'slot': 0, 'action_id': 'action_4c5142a40f', 'start_tick': 0},
                {'id': 'requiem_e', 'slot': 1, 'action_id': 'action_2745f804a5', 'start_tick': 20},
                {'id': 'free_support', 'slot': 1, 'action_id': 'action_2635f721a8', 'start_tick': 40},
            ],
            'team_panel_bonus': ShaftSimulatorValidationTestCase.ZERO_TEAM_PANEL_BONUS,
            'initial_energy': 200,
        })['result']
        support = next(detail for detail in result['details'] if detail['step_id'] == 'free_support')
        self.assertEqual(support['warnings'], [])
        self.assertEqual(support['triggered_reaction']['reaction'], '浊燃')
        self.assertEqual(support['triggered_reaction']['previous_slot'], 0)

    def test_daphne_insight_stacks_and_yi_attachment_scales_with_elapsed_time(self) -> None:
        daphne = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_e8ad982185', 'awakening': 3, 'arc_id': '', 'cartridge_id': ''}],
            'steps': [
                {'id': 'q1', 'slot': 0, 'action_id': 'action_f5e921e6d8', 'start_tick': 0},
                {'id': 'q2', 'slot': 0, 'action_id': 'action_f5e921e6d8', 'start_tick': 50},
            ],
            'initial_energy': 200,
        })['result']
        insight = next(
            buff for buff in daphne['details'][-1]['applied_buffs']
            if buff['definition_id'] == 'character_daphne_insight'
        )
        self.assertEqual(insight['stack_count'], 2)
        self.assertEqual(insight['end_tick'], 345)

        yi = simulate_shaft_axis({
            'team': [{'slot': 0, 'character_id': 'char_7578b18979', 'awakening': 4, 'arc_id': '', 'cartridge_id': ''}],
            'steps': [
                {'id': 'e', 'slot': 0, 'action_id': 'action_2e072f2b0b', 'start_tick': 0},
                {'id': 'fang', 'slot': 0, 'action_id': 'action_ff4f07b530', 'start_tick': 30},
            ],
            'initial_energy': 200,
        })['result']
        attachment = next(
            buff for buff in yi['details'][-1]['applied_buffs']
            if buff['rule_id'] == 'character_yi_a4_attachment_state'
        )
        self.assertEqual(attachment['effects'], {'attach_dmg': 0.06})


if __name__ == '__main__':
    unittest.main()
