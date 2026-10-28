"""NaraMotion — 4 shot B-roll 3D sinematik untuk video profil (EEVEE, Blender 5.x).
B1 node   : penari emas + 10 node sensor IMU di tulang DEF + jejak cahaya pergelangan, studio gelap berkabut.
B2 museum : keris, wayang Arjuna & Semar di atas plinth, lampu sorot + debu volumetrik, dolly menyamping.
B3 gamelan: macro bonang di pendapa senja, DOF sangat dangkal, dolly menyusuri pencon.
B4 outro  : pendapa joglo malam, obor & lampu, penari siluet hangat, kamera mundur & naik (192 frame).
Pemakaian:
  blender -b --factory-startup -P blender/profile_broll.py -- --shot all [--preview] [--frames 1-144] [--step 1] [--out DIR]
Frame yang sudah ada dilewati (render bisa dilanjutkan). Preview mp4 dibuat otomatis bila semua frame final lengkap.
"""
import bpy, bmesh, sys, os, math, random, argparse, time, subprocess
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = "C:/Users/mosto/Desktop/nanramotion"
SKF = ROOT + "/assets_src/sketchfab"
PENARI = ROOT + "/assets_src/penari_rig.blend"
OUT = ROOT + "/assets_src/profile"
FFMPEG = ("C:/Users/mosto/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
          "ffmpeg-9.0-full_build/bin/ffmpeg.exe")
FPS = 24
NFRAMES = {"B1": 144, "B2": 144, "B3": 144, "B4": 192}
JOGLO_S = 2.6     # joglo glb ±5,7 m → pendapa ±14,7 m (atap)
PENARI_S = 1.1    # penari 1,43 m → ±1,58 m


# ---------- util warna & material ----------
def lin(h):
    """hex sRGB → RGBA linear."""
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)

GELAP, EMAS, EMAS2 = lin("1b150d"), lin("d2a54a"), lin("ecc978")


def bsdf_mat(name, base, rough=0.5, metal=0.0, emit=None, strength=0.0, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = base
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = emit; b.inputs["Emission Strength"].default_value = strength
    return m


def proc_mat(name, c1, c2, scale=3.0, rough=(0.25, 0.6), bump=0.15, metal=0.0, fine=40.0, coat=0.0):
    """Material prosedural tidak polos: variasi warna (noise), kekasaran berbintik, bump halus."""
    m = bsdf_mat(name, c1, metal=metal, coat=coat); nt = m.node_tree; N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord")
    n1 = N.new("ShaderNodeTexNoise"); n1.inputs["Scale"].default_value = scale; n1.inputs["Detail"].default_value = 8
    L.new(tc.outputs["Object"], n1.inputs["Vector"])
    cr = N.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].color = c1; cr.color_ramp.elements[1].color = c2
    cr.color_ramp.elements[0].position = 0.35; cr.color_ramp.elements[1].position = 0.7
    L.new(n1.outputs["Fac"], cr.inputs["Fac"]); L.new(cr.outputs["Color"], b.inputs["Base Color"])
    n2 = N.new("ShaderNodeTexNoise"); n2.inputs["Scale"].default_value = fine; n2.inputs["Detail"].default_value = 4
    L.new(tc.outputs["Object"], n2.inputs["Vector"])
    mr = N.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = rough
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.3, 0.7
    L.new(n2.outputs["Fac"], mr.inputs["Value"]); L.new(mr.outputs["Result"], b.inputs["Roughness"])
    bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump; bp.inputs["Distance"].default_value = 0.02
    L.new(n2.outputs["Fac"], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def time_value(nt):
    """Node Value = detik (driver ekspresi sederhana, aman tanpa auto-exec)."""
    v = nt.nodes.new("ShaderNodeValue")
    fc = v.outputs[0].driver_add("default_value"); fc.driver.type = "SCRIPTED"; fc.driver.expression = "frame/24"
    return v


# ---------- util objek ----------
def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob); return ob


def look(ob, target, prev=None):
    q = (Vector(target) - ob.location).to_track_quat("-Z", "Y")
    ob.rotation_euler = q.to_euler("XYZ", prev) if prev is not None else q.to_euler()


def empty(name, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None); e.location = loc; return link(e)


def box(name, size, loc, mat=None, bevel=0.0):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bm.to_mesh(me); bm.free()
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc
    if mat: me.materials.append(mat)
    if bevel:
        md = ob.modifiers.new("bev", "BEVEL"); md.width = bevel; md.segments = 3; md.limit_method = "NONE"
    for p in me.polygons: p.use_smooth = True
    return ob


def cyl(name, r, h, loc, mat=None, verts=32, cone_r2=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r if cone_r2 is None else cone_r2, depth=h)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = len(p.vertices) == 4
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc
    if mat: me.materials.append(mat)
    return ob


def sphere(name, r, loc, mat=None, sub=2):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc
    if mat: me.materials.append(mat)
    return ob


def light(kind, name, loc, energy, color=(1, .7, .4), target=None, size=0.1, spot=None, blend=0.3):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color[:3]
    if kind in ("POINT", "SPOT"): ld.shadow_soft_size = size
    if kind == "AREA": ld.size = size
    if kind == "SUN": ld.angle = size
    if kind == "SPOT": ld.spot_size = math.radians(spot or 30); ld.spot_blend = blend
    ob = link(bpy.data.objects.new(name, ld)); ob.location = loc
    if target is not None: look(ob, target)
    return ob


