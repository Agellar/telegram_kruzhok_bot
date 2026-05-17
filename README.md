# 🎥 Telegram Kruzhok Bot

Telegram-бот, превращающий обычное видео в **видеокружок** (video note) —
квадратное круглое сообщение, которое отправляется одной кнопкой и
воспроизводится с автозапуском. Бот принимает видеофайл, конвертирует
его через FFmpeg в формат, удовлетворяющий ограничениям Telegram
(512×512, ≤ 60 секунд, ≤ 12 МБ), и отправляет результат пользователю.

Перед использованием бот проверяет подписку пользователя на указанный
канал — это удобный механизм gate-кипинга для коммьюнити-каналов.

## ✨ Возможности

- 🎞 Конвертация любого видеоформата (`mp4`, `mov`, `mkv`, `webm`, …) в видеокружок.
- 📐 Автоматический кроп по центру до квадрата + ресайз до 512×512 (lanczos).
- 🎚 Двухпроходное кодирование `libx264` с расчётом битрейта по реальной
  длительности — итоговый файл всегда укладывается в 12 МБ без потери качества
  на коротких клипах.
- 🔐 Обязательная подписка на канал перед использованием.
- ⏱ Per-user cooldown — защита от спама.
- 🧹 Автоматическая чистка временных файлов (включая логи двух проходов).
- ⚙️ Управление параллелизмом через семафор: `MAX_PARALLEL` одновременных
  ffmpeg-задач, остальные ставятся в очередь.
- 🛟 Корректная обработка ошибок Telegram: запрет на video note у получателя,
  оверсайз, недоступность канала, приватные каналы и пр.

## 🚀 Быстрый старт

### Требования

- Python 3.10+
- FFmpeg и ffprobe в `$PATH`
- Telegram-бот ([@BotFather](https://t.me/BotFather))
- Канал, в котором бот добавлен **администратором**

### Установка

```bash
git clone https://github.com/Agellar/telegram_kruzhok_bot.git
cd telegram_kruzhok_bot

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Установка ffmpeg (Debian/Ubuntu)
sudo apt install ffmpeg

cp .env.example .env
# отредактируйте .env: BOT_TOKEN, CHANNEL_ID
```

### Запуск

```bash
set -a; source .env; set +a
python bot.py
```

Либо без `.env`:

```bash
BOT_TOKEN=123:ABC CHANNEL_ID=@my_channel python bot.py
```

## ⚙️ Переменные окружения

| Переменная      | По умолчанию      | Описание |
|-----------------|-------------------|----------|
| `BOT_TOKEN`     | —                 | Токен бота от BotFather |
| `CHANNEL_ID`    | `@your_channel`   | `@username` канала или `-100xxxxxxxxxx` |
| `TEMP_DIR`      | `/tmp/videobot`   | Каталог для временных файлов |
| `MAX_PARALLEL`  | `2`               | Параллельных ffmpeg-задач |
| `MAX_FILE_MB`   | `20`              | Лимит входного файла (Bot API качает максимум 20 МБ) |
| `USER_COOLDOWN` | `5`               | Минимальный интервал между запросами одного юзера, сек |

> **Важно:** стандартный Telegram Bot API не позволяет скачивать файлы
> больше 20 МБ. Если нужен лимит выше — поднимите [локальный Bot API
> сервер](https://github.com/tdlib/telegram-bot-api) и увеличьте
> `MAX_FILE_MB`.

## 🧪 Как это работает

1. Пользователь присылает видео.
2. Бот проверяет подписку на канал через `get_chat_member`.
3. Файл скачивается во временный каталог.
4. `ffprobe` определяет реальную длительность.
5. Рассчитывается целевой битрейт под 11.5 МБ полезной нагрузки.
6. `ffmpeg` делает два прохода `libx264`, кроп до квадрата и ресайз 512×512.
7. Результат отправляется как `video_note`, временные файлы удаляются.

## 🐳 Запуск в Docker (опционально)

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
CMD ["python", "bot.py"]
```

```bash
docker build -t kruzhok-bot .
docker run --rm -e BOT_TOKEN=... -e CHANNEL_ID=@my_channel kruzhok-bot
```

## 📝 Лицензия

MIT
