if (ensureLogin()) {
  bootstrap();
}

const ITEM_TYPE_LABELS = {
  esper: '异能者',
  anomaly_item: '异象道具',
  token: '临时牌',
};

const ELEMENT_ICON_BASE = '/static/images/elements';
const CARD_TYPE_SORT_ORDER = ['esper', 'anomaly_item', 'token'];
const ATTRIBUTE_SORT_ORDER = ['灵', '光', '相', '咒', '暗', '魂'];
const MAX_ITEM_COPIES = 3;

async function bootstrap() {
  const activeStatePromise = apiRequest('/api/game/state?optional=1').catch(() => null);
  const catalogPromise = apiRequest('/api/catalog').then(
    (data) => ({ data }),
    (error) => ({ error }),
  );
  const activeState = await activeStatePromise;
  if (activeState?.status === 'playing') {
    window.location.href = '/table';
    return;
  }
  const catalogResult = await catalogPromise;
  if (catalogResult.error) {
    throw catalogResult.error;
  }

  const data = catalogResult.data;
  const prebuiltDecks = Array.isArray(data.decks) ? data.decks : [];
  const buildSize = Number(data.build_size || 20);
  const savedItemIds = data.saved_build
    ? (data.saved_build.item_ids || [
        ...(data.saved_build.starter_item_ids || []),
        ...(data.saved_build.reserve_item_ids || []),
      ])
    : [];
  const selected = {
    itemIds: [],
    starterIds: [],
    reserveIds: savedItemIds.slice(0, buildSize),
    buildSize,
    minBuildSize: Number(data.min_build_size || 10),
    starterSize: 0,
    maxEsperCards: data.max_esper_cards || 4,
    filter: 'all',
    costFilter: 'all',
    powerFilter: 'all',
    materialFilter: 'all',
    categoryFilter: 'all',
    search: '',
    isSaving: false,
    items: data.items || [],
    characters: data.characters || [],
    esperIds: data.saved_build ? (data.saved_build.esper_card_ids || []).slice(0, data.max_esper_cards || 4) : [],
  };
  const itemById = new Map(selected.items.map((item) => [item.id, item]));
  document.__nteBuildItemById = itemById;
  selected.starterIds = knownIds(selected.starterIds)
    .filter((itemId) => itemById.has(itemId))
    .slice(0, selected.starterSize);
  selected.reserveIds = knownIds(selected.reserveIds)
    .filter((itemId) => itemById.has(itemId))
    .slice(0, selected.buildSize);
  selected.esperIds = uniqueIds(selected.esperIds)
    .filter((itemId) => itemById.get(itemId)?.type === 'esper')
    .slice(0, selected.maxEsperCards);
  sortSelectedZones();
  syncItemIds();
  const catalogGrid = document.getElementById('catalog-grid');
  const starterList = document.getElementById('starter-list');
  const reserveList = document.getElementById('reserve-list');
  const esperList = document.getElementById('esper-list');
  const deckDropZone = document.getElementById('deck-drop-zone');
  const catalogDropZone = document.getElementById('catalog-drop-zone');
  const filterTabs = document.getElementById('build-filter-tabs');
  const typeFilter = document.getElementById('type-filter');
  const costFilter = document.getElementById('cost-filter');
  const powerFilter = document.getElementById('power-filter');
  const materialFilter = document.getElementById('material-filter');
  const categoryFilter = document.getElementById('category-filter');
  const catalogSearch = document.getElementById('catalog-search');
  const deckCount = document.getElementById('deck-count');
  const starterCount = document.getElementById('starter-count');
  const reserveCount = document.getElementById('reserve-count');
  const esperCountLabel = document.getElementById('esper-count');
  const clearBuildBtn = document.getElementById('clear-build-btn');
  const saveBuildBtn = document.getElementById('save-build-btn');
  const prebuiltPreviewBtn = document.getElementById('prebuilt-preview-btn');
  const prebuiltPreviewLayer = document.getElementById('prebuilt-preview-layer');
  const prebuiltPreviewClose = document.getElementById('prebuilt-preview-close');
  const prebuiltPreviewTabs = document.getElementById('prebuilt-preview-tabs');
  const prebuiltPreviewSummary = document.getElementById('prebuilt-preview-summary');
  const prebuiltPreviewBody = document.getElementById('prebuilt-preview-body');
  const buildToast = document.getElementById('build-toast');
  const buildCardPreview = document.getElementById('build-card-preview');
  const buildDragGhost = document.getElementById('build-drag-ghost');
  let activePrebuiltDeckId = String(data.default_deck_id || prebuiltDecks[0]?.id || '');
  let currentDragPayload = null;
  let pointerDrag = null;
  let suppressNextClick = false;
  let buildPreviewPinned = false;
  let buildPreviewPressTimer = null;
  let buildPreviewIgnoreUntil = 0;

  function syncItemIds() {
    selected.itemIds = [...selected.starterIds, ...selected.reserveIds];
  }

  function sortSelectedZones() {
    selected.starterIds.sort(compareCardIds);
    selected.reserveIds.sort(compareCardIds);
    selected.esperIds.sort(compareCardIds);
  }

  function zoneIds(zone) {
    if (zone === 'esper') {
      return selected.esperIds;
    }
    return zone === 'starter' ? selected.starterIds : selected.reserveIds;
  }

  function zoneLimit(zone) {
    if (zone === 'esper') {
      return selected.maxEsperCards;
    }
    return zone === 'starter' ? 0 : selected.buildSize;
  }

  function autoZone() {
    return 'reserve';
  }

  function selectedCounts() {
    const counts = new Map();
    [...selected.itemIds, ...selected.esperIds].forEach((itemId) => {
      counts.set(itemId, Number(counts.get(itemId) || 0) + 1);
    });
    return counts;
  }

  function itemCopyCount(itemId) {
    return selected.itemIds.filter((currentId) => currentId === itemId).length;
  }

  function esperCount() {
    return selected.esperIds.length;
  }

  function visibleCatalogItems() {
    return selected.items.filter((item) => {
      if (item.hidden_from_build) {
        return false;
      }
      if (selected.filter !== 'all' && item.type !== selected.filter) {
        return false;
      }
      if (selected.search) {
        const keyword = selected.search.trim().toLowerCase();
        const haystack = [
          item.name,
          item.description,
          item.attribute,
          item.category,
          ...(item.display_tags || []),
          item.required_material_attribute,
          itemTypeLabel(item.type),
        ].filter(Boolean).join(' ').toLowerCase();
        if (!haystack.includes(keyword)) {
          return false;
        }
      }
      if (selected.costFilter !== 'all') {
        const cost = Number(item.cost || 0);
        if (selected.costFilter === '6') {
          if (cost < 6) {
            return false;
          }
        } else if (cost !== Number(selected.costFilter)) {
          return false;
        }
      }
      if (selected.powerFilter !== 'all' && !powerMatchesFilter(Number(item.power || 0), selected.powerFilter)) {
        return false;
      }
      if (selected.materialFilter !== 'all' && item.type === 'anomaly_item' && item.attribute !== selected.materialFilter) {
        return false;
      }
      if (selected.materialFilter !== 'all' && item.type !== 'anomaly_item') {
        return false;
      }
      if (selected.categoryFilter !== 'all' && item.type === 'anomaly_item' && item.category !== selected.categoryFilter) {
        return false;
      }
      if (selected.categoryFilter !== 'all' && item.type !== 'anomaly_item') {
        return false;
      }
      return true;
    }).sort(compareCards);
  }

  function canAddCard(item, zone = '') {
    if (!item) {
      return { ok: false, reason: '未知卡牌。' };
    }
    if (item.type === 'esper') {
      if (selected.esperIds.includes(item.id)) {
        return { ok: false, reason: '这名异能者已经在编队中。' };
      }
      if (zone && zone !== 'esper') {
        return { ok: false, reason: '异能者只能加入待命区。' };
      }
      if (selected.esperIds.length >= selected.maxEsperCards) {
        return { ok: false, reason: `异能者最多选择 ${selected.maxEsperCards} 张。` };
      }
      return { ok: true, reason: '' };
    }
    if (zone === 'esper') {
      return { ok: false, reason: '异象道具不能加入异能者待命区。' };
    }
    if (item.deck_buildable === false) {
      return { ok: false, reason: '这张牌带有不可构筑标签。' };
    }
    if (itemCopyCount(item.id) >= MAX_ITEM_COPIES) {
      return { ok: false, reason: `同名异象道具最多携带 ${MAX_ITEM_COPIES} 张。` };
    }
    if (selected.itemIds.length >= selected.buildSize) {
      return { ok: false, reason: `异象道具区最多放入 ${selected.buildSize} 张。` };
    }
    return { ok: true, reason: '' };
  }

  function addCard(itemId, zone = autoZone(), insertIndex = null) {
    if (typeof zone === 'number') {
      insertIndex = zone;
      zone = autoZone();
    }
    const item = itemById.get(itemId);
    const targetZone = item?.type === 'esper' ? 'esper' : 'reserve';
    const allowed = canAddCard(item, targetZone);
    if (!allowed.ok) {
      showBuildToast(allowed.reason);
      return false;
    }
    const ids = zoneIds(targetZone);
    if (ids.length >= zoneLimit(targetZone)) {
      showBuildToast(targetZone === 'esper' ? '异能者待命区已满。' : '主牌组已满。');
      return false;
    }
    ids.push(itemId);
    sortSelectedZones();
    syncItemIds();
    renderAll();
    showBuildToast(`${item.name} 已加入${targetZone === 'esper' ? '异能者待命区' : '主牌组'}`);
    return true;
  }

  function removeCard(itemId, zone = '', index = null) {
    const preferredIds = zone ? zoneIds(zone) : null;
    const preferredIndex = preferredIds && Number.isFinite(Number(index)) ? Number(index) : -1;
    const ids = preferredIds && preferredIds[preferredIndex] === itemId
      ? preferredIds
      : selected.starterIds.includes(itemId)
        ? selected.starterIds
        : selected.reserveIds.includes(itemId)
          ? selected.reserveIds
          : selected.esperIds;
    const resolvedIndex = ids === preferredIds && preferredIndex >= 0 ? preferredIndex : ids.indexOf(itemId);
    if (resolvedIndex < 0) {
      return false;
    }
    const [removedId] = ids.splice(resolvedIndex, 1);
    syncItemIds();
    renderAll();
    showBuildToast(`${itemById.get(removedId)?.name || '卡牌'} 已移出构筑集`);
    return true;
  }

  function moveDeckCard(itemId, zone, insertIndex, sourceZoneHint = '', sourceIndexHint = null) {
    const hintedIds = sourceZoneHint ? zoneIds(sourceZoneHint) : null;
    const hintedIndex = hintedIds && Number.isFinite(Number(sourceIndexHint)) ? Number(sourceIndexHint) : -1;
    const sourceZone = hintedIds?.[hintedIndex] === itemId
      ? sourceZoneHint
      : selected.starterIds.includes(itemId) ? 'starter' : selected.reserveIds.includes(itemId) ? 'reserve' : selected.esperIds.includes(itemId) ? 'esper' : '';
    if (!sourceZone) {
      return false;
    }
    const item = itemById.get(itemId);
    const targetZone = zone === 'esper' ? 'esper' : 'reserve';
    const allowed = item?.type === 'esper'
      ? (targetZone === 'esper' ? { ok: true } : { ok: false, reason: '异能者只能放在待命区。' })
      : (targetZone === 'esper' ? { ok: false, reason: '异象道具不能加入待命区。' } : { ok: true });
    if (!allowed.ok) {
      showBuildToast(allowed.reason);
      return false;
    }
    const sourceIds = zoneIds(sourceZone);
    const targetIds = zoneIds(targetZone);
    const currentIndex = hintedIds === sourceIds && hintedIndex >= 0 ? hintedIndex : sourceIds.indexOf(itemId);
    if (sourceZone !== targetZone && targetIds.length >= zoneLimit(targetZone)) {
      showBuildToast(targetZone === 'esper' ? '异能者待命区已满。' : '主牌组已满。');
      return false;
    }
    const [movingId] = sourceIds.splice(currentIndex, 1);
    targetIds.push(movingId);
    sortSelectedZones();
    syncItemIds();
    renderAll();
    return true;
  }

  function renderCatalog() {
    const scrollTop = catalogGrid.scrollTop;
    const picked = selectedCounts();
    const fragment = document.createDocumentFragment();
    visibleCatalogItems().forEach((item) => {
      const selectedCount = Number(picked.get(item.id) || 0);
      const isSelected = selectedCount > 0;
      const addState = canAddCard(item);
      const card = document.createElement('article');
      card.className = `build-card catalog-card item-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}${isSelected ? ' selected' : ''}${!isSelected && !addState.ok ? ' unavailable' : ''}`;
      card.dataset.cardId = item.id;
      card.draggable = false;
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      card.setAttribute('aria-label', `${item.name}，${itemTypeLabel(item.type)}`);
      card.innerHTML = cardMarkup(item, {
        mark: isSelected ? `已加入 x${selectedCount}` : '',
        compact: false,
      });
      card.addEventListener('click', (event) => {
        if (consumeSuppressedClick(event)) {
          return;
        }
        addCard(item.id);
      });
      card.addEventListener('pointerdown', (event) => beginPointerCardDrag(event, 'catalog', item.id, card));
      card.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') {
          return;
        }
        event.preventDefault();
        addCard(item.id);
      });
      card.addEventListener('dragstart', (event) => startCardDrag(event, 'catalog', item.id));
      card.addEventListener('dragend', finishCardDrag);
      bindCardReadPreview(card, item, { touchSide: 'right' });
      fragment.appendChild(card);
    });
    catalogGrid.replaceChildren(fragment);
    catalogGrid.scrollTop = scrollTop;
  }

  function renderDeck() {
    renderDeckZone(esperList, 'esper', selected.esperIds, selected.maxEsperCards);
    if (starterList) {
      renderDeckZone(starterList, 'starter', selected.starterIds, selected.starterSize);
    }
    renderDeckZone(reserveList, 'reserve', selected.reserveIds, selected.buildSize);
  }

  function renderDeckZone(container, zone, itemIds, size) {
    const fragment = document.createDocumentFragment();
    for (let index = 0; index < size; index += 1) {
      const itemId = itemIds[index];
      const item = itemById.get(itemId);
      const slot = document.createElement('div');
      slot.className = `deck-slot${item ? ' filled' : ' empty'}`;
      slot.dataset.zone = zone;
      slot.dataset.slotIndex = String(index);
      slot.addEventListener('dragover', allowDrop);
      slot.addEventListener('dragenter', markDropSlot);
      slot.addEventListener('dragleave', unmarkDropSlot);
      slot.addEventListener('drop', (event) => handleDeckDrop(event, zone, index));
      if (!item) {
        slot.innerHTML = `<span>${zone === 'esper' ? '待命空位' : '牌组空位'}</span>`;
        fragment.appendChild(slot);
        continue;
      }

      const card = document.createElement('article');
      card.className = `deck-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}`;
      card.dataset.cardId = item.id;
      card.draggable = false;
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      card.setAttribute('aria-label', `移除 ${item.name}`);
      card.innerHTML = cardMarkup(item, { compact: true });
      card.addEventListener('click', (event) => {
        if (consumeSuppressedClick(event)) {
          return;
        }
        removeCard(item.id, zone, index);
      });
      card.addEventListener('pointerdown', (event) => beginPointerCardDrag(event, 'deck', item.id, card, { zone, index }));
      card.addEventListener('keydown', (event) => {
        if (event.key !== 'Backspace' && event.key !== 'Delete' && event.key !== 'Enter' && event.key !== ' ') {
          return;
        }
        event.preventDefault();
        removeCard(item.id, zone, index);
      });
      card.addEventListener('dragstart', (event) => startCardDrag(event, 'deck', item.id, { zone, index }));
      card.addEventListener('dragend', finishCardDrag);
      bindCardReadPreview(card, item, { touchSide: 'left' });
      slot.appendChild(card);
      fragment.appendChild(slot);
    }
    container.replaceChildren(fragment);
  }

  function activePrebuiltDeck() {
    return prebuiltDecks.find((deck) => String(deck.id || '') === activePrebuiltDeckId) || prebuiltDecks[0] || null;
  }

  function openPrebuiltPreview() {
    if (!prebuiltDecks.length) {
      showBuildToast('当前没有可预览的预组');
      return;
    }
    hideBuildCardPreview({ force: true });
    renderPrebuiltPreview();
    prebuiltPreviewLayer.classList.add('open');
    prebuiltPreviewLayer.setAttribute('aria-hidden', 'false');
    prebuiltPreviewBtn?.setAttribute('aria-expanded', 'true');
  }

  function closePrebuiltPreview() {
    hideBuildCardPreview({ force: true });
    prebuiltPreviewLayer.classList.remove('open');
    prebuiltPreviewLayer.setAttribute('aria-hidden', 'true');
    prebuiltPreviewBtn?.setAttribute('aria-expanded', 'false');
  }

  function renderPrebuiltPreview() {
    const deck = activePrebuiltDeck();
    if (!deck) {
      prebuiltPreviewTabs.replaceChildren();
      prebuiltPreviewSummary.textContent = '暂无预组。';
      prebuiltPreviewBody.replaceChildren();
      return;
    }
    renderPrebuiltTabs(deck);
    renderPrebuiltSummary(deck);
    renderPrebuiltBody(deck);
  }

  function renderPrebuiltTabs(activeDeck) {
    const fragment = document.createDocumentFragment();
    prebuiltDecks.forEach((deck) => {
      const active = String(deck.id || '') === String(activeDeck.id || '');
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.deckId = String(deck.id || '');
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', active ? 'true' : 'false');
      button.className = active ? 'active' : '';
      button.textContent = deck.short_name || deck.name || '预组';
      fragment.appendChild(button);
    });
    prebuiltPreviewTabs.replaceChildren(fragment);
  }

  function renderPrebuiltSummary(deck) {
    const itemIds = prebuiltItemIds(deck);
    const esperIds = prebuiltEsperIds(deck);
    const difficulty = deck.difficulty ? `<span>${escapeHtml(deck.difficulty)}</span>` : '';
    prebuiltPreviewSummary.innerHTML = `
      <div>
        <strong>${escapeHtml(deck.name || '未命名预组')}</strong>
        ${difficulty}
      </div>
      <p>${escapeHtml(deck.description || '只读预组，可在这里查看完整构成。')}</p>
      <dl>
        <div><dt>异能者</dt><dd>${esperIds.length}</dd></div>
        <div><dt>主牌组</dt><dd>${itemIds.length}</dd></div>
        <div><dt>不同卡名</dt><dd>${deckCardGroups(itemIds).length}</dd></div>
      </dl>
    `;
  }

  function renderPrebuiltBody(deck) {
    const esperIds = prebuiltEsperIds(deck);
    const itemIds = prebuiltItemIds(deck);
    prebuiltPreviewBody.innerHTML = `
      <section class="prebuilt-preview-zone">
        <div class="deck-zone-title">
          <h3>异能者待命区</h3>
          <span>${esperIds.length}</span>
        </div>
        <div class="prebuilt-card-list">
          ${prebuiltCardRows(esperIds, { groupCopies: false })}
        </div>
      </section>
      <section class="prebuilt-preview-zone">
        <div class="deck-zone-title">
          <h3>主牌组</h3>
          <span>${itemIds.length}</span>
        </div>
        <div class="prebuilt-card-list">
          ${prebuiltCardRows(itemIds, { groupCopies: true })}
        </div>
      </section>
    `;
    bindPrebuiltCardPreviews();
  }

  function prebuiltEsperIds(deck) {
    return knownIds(deck?.esper_card_ids || [])
      .filter((itemId) => itemById.get(itemId)?.type === 'esper')
      .sort(compareCardIds);
  }

  function prebuiltItemIds(deck) {
    return knownIds(deck?.card_ids || [])
      .filter((itemId) => itemById.get(itemId)?.type === 'anomaly_item')
      .sort(compareCardIds);
  }

  function deckCardGroups(itemIds) {
    const groups = [];
    const byId = new Map();
    itemIds.forEach((itemId) => {
      if (byId.has(itemId)) {
        byId.get(itemId).count += 1;
        return;
      }
      const group = { itemId, count: 1 };
      byId.set(itemId, group);
      groups.push(group);
    });
    return groups;
  }

  function prebuiltCardRows(itemIds, options = {}) {
    const groups = options.groupCopies ? deckCardGroups(itemIds) : itemIds.map((itemId) => ({ itemId, count: 1 }));
    if (!groups.length) {
      return '<div class="empty-state">暂无卡牌</div>';
    }
    return groups.map((group) => {
      const item = itemById.get(group.itemId);
      if (!item) {
        return '';
      }
      const countBadge = group.count > 1 ? `<span class="prebuilt-card-count">×${group.count}</span>` : '';
      return `
        <article class="deck-card prebuilt-deck-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}" tabindex="0" data-prebuilt-card-id="${escapeAttr(item.id)}" aria-label="${escapeAttr(item.name)}，只读预组卡牌">
          ${cardMarkup(item, { compact: true })}
          ${countBadge}
        </article>
      `;
    }).join('');
  }

  function bindPrebuiltCardPreviews() {
    prebuiltPreviewBody.querySelectorAll('[data-prebuilt-card-id]').forEach((cardNode) => {
      const item = itemById.get(cardNode.dataset.prebuiltCardId || '');
      if (item) {
        bindCardReadPreview(cardNode, item);
      }
    });
  }

  function renderStatus() {
    const count = selected.itemIds.length;
    const missingMin = Math.max(0, selected.minBuildSize - count);
    const remainingMax = Math.max(0, selected.buildSize - count);
    const esperTotal = esperCount();
    if (starterCount) {
      starterCount.textContent = `${selected.starterIds.length} / ${selected.starterSize}`;
    }
    reserveCount.textContent = `${selected.reserveIds.length} / ${selected.buildSize}`;
    esperCountLabel.textContent = `${esperTotal} / ${selected.maxEsperCards}`;
    deckCount.textContent = missingMin
      ? `异象道具 ${count} / ${selected.minBuildSize}-${selected.buildSize} · 异能者 ${esperTotal} / ${selected.maxEsperCards} · 至少还需 ${missingMin} 张`
      : `异象道具 ${count} / ${selected.minBuildSize}-${selected.buildSize} · 异能者 ${esperTotal} / ${selected.maxEsperCards} · 还可加入 ${remainingMax} 张`;
    clearBuildBtn.disabled = selected.isSaving || (selected.itemIds.length === 0 && selected.esperIds.length === 0);
    saveBuildBtn.disabled = selected.isSaving || selected.itemIds.length < selected.minBuildSize || selected.itemIds.length > selected.buildSize || selected.esperIds.length === 0;
    saveBuildBtn.title = selected.itemIds.length < selected.minBuildSize
      ? `至少选择 ${selected.minBuildSize} 张异象道具`
      : selected.esperIds.length === 0
        ? '至少选择 1 名异能者'
        : '保存构筑';
  }

  function renderFilters() {
    filterTabs?.querySelectorAll('button[data-filter]').forEach((button) => {
      const active = button.dataset.filter === selected.filter;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    if (typeFilter) {
      typeFilter.value = selected.filter;
    }
    costFilter.value = selected.costFilter;
    powerFilter.value = selected.powerFilter;
    materialFilter.value = selected.materialFilter;
    renderCategoryFilterOptions();
    categoryFilter.value = selected.categoryFilter;
    catalogSearch.value = selected.search;
  }

  function renderCategoryFilterOptions() {
    const categories = [...new Set(selected.items
      .filter((item) => item.type === 'anomaly_item' && item.category)
      .map((item) => String(item.category))
    )].sort((first, second) => first.localeCompare(second, 'zh-Hans-CN'));
    const current = selected.categoryFilter;
    categoryFilter.innerHTML = '<option value="all">全部</option>';
    categories.forEach((category) => {
      const option = document.createElement('option');
      option.value = category;
      option.textContent = category;
      categoryFilter.appendChild(option);
    });
    if (current !== 'all' && !categories.includes(current)) {
      selected.categoryFilter = 'all';
    }
  }

  function renderAll() {
    renderFilters();
    renderCatalog();
    renderDeck();
    renderStatus();
  }

  function consumeSuppressedClick(event) {
    if (!suppressNextClick) {
      return false;
    }
    event.preventDefault();
    event.stopPropagation();
    suppressNextClick = false;
    return true;
  }

  function cardMarkup(item, { mark = '', compact = false, preview = false } = {}) {
    const description = preview
      ? previewEffectMarkup(item)
      : `<p class="card-meta ${descriptionDensityClass(item.description)}">${descriptionWithAttributeIcon(item)}</p>`;
    const metaMarkup = itemMetaMarkup(item);
    const typeTag = compact ? '' : `
      <div class="build-card-type-row">
        <span class="card-tag">${itemTypeLabel(item.type)}</span>
        ${metaMarkup ? `<div class="build-card-subline">${metaMarkup}</div>` : ''}
      </div>
    `;
    const inlineStats = compact ? `<span class="deck-inline-stats" aria-hidden="true">${buildStatBadges(item)}</span>` : '';
    const statOverlay = compact ? '' : `<div class="build-stat-overlay">${buildStatBadges(item)}</div>`;
    const materialLine = !compact && item.type === 'esper'
      ? `<div class="build-material-line"><span>素材</span><strong>${escapeHtml(materialRequirementText(item))}</strong></div>`
      : '';
    const compactMeta = compact
      ? `<span class="deck-row-meta">${escapeHtml(item.type === 'esper' ? materialRequirementText(item) : item.category || itemTypeLabel(item.type))}</span>`
      : '';
    const statAriaLabel = item.type === 'esper'
      ? `素材需求 ${materialRequirementText(item)}，战力 ${item.power}`
      : `费用 ${item.cost}，战力 ${item.power}`;
    return `
      <div class="item-art${compact ? ' small' : ''}" aria-hidden="true">
        ${iconMarkup(item.icon || item.art)}
        ${statOverlay}
      </div>
      <div class="card-headline">
        ${typeTag}
        <h2>${inlineStats}<span class="deck-card-name">${escapeHtml(item.name)}</span>${compactMeta}</h2>
      </div>
      <div class="sr-only">${escapeHtml(statAriaLabel)}</div>
      ${materialLine}
      ${description}
      ${mark && !compact ? `<span class="selection-mark">${escapeHtml(mark)}</span>` : ''}
    `;
  }

  function buildStatBadges(item) {
    const stats = item.type === 'esper'
      ? [
        { kind: 'material', value: esperMaterialCost(item), attribute: item.attribute || '', title: materialRequirementText(item) },
        { kind: 'power', value: item.power ?? '?' },
      ]
      : [
        { kind: 'cost', value: item.cost ?? '?' },
        { kind: 'power', value: item.power ?? '?' },
      ];
    return stats.map((stat) => `
      <span class="build-stat-badge build-stat-${stat.kind}">
        ${buildStatIcon(stat.kind, stat.attribute)}
        <strong>${escapeHtml(stat.value)}</strong>
      </span>
    `).join('');
  }

  function buildStatIcon(kind, attribute = '') {
    if (kind === 'material') {
      if (attribute && !isWildcardMaterialAttribute(attribute)) {
        return `<img class="build-stat-element-icon" src="${escapeAttr(`${ELEMENT_ICON_BASE}/${attribute}.png`)}" alt="">`;
      }
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.6 21.2 12 12 21.4 2.8 12 12 2.6Zm0 4.2L6.9 12l5.1 5.2 5.1-5.2L12 6.8Z"></path></svg>';
    }
    if (kind === 'cost') {
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.6 1.9 5.2 13h6.1l-1.5 10.1 8.9-12.4h-6.2l1.1-8.8Z"></path></svg>';
    }
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3.5 13.4 13l-2.2 2.2L8.7 12.7 6.5 15 4 12.5 6.3 10 3.6 7.3 4 3.5Zm16 0 .4 3.8-2.7 2.7 2.3 2.5-2.5 2.5-2.2-2.3-8.6 8.6H3.8v-2.9l8.6-8.6L20 3.5Z"></path></svg>';
  }

  function attributeIconMarkup(item, className = 'element-icon') {
    const attribute = String(item?.attribute || '').trim();
    if (!attribute) {
      return '';
    }
    const icon = item.attribute_icon || `${ELEMENT_ICON_BASE}/${attribute}.png`;
    return `<img class="${className}" src="${escapeAttr(icon)}" alt="${escapeAttr(attribute)}" loading="lazy">`;
  }

  function descriptionWithAttributeIcon(item) {
    return `<span>${escapeHtml(item.description || '')}</span>`;
  }

  function previewEffectMarkup(item) {
    const description = String(item.description || '').trim() || '无具体效果。';
    return `
      <section class="build-preview-effect ${descriptionDensityClass(description)}" aria-label="卡牌效果">
        <h3>效果</h3>
        <p>${escapeHtml(description)}</p>
      </section>
    `;
  }

  function itemMetaMarkup(item) {
    if (item.type !== 'anomaly_item' && item.type !== 'token') {
      return '';
    }
    const chips = [];
    if (item.attribute) {
      chips.push(`<span class="build-meta-chip attribute-chip">${attributeIconMarkup(item, 'element-icon')}<b>${escapeHtml(item.attribute)}属性</b></span>`);
    }
    if (item.category) {
      chips.push(`<span class="build-meta-chip">${escapeHtml(item.category)}</span>`);
    }
    (item.display_tags || []).forEach((label) => {
      chips.push(`<span class="build-meta-chip special-chip">${escapeHtml(label)}</span>`);
    });
    return chips.join('');
  }

  function itemMetaText(item) {
    if (item.type !== 'anomaly_item' && item.type !== 'token') {
      return '';
    }
    return [item.attribute ? `${item.attribute}属性` : '', item.category || ''].filter(Boolean).join(' · ');
  }

  function descriptionDensityClass(description = '') {
    const length = String(description || '').length;
    if (length >= 96) {
      return 'desc-dense';
    }
    if (length >= 68) {
      return 'desc-long';
    }
    return '';
  }

  function materialRequirements(item) {
    return Array.isArray(item?.material_requirements) ? item.material_requirements.filter((requirement) => requirement && typeof requirement === 'object') : [];
  }

  function esperMaterialCost(item) {
    const requirements = materialRequirements(item);
    if (requirements.length) {
      return requirements.reduce((total, requirement) => total + Number(requirement.count || 1), 0);
    }
    const cost = Number(item?.material_cost || 2);
    return Math.max(1, Math.min(3, Number.isFinite(cost) ? cost : 2));
  }

  function materialRequirementText(item) {
    if (item?.material_requirement_text) {
      return String(item.material_requirement_text);
    }
    const requirements = materialRequirements(item);
    if (requirements.length) {
      return requirements.map((requirement) => {
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
      }).join('+');
    }
    const attribute = String(item?.required_material_attribute || '').trim();
    const visibleAttribute = isWildcardMaterialAttribute(attribute) ? '' : attribute;
    return `${esperMaterialCost(item)} ${visibleAttribute ? `${visibleAttribute}素材` : '素材'}`;
  }

  function isWildcardMaterialAttribute(attribute) {
    return !attribute || attribute === '任意' || attribute === '指定';
  }

  function startCardDrag(event, source, itemId, meta = {}) {
    const sourceNode = event.currentTarget;
    currentDragPayload = { source, itemId, ...meta };
    event.dataTransfer.effectAllowed = source === 'deck' ? 'move' : 'copy';
    event.dataTransfer.setData('application/x-nte-card', JSON.stringify({ source, itemId, ...meta }));
    event.dataTransfer.setData('text/plain', itemId);
    sourceNode.classList.add('dragging');
    window.requestAnimationFrame(() => sourceNode.classList.remove('dragging'));
  }

  function beginPointerCardDrag(event, source, itemId, sourceNode, meta = {}) {
    if (typeof event.button === 'number' && event.button !== 0) {
      return;
    }
    if (event.pointerType === 'touch') {
      return;
    }
    event.preventDefault();
    pointerDrag = {
      source,
      itemId,
      sourceNode,
      ...meta,
      startX: event.clientX,
      startY: event.clientY,
      active: false,
    };
    document.addEventListener('pointermove', movePointerCardDrag);
    document.addEventListener('pointerup', endPointerCardDrag, { once: true });
    document.addEventListener('pointercancel', cancelPointerCardDrag, { once: true });
  }

  function movePointerCardDrag(event) {
    if (!pointerDrag) {
      return;
    }
    const distance = Math.hypot(event.clientX - pointerDrag.startX, event.clientY - pointerDrag.startY);
    if (!pointerDrag.active && distance < 8) {
      return;
    }
    clearBuildPreviewPressTimer();
    pointerDrag.active = true;
    pointerDrag.sourceNode.classList.add('dragging');
    document.body.classList.add('build-card-dragging');
    updateBuildDragGhost(event.clientX, event.clientY);
    highlightPointerDrop(event.clientX, event.clientY);
  }

  function endPointerCardDrag(event) {
    if (!pointerDrag) {
      return;
    }
    clearBuildPreviewPressTimer();
    if (pointerDrag.active) {
      suppressNextClick = true;
      const targetElement = document.elementFromPoint(event.clientX, event.clientY);
      const targetSlot = targetElement?.closest?.('.deck-slot');
      const targetZone = targetElement?.closest?.('.deck-zone');
      const targetDeck = targetElement?.closest?.('#deck-drop-zone');
      const targetCatalog = targetElement?.closest?.('#catalog-drop-zone');
      if (pointerDrag.source === 'catalog' && (targetSlot || targetDeck)) {
        const item = itemById.get(pointerDrag.itemId);
        const zone = targetSlot?.dataset.zone || targetZone?.dataset.zone || (item?.type === 'esper' ? 'esper' : autoZone());
        addCard(pointerDrag.itemId, zone, targetSlot ? Number(targetSlot.dataset.slotIndex) : null);
      } else if (pointerDrag.source === 'deck' && targetDeck) {
        const zone = targetSlot?.dataset.zone || targetZone?.dataset.zone || 'reserve';
        moveDeckCard(pointerDrag.itemId, zone, targetSlot ? Number(targetSlot.dataset.slotIndex) : null, pointerDrag.zone, pointerDrag.index);
      } else if (pointerDrag.source === 'deck' && targetCatalog) {
        removeCard(pointerDrag.itemId, pointerDrag.zone, pointerDrag.index);
      }
      window.setTimeout(() => {
        suppressNextClick = false;
      }, 0);
    }
    cleanupPointerCardDrag();
  }

  function cancelPointerCardDrag() {
    clearBuildPreviewPressTimer();
    cleanupPointerCardDrag();
  }

  function cleanupPointerCardDrag() {
    if (pointerDrag?.sourceNode) {
      pointerDrag.sourceNode.classList.remove('dragging');
    }
    pointerDrag = null;
    document.body.classList.remove('build-card-dragging');
    hideBuildDragGhost();
    document.removeEventListener('pointermove', movePointerCardDrag);
    document.removeEventListener('pointerup', endPointerCardDrag);
    document.removeEventListener('pointercancel', cancelPointerCardDrag);
    clearPointerDropHighlights();
  }

  function updateBuildDragGhost(x, y) {
    if (!buildDragGhost || !pointerDrag) {
      return;
    }
    const item = itemById.get(pointerDrag.itemId);
    if (!item) {
      return;
    }
    if (!buildDragGhost.classList.contains('open')) {
      buildDragGhost.innerHTML = `
        <article class="deck-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}">
          ${cardMarkup(item, { mark: '', compact: true })}
        </article>
      `;
      buildDragGhost.classList.add('open');
      buildDragGhost.setAttribute('aria-hidden', 'false');
    }
    buildDragGhost.style.transform = `translate(${x + 14}px, ${y + 14}px)`;
  }

  function hideBuildDragGhost() {
    if (!buildDragGhost) {
      return;
    }
    buildDragGhost.classList.remove('open');
    buildDragGhost.setAttribute('aria-hidden', 'true');
    buildDragGhost.replaceChildren();
    buildDragGhost.style.transform = 'translate(-9999px, -9999px)';
  }

  function highlightPointerDrop(x, y) {
    clearPointerDropHighlights();
    const element = document.elementFromPoint(x, y);
    const slot = element?.closest?.('.deck-slot');
    const deck = element?.closest?.('#deck-drop-zone');
    const catalog = element?.closest?.('#catalog-drop-zone');
    if (slot) {
      slot.classList.add('drop-target');
    }
    if (deck && pointerDrag?.source === 'catalog') {
      deckDropZone.classList.add('drop-target');
    }
    if (catalog && pointerDrag?.source === 'deck') {
      catalogDropZone.classList.add('drop-target');
    }
  }

  function clearPointerDropHighlights() {
    deckDropZone.classList.remove('drop-target');
    catalogDropZone.classList.remove('drop-target');
    document.querySelectorAll('.deck-slot.drop-target').forEach((slot) => slot.classList.remove('drop-target'));
  }

  function finishCardDrag() {
    currentDragPayload = null;
  }

  function readCardDrag(event) {
    const raw = event.dataTransfer.getData('application/x-nte-card');
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch (error) {
        return null;
      }
    }
    const text = event.dataTransfer.getData('text/plain');
    return text ? { source: 'catalog', itemId: text } : currentDragPayload;
  }

  function allowDrop(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }

  function markDropSlot(event) {
    event.currentTarget.classList.add('drop-target');
  }

  function unmarkDropSlot(event) {
    event.currentTarget.classList.remove('drop-target');
  }

  function handleDeckDrop(event, zone = 'reserve', insertIndex = null) {
    event.preventDefault();
    const targetZone = event.target.closest?.('.deck-zone')?.dataset.zone;
    const payload = readCardDrag(event);
    const item = itemById.get(payload?.itemId || '');
    const resolvedZone = zone === 'reserve' || zone === 'esper'
      ? zone
      : targetZone || (item?.type === 'esper' ? 'esper' : 'reserve');
    deckDropZone.classList.remove('drop-target');
    document.querySelectorAll('.deck-slot.drop-target').forEach((slot) => slot.classList.remove('drop-target'));
    if (!payload?.itemId) {
      return;
    }
    if (payload.source === 'deck') {
      moveDeckCard(payload.itemId, resolvedZone, insertIndex, payload.zone, payload.index);
      finishCardDrag();
      return;
    }
    addCard(payload.itemId, resolvedZone, insertIndex);
    finishCardDrag();
  }

  function handleCatalogDrop(event) {
    event.preventDefault();
    catalogDropZone.classList.remove('drop-target');
    const payload = readCardDrag(event);
    if (payload?.source === 'deck' && payload.itemId) {
      removeCard(payload.itemId, payload.zone, payload.index);
    }
    finishCardDrag();
  }

  async function saveBuild() {
    if (selected.itemIds.length < selected.minBuildSize || selected.itemIds.length > selected.buildSize) {
      showBuildToast(`请选择 ${selected.minBuildSize} 到 ${selected.buildSize} 张异象道具。`);
      return;
    }
    if (!selected.esperIds.length) {
      showBuildToast('请至少选择 1 名异能者。');
      return;
    }
    const leaderId = selected.esperIds[0]
      || selected.characters[0]?.id
      || selected.items[0]?.id
      || '';
    selected.isSaving = true;
    renderStatus();
    try {
      await apiRequest('/api/build/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_id: leaderId,
          esper_card_ids: selected.esperIds,
          item_ids: selected.itemIds,
        }),
      });
      window.location.href = '/card-game';
    } catch (error) {
      showBuildToast(error.message);
    } finally {
      selected.isSaving = false;
      renderStatus();
    }
  }

  function showBuildToast(message) {
    buildToast.textContent = message;
    buildToast.classList.add('open');
    buildToast.setAttribute('aria-hidden', 'false');
    window.clearTimeout(showBuildToast.timer);
    showBuildToast.timer = window.setTimeout(() => {
      buildToast.classList.remove('open');
      buildToast.setAttribute('aria-hidden', 'true');
    }, 1700);
  }

  function bindCardReadPreview(cardNode, item, options = {}) {
    let previewTouchStart = null;
    cardNode.addEventListener('pointerover', (event) => {
      if (event.pointerType === 'touch' || pointerDrag?.active) {
        return;
      }
      showBuildCardPreview(item, cardNode, { pinned: false, pointerType: event.pointerType || 'mouse', touchSide: options.touchSide });
    });
    cardNode.addEventListener('pointerout', (event) => {
      if (cardNode.contains(event.relatedTarget)) {
        return;
      }
      hideBuildCardPreview();
    });
    cardNode.addEventListener('focusin', () => {
      showBuildCardPreview(item, cardNode, { pinned: false, pointerType: 'keyboard', touchSide: options.touchSide });
    });
    cardNode.addEventListener('focusout', (event) => {
      if (cardNode.contains(event.relatedTarget)) {
        return;
      }
      hideBuildCardPreview();
    });
    cardNode.addEventListener('pointerdown', (event) => {
      const touchLike = event.pointerType === 'touch' || window.matchMedia('(hover: none), (pointer: coarse)').matches;
      if (!touchLike) {
        return;
      }
      clearBuildPreviewPressTimer();
      previewTouchStart = { x: event.clientX, y: event.clientY };
      buildPreviewPressTimer = window.setTimeout(() => {
        suppressNextClick = true;
        buildPreviewIgnoreUntil = Date.now() + 360;
        showBuildCardPreview(item, cardNode, { pinned: true, pointerType: 'touch', touchSide: options.touchSide });
        window.setTimeout(() => {
          suppressNextClick = false;
        }, 720);
      }, 420);
    });
    cardNode.addEventListener('pointermove', (event) => {
      if (!previewTouchStart || event.pointerType !== 'touch') {
        return;
      }
      const distance = Math.hypot(event.clientX - previewTouchStart.x, event.clientY - previewTouchStart.y);
      if (distance >= 8) {
        previewTouchStart = null;
        clearBuildPreviewPressTimer();
      }
    });
    cardNode.addEventListener('pointerup', () => {
      previewTouchStart = null;
      clearBuildPreviewPressTimer();
    });
    cardNode.addEventListener('pointercancel', () => {
      previewTouchStart = null;
      clearBuildPreviewPressTimer();
    });
  }

  function showBuildCardPreview(item, sourceNode, options = {}) {
    buildPreviewPinned = Boolean(options.pinned);
    const touchLike = options.pointerType === 'touch' || window.matchMedia('(hover: none), (pointer: coarse)').matches;
    const sourceRect = sourceNode?.getBoundingClientRect?.();
    const showLeft = sourceRect ? sourceRect.left > window.innerWidth / 2 : false;
    const typeClass = ` type-${classToken(item.type)}`;
    const touchSide = options.touchSide === 'left' ? 'left' : options.touchSide === 'right' ? 'right' : '';
    const touchPositionClass = touchLike
      ? ` touch-preview${touchSide ? ` touch-side-preview preview-${touchSide}` : ''}`
      : showLeft ? ' preview-left' : ' preview-right';
    buildCardPreview.className = `build-card-preview open${typeClass}${touchPositionClass}${buildPreviewPinned ? ' pinned' : ''}`;
    buildCardPreview.setAttribute('aria-hidden', 'false');
    buildCardPreview.innerHTML = `
      <button class="preview-close" data-build-preview-close type="button" aria-label="关闭卡牌预览">×</button>
      <article class="build-card catalog-card preview-catalog-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}">
        ${cardMarkup(item, { mark: '', compact: false, preview: true })}
      </article>
    `;
  }

  function hideBuildCardPreview(options = {}) {
    if (buildPreviewPinned && !options.force) {
      return;
    }
    buildPreviewPinned = false;
    buildCardPreview.className = 'build-card-preview';
    buildCardPreview.setAttribute('aria-hidden', 'true');
    buildCardPreview.replaceChildren();
  }

  function clearBuildPreviewPressTimer() {
    window.clearTimeout(buildPreviewPressTimer);
    buildPreviewPressTimer = null;
  }

  filterTabs?.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-filter]');
    if (!button) {
      return;
    }
    selected.filter = button.dataset.filter || 'all';
    renderAll();
  });
  typeFilter?.addEventListener('change', () => {
    selected.filter = typeFilter.value || 'all';
    renderAll();
  });
  costFilter.addEventListener('change', () => {
    selected.costFilter = costFilter.value || 'all';
    renderAll();
  });
  powerFilter.addEventListener('change', () => {
    selected.powerFilter = powerFilter.value || 'all';
    renderAll();
  });
  materialFilter.addEventListener('change', () => {
    selected.materialFilter = materialFilter.value || 'all';
    renderAll();
  });
  categoryFilter.addEventListener('change', () => {
    selected.categoryFilter = categoryFilter.value || 'all';
    renderAll();
  });
  catalogSearch.addEventListener('input', () => {
    selected.search = catalogSearch.value.trim();
    renderCatalog();
  });
  deckDropZone.addEventListener('dragover', allowDrop);
  deckDropZone.addEventListener('dragenter', () => deckDropZone.classList.add('drop-target'));
  deckDropZone.addEventListener('dragleave', (event) => {
    if (!deckDropZone.contains(event.relatedTarget)) {
      deckDropZone.classList.remove('drop-target');
    }
  });
  deckDropZone.addEventListener('drop', handleDeckDrop);
  catalogDropZone.addEventListener('dragover', allowDrop);
  catalogDropZone.addEventListener('dragenter', () => catalogDropZone.classList.add('drop-target'));
  catalogDropZone.addEventListener('dragleave', (event) => {
    if (!catalogDropZone.contains(event.relatedTarget)) {
      catalogDropZone.classList.remove('drop-target');
    }
  });
  catalogDropZone.addEventListener('drop', handleCatalogDrop);
  clearBuildBtn.addEventListener('click', () => {
    if (!selected.itemIds.length && !selected.esperIds.length) {
      return;
    }
    selected.starterIds = [];
    selected.reserveIds = [];
    selected.esperIds = [];
    syncItemIds();
    renderAll();
    showBuildToast('构筑集已清空');
  });
  prebuiltPreviewBtn?.addEventListener('click', openPrebuiltPreview);
  prebuiltPreviewClose?.addEventListener('click', closePrebuiltPreview);
  prebuiltPreviewTabs?.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-deck-id]');
    if (!button) {
      return;
    }
    activePrebuiltDeckId = button.dataset.deckId || activePrebuiltDeckId;
    renderPrebuiltPreview();
  });
  prebuiltPreviewLayer?.addEventListener('pointerdown', (event) => {
    if (event.target === prebuiltPreviewLayer) {
      closePrebuiltPreview();
    }
  });
  saveBuildBtn.addEventListener('click', saveBuild);
  buildCardPreview.addEventListener('click', (event) => {
    if (Date.now() < buildPreviewIgnoreUntil) {
      return;
    }
    if (event.target.closest('[data-build-preview-close]') || buildCardPreview.classList.contains('touch-preview')) {
      hideBuildCardPreview({ force: true });
    }
  });
  document.addEventListener('pointerdown', (event) => {
    if (Date.now() < buildPreviewIgnoreUntil) {
      return;
    }
    if (
      !buildCardPreview.classList.contains('open')
      || event.target.closest('#build-card-preview')
      || event.target.closest('.catalog-card, .deck-card')
    ) {
      return;
    }
    hideBuildCardPreview({ force: true });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      if (prebuiltPreviewLayer?.classList.contains('open')) {
        closePrebuiltPreview();
        return;
      }
      hideBuildCardPreview({ force: true });
    }
  });

  renderAll();
  await initTutorialManual('build');
}

