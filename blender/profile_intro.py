"""NaraMotion — intro sinematik 3D (18 s, 432 frame @24 fps, 1920x1080), dibangun dari nol lalu dirender (EEVEE).
Tiga scene terpisah, nomor frame global:
  S1_Stupa   f1–144   : crane naik di antara stupa Borobudur, senja keemasan, kabut + debu emas
  S2_Gerbang f145–264 : dolly menembus gerbang bata Trowulan, cahaya dari belakang + god-rays
  S3_Pendapa f265–432 : pendapa joglo senja-malam, obor & lampu minyak, gamelan, wayang, penari gambyong
Transisi antar shot: kilat cahaya emas (exposure dinaikkan lalu diturunkan ±8 frame).
Pemakaian:
  blender -b -P blender/profile_intro.py -- [--out DIR] [--res-scale 1.0] [--frames 1-432] [--step 1]
                                            [--preview] [--samples N] [--no-save] [--build-only]
Frame yang sudah ada di --out dilewati (render bisa dilanjutkan).
"""
import bpy, sys, os, math, random, time, argparse, tempfile
from mathutils import Vector, Matrix

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(ROOT, "assets_src")
SKF = os.path.join(SRC, "sketchfab")
PENARI = os.path.join(SRC, "penari_rig.blend")
BLEND_OUT = os.path.join(SRC, "profile", "intro_scene.blend")

# ---------- argumen ----------
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=None)
ap.add_argument("--res-scale", type=float, default=None)
ap.add_argument("--frames", default="1-432")
ap.add_argument("--step", type=int, default=1)
ap.add_argument("--preview", action="store_true")
ap.add_argument("--samples", type=int, default=None)
ap.add_argument("--no-save", action="store_true")
ap.add_argument("--build-only", action="store_true")
ap.add_argument("--render-only", action="store_true")
A = ap.parse_args(argv)
PREV = A.preview
if A.out is None:
    A.out = os.path.join(tempfile.gettempdir(), "naramotion_intro_preview") if PREV else os.path.join(SRC, "profile", "intro")
OUT = os.path.abspath(A.out)
RES = A.res_scale if A.res_scale else (0.25 if PREV else 1.0)
SAMPLES = A.samples if A.samples else (12 if PREV else 64)
F0, F1 = (int(x) for x in A.frames.split("-"))
SHOTS = [("S1_Stupa", 1, 144), ("S2_Gerbang", 145, 264), ("S3_Pendapa", 265, 432)]
random.seed(7)
T0 = time.time()
def log(*a): print("[intro]", f"{time.time()-T0:6.1f}s", *a, flush=True)

# ---------- util umum ----------
def lerp(a, b, t): return a + (b - a) * t
def smooth(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
def ease_out(t): t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def mat_new(name):
    m = bpy.data.materials.new(name)
    if m.node_tree is None: m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    return m, nt, b

def N(nt, typ, **kw):
    n = nt.nodes.new(typ)
    for k, v in kw.items():
        if hasattr(n, k) and not isinstance(v, dict): setattr(n, k, v)
    return n

def setin(n, **kw):
    for k, v in kw.items(): n.inputs[k.replace("_", " ")].default_value = v

def mix(nt, fac, a, b, blend="MIX"):
    """Mix warna (ShaderNodeMix RGBA); a/b boleh socket atau tuple."""
    m = nt.nodes.new("ShaderNodeMix"); m.data_type = "RGBA"; m.blend_type = blend
    for idx, v in ((0, fac), (6, a), (7, b)):
        if isinstance(v, (int, float)): m.inputs[idx].default_value = v
        elif isinstance(v, tuple): m.inputs[idx].default_value = v if len(v) == 4 else (*v, 1)
        else: nt.links.new(v, m.inputs[idx])
    return m.outputs[2]

def world_pos(nt):
    return N(nt, "ShaderNodeNewGeometry").outputs["Position"]

def noise(nt, vec, scale, detail=4, rough=0.55):
    n = N(nt, "ShaderNodeTexNoise"); nt.links.new(vec, n.inputs["Vector"])
    setin(n, Scale=scale, Detail=detail, Roughness=rough); return n

def ramp(nt, fac, stops):
    r = N(nt, "ShaderNodeValToRGB"); nt.links.new(fac, r.inputs[0])
    els = r.color_ramp.elements
    while len(els) < len(stops): els.new(0.5)
    for e, (p, c) in zip(els, stops): e.position = p; e.color = (*c, 1)
    return r.outputs[0]

def bump(nt, b, height, strength, dist=0.02, normal=None):
    bp = N(nt, "ShaderNodeBump"); nt.links.new(height, bp.inputs["Height"])
    setin(bp, Strength=strength, Distance=dist)
    if normal is not None: nt.links.new(normal, bp.inputs["Normal"])
    nt.links.new(bp.outputs[0], b.inputs["Normal"]); return bp.outputs[0]

def sep_xyz(nt, v):
    s = N(nt, "ShaderNodeSeparateXYZ"); nt.links.new(v, s.inputs[0]); return s

def comb_xyz(nt, x, y, z=0.0):
    c = N(nt, "ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        if isinstance(v, (int, float)): c.inputs[i].default_value = v
        else: nt.links.new(v, c.inputs[i])
    return c.outputs[0]

def math_node(nt, op, a, b=0.0):
    m = N(nt, "ShaderNodeMath"); m.operation = op
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)): m.inputs[i].default_value = v
        else: nt.links.new(v, m.inputs[i])
    return m.outputs[0]

def emis_mat(name, col, strength):
    m, nt, b = mat_new(name)
    setin(b, Base_Color=(0, 0, 0, 1), Emission_Color=(*col, 1), Emission_Strength=strength)
    return m

# ---------- material prosedural ----------
def mat_field():
    """Tanah lapang + rumput kering (shot 1–2)."""
    m, nt, b = mat_new("tanah_lapang")
    P = world_pos(nt)
    big = noise(nt, P, 0.04, 3); mid = noise(nt, P, 0.6, 6); fine = noise(nt, P, 9.0, 8, 0.7)
    c1 = ramp(nt, big.outputs["Fac"], [(0.35, (0.36, 0.27, 0.12)), (0.62, (0.20, 0.135, 0.07))])
    c2 = mix(nt, mid.outputs["Fac"], c1, (0.46, 0.36, 0.17), "OVERLAY")
    c3 = mix(nt, 0.35, c2, fine.outputs["Color"], "MULTIPLY")
    nt.links.new(c3, b.inputs["Base Color"])
    setin(b, Roughness=0.92)
    bump(nt, b, fine.outputs["Fac"], 0.45, 0.03)
    return m

