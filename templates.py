"""HTML-шаблоны админки: страница входа и дашборд. Вынесены отдельно,
чтобы app.py оставался компактным."""

# ─── ОБЩИЕ СТИЛИ (дизайн-токены) ──────────────────────────────────────────────
# Светлая тема, как рекомендуют UX-практики для дашбордов: много воздуха,
# крупные числа, сдержанный цвет (акцент — индиго), один акцент на действие.
_TOKENS = """
:root{
  --bg:#f5f7fb; --surface:#ffffff; --border:#e6e9f0;
  --fg:#1a2233; --muted:#6b7689; --faint:#9aa3b2;
  --accent:#4f46e5; --accent-soft:#eef0fe;
  --ok:#16a34a; --ok-soft:#e7f6ec;
  --bad:#dc2626; --bad-soft:#fdecec;
  --warn:#d97706;
  --shadow:0 1px 2px rgba(16,24,40,.04),0 1px 3px rgba(16,24,40,.08);
  --shadow-lg:0 10px 30px rgba(16,24,40,.12);
  --radius:14px; --radius-sm:10px;
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,system-ui,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;font-family:var(--font);background:var(--bg);color:var(--fg);
  -webkit-font-smoothing:antialiased;font-size:14px;line-height:1.5}
a{color:var(--accent);text-decoration:none}
"""

