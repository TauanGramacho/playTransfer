"""
services/youtube_music.py — PlayTransfer
Leitura e escrita no YouTube Music via ytmusicapi
"""
import json
import os

try:
    from ytmusicapi import YTMusic
    YTM_AVAILABLE = True
except ImportError:
    YTM_AVAILABLE = False


def _check_available():
    if not YTM_AVAILABLE:
        raise ImportError(
            "ytmusicapi não está instalado. Rode: pip install ytmusicapi"
        )


def validate(headers_raw: str) -> dict:
    """
    Valida credenciais do YouTube Music.
    headers_raw: string copiada de uma requisição do browser no YouTube Music.
    """
    _check_available()
    if not headers_raw or len(headers_raw.strip()) < 10:
        raise ValueError("Headers do YouTube Music não fornecidos.")

    # Salva temporariamente os headers
    headers_path = os.path.join(os.path.dirname(__file__), "..", "ytmusic_headers.json")

    try:
        YTMusic.setup(filepath=headers_path, headers_raw=headers_raw)
        ytm = YTMusic(headers_path)
        info = ytm.get_account_info()
        return {
            "display_name": info.get("accountName", "Usuário YouTube Music"),
            "email": info.get("channelHandle", ""),
            "avatar": info.get("accountPhotoUrl", ""),
            "headers_path": headers_path,
        }
    except Exception as e:
        raise ValueError(f"Falha na autenticação do YouTube Music: {e}")


def read_playlist(url: str) -> tuple[str, list[dict]]:
    """
    Lê playlist pública do YouTube Music.
    URL: https://music.youtube.com/playlist?list=PLxxxxxx
         ou https://www.youtube.com/playlist?list=PLxxxxxx
    """
    _check_available()
    import re

    # Extrair playlist ID
    m = re.search(r"(?:list=|playlist/)([A-Za-z0-9_-]+)", url)
    if not m:
        raise ValueError("URL do YouTube Music inválida. Use: https://music.youtube.com/playlist?list=...")

    playlist_id = m.group(1)

    try:
        # Tenta sem auth (playlist pública)
        ytm = YTMusic()
        playlist = ytm.get_playlist(playlist_id, limit=500)
    except Exception as e:
        raise ValueError(f"Não foi possível ler a playlist do YouTube Music: {e}")

    nome = playlist.get("title", "YouTube Music Playlist")
    faixas = []

    for track in playlist.get("tracks", []):
        titulo = track.get("title", "")
        artistas = track.get("artists", [])
        artista = ", ".join(a.get("name", "") for a in artistas) if artistas else ""
        album_data = track.get("album") or {}
        album = album_data.get("name", "") if isinstance(album_data, dict) else ""

        if titulo:
            faixas.append({"titulo": titulo, "artista": artista, "album": album})

    return nome, faixas


def search_track(ytm: "YTMusic", titulo: str, artista: str) -> str | None:
    """Busca uma faixa no YouTube Music. Retorna videoId ou None."""
    try:
        query = f"{artista} {titulo}" if artista else titulo
        results = ytm.search(query, filter="songs", limit=1)
        if results:
            return results[0].get("videoId")
    except Exception:
        pass
    return None


def create_playlist(ytm: "YTMusic", nome: str, descricao: str = "") -> str:
    """Cria uma playlist no YouTube Music. Retorna playlist_id."""
    try:
        pid = ytm.create_playlist(
            title=nome,
            description=descricao or "Transferida via PlayTransfer",
            privacy_status="PRIVATE",
        )
        return pid
    except Exception as e:
        raise ValueError(f"Não foi possível criar playlist no YouTube Music: {e}")


def add_tracks(ytm: "YTMusic", playlist_id: str, video_ids: list[str]) -> None:
    """Adiciona faixas à playlist."""
    try:
        ytm.add_playlist_items(playlist_id, video_ids)
    except Exception as e:
        raise ValueError(f"Erro ao adicionar faixas ao YouTube Music: {e}")


def get_ytm_instance(headers_path: str) -> "YTMusic":
    """Retorna instância autenticada do YTMusic."""
    _check_available()
    if not os.path.exists(headers_path):
        raise ValueError("Arquivo de headers do YouTube Music não encontrado. Reconecte.")
    return YTMusic(headers_path)
