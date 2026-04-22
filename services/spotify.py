"""
Spotify helpers for PlayTransfer.
"""

import json
import os
import re
import time

import requests

try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
except ImportError:
    browser_cookie3 = None
    BROWSER_COOKIE3_AVAILABLE = False

_token_cache: dict = {"token": None, "expires": 0, "key": None}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _spotify_headers(access_token: str = "", json_body: bool = False, client_token: str = "") -> dict:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Origin": "https://open.spotify.com",
        "Referer": "https://open.spotify.com/",
        "App-Platform": "WebPlayer",
    }
    token = _as_clean_text(access_token)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    client_token = _as_clean_text(client_token)
    if client_token:
        headers["client-token"] = client_token
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


class SpotifyRateLimitedError(ValueError):
    """Raised when Spotify asks us to slow down."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class SpotifyTokenExpiredError(ValueError):
    """Raised when the Spotify access token is expired or invalid (HTTP 401)."""
    pass


def _retry_after_seconds(response) -> float | None:
    retry_after = response.headers.get("Retry-After", "")
    try:
        return float(retry_after)
    except Exception:
        return None


def _spotify_request(method: str, url: str, max_retries: int = 0, **kwargs):
    """Call Spotify and respect short Retry-After windows."""
    for attempt in range(max_retries + 1):
        response = requests.request(method, url, **kwargs)
        if response.status_code != 429 or attempt >= max_retries:
            return response

        wait_seconds = _retry_after_seconds(response)
        if wait_seconds is None:
            wait_seconds = min(2 + (attempt * 2), 12)
        time.sleep(max(1, min(wait_seconds, 45)))

    return response


def _as_clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("message", "error_description", "error", "detail"):
            nested = _as_clean_text(value.get(key))
            if nested:
                return nested
        try:
            return json.dumps(value, ensure_ascii=False).strip()
        except Exception:
            return str(value).strip()
    if isinstance(value, (list, tuple, set)):
        parts = [_as_clean_text(item) for item in value]
        return " | ".join(part for part in parts if part)
    return str(value).strip()


def _response_detail(response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    detail = _as_clean_text(payload)
    return detail[:220] if detail else ""


def _is_placeholder_sp_dc(value: str | None) -> bool:
    normalized = _as_clean_text(value).lower()
    return normalized in {
        "",
        "seu_sp_dc_aqui",
        "your_sp_dc_here",
        "cole_seu_sp_dc_aqui",
        "sp_dc_aqui",
    }


def _get_sp_dc() -> str:
    sp_dc = _as_clean_text(os.getenv("SPOTIFY_SP_DC", ""))
    if not sp_dc:
        try:
            with open(".env", "r", encoding="utf-8") as env_file:
                for line in env_file:
                    if line.strip().startswith("SPOTIFY_SP_DC="):
                        sp_dc = _as_clean_text(line.strip().split("=", 1)[1])
        except Exception:
            pass
    return "" if _is_placeholder_sp_dc(sp_dc) else sp_dc


def _normalize_cookie_header(cookie_header: str | None) -> str:
    raw = _as_clean_text(cookie_header)
    if not raw:
        return ""
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    lowered = raw.lower()
    if any(marker in lowered for marker in ("path=", "domain=", "expires=", "max-age=", "httponly", "samesite=")):
        sp_dc = _extract_sp_dc(raw)
        return f"sp_dc={sp_dc}" if sp_dc else ""
    return raw


def _extract_sp_dc(value: str | None) -> str:
    raw = _as_clean_text(value)
    if not raw:
        return ""
    if "sp_dc=" in raw:
        raw = raw.split("sp_dc=", 1)[1].split(";", 1)[0].strip()
    return "" if _is_placeholder_sp_dc(raw) else raw


def _available_cookie_loaders() -> list[tuple[str, object]]:
    if not BROWSER_COOKIE3_AVAILABLE:
        return []

    browser_names = [
        ("Chrome", "chrome"),
        ("Edge", "edge"),
        ("Brave", "brave"),
        ("Firefox", "firefox"),
        ("Opera", "opera"),
        ("Vivaldi", "vivaldi"),
    ]
    loaders = []
    for label, attr in browser_names:
        loader = getattr(browser_cookie3, attr, None)
        if callable(loader):
            loaders.append((label, loader))
    return loaders


def read_saved_spotify_cookie() -> dict:
    """Try to read the Spotify login already saved in local browsers."""
    if not BROWSER_COOKIE3_AVAILABLE:
        raise ValueError(
            "A leitura automatica do navegador ainda nao esta instalada nesta instalacao."
        )

    errors = []

    for browser_name, loader in _available_cookie_loaders():
        try:
            jar = loader(domain_name="spotify.com")
        except Exception as exc:
            errors.append((browser_name, type(exc).__name__, str(exc)))
            continue

        cookie_pairs = []
        sp_dc = ""

        for cookie in jar:
            domain = str(getattr(cookie, "domain", "") or "").lower()
            if "spotify.com" not in domain:
                continue

            name = str(getattr(cookie, "name", "") or "").strip()
            value = str(getattr(cookie, "value", "") or "").strip()
            if not name or not value:
                continue

            cookie_pairs.append(f"{name}={value}")
            if name == "sp_dc":
                sp_dc = value

        sp_dc = _extract_sp_dc(sp_dc)
        if sp_dc:
            return {
                "sp_dc": sp_dc,
                "cookie_header": "; ".join(cookie_pairs),
                "browser": browser_name,
            }

    chrome_blocked = any(
        browser_name == "Chrome" and error_type == "RequiresAdminError"
        for browser_name, error_type, _ in errors
    )
    if chrome_blocked:
        raise ValueError(
            "O Chrome desta maquina bloqueou a leitura automatica do Spotify."
        )

    raise ValueError(
        "Nao encontrei o login do Spotify salvo nos navegadores desta maquina. "
        "Abra o Spotify Web ja logado e tente novamente."
    )


def get_token_via_sp_dc(sp_dc: str = None, cookie_header: str = None) -> str:
    """Get a Spotify access token from sp_dc or a full Cookie header."""
    normalized_cookie_header = _normalize_cookie_header(cookie_header)
    normalized_sp_dc = _extract_sp_dc(sp_dc) or _extract_sp_dc(normalized_cookie_header) or _get_sp_dc()
    cache_key = normalized_cookie_header or normalized_sp_dc

    if (
        _token_cache["token"]
        and _token_cache["expires"] > time.time() + 60
        and _token_cache.get("key") == cache_key
    ):
        return _token_cache["token"]

    if not normalized_sp_dc and not normalized_cookie_header:
        raise ValueError("Cookie do Spotify nao fornecido.")

    cookie_value = normalized_cookie_header or f"sp_dc={normalized_sp_dc}"

    response = requests.get(
        "https://open.spotify.com/api/token",
        headers={
            "User-Agent": UA,
            "Cookie": cookie_value,
            "Accept": "application/json",
        },
        timeout=10,
    )
    if response.status_code == 400:
        response_excerpt = ""
        try:
            payload = response.json()
            response_excerpt = _as_clean_text(
                payload.get("error_description")
                or payload.get("error")
                or payload.get("message")
            )
        except Exception:
            response_excerpt = _as_clean_text(response.text)

        message = (
            "O Spotify recusou o cookie informado (HTTP 400). "
            "Isso pode acontecer mesmo com o valor certo, porque esse metodo manual depende "
            "de cookies internos do Spotify."
        )
        if "totp" in response_excerpt.lower():
            message += " O retorno do Spotify menciona TOTP/validacao interna."
        message += (
            " Tente copiar novamente do Spotify Web logado e, se continuar falhando, "
            "cole o cabecalho Cookie completo da requisicao do navegador em vez de so o sp_dc."
        )
        raise ValueError(message)

    if response.status_code != 200:
        raise ValueError(f"sp_dc invalido ou expirado (HTTP {response.status_code})")

    data = response.json()
    token = data.get("accessToken")
    expires = data.get("accessTokenExpirationTimestampMs", 0) / 1000

    if not token:
        raise ValueError("Nao foi possivel obter token do Spotify. Verifique o sp_dc.")

    _token_cache["token"] = token
    _token_cache["expires"] = expires if expires > time.time() else time.time() + 3600
    _token_cache["key"] = cache_key
    return token


def validate(sp_dc: str = None, cookie_header: str = None) -> dict:
    """Validate Spotify credentials and return basic user info."""
    normalized_sp_dc = sp_dc or _extract_sp_dc(cookie_header)
    if not normalized_sp_dc:
        raise ValueError("Cookie sp_dc nao fornecido.")

    token = get_token_via_sp_dc(sp_dc=normalized_sp_dc, cookie_header=cookie_header)
    response = _spotify_request(
        "GET",
        "https://api.spotify.com/v1/me",
        headers=_spotify_headers(token),
        timeout=10,
    )
    if response.status_code == 429:
        raise SpotifyRateLimitedError(
            "Spotify limitou temporariamente a confirmacao da sessao (HTTP 429).",
            _retry_after_seconds(response),
        )
    if response.status_code == 200:
        data = response.json()
        return {
            "display_name": data.get("display_name", "Usuario Spotify"),
            "email": data.get("email", ""),
            "avatar": (data.get("images") or [{}])[0].get("url", ""),
        }

    return {"display_name": "Usuario Spotify", "email": "", "avatar": ""}


def refresh_oauth_token(refresh_token: str, client_id: str = "", client_secret: str = "") -> str | None:
    """Exchange a Spotify OAuth refresh_token for a new access_token."""
    if not refresh_token:
        return None

    client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not client_id:
        return None

    token_payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    token_headers = {"Content-Type": "application/x-www-form-urlencoded"}

    if client_secret:
        import base64 as _b64
        credentials = _b64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        token_headers["Authorization"] = f"Basic {credentials}"

    try:
        response = requests.post(
            "https://accounts.spotify.com/api/token",
            headers=token_headers,
            data=token_payload,
            timeout=10,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        new_token = data.get("access_token", "")
        if new_token:
            _token_cache["token"] = new_token
            expires_in = data.get("expires_in", 3600)
            _token_cache["expires"] = time.time() + expires_in
            _token_cache["key"] = new_token
        return new_token or None
    except Exception:
        return None


def validate_access_token(access_token: str, client_token: str = "") -> dict:
    """Validate a Spotify Web API token and return basic user info."""
    token = _as_clean_text(access_token)
    if not token:
        raise ValueError("Token do Spotify nao fornecido.")

    response = _spotify_request(
        "GET",
        "https://api.spotify.com/v1/me",
        headers=_spotify_headers(token, client_token=client_token),
        timeout=10,
    )
    if response.status_code == 401:
        raise ValueError("Sessao do Spotify expirada. Conecte novamente.")
    if response.status_code == 429:
        raise SpotifyRateLimitedError(
            "Spotify limitou temporariamente a confirmacao da sessao (HTTP 429).",
            _retry_after_seconds(response),
        )
    if response.status_code != 200:
        raise ValueError(f"Spotify recusou a sessao capturada (HTTP {response.status_code}).")

    data = response.json()
    return {
        "display_name": data.get("display_name") or data.get("id") or "Usuario Spotify",
        "email": data.get("email", ""),
        "avatar": (data.get("images") or [{}])[0].get("url", ""),
    }


def _extract_id_and_type(url: str) -> tuple[str | None, str | None]:
    for media_type in ["playlist", "album", "track"]:
        match = re.search(rf"{media_type}/([A-Za-z0-9]+)", url)
        if match:
            return media_type, match.group(1)
    return None, None


def _parse_embed_payload(html: str) -> dict:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except Exception:
        return {}


def _read_via_token(media_type: str, playlist_id: str, access_token: str) -> tuple[str, list[dict]]:
    headers = _spotify_headers(access_token)
    endpoint = "playlists" if media_type == "playlist" else "albums"

    response = _spotify_request(
        "GET",
        f"https://api.spotify.com/v1/{endpoint}/{playlist_id}",
        headers=headers,
        timeout=10,
    )
    if response.status_code == 401:
        raise ValueError("Sessao do Spotify expirada. Conecte novamente.")
    if response.status_code == 404:
        raise ValueError("Playlist nao encontrada. Verifique se ela esta publica ou se voce tem acesso.")
    if response.status_code == 429:
        raise SpotifyRateLimitedError(
            "Spotify pediu para aguardar antes de ler a playlist (HTTP 429).",
            _retry_after_seconds(response),
        )
    if response.status_code != 200:
        raise ValueError(f"Erro do Spotify (HTTP {response.status_code})")

    info = response.json()
    playlist_name = info.get("name", "Spotify Playlist")
    tracks: list[dict] = []
    offset = 0

    while True:
        page_response = _spotify_request(
            "GET",
            f"https://api.spotify.com/v1/{endpoint}/{playlist_id}/tracks",
            headers=headers,
            params={
                "limit": 100,
                "offset": offset,
                "fields": "items(track(name,artists(name),album(name))),next",
            },
            timeout=15,
        )
        if page_response.status_code == 429:
            raise SpotifyRateLimitedError(
                "Spotify pediu para aguardar antes de ler mais musicas (HTTP 429).",
                _retry_after_seconds(page_response),
            )
        if page_response.status_code != 200:
            break

        page = page_response.json()
        items = page.get("items", [])
        for item in items:
            track = item.get("track") or item
            if not track or not track.get("name"):
                continue
            tracks.append(
                {
                    "titulo": track["name"],
                    "artista": ", ".join(artist["name"] for artist in track.get("artists", [])),
                    "album": track.get("album", {}).get("name", "")
                    if isinstance(track.get("album"), dict)
                    else "",
                }
            )

        offset += len(items)
        if not page.get("next"):
            break

    return playlist_name, tracks


def read_playlist(
    url: str,
    sp_dc: str = None,
    access_token: str = None,
    cookie_header: str = None,
) -> tuple[str, list[dict]]:
    """Read Spotify playlist or album through OAuth, public embed, or cookie."""
    media_type, playlist_id = _extract_id_and_type(url)
    if not playlist_id:
        raise ValueError("URL do Spotify invalida. Use: https://open.spotify.com/playlist/...")

    if access_token:
        return _read_via_token(media_type, playlist_id, access_token)

    tracks: list[dict] = []
    playlist_name = "Spotify Playlist"
    embed_status = None
    embed_page_title = ""
    share_token_link = "pt=" in (url or "")

    try:
        embed_response = requests.get(
            f"https://open.spotify.com/embed/{media_type}/{playlist_id}",
            headers={"User-Agent": UA},
            timeout=10,
        )
        if embed_response.status_code == 200:
            data = _parse_embed_payload(embed_response.text)
            if data:
                page_props = data.get("props", {}).get("pageProps", {})
                embed_status = page_props.get("status")
                embed_page_title = _as_clean_text(page_props.get("title"))
                entity = (
                    page_props.get("state", {})
                    .get("data", {})
                    .get("entity", {})
                )
                tracks_data = entity.get("trackList", [])
                playlist_name = entity.get("name", "Spotify Playlist")

                for track in tracks_data:
                    title = _as_clean_text(track.get("title"))
                    artist = _as_clean_text(track.get("subtitle"))
                    if title:
                        tracks.append({"titulo": title, "artista": artist, "album": ""})

                if tracks and (media_type == "album" or len(tracks) < 50):
                    return playlist_name, tracks
    except Exception as exc:
        print(f"[Spotify] Embed falhou: {exc}")

    normalized_sp_dc = sp_dc or _extract_sp_dc(cookie_header) or _get_sp_dc()
    if not normalized_sp_dc and not cookie_header:
        if embed_status == 404 or "page not found" in embed_page_title.lower():
            if share_token_link:
                raise ValueError(
                    "Esse link do Spotify nao esta publico. "
                    "Sem entrar no Spotify, o app nao consegue abrir essa playlist."
                )
            raise ValueError(
                "Essa playlist do Spotify nao esta publica. "
                "Sem entrar no Spotify, o app nao consegue ler essa playlist."
            )
        if tracks:
            return playlist_name, tracks
        raise ValueError(
            "Playlist pode ter mais de 50 musicas. Forneca o cookie sp_dc para ler a playlist completa."
        )

    token = get_token_via_sp_dc(sp_dc=normalized_sp_dc, cookie_header=cookie_header)
    headers = _spotify_headers(token)
    endpoint = "playlists" if media_type == "playlist" else "albums"

    info_response = _spotify_request(
        "GET",
        f"https://api.spotify.com/v1/{endpoint}/{playlist_id}",
        headers=headers,
        timeout=10,
    )
    if info_response.status_code == 401:
        _token_cache["token"] = None
        raise ValueError("Token do Spotify expirou. Reconecte o Spotify.")
    if info_response.status_code == 404:
        raise ValueError("Playlist nao encontrada. Verifique se ela esta publica.")
    if info_response.status_code == 429:
        raise SpotifyRateLimitedError(
            "Spotify pediu para aguardar antes de ler a playlist (HTTP 429).",
            _retry_after_seconds(info_response),
        )
    if info_response.status_code != 200:
        raise ValueError(f"Erro do Spotify (HTTP {info_response.status_code})")

    info = info_response.json()
    playlist_name = info.get("name", "Spotify Playlist")
    tracks = []
    offset = 0

    while True:
        page_response = _spotify_request(
            "GET",
            f"https://api.spotify.com/v1/{endpoint}/{playlist_id}/tracks",
            headers=headers,
            params={
                "limit": 100,
                "offset": offset,
                "fields": "items(track(name,artists(name),album(name))),next",
            },
            timeout=15,
        )
        if page_response.status_code == 429:
            raise SpotifyRateLimitedError(
                "Spotify pediu para aguardar antes de ler mais musicas (HTTP 429).",
                _retry_after_seconds(page_response),
            )
        if page_response.status_code != 200:
            break

        page = page_response.json()
        items = page.get("items", [])
        for item in items:
            track = item.get("track") or item
            if not track or not track.get("name"):
                continue
            tracks.append(
                {
                    "titulo": track["name"],
                    "artista": ", ".join(artist["name"] for artist in track.get("artists", [])),
                    "album": track.get("album", {}).get("name", "")
                    if isinstance(track.get("album"), dict)
                    else "",
                }
            )

        offset += len(items)
        if not page.get("next"):
            break

    return playlist_name, tracks


def search_track(
    access_token: str,
    titulo: str,
    artista: str = "",
    album: str = "",
    client_token: str = "",
) -> str | None:
    """Search a track on Spotify and return its best-matching URI."""
    if not access_token:
        raise ValueError("Access token do Spotify nao informado.")

    queries = []
    if artista and album:
        queries.append(f'track:"{titulo}" artist:"{artista}" album:"{album}"')
    if artista:
        queries.append(f'track:"{titulo}" artist:"{artista}"')
        queries.append(f"{artista} {titulo}")
    queries.append(titulo)

    headers = _spotify_headers(access_token, client_token=client_token)

    for query in queries:
        try:
            response = _spotify_request(
                "GET",
                "https://api.spotify.com/v1/search",
                headers=headers,
                params={"q": query, "type": "track", "limit": 5},
                timeout=10,
            )
            if response.status_code == 401:
                raise SpotifyTokenExpiredError(
                    "Sessao do Spotify expirada durante busca de musicas."
                )
            if response.status_code == 429:
                raise SpotifyRateLimitedError(
                    "Spotify pediu para aguardar antes de procurar musicas (HTTP 429).",
                    _retry_after_seconds(response),
                )
            if response.status_code != 200:
                continue
            items = response.json().get("tracks", {}).get("items", [])
            if items:
                return items[0].get("uri")
        except (SpotifyRateLimitedError, SpotifyTokenExpiredError):
            raise
        except Exception:
            continue

    return None


def create_playlist(
    access_token: str,
    nome: str,
    descricao: str = "",
    client_token: str = "",
) -> str:
    """Create a private playlist on Spotify and return its id."""
    if not access_token:
        raise ValueError("Access token do Spotify nao informado.")

    print(f"[Spotify DEBUG] create_playlist chamado. Token (primeiros 20 chars): {access_token[:20] if access_token else 'VAZIO'}...")
    response = _spotify_request(
        "POST",
        "https://api.spotify.com/v1/me/playlists",
        headers=_spotify_headers(access_token, json_body=True, client_token=client_token),
        json={
            "name": nome,
            "description": descricao or "Transferida via PlayTransfer",
            "public": False,
        },
        timeout=15,
    )
    print(f"[Spotify DEBUG] create_playlist HTTP {response.status_code} — Body: {response.text[:500]}")

    if response.status_code == 401:
        raise SpotifyTokenExpiredError(
            "Sessao do Spotify expirada. Tentando renovar..."
        )
    if response.status_code == 429:
        detail = _response_detail(response)
        message = "Spotify pediu para aguardar antes de criar a playlist (HTTP 429)."
        if detail:
            message += f" Detalhe: {detail}"
        raise SpotifyRateLimitedError(
            message,
            _retry_after_seconds(response),
        )
    if response.status_code == 403:
        detail = _response_detail(response)
        raise ValueError(
            "O Spotify bloqueou a criacao da playlist com esta sessao (HTTP 403). "
            "Tente reconectar o Spotify ou use o login oficial OAuth."
            + (f" Detalhe: {detail}" if detail else "")
        )
    if response.status_code not in (200, 201):
        detail = _response_detail(response)
        suffix = f" Detalhe: {detail}" if detail else ""
        raise ValueError(f"Nao foi possivel criar playlist no Spotify (HTTP {response.status_code}).{suffix}")

    playlist_id = response.json().get("id")
    if not playlist_id:
        raise ValueError("Spotify nao retornou o ID da playlist criada.")
    return playlist_id


def add_tracks(
    access_token: str,
    playlist_id: str,
    track_uris: list[str],
    client_token: str = "",
) -> None:
    """Add track URIs to a Spotify playlist in batches."""
    if not access_token:
        raise ValueError("Access token do Spotify nao informado.")

    headers = _spotify_headers(access_token, json_body=True, client_token=client_token)

    for index in range(0, len(track_uris), 100):
        chunk = track_uris[index : index + 100]
        response = _spotify_request(
            "POST",
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
            headers=headers,
            json={"uris": chunk},
            timeout=15,
        )
        if response.status_code == 401:
            raise SpotifyTokenExpiredError(
                "Sessao do Spotify expirada ao adicionar musicas."
            )
        if response.status_code == 429:
            raise SpotifyRateLimitedError(
                "Spotify pediu para aguardar antes de adicionar musicas (HTTP 429).",
                _retry_after_seconds(response),
            )
        if response.status_code not in (200, 201):
            raise ValueError(f"Erro ao adicionar faixas no Spotify (HTTP {response.status_code}).")
