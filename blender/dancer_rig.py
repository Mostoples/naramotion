"""NaraMotion — penari ber-rig: manusia MPFB + rig Rigify (add-on rigging Blender), kostum prosedural.

Figur dibuat sebagai patung emas berbusana (kemben + jarik bermotif batik + stagen + sampur pipih, rambut bersanggul)
dalam pose Gambyong, plus aksi loop "gambyong_loop" (24 fps, 192 frame; frame 0 = pose diam untuk poster).
Kostum & rambut diikat ke rig lewat modifier Armature sehingga ikut bergerak saat dianimasikan.
Pemakaian (tanpa --factory-startup agar ekstensi MPFB termuat):
  blender -b -P blender/dancer_rig.py -- <out.png> [--samples N] [--w PX] [--h PX] [--shift F]
          [--save file.blend] [--anim video.mp4] [--asamples N]
"""
import bpy, bmesh, math, os, sys, shutil, subprocess, addon_utils
from mathutils import Vector, Matrix, Quaternion, kdtree
from mathutils.bvhtree import BVHTree

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGV[0] if ARGV else "dancer_concept.png")
OPT = {"samples": 48, "w": 900, "h": 1200, "shift": -0.045, "save": "", "anim": "", "asamples": 16}
for k in range(1, len(ARGV) - 1, 2):
    key = ARGV[k].lstrip("-")
    val = ARGV[k + 1]
    OPT[key] = val if key in ("save", "anim") else (float(val) if key == "shift" else int(val))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS, LOOP = 24, 192  # 8 detik

addon_utils.enable("rigify", default_set=True)
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.rigservice import RigService


def lin(h):
    h = h.lstrip("#")
    return tuple(((int(h[i:i + 2], 16) / 255 + 0.055) / 1.055) ** 2.4 for i in (0, 2, 4))


