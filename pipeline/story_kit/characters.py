"""story_kit/characters.py: shared characters functions, included into a pack script with
`story_kit.include(globals(), "characters")` (pipeline/story_kit/__init__.py; docs/STORY-KIT.md).

The functions run in the pack's own namespace, exactly as if they were written in the pack file, so they read the pack's
constants and helpers. A pack overrides one by defining a function of the same name after the include.
Extracted verbatim from pipeline/ru_characters.py / ru_animate.py / ru_bethlehem.py (identical in esther, daniel,
exodus or prodigal); story-specific literals became pack constants: ENV (env-var prefix, e.g. "RU_"),
PAGE_MATERIAL (the page material name, e.g. "ru_page").

Names a pack must define (or import) before calling these functions:
  ANCHORS, ARM12, ARM_DEG, ART_H, ART_H_DEFAULT, BLEND, BUILDERS, BVHTree, CHARS, CONTRACT_BONES, Ctx, DEFAULT_EXPR,
  DEFAULT_SHEET, DESIGN_JSON, ENV, EXTRA_BONES, EYE, FACES, FIST, FIST_BEND, FR, GOLD, INSET, MODEL, Matrix, ONLY,
  PAGE_MATERIAL, PALETTE, PART_ANCHORS, PART_TRIS, PIECES, PROPS, PROP_ANCHORS, PROP_UV, REGIONS, REGION_OF,
  REST_BAKE, SHEET, SPEC, Vector, WORK, _LEN, bmesh, finish_uv1_and_jaw, json, math, os, pose_test, random
"""


def scaled(base, k, kx=None, **over):
    """A SPEC entry scaled by k (lengths; kx for widths), then overridden."""
    kx = kx or k
    s = dict(base)
    for key in _LEN:
        s[key] = base[key] * (kx if key in ("hw", "hipX") else k)
    s["neck"] = tuple(v * kx for v in base["neck"])
    s["shoulder"] = (base["shoulder"][0] * kx, base["shoulder"][1] * k)
    s["handDims"] = {a: v * kx for a, v in base["handDims"].items()}
    s["k"] = k; s["kx"] = kx
    s.update(over)
    return s


def landmarks(ch):
    s = SPEC[ch]; H = s["top"] - s["chin"]
    L = dict(top=s["top"], chin=s["chin"], zc=s["zc"], hw=s["hw"])
    for k, f in FR.items():
        L[k] = s["chin"] + s.get("fr", {}).get(k, f) * H
    return L


def face_layout(ch):
    """Decal rectangle (character-local x0 y0 x1 y1) and eye / brow / mouth placement in normalised decal space
    (0..1, y up). Square rect from just under the mouth, side max(1.76 hw, 0.72 H) so brows fit (as Esther)."""
    s = SPEC[ch]; L = landmarks(ch); H = L["top"] - L["chin"]; hw = s["hw"]
    w = max(1.76 * hw, 0.72 * H); x0 = -w / 2; y0 = L["mouth"] - 0.14 * H
    rect = [x0, y0, x0 + w, y0 + w]

    def nx(x): return (x - x0) / w

    def ny(y): return (y - y0) / w
    ex, ew, eh = EYE[ch]
    eyeX = ex * hw
    return dict(rect=rect, eyeL=(nx(eyeX), ny(L["eye"])), eyeR=(nx(-eyeX), ny(L["eye"])),
                eyeHalf=(ew * hw / w, eh * hw / w), brow=ny(L["brow"]), mouth=ny(L["mouth"]), nose=ny(L["nose"]),
                eyeLocal=(eyeX, L["eye"], ew * hw, eh * hw), hwN=hw / w)


def sheet_positions():
    """sheetX / sheetY per character: assets/<id>/design.json characters.<id> when present (Set + sheet role),
    else the defaults (also written to model/characters_layout.json)."""
    out = {ch: list(DEFAULT_SHEET[ch]) for ch in CHARS}
    art_h = ART_H_DEFAULT; src = "defaults"; prop_uv = {}
    if os.path.exists(DESIGN_JSON):
        try:
            d = json.load(open(DESIGN_JSON))
            art_h = d.get("artHeightUnits", art_h)
            for ch in CHARS:
                c = d.get("characters", {}).get(ch, {})
                if "sheetX" in c:
                    out[ch] = [c["sheetX"], c.get("sheetY", out[ch][1])]; src = "design.json"
                if c.get("propUV"):
                    prop_uv[ch] = c["propUV"]
        except Exception as e:                                   # noqa: BLE001
            print("design.json unreadable, using defaults:", e)
    return out, art_h, src, prop_uv


