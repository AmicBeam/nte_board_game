(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.ShaftSelfCheck = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function isBasicAction(action) {
    return String(action?.action_type || '') === '普攻' || String(action?.damage_type || '') === '普攻';
  }

  function isBackgroundStep(step, action) {
    const marker = `${action?.name || ''} ${action?.extra_tag || ''}`;
    return Boolean(action?.is_background_damage) || marker.includes('后台') || step?.placement === 'background';
  }

  function basicAttackStage(action) {
    if (!isBasicAction(action)) {
      return null;
    }
    const match = String(action?.name || '').match(/(?:^|[^a-z])a([1-9]\d*)/i);
    return match ? Number(match[1]) : null;
  }

  function inspectAxis(axis, catalog) {
    const actions = new Map((catalog?.actions || []).map((action) => [String(action.id || ''), action]));
    const orderedSteps = (axis?.steps || [])
      .map((step, order) => ({ step, order, action: actions.get(String(step?.action_id || '')) || {} }))
      .sort((left, right) => (
        Number(left.step?.start_tick || 0) - Number(right.step?.start_tick || 0) || left.order - right.order
      ));
    const warnings = [];
    const abnormalCharacters = new Set();

    for (let index = 1; index < orderedSteps.length; index += 1) {
      const previous = orderedSteps[index - 1];
      const current = orderedSteps[index];
      if (
        Number(previous.step?.slot) !== Number(current.step?.slot) ||
        isBackgroundStep(previous.step, previous.action) ||
        isBackgroundStep(current.step, current.action)
      ) {
        continue;
      }
      const previousStage = basicAttackStage(previous.action);
      const currentStage = basicAttackStage(current.action);
      if (previousStage == null || currentStage == null || currentStage === 1 || currentStage >= previousStage) {
        continue;
      }
      const characterName = String(current.action?.character_name || previous.action?.character_name || '该角色');
      if (!abnormalCharacters.has(characterName)) {
        abnormalCharacters.add(characterName);
        warnings.push(`${characterName}存在普攻段数异常`);
      }
    }

    return warnings;
  }

  return { basicAttackStage, inspectAxis };
}));
