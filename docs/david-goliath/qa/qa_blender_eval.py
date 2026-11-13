"""QA helper (headless Blender): evaluate the shipped GLBs independently of the pipeline scripts.

    blender -b --factory-startup --python docs/david-goliath/qa/qa_blender_eval.py -- <out.json>

Writes, in design coordinates (x right, y up, z toward the viewer; art-width units):
  characters.<id>.clips.<clip>: per frame the 2D convex hull (x, z) of every evaluated vertex of every mesh of the
      character (skinned body + bone-parented rigid props) plus min / max y, character-local (actor at origin, yaw 0);
      "lowHull" is the same for the vertices below y 0.010 (what rests on the page);
  desert: per node the world bounding box, per-vertex UV range, the residual against the top-down page projection,
      the highest vertex inside design.json's stage band polygon, every vertex above y 0.010 (x, z, y), and the
      banner bounds over every frame of their wave clips.
  <out>.npz (v3, CONTRACT §12): per desert node the per-loop world position + UV0 ("<node>__P", "<node>__UV"), the
      desert top-surface height field ("heightField", ray cast straight down on a 0.004 grid over the page), and per
      character clip frame a subsample of <= 600 evaluated vertices, character-local ("<ch>__<clip>": frames x N x 3).
qa_check.py reads this file; it never writes into another role's paths.
"""
import json, math, os, sys
import bpy
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
A = os.path.join(ROOT, "assets/david-goliath")
OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp/dg_work/qa/blender_eval.json"
FPS = 30


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS


def to_design(P):
    """Blender (x, y, z) after glTF import = glTF (x, -z, y); design = glTF axes."""
    return np.stack([P[:, 0], P[:, 2], -P[:, 1]], axis=1)


def world_verts(o, dg):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    M = np.array(o.matrix_world)
    W = co @ M[:3, :3].T + M[:3, 3]
    uv = None
    if me.uv_layers:
        lay = me.uv_layers[0]
        loops = np.empty(len(me.loops), dtype=np.int64)
        me.loops.foreach_get("vertex_index", loops)
        luv = np.empty(len(me.loops) * 2, dtype=np.float64)
        lay.data.foreach_get("uv", luv)
        uv = (loops, luv.reshape(-1, 2))
    ev.to_mesh_clear()
    return to_design(W), uv


def hull(P):
    """Monotone-chain convex hull of 2D points."""
    pts = sorted(set(map(tuple, np.round(P, 5).tolist())))
    if len(pts) < 3:
        return [list(p) for p in pts]
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return [list(p) for p in lo[:-1] + up[:-1]]


def set_action(obj, act):
    obj.animation_data_create()
    ad = obj.animation_data
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    ad.action = act
    if getattr(act, "slots", None):
        try:
            ad.action_slot = act.slots[0]
        except Exception:
            pass


def glb_mesh_nodes(path):
    """Names of the glTF nodes that carry a mesh (the importer adds bone-shape Icospheres we must skip)."""
    import struct
    b = open(path, "rb").read()
    j = json.loads(b[20:20 + struct.unpack_from("<I", b, 12)[0]])
    return {n["name"] for n in j["nodes"] if "mesh" in n}


out = {"characters": {}, "desert": {}}
NPZ = {}

