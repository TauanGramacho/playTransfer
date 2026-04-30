"""
Create or update a SoundCloud playlist from the logged-in pywebview profile.

The server-side cookie replay path is rejected by SoundCloud with HTTP 403.
This helper performs the write fetch inside a SoundCloud page, using the same
browser context where the user logged in through the guided window.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

import webview


WINDOW_TITLE = "SoundCloud Playlist - PlayTransfer"
START_URL = "https://soundcloud.com/you/library"
STORAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".runtime", "soundcloud-webview-profile")


def _load_payload() -> dict:
    if len(sys.argv) < 2:
        return {}
    with open(sys.argv[1], "r", encoding="utf-8") as fp:
        return json.load(fp)


def _js_worker(payload: dict) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return f"""
(function () {{
  if (window._ptSoundCloudPlaylistWorkerStarted) return;
  window._ptSoundCloudPlaylistWorkerStarted = true;

  const input = {payload_json};

  function send(result) {{
    try {{
      window.pywebview.api.finish(JSON.stringify(result));
    }} catch (error) {{}}
  }}

  function sleep(ms) {{
    return new Promise(resolve => setTimeout(resolve, ms));
  }}

  function readCookie(name) {{
    const wanted = String(name || '').toLowerCase();
    return String(document.cookie || '').split(';').map(x => x.trim()).reduce((found, part) => {{
      if (found || !part.includes('=')) return found;
      const [key, ...rest] = part.split('=');
      return key.trim().toLowerCase() === wanted ? rest.join('=').trim() : '';
    }}, '');
  }}

  function applyInputCookies() {{
    const raw = String(input.cookie_header || '').trim();
    if (!raw || window._ptSoundCloudInputCookiesApplied) return;
    window._ptSoundCloudInputCookiesApplied = true;
    for (const part of raw.split(';')) {{
      const cookie = String(part || '').trim();
      if (!cookie || !cookie.includes('=')) continue;
      const name = cookie.split('=', 1)[0].trim();
      if (!name || /^(path|domain|expires|max-age|secure|httponly|samesite)$/i.test(name)) continue;
      try {{
        document.cookie = `${{cookie}}; path=/; SameSite=None; Secure`;
      }} catch (error) {{}}
    }}
  }}

  function getSoundCloudConfig() {{
    let clientId = String(input.client_id || '').trim();
    let appVersion = String(input.app_version || '').trim();
    let authToken = String(input.access_token || '').trim();
    authToken = authToken.replace(/^(OAuth|Bearer)\\s+/i, '').trim();
    try {{
      if (!appVersion && window.__sc_version) appVersion = String(window.__sc_version || '');
      if (!authToken && window.__sc_env && window.__sc_env.oauth_token) authToken = String(window.__sc_env.oauth_token || '');
      const hydration = window.__sc_hydration || [];
      for (const item of hydration) {{
        if (!clientId && item && item.hydratable === 'apiClient' && item.data && item.data.id) {{
          clientId = String(item.data.id || '');
        }}
        if (!authToken && item && item.data && item.data.oauth_token) {{
          authToken = String(item.data.oauth_token || '');
        }}
      }}
      if (!clientId) {{
        const raw = JSON.stringify(hydration);
        const match = raw.match(/"apiClient".{{0,260}}"id"\\s*:\\s*"([a-zA-Z0-9]{{20,80}})"/);
        if (match) clientId = match[1];
      }}
      if (!authToken) {{
        const envRaw = JSON.stringify(window.__sc_env || hydration || {{}});
        const tokenMatch = envRaw.match(/"oauth_token"\\s*:\\s*"([^"]{{20,}})"/);
        if (tokenMatch) authToken = tokenMatch[1];
      }}
      if (!authToken) {{
        for (let i = 0; i < localStorage.length; i += 1) {{
          const key = localStorage.key(i) || '';
          const value = localStorage.getItem(key) || '';
          if (/oauth|token|auth/i.test(key + ' ' + value)) {{
            const match = value.match(/(?:OAuth\\s+)?([A-Za-z0-9._~+/=%:-]{{20,}})/);
            if (match) {{
              authToken = match[1];
              break;
            }}
          }}
        }}
      }}
    }} catch (error) {{}}
    return {{ clientId, appVersion, authToken }};
  }}

  async function waitForConfig() {{
    for (let i = 0; i < 35; i += 1) {{
      const config = getSoundCloudConfig();
      if (config.clientId) return config;
      await sleep(700);
    }}
    throw new Error('client_id do SoundCloud nao apareceu na pagina logada');
  }}

  function parseResponseText(text) {{
    let data = null;
    try {{ data = text ? JSON.parse(text) : null; }} catch (error) {{}}
    return {{ data, text: String(text || '').slice(0, 500) }};
  }}

  async function requestWithFetch(method, url, payload, config) {{
    const headers = {{
      'Accept': 'application/json, text/javascript, */*; q=0.01',
      'Content-Type': 'application/json'
    }};
    if (config.authToken) headers.Authorization = `OAuth ${{config.authToken}}`;
    const csrf = readCookie('csrf_token') || readCookie('sc_csrf_token') || readCookie('_csrf');
    if (csrf) headers['X-CSRF-Token'] = csrf;
    const response = await fetch(url, {{
      method,
      credentials: 'include',
      headers,
      body: payload === undefined ? undefined : JSON.stringify(payload)
    }});
    const parsed = parseResponseText(await response.text());
    return {{
      ok: response.ok,
      status: response.status,
      data: parsed.data,
      text: parsed.text
    }};
  }}

  function requestWithXhr(method, url, payload, config) {{
    return new Promise((resolve) => {{
      const xhr = new XMLHttpRequest();
      xhr.open(method, url, true);
      xhr.withCredentials = true;
      xhr.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');
      xhr.setRequestHeader('Content-Type', 'application/json');
      if (config.authToken) xhr.setRequestHeader('Authorization', `OAuth ${{config.authToken}}`);
      const csrf = readCookie('csrf_token') || readCookie('sc_csrf_token') || readCookie('_csrf');
      if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf);
      xhr.onload = function () {{
        const parsed = parseResponseText(xhr.responseText || '');
        resolve({{
          ok: xhr.status >= 200 && xhr.status < 300,
          status: xhr.status,
          data: parsed.data,
          text: parsed.text
        }});
      }};
      xhr.onerror = function () {{
        resolve({{ ok: false, status: 0, data: null, text: 'XHR network error' }});
      }};
      xhr.ontimeout = function () {{
        resolve({{ ok: false, status: 0, data: null, text: 'XHR timeout' }});
      }};
      xhr.timeout = 30000;
      xhr.send(payload === undefined ? undefined : JSON.stringify(payload));
    }});
  }}

  async function requestJson(method, path, payload, config) {{
    const params = new URLSearchParams({{ client_id: config.clientId }});
    if (config.appVersion) params.set('app_version', config.appVersion);
    const url = `https://api-v2.soundcloud.com${{path}}?${{params.toString()}}`;
    try {{
      return await requestWithFetch(method, url, payload, config);
    }} catch (fetchError) {{
      const xhrResult = await requestWithXhr(method, url, payload, config);
      if (xhrResult.ok || xhrResult.status) return xhrResult;
      return {{
        ok: false,
        status: 0,
        data: null,
        text: `${{String(fetchError && fetchError.message || fetchError || 'fetch falhou')}} | ${{xhrResult.text}} | href=${{location.href}} | token=${{config.authToken ? 'sim' : 'nao'}} | cookies=${{String(document.cookie || '').length}}`
      }};
    }}
  }}

  function playlistIdFrom(data) {{
    if (!data) return '';
    return String(data.id || (data.playlist && data.playlist.id) || '');
  }}

  function playlistUrlFrom(data, id) {{
    if (!data) return `https://soundcloud.com/you/sets/${{id}}`;
    return String(data.permalink_url || (data.playlist && data.playlist.permalink_url) || `https://soundcloud.com/you/sets/${{id}}`);
  }}

  async function main() {{
    applyInputCookies();
    const config = await waitForConfig();
    const title = String(input.name || 'PlayTransfer Playlist').trim() || 'PlayTransfer Playlist';
    const description = String(input.description || 'Transferida via PlayTransfer');
    const trackIds = (input.track_ids || []).map(x => Number(x)).filter(Boolean);
    const tracks = trackIds.map(id => ({{ id }}));
    const trackUrns = trackIds.map(id => `soundcloud:tracks:${{id}}`);

    // SoundCloud frequently rejects playlist creation when tracks are sent in
    // the POST payload. Create an empty playlist first, then update tracks.
    const createPayloads = [
      {{ playlist: {{ title, description, sharing: 'private', tracks: [] }} }},
      {{ title, description, sharing: 'private', tracks: [] }},
      {{ title, description, sharing: 'private', track_urns: [] }},
      {{ playlist: {{ title, description, sharing: 'private' }} }},
      {{ title, description, sharing: 'private' }}
    ];

    let created = null;
    const createErrors = [];
    for (const payload of createPayloads) {{
      const result = await requestJson('POST', '/playlists', payload, config);
      if (result.ok && playlistIdFrom(result.data)) {{
        created = result;
        break;
      }}
      createErrors.push(`POST /playlists HTTP ${{result.status}} ${{result.text || ''}}`);
    }}

    if (!created) {{
      throw new Error(createErrors.join(' | '));
    }}

    const playlistId = playlistIdFrom(created.data);

    if (trackIds.length) {{
      const updatePayloads = [
        ['PUT', `/playlists/${{playlistId}}`, {{ playlist: {{ tracks: trackIds }} }}],
        ['PATCH', `/playlists/${{playlistId}}`, {{ playlist: {{ tracks: trackIds }} }}],
        ['PUT', `/playlists/${{playlistId}}`, {{ playlist: {{ tracks }} }}],
        ['PATCH', `/playlists/${{playlistId}}`, {{ playlist: {{ tracks }} }}],
        ['PUT', `/playlists/${{playlistId}}`, {{ tracks }}],
        ['PATCH', `/playlists/${{playlistId}}`, {{ track_urns: trackUrns }}]
      ];
      const updateErrors = [];
      let updated = false;
      for (const [method, path, payload] of updatePayloads) {{
        const result = await requestJson(method, path, payload, config);
        if (result.ok) {{
          updated = true;
          break;
        }}
        updateErrors.push(`${{method}} ${{path}} HTTP ${{result.status}} ${{result.text || ''}}`);
      }}
      if (!updated) {{
        throw new Error(updateErrors.join(' | '));
      }}
    }}

    send({{
      ok: true,
      id: playlistId,
      url: playlistUrlFrom(created.data, playlistId)
    }});
  }}

  main().catch(error => send({{
    ok: false,
    error: String(error && error.message || error || 'erro desconhecido')
  }}));
}})();
"""


def main() -> None:
    os.makedirs(STORAGE_PATH, exist_ok=True)
    payload = _load_payload()
    done = threading.Event()
    result_holder = {"value": None}

    def finish(raw: str):
        try:
            result_holder["value"] = json.loads(raw)
        except Exception as exc:
            result_holder["value"] = {"ok": False, "error": f"resposta invalida: {exc}"}
        done.set()
        return True

    window = webview.create_window(
        title=WINDOW_TITLE,
        url=START_URL,
        width=520,
        height=720,
        resizable=True,
        on_top=False,
        focus=False,
    )

    def runner():
        try:
            window.expose(finish)
        except Exception:
            pass

        script = _js_worker(payload)
        deadline = time.time() + 115
        while not done.is_set() and time.time() < deadline:
            try:
                window.evaluate_js(script)
            except Exception:
                pass
            time.sleep(1)

        if not done.is_set():
            result_holder["value"] = {
                "ok": False,
                "error": "tempo esgotado aguardando a janela logada do SoundCloud",
            }
            done.set()

        try:
            window.destroy()
        except Exception:
            pass

    webview.start(runner, private_mode=False, storage_path=STORAGE_PATH)
    print("SC_PLAYLIST_RESULT:" + json.dumps(result_holder["value"] or {"ok": False, "error": "sem resposta"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
