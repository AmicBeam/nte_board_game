const phaseChip = document.getElementById('phase-chip');
const duelHud = document.getElementById('duel-hud');
const playerSideTitle = document.getElementById('player-side-title');
const leftStatusGrid = document.getElementById('left-status-grid');
const playerDeckZone = document.getElementById('player-deck-zone');
const locationsBoard = document.getElementById('locations-board');
const handList = document.getElementById('hand-list');
const selectionOverlay = document.getElementById('selection-overlay');
const cardPreview = document.getElementById('card-preview');
const logList = document.getElementById('log-list');
const esperStandbyList = document.getElementById('esper-standby-list');
const esperStandbyCopy = document.getElementById('esper-standby-copy');
const duelRightPanel = document.getElementById('duel-right-panel');
const rightPanelTitle = document.getElementById('right-panel-title');
const rightPanelSubtitle = document.getElementById('right-panel-subtitle');
const rightInfoView = document.getElementById('right-info-view');
const rightLogView = document.getElementById('right-log-view');
const rightDiscardView = document.getElementById('right-discard-view');
const rightResourceGrid = document.getElementById('right-resource-grid');
const opponentDeckZone = document.getElementById('opponent-deck-zone');
const opponentHandList = document.getElementById('opponent-hand-list');
const opponentHandCount = document.getElementById('opponent-hand-count');
const rightPanelTabs = Array.from(document.querySelectorAll('[data-right-panel-view]'));
const discardList = document.getElementById('discard-list');
const endTurnBtn = document.getElementById('end-turn-btn');
const finalRoundLabel = document.getElementById('final-round-label');
const copyLogBtn = document.getElementById('copy-log-btn');
const undoTurnBtn = document.getElementById('undo-turn-btn');
const resetRunBtn = document.getElementById('reset-run-btn');
const opponentTopName = document.getElementById('opponent-top-name');
const dragGhost = document.getElementById('card-drag-ghost');
const duelToast = document.getElementById('duel-toast');
const duelTitleBanner = document.getElementById('duel-title-banner');
const effectArrowLayer = document.getElementById('effect-arrow-layer');
const roundCounter = document.getElementById('round-counter');
const energySidecar = document.getElementById('energy-sidecar');
const initiativeSidecar = document.getElementById('initiative-sidecar');
const playerHandName = document.getElementById('player-hand-name');
const playerDiscardName = document.getElementById('player-discard-name');
const opponentDiscardName = document.getElementById('opponent-discard-name');
const playerDiscardBtn = document.getElementById('player-discard-btn');
const opponentDiscardBtn = document.getElementById('opponent-discard-btn');
const playerDiscardCount = document.getElementById('player-discard-count');
const opponentDiscardCount = document.getElementById('opponent-discard-count');
const discardModal = document.getElementById('discard-modal');
const discardModalTitle = document.getElementById('discard-modal-title');
const discardModalSubtitle = document.getElementById('discard-modal-subtitle');
const discardModalList = document.getElementById('discard-modal-list');

let currentState = null;
let actionLocked = false;
let dragState = null;
let rightPanelView = 'info';
let activeDiscardSide = '';
let tableTutorialInitialized = false;
let selectedChoiceIds = [];
let selectionKey = '';
let selectionCollapsed = false;
let cardPreviewPinned = false;
let targetPointer = null;
let lastPresentationKey = '';
let playedResultRedirect = false;
let materialSelection = null;
let materialSelectionClickShieldUntil = 0;
let presentationLocked = false;
const previewCardsByInstanceId = new Map();

const ACTION_ANIMATION_MS = 1000;
const ACTION_INTERVAL_MS = 1000;
const ELEMENT_ICON_BASE = '/static/images/elements';
const CARD_BACK_IMAGE = '/static/images/cards/card-back.svg';

const LOCATION_MARK_LABELS = {
  genesis: '创生',
  murk: '浊燃',
  delay: '延滞',
  darkstar: '黯星',
  discord: '失谐',
  zhue_huchi: '诛恶护持',
  nightmare: '噩梦',
  panyu_qiu: '判予秋',
  collapsing: '倾陷',
};

const LOCATION_MARK_ORDER = ['genesis', 'murk', 'delay', 'darkstar', 'zhue_huchi', 'nightmare', 'panyu_qiu', 'discord', 'collapsing'];

const PHASE_LABELS = {
  selecting: '选牌阶段',
  planning: '部署阶段',
  waiting: '等待对手',
  revealing: '揭示中',
  victory: '胜利',
  defeat: '失败',
  draw: '平局',
};

const DUEL_SCENES = ['rain-city', 'archive-neon', 'tide-platform', 'hollow-stage'];

applyBattleScene();

if (ensureLogin()) {
  setupCardPreviewInteractions();
  loadState();
}

function applyBattleScene() {
  const scene = DUEL_SCENES[Math.floor(Math.random() * DUEL_SCENES.length)];
  document.body.classList.add(`duel-scene-${scene}`);
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
        title: '异象对决手册',
        eyebrow: '牌桌',
        pages: () => buildTableTutorialPages(),
      });
    }
  } catch (error) {
    window.alert(error.message);
    window.location.href = '/build';
  }
}

function renderState(state) {
  const previousState = currentState;
  const shouldHoldPresentation = Boolean(previousState && hasNewPresentation(state));
  const displayState = shouldHoldPresentation ? previousState : state;
  hideCardPreview({ force: true });
  previewCardsByInstanceId.clear();
  currentState = displayState;
  if (displayState.phase !== 'planning' || displayState.selection || displayState.pending_target || presentationLocked) {
    cancelMaterialSelection({ silent: true });
  }
  document.body.dataset.phase = classToken(displayState.phase);
  document.body.classList.toggle('targeting-card', Boolean(displayState.pending_target));
  syncRoundInfo(displayState);
  if (opponentTopName) {
    opponentTopName.textContent = displayState.opponent.nickname || '对手';
  }
  if (duelHud) {
    duelHud.innerHTML = `
      <span>${escapeHtml(displayState.scenario_label || '异象对决')}</span>
      <span>回合 ${displayState.turn}/${displayState.max_turns}</span>
      <span>主战场 ${escapeHtml(displayState.score.total_power_player)}-${escapeHtml(displayState.score.total_power_opponent)}</span>
    `;
  }
  renderLeftInfo(displayState);
  renderRightInfo(displayState);
  renderLocations(displayState, shouldHoldPresentation ? null : previousState);
  renderHand(displayState, { deferSelection: shouldHoldPresentation || hasPendingPresentation(state) });
  renderLog(displayState);
  renderDiscard(displayState);
  renderEsperStandby(displayState);
  syncRightPanel();
  syncMaterialSelection();
  syncControls(displayState);
  syncTargetMode(displayState);
  renderDeclarationArrows(displayState);
  playPresentation(state, { renderFinalAfter: shouldHoldPresentation });
}

function syncRoundInfo(state) {
  if (!state) {
    return;
  }
  if (roundCounter) {
    roundCounter.textContent = `第 ${escapeHtml(state.turn)} / ${escapeHtml(state.max_turns)} 回合`;
  }
  if (phaseChip) {
    phaseChip.textContent = PHASE_LABELS[state.phase] || state.phase;
    phaseChip.className = `phase-chip phase-${classToken(state.phase)}`;
  }
}

function renderLeftInfo(state) {
  if (playerSideTitle) {
    playerSideTitle.textContent = state.player.nickname || '我方';
  }
  const leaderText = sidePublicLabel(state.score?.leader);
  const initiativeText = sidePublicLabel(state.initiative?.first);
  if (playerHandName) {
    playerHandName.textContent = state.player.nickname || '我方';
  }
  if (playerDiscardName) {
    playerDiscardName.textContent = state.player.nickname || '我方';
  }
  if (opponentDiscardName) {
    opponentDiscardName.textContent = state.opponent.nickname || '对手';
  }
  if (energySidecar) {
    energySidecar.innerHTML = `
      <span>能量</span>
      <strong>${escapeHtml(state.energy_remaining)} / ${escapeHtml(state.turn_energy)}</strong>
    `;
  }
  if (initiativeSidecar) {
    initiativeSidecar.innerHTML = `
      <span>结算先手</span>
      <strong>${escapeHtml(initiativeText)}</strong>
    `;
  }
  if (leftStatusGrid) {
    leftStatusGrid.innerHTML = `
      <article class="side-status-card highlight">
        <span>能量</span>
        <strong>${escapeHtml(state.energy_remaining)} / ${escapeHtml(state.turn_energy)}</strong>
        <small>本回合能量</small>
      </article>
      <article class="side-status-card">
        <span>战力</span>
        <strong>${escapeHtml(state.score.total_power_player)} - ${escapeHtml(state.score.total_power_opponent)}</strong>
        <small>实时领先：${escapeHtml(leaderText)}</small>
      </article>
      <article class="side-status-card">
        <span>结算先手</span>
        <strong>${escapeHtml(initiativeText)}</strong>
        <small>${escapeHtml(state.initiative?.reason || '回合开始锁定')}</small>
      </article>
      <article class="side-status-card">
        <span>回合</span>
        <strong>${escapeHtml(state.turn)} / ${escapeHtml(state.max_turns)}</strong>
        <small>${escapeHtml(PHASE_LABELS[state.phase] || state.phase)}</small>
      </article>
    `;
  }
  renderDeckZone(playerDeckZone, 'player', state.player.deck_count, '', { countOnly: true });
}

function renderLocations(state, previousState = null) {
  locationsBoard.innerHTML = '';
  state.locations.forEach((location) => {
    const previousLocation = previousState?.locations?.find((currentLocation) => currentLocation.id === location.id);
    const node = document.createElement('article');
    const canDrop = canPlayToLocation(location) || canPlayEsperToLocation(location);
    const justRevealed = Boolean(location.revealed && previousLocation && !previousLocation.revealed);
    const revealText = location.revealed ? '' : unrevealedRevealText(location, state.turn);
    const revealBadge = revealText ? `<span>${escapeHtml(revealText)}</span>` : '';
    const description = location.revealed ? location.description : `${revealText}，显现后揭示空间规则。`;
    const initiativeFirst = state.initiative?.first || '';
    const opponentInitiativeClass = initiativeFirst === 'opponent' ? ' initiative-first-row' : '';
    const playerInitiativeClass = initiativeFirst === 'player' ? ' initiative-first-row' : '';
    node.className = `duel-location winner-${classToken(location.winner)}${location.revealed ? '' : ' unrevealed'}${canDrop ? ' can-drop' : ''}${justRevealed ? ' location-revealed' : ''}`;
    node.dataset.locationId = location.id;
    node.innerHTML = `
      <div class="location-slots opponent-slots">
        ${location.slots.opponent.map((card) => boardCardHtml(card, 'opponent', previousLocation)).join('')}
      </div>
      <div class="location-contest">
        <div class="location-rule-line">
          ${revealBadge}
          <strong>${escapeHtml(location.name)}</strong>
          <small>${escapeHtml(description)}</small>
        </div>
        <div class="location-power-row opponent${opponentInitiativeClass}">
          <span>对方</span>
          <strong>${escapeHtml(location.power.opponent)}</strong>
          ${locationMarksHtml(location, 'opponent')}
        </div>
        <div class="location-leader">${escapeHtml(location.winner === 'opponent' ? '对手领先' : location.winner === 'player' ? '我方领先' : '持平')}</div>
        <div class="location-power-row player${playerInitiativeClass}">
          <span>我方</span>
          <strong>${escapeHtml(location.power.player)}</strong>
          ${locationMarksHtml(location, 'player')}
        </div>
        <div class="drop-lane" data-location-id="${location.id}">
          <span>${canDrop ? '拖到这里出牌' : location.revealed ? '战场已满' : '尚未显现'}</span>
        </div>
      </div>
      <div class="location-slots player-slots">
        ${location.slots.player.map((card) => boardCardHtml(card, 'player', previousLocation)).join('')}
      </div>
    `;
    locationsBoard.appendChild(node);
  });
}

function unrevealedRevealText(location, currentTurn) {
  const revealTurn = Number(location.reveal_turn || 0);
  const turn = Number(currentTurn || 0);
  const remaining = Math.max(0, revealTurn - turn);
  if (remaining <= 0) {
    return '即将显现';
  }
  return `还剩 ${remaining} 回合显现`;
}

function locationMarksHtml(location, owner) {
  const ownerLabel = owner === 'opponent' ? '敌' : '我';
  const chips = locationMarkChips(location.marks?.[owner] || {}, owner, ownerLabel);
  if (!chips.length) {
    return '<div class="location-marks empty" aria-hidden="true"></div>';
  }
  return `<div class="location-marks">${chips.join('')}</div>`;
}

function locationMarkChips(marks, owner, ownerLabel) {
  return LOCATION_MARK_ORDER
    .filter((tag) => Number(marks[tag] || 0) > 0)
    .map((tag) => `
      <span class="location-mark ${owner}" data-mark="${escapeAttr(tag)}">
        <b>${ownerLabel}</b>
        <span>${escapeHtml(LOCATION_MARK_LABELS[tag] || tag)}</span>
        <strong>${escapeHtml(marks[tag])}</strong>
      </span>
    `);
}

function renderEsperStandby(state) {
  const espers = state.player.esper_standby || [];
  esperStandbyCopy.textContent = espers.length
    ? '拖动异能者到己方素材所在区域。'
    : `对手待命 ${state.opponent.esper_standby_count || 0} 名异能者`;
  esperStandbyList.innerHTML = '';
  if (!espers.length) {
    esperStandbyList.innerHTML = '<div class="empty-state">没有待命异能者</div>';
    return;
  }
  espers.forEach((card) => {
    registerPreviewCard(card);
    const node = document.createElement('article');
    const playable = canPlayEsper(card);
    const blockedReason = playable ? '' : canPlayEsperReason(card);
    node.className = `duel-card esper-card rarity-${classToken(card.rarity)}${playable ? ' playable' : ' disabled'}`;
    node.dataset.cardInstanceId = card.instance_id;
    if (blockedReason) {
      node.dataset.disabledReason = blockedReason;
      node.title = blockedReason;
      node.setAttribute('aria-label', `${card.name}：${blockedReason}`);
    }
    node.tabIndex = playable ? 0 : -1;
    node.innerHTML = cardHtml(card, { compact: true });
    node.addEventListener('pointerdown', (event) => beginCardDrag(event, card, node, { kind: 'esper' }));
    node.addEventListener('mousedown', (event) => beginCardDrag(event, card, node, { kind: 'esper' }));
    node.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') {
        return;
      }
      event.preventDefault();
      quickPlayEsper(card);
    });
    esperStandbyList.appendChild(node);
  });
}

function renderHand(state, options = {}) {
  const hand = state.player.hand || [];
  if (state.selection && !options.deferSelection) {
    renderHandCards(hand, state);
    renderSelection(state.selection);
    return;
  }
  closeSelectionOverlay();
  renderHandCards(hand, state);
}

