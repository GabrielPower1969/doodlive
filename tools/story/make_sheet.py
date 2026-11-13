"""Story colouring sheet (Set + sheet role), generic for story packs built like Esther: the cast's front ID render +
the set's drawings, composed on the A4 page exactly like David & Goliath (tools/make_dg_sheet.py, CONTRACT §11-12,
LESSONS L40-41): same page 1240 x 1754 @150 dpi, four corner markers, art rectangle [120, 283, 1000, 1227], 田字格 title.

Inputs (story <id>)
  assets/<id>/design.json                      sheet (title, footer, markers, art), lines, characters.<c>.sheetX/sheetY
  assets/<id>/model/id_characters_2x.png/.json front-ortho ID render of the cast in rest pose at their sheet places,
                                               2x the art rect (pipeline/es_characters.py; D&G id_2x colour scheme)
  assets/<id>/model/regions_characters.json    regions per figure; anchorUV of parts too small to colour
  assets/<id>/model/set_id_2x.png/.json        the set's drawings at 2x of the page: R = id, G = detail line mask
                                               (pipeline/es_palace.py); constUV = texels the set samples

Outputs (assets/<id>/sheet/ unless noted; names read by Unity's StorySetup)
  lineart.png (1000 x 1227 = UV0 space)   reference.png (blank page = the print)   demo-sheet.png (page, demo colours)
  demo-colored.png (art rect, demo colours) regions.png/.json   template.json   checks.json
  print/<id>-A4.png/.pdf                   $STORY_WORK/<id>_demo_page_fill.png (lines removed: render texture)

Run from the repo root:
  python3 tools/story/make_sheet.py esther                                                build the sheet
  blender -b --factory-startup --python tools/story/make_sheet.py -- esther render        set + cast wearing the demo
      colouring, phone view etc. -> assets/<id>/sheet/textured_*.png (look: colours must land on the right parts)
"""
import json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get("STORY_WORK", "/tmp/story_work"))
SS = 2
INK = (0x26, 0x20, 0x19)
DECOR_GAP_PX = 4


def setup(sid):
    global SID, A, OUT, MODEL, DESIGN, SH, PW, PH, AX, AY, AW, AH, ART_H, LINE_PX, DETAIL_PX, STORY
    SID = sid
    A = ROOT / "assets" / sid
    OUT = A / "sheet"; MODEL = A / "model"
    DESIGN = json.load(open(A / "design.json"))
    SH = DESIGN["sheet"]
    PW, PH = SH["page"]; AX, AY, AW, AH = SH["art"]
    ART_H = DESIGN.get("artHeightUnits", 1.227)
    LINE_PX = DESIGN["lines"]["outerPx"]; DETAIL_PX = DESIGN["lines"]["detailPx"]
    STORY = next(s for s in json.load(open(ROOT / "assets/stories.json", encoding="utf-8"))["stories"] if s["id"] == sid)


def disk(r):
    import numpy as np
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def decode_ids(img, table):
    import numpy as np
    a = np.asarray(img).astype(int)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    k = np.rint((r - 16) / 16) + 15 * np.rint((g - 16) / 16) + 225 * np.rint((b - 64) / 64)
    k = np.where(al > 127, k, 0).astype(int)
    bad = (k > 0) & ~np.isin(k, [e["id"] for e in table])
    if bad.any():
        raise SystemExit(f"ID decode failed on {int(bad.sum())} px")
    return k


