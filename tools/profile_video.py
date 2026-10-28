"""Video profil produk NaraMotion (±2 menit, 1920x1080): intro sinematik 3D → masalah → produk → cara kerja →
5 use case → dampak → penutup. Memakai render Blender (assets_src/profile/intro, broll_B1..B4), rekaman aplikasi
(assets_src/showreel/captures), grafik riset (ml/runs), dan musik gamelan sintesis (assets_src/profile/music_profile.wav).
Pemakaian: python tools/profile_video.py   (set FFMPEG bila ffmpeg tidak ada di PATH)  →  media/naramotion_profil_produk.mp4
"""
import sys, json, glob
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import showreel as R   # pakai ulang: card, shoot, run, img, CSS, ACC, TEAM, CREDIT, FPS

ROOT = R.ROOT; PR = ROOT / "assets_src" / "profile"; CAP = ROOT / "assets_src" / "showreel" / "captures"
WORK = PR / "_work"; WORK.mkdir(parents=True, exist_ok=True); R.WORK = WORK
W, H, FPS, XF = 1920, 1080, R.FPS, 0.6
CAPM = json.loads((CAP / "captures.json").read_text())
ACC = R.ACC; img = R.img
N_VID = "2.568"   # 1.740 + 828 video tari Bali

def newest(pat):
    hits = sorted(glob.glob(str(ROOT / pat)), key=lambda p: Path(p).stat().st_mtime); return Path(hits[-1]) if hits else None

# ---------- kartu ----------
def lower(name, tag, title, sub):
    return (R.card(name, W, 300, f'''<div style="position:absolute;left:70px;bottom:60px;max-width:1180px" class=frame><div style="padding:22px 34px">
      <div class=mono style="font-size:20px">{tag}</div><div class="cin gold" style="font-size:50px;font-weight:700;line-height:1.1;margin-top:6px">{title}</div>
      <div style="font-size:28px;color:#f6e4b4;margin-top:8px;line-height:1.35">{sub}</div></div></div>''', bg=False), W, 300)