function renderHandCards(hand, state) {
  handList.innerHTML = '';
  if (!hand.length) {
    handList.innerHTML = '<div class="empty-state">当前没有手牌</div>';
    return;
  }
  hand.forEach((card) => {
    registerPreviewCard(card);
    const node = document.createElement('article');
    node.className = `duel-card hand-card rarity-${classToken(card.rarity)}`;
    node.dataset.cardInstanceId = card.instance_id;
    applyHandCardState(node, card);
    node.innerHTML = cardHtml(card, { compact: false, showCurrentStats: false, mode: 'hand' });
    attachHandCardHandlers(node, card);
    handList.appendChild(node);
  });
}

function applyHandCardState(node, card) {
  const playable = canPlayCard(card);
  node.classList.toggle('playable', playable);
  node.classList.toggle('disabled', !playable);
  delete node.dataset.disabledReason;
  node.removeAttribute('title');
  node.removeAttribute('aria-label');
  if (!playable) {
    const blockedReason = canPlayCardReason(card);
    if (blockedReason) {
      node.dataset.disabledReason = blockedReason;
      node.title = blockedReason;
      node.setAttribute('aria-label', `${card.name}：${blockedReason}`);
    }
  }
  node.tabIndex = playable ? 0 : -1;
  return playable;
}

function attachHandCardHandlers(node, card) {
  node.addEventListener('pointerdown', (event) => beginCardDrag(event, card, node));
  node.addEventListener('mousedown', (event) => beginCardDrag(event, card, node));
  node.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    event.preventDefault();
    quickPlayCard(card);
  });
}

function renderSelection(selection) {
  const cards = selection.cards || [];
  const visibleCards = selectionCardsForDisplay(selection);
  const nextKey = `${selection.kind}:${cards.map((card) => card.instance_id).join('|')}`;
  if (nextKey !== selectionKey) {
    selectionKey = nextKey;
    selectedChoiceIds = [];
    selectionCollapsed = false;
  }
  selectionOverlay.className = `selection-overlay open selection-${classToken(selection.kind)}${selectionCollapsed ? ' collapsed' : ''}`;
  selectionOverlay.setAttribute('aria-hidden', 'false');
  document.body.classList.toggle('selecting-cards', !selectionCollapsed);
  document.body.classList.toggle('selecting-draw-cards', selection.kind === 'draw' && !selectionCollapsed);
  document.body.classList.toggle('selection-collapsed', selectionCollapsed);

  if (selectionCollapsed) {
    const collapsed = document.createElement('button');
    collapsed.className = 'selection-collapsed-pill';
    collapsed.type = 'button';
    collapsed.textContent = `${selection.title || '选择卡牌'} · ${selectedChoiceIds.length}/${Number(selection.pick_count || 1)}`;
    collapsed.addEventListener('click', () => {
      selectionCollapsed = false;
      renderSelection(selection);
    });
    selectionOverlay.replaceChildren(collapsed);
    return;
  }

  const panel = document.createElement('div');
  panel.className = 'selection-panel';
  panel.innerHTML = `
    <div class="selection-copy">
      <p class="eyebrow">${escapeHtml(selection.kind === 'opening' ? 'Opening Hand' : 'Card Choice')}</p>
      <strong>${escapeHtml(selection.title || '选择卡牌')}</strong>
      <span>${escapeHtml(selection.description || '')}</span>
      <b>${selectedChoiceIds.length} / ${Number(selection.pick_count || 1)}</b>
      ${selection.kind !== 'opening' ? '<button class="secondary-btn selection-collapse-btn" id="collapse-selection-btn" type="button">收起</button>' : ''}
    </div>
  `;

  const rail = document.createElement('div');
  rail.className = 'selection-card-grid';
  visibleCards.forEach((card) => {
    registerPreviewCard(card);
    const shell = document.createElement('div');
    shell.className = 'selection-card-shell';
    const sourceLabel = String(card.selection_source_label || '').trim();
    if (sourceLabel) {
      const sourceBadge = document.createElement('span');
      sourceBadge.className = `selection-source-badge source-${classToken(card.selection_source_zone || sourceLabel)}`;
      sourceBadge.textContent = sourceLabel;
      shell.appendChild(sourceBadge);
    }
    const node = document.createElement('button');
    const selected = selectedChoiceIds.includes(card.instance_id);
    const drawChoice = selection.kind === 'draw';
    node.type = 'button';
    node.className = `duel-card selection-card${drawChoice ? ' draw-choice-card' : ''} rarity-${classToken(card.rarity)}${selected ? ' selected' : ''}`;
    node.dataset.cardInstanceId = card.instance_id;
    node.setAttribute('aria-pressed', selected ? 'true' : 'false');
    node.innerHTML = cardHtml(card, {
      compact: false,
      showCurrentStats: false,
      mode: selection.kind === 'declaration' ? 'hand' : 'default',
    });
    node.addEventListener('click', () => toggleSelectionCard(card.instance_id, selection));
    bindSelectionCardPreview(node, card);
    shell.appendChild(node);
    rail.appendChild(shell);
  });
  panel.appendChild(rail);
  const actions = document.createElement('div');
  actions.className = 'selection-actions';
  actions.innerHTML = '<button class="primary-btn" id="confirm-selection-btn" type="button">确认选择</button>';
  panel.appendChild(actions);
  selectionOverlay.replaceChildren(panel);

  const confirmBtn = panel.querySelector('#confirm-selection-btn');
  confirmBtn.disabled = actionLocked || selectedChoiceIds.length !== Number(selection.pick_count || 1);
  confirmBtn.addEventListener('click', () => confirmSelection(selection));
  const collapseBtn = panel.querySelector('#collapse-selection-btn');
  collapseBtn?.addEventListener('click', () => {
    selectionCollapsed = true;
    renderSelection(selection);
  });
}

function closeSelectionOverlay() {
  hideCardPreview({ force: true });
  selectionOverlay.className = 'selection-overlay';
  selectionOverlay.setAttribute('aria-hidden', 'true');
  selectionOverlay.replaceChildren();
  document.body.classList.remove('selecting-cards');
  document.body.classList.remove('selecting-draw-cards');
  document.body.classList.remove('selection-collapsed');
  selectionCollapsed = false;
}

function selectionCardsForDisplay(selection) {
  return selection.cards || [];
}

function bindSelectionCardPreview(node, card) {
  node.addEventListener('pointerover', (event) => {
    if (event.pointerType === 'touch' || dragState) {
      return;
    }
    showCardPreview(card, node, { pinned: false, pointerType: event.pointerType || 'mouse' });
  });
  node.addEventListener('pointerout', (event) => {
    if (node.contains(event.relatedTarget)) {
      return;
    }
    hideCardPreview();
  });
  node.addEventListener('focusin', () => {
    showCardPreview(card, node, { pinned: false, pointerType: 'keyboard' });
  });
  node.addEventListener('focusout', (event) => {
    if (node.contains(event.relatedTarget)) {
      return;
    }
    hideCardPreview();
  });
}

function renderLog(state) {
  const lines = state.log || [];
  logList.innerHTML = lines.length
    ? lines.map((line) => `<div class="log-item">${escapeHtml(line)}</div>`).join('')
    : '<div class="empty-state">暂无日志</div>';
}

function renderRightInfo(state) {
  const playerEnded = state.player.ended_turn ? '已结束' : '部署中';
  const opponentEnded = state.opponent.ended_turn ? '已结束' : '部署中';
  const opponentInitiative = state.initiative?.first === 'opponent' ? '本回合先揭示' : '本回合后揭示';
  rightResourceGrid.innerHTML = `
    <article class="right-resource-card highlight">
      <span>对手</span>
      <strong>${escapeHtml(state.opponent.nickname || '对手')}</strong>
      <small>${escapeHtml(state.opponent.deck_name || '试用牌组')}</small>
    </article>
    <article class="right-resource-card">
      <span>手牌 / 牌库</span>
      <strong>${escapeHtml(state.opponent.hand_count)} / ${escapeHtml(state.opponent.deck_count)}</strong>
      <small>消耗 ${escapeHtml(state.opponent.discard_count || 0)} · ${escapeHtml(opponentEnded)}</small>
    </article>
    <article class="right-resource-card">
      <span>战力</span>
      <strong>${escapeHtml(state.score.total_power_opponent)}</strong>
      <small>${escapeHtml(opponentInitiative)}</small>
    </article>
    <article class="right-resource-card opponent">
      <span>我方状态</span>
      <strong>${escapeHtml(playerEnded)}</strong>
      <small>我方手牌 ${escapeHtml(state.player.hand_count)} · 牌库 ${escapeHtml(state.player.deck_count)}</small>
    </article>
  `;
  endTurnBtn.dataset.playerEnded = playerEnded;
  renderDeckZone(opponentDeckZone, 'opponent', state.opponent.deck_count, '对方牌库');
  renderOpponentHand(state);
}

function renderDeckZone(node, publicSide, deckCount, label, options = {}) {
  if (!node) {
    return;
  }
  const count = Number(deckCount || 0);
  node.dataset.publicSide = publicSide;
  node.className = `deck-zone ${publicSide}-deck-zone ${deckThicknessClass(count)}${options.countOnly ? ' deck-count-only' : ''}${options.extraClass ? ` ${options.extraClass}` : ''}`;
  node.innerHTML = `
    <div class="deck-stack" aria-hidden="true">
      <span></span><span></span><span></span>
    </div>
    <div class="deck-copy">
      ${label ? `<span>${escapeHtml(label)}</span>` : ''}
      <strong>${escapeHtml(count)}</strong>
    </div>
  `;
}

function renderOpponentHand(state) {
  const cards = state.opponent.hand?.length
    ? state.opponent.hand
    : Array.from({ length: Number(state.opponent.hand_count || 0) }, (_, index) => ({
      instance_id: `opponent-hidden-hand-${index + 1}`,
      art: '/static/images/cards/card-back.svg',
    }));
  if (opponentHandCount) {
    opponentHandCount.textContent = String(cards.length || state.opponent.hand_count || 0);
  }
  if (!opponentHandList) {
    return;
  }
  opponentHandList.innerHTML = cards.length
    ? cards.map((card, index) => hiddenHandCardHtml(card, index)).join('')
    : '<div class="empty-state">对手没有手牌</div>';
}

function hiddenHandCardHtml(card, index) {
  return `
    <button class="opponent-hand-card" type="button" data-card-instance-id="${escapeAttr(card.instance_id)}" aria-label="对手手牌 ${index + 1}">
      <span style="background-image: url('${escapeAttr(card.art || '/static/images/cards/card-back.svg')}')" aria-hidden="true"></span>
    </button>
  `;
}

function deckThicknessClass(count) {
  if (count <= 0) {
    return 'deck-empty';
  }
  if (count <= 3) {
    return 'deck-low';
  }
  if (count <= 8) {
    return 'deck-mid';
  }
  return 'deck-high';
}

function deckThicknessText(count) {
  if (count <= 0) {
    return '已空';
  }
  if (count <= 3) {
    return '很薄';
  }
  if (count <= 8) {
    return '中等';
  }
  return '充足';
}

function sidePublicLabel(value) {
  if (value === 'player') {
    return '我方';
  }
  if (value === 'opponent') {
    return '对手';
  }
  return '持平';
}

function renderDiscard(state) {
  const cards = state.player.discard || [];
  const opponentCards = state.opponent.discard || [];
  renderDeckZone(opponentDiscardBtn, 'opponent', opponentCards.length || state.opponent.discard_count || 0, '墓地', { countOnly: true, extraClass: 'discard-zone opponent-discard-zone' });
  renderDeckZone(playerDiscardBtn, 'player', cards.length, '墓地', { countOnly: true, extraClass: 'discard-zone player-discard-zone' });
  if (playerDiscardCount) {
    playerDiscardCount.textContent = String(cards.length);
  }
  if (opponentDiscardCount) {
    opponentDiscardCount.textContent = String(opponentCards.length || state.opponent.discard_count || 0);
  }
  if (discardList) {
    discardList.innerHTML = cards.length
    ? cards.slice().reverse().map(discardCardHtml).join('')
    : '<div class="empty-state">墓地暂无卡牌</div>';
  }
  if (activeDiscardSide) {
    renderDiscardModal(activeDiscardSide);
  }
}

function discardCardHtml(card) {
  const power = card.power ?? '?';
  const cost = card.type === 'esper' ? card.material_cost ?? 1 : card.cost ?? '?';
  return `
    <article class="discard-card rarity-${classToken(card.rarity)}">
      <span class="discard-card-art" style="background-image: url('${escapeAttr(card.art)}')" aria-hidden="true"></span>
      <div>
        <strong>${escapeHtml(card.name || '墓地卡牌')}</strong>
        <small>${escapeHtml(card.type === 'esper' ? `${materialRequirementText(card)} / ${power} 战` : `${cost} 费 / ${power} 战`)}</small>
      </div>
    </article>
  `;
}

function openDiscardModal(side) {
  activeDiscardSide = side === 'opponent' ? 'opponent' : 'player';
  renderDiscardModal(activeDiscardSide);
  discardModal?.classList.add('open');
  discardModal?.setAttribute('aria-hidden', 'false');
}

function closeDiscardModal() {
  activeDiscardSide = '';
  discardModal?.classList.remove('open');
  discardModal?.setAttribute('aria-hidden', 'true');
}

function renderDiscardModal(side) {
  if (!discardModalList || !currentState) {
    return;
  }
  const publicSide = side === 'opponent' ? 'opponent' : 'player';
  const sideState = currentState[publicSide] || {};
  const cards = sideState.discard || [];
  if (discardModalTitle) {
    discardModalTitle.textContent = publicSide === 'opponent' ? '对方墓地' : '我方墓地';
  }
  if (discardModalSubtitle) {
    discardModalSubtitle.textContent = `${cards.length} 张墓地卡牌`;
  }
  discardModalList.innerHTML = cards.length
    ? cards.slice().reverse().map(discardCardHtml).join('')
    : '<div class="empty-state">墓地暂无卡牌</div>';
}

