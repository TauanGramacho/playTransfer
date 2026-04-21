import ctypes
import json
import re
import threading
import time

import webview


WINDOW_TITLE = "Login Spotify - PlayTransfer"
LOGIN_URL = "https://open.spotify.com/"
SPOTIFY_CAPTURE_JS = r"""
(function() {
  function remember(token, source) {
    token = String(token || '').trim();
    if (!token || token.length < 40) return false;
    if (/[\s{}()[\]"']/.test(token)) return false;
    window.__ptSpotifyToken = JSON.stringify({
      accessToken: token,
      source: source || 'spotify-web',
      clientToken: window.__ptSpotifyClientToken || ''
    });
    return true;
  }

  function rememberClientToken(token, source) {
    token = String(token || '').trim();
    if (!token || token.length < 20) return false;
    if (/[\s{}()[\]"']/.test(token)) return false;
    window.__ptSpotifyClientToken = token;
    if (window.__ptSpotifyToken) {
      try {
        var payload = JSON.parse(window.__ptSpotifyToken);
        payload.clientToken = token;
        payload.clientTokenSource = source || 'spotify-web';
        window.__ptSpotifyToken = JSON.stringify(payload);
      } catch (e) {}
    }
    return true;
  }

  function consider(value, source) {
    var text = String(value || '');
    if (!text) return false;

    var direct = text.match(/\b(BQ[A-Za-z0-9_-]{40,})\b/);
    if (direct && remember(direct[1], source)) return true;

    var named = text.match(/["']?(?:accessToken|access_token|wp_access_token)["']?\s*[:=]\s*["']?([A-Za-z0-9._-]{40,})/i);
    if (named && remember(named[1], source)) return true;

    var clientNamed = text.match(/["']?(?:clientToken|client_token|client-token)["']?\s*[:=]\s*["']?([A-Za-z0-9._:-]{20,})/i);
    if (clientNamed) rememberClientToken(clientNamed[1], source + ':client-token');

    return false;
  }

  function walk(value, source, depth) {
    if (depth > 4 || value == null || window.__ptSpotifyToken) return;
    if (typeof value === 'string') {
      consider(value, source);
      if (value.length < 250000 && /^[\[{]/.test(value.trim())) {
        try { walk(JSON.parse(value), source + ':json', depth + 1); } catch (e) {}
      }
      return;
    }
    if (typeof value !== 'object') return;

    if (Array.isArray(value)) {
      for (var i = 0; i < value.length && i < 80 && !window.__ptSpotifyToken; i++) {
        walk(value[i], source + '[' + i + ']', depth + 1);
      }
      return;
    }

    var count = 0;
    Object.keys(value).forEach(function(key) {
      if (window.__ptSpotifyToken || count++ > 120) return;
      var nested;
      try { nested = value[key]; } catch (e) { return; }
      var lowered = String(key || '').toLowerCase();
      if ((lowered.indexOf('token') !== -1 || lowered.indexOf('auth') !== -1) && typeof nested === 'string') {
        consider(nested, source + ':' + key);
      }
      walk(nested, source + ':' + key, depth + 1);
    });
  }

  function scanStorage(name) {
    try {
      var storage = window[name];
      for (var i = 0; storage && i < storage.length && !window.__ptSpotifyToken; i++) {
        var key = storage.key(i);
        var value = storage.getItem(key);
        consider(key + '=' + value, name + ':' + key);
        walk(value, name + ':' + key, 0);
      }
    } catch (e) {}
  }

  function getHeader(headers, name) {
    if (!headers) return '';
    try {
      if (typeof Headers !== 'undefined' && headers instanceof Headers) return headers.get(name) || '';
      if (Array.isArray(headers)) {
        for (var i = 0; i < headers.length; i++) {
          if (String(headers[i][0] || '').toLowerCase() === name.toLowerCase()) return headers[i][1] || '';
        }
      }
      return headers[name] || headers[name.toLowerCase()] || '';
    } catch (e) {
      return '';
    }
  }

  function considerAuthHeader(headers, source) {
    var auth = String(getHeader(headers, 'authorization') || '');
    var match = auth.match(/^Bearer\s+(.+)$/i);
    if (match) remember(match[1], source);
  }

  function considerClientTokenHeader(headers, source) {
    rememberClientToken(getHeader(headers, 'client-token') || getHeader(headers, 'x-spotify-client-token'), source);
  }

  if (!window.__ptSpotifyHooksInstalled) {
    window.__ptSpotifyHooksInstalled = true;

    try {
      var originalFetch = window.fetch;
      if (typeof originalFetch === 'function') {
        window.fetch = function(input, init) {
          try {
            considerAuthHeader(init && init.headers, 'fetch:init');
            considerAuthHeader(input && input.headers, 'fetch:request');
            considerClientTokenHeader(init && init.headers, 'fetch:init');
            considerClientTokenHeader(input && input.headers, 'fetch:request');
          } catch (e) {}
          return originalFetch.apply(this, arguments).then(function(response) {
            try {
              var url = String(response && response.url || '');
              if (url.indexOf('/api/token') !== -1 || url.indexOf('api.spotify.com') !== -1) {
                response.clone().text().then(function(text) {
                  consider(text, 'fetch:response:' + url);
                  walk(text, 'fetch:response:' + url, 0);
                }).catch(function() {});
              }
            } catch (e) {}
            return response;
          });
        };
      }
    } catch (e) {}

    try {
      var originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
      XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
        try {
          if (String(name || '').toLowerCase() === 'authorization') {
            considerAuthHeader({ authorization: value }, 'xhr:header');
          } else if (String(name || '').toLowerCase() === 'client-token') {
            rememberClientToken(value, 'xhr:header');
          }
        } catch (e) {}
        return originalSetRequestHeader.apply(this, arguments);
      };
    } catch (e) {}
  }

  scanStorage('localStorage');
  scanStorage('sessionStorage');
  walk(window.__NEXT_DATA__, 'window.__NEXT_DATA__', 0);

  try {
    fetch('/api/token', { credentials: 'include', headers: { accept: 'application/json' } })
      .then(function(response) { return response.text(); })
      .then(function(text) {
        consider(text, 'open.spotify.com/api/token');
        walk(text, 'open.spotify.com/api/token', 0);
      })
      .catch(function() {});
  } catch (e) {}

  if (!window.__ptSpotifyIndexedDbScanStarted && window.indexedDB && indexedDB.databases) {
    window.__ptSpotifyIndexedDbScanStarted = true;
    try {
      indexedDB.databases().then(function(databases) {
        (databases || []).slice(0, 12).forEach(function(info) {
          if (!info || !info.name || window.__ptSpotifyToken) return;
          var request = indexedDB.open(info.name);
          request.onsuccess = function() {
            var db = request.result;
            try {
              Array.prototype.slice.call(db.objectStoreNames || []).slice(0, 24).forEach(function(storeName) {
                if (window.__ptSpotifyToken) return;
                try {
                  var tx = db.transaction(storeName, 'readonly');
                  var store = tx.objectStore(storeName);
                  var getAll = store.getAll ? store.getAll() : null;
                  if (getAll) {
                    getAll.onsuccess = function() {
                      walk(getAll.result, 'indexedDB:' + info.name + ':' + storeName, 0);
                    };
                  }
                } catch (e) {}
              });
            } catch (e) {}
          };
        });
      }).catch(function() {});
    } catch (e) {}
  }

  return window.__ptSpotifyToken || '';
})();
"""


