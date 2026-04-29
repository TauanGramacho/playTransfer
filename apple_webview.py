import ctypes
import json
import os
import re
import tempfile
import threading
import time

import webview


WINDOW_TITLE = "Login Apple Music - PlayTransfer"
APPLE_MUSIC_URL = "https://music.apple.com/br/new"
DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".runtime", "apple_webview_debug.log")
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)

APPLE_CAPTURE_JS = r"""
(function() {
  function looksLikeRealToken(token) {
    token = String(token || '').trim();
    if (!token || token.length < 50) return false;
    if (/[\s{}()[\]"']/.test(token)) return false;
    if (/cachedsource|clientconfig|perf|feature|experiment|config/i.test(token)) return false;
    return true;
  }

  function rememberToken(token, source) {
    token = String(token || '').trim().replace(/^Bearer\s+/i, '');
    if (!looksLikeRealToken(token)) return false;
    window.__ptAppleMusicUserToken = token;
    window.__ptAppleCaptureSource = source || 'apple-web';
    return true;
  }

  function rememberStorefront(storefront, source) {
    storefront = String(storefront || '').trim().toLowerCase();
    if (!/^[a-z]{2}$/.test(storefront)) return false;
    window.__ptAppleStorefront = storefront;
    window.__ptAppleStorefrontSource = source || 'apple-web';
    return true;
  }

  function rememberItfe(value, source) {
    value = String(value || '').trim();
    if (!value || value.length < 8) return false;
    if (/[\s{}()[\]"']/.test(value)) return false;
    window.__ptAppleItfe = value;
    window.__ptAppleItfeSource = source || 'apple-web';
    return true;
  }

  function rememberAuthorized(value, source) {
    var text = String(value || '').trim();
    var numeric = Number(text);
    if (!(value === true || numeric >= 3 || text.toUpperCase() === 'AUTHORIZED')) return false;
    window.__ptAppleAuthorized = true;
    window.__ptAppleAuthorizedSource = source || 'apple-web';
    return true;
  }

  function considerUrl(value, source) {
    var text = String(value || '');
    if (!text) return false;
    var match = text.match(/music\.apple\.com\/([a-z]{2})(?:\/|$)/i) || text.match(/\/v1\/catalog\/([a-z]{2})(?:\/|$)/i);
    if (match) {
      rememberStorefront(match[1], source);
    }
    var itfeMatch = text.match(/[?&]itfe=([A-Za-z0-9._:-]{8,})/i);
    if (itfeMatch) rememberItfe(itfeMatch[1], source);
    return !!match || !!itfeMatch;
  }

  function considerText(value, source) {
    var text = String(value || '');
    if (!text) return false;

    considerUrl(text, source);

    var itfeMatch = text.match(/["']?itfe["']?\s*[:=]\s*["']?([A-Za-z0-9._:-]{8,})/i);
    if (itfeMatch) rememberItfe(itfeMatch[1], source);

    var tokenPatterns = [
      /["']?(?:media-user-token|music-user-token|musicUserToken|userToken)["']?\s*[:=]\s*["']?([A-Za-z0-9._=-]{40,})/i,
      /motw-pref:media-user-token[^A-Za-z0-9._=-]*["']?([A-Za-z0-9._=-]{40,})/i
    ];

    for (var i = 0; i < tokenPatterns.length; i++) {
      var match = text.match(tokenPatterns[i]);
      if (match && rememberToken(match[1], source)) return true;
    }

    var storefrontPatterns = [
      /["']?(?:storefront|storefrontId|storefrontCountryCode)["']?\s*[:=]\s*["']?([A-Za-z]{2})/i,
      /music\.apple\.com\/([a-z]{2})(?:\/|$)/i
    ];

    for (var j = 0; j < storefrontPatterns.length; j++) {
      var storefrontMatch = text.match(storefrontPatterns[j]);
      if (storefrontMatch) rememberStorefront(storefrontMatch[1], source);
    }

    return false;
  }

  function inspectHeaderValue(source, key, value) {
    key = String(key || '').toLowerCase();
    if (!key) return;
    if (key === 'music-user-token' || key === 'media-user-token') {
      rememberToken(value, source + ':' + key);
      rememberAuthorized(true, source + ':' + key);
    } else if (key === 'authorization') {
      considerText(key + '=' + value, source);
    } else if (key === 'cookie') {
      considerText(value, source + ':cookie');
    }
  }

  function inspectHeaders(source, headers) {
    if (!headers) return;
    try {
      if (typeof headers.forEach === 'function') {
        headers.forEach(function(value, key) {
          inspectHeaderValue(source, key, value);
        });
        return;
      }
    } catch (e) {}
    try {
      if (Array.isArray(headers)) {
        for (var i = 0; i < headers.length; i++) {
          inspectHeaderValue(source, headers[i][0], headers[i][1]);
        }
        return;
      }
    } catch (e) {}
    try {
      Object.keys(headers).forEach(function(key) {
        inspectHeaderValue(source, key, headers[key]);
      });
    } catch (e) {}
  }

  function hookStorage(name) {
    try {
      var storage = window[name];
      if (!storage || storage.__ptAppleWrapped) return;
      var proto = Object.getPrototypeOf(storage);
      if (!proto || proto.__ptAppleWrapped) return;
      var originalSetItem = proto.setItem;
      proto.setItem = function(key, value) {
        considerText(String(key || '') + '=' + String(value || ''), name + '.setItem');
        return originalSetItem.apply(this, arguments);
      };
      proto.__ptAppleWrapped = true;
      storage.__ptAppleWrapped = true;
    } catch (e) {}
  }

  function installRequestHooks() {
    if (window.__ptAppleHooksInstalled) return;
    window.__ptAppleHooksInstalled = true;

    hookStorage('localStorage');
    hookStorage('sessionStorage');

    try {
      var originalOpen = window.open;
      window.open = function(url, target, features) {
        var text = String(url || '');
        if (/apple\.com|idmsa\.apple\.com|itunes\.apple\.com/i.test(text)) {
          window.location.href = text;
          return window;
        }
        return originalOpen ? originalOpen.apply(window, arguments) : null;
      };
    } catch (e) {}

    try {
      var originalFetch = window.fetch;
      if (typeof originalFetch === 'function') {
        window.fetch = function(input, init) {
          try {
            var requestUrl = typeof input === 'string' ? input : (input && input.url) || '';
            considerUrl(requestUrl, 'fetch');
            inspectHeaders('fetch:init', init && init.headers);
            inspectHeaders('fetch:request', input && input.headers);
          } catch (e) {}

          return originalFetch.apply(this, arguments).then(function(response) {
            try {
              if (response && response.url) considerUrl(response.url, 'fetch:response');
              if (response && response.headers) inspectHeaders('fetch:response', response.headers);
            } catch (e) {}
            return response;
          });
        };
      }
    } catch (e) {}

    try {
      var proto = window.XMLHttpRequest && window.XMLHttpRequest.prototype;
      if (proto && !proto.__ptAppleWrapped) {
        var originalOpen = proto.open;
        var originalSetRequestHeader = proto.setRequestHeader;
        proto.open = function(method, url) {
          this.__ptAppleUrl = url || '';
          this.__ptAppleHeaders = {};
          considerUrl(url || '', 'xhr:open');
          return originalOpen.apply(this, arguments);
        };
        proto.setRequestHeader = function(name, value) {
          this.__ptAppleHeaders = this.__ptAppleHeaders || {};
          this.__ptAppleHeaders[name] = value;
          inspectHeaderValue('xhr:header', name, value);
          return originalSetRequestHeader.apply(this, arguments);
        };
        proto.send = (function(originalSend) {
          return function() {
            try {
              inspectHeaders('xhr:send', this.__ptAppleHeaders || {});
              var self = this;
              this.addEventListener('loadend', function() {
                try {
                  considerUrl(self.responseURL || self.__ptAppleUrl || '', 'xhr:response');
                } catch (e) {}
              }, { once: true });
            } catch (e) {}
            return originalSend.apply(this, arguments);
          };
        })(proto.send);
        proto.__ptAppleWrapped = true;
      }
    } catch (e) {}
  }

  function scanStorage(name) {
    try {
      var storage = window[name];
      if (!storage) return;
      for (var i = 0; i < storage.length; i++) {
        var key = storage.key(i);
        var value = storage.getItem(key);
        var keyLower = String(key || '').toLowerCase();
        if (
          keyLower.includes('media-user-token') ||
          keyLower.includes('music-user-token') ||
          keyLower.includes('musicusertoken') ||
          keyLower.includes('storefront') ||
          keyLower.includes('itfe')
        ) {
          considerText(key + '=' + value, name + ':' + key);
        }
      }
    } catch (e) {}
  }

  function inspectObjectTree(value, source, depth, seen) {
    if (depth > 2 || value == null) return;
    if (typeof value === 'string') {
      considerText(value, source);
      return;
    }
    if (typeof value !== 'object') return;

    try {
      if (seen && seen.has(value)) return;
      if (seen) seen.add(value);
    } catch (e) {}

    var keys = [];
    try {
      keys = Object.keys(value).slice(0, 40);
    } catch (e) {
      return;
    }

    for (var i = 0; i < keys.length; i++) {
      var key = keys[i];
      var child;
      try {
        child = value[key];
      } catch (e) {
        continue;
      }

      var keyLower = String(key || '').toLowerCase();
      if (
        keyLower.includes('token') ||
        keyLower.includes('storefront') ||
        keyLower.includes('itfe') ||
        keyLower.includes('authorize') ||
        keyLower.includes('user')
      ) {
        considerText(key + '=' + child, source + '.' + key);
      }

      if (typeof child === 'object' && child && (
        depth === 0 ||
        keyLower.includes('storekit') ||
        keyLower.includes('music') ||
        keyLower.includes('api') ||
        keyLower.includes('feature')
      )) {
        inspectObjectTree(child, source + '.' + key, depth + 1, seen);
      }
    }
  }

  function inspectMusicKit() {
    try {
      if (!window.MusicKit || !window.MusicKit.getInstance) return;
      var instance = window.MusicKit.getInstance();
      if (!instance) return;

      if (instance.musicUserToken) rememberToken(instance.musicUserToken, 'musickit-instance');
      if (instance.userToken) rememberToken(instance.userToken, 'musickit-instance');
      if (instance.storekit && instance.storekit.userToken) rememberToken(instance.storekit.userToken, 'musickit-storekit');
      if (instance.storefrontId) rememberStorefront(instance.storefrontId, 'musickit-instance');
      if (instance.storefront && instance.storefront.id) rememberStorefront(instance.storefront.id, 'musickit-instance');
      if (instance.storekit && instance.storekit.storefrontCountryCode) rememberStorefront(instance.storekit.storefrontCountryCode, 'musickit-storekit');
      if (instance.authorizationStatus != null) rememberAuthorized(instance.authorizationStatus, 'musickit-instance');
      if (instance.storekit && instance.storekit._authorizationStatus != null) rememberAuthorized(instance.storekit._authorizationStatus, 'musickit-storekit');
      if (instance.storekit && instance.storekit.userTokenIsValid) rememberAuthorized(true, 'musickit-storekit');

      var seen = typeof WeakSet === 'function' ? new WeakSet() : null;
      inspectObjectTree(instance, 'musickit-instance', 0, seen);

    } catch (e) {}
  }

  function inspectCommonGlobals() {
    try {
      if (window.featureKit && window.featureKit.itfe) rememberItfe(window.featureKit.itfe, 'window.featureKit');
    } catch (e) {}
    try {
      if (window.__INITIAL_STATE__) considerText(JSON.stringify(window.__INITIAL_STATE__), '__INITIAL_STATE__');
    } catch (e) {}
    try {
      if (window.__NEXT_DATA__) considerText(JSON.stringify(window.__NEXT_DATA__), '__NEXT_DATA__');
    } catch (e) {}
  }

  installRequestHooks();
  considerUrl(location.href, 'location');
  considerText(location.hash || '', 'location.hash');
  considerText(document.cookie || '', 'document.cookie');
  scanStorage('localStorage');
  scanStorage('sessionStorage');
  inspectMusicKit();
  inspectCommonGlobals();

  return JSON.stringify({
    music_user_token: window.__ptAppleMusicUserToken || '',
    storefront: window.__ptAppleStorefront || '',
    itfe: window.__ptAppleItfe || '',
    authorized: !!window.__ptAppleAuthorized,
    source: window.__ptAppleCaptureSource || '',
  });
})();
"""


