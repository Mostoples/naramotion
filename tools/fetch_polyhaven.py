"""Aset CC0 Poly Haven untuk Arena: tekstur lantai PBR (1k: warna, normal GL, kekasaran) dan langit HDRI.
Keluaran: assets/arena/tex/<nama>_{diff,nor,rough}.jpg ; assets/arena/sky/<hdri>.hdr (1k, cahaya) + <hdri>.jpg (4096×2048, latar)
Pemakaian: python tools/fetch_polyhaven.py
"""
import io, json, urllib.request
from pathlib import Path
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[1]; T = ROOT / "assets/arena/tex"; S = ROOT / "assets/arena/sky"; T.mkdir(parents=True, exist_ok=True); S.mkdir(parents=True, exist_ok=True)
TEX = ["brick_floor_02", "cobblestone_floor_01", "brown_planks_09", "aerial_grass_rock"]
SKY = ["kloofendal_48d_partly_cloudy_puresky"]
UA = {"User-Agent": "NaraMotion/1.0 (non-komersial)"}   # API Poly Haven menolak permintaan tanpa User-Agent
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA)).read()
api = lambda a: json.loads(get(f"https://api.polyhaven.com/files/{a}"))
for a in TEX:
    f = api(a)
    for key, suf in (("Diffuse", "diff"), ("nor_gl", "nor"), ("Rough", "rough")):
        dst = T / f"{a}_{suf}.jpg"
        if not dst.exists(): dst.write_bytes(get(f[key]["1k"]["jpg"]["url"]))
    print("tekstur", a)
for a in SKY:
    f = api(a)
    if not (S / f"{a}.hdr").exists(): (S / f"{a}.hdr").write_bytes(get(f["hdri"]["1k"]["hdr"]["url"]))
    if not (S / f"{a}.jpg").exists():
        Image.open(io.BytesIO(get(f["tonemapped"]["url"]))).convert("RGB").resize((4096, 2048), Image.LANCZOS).save(S / f"{a}.jpg", quality=86)
    print("langit", a)
