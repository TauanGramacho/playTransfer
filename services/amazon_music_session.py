"""
Cookie/session mode for Amazon Music Web.

This module is intentionally separate from services.amazon_music because the
official Amazon API and the web-player session API behave differently.
"""
from __future__ import annotations

import base64
import json
import re
import time
import uuid
from typing import Any
from urllib.parse import parse_qsl, urlparse

import requests

from services.amazon_music import UA, _extract_playlist_id, _read_track_node


GQL_ENDPOINT = "https://gql.music.amazon.dev"
FIREFLY_WEB_API_KEY = "amzn1.application.e1dc16675f9f4c78b31927d5bfd5c229"
FIREFLY_ANON_API_KEY = "amzn1.application.5d9d979e3a5f4e8ea83bc8536b4fde0b"
PLAYLIST_CLIENT_INFO = (
    "Web.TemplatesInterface.v1_0.Touch.PlaylistTemplateInterface."
    "PlaylistClientInformation"
)
SEARCH_KEYWORD_CLIENT_INFO = (
    "Web.TemplatesInterface.v1_0.Touch.SearchTemplateInterface."
    "SearchKeywordClientInformation"
)


def _get_region(session_cookies: dict) -> str:
    region = str(session_cookies.get("_region") or "com").strip()
    return region or "com"


def _base(session_cookies: dict) -> str:
    return f"https://music.amazon.{_get_region(session_cookies)}"


def _clean_cookies(session_cookies: dict) -> dict:
    return {k: v for k, v in session_cookies.items() if not str(k).startswith("_")}


def _compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _csrf(session_cookies: dict) -> str:
    return (
        session_cookies.get("_csrf_token", "")
        or session_cookies.get("csrf-main", "")
        or session_cookies.get("session-token", "")
        or ""
    )


def _headers(session_cookies: dict) -> dict[str, str]:
    base = _base(session_cookies)
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json; charset=UTF-8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": f"{base}/",
        "Origin": base,
        "Connection": "keep-alive",
    }

    access_token = str(session_cookies.get("_access_token") or "").strip()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
        headers["x-amzn-authentication"] = access_token

    csrf_token = _csrf(session_cookies)
    if csrf_token:
        headers["x-music-csrf-token"] = csrf_token
        headers["anti-csrftoken-a2z"] = csrf_token
        headers["csrf-token"] = csrf_token
        if session_cookies.get("_csrf_ts"):
            headers["csrf-ts"] = str(session_cookies["_csrf_ts"])
        if session_cookies.get("_csrf_rnd"):
            headers["csrf-rnd"] = str(session_cookies["_csrf_rnd"])
    return headers


