"""
Веб-админка для telegram_kruzhok_bot.

Читает stats.db (SQLite, режим read-only) и отдаёт дашборд + JSON-API.
Защита — HTTP Basic Auth (ADMIN_USER / ADMIN_PASS из окружения).
Запуск: uvicorn app:app --host 0.0.0.0 --port 8000
"""
import os
import time
import secrets
import sqlite3

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

DB_PATH = os.getenv("STATS_DB", "/data/stats.db")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")

app = FastAPI(title="Kruzhok Bot Admin", docs_url=None, redoc_url=None, openapi_url=None)
security = HTTPBasic()


def auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    ok_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    ok_pass = secrets.compare_digest(credentials.password, ADMIN_PASS)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def db() -> sqlite3.Connection:
    # Том монтируется rw (нужно для WAL sidecar-файлов), но query_only=ON
    # гарантирует, что админка ничего не пишет в саму БД.
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
        # БД ещё не создана / занята — отдаём пусто, не роняем эндпоинт
        return []
    finally:
        if conn is not None:
            conn.close()


# ─── API ──────────────────────────────────────────────────────────────────────
@app.get("/api/summary")
def api_summary(_: str = Depends(auth)) -> JSONResponse:
    now = time.time()
    d1, d7 = now - 86400, now - 7 * 86400
    total_users = q("SELECT COUNT(*) c FROM users")
    total_jobs = q("SELECT COUNT(*) c FROM jobs")
    ok_jobs = q("SELECT COUNT(*) c FROM jobs WHERE status='ok'")
    failed_jobs = q("SELECT COUNT(*) c FROM jobs WHERE status<>'ok'")
    bytes_in = q("SELECT COALESCE(SUM(in_size_bytes),0) s FROM jobs")
    active_24h = q("SELECT COUNT(DISTINCT user_id) c FROM jobs WHERE ts>=?", (d1,))
    active_7d = q("SELECT COUNT(DISTINCT user_id) c FROM jobs WHERE ts>=?", (d7,))
    jobs_24h = q("SELECT COUNT(*) c FROM jobs WHERE ts>=?", (d1,))
    sub_required = q("SELECT COUNT(*) c FROM events WHERE type='sub_required'")
    sub_confirmed = q("SELECT COUNT(*) c FROM events WHERE type='sub_confirmed'")
    starts = q("SELECT COUNT(*) c FROM events WHERE type='start'")

    def one(rows, key="c"):
        return rows[0][key] if rows else 0

    return JSONResponse({
        "total_users": one(total_users),
        "total_jobs": one(total_jobs),
        "ok_jobs": one(ok_jobs),
        "failed_jobs": one(failed_jobs),
        "bytes_in": one(bytes_in, "s"),
        "active_24h": one(active_24h),
        "active_7d": one(active_7d),
        "jobs_24h": one(jobs_24h),
        "starts": one(starts),
        "sub_required": one(sub_required),
        "sub_confirmed": one(sub_confirmed),
    })


@app.get("/api/users")
def api_users(_: str = Depends(auth),
              sort: str = Query("total_jobs"),
              limit: int = Query(200, le=2000)) -> JSONResponse:
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


