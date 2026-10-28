"""Rich picture (gaya SSM/Checkland) ekosistem NaraMotion → media/naramotion_rich_picture.png (4200x2800).
Digambar sebagai SVG (efek goresan tangan lewat feTurbulence), dirender di Chromium.
Pemakaian: python tools/rich_picture.py
"""
import math, html
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "media/naramotion_rich_picture.png"
W, H = 4200, 2800
PAPER, INK, GOLD, RED, BLUE, PURP, GREY, SOFT = "#FBF6EA", "#2B2118", "#B9831F", "#B23A2A", "#2F6690", "#6A4C93", "#8C7E6A", "#F3E7CC"
HAND, NOTE = "'Patrick Hand', 'Comic Sans MS', cursive", "'Caveat', 'Comic Sans MS', cursive"
S = []                      # elemen bergaya goresan (difilter)
T = []                      # teks (tanpa filter agar tajam)

def wrap(s, n):
    out, cur = [], ""
    for w in s.split():
        if len(cur) + len(w) + 1 > n and cur: out.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    return out + [cur] if cur else out

def txt(x, y, s, size=30, font=HAND, anchor="middle", color=INK, weight=400, n=None, italic=False, lh=1.12):
    lines = wrap(s, n) if n else s.split("\n")
    y0 = y - (len(lines) - 1) * size * lh / 2
    sp = "".join(f'<tspan x="{x}" y="{y0 + i * size * lh:.1f}">{html.escape(l)}</tspan>' for i, l in enumerate(lines))
    T.append(f'<text font-family="{font}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}" '
             f'{"font-style=\"italic\"" if italic else ""} dominant-baseline="middle">{sp}</text>')
    return len(lines) * size * lh

def line(x1, y1, x2, y2, c=INK, w=4, dash=None):
    S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="{w}" stroke-linecap="round" {f"stroke-dasharray=\"{dash}\"" if dash else ""}/>')

def person(x, y, h=170, pose="stand", c=INK, w=5, fill=None):
    r = h * 0.11; hy = y - h + r; neck = hy + r; hip = y - h * 0.45; sh = neck + h * 0.08
    S.append(f'<circle cx="{x}" cy="{hy}" r="{r}" fill="{fill or PAPER}" stroke="{c}" stroke-width="{w}"/>')
    line(x, neck, x, hip, c, w)
    if pose == "dance":        # agem: lengan atas mendatar, lengan bawah tegak; mendhak
        for s in (-1, 1):
            ex = x + s * h * 0.3; line(x, sh, ex, sh, c, w); line(ex, sh, ex + s * h * 0.03, sh - h * 0.24, c, w)
            line(ex + s * h * 0.03, sh - h * 0.24, ex + s * h * 0.1, sh - h * 0.28, c, w)
            kx = x + s * h * 0.22; ky = hip + h * 0.22; line(x, hip, kx, ky, c, w); line(kx, ky, x + s * h * 0.17, y, c, w)
    elif pose == "point":
        line(x, sh, x - h * 0.22, hip, c, w); line(x, sh, x + h * 0.32, sh - h * 0.12, c, w)
        for s in (-1, 1): line(x, hip, x + s * h * 0.15, y, c, w)
    elif pose == "up":
        for s in (-1, 1): line(x, sh, x + s * h * 0.25, sh - h * 0.22, c, w); line(x, hip, x + s * h * 0.15, y, c, w)
    else:
        for s in (-1, 1): line(x, sh, x + s * h * 0.2, hip + h * 0.05, c, w); line(x, hip, x + s * h * 0.14, y, c, w)
    return hy - r

def cloud(cx, cy, w, h, text, size=30, n=None, tail=None, c=INK, bg="#FFFDF7"):
    pts = []; k = 14
    for i in range(k):
        a = 2 * math.pi * i / k; pts.append((cx + w / 2 * math.cos(a), cy + h / 2 * math.sin(a)))
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(k):
        p, q = pts[i], pts[(i + 1) % k]; ch = math.dist(p, q); d += f"A{ch * .62:.1f},{ch * .62:.1f} 0 0 1 {q[0]:.1f},{q[1]:.1f} "
    S.append(f'<path d="{d}Z" fill="{bg}" stroke="{c}" stroke-width="3.5"/>')
    if tail:
        tx, ty = tail; ex, ey = cx + (tx - cx) * 0.42, cy + (ty - cy) * 0.42
        for f, r in ((0.15, 14), (0.42, 10), (0.66, 7)):
            bx = ex + (tx - ex) * f * 1.2; by = ey + (ty - ey) * f * 1.2
            S.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{r}" fill="{bg}" stroke="{c}" stroke-width="3"/>')
    txt(cx, cy, text, size, NOTE, n=n or int(w / size * 1.55), color=c)

