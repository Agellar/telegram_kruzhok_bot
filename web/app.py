"""
Публичный веб-конвертер: видео → видеокружок (mp4 512×512, ≤60с, ≤12 МБ).

Без Telegram и без авторизации. Загрузил файл → сервер конвертирует через
ffmpeg → отдаёт готовый mp4 на скачивание. Защита от злоупотребления:
лимит размера, rate-limit по IP, ограничение параллельных конвертаций.
"""
import os
import time
import uuid
import asyncio
import logging
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

TEMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Kruzhok Web Converter", docs_url=None, redoc_url=None, openapi_url=None)
_sem = asyncio.Semaphore(MAX_PARALLEL)
_inflight = 0
_last_ip: dict[str, float] = {}


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
async def convert(request: Request, file: UploadFile = File(...)) -> Response:
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

    _inflight += 1
    try:
        # ── приём файла потоково с контролем размера ──
        size = 0
        with open(src, "wb") as f:
            while chunk := await file.read(1 << 20):  # по 1 МБ
                size += len(chunk)
                if size > limit:
                    cleanup(src)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Файл слишком большой. Максимум — {MAX_FILE_MB} МБ.")
                f.write(chunk)
        if size == 0:
            cleanup(src)
            raise HTTPException(status_code=400, detail="Пустой файл.")

        # IP фиксируем только после успешного приёма (не штрафуем за отказ по размеру)
        _last_ip[ip] = time.time()

        async with _sem:
            ok = await convert_to_video_note(src, dst)
        if not ok:
            raise HTTPException(
                status_code=422,
                detail="Не удалось сконвертировать. Попробуйте другой файл или клип покороче.")

        data = dst.read_bytes()
        logger.info("web convert ok ip=%s job=%s in=%dB out=%dB", ip, job, size, len(data))
        return Response(
            content=data,
            media_type="video/mp4",
            headers={"Content-Disposition": 'attachment; filename="kruzhok.mp4"'},
        )
    finally:
        _inflight -= 1
        cleanup(src, dst)