def proof():
    """$<ENV>WORK/uvproof.png: the ID render with every (piece, region) in its demo colour and a thin dark outline,
    i.e. a perfectly coloured sheet; uvcheck renders the models wearing it through UV0."""
    from PIL import Image, ImageFilter
    import numpy as np
    meta = json.load(open(os.path.join(MODEL, "id_characters_2x.json")))
    im = np.array(Image.open(os.path.join(MODEL, "id_characters_2x.png")).convert("RGBA"))
    out = np.zeros(im.shape[:2] + (3,), np.uint8); out[:] = (250, 248, 242)
    key = im[..., 0].astype(int) * 65536 + im[..., 1].astype(int) * 256 + im[..., 2]
    for e in meta["ids"]:
        r, g, b = e["rgb"]; h = e["hex"].lstrip("#")
        m = (key == r * 65536 + g * 256 + b) & (im[..., 3] > 0)
        out[m] = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    edge = Image.fromarray(key.astype(np.int32).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)
    e = np.array(edge) > 0
    e = np.array(Image.fromarray((e * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    out[e] = (60, 45, 35)
    Image.fromarray(out).resize((1000, round(1000 * ART_H_DEFAULT)), Image.LANCZOS).save(os.path.join(WORK, "uvproof.png"))
    print("proof ->", os.path.join(WORK, "uvproof.png"))


def arm_frames(C, side):
    """Shoulder, elbow, wrist, knuckles and the hand frame for one side (rest pose)."""
    s = C.s; sd = 1 if side == "L" else -1
    a = math.radians(ARM_DEG)
    S0 = V(sd * s["shoulder"][0], s["shoulder"][1], 0)
    d = V(sd * math.cos(a), -math.sin(a), 0)
    E = S0 + d * s["upperArm"]; W = E + d * s["forearm"]
    fist = (C.ch, side) in FIST
    if fist:                                    # wrist cocked: hand points out nearly level, holds the sceptre upright
        b = math.radians(FIST_BEND.get((C.ch, side), 26.0))
        dh = V(sd * math.cos(b), -math.sin(b), 0)
        Np = V(0, 0, 1)                         # palm toward the viewer, thumb on top, knuckles back
    else:
        dh = d.copy()
        pin = -V(-dh.y, dh.x, 0) * sd           # palm toward the body / down
        Np = rot_about(pin, dh, math.radians(28))
        if Np.z > 0:
            Np = rot_about(pin, dh, math.radians(-28))
    Lh = s["hand"]; K = W + dh * (Lh * s["palmFrac"])
    Xh = -Np; Yh = dh.cross(Xh).normalized()
    thumb = (dh.cross(Np) if side == "R" else Np.cross(dh)).normalized()
    return dict(S0=S0, d=d, E=E, W=W, K=K, dh=dh, Np=Np, Xh=Xh, Yh=Yh, thumb=thumb, fist=fist, sd=sd)


def skeleton(C):
    s = C.s; L = C.L; H = C.H; S = C.S; B = {}
    nb = s["neckBase"]; headBase = L["chin"] + 0.247 * H
    B["root"] = (V(0, 0, 0), V(0, 0.03 * S, 0), None)
    B["hips"] = (V(0, s["hipY"], 0), V(0, s["waistY"], 0), "root")
    B["spine"] = (V(0, s["waistY"], 0), V(0, s["chestY"], 0), "hips")
    B["chest"] = (V(0, s["chestY"], 0), V(0, nb, 0), "spine")
    B["neck"] = (V(0, nb, 0), V(0, headBase, 0), "chest")
    B["head"] = (V(0, headBase, 0), V(0, L["top"], 0), "neck")
    chinZ = L["zc"] + 0.0195 * s["hw"] / 0.0199
    B["jaw"] = (V(0, L["chin"] + 0.287 * H, L["zc"] - 0.0013 * S), V(0, L["chin"] + 0.03 * H, chinZ), "head")
    for side in "LR":
        A = arm_frames(C, side); sd = A["sd"]
        B["shoulder" + side] = (V(sd * 0.22 * s["shoulder"][0], nb - 0.0027 * S, 0), A["S0"].copy(), "chest")
        B["upperArm" + side] = (A["S0"].copy(), A["E"].copy(), "shoulder" + side)
        B["forearm" + side] = (A["E"].copy(), A["W"].copy(), "upperArm" + side)
        B["hand" + side] = (A["W"].copy(), A["K"].copy(), "forearm" + side)
        B["fingers" + side] = (A["K"].copy(), A["K"] + A["dh"] * (s["hand"] * (1 - s["palmFrac"])), "hand" + side)
        x = sd * s["hipX"]; xk = x * 1.08
        B["thigh" + side] = (V(x, s["hipY"], 0), V(xk, s["kneeY"], 0), "hips")
        B["shin" + side] = (V(xk, s["kneeY"], 0), V(xk, s["ankleY"], -0.001), "thigh" + side)
        B["foot" + side] = (V(xk, s["ankleY"], -0.001), V(xk, 0.004 * S, 0.62 * s["footLen"]), "shin" + side)
        B["toe" + side] = (V(xk, 0.004 * S, 0.62 * s["footLen"]), V(xk, 0.0032 * S, 0.95 * s["footLen"]), "foot" + side)
    ex, ey, ew, eh = C.F["eyeLocal"]
    zf = L["zc"] + 0.020 * s["hw"] / 0.0199
    C.lid = dict(top=ey + 1.30 * eh, h0=0.18 * eh, closed=ey - 1.0 * eh)
    B["eyelids"] = (V(0, C.lid["top"], zf), V(0, C.lid["top"] - 0.010 * S, zf), "head")
    C.B = B
    C.arm = {sd: arm_frames(C, sd) for sd in "LR"}


def neck_rows(C):
    s = C.s; L = C.L; hx, zf, zb = s["neck"]; nb = s["neckBase"]; S = C.S
    return [ellipse_row(L["chin"] - 0.0045 * S, hx, zf, zb), ellipse_row(L["chin"] - 0.0095 * S, hx * 1.02, zf * 1.02, zb * 1.02),
            ellipse_row(nb + 0.0030 * S, hx * 1.12, zf * 1.06, zb * 1.10), ellipse_row(nb - 0.0020 * S, hx * 1.40, zf * 1.12, zb * 1.22),
            ellipse_row(nb - 0.0070 * S, hx * 1.75, zf * 1.18, zb * 1.30)]


def build_head(C, cull, ears=None):
    s = C.s; L = C.L; H = C.H
    rows = mapped_head_rows(L, s["hw"], s["depth"], s["jaw"], s["cheek"], s["chin_narrow"], s["crown"])
    C.head = HeadEval(rows, L)
    rows = rows + neck_rows(C)
    us = front_dense(26, 0.45)
    cg = Cage()
    ytf, ytb = L["chin"] - 0.002, L["chin"] + 0.33 * H

    def wfn(p):
        zf_ = 0.4 * s["hw"]; zb_ = -0.4 * s["hw"]
        ys = lerp(ytb, ytf, smoothstep(zb_, zf_, p.z))
        wh = smoothstep(ys - 0.06 * H, ys + 0.06 * H, p.y)
        wn = weigh(p, [("chest", None), ("neck", None)], C.B, C.blend)
        return mixw(({"head": 1.0}, wh), (wn, 1 - wh))
    rings = [cg.ring(row_ring(r, us), wfn) for r in rows]
    cg.fan(rings[0], V(0, L["top"], L["zc"] - 0.0005 * C.S), wfn, "skin")
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin")
    last = rows[-1]
    cg.fan(rings[-1], V(0, last[0] - 0.004 * C.S, (last[1] + last[5]) / 2), wfn, "skin")
    post = face_post_fn(L, s["hw"], L["zc"], s["noseH"], 1.0, s["brow"], s["lips"], s["chinAmt"], s["nose_w"],
                        s["nose_long"], s["sockets"], s["cheekbones"])
    C.add("face", cg, decal=True, jaw=True, post=post, cull=cull)
    if ears:
        ey0, ey1, ew, et = ears
        for sx in (-1, 1):
            C.add("ear" + ("L" if sx > 0 else "R"),
                  ear_cage(C.head, L, sx, ey0, ey1, ew, et, C.w(["head"]), NA=10))


def head_u(C, p):
    return (math.atan2(p.x, p.z - C.L["zc"]) / (2 * math.pi)) % 1.0


def mirror_u(u):
    uu = u % 1.0
    return uu if uu <= 0.5 else 1.0 - uu


def hair_shell(C, rim, thick, name, reg, plumb=None, tuck_front=0.12, NU=40, NV=9, grooves=56, groove_amp=0.00026,
               parting=False, waves=0.0, curls=None, top_extra=0.0015, pc=0):
    """Hair shell over the skull. rim(u) = lower edge height; thick(u, y) = thickness; plumb(uu) in 0..1 = how much
    the hair below the widest level hangs straight down instead of hugging jaw / neck. The rim of the front part is
    tucked into the skin; elsewhere the edge gets a rolled inner lip (the hair has thickness)."""
    Hd = C.head; L = C.L; H = C.H
    yw = L["eye"]; Hc = V(0, L["eye"], L["zc"])
    cg = Cage(); wfn = C.w(["head"])

    def outer(u, y):
        yy = min(y, L["top"] - 0.0002)
        p = Hd.at(u, yy); n = Hd.normal(u, yy)
        q = p + n * thick(u, y)
        wp = plumb(mirror_u(u)) if plumb else 0.0
        if wp > 0 and y < yw:
            pw = Hd.at(u, yw) + Hd.normal(u, yw) * thick(u, yw)
            hq = V(q.x, 0, q.z - L["zc"]); rq = hq.length
            rw = V(pw.x, 0, pw.z - L["zc"]).length * (1 + 0.06 * (yw - y) / H)
            r = max(rq, lerp(rq, rw, wp))
            if rq > 1e-9:
                q = V(0, y, L["zc"]) + hq / rq * r
                q.y = y
        return q
    C.hair_outer = outer
    us = [k / NU for k in range(NU)]
    rows = []
    for j in range(-1, NV + 1):
        row = []
        for u in us:
            ry = rim(u); uu = mirror_u(u)
            if j == -1:                      # inner lip / tuck
                if uu < tuck_front:
                    p = Hd.at(u, ry + 0.0015) - Hd.normal(u, ry + 0.0015) * 0.0006
                else:
                    o = outer(u, ry); hn = V(o.x, 0, o.z - L["zc"]).normalized()
                    p = o - hn * thick(u, ry) * 0.85 + V(0, 0.0025 * C.S, 0)
                row.append(p); continue
            t = j / NV
            y = lerp(ry, L["top"] + top_extra, t ** 0.85)
            if j == 0 and uu < tuck_front:
                p = Hd.at(u, ry) + Hd.normal(u, ry) * 0.0002
            else:
                p = outer(u, y)
            row.append(p)
        rows.append(cg.ring(row, wfn))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(rows[-1], V(0, L["top"] + top_extra + 0.0004, L["zc"] - 0.001), wfn, reg, pc)

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            u = head_u(C, p); uu = mirror_u(u); ry = rim(u)
            fade = smoothstep(ry - 0.001, ry + 0.003, p.y)
            dirn = (p - Hc).normalized()
            g = groove_amp * math.cos(grooves * 2 * math.pi * u) * fade
            q = p + n * g
            if parting and p.z > L["zc"] and p.y > L["brow"]:
                q -= n * 0.0007 * math.exp(-(p.x / (0.0016 * C.S)) ** 2) * smoothstep(L["brow"] + 0.2 * H, L["brow"] + 0.35 * H, p.y)
            if waves and uu > 0.14:
                q += V(dirn.x, 0, dirn.z).normalized() * waves * math.sin((L["top"] - p.y) / H * 2 * math.pi * 2.3 + uu * 6) \
                    * smoothstep(L["eye"] + 0.1 * H, L["eye"] - 0.2 * H, p.y)
            if curls:
                q += n * curls(u, p.y) * fade
            out.append(q)
        return out
    C.add(name, cg, post=post, subdiv=1)


def build_forearm_hand(C, side, s_from):
    """Visible forearm (from inside the sleeve) + palm + 4 fingers (3 joints, from knuckle ports) + thumb (side port).
    Weights: forearm -> hand at the wrist; fingers by distance from their knuckle (hand -> fingers); thumb = hand."""
    A = C.arm[side]; s = C.s; hd = s["handDims"]
    d, dh, Xh, Yh, Np, W, K, E = A["d"], A["dh"], A["Xh"], A["Yh"], A["Np"], A["W"], A["K"], A["E"]
    Lh = s["hand"]; LHp = Lh * s["palmFrac"]; LF = s["forearm"]; fist = A["fist"]
    thumb_side0 = Yh.dot(A["thumb"]) > 0
    cg = Cage(); k12 = kcomp(12)
    X0 = perp(Xh, d); Y0 = d.cross(X0)
    warm = C.w(["forearm" + side, "hand" + side], blend=0.18 * Lh)
    rings = []
    stations = [s_from + (LF - s_from) * t for t in (0.0, 0.22, 0.45, 0.68, 0.88, 1.0)]
    for sv in stations:
        t = smoothstep(s_from, LF, sv)
        rx = lerp(hd["armR"], hd["wristH"] / 2, t ** 1.4); ry = lerp(hd["armR"] * 1.05, hd["wristW"] / 2, t ** 1.4)
        c = E + d * sv
        rings.append(cg.ring([section(c, X0, Y0, (rx * k12, rx * k12, ry * k12, ry * k12), a, 2.2) for a in ARM12], warm))
    cg.fan(rings[0], E + d * (s_from - 0.3 * hd["armR"]), warm, "skin")
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin")
    Wp, Hp = hd["palmW"], hd["palmH"]
    cols = [0.10, 0.225, 0.225, 0.225, 0.225] if thumb_side0 else [0.225, 0.225, 0.225, 0.225, 0.10]
    ys = [Wp / 2]
    for cw in cols:
        ys.append(ys[-1] - cw * Wp)

    def palm_ring(c, wsc, hsc, dome=0.18):
        pts = []
        for k in range(12):
            i = k if k < 6 else 11 - k
            top = k < 6
            y = ys[i] * wsc
            edge = i in (0, 5)
            xs = Hp / 2 * hsc * (0.62 if edge else 1.0)
            xs *= (1.0 + dome * (1 - (y / (Wp / 2)) ** 2) * 0.5) if top else (1.0 - 0.10 * (1 - (y / (Wp / 2)) ** 2))
            pts.append(c + Xh * (xs if top else -xs) + Yh * y * (0.92 if edge else 1.0))
        return pts
    wpalm = C.w(["forearm" + side, "hand" + side], blend=0.20 * Lh)
    pr = [cg.ring(palm_ring(W + dh * (0.04 * LHp), 0.78, 1.15, 0.05), wpalm)]
    pr.append(cg.ring(palm_ring(W + dh * (0.32 * LHp), 0.96, 1.08), wpalm))
    pr.append(cg.ring(palm_ring(W + dh * (0.68 * LHp), 1.0, 1.0), wpalm))
    pr.append(cg.ring(palm_ring(W + dh * (0.98 * LHp), 0.98, 0.92, 0.30), wpalm))
    cg.bridge(rings[-1], pr[0], "skin", 0)
    cg.bridge(pr[0], pr[1], "skin", 0)
    tj = 11 if thumb_side0 else 5
    cg.bridge(pr[1], pr[2], "skin", 0, skip=(tj,))
    cg.bridge(pr[2], pr[3], "skin", 0)
    tport = [pr[1][tj], pr[1][(tj + 1) % 12], pr[2][(tj + 1) % 12], pr[2][tj]]
    ring = pr[3]
    finger_cols = [1, 2, 3, 4] if thumb_side0 else [3, 2, 1, 0]
    lens = [0.94, 1.0, 0.94, 0.76]
    flen = Lh * (1 - s["palmFrac"])
    fw, ft = hd["fingerW"], hd["fingerT"]
    curl = [math.radians(a) for a in ((84, 96, 64) if fist else (14, 22, 12))]
    spreads = [-0.05, -0.015, 0.02, 0.07]
    C.fingers = getattr(C, "fingers", {}); C.fingers[side] = []
    thumb_off = Yh if thumb_side0 else -Yh
    for c in range(5):
        q = [ring[c], ring[c + 1], ring[11 - (c + 1)], ring[11 - c]]
        if c not in finger_cols:
            cg.face(q, "skin", 0); continue
        fi = finger_cols.index(c); lf = lens[fi] * flen
        base = sum((cg.v[i] for i in q), V()) / 4
        dirn = (dh - thumb_off * (spreads[fi] * (0.0 if fist else 1.0))).normalized()
        pal = perp(Np, dirn)
        pts = [base, base + dirn * (0.10 * lf)]
        p = pts[-1]; segs = (0.44, 0.31, 0.25)
        joints = []
        for k, (sl, ang) in enumerate(zip(segs, curl)):
            dirn, pal = (dirn * math.cos(ang) + pal * math.sin(ang)).normalized(), (pal * math.cos(ang) - dirn * math.sin(ang)).normalized()
            n0 = p; p = p + dirn * (sl * lf * (0.90 if k == 0 else 1.0))
            joints.append((n0, p, dirn.copy()))
            pts.append(p)
        C.fingers[side].append(dict(path=[x.copy() for x in pts], joints=joints))
        st = []
        # stations: knuckle, proximal mid, PIP, middle mid, DIP, distal mid, near tip
        prof = [(0.06, 1.04), (0.30, 1.00), (0.47, 1.03), (0.62, 0.95), (0.76, 0.97), (0.88, 0.88), (0.97, 0.78)]
        for t, sc in prof:
            pt = cr_open(pts, t)
            st.append((pt, (ft / 2 * sc * 1.25, ft / 2 * sc * 1.25, fw / 2 * sc * 1.18, fw / 2 * sc * 1.18)))
        b0 = base.copy()

        def wf(pp, b0=b0, lf=lf):
            t = smoothstep(0.10 * lf, 0.34 * lf, (pp - b0).length)
            return {"hand" + side: 1 - t, "fingers" + side: t} if t < 0.999 else {"fingers" + side: 1.0}
        extrude_port(cg, q, st, Xh, wf, "skin", 0, cap=True, mode="square", cap_len=0.9)
    # thumb
    whand = C.w(["hand" + side])
    tc = sum((cg.v[i] for i in tport), V()) / 4
    tl = flen * 0.95
    if fist:
        p1 = tc + thumb_off * (0.25 * hd["thumbW"]) + dh * (0.05 * LHp)
        d1 = (dh * 0.55 + thumb_off * 0.35 + Np * 0.55).normalized()
        p2 = p1 + d1 * (0.40 * tl)
        d2 = (dh * 0.55 - thumb_off * 0.55 + Np * 0.35).normalized()
        p3 = p2 + d2 * (0.36 * tl); p4 = p3 + (d2 - thumb_off * 0.3).normalized() * (0.26 * tl)
    else:
        tl = flen * 0.86
        p1 = tc + thumb_off * (0.25 * hd["thumbW"]) + dh * (0.10 * LHp) + Np * (0.15 * hd["thumbW"])
        d1 = (dh * 0.60 + thumb_off * 0.38 + Np * 0.55).normalized()
        p2 = p1 + d1 * (0.42 * tl)
        d2 = (dh * 0.75 + thumb_off * 0.02 + Np * 0.45).normalized()
        p3 = p2 + d2 * (0.33 * tl); p4 = p3 + (d2 + Np * 0.15).normalized() * (0.25 * tl)
    path = [tc, p1, p2, p3, p4]
    st = []
    for t, sc in ((0.14, 1.10), (0.32, 1.02), (0.50, 0.98), (0.66, 0.92), (0.82, 0.88), (0.95, 0.76)):
        st.append((cr_open(path, t), (hd["thumbT"] / 2 * sc * 1.25, hd["thumbT"] / 2 * sc * 1.25,
                                      hd["thumbW"] / 2 * sc * 1.2, hd["thumbW"] / 2 * sc * 1.2)))
    extrude_port(cg, tport, st, Xh, whand, "skin", 0, cap=True, mode="square", cap_len=0.9)
    C.add("hand" + side, cg, subdiv=1)


def skirt_weights(C):
    s = C.s; hipY, kneeY = s["hipY"], s["kneeY"]; hipX = s["hipX"]; hem = C.robe_rows[-1][0]
    wt0 = C.w(["hips", "spine", "chest", ("neck", 0.008 * C.S), ("shoulderL", 0.012 * C.S), ("shoulderR", 0.012 * C.S)])

    wlow = C.w(["hips", "spine"])

    def wfn(p):
        # below the waist only hips / spine (Esther's version let the far-away shoulder bones win the normalisation
        # there, ~0.2 shoulder weight at knee height; harmless at rest, but a shrug or a baked pose dents the skirt)
        w = wt0(p) if p.y >= s["waistY"] else wlow(p)
        if p.y >= hipY:
            return w
        tt = min(1.0, (hipY - p.y) / (hipY - hem))
        kk = 0.82 * smoothstep(0.0, 0.45, tt)
        sL = min(1.0, max(0.0, 0.5 + p.x / (3.2 * hipX)))
        sh = 0.65 * smoothstep(kneeY + 0.012 * C.S, kneeY - 0.035 * C.S, p.y)
        w = {b: v * (1 - kk) for b, v in w.items()}
        for side, f in (("L", sL), ("R", 1 - sL)):
            w["thigh" + side] = w.get("thigh" + side, 0) + kk * f * (1 - sh)
            w["shin" + side] = w.get("shin" + side, 0) + kk * f * sh
        return w
    return wfn


def robe_point(C, y, a, off=0.0):
    return shell_point(C.robe_rows, y, a, off, e=2.5)


def build_robe(C, rows, sleeve_rad, sleeve_end, nf=14, fold_amp=0.0016, sleeve_fold=0.0009, bell_sag=0.0,
               regfn=None, sleeve_lip=(0.86, 0.0004, 0.0040), step=0.0052, N=44, reg="robe", name="robe",
               solidify=0.0, keep=False):
    s = C.s; S = C.S; shY = s["shoulder"][1]
    port = (shY - 0.020 * S, shY + 0.0015 * S)
    hem = rows[-1][0]
    ys = sorted({r[0] for r in rows if r[0] > port[0] + 1e-6} | {port[0], port[1]}, reverse=True)
    n = max(4, int(round((port[0] - hem) / (step * S))))
    ys += [port[0] - (port[0] - hem) * i / n for i in range(1, n + 1)]
    ys = sorted(set(round(y, 6) for y in ys if hem - 1e-9 <= y <= rows[0][0] + 1e-9), reverse=True)
    TT = resample_rows(rows, ys)
    C.robe_rows = TT
    C.sleeve_profile = [(sv * S, r * S) for sv, r in sleeve_rad]
    wtorso = skirt_weights(C)
    sleeves = {}
    for side in "LR":
        A = C.arm[side]; S0, d = A["S0"], A["d"]
        wsl = C.w(["chest", "shoulder" + side, "upperArm" + side, "forearm" + side])
        st = [(S0 + d * (sv * S), (r * S, r * S, r * S * 0.97, r * S * 0.97)) for sv, r in sleeve_rad]
        sleeves[side] = (st, wsl, sleeve_lip)
    cg = torso_shell(C, TT, N, port, math.radians(30), sleeves, wtorso, reg, e=2.5,
                     lip_top=(0.90, -0.0004 * S, 0.0030 * S), lip_bot=(0.95, 0.0002 * S, 0.0045 * S), direct=True,
                     regfn=regfn)
    if regfn:     # torso_shell applies regfn to the body only; sleeves keep "robe" unless the caller re-tags them
        pass
    LU, LF = s["upperArm"], s["forearm"]

    def fold(a):
        return math.cos(nf * a + 0.7) + 0.35 * math.cos((nf // 2 + 1) * a + 2.1) + 0.2 * math.cos((nf + 3) * a + 0.3)

    def post(pts, nrm):
        out = []
        for p in pts:
            q = p.copy()
            sl = None
            for side in "LR":
                A = C.arm[side]; sv = (p - A["S0"]).dot(A["d"])
                if sv > 0.004 * S:
                    rv = p - (A["S0"] + A["d"] * sv)
                    if rv.length < 0.030 * S:
                        sl = (A, sv, rv)
            if sl:
                A, sv, rv = sl
                A0 = perp(V(0, 0, 1), A["d"]); B0 = A["d"].cross(A0)
                ang = math.atan2(rv.dot(B0), rv.dot(A0))
                t = smoothstep(0.55 * LU * S, (LU + LF) * S, sv)
                q += rv.normalized() * sleeve_fold * t * math.cos(6 * ang + 0.4)
                if bell_sag:
                    q.y -= bell_sag * t * t * max(0.0, -rv.normalized().y + 0.3)
            elif p.y < s["waistY"]:
                a = math.atan2(p.x, p.z + 0.001)
                hn = V(p.x, 0, p.z + 0.001)
                hn = hn.normalized() if hn.length > 1e-9 else V(0, 0, 1)
                amp = fold_amp * S * smoothstep(s["waistY"] - 0.004 * S, hem + 0.02 * S, p.y) ** 0.8
                q += hn * amp * fold(a)
                if p.y < hem + 0.0070 * S:
                    q.y += 0.0011 * S * fold(a) * smoothstep(hem + 0.0070 * S, hem + 0.001 * S, p.y)
            out.append(q)
        return out
    def zone(p):
        for side in "LR":
            A = C.arm[side]
            if (p - A["S0"]).length < 0.020 * S and p.y > A["S0"].y - 0.010 * S:
                return True
        return False
    C.add(name, cg, post=post, subdiv=0, smooth=(zone, 8), solidify=solidify * S if solidify else 0.0)
    return cg


def waist_band(C, name, reg, y0, y1, off, pc=0, N=48, bulge=0.0010):
    cg = Cage(); wb = C.w(["hips", "spine"])
    angs = [2 * math.pi * j / N for j in range(N)]
    rings = []
    for y, o in ((y0, off), (y0 + 0.0005, off + bulge * 0.8), (lerp(y0, y1, 0.5), off + bulge), (y1 - 0.0005, off + bulge * 0.8), (y1, off)):
        rings.append(cg.ring([robe_point(C, y, a, o) for a in angs], wb))
    for a, b in zip(rings, rings[1:] + rings[:1]):
        cg.bridge(a, b, reg, pc)
    C.add(name, cg, subdiv=0)


def mantle_point(C, u, y, off, r_sleeve=None, plumb_y=None, plumb_extra=0.0):
    """Point on a garment draped over the robe: robe surface + off, hanging plumb below plumb_y at the back, pushed
    out of the sleeve tubes (push_out_of_sleeves). r_sleeve is unused (kept for call-site readability)."""
    a = 2 * math.pi * u
    hw, zf, zb = table(C.robe_rows, y)
    if plumb_y is not None and y < plumb_y:
        zb_bl = table(C.robe_rows, plumb_y)[2]
        zb = min(zb, zb_bl - plumb_extra * (plumb_y - y) / (0.03 * C.S))
    zc = (zf + zb) / 2; rd = (zf - zb) / 2
    p = V(se(math.sin(a), 2.5) * (hw + off), y, zc + se(math.cos(a), 2.5) * (rd + off))
    return push_out_of_sleeves(C, p, off)


def push_out_of_sleeves(C, p, off):
    """Move a point that lies inside a sleeve tube out to the sleeve surface + off (radially from the arm axis)."""
    for side in "LR":
        A = C.arm[side]
        sv = (p - A["S0"]).dot(A["d"])
        if sv < -0.004 * C.S:
            continue
        svc = max(0.0, sv)
        R = table(C.sleeve_profile, svc)[0] if svc <= C.sleeve_profile[-1][0] else 0.0
        if R <= 0:
            continue
        ax = A["S0"] + A["d"] * sv
        rv = p - ax
        need = R + off
        if sv < 0:                                  # behind the shoulder joint: fade the push out
            need *= smoothstep(-0.004 * C.S, 0.0, sv)
        if rv.length < need and rv.length > 1e-9:
            p = ax + rv.normalized() * need
    return p


def smax(a, b, k):
    return (a + b + math.sqrt((a - b) ** 2 + k * k)) / 2


def hor(v):
    return V(v.x, 0, v.z)


def scale_rows(rows, k, kx, dx=0.0, dz=0.0):
    """Garment rows (y, hw, zf, zb) scaled (y by k, widths by kx), optionally grown by dx / dz (front and back)."""
    return [(y * k, hw * kx + dx, zf * kx + dz, zb * kx - dz) for y, hw, zf, zb in rows]


def hood(C, name, reg, rim, thick, wfn, NU=52, NV=22, flare=0.10, body_off=0.0020, back_settle=0.75,
         front_pull=0.0, folds=(11, 0.0020), hem_wave=0.0010, solid=0.0009, pc=0, pw=0.80, loose_top=0.0,
         settle=0.85):
    """A draped head-cloth (scarf, shawl, keffiyeh): closed rings from the free edge rim(u) up to the crown.
    Above eye level it lies on the hair / skull (+ thick); below it hangs plumb from the widest part of the head
    (flaring a little), settles on the robe's shoulders (+ body_off), lies down onto the back below the shoulder line
    (back_settle) and is pushed out of the sleeves; front columns can be pulled toward the chest centre (front_pull).
    Folds deepen below the chin; the hem waves."""
    Hd = C.head; L = C.L; H = C.H; S = C.S; s = C.s
    yw = L["eye"]; shY = s["shoulder"][1]; nb = s["neckBase"]
    top_robe = C.robe_rows[0][0]; hem_robe = C.robe_rows[-1][0]
    outer = getattr(C, "hair_outer", None)

    def headp(u, y):
        yy = min(y, L["top"] - 0.0002)
        q = outer(u, yy) if outer else Hd.at(u, yy)
        n = Hd.normal(u, max(min(yy, L["top"] - 0.001), L["chin"]))
        return q + n * thick(u, y)

    def fold(a):
        n_, _ = folds
        return math.cos(n_ * a + 0.7) + 0.40 * math.cos((n_ // 2 + 1) * a + 2.1) + 0.25 * math.cos((n_ + 4) * a + 0.3)

    def pt(u, y, edge=False):
        a = 2 * math.pi * u; uu = mirror_u(u)
        c = V(0, y, L["zc"])
        if y >= yw:
            return_head = headp(u, y)
            p = return_head
        else:
            pw_ = headp(u, yw); rw = hor(pw_ - V(0, yw, L["zc"])).length * (1 + flare * (yw - y) / H)
            ph = headp(u, max(y, L["chin"] - 0.05 * H)); hq = hor(ph - V(0, ph.y, L["zc"]))
            r = smax(hq.length, rw, 0.0015 * S)
            ang = math.atan2(hq.x, hq.z) if hq.length > 1e-9 else a
            fp = front_pull * smoothstep(shY + 0.004 * S, s["chestY"] - 0.004 * S, y) * smoothstep(0.30, 0.16, uu)
            ang *= (1 - fp)
            dirn = V(math.sin(ang), 0, math.cos(ang))
            if hem_robe <= y <= top_robe + 0.004 * S:
                q = shell_point(C.robe_rows, min(y, top_robe), ang, body_off * S)
                rb = hor(q - c).length
                st = settle * smoothstep(nb + 0.002 * S, shY - 0.002 * S, y) * smoothstep(0.40, 0.30, uu)
                st = max(st, back_settle * smoothstep(shY, shY - 0.030 * S, y) * smoothstep(0.30, 0.40, uu))
                r = smax(lerp(r, rb, st), rb, 0.0012 * S)
            p = c + dirn * r
        p = push_out_of_sleeves(C, p, body_off * S)
        # folds below the chin, a wave along the hem
        fa = folds[1] * S * smoothstep(L["chin"] + 0.02 * H, L["chin"] - 0.06 * S, y)
        if fa:
            p += hor(p - c).normalized() * fa * fold(a) * (0.5 + 0.5 * smoothstep(0.12, 0.30, uu))
        if edge:
            p.y += hem_wave * S * fold(a + 0.4)
        return p
    us = [k / NU for k in range(NU)]
    cg = Cage()
    ytop = L["top"]
    rows = []
    for j in range(NV):
        t = j / NV
        row = []
        for u in us:
            y = lerp(rim(u), ytop, t ** pw)
            row.append(pt(u, y, edge=(j == 0)))
        rows.append(cg.ring(row, wfn))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, reg, pc)
    topp = headp(0.5, ytop) + V(0, loose_top * S, 0)
    cg.fan(rows[-1], topp, wfn, reg, pc)
    C.hood_pt = pt
    C.add(name, cg, subdiv=0, solidify=solid * S)
    return cg


def hood_weights(C, chain, arm_reach=0.010):
    """Head above the chin, neck / chest / shoulders below, the back drape on the chain bones."""
    s = C.s; S = C.S; L = C.L; H = C.H; nb = s["neckBase"]; shY = s["shoulder"][1]
    wl = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S),
              ("upperArmL", arm_reach * S), ("upperArmR", arm_reach * S)])
    wc = C.w(chain, blend=0.012 * S)

    def f(p):
        wh = smoothstep(nb - 0.002 * S, L["chin"] - 0.02 * H, p.y)
        a = math.atan2(p.x, p.z + 0.001)
        tb = smoothstep(shY + 0.006 * S, shY - 0.012 * S, p.y) * smoothstep(-0.25, -0.65, math.cos(a))
        lo = mixw((wl(p), 1 - tb), (wc(p), tb)) if tb > 0 else wl(p)
        return mixw(({"head": 1.0}, wh), (lo, 1 - wh)) if wh < 1 else {"head": 1.0}
    return f


def drop_faces(cg, pred):
    keep = [i for i, q in enumerate(cg.f) if not pred(sum((cg.v[k] for k in q), V()) / len(q))]
    cg.f = [cg.f[i] for i in keep]; cg.reg = [cg.reg[i] for i in keep]; cg.pc = [cg.pc[i] for i in keep]


def sandal_regfn(S):
    """Sole + toe strap + instep strap + ankle strap; skin between (y, z relative to the ankle)."""
    def f(yy, dz):
        if yy < 0.0030 * S:
            return "sandals"
        if yy < 0.0105 * S and abs(dz - 0.0195 * S) < 0.0018 * S:
            return "sandals"
        if yy < 0.0150 * S and abs(dz - 0.0085 * S) < 0.0024 * S:
            return "sandals"
        if abs(yy - 0.0168 * S) < 0.0016 * S:
            return "sandals"
        return "skin"
    return f


def belt_tie(C, name, reg, kx, y0, tails, wd, pc=1, rows=None):
    """Knot on the belt at x = kx and hanging tails [(dx, y_end)] ending in small tassels."""
    S = C.S; wb = C.w(["hips", "spine", ("thighL", 0.02 * S), ("thighR", 0.02 * S)], blend=0.02 * S)
    cg = Cage()
    rr = rows or C.robe_rows
    ka = math.asin(min(1.0, kx / table(rr, y0)[0]))
    kc = shell_point(rr, y0, ka, 0.0034 * S)
    lathe_y(cg, kc, [(-0.0024 * S, 0.0016 * S), (0.0, 0.0030 * S), (0.0024 * S, 0.0016 * S)], 8, wb, reg, pc, e=2.6, zscale=0.6)
    for dx, y_end in tails:
        pp, nn = [], []
        for t in [i / 7 for i in range(8)]:
            y = lerp(y0 - 0.0018 * S, y_end, t)
            x = kx + dx * S + 0.0024 * S * t * (1 if dx > 0 else -0.5)
            a = math.asin(max(-1, min(1, x / (table(rr, y)[0] + 0.002))))
            p = shell_point(rr, y, a, (0.0028 + 0.0012 * math.sin(t * math.pi)) * S)
            pp.append(p); nn.append(V(p.x, 0, p.z).normalized())
        strip(cg, pp, nn, [wd * S * (1.0 - 0.15 * t) for t in [i / 7 for i in range(8)]], 0.0006 * S, wb, reg, pc)
        blob(cg, pp[-1] + V(0, -0.0016 * S, 0.0004 * S), 0.0016 * S, 0.0024 * S, 0.0012 * S, wb, reg, pc, NU=6, NV=4)
    C.add(name, cg, subdiv=0)


def grip_point(C, side, inset=0.0034):
    A = C.arm[side]; s = C.s; hd = s["handDims"]
    return A["K"] - A["dh"] * (0.18 * s["hand"] * s["palmFrac"]) + A["Np"] * (hd["palmH"] * 0.5 + inset * C.S)


def barley_ear(cg, base, d, ln, r, wfn, reg, pc=0, awns=True):
    """One bearded barley ear: a slim spindle along d (lumpy kernels) and two thin awn tufts."""
    d = d.normalized(); A_ = perp(V(0, 0, 1), d)
    if A_.length < 1e-6:
        A_ = perp(V(1, 0, 0), d)
    Bv = d.cross(A_)
    M = Matrix((A_, d, Bv)).transposed()
    blob(cg, base + d * (ln / 2), r, ln / 2, r * 0.85, wfn, reg, pc, NU=6, NV=5, ax=M)
    if awns:
        tip = base + d * ln
        for sg in (-1, 1):
            q = tip + (d * 0.9 + A_ * 0.35 * sg).normalized() * (ln * 0.55)
            tube(cg, [tip - d * (ln * 0.15), tip, q], [r * 0.25, r * 0.18, r * 0.05], 3, wfn, reg, pc, cap0=False, cap1=False)


def stalk_bunch(cg, centre, axis, n, length, spread, r_stalk, ear_len, ear_r, wfn, reg, pc=0, seed=1, below=0.35,
                droop=0.25):
    """A handful of barley stalks crossing at `centre` (the grip), ears up along axis, cut ends below."""
    rnd = random.Random(seed)
    axis = axis.normalized(); A_ = perp(V(0, 0, 1), axis); Bv = axis.cross(A_)
    for i in range(n):
        ang = 2 * math.pi * i / n + rnd.uniform(-0.3, 0.3)
        sp = spread * (0.5 + 0.5 * rnd.random())
        dirn = (axis + (A_ * math.cos(ang) + Bv * math.sin(ang)) * sp).normalized()
        ln = length * rnd.uniform(0.85, 1.1)
        p0 = centre - dirn * (ln * below) + (A_ * math.cos(ang) + Bv * math.sin(ang)) * (r_stalk * 1.5)
        p1 = centre + (A_ * math.cos(ang) + Bv * math.sin(ang)) * (r_stalk * 1.2)
        tip_d = (dirn + (A_ * math.cos(ang) + Bv * math.sin(ang)) * droop - axis * droop * 0.4).normalized()
        p2 = p1 + dirn * (ln * (1 - below) * 0.55)
        p3 = p2 + tip_d * (ln * (1 - below) * 0.45)
        tube(cg, [p0, p1, p2, p3], [r_stalk] * 4, 4, wfn, reg, pc, cap0=True, cap1=False)
        barley_ear(cg, p3, (p3 - p2), ear_len * rnd.uniform(0.9, 1.1), ear_r, wfn, reg, pc)


def esther_like_rim(C, front=0.38, scale=1.0):
    L = C.L; H = C.H

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, L["brow"] + front * H), (0.05, L["brow"] + (front - 0.03) * H), (0.09, L["brow"] + 0.24 * H),
                      (0.13, L["brow"] + 0.05 * H), (0.165, L["eye"] - 0.06 * H), (0.20, L["nose"] - 0.04 * H),
                      (0.24, L["mouth"] - 0.10 * H), (0.30, L["chin"] - 0.04 * H), (0.40, L["chin"] - 0.08 * H),
                      (0.50, L["chin"] - 0.10 * H)], uu)[0]
    return rim


