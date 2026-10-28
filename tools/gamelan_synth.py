"""Musik latar showreel NaraMotion: komposisi gamelan orisinal hasil sintesis (laras slendro), bebas lisensi.

Instrumen disintesis dari parsial inharmonik: saron/demung (bilah), bonang (pencon), kenong, gong ageng (dengan ombak),
kendang (dhung/tak). Struktur ±72 s: buka → irama tenang → ngelik (tempo naik) → suwuk (melambat, gong akhir).
Pemakaian: python tools/gamelan_synth.py <out.wav> [durasi_s]
"""
import sys, wave
import numpy as np
from scipy.signal import fftconvolve

SR = 48000
OUT = sys.argv[1]; DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 72.0
rng = np.random.default_rng(7)
# laras slendro (perkiraan, Hz) — nada 1 2 3 5 6 dan oktaf atas 1'
SL = {1: 282.0, 2: 325.0, 3: 372.0, 5: 430.0, 6: 494.0, 7: 564.0}
mix = np.zeros((int(SR * (DUR + 6)), 2))

def env(n, a, d):
    t = np.arange(n) / SR; e = np.exp(-t / d); e[: int(a * SR)] *= np.linspace(0, 1, int(a * SR)); return e

def tone(f, dur, partials, decays, amps, beat=0.0, a=0.002):
    n = int(dur * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for r, d, A in zip(partials, decays, amps):
        y += A * np.sin(2 * np.pi * f * r * t + rng.uniform(0, 6.28)) * env(n, a, d)
        if beat: y += A * 0.8 * np.sin(2 * np.pi * (f * r + beat) * t) * env(n, a, d)   # ombak: dua bilah sedikit berbeda
    return y

def put(y, at, gain, pan=0.0):
    i = int(at * SR); y = y[: max(0, len(mix) - i)]
    mix[i:i + len(y), 0] += y * gain * (1 - pan) / 2 * 2 ** 0.5
    mix[i:i + len(y), 1] += y * gain * (1 + pan) / 2 * 2 ** 0.5

saron = lambda f: tone(f, 2.2, [1, 2.76, 5.40], [0.9, 0.35, 0.12], [1, 0.35, 0.12], beat=2.5)
demung = lambda f: tone(f / 2, 3.0, [1, 2.76, 5.40], [1.4, 0.5, 0.15], [1, 0.3, 0.1], beat=1.8)
bonang = lambda f: tone(f * 2, 1.2, [1, 1.52, 2.0, 2.98], [0.45, 0.2, 0.3, 0.1], [1, 0.25, 0.4, 0.1], beat=3.0)
kenong = lambda f: tone(f, 3.5, [1, 2.03, 3.1], [1.8, 0.7, 0.3], [1, 0.3, 0.12], beat=1.2, a=0.004)
gong = lambda: tone(66.0, 7.0, [1, 1.48, 2.2, 3.1], [4.0, 2.2, 1.0, 0.5], [1, 0.35, 0.2, 0.08], beat=0.6, a=0.02)

def dhung():
    n = int(0.6 * SR); t = np.arange(n) / SR; f = 70 + 60 * np.exp(-t / 0.05)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.18)
def tak():
    n = int(0.15 * SR); x = rng.normal(0, 1, n) * env(n, 0.001, 0.025)
    return np.convolve(x, np.hanning(25) / 10, "same") + 0.4 * np.sin(2 * np.pi * 900 * np.arange(n) / SR) * env(n, 0.001, 0.03)

# balungan (32 ketukan, 8 gatra) — melodi orisinal bergaya lancaran slendro
BAL = [2, 1, 2, 6, 2, 1, 2, 6, 3, 3, 5, 6, 7, 6, 5, 3, 5, 6, 5, 3, 2, 1, 2, 6, 3, 5, 6, 7, 6, 5, 3, 2]
NGELIK = [6, 7, 6, 5, 3, 5, 6, 7, 7, 6, 5, 3, 2, 3, 5, 6, 3, 2, 1, 2, 3, 5, 3, 2, 5, 6, 5, 3, 2, 1, 2, 6]

t = 0.0
# buka: gong + demung pelan
put(gong(), 0.0, 0.9)
for k, nada in enumerate([2, 1, 2, 6]): put(demung(SL[nada]), 1.6 + k * 1.1, 0.5, -0.2)
t = 6.4
def section(seq, beat, reps, bonang_on, kendang_level, end_slow=False):
    global t
    for r in range(reps):
        for i, nada in enumerate(seq):
            b = beat * (1 + (0.6 * (i / len(seq)) ** 2 if end_slow and r == reps - 1 else 0))
            put(saron(SL[nada]), t, 0.42, -0.25)
            if i % 2 == 1: put(demung(SL[nada]), t, 0.34, 0.15)
            if bonang_on:   # imbal sederhana: bonang memainkan nada berikut dua kali per ketukan
                nxt = seq[(i + 1) % len(seq)]
                put(bonang(SL[nxt]), t + b * 0.5, 0.12 * bonang_on, 0.45)
                put(bonang(SL[nada]), t + b * 0.25, 0.08 * bonang_on, -0.45)
            if i % 4 == 3: put(kenong(SL[nada]), t, 0.22, 0.05)
            if kendang_level:
                put(dhung(), t, 0.5 * kendang_level, 0.0)
                if i % 2 == 0: put(tak(), t + b * 0.5, 0.13 * kendang_level, 0.1)
                if i % 4 == 2: put(tak(), t + b * 0.75, 0.09 * kendang_level, 0.1)
            if (i + 1) % 16 == 0: put(gong(), t + b, 0.75)
            t += b

if DUR >= 100:   # versi panjang (video profil ±2 menit)
    section(BAL, 60 / 62, 1, 0.0, 0.0)             # irama sangat tenang tanpa bonang/kendang (intro sinematik)
    section(BAL, 60 / 66, 1, 0.6, 0.5)             # irama tenang
    section(NGELIK, 60 / 80, 1, 0.9, 0.8)          # ngelik
    section(BAL, 60 / 84, 1, 1.0, 1.0)             # irama ramai
else:
    section(BAL, 60 / 66, 1, 0.6, 0.5)             # irama tenang ±29 s
    section(NGELIK, 60 / 84, 1, 1.0, 1.0)          # ngelik, tempo naik ±23 s
section(BAL[24:], 60 / 72, 1, 0.8, 0.7, end_slow=True)   # suwuk melambat (8 ketukan)
put(gong(), t + 0.4, 1.0)

# gema ruang pendapa: IR eksponensial 1,6 s
n_ir = int(1.6 * SR); ir = rng.normal(0, 1, n_ir) * np.exp(-np.arange(n_ir) / SR / 0.45); ir /= np.abs(ir).sum() / 6
wet = np.stack([fftconvolve(mix[:, c], ir)[: len(mix)] for c in range(2)], 1)
y = 0.82 * mix + 0.35 * wet
y = y[: int(SR * DUR)]
fade = int(SR * 2.5); y[-fade:] *= np.linspace(1, 0, fade)[:, None]
y /= np.abs(y).max() / 0.89
with wave.open(OUT, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())
print(f"[nara] musik {OUT} {len(y)/SR:.1f} s, akhir frasa {t:.1f} s")
