"""Turntable model .glb Sketchfab untuk showreel: putar 360° dalam N frame (loop mulus), PNG RGBA, cahaya hangat emas
(pendekatan sama dengan poster_glb.py). Model diputar, kamera & cahaya tetap.
Pemakaian: blender -b --factory-startup -P blender/turntable_glb.py -- <in.glb> <out_dir> [px=720] [frames=96] [engine=EEVEE|CYCLES] [samples=32] [fit=1.05]
"""
import bpy, sys, math, os
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
src, out = os.path.abspath(args[0]), os.path.abspath(args[1])
px = int(args[2]) if len(args) > 2 else 720
N = int(args[3]) if len(args) > 3 else 96
engine = (args[4] if len(args) > 4 else "EEVEE").upper()
samples = int(args[5]) if len(args) > 5 else 32
fit = float(args[6]) if len(args) > 6 else 1.05
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
for o in [o for o in sc.objects if o.type in ("CAMERA", "LIGHT")]:
    bpy.data.objects.remove(o)
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in sc.objects if o.type == "MESH" for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
ctr = (lo + hi) / 2
r_xy = max(math.hypot(p.x - ctr.x, p.y - ctr.y) for p in pts)  # jari-jari sapuan saat berputar
h = hi.z - lo.z
size = max(2 * r_xy, h)

# Poros putar di tengah model; semua objek akar diparent ke poros
pivot = bpy.data.objects.new("turn", None); sc.collection.objects.link(pivot); pivot.location = (ctr.x, ctr.y, 0)
bpy.context.view_layer.update()  # matrix_world poros harus terbarui sebelum parenting
for o in [o for o in sc.objects if o.parent is None and o is not pivot]:
    mw = o.matrix_world.copy(); o.parent = pivot; o.matrix_world = mw
for f, ang in ((1, 0.0), (N + 1, math.tau)):
    pivot.rotation_euler = (0, 0, ang); pivot.keyframe_insert("rotation_euler", frame=f)
try:  # interpolasi linear agar kecepatan putar konstan
    from bpy_extras import anim_utils
    fcs = anim_utils.action_get_channelbag_for_slot(pivot.animation_data.action, pivot.animation_data.action_slot).fcurves
except Exception:
    fcs = pivot.animation_data.action.fcurves
for fc in fcs:
    for k in fc.keyframe_points: k.interpolation = "LINEAR"

d = Vector((0.75, -1.0, 0.38)).normalized()
el = math.asin(d.z)
cd = bpy.data.cameras.new("c"); cd.type = "ORTHO"
cd.ortho_scale = max(2 * r_xy, h * math.cos(el) + 2 * r_xy * math.sin(el)) * fit; cd.clip_end = size * 10
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
cam.location = ctr + d * size * 4
cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()

def area(name, vec, power, col):
    ld = bpy.data.lights.new(name, "AREA"); ld.size = size * 1.5; ld.energy = power * size * size; ld.color = col
    ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob)
    ob.location = ctr + Vector(vec).normalized() * size * 2.2
    ob.rotation_euler = (ctr - ob.location).to_track_quat("-Z", "Y").to_euler()
area("key", (1.2, -1.4, 1.3), 260, (1, .9, .74))
area("rim", (-1.2, 1.4, 1.0), 380, (1, .72, .36))
area("fill", (-1.6, -1.0, 0.3), 70, (1, .95, .88))

w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.16, 0.12, 0.07, 1); bg.inputs["Strength"].default_value = 0.6

if engine == "CYCLES":
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "OPTIX"; prefs.get_devices()
        for dv in prefs.devices: dv.use = dv.type == "OPTIX"
        sc.cycles.device = "GPU"
    except Exception:
        pass
    sc.cycles.samples = samples; sc.cycles.use_denoising = True
else:
    for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = e; break
        except TypeError:
            pass
    sc.eevee.taa_render_samples = samples
sc.render.resolution_x = sc.render.resolution_y = px
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.fps = 24; sc.frame_start, sc.frame_end = 1, N  # frame N+1 = frame 1 → loop mulus
sc.render.use_overwrite = False  # lanjutkan: frame yang sudah ada tidak dirender ulang
sc.render.filepath = os.path.join(out, "####")
bpy.ops.render.render(animation=True)
print("[nara] turntable", os.path.basename(src), N, "frame ->", out)
