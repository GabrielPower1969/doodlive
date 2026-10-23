"""Blender (headless): a 3D extruded title — Chinese on top, English below — exported as GLB for the AR scene.
Units: metres-ish model units, overall width ≈ 1.0 (the app scales it). Node names: "title", "hanzi", "english".
Run: blender -b --python pipeline/make_title.py -- "天使" "Angel" assets/titles/angel.glb "tiān shǐ" [preview.png]
Nodes "english" and "pinyin" share the same slot; the app shows one of them (toggle button).
Fonts: pipeline/fonts/*.ttf (extracted from macOS collections; swap for Noto Sans SC before shipping).
"""
import bpy, sys, os, math
argv = sys.argv[sys.argv.index("--") + 1:]
HANZI, ENGLISH, OUT = argv[0], argv[1], argv[2]
PINYIN = argv[3] if len(argv) > 3 else ""
PREVIEW = argv[4] if len(argv) > 4 else None
HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def mat(name, rgb, metal, rough, emit=None, strength=0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Metallic"].default_value = metal; b.inputs["Roughness"].default_value = rough
    if emit: b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = (*rgb, 1); return m
GOLD = mat("title_gold", (0.95, 0.76, 0.30), 0.9, 0.28, (0.6, 0.42, 0.1), 0.35)
IVORY = mat("title_ivory", (0.97, 0.95, 0.90), 0.1, 0.5)

def text(name, body, font_path, size, depth, bevel, material, z):
    cu = bpy.data.curves.new(name, 'FONT'); cu.body = body; cu.size = size
    cu.font = bpy.data.fonts.load(font_path)
    cu.extrude = depth; cu.bevel_depth = bevel; cu.bevel_resolution = 3; cu.fill_mode = 'BOTH'
    cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o)
    o.rotation_euler = (math.radians(90), 0, 0)      # stand the text up: face -Y (towards the viewer in glTF)
    o.location = (0, 0, z); o.data.materials.append(material)
    bpy.context.view_layer.objects.active = o; o.select_set(True)
    bpy.ops.object.convert(target='MESH')
    for p in o.data.polygons: p.use_smooth = False
    return o

root = bpy.data.objects.new("title", None); sc.collection.objects.link(root)
h = text("hanzi", HANZI, f"{HERE}/fonts/hiragino-sans-gb-bold.ttf", 0.42, 0.045, 0.006, GOLD, 0.26)
e = text("english", ENGLISH, f"{HERE}/fonts/hiragino-sans-gb-bold.ttf", 0.16, 0.025, 0.003, IVORY, 0.0)
objs = [h, e]
if PINYIN:
    py = text("pinyin", PINYIN, f"{HERE}/fonts/hiragino-sans-gb-bold.ttf", 0.16, 0.025, 0.003, IVORY, 0.0); objs.append(py)
for o in objs: o.parent = root
# normalise width to ~1.0
bpy.context.view_layer.update()
w = max(o.dimensions.x for o in objs); s = 1.0 / w
for o in objs: o.location.x *= s; o.location.z *= s; o.scale = (s, s, s)
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for o in [root] + objs: o.select_set(True)
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
bpy.ops.export_scene.gltf(filepath=OUT, use_selection=True, export_apply=True, export_yup=True)
print("exported", OUT, "faces", sum(len(o.data.polygons) for o in objs))
if PREVIEW:
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 800, 500
    wd = bpy.data.worlds.new("W"); sc.world = wd; wd.use_nodes = True; wd.node_tree.nodes["Background"].inputs[0].default_value = (0.12, 0.14, 0.2, 1)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
    cam.location = (0.35, -1.6, 0.35); cam.rotation_euler = (math.radians(80), 0, math.radians(12))
    sc.render.filepath = PREVIEW; bpy.ops.render.render(write_still=True); print("preview", PREVIEW)