def build():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage
    H2, W2 = PH * SS, PW * SS

    # ---- cast
    ct = json.load(open(MODEL / "id_characters_2x.json"))
    ids = [dict(e) for e in ct["ids"]]
    clab = decode_ids(Image.open(MODEL / "id_characters_2x.png").convert("RGBA"), ids)
    assert clab.shape == (AH * SS, AW * SS), clab.shape
    lab = np.zeros((H2, W2), np.int32)
    lab[AY * SS:(AY + AH) * SS, AX * SS:(AX + AW) * SS] = clab
    rc = json.load(open(MODEL / "regions_characters.json"))
    # parts too small to colour (anchored to another region): printed as detail line art inside their neighbour
    detail_ids = []
    for e in ids:
        r = rc["characters"].get(e["char"], {}).get("regions", {}).get(e["region"], {})
        if r.get("anchoredTo") and r["anchoredTo"] != e["region"]:
            detail_ids.append(e["id"]); e["detailOf"] = r["anchoredTo"]
    dmask = np.isin(lab, detail_ids)
    char_decor = np.zeros_like(dmask)
    if dmask.any():
        for i in detail_ids:                            # outline of each detail part
            m = lab == i
            char_decor |= m & ~ndimage.binary_erosion(m, iterations=1)
        keep = (lab > 0) & ~dmask
        _, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
        lab = np.where(dmask, lab[iy, ix], lab)
    char_mask = lab > 0

    # ---- set drawings
    st = json.load(open(MODEL / "set_id_2x.json"))
    sa = np.asarray(Image.open(MODEL / "set_id_2x.png").convert("RGBA")).astype(int)
    assert sa.shape[:2] == (H2, W2), sa.shape
    off = max(e["id"] for e in ids)
    slab = sa[..., 0]
    clash = int(((slab > 0) & char_mask).sum())
    for e in st["ids"]:
        ids.append({"id": e["id"] + off, "char": "set", "part": e["part"], "piece": 0, "region": e["region"],
                    "hex": e["hex"], "nodes": e["nodes"]})
    lab = np.where((slab > 0) & ~char_mask, slab + off, lab)
    next_id = max(e["id"] for e in ids) + 1
    if next_id > 255:
        raise SystemExit(f"{next_id} region ids do not fit regions.png (8-bit)")
    set_decor = (sa[..., 1] > 127) & (slab > 0)
    decor0 = ndimage.binary_dilation(set_decor, structure=disk(1)) | char_decor
    decor0 = ndimage.binary_dilation(decor0, structure=disk(1))
    dens = ndimage.uniform_filter(decor0.astype(float), size=15)
    decor0 &= dens < 0.45                                  # drop detail hatching too dense to print (flutes, folds)
    r_out = int(round(LINE_PX * SS / 2)) - 1
    r_in = int(round(DETAIL_PX * SS / 2)) - 1

    def ink(lab):
        e_any = np.zeros_like(lab, bool); e_out = np.zeros_like(lab, bool)
        for ax in (0, 1):
            a_, b_ = (lab[1:, :], lab[:-1, :]) if ax == 0 else (lab[:, 1:], lab[:, :-1])
            ch = a_ != b_; po = ch & ((a_ == 0) | (b_ == 0))
            for m_, tgt in ((ch, e_any), (po, e_out)):
                if ax == 0: tgt[1:, :] |= m_; tgt[:-1, :] |= m_
                else: tgt[:, 1:] |= m_; tgt[:, :-1] |= m_
        line2 = ndimage.binary_dilation(e_out, structure=disk(r_out)) | ndimage.binary_dilation(e_any, structure=disk(r_in))
        dist_edge = ndimage.distance_transform_edt(~e_any) / SS
        d2 = decor0 & (dist_edge >= (LINE_PX / 2 + 2))           # detail lines never split a region
        dl, dn = ndimage.label(d2)
        if dn:
            ar = ndimage.sum(d2, dl, index=np.arange(1, dn + 1))
            d2 &= np.isin(dl, 1 + np.nonzero(ar >= 40)[0])
        all2 = line2 | d2
        hl, hn = ndimage.label(~all2)
        if hn:
            ar = ndimage.sum(~all2, hl, index=np.arange(1, hn + 1))
            all2 |= np.isin(hl, 1 + np.nonzero(ar < 60)[0])
        return all2

    # merge parts the ink would swallow into a touching part of the same colour region
    regname = {e["id"]: (e["char"], e["region"]) for e in ids}
    merged = []
    for _ in range(4):
        all2 = ink(lab)
        dt = ndimage.distance_transform_edt(~all2) * 2 / SS
        cell = ndimage.maximum(dt, lab, index=np.arange(next_id + 1))
        present = np.bincount(lab.ravel(), minlength=next_id + 1) > 0
        weak = [i for i in range(1, next_id) if present[i] and cell[i] < 6.5]
        changed = False
        for i in weak:
            m = lab == i
            ring = ndimage.binary_dilation(m, structure=disk(3)) & ~m
            nb = lab[ring]; nb = nb[(nb > 0) & (nb != i)]
            same = [j for j in np.unique(nb) if regname.get(int(j)) == regname[i]]
            if not same:
                continue
            j = max(same, key=lambda j: int((nb == j).sum()))
            lab[m] = j; merged.append((i, int(j))); changed = True
        if not changed:
            break

    def down(a):
        return a.reshape(PH, SS, PW, SS, *a.shape[2:]).mean(axis=(1, 3))
    a1 = down(all2.astype(float))
    pl, pn = ndimage.label(a1 < 0.5)
    if pn:
        areas = ndimage.sum(a1 < 0.5, pl, index=np.arange(1, pn + 1))
        a1[np.isin(pl, 1 + np.nonzero(areas < 12)[0])] = 1.0
    ink_page = 255.0 * (1 - a1[..., None]) + np.array(INK) * a1[..., None]
    art_sl = (slice(AY, AY + AH), slice(AX, AX + AW))
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(ink_page[art_sl].round().astype(np.uint8)).save(OUT / "lineart.png")

    lut = np.full((next_id + 1, 3), 255.0)
    for e in ids:
        h = e["hex"].lstrip("#"); lut[e["id"]] = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    fill1 = down(lut[lab])
    demo_page = fill1 * (ink_page / 255.0)
    dpaper, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
    lab_grow = np.where((lab == 0) & (dpaper <= 6 * SS), lab[iy, ix], lab)
    fill_grow = down(lut[lab_grow])
    Image.fromarray(demo_page[art_sl].round().astype(np.uint8)).save(OUT / "demo-colored.png")
    WORK.mkdir(parents=True, exist_ok=True)
    Image.fromarray(fill_grow.round().astype(np.uint8)).save(WORK / f"{SID}_demo_page_fill.png")

    lab1p = lab[SS // 2::SS, SS // 2::SS]
    lab1 = lab1p[art_sl]
    Image.fromarray(lab1.astype(np.uint8)).save(OUT / "regions.png")
    json.dump({"note": "regions.png pixel value = id (0 = paper), same pixels as lineart.png. Cast: rest pose, front "
                       "orthographic (UV0 front projection at characters.<id>.sheetX/sheetY). char 'set': drawings of "
                       "the set (design.json set.drawings; 'part' = drawing, 'nodes' = the set nodes that sample it). "
                       "Parts with detailOf are printed as detail lines and take that region's colour (anchorUV).",
               "ids": [{k: v for k, v in e.items() if k != "rgb"} for e in ids]}, open(OUT / "regions.json", "w"),
              indent=1, ensure_ascii=False)

    sys.path.insert(0, str(ROOT / "tools")); from tianzige import draw_title
    t = SH["title"]

    def page_with(rgb_page):
        page = Image.fromarray(rgb_page.round().astype(np.uint8))
        d = ImageDraw.Draw(page); ms = SH["markerSize"]
        for cx, cy in SH["markers"]:
            d.rectangle((cx - ms // 2, cy - ms // 2, cx + ms // 2 - 1, cy + ms // 2 - 1), fill="black")
        draw_title(page, t["hanzi"], t["english"], cy=t["cy"], box=t["box"], gap=t["gap"], label=t["label"],
                   pinyin=t["pinyin"])
        try:
            f1 = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 24)
            f2 = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 20)
        except OSError:
            f1 = f2 = ImageFont.load_default()
        fx, fy, fw, fh = SH["footer"]["rect"]; l1, l2 = SH["footer"]["lines"]
        d.text((fx + fw / 2, fy + 40), l1, fill=(120, 120, 120), font=f1, anchor="mm")
        d.text((fx + fw / 2, fy + 76), l2, fill=(154, 154, 154), font=f2, anchor="mm")
        return page
    page = page_with(ink_page)
    (ROOT / "print").mkdir(exist_ok=True)
    page.save(ROOT / f"print/{SID}-A4.png")
    page.save(ROOT / f"print/{SID}-A4.pdf", resolution=150)
    page.save(OUT / "reference.png")
    page_with(demo_page).save(OUT / "demo-sheet.png")
    json.dump({"page": [PW, PH], "art": [AX, AY, AW, AH], "markers": SH["markers"], "markerSize": SH["markerSize"],
               "artPixels": [AW, AH]}, open(OUT / "template.json", "w"), indent=1)

    # ================================================================== checks
    checks = {"setOverCastPx2x": clash, "mergedIntoSameColourNeighbour": merged, "detailParts": len(detail_ids)}
    byid = {e["id"]: e for e in ids}
    paper = a1[art_sl] < 0.5
    comp, n = ndimage.label(paper)
    dt = ndimage.distance_transform_edt(paper)
    inscribed = ndimage.maximum(dt, comp, index=np.arange(1, n + 1)) * 2
    pieces = []
    for i, dia in enumerate(inscribed, start=1):
        h = lab1[comp == i]
        if (h == 0).mean() > 0.5:
            continue
        e = byid[int(np.bincount(h[h > 0]).argmax())]
        pieces.append((round(float(dia), 1), f'{e["char"]}.{e["part"]}:{e["region"]}'))
    pieces.sort()
    best = {}
    for d_, k in pieces:
        best[k] = max(best.get(k, 0), d_)
    mm6 = 6 / 25.4 * SH["dpi"]                                     # 35.4 px
    checks["pieces"] = len(pieces)
    checks["slivers(<6px)"] = [p for p in pieces if p[0] < 6 and best[p[1]] < 6]
    checks["regionsBelow6mm(best cell)"] = sorted({(round(v, 1), k) for k, v in best.items() if v < mm6})
    seen = set(best)
    still = set(np.unique(lab).tolist())
    checks["regionsWithoutColourableCell"] = sorted({f'{e["char"]}.{e["part"]}:{e["region"]}' for e in ids
                                                     if e["id"] in still} - seen)
    edge_ink = {"bottom": int((a1[art_sl][-6:, :] > 0.5).sum()), "top": int((a1[art_sl][:6, :] > 0.5).sum()),
                "left": int((a1[art_sl][:, :6] > 0.5).sum()), "right": int((a1[art_sl][:, -6:] > 0.5).sum())}
    checks["inkWithin6pxOfArtEdge"] = edge_ink
    # constant / anchor UVs must sit on clean colour of the right region
    dink = ndimage.distance_transform_edt(a1[art_sl] < 0.5)
    samples = {}
    for c, v in rc["characters"].items():
        for r, e in v["regions"].items():
            if e.get("anchorUV"):
                samples[f"{c}.{r}"] = (e["anchorUV"], c, e["anchoredTo"])
    for e in st.get("constUV", []):
        samples["set." + e["node"]] = (e["uv"], "set", e["region"])
    us = {}
    for k, (uv, ch, want) in samples.items():
        px, py = int(uv[0] * AW), int((1 - uv[1]) * AH)
        e = byid.get(int(lab1[py, px]))
        ok = bool(e and e["char"] == ch and e["region"] == want and dink[py, px] >= 3)
        us[k] = {"uv": uv, "region": f'{e["char"]}:{e["region"]}' if e else "paper", "want": want,
                 "inkDistPx": round(float(dink[py, px]), 1), "ok": ok}
    checks["anchorSamples"] = us
    pg = np.asarray(page.convert("RGB")).astype(int).min(axis=-1) < 200
    ms = SH["markerSize"]
    for cx, cy in SH["markers"]:
        pg[max(0, cy - ms // 2 - 3):cy + ms // 2 + 3, max(0, cx - ms // 2 - 3):cx + ms // 2 + 3] = False
    ys_, xs_ = np.nonzero(pg)
    page_m = {"left": int(xs_.min()), "right": int(PW - 1 - xs_.max()), "top": int(ys_.min()),
              "bottom": int(PH - 1 - ys_.max())}
    checks["inkToPageEdgePx(excl. markers)"] = page_m
    json.dump(checks, open(OUT / "checks.json", "w"), indent=1, ensure_ascii=False)
    fails = []
    if any(edge_ink.values()): fails.append(f"line art touches the art-rect edge: {edge_ink}")
    set_sl = [p for p in checks["slivers(<6px)"] if p[1].startswith("set.")]
    checks["castSlivers(<6px, Characters role)"] = [p for p in checks["slivers(<6px)"] if not p[1].startswith("set.")]
    if set_sl: fails.append(f"set slivers: {set_sl}")
    if clash: fails.append(f"set drawing over a figure ({clash} px)")
    for k, v in us.items():                                # cast anchors: right region is enough (line-erase)
        if not v["ok"] and not k.startswith("set.") and v["region"].split(":")[-1] == v["want"]:
            v["ok"] = True; v["note"] = "near a line"
    badu = {k: v for k, v in us.items() if not v["ok"]}
    if badu: fails.append(f"anchor/constant UV off its region: {badu}")
    if min(page_m.values()) < 35.4: fails.append(f"ink closer than 6 mm to the page edge: {page_m}")
    print(json.dumps({k: v for k, v in checks.items() if k != "anchorSamples"}, indent=1, ensure_ascii=False))
    print("anchors ok:", sum(v["ok"] for v in us.values()), "/", len(us))
    if fails:
        raise SystemExit("SHEET FAIL: " + "; ".join(fails))
    print("SHEET PASS")


# ============================================================================================ textured renders
PAGE_LAYER = {}


def render():
    """set + cast wearing the demo colouring (lines erased), from the phone: colours must land on the right parts"""
    import bpy
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    fill = bpy.data.images.load(str(WORK / f"{SID}_demo_page_fill.png"))
    sheet = bpy.data.images.load(str(OUT / "demo-sheet.png"))

    def mat(name, img, art_uv=True, rough=0.85):
        m = bpy.data.materials.new(name); nt = m.node_tree
        b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = rough
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.extension = 'EXTEND'
        tex.interpolation = 'Closest' if art_uv else 'Linear'
        if art_uv:
            uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Location"].default_value = (AX / PW, (PH - AY - AH) / PH, 0)
            mp.inputs["Scale"].default_value = (AW / PW, AH / PH, 1)
            nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], tex.inputs[0])
        nt.links.new(tex.outputs[0], b.inputs["Base Color"])
        return m
    m_art = mat("art", fill)

    def imp(path):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        return [o for o in bpy.data.objects if o not in before]
    objs = imp(MODEL / f"{STORY['set']}.glb")
    roots = {}
    for ch in STORY["cast"]:
        new = imp(MODEL / f"{ch}.glb"); objs += new
        roots[ch] = [(o, o.location.copy(), o.rotation_euler.copy()) for o in new if o.parent is None]
    for o in objs:
        if o.type != 'MESH':
            continue
        if o.data.uv_layers:                         # the page UV = the layer that stays inside 0..1
            import numpy as np
            best, bi = -1.0, 0
            for i, u in enumerate(o.data.uv_layers):
                a = np.zeros(len(o.data.loops) * 2); u.data.foreach_get("uv", a)
                fr = float(((a >= -1e-4) & (a <= 1 + 1e-4)).mean())
                if fr > best: best, bi = fr, i
            PAGE_LAYER[o.name] = (bi, [u.name for u in o.data.uv_layers])
            for u in o.data.uv_layers:
                u.name = "uv_tmp_" + u.name
            o.data.uv_layers[bi].name = "UVMap"
        o.data.materials.clear(); o.data.materials.append(m_art)

    def stage(stg):
        for ch, (x, z, y, yaw) in stg.items():
            for o, loc0, rot0 in roots[ch]:
                o.rotation_mode = 'XYZ'
                o.location = (loc0.x + x, loc0.y - z, loc0.z + y)
                o.rotation_euler = (rot0.x, rot0.y, rot0.z + math.radians(yaw))
    x0, x1 = -AX / AW - 0.5, (PW - AX) / AW - 0.5
    y1, y0 = (AY + AH) / AW, (AY + AH - PH) / AW
    me = bpy.data.meshes.new("paper"); me.from_pydata([(x0, y0, -0.001), (x1, y0, -0.001), (x1, y1, -0.001),
                                                       (x0, y1, -0.001)], [], [(0, 1, 2, 3)])
    lay = me.uv_layers.new(name="UVMap")
    for li, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]): lay.data[li].uv = uv
    sc.collection.objects.link(bpy.data.objects.new("paper", me))
    me.materials.append(mat("paper", sheet, art_uv=False, rough=0.95))
    me2 = bpy.data.meshes.new("tabletop")
    me2.from_pydata([(-3, -3, -0.004), (3, -3, -0.004), (3, 4, -0.004), (-3, 4, -0.004)], [], [(0, 1, 2, 3)])
    sc.collection.objects.link(bpy.data.objects.new("tabletop", me2))
    tm = bpy.data.materials.new("tabletop")
    tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.25, 0.17, 1)
    me2.materials.append(tm)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 3.2; sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(42), math.radians(-22), math.radians(-30))
    sc.world = bpy.data.worlds.new("w")
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.82, 0.86, 0.93, 1)
    bg.inputs[1].default_value = 0.85
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    sc.eevee.taa_render_samples = 32
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.01; cam.data.clip_end = 20
    chars = DESIGN["characters"]
    marks = {c: (chars[c]["sheetX"], 0.0, 0.0, 0) for c in STORY["cast"]}
    tl = json.load(open(A / "timeline.json"))
    opening = {}
    for a in tl["acting"]:
        if a["t"] == 0.0 and "to" in a and a["who"] not in opening:
            opening[a["who"]] = (a["to"][0], a["to"][1], a.get("y", 0.0), 0)
    if "king" in opening:                                 # rest pose cannot sit: stand him in front of the steps
        opening["king"] = (0.0, -0.05, 0.0, 0)
    shots = [("textured_phone", marks, (-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280)),
             ("textured_phone_play", opening, (-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280)),
             ("textured_front", marks, (0.0, 0.26, 2.3), (0.0, 0.20, -0.25), 21, (1600, 1000)),
             ("textured_cast", marks, (0.0, 0.22, 1.25), (0.0, 0.19, 0.0), 22, (1600, 900))]
    for name, stg, eye, tgt, vfov, res in shots:
        stage(stg)
        e = Vector((eye[0], -eye[2], eye[1])); t = Vector((tgt[0], -tgt[2], tgt[1]))
        cam.location = e; cam.rotation_euler = (t - e).to_track_quat('-Z', 'Y').to_euler()
        cam.data.angle_y = math.radians(vfov)
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.filepath = str(OUT / f"{name}.png"); bpy.ops.render.render(write_still=True)
    print("PAGE_UV_LAYER", json.dumps({k: v for k, v in PAGE_LAYER.items() if v[0] != 0}))
    print("RENDER_OK")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    setup(argv[0] if argv else "esther")
    if argv[1:2] == ["render"]:
        render()
    else:
        build()
