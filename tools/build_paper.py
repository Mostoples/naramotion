"""Paper NaraMotion (Markdown dari Claude Docs) → PDF (A4, gaya paper akademik, lewat Chrome) dan DOCX (python-docx).
Pemakaian: python tools/build_paper.py   → paper/NaraMotion_I2ASPO_paper.pdf dan .docx
"""
import re, html
from pathlib import Path
import markdown
from playwright.sync_api import sync_playwright
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

ROOT = Path(__file__).resolve().parents[1]; D = ROOT / "paper"
SRC = (D / "naramotion_paper.md").read_text("utf-8")
FIG = "fig1_architecture.png"

def clean(md):
    md = md.replace("&#91;", "[").replace("\\[", "[").replace("\\]", "]")
    lines = md.splitlines()
    lines = [l for l in lines if not re.match(r"^\w{3} \d{1,2}, \d{4} · @", l)]          # baris tanggal · mention dari editor
    FIGS = {2: "fig/f_hardware.png", 3: "fig/s_landing.png", 4: "fig/s_studio.png", 5: "fig/s_studio_sensors.png", 6: "fig/s_kelas_cam.png",
            7: "fig/s_arsip_bali.png", 8: "fig/s_arsip_anim.png", 9: "fig/f_pose_examples.jpg", 10: "fig/f_sam3d_overlay.jpg", 11: "fig/f_uc3d.png",
            12: "fig/f_m2mr_compare.png", 13: "fig/f_confusion.png", 14: "fig/f_sensor.png", 15: "fig/f_javanese.png"}
    out = []
    for l in lines:
        m = re.match(r"^\[image: Figure (\d+)\.", l)
        if l.startswith("[embedded content: Figure 1"):
            out += [f"![Figure 1]({FIG})", "", "*Figure 1. NaraMotion architecture: offline training on Kaggle GPUs and in-browser runtime.*"]
        elif m and int(m.group(1)) in FIGS: out.append(f"![Figure {m.group(1)}]({FIGS[int(m.group(1))]})")
        else: out.append(l)
    return "\n".join(out)