def _bring_window_to_front(title):
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False

    SW_RESTORE = 9
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_SHOWWINDOW = 0x0040

    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetForegroundWindow(hwnd)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    return True


def _extract_sp_dc(cookie_text):
    if not cookie_text:
        return ""
    match = re.search(r"(?:^|;\s*)sp_dc=([^;]+)", str(cookie_text))
    return (match.group(1).strip() if match else "")


def _remember_cookie_header(shared, cookie_text):
    raw = str(cookie_text or "").strip()
    if not raw:
        return

    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()

    sp_dc = _extract_sp_dc(raw)
    if sp_dc and not shared["sp_dc"]:
        shared["sp_dc"] = sp_dc
    if sp_dc and not shared["cookie_header"]:
        shared["cookie_header"] = raw
    _remember_access_token(shared, raw)


def _extract_from_cookie_objects(shared, cookies):
    for cookie in cookies or []:
        try:
            name = str(getattr(cookie, "name", "") or "").strip()
            value = str(getattr(cookie, "value", "") or "").strip()
            domain = str(getattr(cookie, "domain", "") or "").lower()
            if not name or not value or "spotify.com" not in domain:
                continue

            _remember_cookie_header(shared, f"{name}={value}")
            if "token" in name.lower():
                _remember_access_token(shared, value)
            if name == "sp_dc" and not shared["sp_dc"]:
                shared["sp_dc"] = value

            if hasattr(cookie, "output"):
                _remember_cookie_header(shared, cookie.output())
        except Exception:
            continue


def _remember_access_token(shared, token_payload):
    if not token_payload:
        return

    _remember_client_token(shared, token_payload)

    payload = token_payload
    if isinstance(payload, str):
        direct_token = _extract_access_token_from_text(payload)
        if direct_token and not shared["access_token"]:
            shared["access_token"] = direct_token
            return
        try:
            payload = json.loads(payload)
        except Exception:
            return

    if isinstance(payload, (list, tuple)):
        for value in payload:
            if shared["client_token"]:
                return
            _remember_client_token(shared, value)
        return

    if not isinstance(payload, dict):
        return

    if payload.get("isAnonymous") is True:
        return

    for key in ("candidates", "tokens"):
        for candidate in payload.get(key) or []:
            _remember_access_token(shared, candidate)
            if shared["access_token"]:
                return

    token = str(payload.get("accessToken") or payload.get("access_token") or "").strip()
    if token and not shared["access_token"]:
        shared["access_token"] = token
        shared["expires_at"] = payload.get("accessTokenExpirationTimestampMs") or payload.get("expires_at") or ""


