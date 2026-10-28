"""Render model .glb Sketchfab untuk poster/brosur: Cycles GPU, latar transparan, cahaya hangat emas.
Pemakaian: blender -b --factory-startup -P blender/poster_glb.py -- <in.glb> <out.png> [px] [samples] [fit]
"""
import bpy, sys, math, os
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
src, out = os.path.abspath(args[0]), os.path.abspath(args[1])
px = int(args[2]) if len(args) > 2 else 1400
samples = int(args[3]) if len(args) > 3 else 96
fit = float(args[4]) if len(args) > 4 else 1.08
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
pts = [o.matrix_world @ Vector(c) for o in sc.objects if o.type == "MESH" for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
ctr, size = (lo + hi) / 2, max(hi - lo)

d = Vector((0.75, -1.0, 0.38)).normalized()
cd = bpy.data.cameras.new("c"); cd.type = "ORTHO"; cd.ortho_scale = size * fit; cd.clip_end = size * 10
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

sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try:
    prefs.compute_device_type = "OPTIX"; prefs.get_devices()
    for dv in prefs.devices: dv.use = dv.type == "OPTIX"
    sc.cycles.device = "GPU"
except Exception:
    pass
sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = px
sc.render.film_transparent = True
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print("[nara] rendered", out)