def _json_or_empty(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else {"items": payload}
    except Exception:
        return {}


def _detail(response: requests.Response) -> str:
    payload = _json_or_empty(response)
    message = (
        payload.get("message")
        or payload.get("code")
        or payload.get("error")
        or payload.get("errorMessage")
        or ""
    )
    if message:
        return str(message)[:240]
    return (response.text or "")[:240]


def _refresh_metadata(session_cookies: dict, *, force: bool = False) -> None:
    """Populate access token, CSRF and region metadata from Amazon config.json."""
    if not force and session_cookies.get("_metadata_loaded") == "1":
        return
    session_cookies["_metadata_loaded"] = "1"

    try:
        response = requests.get(
            f"{_base(session_cookies)}/config.json",
            headers=_headers(session_cookies),
            cookies=_clean_cookies(session_cookies),
            timeout=12,
        )
        if response.status_code != 200:
            return
        data = _json_or_empty(response)
        csrf = data.get("csrf") if isinstance(data.get("csrf"), dict) else {}
        mapping = {
            "_access_token": data.get("accessToken"),
            "_customer_id": data.get("customerId"),
            "_device_type": data.get("deviceType"),
            "_device_id": data.get("deviceId"),
            "_marketplace_id": data.get("marketplaceId"),
            "_music_territory": data.get("musicTerritory"),
            "_site_region": data.get("siteRegion"),
            "_session_id": data.get("sessionId"),
            "_display_language": data.get("displayLanguage"),
            "_application_version": data.get("version"),
            "_csrf_token": csrf.get("token"),
            "_csrf_rnd": csrf.get("rnd"),
            "_csrf_ts": csrf.get("ts"),
        }
        for key, value in mapping.items():
            if value:
                session_cookies[key] = str(value)
    except Exception:
        return


def _ensure_access_token(session_cookies: dict) -> str:
    _refresh_metadata(session_cookies)
    token = str(session_cookies.get("_access_token") or "").strip()
    if not token:
        _refresh_metadata(session_cookies, force=True)
        token = str(session_cookies.get("_access_token") or "").strip()
    if not token:
        raise ValueError("Sessao do Amazon Music expirada. Reconecte o Amazon Music.")
    return token


def _region_prefixes(session_cookies: dict) -> list[str]:
    _refresh_metadata(session_cookies)
    prefixes: list[str] = []

    def add(value: str | None) -> None:
        value = (value or "").strip().upper()
        if value == "ZAZ":
            value = "EU"
        if value in {"NA", "EU", "FE"} and value not in prefixes:
            prefixes.append(value)

    add(session_cookies.get("_site_region"))
    territory = (session_cookies.get("_music_territory") or "").upper()
    if territory in {
        "GB", "UK", "IE", "DE", "FR", "ES", "IT", "NL", "BE", "PT", "SE",
        "NO", "DK", "FI", "PL", "AT", "CH", "TR",
    }:
        add("EU")
    elif territory in {"JP", "AU", "NZ", "SG"}:
        add("FE")
    else:
        add("NA")

    for fallback in ("NA", "EU", "FE"):
        add(fallback)
    return prefixes


def _site_region_slug(session_cookies: dict) -> str:
    for prefix in _region_prefixes(session_cookies):
        if prefix == "EU":
            return "eu"
        if prefix == "FE":
            return "fe"
        if prefix == "NA":
            return "na"
    return "na"


def _v1_paths(session_cookies: dict, suffixes: list[str]) -> list[str]:
    roots = [f"/{prefix}/v1" for prefix in _region_prefixes(session_cookies)]
    roots.append("/v1")
    paths: list[str] = []
    for root in roots:
        for suffix in suffixes:
            path = f"{root}{suffix}"
            if path not in paths:
                paths.append(path)
    return paths


def _common_params(session_cookies: dict, limit: int = 5) -> dict[str, Any]:
    _refresh_metadata(session_cookies)
    return {
        "limit": limit,
        "size": limit,
        "musicTerritory": session_cookies.get("_music_territory") or "US",
        "locale": session_cookies.get("_display_language") or "en_US",
    }


def _try_requests(
    method: str,
    paths: list[str],
    session_cookies: dict,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    timeout: int = 20,
) -> tuple[dict[str, Any], str]:
    attempts: list[str] = []
    for path in paths:
        response = requests.request(
            method,
            f"{_base(session_cookies)}{path}",
            headers=_headers(session_cookies),
            cookies=_clean_cookies(session_cookies),
            params=params,
            json=json_body,
            timeout=timeout,
            allow_redirects=False,
        )
        if response.status_code in (200, 201, 202, 204):
            return _json_or_empty(response), path
        if response.status_code in (401, 403):
            raise ValueError("Sessao do Amazon Music expirada. Reconecte o Amazon Music.")
        attempts.append(f"{path} -> HTTP {response.status_code}{f' ({_detail(response)})' if _detail(response) else ''}")
    raise ValueError("; ".join(attempts[:6]) or "Amazon Music nao respondeu.")


def _walk_dicts(value: Any, max_nodes: int = 1500):
    seen = 0
    stack = [value]
    while stack and seen < max_nodes:
        current = stack.pop()
        seen += 1
        if isinstance(current, dict):
            yield current
            for item in current.values():
                if isinstance(item, (dict, list)):
                    stack.append(item)
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, (dict, list)):
                    stack.append(item)


def _walk_strings(value: Any, max_nodes: int = 3000):
    seen = 0
    stack = [value]
    while stack and seen < max_nodes:
        current = stack.pop()
        seen += 1
        if isinstance(current, str):
            yield current
        elif isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "title", "name", "label", "primaryText", "secondaryText"):
            text = _text(value.get(key))
            if text:
                return text
    return ""


def _extract_playlist_id_from_text(text: str) -> str | None:
    patterns = [
        r"/my/playlists/([A-Za-z0-9_.:-]+)",
        r"/playlists/([A-Za-z0-9_.:-]+)",
        r"/user-playlists/([A-Za-z0-9_.:-]+)",
        r"playlistId[=:%22\"']+([A-Za-z0-9_.:-]+)",
        r"playlistID[=:%22\"']+([A-Za-z0-9_.:-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip("%22\"'&? ")
    return None


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _strip_track_noise(value: str) -> str:
    cleaned = re.sub(r"\([^)]*(?:feat|ft\.?|with|remaster|explicit|version|edit)[^)]*\)", " ", value, flags=re.I)
    cleaned = re.sub(r"\[[^\]]*(?:feat|ft\.?|with|remaster|explicit|version|edit)[^\]]*\]", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+-\s+.*(?:remaster|explicit|version|edit).*", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(feat|ft)\.?\s+.+$", " ", cleaned, flags=re.I)
    return _normalize_spaces(cleaned)


def _search_query_variants(titulo: str, artista: str = "") -> list[str]:
    title = _normalize_spaces(titulo)
    artist = _normalize_spaces(artista)
    clean_title = _strip_track_noise(title)
    simpler_title = _normalize_spaces(re.sub(r"[^\w\s'.-]", " ", clean_title, flags=re.UNICODE))
    variants = [
        f"{clean_title} {artist}",
        clean_title,
        f"{simpler_title} {artist}",
        simpler_title,
        f"{title} {artist}",
        title,
    ]
    result: list[str] = []
    seen: set[str] = set()
    for item in variants:
        item = _normalize_spaces(item)
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _extract_track_id_from_text(text: str) -> str | None:
    patterns = [
        r"track(?:Id|ID|Asin)?[=:%22\"']+([A-Z0-9]{8,16})",
        r"asin[=:%22\"']+([A-Z0-9]{8,16})",
        r"/tracks/([A-Z0-9]{8,16})",
        r"/track/([A-Z0-9]{8,16})",
        r"uri:///track/([A-Z0-9]{8,16})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip("%22\"'&? ")
    return None


