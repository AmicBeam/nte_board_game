const MODES = [
  {
    id: 'trial',
    name: '套牌试用关',
    description: '选择我方和敌方套路，对战对应人机，验证展开、干扰和王牌终结。',
    scenario: 'trial',
  },
  {
    id: 'random_ai',
    name: '自建构筑随机人机',
    description: '使用已保存的首发与牌库顺序，对战随机 AI 套牌。',
    scenario: 'random_ai',
  },
];

if (ensureLogin()) {
  bootstrapHome();
}

async function bootstrapHome() {
  try {
    const activeState = await apiRequest('/api/game/state?optional=1');
    if (activeState.status === 'playing') {
      window.location.href = '/table';
      return;
    }
  } catch (error) {
    // 没有进行中对局时继续显示主界面。
  }

  const [me, catalog] = await Promise.all([
    apiRequest('/api/me'),
    apiRequest('/api/catalog'),
  ]);
  preloadHomeCharacterAssets(catalog.characters || []);
  const logoutBtn = document.getElementById('logout-btn');
  const startModeBtn = document.getElementById('start-mode-btn');
  const modeGrid = document.getElementById('mode-grid');
  const trialConfigPanel = document.getElementById('trial-config-panel');
  const playerDeckSelect = document.getElementById('player-deck-select');
  const enemyDeckSelect = document.getElementById('enemy-deck-select');
  const buildSummaryCopy = document.getElementById('build-summary-copy');
  const mainDisplayName = document.getElementById('main-display-name');
  const mainDisplayId = document.getElementById('main-display-id');

  let selectedModeId = MODES[0].id;
  const decks = catalog.decks || [];

  function renderProfile() {
    mainDisplayName.textContent = me.nickname;
    mainDisplayId.textContent = `账号：${me.player_uid}`;
  }

  function renderModes() {
    modeGrid.innerHTML = '';
    MODES.forEach((mode) => {
      const card = document.createElement('article');
      card.className = 'build-card';
      if (mode.id === selectedModeId) {
        card.classList.add('selected');
      }
      card.innerHTML = `
        <h2>${mode.name}</h2>
        <p class="card-meta">${mode.description}</p>
      `;
      card.addEventListener('click', () => {
        selectedModeId = mode.id;
        renderModes();
        renderTrialConfig();
      });
      modeGrid.appendChild(card);
    });
  }

  function renderTrialConfig() {
    const trialMode = selectedModeId === 'trial';
    trialConfigPanel.hidden = !trialMode;
    if (!trialMode) {
      return;
    }
    const optionsHtml = decks.map((deck) => `
      <option value="${escapeAttr(deck.id)}">${escapeHtml(deck.name)} · ${escapeHtml(deck.difficulty || '试用')}</option>
    `).join('');
    playerDeckSelect.innerHTML = optionsHtml;
    enemyDeckSelect.innerHTML = optionsHtml;
    const defaultDeckId = catalog.default_deck_id || decks[0]?.id || '';
    if (!playerDeckSelect.value) {
      playerDeckSelect.value = defaultDeckId;
    }
    if (!enemyDeckSelect.value) {
      enemyDeckSelect.value = defaultDeckId;
    }
  }

  function renderBuildSummary() {
    if (decks.length) {
      buildSummaryCopy.textContent = `已开放 ${decks.length} 套试用套牌；每套 20 张异象道具，最多 4 张异能者。`;
      startModeBtn.disabled = false;
      return;
    }
    if (!catalog.saved_build) {
      buildSummaryCopy.textContent = '当前还没有完成牌组，请先进入构筑页选择异能者与异象道具。';
      startModeBtn.disabled = true;
      return;
    }
    const character = catalog.characters.find((item) => item.id === catalog.saved_build.character_id);
    const characterName = character ? character.name : catalog.saved_build.character_id;
    buildSummaryCopy.textContent = `当前领队：${characterName}，已选择 ${catalog.saved_build.item_ids.length} 张卡牌。`;
    startModeBtn.disabled = false;
  }

  async function startMode() {
    const mode = MODES.find((item) => item.id === selectedModeId) || MODES[0];
    const payload = {
      scenario: mode.scenario,
      force_new: true,
    };
    if (mode.id === 'trial') {
      payload.player_deck_id = playerDeckSelect.value || catalog.default_deck_id;
      payload.enemy_deck_id = enemyDeckSelect.value || catalog.default_deck_id;
    }
    await apiRequest('/api/game/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    window.location.href = '/table';
  }

  function logout() {
    clearToken();
    window.location.href = '/login';
  }

  logoutBtn.addEventListener('click', logout);
  startModeBtn.addEventListener('click', startMode);
  renderProfile();
  renderModes();
  renderTrialConfig();
  renderBuildSummary();
  await initTutorialManual('home');
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

function preloadHomeCharacterAssets(characters) {
  characters.forEach((character) => {
    [character.avatar_image, character.portrait_image].forEach((assetUrl) => {
      if (!assetUrl) {
        return;
      }
      const image = new Image();
      image.decoding = 'async';
      image.loading = 'eager';
      image.src = assetUrl;
    });
  });
}
