import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('/Users/bytedance/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

const config = {
  baseUrl: process.env.BASE_URL || 'http://127.0.0.1:5001',
  playerUid: process.env.PLAYER_UID || '10001',
  loginCode: process.env.LOGIN_CODE || '654321',
  width: Number(process.env.WIDTH || 944),
  height: Number(process.env.HEIGHT || 427),
  dpr: Number(process.env.DPR || 3),
  forceCoarse: process.env.FORCE_COARSE !== '0',
  playCard: process.env.PLAY_CARD !== '0',
  forceNewRun: process.env.FORCE_NEW_RUN !== '0',
  scenario: process.env.SCENARIO || 'trial',
  screenshotDir: process.env.SCREENSHOT_DIR || '/private/tmp',
  chromeExecutable: process.env.CHROME_EXECUTABLE || '',
};

const screenshots = {
  table: `${config.screenshotDir}/nte_mobile_duel_table_${config.width}x${config.height}_dpr${config.dpr}.png`,
  tableSelection: `${config.screenshotDir}/nte_mobile_table_selection_${config.width}x${config.height}_dpr${config.dpr}.png`,
  tableTutorial: `${config.screenshotDir}/nte_mobile_table_tutorial_${config.width}x${config.height}_dpr${config.dpr}.png`,
  build: `${config.screenshotDir}/nte_mobile_build_${config.width}x${config.height}_dpr${config.dpr}.png`,
  buildCatalogPreview: `${config.screenshotDir}/nte_mobile_build_catalog_preview_${config.width}x${config.height}_dpr${config.dpr}.png`,
  buildDeckPreview: `${config.screenshotDir}/nte_mobile_build_deck_preview_${config.width}x${config.height}_dpr${config.dpr}.png`,
  buildTutorial: `${config.screenshotDir}/nte_mobile_build_tutorial_${config.width}x${config.height}_dpr${config.dpr}.png`,
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
  if (config.forceNewRun) {
    return api('/api/game/start', {
      method: 'POST',
      body: JSON.stringify({ scenario: config.scenario, force_new: true }),
    }, token);
  }
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

function rectToJson(rect) {
  if (!rect) {
    return null;
  }
  return {
    left: Math.round(rect.left),
    top: Math.round(rect.top),
    right: Math.round(rect.right),
    bottom: Math.round(rect.bottom),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
  };
}

function overlap(a, b) {
  if (!a || !b) {
    return null;
  }
  const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
  const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  return {
    width: Math.round(width),
    height: Math.round(height),
    area: Math.round(width * height),
  };
}

async function loginPage(page, token) {
  await page.goto(`${config.baseUrl}/login`);
  await page.evaluate((value) => window.localStorage.setItem('nte_token', value), token);
}

async function suppressTutorialStatus(page) {
  await page.route('**/api/tutorial/status?**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ completed: true }),
    });
  });
}

async function avoidBuildRedirect(page) {
  await page.route('**/api/game/state?optional=1', (route) => {
    route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'optional verification state suppressed' }),
    });
  });
}

function preferredDeclarationHandCard(state) {
  const hand = Array.isArray(state?.player?.hand) ? state.player.hand : [];
  return hand.find((card) => {
    const description = String(card?.description || '');
    const targetRule = card?.target_rule && typeof card.target_rule === 'object' ? card.target_rule : {};
    return (Array.isArray(card?.declaration_steps) && card.declaration_steps.length > 0)
      || (Array.isArray(card?.declarations) && card.declarations.length > 0)
      || Object.keys(targetRule).length > 0
      || description.includes('宣言')
      || description.includes('检视')
      || description.includes('选择');
  }) || null;
}