function syncRightPanel() {
  const view = ['info', 'log', 'discard'].includes(rightPanelView) ? rightPanelView : 'info';
  rightPanelView = view;
  duelRightPanel.dataset.view = view;
  rightPanelTabs.forEach((button) => {
    const active = button.dataset.rightPanelView === view;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
  rightPanelTitle.textContent = '右侧面板';
  rightPanelSubtitle.textContent = view === 'log' ? '战况日志' : view === 'discard' ? '墓地卡牌' : '行动与资源';
  [
    ['info', rightInfoView],
    ['log', rightLogView],
    ['discard', rightDiscardView],
  ].forEach(([name, node]) => {
    const active = name === view;
    node.classList.toggle('active', active);
    node.setAttribute('aria-hidden', active ? 'false' : 'true');
  });
  copyLogBtn.hidden = view !== 'log';
}

function setRightPanelView(view) {
  rightPanelView = rightPanelView === view && view !== 'info' ? 'info' : view;
  syncRightPanel();
}

function syncControls(state) {
  const playing = state.status === 'playing';
  const hasPendingTarget = Boolean(state.pending_target);
  const isFinalRound = playing && Number(state.turn || 0) >= Number(state.max_turns || 0);
  endTurnBtn.disabled = actionLocked || presentationLocked || Boolean(materialSelection) || !playing || state.phase !== 'planning' || Boolean(state.selection) || hasPendingTarget;
  endTurnBtn.textContent = hasPendingTarget ? '选择目标' : state.phase === 'waiting' ? '等待对手' : '结束回合';
  endTurnBtn.classList.remove('initiative-first', 'initiative-second');
  endTurnBtn.title = '结束当前部署';
  if (finalRoundLabel) {
    finalRoundLabel.hidden = !isFinalRound;
  }
  undoTurnBtn.disabled = actionLocked || presentationLocked || Boolean(materialSelection) || !playing || state.phase !== 'planning' || Boolean(state.selection) || !state.can_undo_turn;
}

function canPlayCard(card) {
  return canPlayCardReason(card) === '';
}

function canPlayCardReason(card, targetLocation = null) {
  if (!currentState) {
    return '对局状态尚未加载';
  }
  if (actionLocked || presentationLocked) {
    return '正在结算动画，暂时不能部署';
  }
  if (currentState.status !== 'playing') {
    return '对局已经结束';
  }
  if (currentState.phase !== 'planning') {
    return '当前阶段不能部署';
  }
  if (currentState.selection) {
    return '请先完成当前选牌';
  }
  if (currentState.pending_target) {
    return '请先完成目标选择';
  }
  if (materialSelection) {
    return '请先完成素材选择';
  }
  if (Number(card.cost) > Number(currentState.energy_remaining)) {
    return `需要 ${Number(card.cost)} 点能量`;
  }
  const candidateLocations = targetLocation ? [targetLocation] : (currentState.locations || []);
  const openLocations = candidateLocations.filter((location) => canPlayToLocation(location));
  if (!openLocations.length) {
    return '没有可出牌空间';
  }
  if (requiresTargetBeforePlay(card) && !openLocations.some((location) => cardTargetCandidates(location, card).length > 0)) {
    return '需要可选择的己方道具';
  }
  if (!openLocations.some((location) => canPlayCardToLocation(location, card))) {
    return '当前不能部署';
  }
  return '';
}

function canPlayCardToLocation(location, card) {
  if (!location || !canPlayToLocation(location)) {
    return false;
  }
  if (
    !currentState
    || actionLocked
    || currentState.status !== 'playing'
    || currentState.phase !== 'planning'
    || currentState.selection
    || currentState.pending_target
    || materialSelection
    || presentationLocked
    || Number(card.cost) > Number(currentState.energy_remaining)
  ) {
    return false;
  }
  if (requiresTargetBeforePlay(card) && !cardTargetCandidates(location, card).length) {
    return false;
  }
  return true;
}

function requiresTargetBeforePlay(card) {
  return Boolean(card?.target_rule?.required_before_play);
}

function cardTargetCandidates(location, card) {
  const scope = String(card?.target_rule?.scope || (requiresTargetBeforePlay(card) ? 'ally_item_same_location' : ''));
  if (!scope || !location) {
    return [];
  }
  const locations = scope.endsWith('_same_location') ? [location] : (currentState?.locations || []);
  const sideKey = scope.startsWith('opponent') ? 'opponent' : 'player';
  const itemOnly = scope.includes('_item_');
  return locations.flatMap((candidateLocation) => candidateLocation?.slots?.[sideKey] || [])
    .filter((target) => (
      targetCandidateMatchesScope(target, card, scope, itemOnly)
    ));
}

function targetCandidateMatchesScope(target, sourceCard, scope, itemOnly = String(scope || '').includes('_item_')) {
  if (
    !target
    || target.instance_id === sourceCard?.instance_id
    || !target.revealed
    || target.hidden
    || (itemOnly && target.type !== 'anomaly_item')
  ) {
    return false;
  }
  if (scope === 'opponent_power_lte_3_same_location') {
    return Number(target.power || 0) <= 3;
  }
  if (scope === 'ally_damaged_food_same_location') {
    return target.type === 'anomaly_item'
      && target.category === '食物'
      && Number(target.power || 0) < Number(target.base_power || 0);
  }
  if (scope === 'ally_xiang_item_same_location') {
    return target.type === 'anomaly_item' && target.attribute === '相';
  }
  return true;
}

function canPlayEsper(card) {
  return Boolean(
    currentState
    && !actionLocked
    && currentState.status === 'playing'
    && currentState.phase === 'planning'
    && !currentState.selection
    && !currentState.pending_target
    && !materialSelection
    && !presentationLocked
    && (currentState.locations || []).some((location) => canPlayEsperToLocation(location, card))
  );
}

function canReactivateEsper(card) {
  if (!currentState || card?.type !== 'esper' || !card.revealed || card.staged || (card.pending_material_ids || []).length) {
    return false;
  }
  if (Number(card.reactivating_turn || 0) === Number(currentState.turn || 0)) {
    return false;
  }
  const location = (currentState.locations || []).find((candidate) => candidate.id === card.location_id);
  return Boolean(location && canPlayEsperToLocation(location, card));
}

function canPlayEsperReason(card) {
  if (!currentState) {
    return '对局状态尚未加载';
  }
  if (actionLocked || presentationLocked) {
    return '正在结算动画，暂时不能共鸣';
  }
  if (currentState.status !== 'playing') {
    return '对局已经结束';
  }
  if (currentState.phase !== 'planning') {
    return '当前阶段不能唤醒异能者';
  }
  if (currentState.selection) {
    return '请先完成当前选牌';
  }
  if (currentState.pending_target) {
    return '请先完成目标选择';
  }
  if (materialSelection) {
    return '请先完成素材选择';
  }
  const revealedLocations = (currentState.locations || []).filter((location) => location.revealed);
  if (!revealedLocations.length) {
    return '暂无可用的异象空间';
  }
  const materialReadyLocations = revealedLocations.filter((location) => {
    const materials = materialCandidates(location, card);
    return materials.length >= esperMaterialCost(card) && canSatisfyMaterialRequirements(materials, card);
  });
  if (!materialReadyLocations.length) {
    return `需要已揭示 ${materialRequirementText(card)}`;
  }
  if (!materialReadyLocations.some((location) => hasRoomForEsperAfterMaterials(location, card))) {
    return '符合素材的区域已满';
  }
  return '当前不能唤醒';
}

function canPlayToLocation(location) {
  return Boolean(
    currentState
    && currentState.phase === 'planning'
    && !currentState.selection
    && !currentState.pending_target
    && !materialSelection
    && !presentationLocked
    && location.revealed
    && locationOccupiedCount(location, 'player') < Number(location.capacity || 10)
  );
}

function canPlayEsperToLocation(location, card = null) {
  if (!currentState || currentState.phase !== 'planning' || currentState.selection || currentState.pending_target || materialSelection || presentationLocked || !location.revealed) {
    return false;
  }
  const requirement = esperMaterialCost(card);
  const materials = materialCandidates(location, card);
  if (materials.length < requirement) {
    return false;
  }
  if (!canSatisfyMaterialRequirements(materials, card)) {
    return false;
  }
  return hasRoomForEsperAfterMaterials(location, card, requirement);
}

function hasRoomForEsperAfterMaterials(location, card = null, materialCount = null) {
  const consumed = Number(materialCount ?? esperMaterialCost(card));
  const addsCard = !(card?.revealed && card.location_id === location.id);
  const futureCount = locationOccupiedCount(location, 'player') - Math.max(0, consumed) + (addsCard ? 1 : 0);
  return futureCount <= Number(location.capacity || 10);
}

function locationOccupiedCount(location, owner = 'player') {
  const serverCount = Number(location?.occupied?.[owner]);
  if (Number.isFinite(serverCount)) {
    return serverCount;
  }
  return (location?.slots?.[owner] || []).filter((card) => !card.reserved_as_material_for).length;
}

function materialCandidates(location, esperCard = null) {
  const requiredAttribute = requiredMaterialAttribute(esperCard);
  const requirements = materialRequirements(esperCard);
  return (location.slots?.player || []).filter((card) => {
    const tags = new Set(card.tags || []);
    const power = Number(card.power ?? card.computed_power ?? card.base_power ?? 0);
    if (card.type !== 'anomaly_item') {
      return false;
    }
    if (!tags.has('material')) {
      return false;
    }
    if (tags.has('harmony')) {
      return false;
    }
    if (!card.revealed || card.staged) {
      return false;
    }
    if (Number(card.played_turn || -1) === Number(currentState?.turn || 0)) {
      return false;
    }
    if (!Number.isFinite(power) || power <= 0) {
      return false;
    }
    if (requirements.length && !requirements.some((requirement) => materialMatchesRequirement(card, requirement))) {
      return false;
    }
    if (!requirements.length && requiredAttribute && materialAttribute(card) !== requiredAttribute) {
      return false;
    }
    return !card.reserved_as_material_for;
  });
}

function canSatisfyMaterialRequirements(materials, esperCard) {
  const requirements = expandedMaterialRequirements(materialRequirements(esperCard));
  if (!requirements.length) {
    return true;
  }
  const matchesByRequirement = requirements.map((requirement) =>
    materials
      .map((card, index) => ({ card, index }))
      .filter(({ card }) => materialMatchesRequirement(card, requirement))
      .map(({ index }) => index),
  );
  if (matchesByRequirement.some((matches) => !matches.length)) {
    return false;
  }
  const requirementOrder = requirements
    .map((_, index) => index)
    .sort((a, b) => matchesByRequirement[a].length - matchesByRequirement[b].length || a - b);
  const usedMaterialIndexes = new Set();
  const assignNext = (orderIndex) => {
    if (orderIndex >= requirementOrder.length) {
      return true;
    }
    const requirementIndex = requirementOrder[orderIndex];
    for (const materialIndex of matchesByRequirement[requirementIndex]) {
      if (usedMaterialIndexes.has(materialIndex)) {
        continue;
      }
      usedMaterialIndexes.add(materialIndex);
      if (assignNext(orderIndex + 1)) {
        return true;
      }
      usedMaterialIndexes.delete(materialIndex);
    }
    return false;
  };
  return assignNext(0);
}

function expandedMaterialRequirements(requirements) {
  return requirements.flatMap((requirement) => {
    const count = Math.max(1, Number(requirement.count || 1));
    return Array.from({ length: count }, () => requirement);
  });
}

function materialMatchesRequirement(card, requirement) {
  if (requirement.attribute && materialAttribute(card) !== requirement.attribute) {
    return false;
  }
  if (Array.isArray(requirement.attributes)) {
    const options = requirement.attributes.map((attribute) => String(attribute || '')).filter(Boolean);
    if (options.length && !options.includes(materialAttribute(card))) {
      return false;
    }
  }
  if (requirement.category && String(card.category || '') !== String(requirement.category)) {
    return false;
  }
  if (requirement.name && String(card.name || '') !== String(requirement.name)) {
    return false;
  }
  return true;
}

function requiredMaterialAttribute(card) {
  if (materialRequirements(card).length) {
    return '';
  }
  const attribute = String(card?.required_material_attribute || card?.attribute || '').trim();
  return isWildcardMaterialAttribute(attribute) ? '' : attribute;
}

function displayedMaterialAttribute(card) {
  const attribute = String(card?.required_material_attribute || card?.attribute || '').trim();
  return isWildcardMaterialAttribute(attribute) ? '' : attribute;
}

function isWildcardMaterialAttribute(attribute) {
  return !attribute || attribute === '任意' || attribute === '指定';
}

function materialRequirements(card) {
  return Array.isArray(card?.material_requirements) ? card.material_requirements.filter((requirement) => requirement && typeof requirement === 'object') : [];
}

function materialAttribute(card) {
  return String(card?.attribute || card?.element || '').trim();
}

function esperMaterialCost(card) {
  const requirements = materialRequirements(card);
  if (requirements.length) {
    return requirements.reduce((total, requirement) => total + Number(requirement.count || 1), 0);
  }
  const cost = Number(card?.material_cost || 2);
  return Math.max(2, Math.min(3, Number.isFinite(cost) ? cost : 2));
}

function materialRequirementText(card) {
  if (card?.material_requirement_text) {
    return String(card.material_requirement_text);
  }
  const requirements = materialRequirements(card);
  if (requirements.length) {
    return requirements.map(materialRequirementFragment).join('+');
  }
  const required = esperMaterialCost(card);
  const attribute = displayedMaterialAttribute(card);
  return `${required} ${attribute ? `${attribute}素材` : '素材'}`;
}

function materialRequirementFragment(requirement) {
  const count = Number(requirement.count || 1);
  if (requirement.attribute) {
    return `${requirement.attribute}属性素材*${count}`;
  }
  if (Array.isArray(requirement.attributes)) {
    const options = requirement.attributes.map((attribute) => String(attribute || '')).filter(Boolean);
    if (options.length) {
      return `${options.join('/')}属性素材*${count}`;
    }
  }
  if (requirement.category) {
    return `${requirement.category}素材*${count}`;
  }
  if (requirement.name) {
    return `「${requirement.name}」*${count}`;
  }
  return `素材*${count}`;
}

function startMaterialSelection(card, locationId, options = {}) {
  const location = (currentState?.locations || []).find((candidate) => candidate.id === locationId);
  if (!location) {
    showToast('没有找到目标区域');
    return false;
  }
  const required = esperMaterialCost(card);
  const candidates = materialCandidates(location, card);
  if (candidates.length < required) {
    showToast(`${card.name} 需要 ${materialRequirementText(card)}`);
    return false;
  }
  hideCardPreview({ force: true });
  materialSelection = {
    esperCard: card,
    locationId,
    required,
    selectedIds: [],
  };
  if (options.shieldInitialClick) {
    materialSelectionClickShieldUntil = Date.now() + 500;
  }
  document.body.classList.add('selecting-materials');
  syncControls(currentState);
  syncMaterialSelection();
  return true;
}

function cancelMaterialSelection(options = {}) {
  if (!materialSelection) {
    return;
  }
  materialSelection = null;
  materialSelectionClickShieldUntil = 0;
  document.body.classList.remove('selecting-materials');
  clearMaterialSelectionClasses();
  hideTitleBanner('material');
  if (!options.silent) {
    showToast('已取消素材选择');
  }
  syncControls(currentState);
}

function consumeMaterialSelectionClickShield(event) {
  if (!materialSelectionClickShieldUntil) {
    return false;
  }
  if (Date.now() > materialSelectionClickShieldUntil) {
    materialSelectionClickShieldUntil = 0;
    return false;
  }
  materialSelectionClickShieldUntil = 0;
  event.preventDefault();
  event.stopPropagation();
  if (typeof event.stopImmediatePropagation === 'function') {
    event.stopImmediatePropagation();
  }
  return true;
}

function syncMaterialSelection() {
  clearMaterialSelectionClasses();
  document.body.classList.toggle('selecting-materials', Boolean(materialSelection));
  if (!materialSelection) {
    hideTitleBanner('material');
    return;
  }
  const location = (currentState?.locations || []).find((candidate) => candidate.id === materialSelection.locationId);
  const candidateIds = new Set((location ? materialCandidates(location, materialSelection.esperCard) : []).map((card) => card.instance_id));
  const selectedIds = new Set(materialSelection.selectedIds);
  document.querySelectorAll('.board-card.player').forEach((node) => {
    const card = cardFromPreviewNode(node);
    if (!card) {
      return;
    }
    const inTargetLocation = card.location_id === materialSelection.locationId;
    const selectable = inTargetLocation && candidateIds.has(card.instance_id);
    node.classList.add(selectable ? 'material-candidate' : 'material-unavailable');
    if (selectedIds.has(card.instance_id)) {
      node.classList.add('material-selected');
    }
  });
  const selectedCount = materialSelection.selectedIds.length;
  showTitleBanner(
    '选择共鸣素材',
    `${materialSelection.esperCard.name} · 素材 ${materialRequirementText(materialSelection.esperCard)} · ${selectedCount}/${materialSelection.required}`,
    { sticky: true, kind: 'material' },
  );
}

function clearMaterialSelectionClasses() {
  document.querySelectorAll('.board-card.material-candidate, .board-card.material-selected, .board-card.material-unavailable').forEach((node) => {
    node.classList.remove('material-candidate', 'material-selected', 'material-unavailable');
  });
}

async function handleMaterialClick(event) {
  if (!materialSelection) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  const cardNode = event.target.closest('.board-card.player');
  if (!cardNode || !cardNode.classList.contains('material-candidate')) {
    showToast(`请选择虚线标记的 ${materialRequirementText(materialSelection.esperCard)}`);
    return;
  }
  const instanceId = cardNode.dataset.cardInstanceId;
  const index = materialSelection.selectedIds.indexOf(instanceId);
  if (index >= 0) {
    materialSelection.selectedIds.splice(index, 1);
    syncMaterialSelection();
    return;
  }
  if (materialSelection.selectedIds.length >= materialSelection.required) {
    showToast(`只需要 ${materialSelection.required} 个素材`);
    return;
  }
  materialSelection.selectedIds.push(instanceId);
  syncMaterialSelection();
  if (materialSelection.selectedIds.length >= materialSelection.required) {
    const { esperCard, locationId, selectedIds } = materialSelection;
    materialSelection = null;
    materialSelectionClickShieldUntil = 0;
    document.body.classList.remove('selecting-materials');
    clearMaterialSelectionClasses();
    hideTitleBanner('material');
    await submitPlayEsper(esperCard.instance_id, locationId, selectedIds);
  }
}

function toggleSelectionCard(instanceId, selection) {
  if (actionLocked) {
    return;
  }
  const index = selectedChoiceIds.indexOf(instanceId);
  if (index >= 0) {
    selectedChoiceIds.splice(index, 1);
  } else if (selectedChoiceIds.length < Number(selection.pick_count || 1)) {
    selectedChoiceIds.push(instanceId);
  } else if (Number(selection.pick_count || 1) === 1) {
    selectedChoiceIds = [instanceId];
  } else {
    showToast(`最多选择 ${selection.pick_count} 张`);
  }
  renderSelection(selection);
}

async function confirmSelection(selection) {
  if (actionLocked || selectedChoiceIds.length !== Number(selection.pick_count || 1)) {
    return;
  }
  actionLocked = true;
  try {
    const state = await apiRequest('/api/game/choose-cards', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_instance_ids: selectedChoiceIds }),
    });
    selectedChoiceIds = [];
    selectionKey = '';
    actionLocked = false;
    renderState(state);
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

function beginCardDrag(event, card, sourceNode, options = {}) {
  if (dragState) {
    return;
  }
  if (typeof event.button === 'number' && event.button !== 0) {
    return;
  }
  const dragKind = options.kind || 'hand';
  if (dragKind === 'hand' && !canPlayCard(card)) {
    return;
  }
  if (dragKind === 'esper' && !canPlayEsper(card)) {
    return;
  }
  if (dragKind === 'board' && !canMoveStagedCard(card, sourceNode)) {
    return;
  }
  event.preventDefault();
  const mode = event.type.startsWith('mouse') ? 'mouse' : 'pointer';
  if (mode === 'pointer' && typeof sourceNode.setPointerCapture === 'function') {
    sourceNode.setPointerCapture(event.pointerId);
  }
  dragState = {
    pointerId: event.pointerId ?? null,
    mode,
    kind: dragKind,
    card,
    sourceNode,
    startX: event.clientX,
    startY: event.clientY,
  };
  sourceNode.classList.add('dragging-source');
  dragGhost.innerHTML = cardHtml(card, { compact: true });
  dragGhost.classList.add('open');
  moveGhost(event.clientX, event.clientY);
  document.body.classList.add('card-dragging');
  if (mode === 'mouse') {
    document.addEventListener('mousemove', dragMove);
    document.addEventListener('mouseup', dragEnd);
    document.addEventListener('mouseleave', dragCancel);
  } else {
    sourceNode.addEventListener('pointermove', dragMove);
    sourceNode.addEventListener('pointerup', dragEnd);
    sourceNode.addEventListener('pointercancel', dragCancel);
  }
}

function dragMove(event) {
  if (!dragState || (dragState.mode !== 'mouse' && event.pointerId !== dragState.pointerId)) {
    return;
  }
  moveGhost(event.clientX, event.clientY);
  highlightDropTarget(event.clientX, event.clientY);
}

async function dragEnd(event) {
  if (!dragState || (dragState.mode !== 'mouse' && event.pointerId !== dragState.pointerId)) {
    return;
  }
  const state = dragState;
  const locationId = findDropLocationId(event.clientX, event.clientY);
  const returnedToHand = state.kind === 'board' && isOverHandDock(event.clientX, event.clientY);
  const returnedToStandby = state.kind === 'board' && state.card?.type === 'esper' && isOverEsperStandby(event.clientX, event.clientY);
  const dragDistance = Math.hypot(event.clientX - state.startX, event.clientY - state.startY);
  cleanupDrag();
  if (state.kind === 'board') {
    if (returnedToHand || returnedToStandby) {
      await submitReturnCard(state.card.instance_id);
      return;
    }
    if (locationId && locationId !== state.card.location_id) {
      await submitMoveCard(state.card.instance_id, locationId);
      return;
    }
    if (dragDistance < 8) {
      showCardPreview(state.card, state.sourceNode, { pinned: true, pointerType: event.pointerType || 'mouse' });
    }
    return;
  }
  if (state.kind === 'esper') {
    const location = (currentState?.locations || []).find((candidate) => candidate.id === locationId);
    if (location && canPlayEsperToLocation(location, state.card)) {
      startMaterialSelection(state.card, locationId, { shieldInitialClick: true });
      return;
    }
    if (dragDistance < 8) {
      showCardPreview(state.card, state.sourceNode, { pinned: true, pointerType: event.pointerType || 'mouse' });
    }
    return;
  }
  if (!locationId) {
    if (dragDistance < 8) {
      showCardPreview(state.card, state.sourceNode, { pinned: true, pointerType: event.pointerType || 'mouse' });
    }
    return;
  }
  const location = (currentState?.locations || []).find((candidate) => candidate.id === locationId);
  if (!canPlayCardToLocation(location, state.card)) {
    showToast(canPlayCardReason(state.card, location));
    return;
  }
  await submitPlayCard(state.card.instance_id, locationId);
}

function dragCancel() {
  cleanupDrag();
}

function cleanupDrag() {
  if (!dragState) {
    return;
  }
  dragState.sourceNode.classList.remove('dragging-source');
  if (dragState.mode === 'mouse') {
    document.removeEventListener('mousemove', dragMove);
    document.removeEventListener('mouseup', dragEnd);
    document.removeEventListener('mouseleave', dragCancel);
  } else {
    dragState.sourceNode.removeEventListener('pointermove', dragMove);
    dragState.sourceNode.removeEventListener('pointerup', dragEnd);
    dragState.sourceNode.removeEventListener('pointercancel', dragCancel);
  }
  dragGhost.classList.remove('open');
  dragGhost.innerHTML = '';
  document.body.classList.remove('card-dragging');
  clearDropHighlights();
  dragState = null;
}

function moveGhost(x, y) {
  const width = dragGhost.offsetWidth || 124;
  const height = dragGhost.offsetHeight || 176;
  dragGhost.style.transform = `translate(${x - width / 2}px, ${y - height / 2}px) rotate(-2deg)`;
}

function highlightDropTarget(x, y) {
  clearDropHighlights();
  const locationId = findDropLocationId(x, y);
  if (locationId) {
    const target = document.querySelector(`.duel-location[data-location-id="${cssEscape(locationId)}"]`);
    target?.classList.add('drop-target');
  }
  if (dragState?.kind === 'board' && isOverHandDock(x, y)) {
    document.querySelector('.hand-dock')?.classList.add('drop-target');
  }
  if (dragState?.kind === 'board' && dragState.card?.type === 'esper' && isOverEsperStandby(x, y)) {
    esperStandbyList?.classList.add('drop-target');
  }
}

function clearDropHighlights() {
  document.querySelectorAll('.duel-location.drop-target').forEach((node) => node.classList.remove('drop-target'));
  document.querySelector('.hand-dock')?.classList.remove('drop-target');
  esperStandbyList?.classList.remove('drop-target');
}

function findDropLocationId(x, y) {
  const ghostWasOpen = dragGhost.classList.contains('open');
  dragGhost.style.pointerEvents = 'none';
  const element = document.elementFromPoint(x, y);
  dragGhost.style.pointerEvents = '';
  if (!ghostWasOpen) {
    return null;
  }
  const location = element?.closest?.('.duel-location.can-drop');
  return location?.dataset.locationId || null;
}

function isOverHandDock(x, y) {
  const element = document.elementFromPoint(x, y);
  return Boolean(element?.closest?.('.hand-dock, .hand-rail'));
}

function isOverEsperStandby(x, y) {
  const element = document.elementFromPoint(x, y);
  return Boolean(element?.closest?.('.esper-standby-list, .duel-side-panel'));
}

function canMoveStagedCard(card, sourceNode) {
  return Boolean(
    currentState
    && !actionLocked
    && !materialSelection
    && !presentationLocked
    && currentState.status === 'playing'
    && currentState.phase === 'planning'
    && !currentState.selection
    && card?.staged
    && sourceNode?.classList?.contains('player')
  );
}

async function quickPlayCard(card) {
  if (!canPlayCard(card)) {
    showToast(canPlayCardReason(card));
    return;
  }
  const location = (currentState.locations || []).find((candidate) => canPlayCardToLocation(candidate, card));
  if (!location) {
    showToast(canPlayCardReason(card));
    return;
  }
  await submitPlayCard(card.instance_id, location.id);
}

async function quickPlayEsper(card) {
  if (!canPlayEsper(card)) {
    return;
  }
  const location = (currentState.locations || []).find((candidate) => canPlayEsperToLocation(candidate, card));
  if (!location) {
    showToast('没有可用素材区域');
    return;
  }
  startMaterialSelection(card, location.id);
}

async function submitPlayCard(cardInstanceId, locationId) {
  if (actionLocked) {
    return;
  }
  actionLocked = true;
  syncControls(currentState);
  try {
    const state = await apiRequest('/api/game/play-card', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_instance_id: cardInstanceId, location_id: locationId }),
    });
    actionLocked = false;
    renderState(state);
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

