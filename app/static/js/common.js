function getToken() {
  return window.localStorage.getItem('nte_token') || '';
}

function setToken(token) {
  window.localStorage.setItem('nte_token', token);
}

function clearToken() {
  window.localStorage.removeItem('nte_token');
}

function nextLogId() {
  const previous = Number(window.localStorage.getItem('nte_log_id_counter') || '0');
  const next = previous + 1;
  window.localStorage.setItem('nte_log_id_counter', String(next));
  return `web-${String(next).padStart(6, '0')}`;
}

async function apiRequest(url, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  headers['X-Log-Id'] = nextLogId();
  const response = await fetch(url, Object.assign({}, options, { headers }));
  const payload = await response.json();
  if (!response.ok || payload.error) {
    const logId = response.headers.get('X-Log-Id') || headers['X-Log-Id'];
    throw new Error(`${payload.error || '请求失败'}（logId: ${logId}）`);
  }
  return payload;
}

function ensureLogin() {
  if (!getToken()) {
    window.location.href = '/login';
    return false;
  }
  return true;
}

const TUTORIAL_DEFINITIONS = {
  home: {
    title: '主界面手册',
    eyebrow: '主界面',
    pages: [
      {
        title: '试试开启一把单人模式吧！',
        body: [
          '在主界面确认当前构筑后，点击“开始对局”即可进入单人探索。',
          '如果还没有构筑，请先进入构筑页选择角色和道具。',
        ],
      },
      {
        title: '项目与反馈',
        body: [
          '反馈群：575377480',
          'GitHub：https://github.com/AmicBeam/nte_board_game',
        ],
        links: [
          { label: '打开 GitHub', href: 'https://github.com/AmicBeam/nte_board_game' },
        ],
      },
    ],
  },
  build: {
    title: '构筑页手册',
    eyebrow: '构筑',
    pages: [
      {
        title: '先选择角色',
        body: [
          '欢迎游玩，本项目还没有正式的名字，可以帮忙起一个。',
          '请在左侧角色轮盘滑动或点击，操作调整角色，先选择角色小吱吧。',
        ],
        image: { src: '/static/images/characters/portrait/小吱.png', alt: '小吱角色立绘' },
      },
      {
        title: '携带道具',
        body: [
          '右侧战术道具卡片可以点击装配或取下。',
          '每套构筑至多携带 6 个道具，角色专属道具会自动携带。',
        ],
      },
    ],
  },
};

let tutorialModalState = null;

function nteEscapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[char]));
}

