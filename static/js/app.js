/* ═══════════════════════════════════════════════════════════
   PlayTransfer — app.js  v1.1
   OAuth flows, step wizard, polling, sem planos pagos
═══════════════════════════════════════════════════════════ */

// ── State ──────────────────────────────────────────────────
const state = {
  currentStep: 1,
  srcPlatform: null,
  destPlatform: null,
  srcSid: null,
  destSid: null,
  srcDisplayName: null,
  destDisplayName: null,
  youtubePending: {},
  deezerCapturePolls: {},
  deezerTabsOpened: {},
  platforms: {},
  jobId: null,
  eventIdx: 0,
  pollTimer: null,
  transferStats: { found: 0, missing: 0, total: 0 },
  lastResultUrl: '',
};

const deezerTabRefs = {};

const PLATFORM_ICONS = {
  spotify: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#1DB954"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 14.44c-.2.32-.63.42-.95.22-2.6-1.59-5.87-1.95-9.72-1.07-.37.09-.75-.14-.84-.51-.09-.37.14-.75.51-.84 4.21-.96 7.82-.55 10.73 1.24.32.2.42.63.22.96zm1.24-2.76c-.25.4-.78.52-1.18.27-2.98-1.83-7.51-2.36-11.03-1.29-.46.14-.94-.12-1.08-.58-.14-.46.12-.94.58-1.08 4.02-1.22 9.01-.63 12.43 1.47.4.25.52.78.27 1.18zm.1-2.88C14.24 8.85 8.81 8.7 5.54 9.65c-.54.16-1.12-.14-1.28-.69-.16-.54.14-1.12.69-1.28 3.77-1.08 10.04-.87 14 1.52.49.29.65.92.36 1.41-.29.49-.92.65-1.41.36z"/></svg>`,
  deezer:  `<svg viewBox="0 0 24 24" fill="none" style="width:28px;height:28px;color:#A238FF"><path fill="currentColor" d="M4.2 10.3 5.6 7.8 6.9 9.8 8.3 6.6 9.7 10.1 11.1 8.2 12 5.8 12.9 8.2 14.3 10.1 15.7 6.6 17.1 9.8 18.4 7.8 19.8 10.3c0 3.3-2.6 5.6-7.2 9.4a.96.96 0 0 1-1.2 0c-4.6-3.8-7.2-6.1-7.2-9.4Z"/></svg>`,
  youtube: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#FF0000"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`,
  soundcloud: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#FF5500"><path d="M11.56 8.87V17h8.76c.96 0 1.68-.58 1.68-1.56 0-.82-.55-1.46-1.3-1.62.05-.2.08-.4.08-.62 0-1.46-1.14-2.63-2.56-2.63-.16 0-.3.02-.46.05-.17-1.43-1.37-2.55-2.84-2.55C13 8.07 12 8.37 11.56 8.87zM0 15c0 1.1.9 2 2 2s2-.9 2-2V11c0-1.1-.9-2-2-2S0 9.9 0 11v4zm5 0c0 1.1.9 2 2 2s2-.9 2-2V9c0-1.1-.9-2-2-2S5 7.9 5 9v6z"/></svg>`,
  apple:  `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#FC3C44"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>`,
  tidal:  `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#00CCFF"><path d="M12.012 3.992L8.008 7.996 4 3.988 0 7.996l4.004 4.004 4.004-4.004 4.004 4.004 4.008-4.008zM16.016 8 12.008 12.004 16.012 16.008 20.016 12z"/></svg>`,
  amazon: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#00A8E0"><path d="M.045 18.02c.072-.116.187-.124.348-.022 3.636 2.11 7.594 3.166 11.87 3.166 2.852 0 5.668-.533 8.447-1.595l.315-.14c.138-.06.234-.1.293-.13.226-.088.39-.046.493.124.106.172.08.32-.045.436-.7.588-1.518 1.098-2.45 1.528-2.22 1.006-4.558 1.51-7.017 1.51-3.97 0-7.906-1.085-11.14-3.292-.188-.126-.25-.277-.114-.587zM6.54 15.54c-.3-.4-.45-.9-.45-1.5 0-.56.13-1.06.4-1.51.256-.44.634-.75 1.11-.93l1.056-.33.15-.05V7.83c0-.6.16-1.08.48-1.44.3-.37.75-.56 1.35-.56.62 0 1.06.18 1.35.56.3.36.45.84.45 1.44v3.39l1.07.34c.48.16.865.47 1.125.93.27.44.41.94.41 1.51 0 .6-.16 1.11-.467 1.5-.3.4-.73.6-1.28.6-.6 0-1.09-.2-1.48-.6l-1.065-.97-.06-.05-.069.05-1.025.97c-.39.4-.9.6-1.5.6-.55 0-.97-.2-1.28-.6zm-.795-8.955c.22-.47.54-.84.944-1.1.416-.27.9-.4 1.45-.4.437 0 .835.1 1.176.28.35.18.6.44.776.78l.054.1.06-.1c.16-.34.41-.6.76-.78.34-.19.74-.28 1.2-.28.56 0 1.05.14 1.45.4.4.26.72.63.94 1.1.22.48.34 1.03.34 1.67v.34l-.66-.2c-.5-.16-.97-.25-1.42-.25-.37 0-.686.06-.98.17l-.05.02v-1.53c0-.48-.07-.84-.22-1.07-.15-.24-.36-.37-.75-.37s-.63.13-.76.37c-.15.23-.22.59-.22 1.07v1.53l-.05-.02c-.3-.11-.61-.17-.96-.17-.45 0-.92.09-1.43.25l-.66.2v-.34c0-.64.11-1.19.33-1.67z"/></svg>`,
};

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadPlatforms();
  renderPlatformGrids();
  listenOAuthMessages();
  handleOAuthRedirectParams();
});

async function loadPlatforms() {
  try {
    const r = await fetch('/api/platforms');
    state.platforms = await r.json();
  } catch (e) { console.error('Failed to load platforms', e); }
}

// ── OAuth message listener (popup → parent) ─────────────────
function listenOAuthMessages() {
  window.addEventListener('message', (evt) => {
    if (evt.origin !== location.origin) return;
    const d = evt.data;
    if (d.type !== 'oauth_done') return;

    if (d.error) {
      showToast(`Erro ao conectar: ${d.error}`, 'error');
      return;
    }

    if (d.role === 'src') {
      state.srcSid = d.sid;
      state.srcDisplayName = d.displayName;
    } else {
      state.destSid = d.sid;
      state.destDisplayName = d.displayName;
    }

    showToast(`Conectado com sucesso!`, 'success');
    renderConnectForms();
    checkTransferReady();
  });
}

// Handle OAuth redirect back (sem popup)
function handleOAuthRedirectParams() {
  const p = new URLSearchParams(location.search);
  if (!p.get('oauth')) return;
  window.history.replaceState({}, '', '/');
  const sid = p.get('sid') || '';
  const role = p.get('role') || 'src';
  const name = p.get('display_name') || '';
  if (sid) {
    if (role === 'src') { state.srcSid = sid; state.srcDisplayName = name; }
    else { state.destSid = sid; state.destDisplayName = name; }
    goToStep(2);
    renderConnectForms();
    checkTransferReady();
  }
}

// ── OAuth Popup ────────────────────────────────────────────

// ── Scroll ─────────────────────────────────────────────────
function scrollToApp() {
  document.getElementById('app-section').scrollIntoView({ behavior: 'smooth' });
}

