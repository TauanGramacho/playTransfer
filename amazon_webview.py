"""
amazon_webview.py - PlayTransfer
Abre music.amazon.com, captura cookies de sessão (at-main via request_sent,
igual ao Deezer com ARL) E intercepta chamadas de API reais do player
para descobrir os endpoints corretos.
"""
import ctypes
import json
import re
import threading
import time

import webview

WINDOW_TITLE = "Login Amazon Music - PlayTransfer"
START_URL    = "https://music.amazon.com/"
TARGET = {
    "at-main", "ubid-main", "sess-at-main", "x-main",
    "session-id", "session-id-time", "session-token",
    "csrf-main", "lc-main", "i18n-prefs", "sp-cdn",
}
COOKIE_PREFIXES = ("at-", "sess-at-", "ubid-", "x-", "csrf-", "lc-")


def _should_keep_cookie(name):
    name = str(name or "").strip()
    return name in TARGET or name.startswith(COOKIE_PREFIXES)


def _has_auth_cookie(store):
    return any(str(name).startswith("at-") for name, value in store.items() if value)


def _has_ubid_cookie(store):
    return any(str(name).startswith("ubid-") for name, value in store.items() if value)


def _is_relevant_api(url):
    url = str(url or "")
    return (
        "/EU/" in url
        or "/NA/" in url
        or "/FE/" in url
        or "/v1/" in url
        or "/api/" in url
        or "graphql" in url
        or "gql.music.amazon.dev" in url
        or "web.skill.music.a2z.com" in url
        or "mesk.skill.music.a2z.com" in url
        or "api.music.amazon.dev" in url
    )


# JS injetado para interceptar fetch/XHR e capturar endpoints reais
INTERCEPT_JS = r"""
(function() {
  if (window._amzIntercepted) return;
  window._amzIntercepted = true;
  window._amzApiCalls = [];

  function isRelevantAmazonApi(url) {
    return !!url && (
      url.includes('/EU/') ||
      url.includes('/NA/') ||
      url.includes('/FE/') ||
      url.includes('/v1/') ||
      url.includes('/api/') ||
      url.includes('graphql') ||
      url.includes('gql.music.amazon.dev') ||
      url.includes('web.skill.music.a2z.com') ||
      url.includes('mesk.skill.music.a2z.com') ||
      url.includes('api.music.amazon.dev')
    );
  }

  function safeBody(body) {
    if (!body) return null;
    var text = String(body);
    if (text.includes('accessToken') || text.includes('x-amzn-authentication') || text.includes('Authorization')) {
      return '[redacted amazon auth body]';
    }
    return text.substring(0, 600);
  }

  async function captureAmazonConfig() {
    try {
      var cfg = (window.amznMusic && window.amznMusic.appConfig) || null;
      if (!cfg && location.hostname.indexOf('music.amazon') >= 0) {
        var response = await fetch('/config.json', { credentials: 'include', cache: 'no-store' });
        if (response && response.ok) cfg = await response.json();
      }
      if (cfg) window._amzConfig = cfg;
    } catch (e) {}
  }
  captureAmazonConfig();
  setTimeout(captureAmazonConfig, 800);
  setTimeout(captureAmazonConfig, 2000);

  // Intercepta fetch
  var origFetch = window.fetch;
  window.fetch = function(resource, init) {
    var url = (typeof resource === 'string') ? resource : (resource && resource.url) || '';
    if (isRelevantAmazonApi(url)) {
      window._amzApiCalls.push({
        method: (init && init.method) || 'GET',
        url: url,
        body: (init && init.body) ? safeBody(init.body) : null
      });
      if (window._amzApiCalls.length > 50) window._amzApiCalls = window._amzApiCalls.slice(-50);
    }
    return origFetch.apply(this, arguments);
  };

  // Intercepta XHR
  var origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url) {
    if (isRelevantAmazonApi(url)) {
      window._amzApiCalls.push({ method: method, url: url, body: null });
      if (window._amzApiCalls.length > 50) window._amzApiCalls = window._amzApiCalls.slice(-50);
    }
    return origOpen.apply(this, arguments);
  };
})();
"""

