const phaseChip = document.getElementById('phase-chip');
const statsGrid = document.getElementById('stats-grid');
const routeHint = document.getElementById('route-hint');
const mapName = document.getElementById('map-name');
const combatHud = document.getElementById('combat-hud');
const mapBackground = document.getElementById('map-background');
const mapGridLayer = document.getElementById('map-grid-layer');
const mapRangeLayer = document.getElementById('map-range-layer');
const mapPreviewLayer = document.getElementById('map-preview-layer');
const mapFxLayer = document.getElementById('map-fx-layer');
const mapOverlay = document.getElementById('map-overlay');
const bossHud = document.getElementById('boss-hud');
const handList = document.getElementById('hand-list');
const logList = document.getElementById('log-list');
const sidePanelTitle = document.getElementById('side-panel-title');
const sidePanelSubtitle = document.getElementById('side-panel-subtitle');
const itemsSideView = document.getElementById('items-side-view');
const logSideView = document.getElementById('log-side-view');
const sideViewButtons = Array.from(document.querySelectorAll('[data-side-view]'));
const itemFloatingTooltip = document.getElementById('item-floating-tooltip');
const copyLogBtn = document.getElementById('copy-log-btn');
const resetRunBtn = document.getElementById('reset-run-btn');
const logoutRunBtn = document.getElementById('logout-run-btn');
const directionButtons = Array.from(document.querySelectorAll('[data-direction]'));
const eventModal = document.getElementById('event-modal');
const eventModalIcon = document.getElementById('event-modal-icon');
const eventModalTitle = document.getElementById('event-modal-title');
const eventModalMessage = document.getElementById('event-modal-message');
const eventCloseBtn = document.getElementById('event-close-btn');
const battleModal = document.getElementById('battle-modal');
const battleCloseBtn = document.getElementById('battle-close-btn');
const battlePlayerName = document.getElementById('battle-player-name');
const battleEnemyName = document.getElementById('battle-enemy-name');
const battlePlayerHp = document.getElementById('battle-player-hp');
const battleEnemyHp = document.getElementById('battle-enemy-hp');
const battlePlayerDetail = document.getElementById('battle-player-detail');
const battleEnemyDetail = document.getElementById('battle-enemy-detail');
const battleSummaryText = document.getElementById('battle-summary-text');
const battlePlayerCombatant = document.getElementById('battle-player-combatant');
const battleEnemyCombatant = document.getElementById('battle-enemy-combatant');
const battlePlayerDamage = document.getElementById('battle-player-damage');
const battleEnemyDamage = document.getElementById('battle-enemy-damage');

const DIRECTION_VECTORS = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
};

const ITEM_TYPE_LABELS = {
  attack: '攻击',
  defense: '防御',
  utility: '功能',
  mobility: '移动',
  recovery: '恢复',
  dice: '骰子',
  intel: '侦察',
};

const RARITY_LABELS = {
  common: '普通',
  rare: '稀有',
  epic: '史诗',
};

let currentState = null;
let activePreview = null;
let moveLocked = false;

if (ensureLogin()) {
  loadState();
}

function prettyPhase(phase) {
  const mapping = {
    dice: '骰子阶段',
    action: '行动阶段',
    movement: '移动阶段',
    battle: '战斗阶段',
    victory: '胜利',
    defeat: '失败',
    playing: '进行中',
  };
  return mapping[phase] || phase;
}

function iconMarkup(kind) {
  const value = String(kind || 'event');
  if (isImageIcon(value)) {
    return `<img class="map-icon-img" src="${value}" alt="">`;
  }
  return `<span class="map-icon icon-${classToken(value)}"></span>`;
}

function classToken(value) {
  return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
}

function isImageIcon(value) {
  return /\.(png|jpg|jpeg|webp|gif)$/i.test(value) || String(value).startsWith('/static/');
}

function itemIconMarkup(item) {
  const value = String(item.icon || item.type || 'item');
  if (isImageIcon(value)) {
    return `<img class="item-icon-img" src="${value}" alt="">`;
  }
  return `<span class="item-icon item-icon-${classToken(value)}"></span>`;
}

function clampPercent(value, max) {
  if (!max) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((Number(value) / Number(max)) * 100)));
}

function statCard(label, value, options = {}) {
  const tone = options.tone ? ` stat-${options.tone}` : '';
  const meter = options.max ? `<span class="stat-meter"><i style="width: ${clampPercent(options.current, options.max)}%"></i></span>` : '';
  const detail = options.detail ? `<small>${options.detail}</small>` : '';
  return `
    <div class="stat-card${tone}">
      <span>${label}</span>
      <strong>${value}</strong>
      ${detail}
      ${meter}
    </div>
  `;
}

