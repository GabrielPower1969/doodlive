"""David & Goliath colouring sheet: characters from the Blender ID render + the desert of CONTRACT §12 (Sheet role).

Inputs
  $DG_WORK/id_2x.png + id_2x.json   front-orthographic ID render of both characters in rest pose at their sheet
                                    positions, 2x the art rectangle (written by `pipeline/dg_build.py -- build`)
  assets/david-goliath/design.json  palette, sheet layout, desert.print (shapes + decor in draw order: side-view dunes,
                                    camp hills, tents, banners, rocks, shrub; plan-view brook + stones)
  docs/david-goliath/design/make_design.py      decorative lines + printed faces of the characters (art bible)
  docs/david-goliath/design/ground-mask.png     sand-ground mask of §12.4 (only for the textured renders)
  assets/david-goliath/model/desert_lines.json  constant texels the desert samples (brook bank, banner pole)
  $DG_WORK/desert_id.png (optional) UV-space ID render of the built desert (dg_desert.py), used to check print = 3D

Outputs
  assets/david-goliath/sheet/lineart.png       1000 x 1227 line art = the texture space (UV0) of characters and desert
  assets/david-goliath/sheet/template.json     page / art / markers / markerSize / artPixels (same format as web/assets)
  assets/david-goliath/sheet/demo-colored.png  line art coloured with the design.json palette (exact region fills)
  assets/david-goliath/sheet/demo-sheet.png    the demo colouring on the A4 page (brook strip included)
  assets/david-goliath/sheet/regions.png/.json region id per art pixel (8-bit) + id table (char, part, region, hex)
  assets/david-goliath/sheet/reference.png     AR reference image (= the printable page)
  assets/david-goliath/sheet/checks.json       edge margins, gap, smallest colourable pieces, print-vs-3D desert match
  print/david-goliath-A4.png / .pdf            printable A4 @ 150 dpi
  $DG_WORK/demo_page_fill.png                  demo page with every printed line removed (what the app's line-erase
                                               aims for); texture for the textured renders below
  assets/david-goliath/sheet/ground-mask.png   §12.4 ground mask fitted to this print (Design's mask + sand over every
                                               printed drawing grown 10 px: outline + line-erase band)
  $DG_WORK/ground_demo.png                     §12.4 sand ground baked for the demo page (textured renders only)

Run from the repo root:
  python3 tools/make_dg_sheet.py                                         build the sheet
  blender -b --factory-startup --python tools/make_dg_sheet.py -- render textured renders of characters + desert
      with the demo colouring, from the phone -> assets/david-goliath/sheet/textured_*.png (look: colours must land right)
"""
import json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("DG_WORK", "/tmp/dg_work"))
OUT = ROOT / "assets/david-goliath/sheet"
MODEL = ROOT / "assets/david-goliath/model"
DESIGN = json.load(open(ROOT / "assets/david-goliath/design.json"))
SH = DESIGN["sheet"]
PW, PH = SH["page"]
AX, AY, AW, AH = SH["art"]
ART_H = DESIGN["artHeightUnits"]
SS = 2                                       # everything is drawn at 2x, then averaged down
INK = (0x26, 0x20, 0x19)
LINE_PX = DESIGN["lines"]["outerPx"]         # 4.5 px outlines / region borders
DETAIL_PX = DESIGN["lines"]["detailPx"]      # 3 px decorative lines
MUST_COLOUR = {"stone", "pebbles", "flagIsrael", "flagPhil", "sand", "duneShade", "rock", "hillIsrael", "hillPhil",
               "tentIsrael", "tentPhil", "tentDoor", "water", "bush"}   # regions whose colour is sampled by a constant UV or the desert
DECOR_GAP_PX = 4                             # decorative lines stop >= 4 px inside their region (never split it)


# ============================================================================================ geometry helpers
def P2(x, ys):
    """sheet coords (x centred, ys up from the art-rect bottom) -> 2x page pixel."""
    return ((AX + (x + 0.5) * AW) * SS, (AY + AH - ys * AW) * SS)


def disk(r):
    import numpy as np
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def fill_geom(d, g, val):
    for p in getattr(g, "geoms", [g]):
        if p.is_empty or p.geom_type != "Polygon": continue
        d.polygon([P2(x, y) for x, y in p.exterior.coords], fill=val)
        for h in p.interiors:
            d.polygon([P2(x, y) for x, y in h.coords], fill=0)