def hair_cull(C, rim):
    s = C.s; S = C.S; nb = s["neckBase"]

    def cull(p):
        u = head_u(C, p); ry = rim(u)
        if p.y < nb - 0.0060 * S:
            return True
        return (p.y > ry + 0.0045 * S and p.z < 0.70 * s["hw"]) or p.y > ry + 0.0080 * S
    return cull


def region_id(ch, reg):
    key = f"{ch}.{reg}"
    if key not in REGIONS: REGIONS.append(key)
    return REGIONS.index(key) + 1


def piece_id(key):
    if key not in PIECES: PIECES.append(key)
    return PIECES.index(key) + 1


def eyelid_cage(C, face_obj, sheet):
    """Two thin skin lids parked above the eyes (rest = open); scaling the `eyelids` bone along its length (local Y,
    pointing down) by ~closedScale closes them over the eyes."""
    me = face_obj.data
    vs = [to_design(face_obj.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    bvh = BVHTree.FromPolygons([tuple(v) for v in vs], [tuple(p.vertices) for p in me.polygons])
    ex, ey, ew, eh = C.F["eyeLocal"]
    top, h0 = C.lid["top"], C.lid["h0"]
    cg = Cage()
    for sx in (-1, 1):
        cols = []
        for i in range(8):
            x = sx * ex + (i / 7 - 0.5) * 2 * 1.32 * ew
            col = []
            for j in range(4):
                y = top - h0 * j / 3
                hit = bvh.ray_cast(V(x, y, 0.2), V(0, 0, -1), 1.0)
                z = (hit[0].z if hit[0] else C.L["zc"] + 0.015) + 0.00055 * C.S
                col.append(V(x, y, z))
            cols.append(col)
        idx = [[cg.add(p, None) for p in col] for col in cols]
        for i in range(7):
            for j in range(3):
                cg.face((idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1]), "skin", 0)
    C.lid["closedScale"] = round((C.lid["top"] - C.lid["closed"]) / C.lid["h0"], 2)
    return cg


def make_part_object(C, ch, pt, sheet, rig):
    cg = pt["cage"]
    o = new_mesh_obj(f"{ch}_{pt['name']}", [to_bl(v) for v in cg.v], cg.f)
    pkey = pt.get("piece_as")
    pids = [piece_id((ch, pkey or pt["name"], k if not pkey else 0)) for k in cg.pc]
    rids = [region_id(ch, r) for r in cg.reg]
    a1 = o.data.attributes.new("st_piece", 'INT', 'FACE'); a1.data.foreach_set("value", pids)
    a2 = o.data.attributes.new("st_region", 'INT', 'FACE'); a2.data.foreach_set("value", rids)
    rigid = pt.get("rigid")
    if not rigid:
        groups = {}
        for i, w in enumerate(cg.w):
            for b, v in w.items():
                if v > 1e-4: groups.setdefault(b, []).append((i, v))
        for b, lst in groups.items():
            g = o.vertex_groups.get(b) or o.vertex_groups.new(name=b)
            for i, v in lst: g.add([i], v, 'REPLACE')
    fix_normals(o)
    if pt.get("subdiv", 1):
        apply_subsurf(o, pt.get("subdiv", 1))
    fix_normals(o)
    if pt.get("post"):
        me = o.data
        pts = [to_design(v.co) for v in me.vertices]; nrm = [to_design(v.normal) for v in me.vertices]
        for v, p in zip(me.vertices, pt["post"](pts, nrm)):
            v.co = to_bl(p)
        me.update()
    if pt.get("smooth"):
        zone, iters = pt["smooth"]
        bm = bmesh.new(); bm.from_mesh(o.data)
        vs = [v for v in bm.verts if zone(to_design(v.co))]
        for _ in range(iters):
            bmesh.ops.smooth_vert(bm, verts=vs, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.to_mesh(o.data); bm.free(); o.data.update()
    if pt.get("cull"):
        bm = bmesh.new(); bm.from_mesh(o.data)
        hid = {v.index: pt["cull"](to_design(v.co)) for v in bm.verts}
        dead = [f for f in bm.faces if all(hid[v.index] for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bm.to_mesh(o.data); bm.free(); o.data.update()
    if pt.get("solidify"):
        apply_solidify(o, pt["solidify"])
    if pt.get("sharp"):
        o.data.set_sharp_from_angle(angle=math.radians(pt["sharp"]))
    o.parent = rig
    if rigid:
        o.parent_type = 'BONE'; o.parent_bone = rigid
    o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    o.matrix_world = Matrix.Translation((sheet[0], 0, sheet[1]))
    bpy.context.view_layer.update()
    PART_TRIS[o.name] = tri_count([o])
    return o


def bake_rest_pose(C, rig, body, poses):
    """Pose bones (design axis, degrees), apply that pose to the skinned body and make it the new rest pose of the rig
    (rigid props parented to bones keep their posed place). Used for Naomi's stoop."""
    props = [o for o in rig.children if o.parent_type == 'BONE']
    for bone, axis, deg in poses:
        bend(rig, bone, axis, deg)
    bpy.context.view_layer.update()
    keep = {o.name: o.matrix_world.copy() for o in props}
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = body; body.select_set(True)
    bpy.ops.object.modifier_apply(modifier="Armature")
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = rig; rig.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    moved = 0.0
    for o in props:
        moved = max(moved, (o.matrix_world.translation - keep[o.name].translation).length)
        o.matrix_world = keep[o.name]
    bpy.context.view_layer.update()
    am = body.modifiers.new("Armature", 'ARMATURE'); am.object = rig
    return moved


def is_hidden_prop(o):
    ch, _, part = o.name.partition("_")
    return PROPS.get(ch, {}).get(part) is False


def build_character(ch):
    C = Ctx(ch)
    BUILDERS[ch](C)
    order = CONTRACT_BONES + EXTRA_BONES[ch]
    assert set(order) == set(C.B.keys()), (ch, set(order) ^ set(C.B.keys()))
    sheet = SHEET[ch]
    rig = make_armature(f"{ch}_rig", C.B, order)
    rig.location = (sheet[0], 0, sheet[1]); bpy.context.view_layer.update()
    objs = []
    face_obj = None
    for pt in C.parts:
        o = make_part_object(C, ch, pt, sheet, rig)
        objs.append((o, pt))
        if pt["name"] == "face":
            face_obj = o
    lid = dict(name="eyelids", cage=eyelid_cage(C, face_obj, sheet), rigid="eyelids", subdiv=0, piece_as="face")
    objs.append((make_part_object(C, ch, lid, sheet, rig), lid))
    for o, pt in objs:
        finish_uv1_and_jaw(C, ch, o, pt, sheet)
    body = [o for o, pt in objs if not pt.get("rigid")]
    props = [o for o, pt in objs if pt.get("rigid")]
    bpy.ops.object.select_all(action='DESELECT')
    for o in body: o.select_set(True)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.object.join()
    bodyo = bpy.context.view_layer.objects.active; bodyo.name = f"{ch}_body"; bodyo.data.name = f"{ch}_body"
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    am = bodyo.modifiers.new("Armature", 'ARMATURE'); am.object = rig
    baked = None
    if ch in REST_BAKE and not os.environ.get(ENV + "NOBAKE"):
        baked = bake_rest_pose(C, rig, bodyo, REST_BAKE[ch])
    vis = [bodyo] + [o for o in props if not is_hidden_prop(o)]
    stats = front_uv_with_occlusion([(o, o is not bodyo) for o in vis], sheet, ART_H, INSET,
                                    anchors=None, region_name=lambda r: REGIONS[r - 1].split(".")[1])
    if baked is not None:
        stats["restBakePropDrift"] = round(baked, 6)
    # regions / bbox report from the (final) rest pose; hidden props and eyelids do not count for the bbox
    rep = {"regions": {}, "parts": {}, "uvStats": stats}
    for o in [bodyo] + props:
        me = o.data; rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
        pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
        for poly, r, pp in zip(me.polygons, rid, pid):
            reg = REGIONS[r - 1].split(".")[1]
            d = rep["regions"].setdefault(reg, {"parts": set(), "bb": [9, 9, -9, -9]})
            pname = PIECES[pp - 1][1]
            d["parts"].add(pname)
            if o.name.endswith("_eyelids") or is_hidden_prop(o):
                continue
            for vi in poly.vertices:
                p = to_design(o.matrix_world @ me.vertices[vi].co)
                bb = d["bb"]; bb[0] = min(bb[0], p.x); bb[1] = min(bb[1], p.y); bb[2] = max(bb[2], p.x); bb[3] = max(bb[3], p.y)
    return C, rig, bodyo, props, rep


def ears_spec(C):
    L = C.L; H = C.H; k = H / 0.0535
    return (L["chin"] + 0.31 * H, L["chin"] + 0.55 * H, 0.0078 * k, 0.0027 * k)


def head_surface(C, x, y, off=0.0):
    """Point on the target head surface in front at (x, y) (search over u), pushed out along the normal."""
    best = None
    for k in range(-60, 61):
        u = (k / 240.0) % 1.0
        p = C.head.at(u, y)
        dd = abs(p.x - x)
        if best is None or dd < best[0]:
            best = (dd, u, p)
    _, u, p = best
    return p + C.head.normal(u, y) * off, C.head.normal(u, y)


def build_beard(C, top_tab, bot_tab, thick_fn, curls_fn, umax, bottom_y, name="beard", reg="beard", NU=21, NV=11,
                solid=0.0045):
    Hd = C.head; L = C.L; zc = L["zc"]; chin = L["chin"]
    cg = Cage(); wfn = C.w(["head"])

    def base(u, y):
        if y >= chin + 0.004 * C.S:
            return Hd.at(u, y), Hd.normal(u, y)
        y0 = chin + 0.004 * C.S
        pc = Hd.at(u, y0); n = Hd.normal(u, y0)
        t = (y0 - y) / max(1e-6, (y0 - bottom_y))
        p = V(pc.x * (1 - 0.50 * t), y, zc + (pc.z - zc) * (1 - 0.20 * t * t) - 0.002 * C.S * t)
        return p, (n + V(0, -0.7 * t, 0.2 * t)).normalized()
    us = [-umax + 2 * umax * i / (NU - 1) for i in range(NU)]
    rows = []
    for j in range(NV + 1):
        v = j / NV; row = []
        for u in us:
            uu = abs(u)
            yt = table(top_tab, uu)[0]; yb = table(bot_tab, uu)[0]
            y = lerp(yt, yb, v)
            p, n = base(u % 1.0, y)
            row.append(p + n * thick_fn(uu, y, v) - n * 0.0008 * C.S * (1 - smoothstep(0.0, 0.12, v)))
        rows.append(cg.ring(row, wfn))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, reg, 0, closed=False)

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            u = math.atan2(p.x, p.z - zc) / (2 * math.pi)
            out.append(p + n * curls_fn(u, p.y))
        return out
    C.add(name, cg, post=post, solidify=solid * C.S, decal=True, jaw=True, subdiv=0, jawBelow=0.6, jawZ=-0.03)


def moustache(C, name, y0, half_w, droop, curl, r0, reg="beard", off=0.0016):
    L = C.L; S = C.S
    cg = Cage(); wfn = C.w(["head"])
    for sx in (-1, 1):
        path, rad = [], []
        for i in range(9):
            f = i / 8
            x = sx * (0.02 + 0.98 * f) * half_w
            y = y0 - droop * f ** 1.6 + curl * smoothstep(0.65, 1.0, f) ** 2
            p, n = head_surface(C, x, y, off * S + r0 * (1 - 0.6 * f))
            if f > 0.7:
                p += V(sx * 0.0008 * S * (f - 0.7) / 0.3, 0, 0.0006 * S * (f - 0.7) / 0.3)
            path.append(p); rad.append((r0 * (1 - 0.55 * f ** 1.3) * 0.75, r0 * (1 - 0.55 * f ** 1.3)))
        rad[-1] = (rad[-1][0] * 0.5, rad[-1][1] * 0.5)
        tube(cg, path, rad, 8, wfn, reg, 1, cap0=True, cap1=True)
    C.add(name, cg, subdiv=0, decal=True)


def finger_ring(C, side, reg, pc=0):
    """Signet ring on the ring finger's first segment (rigid, `ring` bone)."""
    fg = C.fingers[side][2]; n0, p1, dirn = fg["joints"][0]
    c = n0.lerp(p1, 0.55)
    A = C.arm[side]; hd = C.s["handDims"]
    rr = hd["fingerW"] * 0.60
    cg = Cage()
    a0 = perp(A["Xh"], dirn); b0 = dirn.cross(a0)
    pts = [c + a0 * math.cos(2 * math.pi * k / 12) * rr + b0 * math.sin(2 * math.pi * k / 12) * rr for k in range(12)]
    nrm = [(p - c).normalized() for p in pts]
    band_loop(cg, pts, nrm, [dirn] * 12, 0.0009 * C.S, 0.0006 * C.S, None, reg, pc)
    M = Matrix((b0, dirn, a0)).transposed()
    blob(cg, c + a0 * (rr + 0.0010 * C.S), 0.0017 * C.S, 0.0021 * C.S, 0.0008 * C.S, None, reg, pc, NU=10, NV=5, ax=M)
    C.add("ring", cg, subdiv=0, rigid="ring")
    C.B["ring"] = (c, c + dirn * 0.004 * C.S, "hand" + side)


def head_lathe(C, base_y, prof, N, wfn, reg, pc, cg, extra_x=0.0, extra_f=0.0, extra_b=0.0, e=2.3, tilt=0.0):
    """Surface of revolution around the head (crown, cap): rings at base_y + dy with scale k of the head section at
    base_y (+ clearances). prof = [(dy, k)], k = 0 closes with a pole. tilt (rad) tips it back about the base."""
    Hd = C.head; zc = C.L["zc"]
    rx = abs(Hd.at(0.25, base_y).x) + extra_x
    zf = Hd.at(0.0, base_y).z + extra_f; zb = Hd.at(0.5, base_y).z - extra_b
    zcc = (zf + zb) / 2; rz = (zf - zb) / 2
    pivot = V(0, base_y, zcc)
    R = Matrix.Rotation(-tilt, 3, V(1, 0, 0))
    rings = []
    for dy, k in prof:
        if k <= 0:
            rings.append(None); continue
        pts = [V(se(math.sin(2 * math.pi * j / N), e) * rx * k, base_y + dy, zcc + se(math.cos(2 * math.pi * j / N), e) * rz * k)
               for j in range(N)]
        rings.append(cg.ring([pivot + R @ (p - pivot) for p in pts], wfn))
    for i in range(len(prof) - 1):
        a, b = rings[i], rings[i + 1]
        if a and b:
            cg.bridge(a, b, reg, pc)
        elif a and b is None:
            cg.fan(a, pivot + R @ V(0, prof[i + 1][0], 0), wfn, reg, pc)
    return dict(rx=rx, rz=rz, zc=zcc, pivot=pivot, R=R)


def setup_workbench(res):
    s = sc(); s.render.engine = 'BLENDER_WORKBENCH'
    s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
    s.render.dither_intensity = 0.0
    s.render.resolution_x, s.render.resolution_y = res; s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGBA'
    sh = s.display.shading
    sh.show_cavity = False; sh.show_shadows = False; sh.show_object_outline = False; sh.show_specular_highlight = False


def front_ortho_camera():
    cam = camera(); cam.data.type = 'ORTHO'; cam.data.ortho_scale = ART_H; cam.data.sensor_fit = 'AUTO'
    cam.location = (0.0, -20.0, ART_H / 2); cam.rotation_euler = (math.radians(90), 0, 0)
    return cam


def set_face_materials(o, key_fn, mat_fn):
    me = o.data
    pid = [0] * len(me.polygons); rid = [0] * len(me.polygons)
    me.attributes["st_piece"].data.foreach_get("value", pid); me.attributes["st_region"].data.foreach_get("value", rid)
    me.materials.clear(); slots = {}; idx = []
    for p, r in zip(pid, rid):
        k = key_fn(p, r)
        if k not in slots:
            slots[k] = len(slots); me.materials.append(mat_fn(k))
        idx.append(slots[k])
    me.polygons.foreach_set("material_index", idx)


def page_material():
    m = bpy.data.materials.get(PAGE_MATERIAL) or bpy.data.materials.new(PAGE_MATERIAL)
    m.diffuse_color = (1, 1, 1, 1)
    return m


def all_meshes():
    return [o for o in sc().objects if o.type == 'MESH']


def apply_pixel_anchors(id_png, ids):
    """Constant UV0 for (a) regions too small to colour (ANCHORS), (b) hidden-by-default props that are not printed
    (PROP_ANCHORS, or design.json characters.<id>.propUV), (c) sliver parts (PART_ANCHORS: hands, feet).
    A target "char.region" = the deepest pixel (farthest from any other region / the paper) of that region in the
    front ID render; "char.FACE" = the same for the face skin with the eyes / brows / nose / mouth masked out."""
    import numpy as np
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)          # rows bottom -> top
    rgb = np.round(px[..., :3] * 255).astype(np.int32)
    key = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    alpha = px[..., 3] > 0.5
    cache = {}

    def set_mask(treg):
        """Mask of a set region in the set's page-space ID render, returned in art-rect UV pixels (2x)."""
        sj = os.path.join(MODEL, "set_id_2x.json"); sp = os.path.join(MODEL, "set_id_2x.png")
        if not (os.path.exists(sj) and os.path.exists(sp) and os.path.exists(DESIGN_JSON)):
            return None
        meta = json.load(open(sj)); art = json.load(open(DESIGN_JSON)).get("sheet", {}).get("art")
        if not art:
            return None
        sc_ = meta.get("scale", 2)
        im2 = bpy.data.images.load(sp, check_existing=False)
        W2, H2 = im2.size
        R = np.round(np.array(im2.pixels[:], dtype=np.float32).reshape(H2, W2, 4)[..., 0] * 255).astype(int)
        bpy.data.images.remove(im2)                                         # rows bottom -> top
        idl = [e["id"] for e in meta["ids"] if e["region"] == treg]
        if not idl:
            return None
        AX, AY, AW, AH = art
        crop = R[H2 - int((AY + AH) * sc_):H2 - int(AY * sc_), int(AX * sc_):int((AX + AW) * sc_)]
        m = np.isin(crop, idl)
        return m, m.shape[1], m.shape[0]

    def target_uv(tgt):
        if isinstance(tgt, (list, tuple)):
            for t in tgt:
                uv = target_uv(t)
                if uv:
                    cache[tuple(tgt)] = (uv, t)
                    return uv
            return None
        if tgt in cache:
            return cache[tgt]
        tch, treg = tgt.split(".")
        if tch == "set":
            r = set_mask(treg)
            if r is None or not r[0].any():
                cache[tgt] = None; return None
            m, Wm, Hm = r
            last = m.copy(); mm = m.copy()
            while mm.any():
                last = mm
                e = mm.copy()
                e[1:, :] &= mm[:-1, :]; e[:-1, :] &= mm[1:, :]; e[:, 1:] &= mm[:, :-1]; e[:, :-1] &= mm[:, 1:]
                mm = e
            ys, xs = np.nonzero(last)
            k = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
            cache[tgt] = ((xs[k] + 0.5) / Wm, (ys[k] + 0.5) / Hm)
            return cache[tgt]
        if treg == "FACE":
            keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids
                    if e["char"] == tch and e["part"] == "face" and e["region"] == "skin"]
            mask = np.isin(key, keys) & alpha
            F = face_layout(tch); L = landmarks(tch); Hh = L["top"] - L["chin"]; hw = SPEC[tch]["hw"]
            sX, sY = SHEET[tch]
            yy, xx = np.mgrid[0:H, 0:W]
            lx = (xx + 0.5) / W - 0.5 - sX; ly = (yy + 0.5) / H * ART_H - sY
            ex, ey, ew, eh = F["eyeLocal"]
            feat = (np.abs(np.abs(lx) - ex) < ew * 1.7) & (ly > ey - eh * 2.2) & (ly < L["brow"] + 0.16 * Hh)
            feat |= (np.abs(lx) < 0.42 * hw) & (np.abs(ly - L["mouth"]) < 0.13 * Hh)
            feat |= (np.abs(lx) < 0.26 * hw) & (ly > L["nose"] - 0.07 * Hh) & (ly < ey)
            mask &= ~feat
        else:
            keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids
                    if e["char"] == tch and e["region"] == treg]
            mask = np.isin(key, keys) & alpha
        if not mask.any():
            print("ANCHOR: empty target", tgt); cache[tgt] = None; return None
        last = mask; m = mask.copy()
        while m.any():
            last = m
            e = m.copy()
            e[1:, :] &= m[:-1, :]; e[:-1, :] &= m[1:, :]; e[:, 1:] &= m[:, :-1]; e[:, :-1] &= m[:, 1:]
            m = e
        ys, xs = np.nonzero(last)
        k = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
        cache[tgt] = ((xs[k] + 0.5) / W, (ys[k] + 0.5) / H)
        return cache[tgt]

    def assign(ch, reg, uv, part=None):
        rid = REGIONS.index(f"{ch}.{reg}") + 1 if f"{ch}.{reg}" in REGIONS else None
        if rid is None:
            return 0
        n = 0
        for o in all_meshes():
            if not o.name.startswith(ch + "_"):
                continue
            me = o.data; rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
            pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
            uv0 = me.uv_layers["UVMap"]
            for poly, r, pp in zip(me.polygons, rr, pid):
                if r == rid and (part is None or PIECES[pp - 1][1] == part):
                    n += 1
                    for li in poly.loop_indices:
                        uv0.data[li].uv = uv
        return n
    out = {}
    for ch in ONLY:
        o_ = out.setdefault(ch, {"anchors": {}, "propAnchors": {}, "partAnchors": {}})
        for reg, tgt in ANCHORS.get(ch, {}).items():
            uv = target_uv(tgt)
            if uv:
                assign(ch, reg, uv)
                o_["anchors"][reg] = {"target": tgt.split(".")[1] if tgt.startswith(ch + ".") else tgt,
                                      "uv": [round(uv[0], 5), round(uv[1], 5)]}
        for reg, tgt in PROP_ANCHORS.get(ch, {}).items():
            uv = tuple(PROP_UV[ch][reg]) if reg in PROP_UV.get(ch, {}) else target_uv(tgt)
            src = "design.json propUV" if reg in PROP_UV.get(ch, {}) else cache.get(tuple(tgt), (None, tgt))[1]
            if uv:
                if src.endswith(".FACE"):          # FACE = a texel of that face's printed skin, clear of the features
                    src = src[:-len("FACE")] + "skin"
                assign(ch, reg, uv); o_["propAnchors"][reg] = {"target": src, "uv": [round(uv[0], 5), round(uv[1], 5)]}
        for (part, reg), tgt in PART_ANCHORS.get(ch, {}).items():
            uv = target_uv(tgt)
            if uv:
                sX, sY = SHEET[ch]
                assign(ch, reg, uv, part)
                o_["partAnchors"][f"{part}.{reg}"] = {"target": tgt, "uv": [round(uv[0], 5), round(uv[1], 5)],
                                                      "local": [round(uv[0] - 0.5 - sX, 4), round(uv[1] * ART_H - sY, 4)]}
    bpy.data.images.remove(img)
    return out


