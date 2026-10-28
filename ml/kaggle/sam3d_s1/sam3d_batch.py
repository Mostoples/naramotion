"""NaraMotion · SAM 3D Body (Meta, SAM License) untuk SEMUA klip tari Bali (putri 1.740 + putra 828, Mendeley Data CC BY 4.0).
Pose 3D seluruh tubuh + jari per frame, 5 fps, fp16, dua GPU T4 paralel (kode worker tersimpan base64 di bawah).
Jalankan dari EDITOR Kaggle (Secret HF_TOKEN), Accelerator "GPU T4 x2", Internet ON. SHARD = 0, 1, 2 → Save & Run All tiap bagian.
Keluaran: /kaggle/working/sam3d/<dataset>/<split>/<gerak>/<klip>.npz + log*.txt
"""
SHARD, N_SHARDS = 1, 3
import os, sys, glob, time, json, zipfile, subprocess, base64
OUT = "/kaggle/working"; R = "/tmp/s3db"; TMP = "/tmp/nara"; os.makedirs(TMP, exist_ok=True)
ZIPS = {"putri": "https://data.mendeley.com/public-files/datasets/s2gv9d6gpb/files/b2b8b852-8f88-498d-ba06-47cab9240a80/file_downloaded",
        "putra": "https://data.mendeley.com/public-files/datasets/tr9py7hzj4/files/79b815e5-cf48-48c0-9ce2-fc9bf4fa482a/file_downloaded"}
