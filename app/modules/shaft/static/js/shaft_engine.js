(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ShaftEngine = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const ELEMENTS = ['光', '灵', '咒', '暗', '魂', '相'];
  const ZERO_ACTION_VISUAL_TICKS = 5;
  const MIN_FOREGROUND_START_GAP_TICKS = 2;
  const ENEMY_DEBUFF_DURATIONS = {
    '延滞': 50,
    '黯星': 50,
    '浸染': 120,
    '覆纹': 120,
    '浊燃': 150,
  };
  const TEAM_PANEL_BONUS_DEFAULTS = {
    version: 3,
    furniture_crit_dmg: 0.04,
    furniture_flat_atk: 20,
    furniture_flat_def: 30,
    small_flat_atk: 420,
    small_flat_hp: 5200,
  };
  const SKILL_LEVEL_DEFAULTS = {
    basic: 10,
    skill: 10,
    ultimate: 10,
    support: 10,
  };
  const SUBSTAT_EFFECT_KEYS = {
    all_dmg: 'all_dmg',
    crit_rate: 'crit_rate',
    crit_dmg: 'crit_dmg',
    harmony_strength: 'harmony_strength',
    stagger_strength: 'stagger_strength',
    atk_pct: 'atk_pct',
    flat_atk: 'flat_atk',
    hp_pct: 'hp_pct',
    flat_hp: 'flat_hp',
    def_pct: 'def_pct',
    flat_def: 'flat_def',
  };
  const CURTAIN_PASSIVE_TYPES = ['type2', 'type3', 'type4'];
  const SUPPORTED_TRIGGER_EVENTS = new Set(['action_start', 'action_hit', 'action_end', 'loop_start']);
  const SPECIAL_DAMAGE_SOURCES = ['创生', '浊燃', '黯星'];

  function clone(value) {
    return JSON.parse(JSON.stringify(value ?? null));
  }

  function num(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function int(value, fallback = 0) {
    return Math.round(num(value, fallback));
  }

  function asList(value) {
    return Array.isArray(value) ? value : [];
  }

  function strSet(value) {
    return new Set(asList(value).map((item) => String(item)).filter(Boolean));
  }

  function recordMap(records) {
    return new Map(asList(records).map((record) => [String(record?.id || ''), record]));
  }

  function mods() {
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
      dodge_counter_dmg: 0,
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

  function mergeMods(base, delta, factor = 1) {
    if (!delta || typeof delta !== 'object') {
      return base;
    }
    Object.entries(delta).forEach(([key, value]) => {
      if (Object.prototype.hasOwnProperty.call(base, key)) {
        base[key] += num(value) * factor;
      }
    });
    return base;
  }

  function normalizeStatName(value) {
    const text = String(value || '').trim();
    return text === '环合强度' ? '精通' : text;
  }

  function defaultBuildOptions(characterId, constants) {
    const defaults = constants?.default_build_options && typeof constants.default_build_options === 'object'
      ? constants.default_build_options
      : {};
    return defaults[characterId] && typeof defaults[characterId] === 'object' ? defaults[characterId] : {};
  }

  function normalizeTeamPanelBonus(raw, catalog) {
    const starterBonus = catalog?.starter_axis?.team_panel_bonus || {};
    const defaults = Object.assign({}, TEAM_PANEL_BONUS_DEFAULTS, starterBonus);
    const source = raw && typeof raw === 'object' ? raw : {};
    const bonus = {};
    Object.keys(defaults).forEach((key) => {
      bonus[key] = num(source[key], num(defaults[key]));
    });
    const version = int(source.version);
    if (version < 2 && bonus.furniture_flat_atk === 20 && bonus.small_flat_atk === 440) {
      bonus.small_flat_atk = 420;
    }
    if (version < TEAM_PANEL_BONUS_DEFAULTS.version) {
      bonus.furniture_crit_dmg = TEAM_PANEL_BONUS_DEFAULTS.furniture_crit_dmg;
      bonus.furniture_flat_atk = TEAM_PANEL_BONUS_DEFAULTS.furniture_flat_atk;
      bonus.furniture_flat_def = TEAM_PANEL_BONUS_DEFAULTS.furniture_flat_def;
    } else {
      bonus.furniture_crit_dmg = Math.round(Math.max(0, Math.min(TEAM_PANEL_BONUS_DEFAULTS.furniture_crit_dmg, bonus.furniture_crit_dmg)) * 1000) / 1000;
      bonus.furniture_flat_atk = Math.round(Math.max(0, Math.min(TEAM_PANEL_BONUS_DEFAULTS.furniture_flat_atk, bonus.furniture_flat_atk)));
      bonus.furniture_flat_def = Math.round(Math.max(0, Math.min(TEAM_PANEL_BONUS_DEFAULTS.furniture_flat_def, bonus.furniture_flat_def)));
    }
    bonus.version = TEAM_PANEL_BONUS_DEFAULTS.version;
    return bonus;
  }

  function teamPanelBonusMods(raw, catalog) {
    const bonus = normalizeTeamPanelBonus(raw, catalog);
    const out = mods();
    out.crit_dmg += bonus.furniture_crit_dmg;
    out.flat_atk += bonus.furniture_flat_atk + bonus.small_flat_atk;
    out.flat_def += bonus.furniture_flat_def;
    out.flat_hp += bonus.small_flat_hp;
    return out;
  }

  function substatMods(counts, constants) {
    const out = mods();
    const units = constants?.substat_units || {};
    Object.entries(SUBSTAT_EFFECT_KEYS).forEach(([key, effectKey]) => {
      const unit = units[key] || {};
      out[effectKey] += Math.max(0, num(counts?.[key])) * num(unit.unit_value);
    });
    return out;
  }

  function cartridgeMainStat(member, constants) {
    const characterId = String(member?.character_id || '');
    const options = constants?.cartridge_main_stat_options || {};
    const defaults = defaultBuildOptions(characterId, constants);
    const fallback = normalizeStatName(defaults.cartridge_main_stat) || Object.keys(options)[0] || '';
    const selected = normalizeStatName(member?.cartridge_main_stat) || fallback;
    return Object.prototype.hasOwnProperty.call(options, selected) ? selected : fallback;
  }

  function curtainBonus(member, constants) {
    const characterId = String(member?.character_id || '');
    const defaults = defaultBuildOptions(characterId, constants).curtain_bonus || {};
    const source = member?.curtain_bonus && typeof member.curtain_bonus === 'object' ? member.curtain_bonus : {};
    const options = constants?.curtain_bonus_stat_options || {};
    const fallback = normalizeStatName(defaults.stat) || Object.keys(options)[0] || '';
    const stat = normalizeStatName(source.stat) || fallback;
    const passiveType = CURTAIN_PASSIVE_TYPES.includes(String(source.passive_type || ''))
      ? String(source.passive_type)
      : (CURTAIN_PASSIVE_TYPES.includes(String(defaults.passive_type || '')) ? String(defaults.passive_type) : 'type3');
    return {
      value: Math.max(0, Math.min(100, num(source.value, num(defaults.value)))),
      stat: Object.prototype.hasOwnProperty.call(options, stat) ? stat : fallback,
      passive_type: passiveType,
    };
  }

  function cartridgePassiveLayers(cartridge, passiveType) {
    const type = CURTAIN_PASSIVE_TYPES.includes(passiveType) ? passiveType : 'type3';
    return Math.max(0, int(cartridge?.passive_counts?.[type]));
  }

  function mainStatMods(mainStat, constants) {
    const out = mods();
    const option = constants?.cartridge_main_stat_options?.[mainStat] || {};
    const key = String(option.modifier_key || '');
    if (Object.prototype.hasOwnProperty.call(out, key)) {
      out[key] += num(option.unit_value);
    }
    return out;
  }

  function curtainBonusMods(bonus, cartridge, constants) {
    const out = mods();
    const option = constants?.curtain_bonus_stat_options?.[normalizeStatName(bonus.stat)] || {};
    const key = String(option.modifier_key || '');
    const layers = cartridgePassiveLayers(cartridge, String(bonus.passive_type || 'type3'));
    if (Object.prototype.hasOwnProperty.call(out, key)) {
      out[key] += num(bonus.value) / 100 * layers;
    }
    return { modifiers: out, layers };
  }

  function skillLevels(raw) {
    const source = raw && typeof raw === 'object' ? raw : {};
    return Object.fromEntries(Object.entries(SKILL_LEVEL_DEFAULTS).map(([key, value]) => [
      key,
      Math.max(1, Math.min(10, int(source[key], value))),
    ]));
  }

  function skillLevelBonus(member) {
    return int(member?.awakening) >= 3 ? 1 : 0;
  }

  function skillLevelCategory(action) {
    const actionType = String(action?.action_type || '');
    const damageType = String(action?.damage_type || '');
    if (damageType === '无' || damageType === '' || actionType === '无') {
      return '';
    }
    if (actionType === '普攻' || damageType === '普攻' || actionType === '闪反' || actionType === '下落' || damageType === '闪反' || damageType === '下落') {
      return 'basic';
    }
    if (actionType === 'E' || damageType === 'E') {
      return 'skill';
    }
    if (actionType === 'Q' || damageType === 'Q') {
      return 'ultimate';
    }
    if (actionType === '援护' || damageType === '援护') {
      return 'support';
    }
    return '';
  }

  function skillLevelMultiplier(snapshot, action) {
    const category = skillLevelCategory(action);
    if (!category) {
      return { category: '', level: 0, multiplier: 1 };
    }
    const levels = snapshot.skill_levels || {};
    const baseLevel = Math.max(1, int(levels[category], SKILL_LEVEL_DEFAULTS[category]));
    const effectiveLevel = Math.max(1, baseLevel + int(snapshot.skill_level_bonus));
    return {
      category,
      level: effectiveLevel,
      multiplier: Math.pow(1.08, effectiveLevel - 1),
    };
  }

  function actionTypeBonus(action, panelMods) {
    const actionType = String(action?.action_type || '');
    const damageType = String(action?.damage_type || '');
    const extraTag = String(action?.extra_tag || '');
    let total = panelMods.all_dmg;
    if (actionType === '普攻' || damageType === '普攻') total += panelMods.basic_dmg;
    if (actionType === '闪反' || damageType === '闪反') total += panelMods.dodge_counter_dmg;
    if (actionType === 'E' || damageType === 'E') total += panelMods.skill_dmg;
    if (actionType === 'Q' || damageType === 'Q') total += panelMods.ultimate_dmg;
    if (extraTag === '追击') total += panelMods.follow_dmg;
    if (extraTag === '心灵') total += panelMods.mind_dmg;
    if (extraTag === '附着') total += panelMods.attach_dmg;
    return total;
  }

  function buildSnapshot(member, catalog, teamPanelBonus) {
    const characters = recordMap(catalog.characters);
    const arcs = recordMap(catalog.arcs);
    const cartridges = recordMap(catalog.cartridges);
    const constants = catalog.formula_constants || {};
    const character = characters.get(String(member?.character_id || ''));
    if (!character) {
      throw new Error('队伍中存在未知角色。');
    }
    const arc = arcs.get(String(member?.arc_id || '')) || null;
    const cartridge = cartridges.get(String(member?.cartridge_id || '')) || null;
    const panelMods = mods();
    const mainStat = cartridgeMainStat(member, constants);
    const bonus = curtainBonus(member, constants);
    const curtain = curtainBonusMods(bonus, cartridge, constants);
    mergeMods(panelMods, character.modifiers);
    if (member?.bond_full || int(member?.bond_level) > 0) {
      mergeMods(panelMods, character.bond_bonus?.modifiers);
    }
    if (arc) mergeMods(panelMods, arc.modifiers);
    if (cartridge) mergeMods(panelMods, cartridge.modifiers);
    mergeMods(panelMods, mainStatMods(mainStat, constants));
    mergeMods(panelMods, curtain.modifiers);
    mergeMods(panelMods, substatMods(member?.substat_counts || {}, constants));
    mergeMods(panelMods, teamPanelBonusMods(teamPanelBonus, catalog));
    const element = String(character.element || '');
    panelMods.element_dmg += num(arc?.element_dmg?.[element]);
    const baseStats = character.base_stats || {};
    const baseAtk = num(baseStats.atk) + num(arc?.base_atk);
    const baseHp = num(baseStats.hp);
    const baseDef = num(baseStats.def);
    const stats = {
      atk: baseAtk * (1 + panelMods.atk_pct) + panelMods.flat_atk,
      hp: baseHp * (1 + panelMods.hp_pct) + panelMods.flat_hp,
      def: baseDef * (1 + panelMods.def_pct) + panelMods.flat_def,
      harmony_strength: panelMods.harmony_strength,
      stagger_strength: panelMods.stagger_strength,
      crit_rate: panelMods.crit_rate,
      crit_dmg: panelMods.crit_dmg,
    };
    return {
      slot: int(member?.slot),
      character,
      arc,
      cartridge,
      mods: panelMods,
      base_stats: { atk: baseAtk, hp: baseHp, def: baseDef },
      stats,
      skill_levels: skillLevels(member?.skill_levels),
      skill_level_bonus: skillLevelBonus(member),
      build_options: {
        cartridge_main_stat: mainStat,
        curtain_bonus: {
          value: num(bonus.value),
          stat: bonus.stat || '',
          passive_type: bonus.passive_type || 'type3',
          layers: curtain.layers,
        },
      },
      personal_resources: {},
    };
  }

  function buildPanelProjection(snapshot) {
    const character = snapshot.character || {};
    const panelMods = snapshot.mods || {};
    const baseStats = snapshot.base_stats || {};
    const stats = snapshot.stats || {};
    return {
      slot: int(snapshot.slot),
      character_id: character.id || '',
      character_name: character.name || '',
      base_stats: {
        atk: num(baseStats.atk),
        hp: num(baseStats.hp),
        def: num(baseStats.def),
      },
      zones: {
        atk_pct: num(panelMods.atk_pct),
        flat_atk: num(panelMods.flat_atk),
        hp_pct: num(panelMods.hp_pct),
        flat_hp: num(panelMods.flat_hp),
        def_pct: num(panelMods.def_pct),
        flat_def: num(panelMods.flat_def),
      },
      panel: {
        atk: num(stats.atk),
        hp: num(stats.hp),
        def: num(stats.def),
        crit_rate: num(stats.crit_rate),
        crit_dmg: num(stats.crit_dmg),
        element_dmg: num(panelMods.element_dmg),
        energy_recharge: num(panelMods.energy_recharge),
        harmony_strength: num(stats.harmony_strength),
        stagger_strength: num(stats.stagger_strength),
        all_dmg: num(panelMods.all_dmg),
      },
      build_options: snapshot.build_options || {},
    };
  }

  function normalizeEnemy(raw) {
    const enemy = raw && typeof raw === 'object' ? raw : {};
    const weakness = Array.isArray(enemy.weakness_elements) ? enemy.weakness_elements : [];
    const debuffs = enemy.debuffs && typeof enemy.debuffs === 'object' ? enemy.debuffs : {};
    const hpRatio = enemy.hp_ratio == null && enemy.hp_percent != null ? num(enemy.hp_percent, 100) / 100 : num(enemy.hp_ratio, 1);
    return {
      level: Math.max(1, Math.min(120, int(enemy.level, 90))),
      track_outside: Boolean(enemy.track_outside),
      weakness_elements: weakness.map(String).filter((item) => ELEMENTS.includes(item)),
      debuffs: Object.fromEntries(Object.entries(debuffs)
        .filter(([name]) => Object.prototype.hasOwnProperty.call(ENEMY_DEBUFF_DURATIONS, name))
        .map(([name, endTick]) => [name, Math.max(0, int(endTick))])),
      hp_ratio: Math.max(0, Math.min(1, hpRatio)),
    };
  }

  function resistanceMultiplier(character, enemy, panelMods) {
    const baseRes = 0.3;
    const element = String(character?.element || '');
    const weaknessDown = new Set(enemy.weakness_elements || []).has(element) ? 0.2 : 0;
    const value = 1 - baseRes + weaknessDown + panelMods.res_down;
    if (value < 1) {
      return Math.max(0.05, value);
    }
    return Math.max(0.05, 2 - 1 / Math.max(value, 0.01));
  }

  function defenseMultiplier(enemy, panelMods) {
    const actorLevelFactor = 6 * 80 + 600;
    const enemyFactor = 6 * int(enemy.level, 90) + 600 - (enemy.track_outside ? 60 : 0);
    const defenseLeft = enemyFactor * Math.max(0, 1 - Math.min(1, panelMods.def_ignore)) * Math.max(0, 1 - Math.min(1, panelMods.def_down));
    return actorLevelFactor / Math.max(actorLevelFactor + defenseLeft, 1);
  }

  function critMultiplier(action, panelMods) {
    const rate = String(action?.extra_tag || '') === 'DOT' ? 0.5 : Math.min(1, Math.max(0, panelMods.crit_rate));
    return Math.max(1, 1 + rate * Math.max(0, panelMods.crit_dmg));
  }

  function calculateActionDamage(snapshot, action, enemy, extraModifiers) {
    const panelMods = mergeMods(clone(snapshot.mods), extraModifiers);
    mergeMods(panelMods, action.self_modifiers);
    const baseStats = snapshot.base_stats || {};
    const stats = {
      atk: num(baseStats.atk) * (1 + panelMods.atk_pct) + panelMods.flat_atk,
      hp: num(baseStats.hp) * (1 + panelMods.hp_pct) + panelMods.flat_hp,
      def: num(baseStats.def) * (1 + panelMods.def_pct) + panelMods.flat_def,
      harmony_strength: panelMods.harmony_strength,
      stagger_strength: panelMods.stagger_strength,
      crit_rate: panelMods.crit_rate,
      crit_dmg: panelMods.crit_dmg,
    };
    const multipliers = action.multipliers || {};
    const scalingBase = stats.atk * num(multipliers.atk) + stats.hp * num(multipliers.hp) + stats.def * num(multipliers.def);
    const skill = skillLevelMultiplier(snapshot, action);
    let base = scalingBase * skill.multiplier + num(multipliers.flat);
    let skillCategory = skill.category;
    let skillLevel = skill.level;
    let skillMult = skill.multiplier;
    if (['无', ''].includes(String(action.damage_type || ''))) {
      base = 0;
      skillCategory = '';
      skillLevel = 0;
      skillMult = 1;
    }
    const dmgBonus = actionTypeBonus(action, panelMods) + panelMods.element_dmg;
    const crit = critMultiplier(action, panelMods);
    const resistance = resistanceMultiplier(snapshot.character, enemy, panelMods);
    const defense = defenseMultiplier(enemy, panelMods);
    const direct = Math.max(0, base * (1 + dmgBonus) * crit * resistance * defense * (1 + panelMods.final_dmg));
    return {
      direct_damage: direct,
      stagger_amount: Math.max(0, num(action.stagger) * (1 + panelMods.stagger_strength / 300)),
      harmony: num(action.harmony),
      energy_gain: num(action.energy_gain) * (1 + panelMods.energy_recharge),
      panel: {
        atk: stats.atk,
        hp: stats.hp,
        def: stats.def,
        harmony_strength: stats.harmony_strength,
        stagger_strength: stats.stagger_strength,
        crit_rate: stats.crit_rate,
        crit_dmg: stats.crit_dmg,
      },
      formula_parts: {
        base,
        raw_base: scalingBase + num(multipliers.flat),
        skill_level_category: skillCategory,
        skill_level: skillLevel,
        skill_level_multiplier: skillMult,
        dmg_bonus: dmgBonus,
        crit,
        resistance,
        defense,
      },
    };
  }

  function actionTags(action) {
    const tags = new Set(asList(action?.tags).map(String).filter(Boolean));
    const extraTag = String(action?.extra_tag || '');
    if (extraTag) tags.add(extraTag);
    return tags;
  }

  function specialDamageSource(action) {
    const explicitSource = String(action?.damage_source || '').trim();
    if (SPECIAL_DAMAGE_SOURCES.includes(explicitSource)) return explicitSource;
    const actionName = String(action?.name || '');
    return SPECIAL_DAMAGE_SOURCES.find((source) => actionName.includes(source)) || '';
  }

  function isBackgroundAction(action) {
    return Boolean(action?.is_background_damage) || `${action?.name || ''} ${action?.extra_tag || ''}`.includes('后台');
  }

  function isBasicAction(action) {
    return String(action?.action_type || '') === '普攻' || String(action?.damage_type || '') === '普攻';
  }

  function canBackgroundOverride(action) {
    return Boolean(action?.can_background_override) && isBasicAction(action);
  }

  function isBasicBackgroundOverride(step, action) {
    return !isBackgroundAction(action) && canBackgroundOverride(action) && String(step?.placement || '') === 'background';
  }

  function isStepBackground(step, action) {
    return isBackgroundAction(action) || isBasicBackgroundOverride(step, action);
  }

  function startsForeground(step, action) {
    return !isStepBackground(step, action);
  }

  function blocksSlotOverlap(step, action) {
    return startsForeground(step, action) || isBasicBackgroundOverride(step, action);
  }

  function isSupportAction(action) {
    return String(action?.action_type || '') === '援护';
  }

  function isQAction(action) {
    return String(action?.action_type || '') === 'Q' || String(action?.damage_type || '') === 'Q';
  }

  function supportProtectedStepEntries(steps, actionsById) {
    const ordered = steps.slice().sort((a, b) => {
      const startDelta = int(a.start_tick) - int(b.start_tick);
      if (startDelta) return startDelta;
      const aSupport = isSupportAction(actionsById.get(String(a.action_id || '')) || {});
      const bSupport = isSupportAction(actionsById.get(String(b.action_id || '')) || {});
      return Number(bSupport) - Number(aSupport) || int(a.slot) - int(b.slot);
    });
    let supportExclusiveUntil = 0;
    return ordered.map((step) => {
      const action = actionsById.get(String(step.action_id || '')) || {};
      const isBackground = isStepBackground(step, action);
      let visualStartTick = int(step.start_tick);
      if (!isBackground && visualStartTick < supportExclusiveUntil) {
        visualStartTick = supportExclusiveUntil;
      }
      if (!isBackground && isSupportAction(action)) {
        supportExclusiveUntil = Math.max(
          supportExclusiveUntil,
          visualStartTick + Math.max(1, Math.max(0, int(action.duration_ticks))),
        );
      }
      return { step, visualStartTick };
    });
  }

  function qVisualDurationTicks(action) {
    return Math.max(ZERO_ACTION_VISUAL_TICKS, Math.max(0, int(action?.duration_ticks)));
  }

  function isZeroForegroundQStep(step, action) {
    return startsForeground(step, action) && isQAction(action) && Math.max(0, int(action?.duration_ticks)) === 0;
  }

  function isQCoverImmuneScheduled(scheduled) {
    const action = scheduled?.action || {};
    return isSupportAction(action) || isZeroForegroundQStep(scheduled?.step || {}, action);
  }

  function qVirtualStartTicks(steps, actionsById) {
    return steps
      .map((step, order) => ({ step, order, action: actionsById.get(String(step?.action_id || '')) }))
      .filter((item) => item.action && isZeroForegroundQStep(item.step, item.action))
      .map((item) => ({ tick: int(item.step.start_tick), order: item.order }))
      .sort((a, b) => a.tick - b.tick || a.order - b.order)
      .map((item) => item.tick);
  }

  function calculationTickFromVisual(visualTick, qStarts) {
    const safeTick = Math.max(0, int(visualTick));
    let offset = 0;
    qStarts.forEach((qStartTick) => {
      if (qStartTick < safeTick) {
        offset += Math.min(ZERO_ACTION_VISUAL_TICKS, safeTick - qStartTick);
      }
    });
    return Math.max(0, safeTick - offset);
  }

  function calculationTickFromVisualIntervals(visualTick, qIntervals) {
    const safeTick = Math.max(0, int(visualTick));
    let offset = 0;
    asList(qIntervals).forEach((interval) => {
      const startTick = Math.max(0, int(interval?.start_tick));
      const endTick = Math.max(startTick, int(interval?.end_tick, startTick + ZERO_ACTION_VISUAL_TICKS));
      if (startTick < safeTick) {
        offset += Math.min(endTick - startTick, safeTick - startTick);
      }
    });
    return Math.max(0, safeTick - offset);
  }

  function recalculateUnreleasedTimings(scheduledSteps, qIntervals) {
    scheduledSteps.forEach((scheduled) => {
      if (scheduled.q_instant_release) return;
      const startTick = calculationTickFromVisualIntervals(
        int(scheduled.visual_start_tick, int(scheduled.step?.start_tick)),
        qIntervals,
      );
      const durationTicks = Math.max(0, int(scheduled.original_duration_ticks, int(scheduled.duration_ticks)));
      scheduled.start_tick = startTick;
      scheduled.end_tick = startTick + durationTicks;
      scheduled.duration_ticks = durationTicks;
      scheduled.calculation_start_sequence = 0;
      scheduled.calculation_end_sequence = 0;
    });
  }

  function calculateAxisDurationTicks(steps, actionsById) {
    const qStarts = qVirtualStartTicks(steps, actionsById);
    return Math.max(0, ...asList(steps).map((step) => {
      const action = actionsById.get(String(step?.action_id || '')) || {};
      const startTick = calculationTickFromVisual(int(step?.start_tick), qStarts);
      return Math.max(startTick, startTick + Math.max(0, int(action.duration_ticks)));
    }));
  }

  function actionHitCount(action) {
    return Math.max(0, int(action?.hit_count));
  }

  function actionEnemyDebuffs(action) {
    const out = new Set();
    actionTags(action).forEach((tag) => {
      if (tag.startsWith('enemy_debuff:')) {
        const name = tag.split(':')[1];
        if (Object.prototype.hasOwnProperty.call(ENEMY_DEBUFF_DURATIONS, name)) out.add(name);
      } else if (Object.prototype.hasOwnProperty.call(ENEMY_DEBUFF_DURATIONS, tag)) {
        out.add(tag);
      }
    });
    return out;
  }

  function activeEnemyDebuffs(enemyDebuffs, tick) {
    return Object.fromEntries(Object.entries(enemyDebuffs || {}).filter(([, endTick]) => tick < int(endTick)));
  }

  function applyEnemyDebuffs(enemyDebuffs, action, tick) {
    const applied = [];
    Array.from(actionEnemyDebuffs(action)).sort().forEach((name) => {
      enemyDebuffs[name] = Math.max(int(enemyDebuffs[name]), tick + ENEMY_DEBUFF_DURATIONS[name]);
      applied.push(name);
    });
    return applied;
  }

  function expectedCriticalHits(action, calc) {
    const hitCount = actionHitCount(action);
    if (hitCount <= 0) return 0;
    const panel = calc.panel || {};
    const rate = String(action.extra_tag || '') === 'DOT' ? 0.5 : Math.min(1, Math.max(0, num(panel.crit_rate)));
    return hitCount * rate;
  }

  function validateSteps(steps, actionsById) {
    asList(steps).forEach((step) => {
      const action = actionsById.get(String(step.action_id || ''));
      if (!action) throw new Error('轴中存在未知动作。');
    });
  }

  function placement(isBackground) {
    return isBackground ? 'background' : 'foreground';
  }

  function sourceMatches(source, rule, step, action, snapshot, isBackground) {
    const scope = String(source?.scope || 'registrar');
    if (scope === 'registrar' && int(step.slot) !== int(rule.owner_slot)) return false;
    if (scope === 'non_registrar' && int(step.slot) === int(rule.owner_slot)) return false;
    const actionTypes = strSet(source?.action_types);
    if (actionTypes.size && !actionTypes.has(String(action.action_type || ''))) return false;
    const damageTypes = strSet(source?.damage_types);
    if (damageTypes.size && !damageTypes.has(String(action.damage_type || ''))) return false;
    const actionNames = strSet(source?.action_names);
    if (actionNames.size && !actionNames.has(String(action.name || ''))) return false;
    const actionIds = strSet(source?.action_ids);
    if (actionIds.size && !actionIds.has(String(action.id || ''))) return false;
    const tags = strSet(source?.tags);
    if (tags.size && !Array.from(actionTags(action)).some((tag) => tags.has(tag))) return false;
    const placements = strSet(source?.placements);
    if (placements.size && !placements.has(placement(isBackground))) return false;
    const elements = strSet(source?.elements);
    if (elements.size && !elements.has(String(snapshot.character?.element || ''))) return false;
    return true;
  }

  function conditionsMatch(conditions, context) {
    return asList(conditions).every((condition) => {
      if (!condition || typeof condition !== 'object') return false;
      const type = String(condition.type || '');
      if (type === '' || type === 'always') return true;
      const tags = new Set(asList(context.action_tags).map(String));
      if (type === 'unsupported') return false;
      if (type === 'action_tag') return Array.from(strSet(condition.tags)).some((tag) => tags.has(tag));
      if (type === 'self_hp_loss') return ['self_hp_loss', 'hp_loss', '扣血', '降低生命'].some((tag) => tags.has(tag));
      if (type === 'heal') return ['heal', '治疗'].some((tag) => tags.has(tag));
      if (type === 'fons_full') return context.fons_full !== false;
      if (type === 'awakening_min') return int(context.owner_awakening) >= int(condition.min, int(condition.value));
      if (type === 'expected_critical_hit') return num(context.expected_critical_hits) > 0;
      if (type === 'hit_count_positive') return num(context.hit_count) > 0;
      if (type === 'enemy_debuff_active') {
        const active = Object.entries(context.enemy_debuffs || {}).filter(([, value]) => num(value) > num(context.tick)).map(([key]) => key);
        return Array.from(strSet(condition.debuffs)).some((name) => active.includes(name));
      }
      if (type === 'enemy_debuff_applied') {
        const applied = new Set(asList(context.applied_enemy_debuffs).map(String));
        return Array.from(strSet(condition.debuffs)).some((name) => applied.has(name));
      }
      if (type === 'shield_state') return Boolean(context.shield_active);
      if (type === 'take_damage') return Boolean(context.take_damage);
      if (type === 'enemy_hp_below') return num(context.enemy?.hp_ratio, num(context.enemy?.hp_percent, 100) / 100) < num(condition.threshold, 0.5);
      if (type === 'enemy_weak_to_owner_element') {
        const element = String(context.snapshot?.character?.element || '');
        return new Set(context.enemy?.weakness_elements || []).has(element);
      }
      return false;
    });
  }

  function registeredBuffRules(team, catalog) {
    const buffs = asList(catalog.buffs);
    const characters = recordMap(catalog.characters);
    const arcs = recordMap(catalog.arcs);
    const cartridges = recordMap(catalog.cartridges);
    const rules = [];
    buffs.forEach((buff) => {
      asList(buff?.providers).forEach((provider) => {
        asList(team).forEach((member) => {
          const kind = String(provider?.kind || '');
          const providerId = String(provider?.id || '');
          const selectedId = kind === 'arc'
            ? String(member.arc_id || '')
            : (kind === 'cartridge' ? String(member.cartridge_id || '') : (kind === 'character' ? String(member.character_id || '') : ''));
          if (!providerId || providerId !== selectedId) return;
          const rule = clone(buff);
          rule.owner_slot = int(member.slot);
          rule.owner_character_id = String(member.character_id || '');
          rule.owner_character_name = String(member.character_name || '');
          rule.owner_awakening = int(member.awakening);
          if (kind === 'arc') rule.provider_name = arcs.get(providerId)?.name || '';
          if (kind === 'cartridge') rule.provider_name = cartridges.get(providerId)?.name || '';
          if (kind === 'character') rule.provider_name = characters.get(providerId)?.name || rule.owner_character_name;
          rule.provider_kind = kind;
          rules.push(rule);
        });
      });
    });
    return rules.sort((a, b) => int(a.priority, 100) - int(b.priority, 100) || String(a.id || '').localeCompare(String(b.id || '')) || int(a.owner_slot) - int(b.owner_slot));
  }

  function legacyBuffRules(rawRules) {
    return asList(rawRules).map((rawRule, index) => {
      if (!rawRule || typeof rawRule !== 'object') return null;
      const trigger = rawRule.trigger && typeof rawRule.trigger === 'object' ? rawRule.trigger : {};
      const targets = rawRule.targets && typeof rawRule.targets === 'object' ? rawRule.targets : {};
      const modifiers = rawRule.modifiers && typeof rawRule.modifiers === 'object' ? rawRule.modifiers : {};
      const durationTicks = Math.max(0, int(rawRule.duration_ticks));
      if (!Object.keys(modifiers).length || durationTicks <= 0) return null;
      const triggerSlot = trigger.slot;
      const hasTriggerSlot = triggerSlot != null && triggerSlot !== '';
      const targetSlots = asList(targets.slots).map(int);
      const effects = Object.fromEntries(Object.entries(modifiers).filter(([, value]) => num(value) !== 0).map(([key, value]) => [key, num(value)]));
      if (!Object.keys(effects).length) return null;
      return {
        id: String(rawRule.id || `legacy_buff_${String(index + 1).padStart(3, '0')}`),
        name: String(rawRule.name || `增益 ${index + 1}`),
        provider_kind: 'legacy',
        provider_name: '手动增益',
        owner_slot: hasTriggerSlot ? int(triggerSlot) : -1,
        priority: 10000 + index,
        trigger: {
          event: 'action_hit',
          source: {
            scope: hasTriggerSlot ? 'registrar' : 'team',
            action_ids: trigger.action_id ? [String(trigger.action_id)] : [],
            action_types: trigger.action_type ? [String(trigger.action_type)] : [],
          },
        },
        target: {
          scope: targetSlots.length ? 'slots' : 'team',
          slots: targetSlots,
          action_ids: asList(targets.action_ids).map(String),
          action_types: asList(targets.action_types).map(String),
        },
        duration: { type: 'time', ticks: durationTicks, delay_ticks: Math.max(0, int(rawRule.delay_ticks)), loop_carry: false },
        stacking: { mode: 'refresh', max_stacks: 1 },
        effects,
      };
    }).filter(Boolean);
  }

  function eventMatchesRule(rule, event, step, action, snapshot, isBackground, context = {}) {
    const trigger = rule.trigger && typeof rule.trigger === 'object' ? rule.trigger : {};
    if (String(trigger.event || '') !== event || !SUPPORTED_TRIGGER_EVENTS.has(event)) return false;
    const source = trigger.source && typeof trigger.source === 'object' ? trigger.source : {};
    if (!sourceMatches(source, rule, step, action, snapshot, isBackground)) return false;
    const eventContext = Object.assign({}, context, {
      snapshot,
      owner_awakening: rule.owner_awakening,
    });
    return conditionsMatch(trigger.conditions, eventContext);
  }

  function targetMatches(target, instance, step, action, snapshot, isBackground) {
    const scope = String(target?.scope || 'registrar');
    const ownerSlot = int(instance.owner_slot);
    const stepSlot = int(step.slot);
    if (scope === 'registrar' && stepSlot !== ownerSlot) return false;
    if (scope === 'team') {
      // fall through
    } else if (scope === 'other_team' && stepSlot === ownerSlot) return false;
    else if (scope === 'front' && isBackground) return false;
    else if (scope === 'front_non_registrar' && (isBackground || stepSlot === ownerSlot)) return false;
    else if (scope === 'front_registrar' && (isBackground || stepSlot !== ownerSlot)) return false;
    else if (scope === 'slots') {
      const slots = new Set(asList(target.slots).map(int));
      if (slots.size && !slots.has(stepSlot)) return false;
    }
    const actionTypes = strSet(target?.action_types);
    if (actionTypes.size && !actionTypes.has(String(action.action_type || ''))) return false;
    const actionIds = strSet(target?.action_ids);
    if (actionIds.size && !actionIds.has(String(action.id || ''))) return false;
    const damageTypes = strSet(target?.damage_types);
    if (damageTypes.size && !damageTypes.has(String(action.damage_type || ''))) return false;
    const actionNames = strSet(target?.action_names);
    if (actionNames.size && !actionNames.has(String(action.name || ''))) return false;
    const tags = strSet(target?.tags);
    if (tags.size && !Array.from(actionTags(action)).some((tag) => tags.has(tag))) return false;
    const placements = strSet(target?.placements);
    if (placements.size && !placements.has(placement(isBackground))) return false;
    const elements = strSet(target?.elements);
    if (elements.size && !elements.has(String(snapshot.character?.element || ''))) return false;
    return true;
  }

  function activeBuffResetsOnActionStart(instance, step, action, isBackground) {
    const rule = instance.rule && typeof instance.rule === 'object' ? instance.rule : {};
    const reset = rule.reset && typeof rule.reset === 'object' ? rule.reset : {};
    if (!reset || isBackground) return false;
    const ownerSlot = int(instance.owner_slot);
    const stepSlot = int(step.slot);
    if (reset.owner_foreground && stepSlot === ownerSlot) return true;
    if (reset.owner_leaves_foreground && stepSlot !== ownerSlot) return true;
    if (strSet(reset.action_ids).has(String(action.id || ''))) return true;
    if (strSet(reset.action_names).has(String(action.name || ''))) return true;
    if (strSet(reset.action_types).has(String(action.action_type || ''))) return true;
    return false;
  }

  function triggerCooldownTicks(rule) {
    return Math.max(0, int(rule?.trigger?.cooldown_ticks));
  }

  function stackGainForRule(rule, context = {}) {
    const stacking = rule.stacking && typeof rule.stacking === 'object' ? rule.stacking : {};
    if (stacking.stack_gain != null && stacking.stack_gain !== '') return Math.max(0, num(stacking.stack_gain, 1));
    for (const condition of asList(rule.trigger?.conditions)) {
      if (condition && typeof condition === 'object' && String(condition.type || '') === 'expected_critical_hit') {
        return Math.max(0, num(context.expected_critical_hits));
      }
    }
    return 1;
  }

  function activateBuff(activeBuffs, rule, triggerTick, stackGain = 1) {
    const duration = rule.duration && typeof rule.duration === 'object' ? rule.duration : {};
    const durationTicks = Math.max(0, int(duration.ticks));
    if (durationTicks <= 0) return null;
    const startTick = triggerTick + Math.max(0, int(duration.delay_ticks));
    const endTick = startTick + durationTicks;
    const stacking = rule.stacking && typeof rule.stacking === 'object' ? rule.stacking : {};
    const mode = String(stacking.mode || 'refresh');
    const maxStacks = Math.max(1, num(stacking.max_stacks, 1));
    const gain = Math.max(0, stackGain);
    if (gain <= 0) return null;
    const definitionId = String(rule.id || '');
    const ownerSlot = int(rule.owner_slot);
    for (const instance of activeBuffs) {
      const existingRule = instance.rule && typeof instance.rule === 'object' ? instance.rule : {};
      if (String(existingRule.id || '') !== definitionId || int(instance.owner_slot) !== ownerSlot) continue;
      if (mode === 'independent') continue;
      if (mode === 'add_stack') {
        instance.stack_count = Math.min(maxStacks, Math.max(0, num(instance.stack_count, 1)) + gain);
        instance.start_tick = Math.min(int(instance.start_tick, startTick), startTick);
        instance.end_tick = endTick;
        return instance;
      }
      if (mode === 'extend') {
        instance.end_tick = Math.max(int(instance.end_tick), endTick);
        return instance;
      }
      instance.start_tick = startTick;
      instance.end_tick = endTick;
      instance.stack_count = Math.min(maxStacks, Math.max(1, gain));
      return instance;
    }
    const instance = {
      rule,
      definition_id: definitionId,
      name: rule.name || '',
      owner_slot: ownerSlot,
      start_tick: startTick,
      end_tick: endTick,
      stack_count: Math.min(maxStacks, mode === 'add_stack' ? gain : Math.max(1, gain)),
    };
    activeBuffs.push(instance);
    return instance;
  }

  function buffEffects(instance) {
    const effects = instance.rule?.effects && typeof instance.rule.effects === 'object' ? instance.rule.effects : {};
    const factor = Math.max(0, num(instance.stack_count, 1));
    return Object.fromEntries(Object.entries(effects).filter(([, value]) => num(value) !== 0).map(([key, value]) => [key, num(value) * factor]));
  }

  function buffDisplaysAsLine(rule) {
    const display = rule.display && typeof rule.display === 'object' ? rule.display : {};
    if (display.line === false) return false;
    if (display.line === true) return true;
    const duration = rule.duration && typeof rule.duration === 'object' ? rule.duration : {};
    const target = rule.target && typeof rule.target === 'object' ? rule.target : {};
    const scope = String(target.scope || 'registrar');
    if ((scope === 'registrar' || scope === 'front_registrar') && Math.max(0, int(duration.ticks)) <= 1 && Math.max(0, int(duration.delay_ticks)) <= 0) {
      return false;
    }
    return true;
  }

  function buffSummary(instance) {
    const rule = instance.rule && typeof instance.rule === 'object' ? instance.rule : {};
    const stackCount = Math.max(0, num(instance.stack_count, 1));
    const displayAsLine = buffDisplaysAsLine(rule);
    return {
      rule_id: rule.id || '',
      name: rule.name || '',
      provider_name: rule.provider_name || '',
      owner_slot: int(instance.owner_slot),
      start_tick: int(instance.start_tick),
      end_tick: int(instance.end_tick),
      stack_count: Number.isInteger(stackCount) ? Math.trunc(stackCount) : stackCount,
      display_as_line: displayAsLine,
      line_hidden_reason: displayAsLine ? '' : 'self_action',
    };
  }

  function activeBuffApplies(instance, step, action, snapshot, isBackground) {
    const target = instance.rule?.target && typeof instance.rule.target === 'object' ? instance.rule.target : {};
    return targetMatches(target, instance, step, action, snapshot, isBackground);
  }

  function markQInstantReleaseTarget(scheduled, qVisualStartTick, qCalculationStartTick, qStepId, releaseKind, startSequence, endSequence, collapseToQTick = false) {
    const startTick = int(scheduled.start_tick);
    const durationTicks = Math.max(0, int(scheduled.duration_ticks));
    const endTick = int(scheduled.end_tick);
    const visualEndTick = int(scheduled.visual_end_tick, endTick);
    scheduled.original_duration_ticks ??= durationTicks;
    scheduled.original_end_tick ??= endTick;
    scheduled.original_visual_end_tick ??= visualEndTick;
    scheduled.original_start_tick ??= startTick;
    scheduled.original_calculation_start_sequence ??= int(scheduled.calculation_start_sequence);
    scheduled.original_calculation_end_sequence ??= int(scheduled.calculation_end_sequence);
    const visualStartTick = int(scheduled.visual_start_tick, startTick);
    const originalVisualEndTick = Math.max(visualStartTick, int(scheduled.original_visual_end_tick, visualEndTick));
    const releaseStartTick = collapseToQTick ? qCalculationStartTick : startTick;
    const releaseEndTick = Math.max(releaseStartTick, qCalculationStartTick);
    scheduled.start_tick = releaseStartTick;
    scheduled.end_tick = releaseEndTick;
    scheduled.duration_ticks = Math.max(0, releaseEndTick - releaseStartTick);
    scheduled.calculation_start_sequence = Math.max(0, int(startSequence));
    scheduled.calculation_end_sequence = Math.max(scheduled.calculation_start_sequence + 1, int(endSequence));
    scheduled.visual_end_tick = originalVisualEndTick;
    scheduled.q_instant_release = true;
    scheduled.q_instant_release_kind = releaseKind;
    scheduled.q_instant_release_tick = qVisualStartTick;
    scheduled.q_instant_release_anchor_tick = qVisualStartTick;
    scheduled.q_instant_release_calculation_tick = qCalculationStartTick;
    scheduled.q_instant_release_anchor_step_id = qStepId;
    scheduled.q_instant_release_start_sequence = scheduled.calculation_start_sequence;
    scheduled.q_instant_release_end_sequence = scheduled.calculation_end_sequence;
    return originalVisualEndTick;
  }

  function applyQInstantRelease(scheduledSteps) {
    const qEvents = scheduledSteps
      .filter((scheduled) => isZeroForegroundQStep(scheduled.step || {}, scheduled.action || {}))
      .sort((a, b) => int(a.visual_start_tick, int(a.start_tick)) - int(b.visual_start_tick, int(b.start_tick)) || int(a.slot) - int(b.slot));
    const qVirtualIntervals = [];
    qEvents.forEach((qEvent) => {
      recalculateUnreleasedTimings(scheduledSteps, qVirtualIntervals);
      const qStartTick = int(qEvent.visual_start_tick, int(qEvent.start_tick));
      const qCalculationStartTick = calculationTickFromVisualIntervals(qStartTick, qVirtualIntervals);
      const qDurationTicks = Math.max(0, int(qEvent.original_duration_ticks, int(qEvent.duration_ticks)));
      qEvent.start_tick = qCalculationStartTick;
      qEvent.end_tick = qCalculationStartTick + qDurationTicks;
      qEvent.duration_ticks = qDurationTicks;
      const qStepId = String(qEvent.step?.id || '');
      const qSlot = int(qEvent.slot);
      const releaseSlotVisualEnds = new Map();
      const releaseSlotSequences = new Map();
      const coverTargetStepIds = [];
      scheduledSteps.forEach((scheduled) => {
        if (scheduled === qEvent || scheduled.q_instant_release) return;
        if (isQCoverImmuneScheduled(scheduled)) return;
        const startTick = int(scheduled.visual_start_tick, int(scheduled.start_tick));
        const endTick = int(scheduled.visual_end_tick, int(scheduled.end_tick));
        const durationTicks = Math.max(0, int(scheduled.duration_ticks));
        const inQColumn = int(scheduled.slot) !== qSlot && startTick < qStartTick && qStartTick < endTick;
        const ongoingForeground = !scheduled.is_background && durationTicks > 0 && startTick < qStartTick && qStartTick < endTick;
        if (!inQColumn && !ongoingForeground) return;
        const targetSlot = int(scheduled.slot);
        const startSequence = releaseSlotSequences.get(targetSlot) || 0;
        const endSequence = startSequence + 1;
        const visualEnd = markQInstantReleaseTarget(
          scheduled,
          qStartTick,
          qCalculationStartTick,
          qStepId,
          inQColumn ? 'column' : 'foreground',
          startSequence,
          endSequence,
        );
        releaseSlotVisualEnds.set(targetSlot, Math.max(releaseSlotVisualEnds.get(targetSlot) || 0, visualEnd));
        releaseSlotSequences.set(targetSlot, endSequence);
        coverTargetStepIds.push(String(scheduled.step?.id || ''));
      });
      let changed = true;
      while (changed) {
        changed = false;
        scheduledSteps.forEach((scheduled) => {
          if (scheduled === qEvent || scheduled.q_instant_release || !scheduled.can_background_override) return;
          const slot = int(scheduled.slot);
          const coveredUntil = releaseSlotVisualEnds.get(slot);
          const visualStartTick = int(scheduled.visual_start_tick, int(scheduled.start_tick));
          if (coveredUntil == null || visualStartTick > coveredUntil) return;
          const startSequence = releaseSlotSequences.get(slot) || 0;
          const endSequence = startSequence + 1;
          const visualEnd = markQInstantReleaseTarget(
            scheduled,
            qStartTick,
            qCalculationStartTick,
            qStepId,
            'basic-background',
            startSequence,
            endSequence,
            true,
          );
          releaseSlotVisualEnds.set(slot, Math.max(releaseSlotVisualEnds.get(slot) || 0, visualEnd));
          releaseSlotSequences.set(slot, endSequence);
          coverTargetStepIds.push(String(scheduled.step?.id || ''));
          changed = true;
        });
      }
      const coverVisualEndTick = Math.max(
        int(qEvent.visual_end_tick, qStartTick + qVisualDurationTicks(qEvent.action || {})),
        ...Array.from(releaseSlotVisualEnds.values()).map((tick) => int(tick)),
      );
      if (coverVisualEndTick > int(qEvent.visual_end_tick, qStartTick)) {
        qEvent.original_visual_end_tick ??= int(qEvent.visual_end_tick, qStartTick + qVisualDurationTicks(qEvent.action || {}));
        qEvent.visual_end_tick = coverVisualEndTick;
        qEvent.q_cover_visual_end_tick = coverVisualEndTick;
        qEvent.q_cover_target_step_ids = Array.from(new Set(coverTargetStepIds.filter(Boolean)));
      }
      if (qDurationTicks === 0) {
        qVirtualIntervals.push({
          start_tick: qStartTick,
          end_tick: Math.max(qStartTick + ZERO_ACTION_VISUAL_TICKS, int(qEvent.visual_end_tick, qStartTick + ZERO_ACTION_VISUAL_TICKS)),
        });
      }
    });
    recalculateUnreleasedTimings(scheduledSteps, qVirtualIntervals);
  }

  function resourceMap(raw) {
    if (!raw || typeof raw !== 'object') return {};
    return Object.fromEntries(Object.entries(raw).filter(([, value]) => num(value) !== 0).map(([key, value]) => [String(key), num(value)]));
  }

  function simulateAxis(axisPayload, catalog) {
    if (!catalog || typeof catalog !== 'object') {
      throw new Error('缺少排轴数据目录。');
    }
    const actionsById = recordMap(catalog.actions);
    const teamPayload = asList(axisPayload?.team).length ? asList(axisPayload.team) : asList(catalog.starter_axis?.team);
    const steps = asList(axisPayload?.steps).length ? asList(axisPayload.steps) : asList(catalog.starter_axis?.steps);
    validateSteps(steps, actionsById);

    const teamPanelBonus = normalizeTeamPanelBonus(axisPayload?.team_panel_bonus, catalog);
    const snapshots = new Map(teamPayload.map((member) => {
      const snapshot = buildSnapshot(member, catalog, teamPanelBonus);
      return [snapshot.slot, snapshot];
    }));
    const enemy = normalizeEnemy(axisPayload?.enemy);
    let enemyDebuffs = Object.assign({}, enemy.debuffs || {});
    const options = axisPayload?.options && typeof axisPayload.options === 'object' ? axisPayload.options : {};
    const fonsFull = options.fons_full == null ? true : Boolean(options.fons_full);
    const switchLossTicks = Math.max(0, int(options.switch_loss_ticks, int(catalog.formula_constants?.switch_loss_ticks, 2)));
    const details = [];
    const frontEvents = [];
    let directDamage = 0;
    let staggerDamage = 0;
    let totalStagger = 0;
    const specialDamageBySource = new Map(SPECIAL_DAMAGE_SOURCES.map((source) => [source, 0]));
    const initialEnergy = num(axisPayload?.initial_energy, 100);
    const energyBySlot = new Map(Array.from(snapshots.keys()).map((slot) => [slot, initialEnergy]));
    const harmonyBySlot = new Map(Array.from(snapshots.keys()).map((slot) => [slot, 0]));
    const cooldownUntil = new Map();
    const personalResources = new Map(Array.from(snapshots.keys()).map((slot) => [slot, {}]));
    const initialPersonalResources = axisPayload?.initial_personal_resources && typeof axisPayload.initial_personal_resources === 'object'
      ? axisPayload.initial_personal_resources
      : {};
    personalResources.forEach((resources, slot) => {
      Object.assign(resources, resourceMap(initialPersonalResources[String(slot)] || initialPersonalResources[slot] || {}));
    });
    const buffRules = registeredBuffRules(teamPayload, catalog).concat(legacyBuffRules(axisPayload?.buff_rules));
    const orderedStepEntries = supportProtectedStepEntries(steps, actionsById);
    const qStarts = qVirtualStartTicks(orderedStepEntries.map(({ step, visualStartTick }) => ({
      ...step,
      start_tick: visualStartTick,
    })), actionsById);
    const scheduledSteps = [];
    let scheduleFrontSlot = null;
    let previousForegroundDuration = 0;
    let previousForegroundIsQ = false;
    let previousForegroundEndTick = 0;
    let scheduledLastTick = 0;
    orderedStepEntries.forEach(({ step, visualStartTick: protectedVisualStartTick }) => {
      const slot = int(step.slot);
      const snapshot = snapshots.get(slot);
      if (!snapshot) return;
      const action = actionsById.get(String(step.action_id || ''));
      let visualStartTick = protectedVisualStartTick;
      let startTick = calculationTickFromVisual(visualStartTick, qStarts);
      const isBackground = isStepBackground(step, action);
      const actionIsSupport = isSupportAction(action);
      const qEndSwitch = previousForegroundIsQ && startTick >= previousForegroundEndTick;
      let switchLossDelta = 0;
      if (!isBackground && !actionIsSupport && scheduleFrontSlot !== null && scheduleFrontSlot !== slot && previousForegroundDuration > 0 && !qEndSwitch) {
        switchLossDelta = switchLossTicks;
        startTick += switchLossDelta;
        visualStartTick += switchLossDelta;
      }
      const durationTicks = Math.max(0, int(action.duration_ticks));
      const endTick = startTick + durationTicks;
      const visualEndTick = visualStartTick + (durationTicks > 0 ? durationTicks : ZERO_ACTION_VISUAL_TICKS);
      scheduledSteps.push({
        step,
        slot,
        action,
        start_tick: startTick,
        calculation_start_sequence: 0,
        visual_start_tick: visualStartTick,
        switch_loss_ticks: switchLossDelta,
        is_background: isBackground,
        is_basic_background: isBasicBackgroundOverride(step, action),
        can_background_override: canBackgroundOverride(action),
        duration_ticks: durationTicks,
        end_tick: endTick,
        calculation_end_sequence: 0,
        visual_end_tick: visualEndTick,
        original_start_tick: startTick,
        original_calculation_start_sequence: 0,
        original_duration_ticks: durationTicks,
        original_end_tick: endTick,
        original_calculation_end_sequence: 0,
        original_visual_end_tick: visualEndTick,
      });
      if (!isBackground) {
        scheduleFrontSlot = slot;
        previousForegroundDuration = durationTicks;
        previousForegroundIsQ = isZeroForegroundQStep(step, action);
        previousForegroundEndTick = endTick;
      }
      scheduledLastTick = Math.max(scheduledLastTick, endTick, startTick);
    });
    applyQInstantRelease(scheduledSteps);
    scheduledLastTick = Math.max(0, ...scheduledSteps.map((item) => Math.max(int(item.end_tick), int(item.start_tick))), scheduledLastTick);
    const loopDurationTicks = Math.max(scheduledLastTick, 1);
    let activeBuffs = [];
    const buffTriggerCooldowns = new Map();

    function triggerTickForRule(rule, startTick, endTick) {
      return String(rule.trigger?.event || '') === 'action_end' ? endTick : startTick;
    }

    function triggerBuffsForEvent(event, triggerTick, step, action, snapshot, isBackground, extraContext = {}) {
      const triggered = [];
      const context = Object.assign({
        enemy,
        snapshot,
        tick: triggerTick,
        action_tags: Array.from(actionTags(action)).sort(),
        hit_count: actionHitCount(action),
        enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, triggerTick),
        applied_enemy_debuffs: [],
        fons_full: fonsFull,
      }, extraContext);
      buffRules.forEach((rule) => {
        if (!eventMatchesRule(rule, event, step, action, snapshot, isBackground, context)) return;
        const cooldownTicks = triggerCooldownTicks(rule);
        const cooldownKey = `${int(rule.owner_slot)}:${String(rule.id || '')}`;
        if (cooldownTicks > 0 && triggerTick < (buffTriggerCooldowns.get(cooldownKey) || 0)) return;
        const instance = activateBuff(activeBuffs, rule, triggerTick, stackGainForRule(rule, context));
        if (!instance) return;
        if (cooldownTicks > 0) buffTriggerCooldowns.set(cooldownKey, triggerTick + cooldownTicks);
        const summary = buffSummary(instance);
        summary.trigger_event = event;
        summary.trigger_tick = triggerTick;
        summary.visual_start_tick = Math.max(triggerTick, int(summary.start_tick));
        summary.display_start_tick = summary.visual_start_tick;
        summary.display_end_tick = int(summary.end_tick, summary.visual_start_tick + 1);
        triggered.push(summary);
      });
      return triggered;
    }

    if (options.loop_enabled && loopDurationTicks > 0) {
      scheduledSteps.forEach((scheduled) => {
        const step = scheduled.step;
        const action = scheduled.action;
        const snapshot = snapshots.get(int(scheduled.slot));
        if (!snapshot) return;
        const startTick = int(scheduled.visual_start_tick, int(scheduled.start_tick));
        const endTick = int(scheduled.visual_end_tick, int(scheduled.end_tick));
        buffRules.forEach((rule) => {
          if (!rule.duration?.loop_carry) return;
          const event = String(rule.trigger?.event || '');
          const triggerTick = triggerTickForRule(rule, startTick, endTick);
          const context = {
            enemy,
            snapshot,
            tick: triggerTick,
            action_tags: Array.from(actionTags(action)).sort(),
            hit_count: actionHitCount(action),
            enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, triggerTick),
            applied_enemy_debuffs: [],
            fons_full: fonsFull,
          };
          if (!eventMatchesRule(rule, event, step, action, snapshot, scheduled.is_background, context)) return;
          const instance = activateBuff(activeBuffs, rule, triggerTick - loopDurationTicks, stackGainForRule(rule, context));
          if (instance) {
            instance.start_tick = Math.max(0, int(instance.start_tick));
            instance.looped = true;
          }
        });
      });
    }

    let lastTick = 0;
    scheduledSteps.forEach((scheduled) => {
      const step = scheduled.step;
      const slot = int(scheduled.slot);
      const snapshot = snapshots.get(slot);
      if (!snapshot) return;
      const action = scheduled.action;
      const startTick = int(scheduled.start_tick);
      const visualStartTick = int(scheduled.visual_start_tick, startTick);
      const isBackground = Boolean(scheduled.is_background);
      const durationTicks = Math.max(0, int(scheduled.duration_ticks));
      const endTick = int(scheduled.end_tick);
      const visualEndTick = int(scheduled.visual_end_tick);
      const cooldownKey = `${slot}:${String(action.id || '')}`;
      const availableTick = cooldownUntil.get(cooldownKey) || 0;
      const warnings = [];
      if (startTick < availableTick) warnings.push(`动作 CD 尚未结束，需等到 ${(availableTick / 10).toFixed(1)}s。`);
      const energyCost = num(action.energy_cost);
      let slotEnergy = energyBySlot.get(slot) ?? initialEnergy;
      if (energyCost > slotEnergy) warnings.push('终结技能量不足。');
      const buffTick = visualStartTick;
      enemyDebuffs = activeEnemyDebuffs(enemyDebuffs, buffTick);
      activeBuffs = activeBuffs.filter((buff) => buffTick < int(buff.end_tick) && !activeBuffResetsOnActionStart(buff, step, action, isBackground));
      const triggeredBuffs = triggerBuffsForEvent('action_start', visualStartTick, step, action, snapshot, isBackground);
      const appliedBuffs = [];
      const buffModifiers = mods();
      activeBuffs.forEach((buff) => {
        if (buffTick < int(buff.start_tick) || buffTick >= int(buff.end_tick)) return;
        if (!activeBuffApplies(buff, step, action, snapshot, isBackground)) return;
        mergeMods(buffModifiers, buffEffects(buff));
        appliedBuffs.push(buffSummary(buff));
      });
      const slotResources = personalResources.get(slot) || {};
      Object.entries(resourceMap(action.personal_resource_cost)).forEach(([key, cost]) => {
        if ((slotResources[key] || 0) < cost) warnings.push(`个人资源 ${key} 不足。`);
        slotResources[key] = Math.max(0, (slotResources[key] || 0) - cost);
      });
      Object.entries(resourceMap(action.personal_resource_gain)).forEach(([key, gain]) => {
        slotResources[key] = (slotResources[key] || 0) + gain;
      });
      slotEnergy = Math.max(0, slotEnergy - energyCost);
      const calc = calculateActionDamage(snapshot, action, enemy, buffModifiers);
      const criticalHits = expectedCriticalHits(action, calc);
      const appliedEnemyDebuffs = applyEnemyDebuffs(enemyDebuffs, action, buffTick);
      triggeredBuffs.push(...triggerBuffsForEvent('action_hit', visualStartTick, step, action, snapshot, isBackground, {
        expected_critical_hits: criticalHits,
        applied_enemy_debuffs: appliedEnemyDebuffs,
        enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, buffTick),
      }));
      directDamage += calc.direct_damage;
      const damageSource = specialDamageSource(action);
      if (damageSource) {
        specialDamageBySource.set(damageSource, (specialDamageBySource.get(damageSource) || 0) + calc.direct_damage);
      }
      totalStagger += calc.stagger_amount;
      harmonyBySlot.set(slot, (harmonyBySlot.get(slot) || 0) + calc.harmony);
      slotEnergy += calc.energy_gain + num(action.energy_return);
      energyBySlot.set(slot, slotEnergy);
      while (totalStagger >= 50) {
        totalStagger -= 50;
        const reactionStrength = Math.max(...Array.from(snapshots.values()).map((item) => item.stats.harmony_strength));
        staggerDamage += 12000 * (1 + reactionStrength / 600) * defenseMultiplier(enemy, snapshot.mods);
      }
      if (durationTicks > 0) {
        cooldownUntil.set(cooldownKey, Math.max(cooldownUntil.get(cooldownKey) || 0, startTick + Math.max(durationTicks, int(action.cooldown_ticks))));
      } else if (int(action.cooldown_ticks) > 0) {
        cooldownUntil.set(cooldownKey, Math.max(cooldownUntil.get(cooldownKey) || 0, startTick + int(action.cooldown_ticks)));
      }
      if (!isBackground) {
        frontEvents.push({
          slot,
          start_tick: startTick,
          end_tick: endTick,
          visual_start_tick: visualStartTick,
          visual_end_tick: visualEndTick,
          order: frontEvents.length,
        });
      }
      triggeredBuffs.push(...triggerBuffsForEvent('action_end', visualEndTick, step, action, snapshot, isBackground));
      lastTick = Math.max(lastTick, endTick, startTick);
      details.push({
        step_id: step.id || '',
        slot,
        character_id: snapshot.character.id,
        character_name: snapshot.character.name,
        action_id: action.id,
        action_name: action.name,
        action_type: action.action_type,
        raw_start_tick: int(step.start_tick),
        start_tick: startTick,
        calculation_start_sequence: int(scheduled.calculation_start_sequence),
        end_tick: endTick,
        calculation_end_sequence: int(scheduled.calculation_end_sequence),
        duration_ticks: durationTicks,
        visual_start_tick: visualStartTick,
        visual_end_tick: visualEndTick,
        display_start_tick: visualStartTick,
        display_end_tick: visualEndTick,
        display_duration_ticks: durationTicks,
        display_visual_end_tick: visualEndTick,
        original_start_tick: int(scheduled.original_start_tick, startTick),
        original_calculation_start_sequence: int(scheduled.original_calculation_start_sequence),
        original_duration_ticks: int(scheduled.original_duration_ticks, durationTicks),
        original_end_tick: int(scheduled.original_end_tick, endTick),
        original_calculation_end_sequence: int(scheduled.original_calculation_end_sequence),
        original_visual_end_tick: int(scheduled.original_visual_end_tick, visualEndTick),
        q_instant_release: Boolean(scheduled.q_instant_release),
        q_instant_release_kind: scheduled.q_instant_release_kind || '',
        q_instant_release_tick: scheduled.q_instant_release_tick,
        q_instant_release_anchor_tick: scheduled.q_instant_release_anchor_tick,
        q_instant_release_calculation_tick: scheduled.q_instant_release_calculation_tick,
        q_instant_release_anchor_step_id: scheduled.q_instant_release_anchor_step_id || '',
        q_instant_release_start_sequence: scheduled.q_instant_release_start_sequence,
        q_instant_release_end_sequence: scheduled.q_instant_release_end_sequence,
        q_cover_visual_end_tick: scheduled.q_cover_visual_end_tick,
        q_cover_target_step_ids: asList(scheduled.q_cover_target_step_ids),
        is_background_damage: isBackground,
        is_basic_background: isBasicBackgroundOverride(step, action),
        action_tags: Array.from(actionTags(action)).sort(),
        hit_count: actionHitCount(action),
        expected_critical_hits: criticalHits,
        applied_enemy_debuffs: appliedEnemyDebuffs,
        enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, buffTick),
        direct_damage: calc.direct_damage,
        stagger_amount: calc.stagger_amount,
        harmony: calc.harmony,
        energy_after: slotEnergy,
        harmony_after: harmonyBySlot.get(slot) || 0,
        personal_resources_after: Object.assign({}, slotResources),
        nightmare_stacks: action.nightmare_stacks,
        sin_recovery: action.sin_recovery,
        applied_buffs: appliedBuffs,
        triggered_buffs: triggeredBuffs,
        panel: calc.panel,
        formula_parts: calc.formula_parts,
        warnings,
      });
    });

    frontEvents.sort((a, b) => int(a.visual_start_tick, int(a.start_tick)) - int(b.visual_start_tick, int(b.start_tick)) || int(a.order) - int(b.order));
    const dedupedFrontEvents = [];
    frontEvents.forEach((event) => {
      const last = dedupedFrontEvents[dedupedFrontEvents.length - 1];
      if (last && int(last.visual_start_tick, int(last.start_tick)) === int(event.visual_start_tick, int(event.start_tick))) {
        dedupedFrontEvents[dedupedFrontEvents.length - 1] = event;
      } else {
        dedupedFrontEvents.push(event);
      }
    });
    const frontWindows = [];
    dedupedFrontEvents.forEach((event, index) => {
      const startTick = int(event.visual_start_tick, int(event.start_tick));
      const endTick = index + 1 < dedupedFrontEvents.length
        ? int(dedupedFrontEvents[index + 1].visual_start_tick, int(dedupedFrontEvents[index + 1].start_tick))
        : Math.max(int(event.end_tick), int(event.visual_end_tick), startTick + 1);
      if (endTick <= startTick) return;
      const last = frontWindows[frontWindows.length - 1];
      if (last && int(last.slot) === int(event.slot) && startTick <= int(last.end_tick)) {
        last.end_tick = Math.max(int(last.end_tick), endTick);
        last.visual_end_tick = last.end_tick;
        return;
      }
      frontWindows.push({ slot: int(event.slot), start_tick: startTick, end_tick: endTick, visual_end_tick: endTick });
    });

    const durationTicks = Math.max(lastTick, 0);
    const totalDamage = directDamage + staggerDamage;
    const teamEnergy = Array.from(energyBySlot.values()).reduce((sum, value) => sum + value, 0);
    const totalHarmony = Array.from(harmonyBySlot.values()).reduce((sum, value) => sum + value, 0);
    const damageBySlot = new Map();
    details.forEach((detail) => damageBySlot.set(detail.slot, (damageBySlot.get(detail.slot) || 0) + detail.direct_damage));
    const sortedSlots = Array.from(snapshots.keys()).sort((a, b) => a - b);
    const damageBySource = [
      ...SPECIAL_DAMAGE_SOURCES.map((source) => ({
        source,
        damage: specialDamageBySource.get(source) || 0,
      })),
      { source: '倾陷', damage: staggerDamage },
    ]
      .filter((item) => item.damage > 0)
      .map((item) => ({
        ...item,
        percent: totalDamage > 0 ? item.damage / totalDamage * 100 : 0,
      }));
    return {
      ok: true,
      summary: {
        duration_ticks: durationTicks,
        duration_seconds: durationTicks / 10,
        direct_damage: directDamage,
        stagger_damage: staggerDamage,
        total_damage: totalDamage,
        dps: totalDamage / Math.max(durationTicks / 10, 0.1),
        team_energy: teamEnergy,
        total_harmony: totalHarmony,
      },
      damage_by_slot: sortedSlots.map((slot) => ({
        slot,
        character_id: snapshots.get(slot).character.id,
        character_name: snapshots.get(slot).character.name,
        damage: damageBySlot.get(slot) || 0,
        percent: directDamage > 0 ? (damageBySlot.get(slot) || 0) / directDamage * 100 : 0,
      })),
      damage_by_source: damageBySource,
      resources_by_slot: sortedSlots.map((slot) => ({
        slot,
        character_id: snapshots.get(slot).character.id,
        character_name: snapshots.get(slot).character.name,
        initial_energy: initialEnergy,
        energy: energyBySlot.get(slot) ?? initialEnergy,
        initial_harmony: 0,
        harmony: harmonyBySlot.get(slot) || 0,
        personal_resources: personalResources.get(slot) || {},
      })),
      build_panels_by_slot: sortedSlots.map((slot) => buildPanelProjection(snapshots.get(slot))),
      details,
      front_windows: frontWindows,
      enemy,
    };
  }

  return {
    ELEMENTS,
    ZERO_ACTION_VISUAL_TICKS,
    MIN_FOREGROUND_START_GAP_TICKS,
    calculateAxisDurationTicks,
    buildSnapshot,
    buildPanelProjection,
    simulateAxis,
  };
}));
