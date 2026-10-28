"""NaraMotion · Kaggle kernel 1: ekstraksi pose whole-body (RTMW, 133 titik) dari dataset video
"Woman Basic Balinese Dance Movement" (Mendeley Data, CC BY 4.0, doi:10.17632/s2gv9d6gpb).

Keluaran di /kaggle/working:
  poses_<split>.npz   satu entri per klip: kpts (T,133,2) float16 piksel, score (T,133) float16
  index.json          daftar klip: split, kelas, nama, frame, fps, lebar, tinggi
  preview/*.jpg       satu frame beranotasi per kelas (QA)
  log.txt             kecepatan dan ringkasan
LIMIT > 0 hanya memproses LIMIT klip pertama (uji cepat).
"""
import os, sys, subprocess, time, json, zipfile, shutil
LIMIT = 0
URL = "https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/0a3cd3b8-ca82-465d-891d-e7e39952a3fe"
OUT = "/kaggle/working"; TMP = "/tmp/nara"; os.makedirs(TMP, exist_ok=True); os.makedirs(f"{OUT}/preview", exist_ok=True)
LOG = open(f"{OUT}/log.txt", "a")
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True); return (r.stdout + r.stderr).strip()

log(sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader"))
log(sh("df -h /tmp /kaggle/working | tail -2"))
log(sh("pip install -q rtmlib 2>&1 | tail -2"))
# rtmlib menarik onnxruntime (CPU) yang menimpa versi GPU → buang lalu pasang ulang versi GPU
log(sh("pip uninstall -y -q onnxruntime onnxruntime-gpu 2>&1 | tail -1; pip install -q onnxruntime-gpu==1.22.0 2>&1 | tail -2 || pip install -q onnxruntime-gpu==1.21.1 2>&1 | tail -2"))  # 1.2x ≤ CUDA 12; versi terbaru butuh CUDA 13
import torch  # memuat libcudnn/libcublas milik torch agar CUDA EP onnxruntime menemukannya

import numpy as np, cv2, onnxruntime as ort
# muat pustaka CUDA/cuDNN secara global agar CUDA EP tidak diam-diam jatuh ke CPU
import ctypes, glob as _g
libs = []
for pat in ("libcudart.so.12*", "libcublasLt.so.12*", "libcublas.so.12*", "libcufft.so.11*", "libcurand.so.10*", "libcudnn.so.9*"):
    hits = sorted(_g.glob(f"/usr/**/{pat}", recursive=True) + _g.glob(f"/opt/**/{pat}", recursive=True))
    if hits:
        try: ctypes.CDLL(hits[0], mode=ctypes.RTLD_GLOBAL); libs.append(hits[0])
        except OSError as e: log("gagal muat", hits[0], e)
    else: log("tidak ditemukan", pat)
log("pustaka dimuat:", libs)
try: ort.preload_dlls()
except Exception as e: log("preload_dlls:", e)
ort.set_default_logger_severity(1)
log("ort", ort.__version__, ort.get_available_providers())
assert "CUDAExecutionProvider" in ort.get_available_providers(), "CUDA EP tidak tersedia"

ZIP = f"{TMP}/data.zip"
if not os.path.exists(ZIP):
    t = time.time(); log(sh(f"curl -sS -L -o {ZIP} '{URL}' && ls -la {ZIP}")); log(f"unduh {time.time()-t:.0f} s")
zf = zipfile.ZipFile(ZIP)
clips = sorted(n for n in zf.namelist() if n.endswith(".mp4") and not n.startswith("__MACOSX") and "/._" not in n)
log("klip", len(clips))
if LIMIT: clips = clips[::max(1, len(clips) // LIMIT)][:LIMIT]

from rtmlib import Wholebody, PoseTracker, draw_skeleton
tracker = PoseTracker(Wholebody, det_frequency=6, mode="balanced", backend="onnxruntime", device="cuda", to_openpose=False)
for nm in ("det_model", "pose_model"):
    sub = getattr(tracker, nm, None); ses = getattr(sub, "session", None)
    log(nm, type(sub).__name__, ses.get_providers() if ses else "?", getattr(sub, "model_input_size", ""))

index, store, previewed = [], {}, set()
t0, frames_total = time.time(), 0
for i, name in enumerate(clips):
    split, cls, fn = name.split("/")[-3:]
    path = f"{TMP}/clip.mp4"
    with zf.open(name) as src, open(path, "wb") as dst: shutil.copyfileobj(src, dst)
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    tracker.reset() if hasattr(tracker, "reset") else None
    K, S, mid = [], [], None
    while True:
        ok, fr = cap.read()
        if not ok: break
        kp, sc = tracker(fr)
        if kp is None or len(kp) == 0:
            K.append(np.full((133, 2), np.nan, np.float32)); S.append(np.zeros(133, np.float32)); continue
        # penari = orang dengan kotak terbesar (tubuh 17 titik pertama)
        area = [np.ptp(k[:17, 0]) * np.ptp(k[:17, 1]) for k in kp]; j = int(np.argmax(area))
        K.append(kp[j].astype(np.float32)); S.append(sc[j].astype(np.float32))
        if cls not in previewed and len(K) == 60:
            img = draw_skeleton(fr.copy(), kp[j:j+1], sc[j:j+1], kpt_thr=0.4)
            cv2.imwrite(f"{OUT}/preview/{cls}.jpg", cv2.resize(img, (img.shape[1] * 480 // img.shape[0], 480))); previewed.add(cls)
    cap.release()
    key = f"{split}/{cls}/{fn[:-4]}"
    store.setdefault(split, {})[key.replace("/", "__") + "__kpts"] = np.asarray(K, np.float16)
    store[split][key.replace("/", "__") + "__score"] = np.asarray(S, np.float16)
    index.append(dict(split=split, cls=cls, clip=fn[:-4], frames=len(K), fps=fps, w=W, h=H,
                      valid=float(np.mean([s[:17].mean() > 0.3 for s in S])) if S else 0.0))
    frames_total += len(K)
    if i % 25 == 0 or i == len(clips) - 1:
        el = time.time() - t0
        log(f"[{i+1}/{len(clips)}] {key} T={len(K)} {W}x{H} · {frames_total/el:.1f} fps · {el/60:.1f} mnt")
        if i == 25 and frames_total / el < 8: raise SystemExit(f"terlalu lambat {frames_total/el:.1f} fps")

for split, d in store.items(): np.savez_compressed(f"{OUT}/poses_{split}.npz", **d)
json.dump(index, open(f"{OUT}/index.json", "w"), indent=0)
log("SELESAI", len(index), "klip", frames_total, "frame", f"{(time.time()-t0)/60:.1f} mnt")
os.remove(ZIP)
