"""NaraMotion · Kaggle kernel 2: pengenal gerak dasar tari Bali dari keypoint RTMW (keluaran kernel ekstraksi).

Untuk tiap dataset yang ditemukan (putri: 13 gerak, putra: 11 gerak) dilatih dua varian:
  whole133 — 133 titik (tubuh, kaki, wajah, tangan): akurasi tertinggi, untuk riset/laporan.
  body17   — 17 titik tubuh COCO: masukan yang sama dengan MediaPipe di browser → dipakai Kelas Tari (kamera).
Model: TCN 1-D kecil; titik dinormalisasi ke pinggul & panjang badan. Tanpa flip horizontal (Agem Kanan/Kiri).
Keluaran per <tag>_<varian>: model.onnx, metrics.json, confusion.png; plus templates_<tag>_body17.json (gerak acuan
rata-rata per kelas, 64 frame × 17 titik) untuk skor kemiripan di aplikasi.
"""
import os, json, glob, time, random
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F

OUT = os.environ.get("OUT", "/kaggle/working"); T = 64; SEED = 7
ROOT = os.environ.get("SRC_ROOT", "/kaggle/input")
EPOCHS = int(os.environ.get("EPOCHS", 80))
dev = "cuda" if torch.cuda.is_available() else "cpu"
VARIANTS = {"whole133": 133, "body17": 17}

def normalise(k, s, n):
    """k (T,133,2) piksel, s (T,133) → (T,n,3): x,y relatif pinggul / panjang badan, plus skor."""
    k = k[:, :n].astype(np.float32); s = s[:, :n].astype(np.float32)
    k[~np.isfinite(k)] = 0; s[~np.isfinite(s)] = 0
    hip = (k[:, 11] + k[:, 12]) / 2; sh = (k[:, 5] + k[:, 6]) / 2
    torso = np.linalg.norm(sh - hip, axis=1); good = (s[:, [5, 6, 11, 12]].min(1) > 0.3) & (torso > 1)
    if good.sum() == 0: good[:] = True
    c = np.median(hip[good], 0); L = np.median(torso[good])
    x = (k - c) / max(L, 1.0)
    x[s < 0.3] = 0
    vis = (s >= 0.3).astype(np.float32)   # kanal visibilitas biner: skor RTMW vs MediaPipe tidak sebanding
    return np.concatenate([x, vis[..., None]], -1)

def resample(x, n=T):
    idx = np.linspace(0, len(x) - 1, n); i0 = np.floor(idx).astype(int); i1 = np.minimum(i0 + 1, len(x) - 1); w = (idx - i0)[:, None, None]
    return x[i0] * (1 - w) + x[i1] * w

def feats(x):
    """(T',n,3) → (64, n*5): x, y, skor, vx, vy — urutan yang sama dipakai di browser."""
    x = resample(x); v = np.diff(x[..., :2], axis=0, prepend=x[:1, :, :2])
    return np.concatenate([x, v * 4], -1).reshape(T, -1)

class Block(nn.Module):
    def __init__(s, c, d): super().__init__(); s.c1 = nn.Conv1d(c, c, 5, padding=2 * d, dilation=d); s.b1 = nn.BatchNorm1d(c); s.c2 = nn.Conv1d(c, c, 1); s.b2 = nn.BatchNorm1d(c)
    def forward(s, x): return F.gelu(x + s.b2(s.c2(F.gelu(s.b1(s.c1(x))))))
class TCN(nn.Module):
    def __init__(s, cin, C, w=192):
        super().__init__(); s.inp = nn.Sequential(nn.Dropout(0.1), nn.Conv1d(cin, w, 1), nn.BatchNorm1d(w), nn.GELU())
        s.blocks = nn.Sequential(*[Block(w, d) for d in (1, 2, 4, 8)]); s.head = nn.Sequential(nn.Dropout(0.3), nn.Linear(w * 2, C))
    def forward(s, x): h = s.blocks(s.inp(x)); return s.head(torch.cat([h.mean(-1), h.amax(-1)], 1))
