"""Motif batik prosedural (digambar ulang, bukan disalin) untuk dekorasi NaraMotion.

Keluaran: assets/batik/{parang,kawung,truntum,megamendung}.svg — emas di atas transparan.
Motif parang, kawung, dan truntum berupa ubin <pattern> yang bisa diulang; mega mendung berupa pita lebar.
"""
import math, os

GOLD, GOLD_DEEP, GOLD_BRIGHT = "#d2a54a", "#8d6a2c", "#ecc978"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "batik")
os.makedirs(OUT, exist_ok=True)


def save(name, w, h, body, tile=None):
    if tile:
        tw, th, defs, extra = tile
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
               f'<defs><pattern id="p" width="{tw}" height="{th}" patternUnits="userSpaceOnUse" {extra}>{defs}</pattern></defs>'
               f'<rect width="{w}" height="{h}" fill="url(#p)"/></svg>')
    else:
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>'
    with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    print("batik:", name)


def parang():
    """Parang: pita diagonal berisi bilah 'S' berulang, dipisah garis mlinjon (belah ketupat)."""
    W, H = 64, 72
    blade = (f'<path d="M14 2 C46 6 54 26 34 36 C16 45 18 64 50 70 C30 70 6 60 14 44 C20 32 40 28 30 14 C26 8 20 4 14 2 Z" '
             f'fill="{GOLD}" fill-opacity=".85"/>'
             f'<path d="M18 8 C38 12 42 24 30 31" fill="none" stroke="{GOLD_BRIGHT}" stroke-width="1.2" stroke-opacity=".7"/>')
    rail = (f'<line x1="61" y1="0" x2="61" y2="{H}" stroke="{GOLD_DEEP}" stroke-width="2"/>'
            f'<path d="M61 30 l4 6 -4 6 -4 -6 Z" fill="{GOLD_BRIGHT}"/>'
            f'<circle cx="61" cy="8" r="1.6" fill="{GOLD}"/><circle cx="61" cy="64" r="1.6" fill="{GOLD}"/>')
    save("parang", 640, 640, None, (W, H, blade + rail, 'patternTransform="rotate(-45)"'))


def kawung():
    """Kawung: empat elips (irisan buah aren) mengitari titik pusat, dengan isen di tiap kelopak."""
    T = 80
    c = T / 2
    parts = []
    for ang, (dx, dy) in zip((0, 90, 180, 270), ((0, -1), (1, 0), (0, 1), (-1, 0))):
        x, y = c + dx * 19, c + dy * 19
        rot = 0 if dx == 0 else 90
        parts.append(f'<ellipse cx="{x}" cy="{y}" rx="11" ry="18" transform="rotate({rot} {x} {y})" fill="{GOLD}" fill-opacity=".8"/>')
        parts.append(f'<ellipse cx="{x}" cy="{y}" rx="5" ry="9" transform="rotate({rot} {x} {y})" fill="none" stroke="{GOLD_DEEP}" stroke-width="1.4"/>')
        parts.append(f'<circle cx="{x}" cy="{y}" r="1.8" fill="{GOLD_DEEP}"/>')
    parts.append(f'<circle cx="{c}" cy="{c}" r="3.2" fill="{GOLD_BRIGHT}"/>')
    for (x, y) in ((0, 0), (T, 0), (0, T), (T, T)):
        parts.append(f'<path d="M{x} {y - 5} l5 5 -5 5 -5 -5 Z" fill="{GOLD_DEEP}"/>')
    save("kawung", 640, 640, None, (T, T, "".join(parts), ""))


def truntum():
    """Truntum: bunga bintang kecil tersebar rapat, lambang cinta yang tumbuh kembali."""
    T = 56
    def flower(cx, cy, r, petals=8):
        out = []
        for k in range(petals):
            a = k / petals * math.tau
            px, py = cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.62
            out.append(f'<ellipse cx="{px:.2f}" cy="{py:.2f}" rx="{r * 0.36:.2f}" ry="{r * 0.16:.2f}" '
                       f'transform="rotate({math.degrees(a):.1f} {px:.2f} {py:.2f})" fill="{GOLD}" fill-opacity=".85"/>')
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r * 0.2:.2f}" fill="{GOLD_BRIGHT}"/>')
        return "".join(out)
    body = flower(14, 14, 11) + flower(42, 42, 11)
    for (x, y) in ((42, 14), (14, 42)):
        body += f'<circle cx="{x}" cy="{y}" r="2.2" fill="{GOLD_DEEP}"/>'
        for k in range(4):
            a = k / 4 * math.tau + math.pi / 4
            body += f'<circle cx="{x + math.cos(a) * 6:.2f}" cy="{y + math.sin(a) * 6:.2f}" r="1.1" fill="{GOLD}"/>'
    save("truntum", 640, 640, None, (T, T, body, ""))


def megamendung():
    """Mega mendung (Cirebon): awan berlapis dengan 5 garis gradasi, sebagai pita dekorasi lebar."""
    W, H = 1600, 420
    def cloud(cx, cy, s):
        # Lengkung awan: deret busur di atas, alas melengkung, ujung bergulung
        bumps = [(-1.0, 0.0, 0.42), (-0.55, -0.32, 0.5), (0.0, -0.45, 0.58), (0.55, -0.3, 0.5), (1.0, 0.0, 0.42)]
        d = f"M{cx - 1.42 * s:.1f} {cy:.1f} "
        for bx, by, br in bumps:
            x2, y2 = cx + (bx + br) * s, cy + by * s
            d += f"A{br * s:.1f} {br * s:.1f} 0 0 1 {x2:.1f} {y2 + 0.0:.1f} "
        d += f"Q{cx + 1.2 * s:.1f} {cy + 0.55 * s:.1f} {cx + 0.4 * s:.1f} {cy + 0.42 * s:.1f} "
        d += f"Q{cx:.1f} {cy + 0.7 * s:.1f} {cx - 0.4 * s:.1f} {cy + 0.42 * s:.1f} "
        d += f"Q{cx - 1.2 * s:.1f} {cy + 0.55 * s:.1f} {cx - 1.42 * s:.1f} {cy:.1f} Z"
        return d
    layers = []
    for (cx, cy, s) in ((220, 250, 120), (560, 190, 150), (930, 260, 130), (1290, 200, 160), (1560, 280, 110)):
        for k in range(5):
            ss = s * (1 - k * 0.15)
            col = (GOLD_DEEP, GOLD, GOLD, GOLD_BRIGHT, GOLD_BRIGHT)[k]
            fill = "#1b150d" if k == 0 else "none"
            layers.append(f'<path d="{cloud(cx, cy + k * ss * 0.04, ss)}" fill="{fill}" stroke="{col}" stroke-width="{3.2 - k * 0.4:.1f}" stroke-opacity="{0.95 - k * 0.1:.2f}"/>')
    save("megamendung", W, H, "".join(layers))


if __name__ == "__main__":
    parang(); kawung(); truntum(); megamendung()
