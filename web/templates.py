"""HTML публичного веб-конвертера. Мобильный-first, один экран."""

CONVERTER_HTML = r"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1">
<meta name="theme-color" content="#4f46e5">
<title>Видеокружок онлайн</title>
<style>
:root{
  --bg:#f5f7fb; --surface:#fff; --border:#e6e9f0;
  --fg:#1a2233; --muted:#6b7689; --faint:#9aa3b2;
  --accent:#4f46e5; --accent2:#7c3aed; --accent-soft:#eef0fe;
  --ok:#16a34a; --bad:#dc2626; --bad-soft:#fdecec;
  --radius:16px; --shadow:0 10px 30px rgba(16,24,40,.10);
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,system-ui,sans-serif;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0}
body{font-family:var(--font);color:var(--fg);font-size:15px;line-height:1.5;
  min-height:100dvh;
  padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
  background:
    radial-gradient(900px 480px at 90% -10%, rgba(124,58,237,.12), transparent),
    radial-gradient(700px 420px at -10% 10%, rgba(79,70,229,.10), transparent),
    var(--bg);}
.wrap{max-width:460px;margin:0 auto;padding:28px 18px 40px;
  min-height:100dvh;display:flex;flex-direction:column}
.hero{text-align:center;margin-bottom:22px}
.logo{width:60px;height:60px;border-radius:18px;margin:0 auto 14px;display:grid;place-items:center;
  font-size:30px;background:linear-gradient(135deg,var(--accent),var(--accent2));
  box-shadow:0 10px 24px rgba(79,70,229,.35)}
.hero h1{margin:0 0 6px;font-size:23px;font-weight:750;letter-spacing:-.02em}
.hero p{margin:0;color:var(--muted);font-size:14px}

.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:18px;flex:1;display:flex;flex-direction:column;gap:16px}

/* зона загрузки */
.drop{border:2px dashed #cdd3e0;border-radius:var(--radius);background:#fbfcff;
  padding:30px 18px;text-align:center;cursor:pointer;transition:.18s;
  display:flex;flex-direction:column;align-items:center;gap:10px}
.drop:hover,.drop.drag{border-color:var(--accent);background:var(--accent-soft)}
.drop .ic{font-size:36px}
.drop .t{font-weight:650;font-size:15px}
.drop .s{color:var(--faint);font-size:13px}
input[type=file]{display:none}

