import './style.css';
import { categoryLabel, sourceLabel, importance, coordinates, locationLabel, eventTime, knownEventTime, formatDate, safeURL, normalizeFacets, makeQuery, stateLabel, elapsed, replayItems, clamp } from './model.js';

const app = document.querySelector('#app');
const $ = (selector) => document.querySelector(selector);
const num = (v) => v != null && v !== '' && Number.isFinite(Number(v)) ? new Intl.NumberFormat('zh-CN').format(Number(v)) : '—';
const ICONS = {
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3.5 9h17M3.5 15h17"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 11.5-1L20 9M4 15l2.5 3A7 7 0 0 0 18 17"/>',
  bookmark: '<path d="M6 4h12v17l-6-4-6 4z"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  external: '<path d="M13 4h7v7m0-7L10 14M9 5H4v15h15v-5"/>',
  filter: '<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="2"/><circle cx="16" cy="17" r="2"/>',
  pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  activity: '<path d="M2 12h5l3-8 4 16 3-8h5"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.1M3 12h.1M3 18h.1"/>',
  play: '<path d="m8 5 11 7-11 7z"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  home: '<path d="m3 11 9-8 9 8M6 9v12h12V9"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  logout: '<path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4"/>'
};
function icon(name, className = '') {
  return `<svg class="icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.info}</svg>`;
}
function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text != null) node.textContent = String(text); return node; }
function setText(selector, value) { const node = $(selector); if (node) node.textContent = String(value); }
function announce(text) { setText('#announcer', text); }
let toastTimer;
function toast(message) { clearTimeout(toastTimer); setText('#toast', message); $('#toast').hidden = false; toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4600); }

const state = {
  csrf: '', items: [], total: 0, stats: {}, facets: {}, status: null,
  filters: { sort: 'importance', q: '', source: '', category: '', after: '', before: '', bookmarked: false },
  loading: false, busyBookmark: new Set(), globe: null, selected: null, requestId: 0,
  cutoff: null, replayTimer: null, cluster: null, fetchedAt: null, offline: !navigator.onLine,
  view: 'globe', session: false, refreshTimer: null, newIds: new Set(), failCount: 0,
  bookmarkOverrides: new Map(), paginationPaused: false
};

async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 18000);
  try {
    const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', ...options, signal: controller.signal, headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf } : {}), ...(options.headers || {}) } });
    if (response.status === 401) {
      const wasAuthenticated = state.session;
      state.csrf = ''; state.session = false;
      if (!path.includes('/auth/session') && !$('#login-form')) showLogin(wasAuthenticated ? '登录已失效，请重新输入访问码。' : '');
      const error = new Error('访问码无效或会话已过期。'); error.status = 401; throw error;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { const error = new Error(data.error?.message || `请求未完成（${response.status}）`); error.status = response.status; throw error; }
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('请求超时，请检查服务器连接后重试。');
    throw error;
  } finally { clearTimeout(timeout); }
}

function showLogin(message = '') {
  clearInterval(state.refreshTimer); stopReplay();
  state.globe?.destroy(); state.globe = null;
  state.session = false; state.items = []; state.selected = null; state.fetchedAt = null;
  state.bookmarkOverrides.clear(); state.failCount = 0; state.paginationPaused = false;
  app.innerHTML = `
    <main class="login-shell">
      <div class="login-top"><a class="brand" href="/">${icon('globe', 'brand-symbol')}<span>FRONTIER<span class="brand-sub">前沿观测站</span></span></a><span class="edition">GLOBAL INTELLIGENCE</span></div>
      <div class="login-orbit" aria-hidden="true"><div></div><div></div><div></div><span></span></div>
      <section class="login-card" aria-labelledby="login-title">
        <span class="eyebrow"><span class="small-dot"></span> PRIVATE OBSERVATORY</span>
        <h1 id="login-title">世界，正在发生。</h1>
        <p class="login-lead">在地球上发现前沿事件。<br>沿着时间，理解每一次变化。</p>
        <form id="login-form">
          <label for="access-code">访问码</label>
          <div class="input-wrap"><input id="access-code" name="token" type="password" autocomplete="current-password" placeholder="输入你的私人访问码" required maxlength="512" /></div>
          <p id="login-error" class="form-error" role="alert"></p>
          <button class="primary-button login-submit" type="submit"><span>进入观测站</span>${icon('arrow')}</button>
        </form>
        <p class="login-note">通过受保护的会话连接你的讯息站。<br>API 密钥仅由服务器管理。</p>
      </section>
      <footer class="login-footer"><span>DISCOVER WHAT MOVES THE WORLD.</span><span>Telegram · X · YouTube</span></footer>
    </main>`;
  setText('#login-error', message);
  $('#login-form').addEventListener('submit', async (event) => {
    event.preventDefault(); const button = $('.login-submit'), input = $('#access-code');
    button.disabled = true; button.querySelector('span').textContent = '正在连接…'; setText('#login-error', '');
    try {
      const auth = await api('/api/auth/session', { method: 'POST', body: JSON.stringify({ token: input.value.trim() }) });
      input.value = ''; state.csrf = auth.csrf_token || '';
      if (!state.csrf) { const me = await api('/api/auth/me'); state.csrf = me.csrf_token || ''; }
      state.session = true; await showDashboard();
    } catch (error) { setText('#login-error', error.message); input.focus(); button.disabled = false; button.querySelector('span').textContent = '进入观测站'; }
  });
}

