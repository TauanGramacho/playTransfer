"""
soundcloud_webview.py - PlayTransfer
Abre soundcloud.com em janela nativa, captura oauth_token.

Estratégia para Google OAuth:
- Intercepta window.open() via JS puro (sem depender de pywebview.api)
- Usa window.sessionStorage para passar a URL ao Python via polling
- Assim evita o problema de pywebview.api não estar pronto no clique
"""
import ctypes
import json
import os
import re
import sys
import threading
import time
from urllib.parse import unquote

import requests
import webview

WINDOW_TITLE = "Login SoundCloud - PlayTransfer"
START_URL    = "https://soundcloud.com/signin"
STORAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".runtime", "soundcloud-webview-profile")
ROLE = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()

TOKEN_COOKIE_NAMES = {"oauth_token", "soundcloud_oauth_token", "sc_oauth_token"}
SC_TOKEN_RE = re.compile(r"\b([0-9]+-[0-9]+-[0-9]+-[A-Za-z0-9]{8,})\b")
NAMED_TOKEN_RE = re.compile(
    r"(?:oauth_token|access_token|oauthToken|accessToken)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9._~+/=%:-]{20,})",
    re.I,
)
AUTH_TOKEN_RE = re.compile(r"(?:OAuth|Bearer)\s+([A-Za-z0-9._~+/=%:-]{20,})", re.I)
CLIENT_ID_PATTERNS = [
    re.compile(r"(?:client_id|clientId)\s*[=:]\s*[\"']?([A-Za-z0-9]{20,80})", re.I),
    re.compile(r"[?&]client_id=([A-Za-z0-9]{20,80})", re.I),
    re.compile(r'"hydratable"\s*:\s*"apiClient".{0,260}?"id"\s*:\s*"([A-Za-z0-9]{20,80})"', re.I | re.S),
    re.compile(r'"apiClient".{0,260}?"id"\s*:\s*"([A-Za-z0-9]{20,80})"', re.I | re.S),
]
APP_VERSION_RE = re.compile(r"__sc_version\s*=\s*[\"']([^\"']+)", re.I)
COOKIE_ATTR_NAMES = {
    "path",
    "domain",
    "expires",
    "max-age",
    "secure",
    "httponly",
    "samesite",
    "priority",
}

