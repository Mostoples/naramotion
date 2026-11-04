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
A = a.parse_args(sys.argv[sys.argv.index("--") + 1:])
P_ = "mixamorig:"

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
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=A.rig)
    for o in list(bpy.data.objects):
        if o.type == "MESH" and not any(m.type == "ARMATURE" for m in o.modifiers): bpy.data.objects.remove(o)   # bola latar
    for act in list(bpy.data.actions): bpy.data.actions.remove(act)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    arm.animation_data_clear()
    for pb in arm.pose.bones: pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    return arm

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
    rig_leg = (rest[P_ + "LeftLeg"] - rest[P_ + "LeftUpLeg"]).length + (rest[P_ + "LeftFoot"] - rest[P_ + "LeftLeg"]).length
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
        c = pb[P_ + bone].constraints.new("DAMPED_TRACK"); c.target = E[target]; c.track_axis = "TRACK_Y"
    def locked(bone, target, ref_rest):
        c = pb[P_ + bone].constraints.new("LOCKED_TRACK"); c.target = E[target]; c.lock_axis = "LOCK_Y"
        c.track_axis = best_axis(arm, P_ + bone, ref_rest)
    sc.frame_set(1)
    c = pb[P_ + "Hips"].constraints.new("COPY_LOCATION"); c.target = E["pelvis"]
    damped("Hips", "chest"); locked("Hips", "hipL", rest[P_ + "LeftUpLeg"])
    damped("Spine", "chest"); damped("Spine1", "neck"); damped("Spine2", "neck"); locked("Spine2", "shL", rest[P_ + "LeftArm"])
    damped("Neck", "headc"); damped("Head", "headtop"); locked("Head", "earL", rest[P_ + "Head"] + Vector((0.08, 0, 0.05)))
    for sd, side in (("L", "Left"), ("R", "Right")):
        damped(f"{side}Shoulder", f"sh{sd}"); damped(f"{side}Arm", f"el{sd}"); damped(f"{side}ForeArm", f"wr{sd}")
        damped(f"{side}Hand", f"Middle0{sd}"); locked(f"{side}Hand", f"Index0{sd}", rest[P_ + f"{side}HandIndex1"])
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
            b = pb[P_ + bone]; h = arm.matrix_world @ b.head; tl = arm.matrix_world @ b.tail
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
    bpy.ops.export_scene.gltf(filepath=job["out"], export_format="GLB", export_animations=True, export_force_sampling=True, export_frame_range=True,
                              export_apply=False, export_yup=True)
    return dict(out=job["out"], frames=f_end, scale=round(s, 3), dir_err_deg=round(float(np.mean(errs)), 2), dir_err_max=round(float(np.max(errs)), 2))

rep = [retarget(j) for j in json.load(open(A.jobs))]
for r in rep: print("[retarget]", json.dumps(r))
if A.report: json.dump(rep, open(A.report, "w"), indent=1)
