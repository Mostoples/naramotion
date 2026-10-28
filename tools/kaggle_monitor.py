"""Web pemantau kernel Kaggle NaraMotion (lokal; API key tetap di ~/.kaggle/kaggle.json).

Pemakaian:  python tools/kaggle_monitor.py [--port 8765]   lalu buka http://localhost:8765
- Status semua kernel ber-slug "naramotion" diperiksa tiap 60 s lewat Kaggle CLI.
- Waktu mulai dicatat di ml/runs/monitor_state.json (Kaggle tidak memperbarui lastRunTime selama berjalan).
- Saat kernel COMPLETE/ERROR, keluaran otomatis diunduh ke ml/runs/<nama-kernel>/ lalu log, pratinjau,
  dan metrics.json ditampilkan.
"""
import json, os, re, shutil, subprocess, sys, threading, time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "ml" / "runs"; RUNS.mkdir(parents=True, exist_ok=True)
STATE_F = RUNS / "monitor_state.json"
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
KAGGLE = shutil.which("kaggle") or str(Path(sys.executable).parent / "Scripts" / "kaggle.exe")
if not Path(KAGGLE).exists():
    import sysconfig; KAGGLE = str(Path(sysconfig.get_path("scripts", f"{os.name}_user")) / ("kaggle.exe" if os.name == "nt" else "kaggle"))
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
# Perkiraan durasi per kernel (menit) untuk bilah perkiraan; bukan progres sungguhan.
EXPECT = {"naramotion-pose-extract": (120, 210), "naramotion-train-gesture": (10, 25)}

lock = threading.Lock()
state = json.loads(STATE_F.read_text("utf-8")) if STATE_F.exists() else {}
snapshot = {"kernels": [], "checked": None, "error": None}

def save_state(): STATE_F.write_text(json.dumps(state, indent=1), "utf-8")

def kaggle(*args, timeout=120):
    r = subprocess.run([KAGGLE, *args], capture_output=True, text=True, env=ENV, timeout=timeout, encoding="utf-8", errors="replace")
    return "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "warn" not in l.lower())

def download(ref, name):
    out = RUNS / name
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    kaggle("kernels", "output", ref, "-p", str(out), timeout=1800)
    with lock: state[name]["downloaded"] = datetime.now().isoformat(timespec="seconds"); save_state()

def summarise(name):
    """Ringkasan dari folder hasil unduhan: ekor log, fps, pratinjau, metrik."""
    d = RUNS / name; res = {}
    if not d.exists(): return res
    log = d / "log.txt"
    if log.exists():
        lines = log.read_text("utf-8", errors="replace").replace("Â·", "·").splitlines()
        res["log"] = lines[-14:]
        fps = [float(m.group(1)) for l in lines for m in [re.search(r"([\d.]+) fps", l)] if m]
        if fps: res["fps"] = fps[-1]
        done = [l for l in lines if l.startswith("SELESAI")]
        if done: res["done"] = done[-1]
    res["previews"] = sorted(f"{name}/preview/{p.name}" for p in (d / "preview").glob("*.jpg")) if (d / "preview").exists() else []
    if (d / "metrics.json").exists(): res["metrics"] = json.loads((d / "metrics.json").read_text("utf-8"))
    if (d / "confusion.png").exists(): res["confusion"] = f"{name}/confusion.png"
    res["files"] = sorted(f"{p.relative_to(d).as_posix()} · {p.stat().st_size / 1e6:.1f} MB" for p in d.rglob("*") if p.is_file() and p.suffix in (".npz", ".onnx", ".pt", ".json"))
    return res