# JS que intercepta window.open() sem depender de pywebview.api.
# Em vez de chamar Python, grava a URL no sessionStorage.
# O Python lê via polling no evaluate_js.
WINDOW_OPEN_PATCH = r"""
(function patch() {
    if (window._ptPatched) return;
    window._ptPatched = true;

    function capturePopupUrl(value) {
        var text = String(value || '').trim();
        if (!text) return;
        if (/^about:/i.test(text)) return;
        if (/^javascript:/i.test(text)) return;
        if (/^https?:/i.test(text)) {
            try { sessionStorage.setItem('_pt_popup_url', text); } catch(e){}
        }
    }

    function captureHtml(html) {
        var text = String(html || '');
        var m = text.match(/action=['"]?(https[^'">\s]+)/i)
             || text.match(/content=['"]?\d+;\s*url=(https[^'">\s]+)/i)
             || text.match(/href=['"]?(https:\/\/accounts\.google[^'">\s]+)/i);
        if (m) capturePopupUrl(m[1]);
    }

    function captureTokenText(value) {
        var text = String(value || '');
        if (!/(OAuth|Bearer|oauth_token|access_token|oauthToken|accessToken)/i.test(text)) return;
        try {
            var current = sessionStorage.getItem('_pt_token_candidates') || '';
            if (current.indexOf(text) === -1) {
                sessionStorage.setItem('_pt_token_candidates', current + '\n' + text);
            }
        } catch(e) {}
    }

    function captureHeaders(headers) {
        if (!headers) return;
        try {
            if (typeof headers.forEach === 'function') {
                headers.forEach(function(value, key) { captureTokenText(key + ': ' + value); });
                return;
            }
            if (Array.isArray(headers)) {
                headers.forEach(function(row) { captureTokenText((row || []).join(': ')); });
                return;
            }
            Object.keys(headers).forEach(function(key) { captureTokenText(key + ': ' + headers[key]); });
        } catch(e) {}
    }

    function capturePageState() {
        try {
            const rows = [];
            rows.push('url=' + String(location.href || ''));
            rows.push('cookie=' + String(document.cookie || ''));
            let apiClientId = '';
            try {
                const hydration = window.__sc_hydration || [];
                if (window.__sc_version) rows.push('app_version=' + window.__sc_version);
                for (const item of hydration) {
                    if (item && item.hydratable === 'apiClient' && item.data && item.data.id) {
                        apiClientId = item.data.id;
                        rows.push('client_id=' + apiClientId);
                    }
                }
                rows.push(JSON.stringify(hydration).slice(0, 10000));
            } catch(e) {}
            try {
                for (let i = 0; i < localStorage.length; i += 1) {
                    const key = localStorage.key(i);
                    rows.push(`${key}=${localStorage.getItem(key)}`);
                }
            } catch(e) {}
            try {
                const bodyText = String(document.body && document.body.innerText || '');
                const loggedInDom =
                    !!document.querySelector('[href="/you/library"], a[href*="/you/library"], a[href="/upload"], a[href*="/upload"], button[aria-label*="Profile"], button[aria-label*="profile"], .header__userNav, .userNav')
                    || /\\b(Biblioteca|Library|Upload|Feed|Sair|Sign out)\\b/i.test(bodyText);
                const stillSignin = /\\b(Sign in or create an account|Entre|Entrar|Continue with Google|Continue with email)\\b/i.test(bodyText);
                if (loggedInDom && !stillSignin) {
                    rows.push('browser_dom_logged_in=1');
                    const profileLink = document.querySelector('a[href^="/"][title], a[href^="/"] img')?.closest?.('a') || null;
                    if (profileLink) rows.push('browser_display_name=' + String(profileLink.getAttribute('title') || profileLink.textContent || 'SoundCloud').trim());
                }
            } catch(e) {}
            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.capture_state) {
                    window.pywebview.api.capture_state(rows.join('\n'));
                }
            } catch(e) {}
            captureTokenText(rows.join('\n'));

            if (apiClientId && !window._ptMeFetchInFlight) {
                window._ptMeFetchInFlight = true;
                const appVersion = window.__sc_version || '';
                const meUrl = 'https://api-v2.soundcloud.com/me?client_id=' + encodeURIComponent(apiClientId)
                    + (appVersion ? '&app_version=' + encodeURIComponent(appVersion) : '');
                fetch(meUrl, {
                    credentials: 'include',
                    headers: {'Accept': 'application/json'}
                }).then(async function(response) {
                    const result = ['browser_me_status=' + response.status];
                    try {
                        const data = await response.json();
                        if (response.ok && data) {
                            result.push('browser_me_ok=1');
                            result.push('browser_display_name=' + String(data.username || data.full_name || 'SoundCloud'));
                            result.push('browser_avatar=' + String(data.avatar_url || ''));
                            result.push('browser_user_id=' + String(data.id || ''));
                        }
                    } catch(e) {}
                    try {
                        if (window.pywebview && window.pywebview.api && window.pywebview.api.capture_state) {
                            window.pywebview.api.capture_state(result.join('\n'));
                        }
                    } catch(e) {}
                }).catch(function(error) {
                    try {
                        if (window.pywebview && window.pywebview.api && window.pywebview.api.capture_state) {
                            window.pywebview.api.capture_state('browser_me_status=fetch_error');
                        }
                    } catch(e) {}
                }).finally(function() {
                    setTimeout(function() { window._ptMeFetchInFlight = false; }, 3500);
                });
            }
        } catch(e) {}
    }

    if (!window._ptFetchPatched && window.fetch) {
        window._ptFetchPatched = true;
        var originalFetch = window.fetch;
        window.fetch = function(input, init) {
            try {
                captureTokenText(input && input.url ? input.url : input);
                captureHeaders(input && input.headers);
                captureHeaders(init && init.headers);
            } catch(e) {}
            return originalFetch.apply(this, arguments);
        };
    }

    if (!window._ptXhrPatched && window.XMLHttpRequest) {
        window._ptXhrPatched = true;
        var originalOpen = XMLHttpRequest.prototype.open;
        var originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
        var originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function(method, url) {
            try {
                this._ptUrl = url;
                captureTokenText(url);
            } catch(e) {}
            return originalOpen.apply(this, arguments);
        };
        XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
            captureTokenText(String(name || '') + ': ' + String(value || ''));
            return originalSetRequestHeader.apply(this, arguments);
        };
        XMLHttpRequest.prototype.send = function(body) {
            captureTokenText(this._ptUrl || '');
            captureTokenText(body || '');
            return originalSend.apply(this, arguments);
        };
    }

    document.addEventListener('click', function(evt) {
        var anchor = evt.target && evt.target.closest ? evt.target.closest('a[href]') : null;
        if (!anchor) return;
        var href = anchor.getAttribute('href') || '';
        if (/^https:\/\/accounts\.google/i.test(href)) {
            evt.preventDefault();
            capturePopupUrl(href);
            return;
        }
        if (/^about:/i.test(href)) {
            evt.preventDefault();
        }
    }, true);

    window.open = function(url, name, features) {
        var textUrl = String(url || '').trim();
        var capturedUrl = (
            textUrl &&
            !/^about:/i.test(textUrl) &&
            textUrl.indexOf('javascript:') !== 0
        ) ? textUrl : '';

        capturePopupUrl(capturedUrl);

        var self = this;
        var proxyLocation = {
            _href: capturedUrl || '',
            get href()  { return this._href; },
            set href(v) {
                var next = String(v || '').trim();
                if (!next || /^about:/i.test(next) || /^javascript:/i.test(next)) {
                    this._href = '';
                    return;
                }
                this._href = next;
                capturePopupUrl(next);
            },
            assign:   function(v) { this.href = v; },
            replace:  function(v) { this.href = v; },
            toString: function()  { return this._href || ''; }
        };

        var proxy = {
            closed: false,
            name: name || '',
            opener: window,
            close:       function() { this.closed = true; },
            focus:       function() {},
            blur:        function() {},
            postMessage: function() {},
            document: {
                _written: '',
                open:    function() { this._written = ''; },
                close:   function() {
                    captureHtml(this._written);
                },
                write:   function(html) {
                    this._written += html;
                    captureHtml(html);
                },
                writeln: function(html) { this.write(html + '\n'); },
                createElement: function() { return {}; },
                body: { appendChild: function() {} },
                head: { appendChild: function() {} },
                location: proxyLocation,
                URL: ''
            },
            location: proxyLocation
        };
        return proxy;
    };

    capturePageState();
    if (!window._ptStateTimer) {
        window._ptStateTimer = setInterval(capturePageState, 1200);
    }
})();
"""


