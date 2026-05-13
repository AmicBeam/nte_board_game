const MODES = [
  {
    id: 'solo_explore',
    name: '单人探索',
    description: '单人地图探索模式，支持构筑、掷骰移动与持久化恢复。',
  },
];

if (ensureLogin()) {
  bootstrapHome();
}

async function bootstrapHome() {
  try {
    const activeState = await apiRequest('/api/game/state');
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
  const buildSummaryCopy = document.getElementById('build-summary-copy');
  const mainDisplayName = document.getElementById('main-display-name');
  const mainDisplayId = document.getElementById('main-display-id');

  let selectedModeId = MODES[0].id;

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
      });
      modeGrid.appendChild(card);
    });
  }

  function renderBuildSummary() {
    if (!catalog.saved_build) {
      buildSummaryCopy.textContent = '当前还没有完成构筑，请先进入构筑页选择角色和道具。';
      startModeBtn.disabled = true;
      return;
    }
    const character = catalog.characters.find((item) => item.id === catalog.saved_build.character_id);
    const characterName = character ? character.name : catalog.saved_build.character_id;
    buildSummaryCopy.textContent = `当前构筑角色：${characterName}，已选择 ${catalog.saved_build.item_ids.length} 个道具。`;
    startModeBtn.disabled = false;
  }

  async function startMode() {
    await apiRequest('/api/game/start', { method: 'POST' });
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
  renderBuildSummary();
  await initTutorialManual('home');
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