def _json_blob(value: Any) -> str:
    try:
        return _compact_json(value)
    except Exception:
        return str(value)


def _pick_track_from_webskill(payload: dict[str, Any], titulo: str, artista: str = "") -> str | None:
    clean_title = _strip_track_noise(titulo).lower()
    artist = (artista or "").lower()
    best: tuple[int, str] | None = None

    for node in _walk_dicts(payload, max_nodes=5000):
        blob = _json_blob(node)
        lowered = blob.lower()
        if "podcast" in lowered and "track" not in lowered:
            continue

        track_id = None
        for key in ("trackId", "trackID", "trackAsin", "asin", "globalAsin", "id"):
            value = node.get(key)
            if value and re.fullmatch(r"[A-Z0-9]{8,16}", str(value), flags=re.I):
                track_id = str(value)
                break
        if not track_id:
            for key in ("url", "href", "path", "deeplink", "deepLink", "uri"):
                value = node.get(key)
                if isinstance(value, str):
                    track_id = _extract_track_id_from_text(value)
                    if track_id:
                        break
        if not track_id:
            track_id = _extract_track_id_from_text(blob)
        if not track_id:
            continue

        score = 1
        if clean_title and clean_title in lowered:
            score += 4
        if artist and artist in lowered:
            score += 3
        if "track" in lowered:
            score += 1
        if best is None or score > best[0]:
            best = (score, track_id)

    if best:
        return best[1]
    return None


def _pick_track_id(payload: dict[str, Any]) -> str | None:
    for node in _walk_dicts(payload):
        if not (node.get("title") or node.get("name")):
            continue
        for key in ("id", "trackId", "asin", "catalogId", "musicId", "globalAsin"):
            value = node.get(key)
            if value:
                return str(value)
    return None


def _pick_playlist(payload: dict[str, Any], wanted_name: str = "") -> dict[str, str] | None:
    wanted = wanted_name.strip().lower()
    preferred: list[Any] = []
    data = payload.get("data") if isinstance(payload, dict) else {}
    if isinstance(data, dict):
        preferred.extend([data.get("createPlaylist"), data.get("playlist"), data.get("result"), data])
    preferred.extend([
        payload.get("createPlaylist"),
        payload.get("playlist"),
        payload.get("result"),
        payload,
    ])

    for container in preferred:
        if not isinstance(container, dict):
            continue
        playlist_id = (
            container.get("id")
            or container.get("playlistId")
            or container.get("playlistID")
            or container.get("asin")
            or container.get("catalogId")
        )
        if playlist_id:
            return {"id": str(playlist_id), "url": str(container.get("url") or "")}

    fallback: dict[str, str] | None = None
    for node in _walk_dicts(payload):
        node_text = " ".join(
            part for part in (
                _text(node.get("title")),
                _text(node.get("name")),
                _text(node.get("text")),
                _text(node.get("primaryText")),
                _text(node.get("header")),
            )
            if part
        ).strip()

        playlist_id = (
            node.get("playlistId")
            or node.get("playlistID")
            or node.get("playlist_id")
            or node.get("entityId")
            or node.get("id")
            or node.get("asin")
        )
        for key in ("url", "href", "path", "deepLink", "deeplink"):
            value = node.get(key)
            if isinstance(value, str):
                playlist_id = playlist_id or _extract_playlist_id_from_text(value)

        if playlist_id:
            result = {"id": str(playlist_id), "url": str(node.get("url") or "")}
            if wanted and wanted in node_text.lower():
                return result
            if not fallback and ("playlist" in str(node).lower() or node_text):
                fallback = result

    for value in _walk_strings(payload):
        playlist_id = _extract_playlist_id_from_text(value)
        if playlist_id:
            return {"id": playlist_id, "url": value if value.startswith("http") else ""}

    return fallback


def _webskill_client_headers(session_cookies: dict, page_path: str = "/my/playlists") -> dict[str, str]:
    token = _ensure_access_token(session_cookies)
    base = _base(session_cookies)
    now_ms = str(int(time.time() * 1000))
    csrf_token = _csrf(session_cookies)
    csrf_header = {
        "interface": "CSRFInterface.v1_0.CSRFHeaderElement",
        "token": csrf_token,
        "timestamp": str(session_cookies.get("_csrf_ts") or now_ms),
        "rndNonce": str(session_cookies.get("_csrf_rnd") or uuid.uuid4().hex),
    }
    return {
        "x-amzn-authentication": _compact_json({
            "interface": "ClientAuthenticationInterface.v1_0.ClientTokenElement",
            "accessToken": token,
        }),
        "x-amzn-csrf": _compact_json(csrf_header),
        "x-amzn-device-id": str(session_cookies.get("_device_id") or session_cookies.get("ubid-main") or uuid.uuid4()),
        "x-amzn-device-model": "WEBPLAYER",
        "x-amzn-device-family": "WebPlayer",
        "x-amzn-device-width": "480",
        "x-amzn-device-height": "780",
        "x-amzn-device-language": str(session_cookies.get("_display_language") or "en_US"),
        "x-amzn-session-id": str(session_cookies.get("_session_id") or uuid.uuid4()),
        "x-amzn-request-id": str(uuid.uuid4()),
        "x-amzn-currency-of-preference": "",
        "x-amzn-os-version": "WEB",
        "x-amzn-application-version": str(session_cookies.get("_application_version") or "1.0.0"),
        "x-amzn-device-time-zone": "America/Sao_Paulo",
        "x-amzn-timestamp": now_ms,
        "x-amzn-music-domain": base,
        "x-amzn-referer": f"{base}{page_path}",
        "x-amzn-page-url": f"{base}{page_path}",
    }