function renderState(state) {
  currentState = state;
  const character = state.selected_character || state.character_instance || {};
  phaseChip.textContent = prettyPhase(state.phase);
  phaseChip.className = `phase-chip phase-${classToken(state.phase)}`;
  document.body.dataset.phase = classToken(state.phase);
  routeHint.textContent = state.route_hint;
  mapName.textContent = state.map.name;
  mapBackground.src = state.board.background_image;
  renderCombatHud(state);

  statsGrid.innerHTML = `
    ${statCard('角色', character.name || '-', { tone: 'role', detail: character.title || '作战角色' })}
    ${statCard('生命', `${state.player.hp} / ${state.player.max_hp}`, { tone: 'hp', current: state.player.hp, max: state.player.max_hp })}
    ${statCard('攻击', state.computed_stats.attack, { tone: 'attack', detail: '当前面板' })}
    ${statCard('防御', state.computed_stats.defense, { tone: 'defense', detail: '当前面板' })}
    ${statCard('钥匙', state.player.keys, { tone: 'key', detail: '开门资源' })}
    ${statCard('阶段', prettyPhase(state.phase), { tone: 'turn', detail: '当前行动' })}
  `;

  renderMapGrid(state);
  renderOverlay(state);
  renderBossHud(state);
  renderHand(state);
  renderLog(state);
  syncButtons(state);
  refreshActivePreview();
}

function renderCombatHud(state) {
  const currentLayer = state.map.current_layer || 1;
  const totalLayers = state.map.total_layers || 1;
  combatHud.innerHTML = `
    <span>回合 ${state.turn}</span>
    <span>坐标 ${state.player.x}/${state.player.y}</span>
    <span>层数 ${currentLayer}/${totalLayers}</span>
  `;
}

function renderMapGrid(state) {
  const layer = activeLayer(state);
  const tileByKey = new Map((state.map.tiles || []).filter((tile) => onLayer(tile, layer)).map((tile) => [cellKey(tile.x, tile.y), tile]));
  const monsterByKey = new Map((state.map.monsters || []).filter((monster) => onLayer(monster, layer) && monster.hp > 0).map((monster) => [cellKey(monster.x, monster.y), monster]));
  const bossKeys = new Set((state.map.boss?.positions || []).filter((pos) => onLayer(pos, layer)).map((pos) => cellKey(pos.x, pos.y)));

  mapGridLayer.style.gridTemplateColumns = `repeat(${state.map.width}, minmax(0, 1fr))`;
  mapGridLayer.style.gridTemplateRows = `repeat(${state.map.height}, minmax(0, 1fr))`;
  mapGridLayer.innerHTML = '';

  for (let y = 0; y < state.map.height; y += 1) {
    for (let x = 0; x < state.map.width; x += 1) {
      const tile = tileByKey.get(cellKey(x, y));
      const cell = document.createElement('span');
      const tileType = tileDisplayType(tile);
      cell.className = `map-cell cell-${classToken(tileType)}`;
      cell.style.gridColumn = String(x + 1);
      cell.style.gridRow = String(y + 1);
      if (monsterByKey.has(cellKey(x, y))) {
        cell.classList.add('cell-monster');
      }
      if (bossKeys.has(cellKey(x, y))) {
        cell.classList.add('cell-boss');
      }
      mapGridLayer.appendChild(cell);
    }
  }
}

function renderOverlay(state) {
  mapOverlay.innerHTML = '';
  state.board.icons.forEach((icon) => {
    const node = document.createElement('button');
    node.className = `overlay-token token-${icon.entity_type}`;
    if (icon.top_percent < 22) {
      node.classList.add('tooltip-bottom');
    }
    if (icon.left_percent < 18) {
      node.classList.add('tooltip-left');
    } else if (icon.left_percent > 82) {
      node.classList.add('tooltip-right');
    }
    node.style.left = `${icon.left_percent}%`;
    node.style.top = `${icon.top_percent}%`;
    node.dataset.x = String(icon.x);
    node.dataset.y = String(icon.y);
    node.dataset.layer = String(icon.layer || activeLayer(state));
    node.dataset.entityType = icon.entity_type;
    if (icon.direction) {
      node.dataset.direction = icon.direction;
    }
    if (icon.width_percent) {
      node.style.width = `${icon.width_percent}%`;
    }
    if (icon.height_percent) {
      node.style.height = `${icon.height_percent}%`;
    }
    node.type = 'button';
    node.innerHTML = `${iconMarkup(icon.icon)}${icon.entity_type === 'player' ? '<span class="player-chip">我</span>' : ''}<span class="sr-only">${icon.tooltip}</span><span class="tooltip-bubble">${icon.tooltip}</span>`;
    if (icon.entity_type === 'monster' || icon.entity_type === 'boss') {
      node.addEventListener('pointerenter', () => showThreatRange(icon));
      node.addEventListener('focus', () => showThreatRange(icon));
      node.addEventListener('pointerleave', clearThreatRange);
      node.addEventListener('blur', clearThreatRange);
    }
    mapOverlay.appendChild(node);
  });
}

