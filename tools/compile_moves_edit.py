"""Susun video kompilasi dari rekaman tools/compile_moves_video.py → marketing/kompilasi/naramotion_kompilasi_gerak_1menit.mp4 (60 dtk, 1080p30).
Pembuka (judul di atas cuplikan pertama yang diburamkan) → 20 cuplikan dengan dissolve → penutup + kredit; musik Bali Joged (domain publik).
"""
import json, os, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "marketing/kompilasi"; TMP = OUT / "_raw"
FF = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
D = json.load(open(TMP / "segs.json")); SEG, X, INTRO, OUTRO = 2.6, 0.35, 3.5, 4.5
FONT = "C\\:/Windows/Fonts/georgia.ttf"; FONTS = "C\\:/Windows/Fonts/segoeui.ttf"; LOGO = str(ROOT / "assets/logo/naramotion-mark.png")
run = lambda *a: subprocess.run([FF, "-loglevel", "error", "-y", *a], check=True)
ENC = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30"]

def txt(name, s): p = TMP / name; p.write_text(s, encoding="utf-8"); return str(p).replace("\\", "/").replace(":", "\\:")
# 1) potong cuplikan (sedikit lebih panjang untuk dissolve)
clips = []
for i, t in enumerate(D["segs"]):
    c = TMP / f"c{i:02d}.mp4"; run("-ss", f"{t:.2f}", "-i", D["vid"], "-t", f"{SEG + X:.2f}", "-vf", "scale=1920:1080,fps=30", "-an", *ENC, str(c)); clips.append(c)
# 2) pembuka & penutup: latar cuplikan diburamkan + logo + teks
def card(src, ss, dur, lines, out):
    dt = []
    for (f, fs, y, color, file) in lines:
        dt.append(f"drawtext=fontfile='{f}':textfile='{file}':fontsize={fs}:fontcolor={color}:x=(w-text_w)/2:y={y}:alpha='min(1,t/0.6)'")
    vf = (f"[0:v]scale=1920:1080,boxblur=18:2,eq=brightness=-0.28:saturation=0.8[bg];[1:v]scale=-1:150,format=rgba,fade=in:st=0:d=0.6:alpha=1[lg];"
          f"[bg][lg]overlay=(W-w)/2:200[v0];[v0]{','.join(dt)},fade=in:st=0:d=0.5[v]")
    run("-ss", f"{ss:.2f}", "-i", str(src), "-loop", "1", "-t", f"{dur}", "-i", LOGO, "-filter_complex", vf, "-map", "[v]", "-t", f"{dur}", *ENC, str(out))
GOLD = "0xE8C27A"
card(clips[0], 0, INTRO + X, [(FONT, 30, 400, GOLD, txt("t1.txt", "N A R A M O T I O N")), (FONT, 84, 460, "white", txt("t2.txt", "Kompilasi Gerak Tari Nusantara")),
     (FONTS, 30, 590, "white@0.85", txt("t3.txt", "110 gerak  ·  34 jenis tari  ·  didigitalisasi menjadi animasi 3D"))], TMP / "intro.mp4")
card(clips[-1], 0, OUTRO, [(FONT, 64, 420, "white", txt("o1.txt", "Lestarikan gerak, wariskan budaya")), (FONT, 34, 515, GOLD, txt("o2.txt", "naramotion.web.app")),
     (FONTS, 21, 650, "white@0.75", txt("o3.txt", "Gerak didigitalisasi dengan SAM 3D Body dari video dataset Mendeley, YouTube & Drive tim")),
     (FONTS, 21, 685, "white@0.75", txt("o4.txt", "Penonton: Microsoft Rocketbox (MIT) · Langit & lantai: Poly Haven (CC0) · Musik: Bali Joged (domain publik)")),
     (FONTS, 21, 720, "white@0.6", txt("o5.txt", "Video untuk pemakaian internal - sebagian sumber berlisensi YouTube standar"))], TMP / "outro.mp4")
# 3) rangkai dengan dissolve
parts = [TMP / "intro.mp4", *clips, TMP / "outro.mp4"]; durs = [INTRO + X] + [SEG + X] * len(clips) + [OUTRO]
inp = sum((["-i", str(p)] for p in parts), []); fc = []; prev = "[0:v]"; acc = durs[0]
for k in range(1, len(parts)):
    o = f"[x{k}]"; fc.append(f"{prev}[{k}:v]xfade=transition=fade:duration={X}:offset={acc - X:.3f}{o}"); prev = o; acc += durs[k] - X
total = acc
music = ROOT / "assets/music/bali_joged.mp3"
fc.append(f"[{len(parts)}:a]atrim=0:{total:.2f},afade=in:st=0:d=1.5,afade=out:st={total - 2.5:.2f}:d=2.5,loudnorm=I=-16:TP=-1.5[a]")
final = OUT / "naramotion_kompilasi_gerak_1menit.mp4"
run(*inp, "-stream_loop", "-1", "-i", str(music), "-filter_complex", ";".join(fc), "-map", prev, "-map", "[a]", *ENC, "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", str(final))
print("durasi", round(total, 1), "dtk ->", final, final.stat().st_size // 2**20, "MB")
