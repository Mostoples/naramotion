"""Pilih & unduh potongan video YouTube untuk digitalisasi 3D (SAM 3D Body di Kaggle).
Pilih ±2 video per jenis tari dari ml/sources/youtube_catalog.json: utamakan CC, judul "tutorial/gerak dasar/tunggal/solo",
resolusi ≥720p, durasi 1–15 menit. Unduh potongan 45 detik dari tengah video (720p, tanpa audio) → ml/data/youtube_clips/.
Lisensi standar YouTube: hanya untuk digitalisasi/riset internal dengan menyebut sumber; minta izin sebelum dipublikasikan.
Pemakaian: python tools/youtube_pick_download.py [jumlah_per_tari=2] [detik=45]
"""
import json, re, sys, subprocess
from pathlib import Path
import os, shutil
import yt_dlp
# yt-dlp memeriksa ffmpeg lewat PATH untuk unduhan sebagian
if os.environ.get('FFMPEG_DIR'): os.environ['PATH'] = os.environ['FFMPEG_DIR'] + os.pathsep + os.environ.get('PATH', '')

ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "ml/data/youtube_clips"; OUT.mkdir(parents=True, exist_ok=True)
PER = int(sys.argv[1]) if len(sys.argv) > 1 else 2; SEG = int(sys.argv[2]) if len(sys.argv) > 2 else 45
rows = json.load(open(ROOT / "ml/sources/youtube_catalog.json", encoding="utf-8"))
def dance(r):
    q = r["query"]
    if q.startswith("sumber pengguna"):
        t = (r["title"] or "").lower()
        for k in ("pande gelang", "jaipong", "rampak bedug", "ronggeng", "remo", "tor tor", "saman", "piring", "mojang priangan", "sajojo", "zapin", "indang"):
            if k in t: return k.replace(" ", "_")
        return "kreasi_nusantara"
    return q.replace("tutorial ", "").replace("gerak dasar ", "dasar_").replace(" pareanom", "").replace("tari ", "").replace(" ", "_")
def score(r):
    t = (r["title"] or "").lower()
    s = 100 * r["cc"] + 10 * bool(re.search(r"tutorial|gerak dasar|tunggal|solo|belajar", t)) - 6 * bool(re.search(r"kolosal|massal|kelompok|festival|lomba", t))
    return s + min(r["height"] or 0, 1080) / 100
pick = {}
for r in sorted(rows, key=score, reverse=True):
    d = dance(r)
    if (r["height"] or 0) < 720 or not (60 <= (r["duration"] or 0) <= 900): continue
    if len(pick.setdefault(d, [])) < PER: pick[d].append(r)
sel = [dict(r, dance=d) for d, rs in pick.items() for r in rs]
print(len(pick), "jenis tari,", len(sel), "video")
done = []
for r in sel:
    mid = (r["duration"] or SEG) / 2; a, b = max(0, mid - SEG / 2), mid + SEG / 2
    dst = OUT / f"{r['dance']}__{r['id']}.mp4"
    if not dst.exists():
        opts = {"quiet": True, "no_warnings": True, "format": "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]", "outtmpl": str(dst),
                "download_ranges": yt_dlp.utils.download_range_func(None, [(a, b)]), "force_keyframes_at_cuts": True, "merge_output_format": "mp4", "ffmpeg_location": __import__("os").environ.get("FFMPEG_DIR")}
        try:
            with yt_dlp.YoutubeDL(opts) as y: y.download([r["url"]])
        except Exception as e: print("gagal", r["id"], str(e)[:120]); continue
    if dst.exists():
        done.append(dict(file=dst.name, dance=r["dance"], id=r["id"], url=r["url"], title=r["title"], channel=r["channel"], license=r["license"], start=round(a, 1), end=round(b, 1)))
        print("ok", dst.name, dst.stat().st_size // 1024, "KB")
json.dump(done, open(OUT / "sources.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(done), "klip →", OUT)
