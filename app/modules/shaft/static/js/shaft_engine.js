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
  const PERSONAL_RESOURCE_CAPS = {
    char_701295143d: { '言灵字': 4 },
    char_912dbfe17c: { '闪送之力': 6 },
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
  const SUPPORTED_TRIGGER_EVENTS = new Set(['passive', 'action_start', 'action_hit', 'action_end', 'loop_start', 'reaction_trigger']);
  const PERMANENT_BUFF_END_TICK = 1000000000;
  const SPECIAL_DAMAGE_SOURCES = ['创生', '浊燃', '黯星', '噩梦'];
  const REACTION_BY_ELEMENT_PAIR = new Map([
    ['光|灵', '创生'],
    ['光|相', '延滞'],
    ['灵|咒', '覆纹'],
    ['咒|暗', '浊燃'],
    ['暗|魂', '黯星'],
    ['魂|相', '浸染'],
  ]);
  const REACTION_DURATIONS = {
    '创生': 100,
    '延滞': 50,
    '覆纹': 120,
    '浊燃': 150,
    '黯星': 50,
    '浸染': 120,
  };
  const REACTION_BASE_DAMAGE = {
    5: { '创生': 80, '浊燃': 20, '黯星': 400 },
    10: { '创生': 120, '浊燃': 35, '黯星': 600 },
    15: { '创生': 200, '浊燃': 60, '黯星': 1000 },
    20: { '创生': 300, '浊燃': 90, '黯星': 1500 },
    25: { '创生': 400, '浊燃': 120, '黯星': 2000 },
    30: { '创生': 600, '浊燃': 180, '黯星': 3000 },
    35: { '创生': 800, '浊燃': 240, '黯星': 4000 },
    40: { '创生': 1000, '浊燃': 300, '黯星': 5000 },
    45: { '创生': 1700, '浊燃': 510, '黯星': 8500 },
    50: { '创生': 2200, '浊燃': 660, '黯星': 11000 },
    55: { '创生': 3600, '浊燃': 1080, '黯星': 18000 },
    60: { '创生': 5000, '浊燃': 1500, '黯星': 25000 },
    65: { '创生': 6000, '浊燃': 1800, '黯星': 30000 },
    70: { '创生': 7000, '浊燃': 2100, '黯星': 35000 },
    75: { '创生': 8000, '浊燃': 2400, '黯星': 40000 },
    80: { '创生': 9000, '浊燃': 2700, '黯星': 45000 },
  };

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

  function awakeningNodes(source) {
    if (Array.isArray(source?.awakening_nodes)) {
      return new Set(source.awakening_nodes.map((value) => int(value)).filter((value) => value >= 1 && value <= 6));
    }
    return new Set(Array.from({ length: Math.max(0, Math.min(6, int(source?.awakening))) }, (_, index) => index + 1));
  }

  function hasAwakeningNode(source, level) {
    return awakeningNodes(source).has(int(level));
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
      res_down_光: 0,
      res_down_灵: 0,
      res_down_咒: 0,
      res_down_暗: 0,
      res_down_魂: 0,
      res_down_相: 0,
      res_down_心灵: 0,
      energy_recharge: 0,
      harmony_strength: 0,
      stagger_strength: 0,
      stagger_multiplier: 0,
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
    return awakeningNodes(member).size >= 3 ? 1 : 0;
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
    const arcRefinementRecord = catalog?.arc_refinements?.arcs?.[String(member?.arc_id || '')] || {};
    const requestedArcRefinement = int(member?.arc_refinement);
    const arcRefinementLevel = requestedArcRefinement >= 1 && requestedArcRefinement <= 5
      ? requestedArcRefinement
      : Math.max(1, Math.min(5, int(arcRefinementRecord.default_level, 1)));
    const arcRefinement = arcRefinementRecord.levels?.[String(arcRefinementLevel)] || null;
    const cartridge = cartridges.get(String(member?.cartridge_id || '')) || null;
    const panelMods = mods();
    const mainStat = cartridgeMainStat(member, constants);
    const bonus = curtainBonus(member, constants);
    const curtain = curtainBonusMods(bonus, cartridge, constants);
    // Character-sheet modifiers historically contained baked passive/awakening
    // bonuses. They are deliberately ignored; character buffs are registry rules.
    panelMods.crit_rate = 0.05;
    panelMods.crit_dmg = 0.5;
    if (member?.bond_full || int(member?.bond_level) > 0) {
      mergeMods(panelMods, character.bond_bonus?.modifiers);
    }
    if (arc) mergeMods(panelMods, arcRefinement?.panel_modifiers || arc.modifiers);
    if (cartridge) mergeMods(panelMods, cartridge.modifiers);
    mergeMods(panelMods, mainStatMods(mainStat, constants));
    mergeMods(panelMods, curtain.modifiers);
    mergeMods(panelMods, substatMods(member?.substat_counts || {}, constants));
    mergeMods(panelMods, teamPanelBonusMods(teamPanelBonus, catalog));
    const element = String(character.element || '');
    panelMods.element_dmg += num((arcRefinement?.element_dmg || arc?.element_dmg)?.[element]);
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
      awakening: awakeningNodes(member).size,
      awakening_nodes: Array.from(awakeningNodes(member)).sort((left, right) => left - right),
      character,
      arc,
      arc_refinement: arcRefinementLevel,
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
    const resistances = enemy.resistances && typeof enemy.resistances === 'object' ? enemy.resistances : {};
    return {
      level: Math.max(1, Math.min(120, int(enemy.level, 90))),
      track_outside: Boolean(enemy.track_outside),
      weakness_elements: weakness.map(String).filter((item) => ELEMENTS.includes(item)),
      debuffs: Object.fromEntries(Object.entries(debuffs)
        .filter(([name]) => Object.prototype.hasOwnProperty.call(ENEMY_DEBUFF_DURATIONS, name))
        .map(([name, endTick]) => [name, Math.max(0, int(endTick))])),
      hp_ratio: Math.max(0, Math.min(1, hpRatio)),
      resistances: Object.fromEntries(
        [...ELEMENTS, '心灵'].map((element) => [element, Math.max(-1, Math.min(1, num(resistances[element], 0.3)))]),
      ),
    };
  }

  function resistanceMultiplier(character, enemy, panelMods) {
    const element = String(character?.element || '');
    const damageElement = element || '心灵';
    const baseRes = num(enemy.resistances?.[damageElement], 0.3);
    const weaknessDown = new Set(enemy.weakness_elements || []).has(element) ? 0.2 : 0;
    const elementResDown = num(panelMods[`res_down_${damageElement}`]);
    const value = 1 - baseRes + weaknessDown + panelMods.res_down + elementResDown;
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
    const resistanceCharacter = actionTags(action).has('心灵') ? { element: '' } : snapshot.character;
    const resistance = resistanceMultiplier(resistanceCharacter, enemy, panelMods);
    const defense = defenseMultiplier(enemy, panelMods);
    const direct = Math.max(0, base * (1 + dmgBonus) * crit * resistance * defense * (1 + panelMods.final_dmg));
    return {
      direct_damage: direct,
      stagger_amount: Math.max(0, num(action.stagger) * (1 + panelMods.stagger_strength / 300) * (1 + panelMods.stagger_multiplier)),
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

  function reactionForElements(firstElement, secondElement) {
    const pair = [String(firstElement || ''), String(secondElement || '')]
      .sort((a, b) => ELEMENTS.indexOf(a) - ELEMENTS.indexOf(b))
      .join('|');
    return REACTION_BY_ELEMENT_PAIR.get(pair) || '';
  }

  function reactionBaseDamage(level, reaction) {
    const bracket = Math.max(5, Math.min(80, Math.floor(Math.max(5, num(level, 80)) / 5) * 5));
    return num(REACTION_BASE_DAMAGE[bracket]?.[reaction]);
  }

  function reactionStrengthMultiplier(harmonyStrength) {
    return 1 + Math.max(0, num(harmonyStrength)) / 600;
  }

  function isBackgroundAction(action) {
    return Boolean(action?.is_background_damage) || `${action?.name || ''} ${action?.extra_tag || ''}`.includes('后台');
  }

  function backgroundActionMultiplier(step, action) {
    return isBackgroundAction(action) ? Math.max(1, Math.min(12, int(step?.repeat, 1))) : 1;
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

  function locksForegroundSwitch(step, action) {
    return startsForeground(step, action) && (
      isSupportAction(action) ||
      isZeroForegroundQStep(step, action)
    );
  }

  function tickScheduledStepEntries(steps, actionsById, switchGapTicks = MIN_FOREGROUND_START_GAP_TICKS) {
    const ordered = steps.slice().sort((a, b) => {
      const startDelta = int(a.start_tick) - int(b.start_tick);
      if (startDelta) return startDelta;
      const aAction = actionsById.get(String(a.action_id || '')) || {};
      const bAction = actionsById.get(String(b.action_id || '')) || {};
      const lockDelta = Number(locksForegroundSwitch(b, bAction)) - Number(locksForegroundSwitch(a, aAction));
      return lockDelta || int(a.slot) - int(b.slot);
    });
    let previousForegroundSlot = null;
    let previousForegroundStartTick = null;
    const foregroundLocks = [];
    const carriedShiftBySlot = new Map();
    return ordered.map((step) => {
      const action = actionsById.get(String(step.action_id || '')) || {};
      const isBackground = isStepBackground(step, action);
      const slot = int(step.slot);
      let visualStartTick = int(step.start_tick) + Math.max(0, int(carriedShiftBySlot.get(slot)));
      const carriedStartTick = visualStartTick;
      let switchLossTicks = 0;
      let foregroundLockTicks = 0;
      if (!isBackground) {
        let lockEndTick = Math.max(
          0,
          ...foregroundLocks
            .filter((lock) => visualStartTick < int(lock.end_tick))
            .map((lock) => int(lock.end_tick)),
        );
        while (lockEndTick > visualStartTick) {
          foregroundLockTicks += lockEndTick - visualStartTick;
          visualStartTick = lockEndTick;
          lockEndTick = Math.max(
            0,
            ...foregroundLocks
              .filter((lock) => visualStartTick < int(lock.end_tick))
              .map((lock) => int(lock.end_tick)),
          );
        }
      }
      if (
        !isBackground &&
        previousForegroundSlot !== null &&
        previousForegroundSlot !== int(step.slot) &&
        previousForegroundStartTick !== null
      ) {
        const earliestStartTick = previousForegroundStartTick + Math.max(0, int(switchGapTicks));
        if (visualStartTick < earliestStartTick) {
          switchLossTicks = earliestStartTick - visualStartTick;
          visualStartTick = earliestStartTick;
        }
      }
      if (!isBackground) {
        previousForegroundSlot = int(step.slot);
        previousForegroundStartTick = visualStartTick;
      }
      if (locksForegroundSwitch(step, action)) {
        foregroundLocks.push({
          slot,
          end_tick: visualStartTick + qVisualDurationTicks(action),
        });
      }
      const addedShiftTicks = Math.max(0, visualStartTick - carriedStartTick);
      if (addedShiftTicks > 0) {
        carriedShiftBySlot.set(slot, Math.max(0, int(carriedShiftBySlot.get(slot))) + addedShiftTicks);
      }
      return { step, visualStartTick, switchLossTicks, foregroundLockTicks };
    });
  }

  function qVisualDurationTicks(action) {
    return Math.max(ZERO_ACTION_VISUAL_TICKS, Math.max(0, int(action?.duration_ticks)));
  }

  function isZeroForegroundQStep(step, action) {
    return startsForeground(step, action) && isQAction(action) && Math.max(0, int(action?.duration_ticks)) === 0;
  }

  function isQCoverImmuneScheduled(scheduled) {
    return isSupportAction(scheduled?.action || {}) ||
      isZeroForegroundQStep(scheduled?.step || {}, scheduled?.action || {});
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

  function normalizeFrozenIntervals(qIntervals) {
    const normalized = asList(qIntervals)
      .map((interval) => {
        const startTick = Math.max(0, int(interval?.start_tick));
        return {
          start_tick: startTick,
          end_tick: Math.max(startTick, int(interval?.end_tick, startTick)),
        };
      })
      .filter((interval) => interval.end_tick > interval.start_tick)
      .sort((left, right) => left.start_tick - right.start_tick || left.end_tick - right.end_tick);
    const merged = [];
    normalized.forEach((interval) => {
      const previous = merged[merged.length - 1];
      if (previous && interval.start_tick <= previous.end_tick) {
        previous.end_tick = Math.max(previous.end_tick, interval.end_tick);
      } else {
        merged.push({ ...interval });
      }
    });
    return merged;
  }

  function visualTickFromCalculationTick(calculationTick, qIntervals) {
    const safeCalculationTick = Math.max(0, int(calculationTick));
    let visualTick = safeCalculationTick;
    asList(qIntervals)
      .slice()
      .sort((left, right) => int(left?.start_tick) - int(right?.start_tick))
      .forEach((interval) => {
        const startTick = Math.max(0, int(interval?.start_tick));
        const endTick = Math.max(startTick, int(interval?.end_tick, startTick + ZERO_ACTION_VISUAL_TICKS));
        const intervalCalculationTick = calculationTickFromVisualIntervals(startTick, qIntervals);
        if (intervalCalculationTick < safeCalculationTick) {
          visualTick += endTick - startTick;
        }
      });
    return visualTick;
  }

  function recalculateTimingsFromFrozenIntervals(scheduledSteps, qIntervals) {
    scheduledSteps.forEach((scheduled) => {
      const visualStartTick = int(scheduled.visual_start_tick, int(scheduled.step?.start_tick));
      const visualEndTick = Math.max(visualStartTick, int(scheduled.visual_end_tick, visualStartTick));
      const startTick = calculationTickFromVisualIntervals(visualStartTick, qIntervals);
      const endTick = calculationTickFromVisualIntervals(visualEndTick, qIntervals);
      scheduled.start_tick = startTick;
      scheduled.end_tick = Math.max(startTick, endTick);
      scheduled.duration_ticks = Math.max(0, scheduled.end_tick - scheduled.start_tick);
      if (!scheduled.q_instant_release) {
        scheduled.calculation_start_sequence = 0;
        scheduled.calculation_end_sequence = 0;
      }
    });
  }

  function calculateAxisDurationTicks(steps, actionsById) {
    return Math.max(0, ...asList(steps).map((step) => {
      const action = actionsById.get(String(step?.action_id || '')) || {};
      const startTick = Math.max(0, int(step?.start_tick));
      const durationTicks = isZeroForegroundQStep(step, action)
        ? ZERO_ACTION_VISUAL_TICKS
        : Math.max(0, int(action.duration_ticks));
      return Math.max(startTick, startTick + durationTicks);
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
      if (type === 'awakening_min') {
        const level = int(condition.min, int(condition.value));
        return Array.isArray(context.owner_awakening_nodes)
          ? context.owner_awakening_nodes.map(int).includes(level)
          : int(context.owner_awakening) >= level;
      }
      if (type === 'awakening_max') {
        const nextLevel = int(condition.max, int(condition.value)) + 1;
        return Array.isArray(context.owner_awakening_nodes)
          ? !context.owner_awakening_nodes.map(int).includes(nextLevel)
          : int(context.owner_awakening) < nextLevel;
      }
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
      if (type === 'owner_character_id') {
        return new Set(asList(condition.ids).map(String)).has(String(context.owner_character_id || ''));
      }
      if (type === 'take_damage') return Boolean(context.take_damage);
      if (type === 'enemy_hp_below') return num(context.enemy?.hp_ratio, num(context.enemy?.hp_percent, 100) / 100) < num(condition.threshold, 0.5);
      if (type === 'enemy_weak_to_owner_element') {
        const element = String(context.snapshot?.character?.element || '');
        return new Set(context.enemy?.weakness_elements || []).has(element);
      }
      if (type === 'active_buff_key') {
        return new Set(asList(context.active_buff_keys).map(String)).has(String(condition.key || ''));
      }
      if (type === 'active_buff_any') {
        const active = new Set(asList(context.active_buff_keys).map(String));
        return asList(condition.keys).map(String).some((key) => active.has(key));
      }
      if (type === 'reaction_owner_involved') {
        const ownerSlot = int(context.owner_slot, -1);
        return ownerSlot === int(context.reaction?.previous_slot, -2) || ownerSlot === int(context.reaction?.support_slot, -2);
      }
      if (type === 'reaction_type') {
        return new Set(asList(condition.reactions).map(String)).has(String(context.reaction?.reaction || ''));
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
          rule.owner_awakening = awakeningNodes(member).size;
          rule.owner_awakening_nodes = Array.from(awakeningNodes(member)).sort((left, right) => left - right);
          const arcRefinementRecord = catalog?.arc_refinements?.arcs?.[providerId] || {};
          const requestedArcRefinement = int(member.arc_refinement);
          rule.owner_arc_refinement = requestedArcRefinement >= 1 && requestedArcRefinement <= 5
            ? requestedArcRefinement
            : Math.max(1, Math.min(5, int(arcRefinementRecord.default_level, 1)));
          if (kind === 'arc') {
            const refinement = arcRefinementRecord.levels?.[String(rule.owner_arc_refinement)];
            const refinementEffects = refinement?.buff_effects?.[String(rule.id || '')];
            if (refinementEffects && typeof refinementEffects === 'object') {
              rule.effects = clone(refinementEffects);
            }
          }
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
      owner_awakening_nodes: rule.owner_awakening_nodes,
    });
    return conditionsMatch(trigger.conditions, eventContext);
  }

  function targetMatches(target, instance, step, action, snapshot, isBackground, context = {}) {
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
    if (!conditionsMatch(target?.conditions, Object.assign({}, context, { snapshot }))) return false;
    return true;
  }

  function activeBuffResetsOnActionStart(instance, step, action, isBackground, tick) {
    const rule = instance.rule && typeof instance.rule === 'object' ? instance.rule : {};
    const reset = rule.reset && typeof rule.reset === 'object' ? rule.reset : {};
    if (!reset || isBackground) return false;
    const ownerSlot = int(instance.owner_slot);
    const stepSlot = int(step.slot);
    if (reset.owner_foreground && stepSlot === ownerSlot) return true;
    if (reset.owner_leaves_foreground && stepSlot !== ownerSlot) return true;
    if (reset.owner_leaves_foreground_after_start && stepSlot !== ownerSlot) {
      if (int(tick) < int(instance.start_tick)) {
        instance.ignore_owner_leave_reset = true;
        return false;
      }
      return !instance.ignore_owner_leave_reset;
    }
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
    if (String(stacking.stack_gain_from || '') === 'hit_count') return Math.max(0, num(context.hit_count));
    for (const condition of asList(rule.trigger?.conditions)) {
      if (condition && typeof condition === 'object' && String(condition.type || '') === 'expected_critical_hit') {
        return Math.max(0, num(context.expected_critical_hits));
      }
    }
    return 1;
  }

  function activateBuff(activeBuffs, rule, triggerTick, stackGain = 1, context = {}) {
    const duration = rule.duration && typeof rule.duration === 'object' ? rule.duration : {};
    const isPermanent = String(duration.type || '') === 'permanent';
    const durationTicks = isPermanent ? PERMANENT_BUFF_END_TICK : Math.max(0, int(duration.ticks));
    if (durationTicks <= 0) return null;
    const startTick = triggerTick + Math.max(0, int(duration.delay_ticks));
    const endTick = startTick + durationTicks;
    const stacking = rule.stacking && typeof rule.stacking === 'object' ? rule.stacking : {};
    const mode = String(stacking.mode || 'refresh');
    const maxStacks = Math.max(1, num(stacking.max_stacks, 1));
    const gain = Math.max(0, stackGain);
    if (gain <= 0) return null;
    const definitionId = String(stacking.key || rule.id || '');
    const ownerSlot = int(rule.owner_slot);
    for (const instance of activeBuffs) {
      const existingRule = instance.rule && typeof instance.rule === 'object' ? instance.rule : {};
      const existingStacking = existingRule.stacking && typeof existingRule.stacking === 'object' ? existingRule.stacking : {};
      const existingDefinitionId = String(instance.definition_id || existingStacking.key || existingRule.id || '');
      if (existingDefinitionId !== definitionId || int(instance.owner_slot) !== ownerSlot) continue;
      if (mode === 'independent') continue;
      if (mode === 'add_stack') {
        if (stacking.unique_source_slots) {
          const sourceSlot = int(context.source_slot, -1);
          const sourceSlots = new Set(asList(instance.source_slots).map(int));
          if (sourceSlots.has(sourceSlot)) return null;
          sourceSlots.add(sourceSlot);
          instance.source_slots = Array.from(sourceSlots);
        }
        instance.stack_count = Math.min(maxStacks, Math.max(0, num(instance.stack_count, 1)) + gain);
        instance.start_tick = Math.min(int(instance.start_tick, startTick), startTick);
        instance.end_tick = endTick;
        instance.rule = rule;
        instance.name = rule.name || instance.name || '';
        return instance;
      }
      if (mode === 'extend') {
        instance.end_tick = Math.max(int(instance.end_tick), endTick);
        return instance;
      }
      instance.start_tick = startTick;
      instance.end_tick = endTick;
      instance.stack_count = Math.min(maxStacks, Math.max(1, gain));
      instance.excluded_step_id = context.exclude_trigger_action ? String(context.source_step_id || '') : '';
      return instance;
    }
    if (mode === 'independent') {
      const copyCount = Math.max(1, Math.floor(gain));
      let latestInstance = null;
      for (let copyIndex = 0; copyIndex < copyCount; copyIndex += 1) {
        const siblings = activeBuffs
          .filter((instance) => String(instance.definition_id || '') === definitionId && int(instance.owner_slot) === ownerSlot)
          .sort((left, right) => int(left.end_tick) - int(right.end_tick) || int(left.start_tick) - int(right.start_tick));
        while (siblings.length >= Math.floor(maxStacks)) {
          const expiringFirst = siblings.shift();
          const index = activeBuffs.indexOf(expiringFirst);
          if (index >= 0) activeBuffs.splice(index, 1);
        }
        latestInstance = {
          rule,
          definition_id: definitionId,
          name: rule.name || '',
          owner_slot: ownerSlot,
          start_tick: startTick,
          end_tick: endTick,
          stack_count: 1,
          excluded_step_id: context.exclude_trigger_action ? String(context.source_step_id || '') : '',
        };
        if (stacking.unique_source_slots) latestInstance.source_slots = [int(context.source_slot, -1)];
        activeBuffs.push(latestInstance);
      }
      return latestInstance;
    }
    const instance = {
      rule,
      definition_id: definitionId,
      name: rule.name || '',
      owner_slot: ownerSlot,
      start_tick: startTick,
      end_tick: endTick,
      stack_count: Math.min(maxStacks, mode === 'add_stack' ? gain : Math.max(1, gain)),
      excluded_step_id: context.exclude_trigger_action ? String(context.source_step_id || '') : '',
    };
    if (stacking.unique_source_slots) instance.source_slots = [int(context.source_slot, -1)];
    activeBuffs.push(instance);
    return instance;
  }

  function buffEffects(instance, context = {}) {
    const effects = instance.rule?.effects && typeof instance.rule.effects === 'object' ? instance.rule.effects : {};
    const factor = Math.max(0, num(instance.stack_count, 1));
    const resolved = Object.fromEntries(Object.entries(effects).filter(([, value]) => num(value) !== 0).map(([key, value]) => [key, num(value) * factor]));
    const dynamic = instance.rule?.dynamic_effects && typeof instance.rule.dynamic_effects === 'object'
      ? instance.rule.dynamic_effects
      : {};
    const negative = dynamic.negative_effect_count && typeof dynamic.negative_effect_count === 'object'
      ? dynamic.negative_effect_count
      : {};
    if (negative.effect_key) {
      const enemyDebuffs = new Set(Object.keys(context.enemy_debuffs || {}));
      const activeKeys = new Set(asList(context.active_buff_keys).map(String));
      const count = Math.min(
        Math.max(0, int(negative.max_count, 1)),
        asList(negative.enemy_debuffs).filter((key) => enemyDebuffs.has(String(key))).length
          + asList(negative.buff_keys).filter((key) => activeKeys.has(String(key))).length,
      );
      resolved[String(negative.effect_key)] = num(resolved[String(negative.effect_key)]) + count * num(negative.per_count);
    }
    const activeStack = dynamic.active_stack_count && typeof dynamic.active_stack_count === 'object'
      ? dynamic.active_stack_count
      : {};
    if (activeStack.effect_key && activeStack.key) {
      const count = Math.min(
        Math.max(0, int(activeStack.max_count, 1)),
        asList(context.active_buffs)
          .filter((buff) => String(buff.definition_id || '') === String(activeStack.key))
          .reduce((sum, buff) => sum + Math.max(0, num(buff.stack_count, 1)), 0),
      );
      resolved[String(activeStack.effect_key)] = num(resolved[String(activeStack.effect_key)]) + count * num(activeStack.per_count);
    }
    const elapsed = dynamic.elapsed_ticks && typeof dynamic.elapsed_ticks === 'object' ? dynamic.elapsed_ticks : {};
    if (elapsed.effect_key) {
      const intervals = Math.max(0, Math.floor((num(context.tick) - int(instance.start_tick)) / Math.max(1, int(elapsed.interval_ticks, 10))));
      resolved[String(elapsed.effect_key)] = num(resolved[String(elapsed.effect_key)])
        + Math.min(num(elapsed.max_value, Number.POSITIVE_INFINITY), intervals * num(elapsed.per_interval));
    }
    return Object.fromEntries(Object.entries(resolved).filter(([, value]) => num(value) !== 0));
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

  function buffSummary(instance, context = {}) {
    const rule = instance.rule && typeof instance.rule === 'object' ? instance.rule : {};
    const stackCount = Math.max(0, num(instance.stack_count, 1));
    const displayAsLine = buffDisplaysAsLine(rule);
    return {
      rule_id: rule.id || '',
      definition_id: String(instance.definition_id || rule.stacking?.key || rule.id || ''),
      name: rule.name || '',
      provider_name: rule.provider_name || '',
      owner_slot: int(instance.owner_slot),
      start_tick: int(instance.start_tick),
      end_tick: int(instance.end_tick),
      duration_ticks: String(rule.duration?.type || '') === 'permanent'
        ? PERMANENT_BUFF_END_TICK
        : Math.max(0, int(rule.duration?.ticks)),
      stack_count: Number.isInteger(stackCount) ? Math.trunc(stackCount) : stackCount,
      effects: buffEffects(instance, context),
      display_as_line: displayAsLine,
      line_hidden_reason: displayAsLine ? '' : (String(rule.duration?.type || '') === 'permanent' ? 'passive' : 'self_action'),
    };
  }

  function activeBuffApplies(instance, step, action, snapshot, isBackground, context = {}) {
    if (instance.excluded_step_id && String(instance.excluded_step_id) === String(step?.id || '')) {
      return false;
    }
    const target = instance.rule?.target && typeof instance.rule.target === 'object' ? instance.rule.target : {};
    return targetMatches(target, instance, step, action, snapshot, isBackground, context);
  }

  function applicableBuffContributions(activeBuffs, step, action, snapshot, isBackground, context = {}) {
    const contributions = activeBuffs
      .filter((buff) => (
        int(context.tick) >= int(buff.start_tick)
        && int(context.tick) < int(buff.end_tick)
        && activeBuffApplies(buff, step, action, snapshot, isBackground, context)
      ))
      .map((buff) => {
        const effects = buffEffects(buff, context);
        return {
          buff,
          effects,
          uniqueKey: String(buff.rule?.calculation?.team_unique_key || ''),
          magnitude: Object.values(effects).reduce((sum, value) => sum + Math.max(0, num(value)), 0),
        };
      });
    const selected = [];
    const highestByUniqueKey = new Map();
    contributions.forEach((contribution) => {
      if (!contribution.uniqueKey) {
        selected.push(contribution);
        return;
      }
      const current = highestByUniqueKey.get(contribution.uniqueKey);
      if (!current || contribution.magnitude > current.magnitude) {
        highestByUniqueKey.set(contribution.uniqueKey, contribution);
      }
    });
    selected.push(...highestByUniqueKey.values());
    return selected;
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
    scheduled.calculation_start_sequence = Math.max(0, int(startSequence));
    scheduled.calculation_end_sequence = Math.max(scheduled.calculation_start_sequence + 1, int(endSequence));
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
    let qVirtualIntervals = [];
    qEvents.forEach((qEvent) => {
      const qStartTick = int(qEvent.visual_start_tick, int(qEvent.start_tick));
      const qCalculationStartTick = calculationTickFromVisualIntervals(qStartTick, qVirtualIntervals);
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
        const inQColumn = int(scheduled.slot) !== qSlot && startTick < qStartTick && qStartTick < endTick;
        const ongoingForeground = !scheduled.is_background && startTick < qStartTick && qStartTick < endTick;
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
      qVirtualIntervals = normalizeFrozenIntervals(qVirtualIntervals.concat([{
        start_tick: qStartTick,
        end_tick: Math.max(qStartTick + ZERO_ACTION_VISUAL_TICKS, int(qEvent.visual_end_tick, qStartTick + ZERO_ACTION_VISUAL_TICKS)),
      }]));
    });
    recalculateTimingsFromFrozenIntervals(scheduledSteps, qVirtualIntervals);
    scheduledSteps.forEach((scheduled) => {
      if (!scheduled.q_instant_release) return;
      const qCalculationTick = calculationTickFromVisualIntervals(
        int(scheduled.q_instant_release_anchor_tick),
        qVirtualIntervals,
      );
      scheduled.q_instant_release_calculation_tick = qCalculationTick;
    });
    return qVirtualIntervals;
  }

  function clearQInstantReleaseState(scheduledSteps) {
    scheduledSteps.forEach((scheduled) => {
      [
        'q_instant_release_kind',
        'q_instant_release_tick',
        'q_instant_release_anchor_tick',
        'q_instant_release_calculation_tick',
        'q_instant_release_anchor_step_id',
        'q_instant_release_start_sequence',
        'q_instant_release_end_sequence',
        'q_cover_visual_end_tick',
        'q_cover_target_step_ids',
      ].forEach((key) => delete scheduled[key]);
      scheduled.q_instant_release = false;
      scheduled.calculation_start_sequence = 0;
      scheduled.calculation_end_sequence = 0;
      if (isZeroForegroundQStep(scheduled.step || {}, scheduled.action || {})) {
        scheduled.visual_end_tick = int(scheduled.visual_start_tick) + qVisualDurationTicks(scheduled.action || {});
      }
    });
  }

  function enforceExpandedForegroundLocks(scheduledSteps, switchGapTicks) {
    let shiftedAny = false;
    const foregroundLocks = [];
    let previousForegroundSlot = null;
    let previousForegroundStartTick = null;
    const carriedShiftBySlot = new Map();
    const ordered = scheduledSteps.slice().sort((left, right) => {
      const startDelta = int(left.visual_start_tick) - int(right.visual_start_tick);
      if (startDelta) return startDelta;
      const lockDelta = Number(locksForegroundSwitch(right.step || {}, right.action || {})) -
        Number(locksForegroundSwitch(left.step || {}, left.action || {}));
      return lockDelta || int(left.slot) - int(right.slot);
    });
    ordered.forEach((scheduled) => {
      const slot = int(scheduled.slot);
      const carriedShiftTicks = Math.max(0, int(carriedShiftBySlot.get(slot)));
      if (carriedShiftTicks > 0) {
        scheduled.visual_start_tick = int(scheduled.visual_start_tick) + carriedShiftTicks;
        scheduled.visual_end_tick = int(scheduled.visual_end_tick) + carriedShiftTicks;
        shiftedAny = true;
      }
      if (scheduled.is_background || scheduled.q_instant_release) return;
      const originalStartTick = int(scheduled.visual_start_tick);
      let visualStartTick = originalStartTick;
      let lockEndTick = Math.max(
        0,
        ...foregroundLocks
          .filter((lock) => visualStartTick < int(lock.end_tick))
          .map((lock) => int(lock.end_tick)),
      );
      while (lockEndTick > visualStartTick) {
        visualStartTick = lockEndTick;
        lockEndTick = Math.max(
          0,
          ...foregroundLocks
            .filter((lock) => visualStartTick < int(lock.end_tick))
            .map((lock) => int(lock.end_tick)),
        );
      }
      if (
        previousForegroundSlot !== null &&
        previousForegroundSlot !== int(scheduled.slot) &&
        previousForegroundStartTick !== null
      ) {
        visualStartTick = Math.max(
          visualStartTick,
          previousForegroundStartTick + Math.max(0, int(switchGapTicks)),
        );
      }
      if (visualStartTick > originalStartTick) {
        const shiftTicks = visualStartTick - originalStartTick;
        scheduled.visual_start_tick = visualStartTick;
        scheduled.visual_end_tick = int(scheduled.visual_end_tick) + shiftTicks;
        scheduled.foreground_lock_ticks = Math.max(0, int(scheduled.foreground_lock_ticks)) + shiftTicks;
        carriedShiftBySlot.set(slot, Math.max(0, int(carriedShiftBySlot.get(slot))) + shiftTicks);
        shiftedAny = true;
      }
      previousForegroundSlot = int(scheduled.slot);
      previousForegroundStartTick = int(scheduled.visual_start_tick);
      if (locksForegroundSwitch(scheduled.step || {}, scheduled.action || {})) {
        foregroundLocks.push({
          slot: int(scheduled.slot),
          end_tick: isZeroForegroundQStep(scheduled.step || {}, scheduled.action || {})
            ? int(scheduled.visual_end_tick)
            : int(scheduled.visual_start_tick) + qVisualDurationTicks(scheduled.action || {}),
        });
      }
    });
    return shiftedAny;
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
    const switchLossTicks = Math.max(
      0,
      int(options.switch_gap_ticks, int(options.switch_loss_ticks, int(catalog.formula_constants?.switch_loss_ticks, 2))),
    );
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
    const orderedStepEntries = tickScheduledStepEntries(steps, actionsById, switchLossTicks);
    const scheduledSteps = [];
    const loopOpeningFrontSlot = options.loop_enabled
      ? orderedStepEntries
        .filter(({ step }) => startsForeground(step, actionsById.get(String(step.action_id || '')) || {}))
        .map(({ step }) => int(step.slot))
        .at(-1) ?? null
      : null;
    let scheduleFrontSlot = loopOpeningFrontSlot;
    orderedStepEntries.forEach(({
      step,
      visualStartTick: scheduledVisualStartTick,
      switchLossTicks: switchLossDelta,
      foregroundLockTicks,
    }) => {
      const slot = int(step.slot);
      const snapshot = snapshots.get(slot);
      if (!snapshot) return;
      const action = actionsById.get(String(step.action_id || ''));
      const visualStartTick = scheduledVisualStartTick;
      const isBackground = isStepBackground(step, action);
      const configuredDurationTicks = Math.max(0, int(action.duration_ticks));
      const visualEndTick = visualStartTick + (configuredDurationTicks > 0 ? configuredDurationTicks : ZERO_ACTION_VISUAL_TICKS);
      scheduledSteps.push({
        step,
        slot,
        action,
        previous_front_slot: scheduleFrontSlot,
        start_tick: visualStartTick,
        calculation_start_sequence: 0,
        visual_start_tick: visualStartTick,
        switch_loss_ticks: switchLossDelta,
        foreground_lock_ticks: Math.max(0, int(foregroundLockTicks)),
        is_background: isBackground,
        is_basic_background: isBasicBackgroundOverride(step, action),
        can_background_override: canBackgroundOverride(action),
        duration_ticks: configuredDurationTicks,
        end_tick: visualEndTick,
        calculation_end_sequence: 0,
        visual_end_tick: visualEndTick,
        original_start_tick: visualStartTick,
        original_calculation_start_sequence: 0,
        original_duration_ticks: configuredDurationTicks,
        original_end_tick: visualEndTick,
        original_calculation_end_sequence: 0,
        original_visual_end_tick: visualEndTick,
      });
      if (!isBackground) {
        scheduleFrontSlot = slot;
      }
    });
    let qVirtualIntervals = applyQInstantRelease(scheduledSteps);
    for (let pass = 0; pass < scheduledSteps.length; pass += 1) {
      if (!enforceExpandedForegroundLocks(scheduledSteps, switchLossTicks)) break;
      clearQInstantReleaseState(scheduledSteps);
      qVirtualIntervals = applyQInstantRelease(scheduledSteps);
    }
    scheduledSteps.sort((left, right) => (
      int(left.visual_start_tick) - int(right.visual_start_tick) ||
      int(left.slot) - int(right.slot)
    ));
    scheduleFrontSlot = loopOpeningFrontSlot;
    scheduledSteps.forEach((scheduled) => {
      scheduled.previous_front_slot = scheduleFrontSlot;
      if (!scheduled.is_background) scheduleFrontSlot = int(scheduled.slot);
    });
    const scheduledLastTick = Math.max(0, ...scheduledSteps.map((item) => Math.max(int(item.end_tick), int(item.start_tick))));
    const loopDurationTicks = Math.max(scheduledLastTick, 1);
    const loopPrimedReactionStepIds = new Set();

    function supportBypassesHarmony(scheduled) {
      return Boolean(
        scheduled?.step?.ignore_harmony_requirement ||
        scheduled?.action?.ignore_harmony_requirement ||
        scheduled?.action?.reaction_without_harmony ||
        requiemFreeSupportSource(scheduled)
      );
    }

    function requiemFreeSupportSource(scheduled) {
      if (!isSupportAction(scheduled?.action)) return null;
      const snapshot = snapshots.get(int(scheduled?.slot));
      if (String(snapshot?.character?.id || '') !== 'char_c78f7a08d5' || !hasAwakeningNode(snapshot, 6)) return null;
      const supportTick = int(scheduled?.start_tick);
      return scheduledSteps
        .filter((candidate) => (
          int(candidate?.slot) === int(scheduled?.slot)
          && ['action_2745f804a5', 'action_7af75245df', 'action_0b958faf88'].includes(String(candidate?.action?.id || ''))
          && int(candidate?.start_tick) <= supportTick
          && supportTick - int(candidate?.start_tick) <= 50
        ))
        .sort((left, right) => int(right?.start_tick) - int(left?.start_tick))[0] || null;
    }

    function reactionPreviousSlot(scheduled) {
      return int(requiemFreeSupportSource(scheduled)?.previous_front_slot, int(scheduled?.previous_front_slot, -1));
    }

    function reactionTriggerTick(scheduled, offsetTicks = 0) {
      const visualStartTick = int(scheduled?.visual_start_tick, int(scheduled?.start_tick));
      const visualEndTick = int(scheduled?.visual_end_tick, int(scheduled?.end_tick, visualStartTick));
      return Math.max(visualStartTick, visualEndTick - 2) + int(offsetTicks);
    }

    if (options.loop_enabled) {
      const warmHarmony = new Map(Array.from(snapshots.keys()).map((slot) => [slot, 0]));
      for (let warmLoopIndex = 0; warmLoopIndex < 3; warmLoopIndex += 1) {
        const iterationReactionStepIds = new Set();
        scheduledSteps.forEach((scheduled) => {
          const slot = int(scheduled.slot);
          warmHarmony.set(
            slot,
            (warmHarmony.get(slot) || 0) + num(scheduled.action?.harmony) * backgroundActionMultiplier(scheduled.step, scheduled.action),
          );
          if (!isSupportAction(scheduled.action)) return;
          const previousSnapshot = snapshots.get(reactionPreviousSlot(scheduled));
          const supportSnapshot = snapshots.get(slot);
          if (!previousSnapshot || !supportSnapshot || previousSnapshot.slot === supportSnapshot.slot) return;
          if (!reactionForElements(previousSnapshot.character?.element, supportSnapshot.character?.element)) return;
          const previousHarmony = warmHarmony.get(previousSnapshot.slot) || 0;
          if (previousHarmony < 100 && !supportBypassesHarmony(scheduled)) return;
          iterationReactionStepIds.add(String(scheduled.step?.id || ''));
          if (!scheduled.action?.preserve_harmony && !scheduled.step?.preserve_harmony) {
            warmHarmony.set(previousSnapshot.slot, Math.max(0, previousHarmony - 100));
          }
        });
        if (warmLoopIndex === 2) {
          iterationReactionStepIds.forEach((stepId) => loopPrimedReactionStepIds.add(stepId));
        }
      }
      warmHarmony.forEach((value, slot) => harmonyBySlot.set(slot, value));
    }
    let activeBuffs = [];
    const buffTriggerCooldowns = new Map();
    const reactionEffects = [];
    const reactionDamageEvents = [];
    const reactionDamageBySlot = new Map(Array.from(snapshots.keys()).map((slot) => [slot, 0]));
    let nextReactionEffectId = 1;

    function effectiveReactionPanel(snapshot, tick) {
      const panelMods = clone(snapshot.mods);
      const syntheticStep = { slot: snapshot.slot };
      const syntheticAction = {
        name: '异能环合',
        action_type: '环合',
        damage_type: '环合',
        tags: ['环合'],
      };
      const activeAtTick = activeBuffs.filter((candidate) => tick >= int(candidate.start_tick) && tick < int(candidate.end_tick));
      const context = {
        enemy,
        tick,
        enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, tick),
        active_buffs: activeAtTick,
        active_buff_keys: activeAtTick.map((candidate) => String(candidate.definition_id || '')),
      };
      applicableBuffContributions(activeBuffs, syntheticStep, syntheticAction, snapshot, false, context)
        .forEach((contribution) => mergeMods(panelMods, contribution.effects));
      return panelMods;
    }

    function reactionContributor(reaction, previousSnapshot, supportSnapshot, tick) {
      const candidates = [previousSnapshot, supportSnapshot].filter(Boolean);
      if (!candidates.length) return null;
      let selected = candidates[candidates.length - 1];
      let selectedScore = -1;
      candidates.forEach((snapshot) => {
        const panelMods = effectiveReactionPanel(snapshot, tick);
        const score = reactionBaseDamage(snapshot.character?.level, reaction) *
          reactionStrengthMultiplier(panelMods.harmony_strength);
        if (score > selectedScore || (score === selectedScore && snapshot.slot === supportSnapshot?.slot)) {
          selected = snapshot;
          selectedScore = score;
        }
      });
      return selected;
    }

    function reactionDamageTicks(reaction, startTick) {
      if (reaction === '创生') return [20, 40, 60, 80, 100].map((offset) => startTick + offset);
      if (reaction === '浊燃') return Array.from({ length: 15 }, (_, index) => startTick + (index + 1) * 10);
      if (reaction === '黯星') return [startTick + 50];
      return [];
    }

    function triggerReaction(scheduled, tick, { primeLoop = false } = {}) {
      if (!isSupportAction(scheduled.action)) return { effect: null, warning: '' };
      const supportSnapshot = snapshots.get(int(scheduled.slot));
      const previousSnapshot = snapshots.get(reactionPreviousSlot(scheduled));
      if (!supportSnapshot || !previousSnapshot) {
        return {
          effect: null,
          warning: primeLoop ? '' : '援护技前没有可用于触发环合的前台角色。',
        };
      }
      if (supportSnapshot.slot === previousSnapshot.slot) {
        return {
          effect: null,
          warning: primeLoop ? '' : '援护技没有切换角色，无法触发异能环合。',
        };
      }
      const reaction = reactionForElements(previousSnapshot.character?.element, supportSnapshot.character?.element);
      if (!reaction) {
        return {
          effect: null,
          warning: primeLoop
            ? ''
            : `${previousSnapshot.character?.element || '无属性'}与${supportSnapshot.character?.element || '无属性'}无法产生异能环合。`,
        };
      }
      if (primeLoop && !loopPrimedReactionStepIds.has(String(scheduled.step?.id || ''))) {
        return { effect: null, warning: '' };
      }
      const previousHarmony = harmonyBySlot.get(previousSnapshot.slot) || 0;
      if (!primeLoop && previousHarmony < 100 && !supportBypassesHarmony(scheduled)) {
        return {
          effect: null,
          warning: `${previousSnapshot.character?.name || '上一前台角色'}环合值不足：需要 100，当前 ${Math.max(0, previousHarmony).toFixed(1)}。`,
        };
      }
      const contributor = reactionContributor(reaction, previousSnapshot, supportSnapshot, tick);
      if (!contributor) return { effect: null, warning: '' };
      if (!primeLoop && !scheduled.action?.preserve_harmony && !scheduled.step?.preserve_harmony) {
        harmonyBySlot.set(previousSnapshot.slot, Math.max(0, previousHarmony - 100));
      }
      const durationTicks = int(REACTION_DURATIONS[reaction]);
      const effect = {
        id: `reaction_${nextReactionEffectId}`,
        reaction,
        support_slot: supportSnapshot.slot,
        support_character_id: supportSnapshot.character?.id || '',
        support_character_name: supportSnapshot.character?.name || '',
        previous_slot: previousSnapshot.slot,
        previous_character_id: previousSnapshot.character?.id || '',
        previous_character_name: previousSnapshot.character?.name || '',
        trigger_slot: contributor.slot,
        trigger_character_id: contributor.character?.id || '',
        trigger_character_name: contributor.character?.name || '',
        contributor_slot: contributor.slot,
        contributor_character_id: contributor.character?.id || '',
        contributor_character_name: contributor.character?.name || '',
        start_tick: tick,
        end_tick: tick + durationTicks,
        duration_ticks: durationTicks,
        damage_ticks: reactionDamageTicks(reaction, tick),
        loop_primed: primeLoop,
      };
      nextReactionEffectId += 1;
      reactionEffects.push(effect);
      effect.damage_ticks.forEach((damageTick, index) => {
        reactionDamageEvents.push({
          effect_id: effect.id,
          reaction,
          tick: damageTick,
          sequence: index + 1,
          trigger_slot: effect.trigger_slot,
          contributor_slot: effect.contributor_slot,
          contributor_character_id: effect.contributor_character_id,
          contributor_character_name: effect.contributor_character_name,
          loop_primed: primeLoop,
          damage: null,
        });
      });
      return { effect, warning: '' };
    }

    function reactionDamageAtTick(event) {
      const snapshot = snapshots.get(int(event.contributor_slot));
      if (!snapshot) return 0;
      if (event.kind === 'buff_periodic' || event.kind === 'buff_periodic_settlement') {
        if (event.kind === 'buff_periodic' && event._buff_instance && !activeBuffs.includes(event._buff_instance)) return 0;
        const panelMods = effectiveReactionPanel(snapshot, int(event.tick));
        const atk = num(snapshot.base_stats?.atk) * (1 + panelMods.atk_pct) + panelMods.flat_atk;
        const base = atk * num(event.atk_multiplier);
        const damageBonus = panelMods.all_dmg + panelMods.element_dmg;
        const critical = 1 + 0.5 * Math.max(0, num(panelMods.crit_dmg));
        const defense = defenseMultiplier(enemy, panelMods);
        const resistance = resistanceMultiplier(snapshot.character, enemy, panelMods);
        const finalMultiplier = 1 + panelMods.final_dmg;
        event.formula_parts = { base, damage_bonus: damageBonus, critical, defense, resistance, final_multiplier: finalMultiplier };
        return Math.max(0, base * (1 + damageBonus) * critical * defense * resistance * finalMultiplier);
      }
      const panelMods = effectiveReactionPanel(snapshot, int(event.tick));
      const base = reactionBaseDamage(snapshot.character?.level, event.reaction);
      const strength = reactionStrengthMultiplier(panelMods.harmony_strength);
      const defense = event.reaction === '黯星' ? 1 : defenseMultiplier(enemy, panelMods);
      const resistanceCharacter = event.reaction === '黯星' ? { element: '' } : snapshot.character;
      const resistance = resistanceMultiplier(resistanceCharacter, enemy, panelMods);
      const critical = event.reaction === '浊燃' ? 1 + 0.5 * Math.max(0, num(panelMods.crit_dmg)) : 1;
      event.formula_parts = { base, strength, defense, critical, resistance };
      return Math.max(0, base * strength * defense * critical * resistance);
    }

    function settleReactionDamage(untilTick) {
      reactionDamageEvents
        .filter((event) => event.damage == null && int(event.tick) >= 0 && int(event.tick) <= untilTick)
        .sort((a, b) => int(a.tick) - int(b.tick) || int(a.sequence) - int(b.sequence))
        .forEach((event) => {
          event.damage = reactionDamageAtTick(event);
          directDamage += event.damage;
          specialDamageBySource.set(event.reaction, (specialDamageBySource.get(event.reaction) || 0) + event.damage);
          reactionDamageBySlot.set(
            int(event.contributor_slot),
            (reactionDamageBySlot.get(int(event.contributor_slot)) || 0) + event.damage,
          );
        });
    }

    function schedulePeriodicBuffDamage(instance, rule) {
      const periodic = rule.periodic_damage && typeof rule.periodic_damage === 'object' ? rule.periodic_damage : {};
      const intervalTicks = Math.max(1, int(periodic.interval_ticks));
      const source = String(periodic.source || rule.name || '周期伤害');
      if (!periodic.atk_multiplier || !intervalTicks) return;
      let sequence = 1;
      for (
        let damageTick = int(instance.start_tick) + intervalTicks;
        damageTick <= int(instance.end_tick);
        damageTick += intervalTicks
      ) {
        reactionDamageEvents.push({
          kind: 'buff_periodic',
          reaction: source,
          tick: damageTick,
          sequence,
          contributor_slot: int(instance.owner_slot),
          contributor_character_id: String(rule.owner_character_id || ''),
          contributor_character_name: String(rule.owner_character_name || ''),
          atk_multiplier: num(periodic.atk_multiplier),
          _buff_instance: instance,
          damage: null,
        });
        sequence += 1;
      }
    }

    function reactionAmplificationMultiplier(snapshot, calcPanel, tick) {
      let multiplier = 1;
      reactionEffects.forEach((effect) => {
        if (tick < int(effect.start_tick) || tick >= int(effect.end_tick)) return;
        const element = String(snapshot.character?.element || '');
        if (effect.reaction === '浸染' && ['魂', '相'].includes(element)) {
          multiplier *= 1.2 * reactionStrengthMultiplier(calcPanel?.harmony_strength);
        }
        if (effect.reaction === '覆纹' && ['灵', '咒'].includes(element)) {
          multiplier *= 1.2 * reactionStrengthMultiplier(calcPanel?.harmony_strength);
        }
      });
      return multiplier;
    }

    buffRules.forEach((rule) => {
      if (String(rule.trigger?.event || '') !== 'passive') return;
      const snapshot = snapshots.get(int(rule.owner_slot));
      if (!snapshot) return;
      const context = {
        enemy,
        snapshot,
        tick: 0,
        owner_awakening: rule.owner_awakening,
        owner_awakening_nodes: rule.owner_awakening_nodes,
        enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, 0),
        fons_full: fonsFull,
      };
      if (!conditionsMatch(rule.trigger?.conditions, context)) return;
      activateBuff(activeBuffs, rule, 0, stackGainForRule(rule, context), context);
    });

    function triggerTickForRule(rule, startTick, endTick) {
      return String(rule.trigger?.event || '') === 'action_end' ? endTick : startTick;
    }

    function triggerBuffsForEvent(event, triggerTick, step, action, snapshot, isBackground, extraContext = {}) {
      const triggered = [];
      const baseContext = Object.assign({
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
        const ownerSlot = int(rule.owner_slot);
        const ownerBuffs = activeBuffs.filter((instance) => (
          int(instance.owner_slot) === ownerSlot
          && triggerTick >= int(instance.start_tick)
          && triggerTick < int(instance.end_tick)
        ));
        const context = Object.assign({}, baseContext, {
          owner_slot: ownerSlot,
          owner_character_id: String(rule.owner_character_id || ''),
          active_buff_keys: ownerBuffs.map((instance) => String(instance.definition_id || '')),
          shield_active: activeBuffs.some((instance) => (
            asList(instance.rule?.tags).map(String).includes('护盾')
            && triggerTick >= int(instance.start_tick)
            && triggerTick < int(instance.end_tick)
            && activeBuffApplies(instance, step, action, snapshot, isBackground, baseContext)
          )),
          source_slot: int(step.slot),
          source_step_id: String(step.id || ''),
          exclude_trigger_action: Boolean(rule.activation?.exclude_trigger_action),
        });
        if (!eventMatchesRule(rule, event, step, action, snapshot, isBackground, context)) return;
        const cooldownTicks = triggerCooldownTicks(rule);
        const cooldownKey = `${int(rule.owner_slot)}:${String(rule.id || '')}`;
        if (cooldownTicks > 0 && triggerTick < (buffTriggerCooldowns.get(cooldownKey) || 0)) return;
        const activation = rule.activation && typeof rule.activation === 'object' ? rule.activation : {};
        const runtimeRule = clone(rule);
        const stackSourceKey = String(activation.effects_from_stack?.key || '');
        const stackSource = ownerBuffs.find((instance) => String(instance.definition_id || '') === stackSourceKey);
        if (stackSourceKey) {
          const sourceStacks = Math.max(0, num(stackSource?.stack_count));
          const sourceEffects = runtimeRule.effects && typeof runtimeRule.effects === 'object' ? runtimeRule.effects : {};
          const fullEffectKeys = new Set(asList(activation.effects_from_stack?.full_effect_keys).map(String));
          const perStackEntries = Object.entries(activation.effects_from_stack?.per_stack_from_effect || {});
          const helperEffectKeys = new Set(perStackEntries
            .map(([targetKey, config]) => String(config?.source || targetKey))
            .filter((sourceKey, index) => sourceKey !== String(perStackEntries[index]?.[0] || '')));
          const resolvedEffects = Object.fromEntries(Object.entries(sourceEffects)
            .filter(([key]) => !fullEffectKeys.has(key) && !helperEffectKeys.has(key)));
          perStackEntries.forEach(([targetKey, config]) => {
            const sourceKey = String(config?.source || targetKey);
            resolvedEffects[targetKey] = num(resolvedEffects[targetKey]) + num(sourceEffects[sourceKey]) * num(config?.factor, 1) * sourceStacks;
          });
          if (sourceStacks >= Math.max(1, int(activation.effects_from_stack?.full_stacks, 1))) {
            fullEffectKeys.forEach((key) => {
              resolvedEffects[key] = num(sourceEffects[key]);
            });
          }
          runtimeRule.effects = resolvedEffects;
          runtimeRule.consumed_stacks = sourceStacks;
        }
        const ownerBase = activation.effects_from_owner_base && typeof activation.effects_from_owner_base === 'object'
          ? activation.effects_from_owner_base
          : {};
        if (ownerBase.effect_key && ownerBase.stat) {
          const ownerSnapshot = snapshots.get(ownerSlot);
          runtimeRule.effects = Object.assign({}, runtimeRule.effects, {
            [String(ownerBase.effect_key)]: num(ownerSnapshot?.base_stats?.[String(ownerBase.stat)]) * num(ownerBase.factor, 1),
          });
        }
        const settlementKey = String(activation.settle_periodic_key || '');
        if (settlementKey) {
          ownerBuffs
            .filter((instance) => String(instance.definition_id || '') === settlementKey)
            .forEach((instance, index) => {
              const periodic = instance.rule?.periodic_damage && typeof instance.rule.periodic_damage === 'object'
                ? instance.rule.periodic_damage
                : {};
              reactionDamageEvents.push({
                kind: 'buff_periodic_settlement',
                reaction: String(periodic.source || instance.name || '周期伤害'),
                tick: triggerTick,
                sequence: index + 1,
                contributor_slot: ownerSlot,
                contributor_character_id: String(rule.owner_character_id || ''),
                contributor_character_name: String(rule.owner_character_name || ''),
                atk_multiplier: num(periodic.atk_multiplier),
                damage: null,
              });
            });
        }
        asList(activation.clear_keys).map(String).forEach((key) => {
          activeBuffs = activeBuffs.filter((instance) => int(instance.owner_slot) !== ownerSlot || String(instance.definition_id || '') !== key);
        });
        const previousInstances = new Set(activeBuffs);
        const instance = activateBuff(activeBuffs, runtimeRule, triggerTick, stackGainForRule(runtimeRule, context), context);
        if (!instance) return;
        activeBuffs
          .filter((candidate) => !previousInstances.has(candidate) && candidate.rule?.periodic_damage)
          .forEach((candidate) => schedulePeriodicBuffDamage(candidate, candidate.rule));
        if (cooldownTicks > 0) buffTriggerCooldowns.set(cooldownKey, triggerTick + cooldownTicks);
        const summary = buffSummary(instance);
        summary.trigger_event = event;
        summary.trigger_tick = triggerTick;
        const visualTriggerTick = int(extraContext.visual_trigger_tick, visualTickFromCalculationTick(triggerTick, qVirtualIntervals));
        summary.visual_start_tick = int(summary.start_tick) === triggerTick
          ? visualTriggerTick
          : visualTickFromCalculationTick(int(summary.start_tick), qVirtualIntervals);
        summary.visual_end_tick = String(runtimeRule.duration?.type || '') === 'permanent'
          ? PERMANENT_BUFF_END_TICK
          : visualTickFromCalculationTick(int(summary.end_tick), qVirtualIntervals);
        summary.display_start_tick = summary.visual_start_tick;
        summary.display_end_tick = summary.visual_end_tick;
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
        const startTick = int(scheduled.start_tick);
        const endTick = int(scheduled.end_tick);
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
          const actionMultiplier = backgroundActionMultiplier(step, action);
          for (let copyIndex = 0; copyIndex < actionMultiplier; copyIndex += 1) {
            const instance = activateBuff(activeBuffs, rule, triggerTick - loopDurationTicks, stackGainForRule(rule, context), context);
            if (instance) {
              instance.start_tick = Math.max(0, int(instance.start_tick));
              instance.looped = true;
            }
          }
        });
      });
      scheduledSteps.forEach((scheduled) => {
        const reactionTick = calculationTickFromVisualIntervals(reactionTriggerTick(scheduled), qVirtualIntervals);
        triggerReaction(
          scheduled,
          reactionTick - loopDurationTicks,
          { primeLoop: true },
        );
      });
    }

    let lastTick = 0;
    let runtimeFrontSlot = options.loop_enabled ? loopOpeningFrontSlot : null;
    let runtimeFrontSinceTick = 0;

    function syncFrontTimeBuffs(tick) {
      buffRules
        .filter((rule) => String(rule.trigger?.event || '') === 'front_time')
        .forEach((rule) => {
          const ownerSlot = int(rule.owner_slot);
          const stacking = rule.stacking && typeof rule.stacking === 'object' ? rule.stacking : {};
          const definitionId = String(stacking.key || rule.id || '');
          const intervalTicks = Math.max(1, int(stacking.interval_ticks, 10));
          const maxStacks = Math.max(1, int(stacking.max_stacks, 1));
          const stackCount = ownerSlot === runtimeFrontSlot
            ? Math.min(maxStacks, Math.max(0, Math.floor((tick - runtimeFrontSinceTick) / intervalTicks)))
            : 0;
          const existing = activeBuffs.find(
            (instance) => int(instance.owner_slot) === ownerSlot && String(instance.definition_id || '') === definitionId,
          );
          if (stackCount <= 0) {
            if (existing) activeBuffs.splice(activeBuffs.indexOf(existing), 1);
            return;
          }
          if (existing) {
            existing.stack_count = stackCount;
            existing.end_tick = PERMANENT_BUFF_END_TICK;
            return;
          }
          activeBuffs.push({
            rule,
            definition_id: definitionId,
            name: rule.name || '',
            owner_slot: ownerSlot,
            start_tick: runtimeFrontSinceTick + intervalTicks,
            end_tick: PERMANENT_BUFF_END_TICK,
            stack_count: stackCount,
          });
        });
    }

    scheduledSteps.forEach((scheduled) => {
      const step = scheduled.step;
      const slot = int(scheduled.slot);
      const snapshot = snapshots.get(slot);
      if (!snapshot) return;
      const action = scheduled.action;
      const startTick = int(scheduled.start_tick);
      const visualStartTick = int(scheduled.visual_start_tick, startTick);
      const isBackground = Boolean(scheduled.is_background);
      const actionMultiplier = backgroundActionMultiplier(step, action);
      const durationTicks = Math.max(0, int(scheduled.duration_ticks));
      const endTick = int(scheduled.end_tick);
      const visualEndTick = int(scheduled.visual_end_tick);
      const cooldownKey = `${slot}:${String(action.id || '')}`;
      const availableTick = cooldownUntil.get(cooldownKey) || 0;
      const warnings = [];
      if (int(action.required_awakening) > 0 && !hasAwakeningNode(snapshot, action.required_awakening)) {
        const awakeningLabel = 'ABCDEF'[int(action.required_awakening) - 1] || String(int(action.required_awakening));
        warnings.push(`动作需要 ${awakeningLabel} 觉醒节点。`);
      }
      if (startTick < availableTick) warnings.push(`动作 CD 尚未结束，需等到 ${(availableTick / 10).toFixed(1)}s。`);
      const energyCost = num(action.energy_cost) * actionMultiplier;
      let slotEnergy = energyBySlot.get(slot) ?? initialEnergy;
      if (energyCost > slotEnergy) warnings.push('终结技能量不足。');
      const buffTick = startTick;
      if (!isBackground && runtimeFrontSlot !== slot) {
        runtimeFrontSlot = slot;
        runtimeFrontSinceTick = buffTick;
      }
      settleReactionDamage(buffTick);
      enemyDebuffs = activeEnemyDebuffs(enemyDebuffs, buffTick);
      activeBuffs = activeBuffs.filter((buff) => buffTick < int(buff.end_tick) && !activeBuffResetsOnActionStart(buff, step, action, isBackground, buffTick));
      syncFrontTimeBuffs(buffTick);
      const triggeredBuffs = [];
      for (let copyIndex = 0; copyIndex < actionMultiplier; copyIndex += 1) {
        triggeredBuffs.push(...triggerBuffsForEvent(
          'action_start',
          startTick,
          step,
          action,
          snapshot,
          isBackground,
          { visual_trigger_tick: visualStartTick },
        ));
      }
      const requiredBuffKey = String(action.required_buff_key || '');
      if (requiredBuffKey && !activeBuffs.some((buff) => (
        String(buff.definition_id || '') === requiredBuffKey
        && int(buff.owner_slot) === slot
        && buffTick >= int(buff.start_tick)
        && buffTick < int(buff.end_tick)
      ))) {
        warnings.push(`动作需要处于 ${String(action.required_buff_name || requiredBuffKey)} 状态。`);
      }
      const appliedBuffs = [];
      const buffModifiers = mods();
      const activeAtTick = activeBuffs.filter((buff) => buffTick >= int(buff.start_tick) && buffTick < int(buff.end_tick));
      const buffContext = {
        enemy,
        tick: buffTick,
        enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, buffTick),
        active_buffs: activeAtTick,
        active_buff_keys: activeAtTick.map((buff) => String(buff.definition_id || '')),
      };
      applicableBuffContributions(activeBuffs, step, action, snapshot, isBackground, buffContext)
        .forEach(({ buff, effects }) => {
          mergeMods(buffModifiers, effects);
          appliedBuffs.push(buffSummary(buff, buffContext));
        });
      const slotResources = personalResources.get(slot) || {};
      Object.entries(resourceMap(action.personal_resource_cost)).forEach(([key, cost]) => {
        const totalCost = cost * actionMultiplier;
        if ((slotResources[key] || 0) < totalCost) warnings.push(`个人资源 ${key} 不足。`);
        slotResources[key] = Math.max(0, (slotResources[key] || 0) - totalCost);
      });
      Object.entries(resourceMap(action.personal_resource_gain)).forEach(([key, gain]) => {
        const cap = num(PERSONAL_RESOURCE_CAPS[String(snapshot.character?.id || '')]?.[key], Number.POSITIVE_INFINITY);
        slotResources[key] = Math.min(cap, (slotResources[key] || 0) + gain * actionMultiplier);
      });
      slotEnergy = Math.max(0, slotEnergy - energyCost);
      const calc = calculateActionDamage(snapshot, action, enemy, buffModifiers);
      const consumedBuffs = new Set(
        activeBuffs
          .filter((buff) => (
            buffTick >= int(buff.start_tick)
            && buffTick < int(buff.end_tick)
            && (buff.rule?.consume_on_apply === true || buff.rule?.consume?.on_apply === true)
            && activeBuffApplies(buff, step, action, snapshot, isBackground, {
              enemy,
              tick: buffTick,
              enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, buffTick),
              active_buffs: activeAtTick,
              active_buff_keys: activeAtTick.map((candidate) => String(candidate.definition_id || '')),
            })
          )),
      );
      if (consumedBuffs.size) {
        activeBuffs = activeBuffs.filter((buff) => !consumedBuffs.has(buff));
      }
      const criticalHitsPerAction = expectedCriticalHits(action, calc);
      const criticalHits = criticalHitsPerAction * actionMultiplier;
      const appliedEnemyDebuffs = applyEnemyDebuffs(enemyDebuffs, action, buffTick);
      for (let copyIndex = 0; copyIndex < actionMultiplier; copyIndex += 1) {
        triggeredBuffs.push(...triggerBuffsForEvent('action_hit', startTick, step, action, snapshot, isBackground, {
          visual_trigger_tick: visualStartTick,
          expected_critical_hits: criticalHitsPerAction,
          applied_enemy_debuffs: appliedEnemyDebuffs,
          enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, buffTick),
        }));
      }
      const reactionAmplification = reactionAmplificationMultiplier(snapshot, calc.panel, buffTick);
      const multipliedDirectDamage = calc.direct_damage * actionMultiplier * reactionAmplification;
      const multipliedStagger = calc.stagger_amount * actionMultiplier;
      const multipliedHarmony = calc.harmony * actionMultiplier;
      const multipliedEnergyGain = (calc.energy_gain + num(action.energy_return)) * actionMultiplier;
      directDamage += multipliedDirectDamage;
      const damageSource = specialDamageSource(action);
      if (damageSource) {
        specialDamageBySource.set(damageSource, (specialDamageBySource.get(damageSource) || 0) + multipliedDirectDamage);
      }
      totalStagger += multipliedStagger;
      harmonyBySlot.set(slot, (harmonyBySlot.get(slot) || 0) + multipliedHarmony);
      slotEnergy += multipliedEnergyGain;
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
      const reactionTick = calculationTickFromVisualIntervals(reactionTriggerTick(scheduled), qVirtualIntervals);
      const reactionTrigger = triggerReaction(scheduled, reactionTick);
      const triggeredReaction = reactionTrigger.effect;
      if (triggeredReaction) {
        triggeredBuffs.push(...triggerBuffsForEvent(
          'reaction_trigger',
          reactionTick,
          step,
          action,
          snapshot,
          isBackground,
          {
            reaction: triggeredReaction,
            visual_trigger_tick: reactionTriggerTick(scheduled),
          },
        ));
      }
      if (reactionTrigger.warning) {
        warnings.push(reactionTrigger.warning);
      }
      for (let copyIndex = 0; copyIndex < actionMultiplier; copyIndex += 1) {
        triggeredBuffs.push(...triggerBuffsForEvent(
          'action_end',
          endTick,
          step,
          action,
          snapshot,
          isBackground,
          { visual_trigger_tick: visualEndTick },
        ));
      }
      lastTick = Math.max(lastTick, endTick, startTick);
      details.push({
        step_id: step.id || '',
        slot,
        character_id: snapshot.character.id,
        character_name: snapshot.character.name,
        action_id: action.id,
        action_name: action.name,
        action_type: action.action_type,
        damage_type: action.damage_type,
        damage_element: action.damage_element || snapshot.character.element || '',
        raw_start_tick: int(step.start_tick),
        switch_gap_ticks: Math.max(0, int(scheduled.switch_loss_ticks)),
        foreground_lock_ticks: Math.max(0, int(scheduled.foreground_lock_ticks)),
        start_tick: startTick,
        calculation_start_sequence: int(scheduled.calculation_start_sequence),
        end_tick: endTick,
        calculation_end_sequence: int(scheduled.calculation_end_sequence),
        duration_ticks: durationTicks,
        visual_start_tick: visualStartTick,
        visual_end_tick: visualEndTick,
        display_start_tick: visualStartTick,
        display_end_tick: visualEndTick,
        display_duration_ticks: Math.max(0, int(scheduled.original_duration_ticks)),
        tick_duration_ticks: Math.max(0, visualEndTick - visualStartTick),
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
        action_multiplier: actionMultiplier,
        action_tags: Array.from(actionTags(action)).sort(),
        hit_count: actionHitCount(action) * actionMultiplier,
        expected_critical_hits: criticalHits,
        applied_enemy_debuffs: appliedEnemyDebuffs,
        enemy_debuffs: activeEnemyDebuffs(enemyDebuffs, buffTick),
        direct_damage: multipliedDirectDamage,
        stagger_amount: multipliedStagger,
        harmony: multipliedHarmony,
        energy_gain: multipliedEnergyGain,
        energy_after: slotEnergy,
        harmony_after: harmonyBySlot.get(slot) || 0,
        personal_resources_after: Object.assign({}, slotResources),
        nightmare_stacks: action.nightmare_stacks == null ? action.nightmare_stacks : num(action.nightmare_stacks) * actionMultiplier,
        sin_recovery: action.sin_recovery == null ? action.sin_recovery : num(action.sin_recovery) * actionMultiplier,
        triggered_reaction: triggeredReaction,
        applied_buffs: appliedBuffs,
        triggered_buffs: triggeredBuffs,
        panel: calc.panel,
        formula_parts: Object.assign({}, calc.formula_parts, {
          action_multiplier: actionMultiplier,
          reaction_amplification: reactionAmplification,
        }),
        warnings,
      });
    });

    settleReactionDamage(options.loop_enabled ? loopDurationTicks : Number.POSITIVE_INFINITY);
    reactionEffects.forEach((effect) => {
      effect.visual_start_tick = visualTickFromCalculationTick(int(effect.start_tick), qVirtualIntervals);
      effect.visual_end_tick = visualTickFromCalculationTick(int(effect.end_tick), qVirtualIntervals);
    });
    reactionDamageEvents.forEach((event) => {
      event.visual_tick = visualTickFromCalculationTick(int(event.tick), qVirtualIntervals);
    });
    if (!options.loop_enabled) {
      lastTick = Math.max(
        lastTick,
        ...reactionEffects.map((effect) => int(effect.end_tick)),
        ...reactionDamageEvents.map((event) => int(event.tick)),
      );
    }

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
    const timelineTicks = Math.max(
      0,
      ...scheduledSteps.map((scheduled) => int(scheduled.visual_end_tick, int(scheduled.visual_start_tick))),
    );
    const frozenTicks = qVirtualIntervals.reduce(
      (sum, interval) => sum + Math.max(0, int(interval.end_tick) - int(interval.start_tick)),
      0,
    );
    const totalDamage = directDamage + staggerDamage;
    const teamEnergy = Array.from(energyBySlot.values()).reduce((sum, value) => sum + value, 0);
    const totalHarmony = Array.from(harmonyBySlot.values()).reduce((sum, value) => sum + value, 0);
    const damageBySlot = new Map();
    const damageByActionBySlot = new Map();
    details.forEach((detail) => {
      damageBySlot.set(detail.slot, (damageBySlot.get(detail.slot) || 0) + detail.direct_damage);
      if (!damageByActionBySlot.has(detail.slot)) {
        damageByActionBySlot.set(detail.slot, new Map());
      }
      const actionDamage = damageByActionBySlot.get(detail.slot);
      const actionKey = detail.action_id || detail.action_name;
      const current = actionDamage.get(actionKey) || {
        action_id: detail.action_id,
        action_name: detail.action_name,
        action_type: detail.action_type,
        damage_type: detail.damage_type,
        damage_element: detail.damage_element,
        damage: 0,
      };
      current.damage += detail.direct_damage;
      actionDamage.set(actionKey, current);
    });
    reactionDamageBySlot.forEach((damage, slot) => {
      if (damage <= 0) return;
      damageBySlot.set(slot, (damageBySlot.get(slot) || 0) + damage);
      if (!damageByActionBySlot.has(slot)) {
        damageByActionBySlot.set(slot, new Map());
      }
      reactionDamageEvents
        .filter((event) => int(event.contributor_slot) === int(slot) && num(event.damage) > 0)
        .forEach((event) => {
          const actionKey = `reaction:${event.reaction}`;
          const actionDamage = damageByActionBySlot.get(slot);
          const current = actionDamage.get(actionKey) || {
            action_id: actionKey,
            action_name: event.reaction,
            action_type: '环合',
            damage_type: '环合',
            damage_element: '',
            damage: 0,
          };
          current.damage += num(event.damage);
          actionDamage.set(actionKey, current);
        });
    });
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
        timeline_ticks: timelineTicks,
        frozen_ticks: frozenTicks,
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
      damage_by_action_by_slot: sortedSlots.map((slot) => {
        const characterDamage = damageBySlot.get(slot) || 0;
        return {
          slot,
          character_id: snapshots.get(slot).character.id,
          character_name: snapshots.get(slot).character.name,
          total_damage: characterDamage,
          actions: Array.from((damageByActionBySlot.get(slot) || new Map()).values())
            .filter((item) => item.damage > 0)
            .sort((left, right) => right.damage - left.damage || left.action_name.localeCompare(right.action_name, 'zh-CN'))
            .map((item) => ({
              ...item,
              percent: characterDamage > 0 ? item.damage / characterDamage * 100 : 0,
            })),
        };
      }),
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
      time_axis: {
        tick_seconds: 0.1,
        timeline_ticks: timelineTicks,
        real_duration_ticks: durationTicks,
        frozen_intervals: qVirtualIntervals.map((interval) => ({ ...interval })),
      },
      details,
      reaction_effects: reactionEffects,
      reaction_damage_events: reactionDamageEvents
        .filter((event) => event.damage != null && !event.kind)
        .map((event) => Object.fromEntries(Object.entries(event).filter(([key]) => key !== '_buff_instance'))),
      periodic_damage_events: reactionDamageEvents
        .filter((event) => num(event.damage) > 0 && Boolean(event.kind))
        .map((event) => Object.fromEntries(Object.entries(event).filter(([key]) => key !== '_buff_instance'))),
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
