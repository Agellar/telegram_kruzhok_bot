import os
import re
import json
import time
import uuid
import asyncio
import logging
from pathlib import Path
from contextlib import suppress
from collections import defaultdict

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_ID    = os.getenv("CHANNEL_ID", "@your_channel")
TEMP_DIR      = Path(os.getenv("TEMP_DIR", "/tmp/videobot"))
MAX_PARALLEL  = int(os.getenv("MAX_PARALLEL", "2"))
# Bot API без локального сервера качает максимум 20 МБ.
MAX_FILE_MB   = int(os.getenv("MAX_FILE_MB", "20"))
USER_COOLDOWN = int(os.getenv("USER_COOLDOWN", "5"))  # секунд между запросами одного юзера

# Лимиты Telegram для video note
VIDEO_NOTE_MAX_BYTES   = 12 * 1024 * 1024
VIDEO_NOTE_TARGET_MB   = 11.5  # запас 0.5 МБ на контейнер/метаданные
VIDEO_NOTE_MAX_SEC     = 60
VIDEO_NOTE_AUDIO_KBPS  = 64
VIDEO_NOTE_SIZE        = 512

ALLOWED_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp", ".flv"}

TEMP_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
semaphore = asyncio.Semaphore(MAX_PARALLEL)

# user_id → timestamp последнего запроса
_last_request: dict[int, float] = defaultdict(float)
# Кэш ссылки на канал, чтобы корректно формировать кнопку для приватных каналов
_channel_link: str | None = None

# ─── TEXTS ────────────────────────────────────────────────────────────────────
TEXT_NOT_SUBSCRIBED = "👋 Для использования бота необходимо подписаться на наш канал."
TEXT_WELCOME = (
    "✅ Подписка подтверждена!\n\n"
    "🎥 Отправь мне любое видео — получишь его в виде <b>видеокружка</b> в отличном качестве.\n\n"
    "⚠️ <b>Ограничения Telegram:</b>\n"
    "• Макс. длительность видеокружка — 60 сек\n"
    "• Видео обрезается до квадрата (центр кадра)\n"
    f"• Принимаются только видеофайлы (до {MAX_FILE_MB} МБ)"
)

# ─── KEYBOARD ─────────────────────────────────────────────────────────────────
def subscribe_keyboard() -> types.InlineKeyboardMarkup:
    if _channel_link:
        url = _channel_link
    elif CHANNEL_ID.startswith("@"):
        url = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
    else:
        url = "https://t.me/"  # fallback, обычно невидим — _channel_link задаётся на старте
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📢 Подписаться на канал", url=url)],
        [types.InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
    ])

# ─── SUBSCRIPTION CHECK ───────────────────────────────────────────────────────
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ("left", "kicked")
    except Exception as exc:
        msg = str(exc).lower()
        if "chat not found" in msg:
            logger.critical("CHANNEL_ID='%s' не найден.", CHANNEL_ID)
        elif "member_list_is_inaccessible" in msg or "bot is not a member" in msg:
            logger.critical("Бот не админ канала '%s'.", CHANNEL_ID)
        else:
            logger.error("Ошибка проверки подписки user=%s: %s", user_id, exc)
        return False

# ─── FFPROBE: реальная длительность ───────────────────────────────────────────
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

# ─── FFMPEG: двухпроходная конвертация, гарантированно <= 12 МБ ──────────────
async def convert_to_video_note(src: Path, dst: Path) -> bool:
    duration = await probe_duration(src) or VIDEO_NOTE_MAX_SEC
    effective_sec = min(duration, VIDEO_NOTE_MAX_SEC)

    target_bits = VIDEO_NOTE_TARGET_MB * 1024 * 1024 * 8
    video_br = int(target_bits / effective_sec) - VIDEO_NOTE_AUDIO_KBPS * 1000
    if video_br < 100_000:  # защита от деградации
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
        logger.info("Converted: %.2f MB → %s (dur=%.1fs, br=%d)", size_mb, dst.name, effective_sec, video_br)
        if dst.stat().st_size > VIDEO_NOTE_MAX_BYTES:
            logger.error("Итоговый файл %.2f МБ превышает лимит 12 МБ", size_mb)
            return False
        return True
    finally:
        # Удаляем все вспомогательные файлы двухпроходного кодирования
        log_dir = Path(pass_log).parent
        log_name = Path(pass_log).name
        for p in log_dir.glob(f"{log_name}*"):
            with suppress(Exception):
                p.unlink()

# ─── CLEANUP ──────────────────────────────────────────────────────────────────
def cleanup(*paths: Path) -> None:
    for p in paths:
        with suppress(Exception):
            if p.exists():
                p.unlink()
                logger.debug("Deleted: %s", p)

def safe_suffix(filename: str | None) -> str:
    if not filename:
        return ".mp4"
    suffix = Path(filename).suffix.lower()
    if not suffix or not re.fullmatch(r"\.[a-z0-9]{2,5}", suffix):
        return ".mp4"
    return suffix if suffix in ALLOWED_EXTS else ".mp4"

# ─── HANDLERS ─────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not await is_subscribed(message.from_user.id):
        await message.answer(TEXT_NOT_SUBSCRIBED, reply_markup=subscribe_keyboard())
        return
    await message.answer(TEXT_WELCOME)


