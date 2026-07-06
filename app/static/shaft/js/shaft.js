(function () {
  const ELEMENTS = ['光', '灵', '咒', '暗', '魂', '相'];
  const SLOT_COLORS = ['#58d8d2', '#ffbf57', '#ff5aa5', '#77e36f'];
  const ACTION_TYPES = ['', '普攻', 'E', 'Q', '援护', '无'];
  const SUBSTAT_ORDER = [
    'all_dmg',
    'crit_rate',
    'crit_dmg',
    'harmony_strength',
    'stagger_strength',
    'atk_pct',
    'flat_atk',
    'hp_pct',
    'flat_hp',
    'def_pct',
    'flat_def',
  ];
  const BUFF_MODIFIERS = [
    { key: 'all_dmg', label: '全伤', percent: true },
    { key: 'crit_rate', label: '暴击', percent: true },
    { key: 'crit_dmg', label: '暴伤', percent: true },
    { key: 'atk_pct', label: '攻击%', percent: true },
    { key: 'def_down', label: '减防', percent: true },
    { key: 'res_down', label: '抗性降低', percent: true },
    { key: 'skill_dmg', label: '战技伤害', percent: true },
    { key: 'ultimate_dmg', label: '终结伤害', percent: true },
    { key: 'final_dmg', label: '最终伤害', percent: true },
    { key: 'harmony_strength', label: '环合强度', percent: false },
    { key: 'stagger_strength', label: '倾陷强度', percent: false },
  ];
  const ZERO_ACTION_VISUAL_TICKS = 2;
  const TIMELINE_END_PADDING_TICKS = 10;
  const TIMELINE_TICK_PX = 12;
  const TIMELINE_LABEL_PX = 128;
  const MIN_ACTION_CARD_PX = 58;
  const MIN_Q_INSTANT_CARD_PX = 18;
  const ZERO_ACTION_GAP_PX = 8;
  const MAX_VISUAL_LANES_PER_SLOT = 3;
  const BACKGROUND_DRAG_THRESHOLD_PX = 24;
  const DRAFT_STORAGE_KEY = 'shaft_axis_draft_v1';
  const DEFAULT_TEAM_PANEL_BONUS = {
    version: 2,
    furniture_crit_dmg: 0.04,
    furniture_flat_atk: 20,
    furniture_flat_def: 30,
    small_flat_atk: 420,
    small_flat_hp: 5200,
  };
  const TEAM_PANEL_BONUS_FIELDS = [
    { key: 'furniture_crit_dmg', label: '暴伤家具', kind: 'percent', step: '0.1' },
    { key: 'furniture_flat_atk', label: '攻击家具', kind: 'flat', step: '1' },
    { key: 'furniture_flat_def', label: '防御家具', kind: 'flat', step: '1' },
    { key: 'small_flat_atk', label: '驱动攻击', kind: 'flat', step: '1' },
    { key: 'small_flat_hp', label: '驱动生命', kind: 'flat', step: '100' },
  ];
  const SKILL_LEVEL_FIELDS = [
    { key: 'basic', label: '普攻' },
    { key: 'skill', label: 'E' },
    { key: 'ultimate', label: 'Q' },
    { key: 'support', label: '援护' },
  ];
  const DEFAULT_SKILL_LEVELS = {
    basic: 10,
    skill: 10,
    ultimate: 10,
    support: 10,
  };
  const CURTAIN_PASSIVE_TYPES = [
    { key: 'type2', label: '2型被动' },
    { key: 'type3', label: '3型被动' },
    { key: 'type4', label: '4型被动' },
  ];

  const state = {
    page: 'rotation',
    catalog: null,
    axis: null,
    result: null,
    marketItems: [],
    marketPage: 1,
    marketHasMore: false,
    savedAxisId: null,
    simulationTimer: 0,
    selectedStepId: '',
    selectedStepIds: [],
    buildPanelSlot: 0,
    cursorTick: 0,
    insertMode: 'cursor',
    librarySlot: 0,
    commandTypeFilter: '',
    commandSearch: '',
    timelineDurationTicks: TIMELINE_END_PADDING_TICKS,
    timelineScale: { expansionBreaks: [] },
    dragState: null,
    marqueeState: null,
    clipboardSteps: [],
    suppressClipboardPasteUntil: 0,
    undoStack: [],
    redoStack: [],
    suppressTimelineClickUntil: 0,
    buffDraft: {
      triggerSlot: 0,
      modifierKey: 'all_dmg',
    },
  };

  function $(id) {
    return document.getElementById(id);
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function emptyAxisFromCatalog() {
    const starter = clone(state.catalog?.starter_axis || {});
    starter.steps = [];
    starter.buff_rules = [];
    starter.duration_ticks = 1;
    return starter;
  }

  function displayText(value) {
    return String(value ?? '').replace(/精通/g, '环合强度');
  }

  function escapeHtml(value) {
    return displayText(value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[char]));
  }

  function formatNumber(value, digits = 0) {
    const number = Number(value || 0);
    return number.toLocaleString('zh-CN', {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits,
    });
  }

  function formatPercent(value, digits = 1) {
    return `${formatNumber(Number(value || 0) * 100, digits)}%`;
  }

  function secondsToTicks(value) {
    return Math.max(0, Math.round(Number(value || 0) * 10));
  }

  function ticksToSeconds(value) {
    return (Number(value || 0) / 10).toFixed(1);
  }

  function getVisitorKey() {
    let key = window.localStorage.getItem('shaft_visitor_key') || '';
    if (!key) {
      key = `visitor_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
      window.localStorage.setItem('shaft_visitor_key', key);
    }
    return key;
  }

  function readAxisDraft() {
    try {
      const raw = window.localStorage.getItem(DRAFT_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function axisDraftPayload() {
    if (!state.axis) {
      return null;
    }
    return {
      savedAxisId: state.savedAxisId || null,
      page: state.page || 'rotation',
      title: $('shaft-title-input')?.value || '未命名排轴',
      description: $('shaft-description-input')?.value || '',
      axis: state.axis,
      updatedAt: Date.now(),
    };
  }

  function persistAxisDraft() {
    const payload = axisDraftPayload();
    if (!payload) {
      return;
    }
    try {
      window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(payload));
    } catch (error) {
      // 本地草稿只是体验增强，写入失败不阻塞编辑。
    }
  }

  function restoreAxisDraft(activePage) {
    const draft = readAxisDraft();
    if (!draft || !draft.axis || typeof draft.axis !== 'object') {
      return false;
    }
    state.axis = clone(draft.axis);
    state.savedAxisId = Number(draft.savedAxisId || 0) || null;
    state.page = ['build', 'rotation', 'plaza'].includes(activePage)
      ? activePage
      : (['build', 'rotation', 'plaza'].includes(draft.page) ? draft.page : 'rotation');
    $('shaft-title-input').value = draft.title || '未命名排轴';
    $('shaft-description-input').value = draft.description || '';
    return true;
  }

  async function shaftRequest(url, options = {}, meta = {}) {
    const headers = Object.assign({}, options.headers || {});
    const body = options.body;
    if (body && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    headers['X-Shaft-Visitor-Key'] = getVisitorKey();
    headers['X-Log-Id'] = typeof nextLogId === 'function' ? nextLogId() : `shaft-${Date.now()}`;
    const response = await fetch(url, Object.assign({}, options, { headers }));
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }
    if (response.status === 401 && meta.authRequired) {
      redirectToLogin();
      throw new Error('未登录或登录态已失效。');
    }
    if (!response.ok || payload.error) {
      const logId = response.headers.get('X-Log-Id') || headers['X-Log-Id'];
      throw new Error(`${payload.error || '请求失败'}（logId: ${logId}）`);
    }
    return payload;
  }

  function getCharacterMap() {
    return new Map((state.catalog?.characters || []).map((item) => [item.id, item]));
  }

  function getActionMap() {
    return new Map((state.catalog?.actions || []).map((item) => [item.id, item]));
  }

  function getArcMap() {
    return new Map((state.catalog?.arcs || []).map((item) => [item.id, item]));
  }

  function getCartridgeMap() {
    return new Map((state.catalog?.cartridges || []).map((item) => [item.id, item]));
  }

  function numberValue(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function emptyPanelMods() {
    return {
      crit_rate: 0,
      crit_dmg: 0,
      atk_pct: 0,
      flat_atk: 0,
      hp_pct: 0,
      flat_hp: 0,
      def_pct: 0,
      flat_def: 0,
      def_ignore: 0,
      def_down: 0,
      res_down: 0,
      energy_recharge: 0,
      harmony_strength: 0,
      stagger_strength: 0,
      basic_dmg: 0,
      element_dmg: 0,
      follow_dmg: 0,
      mind_dmg: 0,
      attach_dmg: 0,
      skill_dmg: 0,
      ultimate_dmg: 0,
      all_dmg: 0,
      final_dmg: 0,
    };
  }

  function mergePanelMods(base, delta, factor = 1) {
    Object.entries(delta || {}).forEach(([key, value]) => {
      if (Object.prototype.hasOwnProperty.call(base, key)) {
        base[key] += numberValue(value) * factor;
      }
    });
    return base;
  }

  function substatPanelMods(counts) {
    const mods = emptyPanelMods();
    const units = state.catalog?.formula_constants?.substat_units || {};
    SUBSTAT_ORDER.forEach((key) => {
      const unit = units[key] || {};
      if (Object.prototype.hasOwnProperty.call(mods, key)) {
        mods[key] += Math.max(0, numberValue(counts?.[key])) * numberValue(unit.unit_value);
      }
    });
    return mods;
  }

  function normalizeTeamPanelBonus(raw) {
    const source = raw && typeof raw === 'object' ? raw : {};
    const version = Math.max(0, Math.round(numberValue(source.version)));
    const furnitureFlatAtk = Math.max(0, Math.min(5000, numberValue(source.furniture_flat_atk, DEFAULT_TEAM_PANEL_BONUS.furniture_flat_atk)));
    let smallFlatAtk = Math.max(0, Math.min(5000, numberValue(source.small_flat_atk, DEFAULT_TEAM_PANEL_BONUS.small_flat_atk)));
    if (version < 2 && furnitureFlatAtk === 20 && smallFlatAtk === 440) {
      smallFlatAtk = 420;
    }
    return {
      version: DEFAULT_TEAM_PANEL_BONUS.version,
      furniture_crit_dmg: Math.max(0, Math.min(5, numberValue(source.furniture_crit_dmg, DEFAULT_TEAM_PANEL_BONUS.furniture_crit_dmg))),
      furniture_flat_atk: furnitureFlatAtk,
      furniture_flat_def: Math.max(0, Math.min(5000, numberValue(source.furniture_flat_def, DEFAULT_TEAM_PANEL_BONUS.furniture_flat_def))),
      small_flat_atk: smallFlatAtk,
      small_flat_hp: Math.max(0, Math.min(100000, numberValue(source.small_flat_hp, DEFAULT_TEAM_PANEL_BONUS.small_flat_hp))),
    };
  }

  function teamPanelBonusMods(raw = state.axis?.team_panel_bonus) {
    const bonus = normalizeTeamPanelBonus(raw);
    const mods = emptyPanelMods();
    mods.crit_dmg += bonus.furniture_crit_dmg;
    mods.flat_atk += bonus.furniture_flat_atk + bonus.small_flat_atk;
    mods.flat_def += bonus.furniture_flat_def;
    mods.flat_hp += bonus.small_flat_hp;
    return mods;
  }

  function buildOptionDefaults(characterId) {
    const defaults = state.catalog?.formula_constants?.default_build_options || {};
    return defaults[characterId] && typeof defaults[characterId] === 'object' ? defaults[characterId] : {};
  }

  function normalizeStatName(value) {
    const text = String(value || '').trim();
    return text === '环合强度' ? '精通' : text;
  }

  function mainStatOptions() {
    return state.catalog?.formula_constants?.cartridge_main_stat_options || {};
  }

  function curtainStatOptions() {
    return state.catalog?.formula_constants?.curtain_bonus_stat_options || {};
  }

  function normalizeCartridgeMainStat(raw, characterId = '') {
    const options = mainStatOptions();
    const defaultValue = normalizeStatName(buildOptionDefaults(characterId).cartridge_main_stat) || Object.keys(options)[0] || '';
    const selected = normalizeStatName(raw) || defaultValue;
    return Object.prototype.hasOwnProperty.call(options, selected) ? selected : defaultValue;
  }

  function normalizeCurtainBonus(raw, characterId = '') {
    const defaults = buildOptionDefaults(characterId).curtain_bonus || {};
    const source = raw && typeof raw === 'object' ? raw : {};
    const options = curtainStatOptions();
    const defaultStat = normalizeStatName(defaults.stat) || Object.keys(options)[0] || '';
    const stat = normalizeStatName(source.stat) || defaultStat;
    const passiveType = CURTAIN_PASSIVE_TYPES.some((item) => item.key === source.passive_type)
      ? source.passive_type
      : (CURTAIN_PASSIVE_TYPES.some((item) => item.key === defaults.passive_type) ? defaults.passive_type : 'type3');
    return {
      value: Math.max(0, Math.min(100, numberValue(source.value, numberValue(defaults.value)))),
      stat: Object.prototype.hasOwnProperty.call(options, stat) ? stat : defaultStat,
      passive_type: passiveType,
    };
  }

  function curtainPassiveLayers(member) {
    const cartridge = getCartridgeMap().get(member?.cartridge_id || '');
    const bonus = normalizeCurtainBonus(member?.curtain_bonus, member?.character_id || '');
    return Math.max(0, Math.round(numberValue(cartridge?.passive_counts?.[bonus.passive_type])));
  }

  function mainStatPanelMods(mainStat) {
    const mods = emptyPanelMods();
    const option = mainStatOptions()[mainStat] || {};
    const key = option.modifier_key || '';
    if (Object.prototype.hasOwnProperty.call(mods, key)) {
      mods[key] += numberValue(option.unit_value);
    }
    return mods;
  }

  function curtainBonusPanelMods(member) {
    const mods = emptyPanelMods();
    const bonus = normalizeCurtainBonus(member?.curtain_bonus, member?.character_id || '');
    const option = curtainStatOptions()[bonus.stat] || {};
    const key = option.modifier_key || '';
    if (Object.prototype.hasOwnProperty.call(mods, key)) {
      mods[key] += numberValue(bonus.value) / 100 * curtainPassiveLayers(member);
    }
    return mods;
  }

  function computeBuildPanelForMember(member) {
    if (!member || !state.catalog) {
      return null;
    }
    const character = getCharacterMap().get(member.character_id);
    if (!character) {
      return null;
    }
    const arc = getArcMap().get(member.arc_id);
    const cartridge = getCartridgeMap().get(member.cartridge_id);
    const mods = emptyPanelMods();
    mergePanelMods(mods, character.modifiers);
    if (member.bond_full || numberValue(member.bond_level) > 0) {
      mergePanelMods(mods, character.bond_bonus?.modifiers);
    }
    if (arc) {
      mergePanelMods(mods, arc.modifiers);
    }
    if (cartridge) {
      mergePanelMods(mods, cartridge.modifiers);
    }
    mergePanelMods(mods, mainStatPanelMods(normalizeCartridgeMainStat(member.cartridge_main_stat, member.character_id)));
    mergePanelMods(mods, curtainBonusPanelMods(member));
    mergePanelMods(mods, substatPanelMods(member.substat_counts));
    mergePanelMods(mods, teamPanelBonusMods());
    const element = character.element || '';
    mods.element_dmg += numberValue(arc?.element_dmg?.[element]);

    const baseStats = character.base_stats || {};
    const baseAtk = numberValue(baseStats.atk) + numberValue(arc?.base_atk);
    const baseHp = numberValue(baseStats.hp);
    const baseDef = numberValue(baseStats.def);
    const panel = {
      atk: baseAtk * (1 + mods.atk_pct) + mods.flat_atk,
      hp: baseHp * (1 + mods.hp_pct) + mods.flat_hp,
      def: baseDef * (1 + mods.def_pct) + mods.flat_def,
      crit_rate: mods.crit_rate,
      crit_dmg: mods.crit_dmg,
      element_dmg: mods.element_dmg,
      energy_recharge: mods.energy_recharge,
      harmony_strength: mods.harmony_strength,
      stagger_strength: mods.stagger_strength,
      all_dmg: mods.all_dmg,
    };
    return {
      slot: Number(member.slot || 0),
      character_id: character.id || '',
      character_name: character.name || member.character_name || '',
      base_stats: { atk: baseAtk, hp: baseHp, def: baseDef },
      zones: {
        atk_pct: mods.atk_pct,
        flat_atk: mods.flat_atk,
        hp_pct: mods.hp_pct,
        flat_hp: mods.flat_hp,
        def_pct: mods.def_pct,
        flat_def: mods.flat_def,
      },
      panel,
      build_options: {
        cartridge_main_stat: normalizeCartridgeMainStat(member.cartridge_main_stat, member.character_id),
        curtain_bonus: Object.assign({}, normalizeCurtainBonus(member.curtain_bonus, member.character_id), {
          layers: curtainPassiveLayers(member),
        }),
      },
    };
  }

  function currentBuildPanels() {
    const team = state.axis?.team || [];
    const computed = team.map(computeBuildPanelForMember).filter(Boolean);
    if (computed.length) {
      return computed;
    }
    return state.result?.build_panels_by_slot || [];
  }

  function memberBySlot(slot) {
    return (state.axis?.team || []).find((item) => Number(item.slot) === Number(slot));
  }

  function validStepIdSet() {
    return new Set((state.axis?.steps || []).map((step) => step.id));
  }

  function selectedStepIds() {
    const validIds = validStepIdSet();
    const ids = Array.isArray(state.selectedStepIds) ? state.selectedStepIds : [];
    return ids.filter((id, index) => validIds.has(id) && ids.indexOf(id) === index);
  }

  function selectedSteps() {
    const ids = new Set(selectedStepIds());
    return (state.axis?.steps || []).filter((step) => ids.has(step.id));
  }

  function syncSelection(fallbackToFirst = false) {
    const ids = selectedStepIds();
    if (state.selectedStepId && validStepIdSet().has(state.selectedStepId) && !ids.includes(state.selectedStepId)) {
      ids.push(state.selectedStepId);
    }
    state.selectedStepIds = ids;
    if (!ids.includes(state.selectedStepId)) {
      state.selectedStepId = ids[ids.length - 1] || (fallbackToFirst ? state.axis?.steps?.[0]?.id || '' : '');
    }
    if (state.selectedStepId && !state.selectedStepIds.includes(state.selectedStepId)) {
      state.selectedStepIds.push(state.selectedStepId);
    }
  }

  function setSelectedStepIds(ids, primaryId = '', render = true) {
    const validIds = validStepIdSet();
    state.selectedStepIds = (ids || []).filter((id, index) => validIds.has(id) && (ids || []).indexOf(id) === index);
    state.selectedStepId = validIds.has(primaryId) ? primaryId : state.selectedStepIds[state.selectedStepIds.length - 1] || '';
    if (state.selectedStepId && !state.selectedStepIds.includes(state.selectedStepId)) {
      state.selectedStepIds.push(state.selectedStepId);
    }
    const step = selectedStep();
    if (step) {
      state.cursorTick = Number(step.start_tick || 0);
      const addTime = $('shaft-add-time');
      if (addTime) {
        addTime.value = ticksToSeconds(state.cursorTick);
      }
    }
    if (render) {
      renderTeamDock();
      renderSteps();
      renderTimeline();
      renderStepDetail();
      renderEditorActions();
    } else {
      updateSelectionClasses();
    }
  }

  function selectedStep() {
    return (state.axis?.steps || []).find((step) => step.id === state.selectedStepId) || null;
  }

  function detailByStepId(stepId) {
    return (state.result?.details || []).find((detail) => detail.step_id === stepId) || null;
  }

  function slotResourcesAtCursor(slot) {
    const slotNumber = Number(slot);
    const resource = (state.result?.resources_by_slot || []).find((item) => Number(item.slot) === slotNumber) || {};
    const cursorTick = Number(state.cursorTick || 0);
    let energy = Number(resource.initial_energy ?? state.axis?.initial_energy ?? 100);
    let harmony = Number(resource.initial_harmony ?? 0);
    (state.result?.details || [])
      .filter((detail) => Number(detail.slot) === slotNumber && Number(detail.start_tick || 0) <= cursorTick)
      .sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0))
      .forEach((detail) => {
        energy = Number(detail.energy_after ?? energy);
        harmony = Number(detail.harmony_after ?? harmony);
      });
    return { energy, harmony };
  }

  function memberName(slot) {
    const member = memberBySlot(slot);
    return member?.character_name || getCharacterMap().get(member?.character_id)?.name || `角色 ${Number(slot) + 1}`;
  }

  function actionsForSlot(slot) {
    const member = memberBySlot(slot);
    if (!member) {
      return [];
    }
    return state.catalog?.actions_by_character?.[member.character_id] || [];
  }

  function isBackgroundAction(action) {
    const marker = `${action?.name || ''} ${action?.extra_tag || ''}`;
    return Boolean(action?.is_background_damage) || marker.includes('后台');
  }

  function isBasicAction(action) {
    return String(action?.action_type || '') === '普攻' || String(action?.damage_type || '') === '普攻';
  }

  function canBackgroundOverride(action) {
    return Boolean(action?.can_background_override) && isBasicAction(action);
  }

  function isBasicBackgroundOverride(step, action = actionForStep(step)) {
    return !isBackgroundAction(action) && canBackgroundOverride(action) && step?.placement === 'background';
  }

  function isStepBackground(step, action = actionForStep(step)) {
    return isBackgroundAction(action) || isBasicBackgroundOverride(step, action);
  }

  function startsForeground(step, action = actionForStep(step)) {
    return !isStepBackground(step, action);
  }

  function blocksSlotOverlap(step, action = actionForStep(step)) {
    return startsForeground(step, action) || isBasicBackgroundOverride(step, action);
  }

  function sanitizeStepPlacement(step) {
    if (!step) {
      return;
    }
    const action = actionForStep(step);
    if (!isBasicBackgroundOverride(step, action)) {
      delete step.placement;
    }
  }

  function isSupportAction(action) {
    return String(action?.action_type || '') === '援护';
  }

  function isQAction(action) {
    return String(action?.action_type || '') === 'Q' || String(action?.damage_type || '') === 'Q';
  }

  function tickHasForegroundQ(tick, ignoreStepId = '') {
    const target = Number(tick || 0);
    return (state.axis?.steps || []).some((step) => {
      if (step.id === ignoreStepId || Number(step.start_tick || 0) !== target) {
        return false;
      }
      const action = actionForStep(step);
      return startsForeground(step, action) && isQAction(action);
    });
  }

  function actionDurationTicks(action) {
    return Math.max(0, Number(action?.duration_ticks || 0));
  }

  function actionEditorDurationTicks(action) {
    return Math.max(1, actionDurationTicks(action));
  }

  function actionForStep(step) {
    return getActionMap().get(step?.action_id || '') || {};
  }

  function stepEndTick(step, visual = false) {
    const action = actionForStep(step);
    const duration = actionDurationTicks(action);
    if (visual) {
      return Number(step?.start_tick || 0) + actionEditorDurationTicks(action);
    }
    return Number(step?.start_tick || 0) + duration;
  }

  function axisEndTick(visual = false) {
    return Math.max(
      0,
      ...(state.axis?.steps || []).map((step) => stepEndTick(step, visual)),
      ...(state.axis?.steps || []).map((step) => Number(step.start_tick || 0)),
    );
  }

  function updateAxisDuration() {
    if (state.axis) {
      state.axis.duration_ticks = Math.max(1, axisEndTick(false));
    }
  }

  function editorSnapshot() {
    return {
      steps: clone(state.axis?.steps || []),
      selectedStepId: state.selectedStepId,
      selectedStepIds: clone(selectedStepIds()),
      cursorTick: state.cursorTick,
    };
  }

  function restoreEditorSnapshot(snapshot) {
    if (!snapshot || !state.axis) {
      return;
    }
    state.axis.steps = clone(snapshot.steps || []);
    state.selectedStepIds = clone(snapshot.selectedStepIds || (snapshot.selectedStepId ? [snapshot.selectedStepId] : []));
    state.selectedStepId = snapshot.selectedStepId || state.selectedStepIds[state.selectedStepIds.length - 1] || '';
    syncSelection(true);
    state.cursorTick = Number(snapshot.cursorTick || 0);
    const addTime = $('shaft-add-time');
    if (addTime) {
      addTime.value = ticksToSeconds(state.cursorTick);
    }
    updateAxisDuration();
    closeContextMenu();
    renderAll();
    scheduleSimulation();
  }

  function pushUndoSnapshot() {
    if (!state.axis) {
      return;
    }
    state.undoStack.push(editorSnapshot());
    if (state.undoStack.length > 80) {
      state.undoStack.shift();
    }
    state.redoStack = [];
  }

  function undoLastEdit() {
    const snapshot = state.undoStack.pop();
    if (!snapshot) {
      return;
    }
    state.redoStack.push(editorSnapshot());
    restoreEditorSnapshot(snapshot);
  }

  function redoLastEdit() {
    const snapshot = state.redoStack.pop();
    if (!snapshot) {
      return;
    }
    state.undoStack.push(editorSnapshot());
    restoreEditorSnapshot(snapshot);
  }

  function renderEditorActions() {
    const undoButton = $('shaft-undo-btn');
    const redoButton = $('shaft-redo-btn');
    const deleteButton = $('shaft-delete-step-btn');
    const copyButton = $('shaft-copy-step-btn');
    const pasteButton = $('shaft-paste-step-btn');
    const loopEnabled = $('shaft-loop-enabled');
    const selectionCount = selectedStepIds().length;
    if (undoButton) {
      undoButton.disabled = state.undoStack.length === 0;
    }
    if (redoButton) {
      redoButton.disabled = state.redoStack.length === 0;
    }
    if (deleteButton) {
      deleteButton.disabled = selectionCount === 0;
    }
    if (copyButton) {
      copyButton.disabled = selectionCount === 0;
    }
    if (pasteButton) {
      pasteButton.disabled = !state.clipboardSteps.length;
    }
    if (loopEnabled) {
      loopEnabled.checked = Boolean(state.axis?.options?.loop_enabled);
    }
  }

  function actionLabel(action) {
    if (!action) {
      return '';
    }
    return `${action.action_type || '动作'} · ${action.name}`;
  }

  function actionTypeClass(type) {
    const normalized = String(type || 'other').toLowerCase();
    if (normalized === 'e') {
      return 'skill';
    }
    if (normalized === 'q') {
      return 'ultimate';
    }
    if (String(type || '') === '普攻') {
      return 'basic';
    }
    if (String(type || '') === '援护') {
      return 'support';
    }
    if (String(type || '') === '无') {
      return 'utility';
    }
    return 'other';
  }

  function optionHtml(records, selected, getLabel) {
    return (records || []).map((record) => {
      const label = getLabel ? getLabel(record) : record.name;
      return `<option value="${escapeHtml(record.id)}" ${record.id === selected ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
  }

  function slotOptions(selected) {
    return (state.axis?.team || []).map((member) => `
      <option value="${member.slot}" ${Number(member.slot) === Number(selected) ? 'selected' : ''}>
        ${Number(member.slot) + 1} · ${escapeHtml(member.character_name)}
      </option>
    `).join('');
  }

  function emptySubstatCounts() {
    const out = {};
    SUBSTAT_ORDER.forEach((key) => { out[key] = 0; });
    return out;
  }

  function clampSubstatCount(value) {
    return Math.max(0, Math.min(30, Math.round(Number(value || 0))));
  }

  function normalizeSubstatCounts(raw) {
    const out = Object.assign({}, emptySubstatCounts(), raw || {});
    SUBSTAT_ORDER.forEach((key) => {
      out[key] = clampSubstatCount(out[key]);
    });
    return out;
  }

  function clampSkillLevel(value) {
    return Math.max(1, Math.min(10, Math.round(Number(value || 10))));
  }

  function normalizeSkillLevels(raw) {
    const out = Object.assign({}, DEFAULT_SKILL_LEVELS, raw || {});
    SKILL_LEVEL_FIELDS.forEach((field) => {
      out[field.key] = clampSkillLevel(out[field.key]);
    });
    return out;
  }

  function buildSnapshotFromMember(member) {
    return {
      character_id: member.character_id || '',
      character_name: member.character_name || '',
      arc_id: member.arc_id || '',
      arc_name: member.arc_name || '',
      cartridge_id: member.cartridge_id || '',
      cartridge_name: member.cartridge_name || '',
      awakening: Math.max(0, Math.min(6, Number(member.awakening || 0))),
      bond_level: Math.max(0, Math.min(1, Number(member.bond_level || (member.bond_full ? 1 : 0)))),
      bond_full: Boolean(member.bond_full) || Number(member.bond_level || 0) > 0,
      skill_levels: normalizeSkillLevels(member.skill_levels),
      cartridge_main_stat: normalizeCartridgeMainStat(member.cartridge_main_stat, member.character_id),
      curtain_bonus: normalizeCurtainBonus(member.curtain_bonus, member.character_id),
      substat_counts: normalizeSubstatCounts(member.substat_counts),
    };
  }

  function applyBuildToMember(member, build) {
    if (!member || !build) {
      return;
    }
    member.arc_id = build.arc_id || member.arc_id || '';
    member.cartridge_id = build.cartridge_id || member.cartridge_id || '';
    member.awakening = Math.max(0, Math.min(6, Number(build.awakening || 0)));
    member.bond_level = Math.max(0, Math.min(1, Number(build.bond_level || (build.bond_full ? 1 : 0))));
    member.bond_full = Boolean(build.bond_full) || member.bond_level > 0;
    member.skill_levels = normalizeSkillLevels(build.skill_levels);
    member.cartridge_main_stat = normalizeCartridgeMainStat(build.cartridge_main_stat, member.character_id);
    member.curtain_bonus = normalizeCurtainBonus(build.curtain_bonus, member.character_id);
    member.substat_counts = normalizeSubstatCounts(build.substat_counts);
    updateMemberNames(member);
  }

  function normalizeCharacterBuild(raw) {
    const build = raw && typeof raw === 'object' ? raw : {};
    return {
      character_id: build.character_id || '',
      character_name: build.character_name || '',
      arc_id: build.arc_id || '',
      arc_name: build.arc_name || '',
      cartridge_id: build.cartridge_id || '',
      cartridge_name: build.cartridge_name || '',
      awakening: Math.max(0, Math.min(6, Number(build.awakening || 0))),
      bond_level: Math.max(0, Math.min(1, Number(build.bond_level || (build.bond_full ? 1 : 0)))),
      bond_full: Boolean(build.bond_full) || Number(build.bond_level || 0) > 0,
      skill_levels: normalizeSkillLevels(build.skill_levels),
      cartridge_main_stat: normalizeCartridgeMainStat(build.cartridge_main_stat, build.character_id || ''),
      curtain_bonus: normalizeCurtainBonus(build.curtain_bonus, build.character_id || ''),
      substat_counts: normalizeSubstatCounts(build.substat_counts),
    };
  }

  function seedCharacterBuilds(rawBuilds) {
    const characterIds = new Set((state.catalog?.characters || []).map((character) => character.id));
    const seeded = {};
    const starterBuilds = state.catalog?.starter_axis?.character_builds || {};
    Object.entries(starterBuilds).forEach(([characterId, build]) => {
      if (characterIds.has(characterId)) {
        seeded[characterId] = normalizeCharacterBuild(Object.assign({}, build, { character_id: characterId }));
      }
    });
    Object.entries(rawBuilds && typeof rawBuilds === 'object' ? rawBuilds : {}).forEach(([characterId, build]) => {
      if (characterIds.has(characterId)) {
        seeded[characterId] = normalizeCharacterBuild(Object.assign({}, build, { character_id: characterId }));
      }
    });
    return seeded;
  }

  function rememberMemberBuild(member) {
    if (!member?.character_id) {
      return;
    }
    state.axis.character_builds = seedCharacterBuilds(state.axis.character_builds);
    state.axis.character_builds[member.character_id] = buildSnapshotFromMember(member);
  }

  function ensureAxisShape() {
    if (!state.axis) {
      state.axis = emptyAxisFromCatalog();
    }
    const hadCharacterBuilds = Boolean(
      state.axis.character_builds &&
      typeof state.axis.character_builds === 'object' &&
      Object.keys(state.axis.character_builds).length,
    );
    state.axis.character_builds = seedCharacterBuilds(state.axis.character_builds);
    state.axis.team = Array.isArray(state.axis.team) && state.axis.team.length
      ? state.axis.team.slice(0, 4)
      : clone(state.catalog.starter_axis.team);
    state.axis.steps = Array.isArray(state.axis.steps) ? state.axis.steps : [];
    state.axis.enemy = Object.assign(
      {},
      state.catalog.formula_constants.default_enemy || { level: 90, track_outside: false, weakness_elements: [] },
      state.axis.enemy || {},
    );
    state.axis.options = Object.assign(
      { switch_loss_ticks: state.catalog.formula_constants.switch_loss_ticks || 2, loop_enabled: false },
      state.axis.options || {},
    );
    state.axis.options.loop_enabled = Boolean(state.axis.options.loop_enabled);
    state.axis.team_panel_bonus = normalizeTeamPanelBonus(state.axis.team_panel_bonus);
    state.axis.initial_energy = Number(state.axis.initial_energy ?? 100);
    state.axis.buff_rules = Array.isArray(state.axis.buff_rules) ? state.axis.buff_rules : [];
    state.axis.team.forEach((member, index) => {
      member.slot = Number(member.slot ?? index);
      member.awakening = Math.max(0, Math.min(6, Number(member.awakening || 0)));
      member.bond_level = Math.max(0, Math.min(1, Number(member.bond_level || (member.bond_full ? 1 : 0))));
      member.bond_full = Boolean(member.bond_full) || member.bond_level > 0;
      member.skill_levels = normalizeSkillLevels(member.skill_levels);
      member.cartridge_main_stat = normalizeCartridgeMainStat(member.cartridge_main_stat, member.character_id);
      member.curtain_bonus = normalizeCurtainBonus(member.curtain_bonus, member.character_id);
      member.substat_counts = normalizeSubstatCounts(member.substat_counts);
      updateMemberNames(member);
      if (hadCharacterBuilds && state.axis.character_builds[member.character_id]) {
        applyBuildToMember(member, state.axis.character_builds[member.character_id]);
      } else {
        rememberMemberBuild(member);
      }
    });
    syncSelection(true);
    updateAxisDuration();
  }

  function setStatus(text, tone = '') {
    const node = $('shaft-status');
    if (!node) {
      return;
    }
    node.textContent = text;
    node.dataset.tone = tone;
  }

  function setPage(page, push = true) {
    const normalizedPage = page === 'market' ? 'plaza' : page;
    state.page = ['build', 'rotation', 'plaza'].includes(normalizedPage) ? normalizedPage : 'rotation';
    document.querySelectorAll('[data-shaft-view]').forEach((node) => {
      node.classList.toggle('active', node.dataset.shaftView === state.page);
    });
    document.querySelectorAll('[data-shaft-page-link]').forEach((node) => {
      node.classList.toggle('active', node.dataset.shaftPageLink === state.page);
    });
    if (push) {
      window.history.replaceState({}, '', `/shaft/${state.page}`);
      persistAxisDraft();
    }
  }

  function renderLoginState() {
    const link = $('shaft-login-link');
    if (!link) {
      return;
    }
    if (getToken()) {
      link.href = '/profile';
      link.textContent = '账号';
    } else {
      link.href = typeof loginUrlForCurrentPage === 'function' ? loginUrlForCurrentPage() : '/login';
      link.textContent = '登录';
    }
  }

  function renderTeam() {
    const container = $('shaft-team-slots');
    const characters = state.catalog.characters || [];
    const arcs = state.catalog.arcs || [];
    const cartridges = state.catalog.cartridges || [];
    const substatUnits = state.catalog.formula_constants.substat_units || {};
    const characterMap = getCharacterMap();
    container.innerHTML = (state.axis.team || []).map((member) => {
      const character = characterMap.get(member.character_id) || {};
      const bondLabel = character.bond_bonus?.label || '满羁绊';
      const activeAwakening = Math.max(0, Math.min(6, Number(member.awakening || 0)));
      const slotColor = SLOT_COLORS[Number(member.slot) % SLOT_COLORS.length];
      const awakeningToggles = Array.from({ length: 6 }, (_, index) => {
        const level = index + 1;
        const checked = level <= activeAwakening ? 'checked' : '';
        return `
          <label class="shaft-awakening-dot" title="觉醒 ${level}">
            <input data-slot="${member.slot}" data-field="awakening" data-awakening-level="${level}" type="checkbox" ${checked}>
            <span>${level}</span>
          </label>
        `;
      }).join('');
      const skillLevels = normalizeSkillLevels(member.skill_levels);
      const skillLevelControls = SKILL_LEVEL_FIELDS.map((field) => `
        <label class="shaft-skill-level-tile">
          <span>${escapeHtml(field.label)}</span>
          <input data-slot="${member.slot}" data-skill-level="${field.key}" type="number" min="1" max="10" step="1" inputmode="numeric" value="${skillLevels[field.key]}" aria-label="${escapeHtml(field.label)}技能等级">
        </label>
      `).join('');
      const mainStat = normalizeCartridgeMainStat(member.cartridge_main_stat, member.character_id);
      const curtainBonus = normalizeCurtainBonus(member.curtain_bonus, member.character_id);
      const curtainLayers = curtainPassiveLayers(member);
      const mainStatSelect = Object.entries(mainStatOptions()).map(([key, meta]) => `
        <option value="${escapeHtml(key)}" ${key === mainStat ? 'selected' : ''}>${escapeHtml(meta.label || key)}</option>
      `).join('');
      const curtainStatSelect = Object.entries(curtainStatOptions()).map(([key, meta]) => `
        <option value="${escapeHtml(key)}" ${key === curtainBonus.stat ? 'selected' : ''}>${escapeHtml(meta.label || key)}</option>
      `).join('');
      const curtainPassiveSelect = CURTAIN_PASSIVE_TYPES.map((item) => `
        <option value="${item.key}" ${item.key === curtainBonus.passive_type ? 'selected' : ''}>${escapeHtml(item.label)}</option>
      `).join('');
      const substats = SUBSTAT_ORDER.map((key) => {
        const unit = substatUnits[key] || {};
        const unitValue = Number(unit.unit_value || 0);
        const unitLabel = unit.kind === 'percent'
          ? `${formatNumber(unitValue * 100, 2)}%/B`
          : `${formatNumber(unitValue, 0)}/B`;
        const count = clampSubstatCount(member.substat_counts?.[key]);
        const countPct = Math.max(0, Math.min(100, (count / 30) * 100));
        return `
          <label class="shaft-substat-tile" style="--count-pct:${countPct}%">
            <span class="shaft-substat-name">${escapeHtml(unit.label || key)}</span>
            <small>${escapeHtml(unitLabel)}</small>
            <span class="shaft-substat-entry">
              <input data-slot="${member.slot}" data-substat="${key}" type="number" min="0" max="30" step="1" inputmode="numeric" value="${count}" aria-label="${escapeHtml(unit.label || key)}词条数">
              <b>B</b>
            </span>
            <span class="shaft-substat-meter"><i></i></span>
          </label>
        `;
      }).join('');
      return `
        <article class="shaft-member-card" data-slot="${member.slot}" style="--slot-color:${slotColor}">
          <section class="shaft-member-identity">
            <span class="shaft-member-slot">0${Number(member.slot) + 1}</span>
            <img class="shaft-member-avatar" src="${escapeHtml(character.avatar || member.character_avatar || '')}" alt="">
            <strong>${escapeHtml(character.name || member.character_name || '未选择')}</strong>
            <small>角色80 · 弧盘80</small>
          </section>
          <section class="shaft-member-editor">
            <div class="shaft-loadout-grid">
              <label>
                <span>角色</span>
                <select data-slot="${member.slot}" data-field="character_id">
                  ${optionHtml(characters, member.character_id)}
                </select>
              </label>
              <label>
                <span>弧盘</span>
                <select data-slot="${member.slot}" data-field="arc_id">
                  ${optionHtml(arcs, member.arc_id)}
                </select>
              </label>
              <label>
                <span>卡带</span>
                <select data-slot="${member.slot}" data-field="cartridge_id">
                  ${optionHtml(cartridges, member.cartridge_id)}
                </select>
              </label>
            </div>
            <div class="shaft-member-switches">
              <div class="shaft-awakening-control">
                <span>觉醒</span>
                <div class="shaft-awakening-dots">${awakeningToggles}</div>
              </div>
              <label class="shaft-bond-toggle">
                <input data-slot="${member.slot}" data-field="bond_full" type="checkbox" ${member.bond_full ? 'checked' : ''}>
                <span>${escapeHtml(bondLabel)}</span>
              </label>
            </div>
            <div class="shaft-skill-levels">
              <div>
                <span>技能等级</span>
                <strong>基础等级 1-10</strong>
              </div>
              <div class="shaft-skill-level-grid">${skillLevelControls}</div>
            </div>
            <div class="shaft-cartridge-tuning">
              <div class="shaft-tuning-title">
                <span>卡带调校</span>
                <strong>主词条与空幕</strong>
              </div>
              <label>
                <span>主词条</span>
                <select data-slot="${member.slot}" data-field="cartridge_main_stat">
                  ${mainStatSelect}
                </select>
              </label>
              <label>
                <span>空幕加成</span>
                <input data-slot="${member.slot}" data-curtain-field="value" type="number" min="0" max="100" step="1" inputmode="numeric" value="${formatNumber(curtainBonus.value || 0, 0)}">
              </label>
              <label>
                <span>空幕属性</span>
                <select data-slot="${member.slot}" data-curtain-field="stat">
                  ${curtainStatSelect}
                </select>
              </label>
              <label>
                <span>空幕型号</span>
                <select data-slot="${member.slot}" data-curtain-field="passive_type">
                  ${curtainPassiveSelect}
                </select>
              </label>
              <output>
                <span>自动层数</span>
                <strong>${formatNumber(curtainLayers, 0)}</strong>
              </output>
            </div>
            <div class="shaft-substat-head">
              <div>
                <span>副词条</span>
                <strong>词条数输入</strong>
              </div>
              <em>0-30 B</em>
            </div>
            <div class="shaft-substat-grid">${substats}</div>
          </section>
        </article>
      `;
    }).join('');
  }

  function renderEnemy() {
    $('shaft-enemy-level').value = state.axis.enemy.level || 90;
    $('shaft-enemy-track-outside').checked = Boolean(state.axis.enemy.track_outside);
    const active = new Set(state.axis.enemy.weakness_elements || []);
    $('shaft-weakness-row').innerHTML = ELEMENTS.map((element) => `
      <label class="shaft-chip">
        <input type="checkbox" value="${element}" ${active.has(element) ? 'checked' : ''}>
        <span>${element}</span>
      </label>
    `).join('');
  }

  function renderActionAdder() {
    const addSlot = $('shaft-add-slot');
    const librarySlot = $('shaft-library-slot');
    if (!addSlot) {
      if (librarySlot) {
        librarySlot.innerHTML = slotOptions(state.librarySlot);
      }
      return;
    }
    const selectedSlot = Number(addSlot.value || state.librarySlot || 0);
    addSlot.innerHTML = slotOptions(selectedSlot);
    const slot = Number(addSlot.value || selectedSlot);
    const addAction = $('shaft-add-action');
    addAction.innerHTML = optionHtml(actionsForSlot(slot), addAction.value, actionLabel);
    if (librarySlot) {
      librarySlot.innerHTML = slotOptions(state.librarySlot);
    }
  }

  function renderTeamDock() {
    const dock = $('shaft-team-dock');
    if (!dock) {
      return;
    }
    dock.innerHTML = (state.axis.team || []).map((member) => {
      const selected = Number(member.slot) === Number(state.librarySlot) ? 'active' : '';
      const color = SLOT_COLORS[Number(member.slot) % SLOT_COLORS.length];
      return `
        <button class="shaft-operator-card ${selected}" data-dock-slot="${member.slot}" type="button" style="--slot-color:${color}" title="${Number(member.slot) + 1} · ${escapeHtml(member.character_name)}">
          <img src="${escapeHtml(member.character_avatar || '')}" alt="">
          <b>${Number(member.slot) + 1}</b>
        </button>
      `;
    }).join('');
  }

  function renderTeamBonus() {
    const node = $('shaft-team-bonus-grid');
    if (!node) {
      return;
    }
    state.axis.team_panel_bonus = normalizeTeamPanelBonus(state.axis.team_panel_bonus);
    const bonus = state.axis.team_panel_bonus;
    node.innerHTML = TEAM_PANEL_BONUS_FIELDS.map((field) => {
      const rawValue = bonus[field.key];
      const value = field.kind === 'percent' ? formatNumber(rawValue * 100, 1) : formatNumber(rawValue, 0);
      const suffix = field.kind === 'percent' ? '%' : '';
      return `
        <label class="shaft-team-bonus-tile">
          <span>${escapeHtml(field.label)}</span>
          <b>${escapeHtml(suffix)}</b>
          <input data-team-bonus="${field.key}" type="number" min="0" step="${field.step}" value="${value}" aria-label="${escapeHtml(field.label)}">
        </label>
      `;
    }).join('');
  }

  function renderCommandTypes() {
    $('shaft-command-type-tabs').innerHTML = ACTION_TYPES.map((type) => `
      <button class="shaft-type-chip ${state.commandTypeFilter === type ? 'active' : ''}" data-command-type="${escapeHtml(type)}" type="button">
        ${escapeHtml(type || '全部')}
      </button>
    `).join('');
  }

  function renderCommandLibrary() {
    const search = state.commandSearch.trim().toLowerCase();
    const actions = actionsForSlot(state.librarySlot)
      .filter((action) => !state.commandTypeFilter || action.action_type === state.commandTypeFilter)
      .filter((action) => !search || `${action.name} ${action.action_type} ${action.extra_tag || ''}`.toLowerCase().includes(search));
    $('shaft-command-list').innerHTML = actions.map((action) => `
      <article class="shaft-command-card ${actionTypeClass(action.action_type)} ${isBackgroundAction(action) ? 'background-damage' : ''}" data-action-id="${escapeHtml(action.id)}">
        <div class="shaft-command-card-body">
          <div class="shaft-command-title">
            <span class="shaft-command-type">${escapeHtml(action.action_type || '动作')}</span>
            <strong class="shaft-command-name">${escapeHtml(action.name)}</strong>
          </div>
          <span class="shaft-command-meta">${ticksToSeconds(action.duration_ticks)}s · 回能 ${formatNumber(action.energy_gain || 0, 1)}${isBackgroundAction(action) ? ' · 后台' : ''}</span>
        </div>
        <button class="secondary-btn" data-library-action="${escapeHtml(action.id)}" data-library-slot="${state.librarySlot}" type="button">加入</button>
      </article>
    `).join('') || '<div class="shaft-empty">没有动作</div>';
  }

  function renderSteps() {
    const stepList = $('shaft-step-list');
    if (!stepList) {
      return;
    }
    const selectedIds = new Set(selectedStepIds());
    const rows = (state.axis.steps || []).map((step, index) => {
      const detail = detailByStepId(step.id) || {};
      const actions = actionsForSlot(step.slot);
      const warnings = (detail.warnings || []).length ? ` · ${escapeHtml(detail.warnings.join('；'))}` : '';
      return `
        <div class="shaft-step-row ${selectedIds.has(step.id) ? 'selected' : ''}" data-step-id="${escapeHtml(step.id)}">
          <output class="shaft-step-index"><span>#${index + 1}</span><strong>${ticksToSeconds(step.start_tick)}s</strong></output>
          <label>
            <span>角色</span>
            <select data-step-id="${escapeHtml(step.id)}" data-step-field="slot">${slotOptions(step.slot)}</select>
          </label>
          <label>
            <span>动作</span>
            <select data-step-id="${escapeHtml(step.id)}" data-step-field="action_id">
              ${optionHtml(actions, step.action_id, actionLabel)}
            </select>
          </label>
          <label>
            <span>开始</span>
            <input data-step-id="${escapeHtml(step.id)}" data-step-field="start_tick" type="number" min="0" step="0.1" value="${ticksToSeconds(step.start_tick)}">
          </label>
          <output class="shaft-step-damage"><span>直伤${warnings}</span><strong>${formatNumber(detail.direct_damage || 0)}</strong></output>
          <button class="secondary-btn shaft-remove-btn" data-remove-step="${escapeHtml(step.id)}" type="button" title="删除">×</button>
        </div>
      `;
    }).join('');
    stepList.innerHTML = rows || '<div class="shaft-empty">暂无动作</div>';
  }

  function renderBuffEditor() {
    const triggerSlotSelect = $('shaft-buff-trigger-slot');
    const triggerActionSelect = $('shaft-buff-trigger-action');
    const targetSlots = $('shaft-buff-target-slots');
    const modifierKeySelect = $('shaft-buff-modifier-key');
    if (!triggerSlotSelect || !triggerActionSelect || !targetSlots || !modifierKeySelect) {
      return;
    }
    triggerSlotSelect.innerHTML = slotOptions(state.buffDraft.triggerSlot);
    const triggerSlot = Number(triggerSlotSelect.value || state.buffDraft.triggerSlot || 0);
    triggerActionSelect.innerHTML = optionHtml(actionsForSlot(triggerSlot), triggerActionSelect.value, actionLabel);
    targetSlots.innerHTML = (state.axis.team || []).map((member) => `
      <label class="shaft-chip">
        <input type="checkbox" value="${member.slot}" checked>
        <span>${Number(member.slot) + 1} · ${escapeHtml(member.character_name)}</span>
      </label>
    `).join('');
    modifierKeySelect.innerHTML = BUFF_MODIFIERS.map((item) => `
      <option value="${item.key}" ${item.key === state.buffDraft.modifierKey ? 'selected' : ''}>${escapeHtml(item.label)}</option>
    `).join('');
    renderBuffList();
  }

  function modifierMeta(key) {
    return BUFF_MODIFIERS.find((item) => item.key === key) || BUFF_MODIFIERS[0];
  }

  function modifierDisplay(key, value) {
    const meta = modifierMeta(key);
    return meta.percent ? `${formatNumber(Number(value || 0) * 100, 1)}%` : formatNumber(value, 0);
  }

  function renderBuffList() {
    const buffList = $('shaft-buff-list');
    if (!buffList) {
      return;
    }
    const items = (state.axis.buff_rules || []).map((rule) => {
      const modifierLine = Object.entries(rule.modifiers || {})
        .map(([key, value]) => `${modifierMeta(key).label} ${modifierDisplay(key, value)}`)
        .join('，');
      const triggerAction = getActionMap().get(rule.trigger?.action_id);
      const targetSlots = (rule.targets?.slots || []).map((slot) => memberName(slot)).join('、') || '全部角色';
      const targetTypes = (rule.targets?.action_types || []).join('、') || '全部动作';
      return `
        <div class="shaft-buff-item">
          <div>
            <strong>${escapeHtml(rule.name)}</strong>
            <span>${escapeHtml(memberName(rule.trigger?.slot))} · ${escapeHtml(triggerAction?.name || '动作')} → ${escapeHtml(targetSlots)} · ${escapeHtml(targetTypes)} · ${ticksToSeconds(rule.duration_ticks)}s · ${escapeHtml(modifierLine)}</span>
          </div>
          <button class="secondary-btn shaft-remove-btn" data-remove-buff="${escapeHtml(rule.id)}" type="button" title="删除">×</button>
        </div>
      `;
    }).join('');
    buffList.innerHTML = items || '<div class="shaft-empty">暂无触发增益</div>';
  }

  function renderResults() {
    const summary = state.result?.summary || {};
    $('shaft-direct-damage').textContent = formatNumber(summary.direct_damage || 0);
    $('shaft-stagger-damage').textContent = formatNumber(summary.stagger_damage || 0);
    $('shaft-total-damage').textContent = formatNumber(summary.total_damage || 0);
    $('shaft-dps').textContent = formatNumber(summary.dps || 0);
    const contribution = state.result?.damage_by_slot || [];
    $('shaft-contribution-list').innerHTML = contribution.map((item) => `
      <div class="shaft-contribution-row">
        <span>${escapeHtml(item.character_name)}</span>
        <div class="shaft-contribution-bar"><span style="width: ${Math.max(0, Math.min(100, Number(item.percent || 0)))}%"></span></div>
        <span>${formatNumber(item.percent || 0, 1)}%</span>
      </div>
    `).join('');
    renderBuildPanel();
    renderWorkbenchSummary();
  }

  function renderBuildPanel() {
    const node = $('shaft-build-panel');
    if (!node) {
      return;
    }
    const team = state.axis?.team || [];
    if (!team.length) {
      node.innerHTML = '<div class="shaft-empty">先选择队伍</div>';
      return;
    }
    if (!team.some((member) => Number(member.slot) === Number(state.buildPanelSlot))) {
      state.buildPanelSlot = Number(team[0]?.slot || 0);
    }
    const panels = currentBuildPanels();
    const panel = panels.find((item) => Number(item.slot) === Number(state.buildPanelSlot));
    const member = memberBySlot(state.buildPanelSlot) || team[0] || {};
    const panelStats = panel?.panel || {};
    const baseStats = panel?.base_stats || {};
    const zones = panel?.zones || {};
    const buildOptions = panel?.build_options || {};
    const curtain = buildOptions.curtain_bonus || {};
    const avatarButtons = team.map((item) => {
      const active = Number(item.slot) === Number(state.buildPanelSlot) ? 'active' : '';
      const color = SLOT_COLORS[Number(item.slot) % SLOT_COLORS.length];
      return `
        <button class="shaft-panel-avatar ${active}" data-build-panel-slot="${item.slot}" type="button" style="--slot-color:${color}" title="${Number(item.slot) + 1} · ${escapeHtml(item.character_name)}">
          <img src="${escapeHtml(item.character_avatar || '')}" alt="">
          <b>${Number(item.slot) + 1}</b>
        </button>
      `;
    }).join('');
    if (!panel) {
      node.innerHTML = `
        <div class="shaft-panel-avatar-row">${avatarButtons}</div>
        <div class="shaft-empty">等待计算面板</div>
      `;
      return;
    }
    const mainStats = [
      { label: '攻击', key: 'atk', pct: 'atk_pct', flat: 'flat_atk' },
      { label: '生命', key: 'hp', pct: 'hp_pct', flat: 'flat_hp' },
      { label: '防御', key: 'def', pct: 'def_pct', flat: 'flat_def' },
    ].map((item) => `
      <div class="shaft-panel-major">
        <span>${item.label}</span>
        <strong>${formatNumber(panelStats[item.key] || 0)}</strong>
        <small>基础 ${formatNumber(baseStats[item.key] || 0)} · ${formatPercent(zones[item.pct] || 0)} · 固定 ${formatNumber(zones[item.flat] || 0)}</small>
      </div>
    `).join('');
    const minorStats = [
      ['暴击', formatPercent(panelStats.crit_rate || 0)],
      ['暴伤', formatPercent(panelStats.crit_dmg || 0)],
      ['属伤', formatPercent(panelStats.element_dmg || 0)],
      ['充能', formatPercent(panelStats.energy_recharge || 0)],
      ['环合强度', formatNumber(panelStats.harmony_strength || 0)],
      ['倾陷强度', formatNumber(panelStats.stagger_strength || 0)],
      ['全伤', formatPercent(panelStats.all_dmg || 0)],
    ].map(([label, value]) => `
      <div class="shaft-panel-minor">
        <span>${label}</span>
        <strong>${value}</strong>
      </div>
    `).join('');
    node.innerHTML = `
      <div class="shaft-panel-avatar-row">${avatarButtons}</div>
      <div class="shaft-panel-profile">
        <div>
          <span>当前查看</span>
          <strong>${escapeHtml(member.character_name || panel.character_name || '角色')}</strong>
        </div>
        <small>${escapeHtml(member.arc_name || '')} · ${escapeHtml(member.cartridge_name || '')} · 主词条 ${escapeHtml(buildOptions.cartridge_main_stat || '')} · 空幕 ${escapeHtml(curtain.value || 0)}${escapeHtml(curtain.stat || '')} x ${formatNumber(curtain.layers || 0, 0)}</small>
      </div>
      <div class="shaft-panel-major-grid">${mainStats}</div>
      <div class="shaft-panel-minor-grid">${minorStats}</div>
    `;
  }

  function renderWorkbenchSummary() {
    const node = $('shaft-workbench-summary');
    if (!node) {
      return;
    }
    const summary = state.result?.summary || {};
    const contribution = state.result?.damage_by_slot || [];
    const bars = contribution.map((item, index) => `
      <div class="shaft-mini-contribution">
        <span>${escapeHtml(item.character_name)}</span>
        <b>${formatNumber(item.percent || 0, 1)}%</b>
        <i style="--bar:${Math.max(0, Math.min(100, Number(item.percent || 0)))}%; --slot-color:${SLOT_COLORS[index % SLOT_COLORS.length]}"></i>
      </div>
    `).join('');
    node.innerHTML = `
      <div class="shaft-summary-grid">
        <div><span>总伤害</span><strong>${formatNumber(summary.total_damage || 0)}</strong></div>
        <div><span>DPS</span><strong>${formatNumber(summary.dps || 0)}</strong></div>
        <div><span>直伤</span><strong>${formatNumber(summary.direct_damage || 0)}</strong></div>
        <div><span>倾陷伤害</span><strong>${formatNumber(summary.stagger_damage || 0)}</strong></div>
      </div>
      <div class="shaft-mini-contribution-list">${bars}</div>
    `;
  }

  function applyQInstantReleaseToTimelineDetails(details) {
    const qEvents = (details || [])
      .filter((detail) => !detail.is_background_damage && isQAction(actionForStep({ action_id: detail.action_id })))
      .sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0) || Number(a.slot || 0) - Number(b.slot || 0));
    qEvents.forEach((qDetail) => {
      const qStartTick = Number(qDetail.start_tick || 0);
      const qVisualEndTick = Number(qDetail.visual_end_tick || qDetail.end_tick || qStartTick + 1);
      const qAnchorTick = Number(qDetail.duration_ticks || 0) === 0
        ? qStartTick
        : qStartTick + (Math.max(qStartTick + 1, qVisualEndTick) - qStartTick) / 2;
      details.forEach((detail) => {
        if (detail === qDetail || detail.q_instant_release) {
          return;
        }
        const startTick = Number(detail.start_tick || 0);
        const endTick = Number(detail.end_tick || startTick);
        const durationTicks = Math.max(0, Number(detail.duration_ticks || 0));
        const sameColumnOther = Number(detail.slot) !== Number(qDetail.slot) && (
          (startTick <= qStartTick && qStartTick < endTick) || startTick === qStartTick
        );
        const ongoingForeground = !detail.is_background_damage && durationTicks > 0 && startTick < qStartTick && qStartTick < endTick;
        if (!sameColumnOther && !ongoingForeground) {
          return;
        }
        detail.original_duration_ticks = Number(detail.original_duration_ticks ?? durationTicks);
        detail.original_end_tick = Number(detail.original_end_tick ?? endTick);
        detail.original_visual_end_tick = Number(detail.original_visual_end_tick ?? detail.visual_end_tick ?? endTick);
        detail.duration_ticks = Math.max(0, qStartTick - startTick);
        detail.end_tick = Math.max(startTick, qStartTick);
        detail.visual_end_tick = Math.max(startTick, qStartTick);
        detail.q_instant_release_kind = sameColumnOther ? 'column' : 'foreground';
        detail.q_instant_release = true;
        detail.q_instant_release_tick = qStartTick;
        detail.q_instant_release_anchor_tick = qAnchorTick;
        detail.q_instant_release_anchor_step_id = qDetail.step_id;
      });
    });
    return details;
  }

  function applySwitchLossToTimelineDetails(details) {
    const switchLossTicks = Math.max(
      0,
      Number(state.axis?.options?.switch_loss_ticks ?? state.catalog?.formula_constants?.switch_loss_ticks ?? 2),
    );
    let frontSlot = null;
    let previousForegroundDurationTicks = 0;
    details
      .slice()
      .sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0) || Number(a.slot || 0) - Number(b.slot || 0))
      .forEach((detail) => {
        if (detail.is_background_damage) {
          return;
        }
        if (frontSlot !== null && Number(frontSlot) !== Number(detail.slot) && previousForegroundDurationTicks > 0) {
          detail.start_tick = Number(detail.start_tick || 0) + switchLossTicks;
          detail.end_tick = Number(detail.end_tick || 0) + switchLossTicks;
          detail.visual_end_tick = Number(detail.visual_end_tick || detail.end_tick || 0) + switchLossTicks;
        }
        frontSlot = Number(detail.slot);
        previousForegroundDurationTicks = Math.max(0, Number(detail.duration_ticks || 0));
      });
    return details;
  }

  function timelineMaxTick(renderDetails = null) {
    const details = renderDetails || state.result?.details || [];
    const windows = renderDetails ? [] : (state.result?.front_windows || []);
    const lastTick = Math.max(
      details.length ? 0 : axisEndTick(true),
      Number(state.cursorTick || 0) + 1,
      ...details.map((detail) => Number(detail.visual_end_tick || detail.end_tick || detail.start_tick || 0) + 10),
      ...windows.map((windowItem) => Number(windowItem.end_tick || windowItem.start_tick || 0)),
    );
    return Math.max(1, lastTick + TIMELINE_END_PADDING_TICKS);
  }

  function renderTimeline() {
    const result = state.result;
    const resultDetails = result?.details || [];
    const resultDetailByStepId = new Map(resultDetails.map((detail) => [detail.step_id, detail]));
    const canUseResultTiming = Boolean((state.axis.steps || []).length) && (state.axis.steps || []).every((step) => {
      const resultDetail = resultDetailByStepId.get(step.id);
      return resultDetail &&
        String(resultDetail.action_id || '') === String(step.action_id || '') &&
        Number(resultDetail.slot) === Number(step.slot) &&
        Number(resultDetail.raw_start_tick ?? resultDetail.start_tick ?? -1) === Number(step.start_tick || 0);
    });
    const details = (state.axis.steps || []).map((step) => {
      const action = actionForStep(step);
      const durationTicks = actionDurationTicks(action);
      const startTick = Number(step.start_tick || 0);
      const resultDetail = canUseResultTiming ? (resultDetailByStepId.get(step.id) || {}) : {};
      const renderStartTick = Number(resultDetail.start_tick ?? startTick);
      const renderEndTick = Number(resultDetail.end_tick ?? (renderStartTick + durationTicks));
      const renderDurationTicks = Number(resultDetail.duration_ticks ?? Math.max(0, renderEndTick - renderStartTick));
      const renderVisualEndTick = Number(resultDetail.visual_end_tick ?? (renderStartTick + (renderDurationTicks > 0 ? renderDurationTicks : ZERO_ACTION_VISUAL_TICKS)));
      return Object.assign({}, resultDetail, {
        step_id: step.id,
        slot: Number(step.slot || 0),
        action_id: step.action_id,
        action_name: action.name || step.action_name || '',
        action_type: action.action_type || '',
        raw_start_tick: startTick,
        start_tick: renderStartTick,
        end_tick: renderEndTick,
        duration_ticks: renderDurationTicks,
        visual_end_tick: renderVisualEndTick,
        is_background_damage: isStepBackground(step, action),
        is_basic_background: isBasicBackgroundOverride(step, action),
        placement: step.placement || 'foreground',
      });
    });
    if (!canUseResultTiming) {
      applySwitchLossToTimelineDetails(details);
    }
    applyQInstantReleaseToTimelineDetails(details);
    const durationTicks = timelineMaxTick(details);
    state.timelineDurationTicks = durationTicks;
    const zeroGroups = new Map();
    details.forEach((detail) => {
      if (Number(detail.duration_ticks || 0) !== 0) {
        return;
      }
      const tick = Math.max(0, Number(detail.start_tick || 0));
      zeroGroups.set(tick, (zeroGroups.get(tick) || 0) + 1);
    });
    const expansionBreaks = Array.from(zeroGroups.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([tick, count]) => ({
        tick,
        extraPx: Math.max(0, MIN_ACTION_CARD_PX + ZERO_ACTION_GAP_PX - TIMELINE_TICK_PX) * Math.max(1, Math.ceil(count / MAX_VISUAL_LANES_PER_SLOT)),
      }));
    const visualOffsetPx = (tick) => {
      const safeTick = Math.max(0, Number(tick || 0));
      return safeTick * TIMELINE_TICK_PX + expansionBreaks
        .filter((breakItem) => breakItem.tick < safeTick)
        .reduce((sum, breakItem) => sum + breakItem.extraPx, 0);
    };
    const timelineBodyPx = Math.max(900, visualOffsetPx(durationTicks));
    state.timelineScale = { expansionBreaks, bodyPx: timelineBodyPx };
    const timelineTotalPx = TIMELINE_LABEL_PX + timelineBodyPx;
    const leftPx = (tick) => TIMELINE_LABEL_PX + visualOffsetPx(tick);
    const widthPx = (start, end, visualEnd) => {
      if (Number(end || start) <= Number(start || 0)) {
        return MIN_ACTION_CARD_PX;
      }
      const fixedEnd = visualEnd || end || (Number(start || 0) + ZERO_ACTION_VISUAL_TICKS);
      return Math.max(MIN_ACTION_CARD_PX, visualOffsetPx(Math.max(fixedEnd, Number(start || 0) + 1)) - visualOffsetPx(start));
    };
    const bandWidthPx = (start, end) => Math.max(1, visualOffsetPx(Math.max(Number(end || start), Number(start || 0) + 1)) - visualOffsetPx(start));
    const rulerMarks = [];
    const cursor = (labeled) => `<span class="shaft-cursor-line" style="left:${leftPx(state.cursorTick)}px">${labeled ? `<b>${ticksToSeconds(state.cursorTick)}s</b>` : ''}</span>`;
    for (let tick = 0; tick <= durationTicks; tick += 10) {
      const isMajor = tick % 50 === 0;
      const isSecond = tick % 10 === 0;
      rulerMarks.push(`<span class="shaft-ruler-mark ${isMajor ? 'major' : ''} ${isSecond ? 'second' : ''}" style="left:${leftPx(tick)}px"><span>${tick / 10}s</span></span>`);
    }
    $('shaft-time-ruler').style.width = `${timelineTotalPx}px`;
    $('shaft-timeline').style.width = `${timelineTotalPx}px`;
    $('shaft-time-ruler').style.setProperty('--label-width', `${TIMELINE_LABEL_PX}px`);
    $('shaft-timeline').style.setProperty('--label-width', `${TIMELINE_LABEL_PX}px`);
    $('shaft-time-ruler').innerHTML = rulerMarks.join('') + cursor(true);
    const foregroundEvents = details
      .filter((detail) => !detail.is_background_damage)
      .sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0))
      .map((detail) => ({
        slot: Number(detail.slot || 0),
        start_tick: Number(detail.start_tick || 0),
        end_tick: Number(detail.visual_end_tick || detail.end_tick || detail.start_tick || 0),
      }));
    const frontWindowItems = [];
    foregroundEvents.forEach((eventItem, index) => {
      const endTick = index + 1 < foregroundEvents.length
        ? Math.max(eventItem.start_tick + 1, foregroundEvents[index + 1].start_tick)
        : Math.max(eventItem.start_tick + 1, eventItem.end_tick);
      const lastWindow = frontWindowItems[frontWindowItems.length - 1];
      if (lastWindow && Number(lastWindow.slot) === Number(eventItem.slot)) {
        lastWindow.end_tick = Math.max(lastWindow.end_tick, endTick);
        return;
      }
      frontWindowItems.push({
        slot: eventItem.slot,
        start_tick: eventItem.start_tick,
        end_tick: endTick,
      });
    });
    const qAnchorRightPxByStepId = new Map();
    details.forEach((detail) => {
      if (!detail.step_id || detail.is_background_damage || !isQAction(actionForStep({ action_id: detail.action_id }))) {
        return;
      }
      const qLeft = leftPx(detail.start_tick);
      const qWidth = widthPx(detail.start_tick, detail.end_tick, detail.visual_end_tick);
      const qCenterPx = Number(detail.duration_ticks || 0) === 0 ? leftPx(detail.start_tick) : qLeft + qWidth / 2;
      qAnchorRightPxByStepId.set(detail.step_id, qCenterPx);
    });
    const actionTracks = (state.axis.team || []).map((member) => {
      const selectedIds = new Set(selectedStepIds());
      const color = SLOT_COLORS[Number(member.slot) % SLOT_COLORS.length];
      const resources = slotResourcesAtCursor(member.slot);
      const energyLabel = formatNumber(resources.energy || 0, 1);
      const harmonyLabel = formatNumber(resources.harmony || 0, 1);
      const frontBands = frontWindowItems
        .filter((windowItem) => Number(windowItem.slot) === Number(member.slot))
        .map((windowItem) => `
          <span
            class="shaft-lane-front-band"
            style="left:${leftPx(windowItem.start_tick)}px; width:${bandWidthPx(windowItem.start_tick, windowItem.end_tick)}px; --slot-color:${color}"
            title="${escapeHtml(memberName(windowItem.slot))} 前台 ${ticksToSeconds(windowItem.start_tick)}s"
          ></span>
        `).join('');
      const slotDetails = details
        .filter((detail) => Number(detail.slot) === Number(member.slot))
        .sort((a, b) => Number(a.start_tick) - Number(b.start_tick));
      const backgroundLaneEnds = [];
      const laidOut = slotDetails.map((detail) => {
        let startPx = leftPx(detail.start_tick);
        let cardWidth = widthPx(detail.start_tick, detail.end_tick, detail.visual_end_tick);
        const qAnchorRightPx = qAnchorRightPxByStepId.get(detail.q_instant_release_anchor_step_id || '');
        if (Number.isFinite(qAnchorRightPx)) {
          const elapsedWidth = qAnchorRightPx - startPx;
          if (elapsedWidth >= MIN_Q_INSTANT_CARD_PX) {
            cardWidth = elapsedWidth;
          } else {
            cardWidth = MIN_Q_INSTANT_CARD_PX;
            startPx = qAnchorRightPx - cardWidth;
          }
        }
        let laneIndex = 0;
        if (detail.is_background_damage) {
          const backgroundLaneLimit = Math.max(1, MAX_VISUAL_LANES_PER_SLOT - 1);
          let backgroundLaneIndex = backgroundLaneEnds.findIndex((endPx) => startPx >= endPx + 6);
          if (backgroundLaneIndex < 0) {
            if (backgroundLaneEnds.length < backgroundLaneLimit) {
              backgroundLaneIndex = backgroundLaneEnds.length;
              backgroundLaneEnds.push(0);
            } else {
              backgroundLaneIndex = backgroundLaneEnds.indexOf(Math.min(...backgroundLaneEnds));
            }
          }
          backgroundLaneEnds[backgroundLaneIndex] = startPx + cardWidth;
          laneIndex = backgroundLaneIndex + 1;
        }
        return { detail, laneIndex, startPx, cardWidth };
      });
      const maxLaneIndex = laidOut.reduce((maxIndex, entry) => Math.max(maxIndex, entry.laneIndex), 0);
      const trackHeight = Math.max(132, 46 + (maxLaneIndex + 1) * 38);
      const bars = laidOut
        .map((entry) => {
          const detail = entry.detail;
          const isSelected = selectedIds.has(detail.step_id);
          const selected = isSelected ? 'selected' : '';
          const dragging = state.dragState?.stepIds?.includes(detail.step_id) ? 'dragging-preview' : '';
          const frontStart = !detail.is_background_damage ? 'front-start' : '';
          const basicBackground = detail.is_basic_background ? 'basic-background' : '';
          const qInstant = detail.q_instant_release ? `q-instant-release q-instant-${detail.q_instant_release_kind || 'release'}` : '';
          const top = 18 + entry.laneIndex * 38;
          const durationLabel = Number(detail.duration_ticks || 0) > 0 ? `<em>${ticksToSeconds(detail.duration_ticks)}s</em>` : '';
          return `
            <span class="shaft-action-bar ${actionTypeClass(detail.action_type)} ${detail.is_background_damage ? 'background-damage' : ''} ${basicBackground} ${frontStart} ${qInstant} ${selected} ${dragging}" data-step-id="${escapeHtml(detail.step_id)}" style="left:${entry.startPx}px; top:${top}px; width:${entry.cardWidth}px; --slot-color:${color}" title="${escapeHtml(detail.action_name)}${detail.q_instant_release ? ' · Q即时释放' : ''}">
              <span>${escapeHtml(detail.action_name)}</span>
              ${durationLabel}
            </span>
          `;
        }).join('');
      return `
        <div class="shaft-time-track action-track" data-slot="${member.slot}" style="width:${timelineTotalPx}px; height:${trackHeight}px">
          <span class="shaft-track-label">
            <span class="shaft-track-portrait">
              <img src="${escapeHtml(member.character_avatar || '')}" alt="">
              <small>能量 ${energyLabel}</small>
              <small>环合 ${harmonyLabel}</small>
            </span>
            <span class="shaft-track-name">${escapeHtml(member.character_name)}</span>
          </span>
          <span class="shaft-track-surface"></span>
          ${frontBands}${bars}${cursor(false)}
        </div>
      `;
    }).join('');
    $('shaft-timeline').innerHTML = actionTracks;
  }

  function renderStepDetail() {
    const selectionCount = selectedStepIds().length;
    const step = selectedStep();
    const detail = step ? detailByStepId(step.id) : null;
    const action = step ? actionForStep(step) : null;
    const badge = $('shaft-selected-badge');
    const panel = $('shaft-step-detail');
    if (selectionCount > 1) {
      badge.textContent = `${selectionCount} 个动作`;
      panel.innerHTML = `
        <div class="shaft-detail-hero">
          <span class="shaft-detail-muted">当前框选</span>
          <strong>${selectionCount} 个动作</strong>
        </div>
      `;
      return;
    }
    if (!step || !action) {
      badge.textContent = '未选择';
      panel.innerHTML = '<div class="shaft-empty">选择时间轴上的动作</div>';
      return;
    }
    badge.textContent = `${ticksToSeconds(step.start_tick)}s`;
    const panelStats = detail?.panel || {};
    const durationTicks = Number(detail?.duration_ticks ?? action.duration_ticks ?? 0);
    const durationSeconds = durationTicks / 10;
    const dpsSeconds = Math.max(durationSeconds, 0.1);
    const actionDamage = Number(detail?.direct_damage || 0) + Number(detail?.stagger_damage || 0);
    const actionDps = actionDamage / dpsSeconds;
    const energyGain = Number(action.energy_gain || 0) + Number(action.energy_return || 0);
    const harmonyGain = Number(detail?.harmony ?? action.harmony ?? 0);
    const appliedBuffs = (detail?.applied_buffs || []).map((buff) => buff.name).join('、') || '无';
    const triggeredBuffs = (detail?.triggered_buffs || []).map((buff) => buff.name).join('、') || '无';
    const warnings = (detail?.warnings || []).join('；') || '无';
    const specialStats = [];
    const nightmareStacks = detail?.nightmare_stacks ?? action.nightmare_stacks;
    const sinRecovery = detail?.sin_recovery ?? action.sin_recovery;
    if (nightmareStacks !== undefined && nightmareStacks !== null) {
      specialStats.push(`<div class="shaft-detail-kv"><span>噩梦层数</span><strong>${formatNumber(nightmareStacks, 0)}</strong></div>`);
    }
    if (sinRecovery !== undefined && sinRecovery !== null) {
      specialStats.push(`<div class="shaft-detail-kv"><span>回复罪状</span><strong>${formatNumber(sinRecovery, 0)}</strong></div>`);
    }
    panel.innerHTML = `
      <div class="shaft-detail-hero">
        <strong>${escapeHtml(action.name)}</strong>
        <span class="shaft-detail-muted">${escapeHtml(memberName(step.slot))} · ${escapeHtml(action.action_type || '动作')} · ${isStepBackground(step, action) ? (isBasicBackgroundOverride(step, action) ? '后台普攻' : '后台伤害') : '前台动作'}</span>
      </div>
      <div class="shaft-detail-grid">
        <div class="shaft-detail-kv"><span>开始</span><strong>${ticksToSeconds(detail?.start_tick ?? step.start_tick)}s</strong></div>
        <div class="shaft-detail-kv"><span>结束</span><strong>${ticksToSeconds(detail?.end_tick ?? step.start_tick)}s</strong></div>
        <div class="shaft-detail-kv"><span>直伤</span><strong>${formatNumber(detail?.direct_damage || 0)}</strong></div>
        <div class="shaft-detail-kv"><span>倾陷</span><strong>${formatNumber(detail?.stagger_amount || 0, 2)}</strong></div>
        <div class="shaft-detail-kv"><span>耗时</span><strong>${formatNumber(durationSeconds, 1)}s</strong></div>
        <div class="shaft-detail-kv"><span>回能</span><strong>${formatNumber(energyGain, 1)}</strong></div>
        <div class="shaft-detail-kv"><span>环合</span><strong>${formatNumber(harmonyGain, 1)}</strong></div>
        <div class="shaft-detail-kv"><span>DPS</span><strong>${formatNumber(actionDps)}</strong></div>
        ${specialStats.join('')}
      </div>
      <div class="shaft-detail-hero">
        <span class="shaft-detail-muted">实时面板</span>
        <strong>${escapeHtml(memberName(step.slot))}</strong>
      </div>
      <div class="shaft-detail-grid">
        <div class="shaft-detail-kv"><span>攻击</span><strong>${formatNumber(panelStats.atk || 0)}</strong></div>
        <div class="shaft-detail-kv"><span>生命</span><strong>${formatNumber(panelStats.hp || 0)}</strong></div>
        <div class="shaft-detail-kv"><span>防御</span><strong>${formatNumber(panelStats.def || 0)}</strong></div>
        <div class="shaft-detail-kv"><span>环合强度</span><strong>${formatNumber(panelStats.harmony_strength || 0)}</strong></div>
        <div class="shaft-detail-kv"><span>倾陷强度</span><strong>${formatNumber(panelStats.stagger_strength || 0)}</strong></div>
        <div class="shaft-detail-kv"><span>暴击</span><strong>${formatNumber((panelStats.crit_rate || 0) * 100, 1)}%</strong></div>
        <div class="shaft-detail-kv"><span>暴伤</span><strong>${formatNumber((panelStats.crit_dmg || 0) * 100, 1)}%</strong></div>
      </div>
      <div class="shaft-detail-hero">
        <span class="shaft-detail-muted">生效增益</span>
        <strong>${escapeHtml(appliedBuffs)}</strong>
      </div>
      <div class="shaft-detail-hero">
        <span class="shaft-detail-muted">触发增益</span>
        <strong>${escapeHtml(triggeredBuffs)}</strong>
      </div>
      <div class="shaft-detail-hero">
        <span class="shaft-detail-muted">校验</span>
        <strong>${escapeHtml(warnings)}</strong>
      </div>
    `;
  }

  function renderMarketFilters() {
    const selected = $('shaft-market-character-filter').value || '';
    $('shaft-market-character-filter').innerHTML = `<option value="">全部角色</option>${optionHtml(state.catalog.characters, selected)}`;
  }

  function marketCardHtml(axis, compact) {
    const team = (axis.team || []).map((member) => member.character_name).join(' / ');
    return `
      <article class="shaft-market-card" data-axis-id="${axis.id}" data-axis-source="${compact ? 'mine' : 'market'}">
        <strong>${escapeHtml(axis.title)}</strong>
        <div class="shaft-market-team">${escapeHtml(team)}</div>
        <div class="shaft-market-stats">
          <span>DPS ${formatNumber(axis.dps || 0)}</span>
          <span>直伤 ${formatNumber(axis.direct_damage || 0)}</span>
          <span>倾陷 ${formatNumber(axis.stagger_damage || 0)}</span>
        </div>
        <div class="shaft-market-meta">${escapeHtml(axis.owner?.nickname || '')} · ${escapeHtml(axis.source_version || '')}</div>
        ${compact ? '' : `
          <div class="shaft-market-actions">
            <button class="secondary-btn ${axis.liked ? 'active' : ''}" data-like-axis="${axis.id}" type="button">赞 ${axis.like_count || 0}</button>
            <button class="secondary-btn ${axis.favorited ? 'active' : ''}" data-favorite-axis="${axis.id}" type="button">藏 ${axis.favorite_count || 0}</button>
          </div>
        `}
        ${compact ? `
          <div class="shaft-market-actions">
            <button class="secondary-btn danger-btn" data-delete-axis="${axis.id}" data-axis-title="${escapeHtml(axis.title)}" type="button">删除</button>
          </div>
        ` : ''}
      </article>
    `;
  }

  function renderMarketList() {
    $('shaft-market-list').innerHTML = state.marketItems.map((axis) => marketCardHtml(axis, false)).join('') || '<div class="shaft-empty">暂无公开排轴</div>';
    $('shaft-market-more-btn').hidden = !state.marketHasMore;
  }

  function renderInsertMode() {
    document.querySelectorAll('[data-shaft-insert-mode]').forEach((button) => {
      button.classList.toggle('active', button.dataset.shaftInsertMode === state.insertMode);
    });
  }

  function renderAll() {
    setPage(state.page, false);
    renderLoginState();
    renderTeam();
    renderTeamDock();
    renderTeamBonus();
    renderEnemy();
    renderActionAdder();
    renderCommandTypes();
    renderCommandLibrary();
    renderSteps();
    renderBuffEditor();
    renderResults();
    renderTimeline();
    renderStepDetail();
    renderMarketFilters();
    renderEditorActions();
  }

  function updateMemberNames(member) {
    if (!state.catalog) {
      return;
    }
    const character = getCharacterMap().get(member.character_id) || {};
    const arc = getArcMap().get(member.arc_id) || {};
    const cartridge = getCartridgeMap().get(member.cartridge_id) || {};
    member.character_name = character.name || member.character_name || '';
    member.character_avatar = character.avatar || '';
    member.character_element = character.element || '';
    member.arc_name = arc.name || '';
    member.cartridge_name = cartridge.name || '';
  }

  function removeInvalidStepsForSlot(slot) {
    const validActions = new Set(actionsForSlot(slot).map((action) => action.id));
    state.axis.steps = state.axis.steps.filter((step) => Number(step.slot) !== Number(slot) || validActions.has(step.action_id));
  }

  function sortSteps() {
    state.axis.steps.sort((a, b) => Number(a.start_tick) - Number(b.start_tick) || Number(a.slot) - Number(b.slot));
  }

  function coveredIntervals() {
    return (state.axis?.steps || [])
      .map((step) => ({
        start: Math.max(0, Number(step.start_tick || 0)),
        end: Math.max(Number(step.start_tick || 0) + 1, stepEndTick(step, true)),
      }))
      .filter((item) => item.end > item.start)
      .sort((a, b) => a.start - b.start || a.end - b.end);
  }

  function compactIdleGaps() {
    let guard = 0;
    while (guard < 120) {
      guard += 1;
      sortSteps();
      let cursor = 0;
      const gapInterval = coveredIntervals().find((interval) => {
        if (interval.end <= cursor) {
          cursor = Math.max(cursor, interval.end);
          return false;
        }
        if (interval.start > cursor) {
          return true;
        }
        cursor = Math.max(cursor, interval.end);
        return false;
      });
      if (!gapInterval) {
        break;
      }
      const gap = gapInterval.start - cursor;
      state.axis.steps.forEach((step) => {
        if (Number(step.start_tick || 0) >= gapInterval.start) {
          step.start_tick = Math.max(0, Number(step.start_tick || 0) - gap);
        }
      });
    }
  }

  function applyForegroundConflictOrder(orderedSteps) {
    const usedForegroundStarts = new Set();
    const qStartTicks = new Set((state.axis?.steps || [])
      .filter((step) => {
        const action = actionForStep(step);
        return startsForeground(step, action) && isQAction(action);
      })
      .map((step) => Number(step.start_tick || 0)));
    const slotBlockingEnd = new Map();
    const supportBlocks = [];
    for (const step of orderedSteps) {
      const action = actionForStep(step);
      const foregroundStart = startsForeground(step, action);
      const slotBlocking = blocksSlotOverlap(step, action);
      if (!foregroundStart && !slotBlocking) {
        continue;
      }
      let startTick = Math.max(0, Number(step.start_tick || 0));
      let guard = 0;
      while (guard < 1000) {
        guard += 1;
        if (slotBlocking) {
          startTick = Math.max(startTick, Number(slotBlockingEnd.get(Number(step.slot)) || 0));
        }
        if (foregroundStart) {
          if (qStartTicks.has(startTick)) {
            supportBlocks.forEach((block) => {
              if (block.start < startTick && startTick < block.end) {
                block.end = startTick;
              }
            });
          }
          const supportBlock = supportBlocks.find((block) => startTick >= block.start && startTick < block.end);
          if (supportBlock && !qStartTicks.has(startTick)) {
            startTick = supportBlock.end;
            continue;
          }
          if (usedForegroundStarts.has(startTick) && !qStartTicks.has(startTick)) {
            startTick += 1;
            continue;
          }
        }
        break;
      }
      step.start_tick = startTick;
      const endTick = startTick + actionEditorDurationTicks(action);
      if (foregroundStart) {
        usedForegroundStarts.add(startTick);
      }
      if (slotBlocking) {
        slotBlockingEnd.set(Number(step.slot), endTick);
      }
      if (foregroundStart && isSupportAction(action)) {
        supportBlocks.push({ start: startTick, end: endTick });
      }
    }
  }

  function resolveForegroundConflicts() {
    sortSteps();
    applyForegroundConflictOrder(state.axis.steps);
  }

  function resolveForegroundConflictsWithPriority(priorityStepIds) {
    const priorityIds = new Set(priorityStepIds || []);
    if (!priorityIds.size) {
      resolveForegroundConflicts();
      return;
    }
    sortSteps();
    const prioritySteps = state.axis.steps
      .filter((step) => priorityIds.has(step.id) && (
        startsForeground(step, actionForStep(step)) || blocksSlotOverlap(step, actionForStep(step))
      ))
      .sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0) || Number(a.slot) - Number(b.slot));
    if (!prioritySteps.length) {
      resolveForegroundConflicts();
      return;
    }
    const priorityMinTick = Math.min(...prioritySteps.map((step) => Number(step.start_tick || 0)));
    const prioritySlots = new Set(prioritySteps
      .filter((step) => blocksSlotOverlap(step, actionForStep(step)))
      .map((step) => Number(step.slot)));
    const preSteps = [];
    const postSteps = [];
    state.axis.steps.forEach((step) => {
      const action = actionForStep(step);
      if (priorityIds.has(step.id) || (!startsForeground(step, action) && !blocksSlotOverlap(step, action))) {
        return;
      }
      const startTick = Number(step.start_tick || 0);
      const endTick = stepEndTick(step, true);
      const mustStayAhead = startTick < priorityMinTick && (
        endTick <= priorityMinTick ||
        isSupportAction(action) ||
        prioritySlots.has(Number(step.slot))
      );
      if (mustStayAhead) {
        preSteps.push(step);
      } else {
        postSteps.push(step);
      }
    });
    preSteps.sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0) || Number(a.slot) - Number(b.slot));
    postSteps.sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0) || Number(a.slot) - Number(b.slot));
    applyForegroundConflictOrder(preSteps.concat(prioritySteps, postSteps));
  }

  function normalizeEditedSteps(priorityStepIds = null) {
    const priorityIds = new Set(priorityStepIds || []);
    if (priorityIds.size) {
      resolveForegroundConflictsWithPriority(priorityIds);
      compactIdleGaps();
      resolveForegroundConflictsWithPriority(priorityIds);
    } else {
      resolveForegroundConflicts();
      compactIdleGaps();
      resolveForegroundConflicts();
    }
    sortSteps();
    updateAxisDuration();
  }

  function actionIntervalAtTick(tick) {
    const target = Math.max(0, Number(tick || 0));
    return (state.axis.steps || [])
      .map((step) => ({
        step,
        action: actionForStep(step),
        start: Number(step.start_tick || 0),
        end: Number(step.start_tick || 0) + actionEditorDurationTicks(actionForStep(step)),
      }))
      .filter((item) => startsForeground(item.step, item.action) && item.start < target && target < item.end)
      .sort((a, b) => b.end - a.end)[0] || null;
  }

  function prepareInsertionTick(tick, action = null) {
    const target = Math.max(0, Number(tick || 0));
    if (isQAction(action) || tickHasForegroundQ(target)) {
      return target;
    }
    const interval = actionIntervalAtTick(tick);
    return interval ? interval.end : target;
  }

  function shiftStepsFromTick(startTick, deltaTicks, exceptStepId = '', includeEqual = true) {
    if (deltaTicks <= 0) {
      return;
    }
    state.axis.steps.forEach((step) => {
      if (step.id === exceptStepId) {
        return;
      }
      const current = Number(step.start_tick || 0);
      if (current > startTick || (includeEqual && current === startTick)) {
        step.start_tick = current + deltaTicks;
      }
    });
  }

  function duplicateStartTick(tick, ignoreStepId = '', actionId = '') {
    const candidateAction = getActionMap().get(actionId) || {};
    const candidateStep = { action_id: actionId };
    if (!startsForeground(candidateStep, candidateAction)) {
      return false;
    }
    if (isQAction(candidateAction) || tickHasForegroundQ(tick, ignoreStepId)) {
      return false;
    }
    return state.axis.steps.some((step) => (
      Number(step.start_tick) === Number(tick) &&
      step.id !== ignoreStepId &&
      startsForeground(step, actionForStep(step))
    ));
  }

  function selectStep(stepId, render = true, additive = false) {
    if (!stepId) {
      setSelectedStepIds([], '', render);
      return;
    }
    if (additive) {
      const ids = selectedStepIds();
      const nextIds = ids.includes(stepId) ? ids.filter((id) => id !== stepId) : ids.concat(stepId);
      setSelectedStepIds(nextIds, nextIds.includes(stepId) ? stepId : nextIds[nextIds.length - 1] || '', render);
      return;
    }
    setSelectedStepIds([stepId], stepId, render);
  }

  function insertionTickForAction() {
    if (state.insertMode === 'after-selected') {
      const step = selectedStep();
      const detail = step ? detailByStepId(step.id) : null;
      if (detail) {
        return Number(detail.visual_end_tick || detail.end_tick || detail.start_tick || 0);
      }
      if (step) {
        const action = actionForStep(step);
        return Number(step.start_tick || 0) + Math.max(1, Number(action.duration_ticks || 0));
      }
    }
    return state.cursorTick;
  }

  function addActionAt(slot, actionId, startTick) {
    const action = getActionMap().get(actionId) || {};
    if (!actionId) {
      setStatus('请选择动作', 'error');
      return;
    }
    pushUndoSnapshot();
    const insertTick = prepareInsertionTick(startTick, action);
    const step = {
      id: `step_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
      slot,
      action_id: actionId,
      action_name: action.name || '',
      start_tick: insertTick,
      repeat: 1,
      tags: [],
    };
    if (startsForeground(step, action) && !isQAction(action) && !tickHasForegroundQ(insertTick)) {
      shiftStepsFromTick(insertTick, actionEditorDurationTicks(action), step.id, true);
    }
    state.axis.steps.push(step);
    normalizeEditedSteps();
    state.cursorTick = Number(step.start_tick || 0) + actionEditorDurationTicks(action);
    const addTime = $('shaft-add-time');
    if (addTime) {
      addTime.value = ticksToSeconds(state.cursorTick);
    }
    selectStep(step.id, false);
    closeContextMenu();
    renderAll();
    scheduleSimulation();
  }

  function addStep() {
    const addSlot = $('shaft-add-slot');
    const addAction = $('shaft-add-action');
    const addTime = $('shaft-add-time');
    if (!addSlot || !addAction || !addTime) {
      return;
    }
    addActionAt(Number(addSlot.value || 0), addAction.value, secondsToTicks(addTime.value));
  }

  function removeStep(stepId) {
    if (!stepId || !state.axis.steps.some((step) => step.id === stepId)) {
      return;
    }
    removeSteps([stepId]);
  }

  function removeSteps(stepIds) {
    const ids = new Set(stepIds || []);
    if (!ids.size || !(state.axis?.steps || []).some((step) => ids.has(step.id))) {
      return;
    }
    pushUndoSnapshot();
    state.axis.steps = state.axis.steps.filter((step) => !ids.has(step.id));
    normalizeEditedSteps();
    state.selectedStepIds = selectedStepIds().filter((id) => !ids.has(id));
    state.selectedStepId = state.selectedStepIds[state.selectedStepIds.length - 1] || state.axis.steps[0]?.id || '';
    syncSelection(Boolean(state.selectedStepId));
    state.cursorTick = Number(selectedStep()?.start_tick || state.cursorTick || 0);
    const addTime = $('shaft-add-time');
    if (addTime) {
      addTime.value = ticksToSeconds(state.cursorTick);
    }
    closeContextMenu();
    renderAll();
    scheduleSimulation();
  }

  function removeSelectedSteps() {
    removeSteps(selectedStepIds());
  }

  function copySelectedSteps() {
    const steps = selectedSteps()
      .sort((a, b) => Number(a.start_tick || 0) - Number(b.start_tick || 0) || Number(a.slot) - Number(b.slot));
    if (!steps.length) {
      return;
    }
    const minTick = Math.min(...steps.map((step) => Number(step.start_tick || 0)));
    state.clipboardSteps = steps.map((step) => Object.assign({}, clone(step), {
      relative_start_tick: Number(step.start_tick || 0) - minTick,
    }));
    renderEditorActions();
    setStatus(`已复制 ${steps.length} 个动作`);
  }

  function pasteStepsAtCursor() {
    if (!state.clipboardSteps.length || !state.axis) {
      return;
    }
    pushUndoSnapshot();
    const baseTick = prepareInsertionTick(state.cursorTick);
    const newIds = [];
    state.clipboardSteps.forEach((source) => {
      const action = getActionMap().get(source.action_id) || {};
      const id = `step_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
      newIds.push(id);
      state.axis.steps.push({
        id,
        slot: Number(source.slot || 0),
        action_id: source.action_id,
        action_name: action.name || source.action_name || '',
        start_tick: baseTick + Number(source.relative_start_tick || 0),
        repeat: Math.max(1, Number(source.repeat || 1)),
        placement: source.placement === 'background' ? 'background' : undefined,
        tags: clone(source.tags || []),
      });
    });
    state.axis.steps.forEach(sanitizeStepPlacement);
    normalizeEditedSteps();
    setSelectedStepIds(newIds.filter((id) => state.axis.steps.some((step) => step.id === id)), newIds[newIds.length - 1] || '', false);
    closeContextMenu();
    renderAll();
    scheduleSimulation();
  }

  function addBuffRule() {
    const triggerSlotSelect = $('shaft-buff-trigger-slot');
    const triggerActionSelect = $('shaft-buff-trigger-action');
    const targetSlotList = $('shaft-buff-target-slots');
    const targetTypeSelect = $('shaft-buff-target-type');
    const modifierKeySelect = $('shaft-buff-modifier-key');
    const modifierValueInput = $('shaft-buff-modifier-value');
    const durationInput = $('shaft-buff-duration');
    if (!triggerSlotSelect || !triggerActionSelect || !targetSlotList || !targetTypeSelect || !modifierKeySelect || !modifierValueInput || !durationInput) {
      return;
    }
    const triggerSlot = Number(triggerSlotSelect.value || 0);
    const triggerActionId = triggerActionSelect.value;
    const triggerAction = getActionMap().get(triggerActionId);
    const targetSlots = Array.from(targetSlotList.querySelectorAll('input:checked')).map((input) => Number(input.value));
    const targetType = targetTypeSelect.value;
    const modifierKey = modifierKeySelect.value;
    const modifierValueRaw = Number(modifierValueInput.value || 0);
    const meta = modifierMeta(modifierKey);
    const modifierValue = meta.percent ? modifierValueRaw / 100 : modifierValueRaw;
    if (!triggerActionId || !modifierValue || targetSlots.length === 0) {
      setStatus('增益参数不完整', 'error');
      return;
    }
    state.axis.buff_rules.push({
      id: `buff_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
      name: `${memberName(triggerSlot)} ${triggerAction?.name || ''}`,
      trigger: { slot: triggerSlot, action_id: triggerActionId, action_type: '' },
      targets: { slots: targetSlots, action_ids: [], action_types: targetType ? [targetType] : [] },
      delay_ticks: 0,
      duration_ticks: secondsToTicks(durationInput.value || 10),
      modifiers: { [modifierKey]: modifierValue },
    });
    renderBuffList();
    scheduleSimulation();
  }

  function handleTeamChange(event) {
    const control = event.target.closest('[data-field]');
    if (!control) {
      return;
    }
    const slot = Number(control.dataset.slot);
    const member = memberBySlot(slot);
    if (!member) {
      return;
    }
    if (control.dataset.field === 'awakening') {
      const level = Math.max(1, Math.min(6, Number(control.dataset.awakeningLevel || 1)));
      member.awakening = control.checked ? level : level - 1;
      rememberMemberBuild(member);
    } else if (control.dataset.field === 'bond_full') {
      member.bond_full = control.checked;
      member.bond_level = control.checked ? 1 : 0;
      rememberMemberBuild(member);
    } else if (control.dataset.field === 'character_id') {
      rememberMemberBuild(member);
      member.character_id = control.value;
      const storedBuild = state.axis.character_builds?.[member.character_id];
      if (storedBuild) {
        applyBuildToMember(member, storedBuild);
      } else {
        updateMemberNames(member);
        rememberMemberBuild(member);
      }
      removeInvalidStepsForSlot(slot);
    } else {
      member[control.dataset.field] = control.value;
      updateMemberNames(member);
      rememberMemberBuild(member);
    }
    renderAll();
    scheduleSimulation();
  }

  function handleSubstatInput(event) {
    const input = event.target.closest('input[data-substat]');
    if (!input) {
      return;
    }
    const member = memberBySlot(Number(input.dataset.slot));
    if (!member) {
      return;
    }
    const count = clampSubstatCount(input.value);
    input.value = count;
    member.substat_counts[input.dataset.substat] = count;
    rememberMemberBuild(member);
    const tile = input.closest('.shaft-substat-tile');
    if (tile) {
      tile.style.setProperty('--count-pct', `${Math.max(0, Math.min(100, (count / 30) * 100))}%`);
    }
    renderBuildPanel();
    scheduleSimulation();
  }

  function handleSkillLevelInput(event) {
    const input = event.target.closest('input[data-skill-level]');
    if (!input) {
      return;
    }
    const member = memberBySlot(Number(input.dataset.slot));
    if (!member) {
      return;
    }
    const key = input.dataset.skillLevel;
    if (!SKILL_LEVEL_FIELDS.some((field) => field.key === key)) {
      return;
    }
    const level = clampSkillLevel(input.value);
    input.value = level;
    member.skill_levels = normalizeSkillLevels(Object.assign({}, member.skill_levels || {}, { [key]: level }));
    rememberMemberBuild(member);
    scheduleSimulation();
  }

  function handleCurtainInput(event) {
    const control = event.target.closest('[data-curtain-field]');
    if (!control) {
      return;
    }
    const member = memberBySlot(Number(control.dataset.slot));
    if (!member) {
      return;
    }
    const field = control.dataset.curtainField;
    const current = normalizeCurtainBonus(member.curtain_bonus, member.character_id);
    let shouldRenderTeam = false;
    if (field === 'value') {
      current.value = Math.max(0, Math.min(100, numberValue(control.value)));
    } else if (field === 'stat') {
      current.stat = normalizeCurtainBonus({ stat: control.value, value: current.value, passive_type: current.passive_type }, member.character_id).stat;
      shouldRenderTeam = true;
    } else if (field === 'passive_type') {
      current.passive_type = CURTAIN_PASSIVE_TYPES.some((item) => item.key === control.value) ? control.value : 'type3';
      shouldRenderTeam = true;
    }
    member.curtain_bonus = normalizeCurtainBonus(current, member.character_id);
    rememberMemberBuild(member);
    if (shouldRenderTeam) {
      renderTeam();
    }
    renderBuildPanel();
    scheduleSimulation();
  }

  function handleTeamBonusInput(event) {
    const input = event.target.closest('input[data-team-bonus]');
    if (!input) {
      return;
    }
    const field = TEAM_PANEL_BONUS_FIELDS.find((item) => item.key === input.dataset.teamBonus);
    if (!field) {
      return;
    }
    const rawValue = numberValue(input.value);
    const storedValue = field.kind === 'percent' ? rawValue / 100 : rawValue;
    state.axis.team_panel_bonus = normalizeTeamPanelBonus(Object.assign(
      {},
      state.axis.team_panel_bonus || {},
      { [field.key]: storedValue },
    ));
    renderBuildPanel();
    scheduleSimulation();
  }

  function handleStepChange(event) {
    const target = event.target.closest('[data-step-field]');
    if (!target) {
      return;
    }
    const step = state.axis.steps.find((item) => item.id === target.dataset.stepId);
    if (!step) {
      return;
    }
    pushUndoSnapshot();
    if (target.dataset.stepField === 'slot') {
      step.slot = Number(target.value || 0);
      const actions = actionsForSlot(step.slot);
      if (!actions.some((action) => action.id === step.action_id)) {
        step.action_id = actions[0]?.id || '';
        step.action_name = getActionMap().get(step.action_id)?.name || '';
      }
      sanitizeStepPlacement(step);
    } else if (target.dataset.stepField === 'action_id') {
      step.action_id = target.value;
      step.action_name = getActionMap().get(step.action_id)?.name || '';
      sanitizeStepPlacement(step);
    } else if (target.dataset.stepField === 'start_tick') {
      const nextTick = secondsToTicks(target.value);
      step.start_tick = nextTick;
      state.cursorTick = nextTick;
    }
    normalizeEditedSteps();
    renderSteps();
    renderTimeline();
    renderStepDetail();
    scheduleSimulation();
  }

  function handleStepClick(event) {
    const removeButton = event.target.closest('[data-remove-step]');
    if (removeButton) {
      removeStep(removeButton.dataset.removeStep);
      return;
    }
    const row = event.target.closest('[data-step-id]');
    if (row) {
      selectStep(row.dataset.stepId, true, event.ctrlKey || event.metaKey);
    }
  }

  function handleBuffClick(event) {
    const button = event.target.closest('[data-remove-buff]');
    if (!button) {
      return;
    }
    state.axis.buff_rules = state.axis.buff_rules.filter((rule) => rule.id !== button.dataset.removeBuff);
    renderBuffList();
    scheduleSimulation();
  }

  function handleBuildPanelClick(event) {
    const button = event.target.closest('[data-build-panel-slot]');
    if (!button) {
      return;
    }
    state.buildPanelSlot = Number(button.dataset.buildPanelSlot || 0);
    renderBuildPanel();
  }

  function timelineVisualOffset(tick) {
    const safeTick = Math.max(0, Number(tick || 0));
    return safeTick * TIMELINE_TICK_PX + (state.timelineScale?.expansionBreaks || [])
      .filter((breakItem) => Number(breakItem.tick) < safeTick)
      .reduce((sum, breakItem) => sum + Number(breakItem.extraPx || 0), 0);
  }

  function tickFromTimelineX(x) {
    const target = Math.max(0, Number(x || 0));
    const maxTick = Math.max(0, Number(state.timelineDurationTicks || TIMELINE_END_PADDING_TICKS));
    let low = 0;
    let high = maxTick;
    while (low < high) {
      const middle = Math.floor((low + high) / 2);
      if (timelineVisualOffset(middle) < target) {
        low = middle + 1;
      } else {
        high = middle;
      }
    }
    if (low <= 0) {
      return 0;
    }
    const previous = low - 1;
    return Math.abs(timelineVisualOffset(low) - target) < Math.abs(target - timelineVisualOffset(previous)) ? low : previous;
  }

  function captureActionRects() {
    const rects = new Map();
    document.querySelectorAll('.shaft-action-bar[data-step-id]').forEach((node) => {
      const rect = node.getBoundingClientRect();
      rects.set(node.dataset.stepId, {
        left: rect.left,
        top: rect.top,
      });
    });
    return rects;
  }

  function animateActionLayout(previousRects) {
    if (!previousRects || previousRects.size === 0) {
      return;
    }
    document.querySelectorAll('.shaft-action-bar[data-step-id]').forEach((node) => {
      const previous = previousRects.get(node.dataset.stepId);
      if (!previous) {
        return;
      }
      const rect = node.getBoundingClientRect();
      const dx = previous.left - rect.left;
      const dy = previous.top - rect.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) {
        return;
      }
      node.style.transition = 'none';
      node.style.transform = `translate(${dx}px, ${dy}px)`;
      node.getBoundingClientRect();
      window.requestAnimationFrame(() => {
        node.style.transition = 'transform 150ms cubic-bezier(.2,.8,.2,1), box-shadow 150ms ease, opacity 150ms ease';
        node.style.transform = 'translate(0, 0)';
        window.setTimeout(() => {
          node.style.transition = '';
          node.style.transform = '';
        }, 180);
      });
      });
  }

  function selectionBoxFromPoints(startX, startY, currentX, currentY) {
    return {
      left: Math.min(startX, currentX),
      top: Math.min(startY, currentY),
      right: Math.max(startX, currentX),
      bottom: Math.max(startY, currentY),
      width: Math.abs(currentX - startX),
      height: Math.abs(currentY - startY),
    };
  }

  function rectsIntersect(a, b) {
    return a.left <= b.right && a.right >= b.left && a.top <= b.bottom && a.bottom >= b.top;
  }

  function marqueeElement() {
    let node = document.querySelector('.shaft-selection-marquee');
    if (!node) {
      node = document.createElement('div');
      node.className = 'shaft-selection-marquee';
      document.body.appendChild(node);
    }
    return node;
  }

  function updateMarqueeElement(rect) {
    const node = marqueeElement();
    node.style.left = `${rect.left}px`;
    node.style.top = `${rect.top}px`;
    node.style.width = `${rect.width}px`;
    node.style.height = `${rect.height}px`;
  }

  function removeMarqueeElement() {
    document.querySelector('.shaft-selection-marquee')?.remove();
  }

  function selectActionsInMarquee(rect, additive, baseIds) {
    const ids = additive ? (baseIds || []).slice() : [];
    document.querySelectorAll('.shaft-action-bar[data-step-id]').forEach((node) => {
      const barRect = node.getBoundingClientRect();
      if (rectsIntersect(rect, barRect) && !ids.includes(node.dataset.stepId)) {
        ids.push(node.dataset.stepId);
      }
    });
    setSelectedStepIds(ids, ids[ids.length - 1] || '', false);
    renderStepDetail();
    renderEditorActions();
  }

  function placementForDrag(step, action, originalPlacement, deltaY) {
    if (!canBackgroundOverride(action) || isBackgroundAction(action)) {
      return 'foreground';
    }
    if (deltaY > BACKGROUND_DRAG_THRESHOLD_PX) {
      return 'background';
    }
    if (deltaY < -BACKGROUND_DRAG_THRESHOLD_PX) {
      return 'foreground';
    }
    return originalPlacement === 'background' ? 'background' : 'foreground';
  }

  function applyDraggedPlacement(step, drag, deltaY) {
    const action = actionForStep(step);
    const originalPlacement = drag.originPlacements?.[step.id] || 'foreground';
    const nextPlacement = placementForDrag(step, action, originalPlacement, deltaY);
    if (nextPlacement === 'background') {
      step.placement = 'background';
    } else {
      delete step.placement;
    }
    return nextPlacement !== originalPlacement;
  }

  function dragPlacementWouldChange(drag, deltaY) {
    return (drag.stepIds || [drag.stepId]).some((stepId) => {
      const step = (drag.snapshot.steps || []).find((item) => item.id === stepId);
      if (!step) {
        return false;
      }
      const action = getActionMap().get(step.action_id) || {};
      const originalPlacement = drag.originPlacements?.[stepId] || 'foreground';
      return placementForDrag(step, action, originalPlacement, deltaY) !== originalPlacement;
    });
  }

  function updateSelectionClasses() {
    const selectedIds = new Set(selectedStepIds());
    document.querySelectorAll('.shaft-action-bar[data-step-id]').forEach((node) => {
      node.classList.toggle('selected', selectedIds.has(node.dataset.stepId));
    });
    document.querySelectorAll('.shaft-step-row[data-step-id]').forEach((node) => {
      node.classList.toggle('selected', selectedIds.has(node.dataset.stepId));
    });
  }

  function timelineTickFromEvent(event) {
    const timeline = $('shaft-timeline');
    const rect = timeline.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left - TIMELINE_LABEL_PX));
    return tickFromTimelineX(x);
  }

  function slotFromTimelineEvent(event) {
    const track = event.target.closest('.action-track[data-slot]');
    return track ? Number(track.dataset.slot || 0) : Number(state.librarySlot || 0);
  }

  function closeContextMenu() {
    const menu = $('shaft-context-menu');
    if (!menu) {
      return;
    }
    menu.hidden = true;
    menu.innerHTML = '';
  }

  function showContextMenu(left, top, html) {
    const menu = $('shaft-context-menu');
    if (!menu) {
      return;
    }
    menu.innerHTML = html;
    menu.hidden = false;
    const rect = menu.getBoundingClientRect();
    menu.style.left = `${Math.min(left, window.innerWidth - rect.width - 12)}px`;
    menu.style.top = `${Math.min(top, window.innerHeight - rect.height - 12)}px`;
  }

  function actionContextMenuHtml(slot, tick) {
    const actions = actionsForSlot(slot);
    return `
      <div class="shaft-context-head">
        <strong>${escapeHtml(memberName(slot))}</strong>
        <span>${ticksToSeconds(tick)}s</span>
      </div>
      <div class="shaft-context-actions">
        ${actions.map((action) => `
          <button type="button" data-context-add-action="${escapeHtml(action.id)}" data-context-slot="${slot}" data-context-tick="${tick}">
            <b>${escapeHtml(action.action_type || '动作')}</b>
            <span>${escapeHtml(action.name)}</span>
            <em>${ticksToSeconds(action.duration_ticks)}s</em>
          </button>
        `).join('') || '<div class="shaft-empty">没有动作</div>'}
      </div>
    `;
  }

  function removeContextMenuHtml(stepId) {
    const step = state.axis.steps.find((item) => item.id === stepId);
    const action = actionForStep(step);
    return `
      <div class="shaft-context-head">
        <strong>${escapeHtml(action.name || '动作')}</strong>
        <span>${ticksToSeconds(step?.start_tick || 0)}s</span>
      </div>
      <button class="shaft-context-danger" type="button" data-context-remove-step="${escapeHtml(stepId)}">移除动作</button>
    `;
  }

  function handleTimelineClick(event) {
    if (Date.now() < state.suppressTimelineClickUntil) {
      return;
    }
    closeContextMenu();
    const bar = event.target.closest('[data-step-id]');
    if (bar) {
      selectStep(bar.dataset.stepId, true, event.ctrlKey || event.metaKey);
      return;
    }
    state.cursorTick = timelineTickFromEvent(event);
    const addTime = $('shaft-add-time');
    if (addTime) {
      addTime.value = ticksToSeconds(state.cursorTick);
    }
    renderTimeline();
    renderStepDetail();
    renderEditorActions();
  }

  function handleTimelineContextMenu(event) {
    event.preventDefault();
    const bar = event.target.closest('.shaft-action-bar[data-step-id]');
    if (bar) {
      selectStep(bar.dataset.stepId);
      showContextMenu(event.clientX, event.clientY, removeContextMenuHtml(bar.dataset.stepId));
      return;
    }
    const tick = timelineTickFromEvent(event);
    const slot = slotFromTimelineEvent(event);
    state.cursorTick = tick;
    state.librarySlot = slot;
    const addSlot = $('shaft-add-slot');
    const addTime = $('shaft-add-time');
    if (addSlot) {
      addSlot.value = String(slot);
    }
    if (addTime) {
      addTime.value = ticksToSeconds(tick);
    }
    renderTeamDock();
    renderActionAdder();
    renderCommandLibrary();
    renderTimeline();
    showContextMenu(event.clientX, event.clientY, actionContextMenuHtml(slot, tick));
  }

  function handleContextMenuClick(event) {
    const addButton = event.target.closest('[data-context-add-action]');
    if (addButton) {
      addActionAt(
        Number(addButton.dataset.contextSlot || state.librarySlot || 0),
        addButton.dataset.contextAddAction,
        Number(addButton.dataset.contextTick || state.cursorTick || 0),
      );
      return;
    }
    const removeButton = event.target.closest('[data-context-remove-step]');
    if (removeButton) {
      removeStep(removeButton.dataset.contextRemoveStep);
    }
  }

  function isEditableTarget(target) {
    return Boolean(target?.closest?.('input, textarea, select, [contenteditable="true"]'));
  }

  function handleKeydown(event) {
    if (event.key === 'Escape') {
      closeContextMenu();
      return;
    }
    if (isEditableTarget(event.target)) {
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
      event.preventDefault();
      if (event.shiftKey) {
        redoLastEdit();
      } else {
        undoLastEdit();
      }
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
      event.preventDefault();
      redoLastEdit();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'c') {
      event.preventDefault();
      copySelectedSteps();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'v') {
      event.preventDefault();
      state.suppressClipboardPasteUntil = Date.now() + 250;
      pasteStepsAtCursor();
      return;
    }
    if ((event.key === 'Delete' || event.key === 'Backspace') && selectedStepIds().length) {
      event.preventDefault();
      removeSelectedSteps();
    }
  }

  function handleClipboardCopy(event) {
    if (isEditableTarget(event.target) || !selectedStepIds().length) {
      return;
    }
    event.preventDefault();
    copySelectedSteps();
    try {
      event.clipboardData?.setData('text/plain', `异环动作轴 ${selectedStepIds().length} 个动作`);
    } catch (error) {
      // The in-page clipboard is only a convenience; internal copy state is enough for pasting.
    }
  }

  function handleClipboardPaste(event) {
    if (isEditableTarget(event.target) || !state.clipboardSteps.length) {
      return;
    }
    event.preventDefault();
    if (Date.now() < state.suppressClipboardPasteUntil) {
      return;
    }
    pasteStepsAtCursor();
  }

  function handleTimelineMouseDown(event) {
    const bar = event.target.closest('.shaft-action-bar[data-step-id]');
    if (event.button !== 0) {
      return;
    }
    if (!bar) {
      if (!event.target.closest('#shaft-timeline')) {
        return;
      }
      state.marqueeState = {
        originX: event.clientX,
        originY: event.clientY,
        currentX: event.clientX,
        currentY: event.clientY,
        baseIds: selectedStepIds(),
        additive: event.ctrlKey || event.metaKey,
        moved: false,
      };
      event.preventDefault();
      return;
    }
    const step = state.axis.steps.find((item) => item.id === bar.dataset.stepId);
    if (!step) {
      return;
    }
    if (event.ctrlKey || event.metaKey) {
      selectStep(step.id, true, true);
      state.suppressTimelineClickUntil = Date.now() + 250;
      event.preventDefault();
      return;
    }
    const domSelectedIds = Array.from(document.querySelectorAll('.shaft-action-bar.selected[data-step-id]'))
      .map((node) => node.dataset.stepId)
      .filter(Boolean);
    const activeIds = Array.from(new Set(selectedStepIds().concat(domSelectedIds)));
    if (!activeIds.includes(step.id)) {
      selectStep(step.id);
    } else {
      setSelectedStepIds(activeIds, step.id, false);
      renderStepDetail();
      renderEditorActions();
    }
    const dragStepIds = activeIds.includes(step.id) ? activeIds : [step.id];
    const originTicks = {};
    const originPlacements = {};
    (state.axis.steps || []).forEach((item) => {
      if (dragStepIds.includes(item.id)) {
        originTicks[item.id] = Number(item.start_tick || 0);
        originPlacements[item.id] = item.placement === 'background' ? 'background' : 'foreground';
      }
    });
    state.dragState = {
      stepId: step.id,
      stepIds: dragStepIds,
      originX: event.clientX,
      originY: event.clientY,
      originTick: Number(step.start_tick || 0),
      originTicks,
      originPlacements,
      snapshot: editorSnapshot(),
      previewTick: Number(step.start_tick || 0),
      moved: false,
    };
    document.body.classList.add('shaft-dragging');
    event.preventDefault();
  }

  function handleTimelineMouseMove(event) {
    const marquee = state.marqueeState;
    if (marquee) {
      const rect = selectionBoxFromPoints(marquee.originX, marquee.originY, event.clientX, event.clientY);
      if (rect.width > 3 || rect.height > 3) {
        marquee.moved = true;
        marquee.currentX = event.clientX;
        marquee.currentY = event.clientY;
        updateMarqueeElement(rect);
        selectActionsInMarquee(rect, marquee.additive, marquee.baseIds);
      }
      return;
    }
    const drag = state.dragState;
    if (!drag) {
      return;
    }
    const nextTick = Math.max(0, tickFromTimelineX(timelineVisualOffset(drag.originTick) + event.clientX - drag.originX));
    const deltaY = event.clientY - Number(drag.originY || event.clientY);
    const placementChanged = dragPlacementWouldChange(drag, deltaY);
    if (nextTick === Number(drag.previewTick || 0) && !placementChanged) {
      return;
    }
    const previousRects = captureActionRects();
    state.axis.steps = clone(drag.snapshot.steps || []);
    state.selectedStepIds = clone(drag.stepIds || [drag.stepId]);
    state.selectedStepId = drag.stepId;
    const movedSteps = state.axis.steps.filter((item) => (drag.stepIds || [drag.stepId]).includes(item.id));
    if (!movedSteps.length) {
      return;
    }
    drag.moved = true;
    drag.previewTick = nextTick;
    const deltaTicks = nextTick - Number(drag.originTick || 0);
    const minOriginTick = Math.min(...Object.values(drag.originTicks || { [drag.stepId]: drag.originTick }).map(Number));
    const safeDeltaTicks = Math.max(deltaTicks, -minOriginTick);
    movedSteps.forEach((item) => {
      item.start_tick = Math.max(0, Number(drag.originTicks?.[item.id] ?? item.start_tick ?? 0) + safeDeltaTicks);
      applyDraggedPlacement(item, drag, deltaY);
    });
    normalizeEditedSteps(new Set(drag.stepIds || [drag.stepId]));
    syncSelection(false);
    const normalizedStep = state.axis.steps.find((item) => item.id === drag.stepId);
    state.cursorTick = Number(normalizedStep?.start_tick ?? nextTick);
    const addTime = $('shaft-add-time');
    if (addTime) {
      addTime.value = ticksToSeconds(state.cursorTick);
    }
    renderSteps();
    renderTimeline();
    animateActionLayout(previousRects);
    renderStepDetail();
    renderEditorActions();
  }

  function handleTimelineMouseUp() {
    const marquee = state.marqueeState;
    if (marquee) {
      state.marqueeState = null;
      removeMarqueeElement();
      if (marquee.moved) {
        state.suppressTimelineClickUntil = Date.now() + 250;
      }
      return;
    }
    const drag = state.dragState;
    if (!drag) {
      return;
    }
    state.dragState = null;
    document.body.classList.remove('shaft-dragging');
    if (!drag.moved) {
      return;
    }
    const stepIds = drag.stepIds || [drag.stepId];
    const movedSteps = state.axis.steps.filter((item) => stepIds.includes(item.id));
    if (movedSteps.length) {
      state.undoStack.push(drag.snapshot);
      if (state.undoStack.length > 80) {
        state.undoStack.shift();
      }
      state.redoStack = [];
      normalizeEditedSteps(new Set(stepIds));
      syncSelection(false);
      const primary = state.axis.steps.find((item) => item.id === drag.stepId) || movedSteps[0];
      state.cursorTick = Number(primary?.start_tick || 0);
      state.suppressTimelineClickUntil = Date.now() + 250;
      renderSteps();
      renderTimeline();
      renderStepDetail();
      renderEditorActions();
      scheduleSimulation();
    }
  }

  function handleTeamDockClick(event) {
    const card = event.target.closest('[data-dock-slot]');
    if (!card) {
      return;
    }
    state.librarySlot = Number(card.dataset.dockSlot || 0);
    renderTeamDock();
    renderActionAdder();
    renderCommandLibrary();
  }

  function handleLibraryClick(event) {
    const button = event.target.closest('[data-library-action]');
    if (!button) {
      return;
    }
    addActionAt(Number(button.dataset.librarySlot || state.librarySlot), button.dataset.libraryAction, insertionTickForAction());
  }

  function reflowSteps() {
    pushUndoSnapshot();
    let tick = 0;
    sortSteps();
    for (const step of state.axis.steps) {
      step.start_tick = tick;
      const action = actionForStep(step);
      tick += Math.max(1, Number(action.duration_ticks || 0));
    }
    state.cursorTick = tick;
    normalizeEditedSteps();
    renderAll();
    scheduleSimulation();
  }

  async function runSimulation() {
    window.clearTimeout(state.simulationTimer);
    if (!Array.isArray(state.axis?.steps) || !state.axis.steps.length) {
      state.result = {
        ok: true,
        summary: {
          duration_ticks: 0,
          duration_seconds: 0,
          direct_damage: 0,
          stagger_damage: 0,
          total_damage: 0,
          dps: 0,
          team_energy: 0,
          total_harmony: 0,
        },
        damage_by_slot: [],
        resources_by_slot: [],
        build_panels_by_slot: currentBuildPanels(),
        details: [],
        front_windows: [],
        enemy: state.axis?.enemy || {},
      };
      renderResults();
      renderSteps();
      renderTimeline();
      renderStepDetail();
      renderEditorActions();
      persistAxisDraft();
      setStatus('待排轴');
      return;
    }
    try {
      setStatus('计算中');
      const payload = await shaftRequest('/api/shaft/simulate', {
        method: 'POST',
        body: JSON.stringify(state.axis),
      });
      state.axis = payload.axis;
      state.result = payload.result;
      ensureAxisShape();
      renderTeamDock();
      renderResults();
      renderSteps();
      renderTimeline();
      renderStepDetail();
      renderEditorActions();
      persistAxisDraft();
      setStatus('已计算');
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  function scheduleSimulation() {
    window.clearTimeout(state.simulationTimer);
    persistAxisDraft();
    state.simulationTimer = window.setTimeout(runSimulation, 320);
  }

  function resetAxis() {
    state.axis = emptyAxisFromCatalog();
    state.result = null;
    state.savedAxisId = null;
    state.cursorTick = 0;
    state.selectedStepId = '';
    state.undoStack = [];
    state.redoStack = [];
    $('shaft-title-input').value = '未命名排轴';
    $('shaft-description-input').value = '';
    ensureAxisShape();
    renderAll();
    persistAxisDraft();
    runSimulation();
  }

  async function saveAxis(visibility) {
    if (!getToken()) {
      persistAxisDraft();
      redirectToLogin();
      return;
    }
    const payload = {
      title: $('shaft-title-input').value || '未命名排轴',
      description: $('shaft-description-input').value || '',
      visibility,
      axis: state.axis,
    };
    try {
      setStatus(visibility === 'public' ? '上传中' : '保存中');
      const url = state.savedAxisId ? `/api/shaft/axes/${state.savedAxisId}` : '/api/shaft/axes';
      const method = state.savedAxisId ? 'PUT' : 'POST';
      const saved = await shaftRequest(url, { method, body: JSON.stringify(payload) }, { authRequired: true });
      state.savedAxisId = saved.id;
      state.axis = saved.axis;
      state.result = saved.result;
      ensureAxisShape();
      renderAll();
      persistAxisDraft();
      setStatus(visibility === 'public' ? '已上传' : '已保存');
      await loadMarket(true);
      await loadMyAxes();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  async function loadMarket(reset) {
    if (reset) {
      state.marketPage = 1;
      state.marketItems = [];
    }
    const params = new URLSearchParams({
      character_id: $('shaft-market-character-filter').value || '',
      sort: $('shaft-market-sort').value || 'dps',
      page: String(state.marketPage),
      page_size: '12',
    });
    try {
      const payload = await shaftRequest(`/api/shaft/market?${params.toString()}`);
      state.marketItems = reset ? payload.items : state.marketItems.concat(payload.items || []);
      state.marketHasMore = Boolean(payload.has_more);
      if (state.marketHasMore) {
        state.marketPage = Number(payload.page || state.marketPage) + 1;
      }
      renderMarketList();
    } catch (error) {
      $('shaft-market-list').innerHTML = `<div class="shaft-empty">${escapeHtml(error.message)}</div>`;
    }
  }

  async function loadMyAxes() {
    if (!getToken()) {
      $('shaft-my-axis-list').innerHTML = '<div class="shaft-empty">登录后显示</div>';
      return;
    }
    try {
      const payload = await shaftRequest('/api/shaft/me/axes');
      $('shaft-my-axis-list').innerHTML = (payload.items || []).map((axis) => marketCardHtml(axis, true)).join('') || '<div class="shaft-empty">暂无保存排轴</div>';
    } catch (error) {
      if (String(error.message || '').includes('未登录') || String(error.message || '').includes('token')) {
        clearToken();
        renderLoginState();
        $('shaft-my-axis-list').innerHTML = '<div class="shaft-empty">登录后显示</div>';
        return;
      }
      $('shaft-my-axis-list').innerHTML = `<div class="shaft-empty">${escapeHtml(error.message)}</div>`;
    }
  }

  async function loadAxis(axisId, source) {
    try {
      setStatus('读取排轴');
      const payload = await shaftRequest(`/api/shaft/axes/${axisId}`);
      state.axis = payload.axis;
      state.result = payload.result;
      state.savedAxisId = source === 'mine' ? payload.id : null;
      state.selectedStepId = '';
      state.undoStack = [];
      state.redoStack = [];
      $('shaft-title-input').value = payload.title || '未命名排轴';
      $('shaft-description-input').value = payload.description || '';
      ensureAxisShape();
      renderAll();
      setPage('rotation');
      persistAxisDraft();
      setStatus('已读取');
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  async function deleteAxis(axisId, title) {
    if (!getToken()) {
      persistAxisDraft();
      redirectToLogin();
      return;
    }
    const label = title ? `「${title}」` : `#${axisId}`;
    if (!window.confirm(`确定删除排轴 ${label} 吗？删除后无法恢复。`)) {
      return;
    }
    try {
      setStatus('删除中');
      await shaftRequest(`/api/shaft/axes/${axisId}`, { method: 'DELETE' }, { authRequired: true });
      if (Number(state.savedAxisId || 0) === Number(axisId)) {
        state.savedAxisId = null;
        persistAxisDraft();
      }
      await loadMyAxes();
      await loadMarket(true);
      setStatus('已删除');
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  async function toggleLike(axisId, active) {
    try {
      await shaftRequest(`/api/shaft/axes/${axisId}/like`, { method: active ? 'DELETE' : 'POST' }, { authRequired: true });
      await loadMarket(true);
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  async function toggleFavorite(axisId, active) {
    try {
      await shaftRequest(`/api/shaft/axes/${axisId}/favorite`, { method: active ? 'DELETE' : 'POST' });
      await loadMarket(true);
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  async function handleMarketClick(event) {
    const deleteButton = event.target.closest('[data-delete-axis]');
    if (deleteButton) {
      event.stopPropagation();
      await deleteAxis(Number(deleteButton.dataset.deleteAxis), deleteButton.dataset.axisTitle || '');
      return;
    }
    const likeButton = event.target.closest('[data-like-axis]');
    if (likeButton) {
      event.stopPropagation();
      if (!getToken()) {
        persistAxisDraft();
        redirectToLogin();
        return;
      }
      await toggleLike(Number(likeButton.dataset.likeAxis), likeButton.classList.contains('active'));
      return;
    }
    const favoriteButton = event.target.closest('[data-favorite-axis]');
    if (favoriteButton) {
      event.stopPropagation();
      await toggleFavorite(Number(favoriteButton.dataset.favoriteAxis), favoriteButton.classList.contains('active'));
      return;
    }
    const card = event.target.closest('[data-axis-id]');
    if (card) {
      await loadAxis(Number(card.dataset.axisId), card.dataset.axisSource);
    }
  }

  function bindEvents() {
    document.querySelectorAll('[data-shaft-page-link]').forEach((link) => {
      link.addEventListener('click', (event) => {
        event.preventDefault();
        setPage(link.dataset.shaftPageLink);
      });
    });
    $('shaft-run-btn').addEventListener('click', runSimulation);
    $('shaft-reset-btn').addEventListener('click', resetAxis);
    $('shaft-save-btn').addEventListener('click', () => saveAxis('private'));
    $('shaft-publish-btn').addEventListener('click', () => saveAxis('public'));
    $('shaft-title-input').addEventListener('input', persistAxisDraft);
    $('shaft-description-input').addEventListener('input', persistAxisDraft);
    $('shaft-undo-btn').addEventListener('click', undoLastEdit);
    $('shaft-redo-btn').addEventListener('click', redoLastEdit);
    $('shaft-copy-step-btn').addEventListener('click', copySelectedSteps);
    $('shaft-paste-step-btn').addEventListener('click', pasteStepsAtCursor);
    $('shaft-delete-step-btn').addEventListener('click', removeSelectedSteps);
    $('shaft-reflow-btn').addEventListener('click', reflowSteps);
    $('shaft-loop-enabled').addEventListener('change', (event) => {
      state.axis.options.loop_enabled = event.target.checked;
      renderEditorActions();
      scheduleSimulation();
    });
    $('shaft-library-slot').addEventListener('change', (event) => {
      state.librarySlot = Number(event.target.value || 0);
      renderTeamDock();
      renderActionAdder();
      renderCommandLibrary();
    });
    $('shaft-command-search').addEventListener('input', (event) => {
      state.commandSearch = event.target.value || '';
      renderCommandLibrary();
    });
    $('shaft-command-type-tabs').addEventListener('click', (event) => {
      const button = event.target.closest('[data-command-type]');
      if (!button) {
        return;
      }
      state.commandTypeFilter = button.dataset.commandType || '';
      renderCommandTypes();
      renderCommandLibrary();
    });
    $('shaft-team-dock').addEventListener('click', handleTeamDockClick);
    $('shaft-command-list').addEventListener('click', handleLibraryClick);
    $('shaft-market-refresh-btn').addEventListener('click', () => loadMarket(true));
    $('shaft-market-more-btn').addEventListener('click', () => loadMarket(false));
    $('shaft-my-refresh-btn').addEventListener('click', loadMyAxes);
    $('shaft-market-character-filter').addEventListener('change', () => loadMarket(true));
    $('shaft-market-sort').addEventListener('change', () => loadMarket(true));
    const addBuffButton = $('shaft-add-buff-btn');
    if (addBuffButton) {
      addBuffButton.addEventListener('click', addBuffRule);
    }
    const buffTriggerSlot = $('shaft-buff-trigger-slot');
    if (buffTriggerSlot) {
      buffTriggerSlot.addEventListener('change', (event) => {
        state.buffDraft.triggerSlot = Number(event.target.value || 0);
        renderBuffEditor();
      });
    }
    const buffModifierKey = $('shaft-buff-modifier-key');
    if (buffModifierKey) {
      buffModifierKey.addEventListener('change', (event) => {
        state.buffDraft.modifierKey = event.target.value;
      });
    }
    $('shaft-enemy-level').addEventListener('input', (event) => {
      state.axis.enemy.level = Number(event.target.value || 90);
      scheduleSimulation();
    });
    $('shaft-enemy-track-outside').addEventListener('change', (event) => {
      state.axis.enemy.track_outside = event.target.checked;
      scheduleSimulation();
    });
    $('shaft-team-bonus-grid').addEventListener('input', handleTeamBonusInput);
    $('shaft-team-bonus-grid').addEventListener('change', (event) => {
      handleTeamBonusInput(event);
      renderTeamBonus();
    });
    $('shaft-weakness-row').addEventListener('change', () => {
      state.axis.enemy.weakness_elements = Array.from($('shaft-weakness-row').querySelectorAll('input:checked')).map((input) => input.value);
      scheduleSimulation();
    });
    $('shaft-team-slots').addEventListener('change', handleTeamChange);
    $('shaft-team-slots').addEventListener('change', handleCurtainInput);
    $('shaft-team-slots').addEventListener('input', handleSubstatInput);
    $('shaft-team-slots').addEventListener('input', handleSkillLevelInput);
    $('shaft-team-slots').addEventListener('input', handleCurtainInput);
    const buildPanel = $('shaft-build-panel');
    if (buildPanel) {
      buildPanel.addEventListener('click', handleBuildPanelClick);
    }
    if ($('shaft-step-list')) {
      $('shaft-step-list').addEventListener('change', handleStepChange);
      $('shaft-step-list').addEventListener('input', handleStepChange);
      $('shaft-step-list').addEventListener('click', handleStepClick);
    }
    $('shaft-timeline').addEventListener('click', handleTimelineClick);
    $('shaft-timeline').addEventListener('contextmenu', handleTimelineContextMenu);
    $('shaft-timeline').addEventListener('mousedown', handleTimelineMouseDown);
    $('shaft-context-menu').addEventListener('click', handleContextMenuClick);
    document.addEventListener('click', (event) => {
      if (!event.target.closest('#shaft-context-menu')) {
        closeContextMenu();
      }
    });
    document.addEventListener('keydown', handleKeydown);
    document.addEventListener('copy', handleClipboardCopy);
    document.addEventListener('paste', handleClipboardPaste);
    window.addEventListener('mousemove', handleTimelineMouseMove);
    window.addEventListener('mouseup', handleTimelineMouseUp);
    const buffList = $('shaft-buff-list');
    if (buffList) {
      buffList.addEventListener('click', handleBuffClick);
    }
    $('shaft-market-list').addEventListener('click', handleMarketClick);
    $('shaft-my-axis-list').addEventListener('click', handleMarketClick);
  }

  async function init() {
    const active = document.querySelector('.shaft-page')?.dataset.activePage || 'rotation';
    state.page = active;
    window.NTE_BEFORE_LOGIN_REDIRECT = persistAxisDraft;
    bindEvents();
    try {
      state.catalog = await shaftRequest('/api/shaft/catalog');
      if (!restoreAxisDraft(active)) {
        state.axis = emptyAxisFromCatalog();
      }
      ensureAxisShape();
      $('shaft-data-version').textContent = displayText(state.catalog.source_meta.version_label || '');
      renderAll();
      await runSimulation();
      await loadMarket(true);
      await loadMyAxes();
    } catch (error) {
      setStatus(error.message, 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', init);
}());
