"""NaraMotion · Kaggle: Motion2MixamoRig (GVHMR + HaMeR) — video tari Bali → animasi karakter Mixamo (.glb).
Aset dari dataset privat naramotion-m2mr-assets (SMPL-X & MANO lisensi non-komersial MPI, Y Bot Mixamo, klip CC BY 4.0).
Keluaran: /kaggle/working/out/<klip>/ (mixamo_character.glb, skeleton_motion.npz, mixamo_rotations.npz, videos/compare.mp4, run.json) + log.txt
"""
import os, glob, shutil, subprocess, time
OUT = "/kaggle/working"; LOG = open(f"{OUT}/log.txt", "a")
def sh(cmd, cwd=None):
    t = time.time(); r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    msg = f"$ {cmd}\n[exit {r.returncode}, {time.time()-t:.0f}s]\n{(r.stdout + r.stderr)[-4000:]}\n"
    print(msg, flush=True); LOG.write(msg); LOG.flush(); return r.returncode
SRC = os.path.dirname(glob.glob("/kaggle/input/**/SMPLX_NEUTRAL.npz", recursive=True)[0])
R = "/tmp/m2mr"
sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; python --version; df -h /tmp | tail -1")
sh(f"git clone -q --depth 1 https://github.com/MaxLiu22/Motion2MixamoRig {R}")
sh("pip install -q --upgrade pip setuptools wheel && pip install -q 'numpy>=1.26' && pip install -q --no-build-isolation 'chumpy==0.70'")
sh("pip install -q -e .", cwd=R)
for sub in ["assets/body_models/smplx", "assets/body_models/mano", "assets/mixamo", "assets/video"]: os.makedirs(f"{R}/{sub}", exist_ok=True)
shutil.copy(f"{SRC}/SMPLX_NEUTRAL.npz", f"{R}/assets/body_models/smplx/SMPLX_NEUTRAL.npz")
shutil.copy(f"{SRC}/MANO_RIGHT.pkl", f"{R}/assets/body_models/mano/MANO_RIGHT.pkl")
shutil.copy(f"{SRC}/Y_Bot.fbx", f"{R}/assets/mixamo/Y_Bot.fbx")
sh("m2mr doctor --detect-hands", cwd=R)
for v in sorted(glob.glob(f"{SRC}/*.mp4")):
    name = os.path.splitext(os.path.basename(v))[0]; dst = f"{R}/assets/video/{name}.mp4"; shutil.copy(v, dst)
    sh(f"m2mr run --video assets/video/{name}.mp4 --rig assets/mixamo/Y_Bot.fbx --set-extractor gvhmr --detect-hands --device cuda --output-dir {OUT}/out/{name}", cwd=R)
sh(f"du -sh {OUT}/out/*; find {OUT}/out -maxdepth 2 | head -40")