# ------------------------------------------------------------------ characters (anim GLBs = what Unity ships)
for ch in ("david", "goliath"):
    reset()
    path = os.path.join(A, "anim", ch + ".glb")
    bpy.ops.import_scene.gltf(filepath=path)
    arm = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"][0]
    keep = glb_mesh_nodes(path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name in keep]
    for o in bpy.context.scene.objects:
        if o.animation_data:
            for tr in list(o.animation_data.nla_tracks):
                o.animation_data.nla_tracks.remove(tr)
    clips = {}
    acts = [a for a in bpy.data.actions if a.name.startswith(ch + "_")]
    for act in acts:
        # importer may append the object name: "david_walk_Armature" -> "david_walk"
        name = act.name
        for c in ("_" + arm.name, "_Armature"):
            if name.endswith(c):
                name = name[: -len(c)]
        set_action(arm, act)
        f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
        frames = []
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            P = np.concatenate([world_verts(o, dg)[0] for o in meshes if not o.hide_render])
            low = P[P[:, 1] < 0.010]                  # vertices touching / resting on the page
            sub = P[:: max(1, len(P) // 600)][:600]
            NPZ.setdefault(f"{ch}__PTS", {}).setdefault(name, []).append(np.round(sub, 4).astype(np.float32))
            frames.append({"f": f - f0, "hull": hull(P[:, [0, 2]]), "lowHull": hull(low[:, [0, 2]]) if len(low) else [],
                           "minY": round(float(P[:, 1].min()), 5), "maxY": round(float(P[:, 1].max()), 5)})
        clips[name] = {"frames": frames, "fps": FPS}
        print("QA eval", ch, name, len(frames), "frames", flush=True)
    out["characters"][ch] = {"clips": clips, "meshes": [o.name for o in meshes]}

# ------------------------------------------------------------------ desert
reset()
DPATH = os.path.join(A, "model", "desert.glb")
bpy.ops.import_scene.gltf(filepath=DPATH)
DKEEP = glb_mesh_nodes(DPATH)
dg = bpy.context.evaluated_depsgraph_get()
design = json.load(open(os.path.join(A, "design.json")))
bands = [np.array(b) for b in design["desert"]["stageBand"]["polygonsSheet"]]   # (x, ys), ys = -z; every part (§12.6)


def inside(poly, x, y):
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


nodes = {}
for o in bpy.context.scene.objects:
    if o.type != "MESH" or o.name not in DKEEP:
        continue
    P, uv = world_verts(o, dg)
    rec = {"bbox": [round(float(v), 5) for v in (*P.min(0), *P.max(0))], "verts": int(len(P)),
           "material": [s.material.name for s in o.material_slots if s.material]}
    if uv is not None:
        loops, luv = uv
        u = luv[:, 0]; v_gl = 1.0 - luv[:, 1]                        # Blender flips v on import
        rec["uvRange"] = [round(float(u.min()), 5), round(float(u.max()), 5),
                          round(float(v_gl.min()), 5), round(float(v_gl.max()), 5)]
        # top-down page projection: u = x + 0.5, v_page = -z / artH; glTF v = 1 - v_page
        artH = design["artHeightUnits"]
        Pl = P[loops]
        du = np.abs(u - (Pl[:, 0] + 0.5)); dv = np.abs(v_gl - (1.0 + Pl[:, 2] / artH))
        rec["topDownResidual"] = [round(float(du.max()), 5), round(float(dv.max()), 5)]
        rec["uvConstant"] = bool(np.ptp(u) < 1e-4 and np.ptp(v_gl) < 1e-4)
        NPZ[o.name + "__P"] = Pl.astype(np.float32)
        NPZ[o.name + "__UV"] = np.stack([u, 1.0 - v_gl], 1).astype(np.float32)   # (u, page v): page v = 0 at the art bottom
    # stage band: tallest vertex whose (x, ys) lies inside the band
    hi = -1.0
    for p in P[:: max(1, len(P) // 4000)]:
        if p[1] > hi and any(inside(bd, p[0], -p[2]) for bd in bands):
            hi = float(p[1])
    rec["maxYInStageBand"] = round(hi, 5) if hi >= 0 else None
    tall = P[P[:, 1] > 0.010]                        # for qa_check's own stage band (design.json keeps one part only)
    rec["tallXZY"] = np.round(tall[:, [0, 2, 1]], 4).tolist()
    nodes[o.name] = rec
# desert top-surface height field (ray cast down; banners included at rest pose)
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import bmesh
bm = bmesh.new()
for o in bpy.context.scene.objects:
    if o.type == "MESH" and o.name in DKEEP and o.name != "brook":
        ev_ = o.evaluated_get(dg); me_ = ev_.to_mesh(); me_.transform(o.matrix_world); bm.from_mesh(me_); ev_.to_mesh_clear()
bvh = BVHTree.FromBMesh(bm)
GX = np.arange(-0.62, 0.62 + 1e-9, 0.004); GZ = np.arange(-1.51, 0.244 + 1e-9, 0.004)
HF = np.zeros((len(GZ), len(GX)), dtype=np.float32)
for iz, z in enumerate(GZ):
    for ix, x in enumerate(GX):
        hit = bvh.ray_cast(Vector((x, -z, 2.0)), Vector((0, 0, -1)))   # Blender (x, y, z) = design (x, -z, y)
        if hit[0] is not None: HF[iz, ix] = max(0.0, hit[0].z)
NPZ["heightField"] = HF; NPZ["heightFieldX"] = GX; NPZ["heightFieldZ"] = GZ
# root transform
root = bpy.data.objects.get("desert")
out["desert"]["rootHasTRS"] = bool(root and (root.location.length > 1e-6 or any(abs(s - 1) > 1e-6 for s in root.scale)))
out["desert"]["nodes"] = nodes
out["desert"]["objectNames"] = sorted(o.name for o in bpy.context.scene.objects if not o.name.startswith("Icosphere"))
# banners over their wave clips
ban = {}
for act in bpy.data.actions:
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE" and o.name.split("_")[0] in act.name]
    if not arms:
        arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    lo = np.array([9.0, 9.0, 9.0]); hi = -lo
    for a in arms:
        set_action(a, act)
    f0, f1 = int(round(act.frame_range[0])), int(round(act.frame_range[1]))
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        dgx = bpy.context.evaluated_depsgraph_get()
        for o in bpy.context.scene.objects:
            if o.type == "MESH" and o.name.startswith("banner"):
                P, _ = world_verts(o, dgx)
                lo = np.minimum(lo, P.min(0)); hi = np.maximum(hi, P.max(0))
    ban[act.name] = {"frames": f1 - f0 + 1, "bbox": [round(float(v), 5) for v in (*lo, *hi)]}
out["desert"]["bannerClips"] = ban

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w"))
flat = {k: v for k, v in NPZ.items() if not k.endswith("__PTS")}
for k, v in NPZ.items():
    if k.endswith("__PTS"):
        for clip, fr in v.items(): flat[clip + "__pts"] = np.stack(fr)
np.savez_compressed(os.path.splitext(OUT)[0] + ".npz", **flat)
print("QA eval written", OUT, flush=True)
