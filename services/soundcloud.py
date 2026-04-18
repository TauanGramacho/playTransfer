"""
services/soundcloud.py - PlayTransfer
Leitura publica e escrita autenticada no SoundCloud.
"""
from __future__ import annotations

import os
import re
from typing import Any

import requests

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

    response = requests.put(
        f"{API_V1}/playlists/{playlist_id}",
        headers=_auth_headers(access_token),
        json={"playlist": {"tracks": [{"id": int(track_id)} for track_id in track_ids]}},
        timeout=20,
    )
    if response.status_code not in (200, 201):
        raise ValueError(f"Nao foi possivel adicionar faixas no SoundCloud (HTTP {response.status_code}).")