def _bring_to_front(title):
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.FindWindowW(None, title)
        if hwnd:
            u32.ShowWindow(hwnd, 9)
            u32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
            u32.SetForegroundWindow(hwnd)
            u32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040)
    except Exception:
        pass


def _extract_token(text: str) -> str:
    tokens = _extract_tokens(text)
    return tokens[0] if tokens else ""


def _normalize_token(token: str) -> str:
    value = unquote(str(token or "").strip().strip("\"'"))
    value = value.split(";", 1)[0].strip()
    return value


def _extract_tokens(text: str) -> list[str]:
    source = str(text or "")
    found = []
    seen = set()

    def add(value: str):
        token = _normalize_token(value)
        if len(token) < 20 or any(ch.isspace() for ch in token) or token in seen:
            return
        seen.add(token)
        found.append(token)

    for match in SC_TOKEN_RE.finditer(source):
        add(match.group(1))
    for match in NAMED_TOKEN_RE.finditer(source):
        add(match.group(1))
    for match in AUTH_TOKEN_RE.finditer(source):
        add(match.group(1))

    stripped = _normalize_token(source)
    if stripped and ("-" in stripped or stripped.lower().startswith(("oauth ", "bearer "))):
        add(stripped.replace("OAuth ", "").replace("Bearer ", ""))

    return found


