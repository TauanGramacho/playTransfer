"""
services/amazon_music.py - PlayTransfer
Leitura e escrita no Amazon Music.

Suporta dois modos de autenticação:
  1. OAuth oficial  (API fechada beta - requer developer credentials)
  2. Cookies de sessão (unofficial - capturado pelo amazon_webview.py)
"""
from __future__ import annotations

import os
import re
import json
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

# ─── API oficial ────────────────────────────────────────────────────────────
OFFICIAL_API_BASE = "https://api.music.amazon.dev/v1"

# ─── API não-oficial (web player interno) ───────────────────────────────────
# A região pode ser .com, .com.br, .co.uk, .de, .co.jp etc.
UNOFFICIAL_BASE = "https://music.amazon.{region}/v1"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ════════════════════════════════════════════════════════════════════════════
# MODO 1 — API OFICIAL (mantida para compatibilidade)
# ════════════════════════════════════════════════════════════════════════════

def _headers(api_key: str, access_token: str, accept_language: str = "pt-BR") -> dict[str, str]:
    if not api_key:
        raise ValueError("API key do Amazon Music nao fornecida.")
    if not access_token:
        raise ValueError("Access token do Amazon Music nao fornecido.")
    return {
        "x-api-key": api_key,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": accept_language,
        "User-Agent": UA,
    }