def _webskill_url(session_cookies: dict, path_or_url: str) -> tuple[str, dict[str, str]]:
    if path_or_url.startswith("http"):
        parsed = urlparse(path_or_url)
        path = parsed.path or "/"
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    else:
        parsed = urlparse(path_or_url)
        path = parsed.path or path_or_url
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if not path.startswith("/"):
        path = f"/{path}"

    host_region = _site_region_slug(session_cookies)
    return f"https://{host_region}.web.skill.music.a2z.com{path}", params


def _webskill_request(
    session_cookies: dict,
    path_or_url: str,
    *,
    params: dict[str, Any] | None = None,
    page_path: str = "/my/playlists",
    timeout: int = 25,
) -> dict[str, Any]:
    url, query_params = _webskill_url(session_cookies, path_or_url)
    body: dict[str, Any] = {}
    body.update(query_params)
    if params:
        body.update(params)
    body["headers"] = _compact_json(_webskill_client_headers(session_cookies, page_path))

    response = requests.post(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": _base(session_cookies),
            "Referer": f"{_base(session_cookies)}{page_path}",
        },
        json=body,
        timeout=timeout,
    )
    if response.status_code in (401, 403):
        raise ValueError("Sessao do Amazon Music expirada. Reconecte o Amazon Music.")
    if response.status_code >= 400:
        raise ValueError(f"Amazon Music retornou HTTP {response.status_code}: {_detail(response)}")
    payload = _json_or_empty(response)
    return payload or {"raw": response.text}


def _find_webskill_method(payload: dict[str, Any], endpoint: str) -> dict[str, Any] | None:
    endpoint_lower = endpoint.lower()
    for node in _walk_dicts(payload):
        url = str(node.get("url") or node.get("href") or "")
        if endpoint_lower in url.lower():
            return node
    return None


def _has_service_error(payload: dict[str, Any]) -> bool:
    joined = " ".join(value.lower() for value in _walk_strings(payload))
    return "service error" in joined or "sorry, something went wrong" in joined


def _execute_create_method(
    session_cookies: dict,
    method: dict[str, Any],
    nome: str,
) -> dict[str, Any]:
    playlist_info = {
        "interface": PLAYLIST_CLIENT_INFO,
        "name": nome,
        "path": "/my/playlists",
    }
    params = {"playlistInfo": _compact_json(playlist_info)}
    url = str(method.get("url") or method.get("href") or "/api/createPlaylist")
    return _webskill_request(session_cookies, url, params=params, page_path="/my/playlists")


def _webskill_create_playlist(session_cookies: dict, nome: str) -> dict[str, str]:
    listing = _webskill_request(session_cookies, "/api/showLibraryPlaylists", page_path="/my/playlists")
    method = _find_webskill_method(listing, "/api/createPlaylist")
    if method:
        created_payload = _execute_create_method(session_cookies, method, nome)
    else:
        created_payload = _webskill_request(
            session_cookies,
            "/api/createPlaylist",
            params={
                "userHash": _compact_json({"level": "LIBRARY_MEMBER"}),
                "playlistInfo": _compact_json({
                    "interface": PLAYLIST_CLIENT_INFO,
                    "name": nome,
                    "path": "/my/playlists",
                }),
            },
            page_path="/my/playlists",
        )

    if _has_service_error(created_payload):
        raise ValueError("Amazon Music recusou a criacao da playlist com esta sessao.")

    playlist = _pick_playlist(created_payload, nome)
    if not playlist:
        for _ in range(4):
            time.sleep(0.8)
            listing = _webskill_request(session_cookies, "/api/showLibraryPlaylists", page_path="/my/playlists")
            playlist = _pick_playlist(listing, nome)
            if playlist:
                break

    if not playlist:
        raise ValueError("Amazon Music criou a playlist, mas nao devolveu o ID para continuar.")

    playlist_url = playlist.get("url") or f"{_base(session_cookies)}/my/playlists/{playlist['id']}"
    return {"id": playlist["id"], "url": playlist_url}


