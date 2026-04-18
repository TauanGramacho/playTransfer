"""
services/amazon_music.py - PlayTransfer
Leitura e escrita no Amazon Music Web API.
"""
from __future__ import annotations

import os
import re
from typing import Any

import requests

API_BASE = "https://api.music.amazon.dev/v1"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


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
        f"{API_BASE}{path}",
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


def _extract_playlist_id(url: str) -> str:
    match = re.search(r"/playlists/([A-Za-z0-9\\-]+)", url)
    if not match:
        raise ValueError("URL do Amazon Music invalida. Use um link de playlist.")
    return match.group(1)


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
    payload = _request(
        "GET",
        "/me/playlists",
        api_key,
        access_token,
        params={"limit": 1},
    )
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
            params={"limit": 100, **({"cursor": cursor} if cursor else {})},
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
        search_sets.append(
            [
                {"field": "name", "query": titulo},
                {"field": "artistName", "query": artista},
                {"field": "albumName", "query": album},
            ]
        )
    if titulo and artista:
        search_sets.append(
            [
                {"field": "name", "query": titulo},
                {"field": "artistName", "query": artista},
            ]
        )
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