def cards():
    C = []
    C.append((R.card("p_title", W, H, '''<div style="position:absolute;left:0;right:0;top:120px;text-align:center">
      <div class=jw style="font-size:46px">꧁ ꦤꦫ ꧂</div><div class="cin gold" style="font-size:150px;font-weight:800;line-height:1;text-shadow:0 0 40px rgba(0,0,0,.5)">NaraMotion</div>
      <div class=mono style="font-size:24px;margin-top:18px">Motion capture · 9-DoF · kecerdasan buatan</div></div>''', bg=False), W, H))
    C.append((R.card("p_problem", W, H, '''<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(18,13,7,.92) 0,rgba(18,13,7,.75) 45%,rgba(18,13,7,0) 75%)"></div>
      <div style="position:absolute;left:120px;top:300px;width:820px"><div class=mono style="font-size:22px">Tantangan</div>
      <div class="cin gold" style="font-size:72px;font-weight:700;line-height:1.08;margin-top:16px">Setiap gerak tari menyimpan pengetahuan.</div>
      <div style="font-size:36px;color:#f6e4b4;margin-top:26px;line-height:1.35">Selama ini diwariskan langsung dari maestro ke murid — dan bisa hilang bersama generasinya.</div></div>''', bg=False), W, H))
    C.append((R.card("p_product", W, H, '''<div style="position:absolute;inset:0;background:linear-gradient(270deg,rgba(18,13,7,.9) 0,rgba(18,13,7,.7) 40%,rgba(18,13,7,0) 70%)"></div>
      <div style="position:absolute;right:120px;top:270px;width:760px;text-align:right"><div class=mono style="font-size:22px">Solusi</div>
      <div class="cin gold" style="font-size:96px;font-weight:800;line-height:1;margin-top:16px">NaraMotion</div>
      <div style="font-size:38px;color:#f6e4b4;margin-top:24px;line-height:1.35">Platform motion capture untuk tari Nusantara: 10 node sensor 9-DoF, kecerdasan buatan, dan arsip digital.</div></div>''', bg=False), W, H))
    steps = [("node", "Pasang sensor", "10 node GY-85 di kepala, badan, lengan, paha, betis"), ("gyro", "Fusi sensor", "Madgwick 100×/detik → orientasi tiap segmen"),
             ("dial", "Analisis AI", "Mengenali ragam gerak & menilai tiap sendi"), ("lontar", "Arsip & kelas", "Gerak tersimpan, siswa berlatih dengan umpan balik")]
    C.append((R.card("p_how", W, H, f'''<div style="position:absolute;left:0;right:0;top:110px;text-align:center"><div class=mono style="font-size:22px">Cara kerja</div>
      <div class="cin gold" style="font-size:78px;font-weight:700">Dari gerak ke arsip</div></div>
      <div style="position:absolute;left:110px;right:110px;top:380px;display:grid;grid-template-columns:repeat(4,1fr);gap:30px">{"".join(
        f'<div class=frame style="padding:34px 28px;text-align:center"><div class=cin style="font-size:30px;color:#8d6a2c">{"I II III IV".split()[i]}</div><img src="{img("assets/3d/" + ic + ".webp")}" style="width:150px;margin:8px 0"><div class=cin style="font-size:36px;color:#ecc978">{t}</div><div style="font-size:26px;margin-top:10px;line-height:1.35">{d}</div></div>'
        for i, (ic, t, d) in enumerate(steps))}</div>'''), W, H))
    C.append(lower("p_uc1", "Use case 1 · Sanggar & sekolah", "Siswa berlatih bersama pelatih AI", f"Kamera mengenali 24 gerak dasar tari Bali ({ACC['putri']} akurasi) dan menilai tiap sendi — cukup dengan ponsel atau laptop."))
    C.append(lower("p_uc2", "Use case 2 · Dokumentasi maestro", "Gerak maestro terekam sebagai data", "Studio merekam orientasi 10 segmen tubuh 100×/detik; setiap sesi tersimpan rapi di Arsip."))
    C.append(lower("p_uc3", "Use case 3 · Museum & arsip budaya", "Warisan yang bisa dijelajahi", "Gerak tari, wayang, gamelan, dan pusaka hadir sebagai arsip digital interaktif."))
    jv = newest("ml/runs/javanese/javanese_character.png"); imu = newest("ml/runs/imu_dark.png")
    C.append((R.card("p_uc4", W, H, f'''<div style="position:absolute;left:110px;top:90px"><div class=mono style="font-size:22px">Use case 4 · Peneliti & universitas</div>
      <div class="cin gold" style="font-size:70px;font-weight:700;line-height:1.05;margin-top:12px">Data gerak untuk riset tari</div></div>
      <div style="position:absolute;left:110px;right:110px;top:300px;display:grid;grid-template-columns:1.25fr 1fr;gap:34px;align-items:start">
        <div class=frame style="padding:18px"><img src="{jv.as_uri() if jv else ''}" style="width:100%;border-radius:10px"><div style="font-size:24px;margin-top:10px;color:#f6e4b4">Karakter alus bergerak lebih lambat dan halus (jerk 3–4× lebih rendah) daripada gagah — data VICON tari Jawa.</div></div>
        <div class=frame style="padding:18px"><img src="{imu.as_uri() if imu else ''}" style="width:100%;border-radius:10px"><div style="font-size:24px;margin-top:10px;color:#f6e4b4">Pengenal tari dari sensor IMU: {ACC['imu']} pada penari yang belum pernah dilihat.</div></div></div>'''), W, H))
    C.append((R.card("p_uc5", W, H, '''<div style="position:absolute;left:110px;top:300px;width:760px"><div class=mono style="font-size:22px">Use case 5 · Kreator & pertunjukan</div>
      <div class="cin gold" style="font-size:72px;font-weight:700;line-height:1.08;margin-top:14px">Dari gerak nyata ke panggung digital</div>
      <div style="font-size:34px;color:#f6e4b4;margin-top:24px;line-height:1.35">Data NaraMotion menggerakkan avatar 3D, animasi, dan pertunjukan virtual tanpa kehilangan rasa geraknya.</div></div>'''), W, H))
    nums = [(ACC["putri"], "akurasi Kamera AI · 13 gerak putri"), (ACC["putra"], "akurasi · 11 gerak putra"), (ACC["imu"], "pengenal tari dari IMU"), (N_VID, "video tari Bali untuk melatih AI"), ("10", "node sensor · 9 sumbu · 100 Hz")]
    C.append((R.card("p_impact", W, H, f'''<div style="position:absolute;left:0;right:0;top:120px;text-align:center"><div class=mono style="font-size:22px">Hasil purwarupa</div>
      <div class="cin gold" style="font-size:78px;font-weight:700">Terukur, terbuka, siap dipakai</div></div>
      <div style="position:absolute;left:90px;right:90px;top:400px;display:grid;grid-template-columns:repeat(5,1fr);gap:24px">{"".join(
        f'<div class=frame style="padding:34px 22px;text-align:center"><div class=cin style="font-size:66px;font-weight:700;color:#ecc978">{v}</div><div style="font-size:25px;margin-top:10px;line-height:1.3">{t}</div></div>' for v, t in nums)}</div>
      <div style="position:absolute;left:0;right:0;bottom:120px;text-align:center;font-size:28px;color:#a9987a">Dilatih di Kaggle dari data terbuka (Mendeley Data, AIST++) · berjalan di peramban · naramotion.web.app</div>'''), W, H))
    C.append((R.card("p_end", W, H, f'''<div style="position:absolute;inset:0;background:radial-gradient(50% 55% at 50% 42%,rgba(18,13,7,.86),rgba(18,13,7,.55) 70%,rgba(18,13,7,.3))"></div>
      <div style="position:absolute;inset:0;display:grid;place-content:center;text-align:center;padding:0 160px">
      <div class="cin gold" style="font-size:118px;font-weight:800">NaraMotion</div>
      <div style="font-size:34px;font-style:italic;color:#f6e4b4;margin-top:6px">Tari diwariskan lewat tubuh. Kami menjaganya sebagai data.</div>
      <div style="display:flex;gap:40px;align-items:center;justify-content:center;margin:30px 0"><img src="{R.QR}" style="width:190px;border-radius:12px"><div style="text-align:left"><div class=cin style="font-size:42px;color:#ecc978">Coba sekarang</div><div class=mono style="font-size:30px;letter-spacing:.04em;text-transform:none;color:#f6e4b4">naramotion.web.app</div></div></div>
      <div style="font-size:28px;line-height:1.5">{R.TEAM}</div>
      <div style="font-size:16px;color:#a9987a;margin-top:26px;line-height:1.45">{R.CREDIT} · Model 3D tambahan: Semar (dimzxrecon), Keris (apasipepgapuak), Gerbang Trowulan (aan.javanese32) — Sketchfab, CC BY 4.0</div></div>''', bg=False), W, H))
    C.append((R.card("p_bg", W, H, ""), W, H))
    return C