class Wrap(nn.Module):
    """Masukan ONNX: (b, 64, n*5) — browser cukup mengirim fitur per frame tanpa permute."""
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, x): return torch.softmax(s.m(x.permute(0, 2, 1)), -1)

def augment(x):
    n = len(x); a = random.randint(0, n // 6); b = n - random.randint(0, n // 6); x = x[a:max(b, a + 8)].copy()
    th = np.deg2rad(random.uniform(-10, 10)); R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]], np.float32)
    x[..., :2] = (x[..., :2] @ R.T) * random.uniform(0.9, 1.1) + np.random.normal(0, 0.01, x[..., :2].shape)
    on = x[..., 2:3] > 0
    x[..., :2] += np.random.normal(0, 0.03, (1, x.shape[1], 2)) * on   # geser tetap per titik: beda letak titik MediaPipe vs RTMW
    drop = np.random.rand(x.shape[1]) < 0.08; x[:, drop] = 0          # titik hilang acak (oklusi/visibilitas rendah)
    return x

def fit_one(tag, data, classes, n, seed, init=None):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    C = len(classes); cin = n * 5; model = TCN(cin, C).to(dev)
    if init is not None:   # transfer: semua bobot kecuali kepala klasifikasi
        model.load_state_dict({k: v for k, v in init.items() if not k.startswith("head.")}, strict=False)
    opt = torch.optim.AdamW(model.parameters(), 2e-3, weight_decay=0.05)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=EPOCHS * ((len(data["train"]) + 31) // 32))
    def batch(items, aug): return (torch.tensor(np.stack([feats(augment(x) if aug else x) for x, _ in items])).permute(0, 2, 1).float(),
                                   torch.tensor([y for _, y in items]))
    def evaluate(items):
        model.eval(); P = []
        with torch.no_grad():
            for i in range(0, len(items), 64): P.append(model(batch(items[i:i + 64], False)[0].to(dev)).argmax(1).cpu())
        p = torch.cat(P).numpy(); y = np.array([y for _, y in items]); return float((p == y).mean()), p, y
    best, t0, path = -1, time.time(), f"{OUT}/{tag}_s{seed}.pt"
    tr = list(data["train"])
    for ep in range(EPOCHS):
        model.train(); random.shuffle(tr)
        for i in range(0, len(tr), 32):
            X, y = batch(tr[i:i + 32], True)
            loss = F.cross_entropy(model(X.to(dev)), y.to(dev), label_smoothing=0.1)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        va = evaluate(data["val"])[0]
        if va >= best: best = va; torch.save(model.state_dict(), path)
        if ep % 10 == 0 or ep == EPOCHS - 1: print(f"[{tag}] ep {ep} loss {loss.item():.3f} val {va:.3f} best {best:.3f} {time.time()-t0:.0f}s", flush=True)
    model.load_state_dict(torch.load(path)); return model.eval(), best

class Ens(nn.Module):
    def __init__(s, ms): super().__init__(); s.ms = nn.ModuleList(ms)
    def forward(s, x): return torch.stack([torch.softmax(m(x), -1) for m in s.ms]).mean(0)   # x: (b, cin, 64)

def train_variant(tag, data, classes, n, seeds=(SEED,), init=None):
    fits = [fit_one(tag, data, classes, n, sd, init) for sd in seeds]
    ens = Ens([m for m, _ in fits]).to(dev).eval(); best = float(np.mean([b for _, b in fits]))
    C = len(classes); cin = n * 5
    def predict(items):
        P = []
        with torch.no_grad():
            for i in range(0, len(items), 64):
                X = torch.tensor(np.stack([feats(x) for x, _ in items[i:i + 64]])).permute(0, 2, 1).float().to(dev); P.append(ens(X).argmax(1).cpu())
        return torch.cat(P).numpy()
    p = predict(data["test"]); y = np.array([y for _, y in data["test"]]); te = float((p == y).mean())
    va = float((predict(data["val"]) == np.array([y for _, y in data["val"]])).mean())
    cm = np.zeros((C, C), int)
    for a, b in zip(y, p): cm[a, b] += 1
    per = {classes[i]: round(float(cm[i, i] / max(cm[i].sum(), 1)), 3) for i in range(C)}
    json.dump(dict(tag=tag, classes=classes, val_best=round(va, 4), seeds=list(seeds), transfer=init is not None, test_acc=round(te, 4), per_class=per,
                   confusion=cm.tolist(), n={k: len(v) for k, v in data.items()}, T=T, keypoints=n,
                   features="per titik: x, y, terlihat(0/1), vx*4, vy*4 (urutan COCO-WholeBody)",
                   normalisation="pusat = median titik tengah pinggul (11,12); skala = median jarak bahu-pinggul; skor<0.3 → 0"),
              open(f"{OUT}/{tag}_metrics.json", "w"), indent=1)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 7)); ax.imshow(cm, cmap="YlOrBr")
    ax.set_xticks(range(C), classes, rotation=60, ha="right", fontsize=8); ax.set_yticks(range(C), classes, fontsize=8)
    for i in range(C):
        for j in range(C):
            if cm[i, j]: ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=7)
    ax.set_xlabel("prediksi"); ax.set_ylabel("label"); ax.set_title(f"{tag} · akurasi uji {te:.1%}")
    fig.tight_layout(); fig.savefig(f"{OUT}/{tag}_confusion.png", dpi=130); plt.close(fig)
    ens = ens.cpu().eval(); torch.save(fits[0][0].state_dict(), f"{OUT}/{tag}_model.pt")
    class Out(nn.Module):
        def __init__(s, e): super().__init__(); s.e = e
        def forward(s, x): return s.e(x.permute(0, 2, 1))     # masukan ONNX: (b, 64, n*5)
    torch.onnx.export(Out(ens).eval(), torch.zeros(1, T, cin), f"{OUT}/{tag}_model.onnx", input_names=["x"], output_names=["prob"],
                      dynamic_axes={"x": {0: "b"}}, opset_version=17, dynamo=False)
    print(f"[{tag}] UJI {te:.4f} val {va:.4f}", per, flush=True)
    return te, fits[0][0].state_dict()