def speech(cx, cy, w, h, text, tail, size=30, c=INK, bg="#FFFDF7", n=None):
    x, y = cx - w / 2, cy - h / 2; tx, ty = tail
    bx = min(max(tx, x + 40), x + w - 40); by = y + h if ty > cy else y
    S.append(f'<path d="M{bx - 22},{by} L{tx},{ty} L{bx + 22},{by}" fill="{bg}" stroke="{c}" stroke-width="3.5" stroke-linejoin="round"/>')
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" fill="{bg}" stroke="{c}" stroke-width="3.5"/>')
    S.append(f'<line x1="{bx - 19}" y1="{by}" x2="{bx + 19}" y2="{by}" stroke="{bg}" stroke-width="6"/>')
    txt(cx, cy, text, size, NOTE, n=n or int(w / size * 1.6), color=c)

def swords(x, y, label, s=70, n=22):
    for d in (1, -1):
        x1, y1, x2, y2 = x - s * d, y - s, x + s * d, y + s
        line(x1, y1, x2, y2, RED, 7)
        gx, gy = x1 + (x2 - x1) * 0.78, y1 + (y2 - y1) * 0.78
        line(gx - 20 * d, gy + 20, gx + 20 * d, gy - 20, RED, 7); line(gx + (x2 - gx) * 0, gy, x2, y2, RED, 11)
    txt(x, y + s + 44, label, 28, HAND, color=RED, weight=700, n=n)

def arrow(x1, y1, x2, y2, label=None, c=BLUE, w=5, dash=None, bend=0.0, size=27, n=26, lpos=0.5, both=False):
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2; dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy) or 1
    cx, cy = mx - dy / L * bend * L, my + dx / L * bend * L
    mk = {BLUE: "ab", GOLD: "ag", PURP: "ap", RED: "ar", INK: "ak", GREY: "agr"}[c]
    S.append(f'<path d="M{x1},{y1} Q{cx:.1f},{cy:.1f} {x2},{y2}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round" '
             f'{f"stroke-dasharray=\"{dash}\"" if dash else ""} marker-end="url(#{mk})" {f"marker-start=\"url(#{mk}s)\"" if both else ""}/>')
    if label:
        t = lpos; lx = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t * t * x2; ly = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t * t * y2
        lines = wrap(label, n); bw = max(len(l) for l in lines) * size * 0.47 + 26; bh = len(lines) * size * 1.12 + 14
        T.append(f'<rect x="{lx - bw / 2:.1f}" y="{ly - bh / 2:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="10" fill="{PAPER}" fill-opacity="0.93" stroke="{c}" stroke-width="1.5" stroke-opacity="0.5"/>')
        txt(lx, ly, label, size, HAND, color=c, n=n)

def card(x, y, w, h, title, body, c=INK, bg="#FFFDF7", tsize=31, bsize=26, n=None, tag=None, tagc=GOLD):
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{bg}" stroke="{c}" stroke-width="3.5"/>')
    S.append(f'<path d="M{x + w - 34},{y} L{x + w},{y + 34}" stroke="{c}" stroke-width="3"/>')
    txt(x + 22, y + 34, title, tsize, HAND, "start", c, 700)
    txt(x + 22, y + 52 + (len(wrap(body, n or int(w / bsize * 1.75))) * bsize * 1.12) / 2, body, bsize, HAND, "start", GREY if c == INK else c, n=n or int(w / bsize * 1.75))
    if tag: T.append(f'<rect x="{x + 18}" y="{y + h - 46}" width="{len(tag) * 13 + 24}" height="34" rx="17" fill="{tagc}"/>'); txt(x + 30 + len(tag) * 6.5, y + h - 29, tag, 22, HAND, color="#FFFDF7", weight=700)

def zone(x, y, w, h, label, c=GREY):
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="60" fill="none" stroke="{c}" stroke-width="3" stroke-dasharray="4 14" stroke-linecap="round"/>')
    T.append(f'<rect x="{x + 50}" y="{y - 24}" width="{len(label) * 17 + 40}" height="48" rx="24" fill="{PAPER}"/>')
    txt(x + 70, y, label.upper(), 30, HAND, "start", c, 700)