// ── Step Wizard ────────────────────────────────────────────
function goToStep(n) {
  for (let i = 1; i <= 4; i++) {
    document.getElementById(`step-${i}`)?.classList.remove('active');
  }
  document.getElementById(`step-${n}`)?.classList.add('active');
  document.getElementById(`step-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  state.currentStep = n;
  updateStepIndicator(n);
}

function updateStepIndicator(current) {
  for (let i = 1; i <= 4; i++) {
    const circle = document.getElementById(`step-circle-${i}`);
    const label  = document.getElementById(`step-label-${i}`);
    if (!circle) continue;
    circle.classList.remove('active', 'done');
    label.classList.remove('active');
    if (i < current)      { circle.classList.add('done'); circle.innerHTML = '✓'; }
    else if (i === current){ circle.classList.add('active'); circle.innerHTML = String(i); label.classList.add('active'); }
    else                   { circle.innerHTML = String(i); }
    const line = document.getElementById(`step-line-${i}`);
    if (line) line.classList.toggle('done', i < current);
  }
}

function clearRoleConnection(role) {
  if (role === 'src') {
    state.srcSid = null;
    state.srcDisplayName = null;
  } else {
    state.destSid = null;
    state.destDisplayName = null;
  }
}

function resetPreviewPanel() {
  const panel = document.getElementById('preview-panel');
  if (!panel) return;
  panel.style.display = 'none';
  panel.innerHTML = '';
}

// ── Platform Grids ─────────────────────────────────────────

function makePlatformCard(key, p, role, disabled) {
  const div = document.createElement('div');
  div.className = `platform-card${disabled ? ' disabled' : ''}`;
  div.id = `${role}-${key}`;
  div.style.color = p.color;

  div.innerHTML = `
    <div class="platform-glow" style="background:radial-gradient(circle at 50% 80%,${p.color}22,transparent 70%);"></div>
    <div class="platform-icon" style="background:${p.color}18;">
      ${PLATFORM_ICONS[key] || '🎵'}
    </div>
    <div class="platform-name">${p.name}</div>
    ${disabled ? `<div class="disabled-badge">${role === 'src' ? 'Só destino' : 'Só origem'}</div>` : ''}
    <div class="selected-check">✓</div>
  `;

  if (!disabled) {
    div.addEventListener('click', () => selectPlatform(key, role));
  }
  return div;
}

function makeSoonChip(key, p) {
  const span = document.createElement('div');
  span.className = 'soon-chip';
  span.style.borderColor = p.color + '40';
  span.innerHTML = `
    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px;"></span>
    ${p.name}
    <span class="soon-chip-badge">Em breve</span>
  `;
  return span;
}

function selectPlatform(key, role) {
  const prev = role === 'src' ? state.srcPlatform : state.destPlatform;
  if (prev) document.getElementById(`${role}-${prev}`)?.classList.remove('selected');
  if (prev && prev !== key) {
    clearRoleConnection(role);
    if (role === 'src') resetPreviewPanel();
  }

  if (role === 'src') {
    state.srcPlatform = key;
    if (state.destPlatform === key) {
      state.destPlatform = null;
      document.getElementById(`dest-${key}`)?.classList.remove('selected');
      clearRoleConnection('dest');
    }
  } else {
    state.destPlatform = key;
    if (state.srcPlatform === key) {
      state.srcPlatform = null;
      document.getElementById(`src-${key}`)?.classList.remove('selected');
      clearRoleConnection('src');
      resetPreviewPanel();
    }
  }

  document.getElementById(`${role}-${key}`)?.classList.add('selected');

  const canContinue = state.srcPlatform && state.destPlatform && state.srcPlatform !== state.destPlatform;
  document.getElementById('btn-step1-next').disabled = !canContinue;
  updateUrlHint();
  if (state.currentStep >= 2 && state.srcPlatform && state.destPlatform) renderConnectForms();
  checkTransferReady();
}

// ── Step 2 ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-step1-next')?.addEventListener('click', () => {
    goToStep(2);
    renderConnectForms();
    updateUrlHint();
  });
  document.getElementById('playlist-url')?.addEventListener('input', checkTransferReady);
});


function makeConnectionStatus(platform, role, displayName) {
  const div = document.createElement('div');
  div.className = 'connection-status';
  div.innerHTML = `
    <div class="status-info">
      <div class="status-dot"></div>
      <div>
        <div class="status-name">${state.platforms[platform]?.name || platform}</div>
        <div class="status-user">${escapeHtml(displayName)}</div>
      </div>
    </div>
    <button class="btn-disconnect" onclick="disconnect('${role}')">Trocar conta</button>
  `;
  return div;
}

const OPTIONAL_SOURCE_CONNECTIONS = new Set(['deezer', 'youtube', 'soundcloud', 'apple']);


function isSourceReady() {
  return !!state.srcSid || isSourceConnectionOptional(state.srcPlatform);
}

function makeConnectCallout(config) {
  const div = document.createElement('div');
  const tone = config.tone || 'default';
  const buttonClass = config.buttonClass || 'btn btn-primary';

  div.className = `connect-callout ${tone}`;
  div.innerHTML = `
    <div class="connect-callout-top">
      <div class="connect-callout-icon">
        ${PLATFORM_ICONS[config.platform] || ''}
      </div>
      <div class="connect-callout-copy">
        ${config.badge ? `<div class="connect-callout-badge">${config.badge}</div>` : ''}
        <div class="connect-callout-title">${config.title}</div>
        <div class="connect-callout-subtitle">${config.subtitle}</div>
      </div>
    </div>
    ${config.buttonLabel && config.buttonAction ? `
      <button class="${buttonClass}" onclick="${config.buttonAction}">
        ${config.buttonLabel}
      </button>
    ` : ''}
    ${config.note ? `<div class="connect-callout-note">${config.note}</div>` : ''}
  `;

  return div;
}

function makeAdvancedDetails(summaryText, content, open = false) {
  const details = document.createElement('details');
  details.className = 'advanced-details';
  details.open = open;

  const summary = document.createElement('summary');
  summary.textContent = summaryText;
  details.appendChild(summary);

  const body = document.createElement('div');
  body.className = 'advanced-details-body';
  if (typeof content === 'string') body.innerHTML = content;
  else body.appendChild(content);
  details.appendChild(body);

  return details;
}


// ── Playlist Preview ───────────────────────────────────────
async function previewPlaylist() {
  const url = document.getElementById('playlist-url')?.value?.trim();
  if (!url) { showToast('Cole o link da playlist primeiro', 'warn'); return; }

  const btn = document.getElementById('btn-preview');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin-inline"></span> Carregando...';

  try {
    const r = await fetch('/api/preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ platform: state.srcPlatform, url, sid: state.srcSid || '' }),
    });
    const data = await r.json();
    if (data.ok) { renderPreview(data); checkTransferReady(); }
    else showToast(data.error, 'error');
  } catch { showToast('Erro ao buscar playlist', 'error'); }
  finally { btn.disabled = false; btn.innerHTML = '👁 Pré-visualizar playlist'; }
}

function renderPreview(data) {
  const panel = document.getElementById('preview-panel');
  if (!panel) return;
  panel.style.display = 'block';
  panel.innerHTML = `
    <div class="preview-panel">
      <div class="preview-header">
        <div class="preview-title">🎵 ${escapeHtml(data.nome)}</div>
        <div class="preview-count">${data.total} músicas</div>
      </div>
      <div class="preview-tracks">
        ${data.tracks.slice(0, 20).map((t, i) => `
          <div class="preview-track">
            <div class="track-num">${i+1}</div>
            <div class="track-info">
              <div class="track-title">${escapeHtml(t.titulo)}</div>
              <div class="track-artist">${escapeHtml(t.artista)}</div>
            </div>
          </div>
        `).join('')}
      </div>
      ${data.total > 20 ? `<div class="preview-more">+ ${data.total - 20} músicas</div>` : ''}
    </div>
  `;
}


// ── Transfer ───────────────────────────────────────────────
async function startTransfer() {
  const url = document.getElementById('playlist-url')?.value?.trim();
  if (!url) { showToast('Cole o link da playlist', 'warn'); return; }

  goToStep(3);
  setupProgressUI();

  try {
    const r = await fetch('/api/transfer', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        src_platform: state.srcPlatform, src_url: url, src_sid: state.srcSid || '',
        dest_platform: state.destPlatform, dest_sid: state.destSid || '',
        plan: 'free',
      }),
    });
    const data = await r.json();
    if (data.job_id) { state.jobId = data.job_id; state.eventIdx = 0; startPolling(); }
    else showToast('Erro ao iniciar transferência', 'error');
  } catch { showToast('Erro de rede', 'error'); }
}

function setupProgressUI() {
  const p = state.platforms;
  document.getElementById('progress-src-icon').innerHTML = PLATFORM_ICONS[state.srcPlatform] || '🎵';
  document.getElementById('progress-dest-icon').innerHTML = PLATFORM_ICONS[state.destPlatform] || '🎵';
  document.getElementById('progress-src-name').textContent = p[state.srcPlatform]?.name || '';
  document.getElementById('progress-dest-name').textContent = p[state.destPlatform]?.name || '';
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('progress-found').textContent = '0';
  document.getElementById('progress-missing').textContent = '0';
  document.getElementById('progress-current').textContent = '0';
  document.getElementById('progress-total').textContent = '0';
  document.getElementById('tracks-feed-list').innerHTML = '';
  state.transferStats = { found: 0, missing: 0, total: 0 };
}

// ── Polling ────────────────────────────────────────────────
function startPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(pollJob, 800);
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const r = await fetch(`/api/job/${state.jobId}?from=${state.eventIdx}`);
    const data = await r.json();
    if (data.error) { clearInterval(state.pollTimer); return; }
    data.events.forEach(handleEvent);
    state.eventIdx += data.events.length;
    if (data.done && data.events.length === 0) clearInterval(state.pollTimer);
  } catch (e) { console.error('Poll error', e); }
}

function handleEvent(ev) {
  switch (ev.type) {
    case 'status':
      document.getElementById('progress-status').textContent = ev.msg; break;
    case 'playlist_read':
      state.transferStats.total = ev.total;
      document.getElementById('progress-playlist-name').textContent = ev.nome;
      document.getElementById('progress-total').textContent = ev.total; break;
    case 'track': processTrackEvent(ev); break;
    case 'done':  handleTransferDone(ev); break;
    case 'error': handleTransferError(ev); break;
  }
}

function processTrackEvent(ev) {
  if (ev.found) state.transferStats.found++;
  else state.transferStats.missing++;

  document.getElementById('progress-found').textContent   = state.transferStats.found;
  document.getElementById('progress-missing').textContent = state.transferStats.missing;
  document.getElementById('progress-current').textContent = ev.current;

  const pct = state.transferStats.total > 0
    ? (ev.current / state.transferStats.total * 100).toFixed(1) : 0;
  document.getElementById('progress-bar').style.width = `${pct}%`;

  const feed = document.getElementById('tracks-feed-list');
  const item = document.createElement('div');
  item.className = 'feed-track';
  item.innerHTML = `
    <div class="feed-track-status ${ev.found ? 'found' : 'not-found'}">${ev.found ? '✓' : '✕'}</div>
    <div class="feed-track-info">
      <div class="feed-track-title">${escapeHtml(ev.titulo)}</div>
      <div class="feed-track-artist">${escapeHtml(ev.artista)}</div>
    </div>
  `;
  feed.insertBefore(item, feed.firstChild);
  while (feed.children.length > 60) feed.removeChild(feed.lastChild);
}

function handleTransferDone(ev) {
  clearInterval(state.pollTimer);
  document.getElementById('progress-status').textContent = 'Transferencia concluida!';
  document.getElementById('progress-bar').style.width = '100%';
  state.lastResultUrl = ev.playlist_url || '';
  launchConfetti();
  setTimeout(() => { showResult(ev); goToStep(4); }, 1200);
}


// ── Result ─────────────────────────────────────────────────
function showResult(ev) {
  document.getElementById('result-found').textContent   = ev.encontradas;
  document.getElementById('result-missing').textContent = ev.nao_encontradas;
  document.getElementById('result-total').textContent   = ev.total;
  const link = document.getElementById('result-playlist-link');
  link.href = ev.playlist_url || '#';
  state.lastResultUrl = ev.playlist_url || '';

  const rate = ev.total > 0 ? (ev.encontradas / ev.total * 100).toFixed(0) : 0;
  const [icon, title] =
    rate >= 90 ? ['🎉', 'Transferência Perfeita!'] :
    rate >= 70 ? ['✅', 'Transferência Concluída!'] :
                 ['⚠️', 'Transferência Parcial'];
  document.getElementById('result-icon').textContent   = icon;
  document.getElementById('result-title').textContent  = title;
  document.getElementById('result-subtitle').textContent =
    `${rate}% das músicas foram adicionadas no ${state.platforms[state.destPlatform]?.name || 'destino'}`;

  if (ev.falhas?.length) {
    document.getElementById('result-missing-list').style.display = 'block';
    document.getElementById('missing-tracks-list').innerHTML = ev.falhas.map(f => `
      <div class="feed-track">
        <div class="feed-track-status not-found">✕</div>
        <div class="feed-track-info">
          <div class="feed-track-title">${escapeHtml(f.titulo)}</div>
          <div class="feed-track-artist">${escapeHtml(f.artista)}</div>
        </div>
      </div>
    `).join('');
  }

  document.getElementById('share-card').style.display = 'block';
}

function newTransfer() {
  state.srcPlatform = null; state.destPlatform = null;
  state.srcSid = null; state.destSid = null;
  state.srcDisplayName = null; state.destDisplayName = null;
  Object.values(state.deezerCapturePolls || {}).forEach((timer) => {
    if (timer) clearTimeout(timer);
  });
  Object.keys(deezerTabRefs).forEach((key) => {
    delete deezerTabRefs[key];
  });
  state.deezerTabsOpened = {};
  state.deezerCapturePolls = {};
  state.deezerAutoConnecting = {};
  state.jobId = null; state.eventIdx = 0;
  if (state.pollTimer) clearInterval(state.pollTimer);
  document.getElementById('playlist-url').value = '';
  document.getElementById('preview-panel').style.display = 'none';
  document.getElementById('result-missing-list').style.display = 'none';
  document.getElementById('share-card').style.display = 'none';
  renderPlatformGrids();
  goToStep(1);
  scrollToApp();
}

// ── Share ──────────────────────────────────────────────────
function shareWhatsApp() {
  window.open(`https://wa.me/?text=${encodeURIComponent('Transferi minha playlist entre streamings com o PlayTransfer! Grátis: https://playtransfer.app')}`, '_blank');
}
function shareTwitter() {
  window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent('Acabei de transferir minha playlist com o PlayTransfer! 🎵 100% grátis. Tenta: https://playtransfer.app')}`, '_blank');
}
async function copyLink() {
  try { await navigator.clipboard.writeText('https://playtransfer.app'); showToast('Link copiado!', 'success'); }
  catch { showToast('Não foi possível copiar', 'error'); }
}

// ── Confetti ───────────────────────────────────────────────
function launchConfetti() {
  const colors = ['#7C3AED','#06B6D4','#1DB954','#FF0092','#F59E0B','#EF4444'];
  for (let i = 0; i < 80; i++) {
    const el = document.createElement('div');
    el.className = 'confetti-particle';
    el.style.cssText = `left:${Math.random()*100}vw;top:-10px;background:${colors[Math.floor(Math.random()*colors.length)]};animation-duration:${1.5+Math.random()*2}s;animation-delay:${Math.random()*0.5}s;width:${6+Math.random()*8}px;height:${6+Math.random()*8}px;border-radius:${Math.random()>.5?'50%':'2px'};`;
    document.body.appendChild(el);
    el.addEventListener('animationend', () => el.remove());
  }
}

// ── Toast ──────────────────────────────────────────────────

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}


Object.assign(PLATFORM_ICONS, {
  spotify: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#1DB954"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 14.44c-.2.32-.63.42-.95.22-2.6-1.59-5.87-1.95-9.72-1.07-.37.09-.75-.14-.84-.51-.09-.37.14-.75.51-.84 4.21-.96 7.82-.55 10.73 1.24.32.2.42.63.22.96zm1.24-2.76c-.25.4-.78.52-1.18.27-2.98-1.83-7.51-2.36-11.03-1.29-.46.14-.94-.12-1.08-.58-.14-.46.12-.94.58-1.08 4.02-1.22 9.01-.63 12.43 1.47.4.25.52.78.27 1.18zm.1-2.88C14.24 8.85 8.81 8.7 5.54 9.65c-.54.16-1.12-.14-1.28-.69-.16-.54.14-1.12.69-1.28 3.77-1.08 10.04-.87 14 1.52.49.29.65.92.36 1.41-.29.49-.92.65-1.41.36z"/></svg>`,
  deezer: `<svg viewBox="0 0 24 24" fill="none" style="width:28px;height:28px;color:#A238FF"><path fill="currentColor" d="M4.2 10.3 5.6 7.8 6.9 9.8 8.3 6.6 9.7 10.1 11.1 8.2 12 5.8 12.9 8.2 14.3 10.1 15.7 6.6 17.1 9.8 18.4 7.8 19.8 10.3c0 3.3-2.6 5.6-7.2 9.4a.96.96 0 0 1-1.2 0c-4.6-3.8-7.2-6.1-7.2-9.4Z"/></svg>`,
  youtube: `<svg viewBox="0 0 24 24" fill="none" style="width:28px;height:28px"><circle cx="12" cy="12" r="9" stroke="#FF0033" stroke-width="2.4"/><path d="M10 8.9v6.2l5.2-3.1L10 8.9z" fill="#FF0033"/></svg>`,
  soundcloud: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#FF5500"><path d="M11.56 8.87V17h8.76c.96 0 1.68-.58 1.68-1.56 0-.82-.55-1.46-1.3-1.62.05-.2.08-.4.08-.62 0-1.46-1.14-2.63-2.56-2.63-.16 0-.3.02-.46.05-.17-1.43-1.37-2.55-2.84-2.55C13 8.07 12 8.37 11.56 8.87zM0 15c0 1.1.9 2 2 2s2-.9 2-2V11c0-1.1-.9-2-2-2S0 9.9 0 11v4zm5 0c0 1.1.9 2 2 2s2-.9 2-2V9c0-1.1-.9-2-2-2S5 7.9 5 9v6z"/></svg>`,
  apple: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#F5F5F7"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>`,
  tidal: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#F5F5F7"><path d="M12.012 3.992L8.008 7.996 4 3.988 0 7.996l4.004 4.004 4.004-4.004 4.004 4.004 4.008-4.008zM16.016 8 12.008 12.004 16.012 16.008 20.016 12z"/></svg>`,
  amazon: `<svg viewBox="0 0 24 24" fill="none" style="width:28px;height:28px"><path d="M7.2 7.4c0-1.9 1.3-3.1 3.2-3.1 1.8 0 3 1.1 3 2.9v7.5h-2V8c0-.9-.4-1.4-1.2-1.4-.8 0-1.2.5-1.2 1.4v6.7h-2V7.4z" fill="#00A8E1"/><path d="M4.1 18.2c2 .9 4.2 1.4 6.6 1.4 3.1 0 6-.8 8.4-2.2" stroke="#FF9900" stroke-width="1.8" stroke-linecap="round"/><path d="M17.8 15.9l1.9 1.2-2.2.4" stroke="#FF9900" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
});

function makeTextInputField(id, label, placeholder, value = '') {
  return `
    <div class="form-group" style="margin-top:16px;">
      <label class="form-label" for="${id}">${label}</label>
      <input id="${id}" class="form-input" placeholder="${placeholder}" value="${escapeHtml(value)}" />
    </div>
  `;
}

function makeTextAreaField(id, label, placeholder) {
  return `
    <div class="form-group" style="margin-top:16px;">
      <label class="form-label" for="${id}">${label}</label>
      <textarea id="${id}" class="form-input form-textarea" placeholder="${placeholder}"></textarea>
    </div>
  `;
}


function renderConnectForm(platform, role) {
  const container = document.getElementById(`${role}-connect-form`);
  if (!container) return;
  container.innerHTML = '';

  const sid = role === 'src' ? state.srcSid : state.destSid;
  const name = role === 'src' ? state.srcDisplayName : state.destDisplayName;
  if (sid) {
    container.appendChild(makeConnectionStatus(platform, role, name || 'Conectado'));
    return;
  }

  switch (platform) {
    case 'spotify': container.appendChild(makeSpotifyForm(role)); break;
    case 'deezer': container.appendChild(makeDeezerForm(role)); break;
    case 'youtube': container.appendChild(makeYoutubeForm(role)); break;
    case 'soundcloud': container.appendChild(makeSoundcloudForm(role)); break;
    case 'apple': container.appendChild(makeAppleForm(role)); break;
    case 'amazon': container.appendChild(makeAmazonForm(role)); break;
    case 'tidal': container.appendChild(makeTidalForm(role)); break;
    default:
      container.innerHTML = `<p style="color:var(--color-muted);font-size:0.85rem;">Integração indisponivel.</p>`;
  }
}



async function connectSoundcloud(role) {
  const status = document.getElementById(`${role}-sc-status`);
  const accessToken = document.getElementById(`${role}-soundcloud-token`)?.value?.trim() || '';
  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';
  try {
    const r = await fetch('/api/connect/soundcloud', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role, access_token: accessToken }),
    });
    const d = await r.json();
    if (d.ok) {
      if (role === 'src') { state.srcSid = d.sid; state.srcDisplayName = d.display_name; }
      else { state.destSid = d.sid; state.destDisplayName = d.display_name; }
      showToast('SoundCloud conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
    } else {
      if (status) status.textContent = d.error || 'Falha ao conectar.';
      showToast(d.error || 'Falha ao conectar SoundCloud', 'error');
    }
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar SoundCloud', 'error');
  }
}

async function connectApple(role) {
  const status = document.getElementById(`${role}-apple-status`);
  const developerToken = document.getElementById(`${role}-apple-developer-token`)?.value?.trim() || '';
  const musicUserToken = document.getElementById(`${role}-apple-user-token`)?.value?.trim() || '';
  const storefront = document.getElementById(`${role}-apple-storefront`)?.value?.trim() || 'us';
  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';
  try {
    const r = await fetch('/api/connect/apple', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        role,
        developer_token: developerToken,
        music_user_token: musicUserToken,
        storefront,
      }),
    });
    const d = await r.json();
    if (d.ok) {
      if (role === 'src') { state.srcSid = d.sid; state.srcDisplayName = d.display_name; }
      else { state.destSid = d.sid; state.destDisplayName = d.display_name; }
      showToast('Apple Music conectada!', 'success');
      renderConnectForms();
      checkTransferReady();
    } else {
      if (status) status.textContent = d.error || 'Falha ao conectar.';
      showToast(d.error || 'Falha ao conectar Apple Music', 'error');
    }
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar Apple Music', 'error');
  }
}

async function connectAmazon(role) {
  const status = document.getElementById(`${role}-amazon-status`);
  const apiKey = document.getElementById(`${role}-amazon-api-key`)?.value?.trim() || '';
  const accessToken = document.getElementById(`${role}-amazon-access-token`)?.value?.trim() || '';
  const countryCode = document.getElementById(`${role}-amazon-country-code`)?.value?.trim() || 'US';
  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';
  try {
    const r = await fetch('/api/connect/amazon', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role, api_key: apiKey, access_token: accessToken, country_code: countryCode }),
    });
    const d = await r.json();
    if (d.ok) {
      if (role === 'src') { state.srcSid = d.sid; state.srcDisplayName = d.display_name; }
      else { state.destSid = d.sid; state.destDisplayName = d.display_name; }
      showToast('Amazon Music conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
    } else {
      if (status) status.textContent = d.error || 'Falha ao conectar.';
      showToast(d.error || 'Falha ao conectar Amazon Music', 'error');
    }
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar Amazon Music', 'error');
  }
}

async function startTidalConnect(role) {
  state.tidalPending = state.tidalPending || {};
  const status = document.getElementById(`${role}-tidal-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Gerando codigo do TIDAL...';
  try {
    const r = await fetch('/api/connect/tidal/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();
    if (!d.ok) {
      if (status) status.textContent = d.error || 'Falha ao iniciar login.';
      showToast(d.error || 'Falha ao iniciar login do TIDAL', 'error');
      return;
    }

    state.tidalPending[role] = d.login_id;
    if (status) {
      status.innerHTML = `
        <div style="display:grid;gap:8px;">
          <div>Codigo: <strong>${escapeHtml(d.user_code)}</strong></div>
          <a href="${d.verification_uri_complete}" target="_blank" rel="noopener">Abrir login oficial do TIDAL</a>
          <div>Assim que voce autorizar, esta tela conecta sozinha.</div>
        </div>
      `;
    }
    pollTidalLogin(role, d.login_id);
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao iniciar login do TIDAL', 'error');
  }
}

async function pollTidalLogin(role, loginId) {
  state.tidalPending = state.tidalPending || {};
  const status = document.getElementById(`${role}-tidal-status`);
  if (state.tidalPending[role] !== loginId) return;

  try {
    const r = await fetch(`/api/connect/tidal/poll/${loginId}`);
    const d = await r.json();

    if (d.ok) {
      state.tidalPending[role] = null;
      if (role === 'src') { state.srcSid = d.sid; state.srcDisplayName = d.display_name; }
      else { state.destSid = d.sid; state.destDisplayName = d.display_name; }
      showToast('TIDAL conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return;
    }

    if (d.pending) {
      setTimeout(() => pollTidalLogin(role, loginId), 2000);
      return;
    }

    state.tidalPending[role] = null;
    if (status) status.textContent = d.error || 'Falha ao conectar.';
    showToast(d.error || 'Falha ao conectar TIDAL', 'error');
  } catch {
    state.tidalPending[role] = null;
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar TIDAL', 'error');
  }
}

function disconnect(role) {
  if (!state.tidalPending) state.tidalPending = {};
  state.tidalPending[role] = null;
  if (!state.youtubePending) state.youtubePending = {};
  state.youtubePending[role] = null;
  clearRoleConnection(role);
  renderConnectForms();
  checkTransferReady();
}


function renderConnectForms() {
  const p = state.platforms;
  document.getElementById('src-connect-title').textContent =
    `Origem - ${p[state.srcPlatform]?.name || ''}${isSourceConnectionOptional(state.srcPlatform) ? ' (login opcional)' : ''}`;
  document.getElementById('dest-connect-title').textContent =
    `Destino - ${p[state.destPlatform]?.name || ''}`;

  renderConnectForm(state.srcPlatform, 'src');
  renderConnectForm(state.destPlatform, 'dest');
}

function makeInlineStatus(id) {
  return `<div id="${id}" class="connect-inline-status"></div>`;
}

function makeFormPanel(html) {
  const div = document.createElement('div');
  div.className = 'manual-connect-panel';
  div.innerHTML = html;
  return div;
}

function normalizeManualStep(step, index) {
  if (typeof step === 'string') {
    return {
      eyebrow: `Passo ${index + 1}`,
      title: step,
      detail: '',
      hint: '',
    };
  }

  return {
    eyebrow: step?.eyebrow || `Passo ${index + 1}`,
    title: step?.title || '',
    detail: step?.detail || '',
    hint: step?.hint || '',
  };
}

function renderManualBadges(items = []) {
  if (!items.length) return '';
  return `
    <div class="manual-connect-badges">
      ${items.map((item) => `<span class="manual-connect-badge">${item}</span>`).join('')}
    </div>
  `;
}

function renderManualNotice(notice) {
  if (!notice?.body) return '';
  const tone = notice.tone || 'info';
  return `
    <div class="manual-connect-notice ${tone}">
      <div class="manual-connect-notice-icon">${tone === 'warning' ? '!' : 'i'}</div>
      <div class="manual-connect-notice-copy">
        ${notice.title ? `<div class="manual-connect-notice-title">${notice.title}</div>` : ''}
        <div class="manual-connect-notice-body">${notice.body}</div>
      </div>
    </div>
  `;
}

function renderManualSteps(steps = []) {
  if (!steps.length) return '';
  return `
    <ol class="manual-connect-steps" aria-label="Passo a passo">
      ${steps.map((step, idx) => {
        const item = normalizeManualStep(step, idx);
        return `
          <li class="manual-step-card">
            <div class="manual-step-index">${idx + 1}</div>
            <div class="manual-step-copy">
              <div class="manual-step-eyebrow">${item.eyebrow}</div>
              ${item.title ? `<div class="manual-step-title">${item.title}</div>` : ''}
              ${item.detail ? `<div class="manual-step-detail">${item.detail}</div>` : ''}
              ${item.hint ? `<div class="manual-step-hint">${item.hint}</div>` : ''}
            </div>
          </li>
        `;
      }).join('')}
    </ol>
  `;
}

function makeManualCredentialsForm(config) {
  const div = document.createElement('div');
  div.className = 'manual-connect-panel';
  div.innerHTML = `
    <div class="manual-connect-header">
      <div class="manual-connect-platform">
        <div class="manual-connect-platform-icon">${PLATFORM_ICONS[config.platform] || ''}</div>
        <div class="manual-connect-platform-copy">
          <div class="manual-connect-title">${config.title}</div>
          <div class="manual-connect-subtitle">${config.subtitle}</div>
        </div>
      </div>
      ${renderManualBadges(config.badges || [])}
    </div>
    ${renderManualNotice(config.notice)}
    ${renderManualSteps(config.steps || [])}
    <div class="form-group" style="margin-top:0;">
      <label class="form-label" for="${config.inputId}">${config.label}</label>
      <textarea id="${config.inputId}" class="form-input form-textarea" placeholder="${config.placeholder}"></textarea>
      ${config.help ? `
        <div class="form-hint">
          <span>i</span>
          <span>${config.help}</span>
        </div>
      ` : ''}
    </div>
    <div class="manual-connect-actions">
      ${config.secondaryButtonLabel && config.secondaryButtonAction ? `
        <button class="btn btn-ghost btn-sm" type="button" onclick="${config.secondaryButtonAction}">
          ${config.secondaryButtonLabel}
        </button>
      ` : ''}
      <button class="btn btn-secondary btn-sm" type="button" onclick="${config.action}('${config.role}')">
        ${config.buttonLabel}
      </button>
    </div>
    ${config.footnote ? `<div class="manual-connect-footnote">${config.footnote}</div>` : ''}
    ${makeInlineStatus(config.statusId)}
  `;
  return div;
}

function makeOAuthForm(platform, role) {
  const configured = !!state.platforms[platform]?.oauth_configured;
  const names = { spotify: 'Spotify', deezer: 'Deezer' };
  const name = names[platform] || platform;

  if (!configured) {
    return makeConnectCallout({
      platform,
      tone: 'warning',
      badge: 'Login rapido indisponivel',
      title: `${name} sem login facil nesta instalacao`,
      subtitle: 'A forma simples de entrar ainda nao esta ativa aqui.',
      note: 'Se quiser continuar agora, voce pode usar a opcao avancada logo abaixo.',
    });
  }

  return makeConnectCallout({
    platform,
    badge: 'Login oficial',
    title: `Entrar com ${name}`,
    subtitle: role === 'src'
      ? 'Vamos pedir sua autorizacao para ler a playlist completa do jeito certo.'
      : 'Vamos pedir sua autorizacao para criar a nova playlist na sua conta.',
    note: `Antes de seguir, mostramos rapidinho por que essa permissao e pedida. Sua senha continua no site oficial do ${name}.`,
    buttonLabel: `Entrar e autorizar`,
    buttonAction: `openOAuthPopup('${platform}','${role}')`,
    buttonClass: 'btn btn-primary',
  });
}

function makeSpotifyForm(role) {
  const wrapper = document.createElement('div');
  if (state.platforms.spotify?.oauth_configured) {
    wrapper.appendChild(makeOAuthForm('spotify', role));
    wrapper.appendChild(makeAdvancedDetails(
      'Estou com problema no login rapido',
      makeManualCredentialsForm({
        platform: 'spotify',
        role,
        title: 'Copie o valor do Spotify',
        subtitle: role === 'src'
          ? 'Use isso apenas se o login oficial nao abrir e voce realmente precisar continuar agora.'
          : 'Use isso apenas se o login oficial nao abrir e voce realmente precisar continuar agora.',
        badges: ['Sem senha aqui', 'Copie 1 valor', 'Cole e siga'],
        notice: {
          title: 'Onde clicar',
          body: 'No Spotify Web, abra <strong>F12</strong> e depois <strong>Application &gt; Cookies &gt; https://open.spotify.com</strong>.',
        },
        label: 'Cole aqui o valor copiado ou o cabecalho Cookie completo',
        inputId: `${role}-spotify-cookie`,
        placeholder: 'Cole o Cookie Value de sp_dc ou o cabecalho Cookie completo',
        statusId: `${role}-spotify-status`,
        action: 'connectSpotify',
        buttonLabel: 'Conectar Spotify',
        help: 'Esse modo e avancado. Para a maioria das pessoas, o recomendado e usar "Entrar e autorizar".',
        steps: [
          {
            title: 'Abra o Spotify Web',
            detail: 'Entre na conta certa e deixe a pagina aberta.',
          },
          {
            title: 'Abra os dados do site',
            detail: 'Pressione <kbd>F12</kbd> e clique em <strong>Application</strong> ou <strong>Armazenamento</strong>. Depois entre em <strong>Cookies</strong> e escolha <code>https://open.spotify.com</code>.',
          },
          {
            title: 'Copie o valor certo',
            detail: 'Clique em <code>sp_dc</code> e copie o texto que aparece em <strong>Cookie Value</strong>.',
            hint: 'Se ficar mais facil, voce tambem pode colar o cabecalho completo <code>Cookie</code> de uma requisicao do Spotify Web.',
          },
        ],
      })
    ));
  } else if (role === 'src') {
    wrapper.appendChild(makeConnectCallout({
      platform: 'spotify',
      tone: 'success',
      badge: 'Sem login',
      title: 'Cole o link do Spotify e continue',
      subtitle: 'Para playlists publicas menores, voce nao precisa entrar nem copiar nada.',
      note: 'Playlists privadas ou maiores ainda nao estao disponiveis completas nesta instalacao.',
    }));
  } else {
    wrapper.appendChild(makeConnectCallout({
      platform: 'spotify',
      tone: 'warning',
      badge: 'Indisponivel aqui',
      title: 'Spotify como destino ainda nao esta pronto neste site',
      subtitle: 'Para salvar playlists no Spotify, esta instalacao ainda precisa ativar o login oficial.',
      note: 'Para o usuario final, essa etapa vai aparecer so como botao de login quando o site estiver pronto.',
    }));
  }

  return wrapper;
}

function makeDeezerForm(role) {
  if (role === 'src') {
    return makeConnectCallout({
      platform: 'deezer',
      tone: 'success',
      badge: 'Sem login',
      title: 'Nao precisa entrar no Deezer agora',
      subtitle: 'Para a maioria das playlists publicas, basta colar o link abaixo.',
      note: 'Se o preview nao abrir, confira se a playlist esta publica.',
    });
  }

  const wrapper = document.createElement('div');

  // Se OAuth está configurado, oferece OAuth primeiro + fallback manual
  if (state.platforms.deezer?.oauth_configured) {
    wrapper.appendChild(makeOAuthForm('deezer', role));
    wrapper.appendChild(makeAdvancedDetails(
      'Usar modo automatico do Deezer',
      makeDeezerQuickConnect(role)
    ));
    return wrapper;
  }

  // Sem OAuth: fluxo automatico é o principal
  wrapper.appendChild(makeDeezerQuickConnect(role));
  return wrapper;
}

function makeDeezerQuickConnect(role) {
  const connected = (role === 'src' && state.srcSid) || (role === 'dest' && state.destSid);
  const displayName = role === 'src' ? state.srcDisplayName : state.destDisplayName;

  if (connected && displayName) {
    return makeConnectCallout({
      platform: 'deezer',
      tone: 'success',
      badge: 'Conectado',
      title: `Deezer conectado como ${displayName}`,
      subtitle: 'Pronto para transferir playlists.',
    });
  }

  const opened = !!state.deezerTabsOpened?.[role];
  const autoTrying = !!state.deezerAutoConnecting?.[role];

  return makeFormPanel(`
    <div class="manual-connect-header deezer-quick-header">
      <div class="manual-connect-platform">
        <div class="manual-connect-platform-icon">${PLATFORM_ICONS.deezer || ''}</div>
        <div class="manual-connect-platform-copy">
          <div class="manual-connect-title">Conectar Deezer</div>
          <div class="manual-connect-subtitle">Clique no botao abaixo. O app tenta encontrar seu login do Deezer automaticamente.</div>
        </div>
      </div>
    </div>
    <div class="manual-connect-actions deezer-quick-actions">
      <button class="btn btn-primary btn-sm deezer-auto-connect-btn" type="button" id="${role}-deezer-auto-btn" onclick="autoConnectDeezer('${role}')" ${autoTrying ? 'disabled' : ''}>
        ${autoTrying ? '<span class="spin-inline"></span> Conectando...' : '🔌 Conectar Deezer automaticamente'}
      </button>
    </div>
    <div class="deezer-quick-hint" id="${role}-deezer-hint">
      ${opened
        ? 'O Deezer ja esta aberto. Se voce ja entrou na conta, basta clicar no botao acima.'
        : 'Se o Deezer ja estiver aberto e logado neste navegador, o app consegue capturar o login sozinho.'}
    </div>
    ${makeInlineStatus(`${role}-deezer-status`)}
    <details class="advanced-details compact-manual-details">
      <summary>Nao funcionou? Fazer manualmente</summary>
      <div class="advanced-details-body">
        <div class="form-group" style="margin-top:0;">
          <label class="form-label" for="${role}-deezer-cookie">Cole aqui o valor do cookie arl</label>
          <textarea id="${role}-deezer-cookie" class="form-input form-textarea" placeholder="Cole somente o valor do cookie arl"></textarea>
          <div class="form-hint">
            <span>i</span>
            <span>No Deezer aberto na conta certa, use <code>F12</code> &gt; <code>Application</code>/<code>Armazenamento</code> &gt; <code>Cookies</code> &gt; <code>https://www.deezer.com</code> e copie o <code>arl</code>.</span>
          </div>
        </div>
        <div class="manual-connect-actions">
          <button class="btn btn-secondary btn-sm" type="button" onclick="connectDeezer('${role}')">Conectar Deezer</button>
        </div>
      </div>
    </details>
  `);
}

function makeYoutubeForm(role) {
  if (role === 'src') {
    return makeConnectCallout({
      platform: 'youtube',
      tone: 'success',
      badge: 'Sem login',
      title: 'Nao precisa entrar no YouTube Music agora',
      subtitle: 'Se a playlist for publica, basta colar o link abaixo e continuar.',
      note: 'Se o preview nao abrir, confira se o link esta publico.',
    });
  }

  const wrapper = document.createElement('div');
  const pending = state.youtubePending?.[role];
  const oauthConfigured = !!state.platforms.youtube?.oauth_configured;
  const youtubeManualLabel = 'Cole aqui o cURL completo que voce copiou';
  const youtubeManualPlaceholder = 'Cole aqui o texto inteiro de "Copy as cURL (bash)"';
  const youtubeManualHelp = 'Cole o comando cURL inteiro. Nao copie texto das abas Payload, Preview, Response nem pedacos soltos de Headers.';
  const youtubeManualSteps = [
    {
      title: 'Abra o YouTube Music',
      detail: 'Entre na conta que vai receber a playlist e deixe a pagina inicial aberta.',
    },
    {
      title: 'Abra a aba certa do navegador',
      detail: 'Pressione <kbd>F12</kbd>, clique em <strong>Network</strong> e depois atualize a pagina com <kbd>F5</kbd>.',
    },
    {
      title: 'Ache a linha browse',
      detail: 'Na lista que apareceu, encontre a linha <code>browse</code>. Se precisar, use o filtro e digite <code>browse</code>.',
    },
    {
      title: 'Copie do jeito certo',
      detail: 'Clique com o botao direito na <strong>linha browse</strong> e escolha <strong>Copy &gt; Copy as cURL (bash)</strong>.',
      hint: 'Nao copie o que aparece dentro de <strong>Payload</strong>, <strong>Preview</strong> ou <strong>Response</strong>.',
    },
  ];

  if (pending?.loginId) {
    wrapper.appendChild(makeConnectCallout({
      platform: 'youtube',
      tone: 'success',
      badge: 'Aguardando Google',
      title: 'Termine o login nessa nova aba',
      subtitle: 'Abri uma aba do Google neste mesmo navegador. Autorize a conta que vai receber a playlist e esta tela tenta concluir sozinha.',
      note: pending.userCode
        ? `Se o Google pedir um codigo, use <strong>${escapeHtml(pending.userCode)}</strong>.`
        : 'Se a aba nao abriu, toque em "Abrir aba de novo".',
      buttonLabel: 'Tentar agora',
      buttonAction: `finishYoutubeAutoConnect('${role}')`,
      buttonClass: 'btn btn-primary',
    }));
    wrapper.appendChild(makeFormPanel(`
      <div class="manual-connect-actions">
        <button class="btn btn-ghost btn-sm" type="button" onclick="reopenYoutubeOAuthTab('${role}')">
          Abrir aba de novo
        </button>
      </div>
      ${makeInlineStatus(`${role}-ytm-status`)}
    `));
    wrapper.appendChild(makeAdvancedDetails(
      'Nao funcionou? Fazer do jeito manual',
      makeManualCredentialsForm({
        platform: 'youtube',
        role,
        title: 'Conectar manualmente pelo navegador',
        subtitle: 'Use isso so se a janela guiada nao der certo.',
        badges: ['Sem senha aqui', 'Copie 1 vez', 'Cole o texto inteiro'],
        notice: {
          tone: 'warning',
          title: 'Importante',
          body: 'O app precisa do <strong>cURL completo</strong> da linha <code>browse</code>. Nao abra as abas <strong>Payload</strong>, <strong>Preview</strong> ou <strong>Response</strong> para copiar de la.',
        },
        label: youtubeManualLabel,
        inputId: `${role}-ytm-curl`,
        placeholder: youtubeManualPlaceholder,
        statusId: `${role}-ytm-status`,
        action: 'connectYoutube',
        buttonLabel: 'Conectar YouTube Music',
        secondaryButtonLabel: 'Usar o que copiei',
        secondaryButtonAction: `pasteYoutubeFromClipboard('${role}')`,
        help: youtubeManualHelp,
        steps: youtubeManualSteps,
      }),
      false
    ));
    return wrapper;
  }

  if (oauthConfigured) {
    wrapper.appendChild(makeConnectCallout({
      platform: 'youtube',
      tone: 'warning',
      badge: 'Login oficial',
      title: 'Entrar com Google',
      subtitle: 'Clique abaixo para abrir uma nova aba neste mesmo navegador e autorizar o YouTube Music.',
      note: 'Sua senha continua no Google. Quando a autorizacao terminar, esta tela conecta sozinha.',
      buttonLabel: 'Continuar com Google',
      buttonAction: `startYoutubeAutoConnect('${role}')`,
      buttonClass: 'btn btn-primary',
    }));
    wrapper.appendChild(makeFormPanel(makeInlineStatus(`${role}-ytm-status`)));
  } else {
    wrapper.appendChild(makeConnectCallout({
      platform: 'youtube',
      tone: 'warning',
      badge: 'Modo de teste',
      title: 'Esta instalacao ainda nao ativou o login oficial do Google',
      subtitle: 'Entao, por enquanto, o jeito que funciona para testar e o modo manual logo abaixo.',
      note: 'Nao vou esconder isso em uma dobra: como nao existe 1 clique aqui, o passo manual aparece aberto logo abaixo.',
    }));
    wrapper.appendChild(makeManualCredentialsForm({
      platform: 'youtube',
      role,
      title: 'Conectar manualmente pelo navegador',
      subtitle: 'Use este passo nesta instalacao enquanto o login oficial do Google nao estiver configurado.',
      badges: ['Sem senha aqui', 'Copie 1 vez', 'Cole o texto inteiro'],
      notice: {
        tone: 'warning',
        title: 'Importante',
        body: 'Clique com o botao direito na <strong>linha browse</strong> e copie o <strong>cURL completo</strong>. Nao copie o conteudo interno de <strong>Payload</strong>, <strong>Preview</strong> ou <strong>Response</strong>.',
      },
      label: youtubeManualLabel,
      inputId: `${role}-ytm-curl`,
      placeholder: youtubeManualPlaceholder,
      statusId: `${role}-ytm-status`,
      action: 'connectYoutube',
      buttonLabel: 'Conectar YouTube Music',
      secondaryButtonLabel: 'Usar o que copiei',
      secondaryButtonAction: `pasteYoutubeFromClipboard('${role}')`,
      help: youtubeManualHelp,
      footnote: 'Quando o login oficial do Google for ativado nesta instalacao, este passo manual deixa de ser o caminho principal.',
      steps: [
        {
          title: 'Abra o YouTube Music',
          detail: 'Entre na conta que vai receber a playlist e deixe a pagina inicial aberta.',
        },
        ...youtubeManualSteps.slice(1),
      ],
    }));
    return wrapper;
  }

  wrapper.appendChild(makeAdvancedDetails(
    'Prefiro fazer do jeito manual',
    makeManualCredentialsForm({
      platform: 'youtube',
      role,
      title: 'Conectar manualmente pelo navegador',
      subtitle: 'Use isso so se a conexao automatica nao abrir direito.',
      badges: ['Sem senha aqui', 'Copie 1 vez', 'Cole o texto inteiro'],
      notice: {
        tone: 'warning',
        title: 'Importante',
        body: 'O que voce deve copiar e o <strong>cURL completo</strong> da linha <code>browse</code>. Nao copie texto de <strong>Payload</strong>, <strong>Preview</strong> ou <strong>Response</strong>.',
      },
      label: youtubeManualLabel,
      inputId: `${role}-ytm-curl`,
      placeholder: youtubeManualPlaceholder,
      statusId: `${role}-ytm-status`,
      action: 'connectYoutube',
      buttonLabel: 'Conectar YouTube Music',
      secondaryButtonLabel: 'Usar o que copiei',
      secondaryButtonAction: `pasteYoutubeFromClipboard('${role}')`,
      help: youtubeManualHelp,
      footnote: 'Se o automatico funcionar, voce pode ignorar esta parte.',
      steps: youtubeManualSteps,
    }),
    false
  ));
  return wrapper;
}

function makeSoundcloudForm(role) {
  const wrapper = document.createElement('div');

  if (role === 'src') {
    wrapper.appendChild(makeConnectCallout({
      platform: 'soundcloud',
      tone: 'success',
      badge: 'Sem login',
      title: 'Nao precisa entrar no SoundCloud agora',
      subtitle: 'Playlists publicas funcionam so com o link.',
      note: 'Se a playlist for privada, voce pode usar um token nas opcoes avancadas.',
    }));
    wrapper.appendChild(makeAdvancedDetails(
      'Minha playlist e privada',
    makeManualCredentialsForm({
      platform: 'soundcloud',
      role,
      title: 'Token opcional do SoundCloud',
      subtitle: 'Use isso so se a playlist nao for publica.',
      badges: ['Opcional', 'So para playlist privada'],
      label: 'Cole aqui o access token do SoundCloud',
      inputId: `${role}-soundcloud-token`,
      placeholder: 'access_token...',
        statusId: `${role}-sc-status`,
        action: 'connectSoundcloud',
      buttonLabel: 'Usar token do SoundCloud',
      help: 'Se a playlist for publica, voce pode ignorar esta parte.',
      steps: [
        {
          title: 'Veja se voce realmente precisa disso',
          detail: 'Para playlist publica, pode ignorar esta parte. So use token se a playlist for privada.',
        },
        {
          title: 'Copie o token da conta certa',
          detail: 'Use um access token OAuth valido da conta do SoundCloud que pode ler essa playlist.',
        },
        {
          title: 'Cole e confirme',
          detail: 'Cole o token no campo abaixo para liberar o acesso privado.',
        },
      ],
    }),
      false
    ));
    return wrapper;
  }

  wrapper.appendChild(makeConnectCallout({
    platform: 'soundcloud',
    tone: 'warning',
    badge: 'Avancado',
    title: 'Conectar SoundCloud',
    subtitle: 'Para criar playlists no SoundCloud, esta plataforma ainda pede um token.',
    note: 'Se voce nao tiver esse token, talvez seja mais facil escolher outro destino.',
  }));
  wrapper.appendChild(makeAdvancedDetails(
    'Tenho um token do SoundCloud',
    makeManualCredentialsForm({
      platform: 'soundcloud',
      role,
      title: 'Token do SoundCloud',
      subtitle: 'Cole o token para permitir a criacao da playlist.',
      badges: ['Avancado', 'Use a conta de destino'],
      label: 'Cole aqui o access token do SoundCloud',
      inputId: `${role}-soundcloud-token`,
      placeholder: 'access_token...',
      statusId: `${role}-sc-status`,
      action: 'connectSoundcloud',
      buttonLabel: 'Conectar SoundCloud',
      help: 'Use o token da conta que vai receber a playlist.',
      steps: [
        {
          title: 'Pegue o token certo',
          detail: 'Obtenha um access token OAuth valido da conta do SoundCloud que vai receber a playlist.',
        },
        {
          title: 'Cole no campo abaixo',
          detail: 'Nao precisa editar o token. Pode colar inteiro como recebeu.',
        },
        {
          title: 'Confirme a conexao',
          detail: 'Depois disso, o app pode criar a playlist nessa conta.',
        },
      ],
    }),
    true
  ));
  return wrapper;
}

function makeAppleForm(role) {
  const wrapper = document.createElement('div');

  if (role === 'src') {
    wrapper.appendChild(makeConnectCallout({
      platform: 'apple',
      tone: 'success',
      badge: 'Sem login',
      title: 'Nao precisa entrar na Apple Music agora',
      subtitle: 'Playlists publicas da Apple Music podem ser lidas so com o link.',
      note: 'Basta colar o link da playlist abaixo.',
    }));
    return wrapper;
  }

  wrapper.appendChild(makeConnectCallout({
    platform: 'apple',
    tone: 'warning',
    badge: 'Avancado',
    title: 'Conectar Apple Music',
    subtitle: 'Hoje a Apple ainda exige dois tokens tecnicos para criar playlists por aqui.',
    note: 'Use esta opcao apenas se voce ja tiver esses tokens em maos.',
  }));

  wrapper.appendChild(makeAdvancedDetails(
    'Tenho os tokens da Apple Music',
    makeFormPanel(`
      <div class="manual-connect-header">
        <div class="manual-connect-title">Tokens da Apple Music</div>
        <div class="manual-connect-subtitle">Preencha apenas se voce ja usa MusicKit ou ja recebeu esses dados.</div>
      </div>
      ${makeTextAreaField(`${role}-apple-developer-token`, 'Developer token', 'eyJhbGciOi...')}
      ${makeTextAreaField(`${role}-apple-user-token`, 'Music user token', 'music-user-token...')}
      ${makeTextInputField(`${role}-apple-storefront`, 'Pais da conta', 'br, us, gb...', 'us')}
      <button class="btn btn-secondary btn-sm" onclick="connectApple('${role}')">Conectar Apple Music</button>
      ${makeInlineStatus(`${role}-apple-status`)}
    `),
    true
  ));

  return wrapper;
}

function makeAmazonForm(role) {
  const wrapper = document.createElement('div');
  wrapper.appendChild(makeConnectCallout({
    platform: 'amazon',
    tone: 'warning',
    badge: 'Limitado',
    title: 'Conectar Amazon Music',
    subtitle: 'A Amazon Music Web API ainda e uma opcao avancada e nem sempre esta liberada para todo mundo.',
    note: 'Se quiser seguir, abra as opcoes avancadas abaixo.',
  }));

  wrapper.appendChild(makeAdvancedDetails(
    'Tenho API key e access token',
    makeFormPanel(`
      <div class="manual-connect-header">
        <div class="manual-connect-title">Amazon Music Web API</div>
        <div class="manual-connect-subtitle">Preencha isso apenas se voce ja recebeu acesso oficial a API.</div>
      </div>
      ${makeTextInputField(`${role}-amazon-api-key`, 'API key', 'amzn1.application-oa2-client...')}
      ${makeTextAreaField(`${role}-amazon-access-token`, 'Access token', 'Atza|IwEB...')}
      ${makeTextInputField(`${role}-amazon-country-code`, 'Pais da conta', 'US', 'US')}
      <button class="btn btn-secondary btn-sm" onclick="connectAmazon('${role}')">Conectar Amazon Music</button>
      ${makeInlineStatus(`${role}-amazon-status`)}
    `),
    false
  ));

  return wrapper;
}

function makeTidalForm(role) {
  const div = document.createElement('div');
  div.appendChild(makeConnectCallout({
    platform: 'tidal',
    badge: 'Recomendado',
    title: 'Entrar com TIDAL',
    subtitle: 'O TIDAL abre o login oficial e esta tela acompanha tudo sozinha.',
    note: 'Depois de autorizar, a conta aparece conectada aqui automaticamente.',
    buttonLabel: 'Continuar com TIDAL',
    buttonAction: `startTidalConnect('${role}')`,
    buttonClass: 'btn btn-primary',
  }));

  const status = document.createElement('div');
  status.id = `${role}-tidal-status`;
  status.className = 'connect-inline-status';
  div.appendChild(status);
  return div;
}


async function connectDeezer(role) {
  const arl = document.getElementById(`${role}-deezer-cookie`)?.value?.trim() || '';
  const status = document.getElementById(`${role}-deezer-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';

  try {
    const r = await fetch('/api/connect/deezer', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ arl }),
    });
    const d = await r.json();

    if (d.ok) {
      if (role === 'src') {
        state.srcSid = d.sid;
        state.srcDisplayName = d.display_name;
      } else {
        state.destSid = d.sid;
        state.destDisplayName = d.display_name;
      }
      showToast('Deezer conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return true;
    }

    const message = humanizePlatformError(d.error || 'Falha ao conectar Deezer');
    if (status) status.textContent = message;
    showToast(message, 'error');
    return false;
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar Deezer', 'error');
    return false;
  }
}

async function readDeezerCookieFromBrowser(role) {
  const input = document.getElementById(`${role}-deezer-cookie`);
  const status = document.getElementById(`${role}-deezer-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Tentando buscar o Deezer salvo nesta maquina...';

  try {
    const r = await fetch('/api/connect/deezer/browser-cookie', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();

    if (!d.ok) {
      const message = humanizePlatformError(d.error || 'Falha ao buscar o Deezer no navegador');
      if (status) {
        if (String(message || '').toLowerCase().includes('chrome')) {
          status.textContent = `${message} Abrir e entrar no Deezer nao remove essa trava do Chrome. Para continuar agora, use o passo manual logo abaixo.`;
        } else {
          status.textContent = `${message} O PlayTransfer continua nesta tela. Se precisar, siga pelo passo manual logo abaixo.`;
        }
      }
      showToast(message, 'warn');
      return;
    }

    if (input) {
      input.value = d.arl || '';
      input.focus();
    }

    if (status) {
      status.innerHTML = `<span class="spin-inline"></span> Valor encontrado no ${escapeHtml(d.browser || 'navegador')}. Confirmando conexao...`;
    }
    await connectDeezer(role);
  } catch {
    if (status) {
      status.textContent = 'Nao consegui buscar o Deezer automaticamente agora. O PlayTransfer continua nesta tela; se precisar, siga pelo passo manual logo abaixo.';
    }
    showToast('Nao consegui buscar o Deezer automaticamente nesta maquina.', 'warn');
  }
}

function advanceDeezerGuidedCapture(role) {
  const status = document.getElementById(`${role}-deezer-status`);

  // Se o Deezer não foi aberto ainda, abre automaticamente antes de capturar
  if (!state.deezerTabsOpened?.[role]) {
    if (status) {
      status.innerHTML = '<span class="spin-inline"></span> Abrindo o Deezer...';
    }
    openDeezerTab(role);
    // Espera o Deezer carregar antes de tentar capturar
    setTimeout(() => {
      advanceDeezerGuidedCapture(role);
    }, 3000);
    return;
  }

  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Buscando o login do Deezer...';
  }
  const deezerTab = deezerTabRefs[role];
  if (deezerTab && !deezerTab.closed) {
    try {
      deezerTab.focus();
    } catch {}
  }

  setTimeout(() => startDeezerChromeAutomation(role), 260);
  setTimeout(() => {
    try {
      window.focus();
    } catch {}
  }, 2600);
}

function openDeezerTab(role) {
  // Verifica se já existe uma aba do Deezer aberta por nós
  const existingTab = deezerTabRefs[role];
  if (existingTab && !existingTab.closed) {
    try {
      existingTab.focus();
    } catch {}
    state.deezerTabsOpened[role] = true;
    return existingTab;
  }

  const deezerTab = window.open('https://www.deezer.com/', '_blank');

  if (!deezerTab) {
    const status = document.getElementById(`${role}-deezer-status`);
    if (status) {
      status.textContent = 'O navegador bloqueou a aba do Deezer. Libere pop-ups para este site e tente de novo.';
    }
    return null;
  }

  deezerTabRefs[role] = deezerTab;
  state.deezerTabsOpened[role] = true;

  const status = document.getElementById(`${role}-deezer-status`);
  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Deezer aberto. Aguardando carregamento...';
  }

  setTimeout(() => {
    try {
      deezerTab.blur();
      window.focus();
    } catch {}
  }, 150);

  return deezerTab;
}

/**
 * autoConnectDeezer — Fluxo unificado de conexão automática do Deezer.
 * 1. Tenta ler ARL dos cookies salvos no navegador (browser_cookie3)
 * 2. Se falhar, abre o Deezer em nova aba e tenta automação via Chrome DevTools
 * 3. Se tudo falhar, orienta o usuário pelo modo manual
 */
async function autoConnectDeezer(role) {
  const status = document.getElementById(`${role}-deezer-status`);
  const btn = document.getElementById(`${role}-deezer-auto-btn`);
  const hint = document.getElementById(`${role}-deezer-hint`);

  state.deezerAutoConnecting = state.deezerAutoConnecting || {};
  state.deezerAutoConnecting[role] = true;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin-inline"></span> Conectando...';
  }

  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Tentando encontrar o login do Deezer nos seus navegadores...';
  }

  // Etapa 1: Tentar ler cookie ARL direto dos navegadores da máquina
  try {
    const r = await fetch('/api/connect/deezer/browser-cookie', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();

    if (d.ok && d.arl) {
      if (status) {
        status.innerHTML = `<span class="spin-inline"></span> Login encontrado no ${escapeHtml(d.browser || 'navegador')}! Confirmando...`;
      }
      const input = document.getElementById(`${role}-deezer-cookie`);
      if (input) input.value = d.arl;

      try {
        const success = await connectDeezer(role);
        if (success) {
          state.deezerAutoConnecting[role] = false;
          return; // Sucesso!
        }
        // ARL encontrado mas inválido, continua para etapa 2
      } catch {
        // Falhou inesperadamente, continua para etapa 2
      }
    }
  } catch {
    // browser_cookie3 não disponível ou falhou, continua
  }

  // Etapa 2: Esperar o backend abrir a janela WebView segura e ler o ARL
  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Uma janela limpa de login do Deezer vai abrir na sua tela principal...';
  }
  if (hint) {
    hint.textContent = 'Faca o login na janela que acabou de abrir. Ela fechara sozinha quando der certo.';
  }

  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Capturando o login do Deezer...';
  }

  // Inicia automação Chrome e monitora resultado
  try {
    const r = await fetch('/api/connect/deezer/browser-guided/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();
    if (!d.ok) {
      throw new Error(d.error || 'Falha ao iniciar captura');
    }

    // Poll para resultado
    await pollDeezerAutoConnect(role, 0);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha na captura automatica');
    if (status) {
      status.textContent = `${message} Use o modo manual abaixo.`;
    }
    resetDeezerAutoBtn(role);
  }

  // Volta o foco para o PlayTransfer
  setTimeout(() => {
    try { window.focus(); } catch {}
  }, 1500);
}