async function submitPlayEsper(cardInstanceId, locationId, materialInstanceIds = []) {
  if (actionLocked) {
    return;
  }
  actionLocked = true;
  syncControls(currentState);
  try {
    const state = await apiRequest('/api/game/play-esper', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        card_instance_id: cardInstanceId,
        location_id: locationId,
        material_instance_ids: materialInstanceIds,
      }),
    });
    actionLocked = false;
    renderState(state);
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

async function submitReturnCard(cardInstanceId) {
  if (actionLocked) {
    return;
  }
  actionLocked = true;
  syncControls(currentState);
  try {
    const state = await apiRequest('/api/game/return-card', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_instance_id: cardInstanceId }),
    });
    actionLocked = false;
    renderState(state);
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

async function submitMoveCard(cardInstanceId, locationId) {
  if (actionLocked) {
    return;
  }
  actionLocked = true;
  syncControls(currentState);
  try {
    const state = await apiRequest('/api/game/move-card', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_instance_id: cardInstanceId, location_id: locationId }),
    });
    actionLocked = false;
    renderState(state);
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

async function endTurn() {
  if (actionLocked || !currentState) {
    return;
  }
  actionLocked = true;
  syncControls(currentState);
  try {
    const state = await apiRequest('/api/game/end-turn', { method: 'POST' });
    actionLocked = false;
    renderState(state);
    if (state.status !== 'playing') {
      showToast(resultText(state));
    }
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

async function resetRun() {
  const confirmed = window.confirm('确认撤退并重置当前对局吗？');
  if (!confirmed) {
    return;
  }
  await apiRequest('/api/game/reset', { method: 'POST' });
  window.location.href = '/home';
}

async function undoTurn() {
  if (actionLocked || !currentState || !currentState.can_undo_turn) {
    return;
  }
  cancelMaterialSelection({ silent: true });
  actionLocked = true;
  syncControls(currentState);
  try {
    const state = await apiRequest('/api/game/undo-turn', { method: 'POST' });
    actionLocked = false;
    renderState(state);
    showToast('已撤销本回合操作');
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

async function copyLog() {
  const text = (currentState?.log || []).map((line, index) => `${String(index + 1).padStart(2, '0')} ${line}`).join('\n');
  try {
    await navigator.clipboard.writeText(text);
    showToast('日志已复制');
  } catch (error) {
    window.prompt('复制日志', text);
  }
}

function resultText(state) {
  if (state.status === 'victory') {
    return '胜利';
  }
  if (state.status === 'defeat') {
    return '失败';
  }
  return '平局';
}

function boardCardHtml(card, owner, previousLocation = null) {
  registerPreviewCard(card);
  const hidden = card.hidden ? ' hidden-card' : '';
  const staged = card.staged ? ' staged-card' : '';
  const reserved = card.reserved_as_material_for ? ' reserved-material-card' : '';
  const bonusPower = Number(card.bonus_power || 0);
  const powerState = bonusPower > 0 ? ' buffed-card' : bonusPower < 0 ? ' damaged-card' : '';
  const previousCard = findPreviousBoardCard(previousLocation, owner, card.instance_id);
  const wasHidden = previousCard?.hidden !== false;
  const justRevealed = Boolean(previousLocation && !card.hidden && (!previousCard || wasHidden));
  const powerChanged = Boolean(
    previousCard
    && !card.hidden
    && Number(card.power ?? card.computed_power ?? 0) !== Number(previousCard.power ?? previousCard.computed_power ?? 0)
  );
  const animated = `${justRevealed ? ' just-revealed' : ''}${powerChanged ? ' power-changed' : ''}`;
  const showCost = Boolean(card.staged && !card.hidden);
  const cost = showCost ? (card.type === 'esper' ? esperMaterialCost(card) : card.cost ?? '?') : '';
  const power = card.power ?? '?';
  const title = card.name || '未揭示';
  const costLabel = card.type === 'esper' ? '素材' : '费';
  const label = `${title}${showCost ? `，${cost} ${costLabel}` : ''}，${power} 战`;
  const showItemCorners = !card.hidden && card.type === 'anomaly_item';
  const attributeCorner = showItemCorners && card.attribute
    ? `<span class="board-card-corner board-card-attribute">${attributeIconMarkup(card, 'board-card-element-icon')}<b>${escapeHtml(card.attribute)}</b></span>`
    : '';
  const categoryCorner = showItemCorners && card.category
    ? `<span class="board-card-corner board-card-category">${escapeHtml(card.category)}</span>`
    : '';
  const declaredNames = declarationNamesForCard(card);
  const declarationLabel = declaredNames.length
    ? `<span class="board-card-declaration"><b>宣言</b><strong>${declaredNames.map((name) => escapeHtml(name)).join('、')}</strong></span>`
    : '';
  return `
    <button class="board-card ${owner}${hidden}${staged}${reserved}${powerState}${animated}" type="button" data-card-instance-id="${escapeAttr(card.instance_id)}" aria-label="查看 ${escapeAttr(label)}">
      <span class="board-card-art" style="background-image: url('${escapeAttr(card.art)}')" aria-hidden="true"></span>
      <span class="board-card-stats" aria-hidden="true">
        ${showCost ? statBadgeHtml(card.type === 'esper' ? 'material' : 'cost', cost, card.type === 'esper' ? card.attribute : '', 'cost', card.type === 'esper' ? materialRequirementText(card) : '') : '<span class="duel-stat-badge hidden-stat"></span>'}
        ${statBadgeHtml('power', power, '', 'power')}
      </span>
      ${attributeCorner}
      ${categoryCorner}
      ${declarationLabel}
      <span class="sr-only">${escapeHtml(title)}</span>
    </button>
  `;
}

function declarationNamesForCard(card) {
  if (!card?.staged || card.hidden) {
    return [];
  }
  const declared = Array.isArray(card.declared_card_names) ? card.declared_card_names : [];
  const names = declared.map((name) => String(name || '').trim()).filter(Boolean);
  const targetName = String(card.selected_target_name || '').trim();
  if (targetName) {
    names.push(targetName);
  }
  return Array.from(new Set(names));
}

function attributeIconMarkup(card, className = 'element-icon') {
  const attribute = String(card?.attribute || '').trim();
  if (!attribute) {
    return '';
  }
  const icon = card.attribute_icon || `${ELEMENT_ICON_BASE}/${attribute}.png`;
  return `<img class="${className}" src="${escapeAttr(icon)}" alt="${escapeAttr(attribute)}" loading="lazy">`;
}

function materialRequirementIconMarkup(card, className = 'element-icon') {
  const attribute = displayedMaterialAttribute(card);
  if (!attribute) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.6 21.2 12 12 21.4 2.8 12 12 2.6Zm0 4.2L6.9 12l5.1 5.2 5.1-5.2L12 6.8Z"></path></svg>';
  }
  const icon = card.attribute_icon || `${ELEMENT_ICON_BASE}/${attribute}.png`;
  return `<img class="${className}" src="${escapeAttr(icon)}" alt="${escapeAttr(attribute)}" loading="lazy">`;
}

function descriptionWithAttributeIcon(card) {
  return `<p class="${descriptionDensityClass(card.description)}"><span>${escapeHtml(card.description || '')}</span></p>`;
}

function itemMetaMarkup(card, options = {}) {
  if (card.type !== 'anomaly_item' && card.type !== 'token') {
    return '';
  }
  const attributeLabel = options.attributeLabel !== false;
  const chips = [];
  if (card.attribute) {
    chips.push(`<span class="card-meta-chip attribute-chip${attributeLabel ? '' : ' icon-only'}" title="${escapeAttr(`${card.attribute}属性`)}">${attributeIconMarkup(card, 'element-icon')}${attributeLabel ? `<b>${escapeHtml(card.attribute)}属性</b>` : ''}</span>`);
  }
  if (card.category) {
    chips.push(`<span class="card-meta-chip">${escapeHtml(card.category)}</span>`);
  }
  return chips.join('');
}

function itemMetaText(card) {
  if (card.type !== 'anomaly_item' && card.type !== 'token') {
    return '';
  }
  return [card.attribute ? `${card.attribute}属性` : '', card.category || ''].filter(Boolean).join(' · ');
}

function descriptionDensityClass(description = '') {
  const length = String(description || '').length;
  if (length >= 92) {
    return 'card-description desc-dense';
  }
  if (length >= 64) {
    return 'card-description desc-long';
  }
  return 'card-description';
}

function cardCostBadgeHtml(card, cost) {
  return card.type === 'esper'
    ? statBadgeHtml('material', esperMaterialCost(card), card.attribute || '', 'cost material-cost', materialRequirementText(card))
    : statBadgeHtml('cost', cost, '', 'cost');
}

function cardPowerBadgeHtml(power) {
  return statBadgeHtml('power', power, '', 'power');
}

function cardArtMarkup(card, mode = 'default') {
  const art = String(card?.art || CARD_BACK_IMAGE);
  if (mode === 'preview') {
    return `
      <div class="card-art preview-card-art">
        <img class="preview-card-art-img item-icon-img" src="${escapeAttr(art)}" alt="" loading="lazy" decoding="async">
      </div>
    `;
  }
  return `<div class="card-art" style="background-image: url('${escapeAttr(art)}')"></div>`;
}

function statBadgeHtml(kind, value, attribute = '', extraClass = '', title = '') {
  return `
    <span class="build-stat-badge build-stat-${escapeAttr(kind)} duel-stat-badge ${escapeAttr(extraClass)}" ${title ? `title="${escapeAttr(title)}"` : ''}>
      ${statIconMarkup(kind, attribute)}
      <strong>${escapeHtml(value)}</strong>
    </span>
  `;
}

function statIconMarkup(kind, attribute = '') {
  if (kind === 'material') {
    if (attribute) {
      return `<img class="build-stat-element-icon" src="${escapeAttr(`${ELEMENT_ICON_BASE}/${attribute}.png`)}" alt="">`;
    }
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.6 21.2 12 12 21.4 2.8 12 12 2.6Zm0 4.2L6.9 12l5.1 5.2 5.1-5.2L12 6.8Z"></path></svg>';
  }
  if (kind === 'cost') {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.6 1.9 5.2 13h6.1l-1.5 10.1 8.9-12.4h-6.2l1.1-8.8Z"></path></svg>';
  }
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3.5 13.4 13l-2.2 2.2L8.7 12.7 6.5 15 4 12.5 6.3 10 3.6 7.3 4 3.5Zm16 0 .4 3.8-2.7 2.7 2.3 2.5-2.5 2.5-2.2-2.3-8.6 8.6H3.8v-2.9l8.6-8.6L20 3.5Z"></path></svg>';
}

function cardHtml(card, { compact, showCurrentStats = true, mode = 'default' }) {
  const cost = card.type === 'esper' ? esperMaterialCost(card) : card.cost ?? '?';
  const power = card.power ?? '?';
  const basePower = card.base_power ?? card.original_power ?? power;
  const displayedPower = mode === 'preview' ? basePower : power;
  const title = card.name || '未揭示';
  const isHandMode = mode === 'hand';
  const description = compact || isHandMode ? '' : descriptionWithAttributeIcon(card);
  const typeLabel = card.type === 'anomaly_item' ? '异象道具' : card.type === 'token' ? '临时牌' : '异能者';
  const itemMeta = itemMetaMarkup(card, { attributeLabel: !isHandMode });
  const typeLine = isHandMode
    ? ''
    : `<div class="card-type-row"><span class="card-type">${escapeHtml(typeLabel)}</span>${itemMeta ? `<div class="card-item-meta">${itemMeta}</div>` : ''}</div>`;
  const itemLine = isHandMode && itemMeta ? `<div class="card-item-meta hand-item-meta">${itemMeta}</div>` : '';
  const currentStats = '';
  const consumedNames = [...new Set((card.consumed_material_names || []).filter(Boolean))];
  const consumedLine = !compact && consumedNames.length
    ? `<div class="card-material-line">已吸收：${consumedNames.map((name) => escapeHtml(name)).join('、')}</div>`
    : '';
  const materialLine = card.type === 'anomaly_item' && card.attribute
    ? ''
    : card.type === 'esper'
      ? `<div class="card-material-line"><span>素材</span><strong>${escapeHtml(materialRequirementText(card))}</strong></div>`
      : '';
  return `
    ${cardArtMarkup(card, mode)}
    <div class="card-stats">
      ${cardCostBadgeHtml(card, cost)}
      ${cardPowerBadgeHtml(displayedPower)}
    </div>
    <div class="card-copy">
      ${typeLine}
      <h3>${escapeHtml(title)}</h3>
      ${itemLine}
      ${materialLine}
      ${currentStats}
      ${consumedLine}
      ${description}
    </div>
  `;
}

function buffSourcesMarkup(card, options = {}) {
  const sources = (card.buff_sources || []).filter((source) => Number(source.amount || 0) !== 0);
  if (!sources.length) {
    return options.empty ? '<div class="buff-source-list empty">暂无增益来源</div>' : '';
  }
  return `
    <div class="buff-source-list">
      ${sources.map((source) => `
        <span>
          <b>${escapeHtml(source.name || '效果')}</b>
          <em>${Number(source.amount || 0) > 0 ? '+' : ''}${escapeHtml(source.amount)}</em>
        </span>
      `).join('')}
    </div>
  `;
}

function previewBuffStripMarkup(card) {
  const markup = buffSourcesMarkup(card);
  return markup ? `<div class="preview-buff-strip">${markup}</div>` : '';
}

function setupCardPreviewInteractions() {
  locationsBoard.addEventListener('click', handleMaterialClick, true);
  locationsBoard.addEventListener('click', handleTargetClick, true);
  locationsBoard.addEventListener('pointerdown', (event) => {
    if (materialSelection || presentationLocked) {
      return;
    }
    const sourceNode = event.target.closest('.board-card.player.staged-card');
    if (!sourceNode || !locationsBoard.contains(sourceNode) || currentState?.pending_target) {
      return;
    }
    const card = cardFromPreviewNode(sourceNode);
    if (card) {
      beginCardDrag(event, card, sourceNode, { kind: 'board' });
    }
  });
  document.addEventListener('pointermove', (event) => {
    if (!currentState?.pending_target) {
      return;
    }
    targetPointer = { x: event.clientX, y: event.clientY };
    renderTargetArrow();
  });
  document.addEventListener('click', (event) => {
    if (!currentState?.pending_target || event.target.closest('#locations-board') || event.target.closest('#card-preview')) {
      return;
    }
    submitCancelTarget();
  }, true);
  document.addEventListener('click', (event) => {
    if (!materialSelection) {
      materialSelectionClickShieldUntil = 0;
      return;
    }
    if (consumeMaterialSelectionClickShield(event) || event.target.closest('#locations-board') || event.target.closest('#card-preview')) {
      return;
    }
    cancelMaterialSelection();
  }, true);

  [locationsBoard, handList, esperStandbyList].forEach((container) => {
    container.addEventListener('pointerover', (event) => {
      if (event.pointerType === 'touch' || dragState) {
        return;
      }
      if (materialSelection || presentationLocked) {
        return;
      }
      if (currentState?.selection && !selectionCollapsed) {
        return;
      }
      if (currentState?.pending_target) {
        return;
      }
      const sourceNode = event.target.closest('.board-card, .hand-card, .esper-card');
      if (!sourceNode || !container.contains(sourceNode)) {
        return;
      }
      const card = cardFromPreviewNode(sourceNode);
      if (card) {
        showCardPreview(card, sourceNode, { pinned: false, pointerType: event.pointerType || 'mouse' });
      }
    });
    container.addEventListener('pointerout', (event) => {
      const sourceNode = event.target.closest('.board-card, .hand-card, .esper-card');
      if (!sourceNode || sourceNode.contains(event.relatedTarget)) {
        return;
      }
      hideCardPreview();
    });
    container.addEventListener('focusin', (event) => {
      if (materialSelection || presentationLocked) {
        return;
      }
      if (currentState?.selection && !selectionCollapsed) {
        return;
      }
      const sourceNode = event.target.closest('.board-card, .hand-card, .esper-card');
      const card = sourceNode ? cardFromPreviewNode(sourceNode) : null;
      if (card) {
        showCardPreview(card, sourceNode, { pinned: false, pointerType: 'keyboard' });
      }
    });
    container.addEventListener('focusout', (event) => {
      const sourceNode = event.target.closest('.board-card, .hand-card, .esper-card');
      if (!sourceNode || sourceNode.contains(event.relatedTarget)) {
        return;
      }
      hideCardPreview();
    });
    container.addEventListener('click', (event) => {
      if (materialSelection || presentationLocked) {
        return;
      }
      if (currentState?.pending_target || (currentState?.selection && !selectionCollapsed)) {
        return;
      }
      const sourceNode = event.target.closest('.board-card, .hand-card, .esper-card');
      if (!sourceNode || !container.contains(sourceNode)) {
        return;
      }
      const card = cardFromPreviewNode(sourceNode);
      if (
        sourceNode.classList.contains('board-card')
        && sourceNode.classList.contains('player')
        && canReactivateEsper(card)
      ) {
        event.preventDefault();
        startMaterialSelection(card, card.location_id);
        return;
      }
      if (card) {
        showCardPreview(card, sourceNode, { pinned: true, pointerType: event.pointerType || 'mouse' });
      }
    });
  });

  cardPreview.addEventListener('click', (event) => {
    if (event.target.closest('[data-card-preview-close]')) {
      hideCardPreview({ force: true });
    }
  });
  document.addEventListener('pointerdown', (event) => {
    if (
      !cardPreview.classList.contains('open')
      || event.target.closest('#card-preview')
      || event.target.closest('.board-card, .hand-card, .esper-card')
    ) {
      return;
    }
    hideCardPreview({ force: true });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (materialSelection) {
        cancelMaterialSelection();
        return;
      }
      hideCardPreview({ force: true });
    }
  });
}

function registerPreviewCard(card) {
  if (card?.instance_id) {
    previewCardsByInstanceId.set(String(card.instance_id), card);
  }
}

function cardFromPreviewNode(node) {
  return previewCardsByInstanceId.get(String(node?.dataset?.cardInstanceId || '')) || null;
}

function showCardPreview(card, sourceNode, options = {}) {
  if (presentationLocked && !options.presentation) {
    return;
  }
  cardPreviewPinned = Boolean(options.pinned);
  const touchLike = options.pointerType === 'touch' || window.matchMedia('(hover: none), (pointer: coarse)').matches;
  cardPreview.className = `duel-card-preview open preview-right${touchLike ? ' touch-preview' : ''}${cardPreviewPinned ? ' pinned' : ''}${options.presentation ? ' presentation-preview' : ''}`;
  cardPreview.setAttribute('aria-hidden', 'false');
  cardPreview.innerHTML = `
    <button class="preview-close" data-card-preview-close type="button" aria-label="关闭卡牌预览">×</button>
    <article class="duel-card preview-card rarity-${classToken(card.rarity)}">
      ${cardHtml(card, { compact: false, mode: 'preview' })}
    </article>
    ${previewBuffStripMarkup(card)}
  `;
}

function hideCardPreview(options = {}) {
  if (presentationLocked && !options.force) {
    return;
  }
  if (cardPreviewPinned && !options.force) {
    return;
  }
  cardPreviewPinned = false;
  cardPreview.className = 'duel-card-preview';
  cardPreview.setAttribute('aria-hidden', 'true');
  cardPreview.replaceChildren();
}

function syncTargetMode(state) {
  document.querySelectorAll('.board-card.legal-target, .board-card.target-source, .board-card.illegal-target').forEach((node) => {
    node.classList.remove('legal-target', 'target-source', 'illegal-target');
  });
  if (!state.pending_target) {
    targetPointer = null;
    effectArrowLayer.replaceChildren();
    hideTitleBanner('target');
    return;
  }
  showTitleBanner(state.pending_target.prompt || '请选择一个目标', '', { sticky: true, kind: 'target' });
  const sourceInstanceId = String(state.pending_target.source_instance_id || '');
  const sourceNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(sourceInstanceId)}"]`);
  sourceNode?.classList.add('target-source');
  const legalIds = new Set(legalTargetIds(state).map((instanceId) => String(instanceId)));
  legalIds.forEach((instanceId) => {
    document.querySelector(`.board-card[data-card-instance-id="${cssEscape(instanceId)}"]`)?.classList.add('legal-target');
  });
  document.querySelectorAll('.board-card').forEach((node) => {
    const instanceId = String(node.dataset.cardInstanceId || '');
    if (instanceId && instanceId !== sourceInstanceId && !legalIds.has(instanceId)) {
      node.classList.add('illegal-target');
    }
  });
  renderTargetArrow();
}

function legalTargetIds(state) {
  const pending = state.pending_target;
  if (!pending) {
    return [];
  }
  if (Array.isArray(pending.target_instance_ids)) {
    return pending.target_instance_ids;
  }
  const sourceLocation = (state.locations || []).find((location) => location.id === pending.location_id);
  const locations = pending.scope?.endsWith('_same_location') && sourceLocation ? [sourceLocation] : state.locations || [];
  const sideKey = pending.scope?.startsWith('opponent') ? 'opponent' : 'player';
  const sourceCard = findCardByInstanceId(state, pending.source_instance_id);
  const ids = [];
  locations.forEach((location) => {
    (location.slots?.[sideKey] || []).forEach((card) => {
      const itemOnly = String(pending.scope || '').includes('_item_');
      if (targetCandidateMatchesScope(card, sourceCard, pending.scope || '', itemOnly)) {
        ids.push(card.instance_id);
      }
    });
  });
  return ids;
}

function findCardByInstanceId(state, instanceId) {
  const wanted = String(instanceId || '');
  for (const location of state.locations || []) {
    for (const owner of ['player', 'opponent']) {
      const card = (location.slots?.[owner] || []).find((candidate) => String(candidate.instance_id || '') === wanted);
      if (card) {
        return card;
      }
    }
  }
  return null;
}

async function handleTargetClick(event) {
  if (!currentState?.pending_target) {
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  const cardNode = event.target.closest('.board-card');
  if (cardNode && cardNode.classList.contains('legal-target')) {
    await submitChooseTarget(cardNode.dataset.cardInstanceId);
    return;
  }
  await submitCancelTarget();
}

async function submitChooseTarget(targetInstanceId) {
  if (actionLocked) {
    return;
  }
  const sourceInstanceId = currentState?.pending_target?.source_instance_id;
  actionLocked = true;
  try {
    const state = await apiRequest('/api/game/choose-target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_instance_id: targetInstanceId }),
    });
    actionLocked = false;
    renderState(state);
    drawConfirmedTargetArrow(sourceInstanceId, targetInstanceId);
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

async function submitCancelTarget() {
  if (actionLocked) {
    return;
  }
  actionLocked = true;
  try {
    const state = await apiRequest('/api/game/cancel-target', { method: 'POST' });
    actionLocked = false;
    renderState(state);
  } catch (error) {
    window.alert(error.message);
  } finally {
    actionLocked = false;
    syncControls(currentState);
  }
}

function renderTargetArrow() {
  const pending = currentState?.pending_target;
  if (!pending) {
    return;
  }
  const sourceNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(pending.source_instance_id)}"]`);
  const sourceRect = sourceNode?.getBoundingClientRect?.();
  if (!sourceRect || !targetPointer) {
    return;
  }
  effectArrowLayer.replaceChildren(buildArrowElement(
    sourceRect.left + sourceRect.width / 2,
    sourceRect.top + sourceRect.height / 2,
    targetPointer.x,
    targetPointer.y,
    'target-live',
  ));
}

function drawConfirmedTargetArrow(sourceInstanceId, targetInstanceId) {
  if (!sourceInstanceId || !targetInstanceId) {
    return;
  }
  const sourceNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(sourceInstanceId)}"]`);
  const targetNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(targetInstanceId)}"]`);
  const sourceRect = sourceNode?.getBoundingClientRect?.();
  const targetRect = targetNode?.getBoundingClientRect?.();
  if (!sourceRect || !targetRect) {
    return;
  }
  effectArrowLayer.replaceChildren(buildArrowElement(
    sourceRect.left + sourceRect.width / 2,
    sourceRect.top + sourceRect.height / 2,
    targetRect.left + targetRect.width / 2,
    targetRect.top + targetRect.height / 2,
    'target-confirmed',
  ));
  window.setTimeout(() => {
    effectArrowLayer.replaceChildren();
    renderDeclarationArrows(currentState);
  }, 620);
}