# ---------- ikon ----------
def gate(x, y, s=1.0, c=INK):            # candi bentar: dua menara bertingkat yang terbelah
    for d in (-1, 1):
        pts = []; bx = x + d * 30 * s
        steps = [(0, 0), (90, 0), (90, -60), (80, -60), (80, -120), (68, -120), (68, -175), (55, -175), (55, -225), (40, -225), (40, -265), (25, -265), (0, -300)]
        for px, py in steps: pts.append((bx + d * px * s, y + py * s))
        pts.append((bx, y)); S.append('<path d="M' + " L".join(f"{a:.1f},{b:.1f}" for a, b in pts) + f'Z" fill="{SOFT}" stroke="{c}" stroke-width="4"/>')
        for k in range(1, 5): line(bx + d * 8 * s, y - k * 58 * s, bx + d * (88 - k * 12) * s, y - k * 58 * s, c, 2)
    line(x - 170 * s, y, x + 170 * s, y, c, 4)

def gamelan(x, y, c=INK):
    S.append(f'<rect x="{x - 170}" y="{y}" width="340" height="40" rx="8" fill="#E6CFA0" stroke="{c}" stroke-width="4"/>')
    for i in range(6):
        px = x - 140 + i * 56
        S.append(f'<ellipse cx="{px}" cy="{y - 6}" rx="24" ry="13" fill="{GOLD}" stroke="{c}" stroke-width="3"/><circle cx="{px}" cy="{y - 16}" r="7" fill="{GOLD}" stroke="{c}" stroke-width="3"/>')
    line(x - 160, y + 40, x - 175, y + 80, c, 4); line(x + 160, y + 40, x + 175, y + 80, c, 4)
    line(x + 120, y - 60, x + 150, y - 26, c, 4); S.append(f'<circle cx="{x + 116}" cy="{y - 64}" r="9" fill="{c}"/>')

def screen(x, y, w, h, kind, c=INK):
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#241B12" stroke="{c}" stroke-width="4"/>')
    line(x + w / 2 - 30, y + h + 18, x + w / 2 + 30, y + h + 18, c, 5); line(x + w / 2, y + h, x + w / 2, y + h + 18, c, 5)
    if kind == "studio":
        person(x + w * 0.3, y + h - 18, h * 0.7, "dance", GOLD, 3, "#241B12")
        for k in range(3):
            pts = " ".join(f"{x + w * 0.55 + i * 9},{y + 30 + k * 34 + 12 * math.sin(i * 0.8 + k)}" for i in range(11)); S.append(f'<polyline points="{pts}" fill="none" stroke="{["#E6B85C", "#7FB3D5", "#E07A5F"][k]}" stroke-width="3"/>')
    elif kind == "kelas":
        person(x + w * 0.35, y + h - 18, h * 0.72, "dance", "#E6B85C", 3, "#241B12")
        S.append(f'<circle cx="{x + w * 0.75}" cy="{y + h * 0.45}" r="{h * 0.25}" fill="none" stroke="#E6B85C" stroke-width="5"/>')
        T.append(f'<text x="{x + w * 0.75}" y="{y + h * 0.47}" font-family="{HAND}" font-size="34" fill="#E6B85C" text-anchor="middle" dominant-baseline="middle" font-weight="700">87</text>')
        S.append(f'<circle cx="{x + w * 0.35 + h * 0.2}" cy="{y + h * 0.33}" r="10" fill="none" stroke="#E07A5F" stroke-width="4"/>')
    else:
        for i in range(3):
            S.append(f'<rect x="{x + 16 + i * (w - 24) / 3}" y="{y + 18}" width="{(w - 24) / 3 - 10}" height="{h - 36}" rx="6" fill="#3A2C1A" stroke="#E6B85C" stroke-width="2"/>')
            person(x + 16 + i * (w - 24) / 3 + ((w - 24) / 3 - 10) / 2, y + h - 30, h * 0.5, ["dance", "up", "dance"][i], "#E6B85C", 2.5, "#3A2C1A")

def cloudshape(cx, cy, w, h, fill, c=INK):
    S.append(f'<path d="M{cx - w * .42},{cy + h * .35} A{h * .3},{h * .3} 0 0 1 {cx - w * .38},{cy - h * .05} A{h * .36},{h * .36} 0 0 1 {cx - w * .05},{cy - h * .38} '
             f'A{h * .42},{h * .42} 0 0 1 {cx + w * .32},{cy - h * .12} A{h * .3},{h * .3} 0 0 1 {cx + w * .42},{cy + h * .35} Z" fill="{fill}" stroke="{c}" stroke-width="4.5"/>')

def chip(x, y, s=60, c=INK):
    S.append(f'<rect x="{x - s}" y="{y - s * .6}" width="{2 * s}" height="{1.2 * s}" rx="8" fill="#5B8E5B" stroke="{c}" stroke-width="3.5"/>')
    S.append(f'<rect x="{x - s * .35}" y="{y - s * .3}" width="{s * .7}" height="{s * .6}" rx="4" fill="#2B2118"/>')
    for i in range(5): line(x - s * .8 + i * s * .4, y + s * .6, x - s * .8 + i * s * .4, y + s * .78, c, 3)

