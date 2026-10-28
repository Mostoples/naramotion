"""NaraMotion · Kaggle kernel 4: AIST++ → IMU sintetis 10 node (tata letak NaraMotion) + pengenal genre dari "sensor".

Sumber: AIST++ (Li dkk., ICCV 2021), anotasi CC BY 4.0 oleh Google; video/gerak mengikuti ketentuan AIST Dance DB
(https://aistdancedb.ongaaccel.jp/terms_of_use/) — riset/pendidikan dengan kredit.
Tiap node: kuaternion global (4) + giroskop sintetis di kerangka sensor (3, rad/s) + akselerometer sintetis di kerangka
sensor (3, g, termasuk gravitasi) → 10 node × 10 kanal pada 50 Hz.
Uji: penari terpisah (dancer d*, sekitar 20% penari diuji). Ablasi: 10 node vs. 5 node (tangan, kaki, pinggang) dan per kelompok node.
Keluaran: metrics_aist.json, model_aist_imu.onnx, studio_clips.json (satu klip 12 s per genre untuk Studio), confusion_aist.png
"""
import os, io, glob, json, pickle, random, subprocess, zipfile, re
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F

OUT = "/kaggle/working"; TMP = "/tmp/aist"; os.makedirs(TMP, exist_ok=True)
REL = "https://github.com/google/aistplusplus_dataset/releases/download/v1.0"
for z in ("motions.zip", "keypoints3d.zip"):
    if not os.path.exists(f"{TMP}/{z}"): subprocess.run(f"curl -sSL -o {TMP}/{z} {REL}/{z}", shell=True, check=True)
    subprocess.run(f"cd {TMP} && unzip -qo {z}", shell=True, check=True)
mot = sorted(glob.glob(f"{TMP}/**/motions/*.pkl", recursive=True)); kp = {os.path.basename(p): p for p in glob.glob(f"{TMP}/**/keypoints3d/*.pkl", recursive=True)}
print(len(mot), "gerak,", len(kp), "keypoint", flush=True)

GENRE = {"gBR": "Break", "gPO": "Pop", "gLO": "Lock", "gMH": "Middle Hip-hop", "gLH": "LA Hip-hop", "gHO": "House",
         "gWA": "Waack", "gKR": "Krump", "gJS": "Street Jazz", "gJB": "Ballet Jazz"}
PARENT = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19]
# node NaraMotion → (sendi SMPL yang memutar segmen, pasangan keypoint COCO untuk titik tengah segmen)
NODE = {"kepala": (15, (0, 0)), "badan": (9, (5, 6)),
        "lengan_atas_ki": (16, (5, 7)), "lengan_bawah_ki": (18, (7, 9)), "lengan_atas_ka": (17, (6, 8)), "lengan_bawah_ka": (19, (8, 10)),
        "paha_ki": (1, (11, 13)), "betis_ki": (4, (13, 15)), "paha_ka": (2, (12, 14)), "betis_ka": (5, (14, 16))}
FIVE = ["lengan_bawah_ki", "lengan_bawah_ka", "betis_ki", "betis_ka", "badan"]   # setara tata letak 5 node (tangan, kaki, pinggang)
HZ = 50

def rodrigues(a):
    th = np.linalg.norm(a, axis=-1, keepdims=True) + 1e-9; k = a / th; th = th[..., 0]
    K = np.zeros(a.shape[:-1] + (3, 3)); K[..., 0, 1], K[..., 0, 2], K[..., 1, 2] = -k[..., 2], k[..., 1], -k[..., 0]
    K = K - np.swapaxes(K, -1, -2); I = np.eye(3)
    return I + np.sin(th)[..., None, None] * K + (1 - np.cos(th))[..., None, None] * (K @ K)

def quat(R):
    w = np.sqrt(np.maximum(0, 1 + np.trace(R, axis1=-2, axis2=-1))) / 2; d = 4 * w + 1e-9
    q = np.stack([w, (R[..., 2, 1] - R[..., 1, 2]) / d, (R[..., 0, 2] - R[..., 2, 0]) / d, (R[..., 1, 0] - R[..., 0, 1]) / d], -1)
    q /= np.linalg.norm(q, axis=-1, keepdims=True)
    for t in range(1, len(q)): q[t] *= np.sign((q[t] * q[t - 1]).sum()) or 1
    return q

def logmap(R):
    tr = np.clip((np.trace(R, axis1=-2, axis2=-1) - 1) / 2, -1, 1); th = np.arccos(tr)
    v = np.stack([R[..., 2, 1] - R[..., 1, 2], R[..., 0, 2] - R[..., 2, 0], R[..., 1, 0] - R[..., 0, 1]], -1)
    return v * (th / (2 * np.sin(th) + 1e-9))[..., None]