function renderDeclarationArrows(state) {
  if (!state || state.pending_target || presentationLocked) {
    return;
  }
  const arrows = [];
  (state.locations || []).forEach((location) => {
    ['player', 'opponent'].forEach((owner) => {
      (location.slots?.[owner] || []).forEach((card) => {
        if (!card?.staged || !card.selected_target_instance_id) {
          return;
        }
        const sourceNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(card.instance_id)}"]`);
        const targetNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(card.selected_target_instance_id)}"]`);
        const sourceRect = sourceNode?.getBoundingClientRect?.();
        const targetRect = targetNode?.getBoundingClientRect?.();
        if (!sourceRect || !targetRect) {
          return;
        }
        arrows.push(buildArrowElement(
          sourceRect.left + sourceRect.width / 2,
          sourceRect.top + sourceRect.height / 2,
          targetRect.left + targetRect.width / 2,
          targetRect.top + targetRect.height / 2,
          'declaration-link',
        ));
      });
    });
  });
  if (arrows.length) {
    effectArrowLayer.replaceChildren(...arrows);
  }
}

function buildArrowElement(fromX, fromY, toX, toY, className) {
  const arrow = document.createElement('div');
  const length = Math.max(12, Math.hypot(toX - fromX, toY - fromY));
  const angle = Math.atan2(toY - fromY, toX - fromX) * 180 / Math.PI;
  arrow.className = `effect-arrow ${className}`;
  arrow.style.width = `${length}px`;
  arrow.style.transform = `translate(${fromX}px, ${fromY}px) rotate(${angle}deg)`;
  return arrow;
}