def stroke(d, ls, w_px, fill=255):
    for l in getattr(ls, "geoms", [ls]):
        if l.is_empty or l.geom_type != "LineString": continue
        pts = [P2(x, y) for x, y in l.coords]
        wp = max(1, int(round(w_px * SS)))
        d.line(pts, fill=fill, width=wp, joint="curve")
        r = wp / 2
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


# ============================================================================================ build
def decode_ids(img, table):
    import numpy as np
    a = np.asarray(img).astype(int)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    k = np.rint((r - 16) / 16) + 15 * np.rint((g - 16) / 16) + 225 * np.rint((b - 64) / 64)
    k = np.where(al > 127, k, 0).astype(int)
    known = {e["id"] for e in table}
    bad = (k > 0) & ~np.isin(k, list(known))
    if bad.any():
        raise SystemExit(f"ID decode failed on {int(bad.sum())} px (colour management changed?)")
    exp = np.zeros_like(a[..., :3])
    for e in table:
        exp[k == e["id"]] = e["rgb"]
    err = np.abs(exp - a[..., :3]).max(axis=-1)[k > 0]
    return k, int(err.max()) if err.size else 0


def desert_layers():
    """Ordered (part id, kind, region, geom) in print order (later covers earlier), sheet coords, from
    design.json desert.print.shapes (CONTRACT §12.3). Front pieces are side-view drawings (UV0 = front projection),
    brook and stones are plan view below the art rect. The five stones become parts stone1..stone5."""
    from shapely.geometry import Polygon
    kind_of = {p["id"]: p["kind"] for p in DESIGN["desert"]["pieces"]}
    out, nst = [], 0
    for s in DESIGN["desert"]["print"]["shapes"]:
        rings = s["rings"]
        g = Polygon(rings[0], rings[1:]).buffer(0)
        pid = s["piece"]
        if pid == "fiveStones":
            nst += 1; pid = f"stone{nst}"
        out.append((pid, kind_of[s["piece"]], s["region"], g))
    return out