def fix_uvs_by_id(id_png, ids, erode=5):
    """Final UV0 check against the front ID render (= the printed drawing): every face corner must sample a pixel of
    its own character + region at least `erode` px (2x render) inside the outline. Corners that land elsewhere (back
    of the head projected onto the face, a hidden cape behind the robe, an inset that crossed a thin band) move to
    the nearest such pixel. Anchored regions and eyelids are left alone."""
    import numpy as np
    from mathutils.kdtree import KDTree
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    rgb = np.round(px[..., :3] * 255).astype(np.int64)
    key = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    alpha = px[..., 3] > 0.5
    labels = {}
    lab = np.full((H, W), -1, np.int32)
    for e in ids:
        L = labels.setdefault((e["char"], e["region"]), len(labels))
        lab[(key == e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2]) & alpha] = L
    er = np.full((H, W), -1, np.int32)
    kds = {}
    for (ch, reg), L in labels.items():
        m = lab == L
        for it in range(erode, -1, -1):
            e = m.copy()
            for _ in range(it):
                f = e.copy()
                f[1:, :] &= e[:-1, :]; f[:-1, :] &= e[1:, :]; f[:, 1:] &= e[:, :-1]; f[:, :-1] &= e[:, 1:]
                e = f
            if e.sum() >= 4:
                break
        er[e] = L
        ys, xs = np.nonzero(e)
        step = 2 if len(xs) > 40000 else 1
        kd = KDTree(len(xs[::step]))
        for i, (x, y) in enumerate(zip(xs[::step], ys[::step])):
            kd.insert((float(x), float(y), 0.0), i)
        kd.balance()
        kds[L] = (kd, xs[::step], ys[::step])
    moved = {}; total = 0
    for o in all_meshes():
        ch = o.name.split("_")[0]
        if ch not in ONLY or o.name.endswith("_eyelids"):
            continue
        me = o.data; rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
        uv0 = me.uv_layers["UVMap"]
        skip = set(ANCHORS.get(ch, {}).keys()) | set(PROP_ANCHORS.get(ch, {}).keys())
        pskip = set(PART_ANCHORS.get(ch, {}).keys())
        if is_hidden_prop(o):
            continue
        pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
        for poly, r, pp in zip(me.polygons, rr, pid):
            reg = REGIONS[r - 1].split(".")[1]
            if reg in skip or (PIECES[pp - 1][1], reg) in pskip or (ch, reg) not in labels:
                continue
            L = labels[(ch, reg)]
            pts = []
            bad = False
            for li in poly.loop_indices:
                total += 1
                u, v = uv0.data[li].uv
                x = min(W - 1, max(0, int(u * W))); y = min(H - 1, max(0, int(v * H)))
                pts.append((x, y))
                if er[y, x] != L:
                    bad = True
            if not bad:
                continue
            # the whole face moves to one interior pixel near its projected centre (no streaks across regions)
            cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
            kd, xs, ys = kds[L]
            _, i, _ = kd.find((cx, cy, 0.0))
            for li in poly.loop_indices:
                uv0.data[li].uv = ((xs[i] + 0.5) / W, (ys[i] + 0.5) / H)
            moved[f"{ch}.{reg}"] = moved.get(f"{ch}.{reg}", 0) + 1
    bpy.data.images.remove(img)
    return {"corners": total, "facesMoved": moved}