function buildTableTutorialPages() {
  return [
    {
      title: '单一主战场',
      body: [
        '每局共有 6 回合，教学关为 4 回合，双方争夺同一个主战场。',
        '主战场会携带一条随机特性，终局总战力更高者获胜。',
      ],
    },
    {
      title: '有限资源选牌',
      body: [
        '开局从主牌组随机抽取 4 张手牌。',
        '之后每回合开始，双方各从自己的牌库抽 1 张。',
      ],
    },
    {
      title: '拖动出牌',
      body: [
        '你的回合中，拖动手牌到可用空间即可出牌。',
        '每回合能量等于当前回合数，最高 6 点。',
        '手牌与战场卡右上角显示当前战力；卡牌大图右上角显示基础战力。',
      ],
    },
    {
      title: '先后手揭示',
      body: [
        '每回合开始会根据当前总战力锁定结算先手，持平时随机。',
        '点击结束回合后，AI 会完成部署，结算先手方先揭示全部本回合卡牌，再轮到后手方。',
        '卡牌效果由后端事件系统结算，前端只展示结果。',
      ],
    },
  ];
}

async function playPresentation(state, options = {}) {
  const key = presentationKeyForState(state);
  if (key === lastPresentationKey) {
    renderPendingSelectionAfterPresentation(state);
    return;
  }
  lastPresentationKey = key;
  const actions = state.action_queue || [];
  const banners = state.banner_queue || [];

  if (actions.length) {
    await playActionQueue(actions);
  }
  const latestBanner = banners[banners.length - 1];
  if (latestBanner && !currentState?.pending_target) {
    await showTitleBanner(latestBanner.title, latestBanner.subtitle || '', { kind: latestBanner.kind, duration: latestBanner.kind === 'result' ? 3000 : 1300 });
  }
  if (state.status !== 'playing' && !playedResultRedirect) {
    playedResultRedirect = true;
    await sleep(3000);
    window.location.href = '/home';
  }
  if (options.renderFinalAfter) {
    renderState(state);
    return;
  }
  syncRoundInfo(state);
  renderPendingSelectionAfterPresentation(state);
}

function renderPendingSelectionAfterPresentation(state) {
  const activeState = currentState?.selection ? currentState : state;
  if (!activeState?.selection) {
    return;
  }
  renderHand(activeState, { deferSelection: false });
  syncControls(activeState);
}

function presentationKeyForState(state) {
  const actions = state.action_queue || [];
  const banners = state.banner_queue || [];
  const actionKey = actions.map((action) => `${action.kind}:${action.side || ''}:${action.source_instance_id || action.source_location_id || ''}:${action.target_instance_id || action.card_instance_id || action.location_id || ''}:${action.mark || ''}:${action.amount || action.power_delta || ''}:${action.effect_summary || action.title || ''}:${state.turn}`).join('|');
  const bannerKey = banners.map((banner) => `${banner.kind}:${banner.title}:${banner.subtitle}`).join('|');
  return `${state.status}:${state.turn}:${actionKey}:${bannerKey}`;
}

function hasPendingPresentation(state) {
  const actions = state.action_queue || [];
  const banners = state.banner_queue || [];
  if (!state.selection || (!actions.length && !banners.length)) {
    return false;
  }
  return presentationKeyForState(state) !== lastPresentationKey;
}

function hasNewPresentation(state) {
  const actions = state.action_queue || [];
  const banners = state.banner_queue || [];
  if (!actions.length && !banners.length) {
    return false;
  }
  return presentationKeyForState(state) !== lastPresentationKey;
}

async function playActionQueue(actions) {
  presentationLocked = true;
  document.body.classList.add('presentation-locked');
  syncControls(currentState);
  const revealActions = actions.filter((action) => action.kind === 'reveal_card');
  const spawnActions = actions.filter((action) => action.kind === 'spawn_card');
  ensureCoveredCardsForReveal(revealActions);
  revealActions.forEach((action) => {
    document.querySelector(`.board-card[data-card-instance-id="${cssEscape(action.source_instance_id)}"]`)?.classList.add('pre-flip-back');
  });
  spawnActions.forEach((action) => {
    ensureSpawnPresentationCard(action)?.classList.add('effect-pending-card');
  });
  try {
    for (let index = 0; index < actions.length; index += 1) {
      const action = actions[index];
      if (shouldSkipPresentationAction(action)) {
        continue;
      }
      showActionCardPreview(action);
      if (action.kind === 'message' || action.kind === 'turn_begin') {
        showTitleBanner(action.title || '提示', action.subtitle || '', { sticky: true, kind: 'action' });
        await sleep(Math.round(ACTION_ANIMATION_MS * 0.62));
      } else if (action.kind === 'reveal_phase_begin') {
        showTitleBanner(action.title || '揭示阶段', action.subtitle || '双方伏置卡牌扣放。', { sticky: true, kind: 'action' });
        await sleep(Math.round(ACTION_ANIMATION_MS * 0.72));
        continue;
      } else if (action.kind === 'initiative_decided') {
        await sleep(Math.round(ACTION_ANIMATION_MS * 0.18));
      } else if (action.kind === 'reveal_side_begin') {
        continue;
      } else if (action.kind === 'draw_card') {
        const drawGroup = [action];
        while (index + 1 < actions.length && actions[index + 1].kind === 'draw_card') {
          index += 1;
          drawGroup.push(actions[index]);
        }
        if (drawGroup.length > 1) {
          await playDrawCardGroup(drawGroup);
        } else {
          await playDrawCard(action);
        }
      } else if (action.kind === 'reveal_card') {
        showRevealActionBanner(action);
        const node = revealPresentationCard(action);
        const locationNode = node?.closest('.duel-location');
        locationNode?.classList.add('revealing-card');
        node?.classList.remove('pre-flip-back');
        node?.classList.add('flip-reveal-now');
        syncVisibleBoardTotals();
        await sleep(ACTION_ANIMATION_MS);
        node?.classList.remove('flip-reveal-now');
        locationNode?.classList.remove('revealing-card');
      } else if (action.kind === 'consume_material') {
        const materialGroup = [action];
        while (index + 1 < actions.length && actions[index + 1].kind === 'consume_material') {
          index += 1;
          materialGroup.push(actions[index]);
        }
        effectArrowLayer.replaceChildren();
        showTitleBanner('素材消耗', `共 ${materialGroup.length} 张素材转化为战力。`, { sticky: true, kind: 'action' });
        materialGroup.forEach((materialAction) => playMaterialConsume(materialAction));
        await sleep(ACTION_ANIMATION_MS);
        syncVisibleBoardTotals();
        effectArrowLayer.replaceChildren();
      } else if (action.kind === 'spawn_card') {
        playSpawnCard(action);
        await sleep(ACTION_ANIMATION_MS);
        syncVisibleBoardTotals();
      } else if (action.kind === 'spawn_mark') {
        playSpawnMark(action);
        await sleep(ACTION_ANIMATION_MS);
      } else if (action.kind === 'discard_card') {
        playDiscardCard(action);
        await sleep(ACTION_ANIMATION_MS);
        syncVisibleBoardTotals();
      } else if (action.kind === 'impact_arrow') {
        showImpactActionBanner(action);
        playImpactArrow(action);
        syncVisibleBoardTotals();
        await sleep(ACTION_ANIMATION_MS);
      } else if (action.kind === 'effect_summary') {
        showTitleBanner(action.title || '效果结算', action.effect_summary || action.subtitle || '', { sticky: true, kind: 'action' });
        await sleep(Math.round(ACTION_ANIMATION_MS * 0.75));
      } else {
        await sleep(ACTION_ANIMATION_MS);
      }
      await sleep(ACTION_INTERVAL_MS);
    }
  } finally {
    presentationLocked = false;
    document.body.classList.remove('presentation-locked');
    hideCardPreview({ force: true });
    hideTitleBanner('action');
    syncRoundInfo(currentState);
    syncControls(currentState);
  }
  effectArrowLayer.replaceChildren();
}

function shouldSkipPresentationAction(action) {
  if (action.kind === 'reveal_side_begin') {
    return true;
  }
  return action.kind === 'message' && String(action.title || '').includes('成功覆盖');
}

