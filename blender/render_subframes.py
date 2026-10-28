"""Render ulang scene .blend pada fps lebih tinggi lewat sub-frame (animasi tidak berubah), mis. 24 → 60 fps.
Pemakaian: blender -b <file.blend> -S <scene> -P blender/render_subframes.py -- --old a-b --mult 2.5 --out DIR
Frame keluaran bernomor global: k = (old_frame - 1) * mult + 1 … (melewati frame yang sudah ada).
"""
import bpy, sys, os, math, argparse, time
ap = argparse.ArgumentParser(); ap.add_argument("--old", required=True); ap.add_argument("--mult", type=float, default=2.5); ap.add_argument("--out", required=True)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
lo, hi = (int(v) for v in a.old.split("-")); sc = bpy.context.scene; os.makedirs(a.out, exist_ok=True)
sc.eevee.shadow_pool_size = "1024"
k0, k1 = round((lo - 1) * a.mult) + 1, round(hi * a.mult)
for k in range(k0, k1 + 1):
    fp = os.path.join(a.out, f"{k:04d}.png")
    if os.path.exists(fp) and os.path.getsize(fp) > 0: continue
    f = 1 + (k - 1) / a.mult; fi = math.floor(f); t = time.time()
    sc.frame_set(fi, subframe=f - fi); sc.render.filepath = fp + ".tmp.png"
    bpy.ops.render.render(write_still=True); os.replace(fp + ".tmp.png", fp)
    print(f"[sub] {sc.name} k={k} old={f:.2f} {time.time()-t:.1f}s", flush=True)
