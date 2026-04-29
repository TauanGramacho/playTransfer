"""
app.py — PlayTransfer
Servidor Flask principal — OAuth + API REST + worker threads
"""
import base64, hashlib, json, os, re, subprocess, sys, tempfile, time, threading, traceback, secrets, urllib.parse
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
youtube_guided_logins: dict[str, dict] = {}
spotify_browser_guided: dict[str, dict] = {}
deezer_browser_guided: dict[str, dict] = {}
apple_browser_guided: dict[str, dict] = {}
soundcloud_browser_guided: dict[str, dict] = {}

BASE_URL = os.getenv("BASE_URL", "").strip()
APPLE_MUSIC_BOOTSTRAP_CACHE = {"token": "", "expires_at": 0.0, "source": ""}
APPLE_MUSIC_BOOTSTRAP_LOCK = threading.Lock()

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


def normalize_spotify_base_url(base_url: str) -> str:
    raw = (base_url or "").strip().rstrip("/")
    if not raw:
        raw = get_base_url()
    try:
        parsed = urllib.parse.urlparse(raw)
        if parsed.hostname in {"localhost", "0.0.0.0"}:
            netloc = "127.0.0.1"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return urllib.parse.urlunparse((
                parsed.scheme or "http",
                netloc,
                parsed.path.rstrip("/"),
                "",
                "",
                "",
            )).rstrip("/")
    except Exception:
        pass
    return raw


def get_spotify_base_url() -> str:
    """Spotify requires loopback redirects to use an IP literal, not localhost."""
    return normalize_spotify_base_url(get_base_url())


def build_callback_url(platform: str) -> str:
    base_url = get_spotify_base_url() if platform == "spotify" else get_base_url()
    return f"{base_url}/auth/{platform}/callback"


def normalize_external_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        return raw
    if re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/|$)", raw):
        return f"https://{raw}"
    return raw


@app.route("/api/config/spotify-redirect")
def spotify_redirect_config():
    return jsonify({
        "ok": True,
        "base_url": get_spotify_base_url(),
        "redirect_uri": build_callback_url("spotify"),
    })


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


def _write_env_values(updates: dict[str, str]) -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines: list[str] = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as env_file:
            lines = env_file.readlines()

    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            output.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}\n")
            seen.add(key)
        else:
            output.append(line)

    if output and output[-1].strip():
        output.append("\n")

    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as env_file:
        env_file.writelines(output)


def _looks_like_spotify_client_id(value: str) -> bool:
    return 20 <= len(value) <= 80 and all(char.isalnum() for char in value)


def _looks_like_jwt(value: str) -> bool:
    parts = [part for part in str(value or "").strip().split(".") if part]
    return len(parts) == 3


def _decode_jwt_payload(token: str) -> dict:
    parts = [part for part in str(token or "").strip().split(".") if part]
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _jwt_expiry(token: str) -> float:
    payload = _decode_jwt_payload(token)
    try:
        return float(payload.get("exp") or 0)
    except Exception:
        return 0.0


def _token_has_min_ttl(token: str, min_seconds: int = 120) -> bool:
    if not _looks_like_jwt(token):
        return False
    expiry = _jwt_expiry(token)
    return expiry > (time.time() + min_seconds)


