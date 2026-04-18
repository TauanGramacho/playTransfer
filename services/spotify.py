"""
Spotify helpers for PlayTransfer.
"""

import json
import os
import re
import time

import requests

_token_cache: dict = {"token": None, "expires": 0, "key": None}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


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
    return raw


def _extract_sp_dc(value: str | None) -> str:
    raw = _as_clean_text(value)
    if not raw:
        return ""
    if "sp_dc=" in raw:
        raw = raw.split("sp_dc=", 1)[1].split(";", 1)[0].strip()
    return "" if _is_placeholder_sp_dc(raw) else raw


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
    response = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {token}", "User-Agent": UA},
        timeout=10,
    )
    if response.status_code == 200:
        data = response.json()
        return {
            "display_name": data.get("display_name", "Usuario Spotify"),
            "email": data.get("email", ""),
            "avatar": (data.get("images") or [{}])[0].get("url", ""),
        }

    return {"display_name": "Usuario Spotify", "email": "", "avatar": ""}


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
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": UA}
    endpoint = "playlists" if media_type == "playlist" else "albums"

    response = requests.get(
        f"https://api.spotify.com/v1/{endpoint}/{playlist_id}",
        headers=headers,
        timeout=10,
    )
    if response.status_code == 401:
        raise ValueError("Sessao do Spotify expirada. Conecte novamente.")
    if response.status_code == 404:
        raise ValueError("Playlist nao encontrada. Verifique se ela esta publica ou se voce tem acesso.")
    if response.status_code != 200:
        raise ValueError(f"Erro do Spotify (HTTP {response.status_code})")

    info = response.json()
    playlist_name = info.get("name", "Spotify Playlist")
    tracks: list[dict] = []
    offset = 0

    while True:
        page_response = requests.get(
            f"https://api.spotify.com/v1/{endpoint}/{playlist_id}/tracks",
            headers=headers,
            params={
                "limit": 100,
                "offset": offset,
                "fields": "items(track(name,artists(name),album(name))),next",
            },
            timeout=15,
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
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA}
    endpoint = "playlists" if media_type == "playlist" else "albums"

    info_response = requests.get(
        f"https://api.spotify.com/v1/{endpoint}/{playlist_id}",
        headers=headers,
        timeout=10,
    )
    if info_response.status_code == 401:
        _token_cache["token"] = None
        raise ValueError("Token do Spotify expirou. Reconecte o Spotify.")
    if info_response.status_code == 404:
        raise ValueError("Playlist nao encontrada. Verifique se ela esta publica.")
    if info_response.status_code != 200:
        raise ValueError(f"Erro do Spotify (HTTP {info_response.status_code})")

    info = info_response.json()
    playlist_name = info.get("name", "Spotify Playlist")
    tracks = []
    offset = 0

    while True:
        page_response = requests.get(
            f"https://api.spotify.com/v1/{endpoint}/{playlist_id}/tracks",
            headers=headers,
            params={
                "limit": 100,
                "offset": offset,
                "fields": "items(track(name,artists(name),album(name))),next",
            },
            timeout=15,
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


def search_track(access_token: str, titulo: str, artista: str = "", album: str = "") -> str | None:
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

    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": UA}

    for query in queries:
        try:
            response = requests.get(
                "https://api.spotify.com/v1/search",
                headers=headers,
                params={"q": query, "type": "track", "limit": 5},
                timeout=10,
            )
            if response.status_code != 200:
                continue
            items = response.json().get("tracks", {}).get("items", [])
            if items:
                return items[0].get("uri")
        except Exception:
            continue

    return None


def create_playlist(access_token: str, nome: str, descricao: str = "") -> str:
    """Create a private playlist on Spotify and return its id."""
    if not access_token:
        raise ValueError("Access token do Spotify nao informado.")

    response = requests.post(
        "https://api.spotify.com/v1/me/playlists",
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": UA,
            "Content-Type": "application/json",
        },
        json={
            "name": nome,
            "description": descricao or "Transferida via PlayTransfer",
            "public": False,
        },
        timeout=15,
    )

    if response.status_code not in (200, 201):
        raise ValueError(f"Nao foi possivel criar playlist no Spotify (HTTP {response.status_code}).")

    playlist_id = response.json().get("id")
    if not playlist_id:
        raise ValueError("Spotify nao retornou o ID da playlist criada.")
    return playlist_id


def add_tracks(access_token: str, playlist_id: str, track_uris: list[str]) -> None:
    """Add track URIs to a Spotify playlist in batches."""
    if not access_token:
        raise ValueError("Access token do Spotify nao informado.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": UA,
        "Content-Type": "application/json",
    }

    for index in range(0, len(track_uris), 100):
        chunk = track_uris[index : index + 100]
        response = requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
            headers=headers,
            json={"uris": chunk},
            timeout=15,
        )
        if response.status_code not in (200, 201):
            raise ValueError(f"Erro ao adicionar faixas no Spotify (HTTP {response.status_code}).")
