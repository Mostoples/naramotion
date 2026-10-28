"""Cetak HTML poster/brosur NaraMotion ke PDF (ukuran mm) dan PNG lewat Chromium headless (Playwright).

Pemakaian:
  python tools/render_print.py print/poster.html 841 1189 [--scale 1.5] [--pages 1]
Menulis <nama>.pdf dan <nama>.png (halaman pertama; brosur: <nama>-1.png, <nama>-2.png) di folder yang sama.
"""
import sys, pathlib
from playwright.sync_api import sync_playwright

MM = 96 / 25.4
src = pathlib.Path(sys.argv[1]).resolve()
w_mm, h_mm = float(sys.argv[2]), float(sys.argv[3])
opt = dict(zip(sys.argv[4::2], sys.argv[5::2]))
scale = float(opt.get("--scale", 1))
pages = int(opt.get("--pages", 1))
w_px, h_px = round(w_mm * MM), round(h_mm * MM)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": w_px, "height": h_px}, device_scale_factor=scale)
    pg.goto(src.as_uri(), wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(400)
    pg.pdf(path=str(src.with_suffix(".pdf")), width=f"{w_mm}mm", height=f"{h_mm}mm", print_background=True,
           prefer_css_page_size=True)
    for i in range(pages):
        name = src.with_suffix(".png") if pages == 1 else src.with_name(f"{src.stem}-{i + 1}.png")
        pg.screenshot(path=str(name), clip={"x": 0, "y": i * h_px, "width": w_px, "height": h_px}, full_page=True)
        print("[nara] png", name)
    print("[nara] pdf", src.with_suffix(".pdf"))
    b.close()
