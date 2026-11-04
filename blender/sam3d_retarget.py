"""Retarget hasil digitalisasi SAM 3D Body (70 titik MHR, termasuk ruas jari) ke rig karakter Mixamo (Y Bot) → .glb beranimasi.
Cara: titik 3D tiap frame → empty beranimasi; tiap tulang diarahkan (Damped Track) ke titik ujungnya, putaran (twist)
pinggul, dada, kepala, dan telapak dikunci ke titik samping (Locked Track); lalu di-bake (visual keying) dan diekspor.
Pemakaian:
  blender -b --factory-startup -P blender/sam3d_retarget.py -- --jobs jobs.json --rig assets/ml/anim/m2mr/putri__Agem_Kanan.glb
  jobs.json = [{"npz": ".../Agem_Kanan_66.npz", "out": "assets/ml/rig/putri__Agem_Kanan.glb"}, ...]
"""
import bpy, sys, json, math, argparse
import numpy as np
from mathutils import Vector

a = argparse.ArgumentParser(); a.add_argument("--jobs"); a.add_argument("--rig"); a.add_argument("--fps", type=int, default=30); a.add_argument("--report", default="")
a.add_argument("--map", default="mixamo", choices=["mixamo", "rigify"]); a.add_argument("--armature", default="")
a.add_argument("--anim-only", action="store_true", help="ekspor kerangka + animasi saja (tanpa mesh); karakter dimuat terpisah di web")
a.add_argument("--base-out", default="", help="ekspor karakter (mesh + kerangka, tanpa animasi) sekali ke berkas ini")
A = a.parse_args(sys.argv[sys.argv.index("--") + 1:])
P_ = ""
# nama tulang gaya Mixamo → nama tulang rig sasaran
SIDES = (("Left", "L"), ("Right", "R"))
RIGIFY = {"Hips": "DEF-spine", "Spine": "DEF-spine.001", "Spine1": "DEF-spine.002", "Spine2": "DEF-spine.003", "Neck": "DEF-spine.004", "Head": "DEF-spine.006"}
for side, sd in SIDES:
    RIGIFY.update({f"{side}Shoulder": f"DEF-shoulder.{sd}", f"{side}Arm": f"DEF-upper_arm.{sd}", f"{side}ForeArm": f"DEF-forearm.{sd}", f"{side}Hand": f"DEF-hand.{sd}",
                   f"{side}UpLeg": f"DEF-thigh.{sd}", f"{side}Leg": f"DEF-shin.{sd}", f"{side}Foot": f"DEF-foot.{sd}"})
    for k in (1, 2, 3):
        RIGIFY[f"{side}HandThumb{k}"] = f"DEF-thumb.0{k}.{sd}"
        for fn, rn in (("Index", "f_index"), ("Middle", "f_middle"), ("Ring", "f_ring"), ("Pinky", "f_pinky")): RIGIFY[f"{side}Hand{fn}{k}"] = f"DEF-{rn}.0{k}.{sd}"
def BN(n): return RIGIFY[n] if A.map == "rigify" else "mixamorig:" + n

# ---- titik MHR70 yang dipakai (indeks sama dengan tools/sam3d_to_web.py) ----
K = dict(nose=0, earL=3, earR=4, shL=5, shR=6, elL=7, elR=8, hipL=9, hipR=10, knL=11, knR=12, anL=13, anR=14, toeL=15, toeR=18,
         wrL=62, wrR=41, neck=69)
FINGERS = ["Thumb", "Index", "Middle", "Ring", "Pinky"]
def finger_pts(side, f):   # [MCP, PIP, DIP, ujung] untuk jari ke-f (0 = ibu jari)
    off = 21 if side == "L" else 0; tip = 21 + off + 4 * f
    return [tip + 3, tip + 2, tip + 1, tip]

