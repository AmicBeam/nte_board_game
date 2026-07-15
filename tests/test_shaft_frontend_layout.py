import re
import unittest
from pathlib import Path

from app.modules.shaft.service import simulate_shaft_axis
from app.modules.shaft.domain.catalog import get_record_map, load_shaft_catalog


ROOT = Path(__file__).resolve().parents[1]
SHAFT_JS = ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'js' / 'shaft.js'


def _js_number_constant(name: str) -> int:
    source = SHAFT_JS.read_text(encoding='utf-8')
    match = re.search(rf'\bconst\s+{re.escape(name)}\s*=\s*([0-9]+)\s*;', source)
    if not match:
        raise AssertionError(f'frontend constant {name} is missing or not numeric.')
    return int(match.group(1))


def _frontend_team_panel_bonus_defaults() -> dict[str, float]:
    source = SHAFT_JS.read_text(encoding='utf-8')
    match = re.search(r'const\s+DEFAULT_TEAM_PANEL_BONUS\s*=\s*\{(?P<body>.*?)\};', source, re.S)
    if not match:
        raise AssertionError('frontend team panel bonus defaults are missing.')
    return {
        key: float(value)
        for key, value in re.findall(r'([a-z_]+)\s*:\s*([0-9.]+)', match.group('body'))
    }


def _is_q_action(action: dict) -> bool:
    return str(action.get('action_type') or '') == 'Q' or str(action.get('damage_type') or '') == 'Q'


def _zero_q_actions() -> list[dict]:
    catalog = load_shaft_catalog()
    actions = []
    used_characters = set()
    for action in catalog['actions']:
        if not _is_q_action(action) or int(action.get('duration_ticks') or 0) != 0:
            continue
        character_id = str(action.get('character_id') or '')
        if character_id in used_characters:
            continue
        used_characters.add(character_id)
        actions.append(action)
        if len(actions) == 4:
            break
    if len(actions) != 4:
        raise AssertionError('expected at least four zero-duration Q actions.')
    return actions