def _graphql_auth_value(session_cookies: dict, auth_scheme: str) -> str:
    token = _ensure_access_token(session_cookies)
    if auth_scheme == "AmznMusic":
        # The Amazon Music web player sends AmznMusic with a base64 JSON payload,
        # not the raw access token. Sending the raw token makes playlist edits fail.
        payload = _compact_json({"access_token": token}).encode("utf-8")
        return f"AmznMusic {base64.b64encode(payload).decode('ascii')}"
    return f"{auth_scheme} {token}"


def _graphql_headers(session_cookies: dict, auth_scheme: str) -> dict[str, str]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Origin": _base(session_cookies),
        "Referer": f"{_base(session_cookies)}/",
        "x-api-key": FIREFLY_WEB_API_KEY,
        "x-amzn-session-id": str(session_cookies.get("_session_id") or ""),
        "x-amzn-client-app-version": str(session_cookies.get("_application_version") or "1.0.0"),
        "device-id": str(session_cookies.get("_device_id") or ""),
        "device-type": str(session_cookies.get("_device_type") or ""),
        "music-territory": str(session_cookies.get("_music_territory") or "US"),
    }
    if auth_scheme:
        headers["Authorization"] = _graphql_auth_value(session_cookies, auth_scheme)
    return headers


def _graphql(
    session_cookies: dict,
    operation_name: str,
    query: str,
    variables: dict[str, Any],
    *,
    timeout: int = 25,
) -> dict[str, Any]:
    cached = str(session_cookies.get("_graphql_auth_scheme") or "").strip()
    schemes = [scheme for scheme in (cached, "AmznMusic", "Bearer") if scheme]
    seen: set[str] = set()
    attempts: list[str] = []

    for scheme in schemes:
        if scheme in seen:
            continue
        seen.add(scheme)
        response = requests.post(
            GQL_ENDPOINT,
            headers=_graphql_headers(session_cookies, scheme),
            json={
                "operationName": operation_name,
                "query": query,
                "variables": variables,
            },
            timeout=timeout,
        )
        if response.status_code >= 400:
            attempts.append(f"{scheme} -> HTTP {response.status_code}: {_detail(response)}")
            continue

        payload = _json_or_empty(response)
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if errors:
            message = _compact_json(errors)[:320]
            lowered = message.lower()
            if any(word in lowered for word in ("unauthorized", "forbidden", "authentication", "auth")):
                attempts.append(f"{scheme} -> {message}")
                continue
            attempts.append(f"{scheme} -> {message}")
            continue

        session_cookies["_graphql_auth_scheme"] = scheme
        return payload

    if attempts:
        raise ValueError("; ".join(attempts[:3]))
    raise ValueError("Amazon Music GraphQL nao aceitou esta sessao.")


def _graphql_create_playlist(session_cookies: dict, nome: str, descricao: str) -> dict[str, str]:
    mutation = """
    mutation createPlaylistWithDescription($title: String!, $description: String, $visibility: String, $trackAsins: [String]) {
      createPlaylist(title: $title, description: $description, visibility: $visibility, trackAsins: $trackAsins) {
        id
      }
    }
    """
    payload = _graphql(
        session_cookies,
        "createPlaylistWithDescription",
        mutation,
        {
            "title": nome,
            "description": descricao or "Transferida via PlayTransfer",
            "visibility": "PRIVATE",
            "trackAsins": [],
        },
    )
    playlist = (((payload.get("data") or {}).get("createPlaylist")) or {})
    playlist_id = playlist.get("id") or playlist.get("playlistId")
    if not playlist_id:
        raise ValueError("Amazon Music criou a playlist, mas nao devolveu o ID.")
    playlist_url = playlist.get("url") or f"{_base(session_cookies)}/my/playlists/{playlist_id}"
    return {"id": str(playlist_id), "url": str(playlist_url)}


def _artist_names(node: dict[str, Any]) -> str:
    artists: list[str] = []
    for field in ("contributingArtists", "artists"):
        value = node.get(field)
        if isinstance(value, dict):
            edges = value.get("edges") or []
            for edge in edges:
                artist = edge.get("node") if isinstance(edge, dict) else None
                if isinstance(artist, dict) and artist.get("name"):
                    artists.append(str(artist["name"]))
        elif isinstance(value, list):
            for artist in value:
                if isinstance(artist, dict) and artist.get("name"):
                    artists.append(str(artist["name"]))
    return " ".join(artists)


def _score_track(node: dict[str, Any], titulo: str, artista: str) -> int:
    title = str(node.get("title") or node.get("name") or "").lower()
    artists = _artist_names(node).lower()
    score = 0
    if titulo and titulo.lower() in title:
        score += 3
    if artista and artista.lower() in artists:
        score += 2
    if node.get("id"):
        score += 1
    return score


