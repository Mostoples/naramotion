#!/usr/bin/env bash
# Video pembuka halaman depan (tanpa teks): penari emas Gambyong (B1) → gamelan (B3) → Borobudur & pendapa (intro).
# Bahan: render sub-frame 60 fps di assets_src/profile60. Hasil: assets/hero/hero_{16x9,9x16}.{mp4,jpg}
set -e
cd "$(dirname "$0")/.."
P=assets_src/profile60; M=$(mktemp -d)/hero_master.mp4
ffmpeg -loglevel error -y -framerate 60 -i $P/broll_B1/%04d.png -framerate 60 -i $P/broll_B3/%04d.png -framerate 60 -start_number 200 -i $P/intro/%04d.png \
  -filter_complex "[0]trim=end=7,setpts=PTS-STARTPTS,fps=30,format=yuv420p[a];[1]trim=end=6,setpts=PTS-STARTPTS,fps=30,format=yuv420p[b];[2]trim=end=11,setpts=PTS-STARTPTS,fps=30,format=yuv420p[c];[a][b]xfade=transition=fade:duration=1:offset=6[ab];[ab][c]xfade=transition=fade:duration=1:offset=11,fade=t=in:st=0:d=0.8,fade=t=out:st=21.2:d=0.8[v]" \
  -map "[v]" -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p "$M"
mkdir -p assets/hero
ffmpeg -loglevel error -y -i "$M" -vf scale=1280:720 -c:v libx264 -preset slow -crf 28 -pix_fmt yuv420p -movflags +faststart -an assets/hero/hero_16x9.mp4
ffmpeg -loglevel error -y -i "$M" -vf "crop=608:1080:656:0,scale=720:1280" -c:v libx264 -preset slow -crf 28 -pix_fmt yuv420p -movflags +faststart -an assets/hero/hero_9x16.mp4
ffmpeg -loglevel error -y -ss 3 -i assets/hero/hero_16x9.mp4 -frames:v 1 -q:v 5 assets/hero/hero_16x9.jpg
ffmpeg -loglevel error -y -ss 3 -i assets/hero/hero_9x16.mp4 -frames:v 1 -q:v 5 assets/hero/hero_9x16.jpg