def mat_grass():
    m, nt, b = mat_new("rumput_kering")
    oi = N(nt, "ShaderNodeObjectInfo"); tc = N(nt, "ShaderNodeTexCoord")
    col = ramp(nt, oi.outputs["Random"], [(0.0, (0.40, 0.30, 0.12)), (0.5, (0.52, 0.42, 0.2)), (1.0, (0.28, 0.24, 0.10))])
    sep = sep_xyz(nt, tc.outputs["Generated"])
    col2 = mix(nt, math_node(nt, "MULTIPLY", sep.outputs[2], 0.6), (0.16, 0.12, 0.05), col)
    nt.links.new(col2, b.inputs["Base Color"])
    setin(b, Roughness=0.7, Subsurface_Weight=0.0)
    try: setin(b, Transmission_Weight=0.15)
    except Exception: pass
    return m

def mat_brick():
    """Bata merah Majapahit, pola dari koordinat dunia (x+y, z)."""
    m, nt, b = mat_new("bata_merah")
    P = world_pos(nt); s = sep_xyz(nt, P)
    v = comb_xyz(nt, math_node(nt, "ADD", s.outputs[0], s.outputs[1]), s.outputs[2])
    br = N(nt, "ShaderNodeTexBrick"); br.offset = 0.5
    nt.links.new(v, br.inputs["Vector"])
    setin(br, Color1=(0.46, 0.15, 0.065, 1), Color2=(0.33, 0.10, 0.045, 1), Mortar=(0.30, 0.22, 0.16, 1),
          Scale=1.0, Mortar_Size=0.009, Mortar_Smooth=0.3, Bias=0.0, Brick_Width=0.32, Row_Height=0.085)
    wn = noise(nt, P, 0.7, 5)
    dirt = ramp(nt, wn.outputs["Fac"], [(0.3, (0.55, 0.5, 0.45)), (0.7, (1, 1, 1))])
    c = mix(nt, 1.0, br.outputs["Color"], dirt, "MULTIPLY")
    fn = noise(nt, P, 14.0, 6)
    c = mix(nt, 0.25, c, fn.outputs["Color"], "MULTIPLY")
    nt.links.new(c, b.inputs["Base Color"]); setin(b, Roughness=0.88)
    h = math_node(nt, "SUBTRACT", 1.0, br.outputs["Fac"])
    h = math_node(nt, "ADD", h, math_node(nt, "MULTIPLY", fn.outputs["Fac"], 0.35))
    bump(nt, b, h, 0.6, 0.012)
    return m

def mat_andesit():
    """Batu andesit candi: blok besar, lumut tipis."""
    m, nt, b = mat_new("batu_andesit")
    P = world_pos(nt); s = sep_xyz(nt, P)
    geo = N(nt, "ShaderNodeNewGeometry"); ns = sep_xyz(nt, geo.outputs["Normal"])
    vw = comb_xyz(nt, math_node(nt, "ADD", s.outputs[0], s.outputs[1]), s.outputs[2])
    vt = comb_xyz(nt, s.outputs[0], s.outputs[1])
    bricks = []
    for v, w, h in ((vw, 0.62, 0.32), (vt, 0.7, 0.45)):
        br = N(nt, "ShaderNodeTexBrick"); br.offset = 0.5; nt.links.new(v, br.inputs["Vector"])
        setin(br, Color1=(0.25, 0.235, 0.21, 1), Color2=(0.18, 0.17, 0.155, 1), Mortar=(0.08, 0.075, 0.07, 1),
              Scale=1.0, Mortar_Size=0.012, Mortar_Smooth=0.4, Brick_Width=w, Row_Height=h)
        bricks.append(br)
    top = math_node(nt, "GREATER_THAN", math_node(nt, "ABSOLUTE", ns.outputs[2]), 0.6)
    c = mix(nt, top, bricks[0].outputs["Color"], bricks[1].outputs["Color"])
    hf = mix(nt, top, bricks[0].outputs["Fac"], bricks[1].outputs["Fac"])
    lm = noise(nt, P, 0.35, 5)
    moss = ramp(nt, lm.outputs["Fac"], [(0.55, (0, 0, 0)), (0.75, (1, 1, 1))])
    c = mix(nt, moss, c, (0.11, 0.12, 0.06))
    fn = noise(nt, P, 11.0, 7)
    c = mix(nt, 0.3, c, fn.outputs["Color"], "MULTIPLY")
    nt.links.new(c, b.inputs["Base Color"]); setin(b, Roughness=0.9)
    h = math_node(nt, "ADD", math_node(nt, "SUBTRACT", 1.0, hf), math_node(nt, "MULTIPLY", fn.outputs["Fac"], 0.5))
    bump(nt, b, h, 0.55, 0.015)
    return m

def mat_tegel():
    """Lantai tegel terakota mengilap pendapa."""
    m, nt, b = mat_new("lantai_tegel")
    P = world_pos(nt); s = sep_xyz(nt, P)
    br = N(nt, "ShaderNodeTexBrick"); br.offset = 0.0
    nt.links.new(comb_xyz(nt, s.outputs[0], s.outputs[1]), br.inputs["Vector"])
    setin(br, Color1=(0.30, 0.13, 0.065, 1), Color2=(0.24, 0.10, 0.05, 1), Mortar=(0.10, 0.07, 0.05, 1),
          Scale=1.0, Mortar_Size=0.006, Mortar_Smooth=0.2, Brick_Width=0.4, Row_Height=0.4)
    wn = noise(nt, P, 1.5, 6)
    c = mix(nt, 0.3, br.outputs["Color"], wn.outputs["Color"], "MULTIPLY")
    nt.links.new(c, b.inputs["Base Color"])
    r = ramp(nt, noise(nt, P, 0.8, 4).outputs["Fac"], [(0.35, (0.18, 0.18, 0.18)), (0.7, (0.5, 0.5, 0.5))])
    nt.links.new(r, b.inputs["Roughness"])
    bump(nt, b, math_node(nt, "SUBTRACT", 1.0, br.outputs["Fac"]), 0.3, 0.004)
    return m

def mat_jati(name="kayu_jati", dark=1.0):
    m, nt, b = mat_new(name)
    P = world_pos(nt)
    wv = N(nt, "ShaderNodeTexWave"); wv.wave_type = "BANDS"; wv.bands_direction = "Z"
    nt.links.new(P, wv.inputs["Vector"])
    setin(wv, Scale=6.0, Distortion=9.0, Detail=4.0)
    k = dark
    c = ramp(nt, wv.outputs["Fac"], [(0.2, (0.20 * k, 0.085 * k, 0.03 * k)), (0.8, (0.11 * k, 0.045 * k, 0.018 * k))])
    nt.links.new(c, b.inputs["Base Color"]); setin(b, Roughness=0.42)
    try: setin(b, Coat_Weight=0.15)
    except Exception: pass
    bump(nt, b, wv.outputs["Fac"], 0.08, 0.005)
    return m

