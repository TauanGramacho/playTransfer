"""
services/apple_music.py — PlayTransfer
Leitura pública e escrita autenticada no Apple Music API.
"""
import json
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
API_BASE = "https://amp-api.music.apple.com/v1"
API_FALLBACK_BASE = "https://amp-api-edge.music.apple.com/v1"


def _request(method: str, path: str, **kwargs):
    last_response = None
    last_error = None
    for base_url in (API_BASE, API_FALLBACK_BASE):
        try:
            response = requests.request(method, f"{base_url}{path}", timeout=15, **kwargs)
            last_response = response
            if response.status_code >= 500:
                continue
            return response
        except Exception as exc:
            last_error = exc
            continue
    if last_response is not None:
        return last_response
    raise last_error or RuntimeError("Apple Music API indisponivel.")


def _headers(
    developer_token: str,
    music_user_token: str | None = None,
    cookie_header: str | None = None,
) -> dict:
    headers = {
        "Authorization": f"Bearer {developer_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Origin": "https://music.apple.com",
        "Referer": "https://music.apple.com/",
    }
    if music_user_token:
        headers["Music-User-Token"] = music_user_token
        headers["media-user-token"] = music_user_token
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def _params(base: dict | None = None, itfe: str | None = None) -> dict:
    params = dict(base or {})
    if itfe:
        params["itfe"] = itfe
    return params


def validate(
    developer_token: str,
    music_user_token: str,
    storefront: str = "us",
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> dict:
    if not developer_token:
        raise ValueError("Developer token da Apple Music não fornecido.")
    if not music_user_token:
        raise ValueError("Music user token da Apple Music não fornecido.")

    r = _request(
        "GET",
        "/me/library/playlists",
        headers=_headers(developer_token, music_user_token, cookie_header),
        params=_params({"limit": 1, "l": "pt-BR"}, itfe),
    )
    if r.status_code != 200:
        raise ValueError(f"Apple Music rejeitou os tokens (HTTP {r.status_code}).")

    return {
        "display_name": f"Apple Music ({storefront.upper()})",
        "storefront": storefront.lower(),
    }


def read_playlist(url: str) -> tuple[str, list[dict]]:
    """
    Lê playlist pública da Apple Music via scraping do JSON-LD.
    URL: https://music.apple.com/br/playlist/nome/pl.xxxxxx
    """
    if "music.apple.com" not in url:
        raise ValueError("URL da Apple Music inválida.")

    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        if r.status_code != 200:
            raise ValueError(f"Apple Music retornou HTTP {r.status_code}")

        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL)
        if not match:
            raise ValueError("Não foi possível extrair os dados da playlist.")

        data = json.loads(match.group(1))
        nome = data.get("name", "Apple Music Playlist")
        faixas = []

        for track in data.get("track", []):
            titulo = track.get("name", "")
            artista = ""
            if "byArtist" in track:
                artista = track["byArtist"].get("name", "") if isinstance(track["byArtist"], dict) else track["byArtist"]
            album = ""
            if "inAlbum" in track:
                album = track["inAlbum"].get("name", "") if isinstance(track["inAlbum"], dict) else track["inAlbum"]
            if titulo:
                faixas.append({"titulo": titulo, "artista": artista, "album": album})

        if not faixas:
            raise ValueError("A playlist pública não retornou faixas.")

        return nome, faixas
    except Exception as e:
        raise ValueError(f"Apple Music: não foi possível ler a playlist ({e}).")


def search_track(
    developer_token: str,
    storefront: str,
    titulo: str,
    artista: str = "",
    album: str = "",
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> str | None:
    headers = _headers(developer_token, cookie_header=cookie_header)
    queries = []
    if artista and album:
        queries.append(f"{artista} {titulo} {album}")
    if artista:
        queries.append(f"{artista} {titulo}")
    queries.append(titulo)

    for query in queries:
        try:
            r = _request(
                "GET",
                f"/catalog/{storefront}/search",
                headers=headers,
                params=_params({
                    "term": query,
                    "types": "songs",
                    "limit": 5,
                    "l": "pt-BR",
                }, itfe),
            )
            if r.status_code != 200:
                continue
            items = (((r.json() or {}).get("results") or {}).get("songs") or {}).get("data") or []
            if items:
                return items[0].get("id")
        except Exception:
            continue

    return None


def create_playlist(
    developer_token: str,
    music_user_token: str,
    nome: str,
    descricao: str = "",
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> str:
    r = _request(
        "POST",
        "/me/library/playlists",
        headers=_headers(developer_token, music_user_token, cookie_header),
        params=_params({}, itfe),
        json={
            "attributes": {
                "name": nome,
                "description": descricao or "Transferida via PlayTransfer",
            }
        },
    )
    if r.status_code not in (200, 201):
        raise ValueError(f"Não foi possível criar playlist na Apple Music (HTTP {r.status_code}).")

    playlist_id = ((r.json() or {}).get("data") or [{}])[0].get("id")
    if not playlist_id:
        raise ValueError("Apple Music não retornou o ID da playlist criada.")
    return playlist_id


def add_tracks(
    developer_token: str,
    music_user_token: str,
    playlist_id: str,
    track_ids: list[str],
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> None:
    if not track_ids:
        return

    headers = _headers(developer_token, music_user_token, cookie_header)
    for i in range(0, len(track_ids), 100):
        chunk = track_ids[i:i + 100]
        r = _request(
            "POST",
            f"/me/library/playlists/{playlist_id}/tracks",
            headers=headers,
            params=_params({}, itfe),
            json={"data": [{"id": track_id, "type": "songs"} for track_id in chunk]},
        )
        if r.status_code not in (200, 201, 202, 204):
            raise ValueError(f"Erro ao adicionar faixas na Apple Music (HTTP {r.status_code}).")
