"""Blender (headless): a believable stylised head for the angel. Primitives for brow, cheeks, nose, chin, lips are
fused with a voxel remesh into one smooth face; eyes, lids, lashes, brows, lips and hair stay separate (animatable).
Coordinates: Blender native Z-up. 1.0 = art width (same as web/angel.js). x right, z up, -y towards the viewer.
Run: blender -b --python pipeline/angel_head.py -- out.glb [preview_dir]
"""
import bpy, bmesh, math, sys, os, random
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_GLB = argv[0] if argv else "/tmp/angel_head.glb"
PREVIEW = argv[1] if len(argv) > 1 else None

if __name__ == "__main__": bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
AW, AH = 1128.0, 1384.0
PX = lambda px: px / AW
def P(x, y, fwd=0.0):                      # line-art pixel (y down) + depth towards viewer -> Blender
    return Vector(((x - AW / 2) / AW, -fwd, (AH - y) / AW))
def O(x, up, fwd): return Vector((x, -fwd, up))   # offset: right, up, towards viewer
def S(x, up, fwd): return (x, fwd, up)            # scale given as (right, up, depth)

def sphere(name, loc, r, scale=(1, 1, 1), seg=32, ring=16):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=ring)
    o = bpy.context.object; o.name = name; o.scale = scale
    for p in o.data.polygons: p.use_smooth = True
    return o
def mat(name, rgb, rough=0.6, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*rgb, 1)
    if emit: b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = 0.4
    return m
M = dict(skin=mat("skin", (0.93, 0.76, 0.64), 0.55), white=mat("eyewhite", (0.97, 0.96, 0.93), 0.25),
         iris=mat("iris", (0.30, 0.52, 0.72), 0.3, (0.05, 0.12, 0.2)), pupil=mat("pupil", (0.03, 0.03, 0.04), 0.2),
         lash=mat("lash", (0.17, 0.10, 0.07), 0.6), brow=mat("brow", (0.48, 0.30, 0.16), 0.9),
         lip=mat("lip", (0.85, 0.48, 0.47), 0.45), hair=mat("hair", (0.55, 0.35, 0.18), 0.85))

# ---- face masses (measured on lineart.png: head centre ~(525,358), eyes (472,333)/(547,313)) ----
HC = P(525, 358)
parts = [
    sphere("skull", HC + O(0, PX(10), -PX(6)), PX(80), S(0.96, 1.08, 0.98)),
    sphere("jaw", HC + O(0, -PX(44), PX(8)), PX(56), S(0.88, 0.78, 0.82)),
    sphere("chin", HC + O(-PX(3), -PX(84), PX(26)), PX(17), S(1.1, 0.8, 0.9)),
    sphere("forehead", HC + O(0, PX(50), PX(44)), PX(44), S(1.25, 0.9, 0.7)),
    sphere("nose_bridge", HC + O(-PX(4), PX(2), PX(74)), PX(8), S(0.8, 1.6, 0.8)),
    sphere("nose_tip", HC + O(-PX(5), -PX(16), PX(80)), PX(9.5), S(1.1, 0.85, 0.9)),
    sphere("upper_lip", HC + O(-PX(2), -PX(42), PX(68)), PX(13), S(1.5, 0.42, 0.65)),
    sphere("lower_lip", HC + O(-PX(2), -PX(52), PX(68)), PX(11), S(1.25, 0.48, 0.65)),
    sphere("neck", HC + O(PX(6), -PX(124), -PX(16)), PX(27), S(0.95, 1.2, 0.85)),
]
for sx in (-1, 1):
    parts += [sphere("cheek", HC + O(sx * PX(38), -PX(14), PX(40)), PX(25), S(1, 1.0, 0.7)),
              sphere("brow_ridge", HC + O(sx * PX(32), PX(34), PX(56)), PX(20), S(1.3, 0.45, 0.6)),
              sphere("socket_fill", HC + O(sx * PX(36), PX(14), PX(50)), PX(16), S(1, 0.8, 0.5)),
              sphere("nostril", HC + O(-PX(5) + sx * PX(8), -PX(19), PX(75)), PX(5)),
              sphere("ear", HC + O(sx * PX(78), -PX(6), -PX(8)), PX(16), S(0.5, 1.2, 0.9))]
