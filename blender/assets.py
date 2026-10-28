"""NaraMotion — aset 3D (ikon, emblem, pola) dibuat sepenuhnya dari skrip Blender.

Pemakaian:
  blender -b --factory-startup -P blender/assets.py -- <out_dir> [nama ...] [--samples N] [--size PX]
Tanpa nama = render semua. Palet mengikuti token CSS NaraMotion (emas matte + pernis gelap).
"""
import bpy, bmesh, json, math, os, sys
from mathutils import Vector, Matrix

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGV[0] if ARGV else "assets/3d")
OPTS = {"samples": 96, "size": 640}
NAMES = []
i = 1
while i < len(ARGV):
    if ARGV[i].startswith("--"):
        OPTS[ARGV[i][2:]] = int(ARGV[i + 1]); i += 2
    else:
        NAMES.append(ARGV[i]); i += 1
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- Token warna (sama dengan css/style.css) ----------
LACQUER = "#1e170e"
LACQUER_2 = "#2a2014"
GOLD = "#d2a54a"
GOLD_BRIGHT = "#ecc978"
GOLD_DEEP = "#8d6a2c"
CREAM = "#ebe0c6"
COPPER = "#cf7440"


def lin(hexcol):
    h = hexcol.lstrip("#")
    c = [int(h[k:k + 2], 16) / 255 for k in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


_MATS = {}
def mat(name, color, metal=0.0, rough=0.4, coat=0.0, emit=0.0, aniso=0.0):
    key = (name,)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(color), 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if "Coat Weight" in b.inputs:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.12
    if "Anisotropic" in b.inputs and aniso:
        b.inputs["Anisotropic"].default_value = aniso
    if emit:
        b.inputs["Emission Color"].default_value = (*lin(color), 1)
        b.inputs["Emission Strength"].default_value = emit
    _MATS[key] = m
    return m


def M_GOLD(): return mat("gold", GOLD, metal=1, rough=0.26)
def M_GOLD_SATIN(): return mat("gold_satin", GOLD_DEEP, metal=1, rough=0.42)
def M_GOLD_BRIGHT(): return mat("gold_bright", GOLD_BRIGHT, metal=1, rough=0.2)
def M_LACQUER(): return mat("lacquer", LACQUER, metal=0, rough=0.38, coat=0.6)
def M_LACQUER_2(): return mat("lacquer2", LACQUER_2, metal=0, rough=0.45, coat=0.3)
def M_CREAM(): return mat("cream", CREAM, metal=0, rough=0.5)
def M_COPPER(): return mat("copper", COPPER, metal=1, rough=0.3)
def M_GLOW(): return mat("glow", GOLD_BRIGHT, emit=6)


# ---------- Utilitas adegan ----------
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev_type in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            if any(d.type == dev_type for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev_type
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = OPTS["samples"]
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = OPTS["size"]
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = -0.2
    w = bpy.data.worlds.new("world")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.11, 0.085, 0.055, 1)
    bg.inputs["Strength"].default_value = 0.8
    return sc


def light(name, loc, size, power, color=(1, 1, 1), target=(0, 0, 0.5)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size = size
    ld.energy = power
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def studio_lights():
    light("key", (4, -5, 6), 5, 1400, (1.0, 0.92, 0.8))
    light("fill", (-6, -3, 3), 8, 420, (1.0, 0.95, 0.88))
    light("rim", (0.5, 6, 4.5), 4, 1300, (1.0, 0.78, 0.42))
    light("top", (0, 0, 8), 6, 300, (1, 0.93, 0.82))


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def assign(ob, m):
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return ob


def smooth(ob, bevel=0.0, segs=3):
    for p in ob.data.polygons:
        p.use_smooth = True
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = segs
        mod.limit_method = "ANGLE"
    return ob


def cube(name, size, loc, m, bevel=0.06):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    smooth(ob, bevel, 4)
    return assign(ob, m)


def cyl(name, r, depth, loc, m, rot=(0, 0, 0), verts=96, bevel=0.02):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
    ob = bpy.context.active_object
    ob.name = name
    smooth(ob, bevel, 3)
    return assign(ob, m)


def sphere(name, r, loc, m, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=64, ring_count=32)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    smooth(ob)
    return assign(ob, m)


def torus(name, R, r, loc, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, rotation=rot, major_segments=128, minor_segments=24)
    ob = bpy.context.active_object
    ob.name = name
    smooth(ob)
    return assign(ob, m)


def cone(name, r1, depth, loc, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=0, depth=depth, location=loc, rotation=rot, vertices=64)
    ob = bpy.context.active_object
    ob.name = name
    smooth(ob)
    return assign(ob, m)


def tube_between(name, a, b, r, m):
    a, b = Vector(a), Vector(b)
    d = b - a
    ob = cyl(name, r, d.length, (a + b) / 2, m, verts=32, bevel=0)
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return ob


def poly_curve(name, pts, m, bevel=0.05, closed=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = bevel
    cu.bevel_resolution = 6
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1)
    sp.use_cyclic_u = closed
    ob = link(bpy.data.objects.new(name, cu))
    ob.data.materials.append(m)
    return ob


def prism(name, pts2d, depth, m, y=0.0, bevel=0.03):
    """Poligon 2D di bidang XZ, diekstrusi sepanjang Y (menghadap kamera depan)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new((x, y - depth / 2, z)) for x, z in pts2d]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, depth, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 4
        mod.limit_method = "ANGLE"
    me.materials.append(m)
    return ob


def frame_camera(direction=(0.62, -1.0, 0.62), pad=1.16, ortho=True, target_z=None):
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    pts = []
    for ob in sc.objects:
        if ob.type == "MESH" and not ob.name.startswith("ground"):
            dg = bpy.context.evaluated_depsgraph_get()
            ev = ob.evaluated_get(dg)
            for c in ev.bound_box:
                pts.append(ev.matrix_world @ Vector(c))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (lo + hi) / 2
    cd = bpy.data.cameras.new("cam")
    cd.type = "ORTHO" if ortho else "PERSP"
    cam = link(bpy.data.objects.new("cam", cd))
    sc.camera = cam
    d = Vector(direction).normalized()
    cam.location = center + d * 30
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    loc = [inv @ p for p in pts]
    xs, ys = [p.x for p in loc], [p.y for p in loc]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    cam.location = cam.matrix_world @ Vector((cx, cy, 0))
    cd.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * pad
    cd.clip_end = 100
    return cam


def render(name):
    sc = bpy.context.scene
    path = os.path.join(OUT, name + ".png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[nara] rendered", path)


# ---------- Registry aset ----------
ASSETS = {}
def asset(name):
    def deco(fn):
        ASSETS[name] = fn
        return fn
    return deco


@asset("node")
def make_node():
    """Modul sensor MARG: badan pernis, pelat emas, chip, LED, tali."""
    cube("body", (1.7, 1.15, 0.42), (0, 0, 0.21), M_LACQUER(), bevel=0.14)
    cube("plate", (1.36, 0.82, 0.05), (0, 0, 0.44), M_GOLD_SATIN(), bevel=0.04)
    cube("chip", (0.44, 0.44, 0.08), (-0.22, 0, 0.5), M_LACQUER_2(), bevel=0.02)
    for k in range(6):
        x = -0.38 + k * 0.064
        cube(f"pinA{k}", (0.025, 0.08, 0.02), (x + 0.0, 0.27, 0.47), M_GOLD_BRIGHT(), bevel=0.005)
        cube(f"pinB{k}", (0.025, 0.08, 0.02), (x + 0.0, -0.27, 0.47), M_GOLD_BRIGHT(), bevel=0.005)
    sphere("led", 0.07, (0.42, 0.18, 0.49), M_GLOW(), scale=(1, 1, 0.5))
    torus("ring", 0.17, 0.025, (0.38, -0.14, 0.48), M_GOLD())
    for s in (-1, 1):
        cube(f"strap{s}", (0.2, 1.5, 0.05), (s * 0.98, 0, 0.12), M_LACQUER_2(), bevel=0.02)
        cube(f"buckle{s}", (0.26, 0.22, 0.09), (s * 0.98, 0, 0.17), M_GOLD(), bevel=0.03)
    frame_camera((0.55, -1.0, 0.85))


@asset("gyro")
def make_gyro():
    """Giroskop: tiga cincin gimbal emas mengelilingi rotor pernis."""
    torus("ringX", 1.0, 0.055, (0, 0, 1.2), M_GOLD(), rot=(math.radians(90), 0, 0))
    torus("ringY", 0.86, 0.05, (0, 0, 1.2), M_GOLD_SATIN(), rot=(0, math.radians(90), math.radians(25)))
    torus("ringZ", 0.72, 0.045, (0, 0, 1.2), M_GOLD_BRIGHT(), rot=(math.radians(20), 0, 0))
    cyl("rotor", 0.42, 0.18, (0, 0, 1.2), M_LACQUER(), rot=(math.radians(20), 0, 0), bevel=0.04)
    torus("rotorband", 0.42, 0.03, (0, 0, 1.2), M_GOLD(), rot=(math.radians(20), 0, 0))
    cyl("axle", 0.035, 1.5, (0, 0, 1.2), M_GOLD_BRIGHT(), rot=(math.radians(20), 0, 0), bevel=0)
    cyl("stem", 0.06, 0.25, (0, 0, 0.12), M_GOLD_SATIN())
    cyl("base", 0.55, 0.12, (0, 0, 0.0), M_LACQUER(), bevel=0.04)
    torus("baserim", 0.55, 0.025, (0, 0, 0.06), M_GOLD())
    frame_camera((0.6, -1.0, 0.5))


@asset("accel")
def make_accel():
    """Akselerometer: kubus massa pernis dengan tiga panah sumbu (warna sama dengan grafik x/y/z)."""
    cube("mass", (0.8, 0.8, 0.8), (0, 0, 0), M_LACQUER(), bevel=0.12)
    cube("face", (0.5, 0.02, 0.5), (0, -0.41, 0), M_GOLD_SATIN(), bevel=0.03)
    axes = [((1, 0, 0), M_GOLD_BRIGHT()), ((0, 0, 1), M_CREAM()), ((0, 1, 0), M_COPPER())]
    for (ax, m) in axes:
        a = Vector(ax)
        tube_between("shaft", a * 0.42, a * 1.25, 0.05, m)
        c = cone("tip", 0.12, 0.3, tuple(a * 1.38), m)
        c.rotation_euler = a.to_track_quat("Z", "Y").to_euler()
    sphere("core", 0.08, (0, -0.43, 0), M_GLOW(), scale=(1, 0.4, 1))
    frame_camera((0.75, -1.0, 0.6))


@asset("mag")
def make_mag():
    """Magnetometer: kompas pernis dengan jarum emas-tembaga dan 12 penanda arah."""
    cyl("disc", 1.0, 0.18, (0, 0, 0), M_LACQUER(), bevel=0.06)
    torus("rim", 1.0, 0.07, (0, 0, 0.06), M_GOLD())
    cyl("face", 0.84, 0.02, (0, 0, 0.1), M_LACQUER_2(), bevel=0.005)
    for k in range(12):
        a = k / 12 * math.tau
        big = k % 3 == 0
        ob = cube(f"tick{k}", (0.05, 0.16 if big else 0.09, 0.03), (math.sin(a) * 0.72, math.cos(a) * 0.72, 0.12), M_GOLD_BRIGHT() if big else M_GOLD_SATIN(), bevel=0.01)
        ob.rotation_euler = (0, 0, -a)
    n = cone("north", 0.1, 0.62, (0, 0.31, 0.16), M_GOLD_BRIGHT(), rot=(math.radians(-90), 0, 0))
    n.scale = (1, 1, 1)
    s = cone("south", 0.1, 0.62, (0, -0.31, 0.16), M_COPPER(), rot=(math.radians(90), 0, 0))
    for ob in (n, s):
        ob.scale = (1, 0.35, 1)
    cyl("cap", 0.08, 0.08, (0, 0, 0.2), M_GOLD())
    frame_camera((0.35, -1.0, 1.25))


def gunungan_outline(n=28):
    def bez(p0, p1, p2, p3, t):
        u = 1 - t
        return tuple(u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d for a, b, c, d in zip(p0, p1, p2, p3))
    segs = [((200, 12), (262, 92), (330, 190), (352, 300)), ((352, 300), (368, 380), (360, 440), (340, 500))]
    right = []
    for sgm in segs:
        for k in range(n):
            right.append(bez(*sgm, k / n))
    right.append((340, 500))
    left = [(400 - x, y) for x, y in reversed(right)]
    pts = right + left[1:-1]
    return [((x - 200) / 200, (500 - y) / 200) for x, y in pts]


@asset("gunungan")
def make_gunungan():
    """Emblem gunungan/kayon: bingkai emas, panel pernis, pohon hayat, dan gapura."""
    outer = gunungan_outline()
    prism("frame", outer, 0.16, M_GOLD(), bevel=0.03)
    cx, cz = 0.0, 1.0
    inner = [(cx + (x - cx) * 0.86, cz + (z - cz) * 0.88 + 0.03) for x, z in outer]
    prism("panel", inner, 0.06, M_LACQUER(), y=-0.09, bevel=0.015)
    # Pohon hayat: batang dan cabang melengkung
    poly_curve("trunk", [(0, -0.13, 0.45), (0, -0.13, 1.9)], M_GOLD_BRIGHT(), bevel=0.035)
    for k, h in enumerate((0.8, 1.15, 1.45, 1.72)):
        w = 0.55 - k * 0.11
        for s in (-1, 1):
            pts = [(s * (w * t), -0.13, h + 0.28 * math.sin(t * math.pi * 0.9) * (1 - 0.4 * t)) for t in [j / 10 for j in range(11)]]
            poly_curve(f"branch{k}{s}", pts, M_GOLD_SATIN(), bevel=0.022)
            sphere(f"leaf{k}{s}", 0.055, pts[-1], M_GOLD_BRIGHT())
    # Gapura di kaki gunungan
    cube("gate_base", (0.8, 0.1, 0.1), (0, -0.14, 0.13), M_GOLD(), bevel=0.02)
    for s in (-1, 1):
        cube(f"gate_post{s}", (0.1, 0.1, 0.34), (s * 0.27, -0.14, 0.33), M_GOLD(), bevel=0.02)
    cube("gate_top", (0.72, 0.1, 0.08), (0, -0.14, 0.53), M_GOLD(), bevel=0.02)
    sphere("jewel", 0.07, (0, -0.16, 2.12), M_GLOW())
    frame_camera((0.28, -1.0, 0.18), pad=1.12)


@asset("dancer")
def make_dancer():
    """Figur penari emas dari pose model gerak web (Gambyong), di atas alas pernis."""
    with open(os.path.join(HERE, "pose_gambyong.json")) as f:
        J = json.load(f)
    B = {k: Vector((v[0], -v[2], v[1])) for k, v in J.items()}
    bones = [("pelvis", "spine"), ("spine", "chest"), ("chest", "neck"), ("neck", "head"),
             ("neck", "shoulderL"), ("shoulderL", "elbowL"), ("elbowL", "wristL"), ("wristL", "handL"),
             ("neck", "shoulderR"), ("shoulderR", "elbowR"), ("elbowR", "wristR"), ("wristR", "handR"),
             ("pelvis", "hipL"), ("hipL", "kneeL"), ("kneeL", "ankleL"), ("ankleL", "toeL"),
             ("pelvis", "hipR"), ("hipR", "kneeR"), ("kneeR", "ankleR"), ("ankleR", "toeR")]
    g = M_GOLD()
    for a, b in bones:
        tube_between(f"b_{a}_{b}", B[a], B[b], 0.034, g)
    for k in B:
        if k not in ("nose", "head"):
            sphere(f"j_{k}", 0.042, B[k], g)
    sphere("head", 0.1, B["head"], g)
    back = B["head"] + (B["head"] - B["nose"]) * 1.0 + Vector((0, 0, -0.01))
    sphere("sanggul", 0.055, back, M_GOLD_SATIN())
    # Kain jarik: kerucut terpotong dari pinggang ke lutut
    hipc = (B["hipL"] + B["hipR"]) / 2
    knee = (B["kneeL"] + B["kneeR"]) / 2
    bpy.ops.mesh.primitive_cone_add(radius1=0.24, radius2=0.14, depth=(hipc - knee).length * 1.15, vertices=64,
                                    location=(hipc + knee) / 2 + Vector((0, 0, -0.03)))
    jarik = bpy.context.active_object
    jarik.rotation_euler = (hipc - knee).to_track_quat("Z", "Y").to_euler()
    smooth(jarik, 0.01)
    assign(jarik, M_LACQUER_2())
    # Sampur dari pinggang ke tangan
    for s in ("L", "R"):
        a, h = B["hip" + s], B["hand" + s]
        mid = (a + h) / 2 + Vector((0, -0.05, -0.28))
        pts = [tuple(((1 - t) ** 2) * a + 2 * (1 - t) * t * mid + (t ** 2) * h) for t in [j / 16 for j in range(17)]]
        poly_curve("sampur" + s, pts, M_COPPER(), bevel=0.016)
    cyl("pedestal", 0.62, 0.14, (B["pelvis"].x, 0, -0.07), M_LACQUER(), bevel=0.04)
    torus("pedrim", 0.62, 0.022, (B["pelvis"].x, 0, 0.0), M_GOLD())
    frame_camera((0.42, -1.0, 0.3), pad=1.1)


@asset("dial")
def make_dial():
    """Dial skor kemiripan: busur emas 270° dengan jarum, untuk Kelas Tari."""
    cyl("disc", 1.0, 0.2, (0, 0, 0), M_LACQUER(), bevel=0.07)
    torus("rim", 1.0, 0.05, (0, 0, 0.08), M_GOLD_SATIN())
    start, span = math.radians(225), math.radians(270)
    arc = [(math.cos(start - span * t) * 0.74, math.sin(start - span * t) * 0.74, 0.14) for t in [j / 60 for j in range(61)]]
    poly_curve("track", arc, M_LACQUER_2(), bevel=0.07)
    val = arc[: int(61 * 0.82)]
    poly_curve("value", [(x, y, z + 0.03) for x, y, z in val], M_GOLD_BRIGHT(), bevel=0.075)
    ang = start - span * 0.82
    tube_between("needle", (0, 0, 0.2), (math.cos(ang) * 0.55, math.sin(ang) * 0.55, 0.2), 0.03, M_GOLD())
    cyl("hub", 0.12, 0.12, (0, 0, 0.2), M_GOLD())
    sphere("tip", 0.05, (math.cos(ang) * 0.74, math.sin(ang) * 0.74, 0.2), M_GLOW())
    frame_camera((0.3, -1.0, 1.3))


@asset("lontar")
def make_lontar():
    """Arsip: tumpukan daun lontar diapit kropak pernis, diikat tali emas."""
    L, W = 2.4, 0.46
    cube("cover_bot", (L + 0.12, W + 0.08, 0.1), (0, 0, 0.05), M_LACQUER(), bevel=0.04)
    for k in range(5):
        z = 0.13 + k * 0.055
        cube(f"leaf{k}", (L, W, 0.04), (0.012 * (k % 2), 0.008 * k, z), M_CREAM(), bevel=0.015)
    top = 0.13 + 5 * 0.055 + 0.03
    cube("cover_top", (L + 0.12, W + 0.08, 0.1), (0, 0, top), M_LACQUER(), bevel=0.04)
    cube("inlay", (L - 0.3, 0.05, 0.02), (0, 0, top + 0.06), M_GOLD(), bevel=0.01)
    for s in (-1, 1):
        sphere(f"stud{s}", 0.06, (s * (L / 2 - 0.08), 0, top + 0.07), M_GOLD_BRIGHT(), scale=(1, 1, 0.6))
    for s in (-0.55, 0.55):
        cyl(f"string{s}", 0.025, top + 0.2, (s, 0, top / 2 + 0.05), M_GOLD(), bevel=0)
        torus(f"knot{s}", 0.06, 0.02, (s, 0, top + 0.12), M_GOLD())
    frame_camera((0.5, -1.0, 0.75))


def M_GOLD_DEEP(): return mat("gold_deep", GOLD_DEEP, metal=1, rough=0.5)


@asset("kawung")
def make_kawung():
    """Ubin relief kawung tanpa sambungan, dirender tegak lurus dari atas (bukan transparan)."""
    sc = bpy.context.scene
    sc.render.film_transparent = False
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    T = 2.0
    cube("ground", (T * 3, T * 3, 0.1), (0, 0, -0.05), mat("ground", "#1b150d", rough=0.55), bevel=0)
    for p in sc.objects["ground"].data.polygons:
        p.use_smooth = False  # alas datar: tanpa gradasi, ubin tersambung mulus
    m = mat("petal", "#5c4520", metal=0.85, rough=0.38)
    for ox in (-T, 0, T):
        for oy in (-T, 0, T):
            for (x, y, sx, sy) in ((0, 0.5, 0.27, 0.44), (0, -0.5, 0.27, 0.44), (0.5, 0, 0.44, 0.27), (-0.5, 0, 0.44, 0.27)):
                sphere("p", 1.0, (ox + x * T / 2 * 1.0, oy + y * T / 2 * 1.0, 0), m, scale=(sx * T / 2 * 0.9, sy * T / 2 * 0.9, 0.09))
            sphere("dot", 0.06, (ox, oy, 0.0), m, scale=(1, 1, 0.6))
            sphere("cdot", 0.06, (ox + T / 2, oy + T / 2, 0.0), m, scale=(1, 1, 0.6))
    for ob in list(sc.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    sd = bpy.data.lights.new("sun", "SUN")
    sd.energy = 2.2
    sd.angle = math.radians(18)
    sd.color = (1, 0.9, 0.75)
    sun = link(bpy.data.objects.new("sun", sd))
    sun.rotation_euler = (math.radians(42), 0, math.radians(-45))
    cd = bpy.data.cameras.new("cam")
    cd.type = "ORTHO"
    cd.ortho_scale = T
    cam = link(bpy.data.objects.new("cam", cd))
    cam.location = (0, 0, 10)
    sc.camera = cam
    sc.view_settings.exposure = 0


def main():
    os.makedirs(OUT, exist_ok=True)
    names = NAMES or list(ASSETS)
    for n in names:
        reset()
        if n != "kawung":
            studio_lights()
        ASSETS[n]()
        render(n)


main()
