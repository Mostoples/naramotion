"""Hasil SAM 3D Body (npz per klip, 70 titik MHR) → assets/ml/sam3d_clips.json untuk Studio NaraMotion.

Sumbu kamera (x kanan, y bawah, z menjauh) → dunia NaraMotion (y atas, penari menghadap +z, kiri penari = +x).
Per frame: pinggul dipusatkan di x/z, kaki terendah dikunci ke lantai; penghalusan 3 frame. Jari: 5 rantai per tangan.
Pemakaian: python tools/sam3d_to_web.py <folder npz> [<folder npz> ...]
"""
import sys, json, glob
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GERAK = {"Agem_Kanan": "Agem Kanan", "Nyeregseg": "Nyeregseg", "Ulap_Ulap": "Ulap-Ulap"}
J = {"nose": 0, "neck": 69, "shoulderL": 5, "shoulderR": 6, "elbowL": 7, "elbowR": 8, "wristL": 62, "wristR": 41, "handL": 53, "handR": 32,
     "hipL": 9, "hipR": 10, "kneeL": 11, "kneeR": 12, "ankleL": 13, "ankleR": 14, "toeL": 15, "toeR": 18}
# rantai jari: pergelangan → sendi pangkal → sendi tengah → sendi ujung → ujung jari
FINGERS = [[base] + [tip + 3, tip + 2, tip + 1, tip] for base, off in ((62, 21), (41, 0)) for tip in range(21 + off, 41 + off, 4)]

def to_world(P):
    return np.stack([P[..., 0], -P[..., 1], -P[..., 2]], -1)

def convert(f, dec=3, maxf=None):
    d = np.load(f); P = to_world(d["kp3d"].astype(np.float32) if "kp3d" in d else d["pred_keypoints_3d"].astype(np.float32))   # (T,70,3)
    t = d["t"].astype(float)
    if maxf and len(P) > maxf: P, t = P[:maxf], t[:maxf]
    if len(P) >= 3: P[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]          # penghalusan ringan
    pel = (P[:, 9] + P[:, 10]) / 2
    P[..., 0] -= pel[:, None, 0]; P[..., 2] -= pel[:, None, 2]
    P[..., 1] += (0.06 - P[:, [13, 14, 15, 18], 1].min(1))[:, None]                   # kaki di lantai
    r = lambda a: np.round(a, dec).tolist()
    joints = {k: r(P[:, i]) for k, i in J.items()}
    pel = (P[:, 9] + P[:, 10]) / 2; nk = P[:, 69]
    joints["pelvis"] = r(pel); joints["spine"] = r(pel + (nk - pel) * 0.35); joints["chest"] = r(pel + (nk - pel) * 0.75)
    joints["head"] = r((P[:, 3] + P[:, 4]) / 2)
    fingers = np.round(P[:, np.array(FINGERS)], dec).tolist()                            # (T,10,5,3)
    hz = round(1 / np.median(np.diff(t)), 2) if len(t) > 1 else 10
    stem = Path(f).stem; cls = Path(f).parent.name
    key = cls if cls in GERAK or "_" in cls or cls[:1].isupper() else next((k for k in GERAK if stem.startswith(k)), stem)
    ds = next((x for x in ("putri", "putra") if x in Path(f).parts), "")
    lab = {"Ulap_Ulap": "Ulap-Ulap", "Gandang_Gandang": "Gandang-Gandang"}.get(key, GERAK.get(key, key.replace("_", " ")))
    return dict(name=(ds + "_" if ds else "") + stem, gerak=lab, ds=ds, hz=hz, frames=len(P), joints=joints, fingers=fingers)

args = [a for a in sys.argv[1:] if not a.startswith("--")]
files = [f for a in args for f in sorted(glob.glob(str(Path(a) / "**" / "*.npz"), recursive=True))]
if "--per-gerak" in sys.argv:
    # satu klip per (dataset, gerak): split train, panjang terdekat ke 40 frame (±8 detik pada 5 fps), deteksi penuh
    best = {}
    for f in files:
        p = Path(f); n = len(np.load(f)["t"]); k = (p.parts[-4], p.parts[-2])
        sc = (p.parts[-3] == "train", -abs(n - 40))
        if k not in best or sc > best[k][0]: best[k] = (sc, f)
    files = [best[k][1] for k in sorted(best, key=lambda k: (k[0] != "putri", k[1]))]
clips = [convert(f, dec=2, maxf=60) if "--per-gerak" in sys.argv else convert(f) for f in files]
out = ROOT / "assets/ml/sam3d_clips.json"
json.dump(dict(source="SAM 3D Body (Meta, SAM License) dari Video Dataset of Woman Basic Balinese Dance Movement (Hendrawan dkk., Mendeley Data, CC BY 4.0)",
               clips=clips), open(out, "w"), separators=(",", ":"))
print(len(clips), "klip ->", out, f"{out.stat().st_size/1e6:.2f} MB", [(c["gerak"], c["frames"], c["hz"]) for c in clips])
