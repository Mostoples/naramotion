"""Render cek cepat .glb beranimasi (tampak depan, Workbench): blender -b -P blender/render_rig_check.py -- in.glb out_prefix n"""
import bpy, sys, math
glb, pre, n = sys.argv[sys.argv.index("--") + 1:][:3]; n = int(n)
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene; arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
act = arm.animation_data.action; f0, f1 = map(int, act.frame_range)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -4.2, 1.0); cam.rotation_euler = (math.radians(90), 0, 0); cam.data.lens = 40
sc.render.engine = "BLENDER_WORKBENCH"; sc.render.resolution_x, sc.render.resolution_y = 360, 480
sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "TEXTURE"
for k in range(n):
    f = f0 + round((f1 - f0) * (k + 0.5) / n); sc.frame_set(f); sc.render.filepath = f"{pre}_{k}.png"; bpy.ops.render.render(write_still=True)