async function pollDeezerAutoConnect(role, attempt) {
  const status = document.getElementById(`${role}-deezer-status`);
  const input = document.getElementById(`${role}-deezer-cookie`);

  try {
    const r = await fetch(`/api/connect/deezer/browser-guided/status?role=${encodeURIComponent(role)}`);
    const d = await r.json();

    if (d.status === 'captured' && d.arl) {
      if (input) input.value = d.arl;
      if (status) {
        status.innerHTML = '<span class="spin-inline"></span> Login capturado! Confirmando conexao...';
      }
      try { window.focus(); } catch {}
      const success = await connectDeezer(role);
      if (success) {
        state.deezerAutoConnecting[role] = false;
        return;
      }
      
      resetDeezerAutoBtn(role);
      return;
    }

    if (d.status === 'error') {
      const rawError = String(d.error || '');
      let message = humanizePlatformError(rawError || 'Falha na captura automatica');
      if (rawError === 'missing_arl') {
        message = 'Nao encontrei o login do Deezer. Verifique se voce esta logado no Deezer e tente de novo, ou use o modo manual abaixo.';
      } else if (rawError.includes('chrome_window_not_found')) {
        message = 'Nao encontrei a janela do navegador. Tente de novo ou use o modo manual abaixo.';
      }
      if (status) status.textContent = message;
      try { window.focus(); } catch {}
      resetDeezerAutoBtn(role);
      return;
    }
  } catch {
    if (status) status.textContent = 'Erro ao acompanhar a captura. Tente de novo ou use o modo manual.';
    resetDeezerAutoBtn(role);
    return;
  }

  if (attempt >= 18) {
    if (status) status.textContent = 'A captura demorou demais. Tente de novo ou use o modo manual abaixo.';
    try { window.focus(); } catch {}
    resetDeezerAutoBtn(role);
    return;
  }

  setTimeout(() => pollDeezerAutoConnect(role, attempt + 1), 900);
}

