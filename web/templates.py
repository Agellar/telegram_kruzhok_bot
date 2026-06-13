"""HTML публичного веб-конвертера. Мобильный-first, мультиязычный (5 языков),
со ссылкой на Telegram-бота."""

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
  --tg:#229ed9;
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
.wrap{max-width:460px;margin:0 auto;padding:18px 18px 40px;
  min-height:100dvh;display:flex;flex-direction:column}

/* переключатель языка */
.langbar{display:flex;justify-content:flex-end;margin-bottom:6px}
.lang{appearance:none;font-family:inherit;font-size:13px;color:var(--muted);
  background:#fff;border:1px solid var(--border);border-radius:999px;
  padding:7px 30px 7px 12px;cursor:pointer;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath fill='%236b7689' d='M0 0l5 6 5-6z'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 12px center}

.hero{text-align:center;margin-bottom:18px}
.logo{width:60px;height:60px;border-radius:18px;margin:0 auto 14px;display:grid;place-items:center;
  font-size:30px;background:linear-gradient(135deg,var(--accent),var(--accent2));
  box-shadow:0 10px 24px rgba(79,70,229,.35)}
.hero h1{margin:0 0 6px;font-size:23px;font-weight:750;letter-spacing:-.02em}
.hero p{margin:0;color:var(--muted);font-size:14px}

.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:18px;display:flex;flex-direction:column;gap:16px}

.drop{border:2px dashed #cdd3e0;border-radius:var(--radius);background:#fbfcff;
  padding:30px 18px;text-align:center;cursor:pointer;transition:.18s;
  display:flex;flex-direction:column;align-items:center;gap:10px}
.drop:hover,.drop.drag{border-color:var(--accent);background:var(--accent-soft)}
.drop .ic{font-size:36px}
.drop .t{font-weight:650;font-size:15px}
.drop .s{color:var(--faint);font-size:13px}
input[type=file]{display:none}

