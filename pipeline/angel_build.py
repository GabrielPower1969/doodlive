"""Blender (headless): the full angel — head (from angel_head.py), robe, sleeves, arms, feathered wings, halo,
trumpet, cloud — organised under Empties named exactly like the rig bones the app animates
(hips spine neck head shoulderL/R elbowL/R wristL/R wingL/R wingL/Rmid wingL/Rtip), each Empty at its joint with
identity rotation, so Unity's AngelPose and web/angel.js animate() drive them unchanged.
UV0 on every mesh = front projection (u = x + 0.5, v = z / aspect): the scanned page maps by drawing position.
Run: blender -b --python pipeline/angel_build.py -- out_dir   (writes angel.glb, angel.fbx, previews)
"""
import bpy, bmesh, math, sys, os, random
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "/tmp/angel"
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

HERE = os.path.dirname(os.path.abspath(__file__))
g = {"__name__": "angel_head", "__file__": os.path.join(HERE, "angel_head.py")}
exec(open(g["__file__"]).read(), g)
P, O, S, PX, AW, AH, sphere, mat, M = (g[k] for k in ("P", "O", "S", "PX", "AW", "AH", "sphere", "mat", "M"))
HEAD = g["HEAD_PARTS"]
sc = bpy.context.scene
ASPECT = AH / AW

M.update(robe=mat("robe", (0.96, 0.96, 0.98), 0.8), sash=mat("sash", (0.80, 0.68, 0.40), 0.6),
         wing=mat("wing", (0.98, 0.97, 0.94), 0.7), gold=mat("gold", (0.86, 0.66, 0.26), 0.3),
         cloud=mat("cloud", (1, 1, 1), 1.0), halo=mat("halo", (1.0, 0.92, 0.6), 0.4, (1.0, 0.85, 0.45)))
M["halo"].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.0

# ---------------- helpers ----------------
def smooth(o):
    for p in o.data.polygons: p.use_smooth = True
    return o
def mesh_obj(name, verts, faces, material):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); o.data.materials.append(material); return smooth(o)
def loft(name, rings, material, seg=48, cap_top=False):
    """rings: list of dict(y=px row, cx=px offset, rx=px, depth=px, folds=amp). Elliptic tube, Z-up."""
    verts, faces = [], []
    for r in rings:
        for s in range(seg):
            a = 2 * math.pi * s / seg
            fold = 1 + r.get("folds", 0) * math.sin(a * 11) * max(0.0, math.cos(a - math.pi / 2) * 0.5 + 0.5)
            verts.append(P(AW / 2 + r["cx"] + math.cos(a) * r["rx"] * fold, r["y"], (r.get("cz", 0) + math.sin(a) * r["depth"] * fold) / AW * -1 * -1))
    # P() takes fwd in model units; recompute properly (above used px/AW so fix sign): rebuild with explicit vectors
    verts = []
    for r in rings:
        for s in range(seg):
            a = 2 * math.pi * s / seg
            fold = 1 + r.get("folds", 0) * math.sin(a * 11) * max(0.0, math.cos(a - math.pi / 2) * 0.5 + 0.5)
            verts.append(P(AW / 2 + r["cx"] + math.cos(a) * r["rx"] * fold, r["y"], PX(r.get("cz", 0) + math.sin(a) * r["depth"] * fold)))
    for i in range(len(rings) - 1):
        for s in range(seg):
            a = i * seg + s; b = i * seg + (s + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    if cap_top: faces.append(tuple(range((len(rings) - 1) * seg, len(rings) * seg)))
    return mesh_obj(name, verts, faces, material)
def limb(name, a, b, r0, r1, material, seg=20):
    d = b - a; L = d.length
    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=1, vertices=seg, location=(0, 0, 0))
    o = bpy.context.object; o.name = name
    bm = bmesh.new(); bm.from_mesh(o.data)
    for v in bm.verts: v.co = Vector((v.co.x * (r0 if v.co.z < 0 else r1), v.co.y * (r0 if v.co.z < 0 else r1), (v.co.z + 0.5) * L))
    bm.to_mesh(o.data); bm.free()
    o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.normalized().to_track_quat('Z', 'Y'); o.location = a
    o.data.materials.append(material); return smooth(o)