def _frontend_timeline_layout(axis_payload: dict) -> list[dict]:
    catalog = load_shaft_catalog()
    actions_by_id = get_record_map(catalog['actions'])
    result = simulate_shaft_axis(axis_payload)['result']
    result_detail_by_step_id = {detail['step_id']: detail for detail in result['details']}

    zero_action_visual_ticks = _js_number_constant('ZERO_ACTION_VISUAL_TICKS')
    timeline_tick_px = _js_number_constant('TIMELINE_TICK_PX')
    timeline_label_px = _js_number_constant('TIMELINE_LABEL_PX')
    min_action_card_px = _js_number_constant('MIN_ACTION_CARD_PX')

    details = []
    for step in axis_payload['steps']:
        action = actions_by_id[str(step['action_id'])]
        result_detail = result_detail_by_step_id.get(step['id'], {})
        duration_ticks = max(0, int(action.get('duration_ticks') or 0))
        display_start_tick = int(result_detail.get('display_start_tick') or result_detail.get('visual_start_tick') or step.get('start_tick') or 0)
        display_end_tick = int(result_detail.get('display_end_tick') or (display_start_tick + duration_ticks))
        display_duration_ticks = int(result_detail.get('display_duration_ticks') if result_detail.get('display_duration_ticks') is not None else duration_ticks)
        nominal_display_visual_end_tick = display_start_tick + (
            duration_ticks if duration_ticks > 0 else zero_action_visual_ticks
        )
        fallback_display_visual_end_tick = (
            max(nominal_display_visual_end_tick, int(result_detail.get('visual_end_tick') or nominal_display_visual_end_tick))
            if _is_q_action(action)
            else nominal_display_visual_end_tick
        )
        display_visual_end_tick = int(
            result_detail.get('display_visual_end_tick') or fallback_display_visual_end_tick
        )
        details.append({
            **result_detail,
            'step_id': step['id'],
            'slot': int(step.get('slot') or 0),
            'action_id': step['action_id'],
            'display_start_tick': display_start_tick,
            'display_end_tick': display_end_tick,
            'display_duration_ticks': display_duration_ticks,
            'display_visual_end_tick': display_visual_end_tick,
            'nominal_display_visual_end_tick': nominal_display_visual_end_tick,
            'is_background_damage': False,
            'is_basic_background': bool(step.get('placement') == 'background'),
        })

    expansion_by_tick: dict[int, int] = {}
    for detail in details:
        action = actions_by_id[str(detail['action_id'])]
        display_duration_ticks = int(detail['display_duration_ticks'])
        tick = max(0, int(detail['display_start_tick']))
        visual_end_tick = int(detail['display_visual_end_tick'])
        blocks_track = not detail.get('is_background_damage') or detail.get('is_basic_background')
        is_zero_q = display_duration_ticks == 0 and not detail.get('is_background_damage') and _is_q_action(action)
        if not blocks_track and not is_zero_q:
            continue
        display_end_tick = max(
            tick + 1,
            max(tick + zero_action_visual_ticks, int(detail['nominal_display_visual_end_tick']))
            if is_zero_q else int(detail['nominal_display_visual_end_tick']),
        )
        raw_width = max(1, display_end_tick - tick) * timeline_tick_px
        extra_px = max(0, min_action_card_px - raw_width)
        if extra_px > 0:
            expansion_by_tick[tick] = max(expansion_by_tick.get(tick, 0), extra_px)

    expansion_breaks = [
        {
            'tick': tick,
            'extra_px': extra_px,
        }
        for tick, extra_px in sorted(expansion_by_tick.items())
    ]

    def visual_offset_px(tick: int) -> int:
        safe_tick = max(0, int(tick or 0))
        return safe_tick * timeline_tick_px + sum(
            item['extra_px']
            for item in expansion_breaks
            if item['tick'] < safe_tick
        )

    def left_px(tick: int) -> int:
        return timeline_label_px + visual_offset_px(tick)

    def width_px(start: int, end: int, visual_end: int) -> int:
        fixed_end = visual_end or end or (int(start or 0) + zero_action_visual_ticks)
        if int(fixed_end or start) <= int(start or 0):
            return min_action_card_px
        return max(
            min_action_card_px,
            visual_offset_px(max(fixed_end, int(start or 0) + 1)) - visual_offset_px(start),
        )

    layout = []
    slot_blocking_end_px_by_slot: dict[int, int] = {}
    for detail in sorted(details, key=lambda item: int(item['display_start_tick'])):
        action = actions_by_id[str(detail['action_id'])]
        is_zero_q = int(detail['display_duration_ticks']) == 0 and _is_q_action(action)
        width = min_action_card_px if is_zero_q else width_px(
            int(detail['display_start_tick']),
            int(detail['display_end_tick']),
            int(detail['display_visual_end_tick']),
        )
        if is_zero_q and int(detail['display_visual_end_tick']) > int(detail['display_start_tick']) + zero_action_visual_ticks:
            width = width_px(
                int(detail['display_start_tick']),
                int(detail['display_end_tick']),
                int(detail['display_visual_end_tick']),
            )
        blocking_width = min_action_card_px if is_zero_q else width_px(
            int(detail['display_start_tick']),
            int(detail['display_end_tick']),
            int(detail['nominal_display_visual_end_tick']),
        )
        raw_left = left_px(int(detail['display_start_tick']))
        slot = int(detail.get('slot') or 0)
        left = raw_left
        if not detail.get('is_background_damage'):
            left = max(left, slot_blocking_end_px_by_slot.get(slot, 0))
        if not detail.get('is_background_damage') or detail.get('is_basic_background'):
            slot_blocking_end_px_by_slot[slot] = max(
                slot_blocking_end_px_by_slot.get(slot, 0),
                left + blocking_width,
            )
        layout.append({
            'step_id': detail['step_id'],
            'left_px': left,
            'width_px': width,
            'right_px': left + width,
        })
    return layout


def _calculation_tick_from_visual(visual_tick: int, q_starts: list[int]) -> int:
    safe_tick = max(0, int(visual_tick or 0))
    offset = sum(
        min(_js_number_constant('ZERO_ACTION_VISUAL_TICKS'), safe_tick - int(q_start_tick or 0))
        for q_start_tick in q_starts
        if int(q_start_tick or 0) < safe_tick
    )
    return max(0, safe_tick - offset)


def _visual_tick_label(visual_tick: int, q_starts: list[int]) -> str:
    safe_tick = max(0, int(visual_tick or 0))
    calculation_tick = _calculation_tick_from_visual(safe_tick, q_starts)
    return f'{calculation_tick / 10:.1f}s'


