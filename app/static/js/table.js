const phaseChip = document.getElementById('phase-chip');
const statsGrid = document.getElementById('stats-grid');
const routeHint = document.getElementById('route-hint');
const mapName = document.getElementById('map-name');
const combatHud = document.getElementById('combat-hud');
const mapStage = document.getElementById('map-stage');
const mapStageInner = document.querySelector('.map-stage-inner');
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
const identificationCombo = document.getElementById('identification-combo');
const identificationLevelLabel = document.getElementById('identification-level-label');
const identificationBonusLabel = document.getElementById('identification-bonus-label');
const identificationExpFill = document.getElementById('identification-exp-fill');
const buffPanel = document.getElementById('buff-panel');
const itemFloatingTooltip = document.getElementById('item-floating-tooltip');
const mapFloatingTooltip = document.getElementById('map-floating-tooltip');
const copyLogBtn = document.getElementById('copy-log-btn');
const resetRunBtn = document.getElementById('reset-run-btn');
const logoutRunBtn = document.getElementById('logout-run-btn');
const directionButtons = Array.from(document.querySelectorAll('[data-direction]'));
const mapZoomSlider = document.getElementById('map-zoom-slider');
const MAP_MIN_ZOOM = 1;
const MAP_HARD_MAX_ZOOM = 8;
const MAP_TARGET_CELL_PIXELS = 52;
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

const TURN_BELT_DIRECTIONS = {
  turn_belt_up: 'up',
  turn_belt_down: 'down',
  turn_belt_left: 'left',
  turn_belt_right: 'right',
};

const ITEM_TYPE_LABELS = {
  attack: '攻击',
  defense: '防御',
  utility: '功能',
  mobility: '移动',
  recovery: '恢复',
  dice: '骰子',
  intel: '侦察',
  currency: '货币',
  loot: '鉴别物',
  key: '钥匙',
};

const RARITY_LABELS = {
  n: 'N',
  r: 'R',
  sr: 'SR',
  ur: 'UR',
  common: '普通',
  rare: '稀有',
  epic: '史诗',
};

let currentState = null;
let activePreview = null;
let moveLocked = false;
let initialCameraCentered = false;
let lastRenderedLayer = null;
let primedControl = null;
let tableTutorialInitialized = false;
let hoveredMapCellKey = null;
let mapCameraFrame = 0;
let pendingMapCameraOptions = {};

const mapCamera = {
  x: 0,
  y: 0,
  zoom: MAP_MIN_ZOOM,
  dragging: false,
  dragMoved: false,
  pointerId: null,
  startX: 0,
  startY: 0,
  originX: 0,
  originY: 0,
  baseWidth: 0,
  baseHeight: 0,
};

if (ensureLogin()) {
  loadState();
}

function tutorialNameFromTooltip(text, fallback = '目标') {
  const value = String(text || fallback).split(/[：:。]/)[0].trim();
  return value || fallback;
}

