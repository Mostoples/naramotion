"""Video tari dari folder Google Drive tim (19JlVteFWFsiyhYxHyPNyjcW5vF9jWnIf) → potongan 45 dtk untuk SAM 3D Body.
Unduh (gdown) → ml/data/drive_raw/<ytid>.mp4 ; potong tengah 45 dtk, 720p, tanpa audio → ml/data/drive_clips/<tari>__<ytid>.mp4
Video yang sudah ada di ml/data/youtube_clips dilewati. Asal video tetap YouTube (lisensi standar): hanya internal, minta izin sebelum publikasi.
Pemakaian: python tools/drive_clips.py [detik=45]
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
import gdown
ROOT = Path(__file__).resolve().parents[1]; RAW = ROOT / "ml/data/drive_raw"; OUT = ROOT / "ml/data/drive_clips"
RAW.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
SEG = int(sys.argv[1]) if len(sys.argv) > 1 else 45
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"; FP = shutil.which("ffprobe") or str(Path(FF).with_name("ffprobe" + Path(FF).suffix))
# (drive id, judul) — dari 3 subfolder: Video Tunggal, Playlist Tari Kreasi, Menes Etnika Production
FILES = [
 ("1UkG0zoabdLSCdfL3qOoZ2gsrGkNGASRd", "Tari Remo Gagrak Anyar [RbeyfjuA8ew]"),
 ("1z7lnhb4LmRTdcyTyyxQkUCmXci1ULI6F", "Tari Jaipong gerakan mudah Haturan Mojang Priangan [E6B1j7Z-rks]"),
 ("1hydLAlJE_uQ4hGMmTSz2HiRq58ylJL4v", "TARI KREASI MUDAH ETHNIC DANCE [mJBkyQelAys]"),
 ("17RBIG8bgD9eYcpp4_2cQQVwdtsP5VJ3A", "Tari Kijang Gerakan mudah Tari Kreasi Sunda [d9xJQBnYMNY]"),
 ("1f_mLTtLxHOLhTgfHKGYoHr5I8pQJYeZ6", "Gerakan Tari Kreasi Jaipong Sancang Gugat [mVQfIXqrulA]"),
 ("1p9BrAAZHEBdAAg3YsBQ65HqvSBI150TG", "Tari Kreasi Siswa mudah dan bagus [av8kcH_fkVU]"),
 ("1S9CvcRXHJPVMworpAwgOhWEVzhM1cnZb", "TARI NUSANTARA Gerakan mudah dipelajari [E9aWabbO5c0]"),
 ("1l-_44XM_o0b2BgdmaroWO3h-6Owtj_bP", "Tari Tor Tor gerakan mudah Batak Sumatera utara [vktm0stL8rE]"),
 ("1dP0_YHoTRfYYmRyDqWCyKUoswSi6qK7R", "TARI KREASI Nusantara Modern [O1ISnss3CZw]"),
 ("16FfIluiMESG3Nnv3-BARthzPavs_sOBL", "TARI KREASI TRADISIONAL MUDAH Kolaborasi etnis [VOOxGx0YFYo]"),
 ("12rUihHuou6AJuQCm5kqexSGxUK0NjN0W", "Tari Tradisi Pande Gelang Kelompok 11 Menes Etnika [VUAGt9tOlvo]"),
 ("1pnVosLTOKjgTcvJkYXdDdH8V12Z5j1SI", "Tari Tradisi Pande Gelang Kelompok 10 Menes Etnika [qth667m7Zys]"),
 ("1-qTgxJXkBCcgXX98XVzSDRwM1tTuF4bq", "Kolaborasi antar mapel penampilan Rampak bedug [MmOL97GIajA]"),
 ("1m5SGNZhZDCrsOzhJmtuE7fAfwXQ6NUR5", "Rampak Bedug SMAN 4 pandeglang [6PiW0F_ecwI]"),
 ("1FbI0T_9_JYTIBInp8u_I7fmdg3xctFah", "Tarian Kreasi Nganyam Wanci [gSkNG04TXbI]"),
 ("1JoTDN10RA9gbzhTYM1pEC1HxACHsQBy8", "Tari Leungiteun Lomba Tari Kreasi Nusantara [Gzlz8UO-Stg]"),
 ("19SFMDNmUhNmX5i5D6tNtEM5gaL9miVMG", "Tari Jaipong Tanjung Baru Lomba Tari Kreasi Nusantara [MskduCyhxLY]"),
 ("1j5m6Yw0DDP7GugxMTZsd_jgd1SdkLbw6", "Tari Jaipong Kalang Sunda Lomba Tari Kreasi Nusantara [ifSDHXijfU8]"),
 ("1znfhAXaLSepjpeHw8l7iDSvcmRZfQlzS", "Tari Jaipong Gandrung Bandung Lomba Tari Tradisi Nusantara [WtnMwEUxKtM]"),
 ("1hs-nEUWEQ1wSop7vZrJeXrrKa4oV5DCN", "Tari Pande Gelang Lomba Tari Kreasi Nusantara [ReafQr0COz8]"),
 ("1I6Ae8K9lqB-6Kj8wjwKO3_WvNjGzOfHk", "Latihan Tari FLS3N Provinsi Banten Kontingen Pandeglang [enzcpcrDBHY]"),
 ("1QHX1Id__c0tEJczy8DPKDmCZPjEeAyR5", "Tari FLS3N Prov Banten Kontingen Pandeglang [eCoYZbNsDcA]"),
 ("1XQUUhMvIsmWN7fpE8f7UaMXfC9WghTxl", "Tari Jaipong Tanjung Baru Lomba Tari Kreasi Nusantara [YtwNsyeKDA8]"),
 ("1z8Tx8JbAIDj6iirhbSGAPGrAjWq1uBhm", "Tari Sancang Gugat Lomba Tari Kreasi Nusantara [0aB8p1ix7Q0]"),
 ("1cvLStg7p1NgqTI_-o8VM3ZafCMeZf-XU", "Tari Persembahan Pande Gelang SMA Negeri 4 Pandeglang [0IA_VF3M7tE]"),
 ("1rz9B-P5aNeS14Hu2KqgPWcS-07VZ7UsE", "Tari Pande Gelang [LSbV4MbtLTA]"),
 ("1dTWeu9ub6CUztkLnCoLCPvndAOv5Iz2J", "Tari Pande Gelang [fL-DSob-104]"),
 ("1_dYoUXLby54HLJ6XzaonsCJ-rVW1tb1T", "Tari Ngelanglang Banten [CWVT4HsqzTw]"),
 ("1deUs0D4lhipl6xPKae4N4_xpuFI95Veq", "HUT Banten ke-26 Tarian Persembahan Ngelanglang Banten [1ElrVcTJPSA]"),
 ("1XsIm3zSG853EahRB4gWzz9CDXAT9jeCI", "Lomba Banten Traditional Dance Tarian Ngelanglang Banten [fhGlGd34zgI]"),
 # sudah diproses lewat youtube_clips: 0R9xxBxQrvc 4uH7-MQFWt4 MK51gitWF9Y ZO1UP1bTE3A ks2GtOPXJf4 ; bukan tari: iPFwgbmDhe4
]
DANCES = ("remo", "jaipong", "kijang", "sancang gugat", "tor tor", "pande gelang", "rampak bedug", "nganyam wanci", "leungiteun", "ngelanglang", "mojang priangan")
def dance(t):
    t = t.lower()
    for k in DANCES:
        if k in t: return k.replace(" ", "_")
    return "kreasi_nusantara"
have = {r["id"] for r in json.load(open(ROOT / "ml/data/youtube_clips/sources.json", encoding="utf-8"))}
done = []
for did, title in FILES:
    yt = re.search(r"\[([\w-]{11})\]", title).group(1)
    if yt in have: continue
    raw = RAW / f"{yt}.mp4"
    if not raw.exists(): gdown.download(id=did, output=str(raw), quiet=True)
    dur = float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)], capture_output=True, text=True).stdout.strip() or 0)
    a = max(0.0, dur / 2 - SEG / 2); d = dance(title); dst = OUT / f"{d}__{yt}.mp4"
    if not dst.exists():
        subprocess.run([FF, "-loglevel", "error", "-y", "-ss", f"{a:.1f}", "-i", str(raw), "-t", str(SEG), "-vf", "scale=-2:'min(720,ih)'", "-an",
                        "-c:v", "libx264", "-crf", "20", "-preset", "fast", str(dst)], check=True)
    done.append(dict(file=dst.name, dance=d, id=yt, url=f"https://www.youtube.com/watch?v={yt}", title=title, drive_id=did,
                     license="YouTube standar (via Drive tim) — internal", start=round(a, 1), end=round(min(dur, a + SEG), 1)))
    print("ok", dst.name, round(dur), "s", dst.stat().st_size // 1024, "KB", flush=True)
json.dump(done, open(OUT / "sources.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(done), "klip ->", OUT)
