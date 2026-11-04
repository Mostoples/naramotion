"""Kalibrasi skor 3D untuk data kamera: MediaPipe Pose (model sama dengan browser) pada video penari asli → galat 3D
terhadap acuan SAM 3D Body. Skor 85 diberikan pada galat median gerak BENAR, sehingga beda antar-estimator ikut dikoreksi.
Pemakaian: python tools/calib_3d_mediapipe.py <folder video ds__gerak.mp4>  → memperbarui calib di assets/ml/templates3d_*.json
"""
import sys, json, glob, numpy as np, cv2
from pathlib import Path
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions
ROOT = Path(__file__).resolve().parents[1]
src = open(ROOT / "tools/build_3d_templates.py", encoding="utf-8").read()
ns = {"__file__": str(ROOT / "tools/build_3d_templates.py")}; exec(src.split("for ds in (")[0], ns)   # pakai fungsi yang sama dengan pembuat acuan
ang, dtw_err, T = ns["ang"], ns["dtw_err"], ns["T"]
W3 = dict(nose=0, earL=7, earR=8, shL=11, shR=12, elL=13, elR=14, wrL=15, wrR=16, hipL=23, hipR=24, knL=25, knR=26, anL=27, anR=28)
def feats(wl):
    g = lambda k: np.array([wl[W3[k]].x, -wl[W3[k]].y, -wl[W3[k]].z])
    u = lambda v: v / (np.linalg.norm(v) + 1e-9)
    pel = (g("hipL") + g("hipR")) / 2; neck = (g("shL") + g("shR")) / 2
    X = u(g("hipL") - g("hipR")); Y = neck - pel; Y = u(Y - Y.dot(X) * X); Z = np.cross(X, Y); R = np.stack([X, Y, Z])
    seg = lambda a, b: u(R @ (b - a)); hc = (g("earL") + g("earR")) / 2
    return np.stack([seg(neck, hc + (g("nose") - hc) * 0.5), u(neck - pel), seg(g("shL"), g("elL")), seg(g("elL"), g("wrL")), seg(g("shR"), g("elR")), seg(g("elR"), g("wrR")),
                     seg(g("hipL"), g("knL")), seg(g("knL"), g("anL")), seg(g("hipR"), g("knR")), seg(g("knR"), g("anR"))])
opt = vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_buffer=open(ROOT / "ml/models/pose_landmarker_lite.task", "rb").read()), running_mode=vision.RunningMode.VIDEO, num_poses=1)
res = {"putri": {"own": [], "other": []}, "putra": {"own": [], "other": []}}
tpls = {ds: json.load(open(ROOT / f"assets/ml/templates3d_{ds}.json")) for ds in res}
for f in sorted(glob.glob(str(Path(sys.argv[1]) / "*.mp4"))):
    ds, cls = Path(f).stem.split("__")
    lmk = vision.PoseLandmarker.create_from_options(opt); cap = cv2.VideoCapture(f); fps = cap.get(5) or 30; F = []; i = 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        if i % 2 == 0:
            r = lmk.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)), int(i / fps * 1000))
            if r.pose_world_landmarks: F.append(feats(r.pose_world_landmarks[0]))
        i += 1
    lmk.close()
    if len(F) < 10: print("lewati", f); continue
    F = np.array(F); idx = np.linspace(0, len(F) - 1, T); i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, len(F) - 1); w = (idx - i0)[:, None, None]
    S = F[i0] * (1 - w) + F[i1] * w; S /= np.linalg.norm(S, axis=2, keepdims=True)
    t = tpls[ds]; errs = {c: min(dtw_err(S, np.array(e)).mean() for e in t["templates"][c]["exemplars"]) for c in t["classes"]}
    res[ds]["own"].append(errs[cls]); res[ds]["other"].append(np.median([v for c, v in errs.items() if c != cls]))
    print(ds, cls, f"benar {errs[cls]:.1f}°  lain {res[ds]['other'][-1]:.1f}°  terdekat {min(errs, key=errs.get)}")
for ds, r in res.items():
    own, oth = float(np.median(r["own"])), float(np.median(r["other"]))
    k = round(15 / max(own, 5), 3); t = tpls[ds]
    t["calib"] = {"k": k, "median_err": round(own, 2), "source": "MediaPipe Pose lite pada video penari asli vs acuan SAM 3D Body", "other_median": round(oth, 2)}
    json.dump(t, open(ROOT / f"assets/ml/templates3d_{ds}.json", "w"), separators=(",", ":"))
    print(ds, f"galat median gerak benar {own:.1f}° → k={k}; skor gerak benar ≈85, gerak lain ≈{max(0, 100 - oth * k):.0f}")
