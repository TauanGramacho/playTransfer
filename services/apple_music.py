"""
services/apple_music.py - PlayTransfer
Leitura publica e escrita autenticada no Apple Music API.
"""
import json
import re
import requests

try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
except ImportError:
    browser_cookie3 = None
    BROWSER_COOKIE3_AVAILABLE = False

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
API_BASE = "https://amp-api.music.apple.com/v1"
API_FALLBACK_BASE = "https://amp-api-edge.music.apple.com/v1"


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


def _looks_like_storefront(value: str) -> str:
    text = str(value or "").strip().lower()
    return text if re.fullmatch(r"[a-z]{2}", text) else ""


def _extract_public_playlist_ref(url: str) -> tuple[str, str]:
    match = re.search(
        r"music\.apple\.com/([a-z]{2})/playlist/(?:[^/?#]+/)?(pl\.[A-Za-z0-9._-]+)",
        str(url or ""),
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("URL da Apple Music invalida. Use um link de playlist publica.")
    return match.group(1).lower(), match.group(2)


def _api_path_from_href(href: str) -> str:
    path = str(href or "").strip()
    if not path:
        return ""
    if path.startswith("https://"):
        match = re.search(r"https://[^/]+(/.*)$", path)
        path = match.group(1) if match else path
    if path.startswith("/v1/"):
        path = path[3:]
    if not path.startswith("/"):
        path = f"/{path}"
    return path


def read_saved_apple_session() -> dict:
    """Try to read the Apple Music web session saved in local browsers."""
    if not BROWSER_COOKIE3_AVAILABLE:
        raise ValueError("A leitura automatica do navegador ainda nao esta instalada nesta instalacao.")

    errors = []
    for browser_name, loader in _available_cookie_loaders():
        try:
            jar = loader(domain_name="apple.com")
        except Exception as exc:
            errors.append((browser_name, type(exc).__name__, str(exc)))
            continue

        cookie_pairs = []
        seen = set()
        music_user_token = ""
        storefront = ""
        itfe = ""

        for cookie in jar:
            domain = str(getattr(cookie, "domain", "") or "").lower()
            if "apple.com" not in domain and "itunes.com" not in domain:
                continue

            name = str(getattr(cookie, "name", "") or "").strip()
            value = str(getattr(cookie, "value", "") or "").strip()
            if not name or not value:
                continue

            key = (domain, name)
            if key not in seen:
                seen.add(key)
                cookie_pairs.append(f"{name}={value}")

            lowered_name = name.lower()
            if lowered_name in {"media-user-token", "music-user-token"} and len(value) > 40:
                music_user_token = value
            elif lowered_name in {"itua", "storefront", "storefrontid", "storefrontcountrycode"}:
                storefront = storefront or _looks_like_storefront(value)
            elif lowered_name == "itfe":
                itfe = value

        if cookie_pairs or music_user_token:
            return {
                "music_user_token": music_user_token,
                "cookie_header": "; ".join(cookie_pairs),
                "storefront": storefront,
                "itfe": itfe,
                "browser": browser_name,
            }

    chrome_blocked = any(
        browser_name == "Chrome" and error_type == "RequiresAdminError"
        for browser_name, error_type, _ in errors
    )
    if chrome_blocked:
        raise ValueError("O Chrome desta maquina bloqueou a leitura automatica da Apple Music.")

    raise ValueError(
        "Nao encontrei a sessao da Apple Music salva nos navegadores desta maquina. "
        "Abra o Apple Music Web ja logado e tente novamente."
    )


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


def _auth_variants(
    music_user_token: str | None = None,
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> list[tuple[str, str, str]]:
    token = str(music_user_token or "").strip()
    cookie = str(cookie_header or "").strip()
    itfe_value = str(itfe or "").strip()

    ordered = [
        (token, "", itfe_value),
        (token, "", ""),
        (token, cookie, itfe_value),
        (token, cookie, ""),
        ("", cookie, itfe_value),
        ("", cookie, ""),
    ]

    variants: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in ordered:
        if not candidate[0] and not candidate[1]:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        variants.append(candidate)
    return variants


def _request_with_session(
    method: str,
    path: str,
    developer_token: str,
    music_user_token: str | None = None,
    cookie_header: str | None = None,
    itfe: str | None = None,
    params: dict | None = None,
    success_statuses: tuple[int, ...] = (200,),
    **kwargs,
):
    last_response = None
    for token_value, cookie_value, itfe_value in _auth_variants(music_user_token, cookie_header, itfe):
        response = _request(
            method,
            path,
            headers=_headers(developer_token, token_value, cookie_value),
            params=_params(params, itfe_value),
            **kwargs,
        )
        last_response = response
        if response.status_code in success_statuses:
            return response
        if response.status_code not in (400, 401, 403):
            return response

    return last_response


def _response_json(response) -> dict:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _response_errors(response) -> list[dict]:
    errors = _response_json(response).get("errors") or []
    return errors if isinstance(errors, list) else []


def _response_mentions(response, text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False

    try:
        if lowered in (response.text or "").lower():
            return True
    except Exception:
        pass

    for error in _response_errors(response):
        for key in ("title", "detail", "messageForDisplay", "code"):
            value = str(error.get(key) or "").lower()
            if lowered in value:
                return True
    return False


def _response_storefront(response) -> str:
    try:
        data = _response_json(response).get("data") or []
        first = data[0] if data else {}
        storefront = str(first.get("id") or "").strip().lower()
        return storefront if re.fullmatch(r"[a-z]{2}", storefront) else ""
    except Exception:
        return ""


def _raise_apple_session_error(response, fallback_message: str) -> None:
    status = getattr(response, "status_code", "sem resposta")
    if response is not None and _response_mentions(response, "CloudLibrary"):
        raise ValueError("apple_music_cloud_library_required")
    raise ValueError(f"{fallback_message} (HTTP {status}).")


def fetch_storefront(
    developer_token: str,
    music_user_token: str | None = None,
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> str:
    response = _request_with_session(
        "GET",
        "/me/storefront",
        developer_token,
        music_user_token=music_user_token,
        cookie_header=cookie_header,
        itfe=itfe,
        params={"l": "pt-BR"},
        success_statuses=(200,),
    )
    if not response or response.status_code != 200:
        return ""
    return _response_storefront(response)


def validate(
    developer_token: str,
    music_user_token: str | None = None,
    storefront: str = "us",
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> dict:
    if not developer_token:
        raise ValueError("Developer token da Apple Music nao fornecido.")
    if not music_user_token and not cookie_header:
        raise ValueError("Sessao da Apple Music nao fornecida.")

    resolved_storefront = fetch_storefront(
        developer_token,
        music_user_token=music_user_token,
        cookie_header=cookie_header,
        itfe=itfe,
    ) or storefront.lower()

    r = _request_with_session(
        "GET",
        "/me/library/playlists",
        developer_token,
        music_user_token=music_user_token,
        cookie_header=cookie_header,
        itfe=itfe,
        params={"limit": 1, "l": "pt-BR"},
        success_statuses=(200,),
    )
    if not r or r.status_code != 200:
        _raise_apple_session_error(r, "Apple Music rejeitou a sessao")

    return {
        "display_name": f"Apple Music ({resolved_storefront.upper()})",
        "storefront": resolved_storefront,
    }


def _normalize_catalog_track(track: dict) -> dict | None:
    attrs = track.get("attributes") or {}
    title = str(attrs.get("name") or "").strip()
    if not title:
        return None
    return {
        "titulo": title,
        "artista": str(attrs.get("artistName") or "").strip(),
        "album": str(attrs.get("albumName") or "").strip(),
    }


def _read_playlist_via_catalog_api(
    url: str,
    developer_token: str,
    storefront: str | None = None,
) -> tuple[str, list[dict]]:
    url_storefront, playlist_id = _extract_public_playlist_ref(url)
    resolved_storefront = url_storefront or _looks_like_storefront(storefront or "") or "us"
    headers = _headers(developer_token)

    response = _request(
        "GET",
        f"/catalog/{resolved_storefront}/playlists/{playlist_id}",
        headers=headers,
        params={"include": "tracks", "l": "pt-BR"},
    )
    if response.status_code != 200:
        _raise_apple_session_error(response, "Apple Music nao encontrou essa playlist publica")

    payload = response.json() or {}
    playlist = ((payload.get("data") or [{}])[0]) or {}
    attrs = playlist.get("attributes") or {}
    nome = str(attrs.get("name") or "Apple Music Playlist").strip() or "Apple Music Playlist"
    tracks_rel = (playlist.get("relationships") or {}).get("tracks") or {}
    tracks_data = list(tracks_rel.get("data") or [])

    next_path = _api_path_from_href(tracks_rel.get("next") or "")
    while next_path:
        next_response = _request("GET", next_path, headers=headers)
        if next_response.status_code != 200:
            break
        next_payload = next_response.json() or {}
        tracks_data.extend(next_payload.get("data") or [])
        next_path = _api_path_from_href(next_payload.get("next") or "")

    if not tracks_data:
        tracks_href = _api_path_from_href(tracks_rel.get("href") or f"/catalog/{resolved_storefront}/playlists/{playlist_id}/tracks")
        tracks_response = _request("GET", tracks_href, headers=headers, params={"l": "pt-BR"})
        if tracks_response.status_code == 200:
            tracks_payload = tracks_response.json() or {}
            tracks_data = list(tracks_payload.get("data") or [])

            next_path = _api_path_from_href(tracks_payload.get("next") or "")
            while next_path:
                next_response = _request("GET", next_path, headers=headers)
                if next_response.status_code != 200:
                    break
                next_payload = next_response.json() or {}
                tracks_data.extend(next_payload.get("data") or [])
                next_path = _api_path_from_href(next_payload.get("next") or "")

    faixas = []
    for track in tracks_data:
        normalized = _normalize_catalog_track(track)
        if normalized:
            faixas.append(normalized)

    if not faixas:
        raise ValueError("A playlist publica nao retornou faixas.")

    return nome, faixas


def read_playlist(
    url: str,
    developer_token: str | None = None,
    storefront: str | None = None,
) -> tuple[str, list[dict]]:
    """
    Le a playlist publica da Apple Music pela API publica, com scraping antigo como fallback.
    URL: https://music.apple.com/br/playlist/nome/pl.xxxxxx
    """
    if "music.apple.com" not in url:
        raise ValueError("URL da Apple Music invalida.")

    try:
        if developer_token:
            return _read_playlist_via_catalog_api(url, developer_token, storefront)

        r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        if r.status_code != 200:
            raise ValueError(f"Apple Music retornou HTTP {r.status_code}")

        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL)
        if not match:
            raise ValueError("Nao foi possivel extrair os dados da playlist.")

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
            raise ValueError("A playlist publica nao retornou faixas.")

        return nome, faixas
    except Exception as e:
        raise ValueError(f"Apple Music: nao foi possivel ler a playlist ({e}).")


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
    music_user_token: str | None,
    nome: str,
    descricao: str = "",
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> str:
    r = _request_with_session(
        "POST",
        "/me/library/playlists",
        developer_token,
        music_user_token=music_user_token,
        cookie_header=cookie_header,
        itfe=itfe,
        params={},
        success_statuses=(200, 201),
        json={
            "attributes": {
                "name": nome,
                "description": descricao or "Transferida via PlayTransfer",
            }
        },
    )
    if not r or r.status_code not in (200, 201):
        _raise_apple_session_error(r, "Nao foi possivel criar playlist na Apple Music")

    playlist_id = ((r.json() or {}).get("data") or [{}])[0].get("id")
    if not playlist_id:
        raise ValueError("Apple Music nao retornou o ID da playlist criada.")
    return playlist_id


def add_tracks(
    developer_token: str,
    music_user_token: str | None,
    playlist_id: str,
    track_ids: list[str],
    cookie_header: str | None = None,
    itfe: str | None = None,
) -> None:
    if not track_ids:
        return

    for i in range(0, len(track_ids), 100):
        chunk = track_ids[i:i + 100]
        r = _request_with_session(
            "POST",
            f"/me/library/playlists/{playlist_id}/tracks",
            developer_token,
            music_user_token=music_user_token,
            cookie_header=cookie_header,
            itfe=itfe,
            params={},
            success_statuses=(200, 201, 202, 204),
            json={"data": [{"id": track_id, "type": "songs"} for track_id in chunk]},
        )
        if not r or r.status_code not in (200, 201, 202, 204):
            _raise_apple_session_error(r, "Erro ao adicionar faixas na Apple Music")
