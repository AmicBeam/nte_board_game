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
};

const RARITY_LABELS = {
  common: '普通',
  rare: '稀有',
  epic: '史诗',
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
    characters: data.characters,
    items: data.items,
  };

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
    return ((index % selected.characters.length) + selected.characters.length) % selected.characters.length;
  }

  function selectedCharacter() {
    return selected.characters[normalizeIndex(selected.characterIndex)] || null;
  }

  function statBlock(label, value) {
    return `<div class="stat-card stat-card-compact"><span>${label}</span><strong>${value}</strong></div>`;
  }

  function iconMarkup(icon, fallback = 'item') {
    const value = String(icon || fallback);
    if (/\.(png|jpg|jpeg|webp|gif|svg)$/i.test(value) || value.startsWith('/static/')) {
      return `<img class="item-icon-img" src="${value}" alt="">`;
    }
    return `<span class="item-icon item-icon-${classToken(value)}"></span>`;
  }

  function characterAvatar(character) {
    return `<img src="${character.avatar_image}" alt="">`;
  }

  function itemTypeLabel(type) {
    return ITEM_TYPE_LABELS[type] || type || '道具';
  }

  function rarityLabel(rarity) {
    return RARITY_LABELS[rarity] || rarity || '普通';
  }

  function setCharacterIndex(index) {
    selected.characterIndex = normalizeIndex(index);
    const character = selectedCharacter();
    selected.characterId = character?.id || null;
    renderCharacters();
  }

  function cycleCharacter(delta) {
    setCharacterIndex(selected.characterIndex + delta);
  }

  function renderCharacters() {
    characterCarousel.innerHTML = '';
    const character = selectedCharacter();
    selectedCharacterCopy.textContent = character ? character.name : '尚未选择';
    if (character) {
      selectedPortrait.src = character.portrait_image;
      selectedPortrait.alt = character.name;
      selectedCharacterInfo.innerHTML = `
        <div class="card-headline">
          <p class="eyebrow">${character.title}</p>
          <h2>${character.name}</h2>
        </div>
        <div class="character-stats">
          ${statBlock('生命', character.max_hp)}
          ${statBlock('攻击', character.attack)}
          ${statBlock('防御', character.defense)}
        </div>
        <p class="character-meta">${character.passive}</p>
      `;
    } else {
      selectedPortrait.removeAttribute('src');
      selectedPortrait.alt = '';
      selectedCharacterInfo.innerHTML = '<p class="empty-state">尚未选择角色</p>';
    }

    [-2, -1, 0, 1, 2].forEach((offset) => {
      const index = normalizeIndex(selected.characterIndex + offset);
      const item = selected.characters[index];
      if (!item) {
        return;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `wheel-character offset-${offset}`;
      if (offset === 0) {
        button.classList.add('active');
      }
      button.innerHTML = `
        <span class="wheel-avatar">${characterAvatar(item)}</span>
        <span>${item.name}</span>
      `;
      button.addEventListener('click', () => setCharacterIndex(index));
      characterCarousel.appendChild(button);
    });
  }

  function renderItems() {
    itemGrid.innerHTML = '';
    selected.items.forEach((item) => {
      const card = document.createElement('article');
      card.className = `build-card item-card rarity-${classToken(item.rarity)} type-${classToken(item.type)}`;
      if (selected.itemIds.includes(item.id)) {
        card.classList.add('selected');
      }
      card.innerHTML = `
        <div class="item-art" aria-hidden="true">
          ${iconMarkup(item.icon)}
        </div>
        <div class="card-headline">
          <span class="card-tag">${itemTypeLabel(item.type)} · ${rarityLabel(item.rarity)}</span>
          <h2>${item.name}</h2>
        </div>
        <p class="card-meta">${item.description}</p>
        <span class="selection-mark">已装配</span>
      `;
      card.addEventListener('click', () => toggleItem(item.id));
      itemGrid.appendChild(card);
    });
    deckCount.textContent = `已选择 ${selected.itemIds.length} / ${selected.buildSize} 个`;
  }

  function toggleItem(itemId) {
    const index = selected.itemIds.indexOf(itemId);
    if (index >= 0) {
      selected.itemIds.splice(index, 1);
    } else if (selected.itemIds.length < selected.buildSize) {
      selected.itemIds.push(itemId);
    } else {
      window.alert(`必须选择 ${selected.buildSize} 个道具。`);
    }
    renderItems();
  }

  async function saveBuild() {
    if (!selected.characterId) {
      window.alert('请先选择角色。');
      return;
    }
    if (selected.itemIds.length !== selected.buildSize) {
      window.alert(`请先选择 ${selected.buildSize} 个道具。`);
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

  let dragY = 0;
  characterCarousel.addEventListener('wheel', (event) => {
    event.preventDefault();
    cycleCharacter(event.deltaY > 0 ? 1 : -1);
  }, { passive: false });
  characterCarousel.addEventListener('pointerdown', (event) => {
    dragY = event.clientY;
    characterCarousel.setPointerCapture(event.pointerId);
  });
  characterCarousel.addEventListener('pointermove', (event) => {
    if (!characterCarousel.hasPointerCapture(event.pointerId)) {
      return;
    }
    const delta = event.clientY - dragY;
    if (Math.abs(delta) < 44) {
      return;
    }
    cycleCharacter(delta > 0 ? 1 : -1);
    dragY = event.clientY;
  });
  characterCarousel.addEventListener('pointerup', (event) => {
    if (characterCarousel.hasPointerCapture(event.pointerId)) {
      characterCarousel.releasePointerCapture(event.pointerId);
    }
  });

  saveBuildBtn.addEventListener('click', saveBuild);
  renderCharacters();
  renderItems();
}
