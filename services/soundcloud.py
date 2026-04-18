"""
services/soundcloud.py — PlayTransfer
Leitura de playlists públicas do SoundCloud via Web API
"""
import re
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Client ID público do SoundCloud (obtido via scraping da página)
_client_id_cache = {"id": None}

KNOWN_CLIENT_IDS = [
    "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX",
    "a3e059563d7fd3372b49b37f00a00bcf",
    "2t9loNQH90kzJcsFCODdigxfp325aq4z",
]


def _get_client_id() -> str:
    """Obtém client_id do SoundCloud via scraping."""
    if _client_id_cache["id"]:
        return _client_id_cache["id"]

    # Tenta client IDs conhecidos
    for cid in KNOWN_CLIENT_IDS:
        try:
            r = requests.get(
                "https://api-v2.soundcloud.com/tracks",
                params={"client_id": cid, "limit": 1},
                headers={"User-Agent": UA},
                timeout=5,
            )
            if r.status_code == 200:
                _client_id_cache["id"] = cid
                return cid
        except Exception:
            continue

    # Tenta extrair da página principal
    try:
        r = requests.get("https://soundcloud.com", headers={"User-Agent": UA}, timeout=10)
        scripts = re.findall(r'<script[^>]+src="([^"]+\.js)"', r.text)
        for script_url in reversed(scripts[-5:]):
            try:
                js = requests.get(script_url, headers={"User-Agent": UA}, timeout=5).text
                m = re.search(r'client_id:"([a-zA-Z0-9]{32,})"', js)
                if m:
                    _client_id_cache["id"] = m.group(1)
                    return _client_id_cache["id"]
            except Exception:
                continue
    except Exception:
        pass

    raise ValueError("Não foi possível obter client_id do SoundCloud. Tente novamente mais tarde.")


def validate() -> dict:
    """SoundCloud não requer autenticação para playlists públicas."""
    try:
        _get_client_id()
        return {"display_name": "SoundCloud (público)", "email": "", "avatar": ""}
    except Exception as e:
        raise ValueError(str(e))


def read_playlist(url: str) -> tuple[str, list[dict]]:
    """
    Lê playlist pública do SoundCloud.
    URL: https://soundcloud.com/usuario/sets/nome-da-playlist
    """
    if "soundcloud.com" not in url:
        raise ValueError("URL do SoundCloud inválida.")

    client_id = _get_client_id()

    # Resolve URL para obter dados da playlist
    try:
        r = requests.get(
            "https://api-v2.soundcloud.com/resolve",
            params={"url": url, "client_id": client_id},
            headers={"User-Agent": UA},
            timeout=10,
        )
    except Exception as e:
        raise ValueError(f"Erro ao conectar ao SoundCloud: {e}")

    if r.status_code == 404:
        raise ValueError("Playlist do SoundCloud não encontrada ou privada.")
    if r.status_code != 200:
        raise ValueError(f"Erro do SoundCloud (HTTP {r.status_code}).")

    data = r.json()
    kind = data.get("kind", "")

    if kind not in ("playlist", "system-playlist"):
        raise ValueError("URL não é uma playlist do SoundCloud. Use um link de 'Sets'.")

    nome = data.get("title", "SoundCloud Playlist")
    faixas = []

    tracks = data.get("tracks", [])

    # Algumas faixas podem estar incompletas (apenas IDs) — busca os detalhes
    incomplete_ids = [str(t["id"]) for t in tracks if not t.get("title")]
    if incomplete_ids:
        # Busca em lotes de 50
        for i in range(0, len(incomplete_ids), 50):
            batch = incomplete_ids[i:i+50]
            try:
                r2 = requests.get(
                    "https://api-v2.soundcloud.com/tracks",
                    params={"ids": ",".join(batch), "client_id": client_id},
                    headers={"User-Agent": UA},
                    timeout=10,
                )
                if r2.status_code == 200:
                    detailed = {str(t["id"]): t for t in r2.json()}
                    for t in tracks:
                        if str(t["id"]) in detailed:
                            t.update(detailed[str(t["id"])])
            except Exception:
                pass

    for t in tracks:
        titulo = t.get("title", "")
        # SoundCloud mistura artista no título formato "ARTISTA - TITULO"
        artista = t.get("user", {}).get("username", "")
        if " - " in titulo:
            parts = titulo.split(" - ", 1)
            artista = parts[0].strip() or artista
            titulo = parts[1].strip()
        if titulo:
            faixas.append({"titulo": titulo, "artista": artista, "album": ""})

    return nome, faixas