function uniqueTutorialSamples(samples, limit = 5) {
  const seen = new Set();
  const result = [];
  samples.forEach((sample) => {
    const key = `${sample.name}:${sample.icon || sample.fallback}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    result.push(sample);
  });
  return result.slice(0, limit);
}

function buildTableTutorialPages(state = currentState) {
  const boardIcons = state?.board?.icons || [];
  const mapSamples = uniqueTutorialSamples(boardIcons
    .filter((icon) => !['player', 'monster', 'boss'].includes(icon.entity_type))
    .map((icon) => ({
      name: tutorialNameFromTooltip(icon.tooltip, '地图点位'),
      description: (icon.tags || []).join(' / ') || '悬停查看说明',
      icon: icon.icon,
      fallback: icon.entity_type,
    })));
  const identifySamples = uniqueTutorialSamples(boardIcons
    .filter((icon) => (icon.tags || []).includes('可鉴别'))
    .map((icon) => ({
      name: tutorialNameFromTooltip(icon.tooltip, '可鉴别物'),
      description: '进入鉴别范围后会自动结算',
      icon: icon.icon,
      fallback: icon.entity_type,
    })), 4);
  const itemSamples = uniqueTutorialSamples((state?.hand_details || []).map((item) => ({
    name: item.name,
    description: `${itemTypeLabel(item.type)}，行动阶段可按条件使用`,
    icon: item.icon,
    fallback: item.type,
  })), 6);
  const targetSamples = uniqueTutorialSamples(boardIcons
    .filter((icon) => ['monster', 'boss'].includes(icon.entity_type))
    .map((icon) => ({
      name: tutorialNameFromTooltip(icon.tooltip, icon.entity_type === 'boss' ? 'Boss' : '敌人'),
      description: icon.entity_type === 'boss' ? '最终对战目标' : '地图敌人',
      icon: icon.icon,
      fallback: icon.entity_type,
    })), 4);

  return [
    {
      title: '当前 UI',
      body: [
        '左侧是角色状态和地图缩放，中间是地图，右侧可以切换道具栏和日志。',
        '顶部会显示回合、坐标和楼层，撤退会结束当前对局。',
      ],
      image: { src: currentLayerBackground(state), alt: '当前地图背景' },
    },
    {
      title: '双蓝骰移动',
      body: [
        '每回合会自动掷出两个蓝色骰子，点选地图格即可预览并执行移动。',
        '一枚骰子限制纵向距离，另一枚限制横向距离，两枚骰子可以互换分配。',
        '移动路径最多支持一次转弯，不能经过阻挡或拦截格；超出范围时会显示可移动外轮廓。',
      ],
      image: { src: '/static/images/dice.webp', alt: '骰子' },
    },
    {
      title: '鉴别',
      body: [
        '鉴别范围不是攻击范围，它只负责触发地图物件结算。',
        '经过可鉴别物，或停留后覆盖到门、保险箱、宝箱、战利品时，会自动执行鉴别。',
        '鉴别可以开门、开启保险箱和宝箱，并把可转化物品折算为方斯。',
      ],
      samples: identifySamples.length ? identifySamples : [
        { name: '门', description: '鉴别后开启', fallback: 'door' },
        { name: '保险箱', description: '鉴别后开启并获得战利品', fallback: 'chest' },
        { name: '可鉴别物', description: '鉴别后转化为方斯', fallback: 'event' },
      ],
    },
    {
      title: '鉴别经验与 Combo',
      body: [
        '成功鉴别会积累鉴别经验，经验条在左侧地图缩放上方，升级后鉴别范围会提升。',
        '连续成功鉴别会提升 Combo，Combo 会提高经验获取效率，最高提升 100%。',
        '4 级后经验条满时会改为随机奖励：保险箱追加判定、攻防提升或获得金棋子。',
      ],
      samples: [
        { name: '经验条', description: '绿色进度条，只显示进度不显示具体数值', fallback: 'intel' },
        { name: 'Combo', description: '达到 10 后出现火焰动效', fallback: 'event' },
      ],
    },
    {
      title: '地图上的道具',
      body: [
        '地图上的箱子、保险箱、桌面产物、传送门和机关会以图标叠在地图上。',
        '悬停图标可以查看说明；点选可通行格会预览并执行移动。',
      ],
      samples: mapSamples.length ? mapSamples : [
        { name: '宝箱', description: '接近后可触发产物', fallback: 'chest' },
        { name: '传送门', description: '进入后触发地图效果', fallback: 'portal' },
      ],
    },
    {
      title: '道具栏操作',
      body: [
        '右侧道具页展示当前持有的道具。行动阶段通常每回合可使用 1 个可用道具。',
        '悬停或点按道具可以查看说明，按钮变灰表示当前不能使用。',
      ],
      samples: itemSamples.length ? itemSamples : [
        { name: '方斯', description: '小吱的专属资源道具', icon: '/static/images/item/fons.webp', fallback: 'currency' },
      ],
    },
    {
      title: '对战目标',
      body: [
        '怪物和 Boss 是主要对战目标，贴身相邻时会触发我方直接攻击和敌方反击。',
        '敌人的远程攻击使用怪物自己的射程，和我方鉴别范围无关。',
        '当前目标是探索地图、收集产物、保持存活，并击败最终目标。',
      ],
      samples: targetSamples.length ? targetSamples : [
        { name: '敌人', description: '阻挡道路并造成伤害', fallback: 'monster' },
        { name: 'Boss', description: '最终对战目标', fallback: 'boss' },
      ],
    },
  ];
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
  return /\.(png|jpg|jpeg|webp|gif|svg)$/i.test(value) || String(value).startsWith('/static/');
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
  const currentLayer = activeLayer(state);
  const shouldResetMapZoom = !initialCameraCentered || lastRenderedLayer !== currentLayer;
  const character = state.selected_character || state.character_instance || {};
  phaseChip.textContent = prettyPhase(state.phase);
  phaseChip.className = `phase-chip phase-${classToken(state.phase)}`;
  document.body.dataset.phase = classToken(state.phase);
  routeHint.textContent = state.route_hint;
  mapName.textContent = state.map.name;
  mapBackground.src = currentLayerBackground(state);
  updateMapContentSize(state);
  syncMapZoomLimit(state);
  if (shouldResetMapZoom) {
    setMapZoom(middleMapZoom(state), { immediate: true });
  }
  renderCombatHud(state);

  statsGrid.innerHTML = `
    ${statCard('角色', character.name || '-', { tone: 'role' })}
    ${statCard('生命', `${state.player.hp} / ${state.player.max_hp}`, { tone: 'hp', current: state.player.hp, max: state.player.max_hp })}
    ${statCard('攻击', state.computed_stats.attack || state.player.attack || 0, { tone: 'attack' })}
    ${statCard('防御', state.computed_stats.defense || state.player.defense || 0, { tone: 'defense' })}
  `;
  renderIdentificationProgress(state);
  renderBuffPanel(state);

  renderMapGrid(state);
  renderOverlay(state);
  renderBossHud(state);
  renderHand(state);
  renderLog(state);
  syncButtons(state);
  refreshActivePreview();
  clampMapCamera();
  applyMapCamera();
  if (shouldResetMapZoom) {
    centerCameraOnPlayer(state, { smooth: false });
  }
  if (!initialCameraCentered) {
    initialCameraCentered = true;
  }
  lastRenderedLayer = currentLayer;
}

function renderIdentificationProgress(state) {
  const progress = state.identification_progress || {};
  const combo = Number(progress.combo || 0);
  const bonusPercent = Number(progress.bonus_percent || 0);
  identificationCombo.textContent = `Combo ${combo}`;
  identificationCombo.classList.toggle('combo-fire', Boolean(progress.fire_combo));
  identificationLevelLabel.textContent = progress.is_max_level
    ? `鉴别 Lv.${progress.level || 4} · Buff`
    : `鉴别 Lv.${progress.level || state.computed_stats?.identification_level || 1}`;
  identificationBonusLabel.textContent = `经验效率 +${bonusPercent}%`;
  identificationExpFill.style.width = `${Math.max(0, Math.min(100, Number(progress.progress_percent || 0)))}%`;
}

function renderBuffPanel(state) {
  if (!buffPanel) {
    return;
  }
  const buffs = (state?.player_buffs || [])
    .map((buff) => String(buff.display_text || '').trim())
    .filter(Boolean);
  buffPanel.innerHTML = `
    <span>当前 Buff</span>
    <strong>${buffs.length ? buffs.join(' / ') : '暂无'}</strong>
  `;
}

function renderCombatHud(state) {
  const currentLayer = state.map.current_layer || 1;
  const totalLayers = state.map.total_layers || 1;
  const dice = pendingDice(state);
  combatHud.innerHTML = `
    <span>回合 ${state.turn}</span>
    <span>坐标 ${state.player.x}/${state.player.y}</span>
    <span>层数 ${currentLayer}/${totalLayers}</span>
    <span class="hud-dice">
      <img src="/static/images/dice.webp" alt="蓝骰A"><b>${dice ? dice.a : '-'}</b>
      <img src="/static/images/dice.webp" alt="蓝骰B"><b>${dice ? dice.b : '-'}</b>
    </span>
  `;
}

function renderMapGrid(state) {
  const layer = activeLayer(state);
  const width = mapWidth(state, layer);
  const height = mapHeight(state, layer);
  const tileByKey = new Map();
  (state.map.tiles || []).filter((tile) => onLayer(tile, layer)).forEach((tile) => {
    forEachTileCell(tile, (x, y) => {
      tileByKey.set(cellKey(x, y), tile);
    });
  });
  const monsterByKey = new Map((state.map.monsters || []).filter((monster) => onLayer(monster, layer) && monster.hp > 0 && !monster.captured).map((monster) => [cellKey(monster.x, monster.y), monster]));
  const bossKeys = new Set((state.map.boss?.positions || []).filter((pos) => onLayer(pos, layer)).map((pos) => cellKey(pos.x, pos.y)));

  mapGridLayer.style.setProperty('--grid-cell-width', `${100 / width}%`);
  mapGridLayer.style.setProperty('--grid-cell-height', `${100 / height}%`);
  mapGridLayer.innerHTML = '';

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (isHiddenCell(state, x, y, layer)) {
        const cell = document.createElement('span');
        const bounds = cellBounds(x, y, state);
        cell.className = 'map-cell cell-hidden-zone';
        cell.style.left = `${bounds.left}%`;
        cell.style.top = `${bounds.top}%`;
        cell.style.width = `${bounds.width}%`;
        cell.style.height = `${bounds.height}%`;
        mapGridLayer.appendChild(cell);
        continue;
      }
      const tile = tileByKey.get(cellKey(x, y));
      const tileType = tileDisplayType(tile);
      const hasMonster = monsterByKey.has(cellKey(x, y));
      const hasBoss = bossKeys.has(cellKey(x, y));
      if (tileType === 'floor' && !hasMonster && !hasBoss) {
        continue;
      }
      const cell = document.createElement('span');
      const bounds = cellBounds(x, y, state);
      cell.className = `map-cell cell-${classToken(tileType)}`;
      cell.style.left = `${bounds.left}%`;
      cell.style.top = `${bounds.top}%`;
      cell.style.width = `${bounds.width}%`;
      cell.style.height = `${bounds.height}%`;
      if (hasMonster) {
        cell.classList.add('cell-monster');
      }
      if (hasBoss) {
        cell.classList.add('cell-boss');
      }
      if (tileType === 'wall') {
        if (visibleTileDisplayType(state, tileByKey.get(cellKey(x, y - 1)), x, y - 1, layer) !== 'wall') {
          cell.classList.add('wall-edge-top');
        }
        if (visibleTileDisplayType(state, tileByKey.get(cellKey(x + 1, y)), x + 1, y, layer) !== 'wall') {
          cell.classList.add('wall-edge-right');
        }
        if (visibleTileDisplayType(state, tileByKey.get(cellKey(x, y + 1)), x, y + 1, layer) !== 'wall') {
          cell.classList.add('wall-edge-bottom');
        }
        if (visibleTileDisplayType(state, tileByKey.get(cellKey(x - 1, y)), x - 1, y, layer) !== 'wall') {
          cell.classList.add('wall-edge-left');
        }
      }
      mapGridLayer.appendChild(cell);
    }
  }
}

function renderOverlay(state) {
  mapOverlay.innerHTML = '';
  hideMapTooltip();
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
    node.innerHTML = `${iconMarkup(icon.icon)}${icon.entity_type === 'player' ? '<span class="player-chip">我</span>' : ''}<span class="sr-only">${icon.tooltip}</span>`;
    if (icon.entity_type === 'player' && icon.is_current_player) {
      node.addEventListener('pointerenter', () => showIdentifyRange(icon));
      node.addEventListener('focus', () => showIdentifyRange(icon));
      node.addEventListener('pointerleave', clearMapRange);
      node.addEventListener('blur', clearMapRange);
    } else if (icon.entity_type === 'monster' || icon.entity_type === 'boss') {
      node.addEventListener('pointerenter', () => showThreatTarget(node, icon));
      node.addEventListener('pointermove', () => positionMapTooltip(node));
      node.addEventListener('pointerleave', () => hideThreatTarget(node));
      node.addEventListener('focus', () => showThreatTarget(node, icon));
      node.addEventListener('blur', () => hideThreatTarget(node));
    } else {
      node.addEventListener('pointerenter', () => showMapTarget(node, icon));
      node.addEventListener('pointermove', () => positionMapTooltip(node));
      node.addEventListener('pointerleave', () => hideMapTarget(node));
      node.addEventListener('focus', () => showMapTarget(node, icon));
      node.addEventListener('blur', () => hideMapTarget(node));
    }
    if (icon.entity_type !== 'player') {
      node.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        handleMapTargetSelection(Number(icon.x), Number(icon.y), node, icon);
      });
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
    const canPlay = item.can_play_this_turn !== false && state.phase === 'action' && !state.has_played_item;
    card.className = `hand-card item-card item-tool rarity-${classToken(item.rarity)} type-${classToken(item.type)}`;
    card.innerHTML = `
      <button class="item-tool-button" ${canPlay ? '' : 'disabled'} aria-label="使用${item.name}">
        <span class="item-art small" aria-hidden="true">${itemIconMarkup(item)}</span>
        ${stackLabel ? `<span class="item-stack">${stackLabel}</span>` : ''}
      </button>
    `;
    card.querySelector('button').addEventListener('click', (event) => {
      if (!canPlay) {
        return;
      }
      if (primeTouchControl(event, `item:${item.instance_id}`, card, () => showItemTooltip(card, item, stackLabel))) {
        return;
      }
      clearPrimedControl();
      playItem(item.instance_id);
    });
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
      <span class="card-tag">${itemTypeLabel(item.type)}</span>
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

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function mapTooltipHtml(text, tags = []) {
  const tagHtml = (tags || []).map((tag) => `<span class="map-tooltip-tag">${escapeHtml(tag)}</span>`).join('');
  return `
    ${tagHtml ? `<div class="map-tooltip-tags">${tagHtml}</div>` : ''}
    <div>${escapeHtml(text || '')}</div>
  `;
}

function showMapTooltip(anchor, text, tags = []) {
  if (!mapFloatingTooltip) {
    return;
  }
  mapFloatingTooltip.innerHTML = mapTooltipHtml(text, tags);
  mapFloatingTooltip.classList.add('open');
  mapFloatingTooltip.setAttribute('aria-hidden', 'false');
  positionMapTooltip(anchor);
}

function positionMapTooltip(anchor) {
  if (!mapFloatingTooltip || !mapFloatingTooltip.classList.contains('open')) {
    return;
  }
  const anchorRect = anchor.getBoundingClientRect();
  const tooltipRect = mapFloatingTooltip.getBoundingClientRect();
  const gap = 12;
  let left = anchorRect.left + (anchorRect.width / 2) - (tooltipRect.width / 2);
  left = Math.max(gap, Math.min(left, window.innerWidth - tooltipRect.width - gap));
  let top = anchorRect.top - tooltipRect.height - gap;
  if (top < gap) {
    top = anchorRect.bottom + gap;
  }
  top = Math.max(gap, Math.min(top, window.innerHeight - tooltipRect.height - gap));
  mapFloatingTooltip.style.left = `${left}px`;
  mapFloatingTooltip.style.top = `${top}px`;
}

function hideMapTooltip() {
  if (!mapFloatingTooltip) {
    return;
  }
  mapFloatingTooltip.classList.remove('open');
  mapFloatingTooltip.setAttribute('aria-hidden', 'true');
}

function itemStackLabel(item, state) {
  if (item.amount !== undefined && item.amount !== null) {
    return String(item.amount);
  }
  if (Number(item.quantity || 0) > 1) {
    return String(item.quantity);
  }
  if (item.cooldown_until_turn && Number(item.cooldown_until_turn) > Number(state.turn || 1)) {
    return `CD ${Number(item.cooldown_until_turn) - Number(state.turn || 1)}`;
  }
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
  clearMapRange();
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

function showIdentifyRange(icon) {
  if (!currentState) {
    return;
  }
  hideMapTooltip();
  clearMapRange();
  const cells = identifyRangeCells(
    currentState,
    Number(icon?.x ?? currentState.player.x),
    Number(icon?.y ?? currentState.player.y),
    Number(currentState.computed_stats?.identification_level || currentState.player.identification_level || 1),
  );
  cells.forEach((cell) => {
    const marker = document.createElement('span');
    marker.className = 'range-cell identify-range-cell';
    const bounds = cellBounds(cell.x, cell.y);
    marker.style.left = `${bounds.left}%`;
    marker.style.top = `${bounds.top}%`;
    marker.style.width = `${bounds.width}%`;
    marker.style.height = `${bounds.height}%`;
    mapRangeLayer.appendChild(marker);
  });
  routeHint.textContent = `鉴别范围：${cells.length} 格。`;
}

function clearMapRange() {
  mapRangeLayer.innerHTML = '';
  if (activePreview) {
    renderPreview(activePreview);
  } else if (currentState) {
    routeHint.textContent = currentState.route_hint;
  }
}

const clearThreatRange = clearMapRange;

function resolveThreat(icon) {
  if (icon.entity_type === 'boss') {
    return currentState.map.boss;
  }
  const layer = activeLayer(currentState);
  return (currentState.map.monsters || []).find((monster) => (
    onLayer(monster, layer) && monster.hp > 0 && !monster.captured && monster.x === icon.x && monster.y === icon.y
  ));
}

function rangeCellsForThreat(threat) {
  const range = Number(threat.range || 1);
  const layer = activeLayer(currentState);
  const width = mapWidth(currentState, layer);
  const height = mapHeight(currentState, layer);
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
        if (seen.has(key) || x < 0 || y < 0 || x >= width || y >= height) {
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

function identifyOffsets(level) {
  const normalized = Math.max(1, Math.min(4, Number(level) || 1));
  if (normalized === 1) {
    return [
      { x: 0, y: -1 },
      { x: -1, y: 0 },
      { x: 1, y: 0 },
      { x: 0, y: 1 },
    ];
  }
  if (normalized === 2) {
    return squareOffsets(1);
  }
  if (normalized === 3) {
    return [
      ...squareOffsets(1),
      { x: 0, y: -2 },
      { x: -2, y: 0 },
      { x: 2, y: 0 },
      { x: 0, y: 2 },
    ];
  }
  return squareOffsets(2);
}

function squareOffsets(radius) {
  const offsets = [];
  for (let dy = -radius; dy <= radius; dy += 1) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      if (dx !== 0 || dy !== 0) {
        offsets.push({ x: dx, y: dy });
      }
    }
  }
  return offsets;
}

function identifyRangeCells(state, originX = state.player.x, originY = state.player.y, level = state.computed_stats?.identification_level || 1) {
  const width = mapWidth(state);
  const height = mapHeight(state);
  return identifyOffsets(level)
    .map((offset) => ({ x: Number(originX) + offset.x, y: Number(originY) + offset.y }))
    .filter((cell) => cell.x >= 0 && cell.y >= 0 && cell.x < width && cell.y < height);
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
  if (!tile?.opened && (['safe', 'large_safe'].includes(tile?.type) || ['safe', 'large_safe'].includes(tile?.object_id))) {
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
  if (tile.type === 'keycard_door') {
    return tile.locked === false ? 'floor' : 'door';
  }
  if (tile.type === 'hidden_door') {
    return 'door';
  }
  if (tile.opened && ['safe', 'large_safe'].includes(tile.object_id || tile.type)) {
    return 'floor';
  }
  if (['safe', 'large_safe'].includes(tile.type)) {
    return 'chest';
  }
  if (tile.type === 'boss_tile') {
    return 'floor';
  }
  if (turnBeltDirection(tile)) {
    return 'turn_belt';
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
    Object.keys(tile).forEach((key) => {
      delete tile[key];
    });
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
  const width = mapWidth(currentState);
  const height = mapHeight(currentState);
  return {
    left: (x / width) * 100,
    top: (y / height) * 100,
    width: 100 / width,
    height: 100 / height,
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
  clearPrimedControl();
}

function syncButtons(state) {
  directionButtons.forEach((button) => {
    button.disabled = moveLocked || !canPreview(state);
  });
  if (mapStage) {
    mapStage.classList.toggle('can-select-target', canPreview(state) && !moveLocked);
  }
}

function usesTouchPriming() {
  return window.matchMedia('(hover: none), (pointer: coarse)').matches;
}

function clearPrimedControl() {
  if (primedControl?.element) {
    primedControl.element.classList.remove('touch-primed');
  }
  primedControl = null;
}

function primeTouchControl(event, key, element, previewCallback) {
  if (!usesTouchPriming()) {
    return false;
  }
  if (primedControl?.key === key) {
    return false;
  }
  clearPrimedControl();
  primedControl = { key, element };
  element.classList.add('touch-primed');
  if (previewCallback) {
    previewCallback();
  }
  event.preventDefault();
  event.stopPropagation();
  return true;
}

function canPreview(state) {
  return state && ['action', 'movement'].includes(state.phase) && pendingDice(state) !== null;
}

function pendingDice(state = currentState) {
  const dice = state?.pending_dice;
  if (dice && typeof dice === 'object' && !Array.isArray(dice)) {
    const a = Number(dice.a ?? dice.vertical);
    const b = Number(dice.b ?? dice.horizontal);
    if (Number.isFinite(a) && Number.isFinite(b)) {
      return { a: Math.max(0, a), b: Math.max(0, b) };
    }
  }
  if (Array.isArray(dice) && dice.length >= 2) {
    const a = Number(dice[0]);
    const b = Number(dice[1]);
    if (Number.isFinite(a) && Number.isFinite(b)) {
      return { a: Math.max(0, a), b: Math.max(0, b) };
    }
  }
  if (state?.pending_die !== null && state?.pending_die !== undefined) {
    const legacy = Math.max(0, Number(state.pending_die) || 0);
    return { a: legacy, b: legacy };
  }
  return null;
}

function axisWithinDiceRange(horizontal, vertical, dice = pendingDice()) {
  if (!dice) {
    return false;
  }
  return (
    (vertical <= dice.a && horizontal <= dice.b)
    || (vertical <= dice.b && horizontal <= dice.a)
  );
}

function axisStepsForDirections(directions) {
  return directions.reduce((result, direction) => {
    const vector = DIRECTION_VECTORS[direction];
    if (vector?.x) {
      result.horizontal += 1;
    }
    if (vector?.y) {
      result.vertical += 1;
    }
    return result;
  }, { horizontal: 0, vertical: 0 });
}

function cellKey(x, y) {
  return `${x}:${y}`;
}

function hiddenCellEntries(state = currentState) {
  return Array.isArray(state?.map?.hidden_cells) ? state.map.hidden_cells : [];
}

function activeLayer(state = currentState) {
  return Number(state?.map?.current_layer || state?.board?.current_layer || 1);
}

function isHiddenCell(state, x, y, layer = activeLayer(state)) {
  if (!state?.map || state.map.hidden_room_revealed) {
    return false;
  }
  return hiddenCellEntries(state).some((cell) => (
    Number(cell.layer || 1) === Number(layer)
    && Number(cell.x) === Number(x)
    && Number(cell.y) === Number(y)
  ));
}

function visibleTileDisplayType(state, tile, x, y, layer = activeLayer(state)) {
  if (isHiddenCell(state, x, y, layer)) {
    return 'floor';
  }
  return tileDisplayType(tile);
}

function mapLayerInfo(state = currentState, layer = activeLayer(state)) {
  const layers = state?.map?.layers || state?.board?.layers || [];
  const matched = layers.find((item) => Number(item?.layer || 1) === Number(layer));
  return matched || {
    width: state?.board?.width || state?.map?.width || 1,
    height: state?.board?.height || state?.map?.height || 1,
  };
}

function currentLayerBackground(state = currentState, layer = activeLayer(state)) {
  return mapLayerInfo(state, layer).background_image
    || state?.board?.background_image
    || state?.map?.background_image
    || '/static/images/maps/rob_bank_abandoned_city.png';
}

function mapWidth(state = currentState, layer = activeLayer(state)) {
  return Math.max(1, Number(mapLayerInfo(state, layer).width || 1));
}

function mapHeight(state = currentState, layer = activeLayer(state)) {
  return Math.max(1, Number(mapLayerInfo(state, layer).height || 1));
}

function onLayer(entity, layer = activeLayer()) {
  return Number(entity?.layer || 1) === Number(layer);
}

function cellPercent(point, state = currentState) {
  return {
    left: ((point.x + 0.5) / mapWidth(state)) * 100,
    top: ((point.y + 0.5) / mapHeight(state)) * 100,
  };
}

function tileAt(state, x, y) {
  const layer = activeLayer(state);
  return (state.map.tiles || []).slice().reverse().find((tile) => onLayer(tile, layer) && tileContainsCell(tile, x, y)) || null;
}

function tileFootprintWidth(tile) {
  return Math.max(1, Number(tile?.width || 1));
}

function tileFootprintHeight(tile) {
  return Math.max(1, Number(tile?.height || 1));
}

function tileContainsCell(tile, x, y) {
  const tileX = Number(tile?.x || 0);
  const tileY = Number(tile?.y || 0);
  return x >= tileX && y >= tileY && x < tileX + tileFootprintWidth(tile) && y < tileY + tileFootprintHeight(tile);
}

function forEachTileCell(tile, callback) {
  const startX = Number(tile?.x || 0);
  const startY = Number(tile?.y || 0);
  for (let dy = 0; dy < tileFootprintHeight(tile); dy += 1) {
    for (let dx = 0; dx < tileFootprintWidth(tile); dx += 1) {
      callback(startX + dx, startY + dy);
    }
  }
}

function isMonsterCell(state, x, y) {
  const layer = activeLayer(state);
  return (state.map.monsters || []).some((monster) => onLayer(monster, layer) && monster.hp > 0 && !monster.captured && monster.x === x && monster.y === y);
}

function isBossCell(state, x, y) {
  const boss = state.map.boss || {};
  const layer = activeLayer(state);
  return boss.hp > 0 && (boss.positions || []).some((pos) => onLayer(pos, layer) && pos.x === x && pos.y === y);
}

function isPassableHiddenDoor(tile) {
  return tile?.type === 'hidden_door' || tile?.object_id === 'hidden_door';
}

function getBasicBlockReason(state, x, y) {
  if (x < 0 || y < 0 || x >= mapWidth(state) || y >= mapHeight(state)) {
    return '边界';
  }
  if (isHiddenCell(state, x, y)) {
    return '隐藏区域尚未发现';
  }
  if (isMonsterCell(state, x, y)) {
    return '怪物阻挡';
  }
  if (isBossCell(state, x, y)) {
    return 'Boss 占位';
  }
  const tile = tileAt(state, x, y);
  if (isPassableHiddenDoor(tile)) {
    return null;
  }
  const displayType = tileDisplayType(tile);
  if (displayType === 'wall') {
    return '墙体阻挡';
  }
  if (displayType === 'door' && tile?.locked !== false) {
    return '门阻挡';
  }
  if (!tile?.opened && (['safe', 'large_safe'].includes(tile?.type) || ['safe', 'large_safe'].includes(tile?.object_id))) {
    return '保险箱阻挡';
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
  return turnBeltDirection(tile);
}

function turnBeltDirection(tile) {
  if (!tile) {
    return null;
  }
  const direction = TURN_BELT_DIRECTIONS[tile.object_id] || TURN_BELT_DIRECTIONS[tile.type] || (tile.object_id === 'turn_belt' ? tile.direction : null);
  return DIRECTION_VECTORS[direction] ? direction : null;
}

function buildMovePreview(state, direction) {
  if (!canPreview(state) || !DIRECTION_VECTORS[direction]) {
    return null;
  }
  let x = Number(state.player.x);
  let y = Number(state.player.y);
  let activeDirection = direction;
  const dice = pendingDice(state);
  let stepsRemaining = direction === 'left' || direction === 'right'
    ? Math.max(dice?.a || 0, dice?.b || 0)
    : Math.max(dice?.a || 0, dice?.b || 0);
  const path = [{ x, y, kind: 'start' }];
  const redirects = [];
  let blocked = null;
  let intercepted = null;
  let guard = 0;
  const startTurn = basicTurnDirection(tileAt(state, x, y), stepsRemaining);
  if (startTurn) {
    activeDirection = startTurn;
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

function showThreatTarget(node, icon) {
  showThreatRange(icon);
  showMapTooltip(node, icon.tooltip, icon.tags || []);
}

function hideThreatTarget(node = null) {
  if (node) {
    node.classList.remove('is-route-blocked');
  }
  clearMapRange();
  hideMapTooltip();
  clearPreview();
}

function showMapTarget(node, icon) {
  if (!canPreview(currentState) || moveLocked) {
    showMapTooltip(node, icon.tooltip, icon.tags || []);
    return;
  }
  const preview = buildTargetPreview(currentState, Number(icon.x), Number(icon.y), icon.tooltip || '地图目标');
  node._targetPreview = preview;
  node.classList.toggle('is-route-blocked', Boolean(preview?.blocked));
  renderPreview(preview);
  showMapTooltip(node, targetTooltipText(icon.tooltip, preview), targetTooltipTags(icon.tags || [], preview));
}

function hideMapTarget(node = null) {
  if (node) {
    node.classList.remove('is-route-blocked');
  }
  hideMapTooltip();
  clearPreview();
}

function targetTooltipText(baseText, preview) {
  const base = baseText || '地图目标';
  if (!preview) {
    return base;
  }
  if (preview.blocked) {
    return base;
  }
  const steps = Math.max(0, preview.path.length - 1);
  return `${base}。本次将移动 ${steps} 步${preview.turns ? '，路径会转弯一次' : ''}。`;
}

function targetTooltipTags(tags) {
  return [...tags];
}

function buildTargetPreview(state, targetX, targetY, targetLabel = '目标') {
  const start = { x: Number(state.player.x), y: Number(state.player.y) };
  const target = { x: Number(targetX), y: Number(targetY) };
  const base = {
    direction: 'target',
    path: [{ ...start, kind: 'start' }],
    landing: { ...start },
    redirects: [],
    targetLabel,
    target,
    moveDirections: [],
    turns: 0,
  };
  if (!Number.isInteger(target.x) || !Number.isInteger(target.y)) {
    return { ...base, blocked: { ...start, reason: '目标无效' } };
  }
  const horizontalSteps = Math.abs(target.x - start.x);
  const verticalSteps = Math.abs(target.y - start.y);
  const totalSteps = horizontalSteps + verticalSteps;
  const dice = pendingDice(state);
  if (totalSteps === 0) {
    return base;
  }
  if (!axisWithinDiceRange(horizontalSteps, verticalSteps, dice)) {
    return {
      ...base,
      blocked: { ...target, reason: '超过当前骰子范围' },
      rangeOutline: buildMoveRangeCells(state, dice),
      totalSteps,
    };
  }
  const candidates = oneTurnDirectionCandidates(start, target);
  const blocked = [];
  for (const directions of candidates) {
    const axisSteps = axisStepsForDirections(directions);
    if (!axisWithinDiceRange(axisSteps.horizontal, axisSteps.vertical, dice)) {
      continue;
    }
    const result = previewFromDirections(state, directions, target);
    if (!result.blocked) {
      return { ...result, targetLabel, target };
    }
    blocked.push(result.blocked);
  }
  return {
    ...base,
    blocked: blocked[0] || { ...target, reason: '路径受阻' },
    totalSteps,
  };
}

function buildMoveRangeCells(state, dice = pendingDice(state)) {
  if (!dice) {
    return [];
  }
  const origin = { x: Number(state.player.x), y: Number(state.player.y) };
  const width = mapWidth(state);
  const height = mapHeight(state);
  const maxX = Math.max(dice.a, dice.b);
  const maxY = Math.max(dice.a, dice.b);
  const cells = [];
  for (let dy = -maxY; dy <= maxY; dy += 1) {
    for (let dx = -maxX; dx <= maxX; dx += 1) {
      const x = origin.x + dx;
      const y = origin.y + dy;
      if (x < 0 || y < 0 || x >= width || y >= height) {
        continue;
      }
      if (isHiddenCell(state, x, y)) {
        continue;
      }
      if (axisWithinDiceRange(Math.abs(dx), Math.abs(dy), dice)) {
        cells.push({ x, y });
      }
    }
  }
  return cells;
}

function oneTurnDirectionCandidates(start, target) {
  const horizontal = target.x > start.x ? 'right' : 'left';
  const vertical = target.y > start.y ? 'down' : 'up';
  const dx = Math.abs(target.x - start.x);
  const dy = Math.abs(target.y - start.y);
  const horizontalLeg = Array(dx).fill(horizontal);
  const verticalLeg = Array(dy).fill(vertical);
  if (dx === 0) {
    return [verticalLeg];
  }
  if (dy === 0) {
    return [horizontalLeg];
  }
  return [
    [...horizontalLeg, ...verticalLeg],
    [...verticalLeg, ...horizontalLeg],
  ];
}

function previewFromDirections(state, directions, target) {
  let x = Number(state.player.x);
  let y = Number(state.player.y);
  const path = [{ x, y, kind: 'start' }];
  let previousDirection = null;
  let turns = 0;
  for (const direction of directions) {
    const vector = DIRECTION_VECTORS[direction];
    x += vector.x;
    y += vector.y;
    const isFinal = x === Number(target.x) && y === Number(target.y);
    const tile = tileAt(state, x, y);
    const reason = getPathObstacleReason(state, x, y, { allowIntercept: isFinal && isBasicIntercept(tile) });
    if (reason) {
      return {
        direction: 'target',
        path,
        landing: path[path.length - 1],
        redirects: [],
        blocked: { x, y, reason },
        moveDirections: [],
        turns,
      };
    }
    if (previousDirection && direction !== previousDirection) {
      turns += 1;
    }
    previousDirection = direction;
    path.push({ x, y, kind: isFinal ? 'landing' : 'step', direction });
    if (!isFinal && isBasicIntercept(tile)) {
      return {
        direction: 'target',
        path,
        landing: { x, y },
        redirects: [],
        blocked: { x, y, reason: '拦截格阻断路径' },
        moveDirections: [],
        turns,
      };
    }
  }
  return {
    direction: 'target',
    path,
    landing: path[path.length - 1],
    redirects: [],
    blocked: null,
    moveDirections: directionsForPath(path),
    turns,
  };
}

function getPathObstacleReason(state, x, y, target = null) {
  const blockReason = getBasicBlockReason(state, x, y);
  if (blockReason) {
    return blockReason;
  }
  const tile = tileAt(state, x, y);
  if (isBasicIntercept(tile) && !target?.allowIntercept) {
    return '拦截格阻断路径';
  }
  return null;
}

function directionsForPath(path) {
  const directions = [];
  for (let index = 1; index < path.length; index += 1) {
    const previous = path[index - 1];
    const current = path[index];
    const direction = directionBetween(previous, current);
    if (!direction) {
      return [];
    }
    directions.push(direction);
  }
  return directions;
}

function directionBetween(from, to) {
  return Object.entries(DIRECTION_VECTORS).find(([, vector]) => (
    Number(from.x) + vector.x === Number(to.x)
    && Number(from.y) + vector.y === Number(to.y)
  ))?.[0] || null;
}

function renderPreview(preview) {
  activePreview = preview;
  mapPreviewLayer.innerHTML = '';
  if (!preview || !currentState) {
    routeHint.textContent = currentState?.route_hint || '等待加载';
    return;
  }

  if (preview.rangeOutline?.length) {
    addMoveRangeOutline(preview.rangeOutline);
  }

  preview.path.forEach((point, index) => {
    if (index > 0) {
      addPreviewSegment(preview.path[index - 1], point);
    }
  });

  preview.path.forEach((point, index) => {
    const pos = cellPercent(point);
    const bounds = cellBounds(point.x, point.y);
    const sizeScale = index === 0 ? 0.42 : 0.78;
    const marker = document.createElement('span');
    marker.className = `preview-dot preview-${point.kind}`;
    marker.style.left = `${pos.left}%`;
    marker.style.top = `${pos.top}%`;
    marker.style.width = `${bounds.width * sizeScale}%`;
    marker.style.height = `${bounds.height * sizeScale}%`;
    marker.textContent = shouldShowPreviewIndex(index) ? String(index) : '';
    mapPreviewLayer.appendChild(marker);
  });

  if (preview.blocked && !preview.rangeOutline?.length) {
    const pos = cellPercent(preview.blocked);
    const bounds = cellBounds(preview.blocked.x, preview.blocked.y);
    const block = document.createElement('span');
    block.className = 'preview-block';
    block.style.left = `${pos.left}%`;
    block.style.top = `${pos.top}%`;
    block.style.width = `${bounds.width * 0.86}%`;
    block.style.height = `${bounds.height * 0.86}%`;
    block.textContent = '×';
    mapPreviewLayer.appendChild(block);
  }

  const reason = preview.blocked?.reason || preview.intercepted?.reason;
  const target = preview.blocked ? preview.blocked : preview.landing;
  if (preview.targetLabel) {
    routeHint.textContent = reason
      ? `目标路径：${reason}。`
      : `目标路径：移动 ${preview.path.length - 1} 步至 (${preview.landing.x}, ${preview.landing.y})${preview.turns ? '，转弯一次' : ''}。`;
    return;
  }
  routeHint.textContent = reason
    ? `预览：${preview.path.length - 1} 步后在 (${preview.landing.x}, ${preview.landing.y}) 停止，${reason} 于 (${target.x}, ${target.y})。`
    : `预览：落点 (${preview.landing.x}, ${preview.landing.y})。${preview.redirects.length ? '途中会发生转向。' : ''}`;
}

function currentCellPixelSize(state = currentState, layer = activeLayer(state)) {
  if (!state?.map) {
    return 0;
  }
  const cellWidth = (mapCamera.baseWidth / mapWidth(state, layer)) * mapCamera.zoom;
  const cellHeight = (mapCamera.baseHeight / mapHeight(state, layer)) * mapCamera.zoom;
  return Math.max(0, Math.min(cellWidth, cellHeight));
}

function shouldShowPreviewIndex(index, state = currentState) {
  return index > 0 && currentCellPixelSize(state) >= 22;
}

function addMoveRangeOutline(cells) {
  const keys = new Set(cells.map((cell) => cellKey(cell.x, cell.y)));
  const edges = [
    { name: 'top', dx: 0, dy: -1 },
    { name: 'right', dx: 1, dy: 0 },
    { name: 'bottom', dx: 0, dy: 1 },
    { name: 'left', dx: -1, dy: 0 },
  ];
  cells.forEach((cell) => {
    const bounds = cellBounds(cell.x, cell.y);
    edges.forEach((edge) => {
      if (keys.has(cellKey(cell.x + edge.dx, cell.y + edge.dy))) {
        return;
      }
      const segment = document.createElement('span');
      segment.className = `move-range-outline-segment outline-${edge.name}`;
      segment.style.left = `${bounds.left}%`;
      segment.style.top = `${bounds.top}%`;
      segment.style.width = `${bounds.width}%`;
      segment.style.height = `${bounds.height}%`;
      mapPreviewLayer.appendChild(segment);
    });
  });
}

function addPreviewSegment(from, to) {
  const line = document.createElement('span');
  line.className = 'preview-line';
  if (Number(from.y) === Number(to.y)) {
    const y = Number(from.y);
    const leftX = Math.min(Number(from.x), Number(to.x));
    line.classList.add('preview-line-horizontal');
    line.style.left = `${((leftX + 0.5) / mapWidth(currentState)) * 100}%`;
    line.style.top = `${((y + 0.5) / mapHeight(currentState)) * 100}%`;
    line.style.width = `${(Math.abs(Number(to.x) - Number(from.x)) / mapWidth(currentState)) * 100}%`;
  } else if (Number(from.x) === Number(to.x)) {
    const x = Number(from.x);
    const topY = Math.min(Number(from.y), Number(to.y));
    line.classList.add('preview-line-vertical');
    line.style.left = `${((x + 0.5) / mapWidth(currentState)) * 100}%`;
    line.style.top = `${((topY + 0.5) / mapHeight(currentState)) * 100}%`;
    line.style.height = `${(Math.abs(Number(to.y) - Number(from.y)) / mapHeight(currentState)) * 100}%`;
  } else {
    return;
  }
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

function stageRect() {
  return mapStage.getBoundingClientRect();
}

function updateMapContentSize(state = currentState) {
  if (!mapStage || !mapStageInner || !state?.map) {
    return;
  }
  const width = mapWidth(state);
  const height = mapHeight(state);
  mapStage.style.setProperty('--map-aspect', `${width} / ${height}`);
  mapStage.style.setProperty('--map-aspect-number', String(width / height));
  const rect = stageRect();
  if (!rect.width || !rect.height) {
    return;
  }
  const mapAspect = width / height;
  const viewportAspect = rect.width / rect.height;
  if (viewportAspect > mapAspect) {
    mapCamera.baseHeight = rect.height;
    mapCamera.baseWidth = rect.height * mapAspect;
  } else {
    mapCamera.baseWidth = rect.width;
    mapCamera.baseHeight = rect.width / mapAspect;
  }
  mapStageInner.style.width = `${mapCamera.baseWidth}px`;
  mapStageInner.style.height = `${mapCamera.baseHeight}px`;
}

function currentMapMaxZoom(state = currentState) {
  if (!state?.map || !mapCamera.baseWidth || !mapCamera.baseHeight) {
    return MAP_MIN_ZOOM;
  }
  const cellWidth = mapCamera.baseWidth / mapWidth(state);
  const cellHeight = mapCamera.baseHeight / mapHeight(state);
  const baseCellPixels = Math.max(1, Math.min(cellWidth, cellHeight));
  return Math.max(MAP_MIN_ZOOM, Math.min(MAP_HARD_MAX_ZOOM, MAP_TARGET_CELL_PIXELS / baseCellPixels));
}

function middleMapZoom(state = currentState) {
  const maxZoom = currentMapMaxZoom(state);
  return MAP_MIN_ZOOM + ((maxZoom - MAP_MIN_ZOOM) / 2);
}

function syncMapZoomLimit(state = currentState) {
  const maxZoom = currentMapMaxZoom(state);
  if (mapZoomSlider) {
    mapZoomSlider.max = maxZoom.toFixed(2);
    mapZoomSlider.min = String(MAP_MIN_ZOOM);
  }
  if (mapCamera.zoom > maxZoom) {
    mapCamera.zoom = maxZoom;
  }
  if (mapZoomSlider) {
    mapZoomSlider.value = mapCamera.zoom.toFixed(2);
  }
}

function clampMapCameraPosition(x, y, zoom = mapCamera.zoom) {
  const rect = stageRect();
  if (!rect.width || !rect.height) {
    return { x: 0, y: 0 };
  }
  const baseWidth = mapCamera.baseWidth || rect.width;
  const baseHeight = mapCamera.baseHeight || rect.height;
  const scaledWidth = baseWidth * zoom;
  const scaledHeight = baseHeight * zoom;
  const clampedX = scaledWidth <= rect.width
    ? (rect.width - scaledWidth) / 2
    : Math.max(rect.width - scaledWidth, Math.min(0, x));
  const clampedY = scaledHeight <= rect.height
    ? (rect.height - scaledHeight) / 2
    : Math.max(rect.height - scaledHeight, Math.min(0, y));
  return {
    x: clampedX,
    y: clampedY,
  };
}

function clampMapCamera() {
  const clamped = clampMapCameraPosition(mapCamera.x, mapCamera.y);
  mapCamera.x = clamped.x;
  mapCamera.y = clamped.y;
}

function applyMapCamera(options = {}) {
  if (!mapStageInner) {
    return;
  }
  pendingMapCameraOptions = options;
  if (options.immediate) {
    applyMapCameraNow(options);
    return;
  }
  if (mapCameraFrame) {
    return;
  }
  mapCameraFrame = window.requestAnimationFrame(() => {
    mapCameraFrame = 0;
    applyMapCameraNow(pendingMapCameraOptions);
  });
}

function applyMapCameraNow(options = {}) {
  mapStageInner.style.setProperty('--map-zoom', mapCamera.zoom.toFixed(3));
  mapStageInner.classList.toggle('camera-smooth', Boolean(options.smooth));
  mapStageInner.style.transform = `translate3d(${mapCamera.x}px, ${mapCamera.y}px, 0) scale(${mapCamera.zoom})`;
}

function setMapZoom(value, options = {}) {
  const rect = stageRect();
  const nextZoom = Math.max(MAP_MIN_ZOOM, Math.min(currentMapMaxZoom(currentState), Number(value) || MAP_MIN_ZOOM));
  if (!rect.width || !rect.height) {
    mapCamera.zoom = nextZoom;
    applyMapCamera(options);
    return;
  }
  const focalX = Number.isFinite(options.focalClientX) ? options.focalClientX - rect.left : rect.width / 2;
  const focalY = Number.isFinite(options.focalClientY) ? options.focalClientY - rect.top : rect.height / 2;
  const centerWorldX = (focalX - mapCamera.x) / mapCamera.zoom;
  const centerWorldY = (focalY - mapCamera.y) / mapCamera.zoom;
  mapCamera.zoom = nextZoom;
  mapCamera.x = focalX - (centerWorldX * mapCamera.zoom);
  mapCamera.y = focalY - (centerWorldY * mapCamera.zoom);
  clampMapCamera();
  if (mapZoomSlider) {
    mapZoomSlider.value = mapCamera.zoom.toFixed(2);
  }
  applyMapCamera(options);
}

function centerCameraOnCell(x, y, options = {}) {
  if (!currentState) {
    return;
  }
  const rect = stageRect();
  if (!rect.width || !rect.height) {
    return;
  }
  const baseWidth = mapCamera.baseWidth || rect.width;
  const baseHeight = mapCamera.baseHeight || rect.height;
  const targetX = ((Number(x) + 0.5) / mapWidth(currentState)) * baseWidth * mapCamera.zoom;
  const targetY = ((Number(y) + 0.5) / mapHeight(currentState)) * baseHeight * mapCamera.zoom;
  const clamped = clampMapCameraPosition((rect.width / 2) - targetX, (rect.height / 2) - targetY);
  mapCamera.x = clamped.x;
  mapCamera.y = clamped.y;
  applyMapCamera({ smooth: options.smooth !== false });
}

function centerCameraOnPlayer(state = currentState, options = {}) {
  if (!state?.player) {
    return;
  }
  centerCameraOnCell(state.player.x, state.player.y, options);
}

function isCellVisible(x, y, state = currentState, marginCells = 0.3) {
  if (!state?.map) {
    return true;
  }
  const rect = stageRect();
  if (!rect.width || !rect.height) {
    return true;
  }
  const baseWidth = mapCamera.baseWidth || rect.width;
  const baseHeight = mapCamera.baseHeight || rect.height;
  const cellWidth = (baseWidth / mapWidth(state)) * mapCamera.zoom;
  const cellHeight = (baseHeight / mapHeight(state)) * mapCamera.zoom;
  const screenX = mapCamera.x + (((Number(x) + 0.5) / mapWidth(state)) * baseWidth * mapCamera.zoom);
  const screenY = mapCamera.y + (((Number(y) + 0.5) / mapHeight(state)) * baseHeight * mapCamera.zoom);
  const marginX = cellWidth * marginCells;
  const marginY = cellHeight * marginCells;
  return screenX >= marginX
    && screenY >= marginY
    && screenX <= rect.width - marginX
    && screenY <= rect.height - marginY;
}

function ensureCameraShowsPlayer(state = currentState, options = {}) {
  if (!state?.player || isCellVisible(state.player.x, state.player.y, state)) {
    return;
  }
  centerCameraOnPlayer(state, options);
}

function mapPointFromClient(event) {
  if (!currentState || !mapStageInner) {
    return null;
  }
  const rect = mapStageInner.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }
  const x = Math.floor(((event.clientX - rect.left) / rect.width) * mapWidth(currentState));
  const y = Math.floor(((event.clientY - rect.top) / rect.height) * mapHeight(currentState));
  if (x < 0 || y < 0 || x >= mapWidth(currentState) || y >= mapHeight(currentState)) {
    return null;
  }
  if (isHiddenCell(currentState, x, y)) {
    return null;
  }
  return { x, y };
}

function isOverlayTarget(event) {
  return Boolean(event?.target?.closest?.('.overlay-token'));
}

function finishMapDrag(event = null) {
  if (!mapCamera.dragging) {
    return;
  }
  const pointerId = mapCamera.pointerId;
  const shouldSelect = Boolean(
    event
      && pointerId === event.pointerId
      && !mapCamera.dragMoved
      && !isOverlayTarget(event),
  );
  if (pointerId !== null && mapStage?.hasPointerCapture(pointerId)) {
    mapStage.releasePointerCapture(pointerId);
  }
  mapCamera.dragging = false;
  mapCamera.dragMoved = false;
  mapCamera.pointerId = null;
  mapStage?.classList.remove('drag-ready', 'dragging');
  if (shouldSelect) {
    handleMapPointerSelection(event);
  }
}

function showMapPointerPreview(event) {
  if (mapCamera.dragging || event.target.closest('.overlay-token')) {
    return;
  }
  const point = mapPointFromClient(event);
  const key = point ? cellKey(point.x, point.y) : '';
  if (!point) {
    hoveredMapCellKey = null;
    clearPreview();
    return;
  }
  if (key === hoveredMapCellKey) {
    return;
  }
  hoveredMapCellKey = key;
  renderPreview(buildTargetPreview(currentState, point.x, point.y, '地图格'));
}

function handleMapPointerSelection(event) {
  const point = mapPointFromClient(event);
  if (!point) {
    return;
  }
  handleMapTargetSelection(point.x, point.y);
}

function handleMapTargetSelection(x, y, node = null, icon = null) {
  if (moveLocked || !canPreview(currentState)) {
    if (node && icon) {
      showMapTooltip(node, icon.tooltip, icon.tags || []);
    }
    return;
  }
  clearPrimedControl();
  const preview = buildTargetPreview(currentState, Number(x), Number(y), icon?.tooltip || '地图格');
  if (node) {
    node._targetPreview = preview;
    node.classList.toggle('is-route-blocked', Boolean(preview?.blocked));
  }
  renderPreview(preview);
  if (preview?.blocked || !preview?.moveDirections?.length) {
    if (node && icon) {
      showMapTooltip(node, targetTooltipText(icon.tooltip, preview), targetTooltipTags(icon.tags || [], preview));
    }
    return;
  }
  move(preview.moveDirections[0], preview.moveDirections);
}

async function animatePreview(preview) {
  if (!preview || preview.path.length <= 1) {
    return;
  }
  const ghost = document.createElement('span');
  ghost.className = 'move-ghost';
  const avatar = currentState?.character_instance?.avatar_image;
  ghost.innerHTML = avatar ? `<img src="${avatar}" alt="">` : iconMarkup('player');
  const start = cellPercent(preview.path[0]);
  const bounds = cellBounds(preview.path[0].x, preview.path[0].y);
  ghost.style.left = `${start.left}%`;
  ghost.style.top = `${start.top}%`;
  ghost.style.width = `${bounds.width * 0.92}%`;
  ghost.style.height = `${bounds.height * 0.92}%`;
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
  ensureCameraShowsPlayer(currentState, { smooth: true });
  await animatePreview({ path });
}

async function flashIdentifyRange(step) {
  if (!currentState || Number(step.layer || activeLayer(currentState)) !== activeLayer(currentState)) {
    return;
  }
  (step.cells || []).forEach((cell) => {
    const marker = document.createElement('span');
    marker.className = 'identify-flash-cell';
    const bounds = cellBounds(Number(cell.x), Number(cell.y));
    marker.style.left = `${bounds.left}%`;
    marker.style.top = `${bounds.top}%`;
    marker.style.width = `${bounds.width}%`;
    marker.style.height = `${bounds.height}%`;
    mapFxLayer.appendChild(marker);
  });
  routeHint.textContent = `停留鉴别：${(step.cells || []).length} 格范围。`;
  await sleep(520);
  mapFxLayer.querySelectorAll('.identify-flash-cell').forEach((node) => node.remove());
}

async function playActionQueue(queue, nextState) {
  let showedBattle = false;
  for (const step of queue || []) {
    if (step.type === 'move') {
      await animateBackendMove(step);
    } else if (step.type === 'identify_range') {
      await flashIdentifyRange(step);
    } else if (step.type === 'tile_update') {
      applyTileUpdate(step);
    } else if (step.type === 'popup') {
      await showEventPopup(step);
    } else if (step.type === 'battle') {
      showedBattle = true;
      await showBattlePopup(step, nextState);
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
  const monsters = (state.map.monsters || []).filter((monster) => onLayer(monster, layer) && monster.hp > 0 && !monster.captured);
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

async function showBattlePopup(summary, after) {
  showBattleModalFromSummary(summary, after);
  await waitForBattleClose();
}

function waitForBattleClose() {
  return new Promise((resolve) => {
    const cleanup = () => {
      battleCloseBtn.removeEventListener('click', onCloseClick);
      battleModal.removeEventListener('click', onBackdropClick);
      document.removeEventListener('keydown', onKeyDown);
      resolve();
    };
    const finish = () => {
      closeBattleModal();
      cleanup();
    };
    const onCloseClick = () => finish();
    const onBackdropClick = (event) => {
      if (event.target === battleModal) {
        finish();
      }
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        finish();
      }
    };
    battleCloseBtn.addEventListener('click', onCloseClick);
    battleModal.addEventListener('click', onBackdropClick);
    document.addEventListener('keydown', onKeyDown);
  });
}

function closeBattleModal() {
  battleModal.classList.remove('open', 'battle-animating');
  battleModal.setAttribute('aria-hidden', 'true');
  battlePlayerCombatant.classList.remove('hit');
  battleEnemyCombatant.classList.remove('hit');
  ensureCameraShowsPlayer(currentState, { smooth: true });
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
    if (!tableTutorialInitialized) {
      tableTutorialInitialized = true;
      await initTutorialManual('table', {
        title: '对战页手册',
        eyebrow: '对战',
        pages: () => buildTableTutorialPages(currentState),
      });
    }
  } catch (error) {
    window.alert(error.message);
    window.location.href = '/build';
  }
}

async function playItem(itemInstanceId) {
  try {
    const item = (currentState?.hand_details || []).find((entry) => entry.instance_id === itemInstanceId);
    let declaredValue = null;
    if (item?.requires_die_choice) {
      const dice = pendingDice(currentState);
      const answer = window.prompt('宣言蓝骰点数（1-6）', String(dice?.a || 1));
      if (answer === null) {
        return;
      }
      declaredValue = Number(answer);
      if (!Number.isInteger(declaredValue) || declaredValue < 1 || declaredValue > 6) {
        window.alert('请输入 1 到 6 的整数。');
        return;
      }
    }
    const nextState = await apiRequest('/api/game/play-item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_instance_id: itemInstanceId, declared_value: declaredValue }),
    });
    await playActionQueue(nextState.action_queue || [], nextState);
    renderState(nextState);
  } catch (error) {
    window.alert(error.message);
  }
}

async function move(direction, path = null) {
  if (moveLocked) {
    return;
  }
  const beforeState = currentState;
  try {
    moveLocked = true;
    syncButtons(currentState);
    clearPreview();
    clearPrimedControl();
    const nextState = await apiRequest('/api/game/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ direction, path }),
    });
    const showedBattle = await playActionQueue(nextState.action_queue || [], nextState);
    renderState(nextState);
    clearPreview();
    ensureCameraShowsPlayer(nextState, { smooth: true });
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
  window.localStorage.removeItem('nte_token');
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
if (mapZoomSlider) {
  mapZoomSlider.addEventListener('input', () => {
    clearPrimedControl();
    setMapZoom(mapZoomSlider.value);
  });
}
if (mapStage) {
  mapStage.addEventListener('wheel', (event) => {
    event.preventDefault();
    clearPrimedControl();
    const nextZoom = mapCamera.zoom - (event.deltaY * 0.00065);
    setMapZoom(nextZoom, {
      focalClientX: event.clientX,
      focalClientY: event.clientY,
    });
  }, { passive: false });
  mapStage.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) {
      return;
    }
    if (isOverlayTarget(event)) {
      return;
    }
    clearPrimedControl();
    mapCamera.dragging = true;
    mapCamera.dragMoved = false;
    mapCamera.pointerId = event.pointerId;
    mapCamera.startX = event.clientX;
    mapCamera.startY = event.clientY;
    mapCamera.originX = mapCamera.x;
    mapCamera.originY = mapCamera.y;
    mapStage.classList.add('drag-ready');
    mapStage.setPointerCapture(event.pointerId);
    mapStageInner?.classList.remove('camera-smooth');
  });
  mapStage.addEventListener('pointermove', (event) => {
    if (mapCamera.dragging && event.pointerId !== mapCamera.pointerId) {
      return;
    }
    if (!mapCamera.dragging) {
      showMapPointerPreview(event);
      return;
    }
    const dx = event.clientX - mapCamera.startX;
    const dy = event.clientY - mapCamera.startY;
    if (Math.abs(dx) + Math.abs(dy) > 4) {
      mapCamera.dragMoved = true;
      mapStage.classList.add('dragging');
    }
    const clamped = clampMapCameraPosition(mapCamera.originX + dx, mapCamera.originY + dy);
    mapCamera.x = clamped.x;
    mapCamera.y = clamped.y;
    applyMapCamera();
  });
  mapStage.addEventListener('pointerup', (event) => {
    if (event.pointerId === mapCamera.pointerId) {
      finishMapDrag(event);
    }
  });
  mapStage.addEventListener('pointercancel', (event) => {
    if (event.pointerId === mapCamera.pointerId) {
      finishMapDrag();
    }
  });
  mapStage.addEventListener('lostpointercapture', () => {
    finishMapDrag();
  });
  mapStage.addEventListener('pointerleave', () => {
    if (!mapCamera.dragging) {
      hoveredMapCellKey = null;
      clearPreview();
    }
  });
  window.addEventListener('pointerup', (event) => {
    if (event.pointerId === mapCamera.pointerId) {
      finishMapDrag(event);
    }
  });
  window.addEventListener('pointercancel', (event) => {
    if (event.pointerId === mapCamera.pointerId) {
      finishMapDrag();
    }
  });
  window.addEventListener('blur', () => {
    finishMapDrag();
  });
}
window.addEventListener('resize', () => {
  updateMapContentSize();
  syncMapZoomLimit();
  clampMapCamera();
  applyMapCamera();
});
document.addEventListener('pointerdown', (event) => {
  if (!event.target.closest('.hand-list')) {
    clearPrimedControl();
  }
});