def mat_yard():
    """Halaman tanah padat + kerikil (shot 3)."""
    m, nt, b = mat_new("tanah_halaman")
    P = world_pos(nt)
    big = noise(nt, P, 0.15, 4); fine = noise(nt, P, 7, 8)
    vor = N(nt, "ShaderNodeTexVoronoi"); nt.links.new(P, vor.inputs["Vector"]); setin(vor, Scale=18.0)
    c = ramp(nt, big.outputs["Fac"], [(0.35, (0.21, 0.155, 0.10)), (0.65, (0.14, 0.10, 0.065))])
    peb = ramp(nt, vor.outputs["Distance"], [(0.0, (1, 1, 1)), (0.35, (0, 0, 0))])
    c = mix(nt, peb, c, (0.30, 0.27, 0.23))
    c = mix(nt, 0.3, c, fine.outputs["Color"], "MULTIPLY")
    nt.links.new(c, b.inputs["Base Color"]); setin(b, Roughness=0.93)
    bump(nt, b, math_node(nt, "ADD", peb, math_node(nt, "MULTIPLY", fine.outputs["Fac"], 0.6)), 0.5, 0.02)
    return m

def desat(mat, sat=0.45, val=0.85):
    """Kurangi saturasi tekstur glTF (stupa krem -> andesit abu)."""
    nt = mat.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None or not b.inputs["Base Color"].is_linked: return
    src = b.inputs["Base Color"].links[0].from_socket
    hs = nt.nodes.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = sat; hs.inputs["Value"].default_value = val
    nt.links.new(src, hs.inputs["Color"]); nt.links.new(hs.outputs[0], b.inputs["Base Color"])

def add_detail(mat, scale=6.0, strength=0.35):
    """Tambahkan bump noise ke material glTF yang ada (stupa, dsb.)."""
    nt = mat.node_tree
    b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if b is None or b.inputs["Normal"].is_linked: return
    n = noise(nt, world_pos(nt), scale, 8, 0.65)
    bump(nt, b, n.outputs["Fac"], strength, 0.02)
    b.inputs["Roughness"].default_value = max(b.inputs["Roughness"].default_value, 0.8)

# ---------- impor ----------
S1 = bpy.context.scene

def new_coll(name, scene=None):
    c = bpy.data.collections.new(name); (scene or S1).collection.children.link(c); return c

def activate(coll):
    for lc in S1.view_layers[0].layer_collection.children:
        lc.exclude = lc.collection is not coll
        if lc.collection is coll: S1.view_layers[0].active_layer_collection = lc

def import_glb(name, coll):
    activate(coll)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.import_scene.gltf(filepath=os.path.join(SKF, name, name + ".glb"))
    objs = list(bpy.context.selected_objects)
    bpy.context.view_layer.update()
    return objs

def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi

def rooted(objs, name):
    """Pasang empty induk agar model bisa diskala/diposisikan sebagai satu kesatuan."""
    r = bpy.data.objects.new(name, None); objs[0].users_collection[0].objects.link(r)
    for o in objs:
        if o.parent is None: o.parent = r
    return r

def place(root, pivot, s, loc, rz=0.0, mirror_x=False):
    M = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Scale(s, 4) @ Matrix.Translation(-pivot)
    if mirror_x: M = Matrix.Diagonal((-1, 1, 1, 1)) @ M
    root.matrix_world = M

def cube(name, coll, lo, hi, mat=None, bevel=0.0):
    me = bpy.data.meshes.new(name)
    x0, y0, z0 = lo; x1, y1, z1 = hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me.from_pydata(v, [], f); me.update()
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    if mat: me.materials.append(mat)
    if bevel:
        md = o.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 2
    return o

def plane(name, coll, size, mat, z=0.0, subdiv=0, ctr=(0, 0)):
    h = size / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(ctr[0] - h, ctr[1] - h, z), (ctr[0] + h, ctr[1] - h, z), (ctr[0] + h, ctr[1] + h, z), (ctr[0] - h, ctr[1] + h, z)], [], [(0, 1, 2, 3)])
    me.update(); o = bpy.data.objects.new(name, me); coll.objects.link(o); me.materials.append(mat)
    return o

def cyl(name, coll, r, depth, loc, mat, verts=12, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); coll.objects.link(o); o.location = loc; o.rotation_euler = rot
    me.materials.append(mat); return o

def uvsphere(name, coll, r, loc, mat, scale=(1, 1, 1)):
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=r); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); coll.objects.link(o); o.location = loc; o.scale = scale
    me.materials.append(mat); return o

def ray_hits(depsgraph, origin, direction, dist=1e4):
    ok, loc, nrm, idx, ob, mtx = S1.ray_cast(depsgraph, origin, direction, distance=dist)
    return (loc, ob) if ok else (None, None)

# ---------- elemen atmosfer ----------
def volume_box(name, coll, lo, hi, density, color=(1, 0.9, 0.8), aniso=0.5):
    m, nt, b = mat_new(name + "_vol")
    nt.nodes.remove(b)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    pv = N(nt, "ShaderNodeVolumePrincipled")
    setin(pv, Color=(*color, 1), Density=density, Anisotropy=aniso)
    # kabut sedikit menipis ke atas
    s = sep_xyz(nt, world_pos(nt))
    d = math_node(nt, "MULTIPLY", math_node(nt, "EXPONENT", math_node(nt, "MULTIPLY", s.outputs[2], -1.0 / max(1.0, (hi[2] - lo[2]) * 0.45))), density)
    nt.links.new(d, pv.inputs["Density"])
    nt.links.new(pv.outputs[0], out.inputs["Volume"])
    o = cube(name, coll, lo, hi, m)
    return o

def rnd_node(nd, kind, mn, mx):
    """Random Value (indeks soket berbeda antar versi): cari soket Min/Max sesuai tipe."""
    rv = nd.new("FunctionNodeRandomValue"); rv.data_type = kind
    T = "VALUE" if kind == "FLOAT" else "VECTOR"
    for i in rv.inputs:
        if i.type == T and i.name == "Min": i.default_value = mn
        if i.type == T and i.name == "Max": i.default_value = mx
    return next(o for o in rv.outputs if o.type == T and o.enabled)