async function showDashboard() {
  const params = new URLSearchParams(location.search);
  for (const key of ['q', 'source', 'category']) if (params.has(key)) state.filters[key] = params.get(key).slice(0, 200);
  if (['importance', 'event_time', 'discovered'].includes(params.get('sort'))) state.filters.sort = params.get('sort');
  app.innerHTML = `
    <header class="topbar">
      <a class="brand" href="/" aria-label="FRONTIER 前沿观测站首页">${icon('globe', 'brand-symbol')}<span>FRONTIER<span class="brand-sub">前沿观测站</span></span></a>
      <nav class="main-nav" aria-label="主导航"><button id="nav-world" class="nav-button active" aria-current="page">全球观测</button><button id="nav-bookmarks" class="nav-button">我的收藏</button></nav>
      <div class="topbar-actions"><button id="health-button" class="health-button" aria-label="查看数据源运行状态">${icon('activity')}<span id="connection-label">正在连接</span><span id="connection-dot" class="status-dot checking"></span></button><span class="topbar-divider"></span><button id="refresh" class="icon-button" title="刷新数据" aria-label="刷新数据">${icon('refresh')}</button><button id="logout" class="icon-button" title="退出登录" aria-label="退出登录">${icon('logout')}</button></div>
    </header>
    <main class="dashboard">
      <section class="intro" aria-labelledby="page-title">
        <div><div class="eyebrow">A WORLD IN MOTION <span class="eyebrow-line"></span></div><h1 id="page-title">捕捉世界的<span>下一刻。</span></h1><p>从全球信号，到有据可循的事件。</p></div>
        <div class="global-stats" aria-label="全库事件统计"><div><strong id="stat-total">—</strong><span>已收录事件</span></div><div><strong id="stat-located">—</strong><span>已定位事件</span></div><div><strong id="stat-undated">—</strong><span>时间待确认</span></div></div>
      </section>
      <div id="connection-banner" class="connection-banner" role="status" hidden></div>
      <section class="filter-bar" aria-label="筛选事件">
        <label class="search-box">${icon('search')}<input id="search" type="search" placeholder="搜索事件、关键词…" aria-label="搜索事件或关键词" maxlength="200"/><kbd>/</kbd></label>
        <div class="filter-divider"></div>
        <label class="select-wrap"><span class="sr-only">来源平台</span><select id="source-filter"><option value="">全部来源</option><option value="telegram">Telegram</option><option value="x">X</option><option value="youtube">YouTube</option></select></label>
        <label class="select-wrap"><span class="sr-only">事件类别</span><select id="category-filter"><option value="">全部领域</option></select></label>
        <button id="date-toggle" class="filter-button" aria-expanded="false" aria-controls="date-panel">${icon('clock')}<span id="date-label">全部事件时间</span></button>
        <div class="filter-spacer"></div>
        <button id="clear-filters" class="text-button" hidden>清除筛选</button>
        <button id="view-toggle" class="icon-button" title="切换纯列表视图" aria-label="切换纯列表视图" aria-pressed="false">${icon('list')}</button>
        <button id="export" class="icon-button" title="导出当前筛选结果" aria-label="导出当前筛选结果">${icon('download')}</button>
      </section>
      <section id="date-panel" class="date-panel" aria-label="按事件发生日期筛选" hidden>
        <div><strong>事件发生时间</strong><p>按北京时间筛选。时间未确认的事件不会进入日期区间。</p></div>
        <div class="date-presets"><button data-days="1">今日事件</button><button data-days="7">近 7 天</button><button data-days="30">近 30 天</button><button data-days="0">全部时间</button></div>
        <form id="date-form"><label>从<input id="date-after" type="date"/></label><span>—</span><label>至<input id="date-before" type="date"/></label><button class="primary-button small" type="submit">应用</button></form><p id="date-error" class="form-error" role="alert"></p>
      </section>
      <section class="workspace" id="workspace">
        <section class="map-panel" aria-labelledby="globe-title">
          <div class="map-hud"><div><span class="eyebrow">THE LIVING ATLAS</span><h2 id="globe-title">全球事件图谱</h2></div><span class="map-live"><span class="small-dot"></span><span id="map-mode">实时观测</span></span></div>
          <div class="globe-stage" id="globe-stage" role="region" aria-label="可旋转缩放的 3D 事件地球。使用地图控制按钮，或在事件列表中选择新闻。"><div class="globe-loading" id="globe-loading"><span class="spinner"></span><span>正在建立地球视图</span></div></div>
          <div class="orbit-decoration" aria-hidden="true"></div>
          <div class="map-side-label" aria-hidden="true">FRONTIER / EARTH OBSERVATION</div>
          <div class="map-empty" id="map-empty" hidden><span>尚无可落点的事件</span><p>已确认地理位置的讯息将在这里出现。<br>全球性及地点待确认的事件可在列表阅读。</p></div>
          <div class="map-legend"><span><i class="legend-dot gold"></i>高重要性 ≥ 80</span><span><i class="legend-dot teal"></i>事件</span><span>数字表示聚合事件</span></div>
          <div class="map-controls" aria-label="地球控制"><button id="rotate" class="icon-button active" aria-label="暂停地球自转" aria-pressed="true" title="暂停 / 开启自转">${icon('pause')}</button><span></span><button id="zoom-in" class="icon-button zoom-symbol" aria-label="放大地球" title="放大">+</button><button id="zoom-out" class="icon-button zoom-symbol" aria-label="缩小地球" title="缩小">−</button><button id="reset-globe" class="icon-button" aria-label="重置地球视角" title="重置视角">${icon('globe')}</button></div>
          <div class="map-caption"><span id="map-coverage">正在读取事件位置…</span><button id="map-about" class="map-attribution">Natural Earth · 地图说明</button></div>
        </section>
        <aside class="feed-panel" aria-labelledby="feed-title">
          <div class="feed-header"><div><span class="eyebrow">INTELLIGENCE FEED</span><h2 id="feed-title">前沿讯息 <span id="feed-count">—</span></h2></div><label class="sort-wrap"><span class="sr-only">事件排序方式</span><select id="sort"><option value="importance">重要性优先</option><option value="event_time">事件发生时间</option><option value="discovered">最近收录</option></select></label></div>
          <div id="feed-context" class="feed-context">正在连接你的讯息源</div>
          <div class="event-list" id="event-list" tabindex="-1" aria-label="事件列表" aria-busy="true"></div>
          <div class="feed-footer"><span id="feed-loaded">—</span><button id="load-more" class="text-button" hidden>加载更多 ${icon('arrow')}</button></div>
        </aside>
      </section>
      <section class="timeline-panel" aria-labelledby="timeline-title">
        <div class="timeline-heading"><div><span class="eyebrow">EVENT TIMELINE</span><h2 id="timeline-title">沿时间，回看世界</h2></div><p id="timeline-note">仅回放有明确发生时间的已加载事件</p><button id="exit-replay" class="text-button" hidden>返回实时观测</button></div>
        <div class="timeline-body"><button id="replay" class="replay-button" aria-label="按事件发生时间回放" disabled>${icon('play')}</button><div class="timeline-track-wrap"><div id="timeline-bars" class="timeline-bars" aria-hidden="true"></div><input id="timeline-slider" type="range" min="0" max="1000" value="1000" step="1" aria-label="事件时间回放进度" disabled/><div class="timeline-labels"><span id="timeline-start">等待事件时间</span><strong id="timeline-current">全部已加载事件</strong><span id="timeline-end">—</span></div></div></div>
      </section>
      <footer class="site-footer"><span><span class="small-dot"></span> 观察世界，保持好奇。</span><span id="last-updated">等待首次同步</span><span>时间显示：Asia/Shanghai · 北京时间</span></footer>
    </main>
    <dialog id="detail-dialog" class="detail-dialog" aria-labelledby="detail-title"><div class="dialog-top"><span class="eyebrow">EVENT INTELLIGENCE</span><button class="icon-button dialog-close" aria-label="关闭详情">${icon('close')}</button></div><div id="detail-content"></div></dialog>
    <dialog id="health-dialog" class="health-dialog" aria-labelledby="health-title"><div class="dialog-top"><div><span class="eyebrow">OBSERVATORY STATUS</span><h2 id="health-title">数据源与处理状态</h2></div><button class="icon-button dialog-close" aria-label="关闭运行状态">${icon('close')}</button></div><div id="health-content"></div></dialog>
    <dialog id="cluster-dialog" class="cluster-dialog" aria-labelledby="cluster-title"><div class="dialog-top"><h2 id="cluster-title">此区域的事件</h2><button class="icon-button dialog-close" aria-label="关闭区域事件">${icon('close')}</button></div><div id="cluster-content"></div></dialog>`;
  bindDashboard(); syncFilterInputs(); renderSkeletons();
  initGlobe();
  await Promise.allSettled([loadEvents(), loadStatus()]);
  state.refreshTimer = setInterval(() => { if (state.session && !document.hidden && navigator.onLine) { loadEvents({ silent: true }); loadStatus(); } }, 20000);
}

