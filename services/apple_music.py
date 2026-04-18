"""
services/apple_music.py — PlayTransfer
Apple Music — leitura pública limitada via MusicKit API
"""
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def validate(*args, **kwargs):
    # Apple Music em breve com token de desenvolvedor
    raise NotImplementedError(
        "Apple Music: integração completa chegando em breve. "
        "Requer Apple Developer Program ($99/ano)."
    )


def read_playlist(url: str) -> tuple[str, list[dict]]:
    """
    Tenta ler playlist pública da Apple Music via scraping do embed.
    URL: https://music.apple.com/br/playlist/nome/plxxxxxx
    """
    if "music.apple.com" not in url:
        raise ValueError("URL da Apple Music inválida.")

    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        if r.status_code != 200:
            raise ValueError(f"Apple Music retornou HTTP {r.status_code}")

        # Extrai schema.org JSON-LD
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL)
        if not m:
            raise ValueError("Não foi possível extrair dados da Apple Music.")

        import json
        data = json.loads(m.group(1))
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

        return nome, faixas

    except Exception as e:
        raise ValueError(
            f"Apple Music: não foi possível ler a playlist ({e}). "
            "A integração completa está chegando em breve!"
        )


# Status da integração
STATUS = "coming_soon"
INFO = {
    "name": "Apple Music",
    "status": "coming_soon",
    "message": "Integração completa com Apple Music chegando em breve!",
    "icon": "apple",
}
