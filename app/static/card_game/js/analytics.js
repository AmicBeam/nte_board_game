(function () {
  if (!ensureLogin()) {
    return;
  }

  const state = {
    data: null,
    view: 'decks',
    search: '',
    deckFilter: '',
    statusFilter: '',
    sortKey: '',
    sortDirection: 'desc',
    cardLookup: { byId: new Map(), byName: new Map() },
  };

  const kpis = document.getElementById('analytics-kpis');
  const summary = document.getElementById('analytics-summary');
  const table = document.getElementById('analytics-table');
  const searchInput = document.getElementById('analytics-search');
  const deckFilter = document.getElementById('analytics-deck-filter');
  const statusFilter = document.getElementById('analytics-status-filter');

  const column = (label, key, render, sortValue) => ({
    label,
    key,
    render: render || ((row) => fmt(row[key])),
    sortValue: sortValue || ((row) => row[key]),
  });

  const viewConfig = {
    decks: {
      rows: (data) => data.decks || [],
      defaultSort: 'win_rate',
      columns: [
        column('套牌', 'label', (row) => strong(row.label)),
        column('胜率', 'win_rate', (row) => pct(row.win_rate)),
        column('场次', 'games'),
        column('首异能者', 'avg_first_esper_turn'),
        column('全登场率', 'all_esper_rate', (row) => pct(row.all_esper_rate)),
        column('平均登场数', 'avg_unique_espers'),
        column('终局战力', 'avg_ending_power'),
        column('异能者动作', 'esper_actions'),
        column('互动', 'interaction_events'),
      ],
    },
    matchups: {
      rows: (data) => data.matchups || [],
      defaultSort: 'win_rate',
      columns: [
        column(
          '对局',
          'matchup',
          (row) => `${strong(row.deck_label)} <span class="analytics-pill">vs</span> ${strong(row.opponent_label)}`,
          (row) => `${row.deck_label}-${row.opponent_label}`,
        ),
        column('胜率', 'win_rate', (row) => pct(row.win_rate)),
        column('场次', 'games'),
        column('首异能者', 'avg_first_esper_turn'),
        column('全登场率', 'all_esper_rate', (row) => pct(row.all_esper_rate)),
        column('平均登场数', 'avg_unique_espers'),
        column('阻断率', 'blocked_game_rate', (row) => pct(row.blocked_game_rate)),
        column('终局战力', 'avg_ending_power'),
      ],
    },
    cards: {
      rows: (data) => data.cards || [],
      defaultSort: 'impact_score',
      columns: cardColumns(),
    },
    espers: {
      rows: (data) => data.espers || [],
      defaultSort: 'appearance_rate',
      columns: [
        column('套牌', 'deck_label', (row) => strong(row.deck_label)),
        column('异能者', 'name', (row) => `${cardName(row)} ${pill(row.attribute || '-')}`),
        column('登场率', 'appearance_rate', (row) => pct(row.appearance_rate)),
        column('登场', 'appearances', (row) => `${fmt(row.appearances)}/${fmt(row.games)}`),
        column('登场胜率', 'win_rate_when_appeared', (row) => pct(row.win_rate_when_appeared)),
        column('平均回合', 'avg_first_turn'),
        column('素材数', 'avg_material_count'),
        column('吸收战力', 'avg_absorbed_power'),
        column('终局战力', 'avg_final_power'),
        column('素材条件', 'requirement_text', (row) => materialText(row)),
        column('样例', 'sample_lines', (row) => sampleLines(row.sample_lines), (row) => (row.sample_lines || []).length),
      ],
    },
    delay: {
      rows: (data) => (data.delay || {}).breaks || [],
      defaultSort: 'blocked_matches',
      columns: [
        column('破坏源', 'name', (row) => cardName(row)),
        column('命中素材', 'material_hits'),
        column('破碎', 'destroyed_targets'),
        column('后续阻断', 'blocked_matches'),
        column('阻断率', 'block_rate', (row) => pct(row.block_rate)),
        column('影响分', 'impact_score'),
        column('高频目标', 'top_targets', (row) => targetList(row.top_targets), (row) => (row.top_targets || []).length),
        column('样例', 'sample_lines', (row) => sampleLines(row.sample_lines), (row) => (row.sample_lines || []).length),
      ],
    },
  };

  function cardColumns() {
    return [
      column('卡牌', 'name', (row) => `${cardName(row)} ${pill(row.type === 'esper' ? '异能者' : '道具')}`),
      column('套牌', 'decks', (row) => (row.decks || []).map((deckId) => pill(deckLabel(deckId))).join(''), (row) => (row.decks || []).join(',')),
      column('揭示', 'reveals'),
      column('见牌胜率', 'win_rate_when_seen', (row) => pct(row.win_rate_when_seen)),
      column('影响分', 'impact_score'),
      column('每次揭示', 'impact_per_reveal'),
      column('素材使用', 'material_uses'),
      column('效果日志', 'effect_logs'),
    ];
  }

  function fmt(value) {
    if (value === null || value === undefined || value === '') {
      return '-';
    }
    return nteEscapeHtml(value);
  }

  function pct(value) {
    return `${fmt(value)}%`;
  }

  function strong(value) {
    return `<strong>${nteEscapeHtml(value)}</strong>`;
  }

  function cardName(row, suffix = '', options = {}) {
    const card = resolveCard(row);
    const name = String(row?.name || card?.name || row?.card_id || row?.id || '-');
    const art = String(row?.art || row?.icon || card?.art || card?.icon || '');
    const label = options.pill
      ? `<span class="analytics-pill">${nteEscapeHtml(`${name}${suffix}`)}</span>`
      : `<strong>${nteEscapeHtml(name)}</strong>${suffix}`;
    if (!art) {
      return label;
    }
    const meta = cardMeta(Object.assign({}, card || {}, row || {}));
    const description = String(row?.description || card?.description || row?.requirement_text || card?.material_requirement_text || '');
    return `
      <span
        class="analytics-card-name"
        tabindex="0"
        data-preview-art="${nteEscapeHtml(art)}"
        data-preview-name="${nteEscapeHtml(name)}"
        data-preview-meta="${nteEscapeHtml(meta)}"
        data-preview-desc="${nteEscapeHtml(description)}"
      >${label}</span>
    `;
  }

  function cardMeta(card) {
    const typeLabel = card.type === 'esper' ? '异能者' : (card.type ? '道具' : '');
    const tags = [
      typeLabel,
      card.attribute,
      card.category,
      card.rarity ? String(card.rarity).toUpperCase() : '',
    ].filter(Boolean);
    const cost = Number(card.cost || 0);
    const power = Number(card.power || 0);
    if (cost || power) {
      tags.push(`${cost}费 / ${power}战力`);
    }
    return tags.join(' · ');
  }

  function pill(value, tone = '') {
    return `<span class="analytics-pill ${tone}">${nteEscapeHtml(value)}</span>`;
  }

  function sampleLines(lines) {
    const sample = (lines || []).slice(0, 3);
    if (!sample.length) {
      return '-';
    }
    return sample.map((line) => `<div class="analytics-sample-line">${nteEscapeHtml(line)}</div>`).join('');
  }

  function targetList(targets) {
    const sample = (targets || []).slice(0, 4);
    if (!sample.length) {
      return '-';
    }
    return sample.map((target) => cardName(target, ` x${target.count}`, { pill: true })).join('');
  }

  function materialText(row) {
    const base = row.requirement_text ? nteEscapeHtml(row.requirement_text) : '-';
    if (!row.material_gap) {
      return base;
    }
    return `${base}<div class="analytics-warn">${nteEscapeHtml(row.material_gap)}</div>`;
  }

  function rowSearchText(row) {
    return JSON.stringify(row).toLowerCase();
  }

  function deckLabel(deckId) {
    const deck = (state.data?.decks || []).find((item) => item.id === deckId);
    return deck ? deck.label : deckId;
  }

  function rebuildCardLookup(data) {
    const byId = new Map();
    const byName = new Map();
    [
      ...(data.cards || []),
      ...(data.items || []),
      ...(data.espers || []),
      ...((data.delay || {}).breaks || []),
      ...((data.delay || {}).tools || []),
      ...((data.delay || {}).breaks || []).flatMap((row) => row.top_targets || []),
    ].forEach((card) => {
      if (!card || typeof card !== 'object') {
        return;
      }
      const id = String(card.id || card.card_id || '');
      const name = String(card.name || '');
      if (id && !byId.has(id)) {
        byId.set(id, card);
      }
      if (name && !byName.has(name)) {
        byName.set(name, card);
      }
    });
    state.cardLookup = { byId, byName };
  }

  function resolveCard(row) {
    if (!row || typeof row !== 'object') {
      return null;
    }
    const id = String(row.id || row.card_id || '');
    const name = String(row.name || '');
    return (id && state.cardLookup.byId.get(id)) || (name && state.cardLookup.byName.get(name)) || null;
  }

  function rowDeckIds(row) {
    const ids = new Set();
    ['deck_id', 'opponent_deck_id', 'target_deck_id'].forEach((key) => {
      if (row[key]) {
        ids.add(String(row[key]));
      }
    });
    (row.decks || []).forEach((deckId) => ids.add(String(deckId)));
    (row.target_decks || []).forEach((deckId) => ids.add(String(deckId)));
    return ids;
  }

  function statusMatches(row) {
    switch (state.statusFilter) {
      case 'item':
        return row.type !== 'esper';
      case 'esper':
        return row.type === 'esper' || Boolean(row.card_id && row.appearance_rate !== undefined);
      case 'zero-appearance':
        return Number(row.appearance_rate || 0) === 0 && row.appearances !== undefined;
      case 'material-gap':
        return Boolean(row.material_gap);
      case 'successful-delay':
        return Boolean(row.success) || Number(row.blocked_matches || 0) > 0 || Number(row.successes || 0) > 0;
      default:
        return true;
    }
  }

  function filterRows(rows) {
    const query = state.search.trim().toLowerCase();
    return rows.filter((row) => {
      if (query && !rowSearchText(row).includes(query)) {
        return false;
      }
      if (state.deckFilter && !rowDeckIds(row).has(state.deckFilter)) {
        return false;
      }
      return statusMatches(row);
    });
  }

  function sortRows(rows, columns) {
    const key = state.sortKey || viewConfig[state.view].defaultSort;
    const columnConfig = columns.find((item) => item.key === key) || columns[0];
    const direction = state.sortDirection === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = normalizedSortValue(columnConfig.sortValue(a));
      const right = normalizedSortValue(columnConfig.sortValue(b));
      if (left < right) {
        return -1 * direction;
      }
      if (left > right) {
        return 1 * direction;
      }
      return 0;
    });
  }

  function normalizedSortValue(value) {
    if (value === null || value === undefined || value === '') {
      return Number.NEGATIVE_INFINITY;
    }
    const numeric = Number(value);
    if (!Number.isNaN(numeric)) {
      return numeric;
    }
    return String(value);
  }

  function renderKpis(data) {
    const topDeck = [...(data.decks || [])].sort((a, b) => b.win_rate - a.win_rate)[0];
    const topFullEsperDeck = [...(data.decks || [])].sort((a, b) => Number(b.all_esper_rate || 0) - Number(a.all_esper_rate || 0))[0];
    const delayRecords = (data.delay || {}).records || [];
    const delaySuccess = delayRecords.filter((record) => record.success).length;
    const lowEsper = [...(data.espers || [])].sort((a, b) => Number(a.appearance_rate || 0) - Number(b.appearance_rate || 0))[0];
    const acceptance = data.acceptance || {};
    const failedChecks = (acceptance.checks || []).filter((check) => !check.passed).length;
    const acceptanceLabel = acceptance.status === 'passed' ? '通过' : (acceptance.status === 'attention' ? '需关注' : '-');
    kpis.innerHTML = [
      kpi('看板验收', acceptanceLabel, failedChecks ? `${failedChecks} 项需复盘` : '指标通过'),
      kpi('样本', `${data.samples || 0}`, `${data.focus || '-'} / seed ${data.seed || '-'}`),
      kpi('最高胜率', topDeck ? `${topDeck.label} ${topDeck.win_rate}%` : '-', topDeck ? `${topDeck.games} 场` : ''),
      kpi('4人全登场', topFullEsperDeck ? `${topFullEsperDeck.label} ${topFullEsperDeck.all_esper_rate}%` : '-', topFullEsperDeck ? `平均 ${topFullEsperDeck.avg_unique_espers || 0} 名` : ''),
      kpi('拖延成功', `${delaySuccess}/${delayRecords.length}`, '延滞相关对局'),
      kpi('低登场异能者', lowEsper ? lowEsper.name : '无', lowEsper ? `登场率 ${lowEsper.appearance_rate}%` : '当前样本未发现'),
    ].join('');
  }

  function kpi(label, value, detail) {
    return `
      <article class="analytics-kpi">
        <span>${nteEscapeHtml(label)}</span>
        <strong>${nteEscapeHtml(value)}</strong>
        <small>${nteEscapeHtml(detail || '')}</small>
      </article>
    `;
  }

  function renderSummary(data) {
    const checks = ((data.acceptance || {}).checks || []).map((check) => {
      const mark = check.passed ? '通过' : '需关注';
      return `${mark}：${check.name}。${check.detail}`;
    });
    const notes = data.observations || [];
    const lines = [...checks, ...notes];
    summary.innerHTML = lines.length
      ? lines.map((note) => `<div class="analytics-note">${nteEscapeHtml(note)}</div>`).join('')
      : '<div class="analytics-note">暂无观察结论。</div>';
  }

  function renderDeckFilter() {
    const decks = state.data?.decks || [];
    const current = state.deckFilter;
    deckFilter.innerHTML = [
      '<option value="">全部套牌</option>',
      ...decks.map((deck) => `<option value="${nteEscapeHtml(deck.id)}">${nteEscapeHtml(deck.label)}</option>`),
    ].join('');
    deckFilter.value = current;
  }

  function renderTable() {
    const data = state.data;
    const config = viewConfig[state.view];
    if (!data || !config) {
      return;
    }
    const columns = config.columns;
    const rows = sortRows(filterRows(config.rows(data)), columns);
    table.querySelector('thead').innerHTML = `
      <tr>
        ${columns.map((item) => {
          const active = (state.sortKey || config.defaultSort) === item.key;
          const direction = active ? state.sortDirection : 'desc';
          return `<th><button class="analytics-sort" type="button" data-key="${nteEscapeHtml(item.key)}">${nteEscapeHtml(item.label)}${active ? `<span>${direction === 'asc' ? '↑' : '↓'}</span>` : ''}</button></th>`;
        }).join('')}
      </tr>
    `;
    table.querySelector('tbody').innerHTML = rows.length
      ? rows.map((row) => `<tr>${columns.map((item) => `<td>${item.render(row)}</td>`).join('')}</tr>`).join('')
      : `<tr><td class="analytics-empty" colspan="${columns.length}">没有匹配数据。</td></tr>`;
    table.querySelectorAll('.analytics-sort').forEach((button) => {
      button.addEventListener('click', () => setSort(button.dataset.key || ''));
    });
  }

  function setSort(key) {
    if (state.sortKey === key) {
      state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      state.sortKey = key;
      state.sortDirection = 'desc';
    }
    renderTable();
  }

  function setView(view) {
    state.view = view;
    state.sortKey = '';
    state.sortDirection = 'desc';
    document.querySelectorAll('.analytics-tab').forEach((button) => {
      button.classList.toggle('active', button.dataset.view === view);
    });
    renderTable();
  }

  async function loadAnalytics() {
    const payload = await apiRequest('/api/analytics/balance');
    if (!payload.available) {
      kpis.innerHTML = kpi('数据', '未生成', payload.message || '');
      summary.innerHTML = '<div class="analytics-note">运行评测脚本后刷新本页。</div>';
      table.querySelector('thead').innerHTML = '';
      table.querySelector('tbody').innerHTML = '<tr><td class="analytics-empty">暂无数据。</td></tr>';
      return;
    }
    state.data = payload.data;
    rebuildCardLookup(state.data);
    renderDeckFilter();
    renderKpis(state.data);
    renderSummary(state.data);
    renderTable();
  }

  document.querySelectorAll('.analytics-tab').forEach((button) => {
    button.addEventListener('click', () => setView(button.dataset.view || 'decks'));
  });
  searchInput.addEventListener('input', () => {
    state.search = searchInput.value;
    renderTable();
  });
  deckFilter.addEventListener('change', () => {
    state.deckFilter = deckFilter.value;
    renderTable();
  });
  statusFilter.addEventListener('change', () => {
    state.statusFilter = statusFilter.value;
    renderTable();
  });

  setupCardPreview();

  loadAnalytics().catch((error) => {
    kpis.innerHTML = kpi('读取失败', 'Error', error.message);
  });

  function setupCardPreview() {
    const preview = document.createElement('div');
    preview.className = 'analytics-card-preview-popover';
    preview.innerHTML = `
      <img alt="" loading="lazy">
      <div class="analytics-card-preview-body">
        <strong></strong>
        <small></small>
        <p></p>
      </div>
    `;
    document.body.appendChild(preview);
    const image = preview.querySelector('img');
    const title = preview.querySelector('strong');
    const meta = preview.querySelector('small');
    const desc = preview.querySelector('p');
    let activeTarget = null;

    function show(target, event) {
      if (!target?.dataset.previewArt) {
        return;
      }
      activeTarget = target;
      image.src = target.dataset.previewArt;
      image.alt = target.dataset.previewName || '';
      title.textContent = target.dataset.previewName || '';
      meta.textContent = target.dataset.previewMeta || '';
      desc.textContent = target.dataset.previewDesc || '';
      preview.classList.add('open');
      position(event || target);
    }

    function hide() {
      activeTarget = null;
      preview.classList.remove('open');
    }

    function position(eventOrTarget) {
      let x = 0;
      let y = 0;
      if ('clientX' in eventOrTarget && 'clientY' in eventOrTarget) {
        x = eventOrTarget.clientX;
        y = eventOrTarget.clientY;
      } else {
        const rect = eventOrTarget.getBoundingClientRect();
        x = rect.right;
        y = rect.top;
      }
      const gap = 16;
      const rect = preview.getBoundingClientRect();
      let left = x + gap;
      let top = y + gap;
      if (left + rect.width > window.innerWidth - 12) {
        left = x - rect.width - gap;
      }
      if (top + rect.height > window.innerHeight - 12) {
        top = window.innerHeight - rect.height - 12;
      }
      preview.style.left = `${Math.max(12, left)}px`;
      preview.style.top = `${Math.max(12, top)}px`;
    }

    table.addEventListener('mouseover', (event) => {
      const target = event.target.closest('.analytics-card-name[data-preview-art]');
      if (!target || !table.contains(target) || target === activeTarget) {
        return;
      }
      show(target, event);
    });
    table.addEventListener('mousemove', (event) => {
      if (activeTarget) {
        position(event);
      }
    });
    table.addEventListener('mouseout', (event) => {
      if (!activeTarget || activeTarget.contains(event.relatedTarget)) {
        return;
      }
      hide();
    });
    table.addEventListener('focusin', (event) => {
      const target = event.target.closest('.analytics-card-name[data-preview-art]');
      if (target && table.contains(target)) {
        show(target, target);
      }
    });
    table.addEventListener('focusout', hide);
    window.addEventListener('scroll', hide, true);
  }
}());