async function initGlobe() {
  try {
    const { FrontierGlobe } = await import('./globe.js');
    if (!state.session || !$('#globe-stage')) return;
    state.globe = new FrontierGlobe($('#globe-stage'), {
      onSelect: openEvent,
      onCluster: openCluster,
      onRotate: (enabled) => { const b = $('#rotate'); if (!b) return; b.innerHTML = icon(enabled ? 'pause' : 'play'); b.setAttribute('aria-pressed', String(enabled)); b.setAttribute('aria-label', enabled ? '暂停地球自转' : '开启地球自转'); b.classList.toggle('active', enabled); },
      onFallback: globeFallback
    });
    $('#globe-loading')?.remove(); updateGlobe();
  } catch (error) { globeFallback('此设备暂不支持 3D 地球。所有事件仍可通过列表、筛选与时间轴阅读。'); }
}

function globeFallback(message) {
  $('#globe-loading')?.remove();
  const stage = $('#globe-stage'); if (!stage) return;
  const box = el('div', 'globe-fallback'); box.innerHTML = `${icon('globe')}<h3>以列表继续观测</h3>`; box.append(el('p', '', message));
  const button = el('button', 'primary-button small', '切换列表视图'); button.onclick = () => setView('list'); box.append(button); stage.append(box);
  $('.map-controls').hidden = true; $('#map-empty').hidden = true;
}

function bindDashboard() {
  $('#refresh').onclick = async () => { if (state.loading) return; stopReplay(); state.cutoff = null; state.paginationPaused = false; await Promise.allSettled([loadEvents(), loadStatus()]); };
  $('#logout').onclick = async () => {
    try { await api('/api/auth/logout', { method: 'POST', body: '{}' }); state.csrf = ''; showLogin('你已安全退出。'); }
    catch (error) { toast(error.message); }
  };
  $('#nav-world').onclick = () => { state.filters.bookmarked = false; applyFilters(); };
  $('#nav-bookmarks').onclick = () => { state.filters.bookmarked = true; applyFilters(); };
  let searchTimer;
  $('#search').addEventListener('input', (e) => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.filters.q = e.target.value.trim(); applyFilters(); }, 350); });
  $('#source-filter').onchange = (e) => { state.filters.source = e.target.value; applyFilters(); };
  $('#category-filter').onchange = (e) => { state.filters.category = e.target.value; applyFilters(); };
  $('#sort').onchange = (e) => { state.filters.sort = e.target.value; applyFilters(); };
  $('#date-toggle').onclick = () => { const expanded = $('#date-panel').hidden; $('#date-panel').hidden = !expanded; $('#date-toggle').setAttribute('aria-expanded', String(expanded)); };
  $('#date-form').onsubmit = (e) => {
    e.preventDefault(); const after = $('#date-after').value, before = $('#date-before').value;
    if (after && before && after > before) { setText('#date-error', '起始日期应早于或等于结束日期。'); return; }
    state.filters.after = after; state.filters.before = before; setText('#date-error', '');
    $('#date-panel').hidden = true; $('#date-toggle').setAttribute('aria-expanded', 'false'); applyFilters();
  };
  document.querySelectorAll('[data-days]').forEach((button) => { button.onclick = () => {
    const days = Number(button.dataset.days), today = new Date();
    const chinaDay = (date) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
    state.filters.after = days ? chinaDay(new Date(today.getTime() - (days - 1) * 86400000)) : '';
    state.filters.before = days ? chinaDay(today) : '';
    $('#date-panel').hidden = true; $('#date-toggle').setAttribute('aria-expanded', 'false'); applyFilters();
  }; });
  $('#clear-filters').onclick = () => { state.filters = { sort: state.filters.sort, q: '', source: '', category: '', after: '', before: '', bookmarked: state.filters.bookmarked }; applyFilters(); };
  $('#view-toggle').onclick = () => setView(state.view === 'globe' ? 'list' : 'globe');
  $('#export').onclick = exportEvents;
  $('#health-button').onclick = () => { renderHealth(); openDialog($('#health-dialog')); loadStatus(); };
  $('#load-more').onclick = () => loadEvents({ append: true });
  $('#rotate').onclick = () => state.globe?.setAutoRotate(!state.globe.controls.autoRotate, true);
  $('#zoom-in').onclick = () => state.globe?.zoom(1);
  $('#zoom-out').onclick = () => state.globe?.zoom(-1);
  $('#reset-globe').onclick = () => state.globe?.reset();
  $('#map-about').onclick = () => toast('地图采用 Natural Earth 公共领域数据，边界仅供地理识别。点位来自事件文本；城市或国家级定位不代表精确发生地址。');
  $('#replay').onclick = toggleReplay;
  $('#timeline-slider').oninput = (event) => { stopReplay(); setReplay(Number(event.target.value)); };
  $('#exit-replay').onclick = exitReplay;
  document.querySelectorAll('dialog').forEach((dialog) => {
    dialog.querySelector('.dialog-close').onclick = () => dialog.close();
    dialog.addEventListener('click', (e) => { if (e.target === dialog) { const r = dialog.getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) dialog.close(); } });
    dialog.addEventListener('close', () => { if (dialog.id === 'detail-dialog') { state.selected = null; state.globe?.setSelected(null); document.querySelectorAll('.event-card.selected').forEach((n) => n.classList.remove('selected')); } });
  });
}

