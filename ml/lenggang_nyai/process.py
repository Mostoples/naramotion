"""NaraMotion · M6: keyframe Kinect Tari Lenggang Nyai (Betawi) → urutan gerak acuan + arah 10 segmen.

Sumber: game "Cool Tour Dance" (Imagine Cup Indonesia 2013), github.com/nandafirdaus/cool-tour-dance (tanpa lisensi —
dipakai internal dengan kredit). Tiap file = satu keyframe: 20 sendi Kinect v1 (x, y, z meter); nama file = indeks frame.
Pemakaian: python ml/lenggang_nyai/process.py <folder keluaran>
Keluaran: lenggang_nyai.json (urutan sendi + vektor arah 10 segmen), lenggang_nyai_strip.png (QA)
"""
import sys, json, urllib.request, urllib.parse
from pathlib import Path
import numpy as np

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True); RAW = OUT / "raw"; RAW.mkdir(exist_ok=True)
API = "https://api.github.com/repos/nandafirdaus/cool-tour-dance/git/trees/master?recursive=1"
BASE = "https://raw.githubusercontent.com/nandafirdaus/cool-tour-dance/master/"
tree = json.load(urllib.request.urlopen(API))["tree"]
files = sorted((x["path"] for x in tree if x["path"].endswith(".csv") and "GameNuclexContent/data/Dance/Play" in x["path"]),
               key=lambda p: int(Path(p).stem))
frames, idx = [], []
for p in files:
    f = RAW / Path(p).name
    if not f.exists(): f.write_bytes(urllib.request.urlopen(BASE + urllib.parse.quote(p)).read())
    rows = [l.split(",") for l in f.read_text("utf-8", errors="replace").splitlines() if l.count(",") == 3]
    J = {r[0].strip(): [float(v) for v in r[1:]] for r in rows}
    if len(J) >= 20: frames.append(J); idx.append(int(Path(p).stem))
names = list(frames[0]); P = np.array([[fr[n] for n in names] for fr in frames])   # (K,20,3)
print(len(frames), "keyframe, sendi:", names, "indeks", idx[:5], "…", idx[-1])

SEG = {"kepala": ("ShoulderCenter", "Head"), "badan": ("HipCenter", "ShoulderCenter"),
       "lengan_atas_ki": ("ShoulderLeft", "ElbowLeft"), "lengan_bawah_ki": ("ElbowLeft", "WristLeft"),
       "lengan_atas_ka": ("ShoulderRight", "ElbowRight"), "lengan_bawah_ka": ("ElbowRight", "WristRight"),
       "paha_ki": ("HipLeft", "KneeLeft"), "betis_ki": ("KneeLeft", "AnkleLeft"),
       "paha_ka": ("HipRight", "KneeRight"), "betis_ka": ("KneeRight", "AnkleRight")}
g = lambda n: P[:, names.index(n)]
dirs = {s: (lambda v: (v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)).round(4).tolist())(g(b) - g(a)) for s, (a, b) in SEG.items()}
json.dump(dict(dance="Lenggang Nyai (Betawi)", source="Cool Tour Dance (Imagine Cup Indonesia 2013), github.com/nandafirdaus/cool-tour-dance",
               frame_index=idx, joints=names, positions=P.round(4).tolist(), segment_dirs=dirs, note="arah segmen tanpa puntiran (Kinect v1)"),
          open(OUT / "lenggang_nyai.json", "w", encoding="utf-8"), ensure_ascii=False)

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
BONES = [("Head", "ShoulderCenter"), ("ShoulderCenter", "Spine"), ("Spine", "HipCenter"), ("ShoulderCenter", "ShoulderLeft"),
         ("ShoulderLeft", "ElbowLeft"), ("ElbowLeft", "WristLeft"), ("WristLeft", "HandLeft"), ("ShoulderCenter", "ShoulderRight"),
         ("ShoulderRight", "ElbowRight"), ("ElbowRight", "WristRight"), ("WristRight", "HandRight"), ("HipCenter", "HipLeft"),
         ("HipLeft", "KneeLeft"), ("KneeLeft", "AnkleLeft"), ("AnkleLeft", "FootLeft"), ("HipCenter", "HipRight"),
         ("HipRight", "KneeRight"), ("KneeRight", "AnkleRight"), ("AnkleRight", "FootRight")]
pick = np.linspace(0, len(frames) - 1, 12).astype(int)
fig, axs = plt.subplots(1, 12, figsize=(13, 2.6)); fig.patch.set_facecolor("#1b150d")
for ax, k in zip(axs, pick):
    for a, b in BONES:
        if a in names and b in names:
            pa, pb = P[k, names.index(a)], P[k, names.index(b)]; ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color="#ecc978", lw=1.6)
    ax.set_aspect("equal"); ax.axis("off"); ax.set_title(str(idx[k]), color="#a9987a", fontsize=7)
fig.suptitle("Lenggang Nyai — 12 dari %d keyframe Kinect (Cool Tour Dance, 2013)" % len(frames), color="#f6e4b4", fontsize=9)
fig.savefig(OUT / "lenggang_nyai_strip.png", dpi=110, facecolor=fig.get_facecolor()); print("SELESAI")