def preview_material(ch, reg, decal_img):
    name = f"pv_{ch}_{reg}"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    col = [srgb_to_lin(c) for c in hex_rgb(PALETTE[ch].get(reg, "#cccccc"))] + [1.0]
    rgb = nt.nodes.new("ShaderNodeRGB"); rgb.outputs[0].default_value = col
    # crayon grain: a little value noise on the colour
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0; nz.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.93; mr.inputs["To Max"].default_value = 1.05
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(rgb.outputs[0], mul.inputs[6]); nt.links.new(mr.outputs[0], mul.inputs[7])
    base = mul.outputs[2]
    if decal_img is not None:
        uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "decal"
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.name = "decal"; tex.image = decal_img; tex.extension = 'CLIP'
        tex.interpolation = 'Cubic'
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Factor"])
        nt.links.new(base, mix.inputs[6]); nt.links.new(tex.outputs["Color"], mix.inputs[7])
        base = mix.outputs[2]
    nt.links.new(base, bsdf.inputs["Base Color"])
    if reg in GOLD:
        bsdf.inputs["Metallic"].default_value = 0.55; bsdf.inputs["Roughness"].default_value = 0.32
    else:
        bsdf.inputs["Roughness"].default_value = 0.72 if reg != "skin" else 0.55
        if reg == "skin":
            try:
                bsdf.inputs["Subsurface Weight"].default_value = 0.08
                bsdf.inputs["Subsurface Radius"].default_value = (0.004, 0.002, 0.0015)
            except Exception:
                pass
        else:
            try:
                bsdf.inputs["Sheen Weight"].default_value = 0.25
            except Exception:
                pass
    return m


