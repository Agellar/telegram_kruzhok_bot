"""
Слой статистики на SQLite. Бот пишет события сюда, админка читает.

Все функции записи — синхронные и предназначены для вызова через
asyncio.to_thread из бота, чтобы не блокировать event loop. БД открывается
в WAL-режиме, что разрешает одновременное чтение админкой во время записи.

Сбой любой функции статистики НЕ должен ронять обработку видео — вызывающая
сторона оборачивает вызовы в try/except.
"""
import os
import time
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("STATS_DB", "/data/stats.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    username     TEXT,
    first_name   TEXT,
    last_name    TEXT,
    first_seen   REAL,
    last_seen    REAL,
    total_jobs   INTEGER NOT NULL DEFAULT 0,
    total_ok     INTEGER NOT NULL DEFAULT 0,
    total_failed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    ts              REAL NOT NULL,
    kind            TEXT,           -- video | document
    file_name       TEXT,
    in_size_bytes   INTEGER,
    in_duration_sec REAL,
    out_size_bytes  INTEGER,
    status          TEXT NOT NULL,  -- ok | convert_fail | tg_error | error
    error_code      TEXT,
    processing_ms   INTEGER
);

CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ts      REAL NOT NULL,
    type    TEXT NOT NULL   -- start | sub_required | sub_confirmed | other_msg
);

CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_ts   ON jobs(ts);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.info("Stats DB ready at %s", DB_PATH)


def upsert_user(user_id: int, username: str | None,
                first_name: str | None, last_name: str | None) -> None:
    now = time.time()
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name, last_name,
                                   first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username   = excluded.username,
                    first_name = excluded.first_name,
                    last_name  = excluded.last_name,
                    last_seen  = excluded.last_seen
                """,
                (user_id, username, first_name, last_name, now, now),
            )
    except Exception as exc:
        logger.warning("stats.upsert_user failed: %s", exc)


def log_job(user_id: int, kind: str, file_name: str | None,
            in_size_bytes: int | None, in_duration_sec: float | None,
            out_size_bytes: int | None, status: str,
            error_code: str | None, processing_ms: int | None) -> None:
    ok = 1 if status == "ok" else 0
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (user_id, ts, kind, file_name, in_size_bytes,
                                  in_duration_sec, out_size_bytes, status,
                                  error_code, processing_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, time.time(), kind, file_name, in_size_bytes,
                 in_duration_sec, out_size_bytes, status, error_code,
                 processing_ms),
            )
            conn.execute(
                """
                UPDATE users SET
                    total_jobs   = total_jobs + 1,
                    total_ok     = total_ok + ?,
                    total_failed = total_failed + ?,
                    last_seen    = ?
                WHERE user_id = ?
                """,
                (ok, 1 - ok, time.time(), user_id),
            )
    except Exception as exc:
        logger.warning("stats.log_job failed: %s", exc)


def log_event(user_id: int | None, type: str) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO events (user_id, ts, type) VALUES (?, ?, ?)",
                (user_id, time.time(), type),
            )
    except Exception as exc:
        logger.warning("stats.log_event failed: %s", exc)