# ---------- segmen ----------
def seq(folder):
    return ["-framerate", "24", "-i", str(folder / "%04d.png")]

def seg_seq(folder, dur, out, overlay=None, fade_in=None):
    """Urutan PNG (24 fps) diregangkan ke dur detik (gerak lambat bila perlu) + overlay kartu (opsional, dengan fade)."""
    n = len(list(folder.glob("*.png"))); src = n / 24.0; k = dur / src
    args = seq(folder); fc = f"[0:v]setpts={k:.4f}*PTS,fps={FPS},scale={W}:{H}[b]"
    if overlay:
        args += ["-loop", "1", "-t", str(dur), "-i", str(overlay)]
        fa = f",fade=t=in:st={fade_in[0]}:d={fade_in[1]}:alpha=1" if fade_in else ""
        fc += f";[1:v]format=rgba{fa}[o];[b][o]overlay=0:0:format=auto[v]"
    else: fc += ";[b]null[v]"
    R.run([*args, "-filter_complex", fc + ";[v]format=yuv420p[f]", "-map", "[f]", "-t", str(dur), "-r", str(FPS), str(out)])

def seg_cap(name, start, dur, out, crop="1280:720:320:120", label=None, label_h=300):
    args = ["-ss", str(start), "-t", str(dur), "-i", str(CAP / f"{name}.webm")]
    fc = f"[0:v]crop={crop},scale={W}:{H},fps={FPS}[c]"
    if label: args += ["-loop", "1", "-t", str(dur), "-i", str(label)]; fc += f";[c][1:v]overlay=0:{H - label_h}[v]"
    else: fc += ";[c]null[v]"
    R.run([*args, "-filter_complex", fc + ";[v]format=yuv420p[f]", "-map", "[f]", "-t", str(dur), "-r", str(FPS), str(out)])

def cat_hard(parts, out):
    lst = WORK / (out.stem + ".txt"); lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    R.run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])