def setup_eevee(res):
    s = sc()
    s.render.engine = 'BLENDER_EEVEE'
    s.render.resolution_x, s.render.resolution_y = res; s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGB'
    s.render.film_transparent = False
    s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
    s.view_settings.exposure = -0.15
    try:
        s.eevee.taa_render_samples = 48
    except Exception:
        pass
    for k, v in (("use_shadows", True), ("use_raytracing", True)):
        try:
            setattr(s.eevee, k, v)
        except Exception:
            pass


def preview_lights():
    """Studio turntable: a curved paper backdrop and three suns parented to one empty (`turn`), which is rotated with
    the camera so every view is lit the same way."""
    s = sc()
    w = bpy.data.worlds.get("pvW") or bpy.data.worlds.new("pvW"); s.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.86, 0.80, 0.72, 1); bg.inputs[1].default_value = 0.55
    turn = bpy.data.objects.get("turn") or bpy.data.objects.new("turn", None)
    if turn.name not in s.collection.objects:
        s.collection.objects.link(turn)
    for nm, rot, en, ang, col in (("key", (math.radians(50), 0, math.radians(-35)), 3.6, 10, (1.0, 0.94, 0.84)),
                                  ("rim", (math.radians(62), 0, math.radians(150)), 2.6, 5, (0.88, 0.92, 1.0)),
                                  ("fill", (math.radians(70), 0, math.radians(55)), 0.9, 25, (1.0, 0.97, 0.93))):
        L = bpy.data.lights.get(nm) or bpy.data.lights.new(nm, 'SUN')
        L.energy = en; L.angle = math.radians(ang); L.color = col
        o = bpy.data.objects.get(nm) or bpy.data.objects.new(nm, L)
        if o.name not in s.collection.objects:
            s.collection.objects.link(o)
        o.rotation_euler = rot; o.parent = turn
    if not bpy.data.objects.get("backdrop"):
        verts, faces = [], []
        prof = []
        for i in range(25):                     # floor toward the camera, then a quarter circle up behind
            t = i / 24
            if t < 0.5:
                prof.append((-3.0 + 3.6 * (t / 0.5), 0.0))
            else:
                a = (t - 0.5) / 0.5 * math.pi / 2
                prof.append((0.6 + math.sin(a) * 1.2, 1.2 - math.cos(a) * 1.2))
        prof.append((1.8, 5.0))
        for y, z in prof:
            verts += [(-8, y, z), (8, y, z)]
        for i in range(len(prof) - 1):
            faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
        me = bpy.data.meshes.new("backdrop"); me.from_pydata(verts, [], faces)
        for pl in me.polygons: pl.use_smooth = True
        bd = bpy.data.objects.new("backdrop", me); s.collection.objects.link(bd)
        m = bpy.data.materials.new("backdropM"); m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF"); b.inputs["Base Color"].default_value = (0.82, 0.76, 0.66, 1)
        b.inputs["Roughness"].default_value = 0.95
        me.materials.append(m)
        bd.parent = turn


