"""Gabriel colouring sheet: tools/story/make_sheet.py, unchanged, with the Gabriel-specific bits added from outside
(the shared tool and the other packs' output are not touched), the way tools/story/sheet_daniel.py does it.

This sheet is special: Gabriel fills the page (height 0.62, wings spread about 1.0 wide, slot (0, 0.015), front
view); the set drawings (gate, two islets, two clouds) sit above his wings and in the bottom corners.

What this adds:
  * a stand-in registry entry while `assets/stories.json` (Integration's file) has no "gabriel" yet
  * the cast inputs are patched on a copy (files in model/ are not touched): pieces of one colour region become one
    region and the borders between them are printed as detail lines (feathers inside the two wing regions, hair
    locks, armour plates), and part-anchored pieces print as detail lines (sheet_daniel.py)
  * `print/gabriel-A4-colored.pdf`: the demo-coloured page as an A4 PDF with the same page geometry as the blank one
  * its own textured renders (the hero is 0.62 tall with 1.0 of wings: the shared camera set crops him)
  * `signature`: the title-band distinctness check of tools/make_sheet_signatures.py for this sheet against every
    other sheet, on a copy of the registry (unity/Assets/DoodLive/Resources/sheet_signatures.json is not written)

Run from the repo root:
  python3 tools/story/sheet_gabriel.py                       sheet + checks.json + print/gabriel-A4.* + -colored.pdf
  python3 tools/story/sheet_gabriel.py signature             title band vs every other sheet (NCC, a true match ~0.9)
  blender -b --factory-startup --python tools/story/sheet_gabriel.py -- geometry   depth + normals of gabriel.glb
      (before the sheet, after every character build: the sculpt lines come from it)
  blender -b --factory-startup --python tools/story/sheet_gabriel.py -- render     textured_*.png
Work files: $STORY_WORK, default /tmp/gabriel_set.
"""
import json, math, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_sheet as ms                                   # noqa: E402

SID = "gabriel"
SHEET_NAME = "gabriel-A4"


def setup():
    try:
        ms.setup(SID)
    except StopIteration:                                 # not in the registry yet: everything else is set by now
        d = json.load(open(ms.ROOT / "assets" / SID / "design.json"))
        ms.STORY = {"id": SID, "engine": "story", "title_zh": d["sheet"]["title"]["hanzi"],
                    "title_en": d["sheet"]["title"]["english"],
                    "sheets": [SHEET_NAME, f"{SID}-A4-demo", f"{SID}-A4-colored"],
                    "cast": ["gabriel"], "set": d["set"]["root"]}
        print("note: assets/stories.json has no 'gabriel' entry yet; using a stand-in entry", ms.STORY)
    if "STORY_WORK" not in os.environ:                    # this pack's scratch (CONTRACT: /tmp/gabriel_<role>/)
        ms.WORK = Path("/tmp/gabriel_set")
    if os.environ.get("GABRIEL_SHEET_MODEL"):             # test hook: cast inputs from another folder
        ms.MODEL = Path(os.environ["GABRIEL_SHEET_MODEL"])


WING_REGIONS = ("wingFeathers", "wingCoverts")
THIN_PX = 6.5          # a piece never wider than 2 x this (2x pixels; 13 px = 1.1 mm on paper) is a line, not an area
CREASE_DEG = 40.0      # a fold this sharp between neighbouring pixels is drawn
VALLEY = (0.055, 0.115)  # hysteresis on the screen-space curvature of a groove (low, high)
SOFT_SIGMA, SOFT_VALLEY = 4.5, (0.014, 0.028)   # the same for broad soft grooves (blur in 2x px; low, high)
MIN_LINE_PX = 26       # shorter strokes are noise


def decode(img):
    import numpy as np
    a = np.asarray(img.convert("RGBA")).astype(int)
    k = np.rint((a[..., 0] - 16) / 16) + 15 * np.rint((a[..., 1] - 16) / 16) + 225 * np.rint((a[..., 2] - 64) / 64)
    return np.where(a[..., 3] > 127, k, 0).astype(int)