def principled(name, col, metal=0.0, rough=0.4, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(col), 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    return m


def batik_material(name, png, scale=(1.6, 1.2)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(png)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (*scale, 1)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(coord.outputs["UV"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    # Bagian emas pada motif sedikit metalik
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tex.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Red"], b.inputs["Metallic"])
    b.inputs["Roughness"].default_value = 0.45
    return m


def sampur_material():
    """Kain marun (merah tua) dengan pelipit emas di kedua tepi (UV v = melintang lebar kain)."""
    m = principled("sampur", "#6e1414", metal=0.0, rough=0.6)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Sheen Weight"].default_value = 0.15
    b.inputs["Sheen Tint"].default_value = (*lin("#b03a2a"), 1)
    b.inputs["Specular IOR Level"].default_value = 0.12  # kilap putih rendah agar tetap marun, tidak salmon
    uv = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs[0])
    for inp, a, c in (("Base Color", (*lin("#d2a54a"), 1), (*lin("#6e1414"), 1)), ("Metallic", (1, 1, 1, 1), (0.0, 0.0, 0.0, 1))):
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        cr = ramp.color_ramp; cr.interpolation = "CONSTANT"
        cr.elements[0].color = a; cr.elements[1].position = 0.09; cr.elements[1].color = c
        cr.elements.new(0.91).color = a
        nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs[inp])
    return m


def hair_material():
    """Perunggu gelap dengan alur sisiran (wave texture sepanjang UV v) sebagai bump."""
    m = principled("rambut_perunggu", "#5a3d1c", metal=1.0, rough=0.38)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    uv = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 160
    wave.inputs["Distortion"].default_value = 0.8
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    nt.links.new(uv.outputs["UV"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def smooth01(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------- Adegan ----------
sc = bpy.context.scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)

macro = {"gender": 0.0, "age": 0.45, "muscle": 0.45, "weight": 0.42, "proportions": 0.7, "height": 0.45,
         "cupsize": 0.45, "firmness": 0.5, "race": {"asian": 1.0, "caucasian": 0.0, "african": 0.0}}
body = HumanService.create_human(macro_detail_dict=macro)
body.name = "Penari"

meta = HumanService.add_builtin_rig(body, "rigify.human")
rig = RigService.generate_rigify_rig(meta, name="Penari.rig", meta_rig_action="hide")
assert rig is not None, "Rigify gagal membuat rig"
print("[nara] rig:", rig.name, len(rig.pose.bones), "pose bones")

GOLD = principled("gold_satin", "#c99a42", metal=1.0, rough=0.33)
for slot in body.material_slots:
    slot.material = GOLD
if not body.material_slots:
    body.data.materials.append(GOLD)

# ---------- Pose Gambyong (kontrol Rigify) ----------
pb = rig.pose.bones
def setp(bone, prop, val):
    if bone in pb and prop in pb[bone]:
        pb[bone][prop] = val

for side in ("L", "R"):
    setp(f"upper_arm_parent.{side}", "IK_FK", 1.0)  # lengan FK

def rot(bone, x=0, y=0, z=0):
    if bone in pb:
        b = pb[bone]
        b.rotation_mode = "XYZ"
        b.rotation_euler = (math.radians(x), math.radians(y), math.radians(z))

def upd():
    bpy.context.view_layer.update()

def deg_bone(name):
    for cand in (name, name.replace("DEF-", "ORG-")):
        if cand in pb:
            return cand
    return None

def world_head(name):
    return rig.matrix_world @ pb[name].head

def world_tail(name):
    return rig.matrix_world @ pb[name].tail

rig_torso = pb.get("torso")
if rig_torso:
    rig_torso.location = (0.0, -0.11, 0.0)  # sumbu Y lokal torso = atas; mendhak: panggul turun, kaki IK tetap menapak
rot("hips", 0, 0, 4)
rot("chest", 0, 0, -6)
rot("neck", 0, 0, 8)
rot("head", -4, 12, 6)
# Lengan kiri (hasil ukur: Z+ = mengangkat ke samping, X+ = ke depan): siku lembut, pergelangan ditekuk (ukel)
rot("upper_arm_fk.L", 24, 0, 28)
rot("forearm_fk.L", 62, 0, 0)
rot("hand_fk.L", 45, 0, 10)
# Lengan kanan (cermin, Z-): rendah di samping pinggul, menjimpit sampur
rot("upper_arm_fk.R", 10, 0, -10)
rot("forearm_fk.R", 36, 0, 0)
rot("hand_fk.R", 24, 0, -8)
upd()


def ngithing(s):
    """Tangan ngithing: ibu jari menyentuh ujung jari tengah, jari lain melengkung lentik (dicari numerik)."""
    if f"f_middle.01.{s}" not in pb:
        return
    # arah telapak: dari garis buku jari ke pangkal ibu jari, tegak lurus bidang punggung tangan
    wrist = world_head(deg_bone(f"DEF-hand.{s}"))
    kn_i, kn_p = world_head(deg_bone(f"DEF-f_index.01.{s}")), world_head(deg_bone(f"DEF-f_pinky.01.{s}"))
    axis = ((kn_i + kn_p) / 2 - wrist).normalized()
    side = (kn_p - kn_i).normalized()
    nrm = axis.cross(side).normalized()
    if nrm.dot(world_head(deg_bone(f"DEF-thumb.02.{s}")) - (kn_i + kn_p) / 2) < 0:
        nrm = -nrm
    mid_tip = lambda: world_tail(deg_bone(f"DEF-f_middle.03.{s}"))
    t0 = mid_tip()
    rot(f"f_middle.02.{s}", 40); upd()
    sign = 1 if (mid_tip() - t0).dot(nrm) > 0 else -1
    rot(f"f_middle.02.{s}", 0)
    def curl(f, a, b, c, spread=0.0):
        for j, ang in enumerate((a, b, c)):
            rot(f"{f}.0{j + 1}.{s}", sign * ang, 0, spread if j == 0 else 0)
    curl("f_index", -8, -6, 2, 4); curl("f_ring", -4, -4, 4, -3); curl("f_pinky", -8, -6, 2, -8)  # lentik
    x = {"m": 45.0, "t1x": 0.0, "t1z": 0.0, "t2": 0.0}
    lim = {"m": (10, 85), "t1x": (-60, 60), "t1z": (-60, 60), "t2": (-50, 50)}
    def apply():
        curl("f_middle", x["m"] * 0.5, x["m"], x["m"] * 0.7)
        rot(f"thumb.01.{s}", x["t1x"], 0, x["t1z"])
        rot(f"thumb.02.{s}", x["t2"]); rot(f"thumb.03.{s}", x["t2"] * 0.7)
        upd()
        d = (world_tail(deg_bone(f"DEF-thumb.03.{s}")) - mid_tip()).length
        return abs(d - 0.013) + 0.0004 * (abs(x["t1x"]) + abs(x["t1z"]) + abs(x["t2"])) / 10
    best = apply()
    for step in (16, 8, 4, 2, 1):
        improved = True
        while improved:
            improved = False
            for key in x:
                for dv in (step, -step):
                    old = x[key]
                    x[key] = min(max(old + dv, lim[key][0]), lim[key][1])
                    e = apply()
                    if e < best - 1e-6:
                        best, improved = e, True
                    else:
                        x[key] = old
    apply()
    print(f"[nara] ngithing {s}: jarak ujung {best * 1000:.1f} mm, param", {k: round(v) for k, v in x.items()})

ngithing("L"); ngithing("R")
upd()

# ---------- Kostum prosedural ----------
dg = bpy.context.evaluated_depsgraph_get()
ev = body.evaluated_get(dg)
zs = [(ev.matrix_world @ v.co).z for v in ev.data.vertices]
height = max(zs) - min(zs)
hip = world_head(deg_bone("DEF-thigh.L")) * 0.5 + world_head(deg_bone("DEF-thigh.R")) * 0.5
ankle = world_head(deg_bone("DEF-foot.L")) * 0.5 + world_head(deg_bone("DEF-foot.R")) * 0.5
chest = world_head(deg_bone("DEF-spine.003"))

# Vertex badan saja (bobot dominan tulang belakang/panggul/paha), tanpa lengan
vg = {g.index: g.name for g in body.vertex_groups}
def dominant(v):
    best = max((g for g in v.groups if vg.get(g.group, "").startswith("DEF-")), key=lambda g: g.weight, default=None)
    return vg.get(best.group, "") if best else ""
masks = [m for m in body.modifiers if m.type == "MASK"]
for m in masks: m.show_viewport = False
upd()
ev2 = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
pos = [ev2.matrix_world @ v.co for v in ev2.data.vertices]
same = len(pos) == len(body.data.vertices)
for m in masks: m.show_viewport = True
upd()
helper_idx = {g.index for g in body.vertex_groups if g.name in ("HelperGeometry", "JointCubes")}
def is_helper(v): return any(g.group in helper_idx and g.weight > 0.5 for g in v.groups)
DOM = [dominant(v) for v in body.data.vertices]
OK = [same and not is_helper(v) for v in body.data.vertices]
torso_i = [i for i in range(len(DOM)) if OK[i] and any(k in DOM[i] for k in ("spine", "breast", "pelvis", "shoulder"))]
leg_i = [i for i in range(len(DOM)) if OK[i] and any(k in DOM[i] for k in ("thigh", "pelvis", "shin", "spine"))]
torso_v = [pos[i] for i in torso_i]
leg_v = [pos[i] for i in leg_i]
print("[nara] torso verts", len(torso_v), "leg verts", len(leg_v))
# Bobot kulit DEF- per vertex badan (untuk mengikat kostum ke rig)
BW = [{vg[g.group]: g.weight for g in v.groups if vg.get(g.group, "").startswith("DEF-") and g.weight > 1e-3}
      for v in body.data.vertices]


def fitted_tube(name, pts, z0, z1, cx, cy, margin, rings=24, segs=72, flare=0.0, th0=0.0):
    """Tabung yang jari-jarinya mengikuti titik terjauh tubuh di tiap sudut dan ketinggian."""
    bm = bmesh.new()
    grid = []
    for r in range(rings + 1):
        z = z0 + (z1 - z0) * r / rings
        band = [p for p in pts if abs(p.z - z) < (z1 - z0) / rings * 1.5] or pts
        row = []
        for k in range(segs):
            th = th0 + k / segs * math.tau  # th0: letak sambungan UV
            dx, dy = math.cos(th), math.sin(th)
            reach = max(((p.x - cx) * dx + (p.y - cy) * dy) for p in band)
            rr = max(reach, 0.05) + margin + flare * (1 - r / rings)
            row.append(bm.verts.new((cx + dx * rr, cy + dy * rr, z)))
        grid.append(row)
    uvl = bm.loops.layers.uv.new("UV")
    for r in range(rings):
        for k in range(segs):
            f = bm.faces.new((grid[r][k], grid[r][(k + 1) % segs], grid[r + 1][(k + 1) % segs], grid[r + 1][k]))
            for loop, (u, v) in zip(f.loops, ((k, r), (k + 1, r), (k + 1, r + 1), (k, r + 1))):
                loop[uvl].uv = (u / segs, v / rings)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    for poly in me.polygons: poly.use_smooth = True
    ob.modifiers.new("solid", "SOLIDIFY").thickness = 0.006
    sm = ob.modifiers.new("smooth", "SMOOTH"); sm.factor = 0.8; sm.iterations = 6
    return ob


def bind(ob, cand, wfun=None, k=6):
    """Ikat mesh (dibuat dalam pose) ke rig: bobot dari vertex badan terdekat, lalu koordinat
    dikembalikan ke rest pose (invers linear-blend skinning) agar modifier Armature menghasilkan bentuk semula."""
    me = ob.data
    me.transform(ob.matrix_world); ob.matrix_world = Matrix.Identity(4)
    kd = kdtree.KDTree(len(cand))
    for i in cand: kd.insert(pos[i], i)
    kd.balance()
    D = {b.name: b.matrix @ b.bone.matrix_local.inverted() for b in pb if b.name.startswith("DEF-")}
    groups = {}
    for v in me.vertices:
        p = v.co.copy()
        w = wfun(v.index, p) if wfun else None
        if w is None:
            w = {}
            for _, i, dist in kd.find_n(p, k):
                f = 1.0 / (dist + 0.005)
                for g, x in BW[i].items(): w[g] = w.get(g, 0.0) + x * f
        top = [(g, x) for g, x in sorted(w.items(), key=lambda kv: -kv[1])[:4] if g in D]
        s = sum(x for _, x in top)
        if s <= 0:
            continue
        M = Matrix(((0.0,) * 4,) * 4)
        for g, x in top:
            M += D[g] * (x / s)
            groups.setdefault(g, []).append((v.index, x / s))
        v.co = M.inverted() @ p
    for g, lst in groups.items():
        grp = ob.vertex_groups.get(g) or ob.vertex_groups.new(name=g)
        for i, x in lst: grp.add([i], x, "REPLACE")
    arm = ob.modifiers.new("Armature", "ARMATURE"); arm.object = rig
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    ob.parent = rig; ob.matrix_parent_inverse = rig.matrix_world.inverted()


shoulder = world_head(deg_bone("DEF-upper_arm.L"))
waist = world_head(deg_bone("DEF-spine.002"))
kemben = fitted_tube("Kemben", torso_v, waist.z - 0.05, shoulder.z - 0.055, chest.x, chest.y, 0.014)
km = principled("kemben", "#5a1212", rough=0.55, coat=0.08)  # marun: kilap putih rendah agar tidak merah muda
km.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.15
kemben.data.materials.append(km)
jarik = fitted_tube("Jarik", leg_v, ankle.z + 0.03, waist.z - 0.03, hip.x, hip.y, 0.018, flare=0.05, th0=math.pi / 2)  # sambungan di belakang
# Motif parang besar: tekstur ±24 lereng/ubin; 7/12 ubin keliling = 14 lereng (±6 di depan), ubin tetap persegi
jarik.data.materials.append(batik_material("jarik", os.path.join(ROOT, "assets_src", "tex", "parang.png"), (7 / 12, 0.30)))
STZ = waist.z - 0.03
bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.014, location=(waist.x, waist.y, STZ))
stagen = bpy.context.active_object; stagen.name = "Stagen"; stagen.scale = (1.0, 0.85, 1.0)
stagen.data.materials.append(principled("stagen_emas", "#d2a54a", metal=1.0, rough=0.3))
upd()


# ---------- Sampur: selendang pipih (lebar 7 cm, tebal 2 mm) ----------
def collision_bvh(obs):
    dgx = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for o in obs:
        tmp = bpy.data.meshes.new_from_object(o.evaluated_get(dgx))
        tmp.transform(o.matrix_world); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    t = BVHTree.FromBMesh(bm); bm.free()
    return t


def catmull(pts, per_m=250):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(4, int((p2 - p1).length * per_m))
        for j in range(n):
            t = j / n
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1].copy())
    return out


def resample(pts, step=0.008):
    L = [0.0]
    for a, b in zip(pts, pts[1:]): L.append(L[-1] + (b - a).length)
    n = max(2, int(L[-1] / step)); out = []; j = 0
    for i in range(n + 1):
        s = L[-1] * i / n
        while j < len(L) - 2 and L[j + 1] < s: j += 1
        t = (s - L[j]) / max(L[j + 1] - L[j], 1e-9)
        out.append(pts[j].lerp(pts[j + 1], t))
    return out


coll = collision_bvh([body, kemben, jarik, stagen])
hand_bone_r = deg_bone("DEF-hand.R")
pinch = (world_tail(deg_bone("DEF-thumb.03.R")) + world_tail(deg_bone("DEF-f_middle.03.R"))) / 2
c0 = Vector((hip.x, hip.y, 0))
def ring(deg, z, rx=0.19, ry=0.165):
    a = math.radians(deg)
    return Vector((waist.x + rx * math.cos(a), waist.y + ry * math.sin(a), z))
WZ = STZ - 0.045  # sampur melilit tepat di bawah stagen
ctrl = [ring(-45, WZ - 0.46, 0.2, 0.2), ring(-45, WZ - 0.22, 0.2, 0.19), ring(-40, WZ - 0.02)]
ctrl += [ring(a, WZ) for a in range(-15, 205, 25)]
ctrl += [ring(215, WZ - 0.03), ring(222, WZ - 0.13, 0.205, 0.19)]
i_u0_pt = ctrl[-1]
u_bot = Vector(((i_u0_pt.x + pinch.x) / 2 - 0.02, (i_u0_pt.y + pinch.y) / 2 - 0.05, min(i_u0_pt.z, pinch.z) - 0.2))
ctrl += [u_bot, pinch + Vector((0.015, 0.0, -0.06)), pinch, pinch + Vector((-0.03, -0.01, -0.12)), pinch + Vector((-0.04, -0.02, -0.36))]
path = resample(catmull(ctrl))
nearest_i = lambda q: min(range(len(path)), key=lambda i: (path[i] - q).length)
i_u0, i_pin = nearest_i(i_u0_pt), nearest_i(pinch)
path[i_pin] = pinch.copy()
for it in range(12):  # dorong keluar dari tubuh/kostum + haluskan, titik jepit tetap
    for i, p in enumerate(path):
        if (p - pinch).length < 0.035:
            continue
        loc, nrm, _, dist = coll.find_nearest(p)
        if loc is None:
            continue
        out = (p - loc).dot(nrm) >= 0
        if not out or dist < 0.013:
            path[i] = loc + nrm * 0.013
    if it < 11:
        path = [path[0]] + [(path[i - 1] + path[i] * 2 + path[i + 1]) / 4 if i != i_pin else path[i]
                            for i in range(1, len(path) - 1)] + [path[-1]]
# Orientasi lebar kain: menempel permukaan tubuh (lebar ⟂ arah kain & normal tubuh)
widths, sides = [], []
prev = None
for i, p in enumerate(path):
    t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
    loc, nrm, _, dist = coll.find_nearest(p)
    radial = (p - Vector((hip.x, hip.y, p.z))).normalized()
    n = radial if loc is None else nrm.lerp(radial, smooth01((dist - 0.03) / 0.06)).normalized()
    b = t.cross(n).normalized()
    if prev is not None and b.dot(prev) < 0: b = -b
    sides.append(b); prev = b
    d_pin = (p - pinch).length
    widths.append(0.07 * (1 - 0.8 * math.exp(-(d_pin / 0.07) ** 2)))  # mengumpul di jepitan jari
for _ in range(6):
    sides = [sides[0]] + [(sides[i - 1] + sides[i] * 2 + sides[i + 1]).normalized() for i in range(1, len(sides) - 1)] + [sides[-1]]
bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UV"); rows = []
for p, b, w in zip(path, sides, widths):
    rows.append([bm.verts.new(p + b * (w * (j - 1) / 2)) for j in range(3)])
L = len(rows)
for i in range(L - 1):
    for j in range(2):
        f = bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
        for loop, (u, v) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
            loop[uvl].uv = (u / (L - 1) * 30, v / 2)
me = bpy.data.meshes.new("sampur"); bm.to_mesh(me); bm.free()
for poly in me.polygons: poly.use_smooth = True
sampur = bpy.data.objects.new("Sampur", me); sc.collection.objects.link(sampur)
me.materials.append(sampur_material())
sd = sampur.modifiers.new("solid", "SOLIDIFY"); sd.thickness = 0.002; sd.offset = 0.0
print(f"[nara] sampur {len(path)} titik, panjang ~{len(path) * 0.008:.2f} m")

# Ikat kostum ke rig (bobot dari kulit terdekat)
bind(kemben, torso_i); bind(jarik, leg_i); bind(stagen, torso_i + leg_i)
kd_s = kdtree.KDTree(len(torso_i + leg_i))
for i in torso_i + leg_i: kd_s.insert(pos[i], i)
kd_s.balance()
def near_w(p):
    w = {}
    for _, i, dist in kd_s.find_n(p, 6):
        for g, x in BW[i].items(): w[g] = w.get(g, 0.0) + x / (dist + 0.005)
    s = sum(w.values()) or 1.0
    return {g: x / s for g, x in w.items()}
W_u0, W_hand = near_w(path[i_u0]), {hand_bone_r: 1.0}
def sampur_w(vi, p):
    i = vi // 3
    if i <= i_u0:
        return near_w(path[i])
    if i >= i_pin:
        return W_hand
    s = smooth01((i - i_u0) / (i_pin - i_u0))
    w = {g: x * (1 - s) for g, x in W_u0.items()}
    w[hand_bone_r] = w.get(hand_bone_r, 0.0) + s
    return w
bind(sampur, torso_i + leg_i, wfun=sampur_w)


# ---------- Rambut tersisir ke belakang + sanggul (gelung) + cunduk emas ----------
def torus(bm, center, axis, R, r, su=48, sv=16, sq=1.0):
    q = Vector((0, 0, 1)).rotation_difference(axis)
    grid = []
    for i in range(su):
        a = i / su * math.tau
        row = []
        for j in range(sv):
            b = j / sv * math.tau
            v = Vector(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a) * sq, r * math.sin(b)))
            row.append(bm.verts.new(center + q @ v))
        grid.append(row)
    for i in range(su):
        for j in range(sv):
            bm.faces.new((grid[i][j], grid[(i + 1) % su][j], grid[(i + 1) % su][(j + 1) % sv], grid[i][(j + 1) % sv]))