function attrSelectorValue(value) {
  return String(value || '').replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

async function maybePlayOneCard(page, state) {
  if (!config.playCard) {
    return null;
  }
  const preferred = preferredDeclarationHandCard(state);
  const preferredInstanceId = String(preferred?.instance_id || '');
  let playable = preferredInstanceId
    ? page.locator(`.hand-rail .hand-card.playable[data-card-instance-id="${attrSelectorValue(preferredInstanceId)}"]`).first()
    : page.locator('.hand-rail .hand-card.playable').first();
  if (!(await playable.count()) && preferredInstanceId) {
    playable = page.locator('.hand-rail .hand-card.playable').first();
  }
  if (!(await playable.count())) {
    return null;
  }
  let selectionResult = null;
  await playable.focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(900);
  const confirm = page.locator('.selection-overlay.open .selection-card').first();
  if (await confirm.count()) {
    const metrics = await collectSelectionMetrics(page);
    const result = selectionPass(metrics);
    await page.screenshot({ path: screenshots.tableSelection, fullPage: false, scale: 'device' });
    selectionResult = { ...result, screenshotPath: screenshots.tableSelection, metrics };
    await confirm.click();
    const primary = page.locator('.selection-overlay.open .selection-actions .primary-btn').first();
    if (await primary.count()) {
      await primary.click();
    }
    await page.waitForTimeout(500);
  }
  const previewClose = page.locator('#card-preview.open [data-card-preview-close]').first();
  if (await previewClose.count()) {
    await previewClose.click({ force: true, timeout: 1000 }).catch(() => {});
  } else {
    await page.keyboard.press('Escape').catch(() => {});
  }
  await page.locator('.duel-page').click({ position: { x: 12, y: 12 }, force: true, timeout: 1000 }).catch(() => {});
  await page.waitForTimeout(200);
  return selectionResult;
}

async function ensureBothBoardCardsForMetrics(page) {
  await page.evaluate(async () => {
    const token = window.localStorage.getItem('nte_token') || '';
    const response = await fetch('/api/game/state', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const state = await response.json();
    const nextState = JSON.parse(JSON.stringify(state));
    const location = nextState.locations?.[0];
    if (!location) {
      return;
    }
    const makeCard = (source, owner, fallback = {}) => {
      const card = JSON.parse(JSON.stringify(source || fallback));
      const power = Number(card.current_power ?? card.power ?? card.base_power ?? fallback.power ?? 2);
      Object.assign(card, {
        instance_id: card.instance_id || `verify-synthetic-${owner}-board-card`,
        definition_id: card.definition_id || `verify-synthetic-${owner}-board-card`,
        name: card.name || (owner === 'opponent' ? '对方验证道具' : '我方验证道具'),
        type: card.type || fallback.type || 'anomaly_item',
        cost: Number(card.cost ?? fallback.cost ?? 1),
        hidden: false,
        revealed: true,
        staged: false,
        location_id: location.id,
        played_turn: nextState.turn,
        play_sequence: owner === 'opponent' ? 0 : 1,
        paid_cost: Number(card.cost ?? fallback.cost ?? 1),
        current_power: power,
        base_power: Number(card.base_power ?? card.power ?? power),
        power,
        category: card.category || fallback.category || '耗材',
        attribute: card.attribute || fallback.attribute || '灵',
        art: card.art || fallback.art || '/static/images/item/畅爽焕能.webp',
      });
      return card;
    };
    const playerCard = makeCard(null, 'player', {
      name: '我方验证道具',
      type: 'anomaly_item',
      cost: 1,
      current_power: 2,
      base_power: 2,
      power: 2,
      category: '耗材',
      attribute: '灵',
      art: '/static/images/item/畅爽焕能.webp',
    });
    const opponentCard = makeCard(null, 'opponent', {
      name: '对方验证道具',
      type: 'anomaly_item',
      cost: 1,
      current_power: 3,
      base_power: 3,
      power: 3,
      category: '耗材',
      attribute: '灵',
      art: '/static/images/item/速食早餐袋.webp',
    });
    nextState.player.hand = Array.isArray(nextState.player?.hand) ? nextState.player.hand : [];
    nextState.player.hand_count = nextState.player.hand.length;
    location.slots = location.slots || {};
    location.slots.player = [playerCard];
    location.slots.opponent = [opponentCard];
    location.power = location.power || {};
    location.power.player = playerCard.current_power;
    location.power.opponent = opponentCard.current_power;
    window.renderState(nextState, {
      optimistic: true,
      skipDeclarationPreviewPrefetch: true,
      skipPendingDeclarationOverlay: true,
    });
    document.querySelectorAll('.dragging, .play-intent-source, .pending-play-card').forEach((element) => {
      element.classList.remove('dragging', 'play-intent-source', 'pending-play-card');
    });
    document.querySelector('#card-preview')?.classList.remove('open');
    document.querySelectorAll('*').forEach((element) => {
      element.getAnimations?.().forEach((animation) => animation.cancel());
    });
  });
  await page.mouse.move(12, 12);
  await page.waitForSelector('.player-slots .board-card', { timeout: 5000 });
  await page.waitForSelector('.opponent-slots .board-card', { timeout: 5000 });
  await page.waitForTimeout(150);
  return true;
}

async function verifySyntheticSelection(page) {
  await page.evaluate(async () => {
    const token = window.localStorage.getItem('nte_token') || '';
    const response = await fetch('/api/game/state', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const state = await response.json();
    const hand = Array.isArray(state?.player?.hand) ? state.player.hand : [];
    const cards = hand.slice(0, 6).map((card, index) => ({
      ...card,
      instance_id: `verify-selection-${index}-${card.instance_id || card.id || index}`,
      selection_source_label: '牌库',
      selection_source_zone: 'deck',
    }));
    // renderSelection is defined by table.js in the page's classic script scope.
    window.renderSelection({
      kind: 'declaration',
      title: '都市活力 检视牌库',
      description: '宣言 1 张饮料或耗材道具；揭示时加入手牌。',
      pick_count: 1,
      cards,
    });
  });
  await page.waitForSelector('.selection-overlay.open .selection-card', { timeout: 5000 });
  await page.waitForTimeout(200);
  const metrics = await collectSelectionMetrics(page);
  const result = selectionPass(metrics);
  await page.screenshot({ path: screenshots.tableSelection, fullPage: false, scale: 'device' });
  await page.keyboard.press('Escape').catch(() => {});
  return { ...result, screenshotPath: screenshots.tableSelection, metrics };
}

async function collectSelectionMetrics(page) {
  return page.evaluate(() => {
    const box = (selector) => {
      const element = document.querySelector(selector);
      if (!element) {
        return null;
      }
      const rect = element.getBoundingClientRect();
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    };
    const cards = Array.from(document.querySelectorAll('.selection-overlay.open .selection-card')).map((element) => {
      const rect = element.getBoundingClientRect();
      const title = element.querySelector('.card-copy h3');
      const titleRect = title?.getBoundingClientRect?.();
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        titleTextLength: String(title?.textContent || '').trim().length,
        title: titleRect ? {
          left: Math.round(titleRect.left),
          top: Math.round(titleRect.top),
          right: Math.round(titleRect.right),
          bottom: Math.round(titleRect.bottom),
          width: Math.round(titleRect.width),
          height: Math.round(titleRect.height),
        } : null,
      };
    });
    return {
      open: Boolean(document.querySelector('.selection-overlay.open')),
      viewport: { width: window.innerWidth, height: window.innerHeight },
      panel: box('.selection-overlay.open .selection-panel'),
      cardCount: cards.length,
      sourceBadgeCount: document.querySelectorAll('.selection-overlay.open .selection-source-badge').length,
      cards,
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    };
  });
}

function selectionPass(metrics) {
  const cardTitlesVisible = metrics.cards.every((card) => (
    card.titleTextLength > 0
    && card.title
    && card.title.height >= 10
    && card.title.bottom <= card.bottom + 1
    && card.title.top >= card.top - 1
  ));
  return {
    pass: Boolean(
      metrics.open
      && metrics.cardCount > 0
      && metrics.sourceBadgeCount === 0
      && cardTitlesVisible
      && !metrics.horizontalOverflow
    ),
    cardTitlesVisible,
    sourceBadgesHidden: metrics.sourceBadgeCount === 0,
  };
}

async function collectTableMetrics(page) {
  return page.evaluate(() => {
    const box = (selector) => {
      const element = document.querySelector(selector);
      if (!element) {
        return null;
      }
      const rect = element.getBoundingClientRect();
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    };
    const allHandCards = Array.from(document.querySelectorAll('.hand-rail .duel-card')).map((element) => {
      const rect = element.getBoundingClientRect();
      const title = element.querySelector('.card-copy h3');
      const titleRect = title?.getBoundingClientRect?.();
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        titleTextLength: String(title?.textContent || '').trim().length,
        title: titleRect ? {
          left: Math.round(titleRect.left),
          top: Math.round(titleRect.top),
          right: Math.round(titleRect.right),
          bottom: Math.round(titleRect.bottom),
          width: Math.round(titleRect.width),
          height: Math.round(titleRect.height),
        } : null,
      };
    });
    const firstPlayerCardElement = document.querySelector('.player-slots .board-card');
    const firstOpponentCardElement = document.querySelector('.opponent-slots .board-card');
    const firstPlayerCardStatBadges = firstPlayerCardElement
      ? Array.from(firstPlayerCardElement.querySelectorAll('.board-card-stats .duel-stat-badge:not(.hidden-stat)')).map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          left: Math.round(rect.left),
          top: Math.round(rect.top),
          right: Math.round(rect.right),
          bottom: Math.round(rect.bottom),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          text: String(element.textContent || '').trim(),
        };
      })
      : [];
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      pointerCoarse: window.matchMedia('(pointer: coarse)').matches,
      hoverNone: window.matchMedia('(hover: none)').matches,
      counts: {
        playerCards: document.querySelectorAll('.player-slots .board-card').length,
        handCards: document.querySelectorAll('.hand-rail .duel-card').length,
        opponentCards: document.querySelectorAll('.opponent-slots .board-card').length,
        visibleContestPowerRows: Array.from(document.querySelectorAll('.location-contest .location-power-row'))
          .filter((element) => getComputedStyle(element).display !== 'none').length,
        visibleContestLeaders: Array.from(document.querySelectorAll('.location-contest .location-leader'))
          .filter((element) => getComputedStyle(element).display !== 'none').length,
        visibleInitiativeRows: Array.from(document.querySelectorAll('.location-contest .location-power-row.initiative-first-row'))
          .filter((element) => getComputedStyle(element).display !== 'none').length,
        visibleMobileScoreRows: Array.from(document.querySelectorAll('.mobile-score-sidecar .mobile-score-row'))
          .filter((element) => getComputedStyle(element).display !== 'none').length,
        visibleMobileScoreLeaders: Array.from(document.querySelectorAll('.mobile-score-sidecar .mobile-score-leader'))
          .filter((element) => getComputedStyle(element).display !== 'none').length,
        visibleMobileInitiativeRows: Array.from(document.querySelectorAll('.mobile-score-sidecar .mobile-score-row.initiative-first-row'))
          .filter((element) => getComputedStyle(element).display !== 'none').length,
      },
      styles: {
        locationContest: (() => {
          const element = document.querySelector('.location-contest');
          if (!element) {
            return null;
          }
          const style = getComputedStyle(element);
          return {
            borderTopWidth: style.borderTopWidth,
            backgroundColor: style.backgroundColor,
            boxShadow: style.boxShadow,
          };
        })(),
        mobileScoreDisplay: (() => {
          const element = document.querySelector('.mobile-score-sidecar');
          if (!element) {
            return '';
          }
          return getComputedStyle(element).display;
        })(),
        mobileScore: (() => {
          const element = document.querySelector('.mobile-score-sidecar');
          if (!element) {
            return null;
          }
          const style = getComputedStyle(element);
          return {
            borderTopWidth: style.borderTopWidth,
            backgroundColor: style.backgroundColor,
            boxShadow: style.boxShadow,
          };
        })(),
        battlefieldOverflowVisible: (() => {
          const selectors = [
            '.duel-board-panel',
            '.locations-board',
            '.duel-location',
            '.location-slots',
            '.opponent-slots',
            '.player-slots',
          ];
          return selectors.every((selector) => {
            const element = document.querySelector(selector);
            return element && getComputedStyle(element).overflow === 'visible';
          });
        })(),
      },
      boxes: {
        opponentRow: box('.opponent-command-row'),
        opponentDiscard: box('#opponent-discard-btn'),
        opponentDeck: box('#opponent-deck-zone'),
        location: box('.duel-location'),
        locationContest: box('.location-contest'),
        opponentSlots: box('.opponent-slots'),
        firstOpponentCard: box('.opponent-slots .board-card'),
        playerSlots: box('.player-slots'),
        firstPlayerCard: box('.player-slots .board-card'),
        firstPlayerCardAttribute: box('.player-slots .board-card .board-card-attribute'),
        firstPlayerCardAttributeIcon: box('.player-slots .board-card .board-card-attribute .board-card-element-icon'),
        firstPlayerCardCategory: box('.player-slots .board-card .board-card-category'),
        ruleLine: box('.mobile-location-rule-line') || box('.location-rule-line'),
        mobileScore: box('.mobile-score-sidecar'),
        mobileScoreOpponent: box('.mobile-score-sidecar .mobile-score-row.opponent'),
        mobileScoreLeader: box('.mobile-score-sidecar .mobile-score-leader'),
        mobileScorePlayer: box('.mobile-score-sidecar .mobile-score-row.player'),
        endTurnButton: box('#end-turn-btn'),
        handDock: box('.hand-dock'),
        handRail: box('.hand-rail'),
        playerDiscard: box('#player-discard-btn'),
        playerDeck: box('#player-deck-zone'),
      },
      allHandCards,
      firstPlayerCardStatBadges,
      locationMidlineY: (() => {
        const rect = document.querySelector('.duel-location')?.getBoundingClientRect();
        return rect ? Math.round(rect.top + (rect.height / 2)) : null;
      })(),
      contestCenterY: (() => {
        const rect = document.querySelector('.location-contest')?.getBoundingClientRect();
        return rect ? Math.round(rect.top + (rect.height / 2)) : null;
      })(),
    };
  });
}