function nteEscapeAttr(value) {
  return nteEscapeHtml(value).replace(/`/g, '&#96;');
}

function nteIsImageIcon(value) {
  return /\.(png|jpg|jpeg|webp|gif|svg)$/i.test(String(value || '')) || String(value || '').startsWith('/static/');
}

function nteClassToken(value) {
  return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
}

function nteTutorialIconMarkup(icon, fallback = 'event') {
  const value = String(icon || fallback);
  if (nteIsImageIcon(value)) {
    return `<img class="tutorial-sample-img" src="${nteEscapeAttr(value)}" alt="">`;
  }
  return `<span class="map-icon icon-${nteClassToken(value)}"></span>`;
}

function nteTutorialPageHtml(page) {
  const body = (page.body || [])
    .map((line) => `<p>${nteEscapeHtml(line)}</p>`)
    .join('');
  const links = (page.links || [])
    .map((link) => `<a class="secondary-btn tutorial-link" href="${nteEscapeAttr(link.href)}" target="_blank" rel="noopener noreferrer">${nteEscapeHtml(link.label)}</a>`)
    .join('');
  const image = page.image?.src
    ? `<figure class="tutorial-figure"><img src="${nteEscapeAttr(page.image.src)}" alt="${nteEscapeAttr(page.image.alt || '')}"></figure>`
    : '';
  const samples = (page.samples || [])
    .map((sample) => `
      <article class="tutorial-sample-card">
        <span class="tutorial-sample-icon">${nteTutorialIconMarkup(sample.icon, sample.fallback)}</span>
        <span>
          <strong>${nteEscapeHtml(sample.name || '目标')}</strong>
          ${sample.description ? `<small>${nteEscapeHtml(sample.description)}</small>` : ''}
        </span>
      </article>
    `)
    .join('');
  return `
    <div class="tutorial-copy">
      ${image}
      <h3>${nteEscapeHtml(page.title || '')}</h3>
      ${body}
      ${links ? `<div class="tutorial-links">${links}</div>` : ''}
      ${samples ? `<div class="tutorial-samples">${samples}</div>` : ''}
    </div>
  `;
}

function ensureTutorialModal() {
  let modal = document.getElementById('tutorial-modal');
  if (modal) {
    return modal;
  }
  modal = document.createElement('div');
  modal.id = 'tutorial-modal';
  modal.className = 'tutorial-modal';
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <div class="tutorial-dialog" role="dialog" aria-modal="true" aria-labelledby="tutorial-title">
      <div class="tutorial-header">
        <div>
          <p class="eyebrow" id="tutorial-eyebrow">手册</p>
          <h2 id="tutorial-title">教学手册</h2>
        </div>
        <p class="tutorial-progress" id="tutorial-progress">1 / 1</p>
      </div>
      <div class="tutorial-body" id="tutorial-body"></div>
      <div class="tutorial-footer">
        <button class="secondary-btn" id="tutorial-prev-btn" type="button">上一页</button>
        <button class="primary-btn" id="tutorial-next-btn" type="button">下一页</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  modal.querySelector('#tutorial-prev-btn').addEventListener('click', () => {
    if (!tutorialModalState || tutorialModalState.pageIndex <= 0) {
      return;
    }
    tutorialModalState.pageIndex -= 1;
    renderTutorialModal();
  });
  modal.querySelector('#tutorial-next-btn').addEventListener('click', finishOrAdvanceTutorial);
  return modal;
}

function renderTutorialModal() {
  const modal = ensureTutorialModal();
  const state = tutorialModalState;
  if (!state) {
    return;
  }
  const page = state.pages[state.pageIndex] || {};
  const lastPageIndex = Math.max(0, state.pages.length - 1);
  modal.querySelector('#tutorial-eyebrow').textContent = state.eyebrow;
  modal.querySelector('#tutorial-title').textContent = state.title;
  modal.querySelector('#tutorial-progress').textContent = `${state.pageIndex + 1} / ${state.pages.length}`;
  modal.querySelector('#tutorial-body').innerHTML = nteTutorialPageHtml(page);
  const prevBtn = modal.querySelector('#tutorial-prev-btn');
  const nextBtn = modal.querySelector('#tutorial-next-btn');
  prevBtn.disabled = state.pageIndex === 0;
  nextBtn.disabled = Boolean(state.finishing);
  nextBtn.textContent = state.pageIndex >= lastPageIndex ? '我知道了' : '下一页';
}

function openTutorialManual(scope, options = {}) {
  const definition = TUTORIAL_DEFINITIONS[scope] || {};
  const pages = typeof options.pages === 'function'
    ? options.pages()
    : (options.pages || definition.pages || []);
  tutorialModalState = {
    scope,
    title: options.title || definition.title || '教学手册',
    eyebrow: options.eyebrow || definition.eyebrow || '手册',
    pages: pages.length ? pages : [{ title: '教学手册', body: ['暂无手册内容。'] }],
    pageIndex: 0,
    finishing: false,
  };
  const modal = ensureTutorialModal();
  renderTutorialModal();
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
}

async function finishOrAdvanceTutorial() {
  if (!tutorialModalState) {
    return;
  }
  const lastPageIndex = Math.max(0, tutorialModalState.pages.length - 1);
  if (tutorialModalState.pageIndex < lastPageIndex) {
    tutorialModalState.pageIndex += 1;
    renderTutorialModal();
    return;
  }
  tutorialModalState.finishing = true;
  renderTutorialModal();
  try {
    await apiRequest('/api/tutorial/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope: tutorialModalState.scope }),
    });
  } catch (error) {
    console.warn(error);
  } finally {
    const modal = ensureTutorialModal();
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    tutorialModalState = null;
  }
}

async function initTutorialManual(scope, options = {}) {
  const openBtn = document.querySelector(`[data-tutorial-open="${scope}"]`);
  if (openBtn && openBtn.dataset.tutorialBound !== 'true') {
    openBtn.dataset.tutorialBound = 'true';
    openBtn.addEventListener('click', () => openTutorialManual(scope, options));
  }
  if (options.autoOpen === false) {
    return;
  }
  try {
    const status = await apiRequest(`/api/tutorial/status?scope=${encodeURIComponent(scope)}`);
    if (!status.completed) {
      openTutorialManual(scope, options);
    }
  } catch (error) {
    console.warn(error);
  }
}
