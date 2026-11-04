"""Katalog sumber video tari dari YouTube untuk digitalisasi 3D (SAM 3D Body → rig).
- Mencari per nama tari (ytsearch) + memasukkan channel/playlist yang diberikan pengguna.
- Mengambil metadata penuh tiap video: judul, channel, durasi, resolusi, LISENSI (Creative Commons atau standar).
Keluaran: ml/sources/youtube_catalog.json dan .csv (urut: CC dulu, lalu resolusi & durasi).
Lisensi standar YouTube: hanya untuk analisis internal; minta izin pemilik channel sebelum hasil digitalisasi dipublikasikan.
Pemakaian: python tools/youtube_sources.py
"""
import csv, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import yt_dlp

ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "ml/sources"; OUT.mkdir(parents=True, exist_ok=True)
QUERIES = ["tari gambyong", "tari gambyong pareanom", "tari serimpi", "tari bedhaya", "tari pendet", "tari legong", "tari jaipong",
           "tari remo", "tari saman", "tari piring", "tari tor tor", "tari topeng cirebon", "tari kecak", "tari baris bali",
           "tari golek menak", "tari merak", "tari zapin", "tari yapong", "tari lenggang nyai", "tari bajidor kahot",
           "gerak dasar tari jawa", "gerak dasar tari bali", "tutorial tari gambyong", "tutorial tari bali"]
GIVEN = ["https://www.youtube.com/@menesetnikaproduction/videos", "https://www.youtube.com/watch?v=RbeyfjuA8ew",
         "https://www.youtube.com/playlist?list=PLDSJ_clOBZtyYMJtkm8p9du58Oj7_aUiv"]
PER_QUERY, GIVEN_MAX = 25, 120          # batas per kueri & per sumber pengguna (channel berisi 663 video)
flat = {"quiet": True, "extract_flat": True, "skip_download": True, "ignoreerrors": True}
ids = {}
with yt_dlp.YoutubeDL(flat) as y:
    for q in QUERIES:
        r = y.extract_info(f"ytsearch{PER_QUERY}:{q}", download=False) or {}
        for e in r.get("entries") or []:
            if e and e.get("id"): ids.setdefault(e["id"], {"query": q})
    for u in GIVEN:
        r = y.extract_info(u, download=False) or {}
        for e in (r.get("entries") or [r])[:GIVEN_MAX]:
            if e and e.get("id"): ids.setdefault(e["id"], {"query": "sumber pengguna: " + (r.get("title") or u)})
print(len(ids), "video unik; mengambil metadata…", flush=True)

def meta(vid):
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "ignoreerrors": True, "no_warnings": True}) as y:
            d = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        if not d: return None
        return dict(id=vid, url=f"https://www.youtube.com/watch?v={vid}", title=d.get("title"), channel=d.get("channel"), channel_url=d.get("channel_url"),
                    duration=d.get("duration"), height=d.get("height"), views=d.get("view_count"), upload=d.get("upload_date"),
                    license=d.get("license") or "Standard YouTube License", cc="creative commons" in (d.get("license") or "").lower(),
                    query=ids[vid]["query"])
    except Exception as e:
        return None
rows = []
with ThreadPoolExecutor(6) as ex:
    for i, r in enumerate(ex.map(meta, list(ids))):
        if r: rows.append(r)
        if i % 50 == 0: print(i, "/", len(ids), flush=True)
rows.sort(key=lambda r: (not r["cc"], -(r["height"] or 0), -(r["duration"] or 0)))
json.dump(rows, open(OUT / "youtube_catalog.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
with open(OUT / "youtube_catalog.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), "video;", sum(r["cc"] for r in rows), "berlisensi Creative Commons;", OUT / "youtube_catalog.csv")