def _debug(message):
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    print(f"[Apple WebView] {message}", flush=True)
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as debug_file:
            debug_file.write(line + "\n")
    except Exception:
        pass


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


def _remember_storefront(shared, value):
    raw = str(value or "").strip().lower()
    if re.fullmatch(r"[a-z]{2}", raw):
        shared["storefront"] = raw


def _remember_from_url(shared, value):
    raw = str(value or "")
    if not raw:
        return
    for pattern in (
        r"music\.apple\.com/([a-z]{2})(?:/|$)",
        r"/v1/catalog/([a-z]{2})(?:/|$)",
    ):
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            _remember_storefront(shared, match.group(1))
            return


def _remember_user_token(shared, value):
    raw = str(value or "").strip().strip("'").strip('"')
    raw = re.sub(r"^Bearer\s+", "", raw, flags=re.IGNORECASE)
    if len(raw) < 50 or re.search(r"\s", raw):
        return
    if re.search(r"cachedsource|clientconfig|perf|feature|experiment|config", raw, re.IGNORECASE):
        return
    shared["music_user_token"] = raw


def _remember_itfe(shared, value):
    raw = str(value or "").strip().strip("'").strip('"')
    if len(raw) < 8 or re.search(r"\s", raw):
        return
    shared["itfe"] = raw


