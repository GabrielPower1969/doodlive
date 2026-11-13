"""AR mock renderer for the Design role (CONTRACT §12), run by make_design.py:

    blender -b --factory-startup --python ar_mock_blender.py -- <work>/ar_mock_scene.json

Builds the page as one heightfield mesh from <work>/ar_mock_grid.npz (front pieces wear the scanned page by FRONT
projection, the ground wears the baked sand ground by top-down projection), adds the banner cloths and poles, imports
the character GLBs (rest pose) on their stage marks, and renders the views listed in the scene file.
Blender coordinates: X = page x, Y = d = -z (away from the viewer), Z = height.
"""
import json, math, os, sys
import bpy
import numpy as np
from mathutils import Vector

S = json.load(open(sys.argv[sys.argv.index("--") + 1]))
W, Hp = S["page"]; ART = S["art"]; PX = S["px"]; AB = S["artBottomPx"]


def page_uv(xs, ys):
    """sheet (x, ys) -> page image UV (origin bottom-left)"""
    X = ART[0] + (xs + 0.5) * PX; Y = AB - ys * PX
    return np.stack([X / W, 1 - Y / Hp], -1)


def mat_img(name, path, mapping=None, rough=0.9):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = rough
    try: b.inputs["Specular IOR Level"].default_value = 0.2
    except KeyError: pass
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(path); tex.extension = 'EXTEND'
    if mapping:
        uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (mapping[0], mapping[1], 0); mp.inputs["Scale"].default_value = (mapping[2], mapping[3], 1)
        nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], tex.inputs[0])
    nt.links.new(tex.outputs[0], b.inputs["Base Color"])
    return m


def mat_rgb(name, rgb, rough=0.8):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = rough
    return m


def link(ob):
    bpy.context.scene.collection.objects.link(ob); return ob


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
work = S["work"]
G = np.load(os.path.join(work, "ar_mock_grid.npz"))
Xs, Ds, H, OWN, MAPS = G["X"], G["D"], G["H"], G["OWN"].astype(np.int32), G["MAPS"]
nd, nx = H.shape
xx, dd = np.meshgrid(Xs, Ds)
verts = np.stack([xx.ravel(), dd.ravel(), H.ravel()], -1)
ii, jj = np.meshgrid(np.arange(nd - 1), np.arange(nx - 1), indexing="ij")
v00 = (ii * nx + jj).ravel(); v10 = v00 + 1; v11 = v00 + nx + 1; v01 = v00 + nx
faces = np.stack([v00, v10, v11, v01], -1)
Hf = H.ravel(); Of = OWN.ravel()
ch = Hf[faces]; top = faces[np.arange(len(faces)), ch.argmax(1)]
fown = Of[top]
me = bpy.data.meshes.new("page"); me.from_pydata(verts.tolist(), [], faces.tolist())
uv = me.uv_layers.new(name="UVMap")
corner = faces.ravel(); own_c = np.repeat(fown, 4)
cx, cd, cy = verts[corner, 0], verts[corner, 1], verts[corner, 2]
m = MAPS[np.clip(own_c, 0, None)]
fx = cx / m[:, 0] + m[:, 1]; fy = cy / m[:, 0] + m[:, 2]
uvs = np.where((own_c >= 0)[:, None], page_uv(fx, fy), page_uv(cx, cd))
uv.data.foreach_set("uv", uvs.astype(np.float32).ravel())
me.materials.append(mat_img("ground", os.path.join(work, "ar_ground.png")))
me.materials.append(mat_img("front", os.path.join(work, "ar_front.png")))
me.polygons.foreach_set("material_index", (fown >= 0).astype(np.int32))
me.update()
page = link(bpy.data.objects.new("page", me))

# banners: cloth (front UV) + pole
m_front = bpy.data.materials["front"]; m_pole = mat_rgb("pole", (0.42, 0.27, 0.14))
for b in S["banners"]:
    px, base, z, ph = b["pole"]; d = -z
    pts = b["cloth"][:-1]
    bm = bpy.data.meshes.new("cloth"); bm.from_pydata([(x, d, y) for x, y in pts], [], [list(range(len(pts)))])
    lay = bm.uv_layers.new(name="UVMap"); mp = b["map"]
    arr = np.array(pts); u = page_uv(arr[:, 0] / mp["scale"] + mp["sheetX"], arr[:, 1] / mp["scale"] + mp["sheetY"])
    lay.data.foreach_set("uv", u.astype(np.float32).ravel()); bm.materials.append(m_front)
    link(bpy.data.objects.new("cloth", bm))
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.003, depth=ph + 0.006, location=(px, d, base + (ph + 0.006) / 2))
    bpy.context.object.data.materials.append(m_pole)

# table
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0.6, -0.003))
bpy.context.object.data.materials.append(mat_rgb("table", (0.36, 0.25, 0.17)))

# characters (rest pose) on their marks
mapping = (ART[0] / W, (Hp - ART[1] - ART[3]) / Hp, ART[2] / W, ART[3] / Hp)
m_chr = mat_img("chars", os.path.join(work, "ar_chars.png"), mapping, rough=0.7)
for c, (sx, sz, yaw) in S["stage"].items():
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=S["models"][c])
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.type == 'MESH':
            for s in o.material_slots: s.material = m_chr
    for o in [o for o in new if o.parent is None]:
        o.rotation_mode = 'XYZ'; o.rotation_euler.z += math.radians(yaw)
        o.location.x += sx; o.location.y += -sz

# light + world
sun = link(bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')))
sun.data.energy = 3.2; sun.data.angle = math.radians(3)
sun.rotation_euler = (math.radians(42), math.radians(-22), math.radians(-30))
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True
bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.82, 0.86, 0.93, 1); bg.inputs[1].default_value = 0.85
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try: sc.render.engine = eng; break
    except TypeError: pass
sc.view_settings.view_transform = 'Standard'
try: sc.eevee.taa_render_samples = 24
except AttributeError: pass
cam = link(bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))); sc.camera = cam
cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.01; cam.data.clip_end = 30
for sh in S["shots"]:
    ex, ey, ez = sh["eye"]; tx, ty, tz = sh["target"]          # design coords (x, y up, z toward viewer)
    eye = Vector((ex, -ez, ey)); tgt = Vector((tx, -tz, ty))
    cam.location = eye; cam.rotation_euler = (tgt - eye).to_track_quat('-Z', 'Y').to_euler()
    cam.data.angle_y = math.radians(sh["vfov"])
    sc.render.resolution_x, sc.render.resolution_y = sh["res"]
    sc.render.filepath = os.path.join(S["out"], sh["name"]); bpy.ops.render.render(write_still=True)
print("AR_MOCK_OK")