def flame(x, y, s=1.0):
    S.append(f'<path d="M{x},{y} C{x - 70 * s},{y - 20 * s} {x - 60 * s},{y - 90 * s} {x - 20 * s},{y - 140 * s} C{x - 15 * s},{y - 90 * s} {x + 10 * s},{y - 80 * s} {x + 15 * s},{y - 110 * s} '
             f'C{x + 50 * s},{y - 80 * s} {x + 70 * s},{y - 20 * s} {x},{y} Z" fill="#F2A541" stroke="{INK}" stroke-width="4"/>')
    S.append(f'<path d="M{x},{y - 6 * s} C{x - 30 * s},{y - 20 * s} {x - 20 * s},{y - 55 * s} {x},{y - 75 * s} C{x + 25 * s},{y - 50 * s} {x + 30 * s},{y - 20 * s} {x},{y - 6 * s}Z" fill="#F6D06F"/>')

def laptop(x, y, c=INK):
    S.append(f'<rect x="{x - 90}" y="{y - 120}" width="180" height="115" rx="8" fill="#2B2118" stroke="{c}" stroke-width="4"/>')
    S.append(f'<path d="M{x - 120},{y + 12} L{x + 120},{y + 12} L{x + 95},{y - 5} L{x - 95},{y - 5}Z" fill="#D8C7A6" stroke="{c}" stroke-width="4"/>')
    person(x, y - 18, 85, "dance", "#E6B85C", 3, "#2B2118")

def phone(x, y, c=INK):
    S.append(f'<rect x="{x - 38}" y="{y - 140}" width="76" height="140" rx="12" fill="#2B2118" stroke="{c}" stroke-width="4"/>')
    person(x, y - 22, 80, "dance", "#E6B85C", 3, "#2B2118")

def building(x, y, s=1.0, c=INK, label=None):
    S.append(f'<path d="M{x - 130 * s},{y - 150 * s} L{x},{y - 215 * s} L{x + 130 * s},{y - 150 * s} Z" fill="{SOFT}" stroke="{c}" stroke-width="4"/>')
    S.append(f'<rect x="{x - 120 * s}" y="{y - 150 * s}" width="{240 * s}" height="{150 * s}" fill="#FFFDF7" stroke="{c}" stroke-width="4"/>')
    for i in range(5): S.append(f'<rect x="{x - 100 * s + i * 45 * s}" y="{y - 135 * s}" width="{18 * s}" height="{125 * s}" fill="{SOFT}" stroke="{c}" stroke-width="2.5"/>')
    if label: txt(x, y - 172 * s, label, 22, HAND, color=c, weight=700)

def school(x, y, c=INK):
    S.append(f'<rect x="{x - 140}" y="{y - 130}" width="280" height="130" fill="#FFFDF7" stroke="{c}" stroke-width="4"/>')
    S.append(f'<path d="M{x - 160},{y - 130} L{x},{y - 200} L{x + 160},{y - 130}Z" fill="#C9734A" stroke="{c}" stroke-width="4"/>')
    for i in range(4): S.append(f'<rect x="{x - 115 + i * 62}" y="{y - 105}" width="40" height="38" fill="#BFD7EA" stroke="{c}" stroke-width="2.5"/>')
    S.append(f'<rect x="{x - 22}" y="{y - 55}" width="44" height="55" fill="{SOFT}" stroke="{c}" stroke-width="2.5"/>')
    line(x, y - 200, x, y - 260, c, 3); S.append(f'<path d="M{x},{y - 260} L{x + 46},{y - 248} L{x},{y - 236}Z" fill="{RED}"/><path d="M{x},{y - 248} L{x + 46},{y - 248} L{x},{y - 236}Z" fill="#FFFDF7"/>')

def moneybag(x, y, c=INK):
    S.append(f'<path d="M{x - 30},{y - 120} C{x - 120},{y - 60} {x - 100},{y} {x},{y} C{x + 100},{y} {x + 120},{y - 60} {x + 30},{y - 120} Z" fill="#D9B45A" stroke="{c}" stroke-width="4"/>')
    S.append(f'<path d="M{x - 30},{y - 120} L{x - 45},{y - 150} L{x + 45},{y - 150} L{x + 30},{y - 120}" fill="#D9B45A" stroke="{c}" stroke-width="4"/>')
    T.append(f'<text x="{x}" y="{y - 48}" font-family="{HAND}" font-size="58" fill="{c}" text-anchor="middle" dominant-baseline="middle" font-weight="700">Rp</text>')