def load_points(npz):
    d = np.load(npz); P = d["kp3d"].astype(np.float32); t = d["t"].astype(float)
    P = np.stack([P[..., 0], -P[..., 1], -P[..., 2]], -1)                # kamera → dunia (y atas, menghadap +z, kiri = +x)
    if len(P) >= 3: P[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
    pel = (P[:, 9] + P[:, 10]) / 2
    P[..., 0] -= pel[:, None, 0]; P[..., 2] -= pel[:, None, 2]
    P[..., 1] -= P[:, [13, 14, 15, 18], 1].min(1)[:, None]            # kaki di lantai
    B = np.stack([P[..., 0], -P[..., 2], P[..., 1]], -1)                # dunia → Blender (z atas, menghadap -y, kiri = +x)
    return B, t - t[0]

def setup_scene():
    if A.rig.lower().endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=A.rig)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=A.rig)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    arm = next((o for o in arms if o.name == A.armature), arms[0])
    for o in list(bpy.data.objects):   # buang bola latar, widget Rigify, metarig, objek non-karakter
        skinned = o.type == "MESH" and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)
        if o is not arm and not skinned and not (o.parent is arm and o.type == "MESH"): bpy.data.objects.remove(o)
    for act in list(bpy.data.actions): bpy.data.actions.remove(act)
    arm.animation_data_clear()
    for pb in arm.pose.bones:
        # rig Rigify: tulang DEF utama digerakkan langsung (constraint ke kontrol dilepas); tulang bantu (helper) tetap mengikuti
        if A.map != "rigify" or (pb.name.startswith("DEF-") and "helper" not in pb.name):
            for c in list(pb.constraints): pb.constraints.remove(c)
        pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
    for d in (list(arm.data.collections_all) if hasattr(arm.data, "collections_all") else []): d.is_visible = True   # semua tulang terlihat → ikut di-bake
    for bn in arm.data.bones: bn.hide = False
    if A.map == "rigify": reparent_def(arm)
    return arm

def reparent_def(arm):
    """Rigify: tulang DEF (termasuk wajah) disambungkan ke DEF terdekat mengikuti hierarki ORG, lalu semua constraint DEF dilepas,
    sehingga seluruh mesh ikut kerangka DEF yang kita gerakkan (tanpa kontrol/MCH yang diam)."""
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="EDIT"); eb = arm.data.edit_bones
    for b in eb:
        if not b.name.startswith("DEF-"): continue
        base = b.name[4:]; org = eb.get("ORG-" + base); par = (org.parent if org else b.parent)
        while par is not None:
            cand = eb.get("DEF-" + par.name.split("-", 1)[-1]) if "-" in par.name else eb.get("DEF-" + par.name)
            if cand is not None and cand != b: break
            par = par.parent
        if par is not None and cand is not None: b.use_connect = False; b.parent = cand
        elif b.name != "DEF-spine": b.use_connect = False; b.parent = eb.get("DEF-spine")
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        if pb.name.startswith("DEF-"):
            for c in list(pb.constraints): pb.constraints.remove(c)
    bpy.ops.object.mode_set(mode="OBJECT")

def best_axis(arm, bone, ref_world):
    """sumbu lokal (±X/±Z) tulang yang paling searah dengan titik acuan pada pose istirahat → dipakai untuk Locked Track"""
    b = arm.data.bones[bone]; M = arm.matrix_world @ b.matrix_local; head = M.translation
    d = (ref_world - head); d -= d.project(M.to_3x3().col[1]); d.normalize()
    best = max([("TRACK_X", M.to_3x3().col[0]), ("TRACK_NEGATIVE_X", -M.to_3x3().col[0]), ("TRACK_Z", M.to_3x3().col[2]), ("TRACK_NEGATIVE_Z", -M.to_3x3().col[2])],
               key=lambda kv: kv[1].normalized().dot(d))
    return best[0]

