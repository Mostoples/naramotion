"""NaraMotion — render showreel penari: aksi gambyong_loop frame 1–192 (frame 192 = frame 0, menyambung ke 1),
kamera "cam_orbit" terpisah mengayun ±25° mengitari penari. Blend utama tidak disimpan ulang.
Pemakaian:
  blender -b assets_src/penari_rig.blend -P blender/dancer_showreel.py -- <out_dir> [px=1080] [samples=32] [orbit_deg=25]
"""
import bpy, sys, os, math
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(args[0])
px = int(args[1]) if len(args) > 1 else 1080
samples = int(args[2]) if len(args) > 2 else 32
orbit = math.radians(float(args[3]) if len(args) > 3 else 25.0)
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
LOOP = 192

# Batas figur utuh (termasuk alas) di frame 0
sc.frame_set(0)
dg = bpy.context.evaluated_depsgraph_get()
pts = []
for o in sc.objects:
    if o.type in ("MESH", "CURVE") and not o.name.startswith("WGT-") and not o.hide_render and o.visible_get():
        ev = o.evaluated_get(dg)
        pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
ctr = (lo + hi) / 2
half = max(hi.z - lo.z, hi.x - lo.x, hi.y - lo.y) / 2 * 1.12  # ruang di atas kepala & tepi

old = sc.camera
cd = bpy.data.cameras.new("cam_orbit"); cd.lens = 85
cam = bpy.data.objects.new("cam_orbit", cd); sc.collection.objects.link(cam); sc.camera = cam
dist = half / math.tan(math.atan(cd.sensor_width / 2 / cd.lens)) + 0.4
base = (old.location - ctr) if old else Vector((1.25, -4.3, 0.35))
az0 = math.atan2(base.y, base.x)
elev = math.radians(6)
target = ctr + Vector((0, 0, 0.03))
for f in range(1, LOOP + 1):  # ayunan sinus: f=192 sama dengan f=0, menyambung ke f=1
    az = az0 + orbit * math.sin(math.tau * f / LOOP)
    cam.location = target + Vector((math.cos(az) * math.cos(elev), math.sin(az) * math.cos(elev), math.sin(elev))) * dist
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=f); cam.keyframe_insert("rotation_euler", frame=f)

sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "OPTIX"; prefs.get_devices()
    for d in prefs.devices: d.use = d.type == "OPTIX"
    sc.cycles.device = "GPU"
except Exception:
    pass
sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = px
sc.render.film_transparent = True
sc.render.use_persistent_data = True
sc.render.use_overwrite = False  # lanjutkan: frame yang sudah ada tidak dirender ulang
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.frame_start, sc.frame_end = 1, LOOP
sc.render.filepath = os.path.join(out, "####")
bpy.ops.render.render(animation=True)
print("[nara] showreel penari", out, LOOP, "frame")