# ─── СТРАНИЦА ВХОДА ───────────────────────────────────────────────────────────
LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Вход — Kruzhok Bot</title>
<style>
""" + _TOKENS + r"""
body{min-height:100dvh;display:grid;place-items:center;padding:24px;
  background:
    radial-gradient(1100px 550px at 85% -15%, rgba(124,58,237,.10), transparent),
    linear-gradient(135deg,#eef0fe 0%,#f5f7fb 45%,#eafbf1 100%);}
.card{width:100%;max-width:400px;background:var(--surface);
  border:1px solid var(--border);border-radius:20px;box-shadow:var(--shadow-lg);
  padding:36px 32px;animation:rise .5s cubic-bezier(.2,.7,.2,1)}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
.brand{display:flex;flex-direction:column;align-items:center;gap:14px;margin-bottom:28px}
.logo{width:64px;height:64px;border-radius:18px;display:grid;place-items:center;
  font-size:32px;background:linear-gradient(135deg,#4f46e5,#7c3aed);
  box-shadow:0 8px 20px rgba(79,70,229,.35)}
.brand h1{margin:0;font-size:20px;font-weight:700;letter-spacing:-.01em}
.brand p{margin:0;color:var(--muted);font-size:13px}
form{display:flex;flex-direction:column;gap:16px}
.field label{display:block;font-size:13px;font-weight:600;margin-bottom:6px;color:var(--fg)}
.field input{width:100%;padding:12px 14px;font-size:15px;font-family:inherit;
  border:1.5px solid var(--border);border-radius:var(--radius-sm);background:#fcfcfe;
  transition:border-color .15s,box-shadow .15s;outline:none}
.field input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft);background:#fff}
button{margin-top:4px;padding:13px;font-size:15px;font-weight:600;font-family:inherit;
  color:#fff;background:var(--accent);border:none;border-radius:var(--radius-sm);
  cursor:pointer;transition:filter .15s,transform .05s}
button:hover{filter:brightness(1.08)}
button:active{transform:translateY(1px)}
.error{background:var(--bad-soft);color:var(--bad);font-size:13px;font-weight:500;
  padding:10px 12px;border-radius:var(--radius-sm);text-align:center}
.foot{margin-top:22px;text-align:center;color:var(--faint);font-size:12px}
</style></head>
<body>
  <div class="card">
    <div class="brand">
      <div class="logo">🎥</div>
      <h1>Kruzhok Bot</h1>
      <p>Панель статистики</p>
    </div>
    <!--ERROR-->
    <form method="post" action="/admin/login">
      <div class="field">
        <label for="u">Логин</label>
        <input id="u" name="username" type="text" autocomplete="username"
               autofocus required placeholder="admin">
      </div>
      <div class="field">
        <label for="p">Пароль</label>
        <input id="p" name="password" type="password" autocomplete="current-password"
               required placeholder="••••••••">
      </div>
      <button type="submit">Войти</button>
    </form>
    <div class="foot">Доступ только для администратора</div>
  </div>
</body></html>
"""

# ─── ДАШБОРД ──────────────────────────────────────────────────────────────────
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Kruzhok Bot — статистика</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
""" + _TOKENS + r"""
/* ── Каркас: топбар + контент ── */
.topbar{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.85);
  backdrop-filter:saturate(180%) blur(8px);border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:12px;padding:0 20px;height:60px}
.topbar .logo{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;
  font-size:18px;background:linear-gradient(135deg,#4f46e5,#7c3aed)}
.topbar h1{margin:0;font-size:16px;font-weight:700;letter-spacing:-.01em}
.topbar .sub{color:var(--muted);font-size:12px;margin-left:2px}
.topbar .spacer{flex:1}
.topbar .pill{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);
  padding:6px 10px;border:1px solid var(--border);border-radius:999px;background:#fff}
.dot{width:7px;height:7px;border-radius:50%;background:var(--ok);
  box-shadow:0 0 0 3px var(--ok-soft)}
.btn-ghost{font-size:13px;color:var(--muted);padding:7px 12px;border:1px solid var(--border);
  border-radius:9px;background:#fff;cursor:pointer;font-family:inherit;transition:.15s}
.btn-ghost:hover{color:var(--bad);border-color:var(--bad)}
main{max-width:1180px;margin:0 auto;padding:24px 20px 48px}
.section-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
  color:var(--faint);margin:28px 4px 12px}
.section-title:first-child{margin-top:4px}

/* ── KPI-карточки: крупные числа ── */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:18px;box-shadow:var(--shadow);position:relative;overflow:hidden}
.kpi .ic{position:absolute;right:14px;top:14px;font-size:18px;opacity:.5}
.kpi .label{color:var(--muted);font-size:12.5px;font-weight:500}
.kpi .val{font-size:30px;font-weight:750;letter-spacing:-.02em;margin-top:6px;line-height:1}
.kpi .delta{font-size:12px;color:var(--faint);margin-top:6px}
.kpi.accent{background:linear-gradient(135deg,#4f46e5,#6d5cf0);border:none;color:#fff}
.kpi.accent .label,.kpi.accent .delta{color:rgba(255,255,255,.85)}
.kpi.accent .ic{opacity:.7}

/* ── мини-карточки второго ряда ── */
.minis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.mini{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);
  padding:13px 14px;box-shadow:var(--shadow)}
.mini .label{color:var(--muted);font-size:11.5px}
.mini .val{font-size:19px;font-weight:700;margin-top:3px}
.mini .val.ok{color:var(--ok)} .mini .val.bad{color:var(--bad)}

/* ── панели с графиками ── */
.grid2{display:grid;grid-template-columns:1.4fr 1fr;gap:16px}
.grid2b{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:18px;box-shadow:var(--shadow)}
.panel h2{font-size:14px;font-weight:650;margin:0 0 4px}
.panel .hint{color:var(--faint);font-size:12px;margin:0 0 14px}
canvas{max-height:260px}

/* ── таблицы ── */
.panel.table-panel{padding:18px 0 6px}
.panel.table-panel h2,.panel.table-panel .hint{padding:0 18px}
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:540px}
th,td{text-align:left;padding:10px 14px;white-space:nowrap}
thead th{position:sticky;top:0;background:#fbfbfd;color:var(--muted);font-weight:600;
  font-size:12px;border-bottom:1px solid var(--border);cursor:pointer;user-select:none}
tbody td{border-bottom:1px solid #f1f3f7}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:#fafbff}
.scroll{max-height:440px;overflow:auto}
.user-cell{display:flex;flex-direction:column;gap:1px}
.user-cell .nm{font-weight:600}
.user-cell .un{color:var(--faint);font-size:11.5px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600}
.badge.ok{background:var(--ok-soft);color:var(--ok)}
.badge.bad{background:var(--bad-soft);color:var(--bad)}
.muted{color:var(--muted)} .right{text-align:right}
.empty{padding:32px;text-align:center;color:var(--faint)}

/* ── адаптив ── */
@media(max-width:980px){
  .kpis{grid-template-columns:repeat(2,1fr)}
  .minis{grid-template-columns:repeat(2,1fr)}
  .grid2,.grid2b{grid-template-columns:1fr}
}
@media(max-width:560px){
  .topbar{padding:0 14px;height:56px}
  .topbar .sub{display:none}
  main{padding:16px 12px 40px}
  .kpi .val{font-size:26px}
}
</style></head>
<body>
  <div class="topbar">
    <div class="logo">🎥</div>
    <div>
      <h1>Kruzhok Bot</h1>
      <span class="sub" id="updated">загрузка…</span>
    </div>
    <div class="spacer"></div>
    <span class="pill"><span class="dot"></span> онлайн</span>
    <a href="/admin/logout"><button class="btn-ghost">Выйти</button></a>
  </div>

  <main>
    <div class="section-title">Обзор</div>
    <div class="kpis" id="kpis"></div>

    <div class="section-title">Активность</div>
    <div class="minis" id="minis"></div>

    <div class="section-title">Динамика</div>
    <div class="grid2">
      <div class="panel">
        <h2>Активность по дням</h2>
        <p class="hint">Загрузки и уникальные пользователи за 30 дней</p>
        <canvas id="chartDays"></canvas>
      </div>
      <div class="panel">
        <h2>Топ пользователей</h2>
        <p class="hint">По числу обработанных видео</p>
        <canvas id="chartTop"></canvas>
      </div>
    </div>

    <div class="grid2b" style="margin-top:16px">
      <div class="panel">
        <h2>Воронка подписки</h2>
        <p class="hint">Сколько дошло от /start до подтверждения</p>
        <canvas id="chartFunnel"></canvas>
      </div>
      <div class="panel">
        <h2>Ошибки</h2>
        <p class="hint">Распределение по причинам</p>
        <canvas id="chartErrors"></canvas>
      </div>
    </div>

    <div class="section-title">Пользователи</div>
    <div class="panel table-panel">
      <div class="scroll tbl-wrap"><table id="tblUsers">
        <thead><tr>
          <th data-k="user_id">ID</th><th>Пользователь</th>
          <th class="right" data-k="total_jobs">Всего</th>
          <th class="right" data-k="total_ok">OK</th>
          <th class="right" data-k="total_failed">Ошибок</th>
          <th data-k="last_seen">Последний раз</th>
        </tr></thead><tbody></tbody>
      </table></div>
    </div>

    <div class="section-title">Последние загрузки</div>
    <div class="panel table-panel">
      <div class="scroll tbl-wrap"><table id="tblJobs">
        <thead><tr>
          <th>Время</th><th>Пользователь</th><th>Файл</th><th>Тип</th>
          <th class="right">Вход</th><th class="right">Длит.</th>
          <th class="right">Выход</th><th>Статус</th><th class="right">Обработка</th>
        </tr></thead><tbody></tbody>
      </table></div>
    </div>
  </main>

<script>
const $ = s => document.querySelector(s);
const fmtBytes = b => { if(!b) return '—'; const u=['B','KB','MB','GB'];
  let i=0,n=b; while(n>=1024&&i<u.length-1){n/=1024;i++;} return n.toFixed(n<10&&i>0?1:0)+' '+u[i]; };
const fmtTime = ts => ts ? new Date(ts*1000).toLocaleString('ru-RU',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : '—';
const fmtName = r => [r.first_name, r.last_name].filter(Boolean).join(' ') || (r.username?'@'+r.username:'') || ('id'+r.user_id);
const fmtUn = r => r.username ? '@'+r.username : ('id '+r.user_id);
async function get(u){ const r=await fetch('/admin'+u); if(r.status===401){location.href='/admin/login';throw new Error('auth');}
  if(!r.ok) throw new Error(r.status); return r.json(); }

const GRID='#eef0f4', TICK='#9aa3b2';
const baseScale = extra => ({x:{grid:{display:false},ticks:{color:TICK}},
  y:{grid:{color:GRID},ticks:{color:TICK},beginAtZero:true},...extra});
let charts={};
const mk=(id,cfg)=>{ if(charts[id])charts[id].destroy(); charts[id]=new Chart($('#'+id),cfg); };

async function loadKpis(){
  const s = await get('/api/summary');
  const conv = s.sub_required ? Math.round(100*s.sub_confirmed/s.sub_required)+'%' : '—';
  $('#kpis').innerHTML = [
    ['Пользователей', s.total_users, '👥', 'accent', s.active_7d+' активны за 7 дней'],
    ['Всего загрузок', s.total_jobs, '🎬', '', s.jobs_24h+' за сутки'],
    ['Успешных', s.ok_jobs, '✅', '', s.total_jobs? Math.round(100*s.ok_jobs/s.total_jobs)+'% от всех':'—'],
    ['Трафик (вход)', fmtBytes(s.bytes_in), '📥', '', 'суммарно принято'],
  ].map(([l,v,ic,cls,d])=>`<div class="kpi ${cls}">
      <div class="ic">${ic}</div><div class="label">${l}</div>
      <div class="val">${v}</div><div class="delta">${d}</div></div>`).join('');

  $('#minis').innerHTML = [
    ['Активны 24ч', s.active_24h, ''],
    ['Загрузок 24ч', s.jobs_24h, ''],
    ['Ошибок', s.failed_jobs, s.failed_jobs?'bad':''],
    ['Команд /start', s.starts, ''],
    ['Конверсия подписки', conv, 'ok'],
  ].map(([l,v,c])=>`<div class="mini"><div class="label">${l}</div>
      <div class="val ${c}">${v}</div></div>`).join('');
  $('#updated').textContent = 'обновлено '+new Date().toLocaleTimeString('ru-RU');
  return s;
}

async function loadCharts(s){
  const ts = await get('/api/timeseries?days=30');
  mk('chartDays',{type:'line',
    data:{labels:ts.map(r=>r.d.slice(5)),datasets:[
      {label:'Загрузки',data:ts.map(r=>r.jobs),borderColor:'#4f46e5',
       backgroundColor:'rgba(79,70,229,.08)',fill:true,tension:.35,borderWidth:2,pointRadius:0},
      {label:'Пользователи',data:ts.map(r=>r.users),borderColor:'#16a34a',
       tension:.35,borderWidth:2,pointRadius:0},
    ]},
    options:{plugins:{legend:{labels:{color:TICK,usePointStyle:true,boxWidth:6}}},
      scales:baseScale(),interaction:{intersect:false,mode:'index'}}});

  const users = await get('/api/users?sort=total_jobs&limit=8');
  mk('chartTop',{type:'bar',
    data:{labels:users.map(fmtName),datasets:[{data:users.map(u=>u.total_jobs),
      backgroundColor:'#4f46e5',borderRadius:6,barThickness:14}]},
    options:{indexAxis:'y',plugins:{legend:{display:false}},
      scales:{x:{grid:{color:GRID},ticks:{color:TICK},beginAtZero:true},
              y:{grid:{display:false},ticks:{color:TICK}}}}});

  mk('chartFunnel',{type:'bar',
    data:{labels:['/start','Просили подписку','Подтвердили'],
      datasets:[{data:[s.starts,s.sub_required,s.sub_confirmed],
        backgroundColor:['#4f46e5','#d97706','#16a34a'],borderRadius:6,barThickness:38}]},
    options:{plugins:{legend:{display:false}},scales:baseScale()}});

  const errs = await get('/api/errors');
  mk('chartErrors',{type:'doughnut',
    data:{labels:errs.length?errs.map(e=>e.code):['нет ошибок'],
      datasets:[{data:errs.length?errs.map(e=>e.c):[1],
        backgroundColor:['#dc2626','#d97706','#db2777','#7c3aed','#4f46e5','#9aa3b2'],
        borderWidth:0}]},
    options:{cutout:'62%',plugins:{legend:{position:'right',
      labels:{color:TICK,usePointStyle:true,boxWidth:8,padding:12}}}}});
}

let usersData=[], usersSort='total_jobs';
async function loadUsers(){
  usersData = await get('/api/users?sort='+usersSort+'&limit=500');
  const tb = $('#tblUsers tbody');
  if(!usersData.length){ tb.innerHTML='<tr><td colspan="6" class="empty">Пока нет данных</td></tr>'; return; }
  tb.innerHTML = usersData.map(u=>`<tr>
    <td class="muted">${u.user_id}</td>
    <td><div class="user-cell"><span class="nm">${fmtName(u)}</span><span class="un">${fmtUn(u)}</span></div></td>
    <td class="right">${u.total_jobs}</td>
    <td class="right" style="color:var(--ok)">${u.total_ok}</td>
    <td class="right" style="color:${u.total_failed?'var(--bad)':'var(--faint)'}">${u.total_failed}</td>
    <td class="muted">${fmtTime(u.last_seen)}</td></tr>`).join('');
}
document.querySelectorAll('#tblUsers th[data-k]').forEach(th=>{
  th.onclick=()=>{ usersSort=th.dataset.k; loadUsers(); };
});

async function loadJobs(){
  const jobs = await get('/api/jobs?limit=200');
  const tb = $('#tblJobs tbody');
  if(!jobs.length){ tb.innerHTML='<tr><td colspan="9" class="empty">Пока нет загрузок</td></tr>'; return; }
  tb.innerHTML = jobs.map(j=>`<tr>
    <td class="muted">${fmtTime(j.ts)}</td>
    <td>${fmtName(j)}</td>
    <td>${j.file_name||'—'}</td>
    <td class="muted">${j.kind||'—'}</td>
    <td class="right">${fmtBytes(j.in_size_bytes)}</td>
    <td class="right">${j.in_duration_sec?Math.round(j.in_duration_sec)+'с':'—'}</td>
    <td class="right">${fmtBytes(j.out_size_bytes)}</td>
    <td><span class="badge ${j.status==='ok'?'ok':'bad'}">${j.status==='ok'?'ok':(j.error_code||j.status)}</span></td>
    <td class="right muted">${j.processing_ms?(j.processing_ms/1000).toFixed(1)+'с':'—'}</td></tr>`).join('');
}

async function refresh(){
  try{ const s=await loadKpis(); await Promise.all([loadCharts(s),loadUsers(),loadJobs()]); }
  catch(e){ if(e.message!=='auth') $('#updated').textContent='ошибка обновления'; }
}
refresh();
setInterval(refresh, 30000);
</script>
</body></html>
"""