def dust(name, coll, lo, hi, count, radius, strength, scene_fps=24):
    """Partikel debu emas melayang (Geometry Nodes, deterministik terhadap waktu)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(random.uniform(lo[0], hi[0]), random.uniform(lo[1], hi[1]), random.uniform(lo[2], hi[2])) for _ in range(count)], [], [])
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nd = ng.nodes; L = ng.links
    gi = nd.new("NodeGroupInput"); go = nd.new("NodeGroupOutput")
    st = nd.new("GeometryNodeInputSceneTime"); pos = nd.new("GeometryNodeInputPosition")
    nz = nd.new("ShaderNodeTexNoise"); nz.noise_dimensions = "4D"
    nz.inputs["Scale"].default_value = 0.35; nz.inputs["Detail"].default_value = 1.0
    w = nd.new("ShaderNodeMath"); w.operation = "MULTIPLY"; w.inputs[1].default_value = 0.08
    L.new(st.outputs["Seconds"], w.inputs[0]); L.new(w.outputs[0], nz.inputs["W"]); L.new(pos.outputs[0], nz.inputs["Vector"])
    sub = nd.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    L.new(nz.outputs["Color"], sub.inputs[0])
    sc_ = nd.new("ShaderNodeVectorMath"); sc_.operation = "SCALE"; sc_.inputs["Scale"].default_value = 2.4
    L.new(sub.outputs[0], sc_.inputs[0])
    up = nd.new("ShaderNodeVectorMath"); up.operation = "SCALE"; up.inputs[0].default_value = (0.05, 0.02, 0.06)
    L.new(st.outputs["Seconds"], up.inputs["Scale"])
    add = nd.new("ShaderNodeVectorMath"); add.operation = "ADD"; L.new(sc_.outputs[0], add.inputs[0]); L.new(up.outputs[0], add.inputs[1])
    sp = nd.new("GeometryNodeSetPosition"); L.new(gi.outputs[0], sp.inputs["Geometry"]); L.new(add.outputs[0], sp.inputs["Offset"])
    ico = nd.new("GeometryNodeMeshIcoSphere"); ico.inputs["Radius"].default_value = radius; ico.inputs["Subdivisions"].default_value = 1
    rvo = rnd_node(nd, "FLOAT", 0.35, 1.4)
    iop = nd.new("GeometryNodeInstanceOnPoints")
    L.new(sp.outputs[0], iop.inputs["Points"]); L.new(ico.outputs[0], iop.inputs["Instance"]); L.new(rvo, iop.inputs["Scale"])
    sm = nd.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value = emis_mat(name + "_mat", (1.0, 0.72, 0.32), strength)
    L.new(iop.outputs[0], sm.inputs["Geometry"]); L.new(sm.outputs[0], go.inputs[0])
    md = o.modifiers.new("gn", "NODES"); md.node_group = ng
    return o

def grass_tufts(name, coll, ground, lo, hi, density, mat):
    """Rumpun rumput kering disebar di area tertentu (GN instance)."""
    # mesh rumpun: 9 helai segitiga melengkung
    me = bpy.data.meshes.new(name + "_tuft"); vs = []; fs = []
    for i in range(9):
        a = random.uniform(0, math.tau); r0 = random.uniform(0, 0.06); h = random.uniform(0.25, 0.6)
        lean = random.uniform(0.05, 0.25); w = 0.012
        bx, by = math.cos(a) * r0, math.sin(a) * r0; dx, dy = math.cos(a) * lean, math.sin(a) * lean
        px, py = -math.sin(a) * w, math.cos(a) * w
        k = len(vs)
        vs += [(bx - px, by - py, 0), (bx + px, by + py, 0), (bx + dx * 0.4 + px * 0.6, by + dy * 0.4 + py * 0.6, h * 0.55),
               (bx + dx * 0.4 - px * 0.6, by + dy * 0.4 - py * 0.6, h * 0.55), (bx + dx, by + dy, h)]
        fs += [(k, k + 1, k + 2, k + 3), (k + 3, k + 2, k + 4)]
    me.from_pydata(vs, [], fs); me.update(); me.materials.append(mat)
    tuft = bpy.data.objects.new(name + "_tuft", me)
    src = bpy.data.collections.new(name + "_src")  # tidak ditautkan ke scene
    src.objects.link(tuft)
    # area sebar: bidang terpisah dengan subdivisi
    pm = bpy.data.meshes.new(name)
    pm.from_pydata([(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2])], [], [(0, 1, 2, 3)])
    o = bpy.data.objects.new(name, pm); coll.objects.link(o)
    ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nd = ng.nodes; L = ng.links
    gi = nd.new("NodeGroupInput"); go = nd.new("NodeGroupOutput")
    dp = nd.new("GeometryNodeDistributePointsOnFaces"); dp.distribute_method = "RANDOM"
    pos = nd.new("GeometryNodeInputPosition"); nz = nd.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.12
    L.new(pos.outputs[0], nz.inputs["Vector"])
    mr = nd.new("ShaderNodeMapRange"); mr.inputs[1].default_value = 0.4; mr.inputs[2].default_value = 0.62
    mr.inputs[3].default_value = 0.05; mr.inputs[4].default_value = density
    L.new(nz.outputs["Fac"], mr.inputs[0]); L.new(mr.outputs[0], dp.inputs["Density"])
    L.new(gi.outputs[0], dp.inputs["Mesh"])
    oi = nd.new("GeometryNodeObjectInfo"); oi.inputs["Object"].default_value = tuft
    rro = rnd_node(nd, "FLOAT_VECTOR", (0, 0, 0), (0.12, 0.12, math.tau))
    rso = rnd_node(nd, "FLOAT", 0.5, 1.5)
    iop = nd.new("GeometryNodeInstanceOnPoints")
    L.new(dp.outputs["Points"], iop.inputs["Points"]); L.new(oi.outputs["Geometry"], iop.inputs["Instance"])
    L.new(rro, iop.inputs["Rotation"]); L.new(rso, iop.inputs["Scale"])
    L.new(iop.outputs[0], go.inputs[0])
    md = o.modifiers.new("gn", "NODES"); md.node_group = ng
    return o

def volcano(coll, loc, radius, height, mat):
    import bmesh
    me = bpy.data.meshes.new("gunung"); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=96, radius1=radius, radius2=radius * 0.06, depth=height)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=6, use_grid_fill=True)
    for v in bm.verts:
        n = math.sin(v.co.x * 0.004 + 1.3) * math.cos(v.co.y * 0.005) + 0.5 * math.sin(v.co.x * 0.013)
        v.co.z += height * 0.5; v.co += Vector((0, 0, n * height * 0.04))
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new("gunung", me); coll.objects.link(o); o.location = loc; me.materials.append(mat)
    return o

def haze_mat(name, col, k):
    """Siluet jauh tertutup kabut udara: emisi warna cakrawala."""
    m, nt, b = mat_new(name)
    setin(b, Base_Color=(0.05, 0.04, 0.035, 1), Roughness=1.0, Emission_Color=(*col, 1), Emission_Strength=k)
    return m

# ---------- dunia & lampu ----------
def sun_vec(elev, az):
    """az: derajat dari +Y ke arah +X."""
    e, a = math.radians(elev), math.radians(az)
    return Vector((math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)))

def world_sky(name, elev, az, strength, sun_int=0.6):
    w = bpy.data.worlds.new(name)
    if w.node_tree is None: w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky"); sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = math.radians(elev)
    sky.sun_rotation = math.radians(SKY_ROT_SIGN * az + SKY_ROT_OFFSET)
    sky.sun_intensity = sun_int; sky.sun_size = math.radians(1.2)
    try: sky.air_density = 1.2; sky.aerosol_density = 3.0
    except Exception: pass
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tint = mix(nt, 1.0, sky.outputs[0], (1.0, 0.74, 0.5), "MULTIPLY")  # nuansa jam emas
    nt.links.new(tint, bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs[0])
    return w

SKY_ROT_SIGN, SKY_ROT_OFFSET = 1.0, -180.0  # terukur: rotasi 0 = matahari di -Y, 90 = di -X

def world_dusk(name):
    """Langit senja-malam: gradasi jingga di cakrawala ke biru tua di zenit."""
    w = bpy.data.worlds.new(name)
    if w.node_tree is None: w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord"); s = sep_xyz(nt, tc.outputs["Generated"])
    c = ramp(nt, s.outputs[2], [(0.0, (0.03, 0.02, 0.02)), (0.5, (0.55, 0.22, 0.07)), (0.56, (0.22, 0.12, 0.09)), (0.75, (0.035, 0.045, 0.10)), (1.0, (0.01, 0.014, 0.04))])
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 0.6
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(c, bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs[0])
    return w

def light(name, coll, kind, loc, energy, color, size=0.1, target=None, spot=None):
    d = bpy.data.lights.new(name, kind); d.energy = energy; d.color = color
    if kind in ("POINT", "SPOT"): d.shadow_soft_size = size
    if kind == "AREA": d.size = size
    if kind == "SUN": d.angle = math.radians(size)
    if spot: d.spot_size = math.radians(spot[0]); d.spot_blend = spot[1]
    o = bpy.data.objects.new(name, d); coll.objects.link(o); o.location = loc
    if target is not None:
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o

def sun_lamp(coll, elev, az, energy, color):
    d = sun_vec(elev, az)
    o = light("matahari", coll, "SUN", d * 100, energy, color, size=0.6)
    o.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    # cakram matahari (EEVEE tidak menggambar sun disc dari Sky Texture)
    uvsphere("cakram_matahari", coll, 20.0, d * 1500, emis_mat("matahari_cakram", (1.0, 0.62, 0.3), 60.0))
    return o

# ---------- kamera ----------
def make_cam(name, coll, lens, fstop, focus_obj=None, focus_dist=10.0):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.05; cd.clip_end = 5000
    cd.sensor_width = 36
    cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop
    if focus_obj: cd.dof.focus_object = focus_obj
    else: cd.dof.focus_distance = focus_dist
    o = bpy.data.objects.new(name, cd); coll.objects.link(o)
    return o

def key_cam(cam, f0, f1, pos_fn, look_fn):
    prev = None
    for f in range(f0, f1 + 1):
        t = (f - f0) / max(1, f1 - f0)
        p = Vector(pos_fn(t)); cam.location = p
        e = (Vector(look_fn(t)) - p).to_track_quat("-Z", "Y").to_euler()
        if prev is not None: e.make_compatible(prev)
        cam.rotation_euler = e; prev = e.copy()
        cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)

def key_exposure(sc, pts):
    for f, v in pts:
        sc.view_settings.exposure = v; sc.keyframe_insert("view_settings.exposure", frame=f)

# ---------- render & compositor ----------
def setup_render(sc):
    sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    ee.taa_render_samples = SAMPLES
    for k, v in dict(use_raytracing=True, ray_tracing_method="SCREEN", use_shadows=True, use_fast_gi=True,
                     use_volumetric_shadows=True, volumetric_tile_size="16" if PREV else "4",
                     volumetric_samples=32 if PREV else 96, volumetric_shadow_samples=8 if PREV else 24,
                     volumetric_sample_distribution=0.85, volumetric_ray_depth=8,
                     shadow_ray_count=1 if PREV else 2, shadow_step_count=6, motion_blur_steps=1,
                     bokeh_max_size=60.0, shadow_pool_size="1024", shadow_resolution_scale=0.75).items():
        try: setattr(ee, k, v)
        except Exception as e: log("eevee", k, e)
    try:
        ee.ray_tracing_options.resolution_scale = "2" if PREV else "1"
        ee.ray_tracing_options.use_denoise = True
    except Exception: pass
    r = sc.render
    r.resolution_x, r.resolution_y = 1920, 1080; r.resolution_percentage = int(round(RES * 100))
    r.fps = 24; r.use_motion_blur = True; r.motion_blur_shutter = 0.35
    r.film_transparent = False
    r.image_settings.file_format = "PNG"; r.image_settings.color_mode = "RGB"; r.image_settings.color_depth = "8"
    vs = sc.view_settings; vs.view_transform = "AgX"
    try: vs.look = "AgX - Medium High Contrast"
    except Exception: pass
    sc.display_settings.display_device = "sRGB"
    # compositor: glare bloom untuk sorot emas
    ng = bpy.data.node_groups.new(sc.name + "_comp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers"); rl.scene = sc
    gl = ng.nodes.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"
    try: gl.inputs["Quality"].default_value = "Medium" if PREV else "High"
    except Exception: pass
    gl.inputs["Threshold"].default_value = 1.0; gl.inputs["Strength"].default_value = 0.6
    gl.inputs["Size"].default_value = 0.75; gl.inputs["Saturation"].default_value = 1.1
    gl.inputs["Tint"].default_value = (1.0, 0.82, 0.55, 1)
    go = ng.nodes.new("NodeGroupOutput")
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"]); ng.links.new(gl.outputs[0], go.inputs[0])
    sc.compositing_node_group = ng
    r.use_compositing = True

# =====================================================================
# SHOT 1 — stupa Borobudur, crane naik
# =====================================================================
def build_s1():
    sc = S1; sc.name = "S1_Stupa"
    C = new_coll("SET1_stupa")
    # sumber klaster stupa (3 stupa), diinstansikan beberapa kali
    src = bpy.data.collections.new("SRC_stupa"); S1.collection.children.link(src)
    objs = import_glb("borobudur", src)
    for o in objs:
        for ms in getattr(o.data, "materials", []) or []:
            if ms: add_detail(ms, 5.0, 0.4); desat(ms)
    lo, hi = bbox(objs); piv = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    S1.collection.children.unlink(src)
    s = 5.0 / (hi.z - lo.z) * 1.0  # klaster: stupa terbesar ±5 m
    log("stupa skala", round(s, 2), "lebar klaster", round((hi.x - lo.x) * s, 1), "m")
    def inst(loc, rz, k=1.0):
        e = bpy.data.objects.new("stupa", None); e.instance_type = "COLLECTION"; e.instance_collection = src
        C.objects.link(e)
        e.matrix_world = Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rz), 4, "Z") @ Matrix.Scale(s * k, 4) @ Matrix.Translation(-piv)
    andesit = mat_andesit()
    # teras bertingkat batu andesit
    T1, T2 = 1.3, 2.7
    cube("teras1", C, (-26, 5, -0.3), (26, 70, T1), andesit, 0.05)
    cube("teras2", C, (-17, 17, -0.3), (17, 70, T2), andesit, 0.05)
    cube("teras3", C, (-9, 31, -0.3), (9, 70, T2 + 1.4), andesit, 0.05)
    # klaster di tanah mengapit jalur kamera, lalu di teras
    inst((-6.6, -0.5, 0), 20); inst((6.8, 1.5, 0), -35)
    inst((-9.5, 10, T1), 75); inst((9.0, 9, T1), 140); inst((0.5, 12.5, T1), 210, 0.9)
    inst((-6, 22, T2), 10); inst((7, 23, T2), 95)
    inst((-1.5, 36, T2 + 1.4), 160, 1.1); inst((13, 30, T2), 40); inst((-14, 29, T2), 250)
    # tanah lapang
    field = mat_field(); plane("tanah", C, 900, field, 0.0)
    gm = mat_grass()  # jalur kamera dibiarkan bersih agar helai tidak menembus lensa
    for i, (a_, b_) in enumerate((((-22, -16), (-1.4, 5.2)), ((1.4, -16), (22, 5.2)), ((-1.4, -3.0), (1.4, 5.2)))):
        grass_tufts("rumput1_%d" % i, C, None, (*a_, 0.0), (*b_, 0.0), 9.0, gm)
    # gunung jauh berkabut
    volcano(C, (-1300, 2600, 0), 1100, 520, haze_mat("gunung_kabut", (0.62, 0.42, 0.36), 0.32))
    volcano(C, (1500, 3000, 0), 1200, 400, haze_mat("gunung_kabut2", (0.66, 0.45, 0.38), 0.36))
    # langit & matahari
    ELEV, AZ = 4.5, 6.0
    sc.world = world_sky("langit_jam_emas", ELEV, AZ, 0.2)
    sun_lamp(C, ELEV, AZ, 6.5, (1.0, 0.64, 0.34))
    volume_box("kabut1", C, (-120, -40, -1), (120, 160, 18), 0.0045, (1.0, 0.86, 0.7), 0.6)
    dust("debu1", C, (-7, 1, 0.3), (7, 16, 10), 380, 0.006, 18.0)
    # kamera crane
    foc = bpy.data.objects.new("fokus1", None); C.objects.link(foc); foc.location = (0.5, 12, 2.5)
    cam = make_cam("cam1", C, 32, 5.6, foc)
    key_cam(cam, 1, 144,
            lambda t: (lerp(-0.3, 0.4, t), lerp(-7.5, -1.0, smooth(t)), lerp(0.55, 8.5, smooth(t))),
            lambda t: (lerp(-0.6, 0.6, t), 30, lerp(3.2, 4.2, smooth(t))))
    sc.camera = cam
    sc.frame_start, sc.frame_end = 1, 144
    setup_render(sc)
    key_exposure(sc, [(1, -0.6), (14, 0.25), (134, 0.25), (144, 2.6)])
    return sc

# =====================================================================
# SHOT 2 — Gerbang Trowulan, dolly maju menembus celah
# =====================================================================
def build_s2():
    sc = bpy.data.scenes.new("S2_Gerbang")
    C = new_coll("SET2_gerbang")
    objs = import_glb("trowulan", C)
    brick = mat_brick()
    for o in objs:
        if o.type == "MESH":
            mats = [m for m in o.data.materials if m]
            if not any("rusted" in m.name for m in mats):
                o.data.materials.clear(); o.data.materials.append(brick)
    root = rooted(objs, "ROOT_gerbang")
    lo, hi = bbox(objs)
    s = 13.0 / (hi.z - lo.z)
    place(root, Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)), s, Vector((0, 0, 0)))
    bpy.context.view_layer.update()
    lo, hi = bbox(objs)
    log("gerbang", "ukuran", tuple(round(x, 1) for x in hi - lo))
    # cari celah gerbang: sinar sepanjang +Y pada ketinggian 3 m
    dg = bpy.context.evaluated_depsgraph_get()
    xs = [x * 0.05 for x in range(-160, 161)]
    free = [ray_hits(dg, Vector((x, lo.y - 5, 3.0)), Vector((0, 1, 0)), 200)[0] is None for x in xs]
    best, cur = (0, 0), None
    for i, f in enumerate(free + [False]):
        if f and cur is None: cur = i
        if not f and cur is not None:
            if (i - cur) > (best[1] - best[0]) and abs(xs[(cur + i - 1) // 2]) < 4: best = (cur, i)
            cur = None
    gx = (xs[best[0]] + xs[best[1] - 1]) / 2; gw = xs[best[1] - 1] - xs[best[0]]
    # kedalaman celah (sinar ke bawah sepanjang sumbu tengah)
    ys = [lo.y + i * 0.1 for i in range(int((hi.y - lo.y) / 0.1) + 1)]
    wall = [y for y in ys if ray_hits(dg, Vector((gx - gw / 2 - 0.4, y, 3.0)), Vector((1, 0, 0)), 0.5)[0] is not None]
    gy0, gy1 = (min(wall), max(wall)) if wall else (lo.y, hi.y)
    gz, _ = ray_hits(dg, Vector((gx, (gy0 + gy1) / 2, 20)), Vector((0, 0, -1)), 50)
    gz = gz.z if gz else 0.0
    log("celah gerbang x=%.2f lebar=%.2f y=%.1f..%.1f lantai=%.2f" % (gx, gw, gy0, gy1, gz))
    root.location.x -= gx  # pusatkan celah di x=0
    # tanah lapang + rumput, puing bata
    field = mat_field(); plane("tanah", C, 900, field, 0.1)
    grass_tufts("rumput2", C, None, (-20, -45, 0.0), (20, -8, 0.0), 8.0, mat_grass())
    for i in range(14):
        x = random.choice([-1, 1]) * random.uniform(3.5, 14); y = random.uniform(-30, 4)
        sz = (random.uniform(0.3, 0.9), random.uniform(0.25, 0.6), random.uniform(0.1, 0.35))
        o = cube("puing", C, (-sz[0], -sz[1], -0.05), (sz[0], sz[1], sz[2]), brick, 0.02)
        o.location = (x, y, 0); o.rotation_euler = (0, 0, random.uniform(0, 3.14))
    volcano(C, (-1500, 2600, 0), 1100, 480, haze_mat("gunung_kabut3", (0.64, 0.43, 0.37), 0.34))
    ELEV, AZ = 7.0, -4.0
    sc.world = world_sky("langit_gerbang", ELEV, AZ, 0.2)
    sun_lamp(C, ELEV, AZ, 6.5, (1.0, 0.62, 0.32))
    volume_box("kabut2", C, (-80, -70, -1), (80, 110, 20), 0.006, (1.0, 0.85, 0.68), 0.7)
    dust("debu2", C, (-5, -12, 1.5), (5, 10, 8), 450, 0.006, 18.0)
    gyc = (gy0 + gy1) / 2
    cam = make_cam("cam2", C, 28, 4.0, None, 20.0)
    ze = max(gz, 0) + 1.65
    key_cam(cam, 145, 264,
            lambda t: (0.0, lerp(gy0 - 26, gy1 - 1.0, t), lerp(ze + 0.5, ze, t)),
            lambda t: (0.0, gy1 + 60, lerp(ze + 4.2, ze + 2.2, t)))
    for f in range(145, 265, 4):
        cy = lerp(gy0 - 26, gy1 - 1.0, (f - 145) / 119)
        cam.data.dof.focus_distance = max(gy0 - cy + 1.5, 4.0) if cy < gy0 - 2.5 else 12.0
        cam.data.keyframe_insert("dof.focus_distance", frame=f)
    sc.camera = cam
    sc.frame_start, sc.frame_end = 145, 264
    setup_render(sc)
    key_exposure(sc, [(145, 2.6), (154, 0.0), (252, 0.0), (264, 2.4)])
    sc.collection.children.link(C); S1.collection.children.unlink(C)
    return sc

# =====================================================================
# SHOT 3 — Pendapa joglo, penari gambyong
# =====================================================================
def build_s3():
    sc = bpy.data.scenes.new("S3_Pendapa")
    C = new_coll("SET3_pendapa")
    objs = import_glb("joglo", C)
    tegel, jati, jati_gelap, yard = mat_tegel(), mat_jati(), mat_jati("kayu_jati_plafon", 0.6), mat_yard()
    genteng, nt_, gb = mat_new("genteng_senja")
    setin(gb, Base_Color=(0.16, 0.06, 0.035, 1), Roughness=0.8)
    bump(nt_, gb, noise(nt_, world_pos(nt_), 3.0, 5).outputs["Fac"], 0.3)
    PEND = (0.51, -1.02, 6.18, 3.47)  # jejak atap pendapa (unit model)
    for o in objs:
        if o.type != "MESH" or not o.data.materials or not o.data.materials[0]: continue
        mn = o.data.materials[0].name
        if mn.startswith("Concrete"):
            lo_, hi_ = bbox([o])
            if hi_.x - lo_.x > 9: o.hide_render = True; o.hide_viewport = True  # pelat halaman ganda (z-fight)
            else: o.data.materials[0] = tegel
        elif mn.startswith("Earth"): o.data.materials[0] = yard
        elif mn.startswith("Wood"): o.data.materials[0] = jati
        elif mn.startswith("Paint___Light_Gray"): o.data.materials[0] = jati_gelap
        elif mn.startswith("Roof_Tiles"): o.data.materials[0] = genteng
    root = rooted(objs, "ROOT_joglo")
    S = 2.6
    pc = Vector(((PEND[0] + PEND[2]) / 2, (PEND[1] + PEND[3]) / 2, 0))
    place(root, pc, S, Vector((0, 0, 0)))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    def floor_at(x, y, top=1.6):
        hit, ob = ray_hits(dg, Vector((x, y, top)), Vector((0, 0, -1)), 20)
        return hit.z if hit else 0.0
    yz = floor_at(0, -9.5)
    lo, hi = bbox(objs)
    log("joglo ukuran", tuple(round(x, 1) for x in hi - lo), "halaman z=%.2f" % yz)
    # cari tepi depan lantai pendapa
    fy = -10.0
    for i in range(240):
        y = -10 + i * 0.05
        if floor_at(0, y) > yz + 0.05: fy = y; break
    dy = fy + 2.2            # posisi penari (agak ke depan agar obor depan masuk frame akhir)
    fz = floor_at(0, dy)
    log("tepi depan pendapa y=%.2f, penari y=%.2f lantai z=%.2f" % (fy, dy, fz))
    # tanah luar kompleks
    plane("tanah_luar", C, 600, yard, yz - 0.03)
    # --- penari ---
    with bpy.data.libraries.load(PENARI, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("Penari.rig", "Penari", "Kemben", "Jarik", "Stagen", "Sampur", "Rambut", "Cunduk")]
    for o in dst.objects: C.objects.link(o)
    rig = bpy.data.objects["Penari.rig"]
    rig.location = (0, dy, fz); rig.scale = (1.1, 1.1, 1.1)
    ad = rig.animation_data; act = ad.action if ad else None
    if act is None: act = bpy.data.actions.get("gambyong_loop")
    ad = rig.animation_data_create()
    slot = getattr(ad, "action_slot", None)
    tr = ad.nla_tracks.new(); st = tr.strips.new("gambyong", 265 - 30, act)
    try:
        if slot is not None and st.action_slot is None: st.action_slot = slot
    except Exception: pass
    st.repeat = 3.0
    ad.action = None
    log("aksi", act.name, "rentang", tuple(act.frame_range), "strip", st.frame_start, st.frame_end)
    # --- gamelan kiri & kanan (cermin) ---
    gobjs = import_glb("gamelan", C)
    groot = rooted(gobjs, "ROOT_gamelan")
    glo, ghi = bbox(gobjs)
    gs = 0.8
    gpiv = Vector(((glo.x + ghi.x) / 2, (glo.y + ghi.y) / 2, glo.z))
    place(groot, gpiv, gs, Vector((-3.3, dy + 3.4, fz)), 0)
    activate(C)
    gdup = []
    for o in gobjs:
        d = o.copy(); C.objects.link(d); gdup.append(d)
    m = {o: d for o, d in zip(gobjs, gdup)}
    for o, d in m.items():
        if o.parent in m: d.parent = m[o.parent]
    groot2 = bpy.data.objects.new("ROOT_gamelan_kanan", None); C.objects.link(groot2)
    for d in gdup:
        if d.parent is None: d.parent = groot2
    place(groot2, gpiv, gs, Vector((-3.3, dy + 3.4, fz)), 0, mirror_x=True)
    # --- wayang golek di atas kotak wayang ---
    kotak = mat_jati("kotak_wayang", 0.75)
    for nm, x, rz in (("arjuna", -1.75, 0), ("semar", 1.75, 0)):
        k = cube("kotak_" + nm, C, (x - 0.45, dy - 0.95, fz), (x + 0.45, dy - 0.45, fz + 0.45), kotak, 0.015)
        wo = import_glb(nm, C); wr = rooted(wo, "ROOT_" + nm)
        wl, wh = bbox(wo); ws = 0.72 / (wh.z - wl.z)
        place(wr, Vector(((wl.x + wh.x) / 2, (wl.y + wh.y) / 2, wl.z)), ws, Vector((x, dy - 0.7, fz + 0.45)), rz)
        log(nm, "skala", round(ws, 4))
        light("sorot_" + nm, C, "SPOT", (x * 0.6, dy - 2.8, fz + 2.0), 90, (1.0, 0.72, 0.45), 0.1, (x, dy - 0.7, fz + 0.85), (22, 0.5))
    activate(C)
    # --- obor & lampu minyak ---
    bambu = mat_jati("bambu", 2.2); api = emis_mat("api", (1.0, 0.42, 0.09), 4.5)
    flick = []
    for x, y in ((-2.1, fy - 0.35), (2.1, fy - 0.35), (-6.5, fy - 0.6), (6.5, fy - 0.6)):
        cyl("tiang_obor", C, 0.035, 1.9, (x, y, yz + 0.95), bambu, 8)
        cyl("mangkuk_obor", C, 0.07, 0.12, (x, y, yz + 1.92), bambu, 10)
        fl = uvsphere("api_obor", C, 0.065, (x, y, yz + 2.08), api, (1, 1, 2.0))
        L = light("obor", C, "POINT", (x, y, yz + 2.15), 170, (1.0, 0.5, 0.18), 0.08)
        flick.append((L, fl, 170))
    kaca = emis_mat("lampu_kaca", (1.0, 0.6, 0.25), 6.0); besi = mat_jati("besi_lampu", 0.4)
    def ceil_at(x, y):
        h = ray_hits(dg, Vector((x, y, fz + 0.5)), Vector((0, 0, 1)), 20)[0]
        return h.z if h else fz + 4.0
    for x, y in ((-3.8, dy + 0.5), (3.8, dy + 0.5), (-3.0, dy + 4.0), (3.0, dy + 4.0)):
        top = ray_hits(dg, Vector((x, y, fz + 0.5)), Vector((0, 0, 1)), 20)[0]
        tz = top.z if top else fz + 4.0
        lz = min(fz + 2.35, tz - 0.3)
        cyl("rantai", C, 0.006, tz - lz, (x, y, (tz + lz) / 2), besi, 6)
        cyl("lampu_minyak", C, 0.07, 0.2, (x, y, lz - 0.1), kaca, 12)
        L = light("lampu", C, "POINT", (x, y, lz - 0.12), 90, (1.0, 0.58, 0.25), 0.05)
        flick.append((L, None, 90))
    # lampu kunci penari (sorot hangat) + rim belakang + isi lembut
    sz_ = min(fz + 3.2, ceil_at(0.8, dy - 2.4) - 0.25); rz_ = min(fz + 3.4, ceil_at(0, dy + 3.5) - 0.25)
    light("sorot_penari", C, "SPOT", (0.8, dy - 2.4, sz_), 850, (1.0, 0.74, 0.45), 0.2, (0, dy, fz + 1.0), (40, 0.6))
    light("rim_penari", C, "SPOT", (0.0, dy + 3.5, rz_), 350, (1.0, 0.6, 0.3), 0.3, (0, dy, fz + 1.2), (40, 0.6))
    light("isi_kiri", C, "AREA", (-3.0, dy - 4.5, fz + 1.8), 50, (0.55, 0.62, 1.0), 2.0, (0, dy, fz + 1.0))
    log("sorot z=%.2f rim z=%.2f" % (sz_ - fz, rz_ - fz))
    # kedip api: energi & skala nyala acak halus per frame
    for L, fl, e0 in flick:
        ph = random.uniform(0, 100)
        for f in range(265, 433, 2):
            k = 0.86 + 0.1 * math.sin(f * 0.9 + ph) + 0.06 * math.sin(f * 2.3 + ph * 1.7)
            L.data.energy = e0 * k; L.data.keyframe_insert("energy", frame=f)
            if fl: fl.scale = (1, 1, 2.0 * (0.9 + 0.12 * (k - 0.86) / 0.16)); fl.keyframe_insert("scale", frame=f)
    sc.world = world_dusk("langit_senja_malam")
    volume_box("asap", C, (-25, -25, yz - 0.5), (25, 25, fz + 9), 0.02, (1.0, 0.9, 0.8), 0.45)
    dust("debu3", C, (-3, dy - 4, fz + 0.3), (3, dy + 3, fz + 3.0), 90, 0.004, 8.0)
    # kamera: dolly pelan mendekat lalu berhenti (komposisi simetris, ruang judul di atas)
    foc = bpy.data.objects.new("fokus3", None); C.objects.link(foc); foc.location = (0, dy, fz + 1.1)
    cam = make_cam("cam3", C, 45, 2.8, foc)
    ystart, yend = dy - 10.8, dy - 8.3
    u = lambda t: 1 - (1 - min(1, t / 0.85)) ** 2  # berhenti ±f403, sisanya hold
    key_cam(cam, 265, 432,
            lambda t: (lerp(0.3, 0.0, u(t)), lerp(ystart, yend, u(t)), lerp(yz + 1.9, fz + 1.15, u(t))),
            lambda t: (0.0, dy, lerp(fz + 1.4, fz + 1.55, u(t))))
    sc.camera = cam
    sc.frame_start, sc.frame_end = 265, 432
    setup_render(sc)
    sc.eevee.volumetric_end = 80.0
    key_exposure(sc, [(265, 2.4), (274, 0.0)])
    sc.collection.children.link(C); S1.collection.children.unlink(C)
    return sc

# ---------- render satu scene (subproses: blender -b <blend> -S <scene> -P skrip -- --render-only) ----------
def render_current():
    sc = bpy.context.scene
    sc.render.resolution_percentage = int(round(RES * 100))
    sc.eevee.taa_render_samples = SAMPLES
    os.makedirs(OUT, exist_ok=True)
    done = 0
    for f in range(F0, F1 + 1, max(1, A.step)):
        if not (sc.frame_start <= f <= sc.frame_end): continue
        path = os.path.join(OUT, "%04d.png" % f)
        if os.path.exists(path) and os.path.getsize(path) > 0: continue
        sc.frame_set(f); sc.render.filepath = path
        t = time.time(); bpy.ops.render.render(write_still=True); done += 1
        log("frame", f, sc.name, "%.1fs" % (time.time() - t))
    log("scene", sc.name, "selesai,", done, "frame baru")

if A.render_only:
    render_current(); sys.exit(0)

# ---------- bangun ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
S1 = bpy.context.scene
log("bangun scene… out=", OUT, "res", RES, "samples", SAMPLES)
s3 = build_s3(); log("S3 siap")
s2 = build_s2(); log("S2 siap")
s1 = build_s1(); log("S1 siap")
for lc in S1.view_layers[0].layer_collection.children: lc.exclude = False
for sc in (s1, s2):
    sc.eevee.volumetric_end = 400.0
s3.eevee.volumetric_end = 80.0
blend = os.path.join(tempfile.gettempdir(), "naramotion_intro_preview.blend") if (PREV or A.no_save) else BLEND_OUT
os.makedirs(os.path.dirname(blend), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
log("tersimpan", blend)
if A.build_only: sys.exit(0)

# render tiap scene di subproses agar animasi scene tersebut dievaluasi sebagai scene aktif
import subprocess
for name, a, b in SHOTS:
    if b < F0 or a > F1: continue
    cmd = [bpy.app.binary_path, "-b", blend, "-S", name, "-P", os.path.abspath(__file__), "--", "--render-only",
           "--out", OUT, "--frames", "%d-%d" % (max(a, F0), min(b, F1)), "--res-scale", str(RES), "--samples", str(SAMPLES)]
    if A.step > 1:  # jaga kisi langkah global
        first = next((f for f in range(F0, F1 + 1, A.step) if f >= a), None)
        if first is None or first > b: continue
        cmd[cmd.index("--frames") + 1] = "%d-%d" % (first, min(b, F1)); cmd += ["--step", str(A.step)]
    if PREV: cmd.append("--preview")
    log("render", name, " ".join(cmd[-8:]))
    subprocess.run(cmd, check=False)
log("selesai ->", OUT)