WORKER_B64 = "IiIiV29ya2VyIFNBTSAzRCBCb2R5IChzYXR1IEdQVSk6IG1lbXByb3NlcyBiYWdpYW4gZGFmdGFyIGtsaXAgZGFyaSAvdG1wL25hcmEvam9icy5qc29uLiIiIgppbXBvcnQgb3MsIHN5cywgdGltZSwganNvbiwgemlwZmlsZSwgc2h1dGlsCk9VVCA9ICIva2FnZ2xlL3dvcmtpbmciOyBSID0gIi90bXAvczNkYiI7IFRNUCA9ICIvdG1wL25hcmEiOyBGUFNfT1VUID0gNTsgV09SS0VSID0gaW50KHN5cy5hcmd2WzFdKQpMT0cgPSBvcGVuKGYie09VVH0vbG9ne1dPUktFUn0udHh0IiwgImEiKQpkZWYgbG9nKCphKToKICAgIHMgPSB0aW1lLnN0cmZ0aW1lKCIlSDolTTolUyAiKSArICIgIi5qb2luKG1hcChzdHIsIGEpKTsgcHJpbnQocywgZmx1c2g9VHJ1ZSk7IExPRy53cml0ZShzICsgIlxuIik7IExPRy5mbHVzaCgpClRfRU5EID0gb3MucGF0aC5nZXRtdGltZShmIntUTVB9L2pvYnMuanNvbiIpICsgMTEuMCAqIDM2MDAKc3lzLnBhdGguaW5zZXJ0KDAsIFIpOyBvcy5jaGRpcihSKQppbXBvcnQgbnVtcHkgYXMgbnAsIHRvcmNoLCBjdjIKZnJvbSBzYW1fM2RfYm9keSBpbXBvcnQgbG9hZF9zYW1fM2RfYm9keSwgU0FNM0RCb2R5RXN0aW1hdG9yCmNrID0gZiJ7Un0vY2hlY2twb2ludHMvc2FtLTNkLWJvZHktZGlub3YzIgptb2RlbCwgY2ZnID0gbG9hZF9zYW1fM2RfYm9keShmIntja30vbW9kZWwuY2twdCIsIGRldmljZT0iY3VkYSIsIG1ocl9wYXRoPWYie2NrfS9hc3NldHMvbWhyX21vZGVsLnB0IikKZXN0ID0gU0FNM0RCb2R5RXN0aW1hdG9yKHNhbV8zZF9ib2R5X21vZGVsPW1vZGVsLCBtb2RlbF9jZmc9Y2ZnLCBodW1hbl9kZXRlY3Rvcj1Ob25lLCBodW1hbl9zZWdtZW50b3I9Tm9uZSwgZm92X2VzdGltYXRvcj1Ob25lKQpmcm9tIHVsdHJhbHl0aWNzIGltcG9ydCBZT0xPCnlvbG8gPSBZT0xPKCJ5b2xvdjhtLnB0IikKTlcgPSBpbnQoc3lzLmFyZ3ZbMl0pIGlmIGxlbihzeXMuYXJndikgPiAyIGVsc2UgMgpqb2JzID0ganNvbi5sb2FkKG9wZW4oZiJ7VE1QfS9qb2JzLmpzb24iKSlbV09SS0VSOjpOV10KenMgPSB7ZHM6IHppcGZpbGUuWmlwRmlsZShmIntUTVB9L3tkc30uemlwIikgZm9yIGRzIGluICgicHV0cmkiLCAicHV0cmEiKX0KaGFsZiA9IFRydWUKZGVmIGluZmVyKGZyLCBiKToKICAgIGdsb2JhbCBoYWxmCiAgICBpZiBoYWxmOgogICAgICAgIHRyeToKICAgICAgICAgICAgd2l0aCB0b3JjaC5hdXRvY2FzdCgiY3VkYSIsIGR0eXBlPXRvcmNoLmZsb2F0MTYpOgogICAgICAgICAgICAgICAgcmV0dXJuIGVzdC5wcm9jZXNzX29uZV9pbWFnZShmciwgYmJveGVzPWJbTm9uZV0pCiAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBlOgogICAgICAgICAgICBoYWxmID0gRmFsc2U7IGxvZygiZnAxNiBnYWdhbCwgcGFrYWkgZnAzMjoiLCBzdHIoZSlbOjIwMF0pCiAgICByZXR1cm4gZXN0LnByb2Nlc3Nfb25lX2ltYWdlKGZyLCBiYm94ZXM9YltOb25lXSkKdF9hbGwsIG5fZnIgPSB0aW1lLnRpbWUoKSwgMApmb3IgaiwgKGRzLCBuYW1lKSBpbiBlbnVtZXJhdGUoam9icyk6CiAgICBpZiB0aW1lLnRpbWUoKSA+IFRfRU5EOgogICAgICAgIGxvZygiYmF0YXMgd2FrdHUsIGJlcmhlbnRpIGRpIiwgaiwgIi8iLCBsZW4oam9icykpOyBicmVhawogICAgc3BsaXQsIGNscywgZm4gPSBuYW1lLnNwbGl0KCIvIilbLTM6XTsgZHN0ID0gZiJ7T1VUfS9zYW0zZC97ZHN9L3tzcGxpdH0ve2Nsc30ve2ZuWzotNF19Lm5weiIKICAgIGlmIG9zLnBhdGguZXhpc3RzKGRzdCk6IGNvbnRpbnVlCiAgICBwID0gZiJ7VE1QfS93e1dPUktFUn0ubXA0IgogICAgd2l0aCB6c1tkc10ub3BlbihuYW1lKSBhcyBzLCBvcGVuKHAsICJ3YiIpIGFzIGQ6IHNodXRpbC5jb3B5ZmlsZW9iaihzLCBkKQogICAgY2FwID0gY3YyLlZpZGVvQ2FwdHVyZShwKTsgZnBzID0gY2FwLmdldChjdjIuQ0FQX1BST1BfRlBTKSBvciAzMDsgc3RlcCA9IG1heCgxLCByb3VuZChmcHMgLyBGUFNfT1VUKSkKICAgIHNpemUgPSBucC5hcnJheShbY2FwLmdldChjdjIuQ0FQX1BST1BfRlJBTUVfSEVJR0hUKSwgY2FwLmdldChjdjIuQ0FQX1BST1BfRlJBTUVfV0lEVEgpXSk7IHJlYyA9IHt9OyBpID0gMAogICAgd2hpbGUgVHJ1ZToKICAgICAgICBvaywgZnIgPSBjYXAucmVhZCgpCiAgICAgICAgaWYgbm90IG9rOiBicmVhawogICAgICAgIGlmIGkgJSBzdGVwID09IDA6CiAgICAgICAgICAgIGRldCA9IHlvbG8oZnIsIGNsYXNzZXM9WzBdLCB2ZXJib3NlPUZhbHNlKVswXS5ib3hlcwogICAgICAgICAgICBpZiBsZW4oZGV0KToKICAgICAgICAgICAgICAgIGIgPSBkZXQueHl4eS5jcHUoKS5udW1weSgpOyBiID0gYltucC5hcmdtYXgoKGJbOiwgMl0gLSBiWzosIDBdKSAqIChiWzosIDNdIC0gYls6LCAxXSkpXQogICAgICAgICAgICAgICAgb3V0cyA9IGluZmVyKGZyLCBiKQogICAgICAgICAgICAgICAgaWYgb3V0czoKICAgICAgICAgICAgICAgICAgICBvID0gb3V0c1swXQogICAgICAgICAgICAgICAgICAgIGZvciBrLCB2IGluIFsoImtwM2QiLCBvWyJwcmVkX2tleXBvaW50c18zZCJdKSwgKCJyb3RzIiwgb1sicHJlZF9nbG9iYWxfcm90cyJdKSwgKCJjYW1fdCIsIG9bInByZWRfY2FtX3QiXSksICgiYm9keSIsIG9bImJvZHlfcG9zZV9wYXJhbXMiXSksCiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICgiaGFuZCIsIG9bImhhbmRfcG9zZV9wYXJhbXMiXSksICgiYmJveCIsIGIpLCAoImZvY2FsIiwgb1siZm9jYWxfbGVuZ3RoIl0pLCAoInQiLCBpIC8gZnBzKV06CiAgICAgICAgICAgICAgICAgICAgICAgIHJlYy5zZXRkZWZhdWx0KGssIFtdKS5hcHBlbmQobnAuYXNhcnJheSh2LCBucC5mbG9hdDE2IGlmIGsgaW4gKCJrcDNkIiwgInJvdHMiLCAiYm9keSIsICJoYW5kIikgZWxzZSBucC5mbG9hdDMyKSkKICAgICAgICBpICs9IDEKICAgIG9zLm1ha2VkaXJzKG9zLnBhdGguZGlybmFtZShkc3QpLCBleGlzdF9vaz1UcnVlKQogICAgaWYgcmVjOiBucC5zYXZlel9jb21wcmVzc2VkKGRzdCwgc2l6ZT1zaXplLCAqKntrOiBucC5zdGFjayh2KSBmb3IgaywgdiBpbiByZWMuaXRlbXMoKX0pCiAgICBuX2ZyICs9IGxlbihyZWMuZ2V0KCJ0IiwgW10pKQogICAgaWYgaiAlIDIwID09IDA6IGxvZyhmIlt7aisxfS97bGVuKGpvYnMpfV0ge2RzfS97Y2xzfS97Zm59IMK3IHtuX2ZyfSBmcmFtZSDCtyB7KHRpbWUudGltZSgpLXRfYWxsKS9tYXgobl9mciwxKTouMmZ9IHMvZnJhbWUgwrcgZnAxNj17aGFsZn0iKQpsb2coIndvcmtlciBzZWxlc2FpIiwgbl9mciwgImZyYW1lIikK"
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
