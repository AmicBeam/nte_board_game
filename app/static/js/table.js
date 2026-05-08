const phaseChip = document.getElementById('phase-chip');
const statsGrid = document.getElementById('stats-grid');
const routeHint = document.getElementById('route-hint');
const mapName = document.getElementById('map-name');
const mapBackground = document.getElementById('map-background');
const mapOverlay = document.getElementById('map-overlay');
const handList = document.getElementById('hand-list');
const logList = document.getElementById('log-list');
const resetRunBtn = document.getElementById('reset-run-btn');
const directionButtons = Array.from(document.querySelectorAll('[data-direction]'));

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
  return `<span class="map-icon icon-${kind}"></span>`;
}

function renderState(state) {
  phaseChip.textContent = prettyPhase(state.phase);
  routeHint.textContent = state.route_hint;
  mapName.textContent = state.map.name;
  mapBackground.src = state.board.background_image;

  statsGrid.innerHTML = `
    <div class="stat-card"><span>回合</span><strong>${state.turn}</strong></div>
    <div class="stat-card"><span>骰子</span><strong>${state.pending_die ?? '-'}</strong></div>
    <div class="stat-card"><span>生命</span><strong>${state.player.hp} / ${state.player.max_hp}</strong></div>
    <div class="stat-card"><span>攻击</span><strong>${state.computed_stats.attack}</strong></div>
    <div class="stat-card"><span>防御</span><strong>${state.computed_stats.defense}</strong></div>
    <div class="stat-card"><span>钥匙</span><strong>${state.player.keys}</strong></div>
    <div class="stat-card"><span>Boss HP</span><strong>${state.map.boss.hp} / ${state.map.boss.max_hp}</strong></div>
    <div class="stat-card"><span>角色</span><strong>${state.selected_character.name}</strong></div>
  `;

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
    node.type = 'button';
    node.innerHTML = `${iconMarkup(icon.icon)}${icon.entity_type === 'player' ? '<span class="player-chip">我</span>' : ''}<span class="sr-only">${icon.tooltip}</span><span class="tooltip-bubble">${icon.tooltip}</span>`;
    mapOverlay.appendChild(node);
  });

  if (state.hand_details.length === 0) {
    handList.innerHTML = '<div class="empty-state">当前没有手牌</div>';
  } else {
    handList.innerHTML = '';
    state.hand_details.forEach((item) => {
      const card = document.createElement('article');
      card.className = 'hand-card';
      card.innerHTML = `
        <span class="card-tag">${item.type} · ${item.rarity}</span>
        <h3>${item.name}</h3>
        <p class="card-meta">${item.description}</p>
        <button ${state.phase !== 'action' || state.has_played_item ? 'disabled' : ''}>使用</button>
      `;
      card.querySelector('button').addEventListener('click', () => playItem(item.instance_id));
      handList.appendChild(card);
    });
  }

  logList.innerHTML = state.log.map((line) => `<div class="log-item">${line}</div>`).join('');
  syncButtons(state);
}

function syncButtons(state) {
  directionButtons.forEach((button) => {
    button.disabled = !['action', 'movement'].includes(state.phase) || state.pending_die === null;
  });
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
    renderState(await apiRequest('/api/game/play-item', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_instance_id: itemInstanceId }),
    }));
  } catch (error) {
    window.alert(error.message);
  }
}

async function move(direction) {
  try {
    renderState(await apiRequest('/api/game/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ direction }),
    }));
  } catch (error) {
    window.alert(error.message);
  }
}

async function resetRun() {
  await apiRequest('/api/game/reset', { method: 'POST' });
  window.location.href = '/build';
}

resetRunBtn.addEventListener('click', resetRun);
directionButtons.forEach((button) => {
  button.addEventListener('click', () => move(button.dataset.direction));
});
