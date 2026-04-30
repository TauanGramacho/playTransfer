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
  spotifyAutoConnecting: {},
  spotifyCapturePolls: {},
  platformAutoConnecting: {},
  youtubePending: {},
  youtubeAutoConnecting: {},
  deezerCapturePolls: {},
  deezerTabsOpened: {},
  soundcloudCapturePolls: {},
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
    if (!isAllowedOAuthMessageOrigin(evt.origin)) return;
    const d = evt.data;
    if (d.type !== 'oauth_done') return;

    if (d.error) {
      const platform = d.platform || 'spotify';
      const role = d.role || 'dest';
      const message = humanizePlatformError(d.error);
      const status = document.getElementById(`${role}-${platform}-status`);
      if (platform === 'amazon' && isAmazonOfficialAccessError(d.error)) {
        renderAmazonOfficialAccessNotice(role, d.error);
      } else if (status) {
        status.textContent = message;
      }
      if (platform === 'spotify') resetSpotifyAutoBtn(role);
      if (platform === 'amazon') resetPlatformAutoButton('amazon', role, 'Conectar Amazon Music');
      showToast(message, platform === 'amazon' && isAmazonOfficialAccessError(d.error) ? 'warn' : 'error');
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

const OPTIONAL_SOURCE_CONNECTIONS = new Set(['spotify', 'deezer', 'youtube', 'soundcloud', 'apple']);


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

function openAdvancedConnection(detailsId, inputId = '') {
  const details = document.getElementById(detailsId);
  if (!details) return;
  details.open = true;
  details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  if (inputId) {
    setTimeout(() => document.getElementById(inputId)?.focus(), 140);
  }
}

async function startYoutubeManualGuided(role) {
  openAdvancedConnection(`${role}-youtube-manual-details`, `${role}-ytm-curl`);
  const status = document.getElementById(`${role}-ytm-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Tentando usar o que voce ja copiou...';

  await pasteYoutubeFromClipboard(role);

  const input = document.getElementById(`${role}-ytm-curl`);
  const hasValue = !!String(input?.value || '').trim();
  if (status) {
    status.textContent = hasValue
      ? 'Revise o texto colado e toque em "Conectar YouTube Music".'
      : 'Copie a linha "browse" como cURL no navegador e cole aqui para continuar.';
  }
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
  if (typeof resetAppleGuidedPoll === 'function') {
    resetAppleGuidedPoll('src');
    resetAppleGuidedPoll('dest');
  }
  Object.values(state.deezerCapturePolls || {}).forEach((timer) => {
    if (timer) clearTimeout(timer);
  });
  Object.keys(deezerTabRefs).forEach((key) => {
    delete deezerTabRefs[key];
  });
  state.deezerTabsOpened = {};
  state.deezerCapturePolls = {};
  state.deezerAutoConnecting = {};
  Object.values(state.spotifyCapturePolls || {}).forEach((timer) => {
    if (timer) clearTimeout(timer);
  });
  state.spotifyCapturePolls = {};
  state.spotifyAutoConnecting = {};
  state.platformAutoConnecting = {};
  state.youtubePending = {};
  state.youtubeAutoConnecting = {};
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
      return true;
    } else {
      const message = humanizePlatformError(d.error || 'Falha ao conectar SoundCloud');
      if (status) status.textContent = message;
      showToast(message, 'error');
      return false;
    }
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar SoundCloud', 'error');
    return false;
  }
}

async function connectSoundcloudSavedAccess(role) {
  const r = await fetch('/api/connect/soundcloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ role, access_token: '' }),
  });
  const d = await r.json();
  if (!d.ok) {
    const lowered = String(d.error || '').toLowerCase();
    if (lowered.includes('soundcloud_login_required')) return false;
    throw new Error(d.error || 'Falha ao conectar SoundCloud');
  }

  if (role === 'src') { state.srcSid = d.sid; state.srcDisplayName = d.display_name; }
  else { state.destSid = d.sid; state.destDisplayName = d.display_name; }
  showToast('SoundCloud conectado!', 'success');
  renderConnectForms();
  checkTransferReady();
  return true;
}

function autoConnectSoundcloud(role) {
  const status = document.getElementById(`${role}-sc-status`);
  const btn = document.getElementById(`${role}-soundcloud-auto-btn`);
  state.soundcloudCapturePolls = state.soundcloudCapturePolls || {};

  if (state.soundcloudCapturePolls[role]) {
    clearTimeout(state.soundcloudCapturePolls[role]);
    state.soundcloudCapturePolls[role] = null;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin-inline"></span> Conectando...';
  }
  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Abrindo a janela de login do SoundCloud...';
  }

  const startCapture = () => {
    fetch('/api/capture/soundcloud-session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (!d.ok) throw new Error(d.error || 'Falha ao abrir SoundCloud');
        if (btn) btn.innerHTML = '<span class="spin-inline"></span> Conectando...';
        if (status) status.innerHTML = '<span class="spin-inline"></span> Faça login no SoundCloud na janela aberta. Esta tela confirma sozinha quando a conta estiver pronta.';
        pollSoundcloudSession(role, 0);
      })
      .catch((err) => {
        const message = humanizePlatformError(err.message || 'Falha ao abrir SoundCloud');
        if (status) status.textContent = message;
        showToast(message, 'error');
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '&#128268; Tentar novamente';
        }
      });
  };

  startCapture();
}

function pollSoundcloudSession(role, attempts) {
  const status = document.getElementById(`${role}-sc-status`);
  const btn = document.getElementById(`${role}-soundcloud-auto-btn`);
  const maxAttempts = role === 'dest' ? 115 : 260;

  if (attempts > maxAttempts) {
    if (status) status.textContent = 'Tempo esgotado aguardando o SoundCloud liberar a sessao web. Tente conectar novamente.';
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '&#128268; Tentar novamente';
    }
    return;
  }

  state.soundcloudCapturePolls = state.soundcloudCapturePolls || {};
  state.soundcloudCapturePolls[role] = setTimeout(async () => {
    try {
      const r = await fetch(`/api/capture/soundcloud-session/status?role=${role}`);
      const d = await r.json();

      if (d.status === 'done' && d.connected && d.sid) {
        const name = d.display_name || 'SoundCloud';
        if (role === 'src') {
          state.srcSid = d.sid;
          state.srcDisplayName = name;
        } else {
          state.destSid = d.sid;
          state.destDisplayName = name;
        }
        state.soundcloudCapturePolls[role] = null;
        showToast(`SoundCloud conectado: ${name}`, 'success');
        renderConnectForms();
        checkTransferReady();
        return;
      }

      if (d.status === 'error') {
        const message = humanizePlatformError(d.error || 'Falha ao conectar SoundCloud');
        if (status) status.textContent = message;
        showToast(message, 'error');
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '&#128268; Tentar novamente';
        }
        state.soundcloudCapturePolls[role] = null;
        return;
      }

      if (status && d.step === 'opening_webview') {
        status.innerHTML = '<span class="spin-inline"></span> Abrindo a janela guiada do SoundCloud para concluir o login automaticamente.';
      } else if (status && d.step === 'waiting_browser_login') {
        status.innerHTML = '<span class="spin-inline"></span> Aguardando login no SoundCloud pela janela guiada.';
      } else if (status && d.step === 'checking_web_session') {
        status.innerHTML = '<span class="spin-inline"></span> Conferindo se o SoundCloud liberou permissao para criar playlists.';
      }

      pollSoundcloudSession(role, attempts + 1);
    } catch {
      pollSoundcloudSession(role, attempts + 1);
    }
  }, 1000);
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
      return true;
    } else {
      const message = humanizePlatformError(d.error || 'Falha ao conectar Apple Music');
      if (status) status.textContent = message;
      showToast(message, 'error');
      return false;
    }
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar Apple Music', 'error');
    return false;
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
      return true;
    } else {
      const message = humanizePlatformError(d.error || 'Falha ao conectar Amazon Music');
      if (isAmazonOfficialAccessError(d.error || message)) {
        renderAmazonOfficialAccessNotice(role, d.error || message);
        showToast(message, 'warn');
      } else {
        if (status) status.textContent = message;
        showToast(message, 'error');
      }
      return false;
    }
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar Amazon Music', 'error');
    return false;
  }
}

async function autoConnectSavedAccess(config) {
  const key = `${config.platform}:${config.role}`;
  const status = document.getElementById(config.statusId);
  const btn = document.getElementById(`${config.role}-${config.platform}-auto-btn`);

  state.platformAutoConnecting = state.platformAutoConnecting || {};
  state.platformAutoConnecting[key] = true;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin-inline"></span> Conectando...';
  }
  if (status) {
    status.innerHTML = `<span class="spin-inline"></span> Tentando conectar ${config.name} automaticamente...`;
  }

  const success = await config.connect(config.role);
  state.platformAutoConnecting[key] = false;

  if (success) {
    return true;
  }

  if (config.detailsId) {
    const details = document.getElementById(config.detailsId);
    if (details) details.open = true;
  }

  const retryBtn = document.getElementById(`${config.role}-${config.platform}-auto-btn`);
  if (retryBtn) {
    retryBtn.disabled = false;
    retryBtn.innerHTML = '🔌 Tentar novamente';
  }
  if (status && config.fallbackMessage) {
    status.textContent = config.fallbackMessage;
  }
  return false;
}

function resetPlatformAutoButton(platform, role, label = '🔌 Tentar novamente') {
  const key = `${platform}:${role}`;
  state.platformAutoConnecting = state.platformAutoConnecting || {};
  state.platformAutoConnecting[key] = false;

  const btn = document.getElementById(`${role}-${platform}-auto-btn`);
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = label;
  }
}

function normalizeExternalUrl(url) {
  const raw = String(url || '').trim();
  if (!raw) return '';
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) return raw;
  if (/^[a-z0-9.-]+\.[a-z]{2,}(?:\/|$)/i.test(raw)) return `https://${raw}`;
  return raw;
}

function isAllowedOAuthMessageOrigin(origin) {
  if (origin === location.origin) return true;
  try {
    const incoming = new URL(origin);
    const current = new URL(location.origin);
    const localHosts = new Set(['localhost', '127.0.0.1']);
    return (
      localHosts.has(incoming.hostname) &&
      localHosts.has(current.hostname) &&
      incoming.port === current.port &&
      incoming.protocol === current.protocol
    );
  } catch {
    return false;
  }
}

function autoConnectApple(role) {
  return autoConnectSavedAccess({
    platform: 'apple',
    role,
    name: 'Apple Music',
    statusId: `${role}-apple-status`,
    detailsId: role === 'src' ? '' : `${role}-apple-details`,
    connect: connectApple,
    fallbackMessage: role === 'src'
      ? 'Apple Music pronta para ler playlists publicas pelo link.'
      : 'Para salvar na Apple Music, esta instalacao precisa dos codigos MusicKit dessa conta. Deixei o modo manual aberto abaixo.',
  });
}

function amazonMusicApiDocsUrl() {
  return 'https://developer.amazon.com/docs/music/API_web_overview.html';
}

function openAmazonMusicApiDocs() {
  const opened = window.open(amazonMusicApiDocsUrl(), '_blank');
  try {
    if (opened) opened.opener = null;
  } catch {}
  if (!opened) {
    showToast('O navegador bloqueou a aba da Amazon. Abra a documentacao pelo link exibido no card.', 'warn');
  }
}

function isAmazonOfficialAccessError(message) {
  const lowered = String(message || '').toLowerCase();
  return (
    lowered.includes('amazon_music_api_access_required') ||
    lowered.includes('amazon_music_api_not_enabled') ||
    lowered.includes('amazon_music_oauth_required') ||
    lowered.includes('amazon_lwa_token_exchange_failed') ||
    lowered.includes('amazon_music_auth_failed') ||
    lowered.includes('amazon_music_validation_failed') ||
    lowered.includes('api key do amazon music') ||
    lowered.includes('access token do amazon music') ||
    lowered.includes('beta fechado') ||
    lowered.includes('web api oficial') ||
    lowered.includes('permissao para esse endpoint do amazon music')
  );
}

function renderAmazonOfficialAccessNotice(role, rawMessage = '') {
  const status = document.getElementById(`${role}-amazon-status`);
  if (!status) return;

  const notEnabled = String(rawMessage || '').toLowerCase().includes('not_enabled');
  const configured = !!state.platforms.amazon?.oauth_configured;
  const copy = configured || notEnabled
    ? 'A Amazon abriu o caminho, mas ainda não liberou a criação de playlists nesta instalação. Tente novamente mais tarde.'
    : 'Amazon Music ainda não está disponível nesta instalação.';

  status.textContent = copy;
}

function autoConnectAmazon(role) {
  // Igual ao Deezer: abre o webview de login e captura cookies de sessão
  const status = document.getElementById(`${role}-amazon-status`);
  const btn    = document.getElementById(`${role}-amazon-auto-btn`);

  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spin-inline"></span> Abrindo login da Amazon...'; }
  if (status) status.innerHTML = '<span class="spin-inline"></span> Aguardando login na janela Amazon Music...';

  fetch('/api/capture/amazon-session', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ role }),
  })
    .then(r => r.json())
    .then(d => {
      if (d.ok) {
        pollAmazonSession(role, 0);
      } else {
        if (status) status.textContent = 'Erro ao abrir a janela de login.';
        if (btn) { btn.disabled = false; btn.innerHTML = '🔌 Conectar Amazon Music'; }
      }
    })
    .catch(() => {
      if (status) status.textContent = 'Erro ao abrir a janela de login.';
      if (btn) { btn.disabled = false; btn.innerHTML = '🔌 Conectar Amazon Music'; }
    });
}

function pollAmazonSession(role, attempts) {
  const status = document.getElementById(`${role}-amazon-status`);
  const btn    = document.getElementById(`${role}-amazon-auto-btn`);
  const MAX    = 180;

  if (attempts > MAX) {
    if (status) status.textContent = 'Tempo esgotado. Tente novamente.';
    if (btn)    { btn.disabled = false; btn.innerHTML = '🔌 Conectar Amazon Music'; }
    return;
  }

  setTimeout(async () => {
    try {
      const r = await fetch(`/api/capture/amazon-session/status?role=${role}`);
      const d = await r.json();

      if (d.status === 'done' && d.connected) {
        const name = d.display_name || 'Amazon Music';
        if (role === 'src') {
          state.srcSid         = 'amazon-session';
          state.srcDisplayName = name;
        } else {
          state.destSid         = 'amazon-session';
          state.destDisplayName = name;
        }
        showToast(`Amazon Music conectado: ${name}`, 'success');
        renderConnectForms();
        checkTransferReady();
        return;
      }

      if (d.status === 'error') {
        if (status) status.textContent = d.error || 'Falha ao conectar. Tente novamente.';
        if (btn)    { btn.disabled = false; btn.innerHTML = '🔌 Conectar Amazon Music'; }
        return;
      }

      // Ainda rodando
      pollAmazonSession(role, attempts + 1);
    } catch {
      pollAmazonSession(role, attempts + 1);
    }
  }, 1000);
}