.file{display:none;align-items:center;gap:12px;background:#fbfcff;
  border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.file .fic{font-size:22px}
.file .meta{flex:1;min-width:0}
.file .nm{font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.file .sz{color:var(--faint);font-size:12.5px}
.file .x{color:var(--faint);font-size:20px;padding:4px;cursor:pointer}

.btn{appearance:none;border:none;font-family:inherit;font-size:16px;font-weight:650;
  padding:15px;border-radius:13px;cursor:pointer;color:#fff;text-decoration:none;
  text-align:center;display:block;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  transition:filter .15s,transform .05s,opacity .15s;width:100%}
.btn:hover{filter:brightness(1.07)}
.btn:active{transform:translateY(1px)}
.btn:disabled{opacity:.45;cursor:not-allowed;filter:none}

.progress{display:none;text-align:center}
.bar{height:8px;background:#eef0f4;border-radius:99px;overflow:hidden;margin:14px 0 8px}
.bar > i{display:block;height:100%;width:0;border-radius:99px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .2s}
.spinner{width:30px;height:30px;border:3px solid var(--accent-soft);
  border-top-color:var(--accent);border-radius:50%;margin:6px auto;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.progress .lbl{color:var(--muted);font-size:14px}

.result{display:none;text-align:center}
.circle{width:230px;max-width:72vw;aspect-ratio:1;margin:4px auto 14px;border-radius:50%;
  overflow:hidden;background:#000;box-shadow:0 14px 36px rgba(16,24,40,.22);border:4px solid #fff}
.circle video{width:100%;height:100%;object-fit:cover;display:block}
.result .ok-t{color:var(--ok);font-weight:650;margin-bottom:12px;font-size:15px}
.row{display:flex;gap:10px}
.btn.ghost{background:#fff;color:var(--accent);border:1.5px solid var(--border)}
.btn.ghost:hover{filter:none;background:var(--accent-soft)}

.error{display:none;background:var(--bad-soft);color:var(--bad);font-weight:500;
  font-size:14px;padding:12px 14px;border-radius:12px;text-align:center}

.note{color:var(--faint);font-size:12.5px;text-align:center;line-height:1.7}

/* блок с ботом */
.botcard{margin-top:14px;background:#fff;border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:16px;text-align:center}
.botcard .bt{font-size:13.5px;color:var(--muted);margin-bottom:12px}
.btn.tg{background:var(--tg);display:flex;align-items:center;justify-content:center;gap:8px}
.btn.tg:hover{filter:brightness(1.06)}

.foot{margin-top:16px;text-align:center;color:var(--faint);font-size:12px}
.foot a{color:var(--muted)}
</style></head>
<body>
  <div class="wrap">
    <div class="langbar">
      <select class="lang" id="lang">
        <option value="ru">Русский</option>
        <option value="en">English</option>
        <option value="es">Español</option>
        <option value="pt">Português</option>
        <option value="zh">中文</option>
      </select>
    </div>

    <div class="hero">
      <div class="logo">🎥</div>
      <h1 id="t_title">Видеокружок онлайн</h1>
      <p id="t_subtitle">Загрузите видео — получите кружок для Telegram</p>
    </div>

    <div class="card">
      <label class="drop" id="drop">
        <div class="ic">📁</div>
        <div class="t" id="t_choose">Выберите видео</div>
        <div class="s" id="t_drag">или перетащите файл сюда</div>
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

      <div class="progress" id="progress">
        <div class="spinner" id="spin" style="display:none"></div>
        <div class="bar" id="barWrap"><i id="bar"></i></div>
        <div class="lbl" id="progLbl"></div>
      </div>

      <div class="error" id="error"></div>

      <div class="result" id="result">
        <div class="ok-t" id="t_done">✅ Готово!</div>
        <div class="circle"><video id="preview" playsinline autoplay muted loop></video></div>
        <div class="row">
          <a class="btn" id="download" download="kruzhok.mp4">Скачать</a>
          <button class="btn ghost" id="again">Ещё</button>
        </div>
      </div>

      <div class="note">
        <span id="t_note1"></span><br>
        <span id="t_note2"></span>
      </div>
    </div>

    <div class="botcard">
      <div class="bt" id="t_botcta"></div>
      <a class="btn tg" href="https://t.me/kruzhok_clup_bot" target="_blank" rel="noopener">
        <span>✈️</span><span id="t_botbtn"></span>
      </a>
    </div>

    <div class="foot">Powered by FFmpeg · <a href="/admin" id="t_admin">админка</a></div>
  </div>

<script>
const MAX_MB = {{MAX_MB}};
const $=id=>document.getElementById(id);

/* ─── переводы ─── */
const I18N = {
  ru:{title:"Видеокружок онлайн",subtitle:"Загрузите видео — получите кружок для Telegram",
    choose:"Выберите видео",drag:"или перетащите файл сюда",go:"Сделать кружок",
    uploading:"Загрузка…",converting:"Конвертирую видео…",done:"✅ Готово!",
    download:"Скачать",again:"Ещё",
    note1:"Квадрат 512×512 · до 60 сек · до "+MAX_MB+" МБ",
    note2:"Файл квадратный — Telegram сделает его круглым при отправке как видеокружок",
    botcta:"Хотите отправить настоящим кружком? Это умеет наш бот в Telegram:",
    botbtn:"Открыть бота @kruzhok_clup_bot",admin:"админка",
    e_notvideo:"Это не видеофайл",e_net:"Сеть недоступна. Попробуйте ещё раз",
    e_toobig:"Файл слишком большой (макс. "+MAX_MB+" МБ)",
    e_often:"Слишком часто. Подождите немного",e_busy:"Сервер занят, попробуйте позже",
    e_convert:"Не удалось сконвертировать. Попробуйте другой файл",
    e_generic:"Ошибка. Попробуйте ещё раз"},
  en:{title:"Video Note Online",subtitle:"Upload a video — get a Telegram video circle",
    choose:"Choose a video",drag:"or drag a file here",go:"Make a circle",
    uploading:"Uploading…",converting:"Converting video…",done:"✅ Done!",
    download:"Download",again:"Again",
    note1:"Square 512×512 · up to 60 sec · up to "+MAX_MB+" MB",
    note2:"The file is square — Telegram rounds it when sent as a video note",
    botcta:"Want to send a real round video note? Our Telegram bot does that:",
    botbtn:"Open bot @kruzhok_clup_bot",admin:"admin",
    e_notvideo:"Not a video file",e_net:"Network error. Please try again",
    e_toobig:"File too large (max "+MAX_MB+" MB)",
    e_often:"Too often. Please wait a moment",e_busy:"Server busy, try again later",
    e_convert:"Conversion failed. Try another file",
    e_generic:"Something went wrong. Try again"},
  es:{title:"Videocírculo en línea",subtitle:"Sube un vídeo y obtén un círculo para Telegram",
    choose:"Elige un vídeo",drag:"o arrastra un archivo aquí",go:"Crear círculo",
    uploading:"Subiendo…",converting:"Convirtiendo vídeo…",done:"✅ ¡Listo!",
    download:"Descargar",again:"Otra vez",
    note1:"Cuadrado 512×512 · hasta 60 s · hasta "+MAX_MB+" MB",
    note2:"El archivo es cuadrado — Telegram lo redondea al enviarlo como nota de vídeo",
    botcta:"¿Quieres enviar un círculo real? Nuestro bot de Telegram lo hace:",
    botbtn:"Abrir bot @kruzhok_clup_bot",admin:"panel",
    e_notvideo:"No es un archivo de vídeo",e_net:"Error de red. Inténtalo de nuevo",
    e_toobig:"Archivo demasiado grande (máx. "+MAX_MB+" MB)",
    e_often:"Demasiado seguido. Espera un momento",e_busy:"Servidor ocupado, inténtalo luego",
    e_convert:"Error de conversión. Prueba otro archivo",
    e_generic:"Algo salió mal. Inténtalo de nuevo"},
  pt:{title:"Vídeo redondo online",subtitle:"Envie um vídeo e receba um círculo para o Telegram",
    choose:"Escolha um vídeo",drag:"ou arraste um arquivo aqui",go:"Criar círculo",
    uploading:"Enviando…",converting:"Convertendo vídeo…",done:"✅ Pronto!",
    download:"Baixar",again:"De novo",
    note1:"Quadrado 512×512 · até 60 s · até "+MAX_MB+" MB",
    note2:"O arquivo é quadrado — o Telegram arredonda ao enviar como nota de vídeo",
    botcta:"Quer enviar um círculo de verdade? Nosso bot do Telegram faz isso:",
    botbtn:"Abrir bot @kruzhok_clup_bot",admin:"painel",
    e_notvideo:"Não é um arquivo de vídeo",e_net:"Erro de rede. Tente novamente",
    e_toobig:"Arquivo muito grande (máx. "+MAX_MB+" MB)",
    e_often:"Muito rápido. Aguarde um momento",e_busy:"Servidor ocupado, tente mais tarde",
    e_convert:"Falha na conversão. Tente outro arquivo",
    e_generic:"Algo deu errado. Tente novamente"},
  zh:{title:"在线视频圆圈",subtitle:"上传视频，生成 Telegram 圆形视频",
    choose:"选择视频",drag:"或将文件拖到这里",go:"生成圆圈",
    uploading:"上传中…",converting:"正在转换视频…",done:"✅ 完成！",
    download:"下载",again:"再来一个",
    note1:"正方形 512×512 · 最长 60 秒 · 最大 "+MAX_MB+" MB",
    note2:"文件是正方形的 — 作为视频留言发送时 Telegram 会自动变圆",
    botcta:"想发送真正的圆形视频留言？我们的 Telegram 机器人可以做到：",
    botbtn:"打开机器人 @kruzhok_clup_bot",admin:"后台",
    e_notvideo:"这不是视频文件",e_net:"网络错误，请重试",
    e_toobig:"文件太大（最大 "+MAX_MB+" MB）",
    e_often:"太频繁了，请稍候",e_busy:"服务器繁忙，请稍后再试",
    e_convert:"转换失败，请换一个文件",
    e_generic:"出错了，请重试"},
};

let lang = (()=>{
  const saved = localStorage.getItem('lang');
  if(saved && I18N[saved]) return saved;
  const nav = (navigator.language||'en').slice(0,2).toLowerCase();
  return I18N[nav] ? nav : 'en';
})();

function t(k){ return (I18N[lang]||I18N.en)[k]; }

function applyLang(){
  document.documentElement.lang = lang;
  document.title = t('title');
  $('lang').value = lang;
  $('t_title').textContent=t('title');
  $('t_subtitle').textContent=t('subtitle');
  $('t_choose').textContent=t('choose');
  $('t_drag').textContent=t('drag');
  $('go').textContent=t('go');
  $('t_done').textContent=t('done');
  $('download').textContent=t('download');
  $('again').textContent=t('again');
  $('t_note1').textContent=t('note1');
  $('t_note2').textContent=t('note2');
  $('t_botcta').textContent=t('botcta');
  $('t_botbtn').textContent=t('botbtn');
  $('t_admin').textContent=t('admin');
}
$('lang').addEventListener('change',e=>{ lang=e.target.value; localStorage.setItem('lang',lang); applyLang(); });
applyLang();

/* ─── логика ─── */
const fmtSize=b=>{const u=['B','KB','MB','GB'];let i=0,n=b;while(n>=1024&&i<3){n/=1024;i++;}return n.toFixed(i?1:0)+' '+u[i];};
let chosen=null, blobUrl=null;

const drop=$('drop'), fileInput=$('file');
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('drag');}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('drag');}));
drop.addEventListener('drop',ev=>{ if(ev.dataTransfer.files[0]) setFile(ev.dataTransfer.files[0]); });
fileInput.addEventListener('change',()=>{ if(fileInput.files[0]) setFile(fileInput.files[0]); });

function setFile(f){
  if(!f.type.startsWith('video/')){ showError(t('e_notvideo')); return; }
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
function errByStatus(s){
  if(s===413) return t('e_toobig');
  if(s===429) return t('e_often');
  if(s===503) return t('e_busy');
  if(s===415) return t('e_notvideo');
  if(s===422) return t('e_convert');
  return t('e_generic');
}

$('go').addEventListener('click',()=>{
  if(!chosen) return;
  hideError(); hideResult();
  $('go').disabled=true; $('go').style.display='none';
  $('drop').style.display='none';
  setProgress(true,t('uploading')+' 0%',0,false);

  const fd=new FormData(); fd.append('file',chosen);
  const xhr=new XMLHttpRequest();
  xhr.open('POST','/api/convert?lang='+encodeURIComponent(lang));
  xhr.responseType='blob';
  xhr.upload.onprogress=e=>{
    if(e.lengthComputable){
      const p=Math.round(e.loaded/e.total*100);
      setProgress(true,t('uploading')+' '+p+'%',p,false);
      if(p>=100) setProgress(true,t('converting'),-1,true);
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
    } else {
      finishErr(errByStatus(xhr.status));
    }
  };
  xhr.onerror=()=>finishErr(t('e_net'));
  xhr.send(fd);
});

function finishErr(msg){
  setProgress(false); showError(msg);
  $('go').style.display='block'; $('go').disabled=false;
}

$('again').addEventListener('click',()=>{
  hideResult(); resetFile();
  $('go').style.display='block';
  $('drop').style.display='flex';
});
</script>
</body></html>
"""
