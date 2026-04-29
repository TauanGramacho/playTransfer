"""
services/soundcloud.py - PlayTransfer
Leitura publica e escrita autenticada no SoundCloud.
"""
from __future__ import annotations

import os
import re
from typing import Any

import requests

try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
except ImportError:
    browser_cookie3 = None
    BROWSER_COOKIE3_AVAILABLE = False

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
API_V1 = "https://api.soundcloud.com"
API_V2 = "https://api-v2.soundcloud.com"

_client_id_cache = {"id": None}

KNOWN_CLIENT_IDS = [
    "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX",
    "a3e059563d7fd3372b49b37f00a00bcf",
    "2t9loNQH90kzJcsFCODdigxfp325aq4z",
]

TOKEN_RE = re.compile(r"(?:OAuth|Bearer)\s+([A-Za-z0-9._~+/=-]{20,})", re.I)
NAMED_TOKEN_RE = re.compile(
    r"(?:oauth_token|access_token|oauthToken|accessToken)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9._~+/=%-]{20,})",
    re.I,
)


def _available_cookie_loaders() -> list[tuple[str, object]]:
    if not BROWSER_COOKIE3_AVAILABLE:
        return []

    browser_names = [
        ("Edge", "edge"),
        ("Chrome", "chrome"),
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


def _token_from_text(value: str) -> str:
    text = str(value or "")
    match = TOKEN_RE.search(text) or NAMED_TOKEN_RE.search(text)
    if not match:
        return ""
    token = requests.utils.unquote(match.group(1).strip().strip("\"'"))
    if len(token) < 20 or any(char.isspace() for char in token):
        return ""
    return token


def _token_from_cookie(name: str, value: str) -> str:
    lowered = str(name or "").strip().lower()
    raw_value = str(value or "").strip()
    if lowered in {
        "oauth_token",
        "soundcloud_oauth_token",
        "soundcloud_access_token",
        "access_token",
        "sc_oauth_token",
    }:
        return _token_from_text(f"oauth_token={raw_value}") or raw_value
    if "oauth" in lowered or "access" in lowered or "token" in lowered:
        return _token_from_text(f"{name}={raw_value}")
    return _token_from_text(raw_value)


def _public_headers() -> dict[str, str]:
    return {"User-Agent": UA, "Accept": "application/json"}


def _auth_headers(access_token: str) -> dict[str, str]:
    if not access_token:
        raise ValueError("Access token do SoundCloud nao fornecido.")
    return {
        "User-Agent": UA,
        "Accept": "application/json; charset=utf-8",
        "Content-Type": "application/json",
        "Authorization": f"OAuth {access_token}",
    }


def _get_client_id() -> str:
    client_id = os.getenv("SOUNDCLOUD_CLIENT_ID", "").strip()
    if client_id:
        return client_id

    if _client_id_cache["id"]:
        return _client_id_cache["id"]

    for known in KNOWN_CLIENT_IDS:
        try:
            response = requests.get(
                f"{API_V2}/tracks",
                params={"client_id": known, "limit": 1},
                headers=_public_headers(),
                timeout=5,
            )
            if response.status_code == 200:
                _client_id_cache["id"] = known
                return known
        except Exception:
            continue

    try:
        home = requests.get("https://soundcloud.com", headers=_public_headers(), timeout=10)
        scripts = re.findall(r'<script[^>]+src="([^"]+\\.js)"', home.text)
        for script_url in reversed(scripts[-6:]):
            try:
                script = requests.get(script_url, headers=_public_headers(), timeout=5).text
            except Exception:
                continue
            match = re.search(r'client_id:"([a-zA-Z0-9]{32,})"', script)
            if match:
                _client_id_cache["id"] = match.group(1)
                return _client_id_cache["id"]
    except Exception:
        pass

    raise ValueError("Nao foi possivel obter client_id publico do SoundCloud.")


def _normalize_track(track: dict[str, Any]) -> dict[str, str] | None:
    title = (track.get("title") or "").strip()
    if not title:
        return None

    artist = ""
    user = track.get("user") or {}
    if isinstance(user, dict):
        artist = (user.get("username") or user.get("full_name") or "").strip()

    publisher = track.get("publisher_metadata") or {}
    publisher_artist = (publisher.get("artist") or "").strip() if isinstance(publisher, dict) else ""
    if publisher_artist:
        artist = publisher_artist

    if " - " in title and not publisher_artist:
        possible_artist, possible_title = title.split(" - ", 1)
        if possible_artist and possible_title:
            artist = possible_artist.strip() or artist
            title = possible_title.strip()

    return {"titulo": title, "artista": artist, "album": ""}


def _clean(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _score_track(track: dict[str, Any], titulo: str, artista: str, album: str = "") -> int:
    normalized = _normalize_track(track) or {"titulo": "", "artista": "", "album": ""}
    wanted_title = _clean(titulo)
    wanted_artist = _clean(artista)
    wanted_album = _clean(album)
    found_title = _clean(normalized.get("titulo", ""))
    found_artist = _clean(normalized.get("artista", ""))
    found_album = _clean(normalized.get("album", ""))

    score = 0
    if wanted_title and found_title == wanted_title:
        score += 70
    elif wanted_title and (wanted_title in found_title or found_title in wanted_title):
        score += 45
    elif wanted_title:
        wanted_words = set(wanted_title.split())
        found_words = set(found_title.split())
        if wanted_words:
            score += int(35 * (len(wanted_words & found_words) / len(wanted_words)))

    if wanted_artist and found_artist:
        if wanted_artist == found_artist:
            score += 25
        elif wanted_artist in found_artist or found_artist in wanted_artist:
            score += 18
        elif set(wanted_artist.split()) & set(found_artist.split()):
            score += 10

    if wanted_album and found_album and (wanted_album == found_album or wanted_album in found_album):
        score += 5
    return score


def _resolve_public_playlist(url: str) -> dict[str, Any]:
    client_id = _get_client_id()
    response = requests.get(
        f"{API_V2}/resolve",
        params={"url": url, "client_id": client_id},
        headers=_public_headers(),
        timeout=15,
    )
    if response.status_code == 404:
        raise ValueError("Playlist do SoundCloud nao encontrada ou privada.")
    if response.status_code != 200:
        raise ValueError(f"SoundCloud retornou HTTP {response.status_code}.")
    return response.json()


def _resolve_auth_playlist(url: str, access_token: str) -> dict[str, Any]:
    response = requests.get(
        f"{API_V1}/resolve",
        params={"url": url},
        headers=_auth_headers(access_token),
        timeout=15,
    )
    if response.status_code == 404:
        raise ValueError("Playlist do SoundCloud nao encontrada.")
    if response.status_code != 200:
        raise ValueError(f"SoundCloud retornou HTTP {response.status_code}.")
    return response.json()


def validate(access_token: str | None = None) -> dict[str, str]:
    token = (access_token or "").strip()
    if token:
        response = requests.get(f"{API_V1}/me", headers=_auth_headers(token), timeout=15)
        if response.status_code != 200:
            raise ValueError("Access token do SoundCloud invalido ou expirado.")
        data = response.json()
        return {
            "display_name": data.get("username") or data.get("full_name") or "SoundCloud",
            "avatar": data.get("avatar_url", ""),
        }

    _get_client_id()
    return {"display_name": "SoundCloud (publico)", "avatar": ""}


def _token_from_web_session(cookie_header: str) -> str:
    if not cookie_header:
        return ""
    headers = {
        **_public_headers(),
        "Cookie": cookie_header,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for url in ("https://soundcloud.com/you/library", "https://soundcloud.com/discover"):
        try:
            response = requests.get(url, headers=headers, timeout=12)
        except Exception:
            continue
        for name, value in response.headers.items():
            if str(name).lower() == "set-cookie":
                token = _token_from_text(value)
                if token:
                    return token
        token = _token_from_text(response.text)
        if token:
            return token
    return ""


def read_saved_soundcloud_session() -> dict[str, str]:
    """Try to read a SoundCloud web login saved in local browsers."""
    if not BROWSER_COOKIE3_AVAILABLE:
        raise ValueError("A leitura automatica do navegador ainda nao esta instalada nesta instalacao.")

    errors = []

    for browser_name, loader in _available_cookie_loaders():
        try:
            jar = loader(domain_name="soundcloud.com")
        except Exception as exc:
            errors.append((browser_name, type(exc).__name__, str(exc)))
            continue

        cookie_pairs = []
        seen = set()
        access_token = ""

        for cookie in jar:
            domain = str(getattr(cookie, "domain", "") or "").lower()
            if "soundcloud.com" not in domain:
                continue

            name = str(getattr(cookie, "name", "") or "").strip()
            value = str(getattr(cookie, "value", "") or "").strip()
            if not name or not value:
                continue

            key = (domain, name)
            if key not in seen:
                seen.add(key)
                cookie_pairs.append(f"{name}={value}")

            if not access_token:
                access_token = _token_from_cookie(name, value)

        cookie_header = "; ".join(cookie_pairs)
        if not access_token and cookie_header:
            access_token = _token_from_web_session(cookie_header)

        if access_token:
            return {
                "access_token": access_token,
                "cookie_header": cookie_header,
                "browser": browser_name,
            }

    edge_blocked = any(
        browser_name == "Edge" and error_type == "RequiresAdminError"
        for browser_name, error_type, _ in errors
    )
    if edge_blocked:
        raise ValueError("O Edge desta maquina bloqueou a leitura automatica do SoundCloud.")

    raise ValueError(
        "Nao encontrei o login do SoundCloud salvo nos navegadores desta maquina. "
        "Abra o SoundCloud no Edge, entre com Google e tente novamente."
    )


def read_playlist(url: str, access_token: str | None = None) -> tuple[str, list[dict[str, str]]]:
    if "soundcloud.com" not in url:
        raise ValueError("URL do SoundCloud invalida.")

    token = (access_token or "").strip()
    if token:
        data = _resolve_auth_playlist(url, token)
        tracks = data.get("tracks") or []
        if not tracks and data.get("id"):
            details = requests.get(
                f"{API_V1}/playlists/{data['id']}",
                params={"show_tracks": "true"},
                headers=_auth_headers(token),
                timeout=15,
            )
            if details.status_code == 200:
                data = details.json()
                tracks = data.get("tracks") or []
    else:
        data = _resolve_public_playlist(url)
        tracks = data.get("tracks") or []
        incomplete_ids = [str(track["id"]) for track in tracks if not track.get("title")]
        if incomplete_ids:
            client_id = _get_client_id()
            for start in range(0, len(incomplete_ids), 50):
                chunk = incomplete_ids[start : start + 50]
                response = requests.get(
                    f"{API_V2}/tracks",
                    params={"ids": ",".join(chunk), "client_id": client_id},
                    headers=_public_headers(),
                    timeout=15,
                )
                if response.status_code != 200:
                    continue
                detailed = {str(track["id"]): track for track in response.json()}
                for track in tracks:
                    if str(track.get("id")) in detailed:
                        track.update(detailed[str(track["id"])])

    kind = data.get("kind") or data.get("type") or ""
    if kind not in ("playlist", "system-playlist"):
        raise ValueError("O link informado nao e uma playlist do SoundCloud.")

    normalized_tracks = []
    for track in tracks:
        normalized = _normalize_track(track)
        if normalized:
            normalized_tracks.append(normalized)

    if not normalized_tracks:
        raise ValueError("A playlist do SoundCloud nao retornou faixas.")

    return data.get("title", "SoundCloud Playlist"), normalized_tracks


def search_track(access_token: str, titulo: str, artista: str = "", album: str = "") -> str | None:
    query_options = []
    if artista and album:
        query_options.append(f"{artista} {titulo} {album}")
    if artista:
        query_options.append(f"{artista} {titulo}")
    query_options.append(titulo)

    for query in query_options:
        response = requests.get(
            f"{API_V1}/tracks",
            params={"q": query, "limit": 10, "linked_partitioning": "false"},
            headers=_auth_headers(access_token),
            timeout=15,
        )
        if response.status_code != 200:
            continue
        results = response.json()
        collection = results if isinstance(results, list) else results.get("collection") or []
        ranked = sorted(
            ((track, _score_track(track, titulo, artista, album)) for track in collection),
            key=lambda item: item[1],
            reverse=True,
        )
        if ranked and ranked[0][1] >= 35 and ranked[0][0].get("id"):
            return str(ranked[0][0]["id"])
        for track in collection:
            track_id = track.get("id")
            if track_id:
                return str(track_id)
    return None


def create_playlist(access_token: str, nome: str, descricao: str = "") -> dict[str, str]:
    response = requests.post(
        f"{API_V1}/playlists",
        headers=_auth_headers(access_token),
        json={
            "playlist": {
                "title": nome,
                "description": descricao or "Transferida via PlayTransfer",
                "sharing": "private",
                "tracks": [],
            }
        },
        timeout=20,
    )
    if response.status_code not in (200, 201):
        raise ValueError(f"Nao foi possivel criar playlist no SoundCloud (HTTP {response.status_code}).")

    data = response.json()
    playlist_id = data.get("id")
    if not playlist_id:
        raise ValueError("SoundCloud nao retornou o ID da playlist criada.")
    return {
        "id": str(playlist_id),
        "url": data.get("permalink_url") or f"https://soundcloud.com/you/sets/{playlist_id}",
    }


def add_tracks(access_token: str, playlist_id: str, track_ids: list[str]) -> None:
    if not track_ids:
        return

    tracks_payload = []
    for track_id in track_ids:
        try:
            tracks_payload.append({"id": int(track_id)})
        except Exception:
            continue
    if not tracks_payload:
        return

    response = requests.put(
        f"{API_V1}/playlists/{playlist_id}",
        headers=_auth_headers(access_token),
        json={"playlist": {"tracks": tracks_payload}},
        timeout=30,
    )
    if response.status_code not in (200, 201):
        raise ValueError(f"Nao foi possivel adicionar faixas no SoundCloud (HTTP {response.status_code}).")