def _collect_storage_text(window) -> str:
    try:
        return window.evaluate_js(
            """
            (() => {
                const rows = [];
                try {
                    for (let i = 0; i < localStorage.length; i += 1) {
                        const key = localStorage.key(i);
                        rows.push(`${key}=${localStorage.getItem(key)}`);
                    }
                } catch (e) {}
                try {
                    for (let i = 0; i < sessionStorage.length; i += 1) {
                        const key = sessionStorage.key(i);
                        rows.push(`${key}=${sessionStorage.getItem(key)}`);
                    }
                } catch (e) {}
                return rows.join('\\n');
            })()
            """
        ) or ""
    except Exception:
        return ""


def _collect_bridge_text(window) -> str:
    try:
        return window.evaluate_js("sessionStorage.getItem('_pt_token_candidates') || ''") or ""
    except Exception:
        return ""


def _add_candidates(shared: dict, text: str):
    if not text:
        return
    for token in _extract_tokens(text):
        if token not in shared["candidates"]:
            shared["candidates"].append(token)


def _add_client_id(shared: dict, text: str):
    if shared.get("client_id"):
        return
    source = str(text or "")
    for pattern in CLIENT_ID_PATTERNS:
        for match in pattern.finditer(source):
            value = match.group(1).strip()
            if value:
                shared["client_id"] = value
                return


def _add_app_version(shared: dict, text: str):
    if shared.get("app_version"):
        return
    match = APP_VERSION_RE.search(str(text or ""))
    if match:
        shared["app_version"] = match.group(1).strip()


def _add_cookie_pair(shared: dict, name: str, value: str):
    key = str(name or "").strip()
    val = str(value or "").strip()
    if not key or not val:
        return
    if key.lower() in COOKIE_ATTR_NAMES:
        return
    if any(ch in key for ch in " \t\r\n,;"):
        return
    shared.setdefault("cookies", {})[key] = val


def _parse_cookie_header(shared: dict, header: str):
    text = str(header or "")
    if not text:
        return
    parts = re.split(r";\s*|\n+", text)
    for part in parts:
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        _add_cookie_pair(shared, name, value)


def _parse_set_cookie_header(shared: dict, header: str):
    text = str(header or "")
    if not text:
        return
    # Set-Cookie may contain commas in Expires, so prefer line chunks and the
    # first name=value from each cookie declaration.
    chunks = re.split(r"\n+|,\s*(?=[A-Za-z0-9_.$-]+=)", text)
    for chunk in chunks:
        first = chunk.split(";", 1)[0]
        if "=" not in first:
            continue
        name, value = first.split("=", 1)
        _add_cookie_pair(shared, name, value)


def _cookie_header(shared: dict) -> str:
    cookies = shared.get("cookies") or {}
    return "; ".join(f"{name}={value}" for name, value in cookies.items() if name and value)


def _collect_client_text(window) -> str:
    try:
        return window.evaluate_js(
            """
            (() => {
                const rows = [];
                try {
                    if (window.__sc_version) rows.push('app_version=' + window.__sc_version);
                    const hydration = window.__sc_hydration || [];
                    for (const item of hydration) {
                        if (item && item.hydratable === 'apiClient' && item.data && item.data.id) {
                            rows.push('client_id=' + item.data.id);
                        }
                    }
                    rows.push(JSON.stringify(hydration).slice(0, 8000));
                } catch (e) {}
                return rows.join('\\n');
            })()
            """
        ) or ""
    except Exception:
        return ""


def _web_session_profile(cookie_header: str, client_id: str, app_version: str = "") -> tuple[dict, str]:
    if not cookie_header or not client_id:
        return {}, "missing"
    try:
        response = requests.get(
            "https://api-v2.soundcloud.com/me",
            params={
                "client_id": client_id,
                **({"app_version": app_version} if app_version else {}),
            },
            headers={
                "Accept": "application/json",
                "Cookie": cookie_header,
                "Origin": "https://soundcloud.com",
                "Referer": "https://soundcloud.com/",
                "User-Agent": "Mozilla/5.0 PlayTransfer",
                "X-Requested-With": "XMLHttpRequest",
                **({"X-Datadome-Clientid": _cookie_from_header(cookie_header, "datadome")} if _cookie_from_header(cookie_header, "datadome") else {}),
            },
            timeout=8,
        )
        if response.status_code != 200:
            return {}, f"HTTP {response.status_code}"
        data = response.json()
        return {
            "display_name": data.get("username") or data.get("full_name") or "SoundCloud",
            "avatar": data.get("avatar_url", ""),
            "user_id": data.get("id", ""),
        }, "HTTP 200"
    except Exception as exc:
        return {}, type(exc).__name__