def _remember_authorized(shared, value):
    raw = str(value or "").strip().upper()
    if value is True or raw == "TRUE":
        shared["authorized"] = True
        return
    try:
        if int(str(value).strip()) >= 3:
            shared["authorized"] = True
            return
    except Exception:
        pass
    if raw == "AUTHORIZED":
        shared["authorized"] = True


def _extract_cookie_header(cookies):
    pairs = []
    for cookie in cookies or []:
        try:
            if isinstance(cookie, dict):
                name = str(cookie.get("name") or "").strip()
                value = str(cookie.get("value") or "").strip()
                domain = str(cookie.get("domain") or cookie.get("host") or "").lower()
            else:
                name = str(getattr(cookie, "name", "") or "").strip()
                value = str(getattr(cookie, "value", "") or "").strip()
                domain = str(getattr(cookie, "domain", "") or "").lower()
            if not name or not value:
                continue
            if "apple.com" not in domain and "music.apple.com" not in domain:
                continue
            pairs.append(f"{name}={value}")
            if name.lower() in ("media-user-token", "music-user-token"):
                return "; ".join(pairs), value
        except Exception:
            continue
    return "; ".join(pairs), ""


def check_session(window):
    shared = {
        "music_user_token": "",
        "storefront": "",
        "itfe": "",
        "cookie_header": "",
        "last_url": "",
        "authorized": False,
        "closed": False,
    }

    def remember_url():
        try:
            shared["last_url"] = window.get_current_url() or shared["last_url"]
            _remember_from_url(shared, shared["last_url"])
        except Exception:
            pass

    def on_request(request):
        request_url = str(getattr(request, "url", ""))
        _remember_from_url(shared, request_url)
        itfe_match = re.search(r"[?&]itfe=([^&]+)", request_url)
        if itfe_match:
            _remember_itfe(shared, itfe_match.group(1))
        headers = getattr(request, "headers", {}) or {}
        for name, value in headers.items():
            lowered = str(name or "").lower()
            if lowered in ("media-user-token", "music-user-token"):
                _remember_user_token(shared, value)
                _remember_authorized(shared, True)
            elif lowered == "cookie":
                shared["cookie_header"] = str(value or "").strip()

    def on_response(response):
        _remember_from_url(shared, getattr(response, "url", ""))

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

    last_progress_log_at = 0
    for _ in range(180):
        remember_url()
        if time.time() - last_progress_log_at >= 10:
            last_progress_log_at = time.time()
            _debug(
                "Aguardando captura; "
                f"url={shared['last_url'] or 'desconhecida'}; "
                f"token={'sim' if shared['music_user_token'] else 'nao'}; "
                f"itfe={'sim' if shared['itfe'] else 'nao'}; "
                f"cookie={'sim' if shared['cookie_header'] else 'nao'}; "
                f"authorized={'sim' if shared['authorized'] else 'nao'}; "
                f"storefront={shared['storefront'] or 'desconhecida'}"
            )

        try:
            payload_raw = window.evaluate_js(APPLE_CAPTURE_JS)
            payload = json.loads(payload_raw or "{}")
            _remember_user_token(shared, payload.get("music_user_token"))
            _remember_storefront(shared, payload.get("storefront"))
            _remember_itfe(shared, payload.get("itfe"))
            _remember_authorized(shared, payload.get("authorized"))
        except Exception:
            pass

        try:
            cookies = window.get_cookies()
            cookie_header, cookie_user_token = _extract_cookie_header(cookies)
            if cookie_header:
                shared["cookie_header"] = cookie_header
            if cookie_user_token:
                _remember_user_token(shared, cookie_user_token)
                _remember_authorized(shared, True)
        except Exception:
            pass

        if shared["music_user_token"] or (shared["authorized"] and shared["cookie_header"]):
            print(
                "APPLE_FOUND:"
                + json.dumps(
                    {
                        "music_user_token": shared["music_user_token"],
                        "storefront": shared["storefront"] or "us",
                        "itfe": shared["itfe"],
                        "cookie_header": shared["cookie_header"],
                        "authorized": shared["authorized"],
                        "last_url": shared["last_url"],
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
            print(f"APPLE_ABORTED:{shared['last_url']}", flush=True)
            return

        time.sleep(1)

    print(f"APPLE_TIMEOUT:{shared['last_url']}", flush=True)
    try:
        window.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    storage_path = tempfile.mkdtemp(prefix="playtransfer_apple_login_")
    window = webview.create_window(
        title=WINDOW_TITLE,
        url=APPLE_MUSIC_URL,
        width=460,
        height=720,
        resizable=True,
        on_top=True,
        focus=True,
    )
    threading.Thread(
        target=lambda: (time.sleep(2), check_session(window)),
        daemon=True,
    ).start()
    webview.start(
        private_mode=False,
        storage_path=storage_path,
        user_agent=CHROME_USER_AGENT,
    )