def poll():
    while True:
        try:
            rows = kaggle("kernels", "list", "--mine", "--csv").splitlines()
            refs = [r.split(",")[0] for r in rows[1:] if "naramotion" in r.split(",")[0]]
            ks = []
            for ref in refs:
                name = ref.split("/")[1]
                m = re.search(r"KernelWorkerStatus\.([A-Z_]+)", kaggle("kernels", "status", ref))
                st = m.group(1) if m else "TIDAK DIKETAHUI"
                now = datetime.now()
                with lock:
                    s = state.setdefault(name, {})
                    if st in ("RUNNING", "QUEUED") and s.get("status") not in ("RUNNING", "QUEUED"):
                        s["started"] = s.get("started_hint") or now.isoformat(timespec="seconds"); s.pop("started_hint", None)
                        s.pop("finished", None); s.pop("downloaded", None)
                    if st in ("COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED") and not s.get("finished"):
                        s["finished"] = now.isoformat(timespec="seconds")
                    s["status"] = st; save_state(); s = dict(s)
                if st in ("COMPLETE", "ERROR") and not s.get("downloaded"):
                    threading.Thread(target=download, args=(ref, name), daemon=True).start()
                start = datetime.fromisoformat(s["started"]) if s.get("started") else None
                end = datetime.fromisoformat(s["finished"]) if s.get("finished") else now
                ks.append(dict(ref=ref, name=name, status=st, started=s.get("started"), finished=s.get("finished"),
                               elapsed=round((end - start).total_seconds() / 60, 1) if start else None,
                               expect=EXPECT.get(name), downloaded=s.get("downloaded"),
                               url=f"https://www.kaggle.com/code/{ref}", result=summarise(name)))
            with lock: snapshot.update(kernels=ks, checked=datetime.now().isoformat(timespec="seconds"), error=None)
        except Exception as e:
            with lock: snapshot.update(error=str(e), checked=datetime.now().isoformat(timespec="seconds"))
        time.sleep(60)