function uniqueIds(itemIds) {
  return Array.from(new Set((itemIds || []).map((itemId) => String(itemId)).filter(Boolean)));
}

function knownIds(itemIds) {
  return (itemIds || []).map((itemId) => String(itemId)).filter(Boolean);
}

function compareCards(left, right) {
  return compareCardSortKeys(cardSortKey(left), cardSortKey(right));
}

function compareCardIds(leftId, rightId) {
  const left = document.__nteBuildItemById?.get?.(leftId) || null;
  const right = document.__nteBuildItemById?.get?.(rightId) || null;
  return compareCardSortKeys(cardSortKey(left, leftId), cardSortKey(right, rightId));
}

function cardSortKey(item, fallbackId = '') {
  const type = String(item?.type || '');
  const typeIndex = CARD_TYPE_SORT_ORDER.includes(type) ? CARD_TYPE_SORT_ORDER.indexOf(type) : 99;
  const attribute = String(item?.attribute || item?.required_material_attribute || item?.element || '');
  const attributeIndex = ATTRIBUTE_SORT_ORDER.includes(attribute) ? ATTRIBUTE_SORT_ORDER.indexOf(attribute) : 99;
  const cost = Number(item?.type === 'esper' ? item?.material_cost || item?.cost || 0 : item?.cost || 0);
  const power = Number(item?.power || 0);
  return [typeIndex, cost, attributeIndex, power, String(item?.name || fallbackId)];
}

function compareCardSortKeys(left, right) {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] < right[index]) {
      return -1;
    }
    if (left[index] > right[index]) {
      return 1;
    }
  }
  return 0;
}

function powerMatchesFilter(power, filter) {
  if (filter === '0-1') {
    return power >= 0 && power <= 1;
  }
  if (filter === '2-3') {
    return power >= 2 && power <= 3;
  }
  if (filter === '4-6') {
    return power >= 4 && power <= 6;
  }
  if (filter === '7+') {
    return power >= 7;
  }
  return true;
}

function iconMarkup(icon, fallback = 'item') {
  const value = String(icon || fallback);
  if (/\.(png|jpg|jpeg|webp|gif|svg)$/i.test(value) || value.startsWith('/static/')) {
    return `<img class="item-icon-img" src="${escapeAttr(value)}" alt="" loading="lazy" decoding="async" fetchpriority="low">`;
  }
  return `<span class="item-icon item-icon-${classToken(value)}"></span>`;
}

function itemTypeLabel(type) {
  return ITEM_TYPE_LABELS[type] || type || '卡牌';
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
