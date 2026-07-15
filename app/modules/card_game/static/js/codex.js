const codexGrid = document.getElementById('codex-grid');
const codexMapSummary = document.getElementById('codex-map-summary');

let codexData = null;

if (ensureLogin()) {
  loadCodex();
}

async function loadCodex() {
  try {
    codexData = await apiRequest('/api/encyclopedia');
    const game = codexData.game || {};
    codexMapSummary.textContent = game.description || '三空间异象对决资料。';
    renderCodex();
  } catch (error) {
    codexGrid.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

function renderCodex() {
  if (!codexData) {
    return;
  }
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
  return (codexData.locations || []).map((entry) => ({
    name: entry.name,
    icon: entry.art,
    tag: `第 ${entry.reveal_turn} 回合`,
    badges: ['异象空间'],
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
