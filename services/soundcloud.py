"""
services/soundcloud.py - PlayTransfer
Leitura publica e escrita autenticada no SoundCloud.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any

import requests

try:
    import browser_cookie3
    BROWSER_COOKIE3_AVAILABLE = True
except ImportError:
    browser_cookie3 = None
    BROWSER_COOKIE3_AVAILABLE = False

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
API_V1 = "https://api.soundcloud.com"
API_V2 = "https://api-v2.soundcloud.com"

_client_id_cache = {"id": None}
_app_version_cache = {"value": None}

KNOWN_CLIENT_IDS = [
    "dNJB1Fh1ZimKOFVKIg973yrMZzkm4x6w",
    "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX",
    "a3e059563d7fd3372b49b37f00a00bcf",
    "2t9loNQH90kzJcsFCODdigxfp325aq4z",
]

TOKEN_RE = re.compile(r"(?:OAuth|Bearer)\s+([A-Za-z0-9._~+/=-]{20,})", re.I)
NAMED_TOKEN_RE = re.compile(
    r"(?:oauth_token|access_token|oauthToken|accessToken)[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9._~+/=%-]{20,})",
    re.I,
)


def _available_cookie_loaders() -> list[tuple[str, object]]:
    if not BROWSER_COOKIE3_AVAILABLE:
        return []

    browser_names = [
        ("Edge", "edge"),
        ("Chrome", "chrome"),
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


def _token_from_text(value: str) -> str:
    text = str(value or "")
    match = TOKEN_RE.search(text) or NAMED_TOKEN_RE.search(text)
    if not match:
        return ""
    token = requests.utils.unquote(match.group(1).strip().strip("\"'"))
    if len(token) < 20 or any(char.isspace() for char in token):
        return ""
    return token


def _token_from_cookie(name: str, value: str) -> str:
    lowered = str(name or "").strip().lower()
    raw_value = str(value or "").strip()
    if lowered in {
        "oauth_token",
        "soundcloud_oauth_token",
        "soundcloud_access_token",
        "access_token",
        "sc_oauth_token",
    }:
        return _token_from_text(f"oauth_token={raw_value}") or raw_value
    if "oauth" in lowered or "access" in lowered or "token" in lowered:
        return _token_from_text(f"{name}={raw_value}")
    return _token_from_text(raw_value)


def _public_headers() -> dict[str, str]:
    return {"User-Agent": UA, "Accept": "application/json"}


def _auth_headers(access_token: str) -> dict[str, str]:
    if not access_token:
        raise ValueError("Access token do SoundCloud nao fornecido.")
    token = str(access_token).strip()
    if token.lower().startswith(("oauth ", "bearer ")):
        authorization = token
    else:
        authorization = f"OAuth {token}"
    return {
        "User-Agent": UA,
        "Accept": "application/json; charset=utf-8",
        "Content-Type": "application/json",
        "Authorization": authorization,
    }


def _auth_header_variants(access_token: str) -> list[dict[str, str]]:
    token = str(access_token or "").strip()
    if not token:
        raise ValueError("Access token do SoundCloud nao fornecido.")
    if token.lower().startswith(("oauth ", "bearer ")):
        raw_token = token.split(" ", 1)[1].strip()
    else:
        raw_token = token

    variants = [_auth_headers(token)]
    for scheme in ("Bearer", "OAuth"):
        authorization = f"{scheme} {raw_token}"
        if any(item.get("Authorization") == authorization for item in variants):
            continue
        variants.append({
            "User-Agent": UA,
            "Accept": "application/json; charset=utf-8",
            "Content-Type": "application/json",
            "Authorization": authorization,
            "Origin": "https://soundcloud.com",
            "Referer": "https://soundcloud.com/",
        })
    return variants


def _response_detail(response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    text = str(payload or "").strip()
    return text[:260]


def _cookie_from_header(cookie_header: str, name: str) -> str:
    wanted = str(name or "").strip().lower()
    for part in str(cookie_header or "").split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key.strip().lower() == wanted:
            return value.strip()
    return ""


def _cookie_value(cookie_header: str, names: set[str]) -> str:
    wanted = {name.lower() for name in names}
    for part in str(cookie_header or "").split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name.strip().lower() in wanted:
            return value.strip()
    return ""


def _web_session_headers(cookie_header: str) -> dict[str, str]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json",
        "Origin": "https://soundcloud.com",
        "Referer": "https://soundcloud.com/",
        "Cookie": cookie_header,
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }
    csrf = _cookie_value(cookie_header, {"csrf_token", "sc_csrf_token", "_csrf", "csrf"})
    if csrf:
        headers["X-CSRF-Token"] = csrf
    datadome = _cookie_value(cookie_header, {"datadome"})
    if datadome:
        headers["X-Datadome-Clientid"] = datadome

    token = ""
    for part in str(cookie_header or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            t = _token_from_cookie(k.strip(), v.strip())
            if t:
                token = t
                break
    if token:
        if token.lower().startswith(("oauth ", "bearer ")):
            headers["Authorization"] = token
        else:
            headers["Authorization"] = f"OAuth {token}"

    return headers


def _get_app_version() -> str:
    configured = os.getenv("SOUNDCLOUD_APP_VERSION", "").strip()
    if configured:
        return configured
    if _app_version_cache["value"]:
        return _app_version_cache["value"]
    try:
        home = requests.get("https://soundcloud.com", headers=_public_headers(), timeout=10)
        match = re.search(r"__sc_version\s*=\s*[\"']([^\"']+)", home.text)
        if match:
            _app_version_cache["value"] = match.group(1)
            return _app_version_cache["value"]
    except Exception:
        pass
    return ""


def _web_params(client_id: str, app_version_override: str = "") -> dict[str, str]:
    params = {"client_id": client_id}
    app_version = str(app_version_override or "").strip() or _get_app_version()
    if app_version:
        params["app_version"] = app_version
    return params


def _get_client_id() -> str:
    client_id = os.getenv("SOUNDCLOUD_CLIENT_ID", "").strip()
    if client_id:
        return client_id

    if _client_id_cache["id"]:
        return _client_id_cache["id"]

    try:
        home = requests.get("https://soundcloud.com", headers=_public_headers(), timeout=10)
        hydration_patterns = [
            r'"hydratable"\s*:\s*"apiClient".{0,260}?"id"\s*:\s*"([a-zA-Z0-9]{20,80})"',
            r'"apiClient".{0,260}?"id"\s*:\s*"([a-zA-Z0-9]{20,80})"',
            r"client_id[\"']?\s*[:=]\s*[\"']([a-zA-Z0-9]{20,80})[\"']",
        ]
        for pattern in hydration_patterns:
            match = re.search(pattern, home.text, re.S)
            if match:
                _client_id_cache["id"] = match.group(1)
                return _client_id_cache["id"]

        scripts = re.findall(r'<script[^>]+src="([^"]+\\.js)"', home.text)
        for script_url in reversed(scripts[-6:]):
            try:
                script = requests.get(script_url, headers=_public_headers(), timeout=5).text
            except Exception:
                continue
            match = (
                re.search(r'client_id:"([a-zA-Z0-9]{20,80})"', script)
                or re.search(r"client_id:'([a-zA-Z0-9]{20,80})'", script)
            )
            if match:
                _client_id_cache["id"] = match.group(1)
                return _client_id_cache["id"]
    except Exception:
        pass

    for known in KNOWN_CLIENT_IDS:
        try:
            response = requests.get(
                f"{API_V2}/resolve",
                params={"url": "https://soundcloud.com/discover", "client_id": known},
                headers=_public_headers(),
                timeout=5,
            )
            if response.status_code in (200, 302, 404):
                _client_id_cache["id"] = known
                return known
        except Exception:
            continue

    raise ValueError("Nao foi possivel obter client_id publico do SoundCloud.")


def _normalize_track(track: dict[str, Any]) -> dict[str, str] | None:
    title = (track.get("title") or "").strip()
    if not title:
        return None

    artist = ""
    user = track.get("user") or {}
    if isinstance(user, dict):
        artist = (user.get("username") or user.get("full_name") or "").strip()

    publisher = track.get("publisher_metadata") or {}
    publisher_artist = (publisher.get("artist") or "").strip() if isinstance(publisher, dict) else ""
    if publisher_artist:
        artist = publisher_artist

    if " - " in title and not publisher_artist:
        possible_artist, possible_title = title.split(" - ", 1)
        if possible_artist and possible_title:
            artist = possible_artist.strip() or artist
            title = possible_title.strip()

    return {"titulo": title, "artista": artist, "album": ""}


def _clean(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _score_track(track: dict[str, Any], titulo: str, artista: str, album: str = "") -> int:
    normalized = _normalize_track(track) or {"titulo": "", "artista": "", "album": ""}
    wanted_title = _clean(titulo)
    wanted_artist = _clean(artista)
    wanted_album = _clean(album)
    found_title = _clean(normalized.get("titulo", ""))
    found_artist = _clean(normalized.get("artista", ""))
    found_album = _clean(normalized.get("album", ""))

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


def _resolve_public_playlist(url: str) -> dict[str, Any]:
    client_id = _get_client_id()
    response = requests.get(
        f"{API_V2}/resolve",
        params={"url": url, "client_id": client_id},
        headers=_public_headers(),
        timeout=15,
    )
    if response.status_code == 404:
        raise ValueError("Playlist do SoundCloud nao encontrada ou privada.")
    if response.status_code != 200:
        raise ValueError(f"SoundCloud retornou HTTP {response.status_code}.")
    return response.json()


def _resolve_auth_playlist(url: str, access_token: str) -> dict[str, Any]:
    response = requests.get(
        f"{API_V1}/resolve",
        params={"url": url},
        headers=_auth_headers(access_token),
        timeout=15,
    )
    if response.status_code == 404:
        raise ValueError("Playlist do SoundCloud nao encontrada.")
    if response.status_code != 200:
        raise ValueError(f"SoundCloud retornou HTTP {response.status_code}.")
    return response.json()


def validate(access_token: str | None = None) -> dict[str, str]:
    token = (access_token or "").strip()
    if token:
        headers = _auth_headers(token)
        response = requests.get(f"{API_V1}/me", headers=headers, timeout=15)
        if response.status_code != 200 and not token.lower().startswith(("oauth ", "bearer ")):
            bearer_headers = {**headers, "Authorization": f"Bearer {token}"}
            bearer_response = requests.get(f"{API_V1}/me", headers=bearer_headers, timeout=15)
            if bearer_response.status_code == 200:
                response = bearer_response
        if response.status_code != 200:
            client_id = _get_client_id()
            for scheme in ("OAuth", "Bearer"):
                token_value = token
                if token.lower().startswith(("oauth ", "bearer ")):
                    scheme, token_value = token.split(" ", 1)
                v2_headers = {
                    **headers,
                    "Authorization": f"{scheme} {token_value}",
                    "Origin": "https://soundcloud.com",
                    "Referer": "https://soundcloud.com/",
                }
                v2_response = requests.get(
                    f"{API_V2}/me",
                    params=_web_params(client_id),
                    headers=v2_headers,
                    timeout=15,
                )
                if v2_response.status_code == 200:
                    response = v2_response
                    break
        if response.status_code != 200:
            raise ValueError("Access token do SoundCloud invalido ou expirado.")
        data = response.json()
        return {
            "display_name": data.get("username") or data.get("full_name") or "SoundCloud",
            "avatar": data.get("avatar_url", ""),
        }

    _get_client_id()
    return {"display_name": "SoundCloud (publico)", "avatar": ""}


def validate_web_session(cookie_header: str, client_id: str | None = None, app_version: str = "") -> dict[str, str]:
    cookies = str(cookie_header or "").strip()
    sc_client_id = (client_id or _get_client_id()).strip()
    if not cookies or not sc_client_id:
        raise ValueError("Sessao web do SoundCloud incompleta.")

    response = requests.get(
        f"{API_V2}/me",
        params=_web_params(sc_client_id, app_version),
        headers=_web_session_headers(cookies),
        timeout=15,
    )
    if response.status_code != 200:
        raise ValueError("Sessao web do SoundCloud ainda nao liberou acesso.")
    data = response.json()
    return {
        "display_name": data.get("username") or data.get("full_name") or "SoundCloud",
        "avatar": data.get("avatar_url", ""),
        "user_id": str(data.get("id") or ""),
    }


def _token_from_web_session(cookie_header: str) -> str:
    if not cookie_header:
        return ""
    headers = {
        **_public_headers(),
        "Cookie": cookie_header,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for url in ("https://soundcloud.com/you/library", "https://soundcloud.com/discover"):
        try:
            response = requests.get(url, headers=headers, timeout=12)
        except Exception:
            continue
        for name, value in response.headers.items():
            if str(name).lower() == "set-cookie":
                token = _token_from_text(value)
                if token:
                    return token
        token = _token_from_text(response.text)
        if token:
            return token
    return ""


def read_saved_soundcloud_session() -> dict[str, str]:
    """Try to read a SoundCloud web login saved in local browsers."""
    if not BROWSER_COOKIE3_AVAILABLE:
        raise ValueError("A leitura automatica do navegador ainda nao esta instalada nesta instalacao.")

    errors = []

    for browser_name, loader in _available_cookie_loaders():
        try:
            jar = loader(domain_name="soundcloud.com")
        except Exception as exc:
            errors.append((browser_name, type(exc).__name__, str(exc)))
            continue

        cookie_pairs = []
        seen = set()
        access_token = ""

        for cookie in jar:
            domain = str(getattr(cookie, "domain", "") or "").lower()
            if "soundcloud.com" not in domain:
                continue

            name = str(getattr(cookie, "name", "") or "").strip()
            value = str(getattr(cookie, "value", "") or "").strip()
            if not name or not value:
                continue

            key = (domain, name)
            if key not in seen:
                seen.add(key)
                cookie_pairs.append(f"{name}={value}")

            if not access_token:
                access_token = _token_from_cookie(name, value)

        cookie_header = "; ".join(cookie_pairs)
        if not access_token and cookie_header:
            access_token = _token_from_web_session(cookie_header)

        if access_token:
            return {
                "access_token": access_token,
                "cookie_header": cookie_header,
                "browser": browser_name,
            }

    edge_blocked = any(
        browser_name == "Edge" and error_type == "RequiresAdminError"
        for browser_name, error_type, _ in errors
    )
    if edge_blocked:
        raise ValueError("O Edge desta maquina bloqueou a leitura automatica do SoundCloud.")

    raise ValueError(
        "Nao encontrei o login do SoundCloud salvo nos navegadores desta maquina. "
        "Abra o SoundCloud no Edge, entre com Google e tente novamente."
    )


def read_playlist(url: str, access_token: str | None = None) -> tuple[str, list[dict[str, str]]]:
    if "soundcloud.com" not in url:
        raise ValueError("URL do SoundCloud invalida.")

    token = (access_token or "").strip()
    if token:
        data = _resolve_auth_playlist(url, token)
        tracks = data.get("tracks") or []
        if not tracks and data.get("id"):
            details = requests.get(
                f"{API_V1}/playlists/{data['id']}",
                params={"show_tracks": "true"},
                headers=_auth_headers(token),
                timeout=15,
            )
            if details.status_code == 200:
                data = details.json()
                tracks = data.get("tracks") or []
    else:
        data = _resolve_public_playlist(url)
        tracks = data.get("tracks") or []
        incomplete_ids = [str(track["id"]) for track in tracks if not track.get("title")]
        if incomplete_ids:
            client_id = _get_client_id()
            for start in range(0, len(incomplete_ids), 50):
                chunk = incomplete_ids[start : start + 50]
                response = requests.get(
                    f"{API_V2}/tracks",
                    params={"ids": ",".join(chunk), "client_id": client_id},
                    headers=_public_headers(),
                    timeout=15,
                )
                if response.status_code != 200:
                    continue
                detailed = {str(track["id"]): track for track in response.json()}
                for track in tracks:
                    if str(track.get("id")) in detailed:
                        track.update(detailed[str(track["id"])])

    kind = data.get("kind") or data.get("type") or ""
    if kind not in ("playlist", "system-playlist"):
        raise ValueError("O link informado nao e uma playlist do SoundCloud.")

    normalized_tracks = []
    for track in tracks:
        normalized = _normalize_track(track)
        if normalized:
            normalized_tracks.append(normalized)

    if not normalized_tracks:
        raise ValueError("A playlist do SoundCloud nao retornou faixas.")

    return data.get("title", "SoundCloud Playlist"), normalized_tracks


def search_track(access_token: str, titulo: str, artista: str = "", album: str = "") -> str | None:
    query_options = []
    if artista and album:
        query_options.append(f"{artista} {titulo} {album}")
    if artista:
        query_options.append(f"{artista} {titulo}")
    query_options.append(titulo)

    token = str(access_token or "").strip()
    for query in query_options:
        if token:
            response = requests.get(
                f"{API_V1}/tracks",
                params={"q": query, "limit": 10, "linked_partitioning": "false"},
                headers=_auth_headers(token),
                timeout=15,
            )
        else:
            client_id = _get_client_id()
            response = requests.get(
                f"{API_V2}/search/tracks",
                params={**_web_params(client_id), "q": query, "limit": 10, "linked_partitioning": "false"},
                headers=_public_headers(),
                timeout=15,
            )
        if response.status_code != 200:
            continue
        results = response.json()
        collection = results if isinstance(results, list) else results.get("collection") or []
        ranked = sorted(
            ((track, _score_track(track, titulo, artista, album)) for track in collection),
            key=lambda item: item[1],
            reverse=True,
        )
        if ranked and ranked[0][1] >= 35 and ranked[0][0].get("id"):
            return str(ranked[0][0]["id"])
        for track in collection:
            track_id = track.get("id")
            if track_id:
                return str(track_id)
    return None


def search_track_web_session(
    cookie_header: str,
    client_id: str,
    titulo: str,
    artista: str = "",
    album: str = "",
) -> str | None:
    query_options = []
    if artista and album:
        query_options.append(f"{artista} {titulo} {album}")
    if artista:
        query_options.append(f"{artista} {titulo}")
    query_options.append(titulo)

    headers = _web_session_headers(cookie_header)
    for query in query_options:
        response = requests.get(
            f"{API_V2}/search/tracks",
            params={**_web_params(client_id), "q": query, "limit": 10, "linked_partitioning": "false"},
            headers=headers,
            timeout=15,
        )
        if response.status_code != 200:
            continue
        results = response.json()
        collection = results if isinstance(results, list) else results.get("collection") or []
        ranked = sorted(
            ((track, _score_track(track, titulo, artista, album)) for track in collection),
            key=lambda item: item[1],
            reverse=True,
        )
        if ranked and ranked[0][1] >= 35 and ranked[0][0].get("id"):
            return str(ranked[0][0]["id"])
        for track in collection:
            track_id = track.get("id")
            if track_id:
                return str(track_id)
    return None


def create_playlist(
    access_token: str,
    nome: str,
    descricao: str = "",
    client_id: str = "",
    app_version: str = "",
    cookie_header: str = "",
) -> dict[str, str]:
    description = descricao or "Transferida via PlayTransfer"
    client_id = str(client_id or "").strip() or _get_client_id()
    app_version = str(app_version or "").strip()
    cookie_header = str(cookie_header or "").strip()
    attempts = [
        (
            f"{API_V2}/playlists",
            {"title": nome, "description": description, "sharing": "private", "tracks": []},
            True,
        ),
        (
            f"{API_V2}/playlists",
            {"title": nome, "description": description, "sharing": "private", "track_urns": []},
            True,
        ),
        (
            f"{API_V1}/playlists",
            {"playlist": {"title": nome, "description": description, "sharing": "private", "tracks": []}},
            False,
        ),
    ]
    last_response = None
    for headers in _auth_header_variants(access_token):
        request_headers = {
            **headers,
            "Origin": "https://soundcloud.com",
            "Referer": "https://soundcloud.com/",
            "X-Requested-With": "XMLHttpRequest",
        }
        if cookie_header:
            request_headers["Cookie"] = cookie_header
            datadome = _cookie_from_header(cookie_header, "datadome")
            if datadome:
                request_headers["X-Datadome-Clientid"] = datadome
        for url, payload, use_client_id in attempts:
            response = requests.post(
                url,
                params=_web_params(client_id, app_version) if use_client_id else None,
                headers=request_headers,
                json=payload,
                timeout=20,
            )
            last_response = response
            if response.status_code not in (200, 201):
                continue

            data = response.json()
            playlist_id = data.get("id") or data.get("playlist", {}).get("id")
            if not playlist_id:
                continue
            return {
                "id": str(playlist_id),
                "url": data.get("permalink_url")
                or data.get("playlist", {}).get("permalink_url")
                or f"https://soundcloud.com/you/sets/{playlist_id}",
            }

    if last_response is None:
        raise ValueError("Falha ao gerar playlist no SoundCloud.")
    detail = _response_detail(last_response)
    suffix = f" Detalhe: {detail}" if detail else ""
    raise ValueError(f"Falha ao gerar playlist no SoundCloud (HTTP {last_response.status_code}).{suffix}")


def create_playlist_web_session(cookie_header: str, client_id: str, nome: str, descricao: str = "", app_version: str = "") -> dict[str, str]:
    headers = _web_session_headers(cookie_header)
    description = descricao or "Transferida via PlayTransfer"
    attempts = [
        (
            f"{API_V2}/playlists",
            {"playlist": {"title": nome, "description": description, "sharing": "private", "tracks": []}},
        ),
        (
            f"{API_V2}/playlists",
            {"title": nome, "description": description, "sharing": "private", "tracks": []},
        ),
        (
            f"{API_V2}/playlists",
            {"title": nome, "description": description, "sharing": "private", "track_urns": []},
        ),
        (
            f"{API_V1}/playlists",
            {"playlist": {"title": nome, "description": description, "sharing": "private", "tracks": []}},
        ),
    ]
    last_status = ""
    for url, payload in attempts:
        response = requests.post(
            url,
            params=_web_params(client_id, app_version),
            headers=headers,
            json=payload,
            timeout=25,
        )
        last_status = f"HTTP {response.status_code}"
        if response.status_code not in (200, 201):
            detail = _response_detail(response)
            if detail:
                last_status = f"{last_status}. Detalhe: {detail}"
            continue
        data = response.json() if response.content else {}
        playlist_id = data.get("id") or data.get("playlist", {}).get("id")
        if playlist_id:
            return {
                "id": str(playlist_id),
                "url": data.get("permalink_url")
                or data.get("playlist", {}).get("permalink_url")
                or f"https://soundcloud.com/you/sets/{playlist_id}",
            }

    raise ValueError(f"Falha ao gerar playlist no SC web ({last_status}).")


def create_playlist_with_tracks_webview(
    nome: str,
    descricao: str = "",
    track_ids: list[str] | None = None,
    access_token: str = "",
    cookie_header: str = "",
    client_id: str = "",
    app_version: str = "",
) -> dict[str, str]:
    """Create a SoundCloud playlist from inside the logged-in SoundCloud WebView.

    SoundCloud returns 403 when the server replays browser cookies against
    playlist write endpoints. Running the write fetch in the same WebView profile
    keeps the request in the browser context that the user actually authorized.
    """
    payload = {
        "name": nome,
        "description": descricao or "Transferida via PlayTransfer",
        "track_ids": [str(track_id) for track_id in (track_ids or []) if str(track_id or "").strip()],
        "access_token": str(access_token or "").strip(),
        "cookie_header": str(cookie_header or "").strip(),
        "client_id": str(client_id or "").strip(),
        "app_version": str(app_version or "").strip(),
    }
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(root_dir, "soundcloud_playlist_webview.py")
    if not os.path.exists(script_path):
        raise ValueError("Executor do SoundCloud nao encontrado.")

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as fp:
            json.dump(payload, fp, ensure_ascii=False)
            temp_path = fp.name

        proc = subprocess.run(
            [sys.executable, script_path, temp_path],
            cwd=root_dir,
            capture_output=True,
            text=True,
            timeout=140,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("O SoundCloud demorou muito para criar a playlist na janela logada.") from exc
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    output = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    result = None
    for line in output.splitlines():
        if line.startswith("SC_PLAYLIST_RESULT:"):
            try:
                result = json.loads(line.split("SC_PLAYLIST_RESULT:", 1)[1].strip())
            except Exception:
                result = None

    if not result:
        detail = output.strip()[-500:] or f"processo saiu com codigo {proc.returncode}"
        raise ValueError(f"Nao consegui receber resposta do SoundCloud na janela logada. Detalhe: {detail}")

    if not result.get("ok"):
        detail = str(result.get("error") or result.get("detail") or "").strip()
        raise ValueError(f"O SoundCloud recusou criar ou editar a playlist na janela logada. Detalhe: {detail}")

    playlist_id = str(result.get("id") or "").strip()
    if not playlist_id:
        raise ValueError("O SoundCloud criou uma resposta sem id de playlist.")
    return {
        "id": playlist_id,
        "url": str(result.get("url") or "").strip() or f"https://soundcloud.com/you/sets/{playlist_id}",
    }


def add_tracks(access_token: str, playlist_id: str, track_ids: list[str]) -> None:
    if not track_ids:
        return

    track_ints = []
    for track_id in track_ids:
        try:
            track_ints.append(int(track_id))
        except Exception:
            continue
    tracks_payload = [{"id": track_id} for track_id in track_ints]
    if not tracks_payload:
        return

    client_id = _get_client_id()
    track_urns = [f"soundcloud:tracks:{track_id}" for track_id in track_ints]
    attempts = [
        ("put", f"{API_V2}/playlists/{playlist_id}", {"playlist": {"tracks": tracks_payload}}, True),
        ("patch", f"{API_V2}/playlists/{playlist_id}", {"playlist": {"tracks": tracks_payload}}, True),
        ("put", f"{API_V2}/playlists/{playlist_id}", {"tracks": tracks_payload}, True),
        ("patch", f"{API_V2}/playlists/{playlist_id}", {"track_urns": track_urns}, True),
        ("put", f"{API_V1}/playlists/{playlist_id}", {"playlist": {"tracks": tracks_payload}}, False),
    ]
    last_response = None
    for headers in _auth_header_variants(access_token):
        for method, url, payload, use_client_id in attempts:
            request_fn = requests.patch if method == "patch" else requests.put
            response = request_fn(
                url,
                params=_web_params(client_id) if use_client_id else None,
                headers=headers,
                json=payload,
                timeout=30,
            )
            last_response = response
            if response.status_code in (200, 201, 204):
                return

    if last_response is None:
        raise ValueError("Falha ao incluir musicas no SoundCloud.")
    detail = _response_detail(last_response)
    suffix = f" Detalhe: {detail}" if detail else ""
    raise ValueError(f"Falha ao incluir musicas no SoundCloud (HTTP {last_response.status_code}).{suffix}")


def add_tracks_web_session(cookie_header: str, client_id: str, playlist_id: str, track_ids: list[str], app_version: str = "") -> None:
    if not track_ids:
        return

    track_ints = []
    for track_id in track_ids:
        try:
            track_ints.append(int(track_id))
        except Exception:
            continue
    if not track_ints:
        return

    tracks_payload = [{"id": track_id} for track_id in track_ints]
    track_urns = [f"soundcloud:tracks:{track_id}" for track_id in track_ints]
    headers = _web_session_headers(cookie_header)
    attempts = [
        (
            "put",
            f"{API_V2}/playlists/{playlist_id}",
            {"playlist": {"tracks": tracks_payload}},
        ),
        (
            "patch",
            f"{API_V2}/playlists/{playlist_id}",
            {"playlist": {"tracks": tracks_payload}},
        ),
        (
            "put",
            f"{API_V2}/playlists/{playlist_id}",
            {"tracks": tracks_payload},
        ),
        (
            "patch",
            f"{API_V2}/playlists/{playlist_id}",
            {"track_urns": track_urns},
        ),
        (
            "put",
            f"{API_V1}/playlists/{playlist_id}",
            {"playlist": {"tracks": tracks_payload}},
        ),
    ]
    last_status = ""
    for method, url, payload in attempts:
        request_fn = requests.patch if method == "patch" else requests.put
        response = request_fn(
            url,
            params=_web_params(client_id, app_version),
            headers=headers,
            json=payload,
            timeout=35,
        )
        last_status = f"HTTP {response.status_code}"
        if response.status_code not in (200, 201, 204):
            detail = _response_detail(response)
            if detail:
                last_status = f"{last_status}. Detalhe: {detail}"
            continue
        if response.status_code in (200, 201, 204):
            return

    raise ValueError(f"Falha ao incluir musicas no SC web ({last_status}).")
