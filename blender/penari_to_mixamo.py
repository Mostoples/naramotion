"""Penari Jawa (rig Rigify, assets_src/penari_rig.blend) → kerangka bersih bergaya Mixamo (mixamorig:*).
Tulang baru ditempatkan pada posisi tulang DEF; bobot tulang wajah, tulang bantu (helper), segmen twist, dan tulang kecil
digabung ke tulang utama terdekat (kepala, leher, panggul, lengan, kaki, jari). Tanpa constraint → aman diretarget.
Keluaran: assets_src/characters/penari_mixamo.blend
Pemakaian: blender -b --factory-startup -P blender/penari_to_mixamo.py
"""
import bpy, re
from mathutils import Vector
SRC = r"C:\Users\mosto\Desktop\nanramotion\assets_src\penari_rig.blend"
OUT = r"C:\Users\mosto\Desktop\nanramotion\assets_src\characters\penari_mixamo.blend"
bpy.ops.wm.open_mainfile(filepath=SRC)
rig = bpy.data.objects["Penari.rig"]
SIDES = (("Left", "L"), ("Right", "R"))
M = {"Hips": "DEF-spine", "Spine": "DEF-spine.001", "Spine1": "DEF-spine.002", "Spine2": "DEF-spine.003", "Neck": "DEF-spine.004", "Head": "DEF-spine.006"}
PARENT = {"Spine": "Hips", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Spine2", "Head": "Neck"}
for side, sd in SIDES:
    M.update({f"{side}Shoulder": f"DEF-shoulder.{sd}", f"{side}Arm": f"DEF-upper_arm.{sd}", f"{side}ForeArm": f"DEF-forearm.{sd}", f"{side}Hand": f"DEF-hand.{sd}",
              f"{side}UpLeg": f"DEF-thigh.{sd}", f"{side}Leg": f"DEF-shin.{sd}", f"{side}Foot": f"DEF-foot.{sd}", f"{side}ToeBase": f"DEF-toe.{sd}"})
    PARENT.update({f"{side}Shoulder": "Spine2", f"{side}Arm": f"{side}Shoulder", f"{side}ForeArm": f"{side}Arm", f"{side}Hand": f"{side}ForeArm",
                   f"{side}UpLeg": "Hips", f"{side}Leg": f"{side}UpLeg", f"{side}Foot": f"{side}Leg", f"{side}ToeBase": f"{side}Foot"})
    for fn, rn in (("Thumb", "thumb"), ("Index", "f_index"), ("Middle", "f_middle"), ("Ring", "f_ring"), ("Pinky", "f_pinky")):
        for k in (1, 2, 3):
            M[f"{side}Hand{fn}{k}"] = f"DEF-{rn}.0{k}.{sd}"; PARENT[f"{side}Hand{fn}{k}"] = f"{side}Hand" if k == 1 else f"{side}Hand{fn}{k - 1}"

def target(g):
    """nama grup bobot DEF → tulang Mixamo pengganti"""
    inv = {v: k for k, v in M.items()}
    if g in inv: return inv[g]
    base = re.sub(r"\.\d{3}$", "", g)                      # segmen twist: DEF-upper_arm.L.001 → DEF-upper_arm.L
    if base in inv: return inv[base]
    sd = "Left" if g.endswith(".L") or ".L." in g else "Right" if g.endswith(".R") or ".R." in g else None
    low = g.lower()
    if "spine.005" in low: return "Neck"
    if any(k in low for k in ("forehead", "temple", "brow", "lid", "eye", "cheek", "nose", "lip", "jaw", "chin", "tongue", "teeth", "ear", "face", "skull")): return "Head"
    if "breast" in low: return "Spine2"
    if "pelvis" in low: return "Hips"
    if sd:
        if "palm" in low: return f"{sd}Hand"
        if "elbow" in low: return f"{sd}ForeArm"
        if "knee" in low: return f"{sd}Leg"
        if "shoulder" in low: return f"{sd}Shoulder"
        if "heel" in low or "foot" in low: return f"{sd}Foot"
        if "toe" in low: return f"{sd}ToeBase"
    return "Head" if "spine.006" in low else "Hips"

# 1) kerangka baru di posisi tulang DEF (koordinat dunia)
bpy.context.view_layer.objects.active = rig
pose_bones = {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local, b.matrix_local) for b in rig.data.bones}
arm_data = bpy.data.armatures.new("PenariMixamo"); arm = bpy.data.objects.new("PenariMixamo", arm_data)
bpy.context.scene.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones
for name, d in M.items():
    h, t, ml = pose_bones[d]; e = eb.new("mixamorig:" + name); e.head, e.tail = h, t
    e.align_roll((rig.matrix_world.to_3x3() @ ml.to_3x3()).col[2])
for name, par in PARENT.items(): eb["mixamorig:" + name].parent = eb["mixamorig:" + par]
bpy.ops.object.mode_set(mode="OBJECT")

# 2) bobot: gabungkan grup DEF ke tulang Mixamo
meshes = [o for o in bpy.data.objects if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == rig for m in o.modifiers)]
import bmesh
for o in meshes:
    # geometri bantu MakeHuman (helper rambut/rok/stoking/bulu mata) aslinya disembunyikan modifier Mask "body" → hapus permanen
    mk = next((m for m in o.modifiers if m.type == "MASK" and m.vertex_group), None)
    if mk and mk.vertex_group in o.vertex_groups:
        gi = o.vertex_groups[mk.vertex_group].index
        keep = {v.index for v in o.data.vertices if any(g.group == gi and g.weight > 0 for g in v.groups)}
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context="VERTS"); bm.to_mesh(o.data); bm.free()
        print("mask", o.name, mk.vertex_group, len(keep), "simpul disimpan")
for o in meshes:
    me = o.data; acc = {}
    idx = {g.index: g.name for g in o.vertex_groups}
    for v in me.vertices:
        w = {}
        for ge in v.groups:
            n = idx.get(ge.group)
            if n and n.startswith("DEF-"): t = target(n); w[t] = w.get(t, 0) + ge.weight
        s = sum(w.values())
        for t, x in w.items(): acc.setdefault(t, []).append((v.index, x / s if s > 0 else 0))
    for g in list(o.vertex_groups): o.vertex_groups.remove(g)
    for t, lst in acc.items():
        vg = o.vertex_groups.new(name="mixamorig:" + t)
        for vi, x in lst: vg.add([vi], x, "REPLACE")
    first = True
    for m in list(o.modifiers):
        if m.type == "ARMATURE":
            if first: m.object = arm; m.use_deform_preserve_volume = False; first = False
            else: o.modifiers.remove(m)
        elif m.type == "MASK": o.modifiers.remove(m)
    mw = o.matrix_world.copy(); o.parent = arm; o.matrix_world = mw
    print("mesh", o.name, len(acc), "grup")

# 3) buang rig lama & objek bantu
for o in list(bpy.data.objects):
    if o is arm or o in meshes: continue
    bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("simpan", OUT, len(M), "tulang")
