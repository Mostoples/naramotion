"""NaraMotion · Kaggle kernel 3: pengenal tari dari sensor IMU (uji pipeline sensor sebelum node GY-85 siap).

Data: "Turkish Folk Dance IMU Dataset" (berkaykarakis, Kaggle, CC BY 4.0): 5 node ESP32-C6 + MPU6050
(akselerometer + giroskop) di kaki kanan, tangan kanan, kaki kiri, tangan kiri, pinggang; 3 tari (Artvin, Süslü, Teke); 3 penari.
Validasi: leave-one-subject-out (model diuji pada penari yang tidak pernah dilihat).
Ablasi: akurasi bila satu node dimatikan → node mana paling penting untuk desain perangkat.
Keluaran: metrics_imu.json, model_imu.onnx (dilatih pada semua penari), confusion_imu.png.
"""
import os, glob, json, random, unicodedata
import numpy as np, pandas as pd, torch, torch.nn as nn, torch.nn.functional as F

SRC = (glob.glob("/kaggle/input/**/all_clean.csv", recursive=True) or glob.glob(os.environ.get("IMU_CSV", "")))[0]
OUT = os.environ.get("OUT", "/kaggle/working"); os.makedirs(OUT, exist_ok=True)
HZ, WIN, HOP = 50, 200, 50          # 50 Hz, jendela 4 s, geser 1 s
NODES = {1: "kaki kanan", 2: "tangan kanan", 3: "kaki kiri", 4: "tangan kiri", 5: "pinggang"}
CH = ["Ax", "Ay", "Az", "Gx", "Gy", "Gz"]
EPOCHS = int(os.environ.get("EPOCHS", 40)); SEED = 7
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
dev = "cuda" if torch.cuda.is_available() else "cpu"

d = pd.read_csv(SRC)
d["Label"] = d["Label"].map(lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode() or "Suslu")
classes = sorted(d.Label.unique()); subjects = sorted(d.Subject.unique())
print(len(d), "baris", classes, subjects, flush=True)

# satu sesi = (penari, tari, pengulangan); 5 node diselaraskan ke kisi 50 Hz bersama
sessions = []
for (sub, lab, rep), g in d.groupby(["Subject", "Label", "TekrarNo"]):
    per = {n: gg.sort_values("time_sec") for n, gg in g.groupby("NodeNo")}
    if len(per) < 5: continue
    t0 = max(p.time_sec.min() for p in per.values()); t1 = min(p.time_sec.max() for p in per.values())
    grid = np.arange(t0, t1, 1 / HZ)
    if len(grid) < WIN: continue
    X = np.concatenate([np.stack([np.interp(grid, per[n].time_sec, per[n][c]) for c in CH], 1) for n in sorted(NODES)], 1)
    sessions.append(dict(sub=sub, y=classes.index(lab), X=X.astype(np.float32)))
print(len(sessions), "sesi", flush=True)

def windows(sel):
    X, Y = [], []
    for s in sel:
        for a in range(0, len(s["X"]) - WIN + 1, HOP): X.append(s["X"][a:a + WIN]); Y.append(s["y"])
    return np.stack(X), np.array(Y)

class Net(nn.Module):
    def __init__(s, cin, C, w=96):
        super().__init__()
        s.f = nn.Sequential(nn.Conv1d(cin, w, 7, padding=3), nn.BatchNorm1d(w), nn.GELU(),
                            nn.Conv1d(w, w, 5, padding=4, dilation=2), nn.BatchNorm1d(w), nn.GELU(),
                            nn.Conv1d(w, w, 5, padding=8, dilation=4), nn.BatchNorm1d(w), nn.GELU())
        s.h = nn.Sequential(nn.Dropout(0.3), nn.Linear(2 * w, C))
    def forward(s, x): h = s.f(x); return s.h(torch.cat([h.mean(-1), h.amax(-1)], 1))

