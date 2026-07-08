import unittest
from copy import deepcopy

from app.engine.application.shaft_service import simulate_shaft_axis
from app.shaft.buffs import registered_buff_rules
from app.shaft.catalog import load_shaft_catalog


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
                {'id': 'after_q_e', 'slot': 0, 'action_id': 'action_3987d8ff2d', 'start_tick': 21},
            ],
            'initial_energy': 200,
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
        self.assertAlmostEqual(q_trigger['formula_parts']['dmg_bonus'], 0.32)

        after_q = details['after_q_e']
        self.assertIn(
            'arc_crimson_mirage_q_light_def',
            {buff['rule_id'] for buff in after_q['applied_buffs']},
        )
        self.assertAlmostEqual(after_q['formula_parts']['dmg_bonus'], 0.32)

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
                {'id': 'zhenhong_q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 1},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        detail = next(item for item in result['details'] if item['step_id'] == 'zhenhong_q')

        self.assertAlmostEqual(detail['direct_damage'], 64966.09966946361)
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

    def test_zhenhong_partial_actions_keep_xlsx_self_damage_bonus(self) -> None:
        catalog = load_shaft_catalog()
        actions = {
            action['id']: action
            for action in catalog['actions']
            if action.get('character_name') == '真红'
        }
        bonus_action_ids = {
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
                for action_id in bonus_action_ids
            },
            {'龙a1', '龙a2', '龙a3', '龙a4', '龙a5', '龙e', '穿梭', 'q2'},
        )
        for action_id in bonus_action_ids:
            self.assertAlmostEqual(actions[action_id]['self_modifiers']['all_dmg'], 0.3)
        self.assertAlmostEqual(actions['action_c32b4b9417']['self_modifiers']['all_dmg'], 0.0)

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
                {'id': 'q_without_bonus', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
                {'id': 'q2_with_bonus', 'slot': 0, 'action_id': 'action_e3711f0cf5', 'start_tick': 1},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        self.assertAlmostEqual(details['q_without_bonus']['formula_parts']['dmg_bonus'], 0.0)
        self.assertAlmostEqual(details['q2_with_bonus']['formula_parts']['dmg_bonus'], 0.3)

    def test_fons_condition_defaults_to_full_stacks(self) -> None:
        payload = {
            'team': [
                {
                    'slot': 0,
                    'character_id': 'char_dd034941ef',
                    'arc_id': 'arc_112b3492d8',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'light_e', 'slot': 0, 'action_id': 'action_982c67944f', 'start_tick': 0},
            ],
            'initial_energy': 200,
        }

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
        self.assertAlmostEqual(detail['formula_parts']['dmg_bonus'], 0.25)

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
                    'character_id': 'char_4f917797cb',
                    'arc_id': 'arc_1ddecc32f3',
                    'cartridge_id': '',
                },
            ],
            'steps': [
                {'id': 'multi_hit', 'slot': 0, 'action_id': 'action_bc6c8ca82b', 'start_tick': 0},
            ],
            'initial_energy': 200,
        }

        result = simulate_shaft_axis(payload)['result']
        detail = result['details'][0]
        triggered = {
            buff['rule_id']: buff
            for buff in detail['triggered_buffs']
        }
        self.assertEqual(detail['hit_count'], 5)
        self.assertGreater(detail['expected_critical_hits'], 0)
        self.assertIn('arc_fierce_cotton_crit', triggered)
        self.assertAlmostEqual(triggered['arc_fierce_cotton_crit']['stack_count'], detail['expected_critical_hits'])


if __name__ == '__main__':
    unittest.main()