function renderBossHud(state) {
  const boss = state.map.boss || {};
  const layer = activeLayer(state);
  const positions = (boss.positions || []).filter((pos) => onLayer(pos, layer));
  const active = positions.length > 0 && boss.hp > 0 && (boss.hp < boss.max_hp || isAdjacentToBoss(state.player, positions));
  if (!active) {
    bossHud.classList.remove('active');
    bossHud.innerHTML = '';
    return;
  }
  bossHud.classList.add('active');
  bossHud.innerHTML = `
    <span>${boss.name || 'Boss'}</span>
    <strong>${boss.hp} / ${boss.max_hp}</strong>
    <i><b style="width:${clampPercent(boss.hp, boss.max_hp)}%"></b></i>
  `;
}

function renderHand(state) {
  if (state.hand_details.length === 0) {
    handList.innerHTML = '<div class="empty-state">当前没有道具</div>';
    return;
  }
  handList.innerHTML = '';
  state.hand_details.forEach((item) => {
    const card = document.createElement('article');
    const stackLabel = itemStackLabel(item, state);
    card.className = `hand-card item-card item-tool rarity-${classToken(item.rarity)} type-${classToken(item.type)}`;
    card.innerHTML = `
      <button class="item-tool-button" ${state.phase !== 'action' || state.has_played_item ? 'disabled' : ''} aria-label="使用${item.name}">
        <span class="item-art small" aria-hidden="true">${itemIconMarkup(item)}</span>
        ${stackLabel ? `<span class="item-stack">${stackLabel}</span>` : ''}
      </button>
    `;
    card.querySelector('button').addEventListener('click', () => playItem(item.instance_id));
    card.addEventListener('pointerenter', () => showItemTooltip(card, item, stackLabel));
    card.addEventListener('pointermove', () => positionItemTooltip(card));
    card.addEventListener('pointerleave', hideItemTooltip);
    card.addEventListener('focusin', () => showItemTooltip(card, item, stackLabel));
    card.addEventListener('focusout', hideItemTooltip);
    handList.appendChild(card);
  });
}

function itemTooltipHtml(item, stackLabel) {
  return `
    <div class="card-headline">
      <span class="card-tag">${itemTypeLabel(item.type)} · ${rarityLabel(item.rarity)}</span>
      <h3>${item.name}</h3>
    </div>
    <p class="card-meta">${item.description}</p>
    ${stackLabel ? `<p class="item-stack-detail">当前层数：${stackLabel}</p>` : ''}
  `;
}

function itemTypeLabel(type) {
  return ITEM_TYPE_LABELS[type] || type || '道具';
}

function rarityLabel(rarity) {
  return RARITY_LABELS[rarity] || rarity || '普通';
}

function showItemTooltip(anchor, item, stackLabel) {
  itemFloatingTooltip.innerHTML = itemTooltipHtml(item, stackLabel);
  itemFloatingTooltip.classList.add('open');
  itemFloatingTooltip.setAttribute('aria-hidden', 'false');
  positionItemTooltip(anchor);
}

function positionItemTooltip(anchor) {
  if (!itemFloatingTooltip.classList.contains('open')) {
    return;
  }
  const anchorRect = anchor.getBoundingClientRect();
  const tooltipRect = itemFloatingTooltip.getBoundingClientRect();
  const gap = 12;
  let left = anchorRect.left - tooltipRect.width - gap;
  if (left < gap) {
    left = anchorRect.right + gap;
  }
  const maxLeft = window.innerWidth - tooltipRect.width - gap;
  left = Math.max(gap, Math.min(left, maxLeft));
  let top = anchorRect.top + (anchorRect.height / 2) - (tooltipRect.height / 2);
  const maxTop = window.innerHeight - tooltipRect.height - gap;
  top = Math.max(gap, Math.min(top, maxTop));
  itemFloatingTooltip.style.left = `${left}px`;
  itemFloatingTooltip.style.top = `${top}px`;
}

function hideItemTooltip() {
  itemFloatingTooltip.classList.remove('open');
  itemFloatingTooltip.setAttribute('aria-hidden', 'true');
}

function itemStackLabel(item, state) {
  const effects = (state.active_effects || []).filter((effect) => (
    effect.source_instance_id === item.instance_id || effect.definition_id === item.id
  ));
  for (const effect of effects) {
    const data = effect.data || {};
    const value = data.stacks ?? data.stack ?? data.charges ?? data.charge ?? data.shield_remaining;
    if (value !== undefined && value !== null && Number(value) > 0) {
      return String(value);
    }
  }
  return '';
}