def _bring_window_to_front(title):
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return
        SW_RESTORE = 9; HWND_TOPMOST = -1; HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002; SWP_NOSIZE = 0x0001; SWP_SHOWWINDOW = 0x0040
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetWindowPos(hwnd, HWND_TOPMOST,   0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.SetForegroundWindow(hwnd)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    except Exception:
        pass

def _parse_cookie_header(header_value, store):
    try:
        for part in str(header_value).split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                name = name.strip(); value = value.strip()
                if _should_keep_cookie(name) and value:
                    store[name] = value
    except Exception:
        pass


def _merge_app_config(config, store):
    if not isinstance(config, dict):
        return
    csrf = config.get("csrf") if isinstance(config.get("csrf"), dict) else {}
    mapping = {
        "_access_token": config.get("accessToken"),
        "_customer_id": config.get("customerId"),
        "_device_type": config.get("deviceType"),
        "_device_id": config.get("deviceId"),
        "_marketplace_id": config.get("marketplaceId"),
        "_music_territory": config.get("musicTerritory"),
        "_site_region": config.get("siteRegion"),
        "_session_id": config.get("sessionId"),
        "_display_language": config.get("displayLanguage"),
        "_application_version": config.get("version"),
        "_csrf_token": csrf.get("token"),
        "_csrf_rnd": csrf.get("rnd"),
        "_csrf_ts": csrf.get("ts"),
    }
    for key, value in mapping.items():
        if value:
            store[key] = str(value)


def _capture_app_config(window, store):
    try:
        raw = window.evaluate_js("JSON.stringify(window._amzConfig || null)") or ""
        if raw and raw != "null":
            _merge_app_config(json.loads(raw), store)
    except Exception:
        pass


def check_session(window):
    shared = {
        "cookies":   {},
        "api_calls": [],
        "last_url":  "",
        "closed":    False,
        "triggered": False,
    }

    def on_request(request):
        headers = getattr(request, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() == "cookie":
                _parse_cookie_header(value, shared["cookies"])
            # Captura também a URL do request para descobrir endpoints
        try:
            url = getattr(request, "url", "") or ""
            if _is_relevant_api(url):
                method = getattr(request, "method", "GET") or "GET"
                entry = {"method": method, "url": url}
                if entry not in shared["api_calls"]:
                    shared["api_calls"].append(entry)
                    if len(shared["api_calls"]) > 50:
                        shared["api_calls"] = shared["api_calls"][-50:]
        except Exception:
            pass

    def on_response(response):
        headers = getattr(response, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() == "set-cookie":
                _parse_cookie_header(value, shared["cookies"])

    def on_loaded():
        try:
            url = window.get_current_url() or ""
            if url:
                shared["last_url"] = url
        except Exception:
            pass
        # Injeta interceptor
        try:
            window.evaluate_js(INTERCEPT_JS)
        except Exception:
            pass
        # Tenta document.cookie
        try:
            _parse_cookie_header(window.evaluate_js("document.cookie") or "", shared["cookies"])
        except Exception:
            pass
        # Tenta get_cookies()
        try:
            for ck in (window.get_cookies() or []):
                nm = str(getattr(ck, "name", None) or "").strip()
                vl = str(getattr(ck, "value", None) or "").strip()
                if _should_keep_cookie(nm) and vl:
                    shared["cookies"][nm] = vl
        except Exception:
            pass
        _capture_app_config(window, shared["cookies"])

    def on_closed():
        shared["closed"] = True

    def on_shown():
        def focus_later():
            time.sleep(0.4)
            try: window.restore()
            except Exception: pass
            _bring_window_to_front(WINDOW_TITLE)
        threading.Thread(target=focus_later, daemon=True).start()

    window.events.request_sent      += on_request
    window.events.response_received += on_response
    window.events.loaded            += on_loaded
    window.events.closed            += on_closed
    window.events.shown             += on_shown

    at_main_seen_at = None
    for _ in range(180):
        if shared["closed"]:
            print(f"AMAZON_SESSION_ABORTED:{shared['last_url']}", flush=True)
            return

        c   = shared["cookies"]
        url = shared["last_url"].lower()

        # Polling: get_cookies + document.cookie
        try:
            for ck in (window.get_cookies() or []):
                nm = str(getattr(ck, "name", None) or "").strip()
                vl = str(getattr(ck, "value", None) or "").strip()
                if _should_keep_cookie(nm) and vl:
                    c[nm] = vl
        except Exception:
            pass
        try:
            _parse_cookie_header(window.evaluate_js("document.cookie") or "", c)
        except Exception:
            pass
        _capture_app_config(window, c)

        # Coleta API calls interceptados
        try:
            calls_json = window.evaluate_js("JSON.stringify(window._amzApiCalls || [])")
            if calls_json:
                calls = json.loads(calls_json)
                for call in calls:
                    if call not in shared["api_calls"]:
                        shared["api_calls"].append(call)
        except Exception:
            pass

        not_login = (
            "ap/signin" not in url and "ap/mfa" not in url
            and "accounts.amazon" not in url and url != ""
        )

        # Se logado mas sem at-main → navega para amazon.com para forçar request
        if not_login and _has_ubid_cookie(c) and not _has_auth_cookie(c) and not shared["triggered"]:
            shared["triggered"] = True
            try:
                window.evaluate_js("window.location.href='https://www.amazon.com/';")
            except Exception:
                pass

        if _has_auth_cookie(c):
            if at_main_seen_at is None:
                at_main_seen_at = time.time()
            if "music.amazon" not in url and not shared.get("music_triggered"):
                shared["music_triggered"] = True
                try:
                    window.evaluate_js("window.location.href='https://music.amazon.com/my/playlists';")
                except Exception:
                    pass
                time.sleep(1)
                continue

            if not c.get("_access_token") and time.time() - at_main_seen_at < 35:
                time.sleep(1)
                continue

            try:
                host = window.evaluate_js("window.location.hostname") or "music.amazon.com"
            except Exception:
                host = "music.amazon.com"
            m = re.search(r"amazon\.(\w+(?:\.\w+)?)$", str(host))
            region = m.group(1) if m else "com"
            c["_region"]    = region
            c["_api_calls"] = json.dumps(shared["api_calls"])

            print("AMAZON_SESSION_FOUND:" + json.dumps(c, ensure_ascii=False), flush=True)
            try: window.destroy()
            except Exception: pass
            return

        time.sleep(1)

    print(f"AMAZON_SESSION_TIMEOUT:{shared['last_url']}", flush=True)
    try: window.destroy()
    except Exception: pass


if __name__ == "__main__":
    window = webview.create_window(
        title=WINDOW_TITLE,
        url=START_URL,
        width=480,
        height=680,
        resizable=False,
        on_top=True,
        focus=True,
    )
    webview.start(check_session, window, private_mode=False)
