const codexGrid = document.getElementById('codex-grid');
const codexMapSummary = document.getElementById('codex-map-summary');
const codexTabs = Array.from(document.querySelectorAll('[data-codex-tab]'));

const CODEX_TYPE_LABELS = {
  attack: '攻击',
  currency: '货币',
  defense: '防御',
  dice: '骰子',
  intel: '侦察',
  key: '钥匙',
  loot: '鉴别物',
  mobility: '移动',
  recovery: '恢复',
  utility: '功能',
};

let codexData = null;
let activeCodexTab = 'objects';

if (ensureLogin()) {
  loadCodex();
}

async function loadCodex() {
  try {
    codexData = await apiRequest('/api/encyclopedia');
    const map = codexData.map || {};
    codexMapSummary.textContent = `${map.name || '地图'} · 共 ${map.total_layers || 1} 层`;
    renderCodex();
  } catch (error) {
    codexGrid.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

function renderCodex() {
  if (!codexData) {
    return;
  }
  codexTabs.forEach((button) => {
    button.classList.toggle('active', button.dataset.codexTab === activeCodexTab);
  });
  const entries = resolveCodexEntries();
  if (!entries.length) {
    codexGrid.innerHTML = '<div class="empty-state">暂无资料</div>';
    return;
  }
  codexGrid.innerHTML = entries.map((entry) => `
    <article class="codex-card ${entry.rarity ? `rarity-${classToken(entry.rarity)}` : ''}">
      ${badgesMarkup(entry.badges)}
      <div class="codex-icon" aria-hidden="true">${iconMarkup(entry.icon)}</div>
      <div class="codex-copy">
        <span class="codex-type">${entry.tag || ''}</span>
        <h2>${entry.name}</h2>
        <p>${entry.description || ''}</p>
      </div>
    </article>
  `).join('');
}

function resolveCodexEntries() {
  if (activeCodexTab === 'objects') {
    return (codexData.map_objects || []).map((entry) => ({
      name: entry.name,
      icon: entry.icon,
      tag: entry.block_type || '地图物件',
      badges: entry.tags || [],
      description: entry.description,
    }));
  }
  if (activeCodexTab === 'items') {
    return (codexData.items || []).map((entry) => ({
      name: entry.name,
      icon: entry.icon,
      tag: CODEX_TYPE_LABELS[entry.type] || '道具',
      badges: entry.tags || [],
      rarity: entry.rarity,
      description: entry.description,
    }));
  }
  if (activeCodexTab === 'loot') {
    return (codexData.loot_items || []).map((entry) => ({
      name: entry.name,
      icon: entry.icon,
      tag: CODEX_TYPE_LABELS[entry.type] || '道具',
      badges: entry.tags || [],
      rarity: entry.rarity,
      description: entry.description,
    }));
  }
  return (codexData.enemies || []).map((entry) => ({
    name: entry.name,
    icon: entry.icon,
    tag: entry.kind === 'boss' ? 'Boss' : '敌人',
    badges: [],
    description: entry.description,
  }));
}

function badgesMarkup(badges) {
  const visibleBadges = (badges || []).filter(Boolean);
  if (!visibleBadges.length) {
    return '';
  }
  return `<div class="codex-badges">${visibleBadges.map((badge) => `<span>${badge}</span>`).join('')}</div>`;
}

function iconMarkup(icon) {
  const value = String(icon || 'event');
  if (isImageIcon(value)) {
    return `<img src="${value}" alt="">`;
  }
  return `<span class="map-icon icon-${classToken(value)}"></span>`;
}

function isImageIcon(value) {
  return /\.(png|jpg|jpeg|webp|gif|svg)$/i.test(value) || String(value).startsWith('/static/');
}

function classToken(value) {
  return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
}

codexTabs.forEach((button) => {
  button.addEventListener('click', () => {
    activeCodexTab = button.dataset.codexTab;
    renderCodex();
  });
});