def fit(Xtr, Ytr):
    mu, sd = Xtr.reshape(-1, Xtr.shape[-1]).mean(0), Xtr.reshape(-1, Xtr.shape[-1]).std(0) + 1e-6
    m = Net(Xtr.shape[-1], len(classes)).to(dev); opt = torch.optim.AdamW(m.parameters(), 2e-3, weight_decay=0.05)
    Xt = torch.tensor((Xtr - mu) / sd).permute(0, 2, 1); Yt = torch.tensor(Ytr)
    for ep in range(EPOCHS):
        m.train(); idx = torch.randperm(len(Xt))
        for i in range(0, len(idx), 64):
            b = idx[i:i + 64]; x = Xt[b]
            x = x * (1 + 0.1 * torch.randn(x.shape[0], x.shape[1], 1)) + 0.05 * torch.randn_like(x)  # skala & derau per kanal
            loss = F.cross_entropy(m(x.to(dev)), Yt[b].to(dev), label_smoothing=0.1)
            opt.zero_grad(); loss.backward(); opt.step()
    return m.eval(), mu, sd

def predict(m, mu, sd, X, drop=None):
    X = (X - mu) / sd
    if drop is not None: X = X.copy(); X[..., (drop - 1) * 6:drop * 6] = 0   # node mati → nilai rata-rata
    with torch.no_grad(): return m(torch.tensor(X).permute(0, 2, 1).float().to(dev)).argmax(1).cpu().numpy()

res, cm, abl = {}, np.zeros((len(classes), len(classes)), int), {n: [] for n in NODES}
for s in subjects:
    tr = [x for x in sessions if x["sub"] != s]; te = [x for x in sessions if x["sub"] == s]
    Xtr, Ytr = windows(tr); Xte, Yte = windows(te)
    m, mu, sd = fit(Xtr, Ytr); p = predict(m, mu, sd, Xte)
    res[s] = round(float((p == Yte).mean()), 4)
    for a, b in zip(Yte, p): cm[a, b] += 1
    for n in NODES: abl[n].append(float((predict(m, mu, sd, Xte, drop=n) == Yte).mean()))
    print("uji pada", s, res[s], flush=True)

loso = float(np.mean(list(res.values())))
ablation = {NODES[n]: round(loso - float(np.mean(v)), 4) for n, v in abl.items()}
print("LOSO", loso, "penurunan akurasi bila node dimatikan:", ablation, flush=True)

Xall, Yall = windows(sessions); m, mu, sd = fit(Xall, Yall)
class Wrap(nn.Module):
    def __init__(s, m, mu, sd): super().__init__(); s.m = m; s.register_buffer("mu", torch.tensor(mu)); s.register_buffer("sd", torch.tensor(sd))
    def forward(s, x): return s.m(((x - s.mu) / s.sd).permute(0, 2, 1))   # x: (b, 200, 30) mentah
torch.onnx.export(Wrap(m.cpu(), mu, sd).eval(), torch.zeros(1, WIN, 30), f"{OUT}/model_imu.onnx", input_names=["imu"], output_names=["logits"],
                  dynamic_axes={"imu": {0: "b"}}, opset_version=17, dynamo=False)
json.dump(dict(classes=classes, loso_acc=round(loso, 4), per_subject=res, confusion=cm.tolist(), ablation_drop=ablation,
               window_s=WIN / HZ, hz=HZ, nodes=NODES, channels=CH, n_sessions=len(sessions),
               source="Turkish Folk Dance IMU Dataset (berkaykarakis, Kaggle), CC BY 4.0"), open(f"{OUT}/metrics_imu.json", "w"), indent=1, ensure_ascii=False)

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].imshow(cm, cmap="YlOrBr"); ax[0].set_xticks(range(len(classes)), classes); ax[0].set_yticks(range(len(classes)), classes)
for i in range(len(classes)):
    for j in range(len(classes)): ax[0].text(j, i, cm[i, j], ha="center", va="center", fontsize=8)
ax[0].set_title(f"Leave-one-subject-out {loso:.1%}"); ax[0].set_xlabel("prediksi"); ax[0].set_ylabel("label")
ax[1].barh(list(ablation), list(ablation.values()), color="#d2a54a"); ax[1].set_title("Penurunan akurasi bila node dimatikan")
fig.tight_layout(); fig.savefig(f"{OUT}/confusion_imu.png", dpi=130); print("SELESAI", flush=True)
