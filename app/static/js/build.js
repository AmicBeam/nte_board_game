if (ensureLogin()) {
  bootstrap();
}

const ITEM_TYPE_LABELS = {
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

async function bootstrap() {
  try {
    const activeState = await apiRequest('/api/game/state');
    if (activeState.status === 'playing') {
      window.location.href = '/table';
      return;
    }
  } catch (error) {
    // 没有进行中对局时继续构筑。
  }
  const data = await apiRequest('/api/catalog');
  const savedCharacterId = data.saved_build ? data.saved_build.character_id : null;
  const selected = {
    characterId: savedCharacterId || data.characters[0]?.id || null,
    characterIndex: Math.max(0, data.characters.findIndex((character) => character.id === savedCharacterId)),
    itemIds: data.saved_build ? data.saved_build.item_ids.slice() : [],
    buildSize: data.build_size,
    lockedItemIds: data.locked_item_ids || [],
    characters: data.characters,
    items: data.items,
  };
  preloadCharacterAssets(selected.characters);

  const characterCarousel = document.getElementById('character-carousel');
  const selectedPortrait = document.getElementById('selected-character-portrait');
  const selectedCharacterInfo = document.getElementById('selected-character-info');
  const itemGrid = document.getElementById('item-grid');
  const selectedCharacterCopy = document.getElementById('selected-character-copy');
  const deckCount = document.getElementById('deck-count');
  const saveBuildBtn = document.getElementById('save-build-btn');

  function classToken(value) {
    return String(value || 'unknown').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
  }

  function normalizeIndex(index) {
    if (!selected.characters.length) {
      return 0;
    }
    const roundedIndex = Math.round(index);
    return ((roundedIndex % selected.characters.length) + selected.characters.length) % selected.characters.length;
  }

  function normalizedPosition(position) {
    if (!selected.characters.length) {
      return 0;
    }
    return ((position % selected.characters.length) + selected.characters.length) % selected.characters.length;
  }

  function circularOffset(index, position) {
    const count = selected.characters.length;
    if (!count) {
      return 0;
    }
    const current = normalizedPosition(position);
    let offset = index - current;
    if (offset > count / 2) {
      offset -= count;
    }
    if (offset < -count / 2) {
      offset += count;
    }
    return offset;
  }

  function selectedCharacter() {
    return selected.characters[normalizeIndex(selected.characterIndex)] || null;
  }

  function currentLockedItemIds() {
    const character = selectedCharacter();
    return Array.from(new Set([...(selected.lockedItemIds || []), ...((character && character.exclusive_item_ids) || [])]));
  }

  function sanitizeSelectableItems() {
    const locked = new Set(currentLockedItemIds());
    selected.itemIds = selected.itemIds.filter((itemId) => !locked.has(itemId));
  }

  function iconMarkup(icon, fallback = 'item') {
    const value = String(icon || fallback);
    if (/\.(png|jpg|jpeg|webp|gif|svg)$/i.test(value) || value.startsWith('/static/')) {
      return `<img class="item-icon-img" src="${value}" alt="">`;
    }
    return `<span class="item-icon item-icon-${classToken(value)}"></span>`;
  }

  function characterAvatar(character) {
    return `<img src="${character.avatar_image}" alt="" loading="eager" decoding="async">`;
  }

  function preloadCharacterAssets(characters) {
    const seen = new Set();
    characters.forEach((character) => {
      [character.avatar_image, character.portrait_image].forEach((assetUrl) => {
        if (!assetUrl || seen.has(assetUrl)) {
          return;
        }
        seen.add(assetUrl);
        const preload = document.createElement('link');
        preload.rel = 'preload';
        preload.as = 'image';
        preload.href = assetUrl;
        document.head.appendChild(preload);

        const image = new Image();
        image.decoding = 'async';
        image.loading = 'eager';
        image.src = assetUrl;
      });
    });
  }

  function itemTypeLabel(type) {
    return ITEM_TYPE_LABELS[type] || type || '道具';
  }

  function renderCharacterDetails() {
    const character = selectedCharacter();
    selected.characterId = character?.id || null;
    selectedCharacterCopy.textContent = character ? character.name : '尚未选择';
    if (character) {
      selectedPortrait.src = character.portrait_image;
      selectedPortrait.alt = character.name;
      selectedCharacterInfo.innerHTML = `
        <div class="card-headline">
          <h2>${character.name}</h2>
        </div>
        <p class="character-meta">${character.passive}</p>
      `;
    } else {
      selectedPortrait.removeAttribute('src');
      selectedPortrait.alt = '';
      selectedCharacterInfo.innerHTML = '<p class="empty-state">尚未选择角色</p>';
    }
  }

  let wheelPosition = selected.characterIndex;
  let targetWheelPosition = selected.characterIndex;
  let wheelAnimationFrame = 0;
  let lastWheelFrameAt = 0;
  let lastWheelInputAt = 0;
  let dragStartY = 0;
  let dragStartPosition = 0;
  const wheelSpeed = 0.0027;
  const wheelStepHeight = 82;
  const visibleRadius = Math.min(2, Math.max(1.5, (selected.characters.length - 1) / 2));

  function stopWheelAnimation() {
    if (wheelAnimationFrame) {
      cancelAnimationFrame(wheelAnimationFrame);
      wheelAnimationFrame = 0;
    }
    lastWheelFrameAt = 0;
  }

  function updateSelectedCharacterFromWheel() {
    const nextIndex = normalizeIndex(wheelPosition);
    if (nextIndex === selected.characterIndex) {
      return;
    }
    selected.characterIndex = nextIndex;
    renderCharacterDetails();
    sanitizeSelectableItems();
    renderItems();
  }

  function updateWheelLayout() {
    const buttons = characterCarousel.querySelectorAll('.wheel-character');
    buttons.forEach((button) => {
      const index = Number(button.dataset.index);
      const offset = circularOffset(index, wheelPosition);
      const absoluteOffset = Math.abs(offset);
      const clampedOffset = Math.max(-visibleRadius, Math.min(visibleRadius, offset));
      const curvedX = Math.pow(Math.abs(clampedOffset), 1.38) * 18;
      const y = clampedOffset * wheelStepHeight;
      const scale = Math.max(0.78, 1 - absoluteOffset * 0.065);
      const opacity = Math.max(0.16, 1 - absoluteOffset * 0.27);

      button.style.setProperty('--wheel-x', `${curvedX}px`);
      button.style.setProperty('--wheel-y', `${y}px`);
      button.style.setProperty('--wheel-scale', scale.toFixed(3));
      button.style.setProperty('--wheel-opacity', opacity.toFixed(3));
      button.style.setProperty('--wheel-z', String(100 - Math.round(absoluteOffset * 10)));
      button.classList.toggle('active', absoluteOffset < 0.36);
      button.hidden = absoluteOffset > visibleRadius + 0.01;
      button.style.pointerEvents = absoluteOffset <= visibleRadius + 0.01 ? 'auto' : 'none';
      button.setAttribute('aria-selected', absoluteOffset < 0.36 ? 'true' : 'false');
    });
    updateSelectedCharacterFromWheel();
  }

  function renderCharacters() {
    characterCarousel.innerHTML = '';
    selected.characters.forEach((item, index) => {
      if (!item) {
        return;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'wheel-character';
      button.dataset.index = String(index);
      button.innerHTML = `
        <span class="wheel-avatar">${characterAvatar(item)}</span>
        <span>${item.name}</span>
      `;
      button.addEventListener('click', () => setCharacterIndex(index));
      characterCarousel.appendChild(button);
    });
    renderCharacterDetails();
    updateWheelLayout();
  }

  function animateWheel(timestamp) {
    if (!lastWheelFrameAt) {
      lastWheelFrameAt = timestamp;
    }
    const frameDelta = Math.min(40, timestamp - lastWheelFrameAt);
    lastWheelFrameAt = timestamp;
    const distance = targetWheelPosition - wheelPosition;
    const step = wheelSpeed * frameDelta;
    if (Math.abs(distance) <= step) {
      wheelPosition = targetWheelPosition;
      wheelAnimationFrame = 0;
      lastWheelFrameAt = 0;
      updateWheelLayout();
      return;
    }
    wheelPosition += Math.sign(distance) * step;
    updateWheelLayout();
    wheelAnimationFrame = requestAnimationFrame(animateWheel);
  }

  function startWheelAnimation() {
    if (!wheelAnimationFrame) {
      wheelAnimationFrame = requestAnimationFrame(animateWheel);
    }
  }

  function targetForIndex(index) {
    const count = selected.characters.length;
    if (!count) {
      return 0;
    }
    const normalizedTarget = normalizeIndex(index);
    const current = normalizedPosition(targetWheelPosition);
    let delta = normalizedTarget - current;
    if (delta > count / 2) {
      delta -= count;
    }
    if (delta < -count / 2) {
      delta += count;
    }
    return targetWheelPosition + delta;
  }

  function setCharacterIndex(index) {
    targetWheelPosition = targetForIndex(index);
    startWheelAnimation();
  }

  function cycleCharacter(delta) {
    targetWheelPosition += delta;
    startWheelAnimation();
  }

  function renderItems() {
    itemGrid.innerHTML = '';
    const locked = new Set(currentLockedItemIds());
    selected.items.forEach((item) => {
      if (item.hidden_from_build && !locked.has(item.id)) {
        return;
      }
      const card = document.createElement('article');
      const isLocked = locked.has(item.id);
      const isSelected = isLocked || selected.itemIds.includes(item.id);
      card.className = `build-card item-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}`;
      if (isSelected) {
        card.classList.add('selected');
      }
      if (isLocked) {
        card.classList.add('locked');
      }
      card.innerHTML = `
        <div class="item-art" aria-hidden="true">
          ${iconMarkup(item.icon)}
        </div>
        <div class="card-headline">
          <span class="card-tag">${itemTypeLabel(item.type)}</span>
          <h2>${item.name}</h2>
        </div>
        <p class="card-meta">${item.description}</p>
        <span class="selection-mark">${isLocked ? '专属' : '已装配'}</span>
      `;
      if (!isLocked) {
        card.addEventListener('click', () => toggleItem(item.id));
      }
      itemGrid.appendChild(card);
    });
    deckCount.textContent = `已选择 ${selected.itemIds.length} / 最多 ${selected.buildSize} 个`;
  }

  function toggleItem(itemId) {
    if (currentLockedItemIds().includes(itemId)) {
      return;
    }
    const index = selected.itemIds.indexOf(itemId);
    if (index >= 0) {
      selected.itemIds.splice(index, 1);
    } else if (selected.itemIds.length < selected.buildSize) {
      selected.itemIds.push(itemId);
    } else {
      window.alert(`最多选择 ${selected.buildSize} 个道具。`);
    }
    renderItems();
  }

  async function saveBuild() {
    if (!selected.characterId) {
      window.alert('请先选择角色。');
      return;
    }
    if (selected.itemIds.length > selected.buildSize) {
      window.alert(`最多选择 ${selected.buildSize} 个道具。`);
      return;
    }
    saveBuildBtn.disabled = true;
    try {
      await apiRequest('/api/build/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_id: selected.characterId,
          item_ids: selected.itemIds,
        }),
      });
      window.location.href = '/';
    } catch (error) {
      window.alert(error.message);
    } finally {
      saveBuildBtn.disabled = false;
    }
  }

  characterCarousel.addEventListener('wheel', (event) => {
    event.preventDefault();
    if (Math.abs(event.deltaY) < 3) {
      return;
    }
    const now = performance.now();
    if (now - lastWheelInputAt < 260) {
      return;
    }
    lastWheelInputAt = now;
    cycleCharacter(event.deltaY > 0 ? 1 : -1);
  }, { passive: false });
  characterCarousel.addEventListener('pointerdown', (event) => {
    stopWheelAnimation();
    dragStartY = event.clientY;
    dragStartPosition = wheelPosition;
    characterCarousel.setPointerCapture(event.pointerId);
  });
  characterCarousel.addEventListener('pointermove', (event) => {
    if (!characterCarousel.hasPointerCapture(event.pointerId)) {
      return;
    }
    const delta = event.clientY - dragStartY;
    wheelPosition = dragStartPosition - delta / wheelStepHeight;
    targetWheelPosition = wheelPosition;
    updateWheelLayout();
  });
  characterCarousel.addEventListener('pointerup', (event) => {
    if (characterCarousel.hasPointerCapture(event.pointerId)) {
      characterCarousel.releasePointerCapture(event.pointerId);
    }
    targetWheelPosition = Math.round(wheelPosition);
    startWheelAnimation();
  });
  characterCarousel.addEventListener('pointercancel', (event) => {
    if (characterCarousel.hasPointerCapture(event.pointerId)) {
      characterCarousel.releasePointerCapture(event.pointerId);
    }
    targetWheelPosition = Math.round(wheelPosition);
    startWheelAnimation();
  });

  saveBuildBtn.addEventListener('click', saveBuild);
  renderCharacters();
  renderItems();
  await initTutorialManual('build');
}