def _request(
    method: str,
    path: str,
    api_key: str,
    access_token: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.request(
        method,
        f"{OFFICIAL_API_BASE}{path}",
        headers=_headers(api_key, access_token),
        params=params,
        json=json_body,
        timeout=20,
    )

    if response.status_code == 401:
        raise ValueError("Amazon Music rejeitou as credenciais. Verifique API key e access token.")
    if response.status_code == 403:
        raise ValueError(
            "Sua conta/app nao tem permissao para esse endpoint do Amazon Music. "
            "A Web API oficial ainda esta em beta fechado."
        )
    if response.status_code == 404:
        raise ValueError("Playlist do Amazon Music nao encontrada.")
    if response.status_code >= 400:
        message = ""
        try:
            payload = response.json()
            message = payload.get("message") or payload.get("code") or ""
        except Exception:
            message = response.text[:200]
        suffix = f" {message}" if message else ""
        raise ValueError(f"Amazon Music retornou HTTP {response.status_code}.{suffix}".strip())

    try:
        return response.json()
    except Exception as exc:
        raise ValueError(f"Amazon Music retornou uma resposta invalida: {exc}") from exc


def _clean_playlist_id(value: str) -> str:
    cleaned = unquote(str(value or "")).strip().strip("\"' ")
    cleaned = cleaned.strip("/?#&")
    cleaned = re.split(r"[/#?&]", cleaned, maxsplit=1)[0]
    if re.fullmatch(r"[A-Za-z0-9_.:-]{4,}", cleaned):
        return cleaned
    return ""


def _extract_playlist_id(url: str) -> str:
    raw = unquote(str(url or "").strip())
    parsed = urlparse(raw)
    query = parse_qs(parsed.query)

    for key in ("playlistId", "playlistID", "playlist_id", "id"):
        for value in query.get(key, []):
            playlist_id = _clean_playlist_id(value)
            if playlist_id:
                return playlist_id

    patterns = [
        r"/my/playlists/([^/?#&]+)",
        r"/user-playlists/([^/?#&]+)",
        r"/playlists/([^/?#&]+)",
        r"/playlist/([^/?#&]+)",
        r"uri:///playlist/([^/?#&]+)",
        r"(?:playlistId|playlistID|playlist_id)[=:%22\"']+([A-Za-z0-9_.:-]+)",
    ]
    for text in (parsed.path, raw):
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                playlist_id = _clean_playlist_id(match.group(1))
                if playlist_id:
                    return playlist_id

    raise ValueError("URL do Amazon Music invalida. Use um link de playlist.")


def _read_track_node(node: dict[str, Any]) -> dict[str, str] | None:
    title = (node.get("title") or node.get("name") or "").strip()
    if not title:
        return None

    artists = node.get("artists") or node.get("artist") or []
    if isinstance(artists, dict):
        artists = [artists]
    artist_name = ", ".join(
        (artist.get("name") or artist.get("title") or "").strip()
        for artist in artists
        if isinstance(artist, dict) and (artist.get("name") or artist.get("title"))
    )

    album = node.get("album") or {}
    if isinstance(album, dict):
        album_name = (album.get("title") or album.get("name") or "").strip()
    else:
        album_name = str(album or "").strip()

    return {"titulo": title, "artista": artist_name, "album": album_name}


def validate(api_key: str, access_token: str, country_code: str = "US") -> dict[str, str]:
    payload = _request("GET", "/me/playlists", api_key, access_token, params={"limit": 1})
    data = payload.get("data") or {}
    user = data.get("user") or {}
    customer = user.get("customer") or {}
    display_name = (
        customer.get("name")
        or customer.get("displayName")
        or user.get("name")
        or "Amazon Music"
    )
    return {
        "display_name": display_name,
        "country_code": (country_code or os.getenv("AMAZON_MUSIC_COUNTRY_CODE", "US")).upper(),
    }


def read_playlist(url: str, api_key: str, access_token: str) -> tuple[str, list[dict[str, str]]]:
    playlist_id = _extract_playlist_id(url)
    cursor = None
    tracks: list[dict[str, str]] = []
    playlist_name = "Amazon Music Playlist"

    while True:
        payload = _request(
            "GET",
            f"/playlists/{playlist_id}/tracks",
            api_key,
            access_token,
            params={"limit": 100, **( {"cursor": cursor} if cursor else {})},
        )
        playlist = ((payload.get("data") or {}).get("playlist") or {})
        playlist_name = playlist.get("title") or playlist_name
        tracks_data = playlist.get("tracks") or {}

        for edge in tracks_data.get("edges") or []:
            node = edge.get("node") or {}
            normalized = _read_track_node(node)
            if normalized:
                tracks.append(normalized)

        page_info = tracks_data.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("token")
        if not cursor:
            break

    if not tracks:
        raise ValueError(
            "Nao foi possivel ler as faixas da playlist do Amazon Music. "
            "Verifique se a playlist esta acessivel para essa conta."
        )

    return playlist_name, tracks


def search_track(
    api_key: str,
    access_token: str,
    titulo: str,
    artista: str = "",
    album: str = "",
) -> str | None:
    search_sets = []
    if titulo and artista and album:
        search_sets.append([
            {"field": "name", "query": titulo},
            {"field": "artistName", "query": artista},
            {"field": "albumName", "query": album},
        ])
    if titulo and artista:
        search_sets.append([
            {"field": "name", "query": titulo},
            {"field": "artistName", "query": artista},
        ])
    if titulo:
        search_sets.append([{"field": "name", "query": titulo}])

    for filters in search_sets:
        payload = _request(
            "POST",
            "/search/tracks",
            api_key,
            access_token,
            json_body={"searchFilters": filters, "limit": 5, "sortBy": "relevance"},
        )
        edges = ((((payload.get("data") or {}).get("searchTracks") or {}).get("edges")) or [])
        if edges:
            node = edges[0].get("node") or {}
            track_id = node.get("id")
            if track_id:
                return str(track_id)
    return None


def create_playlist(api_key: str, access_token: str, nome: str, descricao: str = "") -> dict[str, str]:
    payload = _request(
        "POST",
        "/playlists",
        api_key,
        access_token,
        json_body={
            "title": nome,
            "description": descricao or "Transferida via PlayTransfer",
            "visibility": "PRIVATE",
        },
    )
    playlist = ((payload.get("data") or {}).get("createPlaylist") or {})
    playlist_id = playlist.get("id")
    if not playlist_id:
        raise ValueError("Amazon Music nao retornou o ID da playlist criada.")

    playlist_url = playlist.get("url") or f"https://music.amazon.com/my/playlists/{playlist_id}"
    return {"id": str(playlist_id), "url": playlist_url}


def add_tracks(api_key: str, access_token: str, playlist_id: str, track_ids: list[str]) -> None:
    if not track_ids:
        return

    for start in range(0, len(track_ids), 100):
        chunk = track_ids[start : start + 100]
        _request(
            "PUT",
            f"/playlists/{playlist_id}/tracks",
            api_key,
            access_token,
            json_body={"trackIds": chunk, "addDuplicateTracks": False},
        )


# ════════════════════════════════════════════════════════════════════════════
# MODO 2 — COOKIES DE SESSÃO (unofficial, igual ao Deezer)
# ════════════════════════════════════════════════════════════════════════════

def _session_headers(session_cookies: dict, csrf_token: str = "") -> dict:
    """Headers para a API interna do web player."""
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://music.amazon.com/",
        "Origin": "https://music.amazon.com",
    }
    if csrf_token:
        headers["x-music-csrf-token"] = csrf_token
        headers["anti-csrftoken-a2z"] = csrf_token
    return headers


