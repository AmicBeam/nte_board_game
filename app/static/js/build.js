if (ensureLogin()) {
  bootstrap();
}

async function bootstrap() {
  const data = await apiRequest('/api/catalog');
  const selected = {
    characterId: data.saved_build ? data.saved_build.character_id : null,
    itemIds: data.saved_build ? data.saved_build.item_ids.slice() : [],
    buildSize: data.build_size,
    characters: data.characters,
    items: data.items,
  };

  const characterCarousel = document.getElementById('character-carousel');
  const itemGrid = document.getElementById('item-grid');
  const selectedCharacterCopy = document.getElementById('selected-character-copy');
  const deckCount = document.getElementById('deck-count');
  const saveBuildBtn = document.getElementById('save-build-btn');
  function renderCharacters() {
    characterCarousel.innerHTML = '';
    characterCarousel.innerHTML = '';
    selected.characters.forEach((character) => {
      const card = document.createElement('article');
      card.className = 'character-card';
      if (selected.characterId === character.id) {
        card.classList.add('selected');
        selectedCharacterCopy.textContent = `${character.name} · ${character.title}`;
      }
      card.innerHTML = `
        <div>
          <p class="eyebrow">${character.title}</p>
          <h2>${character.name}</h2>
        </div>
        <div class="character-stats">
          <div class="stat-card"><span>HP</span><strong>${character.max_hp}</strong></div>
          <div class="stat-card"><span>ATK</span><strong>${character.attack}</strong></div>
          <div class="stat-card"><span>DEF</span><strong>${character.defense}</strong></div>
        </div>
        <p class="character-meta">${character.passive}</p>
      `;
      card.addEventListener('click', () => {
        selected.characterId = character.id;
        renderCharacters();
      });
      characterCarousel.appendChild(card);
    });
    if (!selected.characterId) {
      selectedCharacterCopy.textContent = '尚未选择';
    }
  }

  function renderItems() {
    itemGrid.innerHTML = '';
    selected.items.forEach((item) => {
      const card = document.createElement('article');
      card.className = 'build-card';
      if (selected.itemIds.includes(item.id)) {
        card.classList.add('selected');
      }
      card.innerHTML = `
        <span class="card-tag">${item.type} · ${item.rarity}</span>
        <h2>${item.name}</h2>
        <p class="card-meta">${item.description}</p>
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

  saveBuildBtn.addEventListener('click', saveBuild);
  renderCharacters();
  renderItems();
}