summary, pretrained = {}, {}
srcs = sorted(glob.glob(f"{ROOT}/**/index.json", recursive=True), key=lambda p: "male" in p.lower())   # putri dulu
for src in srcs:
    D = os.path.dirname(src); index = json.load(open(src))
    ds = "putra" if "male" in D.lower() or any("Malpal" in r["cls"] for r in index) else "putri"
    classes = sorted({r["cls"] for r in index})
    npz = {s: np.load(f"{D}/poses_{s}.npz") for s in ("train", "val", "test") if os.path.exists(f"{D}/poses_{s}.npz")}
    raw = {"train": [], "val": [], "test": []}
    for r in index:
        key = f"{r['split']}__{r['cls']}__{r['clip']}"
        if r["split"] not in npz or key + "__kpts" not in npz[r["split"]]: continue
        k, s = npz[r["split"]][key + "__kpts"], npz[r["split"]][key + "__score"]
        if len(k) >= 8: raw[r["split"]].append((k, s, classes.index(r["cls"])))
    print(ds, {k: len(v) for k, v in raw.items()}, classes, flush=True)
    for var, n in VARIANTS.items():
        data = {sp: [(normalise(k, s, n), y) for k, s, y in v] for sp, v in raw.items()}
        if ds == "putri": te, sd_ = train_variant(f"{ds}_{var}", data, classes, n); pretrained[var] = sd_
        else: te, _ = train_variant(f"{ds}_{var}", data, classes, n, seeds=(SEED, SEED + 1, SEED + 2), init=pretrained.get(var))
        summary[f"{ds}_{var}"] = te
        if var == "body17":   # gerak acuan rata-rata per kelas (train + val) untuk skor kemiripan
            # 6 exemplar per kelas (k-means → anggota terdekat pusat): mewakili 3 sudut kamera & beragam penari,
            # sehingga aplikasi membandingkan siswa dengan contoh acuan yang paling mirip sudut pandangnya.
            tpl = {}
            for ci, c in enumerate(classes):
                xs = np.stack([resample(x)[..., :2] for x, y in data["train"] + data["val"] if y == ci]); F_ = xs.reshape(len(xs), -1)
                k = min(6, len(xs)); rng = np.random.default_rng(SEED); C_ = F_[rng.choice(len(F_), k, replace=False)]
                for _ in range(25):
                    lab = ((F_[:, None] - C_[None]) ** 2).sum(-1).argmin(1)
                    C_ = np.stack([F_[lab == j].mean(0) if (lab == j).any() else C_[j] for j in range(k)])
                ex = [int(((F_ - C_[j]) ** 2).sum(-1).argmin()) for j in range(k)]
                tpl[c] = dict(exemplars=[np.round(xs[i], 3).tolist() for i in dict.fromkeys(ex)], n=len(xs))
            # kalibrasi skor: galat sudut DTW (sama dengan js/camera.js) klip uji vs exemplar terbaik gerak benar / salah
            def seg_ang(F):
                mid = lambda a, b: (F[:, a] + F[:, b]) / 2
                P = {-1: mid(11, 12), -2: mid(5, 6)}; g = lambda i: P[i] if i < 0 else F[:, i]
                S_ = [(-2, 0), (-1, -2), (5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16)]
                return np.stack([np.arctan2(*(g(b) - g(a))[:, ::-1].T) for a, b in S_], 1)   # (64,10)
            def dtw_err(A, B):
                a, b = seg_ang(A), seg_ang(B); d = np.abs(a[:, None] - b[None]) % (2 * np.pi); d = np.degrees(np.minimum(d, 2 * np.pi - d))
                C = d.mean(-1); n = len(C); D = np.full((n + 1, n + 1), np.inf); D[0, 0] = 0
                for i in range(1, n + 1):
                    for j in range(max(1, i - 20), min(n, i + 20) + 1): D[i, j] = C[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
                i = j = n; path = []
                while i > 0 and j > 0:
                    path.append(C[i - 1, j - 1]); m_ = np.argmin([D[i - 1, j - 1], D[i - 1, j], D[i, j - 1]])
                    i, j = (i - 1, j - 1) if m_ == 0 else (i - 1, j) if m_ == 1 else (i, j - 1)
                return float(np.mean(path))
            true_e, wrong_e = [], []
            for x, y in data["test"][:240]:
                X = resample(x)[..., :2]; X = np.where(np.isfinite(X), X, 0)
                true_e.append(min(dtw_err(X, np.array(e)) for e in tpl[classes[y]]["exemplars"]))
                w_ = (y + 1 + random.randrange(len(classes) - 1)) % len(classes)
                wrong_e.append(min(dtw_err(X, np.array(e)) for e in tpl[classes[w_]]["exemplars"]))
            calib = dict(true_p50=round(float(np.median(true_e)), 2), true_p90=round(float(np.percentile(true_e, 90)), 2),
                         wrong_p50=round(float(np.median(wrong_e)), 2), k=round(float(15 / max(np.median(true_e), 5.0)), 4))
            print(f"[{ds}] kalibrasi skor", calib, flush=True)
            json.dump(dict(dataset=ds, T=T, keypoints="COCO-17", classes=classes, templates=tpl, calib=calib,
                           source="Video Dataset of %s Basic Balinese Dance Movement (Mendeley Data, CC BY 4.0)" % ("Male" if ds == "putra" else "Woman")),
                      open(f"{OUT}/templates_{ds}_body17.json", "w"))
json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=1); print("SELESAI", summary)