@app.get("/api/jobs")
def api_jobs(_: str = Depends(auth),
             limit: int = Query(100, le=1000),
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


@app.get("/api/timeseries")
def api_timeseries(_: str = Depends(auth), days: int = Query(30, le=365)) -> JSONResponse:
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


@app.get("/api/errors")
def api_errors(_: str = Depends(auth)) -> JSONResponse:
    rows = q(
        """SELECT COALESCE(error_code, status) code, COUNT(*) c
           FROM jobs WHERE status<>'ok'
           GROUP BY code ORDER BY c DESC""",
    )
    return JSONResponse(rows)


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


# ─── DASHBOARD ────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def dashboard(_: str = Depends(auth)) -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kruzhok Bot — админка</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root { --bg:#0f1419; --card:#1a2027; --muted:#8b97a4; --fg:#e6edf3;
          --accent:#3ea6ff; --ok:#3fb950; --bad:#f85149; --line:#2a323c; }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--fg); }
  header { padding:18px 24px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:12px; }
  header h1 { font-size:18px; margin:0; }
  header .sub { color:var(--muted); font-size:13px; }
  main { padding:24px; max-width:1200px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
           gap:14px; margin-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:16px; }
  .card .label { color:var(--muted); font-size:12px; text-transform:uppercase;
                 letter-spacing:.04em; }
  .card .val { font-size:26px; font-weight:600; margin-top:6px; }
  .card .val.ok { color:var(--ok); } .card .val.bad { color:var(--bad); }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-bottom:24px; }
  @media(max-width:780px){ .grid2{ grid-template-columns:1fr; } }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:16px; }
  .panel h2 { font-size:14px; margin:0 0 12px; color:var(--muted);
              text-transform:uppercase; letter-spacing:.04em; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line);
          white-space:nowrap; }
  th { color:var(--muted); font-weight:500; cursor:pointer; user-select:none; }
  tbody tr:hover { background:#222c36; }
  .badge { padding:2px 8px; border-radius:20px; font-size:11px; }
  .badge.ok { background:rgba(63,185,80,.15); color:var(--ok); }
  .badge.bad { background:rgba(248,81,73,.15); color:var(--bad); }
  .scroll { max-height:420px; overflow:auto; }
  a { color:var(--accent); text-decoration:none; }
  .muted { color:var(--muted); }
  canvas { max-height:260px; }
</style>
</head>
<body>
<header>
  <h1>🎥 Kruzhok Bot</h1>
  <span class="sub" id="updated">загрузка…</span>
</header>
<main>
  <div class="cards" id="cards"></div>
  <div class="grid2">
    <div class="panel"><h2>Активность по дням</h2><canvas id="chartDays"></canvas></div>
    <div class="panel"><h2>Топ пользователей</h2><canvas id="chartTop"></canvas></div>
  </div>
  <div class="grid2">
    <div class="panel">
      <h2>Конверсия подписки</h2><canvas id="chartFunnel"></canvas>
    </div>
    <div class="panel"><h2>Ошибки</h2><canvas id="chartErrors"></canvas></div>
  </div>
  <div class="panel" style="margin-bottom:24px;">
    <h2>Пользователи</h2>
    <div class="scroll"><table id="tblUsers">
      <thead><tr>
        <th data-k="user_id">ID</th><th>Пользователь</th>
        <th data-k="total_jobs">Всего</th><th data-k="total_ok">OK</th>
        <th data-k="total_failed">Ошибок</th><th data-k="last_seen">Последний раз</th>
      </tr></thead><tbody></tbody>
    </table></div>
  </div>
  <div class="panel">
    <h2>Последние загрузки</h2>
    <div class="scroll"><table id="tblJobs">
      <thead><tr>
        <th>Время</th><th>Пользователь</th><th>Файл</th><th>Тип</th>
        <th>Вход</th><th>Длит.</th><th>Выход</th><th>Статус</th><th>Время обр.</th>
      </tr></thead><tbody></tbody>
    </table></div>
  </div>
</main>
<script>
const fmtBytes = b => { if(!b) return '—'; const u=['B','KB','MB','GB'];
  let i=0,n=b; while(n>=1024&&i<u.length-1){n/=1024;i++;} return n.toFixed(1)+' '+u[i]; };
const fmtTime = ts => ts ? new Date(ts*1000).toLocaleString('ru-RU') : '—';
const fmtName = (r) => {
  const name = [r.first_name, r.last_name].filter(Boolean).join(' ');
  const at = r.username ? '@'+r.username : '';
  const id = r.user_id;
  return (name||at||('id'+id)) + (at && name ? ' '+at : '') ;
};
async function get(u){ const r=await fetch(u); if(!r.ok) throw new Error(r.status); return r.json(); }

async function loadSummary(){
  const s = await get('/api/summary');
  const conv = s.sub_required ? (100*s.sub_confirmed/s.sub_required).toFixed(0)+'%' : '—';
  const cards = [
    ['Пользователей', s.total_users],
    ['Всего загрузок', s.total_jobs],
    ['Успешных', s.ok_jobs, 'ok'],
    ['Ошибок', s.failed_jobs, s.failed_jobs?'bad':''],
    ['Активны 24ч', s.active_24h],
    ['Активны 7д', s.active_7d],
    ['Загрузок 24ч', s.jobs_24h],
    ['Трафик (вход)', fmtBytes(s.bytes_in)],
    ['Команд /start', s.starts],
  ];
  document.getElementById('cards').innerHTML = cards.map(([l,v,c])=>
    `<div class="card"><div class="label">${l}</div><div class="val ${c||''}">${v}</div></div>`).join('');
  document.getElementById('updated').textContent = 'обновлено '+new Date().toLocaleTimeString('ru-RU');
  return s;
}

let charts = {};
function mkChart(id, cfg){ if(charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), cfg); }

