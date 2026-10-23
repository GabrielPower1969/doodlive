import bpy, math, sys
from mathutils import Vector
argv = sys.argv[sys.argv.index("--")+1:]; GLB, TEX, OUT = argv
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
img = bpy.data.images.load(TEX)
for m in bpy.data.materials:
    if not m.use_nodes: continue
    nt = m.node_tree; bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf: continue
    if m.name.lower().startswith(('halo','trumpet','gold','eye','cloud')) or 'halo' in m.name.lower(): continue
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img
    nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
sc.render.film_transparent = True; sc.render.resolution_x = 900; sc.render.resolution_y = 1100
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (1, 0.96, 0.88, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.2
for loc, e in (((2, -3, 4), 900), ((-3, -2, 2), 400), ((0, 3, 3), 600)):
    L = bpy.data.objects.new("L", bpy.data.lights.new("L", 'AREA')); L.data.energy = e; L.data.size = 3; L.location = loc
    L.rotation_euler = (Vector((0,0,0.6)) - Vector(loc)).to_track_quat('-Z','Y').to_euler(); sc.collection.objects.link(L)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
# glTF import is Y-up converted to Z-up by Blender
objs = [o for o in sc.objects if o.type == 'MESH']
mn = Vector((min(min((o.matrix_world @ Vector(c))[i] for c in o.bound_box) for o in objs) for i in range(3)))
mx = Vector((max(max((o.matrix_world @ Vector(c))[i] for c in o.bound_box) for o in objs) for i in range(3)))
target = (mn + mx) / 2; h = (mx - mn).length
a = math.radians(-20); r = h * 1.55
cam.location = target + Vector((math.sin(a) * r, -math.cos(a) * r, h * 0.12))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = OUT; bpy.ops.render.render(write_still=True)
print("bbox", mn, mx)