function showThreatRange(icon) {
  if (!currentState) {
    return;
  }
  clearThreatRange();
  const threat = resolveThreat(icon);
  if (!threat) {
    return;
  }
  rangeCellsForThreat(threat).forEach((cell) => {
    const marker = document.createElement('span');
    marker.className = 'range-cell';
    const bounds = cellBounds(cell.x, cell.y);
    marker.style.left = `${bounds.left}%`;
    marker.style.top = `${bounds.top}%`;
    marker.style.width = `${bounds.width}%`;
    marker.style.height = `${bounds.height}%`;
    mapRangeLayer.appendChild(marker);
  });
  routeHint.textContent = `${threat.name} 攻击范围：${threat.range || 1} 格。`;
}

function clearThreatRange() {
  mapRangeLayer.innerHTML = '';
  if (activePreview) {
    renderPreview(activePreview);
  } else if (currentState) {
    routeHint.textContent = currentState.route_hint;
  }
}

function resolveThreat(icon) {
  if (icon.entity_type === 'boss') {
    return currentState.map.boss;
  }
  const layer = activeLayer(currentState);
  return (currentState.map.monsters || []).find((monster) => (
    onLayer(monster, layer) && monster.hp > 0 && monster.x === icon.x && monster.y === icon.y
  ));
}

function rangeCellsForThreat(threat) {
  const range = Number(threat.range || 1);
  const layer = activeLayer(currentState);
  const origins = threat.positions
    ? threat.positions.filter((origin) => onLayer(origin, layer))
    : [{ x: threat.x, y: threat.y, layer }];
  const cells = new Map();
  const seen = new Set();
  origins.forEach((origin) => {
    const queue = [{ x: Number(origin.x), y: Number(origin.y), distance: 0 }];
    seen.add(cellKey(origin.x, origin.y));
    while (queue.length) {
      const point = queue.shift();
      if (point.distance >= range) {
        continue;
      }
      Object.values(DIRECTION_VECTORS).forEach((vector) => {
        const x = point.x + vector.x;
        const y = point.y + vector.y;
        const key = cellKey(x, y);
        if (seen.has(key) || x < 0 || y < 0 || x >= currentState.map.width || y >= currentState.map.height) {
          return;
        }
        seen.add(key);
        if (isRangeBlocked(currentState, x, y)) {
          return;
        }
        cells.set(key, { x, y });
        queue.push({ x, y, distance: point.distance + 1 });
      });
    }
  });
  return Array.from(cells.values());
}

function isRangeBlocked(state, x, y) {
  const tile = tileAt(state, x, y);
  const displayType = tileDisplayType(tile);
  if (displayType === 'wall') {
    return true;
  }
  if (displayType === 'door' && tile?.locked !== false) {
    return true;
  }
  return false;
}

function tileDisplayType(tile) {
  if (!tile) {
    return 'floor';
  }
  if (tile.display_type) {
    return tile.display_type;
  }
  if (tile.type === 'chest' && tile.opened) {
    return 'floor';
  }
  if (tile.type === 'event' && tile.resolved) {
    return 'floor';
  }
  if (tile.type === 'door' && tile.locked === false) {
    return 'floor';
  }
  if (tile.type === 'boss_tile') {
    return 'floor';
  }
  return tile.type || 'floor';
}

function applyTileUpdate(step) {
  if (!currentState || Number(step.layer || activeLayer()) !== activeLayer(currentState)) {
    return;
  }
  const tile = (currentState.map.tiles || []).find((item) => (
    Number(item.x) === Number(step.x)
    && Number(item.y) === Number(step.y)
    && onLayer(item, activeLayer(currentState))
  ));
  if (tile && step.tile) {
    Object.assign(tile, step.tile);
    if (step.display_type) {
      tile.display_type = step.display_type;
    }
  }
  renderMapGrid(currentState);
  const selector = `.overlay-token[data-x="${step.x}"][data-y="${step.y}"][data-layer="${step.layer || activeLayer(currentState)}"]`;
  document.querySelectorAll(selector).forEach((node) => {
    if (!['player', 'monster', 'boss'].includes(node.dataset.entityType)) {
      node.remove();
    }
  });
}

async function showEventPopup(step) {
  eventModalIcon.innerHTML = iconMarkup(step.icon || 'event');
  eventModalTitle.textContent = step.title || '事件';
  eventModalMessage.textContent = step.message || '';
  eventModal.classList.add('open');
  eventModal.setAttribute('aria-hidden', 'false');
  await waitForEventClose();
}

