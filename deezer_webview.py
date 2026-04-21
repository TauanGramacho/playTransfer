import re
import time
import ctypes
import threading

import webview


WINDOW_TITLE = 'Login Deezer - PlayTransfer'


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


def _extract_arl_from_text(cookie_text):
    if not cookie_text:
        return None

    match = re.search(r'(?:^|;\s*)arl=([^;]+)', str(cookie_text))
    if match:
        return match.group(1).strip()
    return None


def _extract_arl_from_objects(cookies):
    for cookie in cookies or []:
        try:
            name = getattr(cookie, 'name', '') or ''
            if name == 'arl':
                return str(getattr(cookie, 'value', '') or '').strip()

            if hasattr(cookie, 'output'):
                output = cookie.output()
                arl = _extract_arl_from_text(output)
                if arl:
                    return arl
        except Exception:
            continue

    return None


def check_cookies(window):
    shared = {"arl": "", "last_url": "", "closed": False}

    def remember_url():
        try:
            shared["last_url"] = window.get_current_url() or shared["last_url"]
        except Exception:
            pass

    def remember_arl(value):
        if value and not shared["arl"]:
            shared["arl"] = str(value).strip()

    def on_request(request):
        headers = getattr(request, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() == "cookie":
                remember_arl(_extract_arl_from_text(value))
                break

    def on_response(response):
        headers = getattr(response, "headers", {}) or {}
        for name, value in headers.items():
            if str(name).lower() == "set-cookie":
                remember_arl(_extract_arl_from_text(value))

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

    for _ in range(90):
        remember_url()

        if shared["arl"]:
            print("ARL_FOUND:" + shared["arl"], flush=True)
            try:
                window.destroy()
            except Exception:
                pass
            return

        try:
            cookies = window.get_cookies()
            remember_arl(_extract_arl_from_objects(cookies))
        except Exception:
            pass

        if not shared["arl"]:
            try:
                cookie_text = window.evaluate_js("document.cookie")
                remember_arl(_extract_arl_from_text(cookie_text))
            except Exception:
                pass

        if shared["arl"]:
            print("ARL_FOUND:" + shared["arl"], flush=True)
            try:
                window.destroy()
            except Exception:
                pass
            return

        if shared["closed"]:
            print(f"ARL_ABORTED:{shared['last_url']}", flush=True)
            return

        time.sleep(1)

    print(f"ARL_TIMEOUT:{shared['last_url']}", flush=True)
    try:
        window.destroy()
    except Exception:
        pass

if __name__ == '__main__':
    window = webview.create_window(
        title=WINDOW_TITLE,
        url='https://www.deezer.com/login',
        width=450,
        height=600,
        resizable=False,
        on_top=True,
        focus=True,
    )
    webview.start(check_cookies, window, private_mode=False)
