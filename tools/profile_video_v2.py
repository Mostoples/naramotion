"""Video profil NaraMotion v2 — bahasa Inggris, narator (edge-tts), 60 fps, 1920x1080.
Bahan: assets_src/profile60/{intro,broll_B1..B4}/ (render sub-frame 60 fps), clips/uc3d_*.mp4, vo/*.mp3, narration.json, music.wav;
rekaman aplikasi assets_src/showreel/captures/. Kartu teks dirender dari HTML pada 4K (zoom halus), lalu disusun FFmpeg.
Pemakaian: FFMPEG=<path> python tools/profile_video_v2.py  →  media/naramotion_product_profile_EN_60fps.mp4
"""
import sys, json, glob, os, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import showreel as R

ROOT = R.ROOT; P = ROOT / "assets_src" / "profile60"; CAP = ROOT / "assets_src" / "showreel" / "captures"
WORK = P / "_work"; WORK.mkdir(parents=True, exist_ok=True); R.WORK = WORK
W, H, FPS, XF = 1920, 1080, 60, 0.6
VO = {n["id"]: n for n in json.load(open(P / "narration.json", encoding="utf-8"))}
CAPM = json.loads((CAP / "captures.json").read_text()); ACC = {k: v.replace(",", ".") for k, v in R.ACC.items()}; img = R.img   # desimal gaya Inggris
def run(a): R.run(a)

# ---------- kartu & label (HTML → PNG 4K, latar transparan bila overlay) ----------
def card(name, body, bg=True, h=H):
    f = R.card(name, W, h, body, bg=bg); return (f, W, h)
def shoot4k(cards):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        for f, w, h in cards:
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
            pg.goto(f.as_uri(), wait_until="load", timeout=60000); pg.wait_for_function("document.fonts.status === 'loaded'", timeout=30000); pg.wait_for_timeout(400)
            pg.screenshot(path=str(f.with_suffix(".png")), omit_background=True); pg.close()
        b.close()

def lower(name, tag, title, sub=""):
    return card(name, f'''<div style="position:absolute;left:70px;bottom:64px;max-width:1240px" class=frame><div style="padding:20px 32px">
      <div class=mono style="font-size:19px">{tag}</div><div class="cin gold" style="font-size:46px;font-weight:700;line-height:1.1;margin-top:6px">{title}</div>
      {f'<div style="font-size:27px;color:#f6e4b4;margin-top:8px;line-height:1.35">{sub}</div>' if sub else ''}</div></div>''', bg=False)