async function loadCharts(s){
  const ts = await get('/api/timeseries?days=30');
  mkChart('chartDays', { type:'line',
    data:{ labels:ts.map(r=>r.d), datasets:[
      {label:'Загрузки', data:ts.map(r=>r.jobs), borderColor:'#3ea6ff', tension:.3},
      {label:'Уник. юзеры', data:ts.map(r=>r.users), borderColor:'#3fb950', tension:.3},
    ]},
    options:{ plugins:{legend:{labels:{color:'#8b97a4'}}},
      scales:{x:{ticks:{color:'#8b97a4'}},y:{ticks:{color:'#8b97a4'},beginAtZero:true}} }});

  const users = await get('/api/users?sort=total_jobs&limit=10');
  mkChart('chartTop', { type:'bar',
    data:{ labels:users.map(fmtName), datasets:[{label:'Загрузок',
      data:users.map(u=>u.total_jobs), backgroundColor:'#3ea6ff'}]},
    options:{ indexAxis:'y', plugins:{legend:{display:false}},
      scales:{x:{ticks:{color:'#8b97a4'},beginAtZero:true},y:{ticks:{color:'#8b97a4'}}} }});

  mkChart('chartFunnel', { type:'bar',
    data:{ labels:['/start','Просили подписку','Подтвердили'],
      datasets:[{ data:[s.starts, s.sub_required, s.sub_confirmed],
        backgroundColor:['#3ea6ff','#d29922','#3fb950']}]},
    options:{ plugins:{legend:{display:false}},
      scales:{x:{ticks:{color:'#8b97a4'}},y:{ticks:{color:'#8b97a4'},beginAtZero:true}} }});

  const errs = await get('/api/errors');
  mkChart('chartErrors', { type:'doughnut',
    data:{ labels:errs.length?errs.map(e=>e.code):['нет ошибок'],
      datasets:[{ data:errs.length?errs.map(e=>e.c):[1],
        backgroundColor:['#f85149','#d29922','#db61a2','#a371f7','#3ea6ff','#8b97a4']}]},
    options:{ plugins:{legend:{labels:{color:'#8b97a4'}}} }});
}

let usersData = [], usersSort = 'total_jobs';
async function loadUsers(){
  usersData = await get('/api/users?sort='+usersSort+'&limit=500');
  renderUsers();
}
function renderUsers(){
  const tb = document.querySelector('#tblUsers tbody');
  tb.innerHTML = usersData.map(u=>`<tr>
    <td class="muted">${u.user_id}</td>
    <td>${fmtName(u)}</td>
    <td>${u.total_jobs}</td>
    <td style="color:#3fb950">${u.total_ok}</td>
    <td style="color:${u.total_failed?'#f85149':'#8b97a4'}">${u.total_failed}</td>
    <td class="muted">${fmtTime(u.last_seen)}</td></tr>`).join('');
}
document.querySelectorAll('#tblUsers th[data-k]').forEach(th=>{
  th.onclick = ()=>{ usersSort = th.dataset.k; loadUsers(); };
});

async function loadJobs(){
  const jobs = await get('/api/jobs?limit=200');
  const tb = document.querySelector('#tblJobs tbody');
  tb.innerHTML = jobs.map(j=>`<tr>
    <td class="muted">${fmtTime(j.ts)}</td>
    <td>${fmtName(j)}</td>
    <td>${j.file_name||'—'}</td>
    <td class="muted">${j.kind||'—'}</td>
    <td>${fmtBytes(j.in_size_bytes)}</td>
    <td>${j.in_duration_sec?Math.round(j.in_duration_sec)+'с':'—'}</td>
    <td>${fmtBytes(j.out_size_bytes)}</td>
    <td><span class="badge ${j.status==='ok'?'ok':'bad'}">${j.status}${j.error_code?(': '+j.error_code):''}</span></td>
    <td class="muted">${j.processing_ms?(j.processing_ms/1000).toFixed(1)+'с':'—'}</td></tr>`).join('');
}

async function refresh(){
  try {
    const s = await loadSummary();
    await Promise.all([loadCharts(s), loadUsers(), loadJobs()]);
  } catch(e){ document.getElementById('updated').textContent = 'ошибка: '+e.message; }
}
refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>
"""
