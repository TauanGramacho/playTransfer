"""
services/apple_music.py — PlayTransfer
Leitura pública e escrita autenticada no Apple Music API.
"""
import json
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
API_BASE = "https://api.music.apple.com/v1"


def _headers(developer_token: str, music_user_token: str | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {developer_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": UA,
    }
    if music_user_token:
        headers["Music-User-Token"] = music_user_token
    return headers


def validate(developer_token: str, music_user_token: str, storefront: str = "us") -> dict:
    if not developer_token:
        raise ValueError("Developer token da Apple Music não fornecido.")
    if not music_user_token:
        raise ValueError("Music user token da Apple Music não fornecido.")

    r = requests.get(
        f"{API_BASE}/me/library/playlists",
        headers=_headers(developer_token, music_user_token),
        params={"limit": 1, "l": "pt-BR"},
        timeout=15,
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


def search_track(developer_token: str, storefront: str, titulo: str, artista: str = "", album: str = "") -> str | None:
    headers = _headers(developer_token)
    queries = []
    if artista and album:
        queries.append(f"{artista} {titulo} {album}")
    if artista:
        queries.append(f"{artista} {titulo}")
    queries.append(titulo)

    for query in queries:
        try:
            r = requests.get(
                f"{API_BASE}/catalog/{storefront}/search",
                headers=headers,
                params={
                    "term": query,
                    "types": "songs",
                    "limit": 5,
                    "l": "pt-BR",
                },
                timeout=15,
            )
            if r.status_code != 200:
                continue
            items = (((r.json() or {}).get("results") or {}).get("songs") or {}).get("data") or []
            if items:
                return items[0].get("id")
        except Exception:
            continue

    return None


def create_playlist(developer_token: str, music_user_token: str, nome: str, descricao: str = "") -> str:
    r = requests.post(
        f"{API_BASE}/me/library/playlists",
        headers=_headers(developer_token, music_user_token),
        json={
            "attributes": {
                "name": nome,
                "description": descricao or "Transferida via PlayTransfer",
            }
        },
        timeout=15,
    )
    if r.status_code not in (200, 201):
        raise ValueError(f"Não foi possível criar playlist na Apple Music (HTTP {r.status_code}).")

    playlist_id = ((r.json() or {}).get("data") or [{}])[0].get("id")
    if not playlist_id:
        raise ValueError("Apple Music não retornou o ID da playlist criada.")
    return playlist_id


def add_tracks(developer_token: str, music_user_token: str, playlist_id: str, track_ids: list[str]) -> None:
    if not track_ids:
        return

    headers = _headers(developer_token, music_user_token)
    for i in range(0, len(track_ids), 100):
        chunk = track_ids[i:i + 100]
        r = requests.post(
            f"{API_BASE}/me/library/playlists/{playlist_id}/tracks",
            headers=headers,
            json={"data": [{"id": track_id, "type": "songs"} for track_id in chunk]},
            timeout=15,
        )
        if r.status_code not in (200, 201, 202, 204):
            raise ValueError(f"Erro ao adicionar faixas na Apple Music (HTTP {r.status_code}).")