class ShaftFrontendTimelineLayoutTestCase(unittest.TestCase):
    def test_build_page_uses_character_loadout_overview_three_column_order(self) -> None:
        template = (ROOT / 'app' / 'modules' / 'shaft' / 'templates' / 'shaft' / 'index.html').read_text(encoding='utf-8')
        css = (ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'css' / 'shaft-page.css').read_text(encoding='utf-8')

        summary = template.index('class="glass-card shaft-panel shaft-build-summary"')
        loadout = template.index('class="glass-card shaft-panel shaft-team-panel"')
        overview = template.index('class="glass-card shaft-panel shaft-build-overview"')
        self.assertLess(summary, loadout)
        self.assertLess(loadout, overview)
        self.assertIn('<h2>角色面板总结</h2>', template)
        self.assertIn('<h2>全队总览</h2>', template)
        self.assertEqual(template.count('id="shaft-build-panel"'), 1)
        self.assertIn(
            'grid-template-columns: minmax(220px, 250px) minmax(700px, 1fr) minmax(270px, 310px);',
            css,
        )
        self.assertIn('@media (max-width: 1239px)', css)
        self.assertLess(template.index('id="shaft-build-panel"'), template.index('<h2>敌人</h2>'))
        self.assertLess(template.index('<h2>敌人</h2>'), loadout)
        self.assertNotIn('<h2>全队面板</h2>', template)
        self.assertIn('<h2>家具上限</h2>', template)

    def test_character_panel_distinguishes_general_and_element_damage(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        formula_constants = (
            ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'data' / 'formula_constants.json'
        ).read_text(encoding='utf-8')

        self.assertIn("{ key: 'all_dmg', label: '通伤', percent: true }", source)
        self.assertIn("['属伤', formatPercent(panelStats.element_dmg || 0)]", source)
        self.assertIn("['通伤', formatPercent(panelStats.all_dmg || 0)]", source)
        self.assertIn('"label": "通伤"', formula_constants)

        labels = ['暴击', '暴伤', '环合强度', '倾陷强度', '通伤', '属伤', '充能']
        positions = [source.index(f"['{label}',", source.index('const minorStats = [')) for label in labels]
        self.assertEqual(positions, sorted(positions))

    def test_team_furniture_bonus_displays_actual_caps(self) -> None:
        defaults = _frontend_team_panel_bonus_defaults()

        self.assertEqual(defaults['furniture_crit_dmg'], 0.04)
        self.assertEqual(defaults['furniture_flat_atk'], 20)
        self.assertEqual(defaults['furniture_flat_def'], 30)

        source = SHAFT_JS.read_text(encoding='utf-8')
        self.assertIn("kind: 'percent', max: 4, step: 0.1", source)
        self.assertIn("kind: 'flat', max: 20, step: 1", source)
        self.assertIn("kind: 'flat', max: 30, step: 1", source)
        self.assertIn('data-team-bonus="${escapeHtml(field.key)}"', source)

    def test_rotation_columns_share_axis_workspace_height_and_self_check_stays_conditional(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        css = (ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'css' / 'shaft-page.css').read_text(encoding='utf-8')
        template = (ROOT / 'app' / 'modules' / 'shaft' / 'templates' / 'shaft' / 'index.html').read_text(encoding='utf-8')

        self.assertIn('--shaft-rotation-panel-height: min(661px, calc(100vh - 28px));', css)
        self.assertEqual(css.count('height: var(--shaft-rotation-panel-height);'), 3)
        self.assertIn('id="shaft-self-check" aria-live="polite" hidden', template)
        self.assertIn('node.hidden = warnings.length === 0;', source)
        self.assertIn('.shaft-self-check[hidden]', css)
        self.assertIn('background: rgba(54, 8, 15, 0.96);', css)

    def test_workbench_summary_shows_duration_and_optional_damage_sources(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        engine = (ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'js' / 'shaft_engine.js').read_text(encoding='utf-8')

        self.assertIn('<div><span>总轴长</span><strong>${formatNumber(summary.duration_seconds || 0, 1)}s</strong></div>', source)
        self.assertNotIn('<div><span>倾陷伤害</span><strong>${formatNumber(summary.stagger_damage || 0)}</strong></div>', source)
        self.assertIn("const SPECIAL_DAMAGE_SOURCES = ['创生', '浊燃', '黯星'];", engine)
        self.assertIn("{ source: '倾陷', damage: staggerDamage }", engine)
        self.assertIn('const sourceBars = (result?.damage_by_source || []).map', source)

        catalog = load_shaft_catalog()
        dark_star_action = next(action for action in catalog['actions'] if action.get('name') == '黯星扣血')
        result = simulate_shaft_axis({
            'team': [{
                'slot': 0,
                'character_id': dark_star_action['character_id'],
                'arc_id': '',
                'cartridge_id': '',
            }],
            'steps': [{
                'id': 'dark_star_damage',
                'slot': 0,
                'action_id': dark_star_action['id'],
                'start_tick': 0,
            }],
        })['result']
        damage_by_source = {item['source']: item for item in result['damage_by_source']}

        self.assertGreater(damage_by_source['黯星']['damage'], 0)
        self.assertGreater(damage_by_source['黯星']['percent'], 0)
        self.assertNotIn('创生', damage_by_source)
        self.assertNotIn('浊燃', damage_by_source)

    def test_buff_lines_are_single_state_line_with_multiline_tooltip(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        css = (ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'css' / 'shaft-page.css').read_text(encoding='utf-8')

        self.assertIn('function mergedBuffLineSegments', source)
        self.assertIn('const buffSegments = mergedBuffLineSegments', source)
        self.assertNotIn('mergedBuffLineRows', source)
        self.assertNotIn('const maxBuffLineCount = buffRows.length', source)
        self.assertIn("tooltipLines.join('\\n')", source)
        tooltip_match = re.search(r'\.shaft-buff-trigger-line::after\s*{(?P<body>.*?)\n}', css, re.S)
        if not tooltip_match:
            raise AssertionError('buff line tooltip style is missing.')
        self.assertIn('white-space: pre-line;', tooltip_match.group('body'))

    def test_buff_line_uses_only_the_latest_stack_snapshot(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function latestBuffStates', source)
        self.assertIn('const current = latestById.get(buff.id);', source)
        self.assertIn('const startsLater = Number(buff.startTick) > Number(current?.startTick ?? -1);', source)
        self.assertIn('const activeBuffs = latestBuffStates(entries', source)

    def test_buff_line_merges_duration_only_refreshes(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn(
            '.map((buff) => `${buff.id}:${buff.name}:${buffStackKey(buff.stackCount)}`)',
            source,
        )
        self.assertNotIn(
            '.map((buff) => `${buff.id}:${buff.name}:${buffStackKey(buff.stackCount)}:${buff.startTick}:${buff.endTick}`)',
            source,
        )

    def test_buff_line_tooltip_follows_pointer_position(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        css = (ROOT / 'app' / 'modules' / 'shaft' / 'static' / 'css' / 'shaft-page.css').read_text(encoding='utf-8')

        self.assertIn('function positionBuffLineTooltip(event)', source)
        self.assertIn("buffLine.style.setProperty('--buff-tooltip-x', `${offsetX}px`);", source)
        self.assertIn("$('shaft-timeline').addEventListener('pointermove', positionBuffLineTooltip);", source)
        self.assertIn('left: var(--buff-tooltip-x, 50%);', css)
        self.assertIn('transform: translate(-50%, 4px);', css)

    def test_unlined_buff_tooltip_hides_duration_and_deduplicates_buffs(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('const uniqueBuffs = new Map();', source)
        self.assertIn('const key = buff.name;', source)
        self.assertIn('.map((buff) => `${buff.name}${buffStackText(buff.stackCount)}`);', source)
        self.assertNotIn('parts.push(buff.tooltip);', source)
        self.assertNotIn('tooltip: `${buffRuleDisplayName(buff)} · ${ticksToSeconds', source)

    def test_axis_edit_schedules_real_simulation_after_local_render(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        schedule_match = re.search(
            r'function\s+scheduleSimulation\s*\([^)]*\)\s*{\s*(?P<body>.*?)\n  }',
            source,
            re.S,
        )
        if not schedule_match:
            raise AssertionError('scheduleSimulation function is missing.')

        schedule_body = schedule_match.group('body')
        self.assertIn('renderLocalCalculationState(statusText);', schedule_body)
        self.assertIn('window.setTimeout(runSimulation, SIMULATION_DEBOUNCE_MS)', schedule_body)

    def test_frontend_uses_engine_display_ticks_for_timeline(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn("const displayStartTick = resultTick('display_start_tick', resultDetail.visual_start_tick ?? startTick);", source)
        self.assertIn("resultTick('display_visual_end_tick', fallbackDisplayVisualEndTick)", source)
        self.assertIn('triggered_buffs: projectedTriggeredBuffs', source)
        self.assertNotIn('const displayStartTick = startTick;', source)
        self.assertNotIn('function rebaseTriggeredBuffsForDisplay', source)

    def test_stale_timeline_projection_keeps_buffs_and_q_layout_until_recalculation(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('state.dragState?.resultSnapshot || state.result || null', source)
        self.assertIn('const usesStaleResult = Boolean(state.isResultStale && state.result && result === state.result);', source)
        self.assertIn("['visual_start_tick', 'trigger_tick', 'start_tick', 'end_tick'].forEach", source)
        self.assertIn('Number(resultDetail.nominal_display_visual_end_tick) + projectionShiftTicks', source)

    def test_timeline_blank_click_and_track_resources_stay_axis_wide(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function slotResourcesForAxis(slot) {', source)
        self.assertIn('const energy = Number(resource.energy ?? resource.initial_energy ?? state.axis?.initial_energy ?? 100);', source)
        self.assertIn('const harmony = Number(resource.harmony ?? resource.initial_harmony ?? 0);', source)
        self.assertNotIn('function slotResourcesAtCursor', source)
        self.assertNotIn('Number(detail.start_tick || 0) <= cursorTick', source)
        self.assertIn('const cursorOnSelectedStart = primarySelectedLayoutForCursor &&', source)
        self.assertIn('state.cursorTick = timelineTickFromEvent(event);', source)
        self.assertIn('renderTimeline();\n        renderStepDetail();\n        renderEditorActions();', source)

    def test_action_insertion_prioritizes_new_step_and_reveals_its_end(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        add_match = re.search(
            r'function\s+addActionAt\s*\([^)]*\)\s*{\s*(?P<body>.*?)\n  }\n\n  function addStep',
            source,
            re.S,
        )
        if not add_match:
            raise AssertionError('addActionAt function is missing.')

        add_body = add_match.group('body')
        self.assertNotIn('shiftStepsFromTick', source)
        self.assertIn('normalizeEditedSteps(new Set([step.id]));', add_body)
        self.assertIn('revealTimelineTick(state.cursorTick);', add_body)
        self.assertLess(add_body.index('selectStep(step.id, false);'), add_body.index('state.cursorTick = Number(step.start_tick || 0) + actionVisualDurationTicks(action, step);'))
        self.assertNotIn('renderAll();', add_body)
        self.assertLess(add_body.index('scheduleSimulation();'), add_body.index('revealTimelineTick(state.cursorTick);'))
        self.assertIn("const shell = timeline?.closest('.shaft-timeline-shell');", source)

    def test_drag_preview_keeps_timeline_and_buff_snapshots_until_drop(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function timelineResult() {', source)
        self.assertIn('return freshResult() || state.dragState?.previewResult || state.dragState?.resultSnapshot || state.result || null;', source)
        self.assertIn('originAxisTicks[item.id] = Number(item.start_tick || 0);', source)
        self.assertIn('const originalProjectionTick = Number(drag?.originAxisTicks?.[step.id] ?? resultDetail.raw_start_tick ?? startTick);', source)
        self.assertLess(
            source.index('originAxisTicks[item.id] = Number(item.start_tick || 0);'),
            source.index('if (dragStepIds.includes(item.id)) {'),
        )
        self.assertIn('expansionBreaks = clone(drag.timelineScale.expansionBreaks || []);', source)
        self.assertIn('buffLinesBySlot[slot] = Array.from(track.querySelectorAll(\'.shaft-buff-trigger-line\'))', source)
        self.assertIn('const heldBuffLines = heldBuffPreview?.buffLinesBySlot?.[String(member.slot)];', source)
        self.assertIn('Array.isArray(heldBuffLines) ? heldBuffLines.join(\'\') : buffSegments.map', source)
        self.assertIn('resultSnapshot: freshResult(),', source)
        self.assertIn('const usesDragPreviewResult = Boolean(drag?.previewResult && result === drag.previewResult);', source)
        self.assertIn('const projectionShiftTicks = (drag && !usesDragPreviewResult) || usesStaleResult', source)
        self.assertIn('if (drag?.timelineScale && !usesDragPreviewResult) {', source)
        self.assertIn("drag.previewResult = window.ShaftEngine.simulateAxis(state.axis, state.catalog);", source)
        self.assertNotIn('animateActionLayout(previousRects, { skipStepIds: dragStepIds, durationMs: 80 });', source)
        mouse_up_match = re.search(
            r'function\s+handleTimelineMouseUp\s*\([^)]*\)\s*{\s*(?P<body>.*?)\n  }\n\n  function handleTeamDockClick',
            source,
            re.S,
        )
        if not mouse_up_match:
            raise AssertionError('handleTimelineMouseUp function is missing.')
        mouse_up_body = mouse_up_match.group('body')
        self.assertIn('runSimulation();', mouse_up_body)
        self.assertNotIn('scheduleSimulation();', mouse_up_body)

    def test_dragging_left_across_a_visual_action_start_snaps_to_its_tick(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function snapTickAfterCrossingVisualStart(drag, clientX, fallbackTick) {', source)
        self.assertIn("activeBar.closest('.action-track')?.querySelectorAll('.shaft-action-bar[data-step-id]')", source)
        self.assertIn('dragDisplayDetail?.display_start_tick ?? dragDisplayDetail?.visual_start_tick ?? step.start_tick', source)
        self.assertIn('originVisualOffset: timelineVisualOffset(originDisplayTick),', source)
        self.assertIn('originBarLeft: barRect.left,', source)
        self.assertIn('anchorOffsetX: event.clientX - barRect.left,', source)
        self.assertIn('const pressedBarRect = bar.getBoundingClientRect();', source)
        self.assertIn(".find((node) => node.dataset.stepId === step.id) || bar;", source)
        self.assertIn('activeBar.isConnected ? activeBar.getBoundingClientRect() : pressedBarRect;', source)
        self.assertIn('startTick: Math.max(0, Number(targetStep.start_tick || 0)),', source)
        self.assertIn('const nextTick = snapTickAfterCrossingVisualStart(drag, event.clientX, mappedTick);', source)

    def test_drag_mapping_preserves_raw_tick_when_display_tick_has_internal_q_offset(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function axisTickFromDragDisplayTick(drag, displayTick) {', source)
        self.assertIn('const originAxisTick = Number(drag?.originTick || 0);', source)
        self.assertIn('const originDisplayTick = Number(drag?.originDisplayTick ?? originAxisTick);', source)
        self.assertIn('return Math.max(0, originAxisTick + Number(displayTick || 0) - originDisplayTick);', source)
        self.assertIn('const mappedDisplayTick = Math.max(0, tickFromTimelineXWithScale(', source)
        self.assertIn('const mappedTick = axisTickFromDragDisplayTick(drag, mappedDisplayTick);', source)

    def test_drag_priority_does_not_reverse_when_crossing_yi_e_to_support_end(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function preserveGapsAfterAutomaticShift(originalStartTicks, priorityStepIds = new Set()) {', source)
        self.assertIn('const priorityIds = new Set(priorityStepIds || []);', source)
        self.assertIn('if (groupSteps.some((step) => priorityIds.has(step.id))) {', source)
        self.assertIn('carriedShiftTicks = 0;', source)
        self.assertIn('if (priorityIds.has(step.id)) {', source)
        self.assertIn('step.start_tick = resolvedStartTick;', source)
        self.assertEqual(source.count('preserveGapsAfterAutomaticShift(originalStartTicks, priorityIds);'), 2)

    def test_support_interval_cannot_be_covered_by_another_foreground_start(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('const supportConflict = foregroundStarts.find((item) => (', source)
        self.assertIn('item.tick <= startTick &&', source)
        self.assertIn('startTick < item.endTick', source)
        self.assertIn('startTick = supportConflict.endTick;', source)
        self.assertIn('isSupport: isSupportAction(action),', source)
        self.assertIn('const supportProtectsItsInterval = startsForeground(step, action) &&', source)
        self.assertIn('startTick <= priorityMinTick;', source)

    def test_loading_saved_axis_recomputes_stale_stored_result(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        load_match = re.search(
            r'async function loadAxis\([^)]*\)\s*{(?P<body>.*?)\n  }\n\n  async function deleteAxis',
            source,
            re.S,
        )
        if not load_match:
            raise AssertionError('loadAxis function is missing.')
        body = load_match.group('body')

        self.assertNotIn('acceptSimulationResult(payload.result);', body)
        self.assertIn('state.result = null;', body)
        self.assertIn('markSimulationStale();', body)
        self.assertIn('await runSimulation();', body)
        self.assertLess(body.index('await runSimulation();'), body.index('markAxisDocumentClean();'))

    def test_keyboard_moves_cursor_and_selected_actions_without_hijacking_inputs(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('if (isEditableTarget(event.target)) {', source)
        self.assertIn('function selectAllTimelineSteps() {', source)
        self.assertIn("event.key.toLowerCase() === 'a' &&", source)
        self.assertIn("state.page === 'rotation'", source)
        self.assertIn('selectAllTimelineSteps();', source)
        self.assertLess(source.index('if (isEditableTarget(event.target)) {'), source.index("event.key.toLowerCase() === 'a' &&"))
        self.assertIn("moveTimelineCursor(event.key === 'ArrowLeft' ? -1 : 1);", source)
        self.assertIn('function selectStepByKeyboard(key) {', source)
        self.assertIn('selectStepByKeyboard(movementKey);', source)
        self.assertIn("} else if (key === 'd') {", source)
        self.assertIn('moveTimelineCursorTo(stepVisualEndTickForCursor(primary));', source)
        self.assertIn('detail?.display_visual_end_tick ?? detail?.visual_end_tick ?? fallbackEndTick', source)
        self.assertIn("moveSelectedStepsByKeyboard(movementKey === 'q' ? -1 : 1);", source)
        self.assertNotIn('moveSelectedStepsToPlacement', source)
        self.assertIn("finishKeyboardStepEdit(stepIds, primary.id, swapped ? '已交换动作位置' : '已移动动作');", source)
        self.assertIn('const spanEnd = stepStart + stepDuration;', source)
        self.assertIn('const spanEnd = neighborStart + neighborDuration;', source)

    def test_axis_editing_preserves_player_authored_gaps_without_reflow(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertNotIn('function compactIdleGaps()', source)
        self.assertNotIn('compactIdleGaps();', source)
        self.assertIn('function preserveGapsAfterAutomaticShift(originalStartTicks, priorityStepIds = new Set()) {', source)
        self.assertIn('const currentOriginalTick = Math.max(0, Number(', source)
        self.assertIn('groupSteps.forEach((step) => {', source)
        self.assertIn('currentOriginalTick + carriedShiftTicks', source)
        self.assertLess(source.index('groupShiftTicks = Math.max(groupShiftTicks'), source.index('carriedShiftTicks = groupShiftTicks'))
        self.assertNotIn('function reflowSteps()', source)
        self.assertNotIn("$('shaft-reflow-btn')", source)

    def test_new_axis_has_a_clear_entry_and_protects_unsaved_changes(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        template = (ROOT / 'app' / 'modules' / 'shaft' / 'templates' / 'shaft' / 'index.html').read_text(encoding='utf-8')

        self.assertIn('id="shaft-new-btn"', template)
        self.assertIn('>新建动作轴</button>', template)
        self.assertNotIn('id="shaft-reset-btn"', template)
        self.assertIn('function hasUnsavedAxisChanges() {', source)
        self.assertIn("window.confirm('当前动作轴有未保存的修改，确定新建并放弃这些修改吗？')", source)
        self.assertIn("$('shaft-new-btn').addEventListener('click', newAxis);", source)
        self.assertNotIn("$('shaft-reset-btn')", source)

    def test_zero_q_visual_slot_label_hides_internal_sequence(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')
        zero_action_visual_ticks = _js_number_constant('ZERO_ACTION_VISUAL_TICKS')
        timeline_tick_px = _js_number_constant('TIMELINE_TICK_PX')
        min_action_card_px = _js_number_constant('MIN_ACTION_CARD_PX')
        q_starts = [index * zero_action_visual_ticks for index in range(4)]

        self.assertNotIn('Q时序', source)
        self.assertGreaterEqual(zero_action_visual_ticks * timeline_tick_px, min_action_card_px)
        self.assertLess(zero_action_visual_ticks * timeline_tick_px - min_action_card_px, timeline_tick_px)
        for index, visual_tick in enumerate(q_starts, start=1):
            self.assertEqual(_calculation_tick_from_visual(visual_tick, q_starts), 0)
            self.assertEqual(_visual_tick_label(visual_tick, q_starts), '0.0s')

        right_side_of_first_q = zero_action_visual_ticks
        self.assertEqual(_calculation_tick_from_visual(right_side_of_first_q, q_starts), 0)
        self.assertEqual(_visual_tick_label(right_side_of_first_q, q_starts), '0.0s')

    def test_q_timeline_abilities_require_zero_duration_foreground_q(self) -> None:
        source = SHAFT_JS.read_text(encoding='utf-8')

        self.assertIn('function isZeroForegroundQStep(step, action = actionForStep(step)) {', source)
        self.assertIn('startsForeground(step, action) && isQAction(action) && actionDurationTicks(action) === 0', source)
        self.assertIn('const currentIsQ = isZeroForegroundQStep(step, action);', source)
        self.assertIn('isQ: isZeroForegroundQStep(step, action),', source)
        self.assertIn('previousForegroundIsQ = isZeroForegroundQStep(detailStep, action);', source)
        self.assertNotIn('const currentIsQ = foregroundStart && isQAction(action);', source)

    def test_four_connected_zero_q_actions_keep_min_width_without_overlap(self) -> None:
        zero_q_actions = _zero_q_actions()
        zero_action_visual_ticks = _js_number_constant('ZERO_ACTION_VISUAL_TICKS')
        min_action_card_px = _js_number_constant('MIN_ACTION_CARD_PX')
        payload = {
            'team': [
                {
                    'slot': index,
                    'character_id': action['character_id'],
                    'arc_id': '',
                    'cartridge_id': '',
                }
                for index, action in enumerate(zero_q_actions)
            ],
            'steps': [
                {
                    'id': f'connected_q_{index}',
                    'slot': index,
                    'action_id': action['id'],
                    'start_tick': index * zero_action_visual_ticks,
                }
                for index, action in enumerate(zero_q_actions)
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        layout = _frontend_timeline_layout(payload)
        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}

        self.assertEqual(len(layout), 4)
        for entry in layout:
            self.assertEqual(entry['width_px'], min_action_card_px)
        for previous, current in zip(layout, layout[1:]):
            self.assertEqual(current['left_px'], previous['right_px'])
            self.assertGreaterEqual(current['left_px'], previous['right_px'])
        self.assertEqual(result['summary']['duration_ticks'], 0)
        self.assertEqual(result['summary']['duration_seconds'], 0)
        for index in range(4):
            detail = details[f'connected_q_{index}']
            self.assertEqual(detail['raw_start_tick'], index * zero_action_visual_ticks)
            self.assertEqual(detail['start_tick'], 0)
            self.assertEqual(detail['end_tick'], 0)
            self.assertEqual(detail['duration_ticks'], 0)

    def test_yi_q_e_reordering_preserves_total_visual_span(self) -> None:
        team = [{
            'slot': 0,
            'character_id': 'char_7578b18979',
            'arc_id': '',
            'cartridge_id': '',
        }]
        common = {
            'team': team,
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }
        q_then_e = _frontend_timeline_layout({
            **common,
            'steps': [
                {'id': 'yi_q', 'slot': 0, 'action_id': 'action_6ece34aff8', 'start_tick': 0},
                {'id': 'yi_e', 'slot': 0, 'action_id': 'action_2e072f2b0b', 'start_tick': 5},
            ],
        })
        e_then_q = _frontend_timeline_layout({
            **common,
            'steps': [
                {'id': 'yi_e', 'slot': 0, 'action_id': 'action_2e072f2b0b', 'start_tick': 0},
                {'id': 'yi_q', 'slot': 0, 'action_id': 'action_6ece34aff8', 'start_tick': 15},
            ],
        })

        def visual_span(layout: list[dict]) -> int:
            return max(entry['right_px'] for entry in layout) - min(entry['left_px'] for entry in layout)

        self.assertEqual(q_then_e[0]['right_px'], q_then_e[1]['left_px'])
        self.assertEqual(e_then_q[0]['right_px'], e_then_q[1]['left_px'])
        self.assertEqual(visual_span(q_then_e), visual_span(e_then_q))
        self.assertEqual(visual_span(q_then_e), 20 * _js_number_constant('TIMELINE_TICK_PX'))

    def test_short_nonzero_action_after_q_keeps_min_width_without_overlap(self) -> None:
        min_action_card_px = _js_number_constant('MIN_ACTION_CARD_PX')
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
                {'id': 'zhenhong_q', 'slot': 0, 'action_id': 'action_c32b4b9417', 'start_tick': 0},
                {'id': 'dragon_a1', 'slot': 0, 'action_id': 'action_40e3b63106', 'start_tick': 2},
                {'id': 'dragon_a2', 'slot': 0, 'action_id': 'action_c2c019771f', 'start_tick': 5},
            ],
            'options': {'switch_loss_ticks': 0},
            'initial_energy': 200,
        }

        layout = _frontend_timeline_layout(payload)
        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        layout_by_step = {entry['step_id']: entry for entry in layout}

        self.assertEqual(layout_by_step['zhenhong_q']['width_px'], min_action_card_px)
        self.assertEqual(layout_by_step['dragon_a1']['width_px'], min_action_card_px)
        self.assertEqual(layout_by_step['dragon_a1']['left_px'], layout_by_step['zhenhong_q']['right_px'])
        self.assertEqual(layout_by_step['dragon_a2']['left_px'], layout_by_step['dragon_a1']['right_px'])
        self.assertEqual(details['dragon_a1']['duration_ticks'], 3)
        self.assertEqual(details['dragon_a1']['end_tick'], details['dragon_a1']['start_tick'] + 3)
        self.assertFalse(details['dragon_a1']['q_instant_release'])

    def test_q_cover_expands_over_chain_without_overlapping_return_q(self) -> None:
        min_action_card_px = _js_number_constant('MIN_ACTION_CARD_PX')
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

        layout = _frontend_timeline_layout(payload)
        result = simulate_shaft_axis(payload)['result']
        details = {detail['step_id']: detail for detail in result['details']}
        layout_by_step = {entry['step_id']: entry for entry in layout}

        self.assertGreater(layout_by_step['main_q']['width_px'], min_action_card_px)
        self.assertEqual(details['main_q']['visual_end_tick'], details['zhenhong_a5']['visual_end_tick'])
        self.assertEqual(layout_by_step['main_q']['right_px'], layout_by_step['zhenhong_a5']['right_px'])
        self.assertEqual(layout_by_step['main_e']['left_px'], layout_by_step['main_q']['right_px'])
        self.assertGreaterEqual(layout_by_step['zhenhong_q']['left_px'], layout_by_step['zhenhong_a5']['right_px'])
        self.assertEqual(details['main_e']['start_tick'], 2)
        self.assertEqual(details['zhenhong_q']['start_tick'], 4)


if __name__ == '__main__':
    unittest.main()
