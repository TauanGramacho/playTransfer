"""
services/spotify.py — PlayTransfer
Leitura de playlists do Spotify via embed público e cookie sp_dc
"""
import os, re, json, time, requests

_token_cache: dict = {"token": None, "expires": 0}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _get_sp_dc() -> str:
    sp_dc = os.getenv("SPOTIFY_SP_DC", "").strip()
    if not sp_dc:
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.strip().startswith("SPOTIFY_SP_DC="):
                        sp_dc = line.strip().split("=", 1)[1].strip()
        except Exception:
            pass
    return sp_dc


def get_token_via_sp_dc(sp_dc: str) -> str:
    """Obtém access token do Spotify via cookie sp_dc (sem Playwright)."""
    if _token_cache["token"] and _token_cache["expires"] > time.time() + 60:
        return _token_cache["token"]

    r = requests.get(
        "https://open.spotify.com/api/token",
        headers={
            "User-Agent": UA,
            "Cookie": f"sp_dc={sp_dc}",
            "Accept": "application/json",
        },
        timeout=10,
    )
    if r.status_code != 200:
        raise ValueError(f"sp_dc inválido ou expirado (HTTP {r.status_code})")

    data = r.json()
    token = data.get("accessToken")
    expires = data.get("accessTokenExpirationTimestampMs", 0) / 1000

    if not token:
        raise ValueError("Não foi possível obter token do Spotify. Verifique o sp_dc.")

    _token_cache["token"] = token
    _token_cache["expires"] = expires if expires > time.time() else time.time() + 3600
    return token


def validate(sp_dc: str) -> dict:
    """Valida credenciais do Spotify. Retorna info do usuário."""
    if not sp_dc:
        raise ValueError("Cookie sp_dc não fornecido.")
    token = get_token_via_sp_dc(sp_dc)

    r = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {token}", "User-Agent": UA},
        timeout=10,
    )
    if r.status_code == 200:
        data = r.json()
        return {
            "display_name": data.get("display_name", "Usuário Spotify"),
            "email": data.get("email", ""),
            "avatar": (data.get("images") or [{}])[0].get("url", ""),
        }
    # Token válido mas sem permissão para /me — ainda funciona para leitura pública
    return {"display_name": "Usuário Spotify", "email": "", "avatar": ""}


def _extract_id_and_type(url: str) -> tuple[str, str]:
    """Extrai (tipo, id) de uma URL do Spotify."""
    for tipo in ["playlist", "album", "track"]:
        m = re.search(rf"{tipo}/([A-Za-z0-9]+)", url)
        if m:
            return tipo, m.group(1)
    return None, None


def _read_via_token(tipo: str, pid: str, access_token: str) -> tuple[str, list[dict]]:
    """Lê playlist/álbum usando access_token OAuth direto."""
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": UA}
    endpoint = "playlists" if tipo == "playlist" else "albums"

    r = requests.get(f"https://api.spotify.com/v1/{endpoint}/{pid}", headers=headers, timeout=10)
    if r.status_code == 401:
        raise ValueError("Sessão do Spotify expirada. Conecte novamente.")
    if r.status_code == 404:
        raise ValueError("Playlist não encontrada. Verifique se é pública ou se você tem acesso.")
    if r.status_code != 200:
        raise ValueError(f"Erro do Spotify (HTTP {r.status_code})")

    info = r.json()
    nome_playlist = info.get("name", "Spotify Playlist")
    faixas = []
    offset = 0

    while True:
        r2 = requests.get(f"https://api.spotify.com/v1/{endpoint}/{pid}/tracks",
                          headers=headers,
                          params={"limit": 100, "offset": offset,
                                  "fields": "items(track(name,artists(name),album(name))),next"},
                          timeout=15)
        if r2.status_code != 200:
            break
        data = r2.json()
        items = data.get("items", [])
        for item in items:
            t = item.get("track") or item
            if not t or not t.get("name"):
                continue
            faixas.append({
                "titulo":  t["name"],
                "artista": ", ".join(a["name"] for a in t.get("artists", [])),
                "album":   t.get("album", {}).get("name", "") if isinstance(t.get("album"), dict) else "",
            })
        offset += len(items)
        if not data.get("next"):
            break

    return nome_playlist, faixas


