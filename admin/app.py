"""
Веб-админка для telegram_kruzhok_bot.

Смонтирована за reverse-proxy под префиксом /admin (Caddy маршрутизирует
/admin* сюда, а корень — на публичный конвертер). Все маршруты, кука и ссылки
используют этот префикс.

Авторизация — cookie-сессия (страница /admin/login вместо браузерного Basic
Auth попапа). Кука подписана HMAC (stdlib, без доп. зависимостей).
"""
import os
import hmac
import time
import base64
import hashlib
import secrets
import sqlite3

from fastapi import FastAPI, Depends, HTTPException, status, Query, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from templates import LOGIN_HTML, DASHBOARD_HTML

BASE = "/admin"  # префикс монтирования (Caddy отдаёт /admin* этому сервису)

DB_PATH = os.getenv("STATS_DB", "/data/stats.db")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32)).encode()
SESSION_TTL = 7 * 24 * 3600
COOKIE_NAME = "kruzhok_session"

app = FastAPI(title="Kruzhok Bot Admin", docs_url=None, redoc_url=None, openapi_url=None)


# ─── СЕССИЯ (HMAC-подписанная кука) ───────────────────────────────────────────
def _sign(payload: str) -> str:
    sig = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def make_session() -> str:
    exp = str(int(time.time()) + SESSION_TTL)
    token = base64.urlsafe_b64encode(f"{ADMIN_USER}|{exp}".encode()).decode()
    return _sign(token)


def valid_session(cookie: str | None) -> bool:
    if not cookie or "." not in cookie:
        return False
    payload, _, sig = cookie.rpartition(".")
    expected = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        user, exp = base64.urlsafe_b64decode(payload).decode().split("|")
    except Exception:
        return False
    return user == ADMIN_USER and int(exp) > time.time()


def require_auth(request: Request) -> None:
    if not valid_session(request.cookies.get(COOKIE_NAME)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth required")


# ─── DB ───────────────────────────────────────────────────────────────────────
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=3000;")
    conn.execute("PRAGMA query_only=ON;")
    return conn


def q(sql: str, params: tuple = ()) -> list[dict]:
    conn = None
    try:
        conn = db()
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        if conn is not None:
            conn.close()


# ─── AUTH ROUTES ──────────────────────────────────────────────────────────────
@app.get(f"{BASE}/login", response_class=HTMLResponse)
def login_page(request: Request, error: int = 0) -> HTMLResponse:
    if valid_session(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse(BASE, status_code=302)
    html = LOGIN_HTML.replace(
        "<!--ERROR-->",
        '<div class="error">Неверный логин или пароль</div>' if error else "",
    )
    return HTMLResponse(html)


@app.post(f"{BASE}/login")
def login_submit(username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    ok = (secrets.compare_digest(username, ADMIN_USER)
          and secrets.compare_digest(password, ADMIN_PASS))
    if not ok:
        time.sleep(0.5)
        return RedirectResponse(f"{BASE}/login?error=1", status_code=302)
    resp = RedirectResponse(BASE, status_code=302)
    resp.set_cookie(
        COOKIE_NAME, make_session(),
        max_age=SESSION_TTL, httponly=True, samesite="lax", secure=True, path=BASE,
    )
    return resp


@app.get(f"{BASE}/logout")
def logout() -> RedirectResponse:
    resp = RedirectResponse(f"{BASE}/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME, path=BASE)
    return resp


# ─── API ──────────────────────────────────────────────────────────────────────
@app.get(f"{BASE}/api/summary")
def api_summary(_: None = Depends(require_auth)) -> JSONResponse:
    now = time.time()
    d1, d7 = now - 86400, now - 7 * 86400

    def one(rows, key="c"):
        return rows[0][key] if rows else 0

    return JSONResponse({
        "total_users": one(q("SELECT COUNT(*) c FROM users")),
        "total_jobs": one(q("SELECT COUNT(*) c FROM jobs")),
        "ok_jobs": one(q("SELECT COUNT(*) c FROM jobs WHERE status='ok'")),
        "failed_jobs": one(q("SELECT COUNT(*) c FROM jobs WHERE status<>'ok'")),
        "bytes_in": one(q("SELECT COALESCE(SUM(in_size_bytes),0) s FROM jobs"), "s"),
        "active_24h": one(q("SELECT COUNT(DISTINCT user_id) c FROM jobs WHERE ts>=?", (d1,))),
        "active_7d": one(q("SELECT COUNT(DISTINCT user_id) c FROM jobs WHERE ts>=?", (d7,))),
        "jobs_24h": one(q("SELECT COUNT(*) c FROM jobs WHERE ts>=?", (d1,))),
        "starts": one(q("SELECT COUNT(*) c FROM events WHERE type='start'")),
        "sub_required": one(q("SELECT COUNT(*) c FROM events WHERE type='sub_required'")),
        "sub_confirmed": one(q("SELECT COUNT(*) c FROM events WHERE type='sub_confirmed'")),
    })


@app.get(f"{BASE}/api/users")
def api_users(_: None = Depends(require_auth),
              sort: str = Query("total_jobs"),
              limit: int = Query(500, le=2000)) -> JSONResponse:
    allowed = {"total_jobs", "total_ok", "total_failed", "last_seen", "first_seen"}
    if sort not in allowed:
        sort = "total_jobs"
    rows = q(
        f"""SELECT user_id, username, first_name, last_name,
                   first_seen, last_seen, total_jobs, total_ok, total_failed
            FROM users ORDER BY {sort} DESC LIMIT ?""",
        (limit,),
    )
    return JSONResponse(rows)


@app.get(f"{BASE}/api/jobs")
def api_jobs(_: None = Depends(require_auth),
             limit: int = Query(200, le=1000),
             user_id: int | None = None) -> JSONResponse:
    if user_id is not None:
        rows = q(
            """SELECT j.*, u.username, u.first_name FROM jobs j
               LEFT JOIN users u ON u.user_id=j.user_id
               WHERE j.user_id=? ORDER BY j.ts DESC LIMIT ?""",
            (user_id, limit),
        )
    else:
        rows = q(
            """SELECT j.*, u.username, u.first_name FROM jobs j
               LEFT JOIN users u ON u.user_id=j.user_id
               ORDER BY j.ts DESC LIMIT ?""",
            (limit,),
        )
    return JSONResponse(rows)


@app.get(f"{BASE}/api/timeseries")
def api_timeseries(_: None = Depends(require_auth), days: int = Query(30, le=365)) -> JSONResponse:
    since = time.time() - days * 86400
    rows = q(
        """SELECT date(ts,'unixepoch') d,
                  COUNT(*) jobs,
                  SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) ok,
                  COUNT(DISTINCT user_id) users
           FROM jobs WHERE ts>=? GROUP BY d ORDER BY d""",
        (since,),
    )
    return JSONResponse(rows)


@app.get(f"{BASE}/api/errors")
def api_errors(_: None = Depends(require_auth)) -> JSONResponse:
    rows = q(
        """SELECT COALESCE(error_code, status) code, COUNT(*) c
           FROM jobs WHERE status<>'ok'
           GROUP BY code ORDER BY c DESC""",
    )
    return JSONResponse(rows)


@app.get(f"{BASE}/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


# ─── DASHBOARD ────────────────────────────────────────────────────────────────
@app.get(BASE, response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    if not valid_session(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse(f"{BASE}/login", status_code=302)
    return HTMLResponse(DASHBOARD_HTML)