function resetDeezerAutoBtn(role) {
  state.deezerAutoConnecting = state.deezerAutoConnecting || {};
  state.deezerAutoConnecting[role] = false;
  const btn = document.getElementById(`${role}-deezer-auto-btn`);
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = '🔌 Tentar novamente';
  }
}

async function startDeezerChromeAutomation(role) {
  const status = document.getElementById(`${role}-deezer-status`);

  if (state.deezerCapturePolls?.[role]) {
    clearTimeout(state.deezerCapturePolls[role]);
    state.deezerCapturePolls[role] = null;
  }

  try {
    const r = await fetch('/api/connect/deezer/browser-guided/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();
    if (!d.ok) {
      throw new Error(d.error || 'Falha ao iniciar a automacao do Deezer');
    }

    if (status) {
      status.textContent = 'Tentando usar a aba do Deezer que voce abriu.';
    }
    pollDeezerChromeAutomation(role, 0);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha ao iniciar a automacao do Deezer');
    if (status) {
      status.textContent = `${message} Se precisar, siga pelo passo manual logo abaixo.`;
    }
  }
}

async function pollDeezerChromeAutomation(role, attempt = 0) {
  const input = document.getElementById(`${role}-deezer-cookie`);
  const status = document.getElementById(`${role}-deezer-status`);

  try {
    const r = await fetch(`/api/connect/deezer/browser-guided/status?role=${encodeURIComponent(role)}`);
    const d = await r.json();

    if (d.status === 'captured' && d.arl) {
      if (input) {
        input.value = d.arl;
        input.focus();
      }
      if (status) {
        status.innerHTML = '<span class="spin-inline"></span> Login reconhecido no Chrome. Confirmando conexao...';
      }
      await connectDeezer(role);
      return;
    }

    if (d.status === 'error') {
      const rawError = String(d.error || 'Falha ao automatizar o Deezer');
      let message = humanizePlatformError(rawError);
      if (rawError === 'missing_arl') {
        message = 'Nao consegui extrair o login do Deezer automaticamente agora. Se precisar, use o modo manual abaixo.';
      } else if (rawError.includes('chrome_window_not_found')) {
        message = 'Nao encontrei uma janela do Chrome pronta para automatizar agora.';
      }
      if (status) {
        status.textContent = message;
      }
      return;
    }

    if (status && attempt === 0) {
      status.textContent = 'Tentando usar a aba do Deezer...';
    }
  } catch {
    if (status) {
      status.textContent = 'Nao consegui acompanhar a automacao do Deezer agora. Se precisar, use o modo manual abaixo.';
    }
    return;
  }

  if (attempt >= 16) {
    if (status) {
      status.textContent = 'A tentativa automatica do Deezer demorou demais. Se precisar, use o modo manual abaixo.';
    }
    return;
  }

  state.deezerCapturePolls[role] = setTimeout(() => {
    pollDeezerChromeAutomation(role, attempt + 1);
  }, 900);
}


async function connectYoutube(role) {
  const input = document.getElementById(`${role}-ytm-curl`);
  let headers = input?.value?.trim() || '';
  const status = document.getElementById(`${role}-ytm-status`);

  if (!headers) {
    try {
      headers = await navigator.clipboard.readText();
      headers = String(headers || '').trim();
      if (headers && input) input.value = headers;
    } catch {
      // segue para a mensagem amigavel abaixo
    }
  }

  if (!headers) {
    showToast('Copie o texto do navegador no YouTube Music e toque em "Usar o que copiei" ou cole manualmente aqui.', 'warn');
    return;
  }

  if (status) status.innerHTML = '<span class="spin-inline"></span> Confirmando acesso...';

  try {
    const r = await fetch('/api/connect/youtube', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ headers_raw: headers }),
    });
    const d = await r.json();

    if (d.ok) {
      if (role === 'src') {
        state.srcSid = d.sid;
        state.srcDisplayName = d.display_name;
      } else {
        state.destSid = d.sid;
        state.destDisplayName = d.display_name;
      }
      showToast('YouTube Music conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return;
    }

    const message = humanizePlatformError(d.error || 'Falha ao conectar YouTube Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar YouTube Music', 'error');
  }
}