function closeEventModal() {
  eventModal.classList.remove('open');
  eventModal.setAttribute('aria-hidden', 'true');
}

function waitForEventClose() {
  return new Promise((resolve) => {
    const done = () => {
      closeEventModal();
      eventCloseBtn.removeEventListener('click', done);
      eventModal.removeEventListener('click', onBackdrop);
      resolve();
    };
    const onBackdrop = (event) => {
      if (event.target === eventModal) {
        done();
      }
    };
    eventCloseBtn.addEventListener('click', done);
    eventModal.addEventListener('click', onBackdrop);
  });
}

function cellBounds(x, y) {
  return {
    left: (x / currentState.map.width) * 100,
    top: (y / currentState.map.height) * 100,
    width: 100 / currentState.map.width,
    height: 100 / currentState.map.height,
  };
}

function renderLog(state) {
  logList.innerHTML = state.log.map((line, index) => `<div class="log-item"><span>${String(index + 1).padStart(2, '0')}</span>${line}</div>`).join('');
}

function setSideView(view) {
  const showingLog = view === 'log';
  itemsSideView.classList.toggle('active', !showingLog);
  logSideView.classList.toggle('active', showingLog);
  sidePanelTitle.textContent = showingLog ? '日志' : '道具';
  sidePanelSubtitle.textContent = showingLog ? '最近战斗记录' : '行动阶段可用 1 个';
  sideViewButtons.forEach((button) => {
    button.classList.toggle('active', button.dataset.sideView === view);
  });
  hideItemTooltip();
}

function syncButtons(state) {
  directionButtons.forEach((button) => {
    button.disabled = moveLocked || !['action', 'movement'].includes(state.phase) || state.pending_die === null;
  });
  const diceNode = document.querySelector('.dice-readout');
  if (diceNode) {
    diceNode.innerHTML = `<img src="/static/images/dice.webp" alt="">${state.pending_die ?? '-'}`;
  }
}

function canPreview(state) {
  return state && ['action', 'movement'].includes(state.phase) && state.pending_die !== null;
}

function cellKey(x, y) {
  return `${x}:${y}`;
}

function activeLayer(state = currentState) {
  return Number(state?.map?.current_layer || state?.board?.current_layer || 1);
}

function onLayer(entity, layer = activeLayer()) {
  return Number(entity?.layer || 1) === Number(layer);
}

function cellPercent(point, state = currentState) {
  return {
    left: ((point.x + 0.5) / state.map.width) * 100,
    top: ((point.y + 0.5) / state.map.height) * 100,
  };
}

function tileAt(state, x, y) {
  const layer = activeLayer(state);
  return (state.map.tiles || []).find((tile) => onLayer(tile, layer) && tile.x === x && tile.y === y) || null;
}

function isMonsterCell(state, x, y) {
  const layer = activeLayer(state);
  return (state.map.monsters || []).some((monster) => onLayer(monster, layer) && monster.hp > 0 && monster.x === x && monster.y === y);
}

function isBossCell(state, x, y) {
  const boss = state.map.boss || {};
  const layer = activeLayer(state);
  return boss.hp > 0 && (boss.positions || []).some((pos) => onLayer(pos, layer) && pos.x === x && pos.y === y);
}

function getBasicBlockReason(state, x, y) {
  if (x < 0 || y < 0 || x >= state.map.width || y >= state.map.height) {
    return '边界';
  }
  if (isMonsterCell(state, x, y)) {
    return '怪物阻挡';
  }
  if (isBossCell(state, x, y)) {
    return 'Boss 占位';
  }
  const tile = tileAt(state, x, y);
  if (tile?.type === 'wall') {
    return '墙体阻挡';
  }
  if (tile?.type === 'door' && tile.locked !== false) {
    return '门阻挡';
  }
  return null;
}

function isBasicIntercept(tile) {
  return tile?.type === 'portal' || tile?.object_id === 'portal';
}

function basicTurnDirection(tile, stepsRemaining) {
  if (stepsRemaining <= 0) {
    return null;
  }
  if ((tile?.type === 'turn_belt' || tile?.object_id === 'turn_belt') && DIRECTION_VECTORS[tile.direction]) {
    return tile.direction;
  }
  return null;
}