function syncFilterInputs() {
  if (!$('#search')) return;
  if (document.activeElement !== $('#search')) $('#search').value = state.filters.q;
  $('#source-filter').value = state.filters.source; $('#sort').value = state.filters.sort;
  $('#date-after').value = state.filters.after; $('#date-before').value = state.filters.before;
  const f = state.filters;
  setText('#date-label', f.after || f.before ? `${f.after || '最早'} → ${f.before || '至今'}` : '全部事件时间');
  $('#date-toggle').classList.toggle('active', Boolean(f.after || f.before));
  $('#clear-filters').hidden = !Boolean(f.q || f.source || f.category || f.after || f.before);
  $('#nav-world').classList.toggle('active', !f.bookmarked); $('#nav-bookmarks').classList.toggle('active', f.bookmarked);
  $('#nav-world').setAttribute('aria-current', f.bookmarked ? 'false' : 'page'); $('#nav-bookmarks').setAttribute('aria-current', f.bookmarked ? 'page' : 'false');
}

function applyFilters() {
  stopReplay(); state.cutoff = null; state.items = []; state.cluster = null; state.paginationPaused = false;
  syncFilterInputs();
  const url = new URL(location.href);
  for (const key of ['q', 'source', 'category', 'sort']) state.filters[key] ? url.searchParams.set(key, state.filters[key]) : url.searchParams.delete(key);
  history.replaceState(null, '', `${url.pathname}${url.search}`);
  loadEvents();
}

function renderSkeletons() {
  const list = $('#event-list'); if (!list) return; list.replaceChildren();
  for (let i = 0; i < 5; i++) { const card = el('div', 'skeleton-card'); card.setAttribute('aria-hidden', 'true'); card.innerHTML = '<span></span><div></div><div></div><p></p>'; list.append(card); }
}

async function loadEvents({ append = false, silent = false } = {}) {
  if (!state.session) return;
  if (silent && state.loading) return;
  // Preserve the user's historical scope during replay or pagination. Health still polls.
  if (silent && (state.cutoff != null || state.paginationPaused)) return;
  const requestId = ++state.requestId;
  state.loading = true; $('#event-list')?.setAttribute('aria-busy', 'true'); $('#refresh')?.classList.add('refreshing');
  if (!silent && !append && !state.items.length) renderSkeletons();
  if ($('#load-more')) $('#load-more').disabled = true;
  const query = makeQuery(state.filters, append ? state.items.length : 0);
  try {
    const data = await api(`/api/events?${query}`);
    if (requestId !== state.requestId || !state.session) return;
    const incoming = Array.isArray(data.items) ? data.items : [];
    for (const item of incoming) {
      const override = state.bookmarkOverrides.get(item.id);
      if (override) {
        if (Boolean(item.bookmarked) === override.value || Date.now() > override.expires) state.bookmarkOverrides.delete(item.id);
        else item.bookmarked = override.value;
      }
    }
    const previous = new Set(state.items.map((item) => item.id));
    state.newIds = silent ? new Set(incoming.filter((item) => !previous.has(item.id)).map((item) => item.id)) : new Set();
    state.items = append ? [...state.items, ...incoming.filter((item) => !previous.has(item.id))] : incoming;
    state.paginationPaused = append;
    state.total = Math.max(0, Number(data.total) || 0); state.stats = data.stats || {}; state.facets = data.facets || {};
    state.fetchedAt = new Date(); state.failCount = 0;
    renderStats(); renderCategories(); renderFeed(); renderTimeline(); updateGlobe(); updateConnection();
    renderSyncTime();
    if (!silent) announce(`已载入 ${state.items.length} 个事件，共 ${state.total} 个匹配结果。`);
    if (state.newIds.size) toast(`捕捉到 ${state.newIds.size} 条新收录事件`);
  } catch (error) {
    if (requestId !== state.requestId || error.status === 401) return;
    state.failCount++; updateConnection(error.message);
    if (!state.items.length) renderFeedError(error.message); else if (!silent) toast(error.message);
  } finally {
    if (requestId === state.requestId) { state.loading = false; $('#event-list')?.setAttribute('aria-busy', 'false'); $('#refresh')?.classList.remove('refreshing'); if ($('#load-more')) $('#load-more').disabled = false; }
  }
}

async function loadStatus() {
  try { const data = await api('/api/status'); if (!state.session) return; state.status = data; updateConnection(); if ($('#health-dialog')?.open) renderHealth(); }
  catch (error) { if (error.status !== 401 && !state.fetchedAt) updateConnection(error.message); }
}

function renderStats() {
  setText('#stat-total', num(state.stats.total)); setText('#stat-located', num(state.stats.located)); setText('#stat-undated', num(state.stats.undated));
}

function renderCategories() {
  const select = $('#category-filter'); if (!select) return;
  const facets = normalizeFacets(state.facets.categories);
  const options = [new Option('全部领域', '')];
  for (const facet of facets) options.push(new Option(`${categoryLabel(facet.value)}${facet.count != null ? ` · ${num(facet.count)}` : ''}`, facet.value));
  if (state.filters.category && !facets.some((f) => f.value === state.filters.category)) options.push(new Option(categoryLabel(state.filters.category), state.filters.category));
  select.replaceChildren(...options); select.value = state.filters.category;
}

function shownItems() { return replayItems(state.items, state.cutoff); }

function renderFeed() {
  const list = $('#event-list'); if (!list) return;
  const active = document.activeElement;
  const activeCard = list.contains(active) ? active.closest('.event-card') : null;
  const focusId = activeCard?.dataset.id;
  const focusSelector = active?.classList.contains('bookmark-button') ? '.bookmark-button' : '.event-open';
  const scrollTop = list.scrollTop;
  const events = shownItems(); list.replaceChildren();
  const countNode = el('span', '', num(state.cutoff == null ? state.total : events.length)); countNode.id = 'feed-count';
  const title = $('#feed-title'); title.replaceChildren(document.createTextNode(state.filters.bookmarked ? '我的收藏 ' : '前沿讯息 '), countNode);
  const sortDescription = state.filters.sort === 'event_time' ? '按事件发生时间排列 · 未知时间保留明确标记' : state.filters.sort === 'discovered' ? '按本站收录时间排列' : '综合影响、范围、新颖性与时效性';
  setText('#feed-context', state.cutoff == null ? sortDescription : `回放至 ${formatDate(new Date(state.cutoff))} · 仅显示已知事件时间`);
  if (!events.length) {
    const empty = el('div', 'empty-state'); empty.innerHTML = icon(state.filters.bookmarked ? 'bookmark' : 'search');
    empty.append(el('h3', '', state.cutoff != null ? '这个时刻，尚无事件' : state.filters.bookmarked ? '收藏你关心的变化' : state.total === 0 && !(state.filters.q || state.filters.category || state.filters.source || state.filters.after || state.filters.before) ? '正在等待世界的信号' : '没有找到匹配事件'));
    empty.append(el('p', '', state.filters.bookmarked ? '打开事件详情，点击收藏，即可在这里持续回看。' : state.cutoff != null ? '拖动下方时间轴，继续探索已加载事件。' : '可以调整关键词、来源或时间范围。新收录的事件会自动出现在这里。'));
    list.append(empty);
  } else events.forEach((event, index) => list.append(eventCard(event, index)));
  setText('#feed-loaded', state.cutoff == null ? `已加载 ${num(state.items.length)} / ${num(state.total)}` : `回放显示 ${num(events.length)} / ${num(state.items.length)}`);
  $('#load-more').hidden = state.items.length >= state.total || state.cutoff != null;
  list.scrollTop = scrollTop;
  if (focusId) {
    const replacement = [...list.querySelectorAll('.event-card')].find((card) => card.dataset.id === focusId)?.querySelector(focusSelector);
    if (replacement) replacement.focus({ preventScroll: true });
    else list.focus({ preventScroll: true });
  }
}

