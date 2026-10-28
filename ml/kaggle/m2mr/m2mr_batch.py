"""NaraMotion · Motion2MixamoRig (GVHMR + HaMeR, GPU) untuk animasi 3D 24 gerak dasar tari Bali.
Target 2 animasi per gerak; klip yang ditolak (mis. lebih dari satu orang) dilewati dan diganti klip berikutnya.
Klip dari zip Mendeley (CC BY 4.0); SMPL-X, MANO, Y Bot dari dataset privat naramotion-m2mr-assets.
Keluaran /kaggle/working/anim/<dataset>__<gerak>__<klip>.glb (+ compare.mp4 kecil, run.json) dan log.txt
"""
PER_CLASS, TRY_PER_CLASS = 2, 4
import os, glob, shutil, subprocess, time, zipfile, json
OUT = "/kaggle/working"; R = "/tmp/m2mr"; TMP = "/tmp/nara"; os.makedirs(TMP, exist_ok=True); os.makedirs(f"{OUT}/anim", exist_ok=True)
LOG = open(f"{OUT}/log.txt", "a"); T_END = time.time() + 11.0 * 3600
def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(map(str, a)); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def sh(cmd, cwd=None, tail=1500):
    t = time.time(); r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    log(f"$ {cmd[:150]} [exit {r.returncode}, {time.time()-t:.0f}s]")
    if r.returncode: log((r.stdout + r.stderr)[-tail:])
    return r.returncode
ZIPS = {"putri": "https://data.mendeley.com/public-files/datasets/s2gv9d6gpb/files/b2b8b852-8f88-498d-ba06-47cab9240a80/file_downloaded",
        "putra": "https://data.mendeley.com/public-files/datasets/tr9py7hzj4/files/79b815e5-cf48-48c0-9ce2-fc9bf4fa482a/file_downloaded"}
SRC = os.path.dirname(glob.glob("/kaggle/input/**/SMPLX_NEUTRAL.npz", recursive=True)[0])
sh(f"git clone -q --depth 1 https://github.com/MaxLiu22/Motion2MixamoRig {R}")
sh("pip install -q --upgrade pip setuptools wheel && pip install -q 'numpy>=1.26' && pip install -q --no-build-isolation 'chumpy==0.70'")
sh("pip install -q -e .", cwd=R)
for sub in ["assets/body_models/smplx", "assets/body_models/mano", "assets/mixamo", "assets/video"]: os.makedirs(f"{R}/{sub}", exist_ok=True)
shutil.copy(f"{SRC}/SMPLX_NEUTRAL.npz", f"{R}/assets/body_models/smplx/"); shutil.copy(f"{SRC}/MANO_RIGHT.pkl", f"{R}/assets/body_models/mano/"); shutil.copy(f"{SRC}/Y_Bot.fbx", f"{R}/assets/mixamo/")
jobs = []
for ds, url in ZIPS.items():
    z = f"{TMP}/{ds}.zip"; sh(f"curl -sS -L -o {z} '{url}'"); zf = zipfile.ZipFile(z)
    names = sorted(n for n in zf.namelist() if n.endswith(".mp4") and "/train/" in "/" + n and not n.startswith("__MACOSX") and "/._" not in n)
    by = {}
    for n in names: by.setdefault(n.split("/")[-2], []).append(n)
    for c in sorted(by): jobs.append((ds, c, by[c][:: max(1, len(by[c]) // TRY_PER_CLASS)][:TRY_PER_CLASS]))
log(len(jobs), "gerak")
done = {}
for ds, c, cands in jobs:   # putaran 1: 1 animasi per gerak dulu (semua gerak tercakup), putaran 2: animasi kedua
    pass
for rnd in range(PER_CLASS):
    for ds, c, cands in jobs:
        key = (ds, c)
        while done.get(key, 0) <= rnd and cands and time.time() < T_END:
            n = cands.pop(0); stem = os.path.basename(n)[:-4]; v = f"{R}/assets/video/{stem}.mp4"
            with zipfile.ZipFile(f"{TMP}/{ds}.zip").open(n) as s, open(v, "wb") as d: shutil.copyfileobj(s, d)
            od = f"{TMP}/out/{stem}"
            rc = sh(f"m2mr run --video assets/video/{stem}.mp4 --rig assets/mixamo/Y_Bot.fbx --set-extractor gvhmr --detect-hands --device cuda --output-dir {od}", cwd=R, tail=600)
            if rc == 0 and os.path.exists(f"{od}/mixamo_character.glb"):
                base = f"{OUT}/anim/{ds}__{c}__{stem}"; shutil.copy(f"{od}/mixamo_character.glb", base + ".glb"); shutil.copy(f"{od}/run.json", base + ".json")
                sh(f"ffmpeg -loglevel error -y -i {od}/videos/compare.mp4 -vf scale=640:-2 -an {base}_compare.mp4")
                done[key] = done.get(key, 0) + 1; log("OK", ds, c, stem, f"{json.load(open(od + '/run.json')).get('elapsed_s', 0):.0f}s")
            os.remove(v)
log("SELESAI", sum(done.values()), "animasi untuk", len(done), "gerak")