def _graphql_search_track(session_cookies: dict, titulo: str, artista: str = "") -> str | None:
    query_variants = _search_query_variants(titulo, artista)
    if not query_variants:
        return None

    query = """
    query searchTracks($query: String!, $searchType: String) {
      searchTracks(searchOptions: { searchFilters: [{ query: $query }], searchType: $searchType }) {
        edges {
          node {
            id
            url
            title
            contributingArtists {
              edges {
                node {
                  id
                  name
                }
              }
            }
          }
        }
        edgeCount
      }
    }
    """
    candidates: list[dict[str, Any]] = []
    failures: list[str] = []
    for query_text in query_variants[:5]:
        for search_type in ("personalized", None):
            try:
                variables = {"query": query_text, "searchType": search_type}
                payload = _graphql(session_cookies, "searchTracks", query, variables, timeout=8)
            except Exception as exc:
                failures.append(f"{query_text}/{search_type or 'default'}: {str(exc)[:180]}")
                continue
            edges = ((((payload.get("data") or {}).get("searchTracks") or {}).get("edges")) or [])
            for edge in edges:
                node = edge.get("node") if isinstance(edge, dict) else None
                if isinstance(node, dict) and node.get("id"):
                    candidates.append(node)
            if candidates:
                break
        if candidates:
            break

    if not candidates:
        if failures:
            print("[Amazon Music DEBUG] searchTracks attempts failed: " + " | ".join(failures[:3]), flush=True)
        return None

    candidates.sort(key=lambda node: _score_track(node, titulo, artista), reverse=True)
    return str(candidates[0].get("id"))


def _webskill_search_track(session_cookies: dict, titulo: str, artista: str = "") -> str | None:
    attempts: list[str] = []
    for query_text in _search_query_variants(titulo, artista)[:5]:
        keyword_info = {
            "interface": SEARCH_KEYWORD_CLIENT_INFO,
            "keyword": query_text,
        }
        payload_variants = [
            {"keyword": keyword_info},
            {"keyword": _compact_json(keyword_info)},
            {"keyword": query_text},
        ]
        for params in payload_variants:
            try:
                payload = _webskill_request(
                    session_cookies,
                    "/api/showSearch",
                    params=params,
                    page_path=f"/search/{query_text}",
                    timeout=10,
                )
                track_id = _pick_track_from_webskill(payload, titulo, artista)
                if track_id:
                    return track_id
                attempts.append(f"{query_text}: vazio")
                break
            except Exception as exc:
                attempts.append(f"{query_text}: {str(exc)[:120]}")
                continue
    if attempts:
        print("[Amazon Music DEBUG] WebSkill search attempts: " + " | ".join(attempts[:4]), flush=True)
    return None


def _graphql_add_track_chunk(session_cookies: dict, playlist_id: str, track_ids: list[str]) -> None:
    mutation = """
    mutation addToPlaylistAppendTracks($playlistId: String!, $trackIds: [String!]!) {
      appendTracks(playlistId: $playlistId, trackIds: $trackIds, rejectDuplicateTracks: false) {
        id
        uri
      }
    }
    """
    fallback_mutation = """
    mutation appendTracks($playlistId: String!, $trackIds: [String]) {
      appendTracks(playlistId: $playlistId, trackIds: $trackIds) {
        id
      }
    }
    """
    for start in range(0, len(track_ids), 100):
        chunk = track_ids[start : start + 100]
        try:
            _graphql(
                session_cookies,
                "addToPlaylistAppendTracks",
                mutation,
                {"playlistId": playlist_id, "trackIds": chunk},
            )
        except Exception:
            _graphql(
                session_cookies,
                "appendTracks",
                fallback_mutation,
                {"playlistId": playlist_id, "trackIds": chunk},
            )


def _graphql_add_tracks(session_cookies: dict, playlist_id: str, track_ids: list[str]) -> None:
    failures: list[str] = []
    for start in range(0, len(track_ids), 50):
        chunk = track_ids[start : start + 50]
        try:
            _graphql_add_track_chunk(session_cookies, playlist_id, chunk)
            continue
        except Exception as exc:
            if len(chunk) == 1:
                failures.append(f"{chunk[0]}: {str(exc)[:160]}")
                continue

        for track_id in chunk:
            try:
                _graphql_add_track_chunk(session_cookies, playlist_id, [track_id])
            except Exception as exc:
                failures.append(f"{track_id}: {str(exc)[:160]}")

    if failures and len(failures) >= len(track_ids):
        raise ValueError("Amazon Music recusou todas as tentativas de adicionar faixas.")
    if failures:
        print("[Amazon Music DEBUG] partial add failures: " + " | ".join(failures[:8]), flush=True)


def _read_playlist_track_node(node: dict[str, Any]) -> dict[str, str] | None:
    title = str(node.get("title") or node.get("name") or "").strip()
    if not title:
        return None

    album = node.get("album") if isinstance(node.get("album"), dict) else {}
    return {
        "titulo": title,
        "artista": _artist_names(node).strip(),
        "album": str(album.get("title") or album.get("name") or "").strip(),
    }


