"""Worker SAM 3D Body (satu GPU): memproses bagian daftar klip dari /tmp/nara/jobs.json."""
import os, sys, time, json, zipfile, shutil
OUT = "/kaggle/working"; R = "/tmp/s3db"; TMP = "/tmp/nara"; FPS_OUT = 5; WORKER = int(sys.argv[1])
LOG = open(f"{OUT}/log{WORKER}.txt", "a")
def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(map(str, a)); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
T_END = os.path.getmtime(f"{TMP}/jobs.json") + 11.0 * 3600
sys.path.insert(0, R); os.chdir(R)
import numpy as np, torch, cv2
from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
ck = f"{R}/checkpoints/sam-3d-body-dinov3"
model, cfg = load_sam_3d_body(f"{ck}/model.ckpt", device="cuda", mhr_path=f"{ck}/assets/mhr_model.pt")
est = SAM3DBodyEstimator(sam_3d_body_model=model, model_cfg=cfg, human_detector=None, human_segmentor=None, fov_estimator=None)
from ultralytics import YOLO
yolo = YOLO("yolov8m.pt")
NW = int(sys.argv[2]) if len(sys.argv) > 2 else 2
jobs = json.load(open(f"{TMP}/jobs.json"))[WORKER::NW]
zs = {ds: zipfile.ZipFile(f"{TMP}/{ds}.zip") for ds in ("putri", "putra")}
half = True
def infer(fr, b):
    global half
    if half:
        try:
            with torch.autocast("cuda", dtype=torch.float16):
                return est.process_one_image(fr, bboxes=b[None])
        except Exception as e:
            half = False; log("fp16 gagal, pakai fp32:", str(e)[:200])
    return est.process_one_image(fr, bboxes=b[None])
t_all, n_fr = time.time(), 0
for j, (ds, name) in enumerate(jobs):
    if time.time() > T_END:
        log("batas waktu, berhenti di", j, "/", len(jobs)); break
    split, cls, fn = name.split("/")[-3:]; dst = f"{OUT}/sam3d/{ds}/{split}/{cls}/{fn[:-4]}.npz"
    if os.path.exists(dst): continue
    p = f"{TMP}/w{WORKER}.mp4"
    with zs[ds].open(name) as s, open(p, "wb") as d: shutil.copyfileobj(s, d)
    cap = cv2.VideoCapture(p); fps = cap.get(cv2.CAP_PROP_FPS) or 30; step = max(1, round(fps / FPS_OUT))
    size = np.array([cap.get(cv2.CAP_PROP_FRAME_HEIGHT), cap.get(cv2.CAP_PROP_FRAME_WIDTH)]); rec = {}; i = 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        if i % step == 0:
            det = yolo(fr, classes=[0], verbose=False)[0].boxes
            if len(det):
                b = det.xyxy.cpu().numpy(); b = b[np.argmax((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]))]
                outs = infer(fr, b)
                if outs:
                    o = outs[0]
                    for k, v in [("kp3d", o["pred_keypoints_3d"]), ("rots", o["pred_global_rots"]), ("cam_t", o["pred_cam_t"]), ("body", o["body_pose_params"]),
                                 ("hand", o["hand_pose_params"]), ("bbox", b), ("focal", o["focal_length"]), ("t", i / fps)]:
                        rec.setdefault(k, []).append(np.asarray(v, np.float16 if k in ("kp3d", "rots", "body", "hand") else np.float32))
        i += 1
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if rec: np.savez_compressed(dst, size=size, **{k: np.stack(v) for k, v in rec.items()})
    n_fr += len(rec.get("t", []))
    if j % 20 == 0: log(f"[{j+1}/{len(jobs)}] {ds}/{cls}/{fn} · {n_fr} frame · {(time.time()-t_all)/max(n_fr,1):.2f} s/frame · fp16={half}")
log("worker selesai", n_fr, "frame")