def front_uv(o):
    """UV0 = page position. Done in world space on the evaluated mesh; must run in rest pose."""
    if o.type != 'MESH': return
    me = o.data
    if not me.uv_layers: me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0]; mw = o.matrix_world
    for poly in me.polygons:
        for li in poly.loop_indices:
            w = mw @ me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (w.x + 0.5, w.z / ASPECT)
def empty(name, at, parent=None):
    """Pivot node at world point `at`. Parent WITHOUT matrix_parent_inverse and set the true local offset, so the
    glTF/FBX exporters write correct local translations (with the inverse trick they wrote world offsets, LESSONS L26)."""
    e = bpy.data.objects.new(name, None); e.empty_display_size = 0.02
    sc.collection.objects.link(e)
    if parent:
        bpy.context.view_layer.update()
        e.parent = parent; e.matrix_parent_inverse = Matrix.Identity(4)
        e.location = at - parent.matrix_world.translation
    else:
        e.location = at
    bpy.context.view_layer.update()
    return e
def attach(o, parent):
    """Parent a mesh to a pivot keeping its world transform, with an identity parent-inverse (see empty())."""
    bpy.context.view_layer.update()
    mw = o.matrix_world.copy()
    o.parent = parent; o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_world = mw

# ---------------- rig points (line-art px; same as web/angel.js) ----------------
B = {}
B["hips"] = empty("hips", P(565, 930))
B["spine"] = empty("spine", P(560, 640), B["hips"])
B["neck"] = empty("neck", P(535, 500), B["spine"])
B["head"] = empty("head", P(527, 420), B["neck"])
B["shoulderL"] = empty("shoulderL", P(350, 610), B["spine"]); B["elbowL"] = empty("elbowL", P(285, 830), B["shoulderL"]); B["wristL"] = empty("wristL", P(175, 975), B["elbowL"])
B["shoulderR"] = empty("shoulderR", P(760, 620), B["spine"]); B["elbowR"] = empty("elbowR", P(840, 840), B["shoulderR"]); B["wristR"] = empty("wristR", P(955, 1010), B["elbowR"])
for side, (x0, x1, x2) in (("L", (420, 210, 20)), ("R", (708, 918, 1108))):
    B["wing" + side] = empty("wing" + side, P(x0, 560, -0.06), B["spine"])
    B["wing" + side + "mid"] = empty("wing" + side + "mid", P(x1, 330, -0.06), B["wing" + side])
    B["wing" + side + "tip"] = empty("wing" + side + "tip", P(x2, 30, -0.06), B["wing" + side + "mid"])
bpy.context.view_layer.update()

parts = []
# ---------------- head ----------------
for o in HEAD["head"], *HEAD["extras"], *HEAD["hair"]:
    attach(o, B["head"]); parts.append(o)

# ---------------- robe (skirt on hips, bodice on spine) ----------------
D = 0.55
skirt = loft("skirt", [
    dict(y=1384 + 28, cx=-14, rx=285, depth=285 * D, folds=0.05), dict(y=1250, cx=-9, rx=255, depth=255 * D, folds=0.045),
    dict(y=1100, cx=-4, rx=220, depth=220 * D, folds=0.03), dict(y=950, cx=1, rx=185, depth=185 * D, folds=0.01),
    dict(y=930, cx=1, rx=178, depth=178 * D)], M["robe"])
