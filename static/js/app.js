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
  platforms: {},
  jobId: null,
  eventIdx: 0,
  pollTimer: null,
  transferStats: { found: 0, missing: 0, total: 0 },
  lastResultUrl: '',
};

const PLATFORM_ICONS = {
  spotify: `<svg viewBox="0 0 24 24" fill="currentColor" style="width:28px;height:28px;color:#1DB954"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 14.44c-.2.32-.63.42-.95.22-2.6-1.59-5.87-1.95-9.72-1.07-.37.09-.75-.14-.84-.51-.09-.37.14-.75.51-.84 4.21-.96 7.82-.55 10.73 1.24.32.2.42.63.22.96zm1.24-2.76c-.25.4-.78.52-1.18.27-2.98-1.83-7.51-2.36-11.03-1.29-.46.14-.94-.12-1.08-.58-.14-.46.12-.94.58-1.08 4.02-1.22 9.01-.63 12.43 1.47.4.25.52.78.27 1.18zm.1-2.88C14.24 8.85 8.81 8.7 5.54 9.65c-.54.16-1.12-.14-1.28-.69-.16-.54.14-1.12.69-1.28 3.77-1.08 10.04-.87 14 1.52.49.29.65.92.36 1.41-.29.49-.92.65-1.41.36z"/></svg>`,
  deezer:  `<svg viewBox="0 0 168 168" fill="none" style="width:28px;height:28px"><path d="M30 119.5h23.5V134H30zM30 97.5h23.5V112H30zM30 75.5h23.5V90H30zM56 119.5h23.5V134H56zM56 97.5h23.5V112H56zM82 119.5h23.5V134H82zM82 97.5h23.5V112H82zM108 119.5h23.5V134H108zM108 97.5h23.5V112H108zM108 75.5h23.5V90H108zM108 53.5h23.5V68H108zM134 119.5H157.5V134H134zM134 97.5H157.5V112H134zM134 75.5H157.5V90H134zM134 53.5H157.5V68H134zM134 31.5H157.5V46H134z" fill="#FF0092"/></svg>`,
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
function openOAuthPopup(platform, role) {
  const url = `/auth/${platform}?role=${role}`;
  const w = 520, h = 640;
  const left = (screen.width - w) / 2;
  const top  = (screen.height - h) / 2;
  const popup = window.open(url, 'oauth_popup',
    `width=${w},height=${h},left=${left},top=${top},toolbar=no,menubar=no`);
  if (!popup) {
    // Popup bloqueado — usa redirect
    window.location.href = url;
  }
}

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

// ── Platform Grids ─────────────────────────────────────────
function renderPlatformGrids() {
  const platforms = state.platforms;
  const srcGrid   = document.getElementById('src-grid');
  const destGrid  = document.getElementById('dest-grid');
  const srcSoon   = document.getElementById('src-soon');
  const destSoon  = document.getElementById('dest-soon');
  if (!srcGrid || !platforms) return;

  srcGrid.innerHTML = destGrid.innerHTML = '';
  if (srcSoon)  srcSoon.innerHTML  = '';
  if (destSoon) destSoon.innerHTML = '';

  Object.entries(platforms).forEach(([key, p]) => {
    if (p.soon) {
      // Plataformas em breve — separadas no card de futuros
      if (srcSoon)  srcSoon.appendChild(makeSoonChip(key, p));
      if (destSoon) destSoon.appendChild(makeSoonChip(key, p));
    } else {
      const srcDisabled = !p.can_read;
      const dstDisabled = !p.can_write;
      srcGrid.appendChild(makePlatformCard(key, p, 'src', srcDisabled));
      destGrid.appendChild(makePlatformCard(key, p, 'dest', dstDisabled));
    }
  });
}

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

  if (role === 'src') {
    state.srcPlatform = key;
    if (state.destPlatform === key) { state.destPlatform = null; document.getElementById(`dest-${key}`)?.classList.remove('selected'); }
  } else {
    state.destPlatform = key;
    if (state.srcPlatform === key) { state.srcPlatform = null; document.getElementById(`src-${key}`)?.classList.remove('selected'); }
  }

  document.getElementById(`${role}-${key}`)?.classList.add('selected');

  const canContinue = state.srcPlatform && state.destPlatform && state.srcPlatform !== state.destPlatform;
  document.getElementById('btn-step1-next').disabled = !canContinue;
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

function renderConnectForms() {
  const p = state.platforms;
  document.getElementById('src-connect-title').textContent =
    `📤 Sua conta de origem — ${p[state.srcPlatform]?.name || ''}`;
  document.getElementById('dest-connect-title').textContent =
    `📥 Sua conta de destino — ${p[state.destPlatform]?.name || ''}`;

  renderConnectForm(state.srcPlatform,  'src');
  renderConnectForm(state.destPlatform, 'dest');
}

function renderConnectForm(platform, role) {
  const container = document.getElementById(`${role}-connect-form`);
  if (!container) return;
  container.innerHTML = '';

  const sid  = role === 'src' ? state.srcSid  : state.destSid;
  const name = role === 'src' ? state.srcDisplayName : state.destDisplayName;

  if (sid) {
    container.appendChild(makeConnectionStatus(platform, role, name || 'Conectado'));
    return;
  }

  switch (platform) {
    case 'spotify':    container.appendChild(makeOAuthForm('spotify', role, '#1DB954')); break;
    case 'deezer':     container.appendChild(makeOAuthForm('deezer',  role, '#FF0092')); break;
    case 'youtube':    container.appendChild(makeYoutubeForm(role)); break;
    case 'soundcloud': container.appendChild(makeSoundcloudForm(role)); break;
    default:
      container.innerHTML = `<p style="color:var(--color-muted);font-size:0.85rem;">
        ${state.platforms[platform]?.name || platform} chegando em breve!</p>`;
  }
}

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
    <button class="btn-disconnect" onclick="disconnect('${role}')">Desconectar</button>
  `;
  return div;
}

// ── OAuth Form (Spotify / Deezer) ──────────────────────────
function makeOAuthForm(platform, role, color) {
  const p = state.platforms[platform] || {};
  const configured = p.oauth_configured;
  const names = { spotify: 'Spotify', deezer: 'Deezer' };
  const name = names[platform] || platform;

  const div = document.createElement('div');

  if (!configured) {
    // OAuth não configurado ainda — orienta o dono do app
    div.innerHTML = `
      <div class="oauth-config-notice">
        <div class="oauth-icon" style="background:${color}20;color:${color};">
          ${PLATFORM_ICONS[platform]}
        </div>
        <div>
          <div style="font-weight:700;margin-bottom:4px;font-size:0.9rem;">Configure o ${name} OAuth</div>
          <div style="font-size:0.78rem;color:var(--color-muted);line-height:1.6;">
            Para ativar o login com ${name}, adicione as credenciais no arquivo <code>.env</code>.<br>
            ${platform === 'spotify'
              ? 'Acesse <a href="https://developer.spotify.com/dashboard" target="_blank">developer.spotify.com/dashboard</a>, crie um app e copie o Client ID e Client Secret.'
              : 'Acesse <a href="https://developers.deezer.com/myapps" target="_blank">developers.deezer.com/myapps</a>, crie um app e copie o App ID e Secret Key.'
            }
          </div>
        </div>
      </div>
    `;
  } else {
    div.innerHTML = `
      <button class="btn-oauth" style="--oauth-color:${color};" onclick="openOAuthPopup('${platform}','${role}')">
        <span class="btn-oauth-icon">${PLATFORM_ICONS[platform]}</span>
        Entrar com ${name}
        <span class="btn-oauth-arrow">→</span>
      </button>
      <div class="oauth-privacy-note">
        🔒 Você será redirecionado ao site oficial do ${name}. Não armazenamos sua senha.
      </div>
    `;
  }
  return div;
}

// ── YouTube Music Form ─────────────────────────────────────
function makeYoutubeForm(role) {
  const div = document.createElement('div');
  div.innerHTML = `
    <div class="ytm-guide">
      <div class="ytm-guide-header">
        ${PLATFORM_ICONS.youtube}
        <div>
          <div style="font-weight:700;font-size:0.95rem;">Como conectar o YouTube Music</div>
          <div style="font-size:0.75rem;color:var(--color-muted);">Leva menos de 1 minuto</div>
        </div>
      </div>

      <div class="ytm-steps">
        <div class="ytm-step">
          <div class="ytm-step-num">1</div>
          <div class="ytm-step-text">
            Abra o <a href="https://music.youtube.com" target="_blank">YouTube Music</a> e faça login na sua conta Google.
          </div>
        </div>
        <div class="ytm-step">
          <div class="ytm-step-num">2</div>
          <div class="ytm-step-text">
            Pressione <kbd>F12</kbd> para abrir o Console do navegador.
          </div>
        </div>
        <div class="ytm-step">
          <div class="ytm-step-num">3</div>
          <div class="ytm-step-text">
            Clique na aba <strong>Network</strong> (Rede) e recarregue a página (<kbd>F5</kbd>).
          </div>
        </div>
        <div class="ytm-step">
          <div class="ytm-step-num">4</div>
          <div class="ytm-step-text">
            Na lista que aparecer, clique em qualquer item chamado <code>browse</code>.
          </div>
        </div>
        <div class="ytm-step">
          <div class="ytm-step-num">5</div>
          <div class="ytm-step-text">
            Clique com o botão direito → <strong>Copy</strong> → <strong>Copy as cURL (bash)</strong> e cole abaixo.
          </div>
        </div>
      </div>
    </div>

    <div class="form-group" style="margin-top:16px;">
      <label class="form-label" for="${role}-ytm-curl">Cole o texto copiado aqui:</label>
      <textarea id="${role}-ytm-curl" class="form-input form-textarea"
                placeholder="curl 'https://music.youtube.com/...' -H 'cookie: ...'"></textarea>
    </div>
    <button class="btn btn-secondary btn-sm" onclick="connectYoutube('${role}')">
      Confirmar conexão →
    </button>
    <div id="${role}-ytm-status" style="margin-top:10px;font-size:0.8rem;color:var(--color-muted);"></div>
  `;
  return div;
}

// ── SoundCloud ─────────────────────────────────────────────
function makeSoundcloudForm(role) {
  const div = document.createElement('div');
  div.innerHTML = `
    <div class="soundcloud-auto-connect">
      ${PLATFORM_ICONS.soundcloud}
      <div>
        <div style="font-weight:700;margin-bottom:4px;">SoundCloud — sem login necessário</div>
        <div style="font-size:0.8rem;color:var(--color-muted);">
          Playlists públicas do SoundCloud funcionam sem autenticação.
        </div>
      </div>
      <button class="btn btn-secondary btn-sm" onclick="connectSoundcloud('${role}')">Usar SoundCloud</button>
    </div>
    <div id="${role}-sc-status" style="margin-top:8px;font-size:0.8rem;color:var(--color-muted);"></div>
  `;
  return div;
}

// ── Connect handlers ───────────────────────────────────────
async function connectYoutube(role) {
  const headers = document.getElementById(`${role}-ytm-curl`)?.value?.trim();
  if (!headers) { showToast('Cole o texto cURL do YouTube Music', 'warn'); return; }
  const status = document.getElementById(`${role}-ytm-status`);
  status.innerHTML = '<span class="spin-inline"></span> Verificando...';
  try {
    const r = await fetch('/api/connect/youtube', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ headers_raw: headers }),
    });
    const d = await r.json();
    if (d.ok) {
      if (role === 'src') { state.srcSid = d.sid; state.srcDisplayName = d.display_name; }
      else { state.destSid = d.sid; state.destDisplayName = d.display_name; }
      showToast(`YouTube Music conectado!`, 'success');
      renderConnectForms();
      checkTransferReady();
    } else {
      status.innerHTML = `❌ ${d.error}`;
      showToast(d.error, 'error');
    }
  } catch { status.innerHTML = '❌ Erro de rede'; }
}

async function connectSoundcloud(role) {
  const status = document.getElementById(`${role}-sc-status`);
  if (status) status.innerHTML = '<span class="spin-inline"></span>';
  try {
    const r = await fetch('/api/connect/soundcloud', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}',
    });
    const d = await r.json();
    if (d.ok) {
      if (role === 'src') { state.srcSid = d.sid; state.srcDisplayName = 'SoundCloud'; }
      else { state.destSid = d.sid; state.destDisplayName = 'SoundCloud'; }
      showToast('SoundCloud pronto!', 'success');
      renderConnectForms();
      checkTransferReady();
    } else {
      showToast(d.error, 'error');
    }
  } catch { showToast('Erro ao conectar SoundCloud', 'error'); }
}

function disconnect(role) {
  if (role === 'src') { state.srcSid = null; state.srcDisplayName = null; }
  else { state.destSid = null; state.destDisplayName = null; }
  renderConnectForms();
  checkTransferReady();
}

// ── URL hint ───────────────────────────────────────────────
function updateUrlHint() {
  const hints = {
    spotify:    'Ex.: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M',
    deezer:     'Ex.: https://www.deezer.com/br/playlist/1234567890',
    youtube:    'Ex.: https://music.youtube.com/playlist?list=PLxxxxxx',
    soundcloud: 'Ex.: https://soundcloud.com/usuario/sets/nome-da-playlist',
    apple:      'Ex.: https://music.apple.com/br/playlist/nome/pl.xxxxxx',
  };
  const el = document.getElementById('url-hint');
  if (el) el.textContent = hints[state.srcPlatform] || 'Cole o link completo da playlist.';
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

function checkTransferReady() {
  const url = document.getElementById('playlist-url')?.value?.trim();
  const srcOk  = !!state.srcSid;
  const destOk = !!state.destSid;
  const urlOk  = !!url;
  const btn = document.getElementById('btn-transfer');
  if (btn) btn.disabled = !(srcOk && destOk && urlOk);
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

function handleTransferError(ev) {
  clearInterval(state.pollTimer);
  document.getElementById('progress-status').textContent = `Erro: ${ev.message}`;
  showToast(`Erro: ${ev.message}`, 'error');
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
function showToast(msg, type = 'info') {
  const icons = { success: '✅', error: '❌', warn: '⚠️', info: 'ℹ️' };
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<div class="toast-icon">${icons[type]}</div><div class="toast-msg">${escapeHtml(msg)}</div>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
