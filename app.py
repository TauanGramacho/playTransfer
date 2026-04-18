"""
app.py — PlayTransfer
Servidor Flask principal — OAuth + API REST + worker threads
"""
import os, time, threading, traceback, secrets, urllib.parse
import requests as req_lib
from flask import Flask, render_template, request, jsonify, redirect, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "playtransfer_dev_secret_" + secrets.token_hex(8))
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def no_cache(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

# ── Estado em memória ─────────────────────────────────────────────────────────
jobs: dict[str, dict] = {}
sessions: dict[str, dict] = {}
oauth_states: dict[str, dict] = {}   # state → {role, platform}

BASE_URL = os.getenv("BASE_URL", "http://localhost:5001")

# ── Plataformas ───────────────────────────────────────────────────────────────
PLATFORMS = {
    "spotify":    {"name": "Spotify",       "color": "#1DB954", "can_read": True,  "can_write": False, "auth": "oauth"},
    "deezer":     {"name": "Deezer",        "color": "#FF0092", "can_read": True,  "can_write": True,  "auth": "oauth"},
    "youtube":    {"name": "YouTube Music", "color": "#FF0000", "can_read": True,  "can_write": True,  "auth": "cookie"},
    "soundcloud": {"name": "SoundCloud",    "color": "#FF5500", "can_read": True,  "can_write": False, "auth": "none"},
    "apple":      {"name": "Apple Music",   "color": "#FC3C44", "can_read": True,  "can_write": True,  "auth": "none"},
    "tidal":      {"name": "TIDAL",         "color": "#00CCFF", "can_read": True,  "can_write": True,  "auth": "none"},
    "amazon":     {"name": "Amazon Music",  "color": "#00A8E0", "can_read": True,  "can_write": True,  "auth": "none"},
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def new_job() -> tuple[str, dict]:
    job_id = os.urandom(8).hex()
    job = {"events": [], "lock": threading.Lock(), "done": False}
    jobs[job_id] = job
    return job_id, job

def emit(job: dict, event: dict):
    with job["lock"]:
        job["events"].append(event)

# ═════════════════════════════════════════════════════════════════════════════
# PÁGINAS
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/oauth-callback")
def oauth_callback_page():
    """Página de callback OAuth — fecha popup e notifica janela principal."""
    return render_template("oauth_callback.html")

# ═════════════════════════════════════════════════════════════════════════════
# SPOTIFY OAUTH
# Registre o app em: https://developer.spotify.com/dashboard
# Redirect URI: http://localhost:5001/auth/spotify/callback
# ═════════════════════════════════════════════════════════════════════════════
SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_SCOPES        = "playlist-read-private playlist-read-collaborative"

@app.route("/auth/spotify")
def auth_spotify():
    role = request.args.get("role", "src")
    state = secrets.token_urlsafe(16)
    oauth_states[state] = {"role": role, "platform": "spotify"}

    params = {
        "client_id":     SPOTIFY_CLIENT_ID or "demo",
        "response_type": "code",
        "redirect_uri":  f"{BASE_URL}/auth/spotify/callback",
        "scope":         SPOTIFY_SCOPES,
        "state":         state,
        "show_dialog":   "false",
    }
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
    return redirect(url)

@app.route("/auth/spotify/callback")
def auth_spotify_callback():
    code  = request.args.get("code", "")
    state = request.args.get("state", "")
    error = request.args.get("error", "")

    if error or not code:
        return redirect(f"/oauth-callback?error={error or 'cancelled'}")

    meta = oauth_states.pop(state, {})
    role = meta.get("role", "src")

    # Troca code por access_token
    import base64
    credentials = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()

    r = req_lib.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {credentials}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code",
              "code": code,
              "redirect_uri": f"{BASE_URL}/auth/spotify/callback"},
        timeout=10,
    )

    if r.status_code != 200:
        return redirect(f"/oauth-callback?error=token_exchange_failed")

    token_data = r.json()
    access_token = token_data.get("access_token", "")

    # Busca info do usuário
    me = req_lib.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    ).json()

    display_name = me.get("display_name", me.get("id", "Usuário Spotify"))
    avatar = (me.get("images") or [{}])[0].get("url", "")

    sid = os.urandom(8).hex()
    sessions[sid] = {
        "platform": "spotify",
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token", ""),
        "display_name": display_name,
        "avatar": avatar,
    }

    return redirect(f"/oauth-callback?sid={sid}&role={role}&display_name={urllib.parse.quote(display_name)}&platform=spotify")


# ═════════════════════════════════════════════════════════════════════════════
# DEEZER OAUTH
# Registre em: https://developers.deezer.com/myapps
# Redirect URI: http://localhost:5001/auth/deezer/callback
# ═════════════════════════════════════════════════════════════════════════════
DEEZER_APP_ID     = os.getenv("DEEZER_APP_ID", "")
DEEZER_SECRET_KEY = os.getenv("DEEZER_SECRET_KEY", "")