async function startYoutubeAutoConnect(role) {
  const status = document.getElementById(`${role}-ytm-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Abrindo uma nova aba do Google...';

  try {
    const r = await fetch('/api/connect/youtube/auto/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();

    if (d.ok && d.sid) {
      if (role === 'src') {
        state.srcSid = d.sid;
        state.srcDisplayName = d.display_name;
      } else {
        state.destSid = d.sid;
        state.destDisplayName = d.display_name;
      }
      state.youtubePending[role] = null;
      showToast('YouTube Music conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return;
    }

    if (d.ok && d.pending) {
      const targetUrl = d.verification_url_complete || d.verification_url || '';
      if (targetUrl) {
        const openedTab = window.open(targetUrl, '_blank', 'noopener');
        if (!openedTab) {
          window.location.href = targetUrl;
          return;
        }
      }

      state.youtubePending[role] = {
        loginId: d.login_id,
        verificationUrl: targetUrl,
        userCode: d.user_code || '',
        retryMs: Math.max(3000, Number(d.interval || 5) * 1000),
      };
      renderConnectForms();
      if (status) {
        status.textContent = d.user_code
          ? `Se o Google pedir, confirme usando o codigo ${d.user_code}.`
          : 'Conclua a autorizacao na nova aba do Google.';
      }
      showToast('Abri uma nova aba do Google neste mesmo navegador. Quando voce autorizar, esta tela tenta concluir sozinha.', 'info');
      setTimeout(() => finishYoutubeAutoConnect(role), 2500);
      return;
    }

    const message = humanizePlatformError(d.error || 'Falha ao abrir o YouTube Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao abrir o YouTube Music automaticamente', 'error');
  }
}

async function finishYoutubeAutoConnect(role) {
  const pending = state.youtubePending?.[role];
  if (!pending?.loginId) {
    showToast('Abra o login do Google para o YouTube Music primeiro.', 'warn');
    return;
  }

  const status = document.getElementById(`${role}-ytm-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Confirmando a conta...';

  try {
    const r = await fetch('/api/connect/youtube/auto/finish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ login_id: pending.loginId }),
    });
    const d = await r.json();

    if (d.ok) {
      if (role === 'src') {
        state.srcSid = d.sid;
        state.srcDisplayName = d.display_name;
      } else {
        state.destSid = d.sid;
        state.destDisplayName = d.display_name;
      }
      state.youtubePending[role] = null;
      showToast('YouTube Music conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return;
    }

    if (d.pending) {
      if (status) {
        status.textContent = pending.userCode
          ? `Ainda aguardando a autorizacao. Se o Google pedir, use o codigo ${pending.userCode}.`
          : 'Ainda aguardando a autorizacao na aba do Google.';
      }
      setTimeout(() => finishYoutubeAutoConnect(role), Number(d.retry_after_ms || pending.retryMs || 4000));
      return;
    }

    if (status) status.textContent = humanizePlatformError(d.error || 'Falha ao confirmar o YouTube Music');
    state.youtubePending[role] = null;
    showToast(humanizePlatformError(d.error || 'Falha ao confirmar o YouTube Music'), 'error');
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao confirmar o YouTube Music', 'error');
  }
}

function reopenYoutubeOAuthTab(role) {
  const pending = state.youtubePending?.[role];
  const targetUrl = pending?.verificationUrl;
  if (!targetUrl) {
    showToast('O link do Google nao esta mais disponivel. Abra o login novamente.', 'warn');
    return;
  }

  const openedTab = window.open(targetUrl, '_blank', 'noopener');
  if (!openedTab) {
    window.location.href = targetUrl;
  }
}

async function pasteYoutubeFromClipboard(role) {
  const input = document.getElementById(`${role}-ytm-curl`);
  if (!input) return;
  const currentValue = String(input.value || '').trim();

  if (!navigator.clipboard?.readText) {
    if (currentValue) {
      input.focus();
      showToast('O campo ja esta preenchido. Agora e so tocar em "Conectar YouTube Music".', 'success');
      return;
    }
    showToast('Seu navegador nao liberou a area de transferencia. Cole manualmente no campo abaixo.', 'warn');
    return;
  }

  try {
    const clipboardText = String((await navigator.clipboard.readText()) || '').trim();
    if (!clipboardText) {
      if (currentValue) {
        input.focus();
        showToast('O campo ja esta preenchido. Agora e so tocar em "Conectar YouTube Music".', 'success');
        return;
      }
      showToast('Nao encontrei nada copiado agora. No navegador, clique com o botao direito na linha "browse" e escolha "Copy as cURL (bash)".', 'warn');
      return;
    }

    input.value = clipboardText;
    input.focus();
    showToast('Texto colado. Agora e so tocar em "Conectar YouTube Music".', 'success');
  } catch {
    showToast('Nao consegui ler a area de transferencia. Cole manualmente no campo abaixo.', 'warn');
  }
}

function checkTransferReady() {
  const url = document.getElementById('playlist-url')?.value?.trim();
  const srcOk = isSourceReady();
  const destOk = !!state.destSid;
  const urlOk = !!url;
  const btn = document.getElementById('btn-transfer');
  if (btn) btn.disabled = !(srcOk && destOk && urlOk);
}


function getOAuthConsentCopy(platform, role) {
  const names = { spotify: 'Spotify', deezer: 'Deezer' };
  const name = names[platform] || 'servico';
  const action =
    role === 'src'
      ? 'ler sua playlist completa e encontrar todas as musicas'
      : 'criar a nova playlist na sua conta';

  return {
    name,
    actionLabel: role === 'src' ? 'Leitura da playlist' : 'Criacao da playlist',
    title: `Autorizar ${name}`,
    subtitle: `Precisamos da sua permissao porque o ${name} nao deixa que outro site entre na sua conta sozinho. Sem essa etapa, o PlayTransfer nao consegue ${action}.`,
    points: [
      `O login acontece no site oficial do ${name}.`,
      'Sua senha nao passa pelo PlayTransfer.',
      `A permissao sera usada apenas para ${action}.`,
      'Se preferir, voce pode cancelar agora e nao continuar.',
    ],
    agreementLabel: `Entendi por que essa autorizacao e pedida e quero continuar com o ${name}.`,
    confirmLabel: `Continuar para o ${name}`,
  };
}

function ensureOAuthConsentModal() {
  let modal = document.getElementById('oauth-consent-modal');
  if (modal) {
    return modal;
  }

  modal = document.createElement('div');
  modal.id = 'oauth-consent-modal';
  modal.className = 'modal-backdrop consent-modal-backdrop';
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <div class="modal consent-modal" role="dialog" aria-modal="true" aria-labelledby="oauth-consent-title">
      <button type="button" class="modal-close" id="oauth-consent-close" aria-label="Fechar">×</button>
      <div class="consent-platform-card">
        <div class="consent-platform-icon" id="oauth-consent-icon"></div>
        <div>
          <div class="consent-platform-label">Permissao solicitada</div>
          <div class="consent-platform-role" id="oauth-consent-role"></div>
        </div>
      </div>
      <h2 id="oauth-consent-title"></h2>
      <p id="oauth-consent-subtitle"></p>
      <div class="consent-points" id="oauth-consent-points"></div>
      <label class="consent-checkbox">
        <input type="checkbox" id="oauth-consent-checkbox" />
        <span id="oauth-consent-agreement"></span>
      </label>
      <div class="consent-actions">
        <button type="button" class="btn btn-secondary" id="oauth-consent-cancel">Agora nao</button>
        <button type="button" class="btn btn-primary" id="oauth-consent-continue" disabled>Continuar</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  const checkbox = modal.querySelector('#oauth-consent-checkbox');
  const continueButton = modal.querySelector('#oauth-consent-continue');
  const cancelButton = modal.querySelector('#oauth-consent-cancel');
  const closeButton = modal.querySelector('#oauth-consent-close');

  checkbox.addEventListener('change', () => {
    continueButton.disabled = !checkbox.checked;
  });

  const close = () => closeOAuthConsentModal();
  cancelButton.addEventListener('click', close);
  closeButton.addEventListener('click', close);

  continueButton.addEventListener('click', () => {
    const { platform, role } = modal.dataset;
    closeOAuthConsentModal();
    launchOAuthPopup(platform, role);
  });

  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeOAuthConsentModal();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('open')) {
      closeOAuthConsentModal();
    }
  });

  return modal;
}