def cards():
    C = []
    C.append(card("e_title", '''<div style="position:absolute;left:0;right:0;top:110px;text-align:center">
      <div class=jw style="font-size:46px">꧁ ꦤꦫ ꧂</div><div class="cin gold" style="font-size:150px;font-weight:800;line-height:1;text-shadow:0 0 50px rgba(0,0,0,.6)">NaraMotion</div>
      <div class=mono style="font-size:24px;margin-top:18px">Motion capture · 9-DoF sensing · artificial intelligence</div></div>''', bg=False))
    C.append(card("e_problem", '''<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(18,13,7,.88) 0,rgba(18,13,7,.6) 42%,rgba(18,13,7,0) 70%)"></div>
      <div style="position:absolute;left:120px;top:330px;width:780px"><div class=mono style="font-size:22px">The challenge</div>
      <div class="cin gold" style="font-size:74px;font-weight:700;line-height:1.08;margin-top:16px">Every gesture holds knowledge.</div>
      <div style="font-size:34px;color:#f6e4b4;margin-top:24px;line-height:1.35">Passed from master to student — and at risk when masters retire.</div></div>''', bg=False))
    C.append(card("e_solution", '''<div style="position:absolute;inset:0;background:linear-gradient(270deg,rgba(18,13,7,.85) 0,rgba(18,13,7,.55) 40%,rgba(18,13,7,0) 68%)"></div>
      <div style="position:absolute;right:120px;top:300px;width:740px;text-align:right"><div class=mono style="font-size:22px">The solution</div>
      <div class="cin gold" style="font-size:96px;font-weight:800;line-height:1;margin-top:16px">NaraMotion</div>
      <div style="font-size:36px;color:#f6e4b4;margin-top:24px;line-height:1.35">10 wearable nodes · 9 axes each · 100 times per second</div></div>''', bg=False))
    steps = [("node", "Wear", "10 GY-85 nodes on head, torso, arms and legs"), ("gyro", "Fuse", "Madgwick filter → 3D orientation, 100 Hz"),
             ("dial", "Understand", "AI recognises movements and scores every joint"), ("lontar", "Preserve", "Performances archived for teaching and research")]
    C.append(card("e_how", f'''<div style="position:absolute;left:0;right:0;top:110px;text-align:center"><div class=mono style="font-size:22px">How it works</div>
      <div class="cin gold" style="font-size:80px;font-weight:700">From movement to archive</div></div>
      <div style="position:absolute;left:110px;right:110px;top:380px;display:grid;grid-template-columns:repeat(4,1fr);gap:30px">{"".join(
        f'<div class=frame style="padding:34px 28px;text-align:center"><div class=cin style="font-size:30px;color:#8d6a2c">{"I II III IV".split()[i]}</div><img src="{img("assets/3d/" + ic + ".webp")}" style="width:150px;margin:8px 0"><div class=cin style="font-size:40px;color:#ecc978">{t}</div><div style="font-size:27px;margin-top:10px;line-height:1.35">{d}</div></div>'
        for i, (ic, t, d) in enumerate(steps))}</div>'''))
    C.append(lower("e_uc1", "Use case 1 · Dance class", "An AI coach in every classroom", f"Recognises 24 Balinese basic movements ({ACC['putri']} accuracy) and scores every joint."))
    C.append(lower("e_uc2", "Use case 2 · Masters & documentation", "Every performance becomes data", "10 body segments recorded 100 times per second, saved to the archive."))
    C.append(card("e_uc3d", '''<div style="position:absolute;left:40px;top:40px" class=frame><div style="padding:14px 24px"><div class=mono style="font-size:18px">Use case 3 · 3D from video</div><div class=cin style="font-size:32px;color:#ecc978">SAM 3D Body — every finger</div></div></div>
      <div style="position:absolute;left:1000px;top:40px" class=frame><div style="padding:14px 24px"><div class=mono style="font-size:18px">Retargeted animation</div><div class=cin style="font-size:32px;color:#ecc978">Motion2MixamoRig character</div></div></div>''', bg=False))
    C.append(lower("e_uc3", "Use case 4 · Museums & archives", "Living digital heritage", "Dance preserved alongside wayang, gamelan and keris."))
    jv = sorted(glob.glob(str(ROOT / "ml/runs/javanese/javanese_character.png")))
    C.append(card("e_uc4", f'''<div style="position:absolute;left:110px;top:90px"><div class=mono style="font-size:22px">Use case 5 · Researchers & universities</div>
      <div class="cin gold" style="font-size:70px;font-weight:700;line-height:1.05;margin-top:12px">Measuring what makes a dance <i>alus</i> or <i>gagah</i></div></div>
      <div style="position:absolute;left:110px;right:110px;top:330px;display:grid;grid-template-columns:1.35fr 1fr;gap:40px;align-items:center">
        <div class=frame style="padding:18px"><img src="{Path(jv[0]).as_uri() if jv else ''}" style="width:100%;border-radius:10px"></div>
        <div><div class=cin style="font-size:120px;font-weight:800;color:#ecc978;line-height:1">3–4×</div><div style="font-size:38px;color:#f6e4b4;line-height:1.3;margin-top:10px">less wrist jerk in refined (<i>alus</i>) characters than in strong (<i>gagah</i>) ones</div>
        <div style="font-size:24px;color:#a9987a;margin-top:18px">Javanese dance, VICON motion capture (Escobar Varela &amp; Hernández-Barraza, 2019)</div></div></div>'''))
    nums = [(ACC["putri"], "AI accuracy · 13 female Balinese movements"), (ACC["putra"], "AI accuracy · 11 male movements"), (ACC["imu"], "dance recognition from IMU sensors"),
            ("2,568", "open dance videos used for training"), ("10", "sensor nodes · 9 axes · 100 Hz")]
    C.append(card("e_impact", f'''<div style="position:absolute;left:0;right:0;top:120px;text-align:center"><div class=mono style="font-size:22px">Prototype results</div>
      <div class="cin gold" style="font-size:80px;font-weight:700">Measured. Open. Ready to use.</div></div>
      <div style="position:absolute;left:90px;right:90px;top:400px;display:grid;grid-template-columns:repeat(5,1fr);gap:24px">{"".join(
        f'<div class=frame style="padding:34px 22px;text-align:center"><div class=cin style="font-size:66px;font-weight:700;color:#ecc978">{v.replace(",", ".") if "%" in v else v}</div><div style="font-size:26px;margin-top:10px;line-height:1.3">{t}</div></div>' for v, t in nums)}</div>
      <div style="position:absolute;left:0;right:0;bottom:120px;text-align:center;font-size:30px;color:#a9987a">Runs entirely in the browser · no studio required · naramotion.web.app</div>'''))
    credit = ("Data: Hendrawan et al., Woman/Male Basic Balinese Dance Movement (Mendeley Data, CC BY 4.0) · AIST++ (Li et al., ICCV 2021, CC BY 4.0) · "
              "Turkish Folk Dance IMU (CC BY 4.0) · Escobar Varela &amp; Hernández-Barraza (2019) · SAM 3D Body (Meta, SAM License) · Motion2MixamoRig, GVHMR, HaMeR, SMPL-X, MANO, Mixamo · "
              "3D models (Sketchfab): Virtual Museums of Małopolska (CC0), eventdesignws, giga, mokhammadsoni, dimzxrecon, apasipepgapuak, aan.javanese32 (CC BY 4.0) · "
              "Voice: Microsoft neural TTS · Music: original synthesized gamelan · Sensor data in the demo is simulated")
    C.append(card("e_end", f'''<div style="position:absolute;inset:0;background:radial-gradient(52% 58% at 50% 44%,rgba(18,13,7,.86),rgba(18,13,7,.55) 70%,rgba(18,13,7,.3))"></div>
      <div style="position:absolute;inset:0;display:grid;place-content:center;text-align:center;padding:0 150px">
      <div class="cin gold" style="font-size:120px;font-weight:800">NaraMotion</div>
      <div style="font-size:36px;font-style:italic;color:#f6e4b4;margin-top:4px">Dance is inherited through the body. We keep it as data.</div>
      <div style="display:flex;gap:40px;align-items:center;justify-content:center;margin:30px 0"><img src="{R.QR}" style="width:190px;border-radius:12px"><div style="text-align:left"><div class=cin style="font-size:44px;color:#ecc978">Try it today</div><div class=mono style="font-size:32px;letter-spacing:.04em;text-transform:none;color:#f6e4b4">naramotion.web.app</div></div></div>
      <div style="font-size:28px;line-height:1.5">{R.TEAM}</div>
      <div style="font-size:15px;color:#a9987a;margin-top:24px;line-height:1.45">{credit}</div></div>''', bg=False))
    return C