def _emit_web_session(shared: dict, validate: bool = True) -> bool:
    cookie_header = _cookie_header(shared)
    client_id = shared.get("client_id") or ""
    if not cookie_header or not client_id:
        return False

    browser_profile = shared.get("browser_profile") or {}
    browser_ok = bool(shared.get("browser_me_ok") or shared.get("browser_dom_logged_in"))
    app_version = str(shared.get("app_version") or "")
    profile, status = _web_session_profile(cookie_header, client_id, app_version) if validate and not browser_ok else ({}, "browser_ok")
    if validate and not profile:
        if browser_ok and ROLE != "dest":
            profile = browser_profile
        else:
            return False

    access_token = _token_from_cookies([{"name": k, "value": v} for k, v in shared.get("cookies", {}).items()])
    if not access_token and shared.get("candidates"):
        access_token = shared["candidates"][0]

    payload = {
        "cookie_header": cookie_header,
        "client_id": client_id,
        "app_version": app_version,
        "access_token": access_token,
        "display_name": profile.get("display_name", "SoundCloud") if profile else "SoundCloud",
        "avatar": profile.get("avatar", "") if profile else "",
        "validated_in_browser": browser_ok,
        "last_url": shared.get("last_url", ""),
    }
    print("SC_SESSION_FOUND:" + json.dumps(payload, ensure_ascii=False), flush=True)
    return True


def _emit_debug(shared: dict, force: bool = False):
    now = time.time()
    if not force and now - float(shared.get("last_debug_at") or 0) < 5:
        return
    shared["last_debug_at"] = now
    cookie_header = _cookie_header(shared)
    client_id = shared.get("client_id") or ""
    _, status = _web_session_profile(cookie_header, client_id, str(shared.get("app_version") or "")) if cookie_header and client_id else ({}, "missing")
    payload = {
        "has_client_id": bool(client_id),
        "cookies": len(shared.get("cookies") or {}),
        "candidates": len(shared.get("candidates") or []),
        "me_status": shared.get("browser_me_status") or status,
        "browser_ok": bool(shared.get("browser_me_ok") or shared.get("browser_dom_logged_in")),
        "url_hosted": "soundcloud.com" in str(shared.get("last_url") or "").lower(),
    }
    print("SC_SESSION_DEBUG:" + json.dumps(payload, ensure_ascii=False), flush=True)


def _safe_capture_state(shared: dict, text: str):
    source = str(text or "")
    if not source:
        return
    _add_client_id(shared, source)
    _add_app_version(shared, source)
    _add_candidates(shared, source)
    match = re.search(r"(?:^|\n)url=(.+)", source)
    if match:
        shared["last_url"] = match.group(1).strip()
    for cookie_match in re.finditer(r"(?:^|\n)cookie=([^\n]*)", source):
        _parse_cookie_header(shared, cookie_match.group(1))
    status_match = re.search(r"(?:^|\n)browser_me_status=([^\n]+)", source)
    if status_match:
        shared["browser_me_status"] = status_match.group(1).strip()
    if re.search(r"(?:^|\n)browser_me_ok=1(?:\n|$)", source):
        shared["browser_me_ok"] = True
        profile = shared.setdefault("browser_profile", {})
        for key, target in (
            ("browser_display_name", "display_name"),
            ("browser_avatar", "avatar"),
            ("browser_user_id", "user_id"),
        ):
            match = re.search(rf"(?:^|\n){key}=([^\n]*)", source)
            if match:
                profile[target] = match.group(1).strip()
    if re.search(r"(?:^|\n)browser_dom_logged_in=1(?:\n|$)", source):
        shared["browser_dom_logged_in"] = True
        profile = shared.setdefault("browser_profile", {})
        match = re.search(r"(?:^|\n)browser_display_name=([^\n]*)", source)
        if match and not profile.get("display_name"):
            profile["display_name"] = match.group(1).strip() or "SoundCloud"