PAGE = r"""<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pemantau Kaggle · NaraMotion</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Spectral:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--ink:#1b150d;--surface:#1e170e;--line:rgba(210,165,74,.18);--gold:#d2a54a;--gold-b:#ecc978;--pale:#f6e4b4;--cream:#ebe0c6;--muted:#a9987a;--dim:#76674c;--ok:#a3c476;--warn:#e0a645;--bad:#d66a4b}
*{box-sizing:border-box}body{margin:0;background:var(--ink);color:var(--cream);font:16px/1.5 Spectral,Georgia,serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 16px 60px}
h1{font:700 28px/1.1 Cinzel,serif;color:var(--gold-b);margin:0 0 4px}.sub{color:var(--muted);font:500 12px IBM Plex Mono,monospace;letter-spacing:.1em;text-transform:uppercase}
.card{background:linear-gradient(145deg,rgba(255,216,150,.05),rgba(0,0,0,.18)),var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px;margin-top:18px;box-shadow:6px 6px 14px rgba(0,0,0,.55),-4px -4px 12px rgba(255,216,150,.04)}
.head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap}
h2{font:600 19px Cinzel,serif;color:var(--gold-b);margin:0}h2 a{color:inherit;text-decoration:none}
.badge{font:500 12px IBM Plex Mono,monospace;padding:4px 10px;border-radius:99px;border:1px solid currentColor}
.RUNNING,.QUEUED{color:var(--warn)}.COMPLETE{color:var(--ok)}.ERROR,.CANCEL_ACKNOWLEDGED{color:var(--bad)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:currentColor;margin-right:6px;vertical-align:1px}
.RUNNING .dot{animation:p 1.4s infinite}@keyframes p{50%{opacity:.25}}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.meta div{background:rgba(0,0,0,.2);border-radius:10px;padding:8px 10px}.meta b{display:block;font:600 18px IBM Plex Mono,monospace;color:var(--pale)}.meta span{font-size:12px;color:var(--muted)}
.bar{height:10px;border-radius:99px;background:rgba(0,0,0,.35);overflow:hidden;position:relative}.bar i{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,var(--gold),var(--gold-b));border-radius:99px}
.bar em{position:absolute;top:0;bottom:0;background:rgba(236,201,120,.18)}
.note{font-size:13px;color:var(--dim);margin-top:6px}
pre{background:rgba(0,0,0,.3);border-radius:10px;padding:10px;font:12px/1.45 IBM Plex Mono,monospace;color:var(--cream);white-space:pre-wrap;max-height:260px;overflow:auto}
.prev{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}.prev img,.conf{width:100%;border-radius:8px;border:1px solid var(--line)}
table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:4px 6px;border-bottom:1px solid var(--line);text-align:left}th{color:var(--muted);font-weight:500}
.foot{margin-top:18px;color:var(--dim);font-size:13px}.err{color:var(--bad)}
</style></head><body><div class="wrap">
<h1>Pemantau Kaggle</h1><div class="sub">NaraMotion · ekstraksi pose &amp; pelatihan gerak</div>
<div id="list"></div><div class="foot" id="foot"></div></div>
<script>
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const t=iso=>iso?new Date(iso).toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit'}):'—';
function card(k){
  const r=k.result||{}, ex=k.expect, run=k.status==='RUNNING'||k.status==='QUEUED';
  let bar='';
  if(ex&&k.elapsed!=null){const max=ex[1]*1.15, w=Math.min(100,k.elapsed/max*100);
    bar=`<div class="bar"><em style="left:${ex[0]/max*100}%;width:${(ex[1]-ex[0])/max*100}%"></em><i style="width:${k.status==='COMPLETE'?100:w}%"></i></div>
    <div class="note">${run?`Perkiraan selesai antara ${t(new Date(new Date(k.started).getTime()+ex[0]*6e4))} dan ${t(new Date(new Date(k.started).getTime()+ex[1]*6e4))} (pita terang). Bilah = waktu berjalan, bukan progres sebenarnya — Kaggle tidak membuka log sebelum selesai.`:''}</div>`;}
  let res='';
  if(r.done) res+=`<p><b style="color:var(--ok)">${esc(r.done)}</b>${r.fps?` · ${r.fps} fps`:''}</p>`;
  if(r.metrics){const m=r.metrics;res+=`<div class="meta"><div><b>${(m.test_acc*100).toFixed(1)}%</b><span>akurasi uji</span></div><div><b>${(m.val_best*100).toFixed(1)}%</b><span>akurasi validasi terbaik</span></div></div>
    <table><tr><th>Gerak</th><th>Akurasi uji</th></tr>${Object.entries(m.per_class).map(([c,v])=>`<tr><td>${esc(c.replace('_',' '))}</td><td>${(v*100).toFixed(0)}%</td></tr>`).join('')}</table>`;}
  if(r.confusion) res+=`<p><img class="conf" src="/runs/${r.confusion}" alt="Confusion matrix"></p>`;
  if(r.log) res+=`<pre>${esc(r.log.join('\n'))}</pre>`;
  if(r.previews&&r.previews.length) res+=`<div class="prev">${r.previews.map(p=>`<img src="/runs/${p}" alt="" loading="lazy">`).join('')}</div>`;
  if(r.files&&r.files.length) res+=`<p class="note">Berkas: ${r.files.map(esc).join(' · ')}</p>`;
  if(!run&&k.status!=='COMPLETE'&&k.status!=='ERROR'&&!res) res='';
  if((k.status==='COMPLETE'||k.status==='ERROR')&&!k.downloaded) res+=`<p class="note">Mengunduh keluaran…</p>`;
  return `<section class="card"><div class="head"><h2><a href="${k.url}" target="_blank" rel="noopener">${esc(k.name)}</a></h2>
    <span class="badge ${k.status}"><span class="dot"></span>${esc(k.status)}</span></div>
    <div class="meta"><div><b>${t(k.started)}</b><span>mulai</span></div><div><b>${k.elapsed!=null?k.elapsed+' mnt':'—'}</b><span>${run?'sudah berjalan':'durasi'}</span></div>
    <div><b>${t(k.finished)}</b><span>selesai</span></div></div>${bar}${res}</section>`;
}
async function tick(){
  try{const s=await (await fetch('/api/status')).json();
    $('#list').innerHTML=s.kernels.length?s.kernels.map(card).join(''):'<section class="card">Memeriksa Kaggle…</section>';
    $('#foot').innerHTML=`Diperiksa ${t(s.checked)} · otomatis tiap 60 detik${s.error?` · <span class="err">${esc(s.error)}</span>`:''}`;
  }catch(e){$('#foot').innerHTML='<span class="err">Server pemantau tidak menjawab.</span>'}
}
tick(); setInterval(tick,30000);
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        p = unquote(self.path.split("?")[0])
        if p == "/": return self.send(200, PAGE.encode(), "text/html; charset=utf-8")
        if p == "/api/status":
            with lock: return self.send(200, json.dumps(snapshot).encode(), "application/json")
        if p.startswith("/runs/"):
            f = (RUNS / p[6:]).resolve()
            if RUNS.resolve() in f.parents and f.is_file():
                ct = {".jpg": "image/jpeg", ".png": "image/png", ".json": "application/json"}.get(f.suffix, "application/octet-stream")
                return self.send(200, f.read_bytes(), ct)
        self.send(404, b"tidak ada", "text/plain")

if __name__ == "__main__":
    threading.Thread(target=poll, daemon=True).start()
    print(f"[nara] pemantau di http://localhost:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
