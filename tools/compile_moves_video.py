"""Video kompilasi 1 menit: cuplikan gerak tari di Arena NaraMotion (Penari Jawa, penonton, 4 arena) + label nama/daerah/sumber.
Butuh server lokal :8799 (python -m http.server 8799) dan ffmpeg (env FFMPEG). Memakai ?internal=1 → video untuk pemakaian internal.
Keluaran: marketing/kompilasi/naramotion_kompilasi_gerak_1menit.mp4
"""
import json, os, shutil, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "marketing/kompilasi"; TMP = OUT / "_raw"; OUT.mkdir(parents=True, exist_ok=True); TMP.mkdir(exist_ok=True)
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
W, H, SEG, INTRO, OUTRO = 1920, 1080, 2.6, 3.5, 4.0
# (kunci gerak, arena) — gerak dasar Bali dulu, lalu tari utuh dari berbagai daerah
yt = {r["dance"]: r for f in ("yt", "yt_internal") for r in json.load(open(ROOT / f"assets/ml/rig_penari/{f}/index.json", encoding="utf-8"))}
PICK = [("putri__Agem_Kanan", "panggung"), ("putri__Ngelo", "panggung"), ("putra__Nayog", "panggung"), ("putri__Ulap_Ulap", "panggung")]
for i, d in enumerate(["legong", "kecak", "pendet", "baris_bali", "gambyong", "serimpi", "golek_menak", "remo", "jaipong", "pande_gelang",
                       "rampak_bedug", "ngelanglang", "saman", "tor_tor", "piring", "sajojo"]):
    PICK.append((yt[d]["key"], ["borobudur", "joglo", "trowulan", "borobudur"][i // 4]))
BASE_NAMES = {"Agem_Kanan": "Agem Kanan", "Ngelo": "Ngelo", "Nayog": "Nayog", "Ulap_Ulap": "Ulap-Ulap"}

def label(key):
    if "__" in key and "/" not in key:
        ds, g = key.split("__"); return f"{BASE_NAMES.get(g, g)}", f"Gerak dasar Bali · {ds}", "Sumber: dataset gerak dasar Bali (Mendeley)"
    r = next(x for x in yt.values() if x["key"] == key)
    return r["gerak"].rsplit(" ", 1)[0], r["region"], f"Sumber video: {r['channel'] or 'Drive tim'} · {'CC BY' if not r['internal'] else 'YouTube'}"

OVER = """(([a, b, c]) => { let el = document.getElementById('lt'); if (!el) { el = document.createElement('div'); el.id = 'lt';
  el.style.cssText = 'position:fixed;left:64px;bottom:64px;z-index:99;font-family:Georgia,serif;color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.7);transition:opacity .3s';
  document.body.appendChild(el); }
  el.innerHTML = `<div style="font-size:15px;letter-spacing:.25em;text-transform:uppercase;color:#e8c27a">${b}</div><div style="font-size:54px;line-height:1.1;margin:4px 0 8px">${a}</div><div style="font:14px Segoe UI,sans-serif;opacity:.85">${c}</div>`;
  let br = document.getElementById('brand'); if (!br) { br = document.createElement('div'); br.id = 'brand';
  br.style.cssText = 'position:fixed;right:56px;top:44px;z-index:99;font:600 16px Georgia,serif;letter-spacing:.3em;color:#e8c27a;text-shadow:0 2px 8px rgba(0,0,0,.6)'; br.textContent = 'NARAMOTION'; document.body.appendChild(br); } })"""
HIDE = "document.querySelector('.panel').style.display='none';document.querySelector('.top').style.display='none';const A=window.__arena;A.controls.autoRotate=true;A.controls.autoRotateSpeed=1.4"
LOADED = "document.querySelector('#load').hidden"
# kamera ±4,3 m dari penari (bukan sudut lebar arena) agar gerak terlihat jelas; tetap berputar pelan
CLOSE = """(() => { const A = window.__arena, s = A.dancerSpot, d = A.camera.position.clone().sub(s); d.y = 0; d.setLength(4.3);
  A.camera.position.set(s.x + d.x, s.y + 1.55, s.z + d.z); A.controls.target.set(s.x, s.y + 0.95, s.z); A.controls.update(); })()"""

segs = []
with sync_playwright() as p:
    b = p.chromium.launch(headless=False, args=["--use-angle=d3d11", "--ignore-gpu-blocklist", "--window-position=-2400,0"])
    ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(TMP), record_video_size={"width": W, "height": H})
    pg = ctx.new_page(); t0 = time.time()
    pg.goto(f"http://localhost:8799/arena.html?internal=1&gerak={PICK[0][0]}"); pg.wait_for_function(LOADED, timeout=180000); pg.wait_for_timeout(4000)
    pg.evaluate(HIDE); arena = "panggung"
    for key, ar in PICK:
        if ar != arena:
            pg.evaluate(f"document.querySelector('[data-arena={ar}]').click()"); pg.wait_for_function(LOADED, timeout=180000); arena = ar
        pg.evaluate(f"window.__showKey('{key}')"); pg.wait_for_function(LOADED, timeout=180000)
        pg.evaluate(CLOSE)
        pg.evaluate(OVER, list(label(key))); pg.wait_for_timeout(700)   # beri waktu animasi mulai & kamera bergerak
        segs.append(time.time() - t0); pg.wait_for_timeout(int(SEG * 1000) + 1200)   # ekor cukup untuk dissolve, sebelum gerak/arena berikutnya dimuat
    vid = pg.video.path(); ctx.close(); b.close()
print(len(segs), "segmen")
json.dump({"segs": segs, "vid": str(vid), "picks": PICK}, open(TMP / "segs.json", "w"))
