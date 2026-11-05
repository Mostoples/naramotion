"""Unduh avatar & animasi Microsoft Rocketbox (MIT, github.com/microsoft/Microsoft-Rocketbox) untuk penonton Arena.
Keluaran: assets_src/rocketbox/<avatar>/{<avatar>.fbx, Textures/*} dan assets_src/rocketbox/anim/*.fbx
Pemakaian: python tools/fetch_rocketbox.py
"""
import concurrent.futures as cf, urllib.request, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "assets_src/rocketbox"
RAW = "https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/master/Assets/"
# berpakaian sopan & umum di Indonesia (jilbab, baju koko + peci, kemeja, anak-anak)
AVATARS = {"Adults": ["Female_Adult_02", "Female_Adult_05", "Female_Adult_06", "Female_Adult_09", "Female_Adult_14", "Female_Adult_15",
                      "Male_Adult_02", "Male_Adult_06", "Male_Adult_08", "Male_Adult_09", "Male_Adult_14", "Male_Adult_15", "Male_Adult_20"],
           "Children": ["Female_Child_02", "Male_Child_01", "Male_Child_02"]}
ANIMS = ["f_sit_chair_idle_neutral_01", "f_idle_neutral_01", "f_claphands_01", "m_sit_chair_idle_neutral_01", "m_idle_neutral_01", "m_claphands_01"]
TEX_KEEP = ("_color", "_normal")   # peta specular tidak dipakai (PBR three.js)

def files():
    import json
    tree = json.load(urllib.request.urlopen("https://api.github.com/repos/microsoft/Microsoft-Rocketbox/git/trees/master?recursive=1"))["tree"]
    paths = {t["path"] for t in tree if t["type"] == "blob"}
    for grp, names in AVATARS.items():
        for n in names:
            base = f"Assets/Avatars/{grp}/{n}/"
            for p in paths:
                if p == base + f"Export/{n}.fbx": yield p, OUT / n / f"{n}.fbx"
                elif p.startswith(base + "Textures/") and any(k in p.lower() for k in TEX_KEEP): yield p, OUT / n / "Textures" / Path(p).name
    for a in ANIMS:
        p = f"Assets/Animations/all_animations_max_motextr_static/{a}.max.fbx"
        if p in paths: yield p, OUT / "anim" / f"{a}.fbx"
        else: print("animasi tidak ada:", a)

def get(job):
    p, dst = job
    if dst.exists() and dst.stat().st_size > 0: return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve("https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/master/" + urllib.parse.quote(p), dst)
    return dst.stat().st_size

jobs = list(files())
with cf.ThreadPoolExecutor(8) as ex: total = sum(ex.map(get, jobs))
print(len(jobs), "berkas,", total // 2**20, "MB baru ->", OUT)
