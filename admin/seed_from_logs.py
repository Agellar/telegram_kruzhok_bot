"""
Одноразовый засев stats.db из старых логов бота.

Бот до внедрения статистики не писал в БД, но логировал в stdout строки вида:
    2026-06-12 19:24:45,044 [INFO] Downloaded user=7826625695 job=ca8694ba
    2026-06-12 19:24:53,900 [INFO] Converted: 11.44 MB → 7826625695_ca8694ba_out.mp4 (dur=24.1s, br=...)
    2026-06-12 19:24:55,909 [INFO] Sent video note user=7826625695 job=ca8694ba

Скрипт читает их (из файла или stdin), реконструирует задания по job_id и
заполняет users/jobs задним числом. Username в логах нет — остаётся NULL.
Скрипт идемпотентен: задания со statusʼом из логов помечаются source='log_seed'
и при повторном запуске не дублируются.

Использование (на сервере):
    docker logs telegram_kruzhok_bot 2>&1 | \
        docker compose run -T --rm admin python seed_from_logs.py -
  или, проще, через одноразовый python-контейнер с доступом к тому /data.
"""
import re
import sys
import sqlite3
from datetime import datetime, timezone

DB_PATH = sys.argv[2] if len(sys.argv) > 2 else "/data/stats.db"

RE_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3})")
RE_DL = re.compile(r"Downloaded user=(\d+) job=([0-9a-f]+)")
RE_SENT = re.compile(r"Sent video note user=(\d+) job=([0-9a-f]+)")
RE_CONV = re.compile(r"Converted: ([\d.]+) MB → (\d+)_([0-9a-f]+)_out\.mp4 \(dur=([\d.]+)s")


def parse_ts(line: str) -> float | None:
    m = RE_TS.match(line)
    if not m:
        return None
    dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    # Логи без таймзоны; трактуем как UTC (контейнерный default).
    return dt.replace(tzinfo=timezone.utc).timestamp() + int(m.group(2)) / 1000


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    lines = sys.stdin if src == "-" else open(src, encoding="utf-8", errors="replace")

    jobs: dict[str, dict] = {}   # job_id → {user, ts, status, out_mb, dur}
    for line in lines:
        ts = parse_ts(line)
        if (m := RE_DL.search(line)):
            uid, job = int(m.group(1)), m.group(2)
            jobs.setdefault(job, {}).update(user=uid, ts=ts, status="error")
        elif (m := RE_CONV.search(line)):
            mb, uid, job, dur = m.group(1), int(m.group(2)), m.group(3), m.group(4)
            j = jobs.setdefault(job, {})
            j.update(user=uid, out_mb=float(mb), dur=float(dur))
            j.setdefault("ts", ts)
        elif (m := RE_SENT.search(line)):
            uid, job = int(m.group(1)), m.group(2)
            j = jobs.setdefault(job, {})
            j.update(user=uid, status="ok")
            j.setdefault("ts", ts)

    valid = {k: v for k, v in jobs.items() if v.get("user") and v.get("ts")}
    if not valid:
        print("Нет распознанных заданий в логах.")
        return

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    # схему создаём минимально, если БД пуста (обычно бот уже создал)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            last_name TEXT, first_seen REAL, last_seen REAL,
            total_jobs INTEGER DEFAULT 0, total_ok INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, ts REAL,
            kind TEXT, file_name TEXT, in_size_bytes INTEGER,
            in_duration_sec REAL, out_size_bytes INTEGER, status TEXT,
            error_code TEXT, processing_ms INTEGER, source TEXT);
    """)
    # колонка source могла отсутствовать в основной схеме — добавим мягко
    cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    if "source" not in cols:
        conn.execute("ALTER TABLE jobs ADD COLUMN source TEXT")

    seeded_jobs = {
        r[0] for r in conn.execute(
            "SELECT printf('%d|%f', user_id, ts) FROM jobs WHERE source='log_seed'"
        )
    }

    added = 0
    for job, v in sorted(valid.items(), key=lambda kv: kv[1]["ts"]):
        key = f"{v['user']}|{v['ts']:.6f}"
        if key in seeded_jobs:
            continue
        out_bytes = int(v["out_mb"] * 1024 * 1024) if "out_mb" in v else None
        conn.execute(
            """INSERT INTO jobs (user_id, ts, kind, file_name, in_size_bytes,
                  in_duration_sec, out_size_bytes, status, error_code,
                  processing_ms, source)
               VALUES (?,?,?,?,?,?,?,?,?,?, 'log_seed')""",
            (v["user"], v["ts"], None, None, None, v.get("dur"),
             out_bytes, v.get("status", "error"), None, None),
        )
        ok = 1 if v.get("status") == "ok" else 0
        conn.execute(
            """INSERT INTO users (user_id, first_seen, last_seen, total_jobs,
                  total_ok, total_failed)
               VALUES (?,?,?,1,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                  first_seen = MIN(first_seen, excluded.first_seen),
                  last_seen  = MAX(last_seen,  excluded.last_seen),
                  total_jobs   = total_jobs + 1,
                  total_ok     = total_ok + excluded.total_ok,
                  total_failed = total_failed + excluded.total_failed""",
            (v["user"], v["ts"], v["ts"], ok, 1 - ok),
        )
        added += 1

    conn.commit()
    conn.close()
    print(f"Засеяно заданий: {added} (распознано в логах: {len(valid)}).")


if __name__ == "__main__":
    main()