# ---------- segmen (semua 60 fps) ----------
def enc(): return ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS)]
def seq(folder, dur, out, overlay=None, fade=(0.5, 0.8)):
    """urutan PNG 60 fps (tanpa peregangan) + overlay kartu 4K (fade-in)"""
    n = len(list(folder.glob("*.png"))); args = ["-framerate", str(FPS), "-i", str(folder / "%04d.png")]
    fc = f"[0:v]scale={W}:{H}:flags=lanczos,tpad=stop_mode=clone:stop_duration=3[b]"
    if overlay:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", str(overlay)]
        fc += f";[1:v]scale={W}:{H}:flags=lanczos,format=rgba,fade=t=in:st={fade[0]}:d={fade[1]}:alpha=1[o];[b][o]overlay=0:0[v]"
    else: fc += ";[b]null[v]"
    run([*args, "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *enc(), str(out)])
def still(png, dur, out, zoom=0.035):
    """kartu 4K → zoom halus: skala per-frame di 4K lalu potong & perkecil (tanpa lompatan piksel)"""
    fc = (f"[0:v]scale=w='trunc(3840*(1+{zoom}*t/{dur})/2)*2':h=-2:eval=frame:flags=bicubic,"
          f"crop=3840:2160,scale={W}:{H}:flags=lanczos,format=yuv420p[v]")
    run(["-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", str(png), "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *enc(), str(out)])
def capture(name, start, dur, out, crop="1280:720:320:120", label=None):
    args = ["-ss", str(start), "-t", str(dur), "-i", str(CAP / f"{name}.webm")]
    fc = f"[0:v]crop={crop},scale={W}:{H}:flags=lanczos,fps={FPS}[c]"
    if label: args += ["-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", str(label)]; fc += f";[1:v]scale={W}:-2:flags=lanczos[l];[c][l]overlay=0:{H}-overlay_h[v]"
    else: fc += ";[c]null[v]"
    run([*args, "-filter_complex", fc, "-map", "[v]", "-t", str(dur), *enc(), str(out)])
def concat_v(parts, out):
    args = []; [args.extend(["-i", str(p)]) for p in parts]
    fc = "".join(f"[{i}:v]fps={FPS},settb=1/{FPS*1000},setpts=PTS-STARTPTS[x{i}];" for i in range(len(parts))) + "".join(f"[x{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[v]"
    run([*args, "-filter_complex", fc, "-map", "[v]", *enc(), str(out)])
def overlay_full(video, png, out, dur):
    run(["-i", str(video), "-loop", "1", "-framerate", str(FPS), "-t", str(dur), "-i", str(png), "-filter_complex",
         f"[1:v]scale={W}:{H}:flags=lanczos,format=rgba,fade=t=in:st=0.4:d=0.8:alpha=1[o];[0:v][o]overlay=0:0[v]", "-map", "[v]", "-t", str(dur), *enc(), str(out)])

def build():
    shoot4k(cards()); w = lambda n: WORK / f"{n}.png"; vo = lambda k: VO[k]["dur"]
    S = []   # (file, dur, vo_id, vo_offset)
    D = dict(intro=18.0, problem=round(vo("problem") + 1.4, 2), solution=round(vo("solution") + 1.4, 2), how=round(vo("how") + 1.4, 2),
             uc1=round(vo("uc1") + 1.4, 2), uc2=round(vo("uc2") + 1.4, 2), uc3=round(vo("uc3") + 1.4, 2), uc4=round(vo("uc4") + 1.4, 2),
             impact=round(vo("impact") + 1.4, 2), outro=12.0)
    seq(P / "intro", D["intro"], WORK / "s01.mp4", overlay=w("e_title"), fade=(12.6, 2.2)); S.append((WORK / "s01.mp4", D["intro"], "intro", 1.8))
    seq(P / "broll_B3", D["problem"], WORK / "s02.mp4", overlay=w("e_problem")); S.append((WORK / "s02.mp4", D["problem"], "problem", 0.6))
    seq(P / "broll_B1", D["solution"], WORK / "s03.mp4", overlay=w("e_solution")); S.append((WORK / "s03.mp4", D["solution"], "solution", 0.6))
    still(w("e_how"), D["how"], WORK / "s04.mp4"); S.append((WORK / "s04.mp4", D["how"], "how", 0.6))
    kc = CAPM["kelas-cam"]; capture("kelas-cam", max(0, kc["ready"] - 0.5), D["uc1"], WORK / "s05.mp4", crop="1440:810:240:170", label=w("e_uc1")); S.append((WORK / "s05.mp4", D["uc1"], "uc1", 0.6))
    sr = CAPM["studio-rec"]; a = round(D["uc2"] - 3.6, 2)
    capture("studio-rec", sr["ready"], a, WORK / "s06a.mp4", label=w("e_uc2"))
    capture("studio-rec", sr["total"] - 3.7, 3.6, WORK / "s06b.mp4", crop="1280:720:320:330", label=w("e_uc2"))
    concat_v([WORK / "s06a.mp4", WORK / "s06b.mp4"], WORK / "s06.mp4"); S.append((WORK / "s06.mp4", D["uc2"], "uc2", 0.6))
    concat_v([P / "clips/uc3d_Agem_Kanan_101.mp4", P / "clips/uc3d_Nyeregseg_23.mp4"], WORK / "s07a.mp4")
    d07 = float(subprocess.run([__import__("os").path.join(__import__("os").path.dirname(R.FF), "ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(WORK / "s07a.mp4")], capture_output=True, text=True).stdout or 12.3)
    overlay_full(WORK / "s07a.mp4", w("e_uc3d"), WORK / "s07.mp4", d07); S.append((WORK / "s07.mp4", round(d07, 2), "uc3d", 0.6))
    seq(P / "broll_B2", D["uc3"], WORK / "s08.mp4", overlay=w("e_uc3")); S.append((WORK / "s08.mp4", D["uc3"], "uc3", 0.6))
    still(w("e_uc4"), D["uc4"], WORK / "s09.mp4"); S.append((WORK / "s09.mp4", D["uc4"], "uc4", 0.6))
    still(w("e_impact"), D["impact"], WORK / "s10.mp4"); S.append((WORK / "s10.mp4", D["impact"], "impact", 0.6))
    seq(P / "broll_B4", D["outro"], WORK / "s11.mp4", overlay=w("e_end"), fade=(1.0, 1.5)); S.append((WORK / "s11.mp4", D["outro"], "outro", 0.9))

    # video: crossfade berurutan
    args = []; [args.extend(["-i", str(f)]) for f, *_ in S]
    fc, last, off, starts = [], "[0:v]", 0.0, [0.0]
    for i in range(1, len(S)):
        off += S[i - 1][1] - XF; starts.append(off)
        fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]"); last = f"[x{i}]"
    total = starts[-1] + S[-1][1]
    # audio: narasi pada awal tiap adegan + musik yang ditekan (sidechain) saat narator bicara
    n = len(S); ai = []
    for k, (_, _, vid, voff) in enumerate(S):
        args += ["-i", str(P / f"vo/{vid}.mp3")]; ai.append((n + k, int((starts[k] + voff) * 1000)))
    args += ["-i", str(P / "music.wav")]; mi = n + len(S)
    for j, (idx, ms) in enumerate(ai): fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume=1.0[v{j}]")
    fc.append("".join(f"[v{j}]" for j in range(len(ai))) + f"amix=inputs={len(ai)}:normalize=0:duration=longest,apad=whole_dur={total}[vo]")
    fc.append("[vo]asplit=2[vo1][vo2]")
    fc.append(f"[{mi}:a]atrim=0:{total},volume=0.55[mu]")
    fc.append("[mu][vo1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck]")
    fc.append(f"[duck][vo2]amix=inputs=2:normalize=0,afade=t=out:st={total - 3}:d=3,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    out = R.OUTDIR / "naramotion_product_profile_EN_60fps.mp4"
    run([*args, "-filter_complex", ";".join(fc), "-map", last, "-map", "[a]", "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)])
    print("profil EN", round(total, 1), "s ->", out)

if __name__ == "__main__":
    miss = [d for d in ["intro", "broll_B1", "broll_B2", "broll_B3", "broll_B4"] if not list((P / d).glob("*.png"))]
    if miss: sys.exit(f"render belum ada: {miss}")
    build()
