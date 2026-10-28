"""Adegan "3D dari video" untuk video profil (1920x1080, 60 fps):
kiri = video penari asli + kerangka SAM 3D Body (70 titik, jari) yang diinterpolasi ke 60 fps,
kanan = karakter Y Bot hasil Motion2MixamoRig (video 30 fps, frame digandakan ke 60 fps).
Pemakaian: python tools/uc3d_clip.py <klip> <out.mp4>   (klip: Agem_Kanan_101 | Nyeregseg_23 | Ulap_Ulap_80)
"""
import sys, subprocess, shutil
from pathlib import Path
import numpy as np, cv2

ROOT = Path(__file__).resolve().parents[1]
clip, out = sys.argv[1], Path(sys.argv[2])
import os
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
d = np.load(ROOT / f"ml/runs/sam3d/{clip}.npz")
P3 = d["pred_keypoints_3d"] + d["pred_cam_t"][:, None]; f = d["focal"]; t = d["t"]
src = cv2.VideoCapture(str(ROOT / f"assets_src/m2mr/kaggle_ds/{clip}.mp4")); fps_src = src.get(5); W0, H0 = int(src.get(3)), int(src.get(4))
frames = []
while True:
    ok, fr = src.read()
    if not ok: break
    frames.append(fr)
ybot = cv2.VideoCapture(str(ROOT / f"ml/runs/m2mr/out/{clip}/videos/mixamo_character.mp4")); yb = []
while True:
    ok, fr = ybot.read()
    if not ok: break
    yb.append(fr)
B = [(5, 6), (5, 7), (6, 8), (9, 10), (5, 9), (6, 10), (9, 11), (11, 13), (10, 12), (12, 14), (7, 62), (8, 41), (0, 69), (69, 5), (69, 6), (13, 17), (13, 15), (14, 20), (14, 18)]
F = []
for base, off in ((41, 0), (62, 21)):
    for tip in range(21 + off, 41 + off, 4): ch = [base, tip + 3, tip + 2, tip + 1, tip]; F += list(zip(ch[:-1], ch[1:]))
GOLD, GOLD2 = (120, 201, 236), (74, 165, 210)    # BGR emas
OUTW, OUTH, FPS = 1920, 1080, 60
dur = len(frames) / fps_src
# kerangka 2D per waktu: proyeksi titik 3D, interpolasi linear antar-sampel (10 fps) → mulus di 60 fps
uv = np.stack([f[:, None] * P3[..., 0] / P3[..., 2] + W0 / 2, f[:, None] * P3[..., 1] / P3[..., 2] + H0 / 2], -1)   # (N,70,2)
def kp_at(tt):
    i = np.searchsorted(t, tt) - 1; i = int(np.clip(i, 0, len(t) - 2)); w = float(np.clip((tt - t[i]) / max(t[i + 1] - t[i], 1e-6), 0, 1))
    return uv[i] * (1 - w) + uv[i + 1] * w
cmd = [FF, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OUTW}x{OUTH}", "-r", str(FPS), "-i", "-",
       "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", str(out)]
pp = subprocess.Popen(cmd, stdin=subprocess.PIPE)
n_out = int(dur * FPS)
# panel kiri: potong video ke rasio 960x1080 di sekitar penari
cx = int(np.median(uv[:, [5, 6, 9, 10], 0])); cw = int(H0 * 960 / 1080); x0 = int(np.clip(cx - cw // 2, 0, W0 - cw))
for k in range(n_out):
    tt = k / FPS; fr = frames[min(int(tt * fps_src), len(frames) - 1)].copy()
    kp = kp_at(tt)
    ov = fr.copy()
    for a, b in B: cv2.line(ov, tuple(map(int, kp[a])), tuple(map(int, kp[b])), GOLD, 5, cv2.LINE_AA)
    for a, b in F: cv2.line(ov, tuple(map(int, kp[a])), tuple(map(int, kp[b])), GOLD2, 2, cv2.LINE_AA)
    for j in (0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 41, 62): cv2.circle(ov, tuple(map(int, kp[j])), 6, (230, 240, 250), -1, cv2.LINE_AA)
    fr = cv2.addWeighted(cv2.convertScaleAbs(fr, alpha=0.7, beta=-10), 1.0, ov, 0, 0); fr = cv2.addWeighted(fr, 0.25, ov, 0.75, 0)
    left = cv2.resize(fr[:, x0:x0 + cw], (960, 1080), interpolation=cv2.INTER_AREA)
    yf = yb[min(int(tt * fps_src), len(yb) - 1)]; yh, yw = yf.shape[:2]; s = 1080 / yh
    yr = cv2.resize(yf, (int(yw * s), 1080), interpolation=cv2.INTER_AREA); xc = (yr.shape[1] - 960) // 2
    right = yr[:, max(0, xc):max(0, xc) + 960]
    if right.shape[1] < 960: right = cv2.copyMakeBorder(right, 0, 0, 0, 960 - right.shape[1], cv2.BORDER_CONSTANT, value=(20, 20, 20))
    canvas = np.hstack([left, right]); canvas[:, 958:962] = (74, 165, 210)
    pp.stdin.write(canvas.tobytes())
pp.stdin.close(); pp.wait(); print(out, f"{dur:.2f} s", n_out, "frame")
