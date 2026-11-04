"""Acuan gerak 3D untuk skor Kelas Tari yang tidak bergantung sudut kamera.
Dari hasil SAM 3D Body (ml/runs/sam3d_*): tiap klip → 10 segmen tubuh sebagai vektor satuan dalam KERANGKA BADAN
(X = pinggul kiri−kanan, Y = pinggul→leher, Z = X×Y), di-resample 64 frame. Kemiringan badan terhadap vertikal
dipakai untuk segmen "torso". Per gerak: 6 exemplar (medoid dari klip train), lalu kalibrasi skor dari klip test:
galat median klip test → skor 85.
Keluaran: assets/ml/templates3d_{putri,putra}.json
Pemakaian: python tools/build_3d_templates.py
"""
import glob, json, random
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]; T = 64; NEX = 6; random.seed(7)
# indeks MHR70 (sama dengan tools/sam3d_to_web.py); L = kiri penari
I = dict(nose=0, earL=3, earR=4, shL=5, shR=6, elL=7, elR=8, hipL=9, hipR=10, knL=11, knR=12, anL=13, anR=14, wrL=62, wrR=41, neck=69)
SEGS = ["head", "torso", "uArmL", "fArmL", "uArmR", "fArmR", "thighL", "shinL", "thighR", "shinR"]

def frame_feats(P):
    """P: (T,70,3) dunia y-atas → (T,10,3) vektor satuan (torso = vektor naik dalam dunia, lainnya dalam kerangka badan)"""
    g = lambda k: P[:, I[k]]
    pel = (g("hipL") + g("hipR")) / 2; neck = g("neck")
    X = g("hipL") - g("hipR"); X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
    Y = neck - pel; Y -= (Y * X).sum(1, keepdims=True) * X; Y /= np.linalg.norm(Y, axis=1, keepdims=True) + 1e-9
    Z = np.cross(X, Y); R = np.stack([X, Y, Z], 1)                     # (T,3,3) baris = sumbu badan
    def seg(a, b):
        v = b - a; v = np.einsum("tij,tj->ti", R, v); return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
    head_c = (g("earL") + g("earR")) / 2
    up = neck - pel; up /= np.linalg.norm(up, axis=1, keepdims=True) + 1e-9   # kemiringan badan (dunia)
    F = [seg(neck, head_c + (g("nose") - head_c) * 0.5), up,
         seg(g("shL"), g("elL")), seg(g("elL"), g("wrL")), seg(g("shR"), g("elR")), seg(g("elR"), g("wrR")),
         seg(g("hipL"), g("knL")), seg(g("knL"), g("anL")), seg(g("hipR"), g("knR")), seg(g("knR"), g("anR"))]
    return np.stack(F, 1)

def load(f):
    d = np.load(f); P = d["kp3d"].astype(np.float32)
    P = np.stack([P[..., 0], -P[..., 1], -P[..., 2]], -1)                 # kamera → dunia, y atas
    if len(P) < 4: return None
    Fe = frame_feats(P)
    idx = np.linspace(0, len(Fe) - 1, T); i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, len(Fe) - 1); w = (idx - i0)[:, None, None]
    R = Fe[i0] * (1 - w) + Fe[i1] * w
    return R / (np.linalg.norm(R, axis=2, keepdims=True) + 1e-9)

def ang(a, b): return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))   # (…,10)
def dtw_err(S, Rf, band=20):
    C = ang(S[:, None], Rf[None]).mean(-1); n, m = C.shape; D = np.full((n + 1, m + 1), np.inf); D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(max(1, i - band), min(m, i + band) + 1): D[i, j] = C[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    i, j, path = n, m, []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1)); a, b, c = D[i - 1, j - 1], D[i - 1, j], D[i, j - 1]
        if a <= b and a <= c: i, j = i - 1, j - 1
        elif b <= c: i -= 1
        else: j -= 1
    e = np.array([ang(S[a], Rf[b]) for a, b in path]).mean(0); return e

for ds in ("putri", "putra"):
    tpl2d = json.load(open(ROOT / f"assets/ml/templates_{ds}_body17.json"))
    out = dict(classes=tpl2d["classes"], segments=SEGS, T=T, templates={}, calib={})
    meds = []
    for c in tpl2d["classes"]:
        files = sorted(glob.glob(str(ROOT / f"ml/runs/sam3d_*/sam3d/{ds}/*/{c}/*.npz")))
        tr = [f for f in files if "/train/" in f.replace("\\", "/")]; te = [f for f in files if "/test/" in f.replace("\\", "/")]
        X = [x for x in (load(f) for f in random.sample(tr, min(40, len(tr)))) if x is not None]
        # medoid sederhana: klip dengan jarak rata-rata terkecil ke klip lain (tanpa DTW, cepat)
        Dm = np.array([[ang(a, b).mean() for b in X] for a in X]); order = np.argsort(Dm.mean(1))
        ex = []
        for k in order:                                                   # medoid yang saling berbeda (variasi kamera/penari)
            if all(Dm[k, j] > 6 for j in ex): ex.append(k)
            if len(ex) == NEX: break
        ex = (ex + list(order))[:NEX] if len(ex) < NEX else ex
        E = [X[k] for k in ex]
        errs = [min((dtw_err(x, e).mean() for e in E)) for x in (load(f) for f in random.sample(te, min(12, len(te)))) if x is not None]
        med = float(np.median(errs)) if errs else 12.0; meds.append(med)
        out["templates"][c] = {"exemplars": [np.round(e, 3).tolist() for e in E], "median_err": round(med, 2)}
        print(ds, c, len(files), "klip", f"galat median test {med:.1f}°")
    out["calib"] = {"k": round(15 / max(float(np.median(meds)), 5), 3), "median_err": round(float(np.median(meds)), 2)}
    p = ROOT / f"assets/ml/templates3d_{ds}.json"; json.dump(out, open(p, "w"), separators=(",", ":"))
    print(p, f"{p.stat().st_size / 1e6:.2f} MB", out["calib"])