async function collectMidlineWithoutBoardCards(page) {
  return page.evaluate(() => {
    const playerSlots = document.querySelector('.player-slots');
    const opponentSlots = document.querySelector('.opponent-slots');
    const playerHtml = playerSlots?.innerHTML || '';
    const opponentHtml = opponentSlots?.innerHTML || '';
    if (playerSlots) {
      playerSlots.replaceChildren();
    }
    if (opponentSlots) {
      opponentSlots.replaceChildren();
    }
    const locationRect = document.querySelector('.duel-location')?.getBoundingClientRect();
    const contestRect = document.querySelector('.location-contest')?.getBoundingClientRect();
    const result = {
      locationMidlineY: locationRect ? Math.round(locationRect.top + (locationRect.height / 2)) : null,
      contestCenterY: contestRect ? Math.round(contestRect.top + (contestRect.height / 2)) : null,
      opponentSlots: opponentSlots ? {
        top: Math.round(opponentSlots.getBoundingClientRect().top),
        bottom: Math.round(opponentSlots.getBoundingClientRect().bottom),
        height: Math.round(opponentSlots.getBoundingClientRect().height),
      } : null,
      playerSlots: playerSlots ? {
        top: Math.round(playerSlots.getBoundingClientRect().top),
        bottom: Math.round(playerSlots.getBoundingClientRect().bottom),
        height: Math.round(playerSlots.getBoundingClientRect().height),
      } : null,
    };
    if (playerSlots) {
      playerSlots.innerHTML = playerHtml;
    }
    if (opponentSlots) {
      opponentSlots.innerHTML = opponentHtml;
    }
    return result;
  });
}