function eventCard(event, index = 0, compact = false) {
  const card = el('article', `event-card${event.id === state.selected ? ' selected' : ''}${state.newIds.has(event.id) ? ' new-event' : ''}${compact ? ' compact' : ''}`);
  card.dataset.id = event.id;
  const main = el('button', 'event-open'); main.type = 'button'; main.setAttribute('aria-label', `阅读事件：${event.title || '未命名事件'}`);
  const top = el('div', 'event-top');
  const category = el('span', 'category-tag', categoryLabel(event.category));
  const score = el('span', `importance-score ${importance(event) >= 80 ? 'high' : ''}`); score.append(el('span', '', String(importance(event))), document.createTextNode(' 重要性')); score.title = event.score_reason || '查看详情了解评分依据';
  top.append(category, score);
  main.append(top, el('h3', '', event.title || '未命名事件'));
  if (event.summary) main.append(el('p', 'event-summary', event.summary));
  const meta = el('div', 'event-meta');
  const place = el('span', coordinates(event).length ? '' : 'uncertain'); place.innerHTML = icon('pin'); place.append(document.createTextNode(locationLabel(event)));
  const time = el('span', knownEventTime(event) ? '' : 'uncertain'); time.innerHTML = icon('clock'); time.append(document.createTextNode(eventTime(event, true)));
  meta.append(place, time); main.append(meta);
  main.onclick = () => openEvent(event.id);
  const bottom = el('div', 'event-bottom');
  const sources = el('div', 'event-sources');
  const platforms = [...new Set((Array.isArray(event.sources) ? event.sources : []).map((s) => s.platform).filter(Boolean))];
  if (platforms.length) platforms.forEach((p) => sources.append(el('span', `source-chip source-${p}`, sourceLabel(p))));
  else sources.append(el('span', 'source-chip', '来源待处理'));
  if (event.confidence === 'multi_source') sources.append(el('span', 'verified', '多源交叉'));
  else if (event.enrichment_status === 'needs_review' || event.confidence === 'needs_review') sources.append(el('span', 'review-badge', '待核实'));
  const save = el('button', `bookmark-button ${event.bookmarked ? 'saved' : ''}`); save.type = 'button'; save.innerHTML = icon('bookmark');
  save.setAttribute('aria-label', event.bookmarked ? '取消收藏此事件' : '收藏此事件'); save.setAttribute('aria-pressed', String(Boolean(event.bookmarked))); save.title = event.bookmarked ? '已收藏' : '收藏事件';
  save.onclick = (e) => { e.stopPropagation(); toggleBookmark(event.id); };
  bottom.append(sources, save); card.append(main, bottom); return card;
}

function renderFeedError(message) {
  const list = $('#event-list'); if (!list) return;
  const box = el('div', 'empty-state'); box.innerHTML = icon('activity'); box.append(el('h3', '', '暂时未连接到讯息站'), el('p', '', message));
  const button = el('button', 'primary-button small', '重新连接'); button.onclick = () => { loadEvents(); loadStatus(); }; box.append(button); list.replaceChildren(box);
  setText('#feed-context', '连接恢复后将继续同步'); setText('#map-coverage', '等待数据连接');
}

function updateConnection(errorMessage = '') {
  if (!$('#connection-label')) return;
  const banner = $('#connection-banner');
  const sources = Array.isArray(state.status?.sources) ? state.status.sources : [];
  const badSources = sources.filter((s) => ['degraded', 'offline', 'error', 'unavailable'].includes(s.state));
  const serviceState = typeof state.status?.service === 'string' ? state.status.service : state.status?.service?.state;
  let label = state.fetchedAt ? '数据已连接' : '正在连接', mode = state.fetchedAt ? 'healthy' : 'checking';
  if (!navigator.onLine) { label = '当前离线'; mode = 'offline'; }
  else if (state.failCount || errorMessage) { label = '连接中断'; mode = 'degraded'; }
  else if (badSources.length || serviceState === 'degraded') { label = '部分来源异常'; mode = 'partial'; }
  else if (state.status?.enrichment?.state === 'daily_limit') { label = '今日整理额度已用完'; mode = 'partial'; }
  setText('#connection-label', label); $('#connection-dot').className = `status-dot ${mode}`;
  banner.hidden = !(state.failCount || !navigator.onLine || errorMessage);
  if (!banner.hidden) banner.textContent = !navigator.onLine ? '网络已离线。当前展示最近一次成功加载的数据，联网后自动继续同步。' : `${errorMessage || '服务器连接暂时中断。'}${state.fetchedAt ? ` 当前保留 ${elapsed(state.fetchedAt)}同步的数据。` : ''}`;
  setText('#map-mode', state.cutoff != null ? '事件时间回放' : mode === 'healthy' || mode === 'partial' ? '实时观测' : '等待连接');
}

function renderSyncTime() {
  if (!state.fetchedAt) return;
  const stamp = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(state.fetchedAt);
  const mode = state.cutoff != null ? '回放期间暂停列表更新' : state.paginationPaused ? '分页阅读中 · 点击刷新回到最新' : '每 20 秒刷新';
  setText('#last-updated', `最近同步 ${stamp} · ${mode}`);
}

function updateGlobe() {
  const items = shownItems(), located = items.filter((e) => coordinates(e).length);
  state.globe?.setEvents(items, state.newIds);
  setText('#map-coverage', `当前 ${num(items.length)} 个事件 · ${num(located.length)} 个可定位 · ${num(items.length - located.length)} 个全球性或地点待确认`);
  const empty = $('#map-empty'); if (empty) empty.hidden = located.length > 0 || !state.fetchedAt || Boolean($('.globe-fallback'));
}