def _cookie_from_header(cookie_header: str, name: str) -> str:
    wanted = str(name or "").strip().lower()
    for part in str(cookie_header or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key.strip().lower() == wanted:
            return value.strip()
    return ""


def _valid_soundcloud_authorization(token: str, client_id: str = "") -> str:
    value = _normalize_token(token)
    if not value:
        return ""
    for scheme in ("OAuth", "Bearer"):
        if client_id:
            try:
                response = requests.get(
                    "https://api-v2.soundcloud.com/me",
                    params={"client_id": client_id},
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"{scheme} {value}",
                        "Origin": "https://soundcloud.com",
                        "Referer": "https://soundcloud.com/",
                        "User-Agent": "Mozilla/5.0 PlayTransfer",
                    },
                    timeout=6,
                )
                if response.status_code == 200:
                    return f"{scheme} {value}"
            except Exception:
                pass
        try:
            response = requests.get(
                "https://api.soundcloud.com/me",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"{scheme} {value}",
                    "User-Agent": "Mozilla/5.0 PlayTransfer",
                },
                timeout=6,
            )
            if response.status_code == 200:
                return f"{scheme} {value}"
        except Exception:
            pass
    return ""


def _token_from_cookies(cookies) -> str:
    for ck in (cookies or []):
        try:
            if isinstance(ck, dict):
                name = str(ck.get("name") or "").strip().lower()
                value = str(ck.get("value") or "").strip()
            else:
                name  = str(getattr(ck, "name",  None) or "").strip().lower()
                value = str(getattr(ck, "value", None) or "").strip()
            if name in TOKEN_COOKIE_NAMES:
                t = _extract_token(value) or (value if len(value) > 20 else "")
                if t:
                    return t
        except Exception:
            pass
    return ""


