"""
app.py — PlayTransfer
Servidor Flask principal — OAuth + API REST + worker threads
"""
import base64, hashlib, json, os, subprocess, tempfile, time, threading, traceback, secrets, urllib.parse
import requests as req_lib
from flask import Flask, render_template, request, jsonify, redirect, session, abort
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "playtransfer_dev_secret_" + secrets.token_hex(8))
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def no_cache(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

# ── Estado em memória ─────────────────────────────────────────────────────────
jobs: dict[str, dict] = {}
sessions: dict[str, dict] = {}
oauth_states: dict[str, dict] = {}   # state → {role, platform, ...}
tidal_logins: dict[str, dict] = {}
youtube_logins: dict[str, dict] = {}
deezer_browser_guided: dict[str, dict] = {}

BASE_URL = os.getenv("BASE_URL", "").strip()

INFO_PAGES = {
    "sobre": {
        "title": "Sobre o PlayTransfer",
        "subtitle": "Uma interface simples para mover playlists entre serviços compatíveis.",
        "sections": [
            {
                "title": "O que o app faz",
                "body": "O PlayTransfer lê uma playlist de origem, procura as faixas no serviço de destino e cria uma nova playlist com os itens encontrados.",
            },
            {
                "title": "Modelo atual",
                "body": "Nesta versão, o app suporta transferências entre Spotify, Deezer, YouTube Music, SoundCloud, Apple Music, TIDAL e Amazon Music, com autenticações específicas por plataforma.",
            },
        ],
    },
    "privacidade": {
        "title": "Privacidade",
        "subtitle": "Como os dados de sessão são usados nesta aplicação.",
        "sections": [
            {
                "title": "Credenciais",
                "body": "Os dados de conexão usados durante a sessão ficam somente em memória do processo Flask atual e servem apenas para ler ou criar playlists enquanto o app estiver aberto.",
            },
            {
                "title": "Escopo",
                "body": "O app utiliza apenas as informações necessárias para autenticar o usuário, ler playlists e criar a playlist de destino quando a plataforma suporta essa operação.",
            },
        ],
    },
    "termos": {
        "title": "Termos de uso",
        "subtitle": "Orientações básicas para uso responsável do app.",
        "sections": [
            {
                "title": "Uso permitido",
                "body": "Use o PlayTransfer apenas com contas, cookies, tokens e playlists que você controla ou tem permissão para acessar.",
            },
            {
                "title": "Dependências externas",
                "body": "A disponibilidade dos fluxos depende das APIs, cookies de sessão e políticas de cada plataforma de streaming, que podem mudar ao longo do tempo.",
            },
        ],
    },
    "contato": {
        "title": "Contato",
        "subtitle": "Canal principal para dúvidas sobre a instância atual do app.",
        "sections": [
            {
                "title": "Canal configurado",
                "body": f"E-mail configurado: {os.getenv('CONTACT_EMAIL', 'defina CONTACT_EMAIL no .env para exibir um canal oficial aqui.')}",
            },
            {
                "title": "Suporte",
                "body": "Se você estiver ajustando esta instância localmente, o caminho mais rápido é revisar o .env e os módulos dentro de services/ para completar as integrações da sua conta.",
            },
        ],
    },
}

# ── Plataformas ───────────────────────────────────────────────────────────────
PLATFORMS = {
    "spotify":    {"name": "Spotify",       "color": "#1DB954", "can_read": True, "can_write": True, "auth": "oauth_or_cookie"},
    "deezer":     {"name": "Deezer",        "color": "#A238FF", "can_read": True, "can_write": True, "auth": "oauth_or_cookie"},
    "youtube":    {"name": "YouTube Music", "color": "#FF0033", "can_read": True, "can_write": True, "auth": "oauth_or_cookie"},
    "soundcloud": {"name": "SoundCloud",    "color": "#FF5500", "can_read": True, "can_write": True, "auth": "token_or_public"},
    "apple":      {"name": "Apple Music",   "color": "#F5F5F7", "can_read": True, "can_write": True, "auth": "public_or_token"},
    "tidal":      {"name": "TIDAL",         "color": "#F5F5F7", "can_read": True, "can_write": True, "auth": "device_code"},
    "amazon":     {"name": "Amazon Music",  "color": "#00A8E1", "can_read": True, "can_write": True, "auth": "api_key_token"},
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def new_job() -> tuple[str, dict]:
    job_id = os.urandom(8).hex()
    job = {"events": [], "lock": threading.Lock(), "done": False}
    jobs[job_id] = job
    return job_id, job

def emit(job: dict, event: dict):
    with job["lock"]:
        job["events"].append(event)


def create_session(platform: str, **data) -> str:
    sid = os.urandom(8).hex()
    sessions[sid] = {"platform": platform, **data}
    return sid


def get_base_url() -> str:
    base_url = BASE_URL.rstrip("/")
    if base_url:
        return base_url
    return request.host_url.rstrip("/")


def build_callback_url(platform: str) -> str:
    return f"{get_base_url()}/auth/{platform}/callback"


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def generate_spotify_pkce_pair() -> tuple[str, str]:
    verifier = _base64url(os.urandom(64))
    challenge = _base64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINAS
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/oauth-callback")
def oauth_callback_page():
    """Página de callback OAuth — fecha popup e notifica janela principal."""
    return render_template("oauth_callback.html")


@app.route("/<page_slug>")
def info_page(page_slug: str):
    page = INFO_PAGES.get(page_slug)
    if not page:
        abort(404)
    return render_template("info_page.html", page=page)

# ═════════════════════════════════════════════════════════════════════════════
# SPOTIFY OAUTH
# Registre o app em: https://developer.spotify.com/dashboard
# Redirect URI recomendada: http://127.0.0.1:5001/auth/spotify/callback
# O app usa PKCE quando houver apenas SPOTIFY_CLIENT_ID.
# ═════════════════════════════════════════════════════════════════════════════
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_SCOPES        = (
    "playlist-read-private "
    "playlist-read-collaborative "
    "playlist-modify-private "
    "playlist-modify-public "
    "user-read-private "
    "user-read-email"
)

@app.route("/auth/spotify")
def auth_spotify():
    if not SPOTIFY_CLIENT_ID:
        return redirect("/oauth-callback?error=spotify_oauth_not_configured")

    role = request.args.get("role", "src")
    state = secrets.token_urlsafe(16)
    oauth_meta = {"role": role, "platform": "spotify"}

    params = {
        "client_id":     SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  build_callback_url("spotify"),
        "scope":         SPOTIFY_SCOPES,
        "state":         state,
        "show_dialog":   "false",
    }

    if not SPOTIFY_CLIENT_SECRET:
        code_verifier, code_challenge = generate_spotify_pkce_pair()
        oauth_meta["code_verifier"] = code_verifier
        params["code_challenge_method"] = "S256"
        params["code_challenge"] = code_challenge

    oauth_states[state] = oauth_meta
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
    return redirect(url)

@app.route("/auth/spotify/callback")
def auth_spotify_callback():
    code  = request.args.get("code", "")
    state = request.args.get("state", "")
    error = request.args.get("error", "")

    if error or not code:
        return redirect(f"/oauth-callback?error={error or 'cancelled'}")

    meta = oauth_states.pop(state, None)
    if not meta or meta.get("platform") != "spotify":
        return redirect("/oauth-callback?error=invalid_state")

    role = meta.get("role", "src")
    callback_url = build_callback_url("spotify")
    token_headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url,
    }

    code_verifier = meta.get("code_verifier")
    if code_verifier:
        token_payload["client_id"] = SPOTIFY_CLIENT_ID
        token_payload["code_verifier"] = code_verifier
    else:
        if not SPOTIFY_CLIENT_SECRET:
            return redirect("/oauth-callback?error=spotify_oauth_not_configured")
        credentials = base64.b64encode(
            f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
        ).decode()
        token_headers["Authorization"] = f"Basic {credentials}"

    r = req_lib.post(
        "https://accounts.spotify.com/api/token",
        headers=token_headers,
        data=token_payload,
        timeout=10,
    )

    if r.status_code != 200:
        return redirect(f"/oauth-callback?error=token_exchange_failed")

    token_data = r.json()
    access_token = token_data.get("access_token", "")

    # Busca info do usuário
    me = req_lib.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    ).json()

    display_name = me.get("display_name", me.get("id", "Usuário Spotify"))
    avatar = (me.get("images") or [{}])[0].get("url", "")

    sid = create_session(
        "spotify",
        access_token=access_token,
        refresh_token=token_data.get("refresh_token", ""),
        display_name=display_name,
        avatar=avatar,
    )

    return redirect(f"/oauth-callback?sid={sid}&role={role}&display_name={urllib.parse.quote(display_name)}&platform=spotify")