function setView(view) {
  state.view = view; $('#workspace').classList.toggle('list-view', view === 'list');
  $('#view-toggle').innerHTML = icon(view === 'list' ? 'globe' : 'list');
  $('#view-toggle').setAttribute('aria-pressed', String(view === 'list'));
  $('#view-toggle').setAttribute('aria-label', view === 'list' ? '切换地球视图' : '切换纯列表视图');
  if (view === 'globe') requestAnimationFrame(() => state.globe?.resize());
}

function openDialog(dialog) {
  state.globe?.setAutoRotate(false);
  document.querySelectorAll('dialog[open]').forEach((d) => { if (d !== dialog) d.close(); });
  if (!dialog.open) dialog.showModal();
}

async function openEvent(id) {
  state.selected = id; const dialog = $('#detail-dialog'); const content = $('#detail-content');
  let event = state.items.find((item) => item.id === id) || state.cluster?.find((item) => item.id === id);
  if (event) { renderDetail(event); state.globe?.focus(event); }
  else { content.replaceChildren(el('div', 'detail-loading', '正在加载事件详情…')); }
  openDialog(dialog); dialog.scrollTop = 0; state.selected = id; state.globe?.setSelected(id);
  document.querySelectorAll('.event-card').forEach((card) => card.classList.toggle('selected', card.dataset.id === String(id)));
  try {
    const data = await api(`/api/events/${encodeURIComponent(id)}`);
    if (state.selected !== id || !dialog.open) return;
    event = data.item || data;
    const override = state.bookmarkOverrides.get(id);
    if (override && Date.now() <= override.expires) event.bookmarked = override.value;
    renderDetail(event);
  } catch (error) { if (error.status !== 401 && state.selected === id) { if (!event) content.replaceChildren(el('p', 'form-error', error.message)); else toast(`保留已加载详情：${error.message}`); } }
}

function detailSection(title, body) { const section = el('section', 'detail-section'); section.append(el('h3', '', title), body); return section; }
function renderDetail(event) {
  const content = $('#detail-content'); if (!content) return;
  const sameEvent = content.dataset.event === String(event.id);
  const scrollTop = $('#detail-dialog').scrollTop;
  const expandedSources = sameEvent ? [...content.querySelectorAll('.source-text')].map((node) => node.open) : [];
  const activeLabel = sameEvent && content.contains(document.activeElement) ? document.activeElement?.getAttribute('aria-label') : null;
  const focusedSave = sameEvent && document.activeElement?.classList.contains('detail-save');
  content.replaceChildren(); content.dataset.event = String(event.id);
  const heading = el('div', 'detail-heading'); heading.append(el('span', 'category-tag', categoryLabel(event.category)));
  const status = event.confidence === 'multi_source' ? '多源交叉印证' : event.confidence === 'needs_review' || event.enrichment_status === 'needs_review' ? '信息待核实' : '单一来源 · 建议结合原文判断';
  heading.append(el('span', event.confidence === 'multi_source' ? 'verified' : 'uncertain', status));
  const title = el('h1', 'detail-title', event.title || '未命名事件'); title.id = 'detail-title';
  content.append(heading, title, el('p', 'detail-summary', event.summary || '事件摘要正在处理中。'));
  const actions = el('div', 'detail-actions');
  const save = el('button', `primary-button small detail-save ${event.bookmarked ? 'saved' : ''}`); save.innerHTML = icon(event.bookmarked ? 'check' : 'bookmark'); save.append(document.createTextNode(event.bookmarked ? '已收藏' : '收藏事件')); save.dataset.event = event.id; save.setAttribute('aria-pressed', String(Boolean(event.bookmarked))); save.onclick = () => toggleBookmark(event.id, event); actions.append(save);
  const locate = el('button', 'secondary-button small', '在地球上定位'); locate.disabled = !coordinates(event).length; locate.onclick = () => { $('#detail-dialog').close(); setView('globe'); state.globe?.focus(event); $('#globe-stage').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'center' }); }; actions.append(locate);
  content.append(actions);
  const facts = el('div', 'detail-facts');
  const timeFact = el('div'); timeFact.append(el('span', 'fact-label', '事件发生时间'), el('strong', '', eventTime(event)), el('p', 'fact-note', ({ explicit: '原文明确时间', inferred: '根据上下文推定', scheduled: '计划发生 · 尚未发生', unknown: '原文尚不足以确认' }[event.event_time_status] || '时间依据待确认')));
  const placeFact = el('div'); placeFact.append(el('span', 'fact-label', '事件位置'), el('strong', '', locationLabel(event)), el('p', 'fact-note', coordinates(event).map((l) => ({ city: '城市级定位', country: '国家级定位', region: '地区级定位', exact: '精确地点', approximate: '近似位置' }[l.precision] || '原文提及地点')).join(' · ') || '保留地理不确定性'));
  facts.append(timeFact, placeFact); content.append(facts);
  if (event.event_time_evidence) content.append(detailSection('时间依据', el('blockquote', 'evidence', event.event_time_evidence)));
  const locations = coordinates(event); if (locations.some((l) => l.evidence)) {
    const box = el('div', 'location-evidence'); locations.forEach((l) => { if (l.evidence) { const p = el('p'); p.append(el('strong', '', `${l.name || '地点'}：`), document.createTextNode(l.evidence)); box.append(p); } }); content.append(detailSection('地理依据', box));
  }
  const scoring = el('div', 'scoring'); const scoreTitle = el('div', 'score-head'); scoreTitle.append(el('strong', '', String(importance(event))), el('span', '', '/ 100 重要性')); scoring.append(scoreTitle);
  const components = event.score_components || {};
  for (const [key, label] of [['impact', '影响程度'], ['scope', '影响范围'], ['novelty', '信息新颖性'], ['urgency', '时效性']]) {
    if (components[key] == null) continue;
    const row = el('div', 'score-row'), track = el('span', 'score-track'), fill = el('i'); fill.style.width = `${clamp(components[key], 0, 100)}%`; track.append(fill); row.append(el('span', '', label), track, el('span', '', String(components[key]))); scoring.append(row);
  }
  scoring.append(el('p', 'score-reason', event.score_reason || '该分数用于发现值得关注的事件，不代表事实真实性。')); content.append(detailSection('为什么值得关注', scoring));
  if (Array.isArray(event.tags) && event.tags.length) { const tags = el('div', 'detail-tags'); event.tags.forEach((tag) => tags.append(el('span', '', `# ${tag}`))); content.append(tags); }
  const sourceBox = el('div', 'source-list');
  const sources = Array.isArray(event.sources) ? event.sources : [];
  if (!sources.length) sourceBox.append(el('p', 'muted', '来源信息正在整理。'));
  sources.forEach((source) => {
    const sourceCard = el('article', 'source-detail'); const head = el('div', 'source-detail-head'); head.append(el('span', 'source-chip', sourceLabel(source.platform)), el('strong', '', source.name || sourceLabel(source.platform)));
    const url = safeURL(source.url);
    if (url) { const link = el('a', 'source-link', '查看原文 '); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; const svg = el('span'); svg.innerHTML = icon('external'); link.append(svg); head.append(link); }
    sourceCard.append(head, el('p', 'source-published', `来源发布时间 ${formatDate(source.published_at, true)}`));
    if (source.text) { const details = el('details', 'source-text'); details.append(el('summary', '', '展开原始内容'), el('p', '', source.text)); sourceCard.append(details); }
    sourceBox.append(sourceCard);
  });
  content.append(detailSection(`原始来源 · ${sources.length}`, sourceBox));
  content.append(el('p', 'detail-disclaimer', '摘要、时间、地点和重要性由自动处理辅助整理，保留原文依据。单一来源及推定信息需结合原文判断。'));
  const provenance = el('div', 'provenance'); provenance.append(el('span', '', `本站收录 ${formatDate(event.ingested_at, true)}`), el('span', '', `来源发布 ${formatDate(event.source_published_at, true)}`)); content.append(provenance);
  if (sameEvent) {
    content.querySelectorAll('.source-text').forEach((node, index) => { node.open = Boolean(expandedSources[index]); });
    $('#detail-dialog').scrollTop = scrollTop;
    if (focusedSave) content.querySelector('.detail-save')?.focus({ preventScroll: true });
    else if (activeLabel) [...content.querySelectorAll('[aria-label]')].find((node) => node.getAttribute('aria-label') === activeLabel)?.focus({ preventScroll: true });
  }
}