def resample(x, n_src_hz, n_dst_hz):
    t0 = np.arange(len(x)) / n_src_hz; t1 = np.arange(0, t0[-1], 1 / n_dst_hz)
    return np.stack([np.interp(t1, t0, x[:, i]) for i in range(x.shape[1])], 1)

def synth(mp, kpp):
    m = pickle.load(open(mp, "rb")); poses = m["smpl_poses"].reshape(-1, 24, 3)[:, :22]
    Rl = rodrigues(poses); G = np.zeros_like(Rl); G[:, 0] = Rl[:, 0]
    for j in range(1, 22): G[:, j] = G[:, PARENT[j]] @ Rl[:, j]
    # SMPL AIST++: sumbu-y ke atas → gravitasi (0,-9.81,0)
    k = pickle.load(open(kpp, "rb")); P = k.get("keypoints3d_optim", k.get("keypoints3d")) / 100.0   # cm → m, (T,17,3)
    T = min(len(G), len(P)); G, P = G[:T], P[:T]
    feats = []
    for name, (j, (a, b)) in NODE.items():
        R = G[:, j]; q = quat(R)
        w = np.concatenate([np.zeros((1, 3)), logmap(np.swapaxes(R[:-1], -1, -2) @ R[1:]) * 60], 0)        # rad/s, kerangka sensor
        pos = (P[:, a] + P[:, b]) / 2
        pos = np.stack([np.convolve(pos[:, i], np.ones(5) / 5, mode="same") for i in range(3)], 1)          # redam derau triangulasi
        acc = np.gradient(np.gradient(pos, axis=0), axis=0) * 3600 + np.array([0, 9.81, 0])                # m/s², +gravitasi (pembacaan diam = +1 g ke atas)
        acc_s = np.einsum("tji,tj->ti", R, acc) / 9.81                                                      # ke kerangka sensor, satuan g
        feats.append(np.concatenate([q, w, acc_s], 1))
    X = np.concatenate(feats, 1).astype(np.float32)                    # (T, 100) @ 60 Hz
    return resample(X, 60, HZ).astype(np.float32), quat_seq(G)

def quat_seq(G):
    return {n: quat(G[:, j]).astype(np.float32) for n, (j, _) in NODE.items()}