def turntable(cam, target, yaw, dist, height, lens=60):
    turn = bpy.data.objects["turn"]
    turn.location = (target.x, 0.0, 0.0)
    turn.rotation_euler = (0, 0, math.radians(yaw))
    bpy.data.objects["backdrop"].location = (0, 0.55 * dist * 0 + 0.0, 0)
    look_from(cam, target, yaw, dist, height, lens)


def _region_of():
    return {i + 1: k.split(".")[1] for i, k in enumerate(REGIONS)}


def bend(rig, bone, axis_design, deg):
    """Rotate a pose bone about a design-space axis through its head, on top of its rest frame (as dg_build)."""
    pb = rig.pose.bones[bone]
    R = Matrix.Rotation(math.radians(deg), 4, to_bl(axis_design).normalized())
    rest = pb.bone.matrix_local
    pb.rotation_mode = 'QUATERNION'
    h = rest.translation.copy()
    pb.matrix_basis = rest.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ rest
    bpy.context.view_layer.update()


def mode_posetest():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    setup_eevee((640, 960)); preview_lights()
    imgs = {ch: bpy.data.images.load(os.path.join(FACES, f"{ch}_{DEFAULT_EXPR[ch]}.png"), check_existing=True) for ch in CHARS}
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        set_face_materials(o, lambda p, r: r, lambda r: preview_material(ch, REGION_OF[r], imgs.get(ch)))
    cam = camera()
    present = [ch for ch in CHARS if bpy.data.objects.get(f"{ch}_rig")]
    for ch in present:
        pose_test(bpy.data.objects[f"{ch}_rig"], ch)
    for ch in present:
        for o in all_meshes():
            if o.name not in ("floor", "backdrop"):
                o.hide_render = o.name.split("_")[0] != ch or is_hidden_prop(o)
        rig = bpy.data.objects[f"{ch}_rig"]; Hh = SPEC[ch]["height"]
        for nm, yaw in (("a", 20), ("b", 70)):
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), yaw, Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pose_{ch}_{nm}.png"))
    print("POSETEST done")


