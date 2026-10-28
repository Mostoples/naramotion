"""NaraMotion · pilot SAM 3D Body (Meta, SAM License) di Kaggle T4: video tari Bali → pose 3D seluruh tubuh per frame.
Token HF dari Kaggle Secret HF_TOKEN (akses facebook/sam-3d-body-dinov3 sudah disetujui). Kotak penari dari YOLO (ultralytics),
bukan detectron2, agar tidak perlu kompilasi. Klip dari dataset privat naramotion-m2mr-assets (CC BY 4.0).
Keluaran /kaggle/working: <klip>.npz (kp3d, joints, global_rots, cam_t, focal, bbox, t), vis/<klip>_*.jpg, log.txt
"""
import os, sys, glob, time, subprocess, json
OUT = "/kaggle/working"; os.makedirs(f"{OUT}/vis", exist_ok=True); LOG = open(f"{OUT}/log.txt", "a")
def log(*a): s = " ".join(map(str, a)); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def sh(cmd, cwd=None):
    t = time.time(); r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    log(f"$ {cmd[:160]}  [exit {r.returncode}, {time.time()-t:.0f}s]"); 
    if r.returncode: log((r.stdout + r.stderr)[-2500:])
    return r.returncode
R = "/tmp/s3db"
log(subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; python --version", shell=True, capture_output=True, text=True).stdout)
sh(f"git clone -q --depth 1 https://github.com/facebookresearch/sam-3d-body {R}")
sh("pip install -q pytorch-lightning pyrender yacs einops timm dill hydra-core pyrootutils roma joblib huggingface_hub ultralytics decord psutil braceexpand webdataset")
from kaggle_secrets import UserSecretsClient
tok = UserSecretsClient().get_secret("HF_TOKEN")
from huggingface_hub import snapshot_download
ck = snapshot_download("facebook/sam-3d-body-dinov3", local_dir=f"{R}/checkpoints/sam-3d-body-dinov3", token=tok)
log("checkpoint", os.listdir(ck))
sys.path.insert(0, R); os.chdir(R)
import numpy as np, torch, cv2
from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator
model, cfg = load_sam_3d_body(f"{ck}/model.ckpt", device="cuda", mhr_path=f"{ck}/assets/mhr_model.pt")
est = SAM3DBodyEstimator(sam_3d_body_model=model, model_cfg=cfg, human_detector=None, human_segmentor=None, fov_estimator=None)
try:
    from tools.vis_utils import visualize_sample_together
except Exception as e:
    visualize_sample_together = None; log("vis tidak tersedia:", e)
from ultralytics import YOLO
yolo = YOLO("yolov8m.pt")
SRC = os.path.dirname(glob.glob("/kaggle/input/**/Agem_Kanan_101.mp4", recursive=True)[0])
KEYS = ["pred_keypoints_3d", "pred_joint_coords", "pred_global_rots", "pred_cam_t", "global_rot", "body_pose_params", "hand_pose_params"]
for vid in sorted(glob.glob(f"{SRC}/*.mp4")):
    name = os.path.basename(vid)[:-4]; cap = cv2.VideoCapture(vid); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(fps / 10)); rec = {k: [] for k in KEYS}; rec.update(focal=[], bbox=[], t=[]); i = 0; t0 = time.time(); torch.cuda.reset_peak_memory_stats()
    while True:
        ok, fr = cap.read()
        if not ok: break
        if i % step == 0:
            det = yolo(fr, classes=[0], verbose=False)[0].boxes
            if len(det):
                b = det.xyxy.cpu().numpy(); b = b[np.argmax((b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1]))]
                outs = est.process_one_image(fr, bboxes=b[None])
                if outs:
                    o = outs[0]
                    for k in KEYS: rec[k].append(np.asarray(o[k], np.float32))
                    rec["focal"].append(float(o["focal_length"])); rec["bbox"].append(b); rec["t"].append(i / fps)
                    if visualize_sample_together and len(rec["t"]) in (1, 15, 30, 45):
                        cv2.imwrite(f"{OUT}/vis/{name}_{len(rec['t']):02d}.jpg", visualize_sample_together(fr, outs, est.faces).astype(np.uint8))
        i += 1
    n = len(rec["t"]); dt = time.time() - t0
    np.savez_compressed(f"{OUT}/{name}.npz", **{k: np.stack(v) for k, v in rec.items() if len(v)})
    log(f"{name}: {n} frame dianalisis dari {i}, {dt/max(n,1):.2f} s/frame, VRAM puncak {torch.cuda.max_memory_allocated()/2**30:.1f} GB, kp3d {np.stack(rec['pred_keypoints_3d']).shape if n else None}")
log("SELESAI")