function closeOAuthConsentModal() {
  const modal = document.getElementById('oauth-consent-modal');
  if (!modal) {
    return;
  }

  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');

  const checkbox = modal.querySelector('#oauth-consent-checkbox');
  const continueButton = modal.querySelector('#oauth-consent-continue');
  if (checkbox) {
    checkbox.checked = false;
  }
  if (continueButton) {
    continueButton.disabled = true;
  }
}

function launchOAuthPopup(platform, role) {
  const url = `/auth/${platform}?role=${role}`;
  const w = 520;
  const h = 640;
  const left = (screen.width - w) / 2;
  const top = (screen.height - h) / 2;
  const popup = window.open(
    url,
    'oauth_popup',
    `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no`
  );
  if (!popup) {
    window.location.href = url;
  }
}

function openOAuthPopup(platform, role) {
  const modal = ensureOAuthConsentModal();
  const copy = getOAuthConsentCopy(platform, role);

  modal.dataset.platform = platform;
  modal.dataset.role = role;

  modal.querySelector('#oauth-consent-icon').innerHTML = PLATFORM_ICONS[platform] || '';
  modal.querySelector('#oauth-consent-role').textContent = copy.actionLabel;
  modal.querySelector('#oauth-consent-title').textContent = copy.title;
  modal.querySelector('#oauth-consent-subtitle').textContent = copy.subtitle;
  modal.querySelector('#oauth-consent-agreement').textContent = copy.agreementLabel;
  modal.querySelector('#oauth-consent-continue').textContent = copy.confirmLabel;
  modal.querySelector('#oauth-consent-points').innerHTML = copy.points
    .map((point) => `
      <div class="consent-point">
        <span class="consent-point-mark">✓</span>
        <span>${escapeHtml(point)}</span>
      </div>
    `)
    .join('');

  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');

  const checkbox = modal.querySelector('#oauth-consent-checkbox');
  const continueButton = modal.querySelector('#oauth-consent-continue');
  checkbox.checked = false;
  continueButton.disabled = true;

  setTimeout(() => checkbox.focus(), 30);
}

