"""Ambil satu video per gerak dari zip Mendeley (CC BY 4.0) lewat HTTP Range, tanpa mengunduh seluruh zip (6 GB).
Klip yang dipilih = klip yang dipakai animasi 3D (assets/ml/anim/m2mr/index.json).
Pemakaian: python tools/fetch_bali_clips.py <folder_keluaran>
"""
import io, json, sys, zipfile, urllib.request
from pathlib import Path
ZIPS = {"putri": "https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/0a3cd3b8-ca82-465d-891d-e7e39952a3fe",
        "putra": "https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/cb0390a4-cca3-4f80-82c9-891b88efba2b"}
class HttpFile(io.RawIOBase):
    def __init__(s, url):
        s.url = url; s.pos = 0
        s.size = int(urllib.request.urlopen(urllib.request.Request(url, method="HEAD")).headers["Content-Length"])
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.pos
    def seek(s, off, whence=0):
        s.pos = off if whence == 0 else s.pos + off if whence == 1 else s.size + off; return s.pos
    def readinto(s, b):
        if s.pos >= s.size: return 0
        end = min(s.pos + len(b), s.size) - 1
        data = urllib.request.urlopen(urllib.request.Request(s.url, headers={"Range": f"bytes={s.pos}-{end}"})).read()
        b[:len(data)] = data; s.pos += len(data); return len(data)
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
idx = json.load(open(Path(__file__).resolve().parents[1] / "assets/ml/anim/m2mr/index.json"))
for ds, url in ZIPS.items():
    zf = zipfile.ZipFile(io.BufferedReader(HttpFile(url), buffer_size=1 << 20))
    names = {n.split("/")[-1][:-4]: n for n in zf.namelist() if n.endswith(".mp4") and "__MACOSX" not in n and "/._" not in n}
    for r in [r for r in idx if r["ds"] == ds]:
        n = names.get(r["clip"])
        if not n: print("tidak ada", r["clip"]); continue
        dst = out / f"{r['key']}.mp4"
        if not dst.exists(): dst.write_bytes(zf.read(n))
        print(ds, r["gerak"], n, dst.stat().st_size)