@app.route("/auth/deezer")
def auth_deezer():
    role = request.args.get("role", "src")
    state = secrets.token_urlsafe(16)
    oauth_states[state] = {"role": role, "platform": "deezer"}

    params = {
        "app_id":  DEEZER_APP_ID or "demo",
        "redirect_uri": f"{BASE_URL}/auth/deezer/callback",
        "perms":   "basic_access,manage_library",
        "state":   state,
    }
    url = "https://connect.deezer.com/oauth/auth.php?" + urllib.parse.urlencode(params)
    return redirect(url)

@app.route("/auth/deezer/callback")
def auth_deezer_callback():
    code  = request.args.get("code", "")
    state = request.args.get("state", "")
    error = request.args.get("error_reason", "")

    if error or not code:
        return redirect(f"/oauth-callback?error={error or 'cancelled'}")

    meta = oauth_states.pop(state, {})
    role = meta.get("role", "src")

    r = req_lib.get(
        "https://connect.deezer.com/oauth/access_token.php",
        params={"app_id": DEEZER_APP_ID, "secret": DEEZER_SECRET_KEY,
                "code": code, "output": "json"},
        timeout=10,
    )

    token_data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    access_token = token_data.get("access_token", "")

    if not access_token:
        # Deezer retorna texto simples com o token
        text = r.text
        if "access_token=" in text:
            access_token = text.split("access_token=")[1].split("&")[0]

    if not access_token:
        return redirect("/oauth-callback?error=token_failed")

    me = req_lib.get(
        "https://api.deezer.com/user/me",
        params={"access_token": access_token},
        timeout=10,
    ).json()

    display_name = me.get("name", "Usuário Deezer")
    avatar = me.get("picture_small", "")

    # Cria sessão ARL via token (precisamos do ARL para o GW)
    # Por ora usa sessão simplificada com o access_token para leitura
    sid = os.urandom(8).hex()
    sessions[sid] = {
        "platform": "deezer",
        "access_token": access_token,
        "deezer_user_id": me.get("id", ""),
        "display_name": display_name,
        "avatar": avatar,
        # dz_session e dz_api_token preenchidos depois via ARL manual se necessário
        "dz_session": None,
        "dz_api_token": None,
    }
    # Tenta criar sessão completa via token para poder criar playlists
    try:
        from services import deezer as dz_service
        dz_info = dz_service.session_from_oauth_token(access_token)
        sessions[sid]["dz_session"]   = dz_info["session"]
        sessions[sid]["dz_api_token"] = dz_info["api_token"]
    except Exception:
        pass

    return redirect(f"/oauth-callback?sid={sid}&role={role}&display_name={urllib.parse.quote(display_name)}&platform=deezer")


