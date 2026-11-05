"""Rekam footage aplikasi NaraMotion untuk video iklan (Playwright + GPU, 1280x720 webm → mp4).
Butuh server lokal di :8799 (python -m http.server 8799). Keluaran: marketing/ad/footage/*.mp4
"""
import os, shutil, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "marketing/ad/footage"; OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_raw"; TMP.mkdir(exist_ok=True)
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
BASE = "http://localhost:8799/"
FAKE = str(ROOT / "ml/data/fakecam.y4m"); DUO = str(ROOT / "ml/data/duo.mp4")
ARGS = ["--use-angle=d3d11", "--ignore-gpu-blocklist", "--window-position=-2400,0", "--autoplay-policy=no-user-gesture-required",
        "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", f"--use-file-for-fake-video-capture={FAKE}"]
NOAUTH = lambda r: r.fulfill(status=200, content_type="text/javascript", body="window.NARA_FIREBASE=null;")

def shot(b, name, w, h, fn, trim=0.0):
    ctx = b.new_context(viewport={"width": w, "height": h}, record_video_dir=str(TMP), record_video_size={"width": w, "height": h}, permissions=["camera"])
    pg = ctx.new_page(); pg.route("**/js/firebase-config.js", NOAUTH)
    t0 = time.time(); start = fn(pg); dur = time.time() - t0
    vid = pg.video.path(); ctx.close()
    out = OUT / f"{name}.mp4"; ss = start if start is not None else trim
    subprocess.run([FF, "-loglevel", "error", "-y", "-ss", f"{ss:.2f}", "-i", vid, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-an", str(out)], check=True)
    print(name, out.stat().st_size // 1024, "KB")

def arena(arena_id, gerak, secs, look=None):
    def f(pg):
        pg.goto(BASE + f"arena.html?gerak={gerak}"); pg.wait_for_function("document.querySelector('#load').hidden", timeout=180000)
        pg.evaluate("document.querySelector('.panel').style.display='none';document.querySelector('.top').style.display='none'")
        if arena_id != "panggung":   # arena pembuka = panggung
            pg.evaluate(f"document.querySelector('[data-arena={arena_id}]').click()"); pg.wait_for_function("document.querySelector('#load').hidden", timeout=180000)
        if look: pg.evaluate(f"document.querySelector('[data-look={look}]').click()")
        pg.wait_for_timeout(2500); t = time.time()
        pg.wait_for_timeout(secs * 1000)
        return t - T0[0]
    return f
T0 = [0]
def timed(f):
    def g(pg): T0[0] = time.time(); return f(pg)
    return g

def kelas(pg):
    pg.goto(BASE + "#kelas"); pg.wait_for_timeout(1500)
    pg.click('#kelas-mode [data-mode="cam"]'); pg.wait_for_function("window.NaraCamera._st.tpl3", timeout=90000)
    pg.select_option("#cam-target", "Agem_Kanan"); pg.click("#cam-start")
    pg.evaluate("document.querySelector('.topbar').style.display='none'; document.querySelector('.app-head').style.display='none'; document.querySelector('#kelas-toolbar').style.display='none'; document.querySelector('#kelas-cam .toolbar').style.display='none'; window.scrollTo(0, document.querySelector('#kelas-cam .kelas-grid').getBoundingClientRect().top + scrollY - 12)")
    t = time.time()
    pg.wait_for_function("window.NaraCamera._st.calibrated", timeout=90000); pg.wait_for_timeout(9000)
    return t - T0[0]

def duo(pg):
    pg.goto(BASE + "#kelas"); pg.wait_for_timeout(1500)
    pg.click('#kelas-mode [data-mode="cam"]'); pg.wait_for_function("window.NaraCamera._st.tpl3", timeout=90000)
    pg.select_option("#cam-people", "2"); pg.select_option("#cam-target", "Agem_Kanan")
    pg.set_input_files("#cam-file", DUO)
    pg.evaluate("document.querySelector('.topbar').style.display='none'; document.querySelector('.app-head').style.display='none'; document.querySelector('#kelas-toolbar').style.display='none'; document.querySelector('#kelas-cam .toolbar').style.display='none'; window.scrollTo(0, document.querySelector('#kelas-cam .kelas-grid').getBoundingClientRect().top + scrollY - 12)")
    pg.wait_for_timeout(9000); t = time.time(); pg.wait_for_timeout(8000)
    return t - T0[0]

def reels(pg):
    pg.goto(BASE); pg.wait_for_timeout(1500)
    pg.evaluate("document.getElementById('video-tari').scrollIntoView()"); pg.click("#reels-full"); pg.wait_for_timeout(1500)
    t = time.time()
    for _ in range(3):
        pg.wait_for_timeout(2200); pg.evaluate("document.getElementById('reels-feed').scrollBy({top: innerHeight, behavior: 'smooth'})")
    pg.wait_for_timeout(1500)
    return t - T0[0]

def landing(pg):
    pg.goto(BASE); t = time.time(); pg.wait_for_timeout(6500); return t - T0[0] + 0.5

with sync_playwright() as p:
    b = p.chromium.launch(headless=False, args=ARGS)
    jobs = [("arena_panggung", 1280, 720, timed(arena("panggung", "putri__Agem_Kanan", 9))),
            ("arena_joglo", 1280, 720, timed(arena("joglo", "putri__Ngelo", 7))),
            ("arena_borobudur", 1280, 720, timed(arena("borobudur", "putra__Nayog", 7, "emas"))),
            ("arena_trowulan", 1280, 720, timed(arena("trowulan", "putri__Ulap_Ulap", 6))),
            ("kelas_kalibrasi", 1280, 720, timed(kelas)), ("kelas_duo", 1280, 720, timed(duo)),
            ("reels", 432, 768, timed(reels)), ("landing", 1280, 720, timed(landing))]
    only = sys.argv[1:]
    for name, w, h, fn in jobs:
        if only and name not in only: continue
        shot(b, name, w, h, fn)
    b.close()
shutil.rmtree(TMP, ignore_errors=True)
