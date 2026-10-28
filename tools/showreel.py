"""Showreel NaraMotion: 16:9 (1920x1080, ±70 s) + 9:16 (1080x1920, ±30 s), teks bahasa Indonesia, musik gamelan sintesis.

Bahan (assets_src/showreel/): music.wav, dancer_loop/*.png (RGBA), turntable_<nama>/*.png, captures/*.webm + captures.json,
metrik di ml/runs/*. Kartu teks dirender dari HTML (font merek) lewat Playwright; disusun FFmpeg.
Pemakaian: python tools/showreel.py [16x9|9x16|all]
"""
import sys, json, glob, shutil, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]; SR = ROOT / "assets_src" / "showreel"; WORK = SR / "_work"; WORK.mkdir(parents=True, exist_ok=True)
OUTDIR = ROOT / "media"; OUTDIR.mkdir(exist_ok=True)
FPS = 30; XF = 0.5
import os
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or next(iter(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*infmpeg.exe"))), "ffmpeg")
MODE = sys.argv[1] if len(sys.argv) > 1 else "all"

def run(args): subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)
def jload(pat):
    hits = sorted(glob.glob(str(ROOT / pat)), key=lambda p: Path(p).stat().st_mtime)
    return json.loads(Path(hits[-1]).read_text("utf-8")) if hits else None

# ---------- angka dari hasil Kaggle ----------
m_put = jload("ml/runs/*/putri_body17_metrics.json"); m_pra = jload("ml/runs/*/putra_body17_metrics.json")
m_w133 = jload("ml/runs/*/putri_whole133_metrics.json"); m_imu = jload("ml/runs/*/metrics_imu.json"); m_aist = jload("ml/runs/*/metrics_aist.json")
pct = lambda m, k="test_acc": f"{m[k] * 100:.1f}%".replace(".", ",") if m else "—"
ACC = dict(putri=pct(m_put), putra=pct(m_pra), w133=pct(m_w133), imu=pct(m_imu, "loso_acc"), aist=pct(m_aist, "acc_10node"))
print("angka:", ACC)

# ---------- kartu HTML ----------
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Spectral:ital,wght@0,400;0,500;1,400&family=IBM+Plex+Mono:wght@500&family=Noto+Sans+Javanese:wght@600&display=block">'
CSS = """*{box-sizing:border-box}html,body{margin:0;background:transparent;color:#ebe0c6;font-family:Spectral,serif}
.bg{position:absolute;inset:0;background:radial-gradient(60% 70% at 50% 45%,#2a1f10 0,#1b150d 60%,#120d07 100%)}
.bg::before{content:"";position:absolute;inset:0;background:url(BATIK) 0 0/240px;opacity:.06}
.gold{background:linear-gradient(180deg,#f6e4b4,#ecc978 40%,#d2a54a 72%,#8d6a2c);-webkit-background-clip:text;color:transparent}
.cin{font-family:Cinzel,serif}.mono{font-family:'IBM Plex Mono',monospace;letter-spacing:.16em;text-transform:uppercase;color:#d2a54a}
.jw{font-family:'Noto Sans Javanese';color:#d2a54a}.frame{background:rgba(30,23,14,.86);border:1px solid rgba(210,165,74,.28);border-radius:22px;box-shadow:0 12px 40px rgba(0,0,0,.5)}"""
BATIK = (ROOT / "assets/batik/parang.svg").as_uri()

def card(name, w, h, body, bg=True):
    html = f"<!doctype html><html><head><meta charset=utf-8>{FONTS}<style>{CSS.replace('BATIK', BATIK)}body{{width:{w}px;height:{h}px;position:relative;overflow:hidden}}</style></head><body>{'<div class=bg></div>' if bg else ''}{body}</body></html>"
    f = WORK / f"{name}.html"; f.write_text(html, "utf-8"); return f

def shoot(cards):
    with sync_playwright() as p:
        b = p.chromium.launch()
        for f, w, h in cards:
            pg = b.new_page(viewport={"width": w, "height": h}); pg.goto(f.as_uri(), wait_until="load", timeout=60000); pg.wait_for_function("document.fonts.status === 'loaded'", timeout=30000); pg.wait_for_timeout(500)
            pg.screenshot(path=str(f.with_suffix(".png")), omit_background=True); pg.close()
        b.close()

def img(p): return (ROOT / p).as_uri()
QR = img("print/img/qr.svg")
TEAM = "<b>SMANSA</b> · Kim Arumi Malika Putri · Afra Na’ila Arkana · Anyaila Wahyu<br><b>ABBS</b> · Khaifat Attallah Wibowo · Nabila Azalea · Khairan Athaya Wibowo"
CREDIT = ("Data: Hendrawan dkk., Video Dataset of Woman/Male Basic Balinese Dance Movement (Mendeley Data, CC BY 4.0) · AIST++ (Li dkk., ICCV 2021, CC BY 4.0) · "
          "Turkish Folk Dance IMU (berkaykarakis, CC BY 4.0) · Escobar Varela &amp; Hernández-Barraza (2019) · Model 3D Sketchfab: Virtual Museums of Małopolska (CC0), "
          "eventdesignws, giga, mokhammadsoni (CC BY 4.0) · Musik: komposisi gamelan sintesis tim NaraMotion · Demo memakai data sensor simulasi")

def cards_16x9():
    W, H = 1920, 1080; C = []
    C.append((card("t_title", W, H, f"""<div style="position:absolute;inset:0;display:grid;place-content:center;text-align:center">
      <div class=jw style="font-size:54px">꧁ ꦤꦫ ꧂</div><div class="cin gold" style="font-size:190px;font-weight:800;line-height:1">NaraMotion</div>
      <div class=mono style="font-size:24px;margin-top:22px">Motion capture · 9-DoF · kecerdasan buatan</div>
      <div style="font-size:34px;font-style:italic;color:#f6e4b4;margin-top:26px">Merekam, mengarsipkan, dan mengajarkan tari Nusantara</div></div>"""), W, H))
    C.append((card("t_dancer", W, H, """<div style="position:absolute;left:120px;top:330px;width:720px">
      <div class=mono style="font-size:22px">Tentang</div><div class="cin gold" style="font-size:78px;font-weight:700;line-height:1.08;margin-top:18px">Tari diwariskan lewat tubuh.</div>
      <div style="font-size:40px;color:#f6e4b4;margin-top:26px">NaraMotion menyimpannya sebagai data — gerak demi gerak, sendi demi sendi.</div></div>"""), W, H))
    C.append((card("t_sensor", W, H, f"""<div style="position:absolute;inset:0;display:grid;grid-template-columns:520px 1fr;gap:80px;align-items:center;padding:0 140px">
      <svg viewBox="0 0 120 200" style="width:520px"><g fill=none stroke="#8d6a2c" stroke-width=3 stroke-linecap=round stroke-linejoin=round><circle cx=60 cy=22 r=13 /><path d="M60 35V100M60 46L36 74L26 104M60 46L84 74L94 104M60 100L46 146L42 192M60 100L74 146L78 192"/></g>
      <g fill="#ecc978" stroke="#1b150d" stroke-width=1.5><circle cx=60 cy=22 r=5 /><circle cx=60 cy=66 r=5 /><circle cx=47 cy=61 r=5 /><circle cx=73 cy=61 r=5 /><circle cx=31 cy=89 r=5 /><circle cx=89 cy=89 r=5 /><circle cx=53 cy=123 r=5 /><circle cx=67 cy=123 r=5 /><circle cx=44 cy=169 r=5 /><circle cx=76 cy=169 r=5 /></g></svg>
      <div><div class=mono style="font-size:22px">Perangkat keras</div><div class="cin gold" style="font-size:84px;font-weight:700;line-height:1.05;margin:16px 0 30px">10 node sensor di tubuh penari</div>
      <div style="display:flex;gap:26px">{''.join(f'<div class=frame style="padding:24px 30px;text-align:center"><img src="{img("assets/3d/" + i + ".webp")}" style="width:120px"><div class=cin style="font-size:28px;color:#ecc978;margin-top:6px">{t}</div><div class=mono style="font-size:15px;letter-spacing:.06em;color:#f6e4b4">{c}</div></div>' for i, t, c in [("accel", "Akselerometer", "ADXL345"), ("gyro", "Giroskop", "ITG-3205"), ("mag", "Magnetometer", "HMC/QMC5883L")])}</div>
      <div style="font-size:34px;margin-top:30px;color:#f6e4b4">GY-85 9-DoF · ESP32-C3 · fusi Madgwick 100 kali per detik</div></div></div>"""), W, H))
    C.append((card("t_ai", W, H, f"""<div style="position:absolute;inset:0;padding:110px 140px">
      <div class=mono style="font-size:22px">Kecerdasan buatan · dilatih di Kaggle</div>
      <div class="cin gold" style="font-size:80px;font-weight:700;line-height:1.05;margin:16px 0 44px">Belajar dari ribuan gerak nyata</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:28px">{''.join(f'<div class=frame style="padding:30px"><div class=cin style="font-size:76px;font-weight:700;color:#ecc978">{v}</div><div style="font-size:28px;margin-top:8px;line-height:1.3">{t}</div></div>' for v, t in [(ACC["putri"], "akurasi Kamera AI · 13 gerak dasar putri Bali (1.740 video)"), (ACC["putra"], "akurasi · 11 gerak dasar putra Bali (828 video)"), (ACC["imu"], "pengenal tari dari sensor IMU, penari yang belum pernah dilihat"), (ACC["aist"], "genre dari IMU sintetis 10 node (mocap AIST++)")])}</div>
      <div style="font-size:30px;margin-top:40px;color:#a9987a">Pose 133 titik (RTMW) diekstrak dari video pada GPU Kaggle · model dijalankan di peramban dengan ONNX</div></div>"""), W, H))
    tt = [("arjuna", "Arjuna", "wayang golek"), ("gamelan", "Gamelan", "pengiring tari"), ("borobudur", "Borobudur", "stupa candi"), ("joglo", "Joglo", "pendapa tempat menari")]
    C.append((card("t_heritage", W, H, f"""<div style="position:absolute;left:0;right:0;top:90px;text-align:center"><div class=mono style="font-size:22px">Arsip budaya</div>
      <div class="cin gold" style="font-size:84px;font-weight:700">Warisan yang dijaga</div></div>
      <div style="position:absolute;left:90px;right:90px;bottom:120px;display:grid;grid-template-columns:repeat(4,1fr);text-align:center">{''.join(f'<div><div class=cin style="font-size:40px;color:#ecc978">{n}</div><div style="font-size:26px;color:#a9987a">{s}</div></div>' for _, n, s in tt)}</div>"""), W, H))
    C.append((card("t_end", W, H, f"""<div style="position:absolute;inset:0;display:grid;place-content:center;text-align:center;padding:0 160px">
      <div class="cin gold" style="font-size:120px;font-weight:800">NaraMotion</div>
      <div style="display:flex;gap:40px;align-items:center;justify-content:center;margin:26px 0 30px"><img src="{QR}" style="width:200px;border-radius:12px"><div style="text-align:left"><div class=cin style="font-size:44px;color:#ecc978">Coba Studio sekarang</div><div class=mono style="font-size:30px;letter-spacing:.04em;text-transform:none;color:#f6e4b4">naramotion.web.app</div></div></div>
      <div style="font-size:30px;line-height:1.5">{TEAM}</div>
      <div style="font-size:17px;color:#76674c;margin-top:30px;line-height:1.45">{CREDIT}</div></div>"""), W, H))
    for n, t in [("l_studio", "Studio · avatar & 9 sumbu sensor waktu nyata · rekaman mocap AIST++"), ("l_kelas", "Kelas Tari · Kamera AI mengenali gerak dasar tari Bali dan menilai tiap sendi"), ("l_arsip", "Arsip · 24 gerak dasar Bali siap dilatih")]:
        C.append((card(n, W, 140, f'<div style="position:absolute;left:60px;bottom:30px" class=frame><div style="padding:18px 30px;font-size:34px;color:#f6e4b4"><span class=mono style="font-size:20px;margin-right:16px">NaraMotion</span>{t}</div></div>', bg=False), W, 140))
    C.append((card("bg", W, H, ""), W, H))
    return C

def cards_9x16():
    W, H = 1080, 1920; C = []
    C.append((card("v_title", W, H, """<div style="position:absolute;inset:0;display:grid;place-content:center;text-align:center;padding:0 60px">
      <div class=jw style="font-size:56px">꧁ ꦤꦫ ꧂</div><div class="cin gold" style="font-size:150px;font-weight:800;line-height:1">Nara<br>Motion</div>
      <div class=mono style="font-size:26px;margin-top:30px">Motion capture tari Nusantara</div></div>"""), W, H))
    C.append((card("v_dancer", W, H, """<div style="position:absolute;left:70px;right:70px;top:170px;text-align:center"><div class="cin gold" style="font-size:84px;font-weight:700;line-height:1.08">Tari diwariskan lewat tubuh.</div></div>
      <div style="position:absolute;left:70px;right:70px;bottom:230px;text-align:center;font-size:46px;color:#f6e4b4">NaraMotion menyimpannya sebagai data.</div>"""), W, H))
    C.append((card("v_kelas", W, H, f"""<div style="position:absolute;left:60px;right:60px;top:140px;text-align:center"><div class=mono style="font-size:26px">Kelas Tari · Kamera AI</div><div class="cin gold" style="font-size:72px;font-weight:700;line-height:1.1;margin-top:16px">AI menilai gerakmu, sendi demi sendi</div></div>
      <div style="position:absolute;left:60px;right:60px;bottom:200px;text-align:center;font-size:40px;color:#f6e4b4">{ACC['putri']} akurasi · 24 gerak dasar tari Bali</div>"""), W, H))
    C.append((card("v_heritage", W, H, """<div style="position:absolute;left:0;right:0;top:160px;text-align:center"><div class="cin gold" style="font-size:90px;font-weight:700">Warisan<br>yang dijaga</div></div>"""), W, H))
    C.append((card("v_end", W, H, f"""<div style="position:absolute;inset:0;display:grid;place-content:center;text-align:center;padding:0 70px">
      <div class="cin gold" style="font-size:120px;font-weight:800;line-height:1">Nara<br>Motion</div><img src="{QR}" style="width:300px;margin:50px auto 24px;border-radius:14px">
      <div class=mono style="font-size:40px;letter-spacing:.02em;text-transform:none;color:#f6e4b4">naramotion.web.app</div>
      <div style="font-size:30px;line-height:1.5;margin-top:40px">SMANSA · ABBS</div>
      <div style="font-size:20px;color:#76674c;margin-top:30px;line-height:1.45">{CREDIT}</div></div>"""), W, H))
    return C

# ---------- segmen ----------
def seg_still(png, dur, out, zoom=True, W=1920, H=1080):
    z = f"zoompan=z='min(zoom+0.0006,1.06)':d={int(dur * FPS)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}" if zoom else f"fps={FPS},scale={W}:{H}"
    run(["-loop", "1", "-t", str(dur), "-i", str(png), "-vf", f"{z},format=yuv420p", "-t", str(dur), "-r", str(FPS), str(out)])

def seq_input(folder, dur):
    n = len(list(folder.glob("*.png"))); return ["-stream_loop", str(int(dur * 24 / max(n, 1)) + 1), "-framerate", "24", "-i", str(folder / "%04d.png")] if n else None

def seg_over(bgpng, layers, dur, out, W=1920, H=1080):
    """bgpng + lapisan [(input_args, filter_scale_pos)] → mp4"""
    args = ["-loop", "1", "-t", str(dur), "-i", str(bgpng)]; fc = []; last = "[0:v]"
    for k, (inp, sc, x, y) in enumerate(layers, 1):
        args += inp; fc.append(f"[{k}:v]{sc}[l{k}]"); fc.append(f"{last}[l{k}]overlay={x}:{y}:shortest=0:eof_action=repeat[o{k}]"); last = f"[o{k}]"
    fc.append(f"{last}fps={FPS},scale={W}:{H},format=yuv420p[v]")
    run([*args, "-filter_complex", ";".join(fc), "-map", "[v]", "-t", str(dur), str(out)])

def seg_capture(name, dur, label, out, crop="1280:720:320:120", W=1920, H=1080):
    meta = json.loads((SR / "captures/captures.json").read_text()); st = meta[name]["ready"]
    lab = WORK / f"{label}.png"
    run(["-ss", str(st), "-t", str(dur), "-i", str(SR / f"captures/{name}.webm"), "-i", str(lab), "-filter_complex",
         f"[0:v]crop={crop},scale={W}:{H},fps={FPS}[c];[c][1:v]overlay=0:{H}-140[v]", "-map", "[v]", "-t", str(dur), "-pix_fmt", "yuv420p", str(out)])

def concat(parts, durs, out, music, total):
    args = []; [args.extend(["-i", str(p)]) for p in parts]
    fc, last, off = [], "[0:v]", 0.0
    for i in range(1, len(parts)):
        off += durs[i - 1] - XF; fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]"); last = f"[x{i}]"
    args += ["-i", str(music)]; fc.append(f"[{len(parts)}:a]atrim=0:{total},afade=t=out:st={total - 2.5}:d=2.5[a]")
    run([*args, "-filter_complex", ";".join(fc), "-map", last, "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(total), str(out)])

def build_16x9():
    shoot(cards_16x9()); P = []; D = [7, 10, 8, 9, 10.5, 8, 9, 9.5]
    w = lambda n: WORK / f"{n}.png"
    seg_still(w("t_title"), D[0], WORK / "s1.mp4"); P.append(WORK / "s1.mp4")
    dl = seq_input(SR / "dancer_loop", D[1]); assert dl, "dancer_loop kosong"
    seg_over(w("t_dancer"), [(dl, "scale=1000:1000", 860, 60)], D[1], WORK / "s2.mp4"); P.append(WORK / "s2.mp4")
    seg_still(w("t_sensor"), D[2], WORK / "s3.mp4"); P.append(WORK / "s3.mp4")
    seg_capture("studio", D[3], "l_studio", WORK / "s4.mp4"); P.append(WORK / "s4.mp4")
    seg_capture("kelas-cam", D[4], "l_kelas", WORK / "s5.mp4", crop="1440:810:240:170"); P.append(WORK / "s5.mp4")
    seg_still(w("t_ai"), D[5], WORK / "s6.mp4"); P.append(WORK / "s6.mp4")
    lay = [(seq_input(SR / f"turntable_{n}", D[6]), "scale=400:400", 90 + i * 445, 330) for i, n in enumerate(["arjuna", "gamelan", "borobudur", "joglo"])]
    seg_over(w("t_heritage"), lay, D[6], WORK / "s7.mp4"); P.append(WORK / "s7.mp4")
    seg_still(w("t_end"), D[7], WORK / "s8.mp4", zoom=False); P.append(WORK / "s8.mp4")
    total = sum(D) - XF * (len(D) - 1)
    concat(P, D, OUTDIR / "naramotion_showreel_16x9.mp4", SR / "music.wav", total); print("16:9", total, "s")

def build_9x16():
    shoot(cards_9x16()); W, H = 1080, 1920; P = []; D = [4, 7, 9, 5.5, 6.5]
    w = lambda n: WORK / f"{n}.png"
    seg_still(w("v_title"), D[0], WORK / "v1.mp4", W=W, H=H); P.append(WORK / "v1.mp4")
    seg_over(w("v_dancer"), [(seq_input(SR / "dancer_loop", D[1]), "scale=1000:1000", 40, 420)], D[1], WORK / "v2.mp4", W, H); P.append(WORK / "v2.mp4")
    meta = json.loads((SR / "captures/captures.json").read_text()); st = meta["kelas-cam"]["ready"] + 1
    run(["-loop", "1", "-t", str(D[2]), "-i", str(w("v_kelas")), "-ss", str(st), "-t", str(D[2]), "-i", str(SR / "captures/kelas-cam.webm"), "-filter_complex",
         f"[1:v]crop=1100:900:240:170,scale=1000:-2[c];[0:v][c]overlay=40:520,fps={FPS},format=yuv420p[v]", "-map", "[v]", "-t", str(D[2]), str(WORK / "v3.mp4")]); P.append(WORK / "v3.mp4")
    lay = [(seq_input(SR / f"turntable_{n}", D[3]), "scale=470:470", 50 + (i % 2) * 510, 620 + (i // 2) * 560) for i, n in enumerate(["arjuna", "gamelan", "borobudur", "joglo"])]
    seg_over(w("v_heritage"), lay, D[3], WORK / "v4.mp4", W, H); P.append(WORK / "v4.mp4")
    seg_still(w("v_end"), D[4], WORK / "v5.mp4", zoom=False, W=W, H=H); P.append(WORK / "v5.mp4")
    total = sum(D) - XF * (len(D) - 1)
    concat(P, D, OUTDIR / "naramotion_showreel_9x16.mp4", SR / "music.wav", total); print("9:16", total, "s")

if __name__ == "__main__":
    if MODE in ("16x9", "all"): build_16x9()
    if MODE in ("9x16", "all"): build_9x16()