def retarget(job):
    arm = setup_scene(); sc = bpy.context.scene; sc.render.fps = A.fps
    B, t = load_points(job["npz"])
    rest = {b.name: (arm.matrix_world @ b.head_local) for b in arm.data.bones}
    # skala dari panjang kaki (paha + betis), tidak bergantung pose (posisi rendah seperti Ngelo tidak mengacaukan skala)
    rig_leg = (rest[BN("LeftLeg")] - rest[BN("LeftUpLeg")]).length + (rest[BN("LeftFoot")] - rest[BN("LeftLeg")]).length
    seg = lambda i, j: np.linalg.norm(B[:, i] - B[:, j], axis=1)
    data_leg = float(np.median((seg(9, 11) + seg(11, 13) + seg(10, 12) + seg(12, 14)) / 2))
    s = rig_leg / max(1e-3, data_leg)
    B = B * s
    # titik turunan
    def mid(i, j): return (B[:, i] + B[:, j]) / 2
    pts = {k: B[:, i] for k, i in K.items()}
    pts["pelvis"] = mid(9, 10); pts["headc"] = mid(3, 4)
    pts["chest"] = pts["pelvis"] + (pts["neck"] - pts["pelvis"]) * 0.75
    pts["headtop"] = pts["headc"] + (pts["headc"] - pts["neck"]) * 0.9
    for sd in "LR":
        for f, name in enumerate(FINGERS):
            for k, idx in enumerate(finger_pts(sd, f)): pts[f"{name}{k}{sd}"] = B[:, idx]
    # empty beranimasi
    col = bpy.data.collections.new("target"); sc.collection.children.link(col); E = {}
    frames = [1 + round(x * A.fps) for x in t]; f_end = frames[-1]
    for name, arr in pts.items():
        e = bpy.data.objects.new("T_" + name, None); col.objects.link(e); E[name] = e
        for fr, p in zip(frames, arr):
            e.location = Vector(map(float, p)); e.keyframe_insert("location", frame=fr)
    sc.frame_start, sc.frame_end = 1, f_end
    pb = arm.pose.bones
    def damped(bone, target):
        c = pb[BN(bone)].constraints.new("DAMPED_TRACK"); c.target = E[target]; c.track_axis = "TRACK_Y"
    def locked(bone, target, ref_rest):
        c = pb[BN(bone)].constraints.new("LOCKED_TRACK"); c.target = E[target]; c.lock_axis = "LOCK_Y"
        c.track_axis = best_axis(arm, BN(bone), ref_rest)
    sc.frame_set(1)
    c = pb[BN("Hips")].constraints.new("COPY_LOCATION"); c.target = E["pelvis"]
    damped("Hips", "chest"); locked("Hips", "hipL", rest[BN("LeftUpLeg")])
    damped("Spine", "chest"); damped("Spine1", "neck"); damped("Spine2", "neck"); locked("Spine2", "shL", rest[BN("LeftArm")])
    damped("Neck", "headc"); damped("Head", "headtop"); locked("Head", "earL", rest[BN("Head")] + Vector((0.08, 0, 0.05)))
    for sd, side in (("L", "Left"), ("R", "Right")):
        damped(f"{side}Shoulder", f"sh{sd}"); damped(f"{side}Arm", f"el{sd}"); damped(f"{side}ForeArm", f"wr{sd}")
        damped(f"{side}Hand", f"Middle0{sd}"); locked(f"{side}Hand", f"Index0{sd}", rest[BN(f"{side}HandIndex1")])
        damped(f"{side}UpLeg", f"kn{sd}"); damped(f"{side}Leg", f"an{sd}"); damped(f"{side}Foot", f"toe{sd}")
        for name in FINGERS:
            if name == "Thumb": damped(f"{side}HandThumb1", f"Thumb1{sd}"); damped(f"{side}HandThumb2", f"Thumb2{sd}"); damped(f"{side}HandThumb3", f"Thumb3{sd}")
            else: damped(f"{side}Hand{name}1", f"{name}1{sd}"); damped(f"{side}Hand{name}2", f"{name}2{sd}"); damped(f"{side}Hand{name}3", f"{name}3{sd}")
    # ukur galat arah tulang sebelum bake (derajat)
    chk = [("LeftArm", "elL"), ("LeftForeArm", "wrL"), ("RightArm", "elR"), ("RightForeArm", "wrR"), ("LeftUpLeg", "knL"), ("RightLeg", "anR"), ("RightHandIndex1", "Index1R")]
    errs = []
    for fr in frames[:: max(1, len(frames) // 6)]:
        sc.frame_set(fr); bpy.context.view_layer.update()
        for bone, tg in chk:
            b = pb[BN(bone)]; h = arm.matrix_world @ b.head; tl = arm.matrix_world @ b.tail
            v1 = (tl - h).normalized(); v2 = (E[tg].matrix_world.translation - h).normalized()
            errs.append(math.degrees(math.acos(max(-1, min(1, v1.dot(v2))))))
    # bake → aksi biasa, hapus constraint & empty
    bpy.context.view_layer.objects.active = arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode="POSE"); bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.nla.bake(frame_start=1, frame_end=f_end, step=1, only_selected=True, visual_keying=True, clear_constraints=True, use_current_action=True, bake_types={"POSE"})
    bpy.ops.object.mode_set(mode="OBJECT")
    if arm.animation_data and arm.animation_data.action: arm.animation_data.action.name = job.get("name", "tari")
    for e in E.values(): bpy.data.objects.remove(e)
    bpy.data.collections.remove(col)
    if A.anim_only:
        for o in list(bpy.data.objects):
            if o is not arm: bpy.data.objects.remove(o)
    bpy.ops.export_scene.gltf(filepath=job["out"], export_format="GLB", export_animations=True, export_force_sampling=True, export_frame_range=True, export_def_bones=(A.map == "rigify"),
                              export_apply=False, export_yup=True)
    return dict(out=job["out"], frames=f_end, scale=round(s, 3), dir_err_deg=round(float(np.mean(errs)), 2), dir_err_max=round(float(np.max(errs)), 2))

if A.base_out:
    arm = setup_scene()
    bpy.ops.export_scene.gltf(filepath=A.base_out, export_format="GLB", export_animations=False, export_def_bones=(A.map == "rigify"), export_apply=False, export_yup=True)
    print("[retarget] karakter dasar →", A.base_out)
rep = [retarget(j) for j in json.load(open(A.jobs))] if A.jobs else []
for r in rep: print("[retarget]", json.dumps(r))
if A.report: json.dump(rep, open(A.report, "w"), indent=1)