data, clips = [], {}
for i, mp in enumerate(mot):
    nm = os.path.basename(mp); g = nm[:3]; dancer = re.search(r"_d(\d+)_", nm)
    if g not in GENRE or nm not in kp or not dancer: continue
    try: X, Q = synth(mp, kp[nm])
    except Exception as e: print("lewati", nm, e); continue
    data.append(dict(name=nm, y=list(GENRE).index(g), d=int(dancer.group(1)), X=X))
    if g not in clips and len(X) > 12 * HZ and "sFM" in nm:   # koreografi lepas (advanced), 12 s, 30 Hz untuk Studio
        s = slice(len(next(iter(Q.values()))) // 3, len(next(iter(Q.values()))) // 3 + 12 * 60, 2)
        clips[g] = dict(name=nm, genre=GENRE[g], hz=30, nodes={n: np.round(q[s], 4).tolist() for n, q in Q.items()})
    if i % 200 == 0: print(i, nm, X.shape, flush=True)
print(len(data), "urutan IMU sintetis", flush=True)

dancers = sorted({x["d"] for x in data}); test_d = set(dancers[::5])
WIN, HOP = 4 * HZ, HZ
def windows(sel, keep=None):
    Xs, Ys = [], []
    for s in sel:
        X = s["X"]
        if keep is not None: X = X.reshape(len(X), 10, 10)[:, keep].reshape(len(X), -1)
        for a in range(0, len(X) - WIN + 1, HOP): Xs.append(X[a:a + WIN]); Ys.append(s["y"])
    return np.stack(Xs), np.array(Ys)
tr = [x for x in data if x["d"] not in test_d]; te = [x for x in data if x["d"] in test_d]
dev = "cuda" if torch.cuda.is_available() else "cpu"; torch.manual_seed(7); random.seed(7)

class Net(nn.Module):
    def __init__(s, cin, C, w=128):
        super().__init__()
        s.f = nn.Sequential(nn.Conv1d(cin, w, 5, padding=2), nn.BatchNorm1d(w), nn.GELU(),
                            nn.Conv1d(w, w, 5, padding=4, dilation=2), nn.BatchNorm1d(w), nn.GELU(),
                            nn.Conv1d(w, w, 5, padding=8, dilation=4), nn.BatchNorm1d(w), nn.GELU(),
                            nn.Conv1d(w, w, 5, padding=16, dilation=8), nn.BatchNorm1d(w), nn.GELU())
        s.h = nn.Sequential(nn.Dropout(0.3), nn.Linear(2 * w, C))
    def forward(s, x): h = s.f(x); return s.h(torch.cat([h.mean(-1), h.amax(-1)], 1))

def run(keep=None, epochs=18):
    Xtr, Ytr = windows(tr, keep); Xte, Yte = windows(te, keep)
    mu, sd = Xtr.reshape(-1, Xtr.shape[-1]).mean(0), Xtr.reshape(-1, Xtr.shape[-1]).std(0) + 1e-6
    m = Net(Xtr.shape[-1], len(GENRE)).to(dev); opt = torch.optim.AdamW(m.parameters(), 2e-3, weight_decay=0.05)
    Xt = torch.tensor((Xtr - mu) / sd).permute(0, 2, 1); Yt = torch.tensor(Ytr)
    for ep in range(epochs):
        m.train(); idx = torch.randperm(len(Xt))
        for i in range(0, len(idx), 128):
            b = idx[i:i + 128]; x = Xt[b] + 0.05 * torch.randn_like(Xt[b])
            loss = F.cross_entropy(m(x.to(dev)), Yt[b].to(dev), label_smoothing=0.1); opt.zero_grad(); loss.backward(); opt.step()
    m.eval(); P = []
    with torch.no_grad():
        Xe = torch.tensor((Xte - mu) / sd).permute(0, 2, 1).float()
        for i in range(0, len(Xe), 512): P.append(m(Xe[i:i + 512].to(dev)).argmax(1).cpu())
    p = torch.cat(P).numpy(); return float((p == Yte).mean()), p, Yte, m, mu, sd

names = list(NODE)
acc10, p, y, m, mu, sd = run()
acc5 = run(keep=[names.index(n) for n in FIVE])[0]
GROUPS = {"kepala": ["kepala"], "badan": ["badan"], "lengan (4 node)": [n for n in names if n.startswith("lengan")], "kaki (4 node)": [n for n in names if n.startswith(("paha", "betis"))]}
acc_drop = {g: round(acc10 - run(keep=[k for k in range(10) if names[k] not in ns], epochs=8)[0], 4) for g, ns in GROUPS.items()}
print("10 node", acc10, "5 node", acc5, "ablasi", acc_drop, flush=True)

C = len(GENRE); cm = np.zeros((C, C), int)
for a, b in zip(y, p): cm[a, b] += 1
class Wrap(nn.Module):
    def __init__(s, m, mu, sd): super().__init__(); s.m = m; s.register_buffer("mu", torch.tensor(mu)); s.register_buffer("sd", torch.tensor(sd))
    def forward(s, x): return s.m(((x - s.mu) / s.sd).permute(0, 2, 1))
torch.onnx.export(Wrap(m.cpu(), mu, sd).eval(), torch.zeros(1, WIN, 100), f"{OUT}/model_aist_imu.onnx", input_names=["imu"], output_names=["logits"],
                  dynamic_axes={"imu": {0: "b"}}, opset_version=17, dynamo=False)
json.dump(dict(genres=list(GENRE.values()), acc_10node=round(acc10, 4), acc_5node=round(acc5, 4), ablation_drop=acc_drop,
               n_seq=len(data), test_dancers=sorted(test_d), hz=HZ, window_s=4, node_order=names,
               channels_per_node=["qw", "qx", "qy", "qz", "gx", "gy", "gz", "ax", "ay", "az"], confusion=cm.tolist(),
               source="AIST++ (Li et al., ICCV 2021), annotations CC BY 4.0 (Google); AIST Dance DB terms"), open(f"{OUT}/metrics_aist.json", "w"), indent=1)
json.dump(dict(source="AIST++ (Li et al., ICCV 2021) · CC BY 4.0 · AIST Dance Video Database", clips=list(clips.values())), open(f"{OUT}/studio_clips.json", "w"))

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(12, 5))
ax[0].imshow(cm, cmap="YlOrBr"); g = list(GENRE.values()); ax[0].set_xticks(range(C), g, rotation=60, ha="right", fontsize=7); ax[0].set_yticks(range(C), g, fontsize=7)
ax[0].set_title(f"Genre dari IMU sintetis 10 node: {acc10:.1%} (5 node: {acc5:.1%})")
ax[1].barh(list(acc_drop), list(acc_drop.values()), color="#d2a54a"); ax[1].set_title("Penurunan akurasi bila node dimatikan")
fig.tight_layout(); fig.savefig(f"{OUT}/confusion_aist.png", dpi=130); print("SELESAI", flush=True)