def check_token(window):
    shared = {
        "token": "",
        "candidates": [],
        "tested": set(),
        "last_url": "",
        "closed": False,
        "cookies": {},
        "client_id": "",
        "app_version": "",
    }

    # ── Eventos ────────────────────────────────────────────────────────────────
    def capture_state(text):
        _safe_capture_state(shared, text)
        if _emit_web_session(shared, validate=True):
            try:
                window.destroy()
            except Exception:
                pass
        else:
            _emit_debug(shared)
        return True

    try:
        window.expose(capture_state)
    except Exception:
        pass

    def on_request(request):
        headers = getattr(request, "headers", {}) or {}
        url = str(getattr(request, "url", "") or "")
        _add_client_id(shared, url)
        for name, value in headers.items():
            lowered = str(name).lower()
            if lowered == "cookie" and "soundcloud.com" in url.lower():
                _parse_cookie_header(shared, str(value))
            if lowered in {"cookie", "authorization"}:
                _add_candidates(shared, str(value))

    def on_response(response):
        headers = getattr(response, "headers", {}) or {}
        url = str(getattr(response, "url", "") or "")
        _add_client_id(shared, url)
        for name, value in headers.items():
            if str(name).lower() == "set-cookie":
                if "soundcloud.com" in url.lower():
                    _parse_set_cookie_header(shared, str(value))
                _add_candidates(shared, str(value))

    def on_loaded():
        try:
            url = window.get_current_url() or ""
            if url:
                shared["last_url"] = url
        except Exception:
            pass

        # Injeta o patch a cada página carregada (antes de qualquer interação)
        try:
            window.evaluate_js(WINDOW_OPEN_PATCH)
        except Exception:
            pass

        try:
            _add_client_id(shared, _collect_client_text(window))
        except Exception:
            pass

        # Captura cookie se já saiu do signin
        url = shared["last_url"].lower()
        if url and "soundcloud.com" in url:
            try:
                document_cookie = window.evaluate_js("document.cookie") or ""
                _parse_cookie_header(shared, document_cookie)
                _add_candidates(shared, document_cookie)
                _add_candidates(shared, _collect_storage_text(window))
                _add_candidates(shared, _collect_bridge_text(window))
            except Exception:
                pass

    def on_closed():
        shared["closed"] = True

    def on_shown():
        def focus():
            time.sleep(0.4)
            try:
                window.restore()
            except Exception:
                pass
            _bring_to_front(WINDOW_TITLE)
        threading.Thread(target=focus, daemon=True).start()

    window.events.request_sent      += on_request
    window.events.response_received += on_response
    window.events.loaded            += on_loaded
    window.events.closed            += on_closed
    window.events.shown             += on_shown

    navigated_past_signin = False

    try:
        window.evaluate_js(WINDOW_OPEN_PATCH)
    except Exception:
        pass

    for _ in range(360):
        if shared["closed"]:
            if _emit_web_session(shared, validate=True):
                return
            print(f"SC_TOKEN_ABORTED:{shared['last_url']}", flush=True)
            return

        url = shared["last_url"].lower()

        # ── Polling: verifica se JS capturou URL de popup no sessionStorage ──
        try:
            popup_url = window.evaluate_js(
                "sessionStorage.getItem('_pt_popup_url') || ''"
            ) or ""
            if popup_url and popup_url.startswith("http"):
                # Limpa para não processar de novo
                window.evaluate_js("sessionStorage.removeItem('_pt_popup_url')")
                window.load_url(popup_url)
                time.sleep(0.5)
                continue
        except Exception:
            pass

        try:
            url_now = window.get_current_url() or ""
            if url_now:
                shared["last_url"] = url_now
                url = url_now.lower()
        except Exception:
            pass

        if not navigated_past_signin:
            if url and "signin" not in url and "login" not in url and "accounts.google" not in url:
                navigated_past_signin = True

        try:
            cookies = window.get_cookies() or []
            cookie_token = _token_from_cookies(cookies)
            _add_candidates(shared, cookie_token)
            for ck in cookies:
                if isinstance(ck, dict):
                    name = str(ck.get("name") or "")
                    value = str(ck.get("value") or "")
                else:
                    name = str(getattr(ck, "name", "") or "")
                    value = str(getattr(ck, "value", "") or "")
                _add_cookie_pair(shared, name, value)
        except Exception:
            pass

        if navigated_past_signin or "soundcloud.com" in url:
            try:
                document_cookie = window.evaluate_js("document.cookie") or ""
                _parse_cookie_header(shared, document_cookie)
                _add_candidates(shared, document_cookie)
                _add_candidates(shared, _collect_storage_text(window))
                _add_candidates(shared, _collect_bridge_text(window))
                _add_client_id(shared, _collect_client_text(window))
            except Exception:
                pass

            for candidate in list(reversed(shared["candidates"])):
                if candidate in shared["tested"]:
                    continue
                shared["tested"].add(candidate)
                authorization = _valid_soundcloud_authorization(candidate, shared.get("client_id", ""))
                if authorization:
                    shared["token"] = authorization
                    print("SC_TOKEN_CONTEXT:" + json.dumps({
                        "cookie_header": _cookie_header(shared),
                        "client_id": shared.get("client_id", ""),
                        "app_version": shared.get("app_version", ""),
                        "last_url": shared.get("last_url", ""),
                    }, ensure_ascii=False), flush=True)
                    for found in shared["candidates"]:
                        print("SC_TOKEN_CANDIDATE:" + found, flush=True)
                    print("SC_TOKEN_FOUND:" + shared["token"], flush=True)
                    try:
                        window.destroy()
                    except Exception:
                        pass
                    return

            if _emit_web_session(shared, validate=True):
                try:
                    window.destroy()
                except Exception:
                    pass
                return

        _emit_debug(shared)

        time.sleep(1)

    if _emit_web_session(shared, validate=True):
        try:
            window.destroy()
        except Exception:
            pass
        return

    _emit_debug(shared, force=True)
    print(f"SC_TOKEN_TIMEOUT:{shared['last_url']}", flush=True)
    try:
        window.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    os.makedirs(STORAGE_PATH, exist_ok=True)
    window = webview.create_window(
        title=WINDOW_TITLE,
        url=START_URL,
        width=500,
        height=700,
        resizable=True,
        on_top=True,
        focus=True,
    )
    webview.start(check_token, window, private_mode=False, storage_path=STORAGE_PATH)