function buildMovePreview(state, direction) {
  if (!canPreview(state) || !DIRECTION_VECTORS[direction]) {
    return null;
  }
  let x = Number(state.player.x);
  let y = Number(state.player.y);
  let activeDirection = direction;
  let stepsRemaining = Number(state.pending_die) || 0;
  const path = [{ x, y, kind: 'start' }];
  const redirects = [];
  let blocked = null;
  let intercepted = null;
  let guard = 0;
  const startTurn = basicTurnDirection(tileAt(state, x, y), stepsRemaining);
  if (startTurn) {
    activeDirection = startTurn;
    path[0].turnDirection = startTurn;
    redirects.push({ x, y, direction: startTurn });
  }

  while (stepsRemaining > 0) {
    guard += 1;
    if (guard > 32) {
      blocked = { x, y, reason: '预览达到上限' };
      break;
    }

    const vector = DIRECTION_VECTORS[activeDirection];
    const nextX = x + vector.x;
    const nextY = y + vector.y;
    const blockReason = getBasicBlockReason(state, nextX, nextY);
    if (blockReason) {
      blocked = { x: nextX, y: nextY, reason: blockReason };
      break;
    }

    x = nextX;
    y = nextY;
    stepsRemaining -= 1;
    const tile = tileAt(state, x, y);
    const point = { x, y, kind: stepsRemaining === 0 ? 'landing' : 'step', direction: activeDirection };
    path.push(point);

    if (isBasicIntercept(tile)) {
      point.kind = 'intercept';
      intercepted = { x, y, reason: '拦截' };
      break;
    }

    const turned = basicTurnDirection(tile, stepsRemaining);
    if (turned) {
      activeDirection = turned;
      point.turnDirection = turned;
      redirects.push({ x, y, direction: turned });
    }
  }

  const landing = path[path.length - 1];
  return {
    direction,
    path,
    landing: { x: landing.x, y: landing.y },
    redirects,
    blocked,
    intercepted,
  };
}

function renderPreview(preview) {
  activePreview = preview;
  mapPreviewLayer.innerHTML = '';
  if (!preview || !currentState) {
    routeHint.textContent = currentState?.route_hint || '等待加载';
    return;
  }

  preview.path.forEach((point, index) => {
    if (index > 0) {
      addPreviewSegment(preview.path[index - 1], point);
    }
  });

  preview.path.forEach((point, index) => {
    const pos = cellPercent(point);
    const marker = document.createElement('span');
    marker.className = `preview-dot preview-${point.kind}`;
    marker.style.left = `${pos.left}%`;
    marker.style.top = `${pos.top}%`;
    marker.textContent = index === 0 ? '' : String(index);
    if (point.turnDirection) {
      marker.dataset.turn = directionLabel(point.turnDirection);
    }
    mapPreviewLayer.appendChild(marker);
  });

  if (preview.blocked) {
    const pos = cellPercent(preview.blocked);
    const block = document.createElement('span');
    block.className = 'preview-block';
    block.style.left = `${pos.left}%`;
    block.style.top = `${pos.top}%`;
    block.textContent = '×';
    mapPreviewLayer.appendChild(block);
  }

  const reason = preview.blocked?.reason || preview.intercepted?.reason;
  const target = preview.blocked ? preview.blocked : preview.landing;
  routeHint.textContent = reason
    ? `预览：${preview.path.length - 1} 步后在 (${preview.landing.x}, ${preview.landing.y}) 停止，${reason} 于 (${target.x}, ${target.y})。`
    : `预览：落点 (${preview.landing.x}, ${preview.landing.y})。${preview.redirects.length ? '途中会发生转向。' : ''}`;
}

function addPreviewSegment(from, to) {
  const start = cellPercent(from);
  const end = cellPercent(to);
  const line = document.createElement('span');
  const dx = end.left - start.left;
  const dy = end.top - start.top;
  const length = Math.sqrt((dx * dx) + (dy * dy));
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);
  line.className = 'preview-line';
  line.style.left = `${start.left}%`;
  line.style.top = `${start.top}%`;
  line.style.width = `${length}%`;
  line.style.transform = `rotate(${angle}deg)`;
  mapPreviewLayer.appendChild(line);
}

function clearPreview() {
  activePreview = null;
  mapPreviewLayer.innerHTML = '';
  if (currentState) {
    routeHint.textContent = currentState.route_hint;
  }
}

function showPreview(direction) {
  if (moveLocked || !canPreview(currentState)) {
    return;
  }
  renderPreview(buildMovePreview(currentState, direction));
}

function refreshActivePreview() {
  const hovered = directionButtons.find((button) => button.matches(':hover, :focus-visible'));
  if (hovered && canPreview(currentState)) {
    showPreview(hovered.dataset.direction);
  } else {
    clearPreview();
  }
}