def _graphql_read_playlist(session_cookies: dict, playlist_id: str) -> tuple[str, list[dict[str, str]]]:
    query = """
    query playlistDetail($id: String!, $cursor: String, $limit: Float) {
      playlist(id: $id) {
        id
        title
        trackCount
        tracks(limit: $limit, cursor: $cursor) {
          edges {
            cursor
            node {
              id
              title
              url
              contributingArtists {
                edges {
                  node {
                    id
                    name
                  }
                }
              }
              album {
                id
                title
              }
            }
          }
          pageInfo {
            hasNextPage
            token
          }
        }
      }
    }
    """
    tracks: list[dict[str, str]] = []
    playlist_name = "Amazon Music Playlist"
    cursor: str | None = None

    while True:
        payload = _graphql(
            session_cookies,
            "playlistDetail",
            query,
            {"id": playlist_id, "cursor": cursor, "limit": 100},
            timeout=20,
        )
        playlist = ((payload.get("data") or {}).get("playlist") or {})
        if not isinstance(playlist, dict) or not playlist:
            raise ValueError("Playlist do Amazon Music nao encontrada.")

        playlist_name = str(playlist.get("title") or playlist_name)
        track_data = playlist.get("tracks") if isinstance(playlist.get("tracks"), dict) else {}
        for edge in track_data.get("edges") or []:
            node = edge.get("node") if isinstance(edge, dict) else None
            normalized = _read_playlist_track_node(node or {})
            if normalized:
                tracks.append(normalized)

        page_info = track_data.get("pageInfo") if isinstance(track_data.get("pageInfo"), dict) else {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("token")
        if not cursor:
            break

    if not tracks:
        raise ValueError(
            "Nao foi possivel ler as faixas da playlist. "
            "Verifique se a playlist e publica ou se a conta esta conectada."
        )
    return playlist_name, tracks


def validate(session_cookies: dict) -> dict[str, str]:
    _refresh_metadata(session_cookies)
    display_name = "Amazon Music"
    for path in _v1_paths(session_cookies, ["/user/settings", "/me", "/account", "/profile"]):
        try:
            data, _path = _try_requests("GET", [path], session_cookies, timeout=12)
        except ValueError as exc:
            if "expirada" in str(exc).lower():
                raise
            continue
        except Exception:
            continue
        source = data.get("data") if isinstance(data.get("data"), dict) else data
        display_name = (
            source.get("customerName")
            or source.get("displayName")
            or source.get("name")
            or display_name
        )
        if display_name != "Amazon Music":
            break

    if display_name == "Amazon Music":
        customer_id = session_cookies.get("_customer_id", "")
        ubid = session_cookies.get("ubid-main", "")
        if customer_id:
            display_name = f"Amazon Music ({customer_id[:8]}...)"
        elif ubid:
            display_name = f"Amazon Music ({ubid[:8]}...)"
    return {"display_name": display_name, "region": _get_region(session_cookies)}


def read_playlist(url: str, session_cookies: dict) -> tuple[str, list[dict[str, str]]]:
    playlist_id = _extract_playlist_id(url)
    try:
        return _graphql_read_playlist(session_cookies, playlist_id)
    except Exception as exc:
        print(f"[Amazon Music DEBUG] GraphQL read playlist failed, trying web API: {exc}", flush=True)

    tracks: list[dict[str, str]] = []
    playlist_name = "Amazon Music Playlist"
    next_token = None

    while True:
        params = _common_params(session_cookies, limit=100)
        if next_token:
            params["nextToken"] = next_token
        try:
            data, _path = _try_requests(
                "GET",
                _v1_paths(
                    session_cookies,
                    [
                        f"/playlists/{playlist_id}/tracks",
                        f"/user/playlists/{playlist_id}/tracks",
                        f"/library/playlists/{playlist_id}/tracks",
                    ],
                ),
                session_cookies,
                params=params,
            )
        except Exception as exc:
            raise ValueError("Nao foi possivel ler essa playlist do Amazon Music com a sessao atual.") from exc

        playlist = (data.get("playlist") or data.get("data") or {})
        if isinstance(playlist, dict) and "playlist" in playlist:
            playlist = playlist["playlist"]
        if isinstance(playlist, dict):
            playlist_name = playlist.get("title") or playlist.get("name") or playlist_name
            items = playlist.get("tracks") or playlist.get("items") or data.get("items") or []
        else:
            items = data.get("items") or []

        edges = (items.get("edges") or items.get("items") or []) if isinstance(items, dict) else items
        for edge in edges:
            node = edge.get("node") or edge if isinstance(edge, dict) else {}
            normalized = _read_track_node(node)
            if normalized:
                tracks.append(normalized)

        next_token = (
            data.get("nextToken")
            or ((playlist.get("tracks") or {}).get("nextToken") if isinstance(playlist, dict) and isinstance(playlist.get("tracks"), dict) else None)
        )
        if not next_token:
            break

    if not tracks:
        raise ValueError(
            "Nao foi possivel ler as faixas da playlist. "
            "Verifique se a playlist e publica ou se a conta esta conectada."
        )
    return playlist_name, tracks


def search_track(session_cookies: dict, titulo: str, artista: str = "") -> str | None:
    try:
        track_id = _graphql_search_track(session_cookies, titulo, artista)
        if track_id:
            return track_id
    except Exception as exc:
        print(f"[Amazon Music DEBUG] GraphQL search failed: {exc}", flush=True)

    try:
        track_id = _webskill_search_track(session_cookies, titulo, artista)
        if track_id:
            return track_id
    except Exception as exc:
        print(f"[Amazon Music DEBUG] WebSkill search failed: {exc}", flush=True)

    query = f"{titulo} {artista}".strip()
    paths = _v1_paths(session_cookies, ["/search", "/catalog/search", "/music/search"])
    param_sets = [
        {**_common_params(session_cookies, 5), "keywords": query, "includeTypes": "track"},
        {**_common_params(session_cookies, 5), "q": query, "type": "track"},
        {**_common_params(session_cookies, 5), "query": query, "entityType": "track"},
    ]
    for params in param_sets:
        try:
            data, _path = _try_requests("GET", paths, session_cookies, params=params, timeout=6)
            track_id = _pick_track_id(data)
            if track_id:
                return track_id
        except Exception:
            continue
    return None


def create_playlist(session_cookies: dict, nome: str, descricao: str = "") -> dict[str, str]:
    description = descricao or "Transferida via PlayTransfer"
    try:
        return _graphql_create_playlist(session_cookies, nome, description)
    except Exception as exc:
        print(f"[Amazon Music DEBUG] GraphQL create failed, trying WebSkill: {exc}")

    try:
        return _webskill_create_playlist(session_cookies, nome)
    except Exception as exc:
        print(f"[Amazon Music DEBUG] WebSkill create failed: {exc}")

    paths = _v1_paths(session_cookies, ["/playlists", "/user/playlists", "/library/playlists", "/me/playlists"])
    payloads = [
        {"title": nome, "description": description, "visibility": "PRIVATE", "public": False},
        {"name": nome, "description": description, "visibility": "PRIVATE", "public": False},
        {"playlist": {"title": nome, "description": description, "visibility": "PRIVATE", "public": False}},
    ]

    attempts: list[str] = []
    for path in paths:
        for payload in payloads:
            response = requests.post(
                f"{_base(session_cookies)}{path}",
                headers=_headers(session_cookies),
                cookies=_clean_cookies(session_cookies),
                json=payload,
                timeout=20,
                allow_redirects=False,
            )
            if response.status_code in (200, 201, 202):
                playlist = _pick_playlist(_json_or_empty(response), nome)
                if not playlist:
                    raise ValueError("Amazon Music aceitou a criacao, mas nao devolveu o ID da playlist.")
                playlist_url = playlist.get("url") or f"{_base(session_cookies)}/my/playlists/{playlist['id']}"
                return {"id": playlist["id"], "url": playlist_url}
            if response.status_code in (401, 403):
                raise ValueError("Sessao do Amazon Music expirada. Reconecte o Amazon Music.")

            detail = _detail(response)
            attempts.append(f"{path} -> HTTP {response.status_code}{f' ({detail})' if detail else ''}")
            if response.status_code in (404, 405):
                break
            if response.status_code not in (400, 409, 415, 422):
                break

    if attempts:
        print("[Amazon Music DEBUG] create playlist attempts: " + " | ".join(attempts[:12]))
    raise ValueError(
        "Nao consegui criar a playlist no Amazon Music com esta sessao. "
        "Reconecte o Amazon Music e tente novamente."
    )


def add_tracks(session_cookies: dict, playlist_id: str, track_ids: list[str]) -> None:
    if not track_ids:
        return

    try:
        _graphql_add_tracks(session_cookies, playlist_id, track_ids)
        return
    except Exception as exc:
        print(f"[Amazon Music DEBUG] GraphQL add failed, trying legacy paths: {exc}")

    paths = _v1_paths(
        session_cookies,
        [
            f"/playlists/{playlist_id}/tracks",
            f"/playlists/{playlist_id}/items",
            f"/user/playlists/{playlist_id}/tracks",
            f"/library/playlists/{playlist_id}/tracks",
        ],
    )
    for start in range(0, len(track_ids), 100):
        chunk = track_ids[start : start + 100]
        payloads = [
            {"trackIds": chunk, "addDuplicateTracks": False},
            {"trackIds": chunk},
            {"ids": chunk},
            {"tracks": [{"id": track_id} for track_id in chunk]},
        ]
        done = False
        attempts: list[str] = []
        for path in paths:
            for payload in payloads:
                stop_path = False
                for method in ("PUT", "POST"):
                    response = requests.request(
                        method,
                        f"{_base(session_cookies)}{path}",
                        headers=_headers(session_cookies),
                        cookies=_clean_cookies(session_cookies),
                        json=payload,
                        timeout=20,
                        allow_redirects=False,
                    )
                    if response.status_code in (200, 201, 202, 204):
                        done = True
                        break
                    if response.status_code in (401, 403):
                        raise ValueError("Sessao do Amazon Music expirada ao adicionar musicas.")
                    attempts.append(f"{method} {path} -> HTTP {response.status_code}")
                    if response.status_code in (404, 405):
                        stop_path = True
                        break
                if done or stop_path:
                    break
            if done:
                break

        if not done:
            if attempts:
                print("[Amazon Music DEBUG] add tracks attempts: " + " | ".join(attempts[:12]))
            raise ValueError(
                "Criei a playlist no Amazon Music, mas nao consegui adicionar as musicas com esta sessao. "
                "Reconecte o Amazon Music e tente novamente."
            )