def render_equations(md):
    """blok ```latex → gambar PNG (MathJax di Chromium) agar rumus tampil sama di PDF dan DOCX"""
    blocks = re.findall(r"```latex\n(.*?)\n```", md, flags=re.S)
    if not blocks: return md
    page = ("<!doctype html><html><head><meta charset=utf-8><script>window.MathJax={svg:{fontCache:'global'}};</script>"
            "<script src='https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js'></script><style>body{margin:0;background:#fff}div{display:inline-block;padding:6px 10px;font-size:20px}</style></head><body>"
            + "".join(f"<div id='e{i}'>\\[{html.escape(b)}\\]</div><br>" for i, b in enumerate(blocks)) + "</body></html>")
    hp = D / "_eq.html"; hp.write_text(page, "utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(device_scale_factor=3); pg.goto(hp.as_uri()); pg.wait_for_function("window.MathJax && MathJax.startup && MathJax.startup.promise", timeout=30000)
        pg.evaluate("MathJax.startup.promise"); pg.wait_for_timeout(800)
        for i in range(len(blocks)): pg.locator(f"#e{i}").screenshot(path=str(D / f"fig/eq_{i + 1}.png"))
        b.close()
    hp.unlink()
    for i, b in enumerate(blocks): md = md.replace(f"```latex\n{b}\n```", f"![Equation {i + 1}](fig/eq_{i + 1}.png)", 1)
    return md

MD = render_equations(clean(SRC)); (D / "naramotion_paper_clean.md").write_text(MD, "utf-8")

# ---------- PDF ----------
body = markdown.markdown(MD, extensions=["tables", "sane_lists"])
body = re.sub(r'<img alt="Equation', '<img class="eq" alt="Equation', body); body = re.sub(r'<img alt=', '<img class="fig" alt=', body)
CSS = """@page { size: A4; }
body { font-family: "Times New Roman", Times, serif; font-size: 11pt; line-height: 1.45; color: #111; text-align: justify; hyphens: auto; }
h1 { font-size: 17pt; text-align: center; line-height: 1.25; margin: 0 0 14pt; }
h2 { font-size: 12.5pt; margin: 16pt 0 6pt; text-transform: none; border-bottom: .6pt solid #999; padding-bottom: 2pt; }
h3 { font-size: 11.5pt; margin: 11pt 0 4pt; font-style: italic; }
p { margin: 0 0 7pt; } ul, ol { margin: 0 0 7pt; padding-left: 18pt; } li { margin-bottom: 2pt; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin: 4pt 0 10pt; page-break-inside: avoid; text-align: left; }
th, td { border-top: .5pt solid #555; border-bottom: .5pt solid #555; padding: 3pt 4pt; vertical-align: top; }
th { background: #eee; }
img.fig { display: block; max-width: 100%; max-height: 15cm; margin: 8pt auto 2pt; page-break-inside: avoid; } p:has(img) { page-break-after: avoid; } img.eq { display: block; max-width: 92%; height: auto; margin: 6pt auto; zoom: .55; }
a { color: #123d8a; text-decoration: none; word-break: break-all; }
h2 + p strong:first-child { font-variant: small-caps; }"""
page = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
hp = D / "naramotion_paper.html"; hp.write_text(page, "utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto(hp.as_uri()); pg.wait_for_timeout(500)
    pg.pdf(path=str(D / "NaraMotion_I2ASPO_paper.pdf"), format="A4", print_background=True, display_header_footer=True,
           header_template="<span></span>", footer_template="<div style='font-size:8pt;width:100%;text-align:center;color:#555'><span class='pageNumber'></span></div>",
           margin={"top": "2.2cm", "bottom": "2.2cm", "left": "2.2cm", "right": "2.2cm"})
    b.close()

# ---------- DOCX ----------
doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
for s in doc.sections: s.top_margin = s.bottom_margin = Cm(2.3); s.left_margin = s.right_margin = Cm(2.2)
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\)|<https?://[^>]+>)")
def runs(par, text):
    for part in INLINE.split(text):
        if not part: continue
        if part.startswith("**"): r = par.add_run(part[2:-2]); r.bold = True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2: r = par.add_run(part[1:-1]); r.italic = True
        elif part.startswith("<http"): r = par.add_run(part[1:-1]); r.font.color.rgb = RGBColor(0x12, 0x3d, 0x8a)
        elif part.startswith("[") and "](" in part:
            t, u = part[1:].split("](", 1); r = par.add_run(t); r.font.color.rgb = RGBColor(0x12, 0x3d, 0x8a)
        else: par.add_run(part)
lines = MD.splitlines(); i = 0
while i < len(lines):
    l = lines[i]
    if l.startswith("# "):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = p.add_run(l[2:]); r.bold = True; r.font.size = Pt(16)
    elif l.startswith("## "): doc.add_heading(l[3:], level=1)
    elif l.startswith("### "): doc.add_heading(l[4:], level=2)
    elif l.startswith("!["):
        src = re.search(r"\(([^)]+)\)", l).group(1); doc.add_picture(str(D / src), width=Cm(12.0 if "eq_" in src else 16.0)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif l.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            if not re.match(r"^\|\s*-", lines[i]): rows.append([c.strip() for c in lines[i].strip("|").split("|")])
            i += 1
        t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for ri, row in enumerate(rows):
            for ci, cell in enumerate(row):
                c = t.cell(ri, ci); c.text = ""; pr = c.paragraphs[0]; runs(pr, cell)
                for r in pr.runs:
                    r.font.size = Pt(9)
                    if ri == 0: r.bold = True
        doc.add_paragraph(); continue
    elif re.match(r"^\d+\. ", l): p = doc.add_paragraph(style="List Number"); runs(p, re.sub(r"^\d+\. ", "", l))
    elif l.startswith("- "): p = doc.add_paragraph(style="List Bullet"); runs(p, l[2:])
    elif l.strip():
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY; runs(p, l)
    i += 1
doc.save(D / "NaraMotion_I2ASPO_paper.docx")
print("PDF + DOCX ->", D)