function directionLabel(direction) {
  const mapping = { up: '↑', down: '↓', left: '←', right: '→' };
  return mapping[direction] || '';
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function animatePreview(preview) {
  if (!preview || preview.path.length <= 1) {
    return;
  }
  const ghost = document.createElement('span');
  ghost.className = 'move-ghost';
  const start = cellPercent(preview.path[0]);
  ghost.style.left = `${start.left}%`;
  ghost.style.top = `${start.top}%`;
  mapFxLayer.appendChild(ghost);

  await sleep(20);
  for (const point of preview.path.slice(1)) {
    const pos = cellPercent(point);
    ghost.style.left = `${pos.left}%`;
    ghost.style.top = `${pos.top}%`;
    await sleep(120);
  }
  ghost.classList.add('fade');
  await sleep(160);
  ghost.remove();
}

async function animateBackendMove(step) {
  if (!currentState || Number(step.layer || activeLayer(currentState)) !== activeLayer(currentState)) {
    return;
  }
  const path = [
    { x: Number(currentState.player.x), y: Number(currentState.player.y), kind: 'start' },
    { x: Number(step.x), y: Number(step.y), kind: 'landing' },
  ];
  currentState.player.x = Number(step.x);
  currentState.player.y = Number(step.y);
  await animatePreview({ path });
}

async function playActionQueue(queue, beforeState, nextState) {
  let showedBattle = false;
  for (const step of queue || []) {
    if (step.type === 'move') {
      await animateBackendMove(step);
    } else if (step.type === 'tile_update') {
      applyTileUpdate(step);
    } else if (step.type === 'popup') {
      await showEventPopup(step);
    } else if (step.type === 'battle') {
      showedBattle = true;
      showBattleModalFromSummary(step, nextState);
    }
  }
  return showedBattle;
}

function findBattleSummary(before, after) {
  const playerLostHp = Math.max(0, Number(before.player.hp) - Number(after.player.hp));
  const bossBefore = before.map.boss || {};
  const bossAfter = after.map.boss || {};
  const bossPositions = (bossAfter.positions || []).filter((pos) => onLayer(pos, activeLayer(after)));
  if (Number(bossAfter.hp) < Number(bossBefore.hp) || isAdjacent(after.player, bossPositions)) {
    return {
      enemyName: bossAfter.name || 'Boss',
      enemyHp: Number(bossAfter.hp),
      enemyMaxHp: Number(bossAfter.max_hp),
      enemyLostHp: Math.max(0, Number(bossBefore.hp) - Number(bossAfter.hp)),
      playerLostHp,
    };
  }

  const beforeMonsters = new Map((before.map.monsters || []).map((monster) => [monster.id, monster]));
  const changedMonster = (after.map.monsters || []).find((monster) => {
    const oldMonster = beforeMonsters.get(monster.id);
    return oldMonster && Number(monster.hp) < Number(oldMonster.hp);
  });
  if (changedMonster || playerLostHp > 0) {
    const target = changedMonster || nearestThreat(after);
    const oldTarget = target ? beforeMonsters.get(target.id) : null;
    return {
      enemyName: target?.name || '敌方单位',
      enemyHp: Number(target?.hp || 0),
      enemyMaxHp: Number(target?.max_hp || 1),
      enemyLostHp: Math.max(0, Number(oldTarget?.hp || target?.hp || 0) - Number(target?.hp || 0)),
      playerLostHp,
    };
  }
  return null;
}

function isAdjacent(player, positions) {
  return positions.some((pos) => Math.abs(Number(player.x) - Number(pos.x)) + Math.abs(Number(player.y) - Number(pos.y)) === 1);
}

function isAdjacentToBoss(player, positions) {
  return positions.some((pos) => Math.abs(Number(player.x) - Number(pos.x)) + Math.abs(Number(player.y) - Number(pos.y)) <= 1);
}

function nearestThreat(state) {
  const layer = activeLayer(state);
  const monsters = (state.map.monsters || []).filter((monster) => onLayer(monster, layer) && monster.hp > 0);
  if (!monsters.length) {
    return null;
  }
  return monsters.sort((a, b) => {
    const da = Math.abs(a.x - state.player.x) + Math.abs(a.y - state.player.y);
    const db = Math.abs(b.x - state.player.x) + Math.abs(b.y - state.player.y);
    return da - db;
  })[0];
}

function showBattleModal(before, after) {
  const summary = findBattleSummary(before, after);
  if (!summary) {
    return;
  }
  showBattleModalFromSummary(summary, after);
}

function normalizeBattleSummary(summary) {
  return {
    enemyName: summary.enemyName ?? summary.enemy_name ?? '敌方单位',
    enemyHp: Number(summary.enemyHp ?? summary.enemy_hp ?? 0),
    enemyMaxHp: Number(summary.enemyMaxHp ?? summary.enemy_max_hp ?? 1),
    enemyLostHp: Number(summary.enemyLostHp ?? summary.enemy_lost_hp ?? 0),
    playerLostHp: Number(summary.playerLostHp ?? summary.player_lost_hp ?? 0),
  };
}

function showBattleModalFromSummary(summary, after) {
  const normalized = normalizeBattleSummary(summary);
  const character = after.character_instance || {};
  battlePlayerName.textContent = character.name || after.current_viewer?.nickname || '当前角色';
  battleEnemyName.textContent = normalized.enemyName;
  battlePlayerHp.style.width = `${clampPercent(after.player.hp, after.player.max_hp)}%`;
  battleEnemyHp.style.width = `${clampPercent(normalized.enemyHp, normalized.enemyMaxHp)}%`;
  battlePlayerDetail.textContent = `HP ${after.player.hp}/${after.player.max_hp}`;
  battleEnemyDetail.textContent = `HP ${normalized.enemyHp}/${normalized.enemyMaxHp}`;
  battlePlayerDamage.textContent = normalized.playerLostHp ? `-${normalized.playerLostHp}` : '';
  battleEnemyDamage.textContent = normalized.enemyLostHp ? `-${normalized.enemyLostHp}` : '';
  battleSummaryText.textContent = normalized.enemyLostHp || normalized.playerLostHp
    ? '战斗已结算。'
    : '本次遭遇没有造成伤害。';
  battleModal.classList.remove('battle-animating');
  window.requestAnimationFrame(() => battleModal.classList.add('battle-animating'));
  battleModal.classList.add('open');
  battleModal.setAttribute('aria-hidden', 'false');
}

function closeBattleModal() {
  battleModal.classList.remove('open', 'battle-animating');
  battleModal.setAttribute('aria-hidden', 'true');
  battlePlayerCombatant.classList.remove('hit');
  battleEnemyCombatant.classList.remove('hit');
}

async function loadState() {
  try {
    let state;
    try {
      state = await apiRequest('/api/game/state');
    } catch (error) {
      state = await apiRequest('/api/game/start', { method: 'POST' });
    }
    renderState(state);
  } catch (error) {
    window.alert(error.message);
    window.location.href = '/build';
  }
}

async function playItem(itemInstanceId) {
  try {
    const beforeState = currentState;
    const nextState = await apiRequest('/api/game/play-item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_instance_id: itemInstanceId }),
    });
    await playActionQueue(nextState.action_queue || [], beforeState, nextState);
    renderState(nextState);
  } catch (error) {
    window.alert(error.message);
  }
}