async function startTidalConnect(role) {
  state.tidalPending = state.tidalPending || {};
  const status = document.getElementById(`${role}-tidal-status`);
  const btn = document.getElementById(`${role}-tidal-auto-btn`);
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin-inline"></span> Conectando...';
  }
  if (status) status.innerHTML = '<span class="spin-inline"></span> Abrindo o login oficial do TIDAL...';
  try {
    const r = await fetch('/api/connect/tidal/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();
    if (!d.ok) {
      const message = humanizePlatformError(d.error || 'Falha ao iniciar login do TIDAL');
      if (status) status.textContent = message;
      showToast(message, 'error');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '🔌 Tentar novamente';
      }
      return;
    }

    state.tidalPending[role] = d.login_id;
    const loginUrl = normalizeExternalUrl(d.verification_uri_complete || d.verification_uri || '');
    let opened = null;
    if (loginUrl) {
      opened = window.open(loginUrl, '_blank', 'noopener');
    }
    if (status) {
      status.innerHTML = `
        <div style="display:grid;gap:8px;">
          <div>Abri o login oficial do TIDAL neste navegador.</div>
          ${d.user_code ? `<div>Se o TIDAL pedir codigo, use <strong>${escapeHtml(d.user_code)}</strong>.</div>` : ''}
          ${loginUrl ? `<a href="${loginUrl}" target="_blank" rel="noopener">Abrir login do TIDAL novamente</a>` : ''}
          <div>Assim que voce autorizar, esta tela conclui a conexao sozinha.</div>
        </div>
      `;
    }
    if (!opened && loginUrl) {
      showToast('Nao consegui abrir a aba do TIDAL automaticamente. Use o link exibido para continuar.', 'warn');
    }
    pollTidalLogin(role, d.login_id);
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao iniciar login do TIDAL', 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🔌 Tentar novamente';
    }
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
    const btn = document.getElementById(`${role}-tidal-auto-btn`);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🔌 Tentar novamente';
    }
  } catch {
    state.tidalPending[role] = null;
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar TIDAL', 'error');
    const btn = document.getElementById(`${role}-tidal-auto-btn`);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🔌 Tentar novamente';
    }
  }
}

function disconnect(role) {
  if (!state.tidalPending) state.tidalPending = {};
  state.tidalPending[role] = null;
  if (!state.youtubePending) state.youtubePending = {};
  state.youtubePending[role] = null;
  if (state.soundcloudCapturePolls?.[role]) {
    clearTimeout(state.soundcloudCapturePolls[role]);
    state.soundcloudCapturePolls[role] = null;
  }
  if (typeof resetAppleGuidedPoll === 'function') {
    resetAppleGuidedPoll(role);
  }
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
      subtitle: 'A forma simples de fazer login ainda nao esta ativa aqui.',
      note: 'Se quiser continuar agora, voce pode usar a opcao avancada logo abaixo.',
    });
  }

  return makeConnectCallout({
    platform,
    badge: 'Login oficial',
    title: `Fazer login com ${name}`,
    subtitle: role === 'src'
      ? 'Vamos pedir sua autorizacao para ler a playlist completa do jeito certo.'
      : 'Vamos pedir sua autorizacao para criar a nova playlist na sua conta.',
    note: `Antes de seguir, mostramos rapidinho por que essa permissao e pedida. Sua senha continua no site oficial do ${name}.`,
    buttonLabel: `Fazer login e autorizar`,
    buttonAction: `openOAuthPopup('${platform}','${role}')`,
    buttonClass: 'btn btn-primary',
  });
}

function makeSpotifyQuickConnect(role) {
  const connected = (role === 'src' && state.srcSid) || (role === 'dest' && state.destSid);
  const displayName = role === 'src' ? state.srcDisplayName : state.destDisplayName;
  const oauthConfigured = !!state.platforms.spotify?.oauth_configured;
  const needsOfficialDestSetup = role === 'dest' && !oauthConfigured;
  const autoTrying = !!state.spotifyAutoConnecting?.[role];

  if (connected && displayName) {
    return makeConnectCallout({
      platform: 'spotify',
      tone: 'success',
      badge: 'Conectado',
      title: `Spotify conectado como ${displayName}`,
      subtitle: 'Pronto para transferir playlists.',
    });
  }

  const subtitle = needsOfficialDestSetup
    ? 'O Spotify exige uma configuracao oficial unica para criar playlists sem bloquear.'
    : oauthConfigured
    ? 'Clique no botao abaixo. O app abre o login oficial do Spotify e termina a conexao sozinho.'
    : 'Clique no botao abaixo. O app tenta encontrar seu login do Spotify automaticamente e, se precisar, abre uma janela guiada para concluir.';

  const hint = needsOfficialDestSetup
    ? 'Isto e setup do PlayTransfer. Depois de ativado, o usuario final so toca em conectar.'
    : oauthConfigured
    ? 'Depois da autorizacao no Spotify, esta tela continua sozinha.'
    : 'Uma janela limpa do Spotify abre para voce fazer login na conta certa. Se sua conta usa Google, Apple ou Facebook, use esse botao na propria janela.';

  const buttonLabel = autoTrying
    ? '<span class="spin-inline"></span> Conectando...'
    : needsOfficialDestSetup
      ? '🔐 Ativar login oficial do Spotify'
      : '🔌 Conectar Spotify automaticamente';

  return makeFormPanel(`
    <div class="manual-connect-header deezer-quick-header">
      <div class="manual-connect-platform">
        <div class="manual-connect-platform-icon">${PLATFORM_ICONS.spotify || ''}</div>
        <div class="manual-connect-platform-copy">
          <div class="manual-connect-title">Conectar Spotify</div>
          <div class="manual-connect-subtitle">${subtitle}</div>
        </div>
      </div>
    </div>
    <div class="manual-connect-actions deezer-quick-actions">
      <button class="btn btn-primary btn-sm deezer-auto-connect-btn" type="button" id="${role}-spotify-auto-btn" onclick="autoConnectSpotify('${role}')" ${autoTrying ? 'disabled' : ''}>
        ${buttonLabel}
      </button>
    </div>
    <div class="deezer-quick-hint" id="${role}-spotify-hint">${hint}</div>
    ${makeInlineStatus(`${role}-spotify-status`)}
  `);
}

function makeAutomaticConnectPanel(config) {
  const autoTrying = !!state.platformAutoConnecting?.[`${config.platform}:${config.role}`] || !!config.autoTrying;
  return makeFormPanel(`
    <div class="manual-connect-header deezer-quick-header">
      <div class="manual-connect-platform">
        <div class="manual-connect-platform-icon">${PLATFORM_ICONS[config.platform] || ''}</div>
        <div class="manual-connect-platform-copy">
          <div class="manual-connect-title">${config.title}</div>
          <div class="manual-connect-subtitle">${config.subtitle}</div>
        </div>
      </div>
    </div>
    <div class="manual-connect-actions deezer-quick-actions">
      <button class="btn btn-primary btn-sm deezer-auto-connect-btn" type="button" id="${config.role}-${config.platform}-auto-btn" onclick="${config.action}" ${autoTrying ? 'disabled' : ''}>
        ${autoTrying ? '<span class="spin-inline"></span> Conectando...' : config.buttonLabel}
      </button>
    </div>
    <div class="deezer-quick-hint" id="${config.role}-${config.platform}-hint">${config.hint || ''}</div>
    ${makeInlineStatus(config.statusId)}
  `);
}

function makeSpotifyForm(role) {
  const wrapper = document.createElement('div');
  if (role === 'src') {
    wrapper.appendChild(makeConnectCallout({
      platform: 'spotify',
      tone: 'success',
      badge: 'Sem login',
      title: 'Cole o link do Spotify e continue',
      subtitle: 'Para playlists publicas menores, voce nao precisa fazer login nem copiar nada.',
      note: 'Se a playlist for privada ou muito grande, o login opcional fica logo abaixo.',
    }));

    if (state.platforms.spotify?.oauth_configured) {
      wrapper.appendChild(makeAdvancedDetails(
        'Playlist privada ou muito grande? Fazer login no Spotify',
        makeOAuthForm('spotify', role),
        false
      ));
    }

    return wrapper;
  }

  wrapper.appendChild(makeSpotifyQuickConnect(role));

  wrapper.appendChild(makeAdvancedDetails(
    'Nao funcionou? Fazer manualmente',
    makeManualCredentialsForm({
      platform: 'spotify',
      role,
      title: 'Copie o valor do Spotify',
      subtitle: state.platforms.spotify?.oauth_configured
        ? 'Use isso so se o automatico nao abrir ou nao terminar.'
        : 'Use isso so se a captura automatica nao conseguir terminar nesta instalacao.',
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
      help: state.platforms.spotify?.oauth_configured
        ? 'Se o automatico funcionar, voce pode ignorar esta parte.'
        : 'Se preferir, pode colar so o Cookie Value de sp_dc.',
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
    }),
    false
  ));

  return wrapper;
}

