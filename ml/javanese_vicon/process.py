"""NaraMotion · M5: mocap VICON tari Jawa → orientasi 10 segmen (format node NaraMotion) + analisis karakter.

Sumber: M. Escobar Varela & L. Hernández-Barraza, "Digital Dance Scholarship: Biomechanics and culturally-situated
dance analysis", Digital Scholarship in the Humanities (2019); data github.com/villaorlado/dance (tanpa lisensi —
dipakai untuk analisis internal dengan kredit; data mentah tidak disebarkan ulang).
Satu take per tipe karakter (gagah, jatayu, lanyap, halus/luruh, raksasa, wanara), marker Plug-in Gait, 100 Hz.

Pemakaian: python ml/javanese_vicon/process.py <folder csv> <folder keluaran>
Keluaran: javanese_metrics.json, javanese_character.png, javanese_10node.npz (kuaternion w,x,y,z per segmen)
"""
import sys, json, math
from pathlib import Path
import numpy as np

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
CHAR = {"gagah": "Gagah (putra gagah)", "jatayu": "Jatayu (burung)", "lanyap": "Lanyap (putra alus lincah)",
        "luruh": "Halus/luruh (putra alus tenang)", "raksasa": "Raksasa (buta)", "wanara": "Wanara (kera)"}
# 10 node NaraMotion → segmen: (asal, ujung, titik bantu bidang)
SEG = {
    "kepala": ("C7", "_HEADC", "_HEADL"),
    "badan": ("_PELV", "C7", "_SHL"),
    "lengan_atas_ki": ("LSHO", "LELB", "LUPA"), "lengan_bawah_ki": ("LELB", "_LWR", "LFRM"),
    "lengan_atas_ka": ("RSHO", "RELB", "RUPA"), "lengan_bawah_ka": ("RELB", "_RWR", "RFRM"),
    "paha_ki": ("_LHIP", "LKNE", "LTHI"), "betis_ki": ("LKNE", "LANK", "LTIB"),
    "paha_ka": ("_RHIP", "RKNE", "RTHI"), "betis_ka": ("RKNE", "RANK", "RTIB"),
}

def read_traj(path):
    L = path.read_text("latin-1").splitlines()
    i = next(k for k, l in enumerate(L) if l.strip().upper() == "TRAJECTORIES")
    hz = float(L[i + 1].split(",")[0]); names = L[i + 2].split(","); rows = []
    for l in L[i + 5:]:
        if not l.strip() or not l[0].isdigit(): break
        rows.append([float(v) if v not in ("", None) else np.nan for v in l.split(",")[: len(names)]])
    A = np.array(rows, float); M = {}
    for c, n in enumerate(names):
        if n.strip() and c + 2 < A.shape[1]: M[n.strip()] = A[:, c:c + 3] / 1000.0   # mm → m
    return hz, M

def fill(x):
    """Isi celah marker (NaN) dengan interpolasi linear per sumbu."""
    x = x.copy(); t = np.arange(len(x))
    for k in range(3):
        ok = np.isfinite(x[:, k])
        if ok.sum() >= 2: x[~ok, k] = np.interp(t[~ok], t[ok], x[ok, k])
    return x

def derived(M):
    g = lambda n: fill(M[n])
    M["_HEADC"] = (g("LFHD") + g("RFHD")) / 2; M["_HEADL"] = (g("LFHD") + g("LBHD")) / 2
    M["_PELV"] = (g("LASI") + g("RASI") + g("LPSI") + g("RPSI")) / 4; M["_SHL"] = g("LSHO")
    M["_LWR"] = (g("LWRA") + g("LWRB")) / 2; M["_RWR"] = (g("RWRA") + g("RWRB")) / 2
    hipw = np.linalg.norm(g("LASI") - g("RASI"), axis=1, keepdims=True)
    # perkiraan pusat sendi pinggul (Davis/Plug-in Gait sederhana): ke bawah & dalam dari ASIS
    for s, o in (("L", "R"), ("R", "L")):
        a, b = g(f"{s}ASI"), g(f"{o}ASI"); down = np.array([0, 0, -1.0])
        M[f"_{s}HIP"] = a + 0.11 * (b - a) + down * 0.33 * hipw
    return M

def frame(o, e, h):
    y = e - o; y /= np.linalg.norm(y, axis=1, keepdims=True) + 1e-9
    z = np.cross(y, h - o); z /= np.linalg.norm(z, axis=1, keepdims=True) + 1e-9
    x = np.cross(y, z); return np.stack([x, y, z], -1)   # (T,3,3) kolom = sumbu segmen

def quat(R):
    w = np.sqrt(np.maximum(0, 1 + R[:, 0, 0] + R[:, 1, 1] + R[:, 2, 2])) / 2
    x = (R[:, 2, 1] - R[:, 1, 2]) / (4 * w + 1e-9); y = (R[:, 0, 2] - R[:, 2, 0]) / (4 * w + 1e-9); z = (R[:, 1, 0] - R[:, 0, 1]) / (4 * w + 1e-9)
    q = np.stack([w, x, y, z], 1); q /= np.linalg.norm(q, axis=1, keepdims=True)
    for t in range(1, len(q)):
        if np.dot(q[t], q[t - 1]) < 0: q[t] = -q[t]   # kontinuitas tanda
    return q

def angvel(R, hz):
    """Kecepatan sudut segmen (rad/s) dari rotasi relatif antar-frame — setara pembacaan giroskop."""
    d = np.einsum("tji,tjk->tik", R[:-1], R[1:]); tr = np.clip((np.trace(d, axis1=1, axis2=2) - 1) / 2, -1, 1)
    return np.concatenate([[0.0], np.arccos(tr) * hz])