def eye(x, y, c=INK, s=1.0):
    S.append(f'<path d="M{x - 80 * s},{y} Q{x},{y - 70 * s} {x + 80 * s},{y} Q{x},{y + 70 * s} {x - 80 * s},{y}Z" fill="#FFFDF7" stroke="{c}" stroke-width="4"/>')
    S.append(f'<circle cx="{x}" cy="{y}" r="{26 * s}" fill="{BLUE}" stroke="{c}" stroke-width="3"/><circle cx="{x}" cy="{y}" r="{11 * s}" fill="{c}"/>')

def globe(x, y, r=70, c=INK):
    S.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#BFD7EA" stroke="{c}" stroke-width="4"/>')
    S.append(f'<ellipse cx="{x}" cy="{y}" rx="{r * .45}" ry="{r}" fill="none" stroke="{c}" stroke-width="2.5"/>')
    line(x - r, y, x + r, y, c, 2.5); line(x - r * .88, y - r * .45, x + r * .88, y - r * .45, c, 2); line(x - r * .88, y + r * .45, x + r * .88, y + r * .45, c, 2)

def magnifier(x, y, c=INK):
    S.append(f'<circle cx="{x}" cy="{y}" r="34" fill="#E3EEF6" stroke="{c}" stroke-width="5"/>'); line(x + 24, y + 24, x + 64, y + 64, c, 9)

def crack(x, y, c=RED):
    S.append(f'<polyline points="{x - 40},{y - 30} {x - 12},{y - 6} {x - 28},{y + 6} {x + 4},{y + 30} {x - 6},{y + 12} {x + 30},{y + 26}" fill="none" stroke="{c}" stroke-width="5" stroke-linejoin="round"/>')

def warn(x, y, s=1.0):
    S.append(f'<path d="M{x},{y - 34 * s} L{x + 38 * s},{y + 30 * s} L{x - 38 * s},{y + 30 * s}Z" fill="#F6D06F" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>')
    T.append(f'<text x="{x}" y="{y + 8 * s}" font-family="{HAND}" font-size="{44 * s}" fill="{INK}" text-anchor="middle" dominant-baseline="middle" font-weight="700">!</text>')

def suit(x, y, h=480):
    top = person(x, y, h, "dance", INK, 7)
    r = h * 0.11; neck = y - h + 2 * r; sh = neck + h * 0.08; hip = y - h * 0.45
    nodes = [(x, y - h + r), (x, (neck + hip) / 2)]
    for s in (-1, 1):
        nodes += [(x + s * h * 0.17, sh), (x + s * h * 0.315, sh - h * 0.14), (x + s * h * 0.11, hip + h * 0.11), (x + s * h * 0.2, hip + h * 0.33)]
    for i, (a, b) in enumerate(nodes):
        S.append(f'<rect x="{a - 15}" y="{b - 15}" width="30" height="30" rx="6" fill="{GOLD}" stroke="{INK}" stroke-width="3"/>')
    for a, b in nodes[:4]:
        S.append(f'<path d="M{a + 18},{b - 24} q10,-12 20,0 M{a + 14},{b - 34} q14,-18 28,0" fill="none" stroke="{BLUE}" stroke-width="3"/>')

# ============== KOMPOSISI ==============
zone(40, 250, 1150, 2120, "Living tradition")
zone(1230, 250, 2000, 700, "Open knowledge sources")
zone(3270, 250, 890, 1720, "Compute & infrastructure")
zone(1230, 2010, 2930, 740, "Society & institutions")

# judul + legenda
txt(80, 95, "Rich picture — NaraMotion: keeping Indonesian dance alive as motion data", 64, HAND, "start", INK, 700)
txt(80, 168, "Who is involved, what they worry about, what flows between them, and where the tensions are  ·  SMANSA × ABBS · 2026", 34, NOTE, "start", GREY)
lx, ly = 3330, 40
S.append(f'<rect x="{lx}" y="{ly}" width="830" height="190" rx="18" fill="#FFFDF7" stroke="{GREY}" stroke-width="2"/>')
txt(lx + 24, ly + 30, "LEGEND", 26, HAND, "start", GREY, 700)
person(lx + 50, ly + 170, 90); txt(lx + 90, ly + 135, "stakeholder", 25, HAND, "start")
S.append(f'<circle cx="{lx + 280}" cy="{ly + 120}" r="22" fill="#FFFDF7" stroke="{INK}" stroke-width="3"/>'); txt(lx + 312, ly + 120, "worry / thought", 25, HAND, "start")
line(lx + 250, ly + 165, lx + 300, ly + 165, BLUE, 5); txt(lx + 312, ly + 165, "data flow", 25, HAND, "start", BLUE)
line(lx + 500, ly + 75, lx + 550, ly + 75, GOLD, 5); txt(lx + 562, ly + 75, "knowledge / feedback", 25, HAND, "start", GOLD)
line(lx + 500, ly + 120, lx + 550, ly + 120, PURP, 5, "10 9"); txt(lx + 562, ly + 120, "licence / influence", 25, HAND, "start", PURP)
line(lx + 505, ly + 152, lx + 545, ly + 178, RED, 6); line(lx + 545, ly + 152, lx + 505, ly + 178, RED, 6); txt(lx + 562, ly + 165, "conflict / tension", 25, HAND, "start", RED)