def read_playlist(url: str, sp_dc: str = None, access_token: str = None) -> tuple[str, list[dict]]:
    """
    Lê músicas de uma playlist/álbum do Spotify.
    Aceita access_token (OAuth) ou sp_dc (cookie).
    """
    tipo, pid = _extract_id_and_type(url)
    if not pid:
        raise ValueError("URL do Spotify inválida. Use: https://open.spotify.com/playlist/...")

    # ── Se temos access_token OAuth, usa diretamente ───────────────────────
    if access_token:
        return _read_via_token(tipo, pid, access_token)

    faixas = []
    nome_playlist = "Spotify Playlist"

    # ── Tentativa 1: Embed público (sem auth) ──────────────────────────────
    try:
        embed_url = f"https://open.spotify.com/embed/{tipo}/{pid}"
        r = requests.get(embed_url, headers={"User-Agent": UA}, timeout=10)
        if r.status_code == 200:
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
            if m:
                data = json.loads(m.group(1))
                entity = (data.get("props", {})
                              .get("pageProps", {})
                              .get("state", {})
                              .get("data", {})
                              .get("entity", {}))
                tracks_data = entity.get("trackList", [])
                nome_playlist = entity.get("name", "Spotify Playlist")
                for t in tracks_data:
                    artista = t.get("subtitle", "")
                    titulo = t.get("title", "")
                    if titulo:
                        faixas.append({"titulo": titulo, "artista": artista, "album": ""})

                # Para álbuns ou playlists curtas, o embed é suficiente
                if faixas and (tipo == "album" or len(faixas) < 50):
                    return nome_playlist, faixas
    except Exception as e:
        print(f"[Spotify] Embed falhou: {e}")

    # ── Tentativa 2: API Oficial com sp_dc ────────────────────────────────
    _sp_dc = sp_dc or _get_sp_dc()
    if not _sp_dc:
        if faixas:
            return nome_playlist, faixas
        raise ValueError(
            "Playlist pode ter mais de 50 músicas. Forneça o cookie sp_dc para ler a playlist completa."
        )

    token = get_token_via_sp_dc(_sp_dc)
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA}

    endpoint = "playlists" if tipo == "playlist" else "albums"
    r = requests.get(f"https://api.spotify.com/v1/{endpoint}/{pid}", headers=headers, timeout=10)

    if r.status_code == 401:
        _token_cache["token"] = None
        raise ValueError("Token do Spotify expirou. Reconecte o Spotify.")
    if r.status_code == 404:
        raise ValueError("Playlist não encontrada. Verifique se é pública.")
    if r.status_code != 200:
        raise ValueError(f"Erro do Spotify (HTTP {r.status_code})")

    info = r.json()
    nome_playlist = info.get("name", "Spotify Playlist")
    faixas = []
    offset = 0

    tracks_key = "tracks" if tipo == "playlist" else "tracks"
    while True:
        track_url = f"https://api.spotify.com/v1/{endpoint}/{pid}/tracks"
        params = {"limit": 100, "offset": offset,
                  "fields": "items(track(name,artists(name),album(name))),next"}
        r2 = requests.get(track_url, headers=headers, params=params, timeout=15)
        if r2.status_code != 200:
            break
        data = r2.json()
        items = data.get("items", [])
        for item in items:
            t = item.get("track") or item
            if not t or not t.get("name"):
                continue
            faixas.append({
                "titulo": t["name"],
                "artista": ", ".join(a["name"] for a in t.get("artists", [])),
                "album": t.get("album", {}).get("name", "") if isinstance(t.get("album"), dict) else "",
            })
        offset += len(items)
        if not data.get("next"):
            break

    return nome_playlist, faixas
