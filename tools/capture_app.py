"""Rekam adegan aplikasi NaraMotion untuk showreel (Playwright, Chrome asli, 1920x1080, tanpa login: SDK Firebase diblokir).

Pemakaian: python tools/capture_app.py <folder keluaran> [adegan ...]
Adegan: hero, studio, kelas-sim, kelas-cam, arsip. Butuh server statis http://127.0.0.1:8080 di akar proyek.
Tiap adegan → <adegan>.webm + catatan detik "siap" di captures.json (potong bagian memuat saat menyunting).
"""
import sys, json, time, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SCENES = sys.argv[2:] or ["hero", "studio", "kelas-sim", "kelas-cam", "arsip"]
BASE = "http://127.0.0.1:8080/index.html"
CLIP = str(next(iter(sorted((Path(__file__).resolve().parents[1] / "assets_src" / "showreel").glob("clip_*.mp4"))), ""))   # klip dataset Bali (CC BY 4.0)
W, H = 1920, 1080
meta = json.loads((OUT / "captures.json").read_text()) if (OUT / "captures.json").exists() else {}

def scene(pg, name, mark):
    if name == "hero":
        pg.goto(BASE); pg.wait_for_timeout(2500); mark()
        pg.wait_for_timeout(5000)
        for y in range(0, 900, 30): pg.mouse.wheel(0, 30); pg.wait_for_timeout(40)
        pg.wait_for_timeout(2500)
    elif name == "studio":
        pg.goto(BASE + "#studio"); pg.wait_for_timeout(2500)
        opts = pg.eval_on_selector_all("#studio-dance option", "o => o.map(x => x.value)")
        pg.select_option("#studio-dance", "aist-gJB" if "aist-gJB" in opts else "gambyong"); pg.wait_for_timeout(1500); mark()
        pg.wait_for_timeout(4500); pg.click('[data-node="fArmL"]'); pg.wait_for_timeout(4500)
    elif name == "kelas-sim":
        pg.goto(BASE + "#kelas"); pg.wait_for_timeout(3500); mark(); pg.wait_for_timeout(8000)
    elif name == "kelas-cam":
        pg.goto(BASE + "#kelas"); pg.wait_for_timeout(800)
        pg.click('#kelas-mode [data-mode="cam"]')
        pg.wait_for_function("document.querySelector('#cam-target').options.length > 0", timeout=60000)
        tgt = pg.eval_on_selector_all("#cam-target option", "o => o.map(x => x.value)")
        want = Path(CLIP).stem if Path(CLIP).exists() else ""
        pick = next((t for t in tgt if t.lower().replace("_", "") in want.lower().replace("_", "")), tgt[0])
        pg.select_option("#cam-target", pick)
        pg.set_input_files("#cam-file", CLIP)
        pg.wait_for_function("document.querySelector('#cam-top').children.length > 0", timeout=120000)
        pg.evaluate("window.scrollTo(0, 230)"); pg.wait_for_timeout(9000); mark(); pg.wait_for_timeout(12000)   # mulai setelah skor stabil
    elif name == "studio-rec":   # dokumentasi maestro: rekam sesi lalu lihat di Arsip
        pg.goto(BASE + "#studio"); pg.wait_for_timeout(3000)
        pg.select_option("#studio-dance", "gambyong"); pg.wait_for_timeout(800); mark()
        pg.click("#studio-rec"); pg.wait_for_timeout(7000); pg.click("#studio-rec"); pg.wait_for_timeout(1500)
        pg.goto(BASE + "#arsip"); pg.wait_for_timeout(2000)
        top = pg.evaluate("document.evaluate(\"//h2[contains(., 'Sesi rekaman')]\", document, null, 9, null).singleNodeValue.getBoundingClientRect().top + scrollY + 220")
        for k in range(30): pg.evaluate(f"window.scrollTo(0, {top} * {(k + 1) / 30})"); pg.wait_for_timeout(33)
        pg.wait_for_timeout(4000)
    elif name == "arsip":
        pg.goto(BASE + "#arsip"); pg.wait_for_timeout(2500); mark()
        for _ in range(40): pg.mouse.wheel(0, 25); pg.wait_for_timeout(50)
        pg.wait_for_timeout(3000)

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--autoplay-policy=no-user-gesture-required"])
    for name in SCENES:
        tmp = OUT / f"_tmp_{name}"; shutil.rmtree(tmp, ignore_errors=True)
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(tmp), record_video_size={"width": W, "height": H})
        ctx.route("**/firebasejs/**", lambda r: r.abort())
        pg = ctx.new_page(); t0 = time.monotonic(); ready = {}
        scene(pg, name, lambda: ready.setdefault("t", round(time.monotonic() - t0, 2)))
        dur = round(time.monotonic() - t0, 2); vid = pg.video.path(); ctx.close()
        shutil.move(vid, OUT / f"{name}.webm"); shutil.rmtree(tmp, ignore_errors=True)
        meta[name] = dict(ready=ready.get("t", 0), total=dur); print(name, meta[name], flush=True)
    b.close()
(OUT / "captures.json").write_text(json.dumps(meta, indent=1))
