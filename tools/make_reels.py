"""Video vertikal (9:16) untuk feed "Reels" NaraMotion + video hero.
- Gerak dasar Bali: klip Mendeley (CC BY 4.0) → potongan 3:4 di sekitar penari (deteksi orang HOG) di atas latar blur.
- Gambyong: animasi penari emas NaraMotion (assets_src/showreel/dancer_loop) di atas latar gelap.
Pemakaian: python tools/make_reels.py <folder_klip_mentah>
"""
import json, os, shutil, subprocess, sys
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[1]; RAW = Path(sys.argv[1]); OUT = ROOT / "assets/reels"; OUT.mkdir(parents=True, exist_ok=True)
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
run = lambda a: subprocess.run([FF, "-loglevel", "error", "-y", *a], check=True)

def dancer_cx(path):
    """posisi x tengah penari (0..1): pusat massa piksel yang bergerak (beda antar-frame) sepanjang klip"""
    cap = cv2.VideoCapture(str(path)); prev = None; acc = None
    while True:
        ok, fr = cap.read()
        if not ok: break
        g = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(fr, (320, 180)), cv2.COLOR_BGR2GRAY), (5, 5), 0).astype(np.float32)
        if prev is not None:
            d = np.abs(g - prev); d[d < 12] = 0; acc = d.sum(0) if acc is None else acc + d.sum(0)
        prev = g
    if acc is None or acc.sum() == 0: return 0.5
    return float((acc * np.arange(len(acc))).sum() / acc.sum() / len(acc))

OVERRIDE = {"putra__Seledet": 0.66}   # close-up wajah: gerak kecil, pusat gerak salah terbaca

def bali(src, dst):
    cx = OVERRIDE.get(Path(src).stem) or dancer_cx(src)
    vf = (f"split[a][b];[a]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=24:2,eq=brightness=-0.18:saturation=0.7[bg];"
          f"[b]crop=ih*3/4:ih:max(0\\,min(iw-ih*3/4\\,iw*{cx:.3f}-ih*3/8)):0,scale=720:960[fg];[bg][fg]overlay=0:(H-h)/2,fps=30")
    run(["-i", str(src), "-t", "8", "-vf", vf, *ENC, str(dst)])
    return cx

def poster(src, dst):
    run(["-ss", "1", "-i", str(src), "-frames:v", "1", "-vf", "scale=360:640", "-q:v", "6", str(dst)])

idx = json.load(open(ROOT / "assets/ml/anim/m2mr/index.json")); items = []

# 1) Gambyong (animasi NaraMotion) dulu: tari khas Solo diutamakan
g = OUT / "gambyong.mp4"
run(["-framerate", "24", "-i", str(ROOT / "assets_src/showreel/dancer_loop/%04d.png"), "-f", "lavfi", "-i", "color=c=0x140e07:s=720x1280:r=24",
     "-filter_complex", "[0]scale=720:720,format=rgba[d];[1][d]overlay=0:300:shortest=1,vignette=PI/4", "-t", "8", *ENC, str(g)])
poster(g, OUT / "gambyong.jpg")
items.append(dict(id="gambyong", file="gambyong", title="Gambyong", region="Surakarta, Jawa Tengah", kind="anim",
                  note="Animasi penari NaraMotion (bukan rekaman penari).", ds=None, move=None))

# 2) 24 gerak dasar Bali (rekaman penari asli)
for r in idx:
    src = RAW / f"{r['key']}.mp4"
    if not src.exists(): print("lewati", r["key"]); continue
    dst = OUT / f"{r['key']}.mp4"; cx = bali(src, dst); poster(dst, OUT / f"{r['key']}.jpg")
    items.append(dict(id=r["key"], file=r["key"], title=r["gerak"], region=f"Bali · gerak dasar {r['ds']}", kind="video",
                      note=f"Klip {r['clip'].replace('_', ' ')} · Hendrawan dkk., Mendeley Data, CC BY 4.0.", ds=r["ds"], move=r["gerak"]))
    print(r["key"], f"cx={cx:.2f}", dst.stat().st_size // 1024, "KB")

json.dump(items, open(OUT / "reels.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)

# video hero dibuat terpisah: tools/make_hero.sh (render 3D tanpa teks)
print(len(items), "reels")