function ensureCoveredCardsForReveal(revealActions) {
  revealActions.forEach((action) => {
    const instanceId = String(action.source_instance_id || '');
    if (!instanceId || document.querySelector(`.board-card[data-card-instance-id="${cssEscape(instanceId)}"]`)) {
      return;
    }
    const locationNode = document.querySelector(`.duel-location[data-location-id="${cssEscape(action.location_id || '')}"]`);
    const publicSide = actionSideToPublic(action.side);
    const slots = locationNode?.querySelector(`.${publicSide}-slots`);
    if (!slots) {
      return;
    }
    const card = {
      ...(action.card || {}),
      instance_id: instanceId,
      hidden: true,
      revealed: false,
      staged: true,
      name: '未揭示',
      art: CARD_BACK_IMAGE,
      type: action.card?.type || 'anomaly_item',
    };
    const wrapper = document.createElement('template');
    wrapper.innerHTML = boardCardHtml(card, publicSide);
    const node = wrapper.content.firstElementChild;
    node?.classList.add('presentation-covered-card', 'pre-flip-back');
    if (node) {
      slots.appendChild(node);
    }
  });
}

function revealPresentationCard(action) {
  const instanceId = String(action.source_instance_id || '');
  let node = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(instanceId)}"]`);
  if (!node || !action.card) {
    return node;
  }
  const publicSide = actionSideToPublic(action.side);
  const template = document.createElement('template');
  template.innerHTML = boardCardHtml({
    ...action.card,
    hidden: false,
    revealed: true,
    staged: false,
  }, publicSide);
  const nextNode = template.content.firstElementChild;
  if (!nextNode) {
    return node;
  }
  node.replaceWith(nextNode);
  return nextNode;
}

function ensureSpawnPresentationCard(action) {
  const instanceId = String(action.target_instance_id || '');
  if (!instanceId) {
    return null;
  }
  let node = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(instanceId)}"]`);
  if (node) {
    return node;
  }
  const locationNode = document.querySelector(`.duel-location[data-location-id="${cssEscape(action.location_id || '')}"]`);
  const publicSide = actionSideToPublic(action.side);
  const slots = locationNode?.querySelector(`.${publicSide}-slots`);
  if (!slots) {
    return null;
  }
  const card = {
    ...(action.card || {}),
    instance_id: instanceId,
    hidden: true,
    revealed: false,
    staged: true,
    name: '未揭示',
    art: CARD_BACK_IMAGE,
    type: action.card?.type || 'anomaly_item',
  };
  const wrapper = document.createElement('template');
  wrapper.innerHTML = boardCardHtml(card, publicSide);
  node = wrapper.content.firstElementChild;
  node?.classList.add('presentation-covered-card', 'effect-pending-card', 'pre-flip-back');
  if (node) {
    slots.appendChild(node);
  }
  return node;
}

function showRevealActionBanner(action) {
  const summary = action.effect_summary || action.subtitle || '';
  if (!summary) {
    hideTitleBanner('action');
    return;
  }
  showTitleBanner(action.title || '揭示', summary, { sticky: true, kind: 'action' });
}

function showActionCardPreview(action) {
  if (action.kind === 'draw_card') {
    return;
  }
  const instanceId = action.source_instance_id || action.target_instance_id || '';
  const card = action.kind === 'reveal_card' && action.card
    ? action.card
    : previewCardsByInstanceId.get(String(instanceId))
    || previewCardsByInstanceId.get(String(action.target_instance_id || ''))
    || action.card;
  if (!card) {
    return;
  }
  showCardPreview(card, null, { presentation: true, pinned: false, pointerType: 'mouse' });
}

function playMaterialConsume(action) {
  const publicSide = actionSideToPublic(action.side);
  const sourceCardNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(action.source_instance_id)}"]`);
  const sourceNode = sourceCardNode
    || (publicSide === 'opponent'
      ? document.querySelector(`.duel-location[data-location-id="${cssEscape(action.location_id || '')}"]`)
      : null);
  const targetNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(action.target_instance_id)}"]`);
  const sourceRect = sourceNode?.getBoundingClientRect?.();
  const targetRect = targetNode?.getBoundingClientRect?.();
  if (!targetRect) {
    return;
  }
  if (sourceRect) {
    playMaterialMoveToDiscard(sourceNode, action);
    removeBoardCardNodeToDiscard(sourceNode, publicSide);
  } else {
    playHiddenMaterialMoveToDiscard(action);
    incrementDiscardCount(publicSide);
  }
  targetNode.classList.add('material-fed');
  showPowerFloat(targetNode, Number(action.material_power || 0), null, null, { kind: 'buff' });
  applyIncrementalBoardPower(targetNode, Number(action.material_power || 0));
  if (sourceRect) {
    effectArrowLayer.appendChild(buildArrowElement(
      sourceRect.left + sourceRect.width / 2,
      sourceRect.top + sourceRect.height / 2,
      targetRect.left + targetRect.width / 2,
      targetRect.top + targetRect.height / 2,
      'material-consume',
    ));
  }
  window.setTimeout(() => targetNode.classList.remove('material-fed'), ACTION_ANIMATION_MS);
}

function playDiscardCard(action) {
  const sourceNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(action.source_instance_id)}"]`);
  if (!sourceNode) {
    incrementDiscardCount(actionSideToPublic(action.side));
    return;
  }
  showTitleBanner(action.title || '进入墓地', action.subtitle || '', { sticky: true, kind: 'action' });
  playMaterialMoveToDiscard(sourceNode, action);
  removeBoardCardNodeToDiscard(sourceNode, actionSideToPublic(action.side));
}

function playMaterialMoveToDiscard(sourceNode, action) {
  if (!effectArrowLayer || !sourceNode) {
    return;
  }
  const publicSide = actionSideToPublic(action.side);
  const discardNode = publicSide === 'opponent' ? opponentDiscardBtn : playerDiscardBtn;
  const sourceRect = sourceNode.getBoundingClientRect?.();
  const targetRect = discardNode?.getBoundingClientRect?.();
  if (!sourceRect || !targetRect) {
    return;
  }
  const artNode = sourceNode.querySelector?.('.board-card-art');
  const ghost = document.createElement('div');
  ghost.className = 'material-card-ghost';
  ghost.style.backgroundImage = artNode?.style?.backgroundImage || '';
  ghost.style.width = `${Math.max(42, sourceRect.width * 0.72)}px`;
  ghost.style.height = `${Math.max(58, sourceRect.height * 0.72)}px`;
  effectArrowLayer.appendChild(ghost);
  const fromX = sourceRect.left + sourceRect.width * 0.14;
  const fromY = sourceRect.top + sourceRect.height * 0.14;
  const toX = targetRect.left + targetRect.width / 2 - parseFloat(ghost.style.width) / 2;
  const toY = targetRect.top + targetRect.height / 2 - parseFloat(ghost.style.height) / 2;
  const animation = ghost.animate([
    { opacity: 0.92, transform: `translate(${fromX}px, ${fromY}px) scale(1)` },
    { opacity: 0.86, offset: 0.48, transform: `translate(${(fromX + toX) / 2}px, ${Math.min(fromY, toY) - 60}px) scale(0.82)` },
    { opacity: 0, transform: `translate(${toX}px, ${toY}px) scale(0.42)` },
  ], {
    duration: ACTION_ANIMATION_MS,
    easing: 'cubic-bezier(0.18, 0.82, 0.24, 1)',
    fill: 'forwards',
  });
  Promise.race([
    animation.finished.catch(() => null),
    sleep(ACTION_ANIMATION_MS + 140),
  ]).finally(() => ghost.remove());
  sourceNode.classList.add('material-consuming');
  window.setTimeout(() => sourceNode.classList.remove('material-consuming'), ACTION_ANIMATION_MS);
}

function playHiddenMaterialMoveToDiscard(action) {
  if (!effectArrowLayer) {
    return;
  }
  const publicSide = actionSideToPublic(action.side);
  const discardNode = publicSide === 'opponent' ? opponentDiscardBtn : playerDiscardBtn;
  const targetRect = discardNode?.getBoundingClientRect?.();
  if (!targetRect) {
    return;
  }
  const ghost = document.createElement('div');
  ghost.className = 'material-card-ghost floating-material-ghost';
  ghost.style.backgroundImage = `url('${escapeAttr(action.card?.art || CARD_BACK_IMAGE)}')`;
  const width = 52;
  const height = 73;
  ghost.style.width = `${width}px`;
  ghost.style.height = `${height}px`;
  const ghostIndex = effectArrowLayer.querySelectorAll('.floating-material-ghost').length;
  const spread = (ghostIndex % 5) - 2;
  effectArrowLayer.appendChild(ghost);
  const fromX = targetRect.left + targetRect.width / 2 - width / 2 + spread * 16;
  const fromY = targetRect.top - height - 16 - Math.floor(ghostIndex / 5) * 10;
  const toX = targetRect.left + targetRect.width / 2 - width / 2;
  const toY = targetRect.top + targetRect.height / 2 - height / 2;
  const animation = ghost.animate([
    { opacity: 0, transform: `translate(${fromX}px, ${fromY - 12}px) scale(0.76)` },
    { opacity: 0.96, offset: 0.28, transform: `translate(${fromX}px, ${fromY}px) scale(1)` },
    { opacity: 0.78, offset: 0.58, transform: `translate(${fromX}px, ${fromY}px) scale(0.9)` },
    { opacity: 0, transform: `translate(${toX}px, ${toY}px) scale(0.42)` },
  ], {
    duration: ACTION_ANIMATION_MS,
    easing: 'cubic-bezier(0.18, 0.82, 0.24, 1)',
    fill: 'forwards',
  });
  Promise.race([
    animation.finished.catch(() => null),
    sleep(ACTION_ANIMATION_MS + 140),
  ]).finally(() => ghost.remove());
}

function removeBoardCardNodeToDiscard(sourceNode, publicSide) {
  if (!sourceNode?.classList?.contains('board-card') || sourceNode.dataset.discardAnimated === 'true') {
    return;
  }
  sourceNode.dataset.discardAnimated = 'true';
  incrementDiscardCount(publicSide);
  window.setTimeout(() => {
    sourceNode.remove();
    renderDeclarationArrows(currentState);
  }, 140);
}

function incrementDiscardCount(publicSide, amount = 1) {
  const nodes = [];
  if (publicSide === 'opponent') {
    nodes.push(opponentDiscardCount, opponentDiscardBtn?.querySelector('.deck-copy strong'));
  } else {
    nodes.push(playerDiscardCount, playerDiscardBtn?.querySelector('.deck-copy strong'));
  }
  nodes.filter(Boolean).forEach((node) => {
    const current = Number(node.textContent || 0);
    node.textContent = String((Number.isFinite(current) ? current : 0) + amount);
  });
}

function applyIncrementalBoardPower(targetNode, amount) {
  if (!targetNode || !Number.isFinite(Number(amount)) || Number(amount) === 0) {
    return;
  }
  const valueNode = targetNode.querySelector('.board-card-stats .build-stat-power strong');
  const current = Number(valueNode?.textContent);
  if (!valueNode || !Number.isFinite(current)) {
    return;
  }
  updateBoardCardPower(targetNode, current + Number(amount));
}

function updateBoardCardPower(targetNode, powerAfter) {
  const nextPower = Number(powerAfter);
  if (!targetNode || !Number.isFinite(nextPower)) {
    return;
  }
  const valueNode = targetNode.querySelector('.board-card-stats .build-stat-power strong');
  if (valueNode) {
    valueNode.textContent = String(nextPower);
  }
  const card = cardFromPreviewNode(targetNode);
  const basePower = Number(card?.base_power ?? card?.original_power ?? nextPower);
  if (card) {
    card.power = nextPower;
    card.computed_power = nextPower;
  }
  targetNode.classList.toggle('buffed-card', Number.isFinite(basePower) && nextPower > basePower);
  targetNode.classList.toggle('damaged-card', Number.isFinite(basePower) && nextPower < basePower);
  targetNode.classList.add('power-changed');
  window.setTimeout(() => targetNode.classList.remove('power-changed'), ACTION_ANIMATION_MS);
}

function syncVisibleBoardTotals() {
  if (!locationsBoard) {
    return;
  }
  const totals = { player: 0, opponent: 0 };
  locationsBoard.querySelectorAll('.duel-location').forEach((locationNode) => {
    if (locationNode.classList.contains('unrevealed')) {
      return;
    }
    const playerPower = visibleLocationPower(locationNode, 'player');
    const opponentPower = visibleLocationPower(locationNode, 'opponent');
    totals.player += playerPower;
    totals.opponent += opponentPower;
    updateLocationPowerRows(locationNode, playerPower, opponentPower);
  });
  updateVisibleScoreReadouts(totals);
}

function visibleLocationPower(locationNode, owner) {
  return Array.from(locationNode.querySelectorAll(`.${owner}-slots .board-card:not(.hidden-card):not(.staged-card)`))
    .filter((node) => node.dataset.discardAnimated !== 'true')
    .reduce((total, node) => total + boardCardPowerFromNode(node), 0);
}

function boardCardPowerFromNode(node) {
  const value = Number(node.querySelector('.board-card-stats .build-stat-power strong')?.textContent);
  return Number.isFinite(value) ? value : 0;
}

function updateLocationPowerRows(locationNode, playerPower, opponentPower) {
  setPowerRowValue(locationNode.querySelector('.location-power-row.player > strong'), playerPower);
  setPowerRowValue(locationNode.querySelector('.location-power-row.opponent > strong'), opponentPower);
  const winner = playerPower > opponentPower ? 'player' : opponentPower > playerPower ? 'opponent' : 'tie';
  locationNode.classList.remove('winner-player', 'winner-opponent', 'winner-tie', 'winner-unknown');
  locationNode.classList.add(`winner-${winner}`);
  const leaderNode = locationNode.querySelector('.location-leader');
  if (leaderNode) {
    leaderNode.textContent = winner === 'player' ? '我方领先' : winner === 'opponent' ? '对手领先' : '持平';
  }
}

function setPowerRowValue(valueNode, nextValue) {
  if (!valueNode) {
    return;
  }
  const currentValue = Number(valueNode.textContent || 0);
  if (Number.isFinite(currentValue) && currentValue === Number(nextValue)) {
    return;
  }
  valueNode.textContent = String(nextValue);
  const rowNode = valueNode.closest('.location-power-row');
  rowNode?.classList.add('power-changed');
  window.setTimeout(() => rowNode?.classList.remove('power-changed'), ACTION_ANIMATION_MS);
}

function updateVisibleScoreReadouts(totals) {
  const totalText = `${totals.player} - ${totals.opponent}`;
  const compactTotalText = `${totals.player}-${totals.opponent}`;
  const leaderText = totals.player > totals.opponent ? '我方' : totals.opponent > totals.player ? '对手' : '持平';
  const hudScore = duelHud?.querySelectorAll('span')?.[2];
  if (hudScore) {
    hudScore.textContent = `主战场 ${compactTotalText}`;
  }
  const statusCards = leftStatusGrid?.querySelectorAll('.side-status-card') || [];
  const powerCard = statusCards[1];
  const powerValue = powerCard?.querySelector('strong');
  const powerHint = powerCard?.querySelector('small');
  if (powerValue) {
    powerValue.textContent = totalText;
  }
  if (powerHint) {
    powerHint.textContent = `实时领先：${leaderText}`;
  }
  const opponentPowerValue = rightResourceGrid?.querySelectorAll('.right-resource-card')?.[2]?.querySelector('strong');
  if (opponentPowerValue) {
    opponentPowerValue.textContent = String(totals.opponent);
  }
}