sub = skirt.modifiers.new("sub", 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
attach(skirt, B["hips"]); parts.append(skirt)
belt = loft("belt", [dict(y=948, cx=1, rx=192, depth=192 * D), dict(y=912, cx=1, rx=192, depth=192 * D)], M["sash"], 40)
attach(belt, B["hips"]); parts.append(belt)
bodice = loft("bodice", [
    dict(y=935, cx=1, rx=178, depth=178 * D), dict(y=800, cx=-1, rx=200, depth=200 * D * 0.95), dict(y=640, cx=-4, rx=205, depth=205 * D * 0.85),
    dict(y=545, cx=-9, rx=175, depth=175 * D * 0.75), dict(y=505, cx=-19, rx=90, depth=72), dict(y=500, cx=-19, rx=1, depth=1)], M["robe"])
sub = bodice.modifiers.new("sub", 'SUBSURF'); sub.levels = 1
attach(bodice, B["spine"]); parts.append(bodice)
# sash: twisted rope across the hips (torus segment approximated by a bent cylinder of beads)
for i in range(14):
    t = i / 13; x = 390 + t * 350; y = 1230 - t * 290 + 40 * math.sin(t * math.pi)
    o = sphere("sash_bead", P(x, y, PX(150 - abs(t - 0.5) * 60)), PX(17), S(1.6, 1, 1), 12, 8); o.rotation_euler.z = math.radians(-35)
    o.data.materials.append(M["sash"]); attach(o, B["hips"]); parts.append(o)

# ---------------- arms ----------------
for side, (sh, el, wr, hand) in (("L", (P(350, 600), P(285, 840), P(180, 975), P(140, 1010, PX(10)))), ("R", (P(760, 610), P(840, 850), P(972, 1018), P(984, 1034, PX(10))))):
    sl = limb("sleeve" + side, sh, el, PX(62), PX(80), M["robe"]); attach(sl, B["shoulder" + side]); parts.append(sl)
    cuff = sphere("cuff" + side, el, PX(80), S(1, 0.35, 0.8), 24, 8); cuff.data.materials.append(M["robe"]); attach(cuff, B["shoulder" + side]); parts.append(cuff)
    fa = limb("forearm" + side, el, wr, PX(30), PX(24), M["skin"]); attach(fa, B["elbow" + side]); parts.append(fa)
    hd = sphere("hand" + side, hand, PX(30), S(1.7, 1.1, 0.55) if side == "L" else S(1.0, 1.4, 0.9), 20, 12); hd.data.materials.append(M["skin"]); attach(hd, B["wrist" + side]); parts.append(hd)
    th = sphere("thumb" + side, hand + O(PX(-22 if side == "L" else 18), PX(16), PX(8)), PX(9), S(1, 1.8, 0.8), 10, 6); th.data.materials.append(M["skin"]); attach(th, B["wrist" + side]); parts.append(th)
# trumpet in the right hand
tr = limb("trumpet_pipe", P(940, 1300), P(1072, 540), PX(9), PX(5), M["gold"], 16); attach(tr, B["wristR"]); parts.append(tr)
bell = limb("trumpet_bell", P(945, 1270), P(905, 1358), PX(12), PX(62), M["gold"], 32); attach(bell, B["wristR"]); parts.append(bell)
rim = sphere("trumpet_rim", P(905, 1358), PX(62), S(1, 0.12, 1), 32, 6); rim.data.materials.append(M["gold"]); rim.rotation_euler.x = math.radians(-25); attach(rim, B["wristR"]); parts.append(rim)

# ---------------- wings: layered feathers along the drawn outline ----------------
outline = [(20, 30), (130, 95), (240, 200), (330, 330), (390, 450), (430, 560), (410, 650), (340, 740), (250, 800),
           (170, 770), (90, 710), (15, 650), (0, 430), (30, 330), (80, 250), (40, 120)]
def inside(poly, x, y):
    c = False
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[i - 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: c = not c
    return c
random.seed(5)
for side in ("L", "R"):
    mirror = (lambda x: x) if side == "L" else (lambda x: AW - x)
    root = (430, 560); chain = [B["wing" + side], B["wing" + side + "mid"], B["wing" + side + "tip"]]
    r0 = chain[0].matrix_world.translation; r2 = chain[2].matrix_world.translation; axis = r2 - r0
    # membrane slab behind the feathers (closes gaps) — a slightly shrunk extruded outline
    verts = [P(mirror(x), y, -PX(72)) for x, y in outline]; cx = sum(v.x for v in verts) / len(verts); cz = sum(v.z for v in verts) / len(verts)
    verts = [Vector((cx + (v.x - cx) * 0.93, v.y, cz + (v.z - cz) * 0.93)) for v in verts]
    verts2 = [v + Vector((0, PX(10), 0)) for v in verts]
    n = len(verts); faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    slab = mesh_obj("wing_slab" + side, verts + verts2, faces, M["wing"])
    attach(slab, chain[0]); parts.append(slab)   # (rigid on the root segment; feathers carry the motion)
    # feathers: 3 layers, radiating from the root, lengths grow towards the tip
    for layer, (step, lenf, wid, dz) in enumerate(((44, 0.42, 0.22, -60), (36, 0.34, 0.20, -50), (30, 0.26, 0.18, -40))):
        for y in range(0, 820, step):
            for x in range(0, 450, step):
                bx = x + random.uniform(-0.4, 0.4) * step; by = y + random.uniform(-0.4, 0.4) * step
                if not inside(outline, bx, by): continue
                dx, dy = bx - root[0], by - root[1]; d = math.hypot(dx, dy) or 1
                L = min(230, 50 + lenf * d)
                while L > 30 and not inside(outline, bx + dx / d * L * 0.8, by + dy / d * L * 0.8): L *= 0.85
                c = P(mirror(bx + dx / d * L / 2), by + dy / d * L / 2, PX(dz + layer * 2 + random.uniform(-2, 2)))
                f = sphere("feather", c, PX(L / 2), S(wid, 1, 0.12), 10, 8)
                ang = math.atan2(dy, dx) * (1 if side == "L" else -1)
                f.rotation_euler = (0, 0, -(ang + math.pi / 2) if side == "L" else -(ang + math.pi / 2))
                # Blender Z-up: rotate about the viewing axis (Y) so the feather's long axis points away from the root
                f.rotation_euler = (0, (ang - math.pi / 2) * (1 if side == "L" else 1), 0)
                f.data.materials.append(M["wing"])
                s = max(0.0, min(1.0, (c - r0).dot(axis) / axis.length_squared))
                attach(f, chain[0] if s < 0.33 else chain[1] if s < 0.66 else chain[2]); parts.append(f)

# ---------------- halo + cloud ----------------
bpy.ops.mesh.primitive_torus_add(major_radius=0.115, minor_radius=0.009, location=P(527, 175, -PX(45)), rotation=(math.radians(-25), 0, 0), major_segments=64, minor_segments=12)
halo = bpy.context.object; halo.name = "halo"; halo.data.materials.append(M["halo"]); smooth(halo); attach(halo, B["head"]); parts.append(halo)
random.seed(7)
cloud_root = empty("cloud", Vector((0, 0, 0)))          # Spin component target in Unity
for i in range(22):
    a = random.uniform(0, 2 * math.pi); r = 0.1 + random.uniform(0, 0.32); s = 0.05 + random.uniform(0, 0.06)
    o = sphere("cloud", Vector((math.cos(a) * r * 1.2, -math.sin(a) * r * 0.6, -0.03 + random.uniform(0, 0.04))), s, (1, 1, 1), 16, 12)
    o.data.materials.append(M["cloud"]); attach(o, cloud_root); parts.append(o)
B["cloud"] = cloud_root

# ---------------- UVs, export ----------------
bpy.context.view_layer.update()
for o in parts:
    if o.type == 'MESH': front_uv(o)
bpy.ops.object.select_all(action='DESELECT')
for o in parts + list(B.values()): o.select_set(True)
bpy.ops.export_scene.gltf(filepath=f"{OUT}/angel.glb", use_selection=True, export_apply=True, export_yup=True)
bpy.ops.export_scene.fbx(filepath=f"{OUT}/angel.fbx", use_selection=True, apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL',
                         axis_forward='-Z', axis_up='Y', bake_space_transform=True, use_mesh_modifiers=True, path_mode='COPY', embed_textures=False)
tris = sum(len(o.data.polygons) for o in parts if o.type == 'MESH')
print("exported", OUT, "faces:", tris)

# ---------------- previews ----------------
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.show_shadows = True
sc.render.resolution_x = 700; sc.render.resolution_y = 900
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.80, 0.9, 1)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 45
target = Vector((0, 0, 0.62))
for deg in (0, 45, 90, 180):
    a = math.radians(deg); r = 2.6
    cam.location = target + Vector((math.sin(a) * r, -math.cos(a) * r, 0.25))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{OUT}/angel_{deg}.png"; bpy.ops.render.render(write_still=True)
print("previews done")