# ═════════════════════════════════════════════════════════════════════════════
# YOUTUBE MUSIC — cookie simplificado
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/api/connect/youtube", methods=["POST"])
def connect_youtube():
    from services import youtube_music
    data = request.json or {}
    headers_raw = data.get("headers_raw", "").strip()
    try:
        info = youtube_music.validate(headers_raw)
        sid = os.urandom(8).hex()
        sessions[sid] = {
            "platform": "youtube",
            "headers_path": info["headers_path"],
            "display_name": info["display_name"],
        }
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ═════════════════════════════════════════════════════════════════════════════
# SOUNDCLOUD — sem auth
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/api/connect/soundcloud", methods=["POST"])
def connect_soundcloud():
    from services import soundcloud
    try:
        info = soundcloud.validate()
        sid = os.urandom(8).hex()
        sessions[sid] = {"platform": "soundcloud", "display_name": info["display_name"]}
        return jsonify({"ok": True, "sid": sid, "display_name": info["display_name"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ═════════════════════════════════════════════════════════════════════════════
# PREVIEW & TRANSFER
# ═════════════════════════════════════════════════════════════════════════════
@app.route("/api/platforms")
def api_platforms():
    # Indica se OAuth está configurado
    p = dict(PLATFORMS)
    p["spotify"]["oauth_configured"] = bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)
    p["deezer"]["oauth_configured"]  = bool(DEEZER_APP_ID and DEEZER_SECRET_KEY)
    return jsonify(p)

@app.route("/api/preview", methods=["POST"])
def api_preview():
    data = request.json or {}
    platform = data.get("platform", "")
    url = data.get("url", "").strip()
    sid = data.get("sid", "")
    try:
        nome, tracks = _read_playlist(platform, url, sid)
        return jsonify({"ok": True, "nome": nome, "total": len(tracks), "tracks": tracks[:20]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

def _read_playlist(platform: str, url: str, sid: str) -> tuple[str, list[dict]]:
    sess = sessions.get(sid, {})

    if platform == "spotify":
        from services import spotify
        token = sess.get("access_token") or sess.get("sp_dc", "")
        return spotify.read_playlist(url, access_token=token if len(token) > 50 else None,
                                     sp_dc=token if len(token) <= 50 else None)

    elif platform == "deezer":
        from services import deezer
        return deezer.read_playlist(url)

    elif platform == "youtube":
        from services import youtube_music
        return youtube_music.read_playlist(url)

    elif platform == "soundcloud":
        from services import soundcloud
        return soundcloud.read_playlist(url)

    else:
        raise ValueError(f"Plataforma '{platform}' ainda não suportada como origem.")

@app.route("/api/transfer", methods=["POST"])
def api_transfer():
    data = request.json or {}
    job_id, job = new_job()
    threading.Thread(target=run_transfer, args=(job, data), daemon=True).start()
    return jsonify({"job_id": job_id})

def run_transfer(job: dict, data: dict):
    src_platform  = data.get("src_platform", "")
    src_url       = data.get("src_url", "")
    src_sid       = data.get("src_sid", "")
    dest_platform = data.get("dest_platform", "")
    dest_sid      = data.get("dest_sid", "")

    try:
        emit(job, {"type": "status", "msg": f"Lendo playlist..."})
        nome, musicas = _read_playlist(src_platform, src_url, src_sid)
        emit(job, {"type": "playlist_read", "nome": nome, "total": len(musicas)})

        ids_encontrados, falhas = [], []

        if dest_platform == "deezer":
            from services import deezer
            dest_sess    = sessions.get(dest_sid, {})
            dz_session   = dest_sess.get("dz_session")
            dz_api_token = dest_sess.get("dz_api_token")
            if not dz_session:
                raise ValueError("Sessão do Deezer não encontrada. Reconecte o Deezer.")

            playlist_id = deezer.create_playlist(dz_session, dz_api_token, nome,
                f"Transferida via PlayTransfer")
            emit(job, {"type": "status", "msg": "Buscando músicas no Deezer..."})

            for i, m in enumerate(musicas):
                tid = deezer.search_track(dz_session, m["titulo"], m["artista"])
                if tid: ids_encontrados.append(tid)
                else:   falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(tid), "current": i + 1, "total": len(musicas)})
                time.sleep(0.10)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                deezer.add_tracks(dz_session, dz_api_token, playlist_id, ids_encontrados)

            dest_url = f"https://www.deezer.com/br/playlist/{playlist_id}"

        elif dest_platform == "youtube":
            from services import youtube_music
            dest_sess    = sessions.get(dest_sid, {})
            headers_path = dest_sess.get("headers_path")
            if not headers_path:
                raise ValueError("Sessão do YouTube Music não encontrada. Reconecte.")

            ytm = youtube_music.get_ytm_instance(headers_path)
            playlist_id = youtube_music.create_playlist(ytm, nome, "Transferida via PlayTransfer")
            emit(job, {"type": "status", "msg": "Buscando músicas no YouTube Music..."})

            for i, m in enumerate(musicas):
                vid = youtube_music.search_track(ytm, m["titulo"], m["artista"])
                if vid: ids_encontrados.append(vid)
                else:   falhas.append(m)
                emit(job, {"type": "track", "titulo": m["titulo"], "artista": m["artista"],
                           "found": bool(vid), "current": i + 1, "total": len(musicas)})
                time.sleep(0.15)

            if ids_encontrados:
                emit(job, {"type": "status", "msg": "Adicionando faixas..."})
                youtube_music.add_tracks(ytm, playlist_id, ids_encontrados)

            dest_url = f"https://music.youtube.com/playlist?list={playlist_id}"

        else:
            raise ValueError(f"Destino '{dest_platform}' ainda não suportado.")

        emit(job, {"type": "done", "encontradas": len(ids_encontrados),
                   "nao_encontradas": len(falhas), "total": len(musicas),
                   "playlist_nome": nome, "playlist_url": dest_url, "falhas": falhas[:20]})

    except Exception as e:
        emit(job, {"type": "error", "message": str(e)})
    finally:
        with job["lock"]:
            job["done"] = True

@app.route("/api/job/<job_id>")
def api_job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    from_idx = int(request.args.get("from", 0))
    with job["lock"]:
        events = job["events"][from_idx:]
        done   = job["done"]
    return jsonify({"events": events, "done": done and not events, "total_events": from_idx + len(events)})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "version": "1.1.0", "app": "PlayTransfer"})

if __name__ == "__main__":
    import webbrowser
    port = int(os.getenv("PORT", 5001))
    def _open():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()
    print(f"\nPlayTransfer rodando em http://localhost:{port}\n")
    app.run(debug=False, port=port, threaded=True)