def encode(k):
    import numpy as np
    from PIL import Image
    a = np.zeros(k.shape + (4,), np.uint8)
    a[..., 0] = 16 + 16 * (k % 15); a[..., 1] = 16 + 16 * ((k // 15) % 15); a[..., 2] = 64 + 64 * (k // 225)
    a[..., 3] = 255
    a[k == 0] = 0
    return Image.fromarray(a, "RGBA")


def face_rect_2x(rc):
    """the face decal's square on the 2x art raster: (x0, y0, x1, y1) in pixels, y down"""
    AX, AY, AW, AH = ms.SH["art"]
    g = rc["characters"][SID]; sh = rc["sheet"][SID]
    x0, y0, x1, y1 = g["faceDecal"]["rectLocal"]
    X = lambda x: (x + sh["sheetX"] + 0.5) * AW * 2
    Y = lambda y: (1.0 - (y + sh["sheetY"]) / ms.ART_H) * AH * 2
    return X(x0), Y(y1), X(x1), Y(y0)


def sculpt_lines(k, ids, rc):
    """detail lines that follow the sculpt, from the geometry pass (depth + normals of gabriel.glb, same pixels as
    the ID render): where one part of a colour region covers another (hair locks, plates, fingers), sharp folds, and
    grooves (the centre line of the chest, the muscles of the cuirass, between locks). Wings are left to their
    feather pieces; the face under the decal is left to the face guide. Returns a boolean 2x mask of 1 px strokes."""
    import numpy as np
    from scipy import ndimage
    from skimage.morphology import skeletonize
    from skimage.filters import apply_hysteresis_threshold
    f = ms.WORK / f"{SID}_geo.npz"
    glb = ms.A / "model" / f"{SID}.glb"
    if not f.exists() or (glb.exists() and f.stat().st_mtime < glb.stat().st_mtime):
        print("note: no fresh geometry pass (run `blender -b --factory-startup --python tools/story/sheet_gabriel.py "
              "-- geometry` first): the figure is printed from the ID render alone")
        return None
    g = np.load(f)
    z = g["depth"].astype(np.float64); n = g["normal"].astype(np.float64); al = g["alpha"]
    if al.shape != k.shape or ((al ^ (k > 0)).sum() > 0.004 * al.sum()):
        print("note: the geometry pass does not match the ID render (another build?): not used")
        return None
    regs = sorted({e["region"] for e in ids}); rid = {r: i + 1 for i, r in enumerate(regs)}
    lut = np.zeros(max(int(k.max()), max(e["id"] for e in ids)) + 1, int)
    for e in ids:
        lut[e["id"]] = rid[e["region"]]
    reg = lut[k]
    wing = np.isin(reg, [rid[r] for r in WING_REGIONS if r in rid])
    px = 1.0 / (ms.SH["art"][2] * 2)
    facing = np.clip(-n[..., 1], 0.08, 1.0)
    occ = np.zeros(k.shape, bool); cre = np.zeros(k.shape, bool)
    for ax, comp in ((0, n[..., 2]), (1, n[..., 0])):
        A = (slice(1, None), slice(None)) if ax == 0 else (slice(None), slice(1, None))
        B = (slice(None, -1), slice(None)) if ax == 0 else (slice(None), slice(None, -1))
        same = (reg[A] == reg[B]) & (reg[A] > 0) & (k[A] == k[B])       # piece borders are inked already
        dz = np.abs(z[A] - z[B])
        slope = np.maximum(np.abs(comp[A]) / facing[A], np.abs(comp[B]) / facing[B]) * px
        o = same & (dz > 2.2 * slope + 0.0015)
        c = same & ~o & ((n[A] * n[B]).sum(-1) < math.cos(math.radians(CREASE_DEG)))
        occ[A] |= o; cre[A] |= c
    sx = ndimage.gaussian_filter(np.where(al, n[..., 0], 0.0), 1.6)
    sy = ndimage.gaussian_filter(np.where(al, -n[..., 2], 0.0), 1.6)
    div = np.gradient(sx, axis=1) + np.gradient(sy, axis=0)
    edge = np.zeros(k.shape, bool)
    edge[1:] |= reg[1:] != reg[:-1]; edge[:, 1:] |= reg[:, 1:] != reg[:, :-1]
    away = ndimage.distance_transform_edt(~edge) > 7              # grooves at a region border are that border
    val = apply_hysteresis_threshold(-div, VALLEY[0], VALLEY[1]) & away & (k > 0)
    # broad, soft grooves of the big moulded surfaces (the chest and abdomen of the cuirass): a wider look at the
    # normals, kept only well inside a piece
    sx = ndimage.gaussian_filter(np.where(al, n[..., 0], 0.0), SOFT_SIGMA)
    sy = ndimage.gaussian_filter(np.where(al, -n[..., 2], 0.0), SOFT_SIGMA)
    div2 = np.gradient(sx, axis=1) + np.gradient(sy, axis=0)
    pedge = np.zeros(k.shape, bool)
    pedge[1:] |= k[1:] != k[:-1]; pedge[:, 1:] |= k[:, 1:] != k[:, :-1]
    deep = ndimage.distance_transform_edt(~pedge) > 3 * SOFT_SIGMA
    soft = apply_hysteresis_threshold(-div2, SOFT_VALLEY[0], SOFT_VALLEY[1]) & deep & (k > 0)
    lines = (occ | cre | val | soft) & ~wing
    fx0, fy0, fx1, fy1 = face_rect_2x(rc)
    m = 6
    lines[max(int(fy0) - m, 0):int(fy1) + m, max(int(fx0) - m, 0):int(fx1) + m] = False
    lines = skeletonize(ndimage.binary_closing(lines, structure=np.ones((3, 3), bool)))
    lab, nlab = ndimage.label(lines, structure=np.ones((3, 3), int))
    if nlab:
        size = ndimage.sum(lines, lab, index=np.arange(1, nlab + 1))
        lines &= np.isin(lab, 1 + np.nonzero(size >= MIN_LINE_PX)[0])
    print(f"sculpt lines: {int(occ.sum())} px overlap, {int(cre.sum())} px fold, {int(val.sum())} px groove, {int(soft.sum())} px soft groove -> "
          f"{int(lines.sum())} px of strokes")
    return lines


def patched_inputs():
    """a copy of model/ (symlinks) with the cast inputs rewritten for print (files in model/ are not touched):
      * pieces too thin to colour (feather shafts, straps) become their centre line
      * sculpt_lines(): strokes from the geometry pass
      * part-anchored pieces become detail line art of their target region (as sheet_daniel.py)
    Lines are painted 3 px wide (2x) under one pseudo id per colour region ('<region>~lines', anchoredTo that
    region), which make_sheet's own detail mechanism prints as detail ink and gives back to the region."""
    import shutil
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    from skimage.morphology import skeletonize
    model = ms.MODEL
    rc = json.load(open(model / "regions_characters.json"))
    ct = json.load(open(model / "id_characters_2x.json"))
    tmp = ms.WORK / f"{SID}_model_patched"
    shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    for f in model.iterdir():
        os.symlink(f.resolve(), tmp / f.name)
    n = 0
    for ch, v in rc["characters"].items():
        for key, an in (v.get("partAnchors") or {}).items():
            part, reg = key.split(".", 1)
            tgt = an["target"]
            tch, treg = tgt.split(".", 1)
            treg = "skin" if treg == "FACE" else treg
            pseudo = f"{reg}@{part}"
            hit = [e for e in ct["ids"] if e["char"] == ch and e["part"] == part and e["region"] == reg]
            if not hit:
                continue
            for e in hit:
                e["region"] = pseudo
            base = v["regions"].get(reg, {})
            v["regions"][pseudo] = {"id": base.get("id"), "hex": base.get("hex"), "parts": [part],
                                    "anchoredTo": treg if tch == ch else f"{tch}.{treg}", "anchorUV": an["uv"],
                                    "printNote": "part anchored by the Characters role: printed as detail lines"}
            n += 1
    print(f"part-anchored pieces printed as detail lines: {n}")
    ids = ct["ids"]
    k = decode(Image.open(model / "id_characters_2x.png"))
    byid = {e["id"]: e for e in ids}
    strokes = np.zeros(k.shape, bool)
    hair_ = np.zeros(k.shape, bool)                       # hairlines: painted 1 px wide (feather shafts)
    # ---- pieces too thin to colour -> centre line
    thin = []
    objs = ndimage.find_objects(k, max_label=int(k.max()))
    for i, sl in enumerate(objs, start=1):
        if sl is None or i not in byid:
            continue
        pad = tuple(slice(max(s_.start - 2, 0), s_.stop + 2) for s_ in sl)
        m = k[pad] == i
        if ndimage.distance_transform_edt(m).max() <= THIN_PX:
            (hair_ if byid[i]["region"] in WING_REGIONS else strokes)[pad] |= skeletonize(m)
            thin.append(i)
    if thin:
        gone = np.isin(k, thin)
        keep = (k > 0) & ~gone
        _, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
        k = np.where(gone, k[iy, ix], k)
        print("thin pieces printed as their centre line:",
              sorted({f'{byid[i]["part"]}:{byid[i]["region"]}' for i in thin}), len(thin))
    # ---- lines that follow the sculpt
    sl_ = sculpt_lines(k, ids, rc)
    if sl_ is not None:
        strokes |= sl_
    strokes &= k > 0
    # ---- paint them under '<region>~lines' pseudo ids
    wide = (ndimage.binary_dilation(strokes, structure=np.ones((3, 3), bool)) | hair_) & (k > 0)
    nxt = max(e["id"] for e in ids) + 1
    regions = rc["characters"][SID]["regions"]
    for reg in sorted({e["region"] for e in ids}):
        own = [e["id"] for e in ids if e["region"] == reg and e["char"] == SID]
        m = wide & np.isin(k, own)
        if not m.any() or "@" in reg:
            continue
        pseudo = f"{reg}~lines"
        base = regions.get(reg, {})
        regions[pseudo] = {"id": base.get("id"), "hex": base.get("hex"), "parts": [], "anchoredTo": reg,
                           "printNote": "detail lines inside this region (Set + sheet role, sheet_gabriel.py)"}
        ids.append({"id": nxt, "rgb": [16 + 16 * (nxt % 15), 16 + 16 * ((nxt // 15) % 15), 64 + 64 * (nxt // 225)],
                    "char": SID, "part": "lines", "piece": 0, "region": pseudo, "hex": base.get("hex", "#FFFFFF")})
        k = np.where(m, nxt, k)
        nxt += 1
    (tmp / "id_characters_2x.png").unlink()
    encode(k).save(tmp / "id_characters_2x.png")
    for name, obj in (("regions_characters.json", rc), ("id_characters_2x.json", ct)):
        (tmp / name).unlink()
        json.dump(obj, open(tmp / name, "w"), indent=1, ensure_ascii=False)
    return tmp


def face_guide():
    """the default face decal as a printed guide (as David & Goliath: 'the printed eyes are only a guide'): the dark
    strokes of docs/gabriel/design/faces/gabriel_<default>.png (brows, lash lines, pupils, mouth), at the decal's own
    place. make_sheet prints no face ink, so it is laid over the finished pages; the scan's line erase removes it and
    the 3D face is the decal. Returns the ink coverage (0..1) on the art rectangle at 1x, or None."""
    import numpy as np
    from PIL import Image
    rc = json.load(open(ms.A / "model" / "regions_characters.json"))
    fd = rc["characters"][SID].get("faceDecal")
    if not fd:
        return None
    src = ms.ROOT / fd["files"][fd["default"]]
    if not src.exists():
        print("note: no face decal yet:", src); return None
    AX, AY, AW, AH = ms.SH["art"]
    im = np.asarray(Image.open(src).convert("RGBA")).astype(float) / 255.0
    lum = 0.299 * im[..., 0] + 0.587 * im[..., 1] + 0.114 * im[..., 2]
    dark = ((lum < 0.42) & (im[..., 3] > 0.55)).astype(np.float32)
    x0, y0, x1, y1 = face_rect_2x(rc)
    w, h = int(round(x1 - x0)), int(round(y1 - y0))
    small = np.asarray(Image.fromarray((dark * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)).astype(float) / 255.0
    cov2 = np.zeros((AH * 2, AW * 2), np.float32)
    X, Y = int(round(x0)), int(round(y0))
    cov2[Y:Y + h, X:X + w] = np.clip((small - 0.25) / 0.5, 0, 1)        # crisp edges
    return cov2.reshape(AH, 2, AW, 2).mean(axis=(1, 3))


def overlay_face():
    import numpy as np
    from PIL import Image
    cov = face_guide()
    if cov is None or not cov.any():
        return None
    AX, AY, AW, AH = ms.SH["art"]
    ink = np.array(ms.INK, float)

    def lay(path, art_only):
        im = Image.open(path).convert("RGB")
        a = np.asarray(im).astype(float)
        sub = a if art_only else a[AY:AY + AH, AX:AX + AW]
        sub[:] = sub * (1 - cov[..., None]) + ink * cov[..., None]
        return Image.fromarray(a.round().astype(np.uint8))
    out = ms.OUT
    lay(out / "lineart.png", True).save(out / "lineart.png")
    lay(out / "demo-colored.png", True).save(out / "demo-colored.png")
    lay(out / "demo-sheet.png", False).save(out / "demo-sheet.png")
    page = lay(out / "reference.png", False)
    page.save(out / "reference.png")
    page.save(ms.OUT_ROOT / f"print/{SID}-A4.png")
    page.save(ms.OUT_ROOT / f"print/{SID}-A4.pdf", resolution=ms.SH["dpi"])
    ys, xs = np.nonzero(cov > 0.5)
    return {"inkPx": int((cov > 0.5).sum()), "bboxArtPx": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
            "from": str(json.load(open(ms.A / "model" / "regions_characters.json"))["characters"][SID]["faceDecal"]["default"])}


def region_level_check():
    """every colour region as a child meets it: the largest circle that fits inside the region's outline, ignoring
    the detail lines inside it (feather edges, folds, locks). make_sheet's own numbers (cells between ALL lines) stay
    in checks.json beside it."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    lab = np.asarray(Image.open(ms.OUT / "regions.png")).astype(int)
    ids = json.load(open(ms.OUT / "regions.json"))["ids"]
    key = {}
    for e in ids:
        if e.get("detailOf"):
            continue
        key.setdefault(f'{e["char"]}.{e["region"]}' if e["char"] != "set" else f'set.{e["part"]}:{e["region"]}', []).append(e["id"])
    mm = 25.4 / ms.SH["dpi"]
    out = {}
    d_paper = ndimage.distance_transform_edt(lab > 0)
    for name, lst in key.items():
        m = np.isin(lab, lst)
        if not m.any():
            continue
        sl = ndimage.find_objects(m.astype(int))[0]
        pad = tuple(slice(max(s_.start - 3, 0), s_.stop + 3) for s_ in sl)
        d_in = ndimage.distance_transform_edt(m[pad])             # to the nearest pixel outside the region
        # half an outer line (to paper) or half an inner line (to another region) is ink, the rest is free
        free = np.minimum(d_in - 0.5 - ms.DETAIL_PX / 2, d_paper[pad] - 0.5 - ms.LINE_PX / 2)
        out[name] = round(2 * float(free[m[pad]].max()) * mm, 1)
    return dict(sorted(out.items(), key=lambda kv: kv[1]))


def build():
    model = ms.MODEL
    ms.MODEL = patched_inputs()
    err = None
    try:
        ms.build()
    except SystemExit as e:                               # the files are written before the verdict
        err = e
    finally:
        ms.MODEL = model
    face = overlay_face()
    rl = region_level_check()
    ck = json.load(open(ms.OUT / "checks.json"))
    ck["faceGuide"] = face
    ck["regionInscribedMm(outline only, detail lines ignored)"] = rl
    ck["regionsUnder6mm(outline only)"] = {k_: v for k_, v in rl.items() if v < 6.0}
    json.dump(ck, open(ms.OUT / "checks.json", "w"), indent=1, ensure_ascii=False)
    small = list(rl.items())[:4]
    print("face guide:", face)
    print("smallest colour regions (largest circle inside the outline, mm):", small)
    print("REGIONS", "ALL >= 6 mm" if not ck["regionsUnder6mm(outline only)"] else
          f'UNDER 6 mm: {ck["regionsUnder6mm(outline only)"]}')
    colored_pdf()
    if err is not None:
        raise err


def colored_pdf():
    """the demo-coloured page as an A4 PDF: same pixels-per-inch and page size as print/gabriel-A4.pdf"""
    from PIL import Image
    src = ms.OUT / "demo-sheet.png"
    if not src.exists():
        return
    im = Image.open(src).convert("RGB")
    assert im.size == tuple(ms.SH["page"]), im.size
    dst = ms.OUT_ROOT / f"print/{SID}-A4-colored.pdf"
    im.save(dst, resolution=ms.SH["dpi"])
    print("coloured A4:", dst, "%.2f x %.2f mm" % (im.size[0] / ms.SH["dpi"] * 25.4, im.size[1] / ms.SH["dpi"] * 25.4))


def signature():
    sys.path.insert(0, str(ms.ROOT / "tools"))
    import make_sheet_signatures as sg
    import numpy as np
    mine = (SHEET_NAME, SID, f"assets/{SID}/sheet/reference.png")
    sheets = [s for s in sg.ANGEL + sg.story_sheets() if s[1] != SID] + [mine]

    def ncc(a, b):
        a = a.astype(float) - a.mean(); b = b.astype(float) - b.mean()
        return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
    sigs = {n: sg.signature(p) for n, _, p in sheets}
    me = sigs[SHEET_NAME]
    rows = sorted(((ncc(me, v), n) for n, v in sigs.items() if n != SHEET_NAME), reverse=True)
    for v, n in rows:
        print(f"  {SHEET_NAME} vs {n:22s} NCC {v:.3f}")
    worst_other = max((ncc(sigs[a], sigs[b]), a, b) for i, a in enumerate(sigs) for b in list(sigs)[i + 1:]
                      if a.split("-")[0] != b.split("-")[0] and SHEET_NAME not in (a, b))
    print(f"most similar to {SHEET_NAME}: {rows[0][1]} NCC {rows[0][0]:.3f}; most similar pair among the others: "
          f"{worst_other[1]} / {worst_other[2]} NCC {worst_other[0]:.3f} (a true match is ~0.9)")
    print("SIGNATURE", "DISTINCT" if rows[0][0] < 0.8 else "TOO SIMILAR")
    return rows[0][0]


def geometry_pass():
    """Blender: front-orthographic depth and normal renders of gabriel.glb in rest pose at his sheet slot, the same
    pixels as model/id_characters_2x.png (2x the art rectangle). build() turns them into detail lines that follow
    the sculpt (hair locks, armour plates and muscles, folds, fingers): $STORY_WORK/gabriel_geo.npz (depth = distance from the camera plane at 5, normal in Blender axes)"""
    import bpy
    AX, AY, AW, AH = ms.SH["art"]
    art_h = ms.ART_H
    ch = ms.DESIGN["characters"][SID]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ms.A / "model" / f"{SID}.glb"))
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and (o.parent is None or "trumpet" in o.name or "eyelid" in o.name):
            o.hide_render = True                           # bone shapes, the hidden prop, the lids
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = art_h; cam.data.clip_start = 0.1; cam.data.clip_end = 20
    cam.location = (-ch["sheetX"], -5.0, art_h / 2 - ch["sheetY"]); cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = AW * 2, AH * 2
    sc.render.resolution_percentage = 100
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.film_transparent = True
    sc.render.filter_size = 0.01
    sc.eevee.taa_render_samples = 1
    sc.view_settings.view_transform = 'Raw'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '16'
    sc.world = bpy.data.worlds.new("w")

    def emit(name, build):
        m = bpy.data.materials.new(name)
        try:
            m.use_nodes = True
        except Exception:
            pass
        nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(build(nt), em.inputs["Color"]); nt.links.new(em.outputs[0], out.inputs["Surface"])
        return m

    def depth(nt):
        cd = nt.nodes.new("ShaderNodeCameraData"); mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 4.0; mr.inputs["From Max"].default_value = 6.0
        nt.links.new(cd.outputs["View Z Depth"], mr.inputs["Value"])
        return mr.outputs[0]

    def normal(nt):
        g = nt.nodes.new("ShaderNodeNewGeometry"); ma = nt.nodes.new("ShaderNodeVectorMath"); ma.operation = 'MULTIPLY_ADD'
        ma.inputs[1].default_value = (0.5, 0.5, 0.5); ma.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(g.outputs["Normal"], ma.inputs[0])
        return ma.outputs[0]
    import numpy as np
    ms.WORK.mkdir(parents=True, exist_ok=True)
    got = {}
    for name, fn in (("depth", depth), ("normal", normal)):
        m = emit("geo_" + name, fn)
        for o in bpy.data.objects:
            if o.type == 'MESH':
                o.data.materials.clear(); o.data.materials.append(m)
        path = str(ms.WORK / f"{SID}_geo_{name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path); img.colorspace_settings.name = 'Non-Color'
        a = np.empty(img.size[0] * img.size[1] * 4, np.float32); img.pixels.foreach_get(a)
        got[name] = a.reshape(img.size[1], img.size[0], 4)[::-1]
        os.remove(path)
    np.savez_compressed(ms.WORK / f"{SID}_geo.npz", depth=(got["depth"][..., 0] * 2.0 + 4.0).astype(np.float32),
                        normal=(got["normal"][..., :3] * 2.0 - 1.0).astype(np.float16),
                        alpha=got["depth"][..., 3] > 0.5)
    print("GEOMETRY_OK")


def render():
    """set + Gabriel wearing the demo colouring (lines erased), as make_sheet.render() but with cameras that hold a
    0.62 hero with 1.0 of wings: colours must land on the right parts"""
    import bpy
    import numpy as np
    from mathutils import Vector
    AX, AY, AW, AH = ms.SH["art"]; PW, PH = ms.SH["page"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    ink = os.environ.get("STORY_RENDER_INK") == "1"         # worst case: the printed lines are NOT erased
    fill = bpy.data.images.load(str(ms.OUT / "demo-sheet.png" if ink else ms.WORK / f"{SID}_demo_page_fill.png"))
    sheet = bpy.data.images.load(str(ms.OUT / "demo-sheet.png"))

    def mat(name, img, art_uv=True, rough=0.85):
        m = bpy.data.materials.new(name)
        try:
            m.use_nodes = True
        except Exception:
            pass
        nt = m.node_tree
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
    objs = imp(ms.A / "model" / f"{ms.STORY['set']}.glb")
    roots = {}
    for ch in ms.STORY["cast"]:
        g = ms.A / "model" / f"{ch}.glb"
        if not g.exists():
            print("note: no", g.name, "yet: the set alone"); continue
        new = imp(g); objs += new
        roots[ch] = [(o, o.location.copy(), o.rotation_euler.copy()) for o in new if o.parent is None]
        for o in new:                                    # props hidden until the play shows them
            if "trumpet" in o.name.lower():
                o.hide_render = True
    page_layer = {}
    for o in objs:
        if o.type != 'MESH':
            continue
        if o.data.uv_layers:                             # the page UV = the layer that stays inside 0..1
            best, bi = -1.0, 0
            for i, u in enumerate(o.data.uv_layers):
                a = np.zeros(len(o.data.loops) * 2); u.data.foreach_get("uv", a)
                fr = float(((a >= -1e-4) & (a <= 1 + 1e-4)).mean())
                if fr > best: best, bi = fr, i
            page_layer[o.name] = (bi, [u.name for u in o.data.uv_layers])
            for u in o.data.uv_layers:
                u.name = "uv_tmp_" + u.name
            o.data.uv_layers[bi].name = "UVMap"
        o.data.materials.clear(); o.data.materials.append(m_art)

    def stage(stg):
        for ch, (x, z, y, yaw) in stg.items():
            for o, loc0, rot0 in roots.get(ch, []):
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
    try:
        tm.use_nodes = True
    except Exception:
        pass
    tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.25, 0.17, 1)
    me2.materials.append(tm)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 2.3; sun.data.angle = math.radians(3); sun.data.color = (1.0, 0.94, 0.82)
    sun.rotation_euler = (math.radians(42), math.radians(-22), math.radians(-30))
    sc.world = bpy.data.worlds.new("w")
    try:
        sc.world.use_nodes = True
    except Exception:
        pass
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.95, 0.86, 0.72, 1)
    bg.inputs[1].default_value = 0.55
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    sc.eevee.taa_render_samples = 32
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.01; cam.data.clip_end = 20
    mark = {"gabriel": (0.0, 0.0, 0.0, 0)}                # the sheet pose where he is printed
    stand = {"gabriel": (0.0, 0.02, 0.0, 0)}              # the play's mark
    front = {"gabriel": (0.0, 0.10, 0.0, -18)}
    shots = [("textured_phone", mark, (-0.05, 1.10, 1.65), (-0.02, 0.20, -0.28), 55, (720, 1280)),
             ("textured_phone_play", stand, (-0.05, 1.10, 1.65), (-0.02, 0.20, -0.28), 55, (720, 1280)),
             ("textured_front", mark, (0.0, 0.42, 2.9), (0.0, 0.36, -0.10), 21, (1600, 1100)),
             ("textured_cast", mark, (0.0, 0.42, 2.3), (0.0, 0.41, 0.0), 22, (1600, 1280)),
             ("textured_face", mark, (0.06, 0.56, 0.62), (0.0, 0.50, 0.0), 30, (1200, 1200)),
             ("textured_herald", front, (0.42, 0.34, 1.20), (0.0, 0.33, -0.05), 40, (1280, 900)),
             ("textured_top", stand, (0.50, 1.05, 0.95), (0.0, 0.12, -0.18), 45, (1280, 900))]
    for name, stg, eye, tgt, vfov, res in shots:
        stage(stg)
        e = Vector((eye[0], -eye[2], eye[1])); t = Vector((tgt[0], -tgt[2], tgt[1]))
        cam.location = e; cam.rotation_euler = (t - e).to_track_quat('-Z', 'Y').to_euler()
        cam.data.angle_y = math.radians(vfov)
        sc.render.resolution_x, sc.render.resolution_y = res
        if ink and name not in ("textured_cast", "textured_top"):
            continue
        sc.render.filepath = str((ms.WORK / f"{SID}_{name}_ink.png") if ink else (ms.OUT / f"{name}.png"))
        bpy.ops.render.render(write_still=True)
    print("PAGE_UV_LAYER", json.dumps({k: v for k, v in page_layer.items() if v[0] != 0}))
    print("RENDER_OK")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    setup()
    if argv[:1] == ["render"]:
        render()
    elif argv[:1] == ["geometry"]:
        geometry_pass()
    elif argv[:1] == ["signature"]:
        signature()
    else:
        build()
