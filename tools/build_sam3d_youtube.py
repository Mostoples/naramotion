"""Kernel Kaggle SAM 3D Body untuk klip YouTube (ml/data/youtube_clips) → dataset privat naramotion-youtube-clips + 2 sesi paralel.
Pemakaian: python tools/build_sam3d_youtube.py   lalu: kaggle datasets create/version -p ml/kaggle/yt_dataset ; kaggle kernels push -p ml/kaggle/sam3d_y1 (dan y2)
"""
import base64, json, re, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; K = ROOT / "ml/kaggle"; CL = ROOT / "ml/data/youtube_clips"; N = 2
# 1) dataset: satu zip berisi yt/<tari>/<klip>.mp4 (+ sumber & lisensi)
D = K / "yt_dataset"; D.mkdir(exist_ok=True)
with zipfile.ZipFile(D / "youtube.zip", "w", zipfile.ZIP_STORED) as z:
    for f in sorted(CL.glob("*.mp4")):
        dance = f.stem.split("__")[0]; z.write(f, f"yt/{dance}/{f.name}")
(D / "sources.json").write_text((CL / "sources.json").read_text(encoding="utf-8"), encoding="utf-8")
json.dump({"title": "NaraMotion YouTube dance clips", "id": "mostoplesrinelan/naramotion-youtube-clips", "licenses": [{"name": "other"}]},
          open(D / "dataset-metadata.json", "w"), indent=1)
# 2) kernel: template utama, tetapi klip dari dataset (bukan zip Mendeley)
src = (K / "sam3d_batch/main_template.py").read_text(encoding="utf-8")
src = src.replace('SHARD, N_SHARDS = 1, 3   # shard 0 sudah dijalankan dari editor', 'SHARD, N_SHARDS = __SHARD__, __N__   # klip YouTube')
src = src.replace('WORKER_B64 = "__B64__"', 'WORKER_B64 = "' + base64.b64encode((K / "sam3d_batch/worker.py").read_bytes()).decode() + '"')
i, j = src.index("jobs = []"), src.index("jobs = jobs[SHARD::N_SHARDS];")
src = src[:i] + '''yz = glob.glob("/kaggle/input/**/youtube.zip", recursive=True)
if yz: import shutil; shutil.copy(yz[0], f"{TMP}/youtube.zip")
else:   # Kaggle mengekstrak zip dataset otomatis → kemas ulang yt/<tari>/<klip>.mp4
    with zipfile.ZipFile(f"{TMP}/youtube.zip", "w", zipfile.ZIP_STORED) as zz:
        for f in glob.glob("/kaggle/input/**/yt/*/*.mp4", recursive=True): zz.write(f, "yt/" + "/".join(f.split("/")[-2:]))
names = sorted(n for n in zipfile.ZipFile(f"{TMP}/youtube.zip").namelist() if n.endswith(".mp4"))
jobs = [("youtube", n) for n in names]; log("youtube", len(jobs), "klip")
''' + src[j:]
src = src.replace('from huggingface_hub import snapshot_download',
                  'import torch; torch.hub.list("facebookresearch/dinov3", trust_repo=True); log("hub dinov3 siap")\nfrom huggingface_hub import snapshot_download')
PKEY = (K / ".progress_key").read_text().strip() if (K / ".progress_key").exists() else ""
src = src.replace('procs = [subprocess.Popen([sys.executable, f"{TMP}/worker.py", str(k), str(NG)], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(k)}) for k in range(NG)]',
                  'procs = []\nfor k in range(NG):\n    procs.append(subprocess.Popen([sys.executable, f"{TMP}/worker.py", str(k), str(NG)], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(k), "NARA_PKEY": "__PKEY__", "NARA_PNAME": "__PNAME__"}))\n    if k < NG - 1: time.sleep(90)')
assert "youtube.zip" in src and "time.sleep(90)" in src and "__PKEY__" in src
for s in range(N):
    d = K / f"sam3d_y{s + 1}"; d.mkdir(exist_ok=True)
    (d / "sam3d_youtube.py").write_text(src.replace("__SHARD__", str(s)).replace("__N__", str(N)).replace("__PKEY__", PKEY).replace("__PNAME__", f"y{s + 1}"), encoding="utf-8")
    json.dump({"id": f"mostoplesrinelan/naramotion-sam3d-y{s + 1}", "title": f"NaraMotion SAM3D Y{s + 1}", "code_file": "sam3d_youtube.py", "language": "python",
               "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
               "dataset_sources": ["mostoplesrinelan/naramotion-hf-token", "mostoplesrinelan/naramotion-youtube-clips"], "competition_sources": [], "kernel_sources": []},
              open(d / "kernel-metadata.json", "w"), indent=2)
print("zip", (D / "youtube.zip").stat().st_size // 1e6, "MB;", len(list(CL.glob("*.mp4"))), "klip; kernel y1, y2 siap")