def _get_session_region(session_cookies: dict) -> str:
    """Detecta a região do usuário pelo cookie ou usa 'com' como padrão."""
    region = session_cookies.get("_region", "com")
    return region if region else "com"


def _session_request(
    method: str,
    path: str,
    session_cookies: dict,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    region = _get_session_region(session_cookies)
    csrf   = session_cookies.get("_csrf_token", "") or session_cookies.get("csrf-main", "")
    # Remove internal meta keys before sending
    cookies_clean = {k: v for k, v in session_cookies.items() if not k.startswith("_")}

    base = f"https://music.amazon.{region}"
    url  = f"{base}{path}"

    resp = requests.request(
        method,
        url,
        headers=_session_headers(session_cookies, csrf),
        cookies=cookies_clean,
        params=params,
        json=json_body,
        timeout=20,
    )

    if resp.status_code == 401:
        raise ValueError("Sessão do Amazon Music expirou. Reconecte sua conta.")
    if resp.status_code == 403:
        raise ValueError("Amazon Music recusou a solicitação. Tente reconectar sua conta.")
    if resp.status_code == 404:
        raise ValueError("Playlist do Amazon Music não encontrada.")
    if resp.status_code >= 400:
        msg = ""
        try:
            msg = resp.json().get("message") or resp.json().get("code") or ""
        except Exception:
            msg = resp.text[:200]
        raise ValueError(f"Amazon Music retornou HTTP {resp.status_code}. {msg}".strip())

    try:
        return resp.json()
    except Exception:
        return {"_raw": resp.text}


def validate_via_session(session_cookies: dict) -> dict[str, str]:
    """Valida os cookies capturados chamando a API interna do web player."""
    region = _get_session_region(session_cookies)
    cookies_clean = {k: v for k, v in session_cookies.items() if not k.startswith("_")}
    csrf   = session_cookies.get("_csrf_token", "") or session_cookies.get("csrf-main", "")

    # Tenta obter info do usuário via endpoint interno
    resp = requests.get(
        f"https://music.amazon.{region}/v1/user/settings",
        headers=_session_headers(session_cookies, csrf),
        cookies=cookies_clean,
        timeout=15,
    )

    display_name = "Amazon Music"
    if resp.status_code == 200:
        try:
            data = resp.json()
            display_name = (
                (data.get("data") or {}).get("customerName")
                or (data.get("data") or {}).get("displayName")
                or display_name
            )
        except Exception:
            pass
    elif resp.status_code in (401, 403):
        raise ValueError("Sessão inválida. Faça login novamente no Amazon Music.")

    # Tenta extrair nome do cookie ubid-main
    if display_name == "Amazon Music":
        ubid = session_cookies.get("ubid-main", "")
        if ubid:
            display_name = f"Amazon Music ({ubid[:8]}...)"

    return {"display_name": display_name, "region": region}


def read_playlist_via_session(
    url: str, session_cookies: dict
) -> tuple[str, list[dict[str, str]]]:
    playlist_id   = _extract_playlist_id(url)
    region        = _get_session_region(session_cookies)
    cookies_clean = {k: v for k, v in session_cookies.items() if not k.startswith("_")}
    csrf          = session_cookies.get("_csrf_token", "") or session_cookies.get("csrf-main", "")

    tracks: list[dict[str, str]] = []
    playlist_name = "Amazon Music Playlist"
    next_token = None

    while True:
        params: dict = {"limit": 100}
        if next_token:
            params["nextToken"] = next_token

        resp = requests.get(
            f"https://music.amazon.{region}/v1/playlists/{playlist_id}/tracks",
            headers=_session_headers(session_cookies, csrf),
            cookies=cookies_clean,
            params=params,
            timeout=20,
        )

        if resp.status_code in (401, 403):
            raise ValueError("Sessão expirada. Reconecte o Amazon Music.")
        if resp.status_code == 404:
            raise ValueError("Playlist não encontrada.")
        if resp.status_code >= 400:
            raise ValueError(f"Erro ao ler playlist: HTTP {resp.status_code}")

        try:
            data = resp.json()
        except Exception:
            raise ValueError("Amazon Music retornou resposta inválida.")

        playlist = (data.get("playlist") or data.get("data") or {})
        if isinstance(playlist, dict) and "playlist" in playlist:
            playlist = playlist["playlist"]

        playlist_name = playlist.get("title") or playlist.get("name") or playlist_name
        items = playlist.get("tracks") or playlist.get("items") or data.get("items") or []

        if isinstance(items, dict):
            edges = items.get("edges") or items.get("items") or []
        else:
            edges = items

        for edge in edges:
            node = edge.get("node") or edge if isinstance(edge, dict) else {}
            normalized = _read_track_node(node)
            if normalized:
                tracks.append(normalized)

        # Paginação
        next_token = (
            (data.get("nextToken"))
            or ((playlist.get("tracks") or {}).get("nextToken") if isinstance(playlist.get("tracks"), dict) else None)
        )
        if not next_token:
            break

    if not tracks:
        raise ValueError(
            "Não foi possível ler as faixas da playlist. "
            "Verifique se a playlist é pública ou se a conta está conectada."
        )

    return playlist_name, tracks


def search_track_via_session(
    session_cookies: dict,
    titulo: str,
    artista: str = "",
) -> str | None:
    region        = _get_session_region(session_cookies)
    cookies_clean = {k: v for k, v in session_cookies.items() if not k.startswith("_")}
    csrf          = session_cookies.get("_csrf_token", "") or session_cookies.get("csrf-main", "")

    query = f"{titulo} {artista}".strip()

    resp = requests.get(
        f"https://music.amazon.{region}/v1/search",
        headers=_session_headers(session_cookies, csrf),
        cookies=cookies_clean,
        params={"keywords": query, "includeTypes": "track", "limit": 5},
        timeout=15,
    )

    if resp.status_code >= 400:
        return None

    try:
        data = resp.json()
        results = (
            (data.get("data") or {}).get("searchTracks")
            or data.get("searchTracks")
            or data.get("tracks")
            or {}
        )
        edges = results.get("edges") or results.get("items") or []
        if edges:
            node = edges[0].get("node") or edges[0]
            return str(node.get("id") or "")
    except Exception:
        pass
    return None


def create_playlist_via_session(
    session_cookies: dict,
    nome: str,
    descricao: str = "",
) -> dict[str, str]:
    region        = _get_session_region(session_cookies)
    cookies_clean = {k: v for k, v in session_cookies.items() if not k.startswith("_")}
    csrf          = session_cookies.get("_csrf_token", "") or session_cookies.get("csrf-main", "")

    resp = requests.post(
        f"https://music.amazon.{region}/v1/playlists",
        headers=_session_headers(session_cookies, csrf),
        cookies=cookies_clean,
        json={
            "title":       nome,
            "description": descricao or "Transferida via PlayTransfer",
            "visibility":  "PRIVATE",
        },
        timeout=20,
    )

    if resp.status_code in (401, 403):
        raise ValueError("Sessão expirada. Reconecte o Amazon Music.")
    if resp.status_code >= 400:
        raise ValueError(f"Erro ao criar playlist: HTTP {resp.status_code}")

    try:
        data     = resp.json()
        playlist = (data.get("data") or {}).get("createPlaylist") or data.get("playlist") or data
        pl_id    = playlist.get("id") or playlist.get("playlistId")
        pl_url   = playlist.get("url") or f"https://music.amazon.{region}/my/playlists/{pl_id}"
        if not pl_id:
            raise ValueError("Amazon Music não retornou o ID da playlist criada.")
        return {"id": str(pl_id), "url": pl_url}
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Resposta inválida ao criar playlist: {exc}") from exc


def add_tracks_via_session(
    session_cookies: dict,
    playlist_id: str,
    track_ids: list[str],
) -> None:
    if not track_ids:
        return

    region        = _get_session_region(session_cookies)
    cookies_clean = {k: v for k, v in session_cookies.items() if not k.startswith("_")}
    csrf          = session_cookies.get("_csrf_token", "") or session_cookies.get("csrf-main", "")

    for start in range(0, len(track_ids), 100):
        chunk = track_ids[start : start + 100]
        resp = requests.put(
            f"https://music.amazon.{region}/v1/playlists/{playlist_id}/tracks",
            headers=_session_headers(session_cookies, csrf),
            cookies=cookies_clean,
            json={"trackIds": chunk, "addDuplicateTracks": False},
            timeout=20,
        )
        if resp.status_code in (401, 403):
            raise ValueError("Sessão expirada ao adicionar músicas.")
        if resp.status_code >= 400:
            raise ValueError(f"Erro ao adicionar músicas: HTTP {resp.status_code}")
