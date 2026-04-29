"""
YouTube Music helpers for PlayTransfer.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import websocket

    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

try:
    from ytmusicapi import OAuthCredentials, YTMusic
    from ytmusicapi.auth.oauth.token import OAuthToken, RefreshingToken
    from ytmusicapi.helpers import get_authorization, initialize_headers

    YTM_AVAILABLE = True
except ImportError:
    YTM_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parent.parent
YTM_HEADERS_DIR = PROJECT_ROOT / ".runtime" / "ytmusic"
YTM_HEADERS_DIR.mkdir(parents=True, exist_ok=True)

YTM_ORIGIN = "https://music.youtube.com"
YTM_OAUTH_CLIENT_ID = os.getenv("YTMUSIC_OAUTH_CLIENT_ID", "").strip()
YTM_OAUTH_CLIENT_SECRET = os.getenv("YTMUSIC_OAUTH_CLIENT_SECRET", "").strip()
BROWSER_CANDIDATES = (
    ("Chrome", Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")),
    ("Chrome", Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"))),
    ("Edge", Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")),
    ("Edge", Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")),
)


def _check_available() -> None:
    if not YTM_AVAILABLE:
        raise ImportError("ytmusicapi nao esta instalado nesta instalacao.")


def _check_auto_available() -> None:
    _check_available()
    if not WEBSOCKET_AVAILABLE:
        raise ImportError("websocket-client nao esta instalado nesta instalacao.")


def oauth_configured() -> bool:
    return bool(YTM_OAUTH_CLIENT_ID and YTM_OAUTH_CLIENT_SECRET)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _headers_output_path() -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return YTM_HEADERS_DIR / f"headers-{timestamp}-{os.urandom(4).hex()}.json"


def _oauth_output_path() -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return YTM_HEADERS_DIR / f"oauth-{timestamp}-{os.urandom(4).hex()}.json"


def _write_headers_file(headers: dict[str, str]) -> str:
    output_path = _headers_output_path()
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(headers, output_file, ensure_ascii=False, indent=2, sort_keys=True)
    return str(output_path)


def _extract_playlist_id(url: str) -> str:
    match = re.search(r"(?:list=|playlist/)([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError("URL do YouTube Music invalida. Use: https://music.youtube.com/playlist?list=...")
    return match.group(1)


def _oauth_credentials() -> "OAuthCredentials":
    _check_available()
    if not oauth_configured():
        raise ValueError(
            "O login oficial do YouTube Music ainda nao foi ativado nesta instalacao."
        )
    return OAuthCredentials(YTM_OAUTH_CLIENT_ID, YTM_OAUTH_CLIENT_SECRET)


def _write_oauth_file(token: "RefreshingToken") -> str:
    output_path = _oauth_output_path()
    token.store_token(str(output_path))
    return str(output_path)


def _extract_cookie_value(cookie_header: str, cookie_name: str) -> str:
    match = re.search(rf"(?:^|;\s*){re.escape(cookie_name)}=([^;]+)", cookie_header)
    return match.group(1).strip() if match else ""


def _ensure_required_cookie(cookie_header: str) -> str:
    normalized = _as_text(cookie_header)
    if not normalized:
        raise ValueError("Nao encontrei os dados da sua sessao do YouTube Music.")

    if "__Secure-3PAPISID=" in normalized:
        return normalized

    for cookie_name in ("SAPISID", "__Secure-1PAPISID", "APISID"):
        candidate = _extract_cookie_value(normalized, cookie_name)
        if candidate:
            return normalized + f"; __Secure-3PAPISID={candidate}"

    raise ValueError("Nao consegui confirmar a sessao do Google nessa janela.")


def _make_browser_auth_headers(cookie_header: str, authuser: str = "0") -> dict[str, str]:
    normalized_cookie = _ensure_required_cookie(cookie_header)
    sapisid = _extract_cookie_value(normalized_cookie, "__Secure-3PAPISID")
    if not sapisid:
        raise ValueError("Nao consegui confirmar a sessao do Google nessa janela.")

    headers = dict(initialize_headers())
    headers.update(
        {
            "origin": YTM_ORIGIN,
            "x-origin": YTM_ORIGIN,
            "cookie": normalized_cookie,
            "x-goog-authuser": str(authuser),
            "authorization": get_authorization(f"{sapisid} {YTM_ORIGIN}"),
        }
    )
    return headers


def _parse_curl_headers(headers_raw: str) -> dict[str, str]:
    flattened = re.sub(r"\^\s*\r?\n", " ", headers_raw)
    flattened = re.sub(r"\\\s*\r?\n", " ", flattened)
    tokens = shlex.split(flattened, posix=True)
    headers: dict[str, str] = {}

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in ("-H", "--header") and index + 1 < len(tokens):
            header_line = tokens[index + 1]
            if ":" in header_line:
                key, value = header_line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
            index += 2
            continue
        if token in ("-b", "--cookie") and index + 1 < len(tokens):
            headers["cookie"] = tokens[index + 1].strip()
            index += 2
            continue
        index += 1

    return headers


def _parse_header_lines(headers_raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw_line in headers_raw.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _looks_like_browse_payload(parsed: Any) -> bool:
    if isinstance(parsed, list):
        sample = [item for item in parsed[:5] if isinstance(item, dict)]
        return bool(sample) and all("key" in item and "value" in item for item in sample)

    if isinstance(parsed, dict):
        lowered_keys = {str(key).lower() for key in parsed.keys()}
        payload_markers = {
            "context",
            "browseid",
            "continuation",
            "params",
            "browseendpointcontextsupportedconfigs",
        }
        return bool(lowered_keys & payload_markers) and "cookie" not in lowered_keys

    return False


def _raise_manual_copy_guidance() -> None:
    raise ValueError(
        "Voce colou o payload da requisicao browse, nao o cURL completo. "
        "No Chrome, clique com o botao direito em browse > Copy > Copy as cURL (bash)."
    )


def _looks_like_browse_payload_text(raw: str) -> bool:
    lowered = raw.lower()
    if any(marker in lowered for marker in ("curl ", "--header", " -h ", "\n-h ", "--cookie", " -b ", "\n-b ", "cookie:", '"cookie"')):
        return False

    repeated_key_value = lowered.count('"key"') >= 2 and lowered.count('"value"') >= 2
    payload_markers = (
        '"u_tz"',
        '"u_his"',
        '"u_h"',
        '"u_aw"',
        '"u_cd"',
        '"u_w"',
        '"context"',
        '"browseid"',
        '"continuation"',
        '"clientscreennonce"',
        '"screenwidthpoints"',
        '"screenheightpoints"',
    )
    return repeated_key_value or any(marker in lowered for marker in payload_markers)


def _normalize_user_headers(headers_raw: str) -> dict[str, str]:
    raw = _as_text(headers_raw)
    if not raw or len(raw) < 10:
        raise ValueError("Headers do YouTube Music nao fornecidos.")

    if _looks_like_browse_payload_text(raw):
        _raise_manual_copy_guidance()

    if raw.startswith("{") or raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if _looks_like_browse_payload(parsed):
                _raise_manual_copy_guidance()
            if not isinstance(parsed, dict):
                raise ValueError("Nao consegui entender o texto colado do YouTube Music.")
            headers = {str(key).lower(): _as_text(value) for key, value in parsed.items() if _as_text(value)}
        except json.JSONDecodeError as exc:
            if _looks_like_browse_payload_text(raw):
                _raise_manual_copy_guidance()
            raise ValueError("Nao consegui entender o texto colado do YouTube Music.") from exc
    elif raw.lower().startswith("curl ") or " -H " in raw or "\n-H " in raw:
        headers = _parse_curl_headers(raw)
    else:
        headers = _parse_header_lines(raw)

    if "cookie" not in headers:
        if _looks_like_browse_payload_text(raw):
            _raise_manual_copy_guidance()
        raise ValueError("Nao encontrei os dados da sua sessao do YouTube Music.")

    headers["x-goog-authuser"] = headers.get("x-goog-authuser", "0")
    return _make_browser_auth_headers(headers["cookie"], headers["x-goog-authuser"])


def _account_summary(info: dict[str, Any]) -> dict[str, str]:
    return {
        "display_name": _as_text(info.get("accountName")) or "Usuario YouTube Music",
        "email": _as_text(info.get("channelHandle")),
        "avatar": _as_text(info.get("accountPhotoUrl")),
    }


def _validate_browser_headers(headers: dict[str, str]) -> dict[str, str]:
    _check_available()

    authuser_candidates = []
    starting_authuser = _as_text(headers.get("x-goog-authuser")) or "0"
    for candidate in [starting_authuser, "0", "1", "2", "3"]:
        if candidate not in authuser_candidates:
            authuser_candidates.append(candidate)

    last_error = None
    for authuser in authuser_candidates:
        try:
            candidate_headers = dict(headers)
            candidate_headers["x-goog-authuser"] = authuser
            ytm = YTMusic(auth=candidate_headers)
            info = ytm.get_account_info()
            result = _account_summary(info)
            result["headers_path"] = _write_headers_file(candidate_headers)
            return result
        except Exception as exc:
            last_error = exc

    raise ValueError(
        "Nao consegui confirmar essa conta do YouTube Music. "
        "Confira se voce entrou na conta certa e tente novamente."
    ) from last_error


def validate(headers_raw: str) -> dict:
    """
    Validate a YouTube Music browser session from pasted headers or a cURL command.
    """
    headers = _normalize_user_headers(headers_raw)
    try:
        return _validate_browser_headers(headers)
    except Exception as exc:
        raise ValueError(f"Falha na autenticacao do YouTube Music: {exc}") from exc


def start_oauth_login() -> dict[str, Any]:
    credentials = _oauth_credentials()
    code = credentials.get_code()
    verification_url = _as_text(code.get("verification_url"))
    user_code = _as_text(code.get("user_code"))
    verification_url_complete = verification_url
    if verification_url and user_code:
        verification_url_complete = (
            f"{verification_url}?user_code={urllib.parse.quote(user_code)}"
        )

    return {
        "kind": "oauth",
        "device_code": _as_text(code.get("device_code")),
        "user_code": user_code,
        "verification_url": verification_url,
        "verification_url_complete": verification_url_complete,
        "interval": int(code.get("interval") or 5),
        "expires_in": int(code.get("expires_in") or 1800),
    }


def poll_oauth_login(login: dict[str, Any]) -> dict[str, Any]:
    credentials = _oauth_credentials()
    device_code = _as_text(login.get("device_code"))
    if not device_code:
        raise ValueError("Nao encontrei o login pendente do YouTube Music.")

    started_at = float(login.get("started_at") or 0)
    expires_in = int(login.get("expires_in") or 1800)
    if started_at and time.time() > started_at + expires_in + 15:
        raise ValueError("O login do YouTube Music expirou. Abra novamente.")

    token_data = credentials.token_from_code(device_code)
    error = _as_text(token_data.get("error"))
    if error:
        if error == "authorization_pending":
            return {
                "pending": True,
                "retry_after_ms": max(3000, int(login.get("interval") or 5) * 1000),
            }
        if error == "slow_down":
            interval = int(login.get("interval") or 5) + 5
            login["interval"] = interval
            return {"pending": True, "retry_after_ms": interval * 1000}
        if error == "access_denied":
            raise ValueError("O login do Google foi cancelado antes de terminar.")
        if error in {"expired_token", "invalid_grant"}:
            raise ValueError("O login do YouTube Music expirou. Abra novamente.")
        raise ValueError(
            f"Nao consegui terminar o login do YouTube Music agora ({error})."
        )

    refreshing_token = RefreshingToken(credentials=credentials, **token_data)
    refreshing_token.update(token_data)
    oauth_path = _write_oauth_file(refreshing_token)

    ytm = YTMusic(auth=oauth_path, oauth_credentials=credentials)
    info = ytm.get_account_info()
    result = _account_summary(info)
    result["oauth_path"] = oauth_path
    return result


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _find_browser_executable() -> tuple[str, str]:
    for browser_name, browser_path in BROWSER_CANDIDATES:
        if browser_path.exists():
            return browser_name, str(browser_path)
    raise ValueError("Nao encontrei Chrome ou Edge nesta instalacao para abrir o YouTube Music automaticamente.")


def _wait_for_debug_endpoint(port: int, timeout: float = 15.0) -> None:
    version_url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(version_url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise ValueError("Nao consegui abrir a janela guiada do YouTube Music.")


def _load_json_url(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def start_guided_login() -> dict[str, Any]:
    """
    Launch a temporary browser window with remote debugging so the app can finish
    the YouTube Music login without DevTools/cURL steps.
    """
    _check_auto_available()
    browser_name, browser_path = _find_browser_executable()
    debug_port = _pick_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="playtransfer-ytm-")

    creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        [
            browser_path,
            f"--remote-debugging-port={debug_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={user_data_dir}",
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            YTM_ORIGIN,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )

    _wait_for_debug_endpoint(debug_port)

    return {
        "browser_name": browser_name,
        "browser_path": browser_path,
        "debug_port": debug_port,
        "browser_pid": process.pid,
        "user_data_dir": user_data_dir,
    }


def _cdp_call(websocket_url: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    ws = websocket.create_connection(websocket_url, timeout=10, suppress_origin=True)
    try:
        ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
        while True:
            message = json.loads(ws.recv())
            if message.get("id") == 1:
                if "error" in message:
                    raise RuntimeError(message["error"].get("message", "Erro do navegador guiado."))
                return message.get("result", {})
    finally:
        ws.close()


def _pick_debug_target(port: int) -> str:
    targets = _load_json_url(f"http://127.0.0.1:{port}/json/list")
    if not isinstance(targets, list):
        raise ValueError("Nao consegui encontrar a janela guiada do YouTube Music.")

    preferred_urls = ("music.youtube.com", "accounts.google.com", "youtube.com")
    for preferred_url in preferred_urls:
        for target in targets:
            if target.get("type") != "page":
                continue
            if preferred_url in _as_text(target.get("url")) and target.get("webSocketDebuggerUrl"):
                return str(target["webSocketDebuggerUrl"])

    for target in targets:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return str(target["webSocketDebuggerUrl"])

    raise ValueError("Nao consegui encontrar a janela guiada do YouTube Music.")


def _cookies_from_debugger(port: int) -> str:
    websocket_url = _pick_debug_target(port)
    _cdp_call(websocket_url, "Network.enable")

    cookies_result = _cdp_call(websocket_url, "Network.getAllCookies")
    cookies = cookies_result.get("cookies") or []
    if not cookies:
        cookies_result = _cdp_call(
            websocket_url,
            "Network.getCookies",
            {"urls": [YTM_ORIGIN, "https://www.youtube.com", "https://accounts.google.com"]},
        )
        cookies = cookies_result.get("cookies") or []

    cookie_pairs: dict[str, str] = {}
    for cookie in cookies:
        domain = _as_text(cookie.get("domain")).lstrip(".")
        if not domain.endswith(("youtube.com", "google.com")):
            continue
        name = _as_text(cookie.get("name"))
        value = _as_text(cookie.get("value"))
        if name and value:
            cookie_pairs[name] = value

    if not cookie_pairs:
        raise ValueError(
            "Ainda nao consegui confirmar sua conta do YouTube Music. "
            "Entre na conta na janela que abriu e tente novamente."
        )

    return "; ".join(f"{name}={value}" for name, value in cookie_pairs.items())


def finish_guided_login(login: dict[str, Any]) -> dict[str, str]:
    """
    Read cookies from the guided browser window and convert them into YTMusic auth.
    """
    _check_auto_available()
    debug_port = int(login.get("debug_port") or 0)
    if not debug_port:
        raise ValueError("Janela guiada do YouTube Music nao encontrada.")

    cookie_header = _cookies_from_debugger(debug_port)
    headers = _make_browser_auth_headers(cookie_header, "0")
    return _validate_browser_headers(headers)


def cleanup_guided_login(login: dict[str, Any], close_browser: bool = False) -> None:
    browser_pid = int(login.get("browser_pid") or 0)
    if close_browser and browser_pid:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(browser_pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                os.kill(browser_pid, 9)
        except Exception:
            pass

    user_data_dir = _as_text(login.get("user_data_dir"))
    if close_browser and user_data_dir and os.path.isdir(user_data_dir):
        try:
            for _ in range(20):
                try:
                    shutil.rmtree(user_data_dir, ignore_errors=False)
                    break
                except OSError:
                    time.sleep(0.15)
        except Exception:
            pass


def read_playlist(url: str) -> tuple[str, list[dict]]:
    """
    Read a public YouTube Music playlist.
    """
    _check_available()
    playlist_id = _extract_playlist_id(url)

    try:
        ytm = YTMusic()
        playlist = ytm.get_playlist(playlist_id, limit=500)
    except Exception as exc:
        raise ValueError(f"Nao foi possivel ler a playlist do YouTube Music: {exc}") from exc

    nome = playlist.get("title", "YouTube Music Playlist")
    faixas = []

    for track in playlist.get("tracks", []):
        titulo = track.get("title", "")
        artistas = track.get("artists", [])
        artista = ", ".join(a.get("name", "") for a in artistas) if artistas else ""
        album_data = track.get("album") or {}
        album = album_data.get("name", "") if isinstance(album_data, dict) else ""

        if titulo:
            faixas.append({"titulo": titulo, "artista": artista, "album": album})

    return nome, faixas


def _ascii_search_variant(value: str) -> str:
    text = _as_text(value)
    if not text:
        return ""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").strip()


def _strip_title_noise(value: str) -> str:
    text = _as_text(value)
    if not text:
        return ""
    text = re.sub(
        r"\s*[\[(][^\])]*(?:feat\.?|featuring|with|remaster(?:ed)?|remix|explicit|clean|version|mono|stereo|deluxe|live)[^\])]*[\])]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", text).strip()


def _youtube_search_queries(titulo: str, artista: str) -> list[str]:
    title = _as_text(titulo)
    artist = _as_text(artista)
    clean_title = _strip_title_noise(title)
    ascii_title = _ascii_search_variant(title)
    ascii_artist = _ascii_search_variant(artist)
    first_artist = re.split(r"\s*(?:,|&|\bfeat\.?\b|\bfeaturing\b)\s*", artist, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    candidates = [
        f"{artist} {title}" if artist else title,
        f"{ascii_artist} {ascii_title}" if ascii_artist and ascii_title else "",
        f"{first_artist} {title}" if first_artist and first_artist != artist else "",
        f"{artist} {clean_title}" if artist and clean_title and clean_title != title else "",
        f"{first_artist} {clean_title}" if first_artist and clean_title and clean_title != title else "",
        title,
        clean_title if clean_title != title else "",
    ]

    queries = []
    seen = set()
    for query in candidates:
        normalized = re.sub(r"\s+", " ", _as_text(query))
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            queries.append(normalized)
    return queries


def search_track(ytm: "YTMusic", titulo: str, artista: str) -> str | None:
    try:
        for query in _youtube_search_queries(titulo, artista):
            results = ytm.search(query, filter="songs", limit=5)
            for result in results or []:
                video_id = result.get("videoId")
                if video_id:
                    return video_id
    except Exception:
        pass
    return None


def create_playlist(ytm: "YTMusic", nome: str, descricao: str = "") -> str:
    try:
        return ytm.create_playlist(
            title=nome,
            description=descricao or "Transferida via PlayTransfer",
            privacy_status="PRIVATE",
        )
    except Exception as exc:
        raise ValueError(f"Nao foi possivel criar playlist no YouTube Music: {exc}") from exc


def add_tracks(ytm: "YTMusic", playlist_id: str, video_ids: list[str]) -> None:
    try:
        ytm.add_playlist_items(playlist_id, video_ids)
    except Exception as exc:
        raise ValueError(f"Erro ao adicionar faixas ao YouTube Music: {exc}") from exc


def get_ytm_instance(auth_path: str) -> "YTMusic":
    _check_available()
    if not os.path.exists(auth_path):
        raise ValueError("Arquivo de acesso do YouTube Music nao encontrado. Reconecte.")

    with open(auth_path, encoding="utf-8") as auth_file:
        auth_data = json.load(auth_file)

    if OAuthToken.is_oauth(auth_data):
        credentials = _oauth_credentials()
        return YTMusic(auth=auth_path, oauth_credentials=credentials)

    return YTMusic(auth=auth_path)
