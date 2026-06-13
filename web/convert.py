"""
Конвертация видео → видеокружок (video note) для публичной веб-версии.

Логика идентична боту (bot.py): кроп по центру до квадрата, ресайз 512×512,
двухпроходное кодирование libx264 с расчётом битрейта под 11.5 МБ, чтобы
итог гарантированно укладывался в лимит Telegram (12 МБ / 60 сек). Вынесено
в отдельный модуль без зависимости от aiogram, чтобы не трогать работающий бот.
"""
import json
import asyncio
import logging
from pathlib import Path
from contextlib import suppress

logger = logging.getLogger("convert")

VIDEO_NOTE_MAX_BYTES = 12 * 1024 * 1024
VIDEO_NOTE_TARGET_MB = 11.5
VIDEO_NOTE_MAX_SEC = 60
VIDEO_NOTE_AUDIO_KBPS = 64
VIDEO_NOTE_SIZE = 512


async def probe_duration(path: Path) -> float | None:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", str(path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        data = json.loads(out.decode(errors="replace"))
        return float(data["format"]["duration"])
    except Exception as exc:
        logger.warning("ffprobe failed for %s: %s", path.name, exc)
        return None


async def convert_to_video_note(src: Path, dst: Path) -> bool:
    """Возвращает True при успехе. Итоговый файл ≤ 12 МБ, иначе False."""
    duration = await probe_duration(src) or VIDEO_NOTE_MAX_SEC
    effective_sec = min(duration, VIDEO_NOTE_MAX_SEC)

    target_bits = VIDEO_NOTE_TARGET_MB * 1024 * 1024 * 8
    video_br = int(target_bits / effective_sec) - VIDEO_NOTE_AUDIO_KBPS * 1000
    if video_br < 100_000:
        video_br = 100_000

    pass_log = str(dst) + "_pass"
    vf = (
        f"crop=min(iw\\,ih):min(iw\\,ih),"
        f"scale={VIDEO_NOTE_SIZE}:{VIDEO_NOTE_SIZE}:flags=lanczos"
    )
    base_args = [
        "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-b:v", str(video_br),
        "-passlogfile", pass_log,
        "-t", str(VIDEO_NOTE_MAX_SEC),
    ]
    cmd_pass1 = ["ffmpeg", "-y"] + base_args + ["-pass", "1", "-an", "-f", "null", "/dev/null"]
    cmd_pass2 = ["ffmpeg", "-y"] + base_args + [
        "-pass", "2",
        "-c:a", "aac", "-b:a", f"{VIDEO_NOTE_AUDIO_KBPS}k",
        "-movflags", "+faststart",
        str(dst),
    ]
    try:
        for cmd in (cmd_pass1, cmd_pass2):
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error("FFmpeg error:\n%s", stderr.decode(errors="replace"))
                return False

        size_mb = dst.stat().st_size / 1024 / 1024
        logger.info("Converted: %.2f MB → %s (dur=%.1fs, br=%d)",
                    size_mb, dst.name, effective_sec, video_br)
        if dst.stat().st_size > VIDEO_NOTE_MAX_BYTES:
            logger.error("Итог %.2f МБ превышает лимит 12 МБ", size_mb)
            return False
        return True
    finally:
        log_dir = Path(pass_log).parent
        log_name = Path(pass_log).name
        for p in log_dir.glob(f"{log_name}*"):
            with suppress(Exception):
                p.unlink()
