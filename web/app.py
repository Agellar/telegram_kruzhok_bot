"""
Публичный веб-конвертер: видео → видеокружок (mp4 512×512, ≤60с, ≤12 МБ).

Без Telegram и без авторизации. Загрузил файл → сервер конвертирует через
ffmpeg → отдаёт готовый mp4 на скачивание. Защита от злоупотребления:
лимит размера, rate-limit по IP, ограничение параллельных конвертаций.
"""
import os
import time
import uuid
import hashlib
import asyncio
import logging
import sqlite3
from pathlib import Path
from contextlib import suppress

from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse, Response, JSONResponse

from convert import convert_to_video_note
from templates import CONVERTER_HTML

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web")

TEMP_DIR = Path(os.getenv("WEB_TEMP_DIR", "/tmp/webconv"))
MAX_FILE_MB = int(os.getenv("WEB_MAX_FILE_MB", "50"))
MAX_PARALLEL = int(os.getenv("WEB_MAX_PARALLEL", "2"))
RATE_SECONDS = int(os.getenv("WEB_RATE_SECONDS", "15"))   # 1 конвертация / N сек на IP
MAX_QUEUE = MAX_PARALLEL + 4                              # сверх этого — 503

STATS_DB = os.getenv("STATS_DB", "/data/stats.db")        # общая БД с ботом/админкой
IP_SALT = os.getenv("IP_SALT", "kruzhok-web-salt")        # соль для хеша IP

TEMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Kruzhok Web Converter", docs_url=None, redoc_url=None, openapi_url=None)
_sem = asyncio.Semaphore(MAX_PARALLEL)
_inflight = 0
_last_ip: dict[str, float] = {}


# ─── СТАТИСТИКА ВЕБ-КОНВЕРТЕРА (таблица web_jobs в общей stats.db) ─────────────
def init_web_stats() -> None:
    try:
        Path(STATS_DB).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(STATS_DB, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS web_jobs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts              REAL NOT NULL,
                    status          TEXT NOT NULL,  -- ok | convert_fail | too_big | error
                    in_size_bytes   INTEGER,
                    out_size_bytes  INTEGER,
                    in_duration_sec REAL,
                    processing_ms   INTEGER,
                    lang            TEXT,
                    ip_hash         TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_web_ts ON web_jobs(ts);
            """)
        logger.info("web_jobs table ready in %s", STATS_DB)
    except Exception as exc:
        logger.warning("init_web_stats failed: %s", exc)


def log_web_job(status: str, in_size: int | None, out_size: int | None,
                duration: float | None, processing_ms: int | None,
                lang: str | None, ip_hash: str | None) -> None:
    try:
        with sqlite3.connect(STATS_DB, timeout=10) as conn:
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute(
                """INSERT INTO web_jobs (ts, status, in_size_bytes, out_size_bytes,
                       in_duration_sec, processing_ms, lang, ip_hash)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (time.time(), status, in_size, out_size, duration,
                 processing_ms, lang, ip_hash),
            )
    except Exception as exc:
        logger.warning("log_web_job failed: %s", exc)


def ip_hash(ip: str) -> str:
    return hashlib.sha256((IP_SALT + ip).encode()).hexdigest()[:16]


@app.on_event("startup")
def _startup() -> None:
    init_web_stats()


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune_rate(now: float) -> None:
    if len(_last_ip) > 5000:
        for ip in [k for k, v in _last_ip.items() if now - v > 3600]:
            _last_ip.pop(ip, None)


def cleanup(*paths: Path) -> None:
    for p in paths:
        with suppress(Exception):
            if p.exists():
                p.unlink()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(CONVERTER_HTML.replace("{{MAX_MB}}", str(MAX_FILE_MB)))


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.post("/api/convert")
async def convert(request: Request, file: UploadFile = File(...),
                  lang: str | None = None) -> Response:
    global _inflight

    # ── rate-limit по IP ──
    ip = client_ip(request)
    now = time.time()
    _prune_rate(now)
    last = _last_ip.get(ip, 0)
    if now - last < RATE_SECONDS:
        wait = int(RATE_SECONDS - (now - last)) + 1
        raise HTTPException(status_code=429,
                            detail=f"Слишком часто. Подождите {wait} сек.")

    # ── валидация типа ──
    mime = (file.content_type or "").lower()
    if not mime.startswith("video/"):
        raise HTTPException(status_code=415, detail="Принимаются только видеофайлы.")

    # ── защита от перегрузки очереди ──
    if _inflight >= MAX_QUEUE:
        raise HTTPException(status_code=503,
                            detail="Сервер занят, попробуйте через минуту.")

    job = uuid.uuid4().hex[:10]
    src = TEMP_DIR / f"{job}_in"
    dst = TEMP_DIR / f"{job}_out.mp4"
    limit = MAX_FILE_MB * 1024 * 1024
    lang = (lang or "")[:5] or None

    # ── трекинг итога: пишем в web_jobs по факту (в finally) ──
    t0 = time.monotonic()
    j_status = "error"
    j_in = j_out = None

    _inflight += 1
    try:
        # ── приём файла потоково с контролем размера ──
        size = 0
        with open(src, "wb") as f:
            while chunk := await file.read(1 << 20):  # по 1 МБ
                size += len(chunk)
                if size > limit:
                    j_status, j_in = "too_big", size
                    cleanup(src)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Файл слишком большой. Максимум — {MAX_FILE_MB} МБ.")
                f.write(chunk)
        j_in = size
        if size == 0:
            j_status = "empty"
            cleanup(src)
            raise HTTPException(status_code=400, detail="Пустой файл.")

        # IP фиксируем только после успешного приёма (не штрафуем за отказ по размеру)
        _last_ip[ip] = time.time()

        async with _sem:
            ok = await convert_to_video_note(src, dst)
        if not ok:
            j_status = "convert_fail"
            raise HTTPException(
                status_code=422,
                detail="Не удалось сконвертировать. Попробуйте другой файл или клип покороче.")

        data = dst.read_bytes()
        j_status, j_out = "ok", len(data)
        logger.info("web convert ok ip=%s job=%s in=%dB out=%dB", ip, job, size, len(data))
        return Response(
            content=data,
            media_type="video/mp4",
            headers={"Content-Disposition": 'attachment; filename="kruzhok.mp4"'},
        )
    finally:
        _inflight -= 1
        cleanup(src, dst)
        # не логируем «пустой» шум — только реальные попытки с непустым файлом
        if j_status != "empty":
            log_web_job(j_status, j_in, j_out, None,
                        int((time.monotonic() - t0) * 1000), lang, ip_hash(ip))