def _extract_apple_web_developer_token(script_text: str) -> str:
    candidates = re.findall(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", script_text or "")
    for token in candidates:
        payload = _decode_jwt_payload(token)
        issuer = str(payload.get("iss") or "")
        roots = payload.get("root_https_origin") or []
        roots_blob = " ".join(str(item) for item in roots)
        if issuer == "AMPWebPlay" or "apple.com" in roots_blob:
            if _token_has_min_ttl(token, min_seconds=0):
                return token
    return ""


def _fetch_apple_web_developer_token() -> str:
    session = req_lib.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    page_url = "https://music.apple.com/us/browse"
    response = session.get(page_url, headers=headers, timeout=20)
    response.raise_for_status()

    script_paths = re.findall(r'<script[^>]+src="([^"]+)"', response.text or "", flags=re.IGNORECASE)
    script_urls: list[str] = []
    for path in script_paths:
        lower = path.lower()
        if "/assets/" not in lower or "index" not in lower or ".js" not in lower:
            continue
        full_url = urllib.parse.urljoin(page_url, path)
        if full_url not in script_urls:
            script_urls.append(full_url)

    # Prefer the modern bundle first, then try the legacy one as fallback.
    script_urls.sort(key=lambda url: ("legacy" in url.lower(), url))

    for script_url in script_urls[:6]:
        script_response = session.get(script_url, headers=headers, timeout=20)
        script_response.raise_for_status()
        token = _extract_apple_web_developer_token(script_response.text)
        if token:
            return token

    raise RuntimeError("apple_musickit_not_configured")


def get_apple_music_developer_token(force_refresh: bool = False) -> tuple[str, str]:
    saved_token = os.environ.get("APPLE_MUSIC_DEVELOPER_TOKEN", "").strip()
    if saved_token and _token_has_min_ttl(saved_token):
        return saved_token, "env"

    with APPLE_MUSIC_BOOTSTRAP_LOCK:
        cached_token = str(APPLE_MUSIC_BOOTSTRAP_CACHE.get("token") or "").strip()
        if cached_token and not force_refresh and _token_has_min_ttl(cached_token):
            return cached_token, str(APPLE_MUSIC_BOOTSTRAP_CACHE.get("source") or "apple_web")

        token = _fetch_apple_web_developer_token()
        APPLE_MUSIC_BOOTSTRAP_CACHE.update({
            "token": token,
            "expires_at": _jwt_expiry(token),
            "source": "apple_web",
        })
        return token, "apple_web"


@app.route("/api/config/spotify-oauth", methods=["POST"])
def configure_spotify_oauth():
    global SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, BASE_URL

    data = request.json or {}
    client_id = str(data.get("client_id") or "").strip()
    client_secret = str(data.get("client_secret") or "").strip()
    base_url = normalize_spotify_base_url(str(data.get("base_url") or "").strip() or get_base_url())

    if not _looks_like_spotify_client_id(client_id):
        return jsonify({
            "ok": False,
            "error": "Cole o Client ID do app Spotify. Ele fica no Spotify Developer Dashboard.",
        })

    if any(char in client_secret for char in "\r\n"):
        return jsonify({"ok": False, "error": "Client Secret invalido."})

    try:
        _write_env_values({
            "BASE_URL": base_url,
            "SPOTIFY_CLIENT_ID": client_id,
            "SPOTIFY_CLIENT_SECRET": client_secret,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Nao consegui salvar no .env: {exc}"})

    BASE_URL = base_url
    SPOTIFY_CLIENT_ID = client_id
    SPOTIFY_CLIENT_SECRET = client_secret
    os.environ["BASE_URL"] = base_url
    os.environ["SPOTIFY_CLIENT_ID"] = client_id
    os.environ["SPOTIFY_CLIENT_SECRET"] = client_secret

    return jsonify({
        "ok": True,
        "oauth_configured": True,
        "oauth_mode": "pkce" if not client_secret else "server",
        "oauth_redirect_uri": build_callback_url("spotify"),
    })


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
        "show_dialog":   "true",
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
        try:
            print(f"[Spotify OAuth] token exchange failed: {r.status_code} {r.text[:300]}")
        except Exception:
            pass
        return redirect(f"/oauth-callback?error=token_exchange_failed")

    token_data = r.json()
    access_token = token_data.get("access_token", "")

    # Busca info do usuário
    me_response = req_lib.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if me_response.status_code != 200:
        try:
            print(f"[Spotify OAuth] /v1/me failed: {me_response.status_code} {me_response.text[:300]}")
        except Exception:
            pass
        return redirect("/oauth-callback?error=spotify_profile_failed")

    me = me_response.json()

    display_name = me.get("display_name", me.get("id", "Usuário Spotify"))
    avatar = (me.get("images") or [{}])[0].get("url", "")

    sid = create_session(
        "spotify",
        access_token=access_token,
        refresh_token=token_data.get("refresh_token", ""),
        auth_source="oauth",
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

# Amazon Music Web API (closed beta)
# Requer Security Profile ID habilitado pela Amazon Music + Login With Amazon.
AMAZON_MUSIC_API_KEY = os.getenv("AMAZON_MUSIC_API_KEY", "").strip()
AMAZON_LWA_CLIENT_ID = os.getenv("AMAZON_LWA_CLIENT_ID", "").strip()
AMAZON_LWA_CLIENT_SECRET = os.getenv("AMAZON_LWA_CLIENT_SECRET", "").strip()
AMAZON_MUSIC_COUNTRY_CODE = os.getenv("AMAZON_MUSIC_COUNTRY_CODE", "US").strip().upper() or "US"
AMAZON_MUSIC_SCOPES = os.getenv(
    "AMAZON_MUSIC_SCOPES",
    "profile music::catalog music::library",
).strip()


def amazon_music_oauth_configured() -> bool:
    return bool(AMAZON_MUSIC_API_KEY and AMAZON_LWA_CLIENT_ID)


def amazon_music_redirect_uri() -> str:
    return build_callback_url("amazon")


def _amazon_oauth_error_redirect(error: str, role: str = "dest"):
    return redirect(f"/oauth-callback?error={urllib.parse.quote(error)}&platform=amazon&role={urllib.parse.quote(role)}")

@app.route("/auth/deezer")
def auth_deezer():
    if not DEEZER_APP_ID:
        return redirect("/oauth-callback?error=deezer_oauth_not_configured")

    role = request.args.get("role", "src")
    state = secrets.token_urlsafe(16)
    oauth_states[state] = {"role": role, "platform": "deezer"}

    params = {
        "app_id":  DEEZER_APP_ID,
        "redirect_uri": build_callback_url("deezer"),
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

    meta = oauth_states.pop(state, None)
    if not meta or meta.get("platform") != "deezer":
        return redirect("/oauth-callback?error=invalid_state")

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


@app.route("/api/config/amazon-music")
def amazon_music_config():
    return jsonify({
        "ok": True,
        "api_key_configured": bool(AMAZON_MUSIC_API_KEY),
        "oauth_configured": amazon_music_oauth_configured(),
        "country_code": AMAZON_MUSIC_COUNTRY_CODE,
        "scopes": AMAZON_MUSIC_SCOPES,
        "oauth_redirect_uri": amazon_music_redirect_uri(),
        "requires_amazon_enablement": True,
    })


@app.route("/api/config/amazon-music", methods=["POST"])
def configure_amazon_music():
    global AMAZON_MUSIC_API_KEY, AMAZON_LWA_CLIENT_ID, AMAZON_LWA_CLIENT_SECRET
    global AMAZON_MUSIC_COUNTRY_CODE, AMAZON_MUSIC_SCOPES, BASE_URL

    data = request.json or {}
    api_key = str(data.get("api_key") or "").strip()
    client_id = str(data.get("client_id") or "").strip()
    client_secret = str(data.get("client_secret") or "").strip()
    country_code = str(data.get("country_code") or "US").strip().upper() or "US"
    scopes = str(data.get("scopes") or AMAZON_MUSIC_SCOPES).strip() or AMAZON_MUSIC_SCOPES
    base_url = normalize_spotify_base_url(str(data.get("base_url") or "").strip() or get_base_url())

    if not api_key.startswith("amzn1.application."):
        return jsonify({"ok": False, "error": "Cole o Security Profile ID da Amazon. Ele comeca com amzn1.application."})
    if not client_id.startswith("amzn1.application-oa2-client."):
        return jsonify({"ok": False, "error": "Cole o Client ID do Login With Amazon. Ele comeca com amzn1.application-oa2-client."})
    if any(char in client_secret for char in "\r\n"):
        return jsonify({"ok": False, "error": "Client Secret da Amazon invalido."})

    try:
        _write_env_values({
            "BASE_URL": base_url,
            "AMAZON_MUSIC_API_KEY": api_key,
            "AMAZON_LWA_CLIENT_ID": client_id,
            "AMAZON_LWA_CLIENT_SECRET": client_secret,
            "AMAZON_MUSIC_COUNTRY_CODE": country_code,
            "AMAZON_MUSIC_SCOPES": scopes,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Nao consegui salvar no .env: {exc}"})

    BASE_URL = base_url
    AMAZON_MUSIC_API_KEY = api_key
    AMAZON_LWA_CLIENT_ID = client_id
    AMAZON_LWA_CLIENT_SECRET = client_secret
    AMAZON_MUSIC_COUNTRY_CODE = country_code
    AMAZON_MUSIC_SCOPES = scopes
    os.environ["BASE_URL"] = base_url
    os.environ["AMAZON_MUSIC_API_KEY"] = api_key
    os.environ["AMAZON_LWA_CLIENT_ID"] = client_id
    os.environ["AMAZON_LWA_CLIENT_SECRET"] = client_secret
    os.environ["AMAZON_MUSIC_COUNTRY_CODE"] = country_code
    os.environ["AMAZON_MUSIC_SCOPES"] = scopes

    return jsonify({
        "ok": True,
        "oauth_configured": True,
        "oauth_redirect_uri": amazon_music_redirect_uri(),
        "country_code": country_code,
        "scopes": scopes,
    })



# ─── Estado da sessão Amazon (cookie-based, igual ao Deezer) ────────────────
AMAZON_SESSION_COOKIES: dict = {}
amazon_session_attempt: dict = {}
amazon_connections: dict = {}        # {"src": {...cookies}, "dest": {...cookies}}


def _has_amazon_auth_cookie(cookies: dict) -> bool:
    return any(str(name).startswith("at-") for name, value in (cookies or {}).items() if value)


def _has_amazon_session_cookie(cookies: dict) -> bool:
    return bool(
        (cookies or {}).get("_access_token")
        or _has_amazon_auth_cookie(cookies)
        or any(str(name).startswith("ubid-") for name, value in (cookies or {}).items() if value)
    )


@app.route("/api/capture/amazon-session", methods=["POST"])
def start_amazon_session_capture():
    global amazon_session_attempt
    if amazon_session_attempt.get("status") == "running":
        return jsonify({"ok": True, "already_running": True})

    role = (request.json or {}).get("role", "dest")
    amazon_session_attempt = {
        "status": "running",
        "step": "opening_webview",
        "role": role,
        "display_name": "",
        "error": "",
        "updated_at": time.time(),
    }

    def _run_capture():
        global amazon_session_attempt, amazon_connections
        try:
            python_exe  = sys.executable
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "amazon_webview.py")
            completed   = subprocess.run(
                [python_exe, script_path],
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            amazon_session_attempt.update({"status": "error", "error": "A janela de login demorou muito.", "step": "timed_out", "updated_at": time.time()})
            return
        except Exception as exc:
            amazon_session_attempt.update({"status": "error", "error": str(exc), "step": "spawn_failed", "updated_at": time.time()})
            return

        output = completed.stdout or ""
        cookies: dict = {}
        aborted = False

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("AMAZON_SESSION_FOUND:"):
                try:
                    cookies = json.loads(line.split("AMAZON_SESSION_FOUND:", 1)[1])
                except Exception:
                    pass
            elif "ABORTED" in line:
                aborted = True

        if _has_amazon_auth_cookie(cookies):
            api_calls_raw = cookies.pop("_api_calls", "[]")
            try:
                api_calls = json.loads(api_calls_raw) if isinstance(api_calls_raw, str) else (api_calls_raw or [])
                if api_calls:
                    print("AMAZON_API_CALLS:" + json.dumps(api_calls[:20]), flush=True)
            except Exception:
                api_calls = []

            display_name = "Amazon Music"
            try:
                from services import amazon_music_session as _amz_session
                _amz_session._refresh_metadata(cookies, force=True)
                if not cookies.get("_access_token"):
                    raise ValueError("amazon_session_missing_access_token")
                info = _amz_session.validate(cookies)
                display_name = info.get("display_name", "Amazon Music")
            except Exception:
                if not cookies.get("_access_token"):
                    amazon_session_attempt.update({
                        "status": "error",
                        "error": "A Amazon abriu o login, mas a sessao completa ainda nao ficou disponivel. Tente conectar novamente.",
                        "step": "missing_access_token",
                        "updated_at": time.time(),
                    })
                    return
                ubid_value = next((str(value) for name, value in cookies.items() if str(name).startswith("ubid-") and value), "")
                display_name = f"Amazon Music ({ubid_value[:8]}...)" if ubid_value else "Amazon Music"

            _role = amazon_session_attempt.get("role", "dest")
            amazon_connections[_role] = cookies
            amazon_connections[_role]["_api_calls"] = api_calls
            amazon_session_attempt.update({
                "status": "done",
                "step": "captured",
                "display_name": display_name,
                "updated_at": time.time(),
            })
        elif any(str(name).startswith("ubid-") for name, value in cookies.items() if value):
            # Logado mas at-main não capturado (HttpOnly não exposto pelo webview)
            amazon_session_attempt.update({"status": "error", "error": "Login detectado mas token de acesso não capturado. Tente novamente — o app vai tentar extrair automaticamente.", "step": "partial", "updated_at": time.time()})
        elif aborted:
            amazon_session_attempt.update({"status": "error", "error": "Janela fechada antes do login.", "step": "aborted", "updated_at": time.time()})
        else:
            amazon_session_attempt.update({"status": "error", "error": "Não consegui capturar a sessão. Faça login completo na janela que abre.", "step": "not_found", "updated_at": time.time()})


    threading.Thread(target=_run_capture, daemon=True).start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/capture/amazon-session/status")
def amazon_session_capture_status():
    role = request.args.get("role", "dest")
    connected = _has_amazon_session_cookie(amazon_connections.get(role, {}))
    return jsonify({"ok": True, "connected": connected, **amazon_session_attempt})


@app.route("/api/connect/amazon-session", methods=["DELETE"])
def disconnect_amazon_session():
    role = (request.json or {}).get("role", "dest")
    amazon_connections.pop(role, None)
    return jsonify({"ok": True})


@app.route("/api/debug/amazon-api-calls")
def debug_amazon_api_calls():
    """Retorna as chamadas de API interceptadas pelo webview do Amazon Music."""
    cookies = amazon_connections.get("dest", {})
    api_calls = cookies.get("_api_calls", [])
    return jsonify({
        "ok": True,
        "count": len(api_calls),
        "api_calls": api_calls,
        "has_at_main": _has_amazon_auth_cookie(cookies),
    })




@app.route("/api/debug/amazon-test")
def debug_amazon_test():
    import requests as _req
    cookies = amazon_connections.get("dest", {})
    if not cookies:
        return jsonify({"error": "Sem cookies capturados"})

    region = cookies.get("_region", "com")
    csrf   = cookies.get("_csrf_token", "") or cookies.get("csrf-main", "") or cookies.get("session-token", "")
    clean  = {k: v for k, v in cookies.items() if not k.startswith("_")}
    base   = f"https://music.amazon.{region}"
    hdrs   = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": f"{base}/",
        "Origin": base,
        "anti-csrftoken-a2z": csrf,
    }

    tests = {}
    # GET endpoints — busca + user info + playlists
    get_paths = [
        "/EU/v1/search?keywords=test&size=1&nextToken=&musicTerritory=US&locale=en_US",
        "/EU/v1/playlists?size=10",
        "/EU/v1/user/playlists?size=10",
        "/EU/v1/mymusic/playlists?size=10",
        "/EU/v1/mymusic/tracks?size=1",
        "/EU/v1/catalog/search?keywords=test&size=1",
        "/EU/v1/catalog/tracks?ids=B09X5RTFFB",
        "/EU/v1/catalog/albums?ids=B09X5RTFFB",
        "/v1/catalog/search?keywords=test&size=1",
        "/v1/search?keywords=test&size=1",
        "/api/v1/search?q=test",
        "/musicv1/search?keywords=test",
    ]
    for path in get_paths:
        url = base + path
        try:
            r = _req.get(url, headers=hdrs, cookies=clean, timeout=8, allow_redirects=False)
            tests[f"GET {path}"] = {"status": r.status_code, "snippet": r.text[:150]}
        except Exception as e:
            tests[f"GET {path}"] = {"error": str(e)}

    # POST para criar playlist
    post_paths = [
        "/EU/v1/playlists",
        "/EU/v1/user/playlists",
        "/EU/v1/mymusic/playlists",
        "/v1/playlists",
    ]
    for path in post_paths:
        url = base + path
        try:
            r = _req.post(url, headers=hdrs, cookies=clean, json={"title": "Test", "description": "test", "visibility": "PRIVATE"}, timeout=8, allow_redirects=False)
            tests[f"POST {path}"] = {"status": r.status_code, "snippet": r.text[:150]}
        except Exception as e:
            tests[f"POST {path}"] = {"error": str(e)}

    return jsonify({
        "region": region,
        "base": base,
        "cookie_keys": list(clean.keys()),
        "has_at_main": _has_amazon_auth_cookie(clean),
        "csrf_present": bool(csrf),
        "tests": tests,
    })


@app.route("/auth/amazon")
def auth_amazon():
    if not amazon_music_oauth_configured():
        return _amazon_oauth_error_redirect("amazon_music_api_access_required", request.args.get("role", "dest"))

    role = request.args.get("role", "dest")
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = generate_spotify_pkce_pair()
    oauth_states[state] = {
        "role": role,
        "platform": "amazon",
        "code_verifier": code_verifier,
    }

    params = {
        "client_id": AMAZON_LWA_CLIENT_ID,
        "scope": AMAZON_MUSIC_SCOPES,
        "response_type": "code",
        "redirect_uri": amazon_music_redirect_uri(),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return redirect("https://www.amazon.com/ap/oa?" + urllib.parse.urlencode(params))


@app.route("/auth/amazon/callback")
def auth_amazon_callback():
    from services import amazon_music

    code = request.args.get("code", "")
    state = request.args.get("state", "")
    error = request.args.get("error", "")

    meta = oauth_states.pop(state, None)
    role = (meta or {}).get("role", request.args.get("role", "dest"))

    if error or not code:
        return _amazon_oauth_error_redirect(error or "login_cancelled", role)
    if not meta or meta.get("platform") != "amazon":
        return _amazon_oauth_error_redirect("invalid_state", role)

    token_payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": amazon_music_redirect_uri(),
        "client_id": AMAZON_LWA_CLIENT_ID,
        "code_verifier": meta.get("code_verifier", ""),
    }
    if AMAZON_LWA_CLIENT_SECRET:
        token_payload["client_secret"] = AMAZON_LWA_CLIENT_SECRET

    token_response = req_lib.post(
        "https://api.amazon.com/auth/o2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=token_payload,
        timeout=15,
    )
    if token_response.status_code != 200:
        try:
            print(f"[Amazon OAuth] token exchange failed: {token_response.status_code} {token_response.text[:300]}")
        except Exception:
            pass
        return _amazon_oauth_error_redirect("amazon_lwa_token_exchange_failed", role)

    token_data = token_response.json()
    access_token = str(token_data.get("access_token") or "").strip()
    if not access_token:
        return _amazon_oauth_error_redirect("amazon_lwa_token_exchange_failed", role)

    try:
        info = amazon_music.validate(AMAZON_MUSIC_API_KEY, access_token, AMAZON_MUSIC_COUNTRY_CODE)
    except Exception as exc:
        message = str(exc)
        try:
            print(f"[Amazon OAuth] validation failed: {message[:300]}")
        except Exception:
            pass
        lowered = message.lower()
        if "permissao" in lowered or "beta fechado" in lowered or "403" in lowered:
            return _amazon_oauth_error_redirect("amazon_music_api_not_enabled", role)
        if "401" in lowered or "credenciais" in lowered:
            return _amazon_oauth_error_redirect("amazon_music_auth_failed", role)
        return _amazon_oauth_error_redirect("amazon_music_validation_failed", role)

    sid = create_session(
        "amazon",
        api_key=AMAZON_MUSIC_API_KEY,
        access_token=access_token,
        refresh_token=token_data.get("refresh_token", ""),
        country_code=info.get("country_code", AMAZON_MUSIC_COUNTRY_CODE),
        auth_source="lwa",
        display_name=info["display_name"],
    )
    display_name = urllib.parse.quote(info["display_name"])
    return redirect(f"/oauth-callback?sid={sid}&role={role}&display_name={display_name}&platform=amazon")


@app.route("/api/connect/spotify", methods=["POST"])
def connect_spotify_manual():
    from services import spotify

    data = request.json or {}
    role = str(data.get("role") or "").strip().lower()
    if role not in {"src", "dest"}:
        role = ""

    access_token = data.get("access_token")
    if not isinstance(access_token, str):
        access_token = ""
    access_token = access_token.strip()

    client_token = data.get("client_token") or data.get("spotify_client_token") or ""
    if not isinstance(client_token, str):
        client_token = ""
    client_token = client_token.strip()

    raw_cookie_input = data.get("sp_dc")
    if not isinstance(raw_cookie_input, str):
        raw_cookie_input = ""
    raw_cookie_input = (raw_cookie_input or os.getenv("SPOTIFY_SP_DC", "")).strip()

    cookie_header = data.get("cookie_header") or data.get("spotify_cookie_header") or raw_cookie_input
    if not isinstance(cookie_header, str):
        cookie_header = ""
    cookie_header = cookie_header.strip()
    if cookie_header.lower().startswith("cookie:"):
        cookie_header = cookie_header.split(":", 1)[1].strip()

    sp_dc = raw_cookie_input
    if "sp_dc=" in sp_dc:
        sp_dc = sp_dc.split("sp_dc=", 1)[1].split(";", 1)[0].strip()
    if not sp_dc and "sp_dc=" in cookie_header:
        sp_dc = cookie_header.split("sp_dc=", 1)[1].split(";", 1)[0].strip()

    if "sp_dc=" not in cookie_header and "sp_key=" not in cookie_header:
        cookie_header = ""

    if role == "dest":
        if not SPOTIFY_CLIENT_ID:
            return jsonify({"ok": False, "error": "spotify_oauth_required_for_destination"})
        return jsonify({"ok": False, "error": "spotify_destination_requires_oauth_reconnect"})

    if access_token:
        trusted_webview = bool(data.get("trusted_webview"))
        webview_display_name = str(data.get("display_name") or "").strip()
        if trusted_webview and webview_display_name:
            info = {
                "display_name": webview_display_name,
                "avatar": str(data.get("avatar") or "").strip(),
            }
        else:
            try:
                info = spotify.validate_access_token(access_token, client_token=client_token)
                if not info.get("display_name"):
                    info["display_name"] = "Conta Spotify"
            except spotify.SpotifyRateLimitedError as exc:
                wait_seconds = int(exc.retry_after or 60)
                return jsonify({
                    "ok": False,
                    "error": (
                        "Spotify ainda esta pausando essa sessao. "
                        f"Aguarde cerca de {wait_seconds}s e conecte o Spotify novamente antes de transferir."
                    ),
                })
            except Exception as e:
                if trusted_webview and (sp_dc or cookie_header):
                    print(f"[Spotify] Webview token invalido ({e}), tentando via sp_dc...")
                    try:
                        fresh_token = spotify.get_token_via_sp_dc(sp_dc=sp_dc, cookie_header=cookie_header or None)
                        if fresh_token:
                            access_token = fresh_token
                            info = spotify.validate_access_token(access_token, client_token=client_token)
                        else:
                            return jsonify({"ok": False, "error": "Token do Spotify capturado e invalido e o sp_dc nao gerou um novo. Tente reconectar."})
                    except Exception as e2:
                        return jsonify({"ok": False, "error": f"Nao foi possivel confirmar a sessao do Spotify: {e2}"})
                else:
                    return jsonify({"ok": False, "error": str(e)})

        try:
            sid = create_session(
                "spotify",
                sp_dc=sp_dc,
                spotify_cookie_header=cookie_header,
                spotify_client_token=client_token,
                access_token=access_token,
                refresh_token="",
                auth_source="webview" if trusted_webview else "manual",
                display_name=info["display_name"],
                avatar=info.get("avatar", ""),
            )
            return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    try:
        info = spotify.validate(sp_dc=sp_dc, cookie_header=cookie_header or None)
        sid = create_session(
            "spotify",
            sp_dc=sp_dc,
            spotify_cookie_header=cookie_header,
            spotify_client_token=client_token,
            access_token=spotify.get_token_via_sp_dc(sp_dc=sp_dc, cookie_header=cookie_header or None),
            refresh_token="",
            display_name=info["display_name"],
            avatar=info.get("avatar", ""),
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
@app.route("/api/connect/spotify/browser-cookie", methods=["POST"])
def connect_spotify_browser_cookie():
    from services import spotify

    try:
        found = spotify.read_saved_spotify_cookie()
        return jsonify({
            "ok": True,
            "sp_dc": found.get("sp_dc", ""),
            "cookie_header": found.get("cookie_header", ""),
            "browser": found.get("browser", ""),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _run_spotify_guided_capture(role: str):
    attempt = spotify_browser_guided.setdefault(role, {})
    attempt.update({
        "status": "pending",
        "error": "",
        "access_token": "",
        "client_token": "",
        "sp_dc": "",
        "cookie_header": "",
        "step": "running_webview",
        "updated_at": time.time(),
    })

    try:
        python_exe = sys.executable
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spotify_webview.py")

        completed = subprocess.run(
            [python_exe, script_path],
            capture_output=True,
            text=True,
            timeout=150,
        )
    except subprocess.TimeoutExpired:
        attempt.update({
            "status": "error",
            "error": "A janela de login do Spotify demorou muito e foi encerrada.",
            "step": "timed_out",
            "updated_at": time.time(),
        })
        return
    except Exception as exc:
        attempt.update({
            "status": "error",
            "error": str(exc),
            "step": "spawn_failed",
            "updated_at": time.time(),
        })
        return

    payload = {}
    aborted = False
    timed_out = False
    login_rejected = False

    for raw_line in (completed.stdout or "").splitlines():
        line = raw_line.strip()
        if line.startswith("SPOTIFY_FOUND:"):
            try:
                payload = json.loads(line.split("SPOTIFY_FOUND:", 1)[1].strip())
            except Exception:
                payload = {}
        elif line.startswith("SPOTIFY_ABORTED:"):
            aborted = True
        elif line.startswith("SPOTIFY_TIMEOUT:"):
            timed_out = True
        elif line.startswith("SPOTIFY_LOGIN_REJECTED:"):
            login_rejected = True

    access_token = str(payload.get("access_token") or "").strip()
    client_token = str(payload.get("client_token") or "").strip()
    sp_dc = str(payload.get("sp_dc") or "").strip()
    cookie_header = str(payload.get("cookie_header") or "").strip()

    if access_token or sp_dc or cookie_header:
        attempt.update({
            "status": "captured",
            "error": "",
            "access_token": access_token,
            "client_token": client_token,
            "sp_dc": sp_dc,
            "cookie_header": cookie_header,
            "display_name": str(payload.get("display_name") or "").strip(),
            "avatar": str(payload.get("avatar") or "").strip(),
            "step": "captured",
            "updated_at": time.time(),
        })
        return

    if aborted:
        attempt.update({
            "status": "error",
            "error": "Voce fechou a janela do Spotify antes de concluir o login.",
            "step": "aborted",
            "updated_at": time.time(),
        })
        return

    if login_rejected:
        attempt.update({
            "status": "error",
            "error": (
                "O Spotify recusou o login nessa janela. "
                "Essa conta pode usar Google/Apple/Facebook ou o Spotify pode estar bloqueando navegador embutido."
            ),
            "step": "login_rejected",
            "updated_at": time.time(),
        })
        return

    if timed_out:
        attempt.update({
            "status": "error",
            "error": "A janela do Spotify demorou muito e foi encerrada.",
            "step": "timed_out",
            "updated_at": time.time(),
        })
        return

    attempt.update({
        "status": "error",
        "error": "missing_spotify_token",
        "step": "no_capture",
        "updated_at": time.time(),
    })


@app.route("/api/connect/spotify/browser-guided/start", methods=["POST"])
def connect_spotify_browser_guided_start():
    data = request.json or {}
    role = str(data.get("role") or "dest").strip() or "dest"

    if role == "dest" and not SPOTIFY_CLIENT_ID:
        spotify_browser_guided[role] = {
            "status": "error",
            "error": "spotify_oauth_required_for_destination",
            "access_token": "",
            "client_token": "",
            "sp_dc": "",
            "cookie_header": "",
            "step": "oauth_required",
            "updated_at": time.time(),
        }
        return jsonify({"ok": False, "error": "spotify_oauth_required_for_destination"})

    spotify_browser_guided[role] = {
        "status": "pending",
        "error": "",
        "access_token": "",
        "client_token": "",
        "sp_dc": "",
        "cookie_header": "",
        "step": "queued",
        "updated_at": time.time(),
    }
    threading.Thread(target=_run_spotify_guided_capture, args=(role,), daemon=True).start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/connect/spotify/browser-guided/status")
def connect_spotify_browser_guided_status():
    role = str(request.args.get("role") or "dest").strip() or "dest"
    data = spotify_browser_guided.get(role) or {
        "status": "idle",
        "error": "",
        "access_token": "",
        "client_token": "",
        "sp_dc": "",
        "cookie_header": "",
        "step": "idle",
        "updated_at": 0,
    }
    return jsonify({
        "ok": True,
        "status": data.get("status", "idle"),
        "error": data.get("error", ""),
        "access_token": data.get("access_token", ""),
        "client_token": data.get("client_token", ""),
        "sp_dc": data.get("sp_dc", ""),
        "cookie_header": data.get("cookie_header", ""),
        "step": data.get("step", "idle"),
        "updated_at": data.get("updated_at", 0),
    })


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
        "step": "running_webview",
        "updated_at": time.time(),
    })

    try:
        # Pega o caminho do ambiente virtual se existir, se não usa sys.executable
        python_exe = sys.executable
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deezer_webview.py")
        
        completed = subprocess.run(
            [python_exe, script_path],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        attempt.update({
            "status": "error",
            "error": "A janela de login demorou muito e foi encerrada.",
            "step": "timed_out",
            "updated_at": time.time(),
        })
        return
    except Exception as exc:
        attempt.update({
            "status": "error",
            "error": f"Erro abrindo a janela de login: {exc}",
            "step": "automation_failed",
            "updated_at": time.time(),
        })
        return

    output = completed.stdout or ""
    error_output = (completed.stderr or "").strip()
    if completed.returncode not in (0, None):
        attempt.update({
            "status": "error",
            "error": error_output or output.strip() or "Falha ao abrir a janela de login do Deezer.",
            "step": "automation_failed",
            "updated_at": time.time(),
        })
        return

    if "ARL_TIMEOUT" in output or "ARL_ABORTED" in output:
        timeout_detail = output.strip()
        attempt.update({
            "status": "error",
            "error": timeout_detail or "A janela de login do Deezer foi fechada antes da captura terminar.",
            "step": "timed_out",
            "updated_at": time.time(),
        })
        return

    arl = ""
    for line in output.splitlines():
        if line.startswith("ARL_FOUND:"):
            arl = line.split("ARL_FOUND:")[1].strip()
            # As vezes pywebview retorna como dict/json, limpando possivel aspas:
            arl = arl.strip("'").strip('"')

    if arl and len(arl) > 20:
        attempt.update({
            "status": "captured",
            "error": "",
            "arl": arl,
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


def _run_apple_guided_capture(role: str):
    attempt = apple_browser_guided.setdefault(role, {})
    attempt.update({
        "status": "pending",
        "error": "",
        "music_user_token": "",
        "storefront": "",
        "cookie_header": "",
        "itfe": "",
        "authorized": False,
        "step": "opening_browser",
        "updated_at": time.time(),
    })

    try:
        import webbrowser as _webbrowser
        _webbrowser.open("https://music.apple.com/br/new")
    except Exception as exc:
        attempt.update({
            "step": "browser_open_failed",
            "error": f"Nao consegui abrir o Apple Music no navegador: {exc}",
            "updated_at": time.time(),
        })

    last_error = ""
    deadline = time.time() + 150
    while time.time() < deadline:
        try:
            from services import apple_music
            payload = apple_music.read_saved_apple_session()
        except Exception as exc:
            last_error = str(exc)
            payload = {}

        music_user_token = str(payload.get("music_user_token") or "").strip()
        storefront = str(payload.get("storefront") or "br").strip().lower() or "br"
        cookie_header = str(payload.get("cookie_header") or "").strip()
        itfe = str(payload.get("itfe") or "").strip()
        authorized = bool(music_user_token or cookie_header)

        if not (music_user_token or cookie_header):
            attempt.update({
                "status": "pending",
                "error": "",
                "step": "waiting_browser_login",
                "updated_at": time.time(),
            })
            time.sleep(2)
            continue

        try:
            developer_token, _ = get_apple_music_developer_token()
            storefront = apple_music.fetch_storefront(
                developer_token,
                music_user_token=music_user_token,
                cookie_header=cookie_header,
                itfe=itfe,
            ) or storefront
            apple_music.validate(
                developer_token,
                music_user_token,
                storefront,
                cookie_header=cookie_header,
                itfe=itfe,
            )
        except Exception as exc:
            last_error = str(exc)
            if "apple_music_cloud_library_required" in last_error or "cloudlibrary" in last_error.lower():
                attempt.update({
                    "status": "error",
                    "error": f"apple_music_validation_failed:{exc}",
                    "music_user_token": music_user_token,
                    "storefront": storefront,
                    "cookie_header": cookie_header,
                    "itfe": itfe,
                    "authorized": authorized,
                    "step": "cloud_library_required",
                    "updated_at": time.time(),
                })
                return

            attempt.update({
                "status": "pending",
                "error": "",
                "music_user_token": music_user_token,
                "storefront": storefront,
                "cookie_header": cookie_header,
                "itfe": itfe,
                "authorized": authorized,
                "step": "waiting_valid_browser_session",
                "updated_at": time.time(),
            })
            time.sleep(2)
            continue

        attempt.update({
            "status": "captured",
            "error": "",
            "music_user_token": music_user_token,
            "storefront": storefront,
            "cookie_header": cookie_header,
            "itfe": itfe,
            "authorized": authorized,
            "step": "captured",
            "updated_at": time.time(),
        })
        return

    attempt.update({
        "status": "error",
        "error": last_error or "apple_browser_session_not_found",
        "step": "timed_out",
        "updated_at": time.time(),
    })


@app.route("/api/connect/apple/browser-guided/start", methods=["POST"])
def connect_apple_browser_guided_start():
    data = request.json or {}
    role = str(data.get("role") or "dest").strip() or "dest"
    apple_browser_guided[role] = {
        "status": "error",
        "error": "apple_browser_cookie_flow_disabled",
        "music_user_token": "",
        "storefront": "",
        "cookie_header": "",
        "itfe": "",
        "authorized": False,
        "step": "disabled",
        "updated_at": time.time(),
    }
    return jsonify({
        "ok": False,
        "error": "Atualize a pagina e tente novamente. O login da Apple Music agora usa uma janela oficial do MusicKit, sem leitura do Chrome.",
    })


@app.route("/api/connect/apple/browser-guided/status")
def connect_apple_browser_guided_status():
    role = str(request.args.get("role") or "dest").strip() or "dest"
    data = apple_browser_guided.get(role) or {
        "status": "idle",
        "error": "",
        "music_user_token": "",
        "storefront": "",
        "cookie_header": "",
        "itfe": "",
        "authorized": False,
        "step": "idle",
        "updated_at": 0,
    }
    return jsonify({
        "ok": True,
        "status": data.get("status", "idle"),
        "error": data.get("error", ""),
        "music_user_token": data.get("music_user_token", ""),
        "storefront": data.get("storefront", ""),
        "cookie_header": data.get("cookie_header", ""),
        "itfe": data.get("itfe", ""),
        "authorized": data.get("authorized", False),
        "step": data.get("step", "idle"),
        "updated_at": data.get("updated_at", 0),
    })


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


@app.route("/api/connect/youtube/guided/start", methods=["POST"])
def connect_youtube_guided_start():
    from services import youtube_music

    try:
        login = youtube_music.start_guided_login()
        login_id = os.urandom(8).hex()
        youtube_guided_logins[login_id] = {**login, "started_at": time.time()}
        return jsonify({
            "ok": True,
            "pending": True,
            "login_id": login_id,
            "browser_name": login.get("browser_name", ""),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/connect/youtube/guided/finish", methods=["POST"])
def connect_youtube_guided_finish():
    from services import youtube_music

    data = request.json or {}
    login_id = (data.get("login_id") or "").strip()
    login = youtube_guided_logins.get(login_id)

    if not login:
        return jsonify({"ok": False, "error": "A janela guiada do YouTube Music expirou. Abra novamente."})

    try:
        info = youtube_music.finish_guided_login(login)
        sid = create_session(
            "youtube",
            headers_path=info["headers_path"],
            display_name=info["display_name"],
        )
        youtube_music.cleanup_guided_login(login, close_browser=True)
        youtube_guided_logins.pop(login_id, None)
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        message = str(e)
        if (
            "Ainda nao consegui confirmar sua conta do YouTube Music" in message
            or "Nao consegui confirmar a sessao do Google nessa janela." in message
            or "Nao consegui confirmar essa conta do YouTube Music." in message
        ):
            return jsonify({
                "ok": False,
                "pending": True,
                "retry_after_ms": 2500,
            })

        youtube_music.cleanup_guided_login(login, close_browser=False)
        youtube_guided_logins.pop(login_id, None)
        return jsonify({"ok": False, "error": message})


@app.route("/api/connect/soundcloud", methods=["POST"])
def connect_soundcloud():
    from services import soundcloud

    data = request.json or {}
    role = data.get("role", "src")
    access_token = (data.get("access_token") or os.getenv("SOUNDCLOUD_ACCESS_TOKEN", "")).strip()

    try:
        if role == "src" and not access_token:
            sid = create_session("soundcloud", access_token="", display_name="SoundCloud (publico)", avatar="")
            return jsonify({"ok": True, "sid": sid, "display_name": "SoundCloud (publico)"})

        if role == "dest" and not access_token:
            raise ValueError("soundcloud_login_required")

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


def _run_soundcloud_guided_capture(role: str):
    import subprocess, sys, json as _json
    attempt = soundcloud_browser_guided.setdefault(role, {})
    attempt.update({
        "status": "running",
        "error": "",
        "sid": "",
        "display_name": "",
        "avatar": "",
        "step": "opening_webview",
        "updated_at": time.time(),
    })

    try:
        webview_script = os.path.join(os.path.dirname(__file__), "soundcloud_webview.py")
        proc = subprocess.run(
            [sys.executable, webview_script],
            capture_output=True, text=True, timeout=180,
        )
        output = (proc.stdout or "") + (proc.stderr or "")

        access_token = ""
        aborted = False

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("SC_TOKEN_FOUND:"):
                access_token = line.split("SC_TOKEN_FOUND:", 1)[1].strip()
            elif "ABORTED" in line or "TIMEOUT" in line:
                aborted = True

        if access_token:
            from services import soundcloud
            info = soundcloud.validate(access_token)
            sid = create_session(
                "soundcloud",
                access_token=access_token,
                display_name=info["display_name"],
                avatar=info.get("avatar", ""),
            )
            attempt.update({
                "status": "done",
                "error": "",
                "sid": sid,
                "display_name": info["display_name"],
                "avatar": info.get("avatar", ""),
                "step": "captured",
                "updated_at": time.time(),
            })
        elif aborted:
            attempt.update({
                "status": "error",
                "error": "Janela fechada antes do login. Abra novamente e faça login no SoundCloud.",
                "step": "aborted",
                "updated_at": time.time(),
            })
        else:
            attempt.update({
                "status": "error",
                "error": "Não consegui capturar o token do SoundCloud. Faça login completo na janela que abre.",
                "step": "not_found",
                "updated_at": time.time(),
            })

    except subprocess.TimeoutExpired:
        attempt.update({
            "status": "error",
            "error": "Tempo esgotado aguardando login no SoundCloud. Tente novamente.",
            "step": "timed_out",
            "updated_at": time.time(),
        })
    except Exception as exc:
        attempt.update({
            "status": "error",
            "error": f"Erro ao abrir a janela de login do SoundCloud: {exc}",
            "step": "error",
            "updated_at": time.time(),
        })




@app.route("/api/capture/soundcloud-session", methods=["POST"])
def start_soundcloud_session_capture():
    data = request.json or {}
    role = str(data.get("role") or "dest").strip() or "dest"
    current = soundcloud_browser_guided.get(role) or {}
    if current.get("status") == "running" and time.time() - float(current.get("updated_at") or 0) < 180:
        return jsonify({"ok": True, "already_running": True})

    soundcloud_browser_guided[role] = {
        "status": "running",
        "error": "",
        "sid": "",
        "display_name": "",
        "avatar": "",
        "step": "queued",
        "updated_at": time.time(),
    }
    threading.Thread(target=_run_soundcloud_guided_capture, args=(role,), daemon=True).start()
    return jsonify({"ok": True, "started": True})


@app.route("/api/capture/soundcloud-session/status")
def soundcloud_session_capture_status():
    role = str(request.args.get("role") or "dest").strip() or "dest"
    data = soundcloud_browser_guided.get(role) or {
        "status": "idle",
        "error": "",
        "sid": "",
        "display_name": "",
        "avatar": "",
        "step": "idle",
        "updated_at": 0,
    }
    return jsonify({
        "ok": True,
        "connected": bool(data.get("sid")),
        "status": data.get("status", "idle"),
        "error": data.get("error", ""),
        "sid": data.get("sid", ""),
        "display_name": data.get("display_name", ""),
        "avatar": data.get("avatar", ""),
        "step": data.get("step", "idle"),
        "updated_at": data.get("updated_at", 0),
    })


@app.route("/api/connect/apple", methods=["POST"])
def connect_apple():
    from services import apple_music

    data = request.json or {}
    role = data.get("role", "src")
    developer_token = (data.get("developer_token") or os.environ.get("APPLE_MUSIC_DEVELOPER_TOKEN", "")).strip()
    music_user_token = (data.get("music_user_token") or os.environ.get("APPLE_MUSIC_USER_TOKEN", "")).strip()
    storefront = (data.get("storefront") or os.environ.get("APPLE_MUSIC_STOREFRONT", "us")).strip().lower() or "us"
    cookie_header = (data.get("cookie_header") or "").strip()
    itfe = (data.get("itfe") or "").strip()

    try:
        if not developer_token:
            developer_token, _ = get_apple_music_developer_token()

        if role == "src" and not (developer_token and music_user_token) and not cookie_header:
            sid = create_session("apple", display_name="Apple Music (pública)", storefront=storefront)
            return jsonify({"ok": True, "sid": sid, "display_name": "Apple Music (pública)"})

        if not developer_token:
            raise ValueError("apple_musickit_not_configured")
        if not music_user_token and not cookie_header:
            raise ValueError("apple_music_user_token_required")

        info = apple_music.validate(
            developer_token,
            music_user_token,
            storefront,
            cookie_header=cookie_header,
            itfe=itfe,
        )
        sid = create_session(
            "apple",
            developer_token=developer_token,
            music_user_token=music_user_token,
            storefront=info.get("storefront", storefront),
            cookie_header=cookie_header,
            itfe=itfe,
            display_name=info["display_name"],
        )
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/config/apple-music")
def apple_music_config():
    developer_token = ""
    bootstrap_source = ""
    try:
        developer_token, bootstrap_source = get_apple_music_developer_token()
    except Exception:
        developer_token = ""
        bootstrap_source = ""
    storefront = os.environ.get("APPLE_MUSIC_STOREFRONT", "us").strip().lower() or "us"
    return jsonify({
        "ok": True,
        "configured": bool(developer_token),
        "developer_token": developer_token,
        "storefront": storefront,
        "bootstrap_source": bootstrap_source,
    })


@app.route("/api/config/apple-music", methods=["POST"])
def configure_apple_music():
    data = request.json or {}
    developer_token = str(data.get("developer_token") or "").strip()
    storefront = str(data.get("storefront") or "us").strip().lower() or "us"

    if not _looks_like_jwt(developer_token):
        return jsonify({
            "ok": False,
            "error": "Cole um developer token valido da Apple Music. Ele costuma ter tres partes separadas por ponto.",
        })

    try:
        _write_env_values({
            "APPLE_MUSIC_DEVELOPER_TOKEN": developer_token,
            "APPLE_MUSIC_STOREFRONT": storefront,
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Nao consegui salvar no .env: {exc}"})

    os.environ["APPLE_MUSIC_DEVELOPER_TOKEN"] = developer_token
    os.environ["APPLE_MUSIC_STOREFRONT"] = storefront
    APPLE_MUSIC_BOOTSTRAP_CACHE.update({
        "token": developer_token,
        "expires_at": _jwt_expiry(developer_token),
        "source": "env",
    })

    return jsonify({
        "ok": True,
        "configured": True,
        "developer_token": developer_token,
        "storefront": storefront,
    })

# ═════════════════════════════════════════════════════════════════════════════
# PREVIEW & TRANSFER
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/api/connect/amazon", methods=["POST"])
def connect_amazon():
    from services import amazon_music

    data = request.json or {}
    api_key = (data.get("api_key") or AMAZON_MUSIC_API_KEY or os.getenv("AMAZON_MUSIC_API_KEY", "")).strip()
    access_token = (data.get("access_token") or os.getenv("AMAZON_MUSIC_ACCESS_TOKEN", "")).strip()
    country_code = (data.get("country_code") or AMAZON_MUSIC_COUNTRY_CODE or os.getenv("AMAZON_MUSIC_COUNTRY_CODE", "US")).strip().upper() or "US"

    try:
        if not api_key or not access_token:
            if amazon_music_oauth_configured():
                raise ValueError("amazon_music_oauth_required")
            raise ValueError("amazon_music_api_access_required")
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
            "verification_uri": normalize_external_url(login.verification_uri),
            "verification_uri_complete": normalize_external_url(login.verification_uri_complete),
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
    p["spotify"]["oauth_redirect_uri"] = build_callback_url("spotify")
    p["deezer"]["oauth_configured"]  = bool(DEEZER_APP_ID and DEEZER_SECRET_KEY)
    p["soundcloud"]["auto_configured"] = True
    p["soundcloud"]["saved_token_configured"] = bool(os.getenv("SOUNDCLOUD_ACCESS_TOKEN", "").strip())
    apple_ready = False
    try:
        apple_ready = bool(get_apple_music_developer_token()[0])
    except Exception:
        apple_ready = False
    p["apple"]["auto_configured"] = apple_ready
    p["apple"]["installation_configured"] = p["apple"]["auto_configured"]
    p["amazon"]["oauth_configured"] = amazon_music_oauth_configured()
    p["amazon"]["oauth_redirect_uri"] = amazon_music_redirect_uri()
    p["amazon"]["api_key_configured"] = bool(AMAZON_MUSIC_API_KEY)
    p["amazon"]["country_code"] = AMAZON_MUSIC_COUNTRY_CODE
    p["amazon"]["scopes"] = AMAZON_MUSIC_SCOPES
    p["amazon"]["requires_amazon_enablement"] = True
    p["amazon"]["auto_configured"] = bool(
        AMAZON_MUSIC_API_KEY
        and (os.getenv("AMAZON_MUSIC_ACCESS_TOKEN", "").strip() or AMAZON_LWA_CLIENT_ID)
    )
    p["tidal"]["auto_configured"] = True
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
        developer_token, _ = get_apple_music_developer_token()
        storefront = sess.get("storefront") or os.environ.get("APPLE_MUSIC_STOREFRONT", "us")
        return apple_music.read_playlist(url, developer_token=developer_token, storefront=storefront)

    elif platform == "tidal":
        from services import tidal
        tidal_session = sess.get("tidal_session")
        if not tidal_session:
            raise ValueError("Sessão do TIDAL não encontrada. Conecte o TIDAL.")
        return tidal.read_playlist(url, tidal_session)

    elif platform == "amazon":
        from services import amazon_music
        from services import amazon_music_session
        session_cookies = amazon_connections.get("src") or amazon_connections.get(sid) or amazon_connections.get("dest")
        if session_cookies and _has_amazon_session_cookie(session_cookies):
            return amazon_music_session.read_playlist(url, session_cookies)
        if not (sess.get("api_key") and sess.get("access_token")):
            raise ValueError("Conecte o Amazon Music para ler essa playlist.")
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
            is_official_spotify_login = dest_sess.get("auth_source") == "oauth"
            if not is_official_spotify_login:
                if SPOTIFY_CLIENT_ID:
                    raise ValueError("spotify_destination_requires_oauth_reconnect")
                raise ValueError("spotify_oauth_required_for_destination")

            access_token = dest_sess.get("access_token")
            refresh_token = dest_sess.get("refresh_token", "")
            sp_dc = dest_sess.get("sp_dc")
            cookie_header = dest_sess.get("spotify_cookie_header", "")
            client_token = dest_sess.get("spotify_client_token", "")
            if not access_token and (sp_dc or cookie_header):
                access_token = spotify.get_token_via_sp_dc(sp_dc=sp_dc, cookie_header=cookie_header)
            if not access_token:
                raise ValueError("Sessão do Spotify não encontrada. Reconecte o Spotify.")

            token_refresh_count = 0

            def refresh_spotify_token():
                nonlocal access_token, token_refresh_count
                # Attempt 1: OAuth refresh_token (works for OAuth connections)
                if refresh_token and SPOTIFY_CLIENT_ID:
                    try:
                        fresh_token = spotify.refresh_oauth_token(
                            refresh_token,
                            client_id=SPOTIFY_CLIENT_ID,
                            client_secret=SPOTIFY_CLIENT_SECRET,
                        )
                        if fresh_token:
                            access_token = fresh_token
                            if dest_sid in sessions:
                                sessions[dest_sid]["access_token"] = fresh_token
                            token_refresh_count += 1
                            print(f"[Spotify] Token renovado via OAuth refresh (#{token_refresh_count})")
                            return True
                    except Exception as exc:
                        print(f"[Spotify] OAuth refresh falhou: {exc}")

                # Attempt 2: sp_dc cookie (works for webview/manual connections)
                if sp_dc or cookie_header:
                    try:
                        fresh_token = spotify.get_token_via_sp_dc(sp_dc=sp_dc, cookie_header=cookie_header)
                    except Exception as exc:
                        print(f"[Spotify] Nao consegui renovar token via sp_dc: {exc}")
                        return False
                    if fresh_token:
                        access_token = fresh_token
                        if dest_sid in sessions:
                            sessions[dest_sid]["access_token"] = fresh_token
                        token_refresh_count += 1
                        print(f"[Spotify] Token renovado via sp_dc (#{token_refresh_count})")
                        return True

                return False

            # Pre-refresh the token to start with a fresh one
            if sp_dc or cookie_header or (refresh_token and SPOTIFY_CLIENT_ID):
                refresh_spotify_token()

            def spotify_with_visible_wait(
                action_label,
                action,
                attempts=5,
                max_wait_seconds=75,
                max_total_wait_seconds=240,
                refresh_on_first_limit=False,
            ):
                last_error = None
                total_waited = 0
                refreshed_after_limit = False
                token_refreshed_for_expiry = False

                for attempt in range(attempts):
                    try:
                        if attempt:
                            emit(job, {"type": "status", "msg": f"Tentando {action_label} no Spotify..."})
                        return action()
                    except spotify.SpotifyTokenExpiredError as exc:
                        # Token expired (401) — try to refresh and retry
                        if not token_refreshed_for_expiry and refresh_spotify_token():
                            token_refreshed_for_expiry = True
                            emit(job, {
                                "type": "status",
                                "msg": "Sessao do Spotify renovada. Tentando de novo..."
                            })
                            continue
                        # Could not refresh — raise as user-facing error
                        raise ValueError(
                            "A sessao do Spotify expirou e nao foi possivel renovar. "
                            "Reconecte o Spotify e tente novamente."
                        ) from exc
                    except spotify.SpotifyRateLimitedError as exc:
                        last_error = exc

                        if refresh_on_first_limit and not refreshed_after_limit and refresh_spotify_token():
                            refreshed_after_limit = True
                            emit(job, {
                                "type": "status",
                                "msg": "Atualizei a sessao do Spotify. Tentando de novo..."
                            })
                            continue

                        if attempt >= attempts - 1:
                            break

                        wait_seconds = exc.retry_after
                        if wait_seconds is None:
                            wait_seconds = min(20 + (attempt * 15), max_wait_seconds)

                        wait_seconds = int(max(5, min(float(wait_seconds) + 6, max_wait_seconds)))
                        remaining_budget = max_total_wait_seconds - total_waited
                        if remaining_budget <= 0:
                            break
                        wait_seconds = min(wait_seconds, remaining_budget)

                        while wait_seconds > 0:
                            emit(job, {
                                "type": "status",
                                "msg": f"Spotify pediu uma pausa. Tentando {action_label} novamente em {wait_seconds}s..."
                            })
                            chunk = min(5, wait_seconds)
                            time.sleep(chunk)
                            total_waited += chunk
                            wait_seconds -= chunk

                if last_error:
                    raise last_error
                raise ValueError("Spotify não respondeu à tentativa de transferência.")

            emit(job, {"type": "status", "msg": "Criando playlist no Spotify..."})
            try:
                playlist_id = spotify_with_visible_wait(
                    "criar a playlist",
                    lambda: spotify.create_playlist(
                        access_token,
                        nome,
                        "Transferida via PlayTransfer",
                        client_token=client_token,
                    ),
                    attempts=6,
                    max_wait_seconds=70,
                    max_total_wait_seconds=300 if is_official_spotify_login else 240,
                    refresh_on_first_limit=True,
                )
            except spotify.SpotifyRateLimitedError as exc:
                if not is_official_spotify_login:
                    raise ValueError(
                        "O Spotify ainda esta pausando esta conta agora. "
                        "Tente novamente em alguns minutos."
                    ) from exc
                raise
            emit(job, {"type": "status", "msg": "Buscando músicas no Spotify..."})

            for i, m in enumerate(musicas):
                track_id = spotify_with_visible_wait(
                    "buscar as musicas",
                    lambda: spotify.search_track(
                        access_token,
                        m["titulo"],
                        m["artista"],
                        m.get("album", ""),
                        client_token=client_token,
                    ),
                    attempts=5,
                    max_wait_seconds=60,
                    max_total_wait_seconds=240,
                )
                if track_id:
                    ids_encontrados.append(track_id)
                else:
                    falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                time.sleep(0.35)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                spotify_with_visible_wait(
                    "adicionar as musicas",
                    lambda: spotify.add_tracks(
                        access_token,
                        playlist_id,
                        ids_encontrados,
                        client_token=client_token,
                    ),
                    attempts=8,
                    max_wait_seconds=90,
                    max_total_wait_seconds=420,
                )

            dest_url = f"https://open.spotify.com/playlist/{playlist_id}"

        elif dest_platform == "soundcloud":
            from services import soundcloud

            dest_sess = sessions.get(dest_sid, {})
            access_token = dest_sess.get("access_token", "")
            if not access_token:
                raise ValueError("Sessão do SoundCloud não encontrada. Reconecte o SoundCloud e tente novamente.")

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
            cookie_header = dest_sess.get("cookie_header", "")
            itfe = dest_sess.get("itfe", "")
            if not developer_token or not (music_user_token or cookie_header):
                raise ValueError("Sessão da Apple Music não encontrada. Reconecte a Apple Music.")

            playlist_id = apple_music.create_playlist(
                developer_token,
                music_user_token,
                nome,
                "Transferida via PlayTransfer",
                cookie_header=cookie_header,
                itfe=itfe,
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
                    cookie_header=cookie_header,
                    itfe=itfe,
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
                apple_music.add_tracks(
                    developer_token,
                    music_user_token,
                    playlist_id,
                    ids_encontrados,
                    cookie_header=cookie_header,
                    itfe=itfe,
                )

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
            from services import amazon_music_session

            # Modo 2: cookies de sessão capturados pelo webview (sem developer credentials)
            session_cookies = amazon_connections.get("dest") or amazon_connections.get(dest_sid)
            if session_cookies and _has_amazon_session_cookie(session_cookies):
                # ── Unofficial cookie-based API ──────────────────────────────
                emit(job, {"type": "status", "msg": "Criando playlist no Amazon Music..."})
                created    = amazon_music_session.create_playlist(session_cookies, nome, "Transferida via PlayTransfer")
                playlist_id = created["id"]
                dest_url    = created["url"]
                emit(job, {"type": "status", "msg": "Buscando músicas no Amazon Music..."})

                for i, m in enumerate(musicas):
                    track_id = amazon_music_session.search_track(session_cookies, m["titulo"], m["artista"])
                    if track_id:
                        ids_encontrados.append(track_id)
                    else:
                        falhas.append(m)
                    emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                               "found": bool(track_id), "current": i + 1, "total": len(musicas)})
                    time.sleep(0.10)

                if ids_encontrados:
                    emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                    amazon_music_session.add_tracks(session_cookies, playlist_id, ids_encontrados)

            else:
                # Modo 1: OAuth oficial (fallback se configurado)
                dest_sess    = sessions.get(dest_sid, {})
                api_key      = dest_sess.get("api_key", "")
                access_token = dest_sess.get("access_token", "")
                if not api_key or not access_token:
                    raise ValueError("Sessão do Amazon Music não encontrada. Conecte o Amazon Music novamente.")

                created     = amazon_music.create_playlist(api_key, access_token, nome, "Transferida via PlayTransfer")
                playlist_id = created["id"]
                dest_url    = created["url"]
                emit(job, {"type": "status", "msg": "Buscando músicas no Amazon Music..."})

                for i, m in enumerate(musicas):
                    track_id = amazon_music.search_track(api_key, access_token, m["titulo"], m["artista"], m.get("album", ""))
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
    return jsonify({"status": "ok", "version": "1.2.26", "app": "PlayTransfer"})

if __name__ == "__main__":
    import webbrowser
    port = int(os.getenv("PORT", 5001))
    def _open():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()
    print(f"\nPlayTransfer rodando em http://localhost:{port}\n")
    app.run(debug=False, port=port, threaded=True)
