"""
services/tidal.py - PlayTransfer
Leitura e escrita no TIDAL via tidalapi.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import re
from typing import Any

import tidalapi


def start_device_login() -> tuple[tidalapi.Session, tidalapi.session.LinkLogin, concurrent.futures.Future[Any]]:
    session = tidalapi.Session()
    login, future = session.login_oauth()
    return session, login, future


def load_session(
    access_token: str,
    refresh_token: str | None = None,
    token_type: str = "Bearer",
    expiry_time: dt.datetime | None = None,
) -> tidalapi.Session:
    session = tidalapi.Session()
    ok = session.load_oauth_session(
        token_type=token_type,
        access_token=access_token,
        refresh_token=refresh_token,
        expiry_time=expiry_time,
    )
    if not ok:
        raise ValueError("Nao foi possivel restaurar a sessao do TIDAL.")
    return session


def validate(session: tidalapi.Session) -> dict[str, str]:
    if not session or not session.check_login():
        raise ValueError("Sessao do TIDAL nao encontrada ou expirada.")

    user = session.user
    display_name = (
        getattr(user, "username", "")
        or " ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part)
        or "Usuario TIDAL"
    )
    return {"display_name": display_name}


def _extract_playlist_id(url: str) -> str:
    match = re.search(r"/playlist/([0-9a-fA-F\\-]{36})", url)
    if not match:
        raise ValueError("URL do TIDAL invalida. Use um link de playlist.")
    return match.group(1)


def read_playlist(url: str, tidal_session: tidalapi.Session) -> tuple[str, list[dict[str, str]]]:
    if not tidal_session or not tidal_session.check_login():
        raise ValueError("Conecte o TIDAL antes de ler playlists.")

    playlist_id = _extract_playlist_id(url)
    playlist = tidal_session.playlist(playlist_id)
    tracks: list[dict[str, str]] = []
    offset = 0
    page_size = 100

    while True:
        page = playlist.tracks(limit=page_size, offset=offset)
        if not page:
            break
        for track in page:
            title = (getattr(track, "title", "") or "").strip()
            if not title:
                continue
            artists = getattr(track, "artists", None) or []
            artist_name = ", ".join(
                (getattr(artist, "name", "") or "").strip()
                for artist in artists
                if getattr(artist, "name", None)
            )
            if not artist_name and getattr(track, "artist", None):
                artist_name = (getattr(track.artist, "name", "") or "").strip()

            album = getattr(track, "album", None)
            album_name = (getattr(album, "name", "") or "").strip() if album else ""
            tracks.append({"titulo": title, "artista": artist_name, "album": album_name})

        if len(page) < page_size:
            break
        offset += len(page)

    if not tracks:
        raise ValueError("A playlist do TIDAL nao retornou faixas.")

    return (getattr(playlist, "name", "") or "TIDAL Playlist"), tracks


def search_track(
    tidal_session: tidalapi.Session,
    titulo: str,
    artista: str = "",
    album: str = "",
) -> str | None:
    queries = []
    if artista and album:
        queries.append(f"{artista} {titulo} {album}")
    if artista:
        queries.append(f"{artista} {titulo}")
    queries.append(titulo)

    for query in queries:
        try:
            results = tidal_session.search(query, models=[tidalapi.Track], limit=5)
        except Exception:
            continue
        tracks = results.get("tracks") or []
        if tracks:
            return str(tracks[0].id)
    return None


def create_playlist(tidal_session: tidalapi.Session, nome: str, descricao: str = "") -> dict[str, str]:
    if not tidal_session or not tidal_session.check_login():
        raise ValueError("Conecte o TIDAL antes de criar playlists.")
    if not getattr(tidal_session, "user", None):
        raise ValueError("Usuario do TIDAL nao encontrado.")

    playlist = tidal_session.user.create_playlist(
        nome,
        descricao or "Transferida via PlayTransfer",
    )
    playlist_id = str(playlist.id)
    return {
        "id": playlist_id,
        "url": getattr(playlist, "share_url", "") or f"https://listen.tidal.com/playlist/{playlist_id}",
    }


def add_tracks(tidal_session: tidalapi.Session, playlist_id: str, track_ids: list[str]) -> None:
    if not track_ids:
        return
    playlist = tidal_session.playlist(playlist_id)
    if not hasattr(playlist, "add"):
        raise ValueError("A playlist do TIDAL criada nao esta editavel por esta conta.")
    for start in range(0, len(track_ids), 100):
        chunk = track_ids[start : start + 100]
        playlist.add(chunk, allow_duplicates=False, limit=100)
