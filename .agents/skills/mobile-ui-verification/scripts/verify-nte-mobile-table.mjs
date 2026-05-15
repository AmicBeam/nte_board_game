import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('/Users/bytedance/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const config = {
  baseUrl: process.env.BASE_URL || 'http://127.0.0.1:5001',
  playerUid: process.env.PLAYER_UID || '10001',
  loginCode: process.env.LOGIN_CODE || '654321',
  width: Number(process.env.WIDTH || 1024),
  height: Number(process.env.HEIGHT || 461),
  dpr: Number(process.env.DPR || 2),
  mapZoom: process.env.MAP_ZOOM || 'max',
  forceCoarse: process.env.FORCE_COARSE !== '0',
  screenshotPath: process.env.SCREENSHOT_PATH || '/private/tmp/nte_mobile_table_verify.png',
  chromeExecutable: process.env.CHROME_EXECUTABLE || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
};

async function api(path, options = {}, token = '') {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${config.baseUrl}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || `${response.status} ${response.statusText}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

async function ensureRunState(token) {
  let state = await api('/api/game/state', {}, token).catch((error) => {
    if (error.status === 404) {
      return null;
    }
    throw error;
  });
  if (!state) {
    const catalog = await api('/api/catalog', {}, token);
    if (!catalog.saved_build) {
      const character = (catalog.characters || []).find((item) => item.id === 'xiaozhi' || item.name === '小吱')
        || (catalog.characters || [])[0];
      const itemIds = (catalog.items || [])
        .filter((item) => !item.hidden_from_build)
        .slice(0, catalog.build_size || 8)
        .map((item) => item.id);
      await api('/api/build/save', {
        method: 'POST',
        body: JSON.stringify({ character_id: character.id, item_ids: itemIds }),
      }, token);
    }
    state = await api('/api/game/start', { method: 'POST', body: '{}' }, token);
  }
  if (state.phase === 'dice') {
    state = await api('/api/game/roll', { method: 'POST', body: '{}' }, token);
  }
  return state;
}

async function installCoarsePointerShim(context) {
  if (!config.forceCoarse) {
    return;
  }
  await context.addInitScript(() => {
    const realMatchMedia = window.matchMedia.bind(window);
    window.matchMedia = (query) => {
      const text = String(query);
      if (text.includes('pointer: coarse') || text.includes('hover: none')) {
        return {
          matches: true,
          media: text,
          onchange: null,
          addListener() {},
          removeListener() {},
          addEventListener() {},
          removeEventListener() {},
          dispatchEvent() { return false; },
        };
      }
      return realMatchMedia(query);
    };
  });
}

function choosePreviewTarget(state) {
  const layer = Number(state.player.layer || state.map?.current_layer || 1);
  const layerInfo = (state.map.layers || []).find((item) => Number(item.layer || 1) === layer)
    || state.board
    || state.map;
  const width = Number(layerInfo.width || 1);
  const height = Number(layerInfo.height || 1);
  const dice = state.pending_dice || {};
  const maxSteps = Math.max(Number(dice.a || dice.vertical || 1), Number(dice.b || dice.horizontal || 1), 1);
  const playerX = Number(state.player.x);
  const playerY = Number(state.player.y);
  const steps = Math.max(1, Math.min(4, maxSteps, playerY));
  return {
    width,
    height,
    target: { x: playerX, y: playerY - steps },
  };
}

async function collectMetrics(page) {
  return page.evaluate(() => {
    const box = (selector) => {
      const element = document.querySelector(selector);
      if (!element) {
        return null;
      }
      const rect = element.getBoundingClientRect();
      return {
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        left: Math.round(rect.left),
        top: Math.round(rect.top),
      };
    };
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      pointerCoarse: window.matchMedia('(pointer: coarse)').matches,
      hoverNone: window.matchMedia('(hover: none)').matches,
      mapZoom: getComputedStyle(document.querySelector('.map-stage-inner')).getPropertyValue('--map-zoom').trim(),
      player: box('.token-player'),
      playerChip: box('.player-chip'),
      previewDots: Array.from(document.querySelectorAll('.preview-dot')).map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          text: element.textContent,
        };
      }).slice(0, 8),
      previewLine: box('.preview-line'),
    };
  });
}

async function main() {
  const login = await api('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ player_uid: config.playerUid, code: config.loginCode }),
  });
  const token = login.token;
  await ensureRunState(token);

  const browser = await chromium.launch({
    headless: true,
    executablePath: config.chromeExecutable,
  });
  const context = await browser.newContext({
    viewport: { width: config.width, height: config.height },
    deviceScaleFactor: config.dpr,
    isMobile: true,
    hasTouch: true,
  });
  await installCoarsePointerShim(context);

  const page = await context.newPage();
  await page.goto(`${config.baseUrl}/login`);
  await page.evaluate((value) => window.localStorage.setItem('nte_token', value), token);
  await page.goto(`${config.baseUrl}/table?verify=mobile-${Date.now()}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#map-stage .token-player', { timeout: 10000 });

  if (config.mapZoom) {
    await page.evaluate((value) => {
      const slider = document.querySelector('#map-zoom-slider');
      if (!slider) {
        return;
      }
      slider.value = value === 'max' ? slider.max : value;
      slider.dispatchEvent(new Event('input', { bubbles: true }));
    }, config.mapZoom);
  }
  await page.waitForTimeout(300);

  const state = await api('/api/game/state', {}, token);
  const { width, height, target } = choosePreviewTarget(state);
  const rect = await page.locator('.map-stage-inner').boundingBox();
  await page.touchscreen.tap(
    rect.x + ((target.x + 0.5) / width) * rect.width,
    rect.y + ((target.y + 0.5) / height) * rect.height,
  );
  await page.waitForTimeout(400);

  const metrics = await collectMetrics(page);
  await page.screenshot({ path: config.screenshotPath, fullPage: false });
  await browser.close();

  console.log(JSON.stringify({
    screenshotPath: config.screenshotPath,
    config,
    metrics,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