def _remember_client_token(shared, token_payload):
    if not token_payload:
        return

    payload = token_payload
    if isinstance(payload, str):
        raw = payload.strip()
        for pattern in (
            r"[\"']?(?:clientToken|client_token|client-token)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9._:-]{20,})",
            r"(?:^|\n|\r|;|\s)client-token\s*[:=]\s*([A-Za-z0-9._:-]{20,})",
        ):
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                token = match.group(1).strip().strip("\"'")
                if token and not re.search(r"\s", token):
                    shared["client_token"] = token
                    return
        try:
            payload = json.loads(raw)
        except Exception:
            return

    if not isinstance(payload, dict):
        return

    token = str(
        payload.get("clientToken")
        or payload.get("client_token")
        or payload.get("client-token")
        or ""
    ).strip()
    if token and not shared["client_token"]:
        shared["client_token"] = token
        return

    for value in payload.values():
        if shared["client_token"]:
            return
        if isinstance(value, (dict, list, tuple)):
            _remember_client_token(shared, value)

def _extract_access_token_from_text(value):
    raw = str(value or "")
    if not raw:
        return ""

    patterns = (
        r"\b(BQ[A-Za-z0-9_-]{40,})\b",
        r"[\"']?(?:accessToken|access_token|wp_access_token)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9._-]{40,})",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            token = match.group(1).strip().strip("\"'")
            if token and not re.search(r"\s", token):
                return token
    return ""


def check_cookies(window):
    shared = {
        "access_token": "",
        "client_token": "",
        "expires_at": "",
        "sp_dc": "",
        "cookie_header": "",
        "last_url": "",
        "closed": False,
    }

    def remember_url():
        try:
            shared["last_url"] = window.get_current_url() or shared["last_url"]
        except Exception:
            pass

    def on_request(request):
        headers = getattr(request, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() in ("client-token", "x-spotify-client-token"):
                _remember_client_token(shared, f"client-token: {value}")
            if str(name).lower() == "cookie":
                _remember_cookie_header(shared, value)

    def on_response(response):
        headers = getattr(response, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() == "set-cookie":
                _remember_cookie_header(shared, value)

    def on_loaded():
        remember_url()

    def on_closed():
        shared["closed"] = True

    def on_shown():
        def focus_later():
            time.sleep(0.4)
            try:
                window.restore()
            except Exception:
                pass
            try:
                window.on_top = True
            except Exception:
                pass
            try:
                _bring_window_to_front(WINDOW_TITLE)
            except Exception:
                pass

        threading.Thread(target=focus_later, daemon=True).start()

    window.events.request_sent += on_request
    window.events.response_received += on_response
    window.events.loaded += on_loaded
    window.events.closed += on_closed
    window.events.shown += on_shown

    token_found_at = None

    for _ in range(120):
        remember_url()

        try:
            page_text = str(window.evaluate_js("document.body ? document.body.innerText : ''") or "").lower()
            if "no healthy upstream" in page_text:
                window.load_url("https://open.spotify.com/")
                time.sleep(2)
                continue
        except Exception:
            pass

        if not shared["access_token"] and "open.spotify.com" in shared["last_url"]:
            try:
                token_payload = window.evaluate_js(SPOTIFY_CAPTURE_JS)
                _remember_access_token(shared, token_payload)
            except Exception:
                pass

        if not shared["sp_dc"]:
            try:
                cookies = window.get_cookies()
                _extract_from_cookie_objects(shared, cookies)
            except Exception:
                pass

        if not shared["sp_dc"]:
            try:
                _remember_cookie_header(shared, window.evaluate_js("document.cookie"))
            except Exception:
                pass

        if shared["access_token"]:
            if token_found_at is None:
                token_found_at = time.time()

            if not shared["client_token"] and time.time() - token_found_at < 5:
                time.sleep(1)
                continue

            print(
                "SPOTIFY_FOUND:"
                + json.dumps(
                    {
                        "access_token": shared["access_token"],
                        "client_token": shared["client_token"],
                        "expires_at": shared["expires_at"],
                        "sp_dc": shared["sp_dc"],
                        "cookie_header": shared["cookie_header"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            try:
                window.destroy()
            except Exception:
                pass
            return

        if shared["closed"]:
            print(f"SPOTIFY_ABORTED:{shared['last_url']}", flush=True)
            return

        time.sleep(1)

    print(f"SPOTIFY_TIMEOUT:{shared['last_url']}", flush=True)
    try:
        window.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    window = webview.create_window(
        title=WINDOW_TITLE,
        url=LOGIN_URL,
        width=460,
        height=680,
        resizable=False,
        on_top=True,
        focus=True,
    )
    webview.start(check_cookies, window, private_mode=False)
