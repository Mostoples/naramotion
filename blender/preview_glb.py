"""Pratinjau cepat model .glb Sketchfab (satu PNG per model) untuk memilih aset."""
import bpy, sys, os, math
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
src, out = args[0], args[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
pts = [o.matrix_world @ Vector(c) for o in sc.objects if o.type == "MESH" for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
ctr, size = (lo + hi) / 2, max(hi - lo)
cd = bpy.data.cameras.new("c"); cd.type = "ORTHO"; cd.ortho_scale = size * 1.15
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam); sc.camera = cam
d = Vector((0.7, -1.0, 0.45)).normalized(); cam.location = ctr + d * size * 4
cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); cd.clip_end = size * 10
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.2
ld = bpy.data.lights.new("s", "SUN"); ld.energy = 3; so = bpy.data.objects.new("s", ld); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(50), 0, math.radians(30))
sc.render.engine = "BLENDER_EEVEE"; sc.render.resolution_x = sc.render.resolution_y = 420
sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