function makeDeezerForm(role) {
  if (role === 'src') {
    return makeConnectCallout({
      platform: 'deezer',
      tone: 'success',
      badge: 'Sem login',
      title: 'Voce nao precisa fazer login no Deezer agora',
      subtitle: 'Para a maioria das playlists publicas, basta colar o link abaixo.',
      note: 'Se a visualizacao previa nao abrir, confira se a playlist esta publica.',
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

function makeYoutubeManualPanel(role, subtitle, footnote = '') {
  const youtubeManualLabel = 'Cole aqui o cURL completo que voce copiou';
  const youtubeManualPlaceholder = 'Cole aqui o texto inteiro de "Copy as cURL (bash)"';
  const youtubeManualHelp = 'Cole o comando cURL inteiro. Nao copie texto das abas Payload, Preview, Response nem pedacos soltos de Headers.';

  return makeManualCredentialsForm({
    platform: 'youtube',
    role,
    title: 'Conectar manualmente pelo navegador',
    subtitle,
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
    footnote,
    steps: [
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
    ],
  });
}

function makeYoutubeQuickConnect(role) {
  const pending = state.youtubePending?.[role];
  const autoTrying = !!pending || !!state.youtubeAutoConnecting?.[role];
  const oauthConfigured = !!state.platforms.youtube?.oauth_configured;

  let subtitle = oauthConfigured
    ? 'Clique no botao abaixo. O app abre o login oficial do Google e tenta concluir sozinho.'
    : 'Clique no botao abaixo. O app tenta usar o que ja tiver disponivel e, se precisar, abre uma janela guiada para concluir o login.';

  let hint = oauthConfigured
    ? 'Depois da autorizacao no Google, esta tela continua sozinha.'
    : 'Se voce ja tiver algo valido copiado do navegador, o app aproveita. Se nao, ele abre uma janela guiada do YouTube Music e tenta terminar tudo sozinho.';

  if (pending?.mode === 'oauth') {
    hint = pending.userCode
      ? `Termine a autorizacao na aba do Google. Se pedirem um codigo, use ${pending.userCode}.`
      : 'Termine a autorizacao na aba do Google. Esta tela continua sozinha depois.';
  } else if (pending?.mode === 'guided') {
    hint = 'Uma janela guiada do YouTube Music deve estar aberta agora. Entre nela e o app tenta concluir sozinho.';
  }

  return makeFormPanel(`
    <div class="manual-connect-header deezer-quick-header">
      <div class="manual-connect-platform">
        <div class="manual-connect-platform-icon">${PLATFORM_ICONS.youtube || ''}</div>
        <div class="manual-connect-platform-copy">
          <div class="manual-connect-title">Conectar YouTube Music</div>
          <div class="manual-connect-subtitle">${subtitle}</div>
        </div>
      </div>
    </div>
    <div class="manual-connect-actions deezer-quick-actions">
      <button class="btn btn-primary btn-sm deezer-auto-connect-btn" type="button" id="${role}-ytm-auto-btn" onclick="autoConnectYoutube('${role}')" ${autoTrying ? 'disabled' : ''}>
        ${autoTrying ? '<span class="spin-inline"></span> Conectando...' : '🔌 Conectar YouTube Music automaticamente'}
      </button>
    </div>
    <div class="deezer-quick-hint" id="${role}-ytm-hint">${hint}</div>
    ${makeInlineStatus(`${role}-ytm-status`)}
  `);
}

function makeYoutubeForm(role) {
  if (role === 'src') {
    return makeConnectCallout({
      platform: 'youtube',
      tone: 'success',
      badge: 'Sem login',
      title: 'Voce nao precisa fazer login no YouTube Music agora',
      subtitle: 'Se a playlist for publica, basta colar o link abaixo e continuar.',
      note: 'Se a visualizacao previa nao abrir, confira se o link esta publico.',
    });
  }

  const wrapper = document.createElement('div');
  const manualDetails = makeAdvancedDetails(
    'Nao funcionou? Fazer manualmente',
    makeYoutubeManualPanel(
      role,
      state.platforms.youtube?.oauth_configured
        ? 'Use isso so se o automatico nao abrir ou nao terminar.'
        : 'Use isso so se a janela guiada nao der certo nesta instalacao.',
      state.platforms.youtube?.oauth_configured
        ? 'Se o automatico funcionar, voce pode ignorar esta parte.'
        : 'Quando o login oficial do Google for ativado nesta instalacao, este passo manual deixa de ser o caminho principal.'
    ),
    false
  );
  manualDetails.id = `${role}-youtube-manual-details`;

  wrapper.appendChild(makeYoutubeQuickConnect(role));
  wrapper.appendChild(manualDetails);
  return wrapper;
}

function makeSoundcloudForm(role) {
  const wrapper = document.createElement('div');
  wrapper.appendChild(makeAutomaticConnectPanel({
    platform: 'soundcloud',
    role,
    title: 'Conectar SoundCloud',
    subtitle: role === 'src'
      ? 'Para playlists publicas, voce pode continuar sem login. Se precisar entrar, este botao conecta a conta.'
      : 'Clique no botao abaixo. O app abre a janela de login do SoundCloud e conecta a conta sozinho.',
    hint: 'O usuario final nao precisa preencher token, API key, pais da conta ou codigo manual.',
    statusId: `${role}-sc-status`,
    buttonLabel: '&#128268; Conectar SoundCloud automaticamente',
    action: `autoConnectSoundcloud('${role}')`,
  }));
  return wrapper;

}

function getSoundcloudRedirectUri() {
  return state.platforms.soundcloud?.oauth_redirect_uri || `${getSpotifySetupOrigin()}/auth/soundcloud/callback`;
}

function makeSoundcloudOfficialSetup(role) {
  const redirectUri = getSoundcloudRedirectUri();
  return makeFormPanel(`
    <div class="manual-connect-header deezer-quick-header">
      <div class="manual-connect-platform">
        <div class="manual-connect-platform-icon">${PLATFORM_ICONS.soundcloud || ''}</div>
        <div class="manual-connect-platform-copy">
          <div class="manual-connect-title">Ativar SoundCloud oficial</div>
          <div class="manual-connect-subtitle">O SoundCloud bloqueia criar playlists por sessao de navegador. Com OAuth oficial, este mesmo botao passa a conectar a conta em um clique.</div>
        </div>
      </div>
    </div>
    <div class="manual-connect-notice warning">
      <div class="manual-connect-notice-copy">
        <div class="manual-connect-notice-title">Configuracao unica da instalacao</div>
        <div class="manual-connect-notice-body">Depois de salvar o app oficial, o usuario final nao precisa preencher token, API key, pais da conta ou codigo manual.</div>
      </div>
    </div>
    <div class="form-group" style="margin-top:0;">
      <label class="form-label" for="${role}-soundcloud-redirect-uri">Redirect URI para cadastrar no SoundCloud</label>
      <input id="${role}-soundcloud-redirect-uri" class="form-input" readonly value="${escapeHtml(redirectUri)}" />
      <div class="form-hint"><span>i</span><span>Cadastre este URL no app SoundCloud antes de salvar.</span></div>
    </div>
    <div class="form-group">
      <label class="form-label" for="${role}-soundcloud-client-id">Client ID do SoundCloud</label>
      <input id="${role}-soundcloud-client-id" class="form-input" autocomplete="off" placeholder="Cole o Client ID aqui" />
    </div>
    <div class="form-group">
      <label class="form-label" for="${role}-soundcloud-client-secret">Client Secret do SoundCloud</label>
      <input id="${role}-soundcloud-client-secret" class="form-input" autocomplete="off" placeholder="Cole o Client Secret aqui" />
    </div>
    <div class="manual-connect-actions deezer-quick-actions">
      <button class="btn btn-secondary btn-sm" type="button" onclick="copySoundcloudRedirectUri('${role}')">Copiar Redirect URI</button>
      <button class="btn btn-secondary btn-sm" type="button" onclick="window.open('https://soundcloud.com/you/apps', '_blank', 'noopener')">Abrir apps do SoundCloud</button>
      <button class="btn btn-primary btn-sm" type="button" id="${role}-soundcloud-oauth-save" onclick="saveSoundcloudOAuthSetup('${role}')">Salvar e conectar</button>
    </div>
    ${makeInlineStatus(`${role}-sc-status`)}
  `);
}

async function copySoundcloudRedirectUri(role) {
  const redirectUri = document.getElementById(`${role}-soundcloud-redirect-uri`)?.value || getSoundcloudRedirectUri();
  try {
    await navigator.clipboard.writeText(redirectUri);
    showToast('Redirect URI do SoundCloud copiada.', 'success');
  } catch {
    showToast('Nao consegui copiar automaticamente. Selecione e copie o texto.', 'warn');
  }
}

async function saveSoundcloudOAuthSetup(role) {
  const status = document.getElementById(`${role}-sc-status`);
  const saveBtn = document.getElementById(`${role}-soundcloud-oauth-save`);
  const clientId = document.getElementById(`${role}-soundcloud-client-id`)?.value?.trim() || '';
  const clientSecret = document.getElementById(`${role}-soundcloud-client-secret`)?.value?.trim() || '';

  if (!clientId || !clientSecret) {
    if (status) status.textContent = 'Cole o Client ID e o Client Secret do app SoundCloud antes de continuar.';
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spin-inline"></span> Salvando...';
  }
  if (status) status.textContent = 'Salvando SoundCloud oficial nesta instalacao...';

  try {
    const response = await fetch('/api/config/soundcloud-oauth', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        base_url: getSpotifySetupOrigin(),
      }),
    });
    const data = await response.json();
    if (!data.ok) {
      throw new Error(data.error || 'Nao foi possivel salvar a configuracao do SoundCloud.');
    }

    state.platforms.soundcloud = {
      ...(state.platforms.soundcloud || {}),
      oauth_configured: true,
      oauth_redirect_uri: data.oauth_redirect_uri || getSoundcloudRedirectUri(),
    };
    showToast('SoundCloud oficial ativado. Abrindo login agora.', 'success');
    renderConnectForms();
    setTimeout(() => openOAuthPopup('soundcloud', role), 250);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Nao foi possivel salvar a configuracao do SoundCloud.');
    if (status) status.textContent = message;
    showToast(message, 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Salvar e conectar';
    }
  }
}

function makeAppleForm(role) {
  const wrapper = document.createElement('div');

  if (role === 'src') {
    wrapper.appendChild(makeAutomaticConnectPanel({
      platform: 'apple',
      role,
      title: 'Conectar Apple Music',
      subtitle: 'Clique no botao abaixo. Para playlists publicas, o app prepara a leitura automaticamente.',
      hint: 'Se o link for publico, voce nao precisa informar codigo nenhum.',
      statusId: `${role}-apple-status`,
      buttonLabel: '🔌 Conectar Apple Music automaticamente',
      action: `autoConnectApple('${role}')`,
    }));
    return wrapper;
  }

  const appleDetails = makeAdvancedDetails(
    'Nao funcionou? Fazer manualmente',
    makeFormPanel(`
      <div class="manual-connect-header">
        <div class="manual-connect-title">Dados da Apple Music</div>
        <div class="manual-connect-subtitle">Preencha apenas se voce ja usa MusicKit ou ja recebeu esses codigos.</div>
      </div>
      ${makeTextAreaField(`${role}-apple-developer-token`, 'Developer token', 'eyJhbGciOi...')}
      ${makeTextAreaField(`${role}-apple-user-token`, 'Music user token', 'music-user-token...')}
      ${makeTextInputField(`${role}-apple-storefront`, 'Pais da conta', 'br, us, gb...', 'us')}
      <button class="btn btn-secondary btn-sm" onclick="connectApple('${role}')">Conectar Apple Music</button>
      ${makeInlineStatus(`${role}-apple-status`)}
    `),
    false
  );
  appleDetails.id = `${role}-apple-details`;

  wrapper.appendChild(makeAutomaticConnectPanel({
    platform: 'apple',
    title: 'Conectar Apple Music',
    role,
    subtitle: 'Clique no botao abaixo. Se esta instalacao ja tiver MusicKit salvo, o app conecta em um passo.',
    hint: 'Se faltar autorizacao da Apple, o app mostra o fallback manual sem poluir o fluxo principal.',
    statusId: `${role}-apple-status`,
    buttonLabel: '🔌 Conectar Apple Music automaticamente',
    action: `autoConnectApple('${role}')`,
  }));
  wrapper.appendChild(appleDetails);

  return wrapper;
}

function makeAmazonForm(role) {
  const wrapper = document.createElement('div');

  wrapper.appendChild(makeAutomaticConnectPanel({
    platform:    'amazon',
    title:       'Conectar Amazon Music',
    role,
    subtitle:    'Clique no botão abaixo. O app abre o login do Amazon Music e conecta a conta sozinho.',
    hint:        'Faça login com sua conta Amazon normalmente. Não é necessário nenhum código ou token.',
    statusId:    `${role}-amazon-status`,
    buttonLabel: '🔌 Conectar Amazon Music automaticamente',
    action:      `autoConnectAmazon('${role}')`,
  }));

  return wrapper;
}


function makeTidalForm(role) {
  const div = document.createElement('div');
  const pending = !!state.tidalPending?.[role];
  div.appendChild(makeAutomaticConnectPanel({
    platform: 'tidal',
    role,
    title: 'Conectar TIDAL',
    subtitle: 'Clique no botao abaixo. O TIDAL abre o login oficial e esta tela acompanha tudo sozinha.',
    hint: pending
      ? 'Termine a autorizacao no TIDAL. Assim que der certo, esta tela continua sozinha.'
      : 'Depois de autorizar, a conta aparece conectada aqui automaticamente.',
    statusId: `${role}-tidal-status`,
    buttonLabel: '🔌 Conectar TIDAL automaticamente',
    action: `startTidalConnect('${role}')`,
    autoTrying: pending,
  }));
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
          status.textContent = `${message} Abrir e fazer login no Deezer nao remove essa trava do Chrome. Para continuar agora, use o passo manual logo abaixo.`;
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
    hint.textContent = 'Uma janela de login do Deezer deve abrir agora. Se ela aparecer atras, traga "Login Deezer - PlayTransfer" para frente e faca o login nela.';
  }

  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Tentando abrir a janela de login do Deezer...';
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

    if (d.status === 'pending' && status) {
      status.innerHTML = '<span class="spin-inline"></span> Aguardando voce concluir o login na janela "Login Deezer - PlayTransfer"...';
    }

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

  if (attempt >= 140) {
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
    return false;
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
      state.youtubePending[role] = null;
      state.youtubeAutoConnecting[role] = false;
      showToast('YouTube Music conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return true;
    }

    const message = humanizePlatformError(d.error || 'Falha ao conectar YouTube Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
    return false;
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar YouTube Music', 'error');
    return false;
  }
}

function looksLikeYoutubeBrowserText(text) {
  const raw = String(text || '').trim();
  if (!raw) return false;
  const lowered = raw.toLowerCase();
  return (
    lowered.startsWith('curl ') ||
    lowered.includes('music.youtube.com') ||
    lowered.includes('youtubei/v1/browse') ||
    lowered.includes('__secure-3papisid') ||
    lowered.includes('cookie:') ||
    lowered.includes('x-goog-authuser')
  );
}

function resetYoutubeAutoBtn(role) {
  state.youtubeAutoConnecting = state.youtubeAutoConnecting || {};
  state.youtubeAutoConnecting[role] = false;
  const btn = document.getElementById(`${role}-ytm-auto-btn`);
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = '🔌 Conectar YouTube Music automaticamente';
  }
}

async function autoConnectYoutube(role) {
  state.youtubeAutoConnecting = state.youtubeAutoConnecting || {};
  state.youtubeAutoConnecting[role] = true;

  const status = document.getElementById(`${role}-ytm-status`);
  const btn = document.getElementById(`${role}-ytm-auto-btn`);
  const input = document.getElementById(`${role}-ytm-curl`);

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin-inline"></span> Conectando...';
  }

  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Tentando confirmar o YouTube Music automaticamente...';
  }

  try {
    if (navigator.clipboard?.readText) {
      try {
        const clipboardText = String((await navigator.clipboard.readText()) || '').trim();
        if (looksLikeYoutubeBrowserText(clipboardText)) {
          if (input) input.value = clipboardText;
          if (status) {
            status.innerHTML = '<span class="spin-inline"></span> Encontrei dados do YouTube Music no que voce copiou. Confirmando...';
          }
          const success = await connectYoutube(role);
          if (success) {
            state.youtubeAutoConnecting[role] = false;
            return;
          }
        }
      } catch {
        // Se o navegador bloquear clipboard, seguimos para o proximo modo automatico.
      }
    }

    if (state.platforms.youtube?.oauth_configured) {
      await startYoutubeAutoConnect(role);
      return;
    }

    await startYoutubeGuidedConnect(role);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha ao abrir o YouTube Music automaticamente');
    if (status) status.textContent = message;
    showToast(message, 'error');
    resetYoutubeAutoBtn(role);
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
      state.youtubeAutoConnecting[role] = false;
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
        mode: 'oauth',
        loginId: d.login_id,
        verificationUrl: targetUrl,
        userCode: d.user_code || '',
        retryMs: Math.max(3000, Number(d.interval || 5) * 1000),
      };
      state.youtubeAutoConnecting[role] = false;
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
    resetYoutubeAutoBtn(role);
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao abrir o YouTube Music automaticamente', 'error');
    resetYoutubeAutoBtn(role);
  }
}