async function toggleBookmark(id, detailEvent = null) {
  if (state.busyBookmark.has(id)) return;
  const event = state.items.find((item) => item.id === id) || detailEvent;
  if (!event) return;
  state.busyBookmark.add(id); const desired = !Boolean(event.bookmarked);
  document.querySelectorAll('.bookmark-button, .detail-save').forEach((b) => { if (b.dataset.event === String(id) || b.closest('.event-card')?.dataset.id === String(id)) b.disabled = true; });
  try {
    const result = await api(`/api/events/${encodeURIComponent(id)}/bookmark`, { method: 'PUT', body: JSON.stringify({ bookmarked: desired }) });
    event.bookmarked = typeof result.bookmarked === 'boolean' ? result.bookmarked : desired;
    state.bookmarkOverrides.set(id, { value: event.bookmarked, expires: Date.now() + 60000 });
    const cached = state.items.find((e) => e.id === id); if (cached) cached.bookmarked = event.bookmarked;
    renderFeed(); if (state.selected === id) renderDetail(event);
    toast(event.bookmarked ? '已加入我的收藏' : '已取消收藏');
    if (state.filters.bookmarked && !event.bookmarked) { state.items = state.items.filter((e) => e.id !== id); state.total = Math.max(0, state.total - 1); renderFeed(); updateGlobe(); renderTimeline(); }
  } catch (error) { if (error.status !== 401) toast(error.message); }
  finally { state.busyBookmark.delete(id); document.querySelectorAll('.bookmark-button, .detail-save').forEach((b) => { b.disabled = false; }); }
}

function openCluster(events, name) {
  state.cluster = events; setText('#cluster-title', `${name || '此区域'} · ${events.length} 个事件`);
  const content = $('#cluster-content'); content.replaceChildren(...events.map((e, i) => eventCard(e, i, true))); openDialog($('#cluster-dialog'));
}

function renderHealth() {
  const content = $('#health-content'); if (!content) return; content.replaceChildren();
  const status = state.status;
  if (!status) { content.append(el('p', 'empty-state', '尚未取得服务器运行状态。')); return; }
  const sources = Array.isArray(status.sources) ? status.sources : [];
  const description = el('p', 'health-lead', '平台状态来自服务器的实际采集结果。历史记录数与最新成功时间分别显示，避免把存量内容当作实时连通。'); content.append(description);
  for (const source of sources) {
    const card = el('section', 'health-source'); const heading = el('div', 'health-source-head');
    heading.append(el('h3', '', sourceLabel(source.platform)), el('span', `health-tag ${source.state}`, stateLabel(source.state))); card.append(heading);
    const facts = el('div', 'health-source-facts'); facts.append(el('span', '', `${num(source.records)} 条历史记录`), el('span', '', `最后成功 ${elapsed(source.last_success_at)}`)); card.append(facts);
    if (source.error) card.append(el('p', 'health-error', source.error)); content.append(card);
  }
  const enrichment = status.enrichment || {}, collector = status.collector || {};
  const section = el('section', 'health-processing'); section.append(el('h3', '', '事件理解与结构化'));
  const facts = el('div', 'processing-stats');
  for (const [key, label] of [['completed', '已处理'], ['pending', '待处理'], ['failed', '处理失败']]) { const box = el('div'); box.append(el('strong', '', num(enrichment[key])), el('span', '', label)); facts.append(box); } section.append(facts);
  section.append(el('p', 'muted', `处理状态：${stateLabel(enrichment.state)} · 采集调度：${stateLabel(collector.state)}`));
  const usage = enrichment.usage || {};
  const hasLimit = enrichment.daily_limit != null && Number.isFinite(Number(enrichment.daily_limit));
  const hasUsed = usage.items != null && Number.isFinite(Number(usage.items));
  if (hasLimit || hasUsed || enrichment.state === 'daily_limit') {
    const quota = el('div', `quota-card${enrichment.state === 'daily_limit' ? ' is-limited' : ''}`);
    const quotaHead = el('div', 'quota-heading');
    quotaHead.append(el('strong', '', '今日事件整理额度'), el('span', '', `${num(usage.items)} / ${num(enrichment.daily_limit)} 个`));
    quota.append(quotaHead);
    if (hasLimit && hasUsed) {
      const progress = el('progress', 'quota-progress');
      progress.max = Math.max(1, Number(enrichment.daily_limit)); progress.value = clamp(usage.items, 0, progress.max);
      progress.setAttribute('aria-label', `今日已使用 ${num(usage.items)} 个整理额度，总额 ${num(enrichment.daily_limit)} 个`);
      quota.append(progress);
    }
    const queue = enrichment.pending != null ? `仍有 ${num(enrichment.pending)} 个候选事件排队。` : '候选事件排队量待确认。';
    const explanation = enrichment.state === 'daily_limit'
      ? `今日整理已达额度限制。${queue}已有事件可以正常阅读。`
      : `${queue}${hasLimit && hasUsed ? `今日剩余额度 ${num(Math.max(0, Number(enrichment.daily_limit) - Number(usage.items)))} 个。` : ''}`;
    quota.append(el('p', 'quota-note', explanation));
    quota.append(el('p', 'quota-note', '每日整理额度于 UTC 00:00（北京时间 08:00）重置，随后按调度恢复。额度用完后原文采集继续；首次历史回填也计入当天额度。'));
    if (usage.requests != null || usage.prompt_tokens != null || usage.completion_tokens != null) {
      const details = el('details', 'usage-details'); details.append(el('summary', '', '查看今日请求与用量'));
      const usageFacts = el('div', 'usage-facts');
      for (const [key, label] of [['requests', 'API 请求'], ['prompt_tokens', '输入词元'], ['completion_tokens', '输出词元']]) {
        const fact = el('div'); fact.append(el('span', '', label), el('strong', '', num(usage[key]))); usageFacts.append(fact);
      }
      details.append(usageFacts); quota.append(details);
    }
    section.append(quota);
  }
  if (enrichment.last_success_at) section.append(el('p', 'muted', `最近处理成功：${formatDate(enrichment.last_success_at, true)}`));
  if (enrichment.error) section.append(el('p', 'health-error', enrichment.error));
  content.append(section, el('p', 'health-foot', `版本 ${status.version || '—'} · 状态展示时间 ${formatDate(new Date(), true)}`));
}

