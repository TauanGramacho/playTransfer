"""
soundcloud_webview.py - PlayTransfer
Abre soundcloud.com em janela nativa, captura oauth_token.
Usa window.expose() para interceptar window.open() do Google OAuth.
"""
import ctypes
import re
import threading
import time

import webview

WINDOW_TITLE = "Login SoundCloud - PlayTransfer"
START_URL    = "https://soundcloud.com/signin"

TOKEN_COOKIE_NAMES = {"oauth_token", "soundcloud_oauth_token", "sc_oauth_token"}
SC_TOKEN_RE = re.compile(r"\b([0-9]+-[0-9]+-[0-9]+-[A-Za-z0-9]{8,})\b")


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
    for m in SC_TOKEN_RE.finditer(str(text or "")):
        t = m.group(1)
        parts = t.split("-")
        if len(parts) == 4 and parts[0].isdigit() and len(parts[3]) >= 8:
            return t
    return ""


def _token_from_cookies(cookies) -> str:
    for ck in (cookies or []):
        try:
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
    shared = {"token": "", "last_url": "", "closed": False}

    # ── Expõe função Python ao JS ──────────────────────────────────────────────
    def popup_navigate(url):
        """Chamada pelo JS override de window.open para navegar na mesma janela."""
        if url and isinstance(url, str) and url.startswith("http"):
            try:
                window.load_url(url)
            except Exception:
                pass

    window.expose(popup_navigate)

    # ── Eventos ────────────────────────────────────────────────────────────────
    def on_request(request):
        headers = getattr(request, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() == "cookie" and not shared["token"]:
                m = re.search(r"(?:^|;)\s*(?:oauth_token|sc_oauth_token)=([^;]+)", str(value), re.I)
                if m:
                    t = _extract_token(m.group(1).strip())
                    if t:
                        shared["token"] = t

    def on_response(response):
        headers = getattr(response, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() == "set-cookie" and not shared["token"]:
                m = re.search(r"(?:oauth_token|sc_oauth_token)=([^;]+)", str(value), re.I)
                if m:
                    t = _extract_token(m.group(1).strip())
                    if t:
                        shared["token"] = t

    def on_loaded():
        try:
            url = window.get_current_url() or ""
            if url:
                shared["last_url"] = url
        except Exception:
            pass

        # Injeta o override de window.open usando a função Python exposta
        try:
            window.evaluate_js("""
                (function patch() {
                    if (window._ptPatched) return;
                    window._ptPatched = true;

                    window.open = function(url, name, features) {
                        // Proxy para about:blank (Google OAuth abre blank e depois navega)
                        var proxy = {
                            closed: false,
                            close: function() {},
                            focus: function() {},
                            document: {write: function(){}, writeln: function(){}, close: function(){}},
                            location: {
                                _href: url || '',
                                get href() { return this._href; },
                                set href(v) {
                                    this._href = v;
                                    if (v && v.indexOf('http') === 0) {
                                        window.pywebview.api.popup_navigate(v);
                                    }
                                },
                                assign: function(v) { this.href = v; },
                                replace: function(v) { this.href = v; }
                            }
                        };

                        if (url && url !== 'about:blank' && url.indexOf('javascript:') !== 0) {
                            window.pywebview.api.popup_navigate(url);
                        }
                        return proxy;
                    };
                })();
            """)
        except Exception:
            pass

        # Captura cookie se já saiu do signin
        url = shared["last_url"].lower()
        if url and "signin" not in url and "login" not in url:
            try:
                cookie_text = window.evaluate_js("document.cookie") or ""
                m = re.search(r"(?:^|;)\s*(?:oauth_token|sc_oauth_token)=([^;]+)", cookie_text, re.I)
                if m and not shared["token"]:
                    t = _extract_token(m.group(1).strip())
                    if t:
                        shared["token"] = t
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

    for _ in range(150):
        if shared["closed"]:
            print(f"SC_TOKEN_ABORTED:{shared['last_url']}", flush=True)
            return

        url = shared["last_url"].lower()

        if not navigated_past_signin:
            if url and "signin" not in url and "login" not in url and "accounts.google" not in url:
                navigated_past_signin = True

        if navigated_past_signin:
            if not shared["token"]:
                try:
                    shared["token"] = _token_from_cookies(window.get_cookies())
                except Exception:
                    pass

            if not shared["token"]:
                try:
                    cookie_text = window.evaluate_js("document.cookie") or ""
                    m = re.search(r"(?:^|;)\s*(?:oauth_token|sc_oauth_token)=([^;]+)", cookie_text, re.I)
                    if m:
                        shared["token"] = _extract_token(m.group(1).strip())
                except Exception:
                    pass

            if shared["token"]:
                print("SC_TOKEN_FOUND:" + shared["token"], flush=True)
                try:
                    window.destroy()
                except Exception:
                    pass
                return

        time.sleep(1)

    print(f"SC_TOKEN_TIMEOUT:{shared['last_url']}", flush=True)
    try:
        window.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    window = webview.create_window(
        title=WINDOW_TITLE,
        url=START_URL,
        width=500,
        height=700,
        resizable=True,
        on_top=True,
        focus=True,
    )
    webview.start(check_token, window, private_mode=False)