def mode_uvcheck():
    """Models wearing $<ENV>WORK/uvproof.png (or $<ENV>UV_TEXTURE) through UV0: front ortho (must equal the sheet) and
    3/4 + back perspective (back of the cape / robe behind the braid take their own region's colour)."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get(ENV + "UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        o.data.materials.clear(); o.data.materials.append(m)
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    sc().view_settings.view_transform = 'Standard'
    cam = front_ortho_camera()
    for nm in ("backdrop",):
        bpy.data.objects[nm].hide_render = True
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = False
    bpy.data.objects["backdrop"].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc().render.resolution_x, sc().render.resolution_y = 1600, 900
    for nm, yaw in (("q34", 30), ("back", 180)):
        turntable(cam, Vector((0.0, 0, 0.19)), yaw, 1.45, 0.16, 50)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    print("UVCHECK done")


def mode_verify():
    out = {}
    for ch in CHARS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"))
        arms = [o for o in sc().objects if o.type == 'ARMATURE']
        meshes = [o for o in sc().objects if o.type == 'MESH' and o.name.startswith(ch)]
        bones = sorted(b.name for b in arms[0].data.bones) if arms else []
        want = sorted(CONTRACT_BONES + EXTRA_BONES[ch])
        info = {"armatures": len(arms), "bonesMatch": bones == want, "missing": sorted(set(want) - set(bones)),
                "extra": sorted(set(bones) - set(want)), "actions": len(bpy.data.actions), "meshes": {}}
        tris = 0
        for o in meshes:
            t = sum(len(p.vertices) - 2 for p in o.data.polygons); tris += t
            maxinf = max((sum(1 for g in v.groups if g.weight > 0) for v in o.data.vertices), default=0)
            uvl = o.data.uv_layers
            n0 = len(uvl[0].data)
            u0 = [uvl[0].data[i].uv for i in range(0, n0, max(1, n0 // 2000))]
            u1 = [uvl[1].data[i].uv for i in range(0, n0, max(1, n0 // 2000))] if len(uvl) > 1 else []
            layer0_page = all(-0.01 <= a.x <= 1.01 and -0.01 <= a.y <= 1.01 for a in u0)
            layer1_decal = (len(u1) > 0 and any(a.x < -0.5 for a in u1))
            info.setdefault("uvOrderOK", True)
            info["uvOrderOK"] &= layer0_page and layer1_decal
            info["meshes"][o.name] = {"skinned": any(m.type == 'ARMATURE' for m in o.modifiers),
                                      "parentBone": o.parent_bone or None, "tris": t,
                                      "uvLayers": [u.name for u in o.data.uv_layers], "maxInfluences": maxinf,
                                      "materials": [m.name for m in o.data.materials if m]}
        info["tris"] = tris; info["trisUnder25k"] = tris < 25000
        h = max((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
        info["heightTop"] = round(h, 4)
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps(out))
