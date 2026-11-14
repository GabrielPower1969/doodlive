"""story_kit/animation.py: shared animation functions, included into a pack script with
`story_kit.include(globals(), "animation")` (pipeline/story_kit/__init__.py; docs/STORY-KIT.md).

The functions run in the pack's own namespace, exactly as if they were written in the pack file, so they read the pack's
constants and helpers. A pack overrides one by defining a function of the same name after the include.
Extracted verbatim from pipeline/ru_characters.py / ru_animate.py / ru_bethlehem.py (identical in esther, daniel,
exodus or prodigal); story-specific literals became pack constants: ENV (env-var prefix, e.g. "RU_"),
PAGE_MATERIAL (the page material name, e.g. "ru_page").

Names a pack must define (or import) before calling these functions:
  ANIM, BLENDER, BLINK_SHAPE, C, CHARS, CI, CLIPS, Clip, DECAL_NODES, ENV, FACES, FACE_DIR, FPS, KNEEL, Matrix,
  PROPS, REGIONS, ROOT, SET_GLB, TL, Vector, WORK, _PAY, bpy, compose_contact, contract_clips, evaluate_primary,
  hidden_props, json, math, os, random, sim_chains, subprocess, sys
"""


def run_blender(mode, *extra):
    cmd = [BLENDER, "-b", "--factory-startup", "--python", os.path.abspath(__file__), "--", mode, *extra]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith((ENV, "Traceback", "Error", "  File")) or "Error" in ln]
    print("\n".join(tail[-260:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get(ENV + "PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get(ENV + "PROBE_OUT", "probe.png"))
    sheet.save(out); print(ENV + "PROBE_SHEET", out)


def main_cli():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(WORK, exist_ok=True); os.makedirs(ANIM, exist_ok=True)
    if mode in ("build", "all"):
        run_blender("build")
    if mode in ("verify", "all"):
        run_blender("verify")
    if mode in ("contact", "all"):
        run_blender("contact"); compose_contact()
    if mode == "probe":
        run_blender("probe"); compose_probe()
    if mode == "compose":
        compose_contact()


def V(x=0.0, y=0.0, z=0.0):
    return Vector((float(x), float(y), float(z)))


def to_bl(p):
    return C @ Vector(p)


def to_d(p):
    return CI @ Vector(p)


def rot_d(axis_d, deg):
    """Rotation (3x3, Blender coords) about a design-space axis."""
    return Matrix.Rotation(math.radians(deg), 3, (C @ Vector(axis_d)).normalized())


def smooth(t):
    t = min(1.0, max(0.0, t)); return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def K(keys, f, N=None, loop=False):
    """Catmull-Rom through [(frame, value)], clamped (or wrapped when loop: the key at N should equal the key at 0)."""
    ks = sorted(keys)
    if len(ks) == 1:
        return ks[0][1]
    if loop:
        f = f % N
        core = [k for k in ks if k[0] < N]
        ext = [(k[0] - N, k[1]) for k in core[-2:]] + core + [(k[0] + N, k[1]) for k in core[:3]]
        ks = ext
    else:
        if f <= ks[0][0]:
            return ks[0][1]
        if f >= ks[-1][0]:
            return ks[-1][1]
        ks = [(2 * ks[0][0] - ks[1][0], ks[0][1])] + ks + [(2 * ks[-1][0] - ks[-2][0], ks[-1][1])]
    for i in range(1, len(ks) - 2):
        (f1, p1), (f2, p2) = ks[i], ks[i + 1]
        if f1 <= f <= f2:
            (f0, p0), (f3, p3) = ks[i - 1], ks[i + 2]
            dt = f2 - f1
            t = (f - f1) / dt if dt else 0.0
            m1 = (p2 - p0) / (f2 - f0) * dt if f2 != f0 else 0.0
            m2 = (p3 - p1) / (f3 - f1) * dt if f3 != f1 else 0.0
            t2, t3 = t * t, t * t * t
            return (2 * t3 - 3 * t2 + 1) * p1 + (t3 - 2 * t2 + t) * m1 + (-2 * t3 + 3 * t2) * p2 + (t3 - t2) * m2
    return ks[-1][1]


def KL(keys, f, N=None, loop=False, lag=0.0):
    """K with every key delayed by `lag` frames (overlapping action: a child follows its parent late)."""
    return K(keys, f - lag, N, loop)


def wave(f, N, cycles=1.0, phase=0.0):
    return math.sin(2 * math.pi * (cycles * f / N + phase))


def ease_io(t):
    t = min(1.0, max(0.0, t)); return 0.5 - 0.5 * math.cos(math.pi * t)


def bump(f, a, b):
    """0 -> 1 -> 0 between frames a and b (sine hump, eased)."""
    if f <= a or f >= b:
        return 0.0
    return math.sin(math.pi * smooth((f - a) / (b - a)))


def pulses(f, N, hits, decay=5.0, loop=True):
    """Irregular hits [(frame, strength)]: sharp attack, exponential decay (laughs, sobs, shakes)."""
    v = 0.0
    for h, s in hits:
        d = f - h
        if loop:
            d = d % N
        if 0 <= d < 6 * decay:
            v += s * (1 - math.exp(-d * 1.5)) * math.exp(-d / decay)
    return v


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def blink(c, f, N, at, loop=True, base=1.0, slow=1.0):
    """Eyelids: blinks starting at the frames in `at` (irregular on purpose). base > 1 = heavy / half-shut lids."""
    s = base
    for b in at:
        d = (f - b) % N if loop else f - b
        u = d / slow
        if 0 <= u < len(BLINK_SHAPE) - 1:
            i = int(u); w = u - i
            s = max(s, lerp(BLINK_SHAPE[i], BLINK_SHAPE[i + 1], w))
    c["eyelids.sy"] = s


def syllables(N, seed, amp=(6.0, 15.0), dur=(3.0, 6.5), gap=0.2, lead=3, tail=5):
    """Irregular jaw keys for talking: syllables of varying length and opening, word gaps and breaths.
    Returns (keys, beats) - beats are the frames of the strongest syllables (for nods and hand beats)."""
    r = random.Random(seed)
    keys = [(0, 0.0)]
    t = float(lead)
    beats = []
    while t < N - tail - dur[0]:
        d = r.uniform(*dur)
        a = r.uniform(*amp)
        if r.random() < 0.22:
            a *= 0.45                       # unstressed / closed vowel
        peak = t + d * r.uniform(0.35, 0.55)
        keys.append((peak, a)); keys.append((t + d, r.uniform(0.0, 2.5)))
        if a > amp[0] + 0.70 * (amp[1] - amp[0]):
            beats.append(peak)
        t += d
        if r.random() < gap:
            t += r.uniform(5, 13)          # word gap / little breath
            keys.append((t - 1, 0.0))
    keys.append((N, 0.0))
    return sorted(keys), beats


def jaw_from(keys, f, N):
    return max(0.0, K(keys, f % N, N, False))


def beat_curve(beats, f, N, width=7.0, loop=True):
    """0..1 bumps at the beat frames (rise 40 %, fall 60 % of width)."""
    v = 0.0
    for b in beats:
        d = f - b
        if loop:
            d = (d + N / 2) % N - N / 2
        if -0.4 * width <= d <= 0.6 * width:
            u = (d + 0.4 * width) / width
            v = max(v, math.sin(math.pi * u))
    return v


def addc(c, k, v):
    c[k] = c.get(k, 0.0) + v


def frame_from(Y_d, Z_d):
    Y = (C @ Y_d).normalized()
    Z = (C @ Z_d)
    Z = (Z - Y * Z.dot(Y)).normalized()
    X = Y.cross(Z)
    return Matrix((X, Y, Z)).transposed()


def ik2(rig, basis, M, upper, lower, target_d, pole_d, legs):
    H = rig.pos(M, upper)
    L1, L2 = rig.length[upper], rig.length[lower]
    T = Vector(target_d)
    dvec = T - H
    d = max(1e-6, min(dvec.length, (L1 + L2) * 0.9995))
    u = dvec.normalized()
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    p = Vector(pole_d) - u * Vector(pole_d).dot(u)
    p = p.normalized() if p.length > 1e-6 else V(0, 0, 1)
    Kn = H + u * a + p * h
    zu = p if legs else -p
    Ru = frame_from(Kn - H, zu)
    rig.set_world_rot(basis, M, upper, Ru)
    X = Ru.col[0]
    Yl = (C @ (T - Kn)).normalized()
    Zl = X.cross(Yl)
    Rl = Matrix((X, Yl, Zl)).transposed()
    rig.set_world_rot(basis, M, lower, Rl)
    return Kn


def clip(ch, name, N, loop, **kw):
    def deco(fn):
        CLIPS.append(Clip(ch, name, N, loop, fn, **kw)); return fn
    return deco


def foot_points(rig, side):
    a = rig.head["foot" + side]
    ball = rig.head["toe" + side] - a
    tip = rig.tail["toe" + side] - a
    heel = V(0, -a.y + 0.001, -0.18 * ball.z)
    return heel, ball, tip


def planted_ankle_y(rig, side, pitch_deg):
    key = (rig.ch, side, round(pitch_deg, 3))
    if key not in _PAY:
        R = rot_d((1, 0, 0), pitch_deg)
        low = min((CI @ (R @ (C @ p))).y for p in foot_points(rig, side))
        _PAY[key] = -low
    return _PAY[key]


def gait(rig, f, N, L, lift, duty, offsetR=0.5, offsetL=0.0, heel=10.0, toeoff=24.0, out=None, lift_shape=1.0,
         spread=0.0, fwd=0.0):
    """In-place gait: per side the ankle target (root space) and foot pitch. Stance: the foot slides from +L/2 to
    -L/2 at constant speed (speed = L / (duty * N / FPS)); swing: eased return with lift."""
    out = out if out is not None else {}
    for side, off in (("L", offsetL), ("R", offsetR)):
        p = (f / N + off) % 1.0
        base = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        if p < duty:
            s = p / duty
            z = L / 2 - L * s
            pitch = -heel * (1 - smooth(s / 0.15)) + toeoff * smooth((s - 0.7) / 0.3)
            y = planted_ankle_y(rig, side, pitch)
            contact = True
        else:
            s = (p - duty) / (1 - duty)
            z = -L / 2 + L * smooth(s)
            pitch = lerp(toeoff, -heel, smooth(s * 1.1))
            y = planted_ankle_y(rig, side, pitch) + lift * math.sin(math.pi * min(1.0, s)) ** lift_shape
            contact = False
        out["leg" + side] = (V(base.x + sx * spread, y, base.z + z + fwd), pitch, contact, p)
    return out


def legs_ik_channels(chs, g):
    for side in "LR":
        t, pitch, _, _ = g["leg" + side]
        chs[f"ik.leg{side}"] = t
        chs[f"foot{side}.pitch"] = pitch


def stand_feet(rig, chs, spread=0.0, fwdL=0.0, fwdR=0.0, pitchL=0.0, pitchR=0.0, liftL=0.0, liftR=0.0, fwd=0.0, xL=0.0, xR=0.0):
    for side, fw, pt, lf, xo in (("L", fwdL, pitchL, liftL, xL), ("R", fwdR, pitchR, liftR, xR)):
        b = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        chs[f"ik.leg{side}"] = V(b.x + sx * spread + xo, planted_ankle_y(rig, side, pt) + lf, b.z + fw + fwd)
        chs[f"foot{side}.pitch"] = pt


def arm_ik(c, side, target, pole=None, space="root", w=1.0):
    c[f"ik.arm{side}"] = Vector(target)
    c[f"ikspace.arm{side}"] = space
    c[f"ikw.arm{side}"] = w
    if pole is not None:
        c[f"pole.arm{side}"] = Vector(pole)


def fingers(c, side, curl):
    c[f"fingers{side}.curl"] = curl


def rel(rig, bone, p):
    """Offset of a root-space (rest) point from a bone's rest head: IK targets in that bone's space."""
    return Vector(p) - rig.head[bone]


def kneel_geom(rig, side, KY=0.012, kz=0.014, thigh_back=6.0, shin_slope=16.0, spread=0.003):
    """Knee joint KY above the page at z = kz, thigh leaning back by thigh_back, shin sloping up behind by shin_slope.
    Returns (hip joint, knee, ankle) in root space."""
    sx = 1 if side == "L" else -1
    b = rig.head["thigh" + side]
    th, sh = rig.length["thigh" + side], rig.length["shin" + side]
    knee = V(rig.head["shin" + side].x + sx * spread, KY, kz)
    tb, ss = math.radians(thigh_back), math.radians(shin_slope)
    hip = knee + V(0, th * math.cos(tb), -th * math.sin(tb))
    ankle = knee + V(0, sh * math.sin(ss), -sh * math.cos(ss))
    return hip, knee, ankle


def tuck_pitch(rig, side, ankle_y):
    """Foot pitch (toes tucked under) whose lowest point just touches the page for this ankle height."""
    best, bp = 1e9, 0.0
    for p in range(0, 100, 2):
        e = abs(planted_ankle_y(rig, side, p) - ankle_y)
        if e < best:
            best, bp = e, p
    return float(bp)


def kneel_legs(rig, c, wL=1.0, wR=1.0, hips_w=None, **kw):
    """Blend both legs (w 0 = standing, 1 = kneeling, knees on the page) and the hips down."""
    prm = dict(KNEEL.get(rig.ch, {})); prm.update(kw)
    hw = 0.5 * (wL + wR) if hips_w is None else hips_w
    hipy = []
    for side, w in (("L", wL), ("R", wR)):
        hip, knee, ankle = kneel_geom(rig, side, **prm)
        hipy.append((hip.y - rig.head["thigh" + side].y, hip.z))
        b = rig.head["foot" + side]
        y_st = planted_ankle_y(rig, side, 0)
        pk = tuck_pitch(rig, side, ankle.y)
        tgt = V(lerp(b.x, ankle.x, w), lerp(y_st, ankle.y, w), lerp(b.z, ankle.z, w))
        pitch = pk * w
        tgt.y = max(tgt.y, planted_ankle_y(rig, side, pitch))
        c[f"ik.leg{side}"] = tgt
        c[f"foot{side}.pitch"] = pitch
        sx = 1 if side == "L" else -1
        c[f"pole.leg{side}"] = V(0.08 * sx, 0, 1)
    dy = sum(h[0] for h in hipy) / 2
    dz = sum(h[1] for h in hipy) / 2
    c["hips.ty"] = c.get("hips.ty", 0.0) + dy * hw
    c["hips.tz"] = c.get("hips.tz", 0.0) + dz * hw


def hug_sway(f, N):
    return wave(f, N, 1, 0.0)


def staff_at(c, foot, d, w=1.0):
    c["staff.foot"] = Vector(foot); c["staff.dir"] = Vector(d).normalized(); c["staff.w"] = w


def ik_limb(rig, basis, M, chs, limb):
    up, lo, end = {"legL": ("thighL", "shinL", "footL"), "legR": ("thighR", "shinR", "footR"),
                   "armL": ("upperArmL", "forearmL", "handL"), "armR": ("upperArmR", "forearmR", "handR")}[limb]
    key = "ik." + limb
    if key not in chs:
        return
    w = chs.get("ikw." + limb, 1.0)
    if w <= 1e-4:
        return
    legs = limb.startswith("leg")
    side = limb[-1]
    sx = 1 if side == "L" else -1
    t = Vector(chs[key])
    space = chs.get("ikspace." + limb, "root")
    Mroot = M["root"] @ rig.rest["root"].inverted()
    if space in M and space != "root":
        t_world = to_d(M[space] @ (rig.rest[space].inverted() @ to_bl(rig.head[space] + t)))
    else:
        t_world = to_d(Mroot @ to_bl(t))
    pole = V(0.15 * sx, 0, 1) if legs else V(0.6 * sx, -0.6, -0.5)
    if "pole." + limb in chs:
        pole = Vector(chs["pole." + limb])
    pole = to_d(Mroot.to_3x3() @ to_bl(pole))
    old = {n: [basis[n][0].copy(), basis[n][1].copy(), basis[n][2]] for n in (up, lo, end)}
    ik2(rig, basis, M, up, lo, t_world, pole, legs)
    if legs:
        pitch = chs.get(f"foot{side}.pitch", 0.0)
        Rf = Mroot.to_3x3().normalized() @ rot_d((0, 1, 0), chs.get(f"foot{side}.ry", 0.0)) @ rot_d((1, 0, 0), pitch) @ rig.rest3[end]
        rig.set_world_rot(basis, M, end, Rf)
    if w < 0.9999:
        for n in (up, lo, end):
            basis[n][0] = old[n][0].slerp(basis[n][0], w)
        rig.fk(basis, M)


def aim_prop(rig, basis, M, bone, want_root_d, hand="handR"):
    """Turn the hand (minimal rotation) so the prop bone points along want (design, root space)."""
    Mroot = M["root"] @ rig.rest["root"].inverted()
    want = (Mroot.to_3x3() @ (C @ Vector(want_root_d))).normalized()
    ax = rig.prop_axis.get(bone, Vector((0, 1, 0)))
    cur = (M[bone].to_3x3().normalized() @ ax).normalized()
    Rd = cur.rotation_difference(want).to_matrix()
    Rh = M[hand].to_3x3().normalized()
    rig.set_world_rot(basis, M, hand, Rd @ Rh)


def staff_solve(rig, basis, M, chs):
    """Naomi: staff foot at chs['staff.foot'] (root space, on the page), staff along chs['staff.dir']: iterate the
    right wrist target until the foot is there. Without staff.foot: optional staff.aim only (staff follows the hand)."""
    if rig.staff_foot is None:
        return
    if "staff.foot" not in chs:
        if "ik.armR" in chs:
            ik_limb(rig, basis, M, chs, "armR")
        if "staff.aim" in chs:
            aim_prop(rig, basis, M, "staff", chs["staff.aim"])
        return
    Mroot = M["root"] @ rig.rest["root"].inverted()
    foot = Vector(chs["staff.foot"]); d = Vector(chs["staff.dir"]).normalized()
    want = to_d(Mroot @ to_bl(foot))
    target = Vector(chs["ik.armR"]) if "ik.armR" in chs else foot + d * (rig.staff_len + 0.004) + V(0.008, 0.004, -0.006)
    ch2 = {"ikspace.armR": "root", "ikw.armR": 1.0, "pole.armR": chs.get("pole.armR", V(-0.7, -0.5, -0.6))}
    for _ in range(7):
        ch2["ik.armR"] = target
        ik_limb(rig, basis, M, ch2, "armR")
        aim_prop(rig, basis, M, "staff", d)
        err = rig.foot_of_staff(M) - want
        if err.length < 2e-5:
            break
        target = target - (CI @ (Mroot.to_3x3().inverted() @ (C @ err)))
    chs["ik.armR"] = target


def bake_clip(rig, clip_):
    N = clip_.N
    prim = [evaluate_primary(rig, clip_, f) for f in range(N + 1)]
    if clip_.loop:
        chs0, b0, M0 = prim[0]
        bN = {n: [b0[n][0].copy(), b0[n][1].copy(), b0[n][2].copy()] for n in b0}
        prim[N] = (prim[N][0], bN, rig.fk(bN))
    sim_chains(rig, prim, clip_.loop)
    if clip_.loop:
        # exact seam: frame N's basis = frame 0's after the chains are closed
        b0 = prim[0][1]
        bN = {n: [b0[n][0].copy(), b0[n][1].copy(), b0[n][2].copy()] for n in b0}
        prim[N] = (prim[N][0], bN, rig.fk(bN))
    return [(p[1], p[2]) for p in prim]


def write_action(rig, clip_, frames):
    obj = rig.obj
    act = bpy.data.actions.get(clip_.action) or bpy.data.actions.new(clip_.action)
    act.use_fake_user = True
    obj.animation_data_create()
    obj.animation_data.action = act
    n = len(frames)
    for pb in obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    lin = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value
    for name in rig.names:
        qs, ls, ss = [], [], []
        prevq = None
        for basis, _ in frames:
            q, l, s = basis[name]
            q = q.copy()
            if prevq is not None and prevq.dot(q) < 0:
                q.negate()
            prevq = q
            qs.append(q); ls.append(l); ss.append(s)
        for path, comps in ((f'pose.bones["{name}"].rotation_quaternion', [[q[i] for q in qs] for i in range(4)]),
                            (f'pose.bones["{name}"].location', [[l[i] for l in ls] for i in range(3)]),
                            (f'pose.bones["{name}"].scale', [[s[i] for s in ss] for i in range(3)])):
            for i, vals in enumerate(comps):
                fc = act.fcurve_ensure_for_datablock(obj, path, index=i, group_name=name)
                fc.keyframe_points.clear()
                fc.keyframe_points.add(n)
                co = []
                for fr, v in enumerate(vals):
                    co += [float(fr), float(v)]
                fc.keyframe_points.foreach_set("co", co)
                fc.keyframe_points.foreach_set("interpolation", [lin] * n)
                fc.update()
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, clip_.N
    act.use_cyclic = clip_.loop
    for m in list(act.pose_markers):
        act.pose_markers.remove(m)
    for mname, mf in clip_.markers.items():
        pm = act.pose_markers.new(mname); pm.frame = int(mf)
    return act


def timeline_clips():
    return sorted({(a["who"], a["clip"]) for a in TL["acting"]})


def mesh_points(rig, step_n=3000, skip_props=()):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in rig.obj.children:
        if o.type != 'MESH' or o.name.endswith("_eyelids") or o.name in skip_props:
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = rig.obj.matrix_world.inverted() @ o.matrix_world
        n = len(me.vertices)
        step = max(1, n // step_n)
        for i in range(0, n, step):
            pts.append((to_d(mw @ me.vertices[i].co), o.name))
        ev.to_mesh_clear()
    return pts


def apply_basis(rig, basis):
    for n in rig.names:
        pb = rig.obj.pose.bones[n]
        pb.rotation_mode = 'QUATERNION'
        q, l, s = basis[n]
        pb.rotation_quaternion = q; pb.location = l; pb.scale = s


def reset_pose(rig):
    for pb in rig.obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)


def fix_uv_order(o):
    """Page UVs must be the FIRST UV map (glTF TEXCOORD_0, 0..1) and the face decal the SECOND (TEXCOORD_1), as in
    David & Goliath / Esther's fix. Rebuild the layers in that order if they are not (page found by name, else range)."""
    me = o.data
    lays = list(me.uv_layers)
    if len(lays) < 2:
        return
    data = {}
    for l in lays:
        buf = [0.0] * (2 * len(l.data)); l.data.foreach_get("uv", buf); data[l.name] = buf
    page = "UVMap" if "UVMap" in data else min(data, key=lambda n: sum(1 for v in data[n] if v < -1e-4 or v > 1 + 1e-4))
    order = [page] + [n for n in data if n != page]
    if [l.name for l in lays] == order:
        return
    for l in list(me.uv_layers):
        me.uv_layers.remove(l)
    for n in order:
        nl = me.uv_layers.new(name=n)
        nl.data.foreach_set("uv", data[n])
    me.uv_layers.active = me.uv_layers[page]
    try:
        me.uv_layers[page].active_render = True
    except Exception:
        pass


def glb_json(path):
    import struct
    b = open(path, "rb").read()
    assert b[:4] == b"glTF"
    l0 = struct.unpack_from("<I", b, 12)[0]
    return json.loads(b[20:20 + l0])


def accessor_range(path, j, idx):
    import struct
    acc = j["accessors"][idx]
    if "min" in acc:
        return acc["min"], acc["max"]
    b = open(path, "rb").read()
    l0 = struct.unpack_from("<I", b, 12)[0]
    bin0 = 20 + l0 + 8
    bv = j["bufferViews"][acc["bufferView"]]
    off = bin0 + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", 8)
    mn, mx = [1e9, 1e9], [-1e9, -1e9]
    for i in range(acc["count"]):
        u, v = struct.unpack_from("<ff", b, off + i * stride)
        mn = [min(mn[0], u), min(mn[1], v)]; mx = [max(mx[0], u), max(mx[1], v)]
    return mn, mx


def mode_verify():
    meta = json.load(open(os.path.join(ANIM, "clips.json")))
    want = {c["action"]: c for c in meta["clips"]}
    out = {"glb": {}, "sampleErr": {}}
    for ch in CHARS:
        path = os.path.join(ANIM, f"{ch}.glb")
        j = glb_json(path)
        anims = {}
        for a in j.get("animations", []):
            tmax = max(j["accessors"][s["input"]]["max"][0] for s in a["samplers"])
            anims[a["name"]] = {"channels": len(a["channels"]), "seconds": round(tmax, 4), "frames": round(tmax * FPS)}
        uv = {}
        for mesh in j.get("meshes", []):
            for pr in mesh["primitives"]:
                for k in ("TEXCOORD_0", "TEXCOORD_1"):
                    if k in pr["attributes"]:
                        mn, mx = accessor_range(path, j, pr["attributes"][k])
                        uv.setdefault(k, []).append((mesh["name"], [round(v, 3) for v in mn], [round(v, 3) for v in mx]))
        uv0_ok = all(mn[0] >= -1e-3 and mn[1] >= -1e-3 and mx[0] <= 1.001 and mx[1] <= 1.001 for _, mn, mx in uv.get("TEXCOORD_0", []))
        out["glb"][ch] = {"bytes": os.path.getsize(path), "animations": anims, "skins": len(j.get("skins", [])),
                          "nodes": [n.get("name") for n in j["nodes"]], "meshes": len(j.get("meshes", [])), "uv": uv,
                          "uv0InUnitSquare": uv0_ok}
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.render.fps = FPS
        bpy.ops.import_scene.gltf(filepath=path)
        arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][0]
        errs = {}
        for name, info in want.items():
            if info["char"] != ch:
                continue
            act = next((a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_")), None)
            if act is None:
                errs[name] = "missing"; continue
            arm.animation_data_create(); arm.animation_data.action = act
            if act.slots:
                try:
                    arm.animation_data.action_slot = act.slots[0]
                except Exception:
                    pass
            worst = 0.0
            for fr, bones in info["samples"].items():
                bpy.context.scene.frame_set(int(fr))
                bpy.context.view_layer.update()
                for bn, exp in bones.items():
                    p = arm.matrix_world @ arm.pose.bones[bn].head
                    got = Vector((p.x, p.z, -p.y))
                    worst = max(worst, (got - Vector(exp)).length)
            errs[name] = round(worst, 6)
        out["sampleErr"][ch] = errs
    want_c = contract_clips()
    out["contractMissing"] = {ch: [c for c in want_c[ch] if f"{ch}_{c}" not in out["glb"][ch]["animations"]] for ch in CHARS}
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    for ch in CHARS:
        for nm, a in sorted(out["glb"][ch]["animations"].items()):
            print(f"{ENV}VERIFY {ch} {nm} {a['frames']}f {a['seconds']}s ch={a['channels']} sampleErr={out['sampleErr'][ch].get(nm)}")
        g = out["glb"][ch]
        print(f"{ENV}VERIFY_GLB {ch} bytes={g['bytes']} skins={g['skins']} meshes={g['meshes']} "
              f"uv0InUnitSquare={g['uv0InUnitSquare']} uv={json.dumps(g['uv'])}")
        print(f"{ENV}VERIFY_NODES {ch} {[n for n in g['nodes'] if n and n.split('_')[-1] in PROPS + ('eyelids',) or n in PROPS]}")
    print(ENV + "VERIFY_MISSING", json.dumps(out["contractMissing"]))


def srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def char_material(ch):
    """Demo colours by face region (attribute st_region -> constant colour ramp) + face decal on UV 'decal'."""
    regs = REGIONS["characters"][ch]["regions"]
    m = bpy.data.materials.new(f"anim_{ch}"); m.use_nodes = True; nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = 0.75
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "st_region"; at.attribute_type = 'GEOMETRY'
    dv = nt.nodes.new("ShaderNodeMath"); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = 64.0
    nt.links.new(at.outputs["Fac"], dv.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    items = sorted((r["id"], r.get("hex", "#cccccc")) for r in regs.values() if "id" in r)
    els[0].position = 0.0; els[0].color = (0.8, 0.8, 0.8, 1)
    els[1].position = 0.999; els[1].color = (0.8, 0.8, 0.8, 1)
    for rid, hx in items:
        e = els.new((rid - 0.5) / 64.0)
        e.color = [srgb_lin(v) for v in hex_rgb(hx)] + [1.0]
    nt.links.new(dv.outputs[0], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    fd = FACES[ch]
    dt = nt.nodes.new("ShaderNodeTexImage")
    dt.image = bpy.data.images.load(os.path.join(FACE_DIR, f"{ch}_{fd['default']}.png"), check_existing=True)
    dt.extension = 'CLIP'
    du = nt.nodes.new("ShaderNodeUVMap"); du.uv_map = "decal"
    nt.links.new(du.outputs["UV"], dt.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    nt.links.new(dt.outputs["Alpha"], mix.inputs["Factor"])
    nt.links.new(col, mix.inputs[6]); nt.links.new(dt.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    DECAL_NODES[ch] = dt
    return m


def setup_look(sc, res, samples=12, stage=True):
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = -0.1
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    sc.world = bpy.data.worlds.new("W"); sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.86, 0.84, 0.80, 1); bg.inputs[1].default_value = 0.9
    sc.world.color = (0.86, 0.84, 0.80)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 2.8; sun.data.angle = math.radians(5)
    sun.rotation_euler = (math.radians(40), math.radians(-12), math.radians(-28))
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    for ch in CHARS:
        m = char_material(ch)
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name.startswith(ch + "_"):
                o.data.materials.clear(); o.data.materials.append(m)
    me = bpy.data.meshes.new("floor")
    R_ = 4.0
    vs = [(-R_, -R_, -0.0005), (R_, -R_, -0.0005), (R_, R_, -0.0005), (-R_, R_, -0.0005), (-R_, -R_, R_), (R_, -R_, R_), (R_, R_, R_), (-R_, R_, R_)]
    me.from_pydata(vs, [], [(0, 1, 2, 3), (3, 2, 6, 7), (0, 4, 5, 1), (1, 5, 6, 2), (0, 3, 7, 4)])
    fo = bpy.data.objects.new("floor", me); sc.collection.objects.link(fo)
    fm = bpy.data.materials.new("floor"); fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.82, 0.74, 0.58, 1); me.materials.append(fm)
    if stage and os.path.exists(SET_GLB) and os.environ.get(ENV + "NOSET") != "1":
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=SET_GLB)
        new = [o for o in bpy.data.objects if o not in before]
        pm = bpy.data.materials.new("anim_set"); pm.use_nodes = True
        b2 = pm.node_tree.nodes.get("Principled BSDF"); b2.inputs["Roughness"].default_value = 0.9
        b2.inputs["Base Color"].default_value = (0.80, 0.70, 0.52, 1)
        hide = {"canopy", "dropped"}
        for o in new:
            if o.type == 'MESH':
                for i in range(len(o.material_slots)):
                    o.material_slots[i].material = pm
            q = o
            while q is not None:
                if q.name.split(".")[0] in hide:
                    o.hide_render = True; break
                q = q.parent
            o.select_set(False)


def camera(sc):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.clip_start = 0.005; cam.data.clip_end = 50
    return cam


def look(cam, target_d, cam_d, lens=40):
    cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.location = to_bl(cam_d)
    cam.rotation_euler = (to_bl(target_d) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def place_rig(rig, x, z, yaw_deg, y=0.0):
    rig.obj.location = to_bl(V(x, y, z))
    rig.obj.rotation_euler = (0, 0, math.radians(yaw_deg))


def show_only(rigs, chs, cl_of=None):
    for ch, r in rigs.items():
        vis = ch in chs
        r.obj.hide_render = not vis
        hid = hidden_props(r, cl_of[ch]) if (cl_of and ch in cl_of) else []
        for o in r.obj.children:
            o.hide_render = (not vis) or (o.name in hid)


def view_cam(cam, rig, mark, view, bone=None, dist_k=2.3, H=None):
    x, z, yaw0 = mark
    H = H or rig.H
    yaw = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "top": 25, "low": 25}[view] + yaw0
    tgt = V(x, H * 0.45, z); dist = H * dist_k; hgt = H * 0.60
    if bone:
        tgt = to_d(rig.obj.matrix_world @ rig.obj.pose.bones[bone].head); dist = H * 0.9; hgt = tgt.y + 0.02
    if view == "top":
        hgt = dist * 1.3
    if view == "low":
        hgt = 0.02
    a_ = math.radians(yaw)
    look(cam, tgt, V(tgt.x + math.sin(a_) * dist, hgt, tgt.z + math.cos(a_) * dist))


def place_pair(rigs, ra, rb, dist, cx=-0.10, cz=0.08):
    """A at (cx - d/2, cz) facing +x (yaw +90), B at (cx + d/2, cz) facing -x: they face each other."""
    place_rig(ra, cx - dist / 2, cz, 90.0); place_rig(rb, cx + dist / 2, cz, -90.0)
