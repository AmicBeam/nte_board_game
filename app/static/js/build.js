if (ensureLogin()) {
  bootstrap();
}

const ITEM_TYPE_LABELS = {
  esper: '异能者',
  anomaly_item: '异象道具',
  token: '临时牌',
  attack: '攻击',
  defense: '防御',
  utility: '功能',
  mobility: '移动',
  recovery: '恢复',
  dice: '骰子',
  intel: '侦察',
  currency: '货币',
  loot: '鉴别物',
  key: '钥匙',
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
  const starterSize = Math.min(Number(data.opening_hand_size || 4), Number(data.build_size || 20));
  const selected = {
    itemIds: [],
    starterIds: data.saved_build
      ? (data.saved_build.starter_item_ids || data.saved_build.item_ids || []).slice(0, starterSize)
      : [],
    reserveIds: data.saved_build
      ? (data.saved_build.reserve_item_ids || (data.saved_build.item_ids || []).slice(starterSize)).slice()
      : [],
    buildSize: data.build_size,
    minBuildSize: Number(data.min_build_size || 10),
    starterSize,
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
    .slice(0, selected.buildSize - selected.starterSize);
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
  const buildToast = document.getElementById('build-toast');
  const buildCardPreview = document.getElementById('build-card-preview');
  const buildDragGhost = document.getElementById('build-drag-ghost');
  let currentDragPayload = null;
  let pointerDrag = null;
  let suppressNextClick = false;
  let buildPreviewPinned = false;
  let buildPreviewPressTimer = null;

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
    return zone === 'starter' ? selected.starterSize : selected.buildSize - selected.starterSize;
  }

  function autoZone() {
    return selected.starterIds.length < selected.starterSize ? 'starter' : 'reserve';
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
    const targetZone = item?.type === 'esper' ? 'esper' : zone === 'starter' ? 'starter' : zone === 'reserve' ? 'reserve' : autoZone();
    const allowed = canAddCard(item, targetZone);
    if (!allowed.ok) {
      showBuildToast(allowed.reason);
      return false;
    }
    const ids = zoneIds(targetZone);
    if (ids.length >= zoneLimit(targetZone)) {
      showBuildToast(targetZone === 'esper' ? '异能者待命区已满。' : targetZone === 'starter' ? '起始手牌已满。' : '预留牌库已满。');
      return false;
    }
    ids.push(itemId);
    sortSelectedZones();
    syncItemIds();
    renderAll();
    showBuildToast(`${item.name} 已加入${targetZone === 'esper' ? '异能者待命区' : targetZone === 'starter' ? '起始手牌' : '预留牌库'}`);
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
    const targetZone = zone === 'esper' ? 'esper' : zone === 'starter' ? 'starter' : 'reserve';
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
      showBuildToast(targetZone === 'esper' ? '异能者待命区已满。' : targetZone === 'starter' ? '起始手牌已满。' : '预留牌库已满。');
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
      fragment.appendChild(card);
    });
    catalogGrid.replaceChildren(fragment);
    catalogGrid.scrollTop = scrollTop;
  }

  function renderDeck() {
    renderDeckZone(esperList, 'esper', selected.esperIds, selected.maxEsperCards);
    renderDeckZone(starterList, 'starter', selected.starterIds, selected.starterSize);
    renderDeckZone(reserveList, 'reserve', selected.reserveIds, selected.buildSize - selected.starterSize);
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
        slot.innerHTML = `<span>${zone === 'esper' ? '待命空位' : zone === 'starter' ? '起手空位' : '预留空位'}</span>`;
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
      bindCardReadPreview(card, item);
      slot.appendChild(card);
      fragment.appendChild(slot);
    }
    container.replaceChildren(fragment);
  }

  function renderStatus() {
    const count = selected.itemIds.length;
    const missingMin = Math.max(0, selected.minBuildSize - count);
    const remainingMax = Math.max(0, selected.buildSize - count);
    const esperTotal = esperCount();
    starterCount.textContent = `${selected.starterIds.length} / ${selected.starterSize}`;
    reserveCount.textContent = `${selected.reserveIds.length} / ${selected.buildSize - selected.starterSize}`;
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

  function cardMarkup(item, { mark = '', compact = false }) {
    const description = `<p class="card-meta ${descriptionDensityClass(item.description)}">${descriptionWithAttributeIcon(item)}</p>`;
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
        <h2>${inlineStats}<span class="deck-card-name">${escapeHtml(item.name)}</span></h2>
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
    return Math.max(2, Math.min(3, Number.isFinite(cost) ? cost : 2));
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
    const resolvedZone = zone === 'starter' || zone === 'reserve' || zone === 'esper'
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
          starter_item_ids: selected.starterIds,
          reserve_item_ids: selected.reserveIds,
          esper_card_ids: selected.esperIds,
          item_ids: selected.itemIds,
        }),
      });
      window.location.href = '/home';
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

  function bindCardReadPreview(cardNode, item) {
    cardNode.addEventListener('pointerover', (event) => {
      if (event.pointerType === 'touch' || pointerDrag?.active) {
        return;
      }
      showBuildCardPreview(item, cardNode, { pinned: false, pointerType: event.pointerType || 'mouse' });
    });
    cardNode.addEventListener('pointerout', (event) => {
      if (cardNode.contains(event.relatedTarget)) {
        return;
      }
      hideBuildCardPreview();
    });
    cardNode.addEventListener('focusin', () => {
      showBuildCardPreview(item, cardNode, { pinned: false, pointerType: 'keyboard' });
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
      buildPreviewPressTimer = window.setTimeout(() => {
        suppressNextClick = true;
        showBuildCardPreview(item, cardNode, { pinned: true, pointerType: 'touch' });
      }, 420);
    });
  }

  function showBuildCardPreview(item, sourceNode, options = {}) {
    buildPreviewPinned = Boolean(options.pinned);
    const touchLike = options.pointerType === 'touch' || window.matchMedia('(hover: none), (pointer: coarse)').matches;
    const sourceRect = sourceNode?.getBoundingClientRect?.();
    const showLeft = sourceRect ? sourceRect.left > window.innerWidth / 2 : false;
    buildCardPreview.className = `build-card-preview open${touchLike ? ' touch-preview' : showLeft ? ' preview-left' : ' preview-right'}${buildPreviewPinned ? ' pinned' : ''}`;
    buildCardPreview.setAttribute('aria-hidden', 'false');
    buildCardPreview.innerHTML = `
      <button class="preview-close" data-build-preview-close type="button" aria-label="关闭卡牌预览">×</button>
      <article class="build-card catalog-card preview-catalog-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}">
        ${cardMarkup(item, { mark: '', compact: false })}
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
  saveBuildBtn.addEventListener('click', saveBuild);
  buildCardPreview.addEventListener('click', (event) => {
    if (event.target.closest('[data-build-preview-close]')) {
      hideBuildCardPreview({ force: true });
    }
  });
  document.addEventListener('pointerdown', (event) => {
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
  return [typeIndex, attributeIndex, cost, power, String(item?.name || fallbackId)];
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