def build():
    R.shoot(cards()); w = lambda n: WORK / f"{n}.png"
    D = [18, 8, 9, 8, 13, 13, 13, 13, 13, 8, 10]; P = []
    seg_seq(PR / "intro", D[0], WORK / "c01.mp4", overlay=w("p_title"), fade_in=(12.5, 2.0)); P.append(WORK / "c01.mp4")
    seg_seq(PR / "broll_B3", D[1], WORK / "c02.mp4", overlay=w("p_problem"), fade_in=(0.6, 1.0)); P.append(WORK / "c02.mp4")
    seg_seq(PR / "broll_B1", D[2], WORK / "c03.mp4", overlay=w("p_product"), fade_in=(0.8, 1.0)); P.append(WORK / "c03.mp4")
    R.seg_still(w("p_how"), D[3], WORK / "c04.mp4"); P.append(WORK / "c04.mp4")
    kc = CAPM["kelas-cam"]; seg_cap("kelas-cam", max(0, kc["ready"] - 1), D[4], WORK / "c05.mp4", crop="1440:810:240:170", label=w("p_uc1")); P.append(WORK / "c05.mp4")
    sr = CAPM["studio-rec"]   # studio merekam 8,5 s → arsip menampilkan sesi 4,5 s
    seg_cap("studio-rec", sr["ready"], 8.5, WORK / "c06a.mp4", label=w("p_uc2"))
    seg_cap("studio-rec", sr["total"] - 4.6, 4.5, WORK / "c06b.mp4", crop="1280:720:320:330", label=w("p_uc2"))
    cat_hard([WORK / "c06a.mp4", WORK / "c06b.mp4"], WORK / "c06.mp4"); P.append(WORK / "c06.mp4")
    seg_seq(PR / "broll_B2", 7.5, WORK / "c07a.mp4", overlay=w("p_uc3_full") if (WORK / "p_uc3_full.png").exists() else None)
    ar = CAPM["arsip"]; seg_cap("arsip", ar["ready"], 5.5, WORK / "c07b.mp4", label=w("p_uc3"))
    # label UC3 juga di atas B-roll museum
    R.run(["-i", str(WORK / "c07a.mp4"), "-loop", "1", "-t", "7.5", "-i", str(w("p_uc3")), "-filter_complex", f"[0:v][1:v]overlay=0:{H - 300},format=yuv420p[v]", "-map", "[v]", "-t", "7.5", str(WORK / "c07a2.mp4")])
    cat_hard([WORK / "c07a2.mp4", WORK / "c07b.mp4"], WORK / "c07.mp4"); P.append(WORK / "c07.mp4")
    R.seg_still(w("p_uc4"), D[7], WORK / "c08.mp4"); P.append(WORK / "c08.mp4")
    # UC5: penari emas menari (loop RGBA) di atas kartu + cuplikan Studio mocap kecil
    st = CAPM["studio"]
    R.run(["-loop", "1", "-t", str(D[8]), "-i", str(w("p_uc5")), "-stream_loop", "3", "-framerate", "24", "-i", str(ROOT / "assets_src/showreel/dancer_loop/%04d.png"),
           "-ss", str(st["ready"]), "-t", str(D[8]), "-i", str(CAP / "studio.webm"), "-filter_complex",
           f"[1:v]scale=900:900[d];[2:v]crop=1280:720:320:120,scale=560:-2[s];[0:v][d]overlay=930:90:shortest=0[a];[a][s]overlay=1290:700:eof_action=repeat,fps={FPS},format=yuv420p[v]",
           "-map", "[v]", "-t", str(D[8]), str(WORK / "c09.mp4")]); P.append(WORK / "c09.mp4")
    R.seg_still(w("p_impact"), D[9], WORK / "c10.mp4"); P.append(WORK / "c10.mp4")
    seg_seq(PR / "broll_B4", D[10], WORK / "c11.mp4", overlay=w("p_end"), fade_in=(1.0, 1.5)); P.append(WORK / "c11.mp4")
    total = sum(D) - XF * (len(D) - 1)
    R.XF = XF; R.concat(P, D, R.OUTDIR / "naramotion_profil_produk.mp4", PR / "music_profile.wav", total)
    print("profil", total, "s")

if __name__ == "__main__":
    missing = [d for d in ["intro", "broll_B1", "broll_B2", "broll_B3", "broll_B4"] if not list((PR / d).glob("*.png"))]
    if missing: sys.exit(f"render belum ada: {missing}")
    build()