# --- tradisi hidup (kiri) ---
gate(260, 590, 0.95); txt(260, 630, "pura & sanggar", 28, HAND)
gamelan(820, 560); txt(820, 670, "gamelan accompaniment", 28, HAND)
person(330, 1120, 210, "dance", INK, 6, "#F6E3B4"); txt(330, 1160, "Maestro (Bali / Jawa)", 32, HAND, weight=700)
cloud(310, 765, 420, 190, "“A number can’t hold taksu… but my movements must not vanish with me.”", 30, tail=(330, 860))
person(780, 1380, 180, "point", INK, 6); txt(780, 1415, "Sanggar teacher", 32, HAND, weight=700)
speech(790, 1120, 470, 140, "“Thirty students, one of me — I can’t correct every wrist.”", (790, 1185), 30)
for i, (sx, sy) in enumerate(((330, 1840), (470, 1870), (610, 1840))): person(sx, sy, 140, ["dance", "stand", "dance"][i], INK, 5)
txt(470, 1905, "Young learners (school & sanggar)", 32, HAND, weight=700)
cloud(330, 1590, 420, 170, "“Practising alone at home — which joint is wrong?”", 30, tail=(380, 1690))
speech(880, 1700, 340, 130, "“Will it run on my old phone?”", (650, 1760), 30)
arrow(410, 1170, 690, 1290, "body-to-body transmission", GOLD, 9, bend=-0.15)
arrow(720, 1420, 560, 1700, "imitation & correction", GOLD, 7, bend=-0.2, n=16)
crack(140, 1250); txt(150, 1420, "video archives keep only the surface: angles, timing, fingers lost", 27, NOTE, color=RED, n=18)
txt(615, 2130, "Fewer young dancers · teachers stretched thin · knowledge lives in bodies", 30, NOTE, color=GREY, n=34)

# --- sumber pengetahuan terbuka (atas) ---
card(1270, 300, 380, 190, "Woman Basic Balinese", "1,740 videos · 13 moves · 9 dancers · 3 cams", tag="CC BY 4.0")
card(1670, 300, 380, 190, "Male Basic Balinese", "828 videos · 11 moves · 4 dancers", tag="CC BY 4.0")
card(1270, 510, 380, 170, "AIST++", "411 sequences · 10 genres → synthetic IMU", tag="CC BY 4.0")
card(1670, 510, 380, 170, "Turkish folk-dance IMU", "30 sessions · 5 real nodes", tag="CC BY 4.0")
card(1270, 700, 380, 170, "Javanese VICON", "6 characters · 100 Hz markers", tag="NO LICENCE", tagc=RED)
warn(1690, 790, 0.9); txt(1880, 790, "internal analysis only — never redistributed", 27, NOTE, color=RED, n=20)
person(2170, 860, 130, "point"); txt(2170, 895, "Dataset authors", 27, HAND, weight=700)
speech(2170, 650, 230, 110, "“Just credit us.”", (2170, 720), 30)
card(2330, 300, 420, 175, "Pose & 3D models", "RTMW (rtmlib) · MediaPipe · SAM 3D Body (Meta) · Motion2MixamoRig", c=PURP, n=30)
card(2330, 495, 420, 150, "Body models", "SMPL-X & MANO: non-commercial, kept in a private dataset", c=PURP, n=30)
cloud(2560, 790, 470, 170, "Gated weights, HF token, SAM licence… read every term!", 28, c=PURP, tail=(2540, 650))
txt(2950, 330, "", 20)
swords(2990, 380, "non-commercial terms vs long-term funding", 40, 26)