async function move(direction) {
  if (moveLocked) {
    return;
  }
  const beforeState = currentState;
  try {
    moveLocked = true;
    syncButtons(currentState);
    clearPreview();
    const nextState = await apiRequest('/api/game/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ direction }),
    });
    const showedBattle = await playActionQueue(nextState.action_queue || [], beforeState, nextState);
    renderState(nextState);
    clearPreview();
    if (!showedBattle) {
      showBattleModal(beforeState, nextState);
    }
  } catch (error) {
    window.alert(error.message);
  } finally {
    moveLocked = false;
    if (currentState) {
      syncButtons(currentState);
    }
  }
}

async function copyLog() {
  const text = (currentState?.log || []).map((line, index) => `${String(index + 1).padStart(2, '0')} ${line}`).join('\n');
  try {
    if (!navigator.clipboard) {
      throw new Error('clipboard unavailable');
    }
    await navigator.clipboard.writeText(text);
  } catch (error) {
    window.prompt('复制日志', text);
  }
}

async function resetRun() {
  const confirmed = window.confirm('确认撤退吗？当前对局会结束。');
  if (!confirmed) {
    return;
  }
  await apiRequest('/api/game/reset', { method: 'POST' });
  window.location.href = '/';
}

function logoutRun() {
  const confirmed = window.confirm('确认退出登录吗？当前对局会继续保存。');
  if (!confirmed) {
    return;
  }
  clearToken();
  window.location.href = '/login';
}

resetRunBtn.addEventListener('click', resetRun);
logoutRunBtn.addEventListener('click', logoutRun);
sideViewButtons.forEach((button) => {
  button.addEventListener('click', () => setSideView(button.dataset.sideView));
});
copyLogBtn.addEventListener('click', copyLog);
eventCloseBtn.addEventListener('click', closeEventModal);
eventModal.addEventListener('click', (event) => {
  if (event.target === eventModal) {
    closeEventModal();
  }
});
battleCloseBtn.addEventListener('click', closeBattleModal);
battleModal.addEventListener('click', (event) => {
  if (event.target === battleModal) {
    closeBattleModal();
  }
});
directionButtons.forEach((button) => {
  button.addEventListener('click', () => move(button.dataset.direction));
  button.addEventListener('pointerenter', () => showPreview(button.dataset.direction));
  button.addEventListener('focus', () => showPreview(button.dataset.direction));
  button.addEventListener('pointerleave', clearPreview);
  button.addEventListener('blur', clearPreview);
});
