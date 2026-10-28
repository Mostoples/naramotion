"""QA aplikasi NaraMotion tanpa login: SDK Firebase diblokir (ruang kerja terbuka), Chrome asli (codec H.264).

Pemakaian:
  python tools/qa_app.py kelas-cam <video.mp4> <out.png>   # Kelas Tari · Kamera AI dengan unggah video
  python tools/qa_app.py studio <dance-id> <out.png>       # Studio dengan tari tertentu (mis. aist-gBR)
Butuh server statis di http://127.0.0.1:8080 (python -m http.server 8080 di akar proyek).
"""
import sys, json
from playwright.sync_api import sync_playwright

mode, arg, out = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = "http://127.0.0.1:8080/index.html"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    logs = []
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"[:240]))
    pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"[:240]))
    pg.route("**/firebasejs/**", lambda r: r.abort())
    if mode == "kelas-cam":
        pg.goto(BASE + "#kelas"); pg.wait_for_timeout(800)
        pg.click('#kelas-mode [data-mode="cam"]')
        pg.wait_for_function("document.querySelector('#cam-target').options.length > 0", timeout=60000)
        pg.set_input_files("#cam-file", arg)
        try:
            pg.wait_for_function("document.querySelector('#cam-top').children.length > 0", timeout=60000)
            pg.wait_for_timeout(6000)
        except Exception as e:
            logs.append("TIMEOUT: " + str(e)[:120])
            logs.append("st: " + json.dumps(pg.evaluate("() => { const s = NaraCamera._st; return {buf: s.buf.length, run: s.running, sess: !!s.session, tpl: !!s.tpl, lm: !!s.landmarker, last: s.buf.length ? s.buf[s.buf.length-1].s.map(v=>+v.toFixed(2)) : null}; }")))
            logs.append("video: " + json.dumps(pg.evaluate("() => { const v = document.querySelector('#cam-video'); return {rs: v.readyState, t: v.currentTime, w: v.videoWidth, err: v.error && v.error.code, paused: v.paused}; }")))
        info = pg.evaluate("""() => ({status: cam_status.textContent, score: document.querySelector('#cam-score').textContent,
            grade: document.querySelector('#cam-grade').textContent,
            top: [...document.querySelectorAll('#cam-top li')].map(li => li.textContent.trim()),
            rows: [...document.querySelectorAll('#joint-rows tr')].map(tr => tr.children[0].textContent + ' ' + tr.children[1].textContent)})""".replace("cam_status", "document.querySelector('#cam-status')"))
    else:
        pg.goto(BASE + "#studio"); pg.wait_for_timeout(1500)
        pg.select_option("#studio-dance", arg); pg.wait_for_timeout(4000)
        info = pg.evaluate("() => ({dance: document.querySelector('#studio-dance').selectedOptions[0].textContent, q: ['w','x','y','z'].map(k => document.querySelector('#q-'+k).textContent)})")
    pg.screenshot(path=out, full_page=False)
    print(json.dumps(info, ensure_ascii=False, indent=1))
    print("\n".join(l for l in logs if not l.startswith("debug"))[-2500:])
    b.close()