# --- komputasi (kanan) ---
cloudshape(3700, 520, 460, 230, "#E3EEF6"); chip(3700, 545, 55); txt(3700, 650, "Kaggle · Tesla T4", 34, HAND, weight=700)
txt(3700, 715, "free ≈30 GPU-h/week · max 2 batch sessions", 27, HAND, color=GREY, n=26)
speech(3700, 870, 520, 150, "“Session limit reached… queue the next shard.”", (3700, 760), 29)
txt(3700, 1010, "468,889 frames → 133 keypoints · TCN training · SAM 3D for 2,568 clips (3 shards)", 26, NOTE, color=BLUE, n=34)
flame(3700, 1350, 1.0); txt(3700, 1395, "Firebase: Hosting · Auth · Realtime DB", 30, HAND, weight=700, n=22)
laptop(3600, 1680); phone(3820, 1680); txt(3700, 1735, "Learners’ browsers (WebAssembly, no install)", 30, HAND, weight=700, n=26)
swords(3700, 1860, "heavy AI vs low-end devices", 36, 30)

# --- platform (tengah) ---
S.append(f'<rect x="1640" y="1060" width="960" height="640" rx="40" fill="#FFF8E8" stroke="{GOLD}" stroke-width="7"/>')
txt(2120, 1110, "NaraMotion · naramotion.web.app", 44, HAND, color="#7A4E10", weight=700)
txt(2120, 1160, "static web platform · non-commercial · cultural preservation", 27, NOTE, color=GREY)
screen(1690, 1210, 260, 170, "studio"); screen(1990, 1210, 260, 170, "kelas"); screen(2290, 1210, 260, 170, "arsip")
for x0, t, d in ((1820, "Studio", "3D replay · 10 sensor streams"), (2120, "Kelas Tari", "camera AI · score · joints"), (2420, "Arsip", "24 moves · 3D characters")):
    txt(x0, 1435, t, 32, HAND, weight=700); txt(x0, 1475, d, 25, HAND, color=GREY, n=18)
S.append(f'<rect x="1700" y="1550" width="840" height="110" rx="18" fill="#241B12"/>')
txt(2120, 1605, "MediaPipe 17 pts → TCN (ONNX, 3.65 / 10.93 MB) → DTW vs 6 exemplars → 0–100", 27, HAND, color="#F3D9A0", n=46)
suit(1400, 1650, 470); txt(1400, 1700, "10-node GY-85 9-DoF suit", 30, HAND, weight=700); txt(1400, 1740, "ESP32-C3 · Madgwick 100 Hz", 26, HAND, color=GREY)
cloud(1430, 1000, 330, 150, "Designed & simulated — not yet built", 28, tail=(1420, 1150), c=RED)
arrow(1490, 1360, 1680, 1330, "quaternions · 26 kB/s", BLUE, 6, bend=0.12, n=12)

# feedback loop di bawah platform
cx0, cy0, rr = 2120, 1860, 105
for a0 in (0, 90, 180, 270):
    a1, a2 = math.radians(a0 + 12), math.radians(a0 + 78)
    S.append(f'<path d="M{cx0 + rr * math.cos(a1):.1f},{cy0 + rr * math.sin(a1):.1f} A{rr},{rr} 0 0 1 {cx0 + rr * math.cos(a2):.1f},{cy0 + rr * math.sin(a2):.1f}" fill="none" stroke="{GOLD}" stroke-width="7" marker-end="url(#ag)"/>')
for a0, t in ((315, "practise"), (45, "record"), (135, "score"), (225, "correct")):
    a = math.radians(a0); txt(cx0 + (rr + 60) * math.cos(a) * 1.25, cy0 + (rr + 40) * math.sin(a), t, 28, HAND, color="#7A4E10", weight=700)
txt(cx0, cy0, "learning loop", 26, NOTE, color=GREY, n=8)
swords(2420, 1860, "2D score depends on camera angle → 3D next", 45, 18)
swords(1150, 990, "authenticity vs quantification", 45, 14)

# --- aliran utama ---
arrow(2060, 300, 3480, 470, "2,568 Balinese videos → GPU pose extraction", BLUE, 6, bend=-0.1, lpos=0.8, n=24)
arrow(2750, 560, 3470, 560, "pretrained weights", PURP, 5, "12 10", n=20, lpos=0.78)
arrow(3480, 650, 2600, 1120, "ONNX models · exemplars · 3D motion (.glb)", BLUE, 7, bend=0.08, n=22)
arrow(3600, 1300, 2600, 1300, "hosting · auth · live sensor DB", BLUE, 6, both=True, n=18, lpos=0.55)
arrow(2600, 1500, 3490, 1640, "runs on-device", BLUE, 6, bend=-0.1, n=16)
arrow(700, 1820, 1700, 1700, "camera / video (stays on the device)", BLUE, 6, bend=0.1, lpos=0.3, n=20)
arrow(1760, 1700, 760, 1930, "score 0–100 + joints to fix", GOLD, 6, bend=-0.1, lpos=0.35, n=18)
arrow(1650, 900, 1700, 1060, None, BLUE, 4, "8 8")