function deckZoneSizesMatch(metrics) {
  const zones = [
    metrics.boxes.opponentDiscard,
    metrics.boxes.opponentDeck,
    metrics.boxes.playerDiscard,
    metrics.boxes.playerDeck,
  ];
  if (zones.some((zone) => !zone)) {
    return false;
  }
  const widths = zones.map((zone) => zone.width);
  const heights = zones.map((zone) => zone.height);
  return Math.max(...widths) - Math.min(...widths) <= 1
    && Math.max(...heights) - Math.min(...heights) <= 1;
}

function tablePass(metrics, emptyBoardMetrics = null) {
  const centerY = (rect) => (rect ? rect.top + (rect.height / 2) : null);
  const opponentCardVsHand = overlap(metrics.boxes.firstOpponentCard, metrics.boxes.handDock);
  const playerVsHand = overlap(metrics.boxes.playerSlots, metrics.boxes.handDock);
  const playerCardVsHand = overlap(metrics.boxes.firstPlayerCard, metrics.boxes.handDock);
  const playerCardVsAnyHandCard = metrics.allHandCards
    .map((handCard) => overlap(metrics.boxes.firstPlayerCard, handCard))
    .find((item) => item && item.area > 0) || null;
  const ruleLineVsPlayerDiscard = overlap(metrics.boxes.ruleLine, metrics.boxes.playerDiscard);
  const statBadgeOverlap = metrics.firstPlayerCardStatBadges
    .flatMap((badge, index) => metrics.firstPlayerCardStatBadges.slice(index + 1).map((other) => overlap(badge, other)))
    .find((item) => item && item.area > 0) || null;
  const handTitlesVisible = metrics.allHandCards.every((handCard) => (
    handCard.titleTextLength > 0
    && handCard.title
    && handCard.title.height >= 10
    && handCard.title.bottom <= handCard.bottom + 1
    && handCard.title.top >= handCard.top - 1
  ));
  const ruleLineBottomLeft = Boolean(
    metrics.boxes.ruleLine
    && metrics.boxes.ruleLine.left <= 28
    && metrics.boxes.ruleLine.bottom >= metrics.viewport.height - 14
    && (!ruleLineVsPlayerDiscard || ruleLineVsPlayerDiscard.area === 0)
  );
  const handCardsInsideViewportBottom = metrics.allHandCards.every((handCard) => (
    handCard.bottom <= metrics.viewport.height - 5
  ));
  const mobileScoreFramelessBesideEndTurn = Boolean(
    metrics.styles.mobileScoreDisplay !== 'none'
    && metrics.boxes.mobileScore
    && metrics.boxes.mobileScore.width >= 110
    && metrics.boxes.mobileScore.right <= metrics.viewport.width - 88
    && metrics.counts.visibleMobileScoreRows === 2
    && metrics.counts.visibleMobileScoreLeaders === 1
    && metrics.counts.visibleMobileInitiativeRows >= 1
    && metrics.styles.mobileScore?.borderTopWidth === '0px'
    && metrics.styles.mobileScore?.backgroundColor === 'rgba(0, 0, 0, 0)'
    && metrics.styles.mobileScore?.boxShadow === 'none'
  );
  const middleAreaOnlyLine = Boolean(
    metrics.boxes.locationContest
    && metrics.boxes.locationContest.height <= 2
    && metrics.counts.visibleContestPowerRows === 0
    && metrics.counts.visibleContestLeaders === 0
    && metrics.styles.locationContest?.borderTopWidth === '0px'
    && metrics.styles.locationContest?.backgroundColor === 'rgba(0, 0, 0, 0)'
    && metrics.styles.locationContest?.boxShadow === 'none'
  );
  const equalBattlefieldRows = Boolean(
    metrics.boxes.opponentSlots
    && metrics.boxes.playerSlots
    && Math.abs(metrics.boxes.opponentSlots.height - metrics.boxes.playerSlots.height) <= 1
    && metrics.locationMidlineY <= 184
  );
  const boardCardChipsBalanced = Boolean(
    metrics.boxes.firstPlayerCard
    && metrics.boxes.firstPlayerCardAttribute
    && metrics.boxes.firstPlayerCardAttributeIcon
    && metrics.boxes.firstPlayerCardCategory
    && metrics.boxes.firstPlayerCardAttribute.width <= 27
    && metrics.boxes.firstPlayerCardAttributeIcon.width >= 11
    && metrics.boxes.firstPlayerCardAttributeIcon.right <= metrics.boxes.firstPlayerCardAttribute.right
    && metrics.boxes.firstPlayerCardAttributeIcon.left >= metrics.boxes.firstPlayerCardAttribute.left
    && metrics.boxes.firstPlayerCardCategory.width >= 32
    && metrics.boxes.firstPlayerCardCategory.left >= metrics.boxes.firstPlayerCardAttribute.right
    && metrics.boxes.firstPlayerCardCategory.right <= metrics.boxes.firstPlayerCard.right - 2
  );
  const playerCardStatsReadable = Boolean(
    metrics.boxes.firstPlayerCard
    && metrics.boxes.firstPlayerCard.width >= 60
    && metrics.firstPlayerCardStatBadges.length >= 1
    && !statBadgeOverlap
  );
  const playerCardFullyInsideSlots = Boolean(
    metrics.boxes.firstPlayerCard
    && metrics.boxes.playerSlots
    && metrics.boxes.firstPlayerCard.top >= metrics.boxes.playerSlots.top - 1
    && metrics.boxes.firstPlayerCard.bottom <= metrics.boxes.playerSlots.bottom + 1
  );
  const opponentCardFullyInsideSlots = Boolean(
    metrics.boxes.firstOpponentCard
    && metrics.boxes.opponentSlots
    && metrics.boxes.firstOpponentCard.top >= metrics.boxes.opponentSlots.top - 1
    && metrics.boxes.firstOpponentCard.bottom <= metrics.boxes.opponentSlots.bottom + 1
  );
  const cardDistanceToMidlineStable = Boolean(
    metrics.locationMidlineY
    && metrics.boxes.firstOpponentCard
    && metrics.boxes.firstPlayerCard
    && Math.abs(
      (metrics.locationMidlineY - metrics.boxes.firstOpponentCard.bottom)
      - (metrics.boxes.firstPlayerCard.top - metrics.locationMidlineY)
    ) <= 1
  );
  const battlefieldOverflowVisible = metrics.styles.battlefieldOverflowVisible === true;
  const contestCenteredOnFixedMidline = Boolean(
    metrics.locationMidlineY
    && metrics.contestCenterY
    && Math.abs(metrics.locationMidlineY - metrics.contestCenterY) <= 1
  );
  const midlineStableWithoutCards = Boolean(
    emptyBoardMetrics
    && metrics.locationMidlineY
    && emptyBoardMetrics.locationMidlineY
    && Math.abs(metrics.locationMidlineY - emptyBoardMetrics.locationMidlineY) <= 1
    && metrics.contestCenterY
    && emptyBoardMetrics.contestCenterY
    && Math.abs(metrics.contestCenterY - emptyBoardMetrics.contestCenterY) <= 1
  );
  const rightControlsAlignedToMidline = Boolean(
    metrics.locationMidlineY
    && metrics.boxes.mobileScore
    && metrics.boxes.endTurnButton
    && Math.abs(centerY(metrics.boxes.mobileScore) - metrics.locationMidlineY) <= 2
    && Math.abs(centerY(metrics.boxes.endTurnButton) - metrics.locationMidlineY) <= 2
  );
  const mobileScoreThreeLineOrder = Boolean(
    metrics.boxes.mobileScoreOpponent
    && metrics.boxes.mobileScoreLeader
    && metrics.boxes.mobileScorePlayer
    && metrics.boxes.mobileScoreOpponent.bottom <= metrics.boxes.mobileScoreLeader.top + 1
    && metrics.boxes.mobileScoreLeader.bottom <= metrics.boxes.mobileScorePlayer.top + 1
    && metrics.boxes.mobileScoreOpponent.left >= metrics.boxes.mobileScore.left - 1
    && metrics.boxes.mobileScorePlayer.left >= metrics.boxes.mobileScore.left - 1
    && metrics.boxes.mobileScoreLeader.left >= metrics.boxes.mobileScore.left - 1
  );
  return {
    pass: Boolean(
      metrics.pointerCoarse
      && metrics.hoverNone
      && metrics.boxes.playerSlots
      && metrics.boxes.opponentSlots
      && metrics.boxes.handDock
      && metrics.boxes.playerSlots.height >= 72
      && metrics.boxes.opponentSlots.height >= 72
      && metrics.boxes.playerSlots.bottom <= metrics.boxes.handDock.top - 8
      && (!opponentCardVsHand || opponentCardVsHand.area === 0)
      && (!playerVsHand || playerVsHand.area === 0)
      && (!playerCardVsHand || playerCardVsHand.area === 0)
      && (!playerCardVsAnyHandCard || playerCardVsAnyHandCard.area === 0)
      && (!config.playCard || metrics.counts.playerCards > 0)
      && metrics.counts.opponentCards > 0
      && handTitlesVisible
      && mobileScoreFramelessBesideEndTurn
      && middleAreaOnlyLine
      && equalBattlefieldRows
      && boardCardChipsBalanced
      && ruleLineBottomLeft
      && handCardsInsideViewportBottom
      && playerCardStatsReadable
      && playerCardFullyInsideSlots
      && opponentCardFullyInsideSlots
      && cardDistanceToMidlineStable
      && battlefieldOverflowVisible
      && contestCenteredOnFixedMidline
      && midlineStableWithoutCards
      && rightControlsAlignedToMidline
      && mobileScoreThreeLineOrder
      && deckZoneSizesMatch(metrics)
    ),
    overlaps: {
      firstOpponentCardVsHandDock: opponentCardVsHand,
      playerSlotsVsHandDock: playerVsHand,
      firstPlayerCardVsHandDock: playerCardVsHand,
      firstPlayerCardVsAnyHandCard: playerCardVsAnyHandCard,
      ruleLineVsPlayerDiscard,
      firstPlayerCardStatBadgeOverlap: statBadgeOverlap,
    },
    deckZoneSizesMatch: deckZoneSizesMatch(metrics),
    handTitlesVisible,
    ruleLineBottomLeft,
    handCardsInsideViewportBottom,
    mobileScoreFramelessBesideEndTurn,
    middleAreaOnlyLine,
    equalBattlefieldRows,
    boardCardChipsBalanced,
    playerCardStatsReadable,
    playerCardFullyInsideSlots,
    opponentCardFullyInsideSlots,
    cardDistanceToMidlineStable,
    battlefieldOverflowVisible,
    contestCenteredOnFixedMidline,
    midlineStableWithoutCards,
    rightControlsAlignedToMidline,
    mobileScoreThreeLineOrder,
    emptyBoardMetrics,
  };
}