/* выбранный файл */
.file{display:none;align-items:center;gap:12px;background:#fbfcff;
  border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.file .fic{font-size:22px}
.file .meta{flex:1;min-width:0}
.file .nm{font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.file .sz{color:var(--faint);font-size:12.5px}
.file .x{color:var(--faint);font-size:20px;padding:4px;cursor:pointer}

/* кнопка */
.btn{appearance:none;border:none;font-family:inherit;font-size:16px;font-weight:650;
  padding:15px;border-radius:13px;cursor:pointer;color:#fff;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  transition:filter .15s,transform .05s,opacity .15s;width:100%}
.btn:hover{filter:brightness(1.07)}
.btn:active{transform:translateY(1px)}
.btn:disabled{opacity:.45;cursor:not-allowed;filter:none}

/* прогресс */
.progress{display:none;text-align:center}
.bar{height:8px;background:#eef0f4;border-radius:99px;overflow:hidden;margin:14px 0 8px}
.bar > i{display:block;height:100%;width:0;border-radius:99px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .2s}
.spinner{width:30px;height:30px;border:3px solid var(--accent-soft);
  border-top-color:var(--accent);border-radius:50%;margin:6px auto;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.progress .lbl{color:var(--muted);font-size:14px}

/* результат */
.result{display:none;text-align:center}
.circle{width:230px;max-width:72vw;aspect-ratio:1;margin:4px auto 16px;border-radius:50%;
  overflow:hidden;background:#000;box-shadow:0 14px 36px rgba(16,24,40,.22);
  border:4px solid #fff}
.circle video{width:100%;height:100%;object-fit:cover;display:block}
.result .ok-t{color:var(--ok);font-weight:650;margin-bottom:14px;font-size:15px}
.row{display:flex;gap:10px}
.btn.ghost{background:#fff;color:var(--accent);border:1.5px solid var(--border)}
.btn.ghost:hover{filter:none;background:var(--accent-soft)}

/* ошибка */
.error{display:none;background:var(--bad-soft);color:var(--bad);font-weight:500;
  font-size:14px;padding:12px 14px;border-radius:12px;text-align:center}

.note{color:var(--faint);font-size:12.5px;text-align:center;line-height:1.7}
.foot{margin-top:18px;text-align:center;color:var(--faint);font-size:12px}
.foot a{color:var(--muted)}
</style></head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="logo">🎥</div>
      <h1>Видеокружок онлайн</h1>
      <p>Загрузите видео — получите кружок для Telegram</p>
    </div>

    <div class="card">
      <!-- выбор файла -->
      <label class="drop" id="drop">
        <div class="ic">📁</div>
        <div class="t">Выберите видео</div>
        <div class="s">или перетащите файл сюда</div>
        <input type="file" id="file" accept="video/*">
      </label>

      <div class="file" id="fileBox">
        <span class="fic">🎬</span>
        <div class="meta">
          <div class="nm" id="fileName">—</div>
          <div class="sz" id="fileSize"></div>
        </div>
        <span class="x" id="fileClear">✕</span>
      </div>

      <button class="btn" id="go" disabled>Сделать кружок</button>

      <!-- прогресс -->
      <div class="progress" id="progress">
        <div class="spinner" id="spin" style="display:none"></div>
        <div class="bar" id="barWrap"><i id="bar"></i></div>
        <div class="lbl" id="progLbl">Загрузка…</div>
      </div>

      <!-- ошибка -->
      <div class="error" id="error"></div>

      <!-- результат -->
      <div class="result" id="result">
        <div class="ok-t">✅ Готово!</div>
        <div class="circle"><video id="preview" playsinline autoplay muted loop></video></div>
        <div class="row">
          <a class="btn" id="download" download="kruzhok.mp4">Скачать</a>
          <button class="btn ghost" id="again">Ещё</button>
        </div>
      </div>

      <div class="note" id="note">
        Квадрат 512×512 · до 60 сек · до {{MAX_MB}} МБ<br>
        Длиннее 60 сек — возьмём первые 60 секунд
      </div>
    </div>

    <div class="foot">Powered by FFmpeg · <a href="/admin">админка</a></div>
  </div>

<script>
const $=s=>document.getElementById(s);
const fmtSize=b=>{const u=['B','KB','MB','GB'];let i=0,n=b;while(n>=1024&&i<3){n/=1024;i++;}return n.toFixed(i?1:0)+' '+u[i];};
let chosen=null, blobUrl=null;

const drop=$('drop'), fileInput=$('file');
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('drag');}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('drag');}));
drop.addEventListener('drop',ev=>{ if(ev.dataTransfer.files[0]) setFile(ev.dataTransfer.files[0]); });
fileInput.addEventListener('change',()=>{ if(fileInput.files[0]) setFile(fileInput.files[0]); });

function setFile(f){
  if(!f.type.startsWith('video/')){ showError('Это не видеофайл.'); return; }
  chosen=f;
  $('fileName').textContent=f.name;
  $('fileSize').textContent=fmtSize(f.size);
  $('fileBox').style.display='flex';
  $('drop').style.display='none';
  $('go').disabled=false;
  hideError(); hideResult();
}
$('fileClear').addEventListener('click',resetFile);
function resetFile(){
  chosen=null; fileInput.value='';
  $('fileBox').style.display='none';
  $('drop').style.display='flex';
  $('go').disabled=true;
}

function showError(m){ const e=$('error'); e.textContent=m; e.style.display='block'; }
function hideError(){ $('error').style.display='none'; }
function hideResult(){ $('result').style.display='none'; }
function setProgress(show,label,pct,spin){
  $('progress').style.display=show?'block':'none';
  if(label!==undefined) $('progLbl').textContent=label;
  if(pct!==undefined){ $('barWrap').style.display=pct<0?'none':'block'; if(pct>=0)$('bar').style.width=pct+'%'; }
  $('spin').style.display=spin?'block':'none';
}

$('go').addEventListener('click',()=>{
  if(!chosen) return;
  hideError(); hideResult();
  $('go').disabled=true; $('go').style.display='none';
  $('drop').style.display='none';
  setProgress(true,'Загрузка… 0%',0,false);

  const fd=new FormData(); fd.append('file',chosen);
  const xhr=new XMLHttpRequest();
  xhr.open('POST','/api/convert');
  xhr.responseType='blob';
  xhr.upload.onprogress=e=>{
    if(e.lengthComputable){
      const p=Math.round(e.loaded/e.total*100);
      setProgress(true,'Загрузка… '+p+'%',p,false);
      if(p>=100) setProgress(true,'Конвертирую видео…',-1,true);
    }
  };
  xhr.onload=()=>{
    if(xhr.status===200){
      if(blobUrl) URL.revokeObjectURL(blobUrl);
      blobUrl=URL.createObjectURL(xhr.response);
      $('preview').src=blobUrl;
      $('download').href=blobUrl;
      setProgress(false);
      $('result').style.display='block';
      $('note').style.display='none';
    } else {
      let msg='Ошибка конвертации.';
      const r=new FileReader();
      r.onload=()=>{ try{ msg=JSON.parse(r.result).detail||msg; }catch(_){ } finishErr(msg); };
      r.onerror=()=>finishErr(msg);
      r.readAsText(xhr.response);
    }
  };
  xhr.onerror=()=>finishErr('Сеть недоступна. Попробуйте ещё раз.');
  xhr.send(fd);
});

function finishErr(msg){
  setProgress(false); showError(msg);
  $('go').style.display='block'; $('go').disabled=false;
  $('note').style.display='block';
}

$('again').addEventListener('click',()=>{
  hideResult(); resetFile();
  $('go').style.display='block';
  $('note').style.display='block';
  $('drop').style.display='flex';
});
</script>
</body></html>
"""