def angle(a, b, c):
    u, v = a - b, c - b
    return np.degrees(np.arccos(np.clip((u * v).sum(1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1) + 1e-9), -1, 1)))

metrics, npz = {}, {}
for key, label in CHAR.items():
    f = SRC / f"{key}.csv"
    if not f.exists(): continue
    hz, M = read_traj(f); M = derived(M); T = len(M["C7"])
    Rs = {s: frame(M[o] if o.startswith("_") else fill(M[o]), fill(M[e]) if not e.startswith("_") else M[e],
                   M[h] if h.startswith("_") else fill(M[h])) for s, (o, e, h) in SEG.items()}
    for s, R in Rs.items(): npz[f"{key}__{s}"] = quat(R).astype(np.float32)
    w = {s: angvel(R, hz) for s, R in Rs.items()}
    wr = [fill(M["LWRA"]), fill(M["RWRA"])]; an = [fill(M["LANK"]), fill(M["RANK"])]
    spd = lambda p: np.linalg.norm(np.diff(p, axis=0), axis=1) * hz
    jerk = lambda p: np.linalg.norm(np.diff(p, n=3, axis=0), axis=1) * hz ** 3
    elbow = [angle(fill(M[f"{s}SHO"]), fill(M[f"{s}ELB"]), fill(M[f"{s}WRA"])) for s in "LR"]
    knee = [angle(M[f"_{s}HIP"], fill(M[f"{s}KNE"]), fill(M[f"{s}ANK"])) for s in "LR"]
    arm_up = [np.degrees(np.arccos(np.clip(-(fill(M[f"{s}ELB"]) - fill(M[f"{s}SHO"]))[:, 2] / (np.linalg.norm(fill(M[f"{s}ELB"]) - fill(M[f"{s}SHO"]), axis=1) + 1e-9), -1, 1))) for s in "LR"]
    stance = np.linalg.norm((fill(M["LANK"]) - fill(M["RANK"]))[:, :2], axis=1)
    pelv_h = M["_PELV"][:, 2]
    metrics[key] = dict(
        label=label, frames=T, hz=hz, durasi_s=round(T / hz, 2),
        kecepatan_pergelangan_m_s=round(float(np.mean([spd(p).mean() for p in wr])), 3),
        kecepatan_kaki_m_s=round(float(np.mean([spd(p).mean() for p in an])), 3),
        jerk_pergelangan_m_s3=round(float(np.mean([np.median(jerk(p)) for p in wr])), 1),
        rom_siku_deg=round(float(np.mean([np.ptp(a) for a in elbow])), 1),
        tekuk_lutut_rata_deg=round(float(180 - np.mean([a.mean() for a in knee])), 1),
        angkat_lengan_atas_deg=round(float(np.mean([np.percentile(a, 90) for a in arm_up])), 1),
        lebar_tapak_m=round(float(np.median(stance)), 3),
        turun_pinggul_m=round(float(np.ptp(pelv_h)), 3),
        gyro_rata_rad_s={s: round(float(v.mean()), 3) for s, v in w.items()},
    )
    print(key, {k: v for k, v in metrics[key].items() if k != "gyro_rata_rad_s"}, flush=True)

np.savez_compressed(OUT / "javanese_10node.npz", **npz)
json.dump(dict(source="Escobar Varela & Hernández-Barraza (2019), DSH; github.com/villaorlado/dance", segments=list(SEG), characters=metrics),
          open(OUT / "javanese_metrics.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
keys = [k for k in CHAR if k in metrics]
feat = [("kecepatan_pergelangan_m_s", "Kecepatan pergelangan (m/s)"), ("angkat_lengan_atas_deg", "Angkat lengan atas (°)"),
        ("lebar_tapak_m", "Lebar tapak (m)"), ("tekuk_lutut_rata_deg", "Tekuk lutut (perkiraan, °)"),
        ("jerk_pergelangan_m_s3", "Jerk pergelangan (m/s³)"), ("rom_siku_deg", "Rentang siku (°)")]
fig, axs = plt.subplots(2, 3, figsize=(12, 6.4)); fig.patch.set_facecolor("#1b150d")
alus = {"lanyap", "luruh"}
for ax, (f, t) in zip(axs.flat, feat):
    v = [metrics[k][f] for k in keys]
    ax.bar(range(len(keys)), v, color=["#ecc978" if k in alus else "#9a5a2a" for k in keys])
    ax.set_xticks(range(len(keys)), [k.capitalize() for k in keys], rotation=30, ha="right", color="#ebe0c6", fontsize=8)
    ax.set_title(t, color="#ecc978", fontsize=10); ax.set_facecolor("#1e170e"); ax.tick_params(colors="#a9987a", labelsize=8)
    for s in ax.spines.values(): s.set_color("#76674c")
fig.suptitle("Ciri gerak per tipe karakter tari Jawa (emas = alus, cokelat = gagah/kasar)", color="#f6e4b4")
fig.text(0.01, 0.01, "Data: Escobar Varela & Hernández-Barraza (2019), github.com/villaorlado/dance · 1 take per karakter", color="#76674c", fontsize=7)
fig.tight_layout(rect=(0, 0.03, 1, 0.95)); fig.savefig(OUT / "javanese_character.png", dpi=130, facecolor=fig.get_facecolor())
print("SELESAI", OUT)