async function verifyTable(page, token, state) {
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await suppressTutorialStatus(page);
  await loginPage(page, token);
  await page.goto(`${config.baseUrl}/table?verify=mobile-table-${Date.now()}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.duel-page .duel-location', { timeout: 10000 });
  await page.waitForTimeout(500);
  if (process.env.REAL_PLAY_CARD === '1') {
    await maybePlayOneCard(page, state);
  }
  await ensureBothBoardCardsForMetrics(page);
  const metrics = await collectTableMetrics(page);
  await page.screenshot({ path: screenshots.table, fullPage: false, scale: 'device' });
  const emptyBoardMetrics = await collectMidlineWithoutBoardCards(page);
  const result = tablePass(metrics, emptyBoardMetrics);
  const selection = await verifySyntheticSelection(page);
  return {
    ...result,
    pass: Boolean(result.pass && selection?.pass),
    screenshotPath: screenshots.table,
    metrics,
    selection,
  };
}

async function collectTutorialMetrics(page) {
  return page.evaluate(() => {
    const modal = document.querySelector('#tutorial-modal.open');
    const dialog = document.querySelector('#tutorial-modal.open .tutorial-dialog');
    const rect = dialog?.getBoundingClientRect();
    return {
      open: Boolean(modal && dialog),
      viewport: { width: window.innerWidth, height: window.innerHeight },
      dialog: rect ? {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      } : null,
      overflowing: rect ? rect.top < 0 || rect.left < 0 || rect.right > window.innerWidth || rect.bottom > window.innerHeight : true,
    };
  });
}

async function verifyTutorial(page, token, path, scope, screenshotPath) {
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await page.route('**/api/tutorial/status?**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ scope, completed: true }),
    });
  });
  if (path === '/build') {
    await avoidBuildRedirect(page);
  }
  await loginPage(page, token);
  await page.goto(`${config.baseUrl}${path}?verify=mobile-tutorial-${Date.now()}`, { waitUntil: 'networkidle' });
  await page.waitForSelector(`[data-tutorial-open="${scope}"]`, { timeout: 10000 });
  await page.locator(`[data-tutorial-open="${scope}"]`).first().click({ force: true });
  await page.waitForSelector('#tutorial-modal.open .tutorial-dialog', { timeout: 10000 });
  await page.waitForTimeout(300);
  const metrics = await collectTutorialMetrics(page);
  await page.screenshot({ path: screenshotPath, fullPage: false, scale: 'device' });
  return {
    pass: Boolean(metrics.open && !metrics.overflowing),
    screenshotPath,
    metrics,
  };
}

async function collectBuildMetrics(page) {
  return page.evaluate(() => {
    const box = (selector) => {
      const element = document.querySelector(selector);
      return rectToJson(element?.getBoundingClientRect?.());
    };
    function rectToJson(rect) {
      if (!rect) {
        return null;
      }
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    }
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      path: window.location.pathname,
      pointerCoarse: window.matchMedia('(pointer: coarse)').matches,
      boxes: {
        page: box('.build-page'),
        command: box('.build-command'),
        workbench: box('.build-workbench'),
        catalog: box('.build-catalog-panel'),
        deck: box('.build-deck-panel'),
        firstCatalogCard: box('.build-card-grid .build-card'),
        firstDeckCard: box('.build-deck-panel .deck-card'),
      },
      counts: {
        catalogCards: document.querySelectorAll('.build-card-grid .build-card').length,
        deckCards: document.querySelectorAll('.build-deck-panel .deck-card').length,
      },
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      verticalScrollable: document.documentElement.scrollHeight > window.innerHeight + 1,
    };
  });
}

async function longPressBuildCard(page, selector) {
  const card = page.locator(selector).first();
  await card.scrollIntoViewIfNeeded();
  const box = await card.boundingBox();
  if (!box) {
    throw new Error(`Cannot locate card for long press: ${selector}`);
  }
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(560);
  await page.mouse.up();
  await page.waitForSelector('#build-card-preview.open .build-preview-effect', { timeout: 5000 });
  await page.waitForTimeout(200);
}

async function collectBuildPreviewMetrics(page) {
  return page.evaluate(() => {
    const box = (selector) => {
      const element = document.querySelector(selector);
      return rectToJson(element?.getBoundingClientRect?.());
    };
    function rectToJson(rect) {
      if (!rect) {
        return null;
      }
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        right: Math.round(rect.right),
        bottom: Math.round(rect.bottom),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    }
    const preview = document.querySelector('#build-card-preview.open');
    const effect = document.querySelector('#build-card-preview.open .build-preview-effect p');
    const previewBox = box('#build-card-preview.open');
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      classes: preview ? Array.from(preview.classList) : [],
      boxes: {
        preview: previewBox,
        card: box('#build-card-preview.open .preview-catalog-card'),
        art: box('#build-card-preview.open .item-art'),
        effect: box('#build-card-preview.open .build-preview-effect'),
      },
      effectTextLength: String(effect?.textContent || '').trim().length,
      effectText: String(effect?.textContent || '').trim().slice(0, 80),
      horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    };
  });
}

function buildPreviewPass(metrics, { expectSide = '' } = {}) {
  const leftDocked = Boolean(
    metrics.boxes.preview
    && metrics.boxes.preview.left >= -1
    && metrics.boxes.preview.right <= Math.ceil(metrics.viewport.width * 0.45)
  );
  const rightDocked = Boolean(
    metrics.boxes.preview
    && metrics.boxes.preview.left >= Math.floor(metrics.viewport.width * 0.55)
    && metrics.boxes.preview.right <= metrics.viewport.width + 1
  );
  return {
    pass: Boolean(
      metrics.effectTextLength > 0
      && metrics.boxes.effect
      && metrics.boxes.effect.height >= 34
      && (expectSide !== 'left' || leftDocked)
      && (expectSide !== 'right' || rightDocked)
      && !metrics.horizontalOverflow
    ),
    leftDocked,
    rightDocked,
  };
}

async function verifyBuild(page, token) {
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await suppressTutorialStatus(page);
  await avoidBuildRedirect(page);
  await loginPage(page, token);
  await page.goto(`${config.baseUrl}/build?verify=mobile-build-${Date.now()}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.build-page .build-card-grid .build-card', { timeout: 10000 });
  await page.waitForTimeout(500);
  const metrics = await collectBuildMetrics(page);
  await page.screenshot({ path: screenshots.build, fullPage: false, scale: 'device' });
  await longPressBuildCard(page, '.build-card-grid .catalog-card.type-anomaly_item');
  const catalogPreviewMetrics = await collectBuildPreviewMetrics(page);
  const catalogPreviewResult = buildPreviewPass(catalogPreviewMetrics, { expectSide: 'right' });
  await page.screenshot({ path: screenshots.buildCatalogPreview, fullPage: false, scale: 'device' });
  await page.locator('#build-card-preview.open').click({ position: { x: 8, y: 8 }, force: true }).catch(() => {});
  await page.waitForTimeout(200);
  await longPressBuildCard(page, '.build-deck-panel .deck-card');
  const deckPreviewMetrics = await collectBuildPreviewMetrics(page);
  const deckPreviewResult = buildPreviewPass(deckPreviewMetrics, { expectSide: 'left' });
  await page.screenshot({ path: screenshots.buildDeckPreview, fullPage: false, scale: 'device' });
  await page.locator('#build-card-preview.open [data-build-preview-close]').click({ force: true }).catch(() => {});
  return {
    pass: Boolean(
      metrics.path === '/build'
      && metrics.pointerCoarse
      && metrics.counts.catalogCards > 0
      && metrics.boxes.command
      && metrics.boxes.workbench
      && !metrics.horizontalOverflow
      && catalogPreviewResult.pass
      && deckPreviewResult.pass
    ),
    screenshotPath: screenshots.build,
    metrics,
    previews: {
      catalog: { ...catalogPreviewResult, screenshotPath: screenshots.buildCatalogPreview, metrics: catalogPreviewMetrics },
      deck: { ...deckPreviewResult, screenshotPath: screenshots.buildDeckPreview, metrics: deckPreviewMetrics },
    },
  };
}

async function main() {
  const login = await api('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ player_uid: config.playerUid, code: config.loginCode }),
  });
  const token = login.token;
  const state = await ensureRunState(token);

  const launchOptions = {
    headless: true,
  };
  if (config.chromeExecutable) {
    launchOptions.executablePath = config.chromeExecutable;
  }
  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext({
    viewport: { width: config.width, height: config.height },
    deviceScaleFactor: config.dpr,
    isMobile: true,
    hasTouch: true,
  });
  await installCoarsePointerShim(context);
  const page = await context.newPage();

  const results = {
    table: await verifyTable(page, token, state),
    tableTutorial: await verifyTutorial(page, token, '/table', 'table', screenshots.tableTutorial),
    build: await verifyBuild(page, token),
    buildTutorial: await verifyTutorial(page, token, '/build', 'build', screenshots.buildTutorial),
  };

  await browser.close();

  const pass = Object.values(results).every((result) => result.pass);
  console.log(JSON.stringify({
    pass,
    config,
    game: { turn: state.turn, phase: state.phase },
    screenshots,
    results,
  }, null, 2));
  if (!pass) {
    process.exit(2);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