async function startYoutubeGuidedConnect(role) {
  const status = document.getElementById(`${role}-ytm-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Abrindo uma janela guiada do YouTube Music...';

  try {
    const r = await fetch('/api/connect/youtube/guided/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();

    if (d.ok && d.pending) {
      state.youtubePending[role] = {
        mode: 'guided',
        loginId: d.login_id,
        browserName: d.browser_name || '',
        retryMs: 2500,
      };
      state.youtubeAutoConnecting[role] = false;
      renderConnectForms();

      const refreshedStatus = document.getElementById(`${role}-ytm-status`);
      if (refreshedStatus) {
        refreshedStatus.textContent = 'Entre na janela guiada do YouTube Music. Quando a conta estiver pronta, esta tela continua sozinha.';
      }
      showToast('Abri uma janela guiada do YouTube Music para terminar esse login automaticamente.', 'info');
      setTimeout(() => finishYoutubeAutoConnect(role), 2200);
      return;
    }

    const message = humanizePlatformError(d.error || 'Falha ao abrir a janela guiada do YouTube Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
    resetYoutubeAutoBtn(role);
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao abrir a janela guiada do YouTube Music', 'error');
    resetYoutubeAutoBtn(role);
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
    const endpoint = pending.mode === 'guided'
      ? '/api/connect/youtube/guided/finish'
      : '/api/connect/youtube/auto/finish';
    const r = await fetch(endpoint, {
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
      state.youtubeAutoConnecting[role] = false;
      showToast('YouTube Music conectado!', 'success');
      renderConnectForms();
      checkTransferReady();
      return;
    }

    if (d.pending) {
      if (status) {
        status.textContent = pending.mode === 'guided'
          ? 'Ainda aguardando voce terminar o login na janela guiada do YouTube Music.'
          : pending.userCode
            ? `Ainda aguardando a autorizacao. Se o Google pedir, use o codigo ${pending.userCode}.`
            : 'Ainda aguardando a autorizacao na aba do Google.';
      }
      setTimeout(() => finishYoutubeAutoConnect(role), Number(d.retry_after_ms || pending.retryMs || 4000));
      return;
    }

    if (status) status.textContent = humanizePlatformError(d.error || 'Falha ao confirmar o YouTube Music');
    state.youtubePending[role] = null;
    state.youtubeAutoConnecting[role] = false;
    renderConnectForms();
    showToast(humanizePlatformError(d.error || 'Falha ao confirmar o YouTube Music'), 'error');
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    state.youtubePending[role] = null;
    state.youtubeAutoConnecting[role] = false;
    renderConnectForms();
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
  const names = { spotify: 'Spotify', deezer: 'Deezer', amazon: 'Amazon Music', soundcloud: 'SoundCloud' };
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
  // Se Amazon não está configurada, abre o wizard de setup
  // (igual ao Spotify que pede Client ID na primeira vez)
  if (platform === 'amazon' && !state.platforms.amazon?.oauth_configured) {
    openAmazonOAuthSetupModal(role);
    return;
  }

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

function getSpotifyRedirectUri() {
  return state.platforms.spotify?.oauth_redirect_uri || `${getSpotifySetupOrigin()}/auth/spotify/callback`;
}

function getSpotifySetupOrigin() {
  const url = new URL(location.href);
  if (url.hostname === 'localhost' || url.hostname === '0.0.0.0') {
    url.hostname = '127.0.0.1';
  }
  url.pathname = '';
  url.search = '';
  url.hash = '';
  return url.origin;
}

async function refreshSpotifyRedirectConfig() {
  try {
    const r = await fetch('/api/config/spotify-redirect');
    const d = await r.json();
    if (d.ok && d.redirect_uri) {
      state.platforms.spotify = {
        ...(state.platforms.spotify || {}),
        oauth_redirect_uri: d.redirect_uri,
      };
      return d.redirect_uri;
    }
  } catch {}
  return getSpotifyRedirectUri();
}

function ensureSpotifyOAuthSetupModal() {
  let modal = document.getElementById('spotify-oauth-setup-modal');
  if (modal) {
    return modal;
  }

  modal = document.createElement('div');
  modal.id = 'spotify-oauth-setup-modal';
  modal.className = 'modal-backdrop consent-modal-backdrop';
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <div class="modal consent-modal" role="dialog" aria-modal="true" aria-labelledby="spotify-oauth-setup-title">
      <button type="button" class="modal-close" id="spotify-oauth-setup-close" aria-label="Fechar">×</button>
      <div class="consent-platform-card">
        <div class="consent-platform-icon">${PLATFORM_ICONS.spotify || ''}</div>
        <div>
          <div class="consent-platform-label">Setup do PlayTransfer</div>
          <div class="consent-platform-role">Login oficial do Spotify</div>
        </div>
      </div>
      <h2 id="spotify-oauth-setup-title">Ativar Spotify oficial</h2>
      <p>Essa etapa e feita uma vez por quem instala o PlayTransfer. O usuario final nao precisa ver isso depois.</p>
      <div class="consent-points">
        <div class="consent-point">
          <span class="consent-point-mark">1</span>
          <span>Abra o painel do Spotify, crie um app e entre em <strong>Settings</strong>.</span>
        </div>
        <div class="consent-point">
          <span class="consent-point-mark">2</span>
          <span>Em <strong>Redirect URIs</strong>, cole o link abaixo e salve. Ele nao e para abrir; e so o caminho de retorno do login.</span>
        </div>
        <div class="consent-point">
          <span class="consent-point-mark">3</span>
          <span>Copie o <strong>Client ID</strong> do app Spotify e cole aqui. Nao precisa de Client Secret.</span>
        </div>
      </div>
      <label class="setup-field">
        <span>Redirect URI para copiar no Spotify</span>
        <input class="form-input" id="spotify-oauth-redirect-uri" readonly />
      </label>
      <label class="setup-field">
        <span>Client ID do Spotify</span>
        <input class="form-input" id="spotify-oauth-client-id" autocomplete="off" placeholder="Cole o Client ID aqui" />
      </label>
      <div class="connect-inline-status" id="spotify-oauth-setup-status"></div>
      <div class="consent-actions">
        <button type="button" class="btn btn-secondary" id="spotify-oauth-open-dashboard">Abrir painel do Spotify</button>
        <button type="button" class="btn btn-secondary" id="spotify-oauth-copy-redirect">Copiar Redirect URI</button>
        <button type="button" class="btn btn-primary" id="spotify-oauth-save">Salvar e conectar</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  const close = () => closeSpotifyOAuthSetupModal();
  modal.querySelector('#spotify-oauth-setup-close')?.addEventListener('click', close);
  modal.addEventListener('click', (event) => {
    if (event.target === modal) close();
  });
  modal.querySelector('#spotify-oauth-copy-redirect')?.addEventListener('click', async () => {
    const redirectUri = modal.querySelector('#spotify-oauth-redirect-uri')?.value || getSpotifyRedirectUri();
    try {
      await navigator.clipboard.writeText(redirectUri);
      showToast('Redirect URI copiada.', 'success');
    } catch {
      showToast('Nao consegui copiar automaticamente. Selecione e copie o texto.', 'warn');
    }
  });
  modal.querySelector('#spotify-oauth-open-dashboard')?.addEventListener('click', () => {
    window.open('https://developer.spotify.com/dashboard', '_blank', 'noopener');
  });
  modal.querySelector('#spotify-oauth-save')?.addEventListener('click', () => saveSpotifyOAuthSetup());

  return modal;
}

function openSpotifyOAuthSetupModal(role = 'dest') {
  const modal = ensureSpotifyOAuthSetupModal();
  modal.dataset.role = role;
  modal.querySelector('#spotify-oauth-redirect-uri').value = getSpotifyRedirectUri();
  modal.querySelector('#spotify-oauth-client-id').value = '';
  modal.querySelector('#spotify-oauth-setup-status').textContent = '';
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
  refreshSpotifyRedirectConfig().then((redirectUri) => {
    const input = modal.querySelector('#spotify-oauth-redirect-uri');
    if (input) input.value = redirectUri;
  });
  setTimeout(() => modal.querySelector('#spotify-oauth-client-id')?.focus(), 30);
}

function closeSpotifyOAuthSetupModal() {
  const modal = document.getElementById('spotify-oauth-setup-modal');
  if (!modal) return;
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
}

async function saveSpotifyOAuthSetup() {
  const modal = ensureSpotifyOAuthSetupModal();
  const role = modal.dataset.role || 'dest';
  const clientId = modal.querySelector('#spotify-oauth-client-id')?.value?.trim() || '';
  const clientSecret = '';
  const status = modal.querySelector('#spotify-oauth-setup-status');
  const saveBtn = modal.querySelector('#spotify-oauth-save');

  if (!clientId) {
    if (status) status.textContent = 'Cole o Client ID do app Spotify antes de continuar.';
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spin-inline"></span> Salvando...';
  }
  if (status) status.textContent = 'Salvando configuracao local...';

  try {
    const r = await fetch('/api/config/spotify-oauth', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        client_id: clientId,
        client_secret: clientSecret,
        base_url: getSpotifySetupOrigin(),
      }),
    });
    const d = await r.json();
    if (!d.ok) {
      throw new Error(d.error || 'Nao foi possivel ativar o Spotify oficial.');
    }

    state.platforms.spotify = {
      ...(state.platforms.spotify || {}),
      oauth_configured: true,
      oauth_mode: d.oauth_mode || 'pkce',
      oauth_redirect_uri: d.oauth_redirect_uri || getSpotifyRedirectUri(),
    };
    closeSpotifyOAuthSetupModal();
    showToast('Spotify oficial ativado. Abrindo login agora.', 'success');
    renderConnectForms();
    setTimeout(() => openOAuthPopup('spotify', role), 250);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Nao foi possivel salvar a configuracao do Spotify.');
    if (status) status.textContent = message;
    showToast(message, 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Salvar e conectar';
    }
  }
}

function getAmazonRedirectUri() {
  return state.platforms.amazon?.oauth_redirect_uri || `${getSpotifySetupOrigin()}/auth/amazon/callback`;
}

function ensureAmazonOAuthSetupModal() {
  let modal = document.getElementById('amazon-oauth-setup-modal');
  if (modal) return modal;

  modal = document.createElement('div');
  modal.id = 'amazon-oauth-setup-modal';
  modal.className = 'modal-backdrop consent-modal-backdrop';
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <div class="modal consent-modal" role="dialog" aria-modal="true" aria-labelledby="amazon-oauth-setup-title">
      <button type="button" class="modal-close" id="amazon-oauth-setup-close" aria-label="Fechar">×</button>
      <div class="consent-platform-card">
        <div class="consent-platform-icon">${PLATFORM_ICONS.amazon || ''}</div>
        <div>
          <div class="consent-platform-label">Setup do PlayTransfer</div>
          <div class="consent-platform-role">Login oficial da Amazon</div>
        </div>
      </div>
      <h2 id="amazon-oauth-setup-title">Ativar Amazon Music</h2>
      <p>Faça isso uma vez e pronto. O app detecta as credenciais automaticamente assim que você navegar para o seu perfil no console da Amazon.</p>

      <!-- Botão de captura automática -->
      <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:14px 16px;margin-bottom:16px">
        <div style="font-weight:600;margin-bottom:6px">⚡ Captura automática (recomendado)</div>
        <div style="font-size:.85rem;opacity:.8;margin-bottom:10px">Clique no botão abaixo. Uma janela do console da Amazon vai abrir. Navegue até o seu Security Profile — o app preenche tudo sozinho.</div>
        <button type="button" class="btn btn-secondary" id="amazon-auto-capture-btn" style="width:100%">🔍 Abrir console e capturar automaticamente</button>
        <div class="connect-inline-status" id="amazon-auto-capture-status" style="margin-top:8px"></div>
      </div>

      <details style="margin-bottom:12px">
        <summary style="cursor:pointer;font-size:.85rem;opacity:.7">Preencher manualmente (avançado)</summary>
        <div style="padding-top:12px">
          <div class="consent-points" style="margin-bottom:12px">
            <div class="consent-point">
              <span class="consent-point-mark">1</span>
              <span>Acesse o <strong>console da Amazon</strong> e crie um Security Profile.</span>
            </div>
            <div class="consent-point">
              <span class="consent-point-mark">2</span>
              <span>Em <strong>Web Settings → Allowed Return URLs</strong>, cole o link abaixo e salve.</span>
            </div>
            <div class="consent-point">
              <span class="consent-point-mark">3</span>
              <span>Copie o <strong>Security Profile ID</strong> e o <strong>Client ID</strong> e cole nos campos abaixo.</span>
            </div>
          </div>
          <label class="setup-field">
            <span>Return URL — cole no painel da Amazon</span>
            <div style="display:flex;gap:8px;align-items:center">
              <input class="form-input" id="amazon-oauth-setup-redirect-uri" readonly style="flex:1" />
              <button type="button" class="btn btn-secondary" id="amazon-oauth-copy-redirect" style="white-space:nowrap">Copiar</button>
            </div>
          </label>
          <label class="setup-field">
            <span>Security Profile ID</span>
            <input class="form-input" id="amazon-oauth-setup-api-key" autocomplete="off" placeholder="amzn1.application.xxxx" />
          </label>
          <label class="setup-field">
            <span>Client ID</span>
            <input class="form-input" id="amazon-oauth-setup-client-id" autocomplete="off" placeholder="amzn1.application-oa2-client.xxxx" />
          </label>
          <label class="setup-field">
            <span>Client Secret (opcional)</span>
            <input class="form-input" id="amazon-oauth-setup-client-secret" autocomplete="off" placeholder="Deixe vazio se não tiver" />
          </label>
        </div>
      </details>

      <div class="connect-inline-status" id="amazon-oauth-setup-status"></div>
      <div class="consent-actions">
        <button type="button" class="btn btn-secondary" id="amazon-oauth-open-dashboard">🔗 Abrir console</button>
        <button type="button" class="btn btn-primary" id="amazon-oauth-save">Salvar e conectar</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  const close = () => closeAmazonOAuthSetupModal();
  modal.querySelector('#amazon-oauth-setup-close')?.addEventListener('click', close);
  modal.addEventListener('click', (event) => { if (event.target === modal) close(); });

  modal.querySelector('#amazon-oauth-copy-redirect')?.addEventListener('click', async () => {
    const redirectUri = modal.querySelector('#amazon-oauth-setup-redirect-uri')?.value || getAmazonRedirectUri();
    try {
      await navigator.clipboard.writeText(redirectUri);
      showToast('Return URL copiada.', 'success');
    } catch {
      showToast('Não consegui copiar automaticamente. Selecione e copie o texto.', 'warn');
    }
  });

  modal.querySelector('#amazon-oauth-open-dashboard')?.addEventListener('click', () => {
    window.open('https://developer.amazon.com/loginwithamazon/console/site/lwa/overview.html', '_blank', 'noopener');
  });

  modal.querySelector('#amazon-auto-capture-btn')?.addEventListener('click', () => startAmazonAutoCapture(modal));
  modal.querySelector('#amazon-oauth-save')?.addEventListener('click', () => saveAmazonOAuthSetup());

  return modal;
}

async function startAmazonAutoCapture(modal) {
  const captureBtn    = modal.querySelector('#amazon-auto-capture-btn');
  const captureStatus = modal.querySelector('#amazon-auto-capture-status');

  if (captureBtn) { captureBtn.disabled = true; captureBtn.innerHTML = '<span class="spin-inline"></span> Abrindo console da Amazon...'; }
  if (captureStatus) captureStatus.textContent = 'Aguardando — navegue até o seu Security Profile no console.';

  try {
    const r = await fetch('/api/capture/amazon-lwa', { method: 'POST' });
    const d = await r.json();
    if (!d.ok) throw new Error('Não foi possível iniciar a captura.');
    pollAmazonCapture(modal, 0);
  } catch (err) {
    if (captureStatus) captureStatus.textContent = 'Erro ao abrir o console. Tente manualmente.';
    if (captureBtn) { captureBtn.disabled = false; captureBtn.innerHTML = '🔍 Abrir console e capturar automaticamente'; }
  }
}

function pollAmazonCapture(modal, attempts) {
  const captureBtn    = modal.querySelector('#amazon-auto-capture-btn');
  const captureStatus = modal.querySelector('#amazon-auto-capture-status');
  const MAX_ATTEMPTS  = 200; // ~200 segundos

  if (attempts > MAX_ATTEMPTS) {
    if (captureStatus) captureStatus.textContent = 'Tempo esgotado. Preencha manualmente se necessário.';
    if (captureBtn) { captureBtn.disabled = false; captureBtn.innerHTML = '🔍 Abrir console e capturar automaticamente'; }
    return;
  }

  setTimeout(async () => {
    try {
      const r = await fetch('/api/capture/amazon-lwa/status');
      const d = await r.json();

      if (d.status === 'done' && d.client_id && d.security_profile_id) {
        // Preenche os campos automaticamente
        const apiKeyInput    = modal.querySelector('#amazon-oauth-setup-api-key');
        const clientIdInput  = modal.querySelector('#amazon-oauth-setup-client-id');
        if (apiKeyInput)   apiKeyInput.value   = d.security_profile_id;
        if (clientIdInput) clientIdInput.value = d.client_id;

        if (captureStatus) captureStatus.textContent = '✅ Credenciais capturadas! Clique em "Salvar e conectar".';
        if (captureBtn) { captureBtn.disabled = false; captureBtn.innerHTML = '✅ Capturado'; }

        // Abre o details manualmente para mostrar os campos preenchidos
        const details = modal.querySelector('details');
        if (details) details.open = true;

        // Auto-salva se campos estiverem preenchidos
        await saveAmazonOAuthSetup();
        return;
      }

      if (d.status === 'error') {
        if (captureStatus) captureStatus.textContent = d.error || 'Não foi possível capturar. Preencha manualmente.';
        if (captureBtn) { captureBtn.disabled = false; captureBtn.innerHTML = '🔍 Tentar novamente'; }
        return;
      }

      // Ainda rodando → continua polling
      if (captureStatus) captureStatus.textContent = 'Aguardando — navegue até o seu Security Profile no console.';
      pollAmazonCapture(modal, attempts + 1);
    } catch {
      pollAmazonCapture(modal, attempts + 1);
    }
  }, 1000);
}



function openAmazonOAuthSetupModal(role = 'dest') {
  const modal = ensureAmazonOAuthSetupModal();
  modal.dataset.role = role;
  modal.querySelector('#amazon-oauth-setup-redirect-uri').value = getAmazonRedirectUri();
  modal.querySelector('#amazon-oauth-setup-api-key').value = '';
  modal.querySelector('#amazon-oauth-setup-client-id').value = '';
  modal.querySelector('#amazon-oauth-setup-client-secret').value = '';
  modal.querySelector('#amazon-oauth-setup-status').textContent = '';
  const captureStatus = modal.querySelector('#amazon-auto-capture-status');
  if (captureStatus) captureStatus.textContent = '';
  const captureBtn = modal.querySelector('#amazon-auto-capture-btn');
  if (captureBtn) { captureBtn.disabled = false; captureBtn.innerHTML = '🔍 Abrir console e capturar automaticamente'; }
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
}


function closeAmazonOAuthSetupModal() {
  const modal = document.getElementById('amazon-oauth-setup-modal');
  if (!modal) return;
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
}

async function saveAmazonOAuthSetup() {
  const modal = ensureAmazonOAuthSetupModal();
  const role = modal.dataset.role || 'dest';
  const apiKey = modal.querySelector('#amazon-oauth-setup-api-key')?.value?.trim() || '';
  const clientId = modal.querySelector('#amazon-oauth-setup-client-id')?.value?.trim() || '';
  const clientSecret = modal.querySelector('#amazon-oauth-setup-client-secret')?.value?.trim() || '';
  const status = modal.querySelector('#amazon-oauth-setup-status');
  const saveBtn = modal.querySelector('#amazon-oauth-save');

  if (!apiKey || !clientId) {
    if (status) status.textContent = 'Cole o Security Profile ID e o Client ID antes de continuar.';
    return;
  }

  if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<span class="spin-inline"></span> Salvando...'; }
  if (status) status.textContent = 'Salvando configuração da Amazon...';

  try {
    const r = await fetch('/api/config/amazon-music', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        api_key: apiKey,
        client_id: clientId,
        client_secret: clientSecret,
        country_code: 'US',
        scopes: 'profile music::catalog music::library',
        base_url: getSpotifySetupOrigin(),
      }),
    });
    const d = await r.json();
    if (!d.ok) throw new Error(d.error || 'Não foi possível salvar a configuração da Amazon Music.');

    state.platforms.amazon = {
      ...(state.platforms.amazon || {}),
      oauth_configured: true,
      auto_configured: true,
      api_key_configured: true,
      oauth_redirect_uri: d.oauth_redirect_uri || getAmazonRedirectUri(),
    };
    closeAmazonOAuthSetupModal();
    showToast('Amazon Music ativado. Abrindo login agora.', 'success');
    renderConnectForms();
    setTimeout(() => openOAuthPopup('amazon', role), 250);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Não foi possível salvar a configuração da Amazon Music.');
    if (status) status.textContent = message;
    showToast(message, 'error');
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Salvar e conectar'; }
  }
}

async function copyAmazonRedirectUri(role) {
  const redirectUri = document.getElementById(`${role}-amazon-redirect-uri`)?.value || getAmazonRedirectUri();
  try {
    await navigator.clipboard.writeText(redirectUri);
    showToast('Return URL da Amazon copiada.', 'success');
  } catch {
    showToast('Não consegui copiar automaticamente. Selecione e copie o texto.', 'warn');
  }
}

async function saveAmazonOfficialSetup(role) {
  const status = document.getElementById(`${role}-amazon-status`);
  const saveBtn = document.querySelector(`#${role}-amazon-details .btn-primary`);
  const apiKey = document.getElementById(`${role}-amazon-api-key`)?.value?.trim() || '';
  const clientId = document.getElementById(`${role}-amazon-client-id`)?.value?.trim() || '';
  const clientSecret = document.getElementById(`${role}-amazon-client-secret`)?.value?.trim() || '';
  const countryCode = document.getElementById(`${role}-amazon-country-code`)?.value?.trim() || 'US';
  const scopes = document.getElementById(`${role}-amazon-scopes`)?.value?.trim() || 'profile music::catalog music::library';

  if (!apiKey || !clientId) {
    if (status) {
      status.textContent = 'Cole o Security Profile ID e o Client ID do Login With Amazon antes de salvar.';
    }
    return;
  }

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<span class="spin-inline"></span> Salvando...';
  }
  if (status) {
    status.textContent = 'Salvando configuracao oficial da Amazon...';
  }

  try {
    const r = await fetch('/api/config/amazon-music', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        api_key: apiKey,
        client_id: clientId,
        client_secret: clientSecret,
        country_code: countryCode,
        scopes,
        base_url: getSpotifySetupOrigin(),
      }),
    });
    const d = await r.json();
    if (!d.ok) {
      throw new Error(d.error || 'Nao foi possivel salvar a configuracao da Amazon Music.');
    }

    state.platforms.amazon = {
      ...(state.platforms.amazon || {}),
      oauth_configured: true,
      auto_configured: true,
      api_key_configured: true,
      country_code: d.country_code || countryCode,
      scopes: d.scopes || scopes,
      oauth_redirect_uri: d.oauth_redirect_uri || getAmazonRedirectUri(),
    };
    showToast('Amazon Music oficial configurado. Abrindo login agora.', 'success');
    renderConnectForms();
    setTimeout(() => openOAuthPopup('amazon', role), 250);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Nao foi possivel salvar a configuracao da Amazon Music.');
    if (status) status.textContent = message;
    showToast(message, 'error');
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Salvar e conectar';
    }
  }
}