function getBrowserCookieConsentCopy(platform) {
  if (platform === 'deezer') {
    return {
      name: 'Deezer',
      actionLabel: 'Captura automatica',
      title: 'Autorizar captura automatica do Deezer',
      subtitle: 'O PlayTransfer vai usar a aba do Deezer que voce abriu para tentar capturar o login automaticamente.',
      points: [
        'Primeiro abra o Deezer por este site.',
        'Depois volte para o PlayTransfer e confirme esta captura.',
        'Sua senha nao passa pelo PlayTransfer.',
        'Se nao funcionar, voce continua aqui e o modo manual fica logo abaixo.',
      ],
      agreementLabel: 'Autorizo essa tentativa automatica usando a aba do Deezer que eu abri.',
      confirmLabel: 'Capturar agora',
    };
  }

  return {
    name: 'navegador',
    actionLabel: 'Leitura local',
    title: 'Autorizar leitura local',
    subtitle: 'O PlayTransfer vai tentar ler dados salvos no navegador desta maquina.',
    points: [
      'A leitura acontece apenas no computador local.',
      'Nenhuma senha e pedida nesta tela.',
    ],
    agreementLabel: 'Entendi e quero continuar.',
    confirmLabel: 'Continuar',
  };
}

function ensureBrowserCookieConsentModal() {
  let modal = document.getElementById('browser-cookie-consent-modal');
  if (modal) {
    return modal;
  }

  modal = document.createElement('div');
  modal.id = 'browser-cookie-consent-modal';
  modal.className = 'modal-backdrop consent-modal-backdrop';
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <div class="modal consent-modal" role="dialog" aria-modal="true" aria-labelledby="browser-cookie-consent-title">
      <button type="button" class="modal-close" id="browser-cookie-consent-close" aria-label="Fechar">×</button>
      <div class="consent-platform-card">
        <div class="consent-platform-icon" id="browser-cookie-consent-icon"></div>
        <div>
          <div class="consent-platform-label">Permissao solicitada</div>
          <div class="consent-platform-role" id="browser-cookie-consent-role"></div>
        </div>
      </div>
      <h2 id="browser-cookie-consent-title"></h2>
      <p id="browser-cookie-consent-subtitle"></p>
      <div class="consent-points" id="browser-cookie-consent-points"></div>
      <label class="consent-checkbox">
        <input type="checkbox" id="browser-cookie-consent-checkbox" />
        <span id="browser-cookie-consent-agreement"></span>
      </label>
      <div class="consent-actions">
        <button type="button" class="btn btn-secondary" id="browser-cookie-consent-cancel">Agora nao</button>
        <button type="button" class="btn btn-primary" id="browser-cookie-consent-continue" disabled>Continuar</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  const checkbox = modal.querySelector('#browser-cookie-consent-checkbox');
  const continueButton = modal.querySelector('#browser-cookie-consent-continue');
  const cancelButton = modal.querySelector('#browser-cookie-consent-cancel');
  const closeButton = modal.querySelector('#browser-cookie-consent-close');

  checkbox.addEventListener('change', () => {
    continueButton.disabled = !checkbox.checked;
  });

  const close = () => closeBrowserCookieConsentModal();
  cancelButton.addEventListener('click', close);
  closeButton.addEventListener('click', close);

  continueButton.addEventListener('click', () => {
    const { platform, role } = modal.dataset;
    closeBrowserCookieConsentModal();
    if (platform === 'deezer') {
      advanceDeezerGuidedCapture(role);
    }
  });

  modal.addEventListener('click', (event) => {
    if (event.target === modal) {
      closeBrowserCookieConsentModal();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('open')) {
      closeBrowserCookieConsentModal();
    }
  });

  return modal;
}

