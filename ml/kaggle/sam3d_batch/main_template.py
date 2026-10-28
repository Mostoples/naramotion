"""NaraMotion · SAM 3D Body (Meta, SAM License) untuk SEMUA klip tari Bali (putri 1.740 + putra 828, Mendeley Data CC BY 4.0).
Pose 3D seluruh tubuh + jari per frame, 5 fps, fp16, dua GPU T4 paralel (kode worker tersimpan base64 di bawah).
Jalankan dari EDITOR Kaggle (Secret HF_TOKEN), Accelerator "GPU T4 x2", Internet ON. SHARD = 0, 1, 2 → Save & Run All tiap bagian.
Keluaran: /kaggle/working/sam3d/<dataset>/<split>/<gerak>/<klip>.npz + log*.txt
"""
SHARD, N_SHARDS = 1, 3   # shard 0 sudah dijalankan dari editor
import os, sys, glob, time, json, zipfile, subprocess, base64
OUT = "/kaggle/working"; R = "/tmp/s3db"; TMP = "/tmp/nara"; os.makedirs(TMP, exist_ok=True)
ZIPS = {"putri": "https://data.mendeley.com/public-files/datasets/s2gv9d6gpb/files/b2b8b852-8f88-498d-ba06-47cab9240a80/file_downloaded",
        "putra": "https://data.mendeley.com/public-files/datasets/tr9py7hzj4/files/79b815e5-cf48-48c0-9ce2-fc9bf4fa482a/file_downloaded"}
WORKER_B64 = "__B64__"
LOG = open(f"{OUT}/log.txt", "a")
def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(map(str, a)); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def sh(cmd):
    t = time.time(); r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    log(f"$ {cmd[:140]} [exit {r.returncode}, {time.time()-t:.0f}s]")
    if r.returncode: log((r.stdout + r.stderr)[-2000:])
# token: dari dataset privat (file hf_token.txt, agar bisa dijalankan lewat API) atau Kaggle Secret HF_TOKEN (run dari editor)
tf = glob.glob("/kaggle/input/**/hf_token.txt", recursive=True)
if tf: tok = open(tf[0]).read().strip()
else:
    from kaggle_secrets import UserSecretsClient
    tok = UserSecretsClient().get_secret("HF_TOKEN")
log(subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", shell=True, capture_output=True, text=True).stdout)
sh(f"git clone -q --depth 1 https://github.com/facebookresearch/sam-3d-body {R}")
sh("pip install -q pytorch-lightning pyrender yacs einops timm dill hydra-core pyrootutils roma joblib huggingface_hub ultralytics braceexpand webdataset")
from huggingface_hub import snapshot_download
snapshot_download("facebook/sam-3d-body-dinov3", local_dir=f"{R}/checkpoints/sam-3d-body-dinov3", token=tok)
jobs = []
for ds, url in ZIPS.items():
    z = f"{TMP}/{ds}.zip"; sh(f"curl -sS -L -o {z} '{url}'")
    names = sorted(n for n in zipfile.ZipFile(z).namelist() if n.endswith(".mp4") and not n.startswith("__MACOSX") and "/._" not in n)
    by = {}
    for n in names: by.setdefault(n.split("/")[-2], []).append(n)
    jobs += [(ds, by[c][i]) for i in range(max(map(len, by.values()))) for c in sorted(by) if i < len(by[c])]   # selang-seling antar gerak
    log(ds, len(names), "klip,", len(by), "gerak")
jobs = jobs[SHARD::N_SHARDS]; json.dump(jobs, open(f"{TMP}/jobs.json", "w")); log("shard", SHARD, "→", len(jobs), "klip")
open(f"{TMP}/worker.py", "wb").write(base64.b64decode(WORKER_B64))
NG = max(1, subprocess.run("nvidia-smi -L", shell=True, capture_output=True, text=True).stdout.count("GPU "))   # 1 atau 2 GPU
log("GPU:", NG)
procs = [subprocess.Popen([sys.executable, f"{TMP}/worker.py", str(k), str(NG)], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(k)}) for k in range(NG)]
for p in procs: p.wait()
log("SELESAI", len(glob.glob(f"{OUT}/sam3d/**/*.npz", recursive=True)), "npz")
