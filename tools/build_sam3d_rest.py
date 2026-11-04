"""Buat kernel Kaggle untuk SISA klip SAM 3D Body (yang belum ada di ml/runs/sam3d_s*), dibagi N sesi paralel.
Perbaikan dari putaran pertama: repo DINOv3 (torch.hub) diunduh sekali sebelum worker jalan, worker GPU kedua
mulai 90 s kemudian (shard 1 gagal karena dua worker mengunduh hub bersamaan).
Pemakaian: python tools/build_sam3d_rest.py [N_SESI=2]   → ml/kaggle/sam3d_r1..rN/ lalu `kaggle kernels push -p ...`
"""
import base64, glob, gzip, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; K = ROOT / "ml/kaggle"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2
# .../sam3d/<dataset>/<split>/<gerak>/<klip>.npz → kunci "dataset/gerak/klip"
done = sorted({f"{Path(f).parts[-4]}/{Path(f).parts[-2]}/{Path(f).stem}" for f in glob.glob(str(ROOT / "ml/runs/sam3d_s*/sam3d/**/*.npz"), recursive=True)})
print(len(done), "klip selesai")
DONE_B64 = base64.b64encode(gzip.compress(json.dumps(done).encode())).decode()
WORKER_B64 = base64.b64encode((K / "sam3d_batch/worker.py").read_bytes()).decode()
src = (K / "sam3d_batch/main_template.py").read_text(encoding="utf-8")
src = src.replace('SHARD, N_SHARDS = 1, 3   # shard 0 sudah dijalankan dari editor', 'SHARD, N_SHARDS = __SHARD__, __N__   # putaran 2: hanya klip yang belum selesai')
src = src.replace('WORKER_B64 = "__B64__"', f'WORKER_B64 = "{WORKER_B64}"\nDONE = set(json.loads(__import__("gzip").decompress(base64.b64decode("{DONE_B64}"))))')
src = src.replace('jobs = jobs[SHARD::N_SHARDS];', 'jobs = [j for j in jobs if f"{j[0]}/{j[1].split(\'/\')[-2]}/{j[1].split(\'/\')[-1][:-4]}" not in DONE]; log("sisa", len(jobs), "klip")\njobs = jobs[SHARD::N_SHARDS];')
src = src.replace('from huggingface_hub import snapshot_download',
                  '# unduh repo DINOv3 untuk torch.hub SEKALI di sini (dua worker serentak merusak cache → ImportError di putaran 1)\n'
                  'import torch; torch.hub.list("facebookresearch/dinov3", trust_repo=True); log("hub dinov3 siap")\n'
                  'from huggingface_hub import snapshot_download')
PKEY = (K / ".progress_key").read_text().strip() if (K / ".progress_key").exists() else ""
src = src.replace('env={**os.environ, "CUDA_VISIBLE_DEVICES": str(k)}', 'env={**os.environ, "CUDA_VISIBLE_DEVICES": str(k), "NARA_PKEY": "__PKEY__", "NARA_PNAME": "__PNAME__"}')
src = src.replace('procs = [subprocess.Popen([sys.executable, f"{TMP}/worker.py", str(k), str(NG)], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(k)}) for k in range(NG)]',
                  'procs = []\nfor k in range(NG):\n    procs.append(subprocess.Popen([sys.executable, f"{TMP}/worker.py", str(k), str(NG)], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(k)}))\n    if k < NG - 1: time.sleep(90)   # beri jeda agar pemuatan model tidak bertabrakan')
assert "__B64__" not in src and "DONE = set" in src and "time.sleep(90)" in src and "torch.hub.list" in src and "sisa" in src
for s in range(N):
    d = K / f"sam3d_r{s + 1}"; d.mkdir(exist_ok=True)
    (d / "sam3d_rest.py").write_text(src.replace("__SHARD__", str(s)).replace("__N__", str(N)).replace("__PKEY__", PKEY).replace("__PNAME__", f"r{s + 1}"), encoding="utf-8")
    json.dump({"id": f"mostoplesrinelan/naramotion-sam3d-r{s + 1}", "title": f"NaraMotion SAM3D R{s + 1}", "code_file": "sam3d_rest.py",
               "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
               "dataset_sources": ["mostoplesrinelan/naramotion-hf-token"], "competition_sources": [], "kernel_sources": []},
              open(d / "kernel-metadata.json", "w"), indent=2)
    print(d)