def bbox(objs, dg=None):
    pts = []
    for o in objs:
        if o.type != "MESH": continue
        ev = o.evaluated_get(dg) if dg else o
        pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def import_glb(name, scale=None, size=None, axis=2, rot=None, loc=(0, 0, 0), pivot=None):
    """Import glb → semua akar di-parent ke empty '<name>_root' (pivot = dasar-tengah bbox, atau titik khusus).
    size: ukuran nyata (m) pada sumbu `axis` setelah rotasi; scale: faktor langsung."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=f"{SKF}/{name}/{name}.glb")
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type in ("CAMERA", "LIGHT")]:
        new.remove(o); bpy.data.objects.remove(o)
    root = empty(name + "_root")
    bpy.context.view_layer.update()
    if rot:  # rotasi dulu agar bbox diukur pada orientasi akhir
        tmp = Matrix.Rotation(rot[0], 4, "X") @ Matrix.Rotation(rot[1], 4, "Y") @ Matrix.Rotation(rot[2], 4, "Z")
        for o in new:
            if o.parent is None: o.matrix_world = tmp @ o.matrix_world
        bpy.context.view_layer.update()
    lo, hi = bbox(new)
    piv = Vector(pivot) if pivot is not None else Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    root.location = piv; bpy.context.view_layer.update()
    for o in new:
        if o.parent is None:
            mw = o.matrix_world.copy(); o.parent = root; o.matrix_world = mw
    s = scale if scale else size / (hi - lo)[axis]
    root.scale = (s, s, s); root.location = loc
    bpy.context.view_layer.update()
    print(f"[broll] {name}: skala {s:.4f}, ukuran nyata {tuple(round(v * s, 2) for v in (hi - lo))} m")
    return root, new


def append_penari(scale=PENARI_S, alas=True, loc=(0, 0, 0)):
    names = ["Penari", "Penari.rig", "Kemben", "Jarik", "Stagen", "Sampur", "Rambut", "Cunduk"] + (["Cylinder"] if alas else [])
    with bpy.data.libraries.load(PENARI, link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
        dst.actions = ["gambyong_loop"]
    col = bpy.data.collections.new("penari"); bpy.context.scene.collection.children.link(col)
    for o in dst.objects: col.objects.link(o)
    rig = bpy.data.objects["Penari.rig"]
    act = bpy.data.actions.get("gambyong_loop")
    if rig.animation_data is None: rig.animation_data_create()
    if rig.animation_data.action is None: rig.animation_data.action = act
    if act and getattr(rig.animation_data, "action_slot", None) is None and len(getattr(act, "slots", [])):
        rig.animation_data.action_slot = act.slots[0]
    root = empty("penari_root", loc)
    for o in dst.objects:
        if o.parent is None: o.parent = root
    root.scale = (scale,) * 3
    if not alas: root.location.z = loc[2] + 0.0
    return rig, root, {o.name: o for o in dst.objects}


# ---------- dunia, render, compositor ----------
def world(col_bottom, col_horizon, col_top, strength=1.0, fog=0.0, fog_col=(1, .85, .6, 1), stars=0.0, aniso=0.3):
    w = bpy.data.worlds.new("w"); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree; N, L = nt.nodes, nt.links
    bg = N["Background"]; bg.inputs["Strength"].default_value = strength
    tc = N.new("ShaderNodeTexCoord"); sx = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Generated"], sx.inputs[0])
    cr = N.new("ShaderNodeValToRGB"); e = cr.color_ramp.elements
    e[0].position, e[0].color = 0.40, col_bottom; e[1].position, e[1].color = 0.95, col_top
    h = e.new(0.52); h.color = col_horizon
    mr = N.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = -1; mr.inputs["From Max"].default_value = 1
    L.new(sx.outputs["Z"], mr.inputs["Value"]); L.new(mr.outputs["Result"], cr.inputs["Fac"])
    col = cr.outputs["Color"]
    if stars:  # bintik bintang samar: voronoi pada arah pandang
        vo = N.new("ShaderNodeTexVoronoi"); vo.inputs["Scale"].default_value = 180
        L.new(tc.outputs["Generated"], vo.inputs["Vector"])
        lt = N.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.06
        L.new(vo.outputs["Distance"], lt.inputs[0])
        sr = N.new("ShaderNodeSeparateColor"); L.new(vo.outputs["Color"], sr.inputs[0])
        gt = N.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.82
        L.new(sr.outputs[0], gt.inputs[0])
        m1 = N.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; L.new(lt.outputs[0], m1.inputs[0]); L.new(gt.outputs[0], m1.inputs[1])
        up = N.new("ShaderNodeMath"); up.operation = "GREATER_THAN"; up.inputs[1].default_value = 0.08
        L.new(sx.outputs["Z"], up.inputs[0])
        m2 = N.new("ShaderNodeMath"); m2.operation = "MULTIPLY"; L.new(m1.outputs[0], m2.inputs[0]); L.new(up.outputs[0], m2.inputs[1])
        m3 = N.new("ShaderNodeMath"); m3.operation = "MULTIPLY"; m3.inputs[1].default_value = stars; L.new(m2.outputs[0], m3.inputs[0])
        ad = N.new("ShaderNodeMix"); ad.data_type = "RGBA"; ad.blend_type = "ADD"; ad.inputs[0].default_value = 1
        L.new(col, ad.inputs[6]); L.new(m3.outputs[0], ad.inputs[7]); col = ad.outputs[2]
    L.new(col, bg.inputs["Color"])
    if fog:
        pv = N.new("ShaderNodeVolumePrincipled"); pv.inputs["Density"].default_value = fog
        pv.inputs["Color"].default_value = fog_col; pv.inputs["Anisotropy"].default_value = aniso
        L.new(pv.outputs[0], N["World Output"].inputs["Volume"])
    return w


def render_setup(preview, motion=0.35, vol_end=40.0, exposure=0.0, look="AgX - Medium High Contrast"):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    ee.taa_render_samples = 12 if preview else 64
    ee.use_raytracing = True; ee.ray_tracing_method = "SCREEN"
    ee.ray_tracing_options.resolution_scale = "2" if preview else "1"
    ee.ray_tracing_options.trace_max_roughness = 0.6
    ee.use_fast_gi = True
    ee.shadow_pool_size = "1024"   # cegah "Shadow buffer full" (bayangan hilang)
    ee.use_shadows = True; ee.shadow_ray_count = 2 if not preview else 1; ee.shadow_step_count = 6
    ee.volumetric_tile_size = "8" if preview else "4"
    ee.volumetric_samples = 48 if preview else 96
    ee.use_volumetric_shadows = True; ee.volumetric_end = vol_end; ee.volumetric_light_clamp = 0
    ee.use_volume_custom_range = False
    ee.bokeh_max_size = 100
    sc.render.use_motion_blur = motion > 0; sc.render.motion_blur_shutter = motion
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.resolution_percentage = 50 if preview else 100
    sc.render.fps = FPS
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    sc.render.use_file_extension = False
    sc.view_settings.view_transform = "AgX"
    try: sc.view_settings.look = look
    except TypeError: pass
    sc.view_settings.exposure = exposure


def compositor(bloom=0.5, thr=1.0, size=0.6, vignette=0.25):
    """Glare (Bloom) + vinyet lembut di compositor (API node-group Blender 5.x)."""
    sc = bpy.context.scene
    ng = bpy.data.node_groups.new("comp", "CompositorNodeTree")
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    N, L = ng.nodes, ng.links
    rl = N.new("CompositorNodeRLayers"); out = N.new("NodeGroupOutput")
    gl = N.new("CompositorNodeGlare")
    gl.inputs["Type"].default_value = "Bloom"; gl.inputs["Quality"].default_value = "High"
    gl.inputs["Threshold"].default_value = thr; gl.inputs["Strength"].default_value = bloom
    gl.inputs["Size"].default_value = size
    L.new(rl.outputs["Image"], gl.inputs["Image"])
    img = gl.outputs["Image"]
    if vignette:
        try:
            el = N.new("CompositorNodeEllipseMask")
            el.inputs["Size"].default_value = (1.25, 1.25)
            bl = N.new("CompositorNodeBlur"); bl.inputs["Size"].default_value = (300, 300)
            L.new(el.outputs["Mask"], bl.inputs["Image"])
            mr = N.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 1 - vignette
            L.new(bl.outputs["Image"], mr.inputs["Value"])
            mx = N.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"
            mx.inputs[0].default_value = 1.0
            L.new(img, mx.inputs[6]); L.new(mr.outputs["Result"], mx.inputs[7]); img = mx.outputs[2]
        except Exception as ex:
            print("[broll] vinyet dilewati:", ex)
    L.new(img, out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True


def camera(name, lens=50, fstop=2.8, focus=None, sensor=36):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = sensor; cd.clip_start = 0.02; cd.clip_end = 400
    cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop; cd.dof.aperture_blades = 7
    if focus: cd.dof.focus_object = focus
    cam = link(bpy.data.objects.new(name, cd)); bpy.context.scene.camera = cam
    return cam


def ease(t):  # gerak pelan: separuh linear, separuh smoothstep (tidak berhenti mati di ujung)
    return 0.5 * t + 0.5 * t * t * (3 - 2 * t)


def anim_cam(cam, n, fn, offset=0, focus=None, focus_fn=None):
    """fn(t) → (posisi, target); dikunci tiap frame."""
    prev = None
    for i in range(1, n + 1):
        t = (i - 1) / (n - 1)
        p, tg = fn(t)
        cam.location = p; look(cam, tg, prev); prev = cam.rotation_euler.copy()
        cam.keyframe_insert("location", frame=i + offset); cam.keyframe_insert("rotation_euler", frame=i + offset)
        if focus is not None and focus_fn is not None:
            focus.location = focus_fn(t); focus.keyframe_insert("location", frame=i + offset)


def dust(name, boxes, n, radius, mat, amp=0.35, seed=3, wspeed=0.05):
    """Debu melayang: titik acak → Geometry Nodes (geser noise 4D terhadap waktu) → instance ico kecil."""
    rnd = random.Random(seed); vs = []
    for (c, s) in boxes:
        for _ in range(n):
            vs.append((c[0] + rnd.uniform(-s[0], s[0]), c[1] + rnd.uniform(-s[1], s[1]), c[2] + rnd.uniform(-s[2], s[2])))
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], [])
    ob = link(bpy.data.objects.new(name, me))
    ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
    pos, tm = N.new("GeometryNodeInputPosition"), N.new("GeometryNodeInputSceneTime")
    nz = N.new("ShaderNodeTexNoise"); nz.noise_dimensions = "4D"; nz.inputs["Scale"].default_value = 0.8
    wm = N.new("ShaderNodeMath"); wm.operation = "MULTIPLY"; wm.inputs[1].default_value = wspeed
    L.new(tm.outputs["Seconds"], wm.inputs[0]); L.new(wm.outputs[0], nz.inputs["W"]); L.new(pos.outputs[0], nz.inputs["Vector"])
    sb = N.new("ShaderNodeVectorMath"); sb.operation = "SUBTRACT"; sb.inputs[1].default_value = (0.5, 0.5, 0.5)
    L.new(nz.outputs["Color"], sb.inputs[0])
    sv = N.new("ShaderNodeVectorMath"); sv.operation = "SCALE"; sv.inputs["Scale"].default_value = amp
    L.new(sb.outputs[0], sv.inputs[0])
    sp = N.new("GeometryNodeSetPosition"); L.new(gi.outputs[0], sp.inputs["Geometry"]); L.new(sv.outputs[0], sp.inputs["Offset"])
    ico = N.new("GeometryNodeMeshIcoSphere"); ico.inputs["Radius"].default_value = radius; ico.inputs["Subdivisions"].default_value = 1
    ip = N.new("GeometryNodeInstanceOnPoints"); L.new(sp.outputs[0], ip.inputs["Points"]); L.new(ico.outputs["Mesh"], ip.inputs["Instance"])
    sm = N.new("GeometryNodeSetMaterial"); sm.inputs["Material"].default_value = mat
    L.new(ip.outputs[0], sm.inputs["Geometry"]); L.new(sm.outputs[0], go.inputs[0])
    ob.modifiers.new("gn", "NODES").node_group = ng
    return ob


def fog_box(size, center, density, col=(1, .85, .7, 1), aniso=0.5):
    """Kabut dalam kubus (bukan world volume: di EEVEE 5 world volume menutup langit)."""
    m = bpy.data.materials.new("kabut"); m.use_nodes = True; nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    pv = nt.nodes.new("ShaderNodeVolumePrincipled"); pv.inputs["Density"].default_value = density
    pv.inputs["Color"].default_value = col; pv.inputs["Anisotropy"].default_value = aniso
    nt.links.new(pv.outputs[0], nt.nodes["Material Output"].inputs["Volume"])
    return box("kabut", size, center, m)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


# ---------- B1: node sensor ----------
NODE_SPEC = [  # (tulang DEF, posisi relatif sepanjang tulang, arah luar kira-kira)
    ("DEF-spine.006", 0.50, (0, -1, 0.25)),   # kepala (dahi)
    ("DEF-spine.003", 0.45, (0, -1, 0)),      # dada
    ("DEF-upper_arm.L", 0.65, (1, -0.5, 0)), ("DEF-upper_arm.R", 0.65, (-1, -0.5, 0)),
    ("DEF-forearm.L", 0.70, (1, -0.6, 0.3)), ("DEF-forearm.R", 0.70, (-1, -0.6, 0.3)),
    ("DEF-thigh.L", 0.75, (0.35, -1, 0)), ("DEF-thigh.R", 0.75, (-0.35, -1, 0)),
    ("DEF-shin.L", 0.55, (0.2, -1, 0)), ("DEF-shin.R", 0.55, (-0.2, -1, 0)),
]


def world_bvh(objs, dg):
    vs, ps = [], []
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); mw = ev.matrix_world; k = len(vs)
        vs += [mw @ v.co for v in me.vertices]; ps += [[k + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(vs, ps)


def node_mesh():
    """Node IMU 3×2×1 cm bersudut membulat: cangkang gelap, pelat emas, LED."""
    me = bpy.data.meshes.new("node_imu"); bm = bmesh.new()
    def rbox(sx, sy, sz, z0, r, mi):
        before = set(bm.faces)
        g = bmesh.ops.create_cube(bm, size=1.0)
        vv = g["verts"]
        for v in vv: v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz + z0))
        ee = list({e for v in vv for e in v.link_edges})
        res = bmesh.ops.bevel(bm, geom=vv + ee, offset=r, segments=3, affect="EDGES", profile=0.5)
        for f in set(bm.faces) - before:
            f.material_index = mi; f.smooth = True
    rbox(0.030, 0.020, 0.0085, -0.00075, 0.0028, 0)      # cangkang
    rbox(0.022, 0.013, 0.0015, 0.0042, 0.0006, 1)        # pelat emas di atas
    g = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.0028, radius2=0.0028, depth=0.0016)
    for v in g["verts"]: v.co += Vector((0.0085, 0, 0.0055))
    for f in {f for v in g["verts"] for f in v.link_faces}: f.material_index = 2; f.smooth = True
    bm.to_mesh(me); bm.free()
    shell = bsdf_mat("node_cangkang", GELAP, rough=0.28, coat=0.6)
    gold = bsdf_mat("node_emas", EMAS2, rough=0.22, metal=1.0)
    led = bpy.data.materials.new("node_led"); led.use_nodes = True; nt = led.node_tree; N, L = nt.nodes, nt.links
    b = N["Principled BSDF"]; b.inputs["Base Color"].default_value = EMAS2; b.inputs["Emission Color"].default_value = EMAS2
    t = time_value(nt); oi = N.new("ShaderNodeObjectInfo")
    # denyut: kuat = 6 + 34·(½+½·sin(2π·0,8·t + fase acak))²
    m1 = N.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; m1.inputs[1].default_value = math.tau * 0.8; L.new(t.outputs[0], m1.inputs[0])
    m2 = N.new("ShaderNodeMath"); m2.operation = "MULTIPLY_ADD"; m2.inputs[1].default_value = math.tau
    L.new(oi.outputs["Random"], m2.inputs[0]); L.new(m1.outputs[0], m2.inputs[2])
    sn = N.new("ShaderNodeMath"); sn.operation = "SINE"; L.new(m2.outputs[0], sn.inputs[0])
    m3 = N.new("ShaderNodeMath"); m3.operation = "MULTIPLY_ADD"; m3.inputs[1].default_value = 0.5; m3.inputs[2].default_value = 0.5
    L.new(sn.outputs[0], m3.inputs[0])
    m4 = N.new("ShaderNodeMath"); m4.operation = "POWER"; m4.inputs[1].default_value = 2; L.new(m3.outputs[0], m4.inputs[0])
    m5 = N.new("ShaderNodeMath"); m5.operation = "MULTIPLY_ADD"; m5.inputs[1].default_value = 70; m5.inputs[2].default_value = 8
    L.new(m4.outputs[0], m5.inputs[0]); L.new(m5.outputs[0], b.inputs["Emission Strength"])
    for m in (shell, gold, led): me.materials.append(m)
    return me


def attach_nodes(rig, body_objs, frame):
    sc = bpy.context.scene; sc.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get(); bvh = world_bvh(body_objs, dg)
    rev = rig.evaluated_get(dg); me = node_mesh(); nodes = []
    for k, (bn, tt, d0) in enumerate(NODE_SPEC):
        pb = rev.pose.bones[bn]
        h, tl = rev.matrix_world @ pb.head, rev.matrix_world @ pb.tail
        ax = (tl - h).normalized(); mid = h.lerp(tl, tt)
        d = Vector(d0).normalized(); d = (d - ax * d.dot(ax)).normalized()
        hit = bvh.ray_cast(mid + d * 0.5, -d, 0.6)
        if hit[0] is None or (hit[0] - mid).length > 0.16:
            loc, n = bvh.find_nearest(mid + d * 0.03)[:2]
        else:
            loc, n = hit[0], hit[1]
        if n.dot(d) < 0: n = -n
        n = (n * 0.5 + d * 0.5).normalized()  # rata-rata dengan arah luar agar tidak miring tajam
        x = (ax - n * ax.dot(n)).normalized(); y = n.cross(x)
        M = Matrix.Translation(loc + n * 0.0045) @ Matrix((x, y, n)).transposed().to_4x4()
        ob = link(bpy.data.objects.new(f"node_{k:02d}_{bn}", me)); ob.pass_index = k
        P = rev.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))  # parent tulang = ekor tulang
        ob.parent = rig; ob.parent_type = "BONE"; ob.parent_bone = bn
        ob.matrix_parent_inverse = P.inverted(); ob.matrix_basis = M
        nodes.append(ob)
    return nodes


def check_nodes(nodes, body_objs, frames):
    """QA numerik: jarak node ke permukaan tubuh terdekat di beberapa frame (harus kecil & stabil)."""
    sc = bpy.context.scene; worst = 0
    for f in frames:
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get(); bvh = world_bvh(body_objs, dg)
        for nd in nodes:
            p = nd.evaluated_get(dg).matrix_world.translation
            dist = bvh.find_nearest(p)[3]; worst = max(worst, dist)
    print(f"[broll] QA node: jarak maks node→permukaan = {worst * 100:.2f} cm pada frame {list(frames)}")


class Trail:
    """Jejak cahaya pergelangan: kurva poly berjumlah titik tetap, diperbarui tiap frame dari riwayat posisi."""
    def __init__(self, rig, bone, mat, hist=72, sub=2, radius=0.005):
        self.rig, self.bone, self.hist, self.sub = rig, bone, hist, sub
        cu = bpy.data.curves.new("trail_" + bone, "CURVE"); cu.dimensions = "3D"
        cu.bevel_depth = radius; cu.bevel_resolution = 3; cu.use_fill_caps = True
        self.sp = cu.splines.new("POLY"); self.np = hist * sub + 1; self.sp.points.add(self.np - 1)
        for i, p in enumerate(self.sp.points): p.radius = (i / (self.np - 1)) ** 1.6
        cu.materials.append(mat)
        self.ob = link(bpy.data.objects.new("trail_" + bone, cu)); self.cache = {}

    def pos(self, f):
        key = round(f * self.sub)
        if key not in self.cache:
            sc = bpy.context.scene; fi = math.floor(f); sc.frame_set(fi, subframe=f - fi)
            dg = bpy.context.evaluated_depsgraph_get(); r = self.rig.evaluated_get(dg)
            self.cache[key] = (r.matrix_world @ r.pose.bones[self.bone].head).copy()
        return self.cache[key]

    def update(self, f):
        # jejak mengalir: posisi lampau pergelangan + hanyutan pelan ke atas/luar (gerak gambyong sangat halus)
        side = 1 if self.bone.endswith(".L") else -1
        for i in range(self.np):
            a = (self.np - 1 - i) / self.sub; sec = a / FPS
            p = self.pos(f - a) + Vector((side * 0.06, 0.05, 0.10)) * sec
            p += Vector((0.012 * math.sin(math.tau * 0.5 * sec + f / FPS * 1.3), 0, 0.01 * math.cos(math.tau * 0.4 * sec))) * min(sec * 2, 1)
            self.sp.points[i].co = (p.x, p.y, p.z, 1)
        fi = math.floor(f); bpy.context.scene.frame_set(fi, subframe=f - fi)


def build_B1(preview):
    sc = reset(); OFF = 48  # frame scene = frame shot + 48 (riwayat jejak tersedia)
    rig, root, P = append_penari(alas=False)
    world(lin("010101"), lin("060504"), lin("020202"), strength=1.0, fog=0.006, fog_col=(1, .86, .62, 1), aniso=0.45)
    # lantai reflektif gelap: batu poles bervariasi + cincin emas tipis
    fl = box("lantai", (40, 40, 0.1), (0, 0, -0.11), proc_mat("lantai_batu", lin("0b0907"), lin("17120b"), scale=0.8,
             rough=(0.14, 0.34), bump=0.03, fine=3, coat=0.3))
    ring_m = bsdf_mat("cincin", lin("120d06"), emit=EMAS, strength=1.2)
    for r in (1.05, 1.6):
        bpy.ops.mesh.primitive_torus_add(major_radius=r, minor_radius=0.0025, major_segments=256, minor_segments=8, location=(0, 0, -0.058))
        o = bpy.context.active_object; o.data.materials.append(ring_m)
    # 10 node sensor menempel ke tulang DEF
    body = [P[n] for n in ("Penari", "Kemben", "Jarik", "Stagen", "Rambut") if n in P]
    nodes = attach_nodes(rig, body, 1 + OFF)
    check_nodes(nodes, body, [1 + OFF, 72 + OFF, 144 + OFF])
    tm = bsdf_mat("jejak", EMAS2, emit=EMAS2, strength=9)
    trails = [Trail(rig, "DEF-hand.L", tm), Trail(rig, "DEF-hand.R", tm)]
    # cahaya: kunci hangat, dua rim emas, sorot atas (kerucut di kabut)
    light("SPOT", "kunci", (-2.0, -3.0, 3.6), 1500, (1, .82, .6), target=(0, 0, 1.0), size=0.35, spot=38, blend=0.6)
    light("SPOT", "rim_L", (-2.6, 2.4, 2.6), 900, (1, .66, .3), target=(0, 0, 1.1), size=0.15, spot=32)
    light("SPOT", "rim_R", (2.8, 2.2, 2.2), 750, (1, .72, .38), target=(0, 0, 1.0), size=0.15, spot=32)
    light("SPOT", "atas", (0.3, 0.6, 5.5), 1600, (1, .78, .5), target=(0, 0, 0), size=0.2, spot=24, blend=0.5)
    light("SPOT", "latar", (0, 8, 4.5), 350, (1, .6, .25), target=(0, 3, 0), size=0.3, spot=40, blend=0.8)
    # kamera: orbit 30° + dolly-in, fokus ke dada
    fo = empty("fokus"); fo.parent = rig; fo.parent_type = "BONE"; fo.parent_bone = "DEF-spine.003"
    cam = camera("cam", lens=50, fstop=2.2, focus=fo)
    def fn(t):
        e = ease(t); az = math.radians(-112 + 30 * e); dist = 4.9 - 1.85 * e
        tz = 0.82 + 0.25 * e; cz = 1.05 + 0.22 * e
        return Vector((math.cos(az) * dist, math.sin(az) * dist, cz)), Vector((0, -0.1, tz))
    anim_cam(cam, NFRAMES["B1"], fn, offset=OFF)
    render_setup(preview, motion=0.35, vol_end=30)
    compositor(bloom=0.55, thr=0.9, size=0.55, vignette=0.3)
    def per_frame(f):
        for tr in trails: tr.update(f)
    return OFF, per_frame


# ---------- B2: museum ----------
def build_B2(preview):
    sc = reset()
    world(lin("010101"), lin("040302"), lin("020202"), strength=1.0, fog=0.05, fog_col=(1, .9, .75, 1), aniso=0.5)
    floor_m = proc_mat("lantai_beton", lin("0d0b09"), lin("1a1612"), scale=1.2, rough=(0.12, 0.45), bump=0.08, fine=12, coat=0.2)
    wall_m = proc_mat("dinding", lin("120e09"), lin("1d160e"), scale=1.5, rough=(0.7, 0.95), bump=0.06, fine=8)
    stone_m = proc_mat("plinth_batu", lin("1c1915"), lin("2c2721"), scale=6, rough=(0.45, 0.8), bump=0.25, fine=60)
    wood_m = proc_mat("kayu_gelap", lin("1b0f07"), lin("2e1a0c"), scale=14, rough=(0.25, 0.45), bump=0.06, fine=90, coat=0.4)
    brass = bsdf_mat("kuningan", EMAS, rough=0.3, metal=1.0)
    rope = bsdf_mat("tali_beludru", lin("3a0d0b"), rough=0.85)
    box("lantai", (30, 20, 0.1), (1.3, 3, -0.05), floor_m)
    box("dinding", (30, 0.2, 7), (1.3, 3.2, 3.5), wall_m)
    for i, x in enumerate((-1.4, 0.65, 1.95, 4.0)):  # pilaster dinding (memberi ritme latar)
        box(f"pilaster{i}", (0.28, 0.12, 7), (x, 3.06, 3.5), wall_m)
    # tiga plinth: posisi (x, y), tinggi
    items = [("keris", 0.0, 0.25, 1.00), ("arjuna", 1.3, 0.55, 0.80), ("semar", 2.6, 0.2, 0.85)]
    tops = {}
    for n, x, y, h in items:
        box("plinth_" + n, (0.46, 0.46, h - 0.03), (x, y, (h - 0.03) / 2), stone_m, bevel=0.004)
        box("tutup_" + n, (0.52, 0.52, 0.03), (x, y, h - 0.015), wood_m, bevel=0.003)
        tops[n] = Vector((x, y, h))
    # keris berdiri (gagang di bawah) di atas dudukan kayu kecil; arjuna 0,7 m; semar 0,62 m (dengan alasnya)
    t = tops["keris"]
    box("dudukan_keris", (0.14, 0.08, 0.05), t + Vector((0, 0, 0.025)), wood_m, bevel=0.004)
    import_glb("keris", size=0.5, axis=2, rot=(-math.pi / 2, 0, 0), loc=t + Vector((0, 0, 0.035)))
    import_glb("arjuna", size=0.70, axis=2, rot=(0, 0, math.radians(-20)), loc=tops["arjuna"])
    import_glb("semar", size=0.62, axis=2, rot=(0, 0, math.radians(15)), loc=tops["semar"])
    # lampu sorot hangat dari atas tiap objek + cahaya dinding redup
    for n, x, y, h in items:
        light("SPOT", "sorot_" + n, (x + 0.2, y - 0.45, 3.4), 1500, (1, .74, .45), target=(x, y, h + 0.35), size=0.04, spot=24, blend=0.3)
    light("AREA", "isi", (1.3, -3.5, 2.2), 8, (1, .85, .7), target=(1.3, 0.3, 1.2), size=4)
    light("SPOT", "cuci_dinding", (1.3, 1.2, 4.8), 160, (1, .6, .3), target=(1.3, 1.8, 1.0), size=0.5, spot=70, blend=1.0)
    dm = bsdf_mat("debu", lin("fff2d8"), rough=1.0, emit=lin("ffdca0"), strength=0.02)
    dust("debu", [((x, y - 0.25, 2.2), (0.55, 0.55, 1.1)) for _, x, y, _ in items], 380, 0.0011, dm, amp=0.3)
    # kamera: dolly menyamping, fokus berpindah halus ke objek terdekat di tengah bingkai
    fo = empty("fokus")
    cam = camera("cam", lens=40, fstop=1.8, focus=fo)
    cy, cz = -1.3, 1.36
    def fn(t):
        x = -0.25 + 3.1 * ease(t)
        return Vector((x, cy, cz)), Vector((x + 0.2, 0.3, 1.26))
    def ffn(t):
        x = -0.25 + 3.1 * ease(t) + 0.2; w = [math.exp(-((x - it[1]) / 0.45) ** 2) + 1e-6 for it in items]
        s = sum(w); return Vector((sum(wi * it[1] for wi, it in zip(w, items)) / s,
                                  sum(wi * it[2] for wi, it in zip(w, items)) / s, 1.3))
    anim_cam(cam, NFRAMES["B2"], fn, focus=fo, focus_fn=ffn)
    render_setup(preview, motion=0.3, vol_end=20)
    compositor(bloom=0.45, thr=0.85, size=0.6, vignette=0.35)
    return 0, None


# ---------- joglo (B3 & B4) ----------
def joglo():
    """Joglo diskalakan ×2,6; titik tengah lantai pendapa (Mesh1_Concrete) jadi (0,0,0)."""
    pv = (3.345, 1.23, 0.12)
    root, objs = import_glb("joglo", scale=JOGLO_S, pivot=pv, loc=(0, 0, 0))
    yard = (-0.08 - pv[2]) * JOGLO_S
    earth = proc_mat("tanah_halaman", lin("1d140c"), lin("33241a"), scale=0.6, rough=(0.75, 0.95), bump=0.4, fine=8)
    batu = proc_mat("lantai_pendapa", lin("1a1510"), lin("2a2219"), scale=1.5, rough=(0.2, 0.5), bump=0.08, fine=10, coat=0.25)
    for o in objs:
        if o.type == "MESH" and "Earth" in o.name:
            o.data.materials.clear(); o.data.materials.append(earth)
        elif o.type == "MESH" and "Concrete" in o.name:  # lantai pendapa: batu gelap berpoles (bukan beton terang)
            o.data.materials.clear(); o.data.materials.append(batu)
    box("tanah_luar", (400, 400, 0.1), (0, 0, yard - 0.06), earth)
    return root, objs, yard


# ---------- B3: gamelan ----------
def build_B3(preview):
    sc = reset()
    world(lin("0d0704"), lin("c47a3a"), lin("1e2546"), strength=0.35)
    joglo(); fog_box((16, 12, 6), (0, 0, 2.5), 0.012, (1, .8, .55, 1), 0.6)
    groot, gobjs = import_glb("gamelan", scale=1.0, loc=(0, 1.2, 0))
    bon = [o for o in gobjs if o.type == "MESH" and any("bonang" in (m.name if m else "").lower() for m in o.data.materials)]
    lo, hi = bbox(bon)
    print(f"[broll] bonang bbox {tuple(round(v, 2) for v in lo)} → {tuple(round(v, 2) for v in hi)}")
    # dua tabuh bonang sederhana diletakkan di atas rak
    wood = proc_mat("tabuh_kayu", lin("3a2010"), lin("5a3418"), scale=30, rough=(0.35, 0.55), bump=0.05)
    cord = proc_mat("tabuh_tali", lin("5a1410"), lin("7a2016"), scale=200, rough=(0.8, 0.95), bump=0.6, fine=300)
    for k, (dx, ang) in enumerate(((0.35, 18), (0.48, 34))):
        g = empty(f"tabuh{k}", (lo.x + dx, lo.y - 0.02, hi.z + 0.012)); g.rotation_euler = (0, math.radians(88), math.radians(ang))
        s = cyl(f"tabuh{k}_gagang", 0.006, 0.34, (0, 0, 0.0), wood); s.parent = g
        hd = cyl(f"tabuh{k}_kepala", 0.016, 0.07, (0, 0, 0.19), cord, cone_r2=0.014); hd.parent = g
    # matahari senja menyamping + pantulan hangat
    sun = light("SUN", "senja", (0, 0, 10), 4.5, (1, .62, .32), size=math.radians(1.5))
    sun.rotation_euler = (Vector((-1.0, -0.3, -0.22)).normalized()).to_track_quat("-Z", "Y").to_euler()
    light("AREA", "pantul", (2.5, -2.0, 1.2), 15, (1, .7, .45), target=(0, 1.2, 0.5), size=2)
    light("AREA", "sisi_senja", (lo.x + 3.2, lo.y - 0.6, 1.1), 260, (1, .55, .25), target=((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z), size=1.2)
    # kamera: dolly menyusuri pencon bonang, lensa makro, DOF sangat dangkal
    fo = empty("fokus"); cam = camera("cam", lens=70, fstop=1.6, focus=fo)
    y0, z0 = lo.y - 0.62, hi.z + 0.24
    def fn(t):
        x = lo.x + 0.15 + (hi.x - lo.x - 0.55) * ease(t)
        return Vector((x, y0, z0)), Vector((x + 0.3, (lo.y + hi.y) / 2, hi.z - 0.1))
    def ffn(t):
        x = lo.x + 0.15 + (hi.x - lo.x - 0.55) * ease(t)
        return Vector((x + 0.3, lo.y + 0.12, hi.z - 0.08))
    anim_cam(cam, NFRAMES["B3"], fn, focus=fo, focus_fn=ffn)
    render_setup(preview, motion=0.3, vol_end=40, exposure=-0.6)
    compositor(bloom=0.4, thr=1.0, size=0.6, vignette=0.3)
    return 0, None


# ---------- B4: outro ----------
def build_B4(preview):
    sc = reset()
    world(lin("070a12"), lin("1c2c55"), lin("0a1430"), strength=1.0, stars=5.0)
    _, _, yard = joglo(); fog_box((34, 40, 12), (0, -6, 5), 0.003, (1, .85, .7, 1), 0.5)
    rig, root, P = append_penari(alas=False)
    flame = bsdf_mat("api", lin("ffb04a"), emit=lin("ff9a30"), strength=40)
    lamp_m = bsdf_mat("lampion", lin("ffd9a0"), emit=lin("ffc070"), strength=18)
    pole = proc_mat("tiang_obor", lin("1e140b"), lin("2c1d10"), scale=20, rough=(0.5, 0.8))
    rnd = random.Random(7)
    def flicker(ld, base):
        ld.energy = base; ld.keyframe_insert("energy", frame=1)
        fc = ld.animation_data.action.fcurves[0] if hasattr(ld.animation_data.action, "fcurves") else None
        if fc is None:
            from bpy_extras import anim_utils
            fc = anim_utils.action_get_channelbag_for_slot(ld.animation_data.action, ld.animation_data.action_slot).fcurves[0]
        m = fc.modifiers.new("NOISE"); m.scale = 14 + rnd.random() * 6; m.strength = base * 0.06; m.phase = rnd.random() * 100   # nyala api lembut, bukan kedip
    # obor di halaman depan pendapa
    for i, (x, y) in enumerate(((-7.2, -5.8), (7.2, -5.8), (-7.2, 2.5), (7.2, 2.5))):
        cyl(f"obor{i}", 0.035, 1.7, (x, y, yard + 0.85), pole)
        cyl(f"obor{i}_mangkuk", 0.09, 0.12, (x, y, yard + 1.75), pole, cone_r2=0.05)
        f = sphere(f"obor{i}_api", 0.07, (x, y, yard + 1.9), flame); f.scale = (1, 1, 1.9)
        flicker(light("POINT", f"obor{i}_L", (x, y, yard + 1.95), 260, (1, .55, .2), size=0.12).data, 260)
    # lampu gantung di bawah atap pendapa
    for i, (x, y) in enumerate(((-4.4, -3.4), (4.4, -3.4), (-4.4, 3.4), (4.4, 3.4))):
        cyl(f"kabel{i}", 0.004, 0.8, (x, y, 2.85), pole)
        sphere(f"lampion{i}", 0.11, (x, y, 2.35), lamp_m).scale = (1, 1, 1.3)
        flicker(light("POINT", f"lampion{i}_L", (x, y, 2.35), 100, (1, .65, .32), size=0.1).data, 140)
    # cahaya belakang kuat (siluet hangat) + bulan dingin sangat lemah
    light("SPOT", "punggung", (0, 3.6, 2.6), 450, (1, .62, .28), target=(0, 0, 1.0), size=0.6, spot=40, blend=0.8)
    light("AREA", "isi_depan", (0, -6, 1.0), 150, (1, .75, .5), target=(0, 0, 0.9), size=3)
    moon = light("SUN", "bulan", (0, 0, 10), 1.1, (.55, .65, 1.0), size=math.radians(2))
    moon.rotation_euler = (Vector((0.6, 0.6, -0.45)).normalized()).to_track_quat("-Z", "Y").to_euler()
    # kamera: mulai dekat, mundur pelan & naik; ruang tengah-atas dibiarkan tenang
    fo = empty("fokus"); fo.parent = rig; fo.parent_type = "BONE"; fo.parent_bone = "DEF-spine.003"
    cam = camera("cam", lens=28, fstop=2.8, focus=fo)
    def fn(t):
        e = ease(t)
        return Vector((0.0, -6.0 - 9.5 * e, 1.3 + 1.4 * e)), Vector((0, 0, 1.3 + 2.9 * e))
    anim_cam(cam, NFRAMES["B4"], fn)
    render_setup(preview, motion=0.3, vol_end=60)
    compositor(bloom=0.35, thr=1.2, size=0.55, vignette=0.25)
    return 0, None


BUILD = {"B1": build_B1, "B2": build_B2, "B3": build_B3, "B4": build_B4}


def make_mp4(shot, d):
    n = NFRAMES[shot]
    if not all(os.path.exists(os.path.join(d, f"{i:04d}.png")) for i in range(1, n + 1)): return
    mp4 = os.path.join(OUT, f"broll_{shot}_preview.mp4")
    if not os.path.exists(FFMPEG): print("[broll] ffmpeg tidak ditemukan"); return
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(d, "%04d.png"),
                    "-vf", "scale=960:-2", "-c:v", "libx264", "-crf", "24", "-preset", "slow", "-pix_fmt", "yuv420p", mp4])
    print("[broll] mp4:", mp4)


def run(shot, a):
    t0 = time.time()
    off, per_frame = BUILD[shot](a.preview)
    sc = bpy.context.scene; n0 = NFRAMES[shot]; mult = getattr(a, "mult", 1.0); n = round(n0 * mult)
    sc.frame_start, sc.frame_end = 1 + off, n0 + off
    lo, hi = (1, n)
    if a.frames:
        lo, hi = (int(v) for v in a.frames.split("-")) if "-" in a.frames else (int(a.frames),) * 2
    base = a.out or (OUT + ("/_pv" if a.preview else ""))
    d = os.path.join(base, f"broll_{shot}"); os.makedirs(d, exist_ok=True)
    print(f"[broll] {shot} siap dalam {time.time() - t0:.1f} s → {d}")
    for i in range(lo, min(hi, n) + 1, a.step):
        fp = os.path.join(d, f"{i:04d}.png")
        if os.path.exists(fp) and os.path.getsize(fp) > 0: continue
        f = off + 1 + (i - 1) / mult; fi = math.floor(f)   # mult>1: frame antara (sub-frame) → fps lebih tinggi, gerak sama
        t1 = time.time(); sc.frame_set(fi, subframe=f - fi)
        if per_frame: per_frame(f)
        tmp = fp + ".tmp.png"; sc.render.filepath = tmp
        bpy.ops.render.render(write_still=True); os.replace(tmp, fp)
        print(f"[broll] {shot} frame {i}/{n} {time.time() - t1:.1f} s", flush=True)
    print(f"[broll] {shot} selesai {time.time() - t0:.0f} s")
    if not a.preview and not a.out: make_mp4(shot, d)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default="all", choices=["B1", "B2", "B3", "B4", "all"])
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--frames", default=None)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--out", default=None)
    ap.add_argument("--mult", type=float, default=1.0, help="pengali fps lewat sub-frame (2.5: 24→60 fps)")
    a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    for s in (["B1", "B2", "B3", "B4"] if a.shot == "all" else [a.shot]):
        run(s, a)