def build_hair():
    rig.data.pose_position = "REST"; upd()  # dibangun di rest pose: kepala tegak, depan = -Y
    dgr = bpy.context.evaluated_depsgraph_get()
    evr = body.evaluated_get(dgr)
    bvh = BVHTree.FromObject(body, dgr)
    hb = rig.data.bones["head"]
    vs = [evr.matrix_world @ v.co for v in evr.data.vertices]
    vs = [p for p in vs if p.z > hb.head_local.z + 0.04 and abs(p.x - hb.head_local.x) < 0.12]
    zt = max(p.z for p in vs)
    ys = [p.y for p in vs]; xs = [p.x for p in vs]
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2 + 0.01, zt - 0.095))
    def surf(az, el, off):
        d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
        loc, nrm, _, _ = bvh.ray_cast(c + d * 0.35, -d)
        if loc is None:
            loc, nrm = c + d * 0.09, d
        if nrm.dot(d) < 0: nrm = -nrm
        return loc + nrm * off, d
    def e_min(az):  # garis rambut: dahi tinggi, di atas telinga, tengkuk rendah
        ca = math.cos(az)
        return math.radians(-9 + (35 if ca > 0 else 36) * ca)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UV")
    segs, rings = 96, 28
    grid = []
    for i in range(rings):
        row = []
        for j in range(segs):
            az = j / segs * math.tau
            el = e_min(az) + (math.radians(86) - e_min(az)) * (i / (rings - 1)) ** 0.8
            thick = -0.0008 + (0.0045 + 0.007 * max(0.0, math.sin(el)) + 0.004 * max(0.0, -math.cos(az))) * smooth01(i / 6)  # tepi melebur ke kulit
            row.append(bm.verts.new(surf(az, el, thick)[0]))
        grid.append(row)
    apex = bm.verts.new(surf(0, math.radians(90), 0.011)[0])
    for i in range(rings - 1):
        for j in range(segs):
            f = bm.faces.new((grid[i][j], grid[i][(j + 1) % segs], grid[i + 1][(j + 1) % segs], grid[i + 1][j]))
            for loop, (u, v) in zip(f.loops, ((j, i), (j + 1, i), (j + 1, i + 1), (j, i + 1))):
                loop[uvl].uv = (u / segs, v / rings)
    for j in range(segs):
        bm.faces.new((grid[-1][j], grid[-1][(j + 1) % segs], apex))
    # Sanggul (gelung) di belakang kepala, agak rendah, dengan lilitan ukel
    bun_c, d_b = surf(math.pi, math.radians(-22), 0.0)
    bun_c = bun_c + d_b * 0.034
    sph = bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
    for v in sph["verts"]:
        v.co = bun_c + Vector((v.co.x * 0.058, v.co.y * 0.033, v.co.z * 0.044))
    torus(bm, bun_c + d_b * 0.006, d_b, 0.044, 0.012, sq=0.78)
    torus(bm, bun_c + d_b * 0.022, d_b, 0.026, 0.009, sq=0.78)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("rambut"); bm.to_mesh(me); bm.free()
    for poly in me.polygons: poly.use_smooth = True
    hair = bpy.data.objects.new("Rambut", me); sc.collection.objects.link(hair)
    me.materials.append(hair_material())
    sd = hair.modifiers.new("solid", "SOLIDIFY"); sd.thickness = 0.0012; sd.offset = -1
    # Cunduk: tiga tusuk emas mengipas dari atas sanggul, ujung bunga kecil
    bm = bmesh.new()
    for sx in (-1, 0, 1):
        base = bun_c + Vector((sx * 0.02, 0.004, 0.03))
        d = Vector((sx * 0.4, 0.35, 1.0)).normalized()
        cone = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.0022, radius2=0.0016, depth=0.07)
        q = Vector((0, 0, 1)).rotation_difference(d)
        for v in cone["verts"]: v.co = base + d * 0.035 + q @ v.co
        top = base + d * 0.072
        for k in range(5):
            a = k / 5 * math.tau
            pet = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.0055)
            off = q @ Vector((math.cos(a) * 0.006, math.sin(a) * 0.006, 0))
            for v in pet["verts"]: v.co = top + off + v.co
        mid = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.004)
        for v in mid["verts"]: v.co = top + q @ Vector((0, 0, 0.003)) + v.co
    me2 = bpy.data.meshes.new("cunduk"); bm.to_mesh(me2); bm.free()
    for poly in me2.polygons: poly.use_smooth = True
    cunduk = bpy.data.objects.new("Cunduk", me2); sc.collection.objects.link(cunduk)
    me2.materials.append(principled("cunduk_emas", "#e0b456", metal=1.0, rough=0.22))
    # Kaku mengikuti tulang deform kepala
    hdef = min((b for b in rig.data.bones if b.name.startswith("DEF-")), key=lambda b: (b.head_local - hb.head_local).length)
    for ob in (hair, cunduk):
        g = ob.vertex_groups.new(name=hdef.name); g.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
        arm = ob.modifiers.new("Armature", "ARMATURE"); arm.object = rig
        ob.modifiers.move(len(ob.modifiers) - 1, 0)
        ob.parent = rig; ob.matrix_parent_inverse = rig.matrix_world.inverted()
    rig.data.pose_position = "POSE"; upd()
    print("[nara] rambut terikat ke", hdef.name)