# --- masyarakat & institusi (bawah) ---
for i in range(6): person(1420 + i * 70, 2330, 120, ["up", "stand"][i % 2], INK, 4.5, ["#F6E3B4", "#D7E6F2"][i // 3])
txt(1595, 2370, "Team: SMANSA × ABBS", 32, HAND, weight=700); txt(1595, 2410, "students building NaraMotion", 26, HAND, color=GREY)
cloud(1600, 2610, 520, 170, "“Be honest: suit not validated yet; credit every source.”", 28, tail=(1590, 2420))
arrow(1590, 2180, 1960, 1960, "build · train · document", GOLD, 6, bend=-0.15, n=14)
arrow(1450, 2190, 1410, 1790, "assemble 10 nodes (next)", INK, 4, "10 10", n=14, lpos=0.75)
school(2180, 2400); txt(2180, 2440, "Schools & sanggar classes", 30, HAND, weight=700, n=26)
speech(2200, 2620, 400, 110, "“Pilot it with real classes.”", (2200, 2470), 29)
building(2700, 2400, 1.0); txt(2700, 2440, "Cultural agencies & museums", 30, HAND, weight=700, n=24)
cloud(2700, 2630, 420, 150, "Who owns a digitised movement?", 28, tail=(2700, 2470))
arrow(2700, 2190, 2560, 1710, "permissions · partnerships", PURP, 5, "12 10", n=14)
person(3130, 2370, 140, "point"); magnifier(3230, 2250); txt(3150, 2410, "Researchers", 30, HAND, weight=700)
cloud(3130, 2610, 380, 150, "No open IMU data for Indonesian dance yet", 27, tail=(3130, 2450))
arrow(2560, 1690, 3080, 2200, "future open inertial dataset", PURP, 5, "12 10", bend=-0.1, n=16, lpos=0.6)
eye(3520, 2300, INK, 0.9); txt(3520, 2380, "I2ASPO judges", 30, HAND, weight=700)
speech(3520, 2560, 300, 120, "“Real impact, or a demo?”", (3520, 2420), 28)
moneybag(3940, 2440); txt(3940, 2480, "Tourism & shows", 30, HAND, weight=700)
speech(3940, 2640, 330, 110, "“Could we sell this?”", (3940, 2520), 28)
swords(3720, 2190, "commodification vs preservation", 40, 18)
globe(1060, 2560, 75); txt(1060, 2665, "Public & diaspora", 30, HAND, weight=700)
arrow(1660, 1700, 1140, 2500, "open Arsip, credited", GOLD, 5, bend=0.12, n=12, lpos=0.75)
arrow(3440, 2280, 1720, 2300, None, GREY, 3, "6 10", bend=0.04)
txt(2460, 2250, "paper · deck · profile video", 26, NOTE, color=GREY, n=12)

# lingkungan luar
T.append(f'<rect x="12" y="2768" width="{W - 24}" height="24" fill="{PAPER}"/>')
txt(W / 2, 2775, "WIDER ENVIRONMENT: globalisation & changing tastes · digital divide · free-tier compute limits · gated AI models & non-commercial licences · community ownership of heritage", 25, HAND, color=GREY, weight=700)

defs = "".join(f'<marker id="{k}" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M1,1 L11,6 L1,11 Z" fill="{c}"/></marker>'
               f'<marker id="{k}s" viewBox="0 0 12 12" refX="9" refY="6" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M1,1 L11,6 L1,11 Z" fill="{c}"/></marker>'
               for k, c in (("ab", BLUE), ("ag", GOLD), ("ap", PURP), ("ar", RED), ("ak", INK), ("agr", GREY)))
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs>{defs}'
       '<filter id="rough" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.022" numOctaves="2" seed="7"/>'
       '<feDisplacementMap in="SourceGraphic" scale="5"/></filter>'
       '<pattern id="grain" width="6" height="6" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.8" fill="#E9DFC9"/></pattern></defs>'
       f'<rect width="{W}" height="{H}" fill="{PAPER}"/><rect width="{W}" height="{H}" fill="url(#grain)" opacity="0.6"/>'
       f'<g filter="url(#rough)">{"".join(S)}</g>{"".join(T)}</svg>')
page = ("<!doctype html><html><head><meta charset=utf-8><link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Patrick+Hand&display=swap'>"
        f"<style>*{{margin:0}}body{{width:{W}px;height:{H}px}}</style></head><body>{svg}</body></html>")
tmp = OUT.with_suffix(".html"); tmp.write_text(page, "utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H}); pg.goto(tmp.as_uri()); pg.wait_for_load_state("networkidle")
    pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500); pg.screenshot(path=str(OUT)); b.close()
tmp.unlink(); print(OUT)
