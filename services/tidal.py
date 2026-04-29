"""
services/tidal.py - PlayTransfer
Leitura e escrita no TIDAL via tidalapi.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import re
import urllib.parse
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
    raw = str(url or "").strip()
    match = re.search(r"/(?:browse/)?playlist/([0-9a-fA-F-]{36})", raw)
    if match:
        return match.group(1)

    try:
        parsed = urllib.parse.urlparse(raw)
        params = urllib.parse.parse_qs(parsed.query)
        for key in ("playlistId", "playlist_id", "uuid", "id"):
            value = (params.get(key) or [""])[0]
            if re.fullmatch(r"[0-9a-fA-F-]{36}", value):
                return value
    except Exception:
        pass

    if re.fullmatch(r"[0-9a-fA-F-]{36}", raw):
        return raw
    raise ValueError("URL do TIDAL invalida. Use um link de playlist.")


def _clean(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _track_score(track: Any, titulo: str, artista: str, album: str = "") -> int:
    wanted_title = _clean(titulo)
    wanted_artist = _clean(artista)
    wanted_album = _clean(album)
    found_title = _clean(getattr(track, "title", ""))

    artists = getattr(track, "artists", None) or []
    found_artist = _clean(" ".join(
        (getattr(artist, "name", "") or "")
        for artist in artists
        if getattr(artist, "name", None)
    ))
    if not found_artist and getattr(track, "artist", None):
        found_artist = _clean(getattr(track.artist, "name", ""))

    found_album = ""
    if getattr(track, "album", None):
        found_album = _clean(getattr(track.album, "name", ""))

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
            results = tidal_session.search(query, models=[tidalapi.Track], limit=10)
        except Exception:
            continue
        tracks = results.get("tracks") or []
        ranked = sorted(
            ((track, _track_score(track, titulo, artista, album)) for track in tracks),
            key=lambda item: item[1],
            reverse=True,
        )
        if ranked and ranked[0][1] >= 35:
            return str(ranked[0][0].id)
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
    added_any = False
    for start in range(0, len(track_ids), 100):
        chunk = track_ids[start : start + 100]
        try:
            playlist.add(chunk, allow_duplicates=False, limit=100)
            added_any = True
            continue
        except Exception:
            pass

        for track_id in chunk:
            try:
                playlist.add([track_id], allow_duplicates=False, limit=1)
                added_any = True
            except Exception:
                continue

    if not added_any:
        raise ValueError("Nao consegui adicionar faixas no TIDAL com esta sessao. Reconecte o TIDAL e tente novamente.")