# ═════════════════════════════════════════════════════════════════════════════
# DEEZER OAUTH
# Registre em: https://developers.deezer.com/myapps
# Redirect URI: http://localhost:5001/auth/deezer/callback
# ═════════════════════════════════════════════════════════════════════════════
DEEZER_APP_ID     = os.getenv("DEEZER_APP_ID", "")
DEEZER_SECRET_KEY = os.getenv("DEEZER_SECRET_KEY", "")

@app.route("/auth/deezer")
def auth_deezer():
    role = request.args.get("role", "src")
    state = secrets.token_urlsafe(16)
    oauth_states[state] = {"role": role, "platform": "deezer"}

    params = {
        "app_id":  DEEZER_APP_ID or "demo",
        "redirect_uri": f"{BASE_URL}/auth/deezer/callback",
        "perms":   "basic_access,manage_library",
        "state":   state,
    }
    url = "https://connect.deezer.com/oauth/auth.php?" + urllib.parse.urlencode(params)
    return redirect(url)

@app.route("/auth/deezer/callback")
def auth_deezer_callback():
    code  = request.args.get("code", "")
    state = request.args.get("state", "")
    error = request.args.get("error_reason", "")

    if error or not code:
        return redirect(f"/oauth-callback?error={error or 'cancelled'}")

    meta = oauth_states.pop(state, {})
    role = meta.get("role", "src")

    r = req_lib.get(
        "https://connect.deezer.com/oauth/access_token.php",
        params={"app_id": DEEZER_APP_ID, "secret": DEEZER_SECRET_KEY,
                "code": code, "output": "json"},
        timeout=10,
    )

    token_data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    access_token = token_data.get("access_token", "")

    if not access_token:
        # Deezer retorna texto simples com o token
        text = r.text
        if "access_token=" in text:
            access_token = text.split("access_token=")[1].split("&")[0]

    if not access_token:
        return redirect("/oauth-callback?error=token_failed")

    me = req_lib.get(
        "https://api.deezer.com/user/me",
        params={"access_token": access_token},
        timeout=10,
    ).json()

    display_name = me.get("name", "Usuário Deezer")
    avatar = me.get("picture_small", "")

    # Cria sessão ARL via token (precisamos do ARL para o GW)
    # Por ora usa sessão simplificada com o access_token para leitura
    sid = create_session(
        "deezer",
        access_token=access_token,
        deezer_user_id=me.get("id", ""),
        display_name=display_name,
        avatar=avatar,
        # dz_session e dz_api_token preenchidos depois via ARL manual se necessário
        dz_session=None,
        dz_api_token=None,
    )
    # Tenta criar sessão completa via token para poder criar playlists
    try:
        from services import deezer as dz_service
        dz_info = dz_service.session_from_oauth_token(access_token)
        sessions[sid]["dz_session"]   = dz_info["session"]
        sessions[sid]["dz_api_token"] = dz_info["api_token"]
    except Exception:
        pass

    return redirect(f"/oauth-callback?sid={sid}&role={role}&display_name={urllib.parse.quote(display_name)}&platform=deezer")


