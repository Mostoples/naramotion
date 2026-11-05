"""Hasil SAM 3D Body klip YouTube/Drive → animasi Penari Jawa (assets/ml/rig_penari/yt/<stem>.glb) + indeks untuk Arena.
1) python tools/build_yt_rigs.py            → ml/runs/yt_jobs.json + assets/ml/rig_penari/yt/index.json
2) blender -b --factory-startup -P blender/sam3d_retarget.py -- --jobs ml/runs/yt_jobs.json
     --rig assets_src/characters/penari_mixamo.blend --armature PenariMixamo --anim-only
Run Kaggle yang dibaca: ml/runs/sam3d_y*, ml/runs/sam3d_d* (unduh dengan tools/kaggle_output_all.py).
Sumber berlisensi YouTube standar → folder yt_internal/ (tidak di-deploy) dan "internal": true → Arena hanya menampilkannya bila ?internal=1.
"""
import glob, json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "assets/ml/rig_penari/yt"; OUT.mkdir(parents=True, exist_ok=True)
(ROOT / "assets/ml/rig_penari/yt_internal").mkdir(exist_ok=True)   # lisensi YouTube standar: tidak di-deploy (firebase.json ignore)
NAMES = {"bajidor_kahot": "Bajidor Kahot", "bali": "Tari Bali", "baris_bali": "Baris", "bedhaya": "Bedhaya", "dasar_bali": "Gerak dasar Bali",
         "dasar_jawa": "Gerak dasar Jawa", "gambyong": "Gambyong", "golek_menak": "Golek Menak", "indang": "Indang", "jaipong": "Jaipong",
         "kecak": "Kecak", "kreasi_nusantara": "Kreasi Nusantara", "legong": "Legong", "lenggang_nyai": "Lenggang Nyai", "merak": "Merak",
         "mojang_priangan": "Mojang Priangan", "pande_gelang": "Pande Gelang", "pendet": "Pendet", "piring": "Piring", "rampak_bedug": "Rampak Bedug",
         "remo": "Remo", "ronggeng": "Ronggeng", "sajojo": "Sajojo", "saman": "Saman", "serimpi": "Serimpi", "topeng_cirebon": "Topeng Cirebon",
         "tor_tor": "Tor Tor", "yapong": "Yapong", "zapin": "Zapin", "kijang": "Kijang", "sancang_gugat": "Sancang Gugat", "leungiteun": "Leungiteun",
         "nganyam_wanci": "Nganyam Wanci", "ngelanglang": "Ngelanglang Banten"}
REGION = {"Bali": ("bali", "baris_bali", "dasar_bali", "kecak", "legong", "pendet"), "Jawa": ("bedhaya", "dasar_jawa", "gambyong", "golek_menak", "remo", "serimpi"),
          "Sunda & Banten": ("bajidor_kahot", "jaipong", "kijang", "leungiteun", "merak", "mojang_priangan", "nganyam_wanci", "ngelanglang", "pande_gelang",
                             "rampak_bedug", "ronggeng", "sancang_gugat", "topeng_cirebon", "yapong"),
          "Sumatra": ("indang", "piring", "saman", "tor_tor", "zapin"), "Betawi": ("lenggang_nyai",), "Papua": ("sajojo",)}
src = {}
for f in ("ml/data/youtube_clips/sources.json", "ml/data/drive_clips/sources.json"):
    p = ROOT / f
    if p.exists():
        for r in json.load(open(p, encoding="utf-8")): src[Path(r["file"]).stem] = dict(r, via="Drive tim" if "drive" in f else "YouTube")
jobs, idx = [], []
for npz in sorted(glob.glob(str(ROOT / "ml/runs/sam3d_[yd]*/sam3d/youtube/yt/*/*.npz"))):
    stem = Path(npz).stem; n = np.load(npz)["kp3d"].shape[0]
    if n < 50: print("lewati (terlalu pendek)", stem, n); continue
    dance = stem.split("__")[0]; s = src.get(stem, {})
    internal = "creative" not in str(s.get("license", "")).lower(); sub = "yt_internal" if internal else "yt"
    region = next((k for k, v in REGION.items() if dance in v), "Nusantara")
    same = sum(1 for r in idx if r["dance"] == dance) + 1
    jobs.append({"npz": str(Path(npz).relative_to(ROOT)).replace("\\", "/"), "out": f"assets/ml/rig_penari/{sub}/{stem}.glb", "name": stem})
    idx.append({"key": f"{sub}/{stem}", "dance": dance, "region": region, "gerak": f"{NAMES.get(dance, dance.replace('_', ' ').title())} {same}",
                "sec": round(n / 5), "title": s.get("title", ""), "channel": s.get("channel", ""), "url": s.get("url", ""), "via": s.get("via", ""),
                "license": s.get("license", "YouTube standar"), "internal": internal})
json.dump(jobs, open(ROOT / "ml/runs/yt_jobs.json", "w"), indent=0)
json.dump([r for r in idx if not r["internal"]], open(OUT / "index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump([r for r in idx if r["internal"]], open(OUT.parent / "yt_internal/index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)   # tidak di-deploy
print(len(jobs), "klip;", len({r["dance"] for r in idx}), "jenis tari;", sum(r["internal"] for r in idx), "internal")