for p in parts: p.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.join(); head = bpy.context.object; head.name = "Head"
# fuse the overlapping spheres into ONE manifold surface first (a boolean on a self-intersecting join is unreliable)
rm = head.modifiers.new("remesh", 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = PX(2.2); rm.use_smooth_shade = True
bpy.context.view_layer.objects.active = head; bpy.ops.object.modifier_apply(modifier="remesh")
for sx in (-1, 1):                              # eye sockets, carved from the fused head
    cut = sphere("cut", HC + O(sx * PX(37), PX(14), PX(72)), PX(15), S(1.15, 0.85, 1))
    m = head.modifiers.new("cut", 'BOOLEAN'); m.operation = 'DIFFERENCE'; m.object = cut; m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = head; bpy.ops.object.modifier_apply(modifier="cut"); bpy.data.objects.remove(cut)
sm = head.modifiers.new("smooth", 'CORRECTIVE_SMOOTH'); sm.iterations = 12; sm.factor = 0.6; sm.use_only_smooth = True
bpy.ops.object.modifier_apply(modifier="smooth")
dec = head.modifiers.new("dec", 'DECIMATE'); dec.ratio = 0.35; bpy.ops.object.modifier_apply(modifier="dec")
for p in head.data.polygons: p.use_smooth = True
head.data.materials.clear(); head.data.materials.append(M["skin"])

# ---- eyes, lids, lashes, brows, lips ----
ER = PX(13); extras = []
for sx, (ex, ey) in zip((-1, 1), ((472, 333), (547, 313))):
    side = 'L' if sx < 0 else 'R'
    c = P(ex, ey, PX(70))
    eye = sphere(f"Eye{side}", c, ER); eye.data.materials.append(M["white"]); extras.append(eye)
    o = sphere("iris", c + O(0, 0, ER * 0.76), ER * 0.64, S(1, 1, 0.35)); o.data.materials.append(M["iris"]); extras.append(o)
    o = sphere("pupil", c + O(0, 0, ER * 0.93), ER * 0.3, S(1, 1, 0.3)); o.data.materials.append(M["pupil"]); extras.append(o)
    o = sphere("hl", c + O(ER * 0.25, ER * 0.25, ER * 0.98), ER * 0.1); o.data.materials.append(M["white"]); extras.append(o)
    lid = sphere(f"Lid{side}", c, ER * 1.12)                      # upper half-shell, hinge = eye centre
    bm = bmesh.new(); bm.from_mesh(lid.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < ER * 0.3 or v.co.y > 0], context='VERTS'); bm.to_mesh(lid.data); bm.free()
    sol = lid.modifiers.new("sol", 'SOLIDIFY'); sol.thickness = PX(2.5); lid.data.materials.append(M["skin"]); lid.rotation_euler.x = math.radians(6); extras.append(lid)
    bpy.ops.mesh.primitive_torus_add(major_radius=ER * 1.14, minor_radius=PX(1.6), location=c + O(0, ER * 0.1, 0), rotation=(math.radians(100), 0, 0), major_segments=32, minor_segments=6)
    lash = bpy.context.object; lash.name = "lash"; bm = bmesh.new(); bm.from_mesh(lash.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < ER * 0.35], context='VERTS'); bm.to_mesh(lash.data); bm.free()
    lash.data.materials.append(M["lash"]); extras.append(lash)
    pts = [(ex + sx * -22, ey - 16), (ex + sx * -6, ey - 27), (ex + sx * 12, ey - 30), (ex + sx * 28, ey - 24)]
    cu = bpy.data.curves.new("brow", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = PX(3.2); cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1)
    for bp, (bx, by) in zip(sp.bezier_points, pts): bp.co = P(bx, by, PX(80)); bp.handle_left_type = bp.handle_right_type = 'AUTO'
    brow = bpy.data.objects.new(f"Brow{side}", cu); sc.collection.objects.link(brow); brow.data.materials.append(M["brow"]); extras.append(brow)
for nm, y, scl in (("UpperLip", -42, S(1.55, 0.42, 0.62)), ("LowerLip", -52, S(1.25, 0.46, 0.62))):
    o = sphere(nm, HC + O(-PX(2), PX(y), PX(70)), PX(13.5), scl); o.data.materials.append(M["lip"]); extras.append(o)

# ---- hair: two rings of curls along the drawn outline, a fringe, and a back volume ----
random.seed(11); hair = []
for k, (rx, ry, n) in enumerate(((PX(90), PX(98), 19), (PX(112), PX(122), 23))):
    for i in range(n):
        a = math.radians(-55 + 290 * i / (n - 1)) + random.uniform(-0.04, 0.04)
        c = HC + O(math.cos(a) * rx, PX(18) + math.sin(a) * ry, PX(30) - k * PX(32) + random.uniform(-PX(4), PX(4)))
        if (c - HC).length < PX(82) and c.z < HC.z + PX(50): continue        # keep the face clear
        r = PX(15 + random.uniform(0, 7) - k * 1)
        o = sphere("curl", c, r, S(1, 1.05, 0.9), 16, 10); o.data.materials.append(M["hair"]); hair.append(o)
for x in (476, 500, 524, 548, 572):
    o = sphere("fringe", P(x, 274 + abs(x - 524) * 0.25, PX(70) - abs(x - 524) * 0.0004), PX(19), S(1, 0.8, 0.75), 16, 10); o.data.materials.append(M["hair"]); hair.append(o)
o = sphere("hair_back", HC + O(PX(4), PX(4), -PX(34)), PX(104), S(0.95, 1.04, 0.78)); o.data.materials.append(M["hair"]); hair.append(o)

# ---- export + preview (only when run directly; angel_build.py imports the parts) ----
HEAD_OBJS = [head] + extras + hair
HEAD_PARTS = dict(head=head, extras=extras, hair=hair, mats=M)
objs = HEAD_OBJS
if __name__ != "__main__": PREVIEW = None; OUT_GLB = None
bpy.ops.object.select_all(action='DESELECT')
for o in objs: o.select_set(True)
if OUT_GLB:
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, use_selection=True, export_apply=True, export_yup=True)
    print("exported", OUT_GLB, "faces:", sum(len(o.data.polygons) for o in objs if o.type == 'MESH'))

if PREVIEW:
    os.makedirs(PREVIEW, exist_ok=True)
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.show_shadows = True
    sc.render.resolution_x = sc.render.resolution_y = 600
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 70
    for deg in (0, 35, 90):
        a = math.radians(deg); r = 0.8
        cam.location = HC + O(math.sin(a) * r, PX(8), math.cos(a) * r)
        cam.rotation_euler = (HC - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = f"{PREVIEW}/head_{deg}.png"; bpy.ops.render.render(write_still=True)
    print("previews in", PREVIEW)