function closeBrowserCookieConsentModal() {
  const modal = document.getElementById('browser-cookie-consent-modal');
  if (!modal) {
    return;
  }

  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');

  const checkbox = modal.querySelector('#browser-cookie-consent-checkbox');
  const continueButton = modal.querySelector('#browser-cookie-consent-continue');
  if (checkbox) {
    checkbox.checked = false;
  }
  if (continueButton) {
    continueButton.disabled = true;
  }
}

function openBrowserCookieConsent(platform, role) {
  if (platform === 'deezer') {
    advanceDeezerGuidedCapture(role);
    return;
  }

  const modal = ensureBrowserCookieConsentModal();
  const copy = getBrowserCookieConsentCopy(platform);

  modal.dataset.platform = platform;
  modal.dataset.role = role;

  modal.querySelector('#browser-cookie-consent-icon').innerHTML = PLATFORM_ICONS[platform] || '';
  modal.querySelector('#browser-cookie-consent-role').textContent = copy.actionLabel;
  modal.querySelector('#browser-cookie-consent-title').textContent = copy.title;
  modal.querySelector('#browser-cookie-consent-subtitle').textContent = copy.subtitle;
  modal.querySelector('#browser-cookie-consent-agreement').textContent = copy.agreementLabel;
  modal.querySelector('#browser-cookie-consent-continue').textContent = copy.confirmLabel;
  modal.querySelector('#browser-cookie-consent-points').innerHTML = copy.points
    .map((point) => `
      <div class="consent-point">
        <span class="consent-point-mark">✓</span>
        <span>${escapeHtml(point)}</span>
      </div>
    `)
    .join('');

  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');

  const checkbox = modal.querySelector('#browser-cookie-consent-checkbox');
  const continueButton = modal.querySelector('#browser-cookie-consent-continue');
  checkbox.checked = false;
  continueButton.disabled = true;

  setTimeout(() => checkbox.focus(), 30);
}

function humanizePlatformError(message) {
  const raw = String(message || '').trim();
  if (!raw) {
    return 'Nao foi possivel concluir essa etapa agora.';
  }

  const lowered = raw.toLowerCase();

  if (lowered.includes('playlist pode ter mais de 50')) {
    if (state.platforms.spotify?.oauth_configured) {
      return 'Essa playlist do Spotify e grande. Clique em "Entrar e autorizar" para liberar a leitura completa.';
    }
    return 'Essa playlist do Spotify e maior do que o acesso publico permite nesta instalacao.';
  }

  if (
    lowered.includes('nao esta publico') ||
    lowered.includes('nao esta publica') ||
    lowered.includes('acesso compartilhado ou protegido')
  ) {
    return 'Essa playlist do Spotify nao esta publica. Sem entrar no Spotify, o app nao consegue abrir ela.';
  }

  if (
    lowered.includes('sp_dc') ||
    lowered.includes('http 400') ||
    lowered.includes('spotify recusou o cookie') ||
    lowered.includes('cookie informado')
  ) {
    if (state.platforms.spotify?.oauth_configured) {
      return 'O modo manual do Spotify nao conseguiu confirmar sua sessao. Use o login oficial em "Entrar e autorizar".';
    }
    return 'O modo manual do Spotify nao conseguiu confirmar sua sessao. Para evitar isso de vez, esta instalacao ainda precisa ativar o login oficial do Spotify.';
  }

  if (lowered.includes('spotify_oauth_not_configured')) {
    return 'O login automatico do Spotify ainda nao foi ativado nesta instalacao.';
  }

  if (lowered.includes('nao encontrei o cookie arl do deezer')) {
    return 'Nao achei o login do Deezer salvo nos navegadores desta maquina. Abra o Deezer ja logado e tente de novo.';
  }

  if (lowered.includes('chrome desta maquina bloqueou a leitura automatica do deezer')) {
    return 'O Chrome desta maquina bloqueou a leitura automatica do Deezer. Essa permissao nao pode ser liberada por este site.';
  }

  if (lowered.includes('chrome_window_not_found')) {
    return 'Nao encontrei uma janela do Chrome pronta para automatizar agora.';
  }

  if (lowered.includes('missing_arl')) {
    return 'Nao consegui extrair o login do Deezer automaticamente nessa tentativa.';
  }

  if (lowered.includes('nao consegui confirmar a captura automatica no chrome')) {
    return 'Nao consegui achar o login do Deezer nessa tentativa. Se a aba do Deezer ja esta aberta e logada, toque em "Capturar automaticamente" de novo.';
  }

  if (lowered.includes('leitura automatica do navegador ainda nao esta instalada')) {
    return 'A busca automatica no navegador ainda nao esta pronta nesta instalacao.';
  }

  if (lowered.includes('sessao invalida ou expirada')) {
    return 'O cookie encontrado do Deezer nao vale mais. Abra o Deezer de novo, atualize a pagina e tente outra vez.';
  }

  if (lowered.includes('token_exchange_failed') || lowered.includes('invalid_state')) {
    return 'O login oficial do Spotify nao terminou corretamente. Tente novamente.';
  }

  if (lowered.includes('headers do youtube music')) {
    return 'Copie o cURL completo do YouTube Music para continuar. Nao copie Payload, Preview ou Response.';
  }

  if (
    lowered.includes('payload da requisicao browse') ||
    lowered.includes('copy as curl') ||
    lowered.includes('copy as cURL'.toLowerCase())
  ) {
    return 'Voce colou o conteudo da requisicao browse, nao o cURL completo. No Chrome, clique com o botao direito na linha "browse" e escolha "Copy > Copy as cURL (bash)".';
  }

  if (
    lowered.includes('nao encontrei os dados da sua sessao do youtube music') ||
    lowered.includes('nao consegui entender o texto colado do youtube music')
  ) {
    return 'Nao encontrei a sessao do YouTube Music nesse texto. No Chrome, clique com o botao direito na linha "browse" e escolha "Copy > Copy as cURL (bash)", sem copiar Payload, Preview ou Response.';
  }

  if (lowered.includes('falha na autenticacao do youtube music')) {
    return 'Nao consegui confirmar essa conta do YouTube Music. Copie de novo no navegador e tente outra vez.';
  }

  if (lowered.includes('ytmusicapi')) {
    return 'O YouTube Music ainda nao esta pronto nesta instalacao.';
  }

  if (lowered.includes('login oficial do youtube music ainda nao foi ativado')) {
    return 'O login oficial do YouTube Music ainda nao foi ativado nesta instalacao.';
  }

  if (lowered.includes('login do google foi cancelado')) {
    return 'O login do Google foi cancelado antes de terminar.';
  }

  if (lowered.includes('login do youtube music expirou')) {
    return 'O login do YouTube Music expirou. Abra novamente.';
  }

  if (lowered.includes('janela guiada do youtube music expirou')) {
    return 'A janela do YouTube Music expirou. Abra de novo e tente mais uma vez.';
  }

  if (lowered.includes('ainda nao consegui confirmar sua conta do youtube music')) {
    return 'Entre na conta certa na janela do YouTube Music e depois toque em "Ja entrei".';
  }

  if (lowered.includes('nao consegui abrir a janela guiada do youtube music')) {
    return 'Nao consegui abrir a janela do YouTube Music automaticamente nesta instalacao.';
  }

  if (
    lowered.includes('handshake status 403') ||
    lowered.includes('rejected an incoming websocket connection') ||
    lowered.includes('remote-allow-origins')
  ) {
    return 'O navegador bloqueou a confirmacao automatica desta vez. Abra o login do YouTube Music de novo.';
  }

  return raw;
}

function clearToasts() {
  const container = document.getElementById('toast-container');
  if (container) container.innerHTML = '';
}

function renderPlatformGrids() {
  const platforms = state.platforms;
  const srcGrid = document.getElementById('src-grid');
  const destGrid = document.getElementById('dest-grid');
  const srcSoon = document.getElementById('src-soon');
  const destSoon = document.getElementById('dest-soon');
  if (!srcGrid || !destGrid || !platforms) return;

  srcGrid.innerHTML = '';
  destGrid.innerHTML = '';
  if (srcSoon) srcSoon.innerHTML = '';
  if (destSoon) destSoon.innerHTML = '';

  Object.entries(platforms).forEach(([key, platform]) => {
    srcGrid.appendChild(makePlatformCard(key, platform, 'src', !platform.can_read));
    destGrid.appendChild(makePlatformCard(key, platform, 'dest', !platform.can_write));
  });

  const soonSection = document.querySelector('.soon-section');
  if (soonSection) soonSection.style.display = 'none';
}

function isSourceConnectionOptional(platform) {
  return OPTIONAL_SOURCE_CONNECTIONS.has(platform) || (platform === 'spotify' && !state.platforms.spotify?.oauth_configured);
}

function updateUrlHint() {
  const hints = {
    spotify: 'Ex.: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M',
    deezer: 'Ex.: https://www.deezer.com/br/playlist/1234567890',
    youtube: 'Ex.: https://music.youtube.com/playlist?list=PLxxxxxx',
    soundcloud: 'Ex.: https://soundcloud.com/usuario/sets/nome-da-playlist',
    apple: 'Ex.: https://music.apple.com/br/playlist/nome/pl.xxxxxx',
    tidal: 'Ex.: https://listen.tidal.com/playlist/00000000-0000-0000-0000-000000000000',
    amazon: 'Ex.: https://music.amazon.com/my/playlists/abcd1234',
  };

  let hint = hints[state.srcPlatform] || 'Cole o link completo da playlist.';
  if (state.srcPlatform === 'spotify' && !state.platforms.spotify?.oauth_configured) {
    hint += ' Playlists publicas menores funcionam direto; playlists privadas ou maiores ainda nao estao disponiveis por completo aqui.';
  } else if (isSourceConnectionOptional(state.srcPlatform)) {
    hint += ' Para playlists publicas, voce pode pular o login da origem.';
  } else if (state.srcPlatform === 'spotify') {
    hint += ' Se a playlist for privada ou muito grande, entre no Spotify antes.';
  }

  const el = document.getElementById('url-hint');
  if (el) el.textContent = hint;
}

function showToast(msg, type = 'info') {
  const icons = { success: '✅', error: '❌', warn: '⚠️', info: 'ℹ️' };
  const finalMsg = humanizePlatformError(msg);
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<div class="toast-icon">${icons[type]}</div><div class="toast-msg">${escapeHtml(finalMsg)}</div>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

function handleTransferError(ev) {
  clearInterval(state.pollTimer);
  const message = humanizePlatformError(ev.message);
  document.getElementById('progress-status').textContent = `Erro: ${message}`;
  showToast(message, 'error');
}

async function connectSpotify(role) {
  const spDc = document.getElementById(`${role}-spotify-cookie`)?.value?.trim() || '';
  const status = document.getElementById(`${role}-spotify-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';

  try {
    const r = await fetch('/api/connect/spotify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ sp_dc: spDc }),
    });
    const d = await r.json();

    if (d.ok) {
      if (role === 'src') {
        state.srcSid = d.sid;
        state.srcDisplayName = d.display_name;
      } else {
        state.destSid = d.sid;
        state.destDisplayName = d.display_name;
      }
      showToast('Spotify conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return;
    }

    const message = humanizePlatformError(d.error || 'Falha ao conectar Spotify');
    if (status) status.textContent = message;
    showToast(message, 'error');
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar Spotify', 'error');
  }
}