function humanizePlatformError(message) {
  const raw = String(message || '').trim();
  if (!raw) {
    return 'Nao foi possivel concluir essa etapa agora.';
  }

  const lowered = raw.toLowerCase();

  if (
    (lowered.includes('amazon music') && lowered.includes('http 404')) ||
    lowered.includes('erro ao criar playlist: http 404') ||
    lowered.includes('nao consegui criar a playlist no amazon music com esta sessao')
  ) {
    return 'Nao consegui criar a playlist no Amazon Music com esta sessao. Reconecte o Amazon Music e tente novamente.';
  }

  if (
    lowered.includes('criei a playlist no amazon music') &&
    lowered.includes('nao consegui adicionar as musicas')
  ) {
    return 'Criei a playlist no Amazon Music, mas nao consegui adicionar as musicas com esta sessao. Reconecte o Amazon Music e tente novamente.';
  }

  if (lowered.includes('playlist pode ter mais de 50')) {
    if (state.platforms.spotify?.oauth_configured) {
      return 'Essa playlist do Spotify e grande. Clique em "Fazer login e autorizar" para liberar a leitura completa.';
    }
    return 'Essa playlist do Spotify e maior do que o acesso publico permite nesta instalacao.';
  }

  if (
    lowered.includes('nao esta publico') ||
    lowered.includes('nao esta publica') ||
    lowered.includes('acesso compartilhado ou protegido')
  ) {
    return 'Essa playlist do Spotify nao esta publica. Sem fazer login no Spotify, o app nao consegue abrir ela.';
  }

  if (
    lowered.includes('sp_dc') ||
    lowered.includes('http 400') ||
    lowered.includes('spotify recusou o cookie') ||
    lowered.includes('cookie informado')
  ) {
    if (state.platforms.spotify?.oauth_configured) {
      return 'O modo manual do Spotify nao conseguiu confirmar sua sessao. Use o login oficial em "Fazer login e autorizar".';
    }
    return 'O modo manual do Spotify nao conseguiu confirmar sua sessao. Para evitar isso de vez, esta instalacao ainda precisa ativar o login oficial do Spotify.';
  }

  if (lowered.includes('spotify_oauth_not_configured')) {
    return 'O login automatico do Spotify ainda nao foi ativado nesta instalacao.';
  }

  if (lowered.includes('spotify_oauth_required_for_destination')) {
    return 'Para usar Spotify como destino, falta configurar o login oficial do Spotify no PlayTransfer. Depois disso, o usuario conecta com um clique.';
  }

  if (lowered.includes('spotify_destination_requires_oauth_reconnect')) {
    return 'Reconecte o Spotify pelo login oficial antes de transferir para ele. O login antigo por navegador nao consegue criar playlist com estabilidade.';
  }

  if (lowered.includes('spotify_oauth_missing_playlist_scope')) {
    return 'O Spotify conectou, mas nao liberou permissao para criar playlists. Reconecte pelo login oficial e aceite a permissao de criar playlists.';
  }

  if (lowered.includes('spotify_oauth_reconnect_required_after_403')) {
    return 'O Spotify recusou essa sessao OAuth para criar playlist. Reconecte o Spotify pelo login oficial e tente a transferencia novamente.';
  }

  if (lowered.includes('spotify_profile_failed')) {
    return 'O Spotify autorizou, mas nao devolveu os dados da conta. Tente conectar novamente pelo login oficial.';
  }

  if (lowered.includes('token_exchange_failed')) {
    return 'O Spotify abriu o login oficial, mas a troca de autorizacao falhou. Confira o Client ID e a Redirect URI configurados no Spotify Developer Dashboard.';
  }

  if (lowered.includes('spotify recusou o login nessa janela')) {
    return 'O Spotify recusou o login nessa janela. Use o botao Google/Apple/Facebook se essa conta foi criada assim; para resolver de vez, o app precisa usar o login oficial OAuth do Spotify no navegador.';
  }

  if (lowered.includes('sessao do spotify expirou') || lowered.includes('nao foi possivel renovar')) {
    return 'A sessao do Spotify expirou. Reconecte o Spotify e tente a transferencia novamente.';
  }

  if (lowered.includes('spotify ainda esta pausando essa sessao') || lowered.includes('spotify ainda esta pausando esta conta')) {
    return 'O Spotify esta limitando essa conta agora. Aguarde alguns minutos e tente transferir novamente.';
  }

  if (
    lowered.includes('nao foi possivel criar playlist no soundcloud') ||
    lowered.includes('nao foi possivel adicionar faixas no soundcloud') ||
    lowered.includes('falha ao gerar playlist no soundcloud') ||
    lowered.includes('falha ao incluir musicas no soundcloud') ||
    lowered.includes('soundcloud com a sessao web') ||
    lowered.includes('soundcloud recusou criar ou editar')
  ) {
    return 'O SoundCloud conectou e encontrou as musicas, mas recusou a criacao final da playlist nesta sessao. Reconecte o SoundCloud e tente iniciar a transferencia novamente.';
  }

  if (
    lowered.includes('soundcloud_oauth_not_configured') ||
    lowered.includes('soundcloud_oauth_required_for_destination')
  ) {
    return 'Conecte o SoundCloud pelo botao automatico antes de iniciar a transferencia.';
  }

  if (lowered.includes('soundcloud_token_exchange_failed')) {
    return 'O SoundCloud abriu o login oficial, mas a troca de autorizacao falhou. Confira Client ID, Client Secret e Redirect URI do app SoundCloud.';
  }

  if (lowered.includes('soundcloud_profile_failed')) {
    return 'O SoundCloud autorizou, mas nao devolveu os dados da conta. Tente conectar novamente pelo login oficial.';
  }

  if (
    lowered.includes('spotify') &&
    (lowered.includes('http 403') || lowered.includes('bloqueou a criacao da playlist com esta sessao'))
  ) {
    return 'O Spotify bloqueou essa operacao com a sessao atual (erro 403). Tente reconectar o Spotify usando o login oficial OAuth.';
  }

  if (
    lowered.includes('spotify bloqueou a criacao da playlist') ||
    lowered.includes('ativar o login oficial do spotify')
  ) {
    return 'O Spotify bloqueou a criacao por esse login do navegador. Para Spotify como destino, esta instalacao precisa usar o login oficial do Spotify.';
  }

  if (lowered.includes('api rate limit exceeded') && lowered.includes('spotify')) {
    return 'O Spotify limitou essa sessao agora. Aguarde um pouco e tente conectar o Spotify novamente.';
  }

  if (lowered.includes('nao encontrei o login do spotify salvo nos navegadores desta maquina')) {
    return 'Nao achei o login do Spotify salvo nos navegadores desta maquina. Abra o Spotify Web ja logado e tente de novo.';
  }

  if (lowered.includes('chrome desta maquina bloqueou a leitura automatica do spotify')) {
    return 'O Chrome desta maquina bloqueou a leitura automatica do Spotify. O app vai depender da janela guiada ou do modo manual.';
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

  if (lowered.includes('arl_timeout')) {
    return 'A janela do Deezer ficou aberta, mas o login nao terminou a tempo. Tente de novo e conclua o login nela.';
  }

  if (lowered.includes('arl_aborted')) {
    return 'A janela do Deezer foi fechada antes do login automatico terminar.';
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

  if (
    lowered.includes('nao consegui validar a sessao do soundcloud') ||
    lowered.includes('access token do soundcloud invalido ou expirado') ||
    lowered.includes('tempo esgotado aguardando a sessao web do soundcloud')
  ) {
    return 'Consegui abrir o SoundCloud, mas essa sessao ainda nao liberou permissao para criar playlists. Tente conectar novamente pela janela guiada.';
  }

  if (
    lowered.includes('soundcloud_login_required') ||
    lowered.includes('soundcloud_web_session_required') ||
    lowered.includes('soundcloud_validation_failed') ||
    lowered.includes('nao encontrei o login do soundcloud salvo') ||
    lowered.includes('edge desta maquina bloqueou a leitura automatica do soundcloud') ||
    lowered.includes('soundcloud_browser_token_not_found') ||
    lowered.includes('playlist do soundcloud nao encontrada ou privada') ||
    lowered.includes('para usar soundcloud como destino') ||
    (lowered.includes('soundcloud') && lowered.includes('access token'))
  ) {
    return 'Abra a janela de login do SoundCloud pelo botao, entre na sua conta e deixe o app confirmar sozinho.';
  }

  if (lowered.includes('developer token da apple music') || lowered.includes('music user token da apple music')) {
    return 'Para usar a Apple Music aqui, faltam os codigos dessa conta.';
  }

  if (
    lowered.includes('amazon_music_api_access_required') ||
    lowered.includes('amazon_music_oauth_required') ||
    lowered.includes('api key do amazon music') ||
    lowered.includes('access token do amazon music')
  ) {
    return 'Amazon Music ainda não está disponível nesta instalação.';
  }

  if (lowered.includes('amazon_music_api_not_enabled')) {
    return 'A Amazon abriu a conta, mas ainda não liberou esta integração para criar playlists aqui.';
  }

  if (lowered.includes('amazon_lwa_token_exchange_failed')) {
    return 'A Amazon abriu o login, mas não concluiu a autorização para o PlayTransfer. Tente novamente.';
  }

  if (lowered.includes('amazon_music_auth_failed')) {
    return 'A Amazon Music recusou essa sessão. Tente conectar novamente.';
  }

  if (lowered.includes('amazon_music_validation_failed')) {
    return 'Consegui voltar da Amazon, mas ainda não consegui confirmar a permissão para criar playlists aqui.';
  }

  if (lowered.includes('beta fechado') && lowered.includes('amazon music')) {
    return 'Amazon Music ainda não está disponível nesta instalação.';
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
  return OPTIONAL_SOURCE_CONNECTIONS.has(platform);
}

function updateUrlHint() {
  const hints = {
    spotify: 'Ex.: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M',
    deezer: 'Ex.: https://www.deezer.com/br/playlist/1234567890',
    youtube: 'Ex.: https://music.youtube.com/playlist?list=PLxxxxxx',
    soundcloud: 'Ex.: https://soundcloud.com/usuario/sets/nome-da-playlist',
    apple: 'Ex.: https://music.apple.com/br/playlist/nome/pl.xxxxxx',
    tidal: 'Ex.: https://listen.tidal.com/playlist/00000000-0000-0000-0000-000000000000',
    amazon: 'Ex.: https://music.amazon.com.br/user-playlists/abcd1234',
  };

  let hint = hints[state.srcPlatform] || 'Cole o link completo da playlist.';
  if (state.srcPlatform === 'spotify') {
    hint += ' Playlists publicas menores funcionam direto sem login.';
  } else if (isSourceConnectionOptional(state.srcPlatform)) {
    hint += ' Para playlists publicas, voce pode pular o login da origem.';
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

async function connectSpotify(role, credentials = null) {
  const spDc = document.getElementById(`${role}-spotify-cookie`)?.value?.trim() || '';
  const status = document.getElementById(`${role}-spotify-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';

  try {
    const r = await fetch('/api/connect/spotify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ...(credentials || { sp_dc: spDc }), role }),
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
      return true;
    }

    const message = humanizePlatformError(d.error || 'Falha ao conectar Spotify');
    if (status) status.textContent = message;
    showToast(message, 'error');
    return false;
  } catch {
    if (status) status.textContent = 'Erro de rede.';
    showToast('Erro ao conectar Spotify', 'error');
    return false;
  }
}

async function autoConnectSpotify(role) {
  const status = document.getElementById(`${role}-spotify-status`);
  const btn = document.getElementById(`${role}-spotify-auto-btn`);
  const hint = document.getElementById(`${role}-spotify-hint`);
  const oauthConfigured = !!state.platforms.spotify?.oauth_configured;

  if (oauthConfigured) {
    if (status) status.innerHTML = '<span class="spin-inline"></span> Abrindo o login oficial do Spotify...';
    openOAuthPopup('spotify', role);
    return;
  }

  if (role === 'dest') {
    if (status) status.textContent = 'Vamos ativar o login oficial do Spotify nesta instalacao.';
    if (hint) hint.textContent = 'Cole o Client ID uma vez. Depois o usuario final nao ve mais essa etapa.';
    openSpotifyOAuthSetupModal(role);
    return;
  }

  state.spotifyAutoConnecting = state.spotifyAutoConnecting || {};
  state.spotifyAutoConnecting[role] = true;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spin-inline"></span> Conectando...';
  }

  if (status) {
    status.innerHTML = '<span class="spin-inline"></span> Abrindo uma janela limpa de login do Spotify...';
  }
  if (hint) {
    hint.textContent = 'Entre na conta do Spotify que vai receber a playlist. Se aparecer erro, tente Google/Apple/Facebook na propria janela ou feche para tentar de novo.';
  }

  try {
    const r = await fetch('/api/connect/spotify/browser-guided/start', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ role }),
    });
    const d = await r.json();
    if (!d.ok) {
      throw new Error(d.error || 'Falha ao iniciar captura');
    }

    await pollSpotifyAutoConnect(role, 0);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha na captura automatica do Spotify');
    if (status) status.textContent = message;
    resetSpotifyAutoBtn(role);
  }
}

async function pollSpotifyAutoConnect(role, attempt = 0) {
  const status = document.getElementById(`${role}-spotify-status`);
  const input = document.getElementById(`${role}-spotify-cookie`);

  try {
    const r = await fetch(`/api/connect/spotify/browser-guided/status?role=${encodeURIComponent(role)}`);
    const d = await r.json();

    if (d.status === 'pending') {
      if (status) {
        status.innerHTML = '<span class="spin-inline"></span> Aguardando o login do Spotify. Se a janela mostrar erro, tente outro metodo de entrada nela.';
      }
    } else if (d.status === 'captured' && (d.access_token || d.cookie_header || d.sp_dc)) {
      if (input && (d.cookie_header || d.sp_dc)) input.value = d.cookie_header || d.sp_dc;
      if (status) {
        status.innerHTML = '<span class="spin-inline"></span> Login capturado! Confirmando conexao...';
      }

      const success = await connectSpotify(
        role,
        (d.access_token || d.cookie_header || d.sp_dc) ? {
          access_token: d.access_token,
          trusted_webview: true,
          client_token: d.client_token || '',
          sp_dc: d.sp_dc || '',
          cookie_header: d.cookie_header || '',
          display_name: d.display_name || '',
          avatar: d.avatar || '',
        } : null
      );
      if (success) {
        state.spotifyAutoConnecting[role] = false;
        return;
      }

      resetSpotifyAutoBtn(role);
      return;
    } else if (d.status === 'error') {
      let message = humanizePlatformError(d.error || 'Falha na captura automatica do Spotify');
      if (String(d.error || '') === 'missing_spotify_token') {
        message = 'Nao consegui confirmar o login do Spotify nessa tentativa. Abra a janela de login e tente de novo.';
      }
      if (status) status.textContent = message;
      resetSpotifyAutoBtn(role);
      return;
    }
  } catch {
    if (status) status.textContent = 'Erro ao acompanhar a captura do Spotify. Tente de novo ou use o modo manual abaixo.';
    resetSpotifyAutoBtn(role);
    return;
  }

  if (attempt >= 160) {
    if (status) status.textContent = 'A captura do Spotify demorou demais. Tente de novo ou use o modo manual abaixo.';
    resetSpotifyAutoBtn(role);
    return;
  }

  state.spotifyCapturePolls = state.spotifyCapturePolls || {};
  state.spotifyCapturePolls[role] = setTimeout(() => {
    pollSpotifyAutoConnect(role, attempt + 1);
  }, 900);
}

function resetSpotifyAutoBtn(role) {
  state.spotifyAutoConnecting = state.spotifyAutoConnecting || {};
  state.spotifyAutoConnecting[role] = false;

  if (state.spotifyCapturePolls?.[role]) {
    clearTimeout(state.spotifyCapturePolls[role]);
    state.spotifyCapturePolls[role] = null;
  }

  const btn = document.getElementById(`${role}-spotify-auto-btn`);
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = '🔌 Tentar novamente';
  }
}

let appleMusicKitLoaderPromise = null;
const APPLE_MUSIC_LOGIN_WINDOW_NAME = 'apple-music-service-view';

async function fetchAppleMusicConfig() {
  const response = await fetch('/api/config/apple-music');
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || 'apple_musickit_not_configured');
  }
  return data;
}

async function saveAppleMusicDeveloperToken(role) {
  const status = document.getElementById(`${role}-apple-status`);
  const developerToken = document.getElementById(`${role}-apple-developer-token`)?.value?.trim() || '';
  const storefront = (document.getElementById(`${role}-apple-storefront`)?.value?.trim() || 'us').toLowerCase();

  if (!developerToken) {
    openAppleManualDetails(role);
    if (status) status.textContent = 'Cole o developer token da Apple Music para ativar o login oficial desta instalação.';
    throw new Error('apple_musickit_not_configured');
  }

  if (status) status.innerHTML = '<span class="spin-inline"></span> Salvando o developer token desta instalacao...';

  const response = await fetch('/api/config/apple-music', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      developer_token: developerToken,
      storefront,
    }),
  });
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || 'apple_musickit_not_configured');
  }
  return data;
}

function openAppleManualDetails(role) {
  const details = document.getElementById(`${role}-apple-details`);
  if (!details) return;
  details.open = true;
  details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function setAppleAutoButton(role, busy) {
  const btn = document.getElementById(`${role}-apple-auto-btn`);
  if (!btn) return;
  btn.disabled = busy;
  btn.innerHTML = busy ? '<span class="spin-inline"></span> Conectando...' : '🔌 Tentar novamente';
}

function appleLoginPopupFeatures() {
  const width = 520;
  const height = 720;
  const left = Math.max(0, Math.round((window.screenX || 0) + ((window.outerWidth || window.innerWidth || 1200) - width) / 2));
  const top = Math.max(0, Math.round((window.screenY || 0) + ((window.outerHeight || window.innerHeight || 900) - height) / 2));
  return `popup=yes,width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`;
}

function openAppleLoginPopupShell() {
  try {
    const popup = window.open('', APPLE_MUSIC_LOGIN_WINDOW_NAME, appleLoginPopupFeatures());
    if (popup && !popup.closed) {
      try {
        popup.document.title = 'Login Apple Music - PlayTransfer';
        popup.document.body.style.cssText = 'margin:0;display:grid;place-items:center;min-height:100vh;background:#111;color:#fff;font-family:sans-serif;';
        popup.document.body.innerHTML = '<div style="text-align:center;max-width:320px;padding:24px;"><strong>Apple Music</strong><p>Preparando login oficial...</p></div>';
      } catch {}
      popup.focus();
    }
    return popup || null;
  } catch {
    return null;
  }
}

function closeAppleLoginPopup(popup) {
  try {
    if (popup && !popup.closed) popup.close();
  } catch {}
}

function looksLikeAppleMusicUserToken(value) {
  const token = String(value || '').trim().replace(/^Bearer\s+/i, '');
  if (!token || token.length < 40) return false;
  if (/[\s{}()[\]"']/.test(token)) return false;
  if (/cachedsource|clientconfig|feature|experiment|config/i.test(token)) return false;
  return true;
}

function readAppleMusicTokenFromStorage() {
  const stores = [window.localStorage, window.sessionStorage].filter(Boolean);
  const tokenPattern = /(?:media-user-token|music-user-token|musicUserToken|userToken)["']?\s*[:=]\s*["']?([A-Za-z0-9._=-]{40,})/i;

  for (const store of stores) {
    try {
      for (let i = 0; i < store.length; i++) {
        const key = String(store.key(i) || '');
        const value = String(store.getItem(key) || '');
        const combined = `${key}=${value}`;
        const match = combined.match(tokenPattern);
        if (match && looksLikeAppleMusicUserToken(match[1])) return match[1].trim();

        const lowerKey = key.toLowerCase();
        if (
          (lowerKey.includes('media-user-token') ||
            lowerKey.includes('music-user-token') ||
            lowerKey.includes('musicusertoken') ||
            lowerKey.includes('usertoken')) &&
          looksLikeAppleMusicUserToken(value)
        ) {
          return value.trim();
        }
      }
    } catch {}
  }
  return '';
}

function getAppleMusicUserToken(music, event = null) {
  const candidates = [
    music?.musicUserToken,
    event?.musicUserToken,
    event?.userToken,
    event?.token,
    event?.data?.musicUserToken,
    event?.data?.userToken,
    event?.detail?.musicUserToken,
    event?.detail?.userToken,
    readAppleMusicTokenFromStorage(),
  ];

  for (const candidate of candidates) {
    const token = String(candidate || '').trim();
    if (looksLikeAppleMusicUserToken(token)) return token.replace(/^Bearer\s+/i, '');
  }
  return '';
}

function waitForAppleMusicAuthorization(music, authorizeAction, loginPopup) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const listeners = [];
    const startedAt = Date.now();

    const cleanup = () => {
      clearInterval(interval);
      clearTimeout(timeout);
      for (const [target, eventName, handler] of listeners) {
        try {
          target?.removeEventListener?.(eventName, handler);
        } catch {}
      }
    };

    const finish = (token) => {
      if (settled) return;
      const normalized = String(token || '').trim();
      if (!looksLikeAppleMusicUserToken(normalized)) return;
      settled = true;
      cleanup();
      closeAppleLoginPopup(loginPopup);
      resolve(normalized.replace(/^Bearer\s+/i, ''));
    };

    const fail = (error) => {
      if (settled) return;
      settled = true;
      cleanup();
      closeAppleLoginPopup(loginPopup);
      reject(error instanceof Error ? error : new Error(String(error || 'apple_musickit_authorize_failed')));
    };

    const check = (event = null) => {
      const token = getAppleMusicUserToken(music, event);
      if (token) finish(token);
    };

    const eventNames = [
      window.MusicKit?.Events?.userTokenDidChange,
      window.MusicKit?.Events?.authorizationStatusDidChange,
      'userTokenDidChange',
      'authorizationStatusDidChange',
    ].filter(Boolean);

    for (const target of [music, music?.storekit].filter(Boolean)) {
      for (const eventName of eventNames) {
        try {
          const handler = (event) => check(event);
          target?.addEventListener?.(eventName, handler);
          listeners.push([target, eventName, handler]);
        } catch {}
      }
    }

    const interval = setInterval(() => {
      check();
      try {
        if (loginPopup && loginPopup.closed && Date.now() - startedAt > 2500) {
          const token = getAppleMusicUserToken(music);
          if (token) finish(token);
          else fail(new Error('apple_musickit_authorize_closed'));
        }
      } catch {}
    }, 500);

    const timeout = setTimeout(() => {
      const token = getAppleMusicUserToken(music);
      if (token) finish(token);
      else fail(new Error('apple_musickit_authorize_timeout'));
    }, 90000);

    check();

    let authorizePromise;
    try {
      authorizePromise = typeof authorizeAction === 'function' ? authorizeAction() : authorizeAction;
    } catch (error) {
      fail(error);
      return;
    }

    Promise.resolve(authorizePromise)
      .then((token) => {
        const resolvedToken = token || getAppleMusicUserToken(music);
        if (resolvedToken) {
          finish(resolvedToken);
          return;
        }
        setTimeout(() => {
          const lateToken = getAppleMusicUserToken(music);
          if (lateToken) finish(lateToken);
          else fail(new Error('apple_music_user_token_required'));
        }, 1200);
      })
      .catch((error) => fail(error));
  });
}

async function ensureAppleMusicKitLoaded() {
  if (window.MusicKit) return window.MusicKit;
  if (appleMusicKitLoaderPromise) return appleMusicKitLoaderPromise;

  appleMusicKitLoaderPromise = new Promise((resolve, reject) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      if (!window.MusicKit) return;
      settled = true;
      resolve(window.MusicKit);
    };
    const fail = () => {
      if (settled) return;
      settled = true;
      reject(new Error('apple_musickit_load_failed'));
    };

    document.addEventListener('musickitloaded', finish, { once: true });

    const existing = document.querySelector('script[data-musickit-loader="apple"]');
    if (existing) {
      existing.addEventListener('load', finish, { once: true });
      existing.addEventListener('error', fail, { once: true });
      setTimeout(finish, 0);
      setTimeout(fail, 15000);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://js-cdn.music.apple.com/musickit/v1/musickit.js';
    script.async = true;
    script.dataset.musickitLoader = 'apple';
    script.onload = finish;
    script.onerror = fail;
    document.head.appendChild(script);
    setTimeout(fail, 15000);
  });

  return appleMusicKitLoaderPromise;
}

async function getAppleMusicInstance(developerToken) {
  const MusicKit = await ensureAppleMusicKitLoaded();
  if (!MusicKit) {
    throw new Error('apple_musickit_load_failed');
  }

  const tokenChanged = state.appleMusicKitConfig?.developerToken !== developerToken;
  if (!state.appleMusicKitConfig || tokenChanged) {
    try {
      MusicKit.configure({
        developerToken,
        app: {
          name: 'PlayTransfer',
          build: '1.2.19',
        },
      });
      state.appleMusicKitConfig = { developerToken };
    } catch (error) {
      if (!MusicKit.getInstance) {
        throw new Error('apple_musickit_config_failed');
      }
    }
  }

  const instance = MusicKit.getInstance?.();
  if (!instance) {
    throw new Error('apple_musickit_config_failed');
  }
  return instance;
}

async function authorizeAppleMusicUser(developerToken, loginPopup = null) {
  let music;
  try {
    music = await getAppleMusicInstance(developerToken);
  } catch (error) {
    closeAppleLoginPopup(loginPopup);
    throw error;
  }

  if (music.musicUserToken) {
    closeAppleLoginPopup(loginPopup);
    return music.musicUserToken;
  }

  const originalOpen = window.open;
  window.open = function(url, target, features) {
    const text = String(url || '');
    if (/apple\.com|idmsa\.apple\.com|itunes\.apple\.com/i.test(text)) {
      if (loginPopup && !loginPopup.closed) {
        try {
          loginPopup.location.href = text;
          loginPopup.focus();
          return loginPopup;
        } catch {}
      }
      return originalOpen.call(window, text, target || APPLE_MUSIC_LOGIN_WINDOW_NAME, appleLoginPopupFeatures());
    }
    return originalOpen.apply(window, arguments);
  };

  try {
    const token = await waitForAppleMusicAuthorization(music, () => music.authorize(), loginPopup);
    return token || '';
  } catch (error) {
    closeAppleLoginPopup(loginPopup);
    const reason = String(error?.message || error || '').trim();
    throw new Error(`apple_musickit_authorize_failed${reason ? `:${reason}` : ''}`);
  } finally {
    window.open = originalOpen;
  }
}

function makeAppleForm(role) {
  const wrapper = document.createElement('div');
  const appleDetails = makeAdvancedDetails(
    'Nao funcionou? Fazer manualmente',
    makeFormPanel(`
      <div class="manual-connect-header">
        <div class="manual-connect-title">Dados da Apple Music</div>
        <div class="manual-connect-subtitle">Cole o developer token uma vez nesta instalacao. O music user token pode ficar vazio: o login oficial da Apple preenche isso sozinho.</div>
      </div>
      ${makeTextAreaField(`${role}-apple-developer-token`, 'Developer token da instalacao', 'eyJhbGciOi...')}
      ${makeTextAreaField(`${role}-apple-user-token`, 'Music user token (opcional)', 'music-user-token...')}
      ${makeTextInputField(`${role}-apple-storefront`, 'Pais da conta', 'br, us, gb...', 'us')}
      <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:16px;">
        <button class="btn btn-secondary btn-sm" type="button" onclick="saveAppleMusicDeveloperToken('${role}')">Salvar developer token</button>
        <button class="btn btn-secondary btn-sm" type="button" onclick="connectApple('${role}')">Conectar Apple Music</button>
      </div>
      ${makeInlineStatus(`${role}-apple-status`)}
    `),
    role === 'dest'
  );
  appleDetails.id = `${role}-apple-details`;

  const automaticSubtitle = role === 'src'
    ? 'Se a playlist for publica, o app ja consegue ler so pelo link. Se o MusicKit desta instalacao estiver pronto, este botao tambem entra na conta Apple Music.'
    : 'Quando esta instalacao ja tem o developer token salvo, este botao abre o login oficial da Apple e conecta a conta em um passo.';
  const automaticHint = role === 'src'
    ? 'Para usar apenas links publicos, voce pode seguir sem login. Para fazer login na conta Apple Music, falta so o setup do MusicKit desta instalacao.'
    : 'Se ainda nao houver MusicKit configurado, o app abre o bloco abaixo para salvar o developer token e continuar daqui.';

  wrapper.appendChild(makeAutomaticConnectPanel({
    platform: 'apple',
    role,
    title: 'Conectar Apple Music',
    subtitle: automaticSubtitle,
    hint: automaticHint,
    statusId: `${role}-apple-status`,
    buttonLabel: '🔌 Conectar Apple Music oficialmente',
    action: `autoConnectApple('${role}')`,
  }));

  wrapper.appendChild(appleDetails);
  return wrapper;
}

async function connectApple(role, options = {}) {
  const status = document.getElementById(`${role}-apple-status`);
  let developerToken = options.developer_token ?? document.getElementById(`${role}-apple-developer-token`)?.value?.trim() ?? '';
  let musicUserToken = options.music_user_token ?? document.getElementById(`${role}-apple-user-token`)?.value?.trim() ?? '';
  let storefront = (options.storefront ?? document.getElementById(`${role}-apple-storefront`)?.value?.trim() ?? 'us').toLowerCase() || 'us';

  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';

  try {
    if (!developerToken) {
      const config = await fetchAppleMusicConfig().catch(() => null);
      if (config?.configured) {
        developerToken = config.developer_token || '';
        storefront = config.storefront || storefront;
      }
    }

    if (!developerToken && role === 'src') {
      const response = await fetch('/api/connect/apple', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ role, storefront }),
      });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || 'Falha ao preparar Apple Music');
      state.srcSid = data.sid;
      state.srcDisplayName = data.display_name;
      showToast('Apple Music pronta para links publicos!', 'success');
      renderConnectForms();
      checkTransferReady();
      return true;
    }

    if (!developerToken) {
      openAppleManualDetails(role);
      throw new Error('apple_musickit_not_configured');
    }

    if (!musicUserToken) {
      musicUserToken = await authorizeAppleMusicUser(developerToken, options.loginPopup || null);
    }

    if (!musicUserToken) {
      throw new Error('apple_music_user_token_required');
    }

    const response = await fetch('/api/connect/apple', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        role,
        developer_token: developerToken,
        music_user_token: musicUserToken,
        storefront,
      }),
    });
    const data = await response.json();
    if (!data.ok) {
      throw new Error(data.error || 'Falha ao conectar Apple Music');
    }

    if (role === 'src') {
      state.srcSid = data.sid;
      state.srcDisplayName = data.display_name;
    } else {
      state.destSid = data.sid;
      state.destDisplayName = data.display_name;
    }

    showToast('Apple Music conectada!', 'success');
    renderConnectForms();
    checkTransferReady();
    return true;
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha ao conectar Apple Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
    return false;
  }
}

async function autoConnectApple(role) {
  const status = document.getElementById(`${role}-apple-status`);
  setAppleAutoButton(role, true);
  let loginPopup = null;

  try {
    let config = await fetchAppleMusicConfig().catch(() => null);
    if (!config?.configured) {
      const inlineDeveloperToken = document.getElementById(`${role}-apple-developer-token`)?.value?.trim() || '';
      if (inlineDeveloperToken) {
        config = await saveAppleMusicDeveloperToken(role);
      }
    }

    if (!config?.configured) {
      if (role === 'src') {
        const success = await connectApple(role, {});
        setAppleAutoButton(role, false);
        return success;
      }

      openAppleManualDetails(role);
      if (status) {
        status.textContent = 'Falta salvar o developer token desta instalacao. Depois disso, o login oficial da Apple abre daqui mesmo.';
      }
      setAppleAutoButton(role, false);
      return false;
    }

    const success = await connectApple(role, {
      developer_token: config.developer_token,
      storefront: config.storefront || 'us',
    });
    setAppleAutoButton(role, false);
    if (!success) {
      openAppleManualDetails(role);
    }
    return success;
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha ao conectar Apple Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
    openAppleManualDetails(role);
    setAppleAutoButton(role, false);
    return false;
  }
}

const _previousHumanizePlatformError = humanizePlatformError;
humanizePlatformError = function(message) {
  const raw = String(message || '').trim();
  const lowered = raw.toLowerCase();

  if (lowered.includes('apple_musickit_not_configured')) {
    return 'Esta instalacao ainda nao tem o developer token da Apple Music. Cole esse token no bloco manual uma vez e depois use o login oficial.';
  }

  if (lowered.includes('apple_music_user_token_required')) {
    return 'A Apple Music abriu, mas ainda faltou autorizar a conta. Tente o login oficial novamente.';
  }

  if (lowered.includes('apple_musickit_load_failed')) {
    return 'Nao consegui carregar o login oficial da Apple Music neste navegador.';
  }

  if (lowered.includes('apple_musickit_config_failed')) {
    return 'O MusicKit da Apple nao aceitou a configuracao desta instalacao. Revise o developer token salvo.';
  }

  if (lowered.includes('apple_musickit_authorize_failed')) {
    return 'A Apple Music nao concluiu a autorizacao da conta. Tente o login oficial novamente.';
  }

  return _previousHumanizePlatformError(raw);
};

function isAppleInstallationConfigured() {
  return !!state.platforms.apple?.installation_configured;
}

function makeAppleForm(role) {
  const wrapper = document.createElement('div');
  const installationReady = isAppleInstallationConfigured();

  wrapper.appendChild(makeAutomaticConnectPanel({
    platform: 'apple',
    role,
    title: 'Conectar Apple Music',
    subtitle: role === 'src'
      ? 'Para playlists publicas, o app pode ler so pelo link. Se voce quiser fazer login na conta Apple Music, este botao abre o login oficial em um clique.'
      : 'Este botao abre o login oficial da Apple Music e conecta a conta aqui mesmo, no mesmo fluxo dos outros destinos.',
    hint: installationReady
      ? 'O usuario final nao precisa preencher token, pais da conta ou codigo manual.'
      : 'Se o login oficial da Apple ainda estiver preparando esta sessao, tente novamente em alguns segundos.',
    statusId: `${role}-apple-status`,
    buttonLabel: '🔌 Conectar Apple Music',
    action: `autoConnectApple('${role}')`,
  }));

  return wrapper;
}

async function autoConnectApple(role) {
  const status = document.getElementById(`${role}-apple-status`);
  setAppleAutoButton(role, true);
  let loginPopup = null;

  try {
    const config = await fetchAppleMusicConfig().catch(() => null);
    const configured = !!config?.configured && !!config?.developer_token;
    if (state.platforms.apple) {
      state.platforms.apple.installation_configured = configured;
      state.platforms.apple.auto_configured = configured;
    }

    const success = await connectApple(role, {
      developer_token: config?.developer_token || '',
      storefront: config?.storefront || 'us',
    });
    if (!success && !configured && status && role === 'dest') {
      status.textContent = 'Nao consegui preparar o login oficial da Apple Music agora. Tente novamente em alguns segundos.';
    }
    setAppleAutoButton(role, false);
    return success;
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha ao conectar Apple Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
    setAppleAutoButton(role, false);
    return false;
  }
}

const __previousHumanizePlatformError = humanizePlatformError;
humanizePlatformError = function(message) {
  const raw = String(message || '').trim();
  const lowered = raw.toLowerCase();

  if (lowered.includes('apple_musickit_not_configured')) {
    return 'Nao consegui preparar o login oficial da Apple Music agora. Tente novamente em alguns segundos.';
  }

  if (lowered.includes('apple_music_user_token_required')) {
    return 'A Apple Music abriu, mas a conta ainda nao terminou a autorizacao. Tente o login oficial novamente.';
  }

  return __previousHumanizePlatformError(raw);
};

function resetAppleGuidedPoll(role) {
  state.appleCapturePolls = state.appleCapturePolls || {};
  if (state.appleCapturePolls[role]) {
    clearTimeout(state.appleCapturePolls[role]);
    state.appleCapturePolls[role] = null;
  }
}

function isAppleCloudLibraryError(message) {
  const lowered = String(message || '').toLowerCase();
  return (
    lowered.includes('apple_music_cloud_library_required') ||
    lowered.includes('apple_music_subscription_or_library_required') ||
    lowered.includes('apple_music_user_token_required_after_login') ||
    lowered.includes('cloudlibrary')
  );
}

function isAppleAuthorizationFinishedWithoutLibrary(message) {
  const lowered = String(message || '').toLowerCase();
  return (
    lowered.includes('apple_musickit_authorize_failed') ||
    lowered.includes('apple_music_user_token_required') ||
    lowered.includes('apple_musickit_authorize_closed') ||
    lowered.includes('apple_musickit_authorize_timeout')
  );
}

function normalizeAppleStorefront(value) {
  const storefront = String(value || '').trim().toLowerCase();
  return /^[a-z]{2}$/.test(storefront) ? storefront : '';
}

function appleCloudLibraryUnlockUrl(role) {
  const cached = state.appleMusicLastAuth?.[role] || {};
  const formStorefront = document.getElementById(`${role}-apple-storefront`)?.value;
  const browserCountry = String(navigator.language || '').split('-')[1] || '';
  const storefront =
    normalizeAppleStorefront(formStorefront) ||
    normalizeAppleStorefront(cached.storefront) ||
    normalizeAppleStorefront(browserCountry) ||
    'br';
  return `https://music.apple.com/${storefront}/subscribe`;
}

function renderAppleCloudLibraryUnlock(role, rawMessage = '') {
  const status = document.getElementById(`${role}-apple-status`);
  if (!status) return;

  const message = humanizePlatformError(rawMessage || 'apple_music_cloud_library_required');
  status.innerHTML = `
    <div class="apple-library-unlock">
      <div class="apple-library-unlock-title">Conta Apple Music encontrada</div>
      <div class="apple-library-unlock-copy">${message}</div>
      <div class="manual-connect-actions">
        <button class="btn btn-primary btn-sm" type="button" onclick="openAppleCloudLibraryUnlock('${role}')">
          Abrir Apple Music na web
        </button>
        <button class="btn btn-secondary btn-sm" type="button" onclick="retryAppleCloudLibrary('${role}')">
          Tentar novamente
        </button>
      </div>
    </div>
  `;
}

function openAppleCloudLibraryUnlock(role) {
  const url = appleCloudLibraryUnlockUrl(role);
  const opened = window.open(url, '_blank');
  try {
    if (opened) opened.opener = null;
  } catch {}
  const status = document.getElementById(`${role}-apple-status`);

  if (!opened) {
    if (status) {
      status.innerHTML = `
        <div class="apple-library-unlock">
          <div class="apple-library-unlock-title">Abra a ativacao da Apple</div>
          <div class="apple-library-unlock-copy">
             O navegador bloqueou a nova aba. Abra este link web e depois volte para tentar novamente:
             <a href="${url}" target="_blank" rel="noopener">ativacao online do Apple Music</a>
          </div>
          <div class="manual-connect-actions">
            <button class="btn btn-secondary btn-sm" type="button" onclick="retryAppleCloudLibrary('${role}')">
              Tentar novamente
            </button>
          </div>
        </div>
      `;
    }
    showToast('O navegador bloqueou a aba da Apple. Use o link exibido no card.', 'warn');
    return;
  }

  if (status) {
    status.innerHTML = `
      <div class="apple-library-unlock">
        <div class="apple-library-unlock-title">Finalize no site da Apple</div>
        <div class="apple-library-unlock-copy">
          Depois que a Apple liberar a assinatura ou a biblioteca dessa conta no Apple Music Web, volte aqui e tente novamente.
        </div>
        <div class="manual-connect-actions">
          <button class="btn btn-secondary btn-sm" type="button" onclick="retryAppleCloudLibrary('${role}')">
            Tentar novamente
          </button>
        </div>
      </div>
    `;
  }
}

async function retryAppleCloudLibrary(role) {
  const status = document.getElementById(`${role}-apple-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Verificando a liberacao da Apple Music...';

  try {
    const cached = state.appleMusicLastAuth?.[role];
    if (cached?.music_user_token || cached?.cookie_header) {
      await connectApple(role, {
        developer_token: cached.developer_token || '',
        music_user_token: cached.music_user_token || '',
        storefront: cached.storefront || 'us',
        cookie_header: cached.cookie_header || '',
        itfe: cached.itfe || '',
      });
      return;
    }

    await autoConnectApple(role);
  } catch (error) {
    const message = humanizePlatformError(error?.message || 'Falha ao verificar a Apple Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
  }
}

async function connectApple(role, options = {}) {
  const status = document.getElementById(`${role}-apple-status`);
  let musicUserToken = options.music_user_token ?? '';
  let storefront = (options.storefront ?? 'us').toLowerCase() || 'us';
  const cookieHeader = options.cookie_header ?? '';
  const itfe = options.itfe ?? '';

  if (status) status.innerHTML = '<span class="spin-inline"></span> Conectando...';

  try {
    const config = await fetchAppleMusicConfig().catch(() => null);
    const developerToken = options.developer_token || config?.developer_token || '';
    storefront = (options.storefront || config?.storefront || storefront || 'us').toLowerCase();

    if (!musicUserToken && !cookieHeader && role === 'src') {
      const response = await fetch('/api/connect/apple', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ role, storefront }),
      });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || 'Falha ao preparar Apple Music');
      state.srcSid = data.sid;
      state.srcDisplayName = data.display_name;
      showToast('Apple Music pronta para links publicos!', 'success');
      renderConnectForms();
      checkTransferReady();
      return true;
    }

    if (!developerToken) {
      throw new Error('apple_musickit_not_configured');
    }

    if (!musicUserToken && !cookieHeader) {
      if (status) status.innerHTML = '<span class="spin-inline"></span> Abrindo login oficial da Apple Music...';
      musicUserToken = await authorizeAppleMusicUser(developerToken, options.loginPopup || null);
      if (status) status.innerHTML = '<span class="spin-inline"></span> Login autorizado. Validando biblioteca...';
    }

    if (!musicUserToken && !cookieHeader) {
      throw new Error('apple_music_user_token_required_after_login');
    }

    state.appleMusicLastAuth = state.appleMusicLastAuth || {};
    state.appleMusicLastAuth[role] = {
      developer_token: developerToken,
      music_user_token: musicUserToken,
      storefront,
      cookie_header: cookieHeader,
      itfe,
    };

    const response = await fetch('/api/connect/apple', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        role,
        developer_token: developerToken,
        music_user_token: musicUserToken,
        storefront,
        cookie_header: cookieHeader,
        itfe,
      }),
    });
    const data = await response.json();
    if (!data.ok) {
      throw new Error(data.error || 'Falha ao conectar Apple Music');
    }

    if (role === 'src') {
      state.srcSid = data.sid;
      state.srcDisplayName = data.display_name;
    } else {
      state.destSid = data.sid;
      state.destDisplayName = data.display_name;
    }

    showToast('Apple Music conectada!', 'success');
    renderConnectForms();
    checkTransferReady();
    return true;
  } catch (error) {
    if (isAppleCloudLibraryError(error?.message) || isAppleAuthorizationFinishedWithoutLibrary(error?.message)) {
      renderAppleCloudLibraryUnlock(role, isAppleCloudLibraryError(error?.message) ? error?.message : 'apple_music_subscription_or_library_required');
      showToast(humanizePlatformError('apple_music_subscription_or_library_required'), 'warn');
      return false;
    }

    const message = humanizePlatformError(error?.message || 'Falha ao conectar Apple Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
    return false;
  }
}

async function pollAppleGuidedConnect(role, attempt = 0) {
  const status = document.getElementById(`${role}-apple-status`);

  try {
    const response = await fetch(`/api/connect/apple/browser-guided/status?role=${encodeURIComponent(role)}`);
    const data = await response.json();

    if (data.status === 'captured' && (data.music_user_token || data.cookie_header)) {
      if (status) status.innerHTML = '<span class="spin-inline"></span> Login reconhecido. Confirmando conexao...';
      await connectApple(role, {
        music_user_token: data.music_user_token,
        storefront: data.storefront || 'us',
        cookie_header: data.cookie_header || '',
        itfe: data.itfe || '',
      });
      setAppleAutoButton(role, false);
      resetAppleGuidedPoll(role);
      return;
    }

    if (data.status === 'error') {
      if (isAppleCloudLibraryError(data.error)) {
        renderAppleCloudLibraryUnlock(role, data.error);
        showToast(humanizePlatformError(data.error), 'warn');
        setAppleAutoButton(role, false);
        resetAppleGuidedPoll(role);
        return;
      }

      const message = humanizePlatformError(data.error || 'Falha ao confirmar o login da Apple Music');
      if (status) status.textContent = message;
      showToast(message, 'error');
      setAppleAutoButton(role, false);
      resetAppleGuidedPoll(role);
      return;
    }

    if (status && attempt === 0) {
      status.innerHTML = '<span class="spin-inline"></span> Aguardando o login no Apple Music Web...';
    }
  } catch {
    if (status) status.textContent = 'Erro de rede enquanto eu aguardava a Apple Music.';
    showToast('Erro ao acompanhar o login da Apple Music', 'error');
    setAppleAutoButton(role, false);
    resetAppleGuidedPoll(role);
    return;
  }

  state.appleCapturePolls = state.appleCapturePolls || {};
  state.appleCapturePolls[role] = setTimeout(() => {
    pollAppleGuidedConnect(role, attempt + 1);
  }, 1000);
}

async function startAppleGuidedConnect(role) {
  const status = document.getElementById(`${role}-apple-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span> Abrindo login oficial da Apple Music...';
  resetAppleGuidedPoll(role);
  const loginPopup = openAppleLoginPopupShell();
  const config = await fetchAppleMusicConfig().catch(() => null);
  if (!config?.configured || !config?.developer_token) {
    closeAppleLoginPopup(loginPopup);
    throw new Error('apple_musickit_not_configured');
  }
  return connectApple(role, {
    developer_token: config.developer_token,
    storefront: config.storefront || 'us',
    loginPopup,
  });
}

async function autoConnectApple(role) {
  const status = document.getElementById(`${role}-apple-status`);
  setAppleAutoButton(role, true);
  let loginPopup = null;

  try {
    if (role === 'src') {
      const usePublicSource = !String(document.getElementById('playlist-url')?.value || '').trim();
      if (usePublicSource) {
        const success = await connectApple(role, {});
        setAppleAutoButton(role, false);
        return success;
      }
    }

    loginPopup = openAppleLoginPopupShell();
    const config = await fetchAppleMusicConfig().catch(() => null);
    if (!config?.configured || !config?.developer_token) {
      closeAppleLoginPopup(loginPopup);
      throw new Error('apple_musickit_not_configured');
    }

    const success = await connectApple(role, {
      developer_token: config?.developer_token || '',
      storefront: config?.storefront || 'us',
      loginPopup,
    });
    setAppleAutoButton(role, false);
    return success;
  } catch (error) {
    closeAppleLoginPopup(loginPopup);
    if (isAppleCloudLibraryError(error?.message) || isAppleAuthorizationFinishedWithoutLibrary(error?.message)) {
      renderAppleCloudLibraryUnlock(role, isAppleCloudLibraryError(error?.message) ? error?.message : 'apple_music_subscription_or_library_required');
      showToast(humanizePlatformError('apple_music_subscription_or_library_required'), 'warn');
      setAppleAutoButton(role, false);
      resetAppleGuidedPoll(role);
      return false;
    }

    const message = humanizePlatformError(error?.message || 'Falha ao iniciar a Apple Music');
    if (status) status.textContent = message;
    showToast(message, 'error');
    setAppleAutoButton(role, false);
    resetAppleGuidedPoll(role);
    return false;
  }
}

const ___previousHumanizePlatformError = humanizePlatformError;
humanizePlatformError = function(message) {
  const raw = String(message || '').trim();
  const lowered = raw.toLowerCase();

  if (lowered.includes('missing_apple_user_token')) {
    return 'Nao consegui confirmar o login da Apple Music nessa tentativa. Tente o login oficial novamente.';
  }

  if (lowered.includes('apple_musickit_config_failed')) {
    return 'A Apple Music abriu, mas a sessao dessa conta nao ficou disponivel para o app ainda. Tente novamente.';
  }

  if (lowered.includes('apple_musickit_load_failed')) {
    return 'Nao consegui carregar o login oficial da Apple Music agora.';
  }

  if (lowered.includes('apple_musickit_authorize_timeout')) {
    return 'A janela da Apple Music ficou aberta, mas a autorizacao nao voltou para o app. Feche a janela e tente conectar novamente.';
  }

  if (lowered.includes('apple_musickit_authorize_closed')) {
    return 'A janela da Apple Music foi fechada antes da autorizacao voltar para o app. Tente conectar novamente.';
  }

  if (lowered.includes('apple_browser_session_not_found') || lowered.includes('nao encontrei a sessao da apple music')) {
    return 'Nao encontrei o login da Apple Music no navegador ainda. Faca login no Apple Music Web e tente novamente.';
  }

  if (lowered.includes('chrome desta maquina bloqueou') && lowered.includes('apple')) {
    return 'Esse caminho antigo tentava ler a sessao do Chrome. Atualize a pagina e tente novamente: agora o login da Apple Music usa uma janela oficial do MusicKit.';
  }

  if (lowered.includes('apple_music_cloud_library_required') || lowered.includes('cloudlibrary')) {
    return 'Consegui abrir a conta Apple Music, mas essa conta nao liberou acesso a biblioteca do iCloud Music. Sem isso, a Apple nao deixa criar playlists aqui.';
  }

  if (
    lowered.includes('apple_music_subscription_or_library_required') ||
    lowered.includes('apple_music_user_token_required_after_login') ||
    lowered.includes('apple_music_user_token_required')
  ) {
    return 'Consegui abrir a conta Apple Music, mas a Apple nao liberou acesso a biblioteca do iCloud Music. Se voce clicou em "Agora nao", conclua essa liberacao na Apple e tente novamente.';
  }

  if (lowered.includes('apple_musickit_authorize_failed')) {
    return 'Consegui abrir a Apple Music, mas a autorizacao nao liberou a biblioteca do iCloud Music para criar playlists aqui. Conclua essa liberacao na Apple e tente novamente.';
  }

  if (lowered.includes('apple music rejeitou a sessao') || lowered.includes('apple music rejeitou os tokens')) {
    return 'Consegui abrir a conta Apple Music, mas a validacao da sessao falhou. Tente o login oficial novamente.';
  }

  if (lowered.includes('apple_music_validation_failed')) {
    return 'Consegui abrir a Apple Music, mas a sessao dessa conta ainda nao ficou valida para o app. Faca o login oficial completo e tente outra vez.';
  }

  return ___previousHumanizePlatformError(raw);
};