@app.route("/api/connect/spotify", methods=["POST"])
def connect_spotify_manual():
    from services import spotify

    data = request.json or {}
    raw_cookie_input = data.get("sp_dc")
    if not isinstance(raw_cookie_input, str):
        raw_cookie_input = ""
    raw_cookie_input = (raw_cookie_input or os.getenv("SPOTIFY_SP_DC", "")).strip()
    cookie_header = raw_cookie_input
    if cookie_header.lower().startswith("cookie:"):
        cookie_header = cookie_header.split(":", 1)[1].strip()

    sp_dc = raw_cookie_input
    if "sp_dc=" in sp_dc:
        sp_dc = sp_dc.split("sp_dc=", 1)[1].split(";", 1)[0].strip()

    if "sp_dc=" not in cookie_header and "sp_key=" not in cookie_header:
        cookie_header = ""

    try:
        info = spotify.validate(sp_dc=sp_dc, cookie_header=cookie_header or None)
        sid = create_session(
            "spotify",
            sp_dc=sp_dc,
            spotify_cookie_header=cookie_header,
            access_token=spotify.get_token_via_sp_dc(sp_dc=sp_dc, cookie_header=cookie_header or None),
            refresh_token="",
            display_name=info["display_name"],
            avatar=info.get("avatar", ""),
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/connect/deezer", methods=["POST"])
def connect_deezer_manual():
    from services import deezer

    data = request.json or {}
    arl = (data.get("arl") or os.getenv("DEEZER_ARL", "")).strip()
    if "arl=" in arl:
        arl = arl.split("arl=", 1)[1].split(";", 1)[0].strip()

    try:
        info = deezer.validate(arl)
        sid = create_session(
            "deezer",
            arl=arl,
            access_token="",
            display_name=info["display_name"],
            avatar="",
            dz_session=info["session"],
            dz_api_token=info["api_token"],
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ═════════════════════════════════════════════════════════════════════════════
# YOUTUBE MUSIC — cookie simplificado
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/api/connect/deezer/browser-cookie", methods=["POST"])
def connect_deezer_browser_cookie():
    from services import deezer

    try:
        found = deezer.read_saved_arl()
        return jsonify({
            "ok": True,
            "arl": found["arl"],
            "browser": found.get("browser", ""),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _run_deezer_chrome_guided_capture(role: str):
    attempt = deezer_browser_guided.setdefault(role, {})
    attempt.update({
        "status": "pending",
        "error": "",
        "arl": "",
        "step": "starting",
        "updated_at": time.time(),
    })

    js_payload = "(function(){var a=(document.cookie.match(/(?:^|;\\s*)arl=([^;]+)/)||['',''])[1];prompt('PLAYTRANSFER', a);})();void(0);"
    js_b64 = base64.b64encode(js_payload.encode("utf-8")).decode("ascii")

    ps_script = f"""
$ErrorActionPreference = 'Stop'
$wshell = New-Object -ComObject WScript.Shell
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WinApi {{
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}}
"@
$foreground = [WinApi]::GetForegroundWindow()
if ($foreground -eq [IntPtr]::Zero) {{ throw 'chrome_window_not_found' }}
[WinApi]::ShowWindowAsync($foreground, 9) | Out-Null
Start-Sleep -Milliseconds 120
[WinApi]::SetForegroundWindow($foreground) | Out-Null
$browserPid = [uint32]0
[WinApi]::GetWindowThreadProcessId($foreground, [ref]$browserPid) | Out-Null
if ($browserPid -eq 0) {{ throw 'chrome_window_not_found' }}
$null = $wshell.AppActivate([int]$browserPid)
Start-Sleep -Milliseconds 300

$wshell.SendKeys('{{ESC}}')
Start-Sleep -Milliseconds 80

Set-Clipboard -Value ''
$consoleCommand = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{js_b64}'))
Set-Clipboard -Value $consoleCommand

$wshell.SendKeys('{{F6}}')
Start-Sleep -Milliseconds 150
$wshell.SendKeys('^l')
Start-Sleep -Milliseconds 150
$wshell.SendKeys('javascript:')
Start-Sleep -Milliseconds 80
$wshell.SendKeys('^v')
Start-Sleep -Milliseconds 150
$wshell.SendKeys('{{ENTER}}')
Start-Sleep -Milliseconds 1200

Set-Clipboard -Value ''
$wshell.SendKeys('^a')
Start-Sleep -Milliseconds 80
$wshell.SendKeys('^c')
Start-Sleep -Milliseconds 250
$wshell.SendKeys('{{ESC}}')
Start-Sleep -Milliseconds 150

$capturedArl = ''
try {{
  $capturedArl = (Get-Clipboard -Raw).Trim()
}} catch {{
  $capturedArl = ''
}}

if (-not $capturedArl) {{
  throw 'missing_arl'
}}
if ($capturedArl.Contains('document.cookie') -or $capturedArl.StartsWith('javascript:')) {{
  throw 'missing_arl'
}}
Write-Output $capturedArl
"""

    attempt["step"] = "running_chrome"
    attempt["updated_at"] = time.time()

    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".ps1", encoding="utf-8") as fh:
            fh.write(ps_script)
            script_path = fh.name
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        attempt.update({
            "status": "error",
            "error": "A automacao do Chrome demorou mais do que o esperado.",
            "step": "timed_out",
            "updated_at": time.time(),
        })
        return
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        attempt.update({
            "status": "error",
            "error": f"Nao consegui automatizar o Chrome agora: {detail}",
            "step": "automation_failed",
            "updated_at": time.time(),
        })
        return
    except Exception as exc:
        attempt.update({
            "status": "error",
            "error": f"Nao consegui automatizar o Chrome agora: {exc}",
            "step": "automation_failed",
            "updated_at": time.time(),
        })
        return
    finally:
        try:
            if 'script_path' in locals() and os.path.exists(script_path):
                os.remove(script_path)
        except Exception:
            pass

    captured_arl = (completed.stdout or "").strip()
    if captured_arl and len(captured_arl) > 20:
        attempt.update({
            "status": "captured",
            "error": "",
            "arl": captured_arl,
            "step": "captured",
            "updated_at": time.time(),
        })
        return

    attempt.update({
        "status": "error",
        "error": "missing_arl",
        "step": "no_capture",
        "updated_at": time.time(),
    })


@app.route("/api/connect/deezer/browser-guided/start", methods=["POST"])
def connect_deezer_browser_guided_start():
    data = request.json or {}
    role = str(data.get("role") or "dest").strip() or "dest"
    deezer_browser_guided[role] = {
        "status": "pending",
        "error": "",
        "arl": "",
        "step": "queued",
        "updated_at": time.time(),
    }
    threading.Thread(target=_run_deezer_chrome_guided_capture, args=(role,), daemon=True).start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/connect/deezer/browser-guided/status")
def connect_deezer_browser_guided_status():
    role = str(request.args.get("role") or "dest").strip() or "dest"
    data = deezer_browser_guided.get(role) or {
        "status": "idle",
        "error": "",
        "arl": "",
        "step": "idle",
        "updated_at": 0,
    }
    return jsonify({
        "ok": True,
        "status": data.get("status", "idle"),
        "error": data.get("error", ""),
        "arl": data.get("arl", ""),
        "step": data.get("step", "idle"),
        "updated_at": data.get("updated_at", 0),
    })


@app.route("/api/connect/deezer/browser-guided/capture")
def connect_deezer_browser_guided_capture():
    role = str(request.args.get("role") or "dest").strip() or "dest"
    arl = str(request.args.get("arl") or "").strip()
    error = str(request.args.get("error") or "").strip()

    current = deezer_browser_guided.setdefault(role, {})
    if arl:
        current.update({
            "status": "captured",
            "error": "",
            "arl": arl,
            "step": "captured",
            "updated_at": time.time(),
        })
    else:
        current.update({
            "status": "error",
            "error": error or "missing_arl",
            "arl": "",
            "step": "capture_failed",
            "updated_at": time.time(),
        })

    return ("", 204)


@app.route("/api/connect/youtube", methods=["POST"])
def connect_youtube():
    from services import youtube_music
    data = request.json or {}
    headers_raw = data.get("headers_raw", "").strip()
    try:
        info = youtube_music.validate(headers_raw)
        sid = create_session(
            "youtube",
            headers_path=info["headers_path"],
            display_name=info["display_name"],
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ═════════════════════════════════════════════════════════════════════════════
# SOUNDCLOUD — sem auth
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/api/connect/youtube/auto/start", methods=["POST"])
def connect_youtube_auto_start():
    from services import youtube_music

    try:
        login = youtube_music.start_oauth_login()
        login_id = os.urandom(8).hex()
        youtube_logins[login_id] = {**login, "started_at": time.time()}
        return jsonify({
            "ok": True,
            "pending": True,
            "login_id": login_id,
            "verification_url": login.get("verification_url", ""),
            "verification_url_complete": login.get("verification_url_complete", ""),
            "user_code": login.get("user_code", ""),
            "interval": login.get("interval", 5),
            "expires_in": login.get("expires_in", 1800),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/connect/youtube/auto/finish", methods=["POST"])
def connect_youtube_auto_finish():
    from services import youtube_music

    data = request.json or {}
    login_id = (data.get("login_id") or "").strip()
    login = youtube_logins.get(login_id)

    if not login:
        return jsonify({"ok": False, "error": "O login do YouTube Music expirou. Abra novamente."})

    try:
        info = youtube_music.poll_oauth_login(login)
        if info.get("pending"):
            return jsonify({
                "ok": False,
                "pending": True,
                "retry_after_ms": info.get("retry_after_ms", 4000),
            })
        sid = create_session(
            "youtube",
            oauth_path=info["oauth_path"],
            display_name=info["display_name"],
        )
        youtube_logins.pop(login_id, None)
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/connect/soundcloud", methods=["POST"])
def connect_soundcloud():
    from services import soundcloud

    data = request.json or {}
    role = data.get("role", "src")
    access_token = (data.get("access_token") or os.getenv("SOUNDCLOUD_ACCESS_TOKEN", "")).strip()

    try:
        if role == "dest" and not access_token:
            raise ValueError("Para usar SoundCloud como destino, informe um access token.")

        info = soundcloud.validate(access_token or None)
        sid = create_session(
            "soundcloud",
            access_token=access_token,
            display_name=info["display_name"],
            avatar=info.get("avatar", ""),
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/connect/apple", methods=["POST"])
def connect_apple():
    from services import apple_music

    data = request.json or {}
    role = data.get("role", "src")
    developer_token = (data.get("developer_token") or os.getenv("APPLE_MUSIC_DEVELOPER_TOKEN", "")).strip()
    music_user_token = (data.get("music_user_token") or os.getenv("APPLE_MUSIC_USER_TOKEN", "")).strip()
    storefront = (data.get("storefront") or os.getenv("APPLE_MUSIC_STOREFRONT", "us")).strip().lower() or "us"

    try:
        if role == "src" and not (developer_token and music_user_token):
            sid = create_session("apple", display_name="Apple Music (pública)", storefront=storefront)
            return jsonify({"ok": True, "sid": sid, "display_name": "Apple Music (pública)"})

        info = apple_music.validate(developer_token, music_user_token, storefront)
        sid = create_session(
            "apple",
            developer_token=developer_token,
            music_user_token=music_user_token,
            storefront=info.get("storefront", storefront),
            display_name=info["display_name"],
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ═════════════════════════════════════════════════════════════════════════════
# PREVIEW & TRANSFER
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/api/connect/amazon", methods=["POST"])
def connect_amazon():
    from services import amazon_music

    data = request.json or {}
    api_key = (data.get("api_key") or os.getenv("AMAZON_MUSIC_API_KEY", "")).strip()
    access_token = (data.get("access_token") or os.getenv("AMAZON_MUSIC_ACCESS_TOKEN", "")).strip()
    country_code = (data.get("country_code") or os.getenv("AMAZON_MUSIC_COUNTRY_CODE", "US")).strip().upper() or "US"

    try:
        info = amazon_music.validate(api_key, access_token, country_code)
        sid = create_session(
            "amazon",
            api_key=api_key,
            access_token=access_token,
            country_code=country_code,
            display_name=info["display_name"],
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/connect/tidal/start", methods=["POST"])
def connect_tidal_start():
    from services import tidal

    try:
        tidal_session, login, future = tidal.start_device_login()
        login_id = os.urandom(8).hex()
        tidal_logins[login_id] = {
            "session": tidal_session,
            "future": future,
            "started_at": time.time(),
            "expires_in": login.expires_in,
        }
        return jsonify({
            "ok": True,
            "login_id": login_id,
            "verification_uri": login.verification_uri,
            "verification_uri_complete": login.verification_uri_complete,
            "user_code": login.user_code,
            "expires_in": login.expires_in,
            "interval": login.interval,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/connect/tidal/poll/<login_id>")
def connect_tidal_poll(login_id):
    from services import tidal

    pending = tidal_logins.get(login_id)
    if not pending:
        return jsonify({"ok": False, "error": "Login do TIDAL não encontrado ou expirado."}), 404

    future = pending["future"]
    if not future.done():
        if time.time() > pending["started_at"] + pending["expires_in"] + 10:
            tidal_logins.pop(login_id, None)
            return jsonify({"ok": False, "error": "Login do TIDAL expirou."})
        return jsonify({"ok": False, "pending": True})

    try:
        success = future.result()
        if not success:
            raise ValueError("O TIDAL não concluiu a autenticação.")

        tidal_session = pending["session"]
        info = tidal.validate(tidal_session)
        sid = create_session(
            "tidal",
            tidal_session=tidal_session,
            access_token=getattr(tidal_session, "access_token", ""),
            refresh_token=getattr(tidal_session, "refresh_token", ""),
            token_type=getattr(tidal_session, "token_type", "Bearer"),
            display_name=info["display_name"],
        )
        tidal_logins.pop(login_id, None)
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        tidal_logins.pop(login_id, None)
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/platforms")
def api_platforms():
    # Indica se OAuth está configurado
    p = {key: {**value} for key, value in PLATFORMS.items()}
    p["spotify"]["oauth_configured"] = bool(SPOTIFY_CLIENT_ID)
    p["spotify"]["oauth_mode"] = "pkce" if (SPOTIFY_CLIENT_ID and not SPOTIFY_CLIENT_SECRET) else "server"
    p["deezer"]["oauth_configured"]  = bool(DEEZER_APP_ID and DEEZER_SECRET_KEY)
    try:
        from services import youtube_music
        p["youtube"]["oauth_configured"] = youtube_music.oauth_configured()
        p["youtube"]["oauth_mode"] = "device_code" if p["youtube"]["oauth_configured"] else "manual"
    except Exception:
        p["youtube"]["oauth_configured"] = False
        p["youtube"]["oauth_mode"] = "manual"
    return jsonify(p)

@app.route("/api/preview", methods=["POST"])
def api_preview():
    data = request.json or {}
    platform = data.get("platform", "")
    url = data.get("url", "").strip()
    sid = data.get("sid", "")
    try:
        nome, tracks = _read_playlist(platform, url, sid)
        return jsonify({"ok": True, "nome": nome, "total": len(tracks), "tracks": tracks[:20]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

def _read_playlist(platform: str, url: str, sid: str) -> tuple[str, list[dict]]:
    sess = sessions.get(sid, {})

    if platform == "spotify":
        from services import spotify
        access_token = sess.get("access_token")
        sp_dc = sess.get("sp_dc", "")
        cookie_header = sess.get("spotify_cookie_header", "")
        return spotify.read_playlist(
            url,
            access_token=access_token,
            sp_dc=sp_dc,
            cookie_header=cookie_header,
        )

    elif platform == "deezer":
        from services import deezer
        return deezer.read_playlist(url)

    elif platform == "youtube":
        from services import youtube_music
        return youtube_music.read_playlist(url)

    elif platform == "soundcloud":
        from services import soundcloud
        return soundcloud.read_playlist(url, access_token=sess.get("access_token"))

    elif platform == "apple":
        from services import apple_music
        return apple_music.read_playlist(url)

    elif platform == "tidal":
        from services import tidal
        tidal_session = sess.get("tidal_session")
        if not tidal_session:
            raise ValueError("Sessão do TIDAL não encontrada. Conecte o TIDAL.")
        return tidal.read_playlist(url, tidal_session)

    elif platform == "amazon":
        from services import amazon_music
        return amazon_music.read_playlist(url, sess.get("api_key", ""), sess.get("access_token", ""))

    else:
        raise ValueError(f"Plataforma '{platform}' ainda não suportada como origem.")

@app.route("/api/transfer", methods=["POST"])
def api_transfer():
    data = request.json or {}
    job_id, job = new_job()
    threading.Thread(target=run_transfer, args=(job, data), daemon=True).start()
    return jsonify({"job_id": job_id})

def run_transfer(job: dict, data: dict):
    src_platform  = data.get("src_platform", "")
    src_url       = data.get("src_url", "")
    src_sid       = data.get("src_sid", "")
    dest_platform = data.get("dest_platform", "")
    dest_sid      = data.get("dest_sid", "")

    try:
        emit(job, {"type": "status", "msg": "Lendo playlist..."})
        nome, musicas = _read_playlist(src_platform, src_url, src_sid)
        emit(job, {"type": "playlist_read", "nome": nome, "total": len(musicas)})

        ids_encontrados, falhas = [], []
        dest_url = ""

        if dest_platform == "deezer":
            from services import deezer

            dest_sess = sessions.get(dest_sid, {})
            dz_session = dest_sess.get("dz_session")
            dz_api_token = dest_sess.get("dz_api_token")
            if not dz_session:
                raise ValueError("Sessão do Deezer não encontrada. Reconecte o Deezer.")

            playlist_id = deezer.create_playlist(dz_session, dz_api_token, nome, "Transferida via PlayTransfer")
            emit(job, {"type": "status", "msg": "Buscando músicas no Deezer..."})

            for i, m in enumerate(musicas):
                track_id = deezer.search_track(dz_session, m["titulo"], m["artista"])
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.10)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                deezer.add_tracks(dz_session, dz_api_token, playlist_id, ids_encontrados)

            dest_url = f"https://www.deezer.com/br/playlist/{playlist_id}"

        elif dest_platform == "youtube":
            from services import youtube_music

            dest_sess = sessions.get(dest_sid, {})
            auth_path = dest_sess.get("oauth_path") or dest_sess.get("headers_path")
            if not auth_path:
                raise ValueError("Sessão do YouTube Music não encontrada. Reconecte.")

            ytm = youtube_music.get_ytm_instance(auth_path)
            playlist_id = youtube_music.create_playlist(ytm, nome, "Transferida via PlayTransfer")
            emit(job, {"type": "status", "msg": "Buscando músicas no YouTube Music..."})

            for i, m in enumerate(musicas):
                track_id = youtube_music.search_track(ytm, m["titulo"], m["artista"])
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.15)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                youtube_music.add_tracks(ytm, playlist_id, ids_encontrados)

            dest_url = f"https://music.youtube.com/playlist?list={playlist_id}"

        elif dest_platform == "spotify":
            from services import spotify

            dest_sess = sessions.get(dest_sid, {})
            access_token = dest_sess.get("access_token")
            sp_dc = dest_sess.get("sp_dc")
            cookie_header = dest_sess.get("spotify_cookie_header", "")
            if not access_token and (sp_dc or cookie_header):
                access_token = spotify.get_token_via_sp_dc(sp_dc=sp_dc, cookie_header=cookie_header)
            if not access_token:
                raise ValueError("Sessão do Spotify não encontrada. Reconecte o Spotify.")

            playlist_id = spotify.create_playlist(access_token, nome, "Transferida via PlayTransfer")
            emit(job, {"type": "status", "msg": "Buscando músicas no Spotify..."})

            for i, m in enumerate(musicas):
                track_id = spotify.search_track(access_token, m["titulo"], m["artista"], m.get("album", ""))
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.10)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                spotify.add_tracks(access_token, playlist_id, ids_encontrados)

            dest_url = f"https://open.spotify.com/playlist/{playlist_id}"

        elif dest_platform == "soundcloud":
            from services import soundcloud

            dest_sess = sessions.get(dest_sid, {})
            access_token = dest_sess.get("access_token", "")
            if not access_token:
                raise ValueError("Sessão do SoundCloud não encontrada. Informe um access token.")

            created = soundcloud.create_playlist(access_token, nome, "Transferida via PlayTransfer")
            playlist_id = created["id"]
            dest_url = created["url"]
            emit(job, {"type": "status", "msg": "Buscando músicas no SoundCloud..."})

            for i, m in enumerate(musicas):
                track_id = soundcloud.search_track(access_token, m["titulo"], m["artista"], m.get("album", ""))
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.10)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                soundcloud.add_tracks(access_token, playlist_id, ids_encontrados)

        elif dest_platform == "apple":
            from services import apple_music

            dest_sess = sessions.get(dest_sid, {})
            developer_token = dest_sess.get("developer_token", "")
            music_user_token = dest_sess.get("music_user_token", "")
            storefront = dest_sess.get("storefront", "us")
            if not developer_token or not music_user_token:
                raise ValueError("Sessão da Apple Music não encontrada. Informe developer token e music user token.")

            playlist_id = apple_music.create_playlist(
                developer_token,
                music_user_token,
                nome,
                "Transferida via PlayTransfer",
            )
            dest_url = f"https://music.apple.com/{storefront}/library/playlist/{playlist_id}"
            emit(job, {"type": "status", "msg": "Buscando músicas na Apple Music..."})

            for i, m in enumerate(musicas):
                track_id = apple_music.search_track(
                    developer_token,
                    storefront,
                    m["titulo"],
                    m["artista"],
                    m.get("album", ""),
                )
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.10)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                apple_music.add_tracks(developer_token, music_user_token, playlist_id, ids_encontrados)

        elif dest_platform == "tidal":
            from services import tidal

            dest_sess = sessions.get(dest_sid, {})
            tidal_session = dest_sess.get("tidal_session")
            if not tidal_session:
                raise ValueError("Sessão do TIDAL não encontrada. Conecte o TIDAL.")

            created = tidal.create_playlist(tidal_session, nome, "Transferida via PlayTransfer")
            playlist_id = created["id"]
            dest_url = created["url"]
            emit(job, {"type": "status", "msg": "Buscando músicas no TIDAL..."})

            for i, m in enumerate(musicas):
                track_id = tidal.search_track(tidal_session, m["titulo"], m["artista"], m.get("album", ""))
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.10)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                tidal.add_tracks(tidal_session, playlist_id, ids_encontrados)

        elif dest_platform == "amazon":
            from services import amazon_music

            dest_sess = sessions.get(dest_sid, {})
            api_key = dest_sess.get("api_key", "")
            access_token = dest_sess.get("access_token", "")
            if not api_key or not access_token:
                raise ValueError("Sessão do Amazon Music não encontrada. Informe API key e access token.")

            created = amazon_music.create_playlist(api_key, access_token, nome, "Transferida via PlayTransfer")
            playlist_id = created["id"]
            dest_url = created["url"]
            emit(job, {"type": "status", "msg": "Buscando músicas no Amazon Music..."})

            for i, m in enumerate(musicas):
                track_id = amazon_music.search_track(
                    api_key,
                    access_token,
                    m["titulo"],
                    m["artista"],
                    m.get("album", ""),
                )
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.10)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                amazon_music.add_tracks(api_key, access_token, playlist_id, ids_encontrados)

        else:
            raise ValueError(f"Destino '{dest_platform}' ainda não suportado.")

        emit(job, {"type": "done", "encontradas": len(ids_encontrados),
                   "nao_encontradas": len(falhas), "total": len(musicas),
                   "playlist_nome": nome, "playlist_url": dest_url, "falhas": falhas[:20]})

    except Exception as e:
        emit(job, {"type": "error", "message": str(e)})
    finally:
        with job["lock"]:
            job["done"] = True

@app.route("/api/job/<job_id>")
def api_job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    from_idx = int(request.args.get("from", 0))
    with job["lock"]:
        events = job["events"][from_idx:]
        done   = job["done"]
    return jsonify({"events": events, "done": done and not events, "total_events": from_idx + len(events)})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "1.2.0", "app": "PlayTransfer"})

if __name__ == "__main__":
    import webbrowser
    port = int(os.getenv("PORT", 5001))
    def _open():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()
    print(f"\nPlayTransfer rodando em http://localhost:{port}\n")
    app.run(debug=False, port=port, threaded=True)