build_hair()


# ---------- Animasi loop "gambyong_loop" (kontrol FK/IK Rigify) ----------
def make_loop():
    om = math.tau / LOOP
    S = lambda k, ph=0.0: (lambda t: math.sin(k * om * t + ph) - math.sin(ph))  # nol di frame 0 & 192
    def step(a, b):
        return lambda t: smooth01((t - a) / (b - a))
    def bump(a, b):
        return lambda t: math.sin(math.pi * min(max((t - a) / (b - a), 0.0), 1.0)) ** 2
    X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))  # depan penari = -Y, kiri = +X
    # (sumbu, amplitudo derajat, fungsi). sumbu Vector = sumbu dunia; "X"/"Y"/"Z" = sumbu lokal tulang
    R = {
        "hips": [(Y, 3.0, S(2)), (Z, 2.0, S(2, 0.4))],                     # ngleyek
        "chest": [(Y, -4.0, S(2, 0.3)), (Z, -2.5, S(2, 0.6))],
        "neck": [(Y, 2.5, S(2, 0.9))],
        "head": [(Z, 7.0, S(2, 0.8)), (X, 2.0, S(4, 0.2))],               # pacak gulu
        "upper_arm_fk.L": [(-Y, 9.0, S(1)), (X, 4.0, S(1, 1.2))],          # lengan bergantian naik-turun
        "upper_arm_fk.R": [(Y, -7.0, S(1)), (X, 3.0, S(1, 1.4))],
        "forearm_fk.L": [("X", 8.0, S(1, 0.6))],
        "forearm_fk.R": [("X", -5.0, S(1, 0.6))],
        "hand_fk.L": [("Y", 24.0, S(2, 0.5)), ("X", 12.0, S(2, 2.1))],     # ukel
        "hand_fk.R": [("Y", 12.0, S(2, 1.5)), ("X", 8.0, S(2, 3.0))],
    }
    T = {
        "torso": [(X, 0.022, S(2)), (Z, -0.008, lambda t: (1 - math.cos(4 * om * t)) / 2)],
        "foot_ik.L": [(-Y, 0.035, lambda t: step(16, 56)(t) - step(112, 152)(t)), (Z, 0.012, lambda t: bump(16, 56)(t) + bump(112, 152)(t))],
        "foot_ik.R": [(-Y, 0.03, lambda t: step(64, 104)(t) - step(152, 188)(t)), (Z, 0.01, lambda t: bump(64, 104)(t) + bump(152, 188)(t))],
    }
    R = {n: v for n, v in R.items() if n in pb}; T = {n: v for n, v in T.items() if n in pb}
    for n in R: pb[n].rotation_mode = "XYZ"
    upd()
    base_q = {n: pb[n].rotation_euler.to_quaternion() for n in R}
    m3inv = {n: pb[n].matrix.to_3x3().normalized().inverted() for n in R}
    base_l, loc_of = {}, {}
    for n in T:  # turunan lokasi lokal per sumbu dunia (diukur, aman terhadap orientasi tulang)
        b = pb[n]; base_l[n] = b.location.copy(); M0 = b.matrix.copy(); cols = []
        for ax in (X, Y, Z):
            b.matrix = Matrix.Translation(ax * 0.1) @ M0; upd()
            cols.append((b.location - base_l[n]) / 0.1)
            b.location = base_l[n]; upd()
        loc_of[n] = cols
    act = bpy.data.actions.new("gambyong_loop"); act.use_fake_user = True
    rig.animation_data_create(); rig.animation_data.action = act
    prev = {n: pb[n].rotation_euler.copy() for n in R}
    for f in range(0, LOOP + 1, 4):
        for n, terms in R.items():
            q = base_q[n].copy()
            for ax, amp, fn in terms:
                a = Vector({"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[ax]) if isinstance(ax, str) else m3inv[n] @ ax
                q = q @ Quaternion(a.normalized(), math.radians(amp * fn(f)))
            e = q.to_euler("XYZ", prev[n]); prev[n] = e
            pb[n].rotation_euler = e
            pb[n].keyframe_insert("rotation_euler", frame=f, group=n)
        for n, terms in T.items():
            d = [0.0, 0.0, 0.0]
            for ax, amp, fn in terms:
                for c in range(3): d[c] += ax[c] * amp * fn(f)
            pb[n].location = base_l[n] + loc_of[n][0] * d[0] + loc_of[n][1] * d[1] + loc_of[n][2] * d[2]
            pb[n].keyframe_insert("location", frame=f, group=n)
    try:  # Blender 4.4+: action berlapis (slot/channelbag)
        from bpy_extras import anim_utils
        fcs = anim_utils.action_get_channelbag_for_slot(act, rig.animation_data.action_slot).fcurves
    except Exception:
        fcs = act.fcurves
    for fc in fcs:
        fc.modifiers.new("CYCLES")
    sc.render.fps = FPS; sc.frame_start = 0; sc.frame_end = LOOP - 1
    sc.frame_set(0)
    print("[nara] aksi", act.name, len(fcs), "f-curve")

make_loop()

# Alas pentas
bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=0.55, depth=0.08, location=(hip.x, hip.y, ankle.z - 0.12))
alas = bpy.context.active_object; bpy.ops.object.shade_smooth()
alas.data.materials.append(principled("pernis", "#1e170e", rough=0.4, coat=0.6))

# ---------- Cahaya, kamera, render ----------
def area(name, loc, size, power, col):
    ld = bpy.data.lights.new(name, "AREA"); ld.size = size; ld.energy = power; ld.color = col
    ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob); ob.location = loc
    ob.rotation_euler = (Vector((hip.x, hip.y, hip.z)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
area("key", (2.2, -2.6, 2.6), 2.5, 600, (1, .92, .8))
area("rim", (-1.4, 2.2, 2.2), 2.0, 700, (1, .78, .42))
area("fill", (-2.5, -1.8, 1.2), 3.0, 160, (1, .95, .9))

cd = bpy.data.cameras.new("cam"); cd.lens = 85; cd.shift_y = OPT["shift"]
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
target = Vector((hip.x, hip.y, ankle.z + height * 0.47))
cam.location = target + Vector((1.25, -4.3, 0.35))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "OPTIX"; prefs.get_devices()
    for d in prefs.devices: d.use = d.type == "OPTIX"
    sc.cycles.device = "GPU"
except Exception:
    pass
sc.cycles.samples = OPT["samples"]; sc.cycles.use_denoising = True
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = OPT["w"], OPT["h"]
sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = -0.1
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.1, 0.08, 0.05, 1)
sc.frame_set(0)  # pose diam untuk poster
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("[nara] rendered", OUT)
if OPT["save"]:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OPT["save"]))
    print("[nara] saved", OPT["save"])

# ---------- Video uji animasi (opsional) ----------
if OPT["anim"]:
    mp4 = os.path.abspath(OPT["anim"])
    fdir = os.path.splitext(mp4)[0] + "_frames"
    os.makedirs(fdir, exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y = 480, 640
    sc.cycles.samples = OPT["asamples"]; sc.render.film_transparent = False
    sc.render.use_persistent_data = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(fdir, "####")
    bpy.ops.render.render(animation=True)
    ff = shutil.which("ffmpeg") or os.environ.get("FFMPEG")
    if not ff:  # ffmpeg WinGet sering hanya ada di PATH Git Bash, bukan PATH Windows
        import glob
        hits = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages", "*FFmpeg*", "*", "bin", "ffmpeg.exe"))
        ff = hits[0] if hits else None
    if ff:
        subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(FPS), "-start_number", "0",
                        "-i", os.path.join(fdir, "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)
        shutil.rmtree(fdir)
        print("[nara] video", mp4)
    else:
        print("[nara] ffmpeg tidak ditemukan; frame PNG di", fdir)
