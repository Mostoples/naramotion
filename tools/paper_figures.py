"""Figur cetak (latar terang) untuk paper NaraMotion + fakta tambahan (parameter model, ukuran, akurasi per gerak).
Pemakaian: python tools/paper_figures.py  → paper/fig/*.png, paper/facts.json
"""
import json, glob, os
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]; F = ROOT / "paper/fig"; F.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
GOLD, BROWN, GREY = "#b8862f", "#7a4a1e", "#888888"
newest = lambda pat: max(glob.glob(str(ROOT / pat)), key=os.path.getmtime)
facts = {}

# 1) confusion matrix putri & putra (model browser body17)
fig, axs = plt.subplots(1, 2, figsize=(10, 4.6))
for ax, ds in zip(axs, ["putri", "putra"]):
    m = json.load(open(newest(f"ml/runs/tg3/{ds}_body17_metrics.json"))); cm = np.array(m["confusion"]); cl = [c.replace("_", " ") for c in m["classes"]]
    nrm = cm / cm.sum(1, keepdims=True); ax.imshow(nrm, cmap="YlOrBr", vmin=0, vmax=1)
    ax.set_xticks(range(len(cl)), cl, rotation=70, ha="right", fontsize=7); ax.set_yticks(range(len(cl)), cl, fontsize=7)
    for i in range(len(cl)):
        for j in range(len(cl)):
            if cm[i, j]: ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=6, color="white" if nrm[i, j] > .6 else "black")
    ax.set_title(f"{'Female, 13' if ds == 'putri' else 'Male, 11'} movements · test accuracy {m['test_acc']*100:.1f}%", fontsize=9)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    facts[f"{ds}_per_class"] = m["per_class"]; facts[f"{ds}_n"] = m["n"]
fig.tight_layout(); fig.savefig(F / "f_confusion.png", dpi=200); plt.close(fig)

# 2) sensor: ablasi IMU Turki + tata letak AIST
mi = json.load(open(newest("ml/runs/*/metrics_imu.json"), encoding="utf-8")); ma = json.load(open(newest("ml/runs/*/metrics_aist.json")))
fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
ab = mi["ablation_drop"]; names = {"kaki kanan": "right foot", "tangan kanan": "right hand", "kaki kiri": "left foot", "tangan kiri": "left hand", "pinggang": "waist"}
ks = sorted(ab, key=lambda k: ab[k]); axs[0].barh([names.get(k, k) for k in ks], [ab[k] * 100 for k in ks], color=[GOLD if ab[k] == max(ab.values()) else BROWN for k in ks])
axs[0].set_xlabel("accuracy drop when node removed (points)"); axs[0].set_title(f"Real 5-node IMU (Turkish folk dance), LOSO {mi['loso_acc']*100:.1f}%")
lay = {"10 nodes": ma["acc_10node"] * 100, "5 nodes": ma["acc_5node"] * 100, "10 − legs (4)": (ma["acc_10node"] - ma["ablation_drop"]["kaki (4 node)"]) * 100,
       "10 − arms (4)": (ma["acc_10node"] - ma["ablation_drop"]["lengan (4 node)"]) * 100}
axs[1].bar(list(lay), list(lay.values()), color=[GOLD, BROWN, BROWN, BROWN]); axs[1].axhline(10, color=GREY, ls="--", lw=.8); axs[1].text(3.4, 11, "chance", fontsize=7, color=GREY, ha="right")
for i, v in enumerate(lay.values()): axs[1].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=8)
axs[1].set_ylabel("test accuracy (%)"); axs[1].set_ylim(0, 85); axs[1].set_title("Synthetic IMU from AIST++, 10 genres")
fig.tight_layout(); fig.savefig(F / "f_sensor.png", dpi=200); plt.close(fig)
facts["aist"] = {k: round(v, 1) for k, v in lay.items()}

# 3) karakter tari Jawa
jm = json.load(open(ROOT / "ml/runs/javanese/javanese_metrics.json", encoding="utf-8"))["characters"]
order = ["luruh", "lanyap", "gagah", "wanara", "raksasa", "jatayu"]; lab = ["Halus/luruh", "Lanyap", "Gagah", "Wanara", "Raksasa", "Jatayu"]
fig, axs = plt.subplots(1, 3, figsize=(10, 3.2))
for ax, (k, t) in zip(axs, [("kecepatan_pergelangan_m_s", "Wrist speed (m/s)"), ("jerk_pergelangan_m_s3", "Wrist jerk (m/s³)"), ("lebar_tapak_m", "Stance width (m)")]):
    ax.bar(lab, [jm[o][k] for o in order], color=[GOLD, GOLD, BROWN, BROWN, BROWN, BROWN]); ax.set_title(t); ax.tick_params(axis="x", rotation=40, labelsize=7)
fig.suptitle("Javanese character types (gold = alus, brown = gagah/animal); one VICON take each", fontsize=9)
fig.tight_layout(); fig.savefig(F / "f_javanese.png", dpi=200); plt.close(fig)

# 4) contoh pose RTMW dari kernel ekstraksi (6 gerak)
pv = sorted(glob.glob(str(ROOT / "ml/runs/*/preview/*.jpg")))
seen, ims = set(), []
for p in pv:
    n = Path(p).stem
    if n in seen: continue
    seen.add(n); ims.append((n, Image.open(p).convert("RGB")))
ims = ims[:8]
if ims:
    h = 260; row = [im.resize((int(im.width * h / im.height), h)) for _, im in ims]
    cols = 4; rows = (len(row) + cols - 1) // cols; cw = max(r.width for r in row)
    sheet = Image.new("RGB", (cw * cols, h * rows), "white")
    for i, r in enumerate(row): sheet.paste(r, ((i % cols) * cw + (cw - r.width) // 2, (i // cols) * h))
    sheet.save(F / "f_pose_examples.jpg", quality=90); facts["pose_examples"] = [n for n, _ in ims]

# 5) parameter & ukuran model
try:
    import torch
    for t in ["putri_body17", "putri_whole133"]:
        sd = torch.load(newest(f"ml/runs/tg3/{t}_model.pt"), map_location="cpu"); facts[f"{t}_params"] = int(sum(v.numel() for v in sd.values() if v.dtype.is_floating_point))
except Exception as e: facts["params_error"] = str(e)
for t in ["putri_body17", "putra_body17"]: facts[f"{t}_onnx_mb"] = round(os.path.getsize(ROOT / f"assets/ml/{t}_model.onnx") / 1e6, 2)
json.dump(facts, open(ROOT / "paper/facts.json", "w"), indent=1); print(json.dumps(facts, indent=0)[:1500])
