"""
services/deezer.py — PlayTransfer
Leitura e escrita no Deezer via OAuth token ou ARL
"""
import requests

try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
except ImportError:
    browser_cookie3 = None
    BROWSER_COOKIE3_AVAILABLE = False

DEEZER_GW = "https://www.deezer.com/ajax/gw-light.php"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _make_session(arl: str = None) -> requests.Session:
    s = requests.Session()
    if arl:
        s.cookies.set("arl", arl, domain=".deezer.com")
    s.headers.update({"User-Agent": UA, "Content-Type": "application/json"})
    return s


def _gw_call(session: requests.Session, method: str, api_token: str, body: dict) -> dict:
    r = session.post(
        DEEZER_GW,
        params={"method": method, "input": "3", "api_version": "1.0", "api_token": api_token},
        json=body, timeout=15,
    )
    return r.json()


def session_from_oauth_token(access_token: str) -> dict:
    """
    Cria uma sessão Deezer usando o access_token OAuth (para criar playlists).
    O Deezer ainda precisa de cookies de sessão para o GW — usamos o token para obter eles.
    """
    # Usa o access_token diretamente na API pública (leitura funciona assim)
    # Para escrita via GW, precisamos fazer login via token na web
    s = requests.Session()
    s.headers.update({"User-Agent": UA})

    # Tenta obter cookies de sessão visitando a API com o token
    r = s.get(
        "https://www.deezer.com/ajax/action.php",
        params={"method": "deezer.getUserData"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )

    # Abordagem alternativa: faz login no GW via token de sessão
    r2 = s.post(
        DEEZER_GW,
        params={"method": "deezer.getUserData", "input": "3",
                "api_version": "1.0", "api_token": "null"},
        json={}, timeout=15,
    )

    try:
        data = r2.json()
        uid = data.get("results", {}).get("USER", {}).get("USER_ID", 0)
        api_token = data.get("results", {}).get("checkForm", "")
        if uid:
            return {"session": s, "api_token": api_token}
    except Exception:
        pass

    return {"session": s, "api_token": ""}


def validate(arl: str) -> dict:
    """Valida ARL do Deezer. Retorna info da sessão."""
    if not arl:
        raise ValueError("ARL do Deezer não fornecido.")
    s = _make_session(arl)
    r = s.post(DEEZER_GW,
               params={"method": "deezer.getUserData", "input": "3",
                       "api_version": "1.0", "api_token": "null"},
               json={}, timeout=15).json()

    user = r.get("results", {}).get("USER", {})
    uid = user.get("USER_ID", 0)
    api_token = r.get("results", {}).get("checkForm", "")

    if not uid or uid == 0:
        raise ValueError("Sessão inválida ou expirada.")

    return {
        "session": s,
        "api_token": api_token,
        "display_name": user.get("BLOG_NAME", "Usuário Deezer"),
        "email": user.get("EMAIL", ""),
    }


def read_playlist(url: str) -> tuple[str, list[dict]]:
    """Lê playlist pública do Deezer via API pública."""
    import re
    m = re.search(r"deezer\.com(?:/\w+)?/playlist/(\d+)", url)
    if not m:
        m = re.search(r"deezer\.com(?:/\w+)?/album/(\d+)", url)
        if m:
            return _read_album_public(m.group(1))
        raise ValueError("URL do Deezer inválida. Use: https://www.deezer.com/playlist/...")

    pid = m.group(1)
    r = requests.get(f"https://api.deezer.com/playlist/{pid}", timeout=10).json()

    if r.get("error"):
        raise ValueError(f"Playlist não encontrada ou privada.")

    nome = r.get("title", "Deezer Playlist")
    faixas = []
    tracks = r.get("tracks", {}).get("data", [])
    next_url = r.get("tracks", {}).get("next")

    while True:
        for t in tracks:
            faixas.append({
                "titulo": t.get("title", ""),
                "artista": t.get("artist", {}).get("name", ""),
                "album": t.get("album", {}).get("title", ""),
            })
        if not next_url:
            break
        r2 = requests.get(next_url, timeout=10).json()
        tracks = r2.get("data", [])
        next_url = r2.get("next")

    return nome, faixas


def _read_album_public(album_id: str) -> tuple[str, list[dict]]:
    r = requests.get(f"https://api.deezer.com/album/{album_id}", timeout=10).json()
    if r.get("error"):
        raise ValueError("Álbum não encontrado.")
    nome = r.get("title", "Deezer Album")
    artist = r.get("artist", {}).get("name", "")
    faixas = [
        {"titulo": t.get("title", ""), "artista": t.get("artist", {}).get("name", artist), "album": nome}
        for t in r.get("tracks", {}).get("data", [])
    ]
    return nome, faixas


def search_track(session: requests.Session, titulo: str, artista: str) -> int | None:
    try:
        r = session.get("https://api.deezer.com/search",
                        params={"q": f"{artista} {titulo}", "limit": 1}, timeout=10).json()
        data = r.get("data", [])
        if data:
            return data[0]["id"]
    except Exception:
        pass
    return None


def create_playlist(session: requests.Session, api_token: str, nome: str, descricao: str = "") -> int:
    r = _gw_call(session, "playlist.create", api_token, {
        "title": nome,
        "description": descricao or "Transferida via PlayTransfer",
        "songs": [], "status": 0,
    })
    pid = r.get("results")
    if not pid:
        raise ValueError("Não foi possível criar a playlist no Deezer.")
    return int(pid)


def add_tracks(session: requests.Session, api_token: str, playlist_id: int, track_ids: list[int]) -> None:
    for i in range(0, len(track_ids), 100):
        chunk = track_ids[i:i + 100]
        _gw_call(session, "playlist.addSongs", api_token, {
            "playlist_id": playlist_id,
            "songs": [[tid, idx] for idx, tid in enumerate(chunk, i)],
        })


def _available_cookie_loaders() -> list[tuple[str, object]]:
    if not BROWSER_COOKIE3_AVAILABLE:
        return []

    browser_names = [
        ("Chrome", "chrome"),
        ("Edge", "edge"),
        ("Brave", "brave"),
        ("Firefox", "firefox"),
        ("Opera", "opera"),
        ("Vivaldi", "vivaldi"),
    ]
    loaders = []
    for label, attr in browser_names:
        loader = getattr(browser_cookie3, attr, None)
        if callable(loader):
            loaders.append((label, loader))
    return loaders


def read_saved_arl() -> dict:
    """
    Tenta ler o cookie ARL salvo em navegadores instalados no computador.
    Recurso local, pensado para a instÃ¢ncia desktop do app.
    """
    if not BROWSER_COOKIE3_AVAILABLE:
        raise ValueError(
            "A leitura automatica do navegador ainda nao esta instalada nesta instalacao."
        )

    errors = []

    for browser_name, loader in _available_cookie_loaders():
        try:
            jar = loader(domain_name="deezer.com")
        except Exception as exc:
            errors.append((browser_name, type(exc).__name__, str(exc)))
            continue

        for cookie in jar:
            if cookie.name.lower() == "arl" and cookie.value:
                return {"arl": cookie.value.strip(), "browser": browser_name}

    chrome_blocked = any(
        browser_name == "Chrome" and error_type == "RequiresAdminError"
        for browser_name, error_type, _ in errors
    )
    if chrome_blocked:
        raise ValueError(
            "O Chrome desta maquina bloqueou a leitura automatica do Deezer."
        )

    raise ValueError(
        "Nao encontrei o cookie arl do Deezer nos navegadores desta maquina. "
        "Abra o Deezer ja logado em Chrome, Edge ou Firefox e tente novamente."
    )