@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery) -> None:
    if await is_subscribed(callback.from_user.id):
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(TEXT_WELCOME)
        await callback.answer()
    else:
        await callback.answer(
            "❌ Вы ещё не подписаны. Подпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )


@dp.message(F.video | F.document)
async def handle_video(message: Message) -> None:
    uid = message.from_user.id

    if not await is_subscribed(uid):
        await message.answer(TEXT_NOT_SUBSCRIBED, reply_markup=subscribe_keyboard())
        return

    # Throttling per user
    now = time.monotonic()
    if now - _last_request[uid] < USER_COOLDOWN:
        wait = int(USER_COOLDOWN - (now - _last_request[uid])) + 1
        await message.answer(f"⏳ Слишком часто. Подожди {wait} сек.")
        return
    _last_request[uid] = now

    if message.document:
        mime = (message.document.mime_type or "").lower()
        if not mime.startswith("video/"):
            await message.answer("❌ Принимаются только видеофайлы.")
            return
        file_obj = message.document
        original_name = message.document.file_name
    else:
        file_obj = message.video
        original_name = getattr(message.video, "file_name", None)

    if file_obj.file_size and file_obj.file_size > MAX_FILE_MB * 1024 * 1024:
        await message.answer(
            f"❌ Файл слишком большой. Максимум — {MAX_FILE_MB} МБ.\n"
            "(ограничение Telegram Bot API)"
        )
        return

    # Ранний отказ по слишком длинному видео не делаем — мы и так обрежем до 60с.
    # Но если duration известен и > 10 минут, явно отказываем — нет смысла качать.
    duration_meta = getattr(file_obj, "duration", None)
    if duration_meta and duration_meta > 600:
        await message.answer(
            "❌ Видео слишком длинное. Пришли клип покороче "
            "(будут взяты первые 60 секунд)."
        )
        return

    job_id = uuid.uuid4().hex[:8]
    suffix = safe_suffix(original_name)
    src = TEMP_DIR / f"{uid}_{job_id}_in{suffix}"
    dst = TEMP_DIR / f"{uid}_{job_id}_out.mp4"
    status = await message.answer("⏳ Конвертирую видео, подожди немного…")

    async with semaphore:
        try:
            file_info = await bot.get_file(file_obj.file_id)
            await bot.download_file(file_info.file_path, destination=str(src))
            logger.info("Downloaded user=%s job=%s", uid, job_id)

            if not await convert_to_video_note(src, dst):
                with suppress(TelegramBadRequest):
                    await status.edit_text(
                        "❌ Ошибка конвертации.\n"
                        "Попробуй другой файл или клип покороче."
                    )
                return

            await message.answer_video_note(video_note=FSInputFile(str(dst)))
            with suppress(TelegramBadRequest):
                await status.delete()
            logger.info("Sent video note user=%s job=%s", uid, job_id)

        except TelegramBadRequest as exc:
            err = str(exc)
            logger.error("TelegramBadRequest user=%s: %s", uid, err)
            with suppress(TelegramBadRequest):
                if "VOICE_MESSAGES_FORBIDDEN" in err:
                    await status.edit_text(
                        "❌ У вас запрещён приём видеокружков и голосовых сообщений.\n\n"
                        "Чтобы исправить:\n"
                        "Telegram → Настройки → Конфиденциальность → "
                        "Голосовые сообщения → <b>Все</b>\n\n"
                        "После изменения настройки отправьте видео повторно."
                    )
                elif "file is too big" in err.lower():
                    await status.edit_text(
                        "❌ Файл после конвертации слишком большой для Telegram.\n"
                        "Попробуй более короткий клип (до 60 сек)."
                    )
                else:
                    await status.edit_text("❌ Telegram отклонил файл. Попробуй ещё раз.")

        except Exception as exc:
            logger.exception("Unexpected error user=%s: %s", uid, exc)
            with suppress(TelegramBadRequest):
                await status.edit_text("❌ Непредвиденная ошибка. Попробуй ещё раз.")
        finally:
            cleanup(src, dst)


@dp.message(F.text | F.photo | F.audio | F.voice | F.sticker | F.animation)
async def handle_other(message: Message) -> None:
    if not await is_subscribed(message.from_user.id):
        await message.answer(TEXT_NOT_SUBSCRIBED, reply_markup=subscribe_keyboard())
        return
    await message.answer("🎥 Отправь мне видеофайл. Другие типы сообщений не принимаются.")

# ─── STARTUP / SHUTDOWN ───────────────────────────────────────────────────────
async def on_startup() -> None:
    global _channel_link
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        logger.info("Канал найден: '%s' (id=%s, type=%s)", chat.title, chat.id, chat.type)
        if chat.username:
            _channel_link = f"https://t.me/{chat.username}"
        elif chat.invite_link:
            _channel_link = chat.invite_link
        else:
            with suppress(Exception):
                _channel_link = await bot.export_chat_invite_link(chat.id)
        if chat.type not in ("channel", "supergroup"):
            logger.warning(
                "CHANNEL_ID='%s' — это %s, а не канал.",
                CHANNEL_ID, chat.type,
            )
    except Exception as exc:
        logger.critical(
            "Ошибка CHANNEL_ID='%s': %s\n"
            "→ Укажи @username канала или числовой ID -100xxxxxxxxxx\n"
            "→ Бот должен быть администратором канала",
            CHANNEL_ID, exc,
        )


async def on_shutdown() -> None:
    logger.info("Shutdown: чистим TEMP_DIR=%s", TEMP_DIR)
    with suppress(Exception):
        for p in TEMP_DIR.iterdir():
            with suppress(Exception):
                p.unlink()

# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    logger.info("Bot starting | channel=%s | parallel=%d | max_mb=%d",
                CHANNEL_ID, MAX_PARALLEL, MAX_FILE_MB)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