function timelineBounds() {
  const times = state.items.map(knownEventTime).filter(Boolean).map((d) => d.getTime());
  return times.length ? { min: Math.min(...times), max: Math.max(...times), times } : null;
}
function renderTimeline() {
  const bounds = timelineBounds(); if (!$('#timeline-slider')) return;
  const disabled = !bounds; $('#timeline-slider').disabled = disabled; $('#replay').disabled = disabled;
  $('#timeline-bars').replaceChildren();
  if (!bounds) { setText('#timeline-start', '等待明确的事件时间'); setText('#timeline-end', '—'); setText('#timeline-current', '尚无可回放事件'); setText('#timeline-note', '未知时间的事件保留在列表中，不放入时间轴'); return; }
  const counts = Array(64).fill(0), span = Math.max(1, bounds.max - bounds.min);
  bounds.times.forEach((t) => counts[Math.min(63, Math.floor(((t - bounds.min) / span) * 63))]++);
  const maxCount = Math.max(1, ...counts);
  counts.forEach((count, index) => { const bar = el('span', count ? 'timeline-bar has-events' : 'timeline-bar'); bar.style.height = `${count ? 15 + count / maxCount * 85 : 4}%`; bar.classList.toggle('beyond', state.cutoff != null && bounds.min + index / 63 * span > state.cutoff); $('#timeline-bars').append(bar); });
  setText('#timeline-start', formatDate(new Date(bounds.min))); setText('#timeline-end', formatDate(new Date(bounds.max)));
  setText('#timeline-note', `回放范围：已加载 ${num(state.items.length)} 个事件中的 ${num(bounds.times.length)} 个已知时间事件`);
  $('#exit-replay').hidden = state.cutoff == null;
  if (state.cutoff == null) { $('#timeline-slider').value = '1000'; setText('#timeline-current', '全部已加载事件'); }
  else { $('#timeline-slider').value = String(clamp((state.cutoff - bounds.min) / span * 1000, 0, 1000)); setText('#timeline-current', formatDate(new Date(state.cutoff), true)); }
  $('#timeline-slider').setAttribute('aria-valuetext', state.cutoff == null ? '全部已加载事件' : formatDate(new Date(state.cutoff), true));
}
function setReplay(value) {
  const bounds = timelineBounds(); if (!bounds) return;
  state.cutoff = bounds.min + value / 1000 * (bounds.max - bounds.min);
  state.globe?.setAutoRotate(false); renderFeed(); updateGlobe(); renderTimeline(); updateConnection(); renderSyncTime();
}
function stopReplay() {
  clearInterval(state.replayTimer); state.replayTimer = null;
  if ($('#replay')) { $('#replay').innerHTML = icon('play'); $('#replay').setAttribute('aria-label', '播放事件时间回放'); }
}
function toggleReplay() {
  if (state.replayTimer) { stopReplay(); return; }
  const bounds = timelineBounds(); if (!bounds) return;
  let value = state.cutoff == null || state.cutoff >= bounds.max ? 0 : Number($('#timeline-slider').value);
  setReplay(value); $('#replay').innerHTML = icon('pause'); $('#replay').setAttribute('aria-label', '暂停时间回放');
  state.replayTimer = setInterval(() => { value = Math.min(1000, value + 20); setReplay(value); if (value === 1000) stopReplay(); }, 240);
}
function exitReplay() { stopReplay(); state.cutoff = null; renderFeed(); updateGlobe(); renderTimeline(); updateConnection(); renderSyncTime(); if (!state.paginationPaused) loadEvents({ silent: true }); }

async function exportEvents() {
  const button = $('#export'); button.disabled = true;
  try {
    const query = makeQuery(state.filters); query.delete('offset'); query.set('limit', '200');
    const data = await api(`/api/export?${query}`);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' });
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `frontier-events-${new Date().toISOString().slice(0, 10)}.json`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    toast('已导出当前筛选结果（最多 200 个事件）');
  } catch (error) { if (error.status !== 401) toast(error.message); }
  finally { if (button.isConnected) button.disabled = false; }
}

document.addEventListener('keydown', (event) => {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName) || document.activeElement?.isContentEditable;
  if (event.key === '/' && !typing && !document.querySelector('dialog[open]')) { event.preventDefault(); $('#search')?.focus(); }
});
window.addEventListener('online', () => { if (state.session) { updateConnection(); loadEvents({ silent: true }); loadStatus(); } });
window.addEventListener('offline', () => { if (state.session) { stopReplay(); updateConnection(); } });
document.addEventListener('visibilitychange', () => { if (document.hidden) stopReplay(); else if (state.session && state.fetchedAt && Date.now() - state.fetchedAt.getTime() > 20000) { loadEvents({ silent: true }); loadStatus(); } });

async function start() {
  app.innerHTML = '<div class="app-loading"><span class="spinner"></span><strong>FRONTIER</strong><span>正在连接观测站</span></div>';
  try {
    const auth = await api('/api/auth/me');
    if (!auth.authenticated) { showLogin(); return; }
    state.csrf = auth.csrf_token || ''; state.session = true; await showDashboard();
  } catch (error) { if (error.status !== 401) showLogin(error.message); else if (!$('#login-form')) showLogin(); }
}
start();