function playSpawnCard(action) {
  const targetNode = ensureSpawnPresentationCard(action);
  if (!targetNode) {
    return;
  }
  showTitleBanner(action.title || '效果生成', action.subtitle || '', { sticky: true, kind: 'action' });
  targetNode.classList.remove('effect-pending-card');
  targetNode.classList.add('flip-reveal-now');
  playImpactArrow(action);
  window.setTimeout(() => targetNode.classList.remove('flip-reveal-now'), ACTION_ANIMATION_MS);
}

function playSpawnMark(action) {
  const locationNode = document.querySelector(`.duel-location[data-location-id="${cssEscape(action.location_id || action.source_location_id || '')}"]`);
  showTitleBanner(action.title || '区域标记', action.subtitle || '', { sticky: true, kind: 'action' });
  if (!locationNode) {
    return;
  }
  updateLocationMarkDisplay(action, locationNode);
  locationNode.classList.add('mark-pulse');
  playImpactArrow(action);
  window.setTimeout(() => locationNode.classList.remove('mark-pulse'), ACTION_ANIMATION_MS);
}

function updateLocationMarkDisplay(action, locationNode) {
  const mark = String(action.mark || '');
  if (!mark) {
    return;
  }
  const publicSide = actionSideToPublic(action.side);
  const row = locationNode.querySelector(`.location-power-row.${publicSide}`);
  if (!row) {
    return;
  }
  let marksNode = row.querySelector('.location-marks');
  if (!marksNode) {
    marksNode = document.createElement('div');
    marksNode.className = 'location-marks';
    row.appendChild(marksNode);
  }
  marksNode.classList.remove('empty');
  let chip = marksNode.querySelector(`.location-mark[data-mark="${cssEscape(mark)}"]`);
  const current = Number(chip?.querySelector('strong')?.textContent || 0);
  const count = Number.isFinite(Number(action.mark_count))
    ? Number(action.mark_count)
    : current + Number(action.amount || 1);
  if (!chip) {
    chip = document.createElement('span');
    chip.className = `location-mark ${publicSide}`;
    chip.dataset.mark = mark;
    chip.innerHTML = `
      <b>${publicSide === 'opponent' ? '敌' : '我'}</b>
      <span>${escapeHtml(LOCATION_MARK_LABELS[mark] || mark)}</span>
      <strong>${escapeHtml(count)}</strong>
    `;
    marksNode.appendChild(chip);
    return;
  }
  const countNode = chip.querySelector('strong');
  if (countNode) {
    countNode.textContent = String(count);
  }
}

function playImpactArrow(action) {
  const sourceNode = action.source_instance_id
    ? document.querySelector(`.board-card[data-card-instance-id="${cssEscape(action.source_instance_id)}"]`)
    : document.querySelector(`.duel-location[data-location-id="${cssEscape(action.source_location_id)}"]`);
  const targetNode = document.querySelector(`.board-card[data-card-instance-id="${cssEscape(action.target_instance_id)}"]`);
  const sourceRect = sourceNode?.getBoundingClientRect?.();
  const targetRect = targetNode?.getBoundingClientRect?.();
  if (!sourceRect || !targetRect) {
    return;
  }
  effectArrowLayer.replaceChildren(buildArrowElement(
    sourceRect.left + sourceRect.width / 2,
    sourceRect.top + sourceRect.height / 2,
    targetRect.left + targetRect.width / 2,
    targetRect.top + targetRect.height / 2,
    'impact',
  ));
  const amount = Number(action.power_delta || 0);
  if (amount) {
    showPowerFloat(targetNode, amount, action.power_before, action.power_after, { kind: amount > 0 ? 'buff' : 'damage' });
    updateBoardCardPower(targetNode, action.power_after);
  }
}

function showImpactActionBanner(action) {
  const title = action.title || '';
  if (!title) {
    return;
  }
  const subtitle = action.subtitle || powerChangeText(action);
  showTitleBanner(title, subtitle, { sticky: true, kind: 'action' });
}

function powerChangeText(action) {
  const before = Number(action.power_before);
  const after = Number(action.power_after);
  const delta = Number(action.power_delta || 0);
  if (Number.isFinite(before) && Number.isFinite(after) && delta) {
    return `${before} ${delta > 0 ? '+' : '-'} ${Math.abs(delta)} = ${after}`;
  }
  return '';
}

function showPowerFloat(targetNode, amount, before = null, after = null, options = {}) {
  if (!targetNode || !Number.isFinite(Number(amount)) || Number(amount) === 0) {
    return;
  }
  const rect = targetNode.getBoundingClientRect?.();
  const layer = effectArrowLayer || document.body;
  if (!rect) {
    return;
  }
  const value = Number(amount);
  const marker = document.createElement('div');
  marker.className = `power-float ${options.kind === 'damage' || value < 0 ? 'damage' : 'buff'}`;
  if (Number.isFinite(Number(before)) && Number.isFinite(Number(after))) {
    marker.innerHTML = `
      <span>${escapeHtml(before)}</span>
      <em>${value > 0 ? '+' : '-'}${escapeHtml(Math.abs(value))}</em>
      <strong>${escapeHtml(after)}</strong>
    `;
  } else {
    marker.innerHTML = `<strong>${value > 0 ? '+' : ''}${escapeHtml(value)}</strong>`;
  }
  marker.style.left = `${rect.left + rect.width / 2}px`;
  marker.style.top = `${Math.max(8, rect.top - 8)}px`;
  layer.appendChild(marker);
  window.setTimeout(() => marker.remove(), 1120);
}

async function playDrawCardGroup(actions) {
  const visible = actions.find((action) => !action.silent);
  if (visible) {
    showTitleBanner(visible.title || '抽牌', visible.subtitle || '从牌库加入手牌', { sticky: true, kind: 'action' });
  }
  await Promise.all(actions.map((action) => playDrawCard(action, { suppressBanner: true })));
}

async function playDrawCard(action, options = {}) {
  const publicSide = actionSideToPublic(action.side);
  const deckNode = publicSide === 'opponent' ? opponentDeckZone : playerDeckZone;
  const targetNode = drawTargetNode(publicSide, action.card_instance_id) || createDrawPlaceholder(publicSide, action.card_instance_id);
  const label = publicSide === 'opponent' ? '对手' : '我方';
  if (!action.silent && !options.suppressBanner) {
    showTitleBanner(action.title || '抽牌', `${label}${action.subtitle || '从牌库加入手牌'}`, { sticky: true, kind: 'action' });
  }
  deckNode?.classList.add('deck-draw-pulse');
  targetNode?.classList.add('hand-receive-pulse');
  const sourceRect = deckNode?.getBoundingClientRect?.();
  const targetRect = targetNode?.getBoundingClientRect?.();
  if (sourceRect && targetRect) {
    await playDrawInsertCard(sourceRect, targetRect, publicSide, action.card || null);
  } else {
    await sleep(ACTION_ANIMATION_MS);
  }
  deckNode?.classList.remove('deck-draw-pulse');
  targetNode?.classList.remove('hand-receive-pulse');
  commitDrawnCardToHand(publicSide, action, targetNode);
}

function createDrawPlaceholder(publicSide, cardInstanceId) {
  const rail = publicSide === 'opponent' ? opponentHandList : handList;
  if (!rail) {
    return null;
  }
  rail.querySelector('.empty-state')?.remove();
  const placeholder = document.createElement('div');
  placeholder.className = `draw-hand-slot-placeholder ${publicSide}`;
  placeholder.dataset.cardInstanceId = String(cardInstanceId || '');
  placeholder.setAttribute('aria-hidden', 'true');
  rail.appendChild(placeholder);
  return placeholder;
}

function playDrawInsertCard(sourceRect, targetRect, publicSide, card = null) {
  if (!effectArrowLayer) {
    return sleep(ACTION_ANIMATION_MS);
  }
  const ghost = document.createElement('div');
  const faceUp = publicSide === 'player' && card && !card.hidden;
  ghost.className = `draw-card-ghost ${publicSide}${faceUp ? ' face-up' : ''}`;
  const art = faceUp ? String(card.art || '') : '';
  if (art) {
    ghost.style.setProperty('--draw-card-art', `url("${cssUrlEscape(art)}")`);
  }
  ghost.innerHTML = `<span>${faceUp ? escapeHtml(card.name || '') : ''}</span>`;
  const cardWidth = Math.max(publicSide === 'opponent' ? 38 : 62, targetRect.width);
  const cardHeight = Math.max(Math.round(cardWidth * 1.38), targetRect.height);
  ghost.style.width = `${cardWidth}px`;
  ghost.style.height = `${cardHeight}px`;
  effectArrowLayer.appendChild(ghost);
  const fromX = sourceRect.left + sourceRect.width / 2 - cardWidth / 2;
  const fromY = sourceRect.top + sourceRect.height / 2 - cardHeight / 2;
  const toX = targetRect.left + targetRect.width / 2 - cardWidth / 2;
  const toY = targetRect.top + targetRect.height / 2 - cardHeight / 2;
  const midX = (fromX + toX) / 2 + (publicSide === 'opponent' ? -28 : 36);
  const midY = Math.min(fromY, toY) - 86;
  const animation = ghost.animate([
    { opacity: 0, transform: `translate(${fromX}px, ${fromY}px) scale(0.42) rotate(-10deg)` },
    { opacity: 1, offset: 0.18, transform: `translate(${fromX}px, ${fromY}px) scale(0.7) rotate(-8deg)` },
    { opacity: 1, offset: 0.58, transform: `translate(${midX}px, ${midY}px) scale(0.96) rotate(8deg)` },
    { opacity: 1, transform: `translate(${toX}px, ${toY}px) scale(1) rotate(0deg)` },
  ], {
    duration: ACTION_ANIMATION_MS,
    easing: 'cubic-bezier(0.18, 0.82, 0.24, 1)',
    fill: 'forwards',
  });
  return Promise.race([
    animation.finished.catch(() => null),
    sleep(ACTION_ANIMATION_MS + 140),
  ]).finally(() => ghost.remove());
}

function commitDrawnCardToHand(publicSide, action, targetNode) {
  if (!targetNode) {
    return;
  }
  const card = action.card || null;
  if (publicSide === 'opponent') {
    const next = document.createElement('template');
    next.innerHTML = hiddenHandCardHtml({
      instance_id: action.card_instance_id || `opponent-drawn-${Date.now()}`,
      art: CARD_BACK_IMAGE,
    }, opponentHandList?.querySelectorAll('.opponent-hand-card').length || 0);
    targetNode.replaceWith(next.content.firstElementChild);
    if (opponentHandCount) {
      opponentHandCount.textContent = String(opponentHandList?.querySelectorAll('.opponent-hand-card').length || 0);
    }
    return;
  }
  if (!card) {
    targetNode.remove();
    return;
  }
  registerPreviewCard(card);
  const node = document.createElement('article');
  node.className = `duel-card hand-card rarity-${classToken(card.rarity)}`;
  node.dataset.cardInstanceId = card.instance_id || action.card_instance_id || '';
  applyHandCardState(node, card);
  node.innerHTML = cardHtml(card, { compact: false, showCurrentStats: false, mode: 'hand' });
  attachHandCardHandlers(node, card);
  targetNode.replaceWith(node);
}

function drawTargetNode(publicSide, cardInstanceId) {
  if (publicSide === 'opponent') {
    return document.querySelector(`.opponent-hand-card[data-card-instance-id="${cssEscape(cardInstanceId || '')}"]`);
  }
  return document.querySelector(`.hand-card[data-card-instance-id="${cssEscape(cardInstanceId || '')}"]`);
}

function actionSideToPublic(side) {
  if (!currentState) {
    return side === 'b' ? 'opponent' : 'player';
  }
  if (side === currentState.player_seat || side === 'player') {
    return 'player';
  }
  if (side === currentState.opponent_seat || side === 'opponent') {
    return 'opponent';
  }
  return side === 'b' ? 'opponent' : 'player';
}

function showTitleBanner(title, subtitle = '', options = {}) {
  if (!duelTitleBanner) {
    return Promise.resolve();
  }
  duelTitleBanner.dataset.kind = options.kind || '';
  duelTitleBanner.innerHTML = `
    <strong>${escapeHtml(title || '')}</strong>
    ${subtitle ? `<span>${escapeHtml(subtitle)}</span>` : ''}
  `;
  duelTitleBanner.classList.add('open');
  duelTitleBanner.setAttribute('aria-hidden', 'false');
  if (options.sticky) {
    return Promise.resolve();
  }
  const duration = Number(options.duration || 1200);
  return sleep(duration).then(() => {
    hideTitleBanner(options.kind || '');
  });
}

function hideTitleBanner(kind = '') {
  if (!duelTitleBanner) {
    return;
  }
  if (kind && duelTitleBanner.dataset.kind && duelTitleBanner.dataset.kind !== kind) {
    return;
  }
  duelTitleBanner.classList.remove('open');
  duelTitleBanner.setAttribute('aria-hidden', 'true');
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function showToast(message) {
  duelToast.textContent = message;
  duelToast.classList.add('open');
  duelToast.setAttribute('aria-hidden', 'false');
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    duelToast.classList.remove('open');
    duelToast.setAttribute('aria-hidden', 'true');
  }, 1800);
}

function classToken(value) {
  return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
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

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#96;');
}

function cssEscape(value) {
  if (window.CSS?.escape) {
    return window.CSS.escape(value);
  }
  return String(value).replace(/["\\]/g, '\\$&');
}

function cssUrlEscape(value) {
  return String(value || '').replace(/["\\\n\r]/g, (char) => `\\${char}`);
}

function findPreviousBoardCard(previousLocation, owner, instanceId) {
  if (!previousLocation || !instanceId) {
    return null;
  }
  const cards = previousLocation.slots?.[owner] || [];
  return cards.find((card) => card.instance_id === instanceId) || null;
}

endTurnBtn.addEventListener('click', endTurn);
copyLogBtn.addEventListener('click', copyLog);
rightPanelTabs.forEach((button) => {
  button.addEventListener('click', () => setRightPanelView(button.dataset.rightPanelView || 'info'));
});
playerDiscardBtn?.addEventListener('click', () => openDiscardModal('player'));
opponentDiscardBtn?.addEventListener('click', () => openDiscardModal('opponent'));
discardModal?.addEventListener('click', (event) => {
  if (event.target === discardModal) {
    closeDiscardModal();
  }
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && activeDiscardSide) {
    closeDiscardModal();
  }
});
undoTurnBtn.addEventListener('click', undoTurn);
resetRunBtn.addEventListener('click', resetRun);
window.addEventListener('resize', () => renderDeclarationArrows(currentState));
syncRightPanel();
