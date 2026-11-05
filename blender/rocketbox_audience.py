"""Penonton Arena dari avatar Microsoft Rocketbox (MIT) → assets/arena/penonton/<avatar>.glb (mesh + 3 animasi: sit, idle, clap).
Animasi Rocketbox (rig Bip01 yang sama) ditempel lewat Copy Rotation per tulang (ruang dunia) lalu di-bake; tekstur 4K TGA
diperkecil ke 1024 px. Anak-anak hanya berdiri (idle, clap): pinggul tidak diikutkan agar tinggi badan tetap.
Pemakaian: blender -b --factory-startup -P blender/rocketbox_audience.py   (setelah python tools/fetch_rocketbox.py)
"""
import bpy, glob, os
R = "C:/Users/mosto/Desktop/nanramotion/assets_src/rocketbox/"; OUT = "C:/Users/mosto/Desktop/nanramotion/assets/arena/penonton/"
os.makedirs(OUT, exist_ok=True)
TEX = 1024; CLIP = {"sit": ("sit_chair_idle_neutral_01", 360), "idle": ("idle_neutral_01", 360), "clap": ("claphands_01", 240)}   # frame (30 fps)

def material(mat, tex):
    """bangun ulang material: warna (+alpha untuk rambut/bulu mata), normal map"""
    kind = mat.name.split("_")[-1]   # body | head | opacity
    col = next((t for t in tex if t.endswith(f"{kind}_color.tga")), None); nor = next((t for t in tex if t.endswith(f"{kind}_normal.tga")), None)
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bs = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(bs.outputs[0], out.inputs[0])
    bs.inputs["Roughness"].default_value = 0.7
    if col:
        im = bpy.data.images.load(col); im.scale(TEX, TEX) if im.size[0] > TEX else None
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = im; nt.links.new(t.outputs["Color"], bs.inputs["Base Color"])
        if kind == "opacity": nt.links.new(t.outputs["Alpha"], bs.inputs["Alpha"]); mat.blend_method = "CLIP" if hasattr(mat, "blend_method") else None
    if nor:
        im = bpy.data.images.load(nor); im.colorspace_settings.name = "Non-Color"; im.scale(TEX, TEX) if im.size[0] > TEX else None
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = im; nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(t.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])

def build(name):
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene; sc.render.fps = 30
    bpy.ops.import_scene.fbx(filepath=f"{R}{name}/{name}.fbx")
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE"); arm.name = "Penonton"
    for o in list(bpy.data.objects):
        if o.type == "EMPTY": bpy.data.objects.remove(o)
    tex = glob.glob(f"{R}{name}/Textures/*.tga")
    for m in bpy.data.materials:
        if m.use_nodes: material(m, tex)
    child = "Child" in name; g = "f" if name.startswith("Female") else "m"
    for clip, (stem, n) in CLIP.items():
        if child and clip == "sit": continue
        bpy.ops.import_scene.fbx(filepath=f"{R}anim/{g}_{stem}.fbx")
        src = next(o for o in bpy.data.objects if o.type == "ARMATURE" and o is not arm)
        for pb in arm.pose.bones:
            sn = "Bip01" + pb.name[5:]   # rig anak memakai awalan Bip02
            if sn not in src.pose.bones: continue
            c = pb.constraints.new("COPY_ROTATION"); c.target = src; c.subtarget = sn
            if sn == "Bip01 Pelvis" and not child:
                c = pb.constraints.new("COPY_LOCATION"); c.target = src; c.subtarget = sn
        bpy.ops.object.select_all(action="DESELECT"); arm.select_set(True); bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="POSE"); bpy.ops.pose.select_all(action="SELECT")
        arm.animation_data_create(); arm.animation_data.action = None
        bpy.ops.nla.bake(frame_start=1, frame_end=n, step=2, only_selected=True, visual_keying=True, clear_constraints=True, use_current_action=False, bake_types={"POSE"})
        bpy.ops.object.mode_set(mode="OBJECT")
        act = arm.animation_data.action; act.name = clip; act.use_fake_user = True
        tr = arm.animation_data.nla_tracks.new(); tr.name = clip; tr.strips.new(clip, 1, act); arm.animation_data.action = None
        for o in [src] + [c for c in src.children_recursive]: bpy.data.objects.remove(o)
        for a in list(bpy.data.actions):
            if a.users == 0 and not a.use_fake_user: bpy.data.actions.remove(a)
    bpy.ops.export_scene.gltf(filepath=f"{OUT}{name}.glb", export_format="GLB", export_animation_mode="NLA_TRACKS", export_image_format="WEBP",
                              export_apply=False, export_yup=True)
    print("ok", name, [t.name for t in arm.animation_data.nla_tracks], os.path.getsize(f"{OUT}{name}.glb") // 1024, "KB")

for d in sorted(glob.glob(R + "*_*_*/")):
    n = os.path.basename(d.rstrip("/\\"))
    if n != "anim" and (not os.environ.get("ONLY") or n in os.environ["ONLY"].split(",")): build(n)