def desert_decor(layers):
    """Detail strokes from design.json desert.print.decor: [(LineString, width_px, is_outline)]. A stroke whose middle
    lies on no printed shape (a banner pole standing on paper) is printed like an outline; the rest are decor and stop
    short of every region border (never split a region)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    allg = unary_union([g for _, _, _, g in layers])
    res = []
    for e in DESIGN["desert"]["print"]["decor"]:
        l = LineString(e["points"])
        res.append((l, e["widthPx"], not allg.contains(l.interpolate(0.5, normalized=True))))
    return res


def value_noise(u, v, seed):
    """smooth value noise in [-1, 1], period 1 (64 x 64 lattice, smoothstep blend) at arrays u, v."""
    import numpy as np
    lat = np.random.default_rng(seed).uniform(-1, 1, (64, 64))
    u, v = u * 64, v * 64
    i0, j0 = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - i0, v - j0
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
    g = lambda i, j: lat[j % 64, i % 64]
    return (g(i0, j0) * (1 - fu) * (1 - fv) + g(i0 + 1, j0) * fu * (1 - fv)
            + g(i0, j0 + 1) * (1 - fu) * fv + g(i0 + 1, j0 + 1) * fu * fv)


def bake_ground(scan, real_page, m):
    """CONTRACT §12.4 sand ground for the demo, baked at page resolution: what the app's ground layer shows (sand
    outside the art rect and on the flat copies of the characters / front pieces; the scan where the child painted
    the ground; the real page through the brook hole). Only for the textured renders; the app runs this as a shader."""
    import numpy as np
    from PIL import Image
    gp = DESIGN["desert"]["ground"]["params"]
    Y, X = np.mgrid[0:PH, 0:PW].astype(float) + 0.5
    x, d = (X - (AX + AW / 2)) / AW, ((AY + AH) - Y) / AW
    n1 = value_noise(x / gp["noisePeriod"], d / gp["noisePeriod"], 1)
    n2 = value_noise(x / gp["patchPeriod"] + 7.3, d / gp["patchPeriod"], 2)
    phi = 2 * np.pi * (d / gp["rippleWavelength"] + gp["rippleWarpAmp"] * np.sin(2 * np.pi * x / gp["rippleWarpPeriod"])
                       + gp["rippleNoiseAmp"] * n1)
    h = gp["sand"].lstrip("#"); base = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)
    sand = base * (1 + gp["rippleContrast"] * np.sin(phi) + gp["patchContrast"] * n2)[..., None]
    sc = scan / 255.0
    t = np.clip((sc.min(axis=-1) - gp["paperLo"]) / (gp["paperHi"] - gp["paperLo"]), 0, 1); paper = t * t * (3 - 2 * t)
    out = np.where((m < 64)[..., None], sand, scan * (1 - paper[..., None]) + sand * paper[..., None])
    out = np.where((m > 191)[..., None], real_page, out)
    return Image.fromarray(np.clip(out, 0, 255).round().astype(np.uint8))


def byname(ids, i):
    e = next(x for x in ids if x["id"] == i)
    return f'{e["char"]}.{e["part"]}:{e["region"]}'


def build():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage
    sys.dont_write_bytecode = True                 # no __pycache__ in the Design role's folder
    sys.path.insert(0, str(ROOT / "docs/david-goliath/design"))
    import make_design as md                       # noqa: E402

    table = json.load(open(WORK / "id_2x.json"))
    ids = table["ids"]
    clab, err = decode_ids(Image.open(WORK / "id_2x.png").convert("RGBA"), ids)
    assert clab.shape == (AH * SS, AW * SS), clab.shape
    H2, W2 = PH * SS, PW * SS
    lab = np.zeros((H2, W2), np.int32)             # page-wide label map at 2x (characters + desert + brook)
    lab[AY * SS:(AY + AH) * SS, AX * SS:(AX + AW) * SS] = clab
    char_mask = lab > 0

    # ---- desert regions (side-view front pieces + plan-view brook/stones), print order, never over a character
    layers = desert_layers()
    pal_d = DESIGN["palette"]["desert"]
    next_id = max(e["id"] for e in ids) + 1
    clash = 0
    for pid, kind, region, g in layers:
        m = Image.new("L", (W2, H2), 0); fill_geom(ImageDraw.Draw(m), g, 255)
        mm = np.asarray(m) > 127
        clash += int((mm & char_mask).sum())
        mm &= ~char_mask
        lab[mm] = next_id
        hx = pal_d[region]
        ids.append({"id": next_id, "rgb": None, "char": "desert", "part": pid, "piece": 0, "region": region, "hex": hx,
                    "kind": kind, **({"pageOnly": True} if kind in ("water", "stones") else {})})
        next_id += 1
    if next_id > 255:
        raise SystemExit(f"{next_id} region ids do not fit regions.png (8-bit)")

    # ---- decorative strokes (independent of the region map): characters (art bible) + desert
    fD, _, _ = md.build_david(); fG, *_ = md.build_goliath()
    cD, cG = DESIGN["characters"]["david"], DESIGN["characters"]["goliath"]
    fD = fD.translate(cD["sheetX"], cD.get("sheetY", 0.0)); fG = fG.translate(cG["sheetX"], cG.get("sheetY", 0.0))
    decor = Image.new("L", (W2, H2), 0); dd = ImageDraw.Draw(decor)
    for f in (fD, fG):
        for ls, w, _ in f.decor:
            stroke(dd, ls, w * 1000)
    outl = Image.new("L", (W2, H2), 0); do = ImageDraw.Draw(outl)
    for ls, wpx, is_outline in desert_decor(layers):
        stroke(do if is_outline else dd, ls, wpx)
    face = Image.new("L", (W2, H2), 0); dfc = ImageDraw.Draw(face)
    for f in (fD, fG):
        for ls, w in f.face: stroke(dfc, ls, w * 1000)
        for g in f.ink: fill_geom(dfc, g, 255)
    decor0, face0, outl0 = np.asarray(decor) > 127, np.asarray(face) > 127, np.asarray(outl) > 127
    r_out = int(round(LINE_PX * SS / 2)) - 1                      # silhouette against paper: ~4.5 px
    r_in = int(round(DETAIL_PX * SS / 2)) - 1                     # border between two regions: ~3 px (detail weight)

    thin_ids = [e["id"] for e in ids if e["char"] == "david" and e["region"] == "stone"]

    def ink(lab):
        """2x ink mask for a region map: outer outlines, thinner inner borders, decor kept off every border."""
        e_any = np.zeros_like(lab, bool); e_out = np.zeros_like(lab, bool)
        for ax in (0, 1):
            a_, b_ = (lab[1:, :], lab[:-1, :]) if ax == 0 else (lab[:, 1:], lab[:, :-1])
            ch = a_ != b_; po = ch & ((a_ == 0) | (b_ == 0))
            for m_, tgt in ((ch, e_any), (po, e_out)):
                if ax == 0: tgt[1:, :] |= m_; tgt[:-1, :] |= m_
                else: tgt[:, 1:] |= m_; tgt[:, :-1] |= m_
        thin = np.isin(lab, thin_ids)
        e_thin = e_any & ndimage.binary_dilation(thin, iterations=2) & ~e_out
        line2 = (ndimage.binary_dilation(e_out, structure=disk(r_out)) | ndimage.binary_dilation(e_any & ~e_thin, structure=disk(r_in))
                 | ndimage.binary_dilation(e_thin, structure=disk(1)))     # ~2 px ring round tiny must-colour parts
        dist_edge = ndimage.distance_transform_edt(~e_any) / SS    # 1x px to the nearest region border
        d2 = decor0 & (dist_edge >= (LINE_PX / 2 + DECOR_GAP_PX))  # never touch a border: a region is never split
        dl, dn = ndimage.label(d2)                                  # drop stubs that the masking cut off
        if dn:
            ar = ndimage.sum(d2, dl, index=np.arange(1, dn + 1))
            d2 &= np.isin(dl, 1 + np.nonzero(ar >= 120)[0])
        all2 = line2 | d2 | (face0 & (dist_edge >= LINE_PX / 2 + 1)) | outl0
        hl, hn = ndimage.label(~all2)                               # pin-holes inside thick ink -> ink
        if hn:
            ar = ndimage.sum(~all2, hl, index=np.arange(1, hn + 1))
            all2 |= np.isin(hl, 1 + np.nonzero(ar < 60)[0])
        return all2

    # ---- merge parts that the ink would swallow into a touching part of the same colour region (ear -> face,
    # boot trim -> boot, strap -> bag): the line between them goes, the part stays colourable and keeps its colour
    regname = {e["id"]: (e["char"], e["region"]) for e in ids}
    merged = []
    for _ in range(4):
        all2 = ink(lab)
        free = ~all2
        dt = ndimage.distance_transform_edt(free) * 2 / SS          # 1x px inscribed diameter at each pixel
        cell = ndimage.maximum(dt, lab, index=np.arange(next_id + 1))
        present = np.bincount(lab.ravel(), minlength=next_id + 1) > 0
        weak = [i for i in range(1, next_id + 1) if present[i] and cell[i] < 6.5]
        changed = False
        for i in weak:
            m = lab == i
            ring = ndimage.binary_dilation(m, structure=disk(3)) & ~m
            nb = lab[ring]; nb = nb[(nb > 0) & (nb != i)]
            same = [j for j in np.unique(nb) if regname.get(int(j)) == regname[i]]
            if not same: continue
            j = max(same, key=lambda j: int((nb == j).sum()))
            lab[m] = j; merged.append((byname(ids, i), byname(ids, int(j)))); changed = True
        if not changed: break

    def down(a):
        return a.reshape(PH, SS, PW, SS, *a.shape[2:]).mean(axis=(1, 3))
    a1 = down(all2.astype(float))                                 # 1x ink coverage over the whole page
    pl, pn = ndimage.label(a1 < 0.5)
    if pn:
        areas = ndimage.sum(a1 < 0.5, pl, index=np.arange(1, pn + 1))
        a1[np.isin(pl, 1 + np.nonzero(areas < 12)[0])] = 1.0
    ink_page = 255.0 * (1 - a1[..., None]) + np.array(INK) * a1[..., None]   # white page + ink
    art_sl = (slice(AY, AY + AH), slice(AX, AX + AW))
    lineart = Image.fromarray(ink_page[art_sl].round().astype(np.uint8))
    OUT.mkdir(parents=True, exist_ok=True)
    lineart.save(OUT / "lineart.png")

    # ---- demo colouring (exact region fills, multiplied by the ink)
    lut = np.full((next_id + 1, 3), 255.0)
    for e in ids:
        h = e["hex"].lstrip("#"); lut[e["id"]] = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    fill1 = down(lut[lab])                                        # 1x colour fills, no ink
    demo_page = fill1 * (ink_page / 255.0)
    # erased-page texture: like the app's line-erase, the outline band takes the colour of the region it borders
    dpaper, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True)
    lab_grow = np.where((lab == 0) & (dpaper <= 6 * SS), lab[iy, ix], lab)
    fill_grow = down(lut[lab_grow])
    demo_img = Image.fromarray(demo_page[art_sl].round().astype(np.uint8)); demo_img.save(OUT / "demo-colored.png")
    WORK.mkdir(parents=True, exist_ok=True)
    Image.fromarray(fill_grow.round().astype(np.uint8)).save(WORK / "demo_page_fill.png")

    # ---- regions at 1x (nearest), id table
    lab1p = lab[SS // 2::SS, SS // 2::SS]
    lab1 = lab1p[art_sl]
    Image.fromarray(lab1.astype(np.uint8)).save(OUT / "regions.png")
    json.dump({"note": "regions.png pixel value = id (0 = paper), same pixels as lineart.png. Characters: rest pose, front "
                       "orthographic (UV0 front projection). char 'desert': side-view front pieces (UV0 front projection, "
                       "scale/sheetY per design.json desert.pieces[].frontUV, CONTRACT §12.1); 'part' = desert.glb node id "
                       "(stone1..5 = fiveStones). pageOnly = brook and stones, printed in plan view below the art rect, so "
                       "not in regions.png. Region 'tentDoor' = the doorway recess in each tent gable.",
               "ids": [{k: v for k, v in e.items() if k != "rgb"} for e in ids]}, open(OUT / "regions.json", "w"), indent=1)

    # ---- page
    sys.path.insert(0, str(ROOT / "tools")); from tianzige import draw_title
    t = SH["title"]

    def page_with(rgb_page):
        page = Image.fromarray(rgb_page.round().astype(np.uint8))
        d = ImageDraw.Draw(page); ms = SH["markerSize"]
        for cx, cy in SH["markers"]:
            d.rectangle((cx - ms // 2, cy - ms // 2, cx + ms // 2 - 1, cy + ms // 2 - 1), fill="black")
        draw_title(page, t["hanzi"], t["english"], cy=t["cy"], box=t["box"], gap=t["gap"], label=t["label"], pinyin=t["pinyin"])
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
    page.save(ROOT / "print/david-goliath-A4.png")
    page.save(ROOT / "print/david-goliath-A4.pdf", resolution=150)
    page.save(OUT / "reference.png")
    demo_sheet = page_with(demo_page); demo_sheet.save(OUT / "demo-sheet.png")
    # §12.4 ground mask fitted to this print: Design's mask, plus sand (0) over every printed character / front-piece
    # drawing grown by its outline and the line-erase band (10 px), so no erased-outline colour leaks onto the ground
    gm = np.array(Image.open(ROOT / DESIGN["desert"]["ground"]["maskPng"]).convert("L").resize((PW, PH), Image.NEAREST))
    flat_ids = [e["id"] for e in ids if e["char"] != "desert" or e.get("kind") not in ("water", "stones")]
    flat = ndimage.binary_dilation(np.isin(lab1p, flat_ids), structure=disk(10))
    leak_before = int((flat & (gm == 128)).sum())
    gm = np.where(flat & (gm < 192), 0, gm).astype(np.uint8)
    Image.fromarray(gm).save(OUT / "ground-mask.png")
    bake_ground(fill_grow, np.asarray(demo_sheet.convert("RGB")).astype(float), gm).save(WORK / "ground_demo.png")
    json.dump({"page": [PW, PH], "art": [AX, AY, AW, AH], "markers": SH["markers"], "markerSize": SH["markerSize"],
               "artPixels": [AW, AH]}, open(OUT / "template.json", "w"), indent=1)

    # ============================================================================ checks
    checks = {"idDecodeMaxErr": err, "desertOverCharacterPx2x": clash, "mergedIntoSameColourNeighbour": merged,
              "groundMaskPxFixed(design mask 128 -> 0 near printed drawings)": leak_before}
    byid = {e["id"]: e for e in ids}
    charmap = np.zeros(next_id + 1, dtype=int)
    for e in ids:
        charmap[e["id"]] = {"david": 1, "goliath": 2, "desert": 3}.get(e["char"], 0)
    who = charmap[lab1]
    for c, n in (("david", 1), ("goliath", 2)):
        ys, xs = np.nonzero(who == n)
        x0, x1 = xs.min() / AW - 0.5, (xs.max() + 1) / AW - 0.5
        y0, y1 = ART_H - (ys.max() + 1) / AW, ART_H - ys.min() / AW
        rect = [AX + int(xs.min()), AY + int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
        want = SH["figureRectsPx"][c]
        checks[c] = {"boundsUnits": [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)],
                     "marginToArtEdge": round(min(x0 + 0.5, 0.5 - x1, ART_H - y1), 4), "marginToArtBottom": round(y0, 4),
                     "rectPx": rect, "designRectPx": want, "rectDiffPx": int(max(abs(a - b) for a, b in zip(rect, want)))}
    checks["gapDavidGoliath"] = round(float(ndimage.distance_transform_edt(who != 1)[who == 2].min() / AW), 4)
    dchar = ndimage.distance_transform_edt(~((who == 1) | (who == 2)))
    checks["desertToCharacterMinPx"] = round(float(dchar[who == 3].min()), 1) if (who == 3).any() else None

    # colourable pieces over the art rect + the brook strip (1x)
    bx, by, bw, bh = DESIGN["desert"]["brookStripPx"]
    x0c, y0c, x1c, y1c = min(AX, bx) - 8, AY - 8, max(AX + AW, bx + bw) + 8, min(PH, max(AY + AH, by + bh) + 8)
    crop = (slice(y0c, y1c), slice(x0c, x1c))
    paper = a1[crop] < 0.5
    labc = lab1p[crop]
    comp, n = ndimage.label(paper)
    dt = ndimage.distance_transform_edt(paper)
    inscribed = ndimage.maximum(dt, comp, index=np.arange(1, n + 1)) * 2
    areas = ndimage.sum(paper, comp, index=np.arange(1, n + 1))
    pieces = []
    for i, dia in enumerate(inscribed, start=1):
        m = comp == i
        h = labc[m]
        if (h == 0).mean() > 0.5:
            continue                                               # paper / background, not a colourable region
        top = int(np.bincount(h[h > 0]).argmax())
        e = byid[top]
        pieces.append((round(float(dia), 1), int(areas[i - 1]), f'{e["char"]}.{e["part"]}:{e["region"]}'))
    pieces.sort()
    checks["pieces"] = len(pieces)
    best = {}
    for p_ in pieces: best[p_[2]] = max(best.get(p_[2], 0), p_[0])
    checks["slivers(<6px)"] = [p for p in pieces if p[0] < 6 and best[p[2]] < 6]      # the region's best cell is tiny
    checks["thinStrips(<6px, region has a bigger cell)"] = [p for p in pieces if p[0] < 6 and best[p[2]] >= 6]
    checks["small(6-10px)"] = [p for p in pieces if 6 <= p[0] < 10]
    checks["smallestTen"] = pieces[:10]
    # every region id must keep at least one colourable cell (else a region vanished under the ink)
    seen = {p[2] for p in pieces}
    still = set(np.unique(lab).tolist())
    lost = sorted({f'{e["char"]}.{e["part"]}:{e["region"]}' for e in ids if e["id"] in still} - seen)
    checks["regionsWithoutColourableCell"] = lost
    edge_ink = {"bottom": int((a1[art_sl][-6:, :] > 0.5).sum()), "top": int((a1[art_sl][:6, :] > 0.5).sum()),
                "left": int((a1[art_sl][:, :6] > 0.5).sum()), "right": int((a1[art_sl][:, -6:] > 0.5).sum())}
    checks["inkWithin6pxOfArtEdge"] = edge_ink
    checks["brookInkToPageBottomPx"] = int(PH - 1 - np.nonzero((a1[:, bx:bx + bw] > 0.5).any(axis=1))[0].max())

    # constant-UV samples used by desert.glb must sit on clean colour, away from ink
    dink = ndimage.distance_transform_edt(a1[art_sl] < 0.5)
    uvs = json.load(open(MODEL / "desert_lines.json"))["uv"]
    samples = {"sandBank": (uvs["sandBankUV"], "sand"), "stone": (DESIGN["desert"]["stoneUV"], "stone"),
               "pole": (uvs["poleUV"], "spearShaft")}
    us = {}
    for k, (uv, want) in samples.items():
        px, py = int(uv[0] * AW), int((1 - uv[1]) * AH)
        e = byid.get(int(lab1[py, px]))
        us[k] = {"uv": [round(uv[0], 4), round(uv[1], 4)], "region": e["region"] if e else "paper", "want": want,
                 "inkDistPx": round(float(dink[py, px]), 1), "ok": bool(e and e["region"] == want and dink[py, px] >= 3)}
    checks["constantUVSamples"] = us

    # print vs built 3D: desert_id.png = every front piece drawn in UV0 space (page frame), layered in print order
    # (dg_desert.py). precision = share of the texels a piece samples that lie on that piece's printed drawing or on
    # a printed border band (the colour lands on the right part); coverage = share of the printed drawing it samples (< 1: UV inset 0.004).
    prec = {}
    if (WORK / "desert_id.png").exists():
        dj = json.load(open(WORK / "desert_id.json"))
        dimg = np.asarray(Image.open(WORK / "desert_id.png").convert("RGBA")).astype(int)
        q = lambda v, o, st: np.clip(np.rint((v - o) / st), 0, None)
        k3 = q(dimg[..., 0], 16, 16) + 15 * q(dimg[..., 1], 16, 16) + 225 * q(dimg[..., 2], 64, 64)
        k3 = np.where(dimg[..., 3] > 127, k3, 0).astype(int)
        part1 = np.array([byid[i]["part"] if i in byid and byid[i]["char"] == "desert" else "" for i in range(next_id + 1)])[lab1p]
        # The 3D UVs sit 0.004 (4 px) inside every drawing, so in this UV-space render a piece further back shows
        # through a 4 px band along the outline of the piece printed over it (e.g. duneFar along the hill edges).
        # In 3D that band is hidden behind the front piece, so texels within 5 px of a printed border do not count.
        edge = np.zeros_like(lab1p, bool)
        edge[1:, :] |= lab1p[1:, :] != lab1p[:-1, :]; edge[:, 1:] |= lab1p[:, 1:] != lab1p[:, :-1]
        core = ndimage.distance_transform_edt(~edge) >= 5
        cov = {}
        for pid, e in dj["ids"].items():
            if pid in ("brook", "fiveStones"):
                continue                                           # water film / constant texel: checked elsewhere
            a = k3 == e["id"]; b = part1 == pid
            if a.sum():
                prec[pid] = round(float(1 - (a & ~b & core).sum() / a.sum()), 3)
                cov[pid] = round(float((a & b).sum() / max(1, b.sum())), 3)
        checks["desertPrintVs3D_precision"] = prec
        checks["desertPrintVs3D_coverage"] = cov
        checks["desertPrintVs3D_minPrecision"] = min(prec.values()) if prec else None

    # every ink except the four markers >= 6 mm (35.4 px) from every page edge (CONTRACT §12.3)
    pg = np.asarray(page.convert("RGB")).astype(int).min(axis=-1) < 200
    ms = SH["markerSize"]
    for cx, cy in SH["markers"]:
        pg[max(0, cy - ms // 2 - 3):cy + ms // 2 + 3, max(0, cx - ms // 2 - 3):cx + ms // 2 + 3] = False
    ys_, xs_ = np.nonzero(pg)
    page_m = {"left": int(xs_.min()), "right": int(PW - 1 - xs_.max()), "top": int(ys_.min()), "bottom": int(PH - 1 - ys_.max())}
    checks["inkToPageEdgePx(excl. markers)"] = page_m
    checks["inkToPageEdgeMinMm"] = round(min(page_m.values()) / SH["dpi"] * 25.4, 2)
    json.dump(checks, open(OUT / "checks.json", "w"), indent=1)
    fails = []
    if any(edge_ink.values()): fails.append(f"line art touches the art-rect edge: {edge_ink}")
    if checks["slivers(<6px)"]: fails.append(f"slivers: {checks['slivers(<6px)']}")
    must = [x for x in lost if x.split(":")[1] in MUST_COLOUR]   # tiny trims (sandal straps) may print as solid ink
    if must: fails.append(f"regions without a colourable cell: {must}")
    if clash: fails.append(f"desert overlaps a character drawing ({clash} px)")
    if not all(v["ok"] for v in us.values()): fails.append(f"constant-UV sample on ink or wrong region: {us}")
    if min(page_m.values()) < 35.4: fails.append(f"ink closer than 6 mm to the page edge: {page_m}")
    bad = {k: v for k, v in prec.items() if v < 0.97}
    if bad: fails.append(f"desert 3D samples off its printed drawing: {bad}")
    print(json.dumps({k: v for k, v in checks.items() if k not in ("smallestTen",)}, indent=1))
    if fails:
        raise SystemExit("SHEET FAIL: " + "; ".join(fails))
    print("SHEET PASS")


# ============================================================================================ textured renders (Blender)
def render():
    """Characters + desert wearing the demo colouring (line-erased page) on the §12.4 sand ground, seen from the
    DGPreview phone view and three more. Proof that every colour lands on the right 3D part."""
    import bpy
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    fill = bpy.data.images.load(str(WORK / "demo_page_fill.png"))
    ground = bpy.data.images.load(str(WORK / "ground_demo.png"))

    def mat(name, img, art_uv=True, rough=0.85):
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
        b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = rough
        try: b.inputs["Specular IOR Level"].default_value = 0.2
        except KeyError: pass
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.extension = 'EXTEND'
        tex.interpolation = 'Closest' if art_uv else 'Linear'
        if art_uv:                                  # art-rect UV -> page image UV (image origin bottom-left)
            uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Location"].default_value = (AX / PW, (PH - AY - AH) / PH, 0)
            mp.inputs["Scale"].default_value = (AW / PW, AH / PH, 1)
            nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], tex.inputs[0])
        nt.links.new(tex.outputs[0], b.inputs["Base Color"])
        return m
    m_art = mat("art", fill)
    water = bpy.data.materials.new("water"); water.use_nodes = True
    wb = water.node_tree.nodes["Principled BSDF"]
    wb.inputs["Base Color"].default_value = (0.6, 0.85, 1.0, 1); wb.inputs["Roughness"].default_value = 0.05
    wb.inputs["Alpha"].default_value = 0.25
    try: water.surface_render_method = 'BLENDED'
    except Exception: water.blend_method = 'BLEND'

    def imp(path):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        return [o for o in bpy.data.objects if o not in before]
    objs = imp(MODEL / "desert.glb")
    roots = {}
    for ch in ("david", "goliath"):
        new = imp(MODEL / f"{ch}.glb"); objs += new
        roots[ch] = [(o, o.location.copy(), o.rotation_euler.copy()) for o in new if o.parent is None]
    for o in objs:
        if o.type != 'MESH': continue
        for s_ in o.material_slots or []:
            s_.material = water if (s_.material and s_.material.name.startswith("dg_water")) else m_art
        if not o.material_slots: o.data.materials.append(m_art)

    def stage(st):                                  # {char: (x, z, yaw deg)} in page coords (+z toward the viewer)
        for ch, (x, z, yaw) in st.items():
            for o, loc0, rot0 in roots[ch]:
                o.rotation_mode = 'XYZ'
                o.location = (loc0.x + x, loc0.y - z, loc0.z); o.rotation_euler = (rot0.x, rot0.y, rot0.z + math.radians(yaw))
    # the page = §12.4 sand ground baked for the demo page (whole A4, brook hole shows the real page)
    x0, x1 = -AX / AW - 0.5, (PW - AX) / AW - 0.5
    y1, y0 = (AY + AH) / AW, (AY + AH - PH) / AW
    me = bpy.data.meshes.new("paper"); me.from_pydata([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], [], [(0, 1, 2, 3)])
    lay = me.uv_layers.new(name="UVMap")
    for li, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]): lay.data[li].uv = uv
    paper = bpy.data.objects.new("paper", me); sc.collection.objects.link(paper)
    me.materials.append(mat("paper", ground, art_uv=False, rough=0.95))
    me2 = bpy.data.meshes.new("table"); me2.from_pydata([(-3, -3, -0.002), (3, -3, -0.002), (3, 4, -0.002), (-3, 4, -0.002)], [], [(0, 1, 2, 3)])
    tb = bpy.data.objects.new("table", me2); sc.collection.objects.link(tb)
    tm = bpy.data.materials.new("table"); tm.use_nodes = True
    tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.25, 0.17, 1); me2.materials.append(tm)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 3.2; sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(42), math.radians(-22), math.radians(-30))
    sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.82, 0.86, 0.93, 1); bg.inputs[1].default_value = 0.85
    sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    try: sc.eevee.taa_render_samples = 32
    except Exception: pass
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.01; cam.data.clip_end = 20
    marks = {c: (DESIGN["characters"][c]["sheetX"], 0.0, 0) for c in ("david", "goliath")}   # opening: on the sheet marks
    play = {"david": (-0.30, 0.10, 35), "goliath": (0.22, -0.25, -35)}                       # Design's mock pose
    # (name, stage, eye, target, vfov, res): page coords (x, y up, z toward the viewer); phone = DGPreview phone view
    shots = [("textured_phone", marks, (-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280)),
             ("textured_phone_play", play, (-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280)),
             ("textured_right", play, (0.30, 0.90, 1.10), (0.10, 0.08, -0.55), 55, (720, 1280)),
             ("textured_low", play, (0.15, 0.30, 0.95), (-0.05, 0.18, -0.30), 45, (1280, 720)),
             ("textured_camps", play, (0.0, 0.62, -0.42), (0.0, 0.33, -1.25), 50, (1280, 720)),
             ("textured_brook", play, (-0.25, 0.30, 0.45), (-0.40, 0.0, 0.11), 40, (1200, 900))]
    for name, st, eye, tgt, vfov, res in shots:
        stage(st)
        e = Vector((eye[0], -eye[2], eye[1])); t = Vector((tgt[0], -tgt[2], tgt[1]))
        cam.location = e; cam.rotation_euler = (t - e).to_track_quat('-Z', 'Y').to_euler()
        cam.data.angle_y = math.radians(vfov)
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.filepath = str(OUT / f"{name}.png"); bpy.ops.render.render(write_still=True)
    print("RENDER_OK")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv[:1] == ["render"]:
        render()
    else:
        build()
