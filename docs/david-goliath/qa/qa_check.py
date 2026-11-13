#!/usr/bin/env python3
"""Independent QA checks for the David & Goliath production (QA role).

Run from the repo root:  python3 docs/david-goliath/qa/qa_check.py
Prints one PASS/FAIL/WARN line per check plus evidence, writes qa/qa_results.json.
Reads only; never modifies another role's files.
"""
import json, os, re, struct, subprocess, sys, glob, hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
os.chdir(ROOT)
A = "assets/david-goliath"
U = "unity/Assets/DoodLive/DavidGoliath"
results = []

def rec(check, status, evidence):
    results.append({"check": check, "status": status, "evidence": evidence})
    print(f"[{status}] {check}\n    " + "\n    ".join(evidence if isinstance(evidence, list) else [evidence]))

def ffdur(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=sample_rate,channels,codec_name,bit_rate",
                          "-of", "json", p], capture_output=True, text=True).stdout
    j = json.loads(out); s = j["streams"][0]
    return float(j["format"]["duration"]), int(s["sample_rate"]), int(s["channels"]), s["codec_name"], s.get("bit_rate")

def glb_json(p):
    b = open(p, "rb").read()
    magic, ver, length = struct.unpack_from("<III", b, 0)
    assert magic == 0x46546C67, p
    clen, ctype = struct.unpack_from("<II", b, 12)
    return json.loads(b[20:20 + clen])

# ------------------------------------------------------------------ contract constants (CONTRACT §3, §5)
BASE_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
              "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
              "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR"]
PARENT = {"hips": "root", "spine": "hips", "chest": "spine", "neck": "chest", "head": "neck", "jaw": "head",
          "shoulderL": "chest", "upperArmL": "shoulderL", "forearmL": "upperArmL", "handL": "forearmL",
          "shoulderR": "chest", "upperArmR": "shoulderR", "forearmR": "upperArmR", "handR": "forearmR",
          "thighL": "hips", "shinL": "thighL", "footL": "shinL", "toeL": "footL",
          "thighR": "hips", "shinR": "thighR", "footR": "shinR", "toeR": "footR"}
EXTRA = {"david": {"slingCord1": "handR", "slingCord2": "slingCord1", "slingPouch": "slingCord2", "stone": "root"},
         "goliath": {"spear": "handR", "shield": "handL", "helmet": "head"}}
# CONTRACT §11.6: six finger bones on both characters (fingers + thumb children of hand, fingerTips child of fingers)
FINGERS = {f"{b}{s}": p.format(s=s) for s in "LR" for b, p in (("fingers", "hand{s}"), ("fingerTips", "fingers{s}"), ("thumb", "hand{s}"))}
for _c in EXTRA: EXTRA[_c].update(FINGERS)
CLIPS = {"david": ["idle", "walk", "talk", "kneel_pick", "sling_windup", "sling_release", "run", "victory", "pray"],
         "goliath": ["idle", "walk", "talk", "taunt", "laugh", "roar", "charge", "hit_react", "fall", "down"]}

# ------------------------------------------------------------------ 1. timeline validity
tl = json.load(open(f"{A}/timeline.json"))
ev, bad = [], []
D = tl["duration"]
ev.append(f"version={tl['version']} duration={D} fps={tl['fps']} shots={len(tl['shots'])} acting={len(tl['acting'])} "
          f"lines={len(tl['lines'])} fx={len(tl['fx'])} sfx={len(tl['sfx'])} music={len(tl['music'])} requestedClips={tl['requestedClips']}")
if not (60 <= D <= 90): bad.append(f"duration {D} outside 60-90 (CONTRACT §0 'about 60-90 s')")
sh = tl["shots"]; prev = 0.0
for s in sh:
    if abs(s["t0"] - prev) > 1e-6: bad.append(f"shot {s['id']} t0={s['t0']} != prev t1 {prev}")
    prev = s["t1"]
    for k in ["title_zh", "title_en", "camera", "desc"]:
        if k not in s: bad.append(f"shot {s['id']} missing {k}")
    c = s.get("camera", {})
    if c.get("type") not in ("orbit", "fixed", "follow"): bad.append(f"shot {s['id']} camera.type {c.get('type')}")
    if c.get("target") not in ("david", "goliath", "both", "stone"): bad.append(f"shot {s['id']} camera.target {c.get('target')}")
if abs(prev - D) > 1e-6: bad.append(f"last shot ends {prev} != duration {D}")
for key in ["acting", "lines", "fx", "sfx", "music"]:
    ts = [e["t"] for e in tl[key]]
    if ts != sorted(ts): bad.append(f"{key} not sorted by t")
    if any(t < 0 or t > D for t in ts): bad.append(f"{key} has t outside [0,{D}]")
faces = set()
for e in tl["acting"]:
    if e["who"] not in CLIPS: bad.append(f"acting who={e['who']}"); continue
    if e["clip"] not in CLIPS[e["who"]]: bad.append(f"acting {e['t']} {e['who']} clip {e['clip']} not in CONTRACT §5")
    if "face" in e: faces.add(e["face"])
    # paper edge (template.json page/art): z = 0 is the art bottom, the page reaches +0.244 toward the viewer;
    # keep the feet 0.024 inside it (CONTRACT §10 D8)
    if "to" in e and (abs(e["to"][0]) > 0.5 or not (-1.486 <= e["to"][1] <= 0.22)):
        bad.append(f"acting {e['t']} {e['who']} to {e['to']} leaves the paper (|x| <= 0.5, z in [-1.486, 0.22])")
used = {(e["who"], e["clip"]) for e in tl["acting"]}
unused = [f"{c}_{k}" for c in CLIPS for k in CLIPS[c] if (c, k) not in used]
ev.append(f"face values used: {sorted(faces)} (CONTRACT §6 example only shows 'david'; 'viewer' is a Story extension)")
ev.append(f"contract clips never used by timeline: {unused or 'none'}")
for f in tl["fx"]:
    who, _, bone = f["at"].partition(".")
    ok = bone in BASE_BONES or bone in EXTRA.get(who, {})
    if not ok: bad.append(f"fx {f['id']} at {f['at']}: bone not in CONTRACT §3")
ids = [l["id"] for l in tl["lines"]]
if len(set(ids)) != len(ids): bad.append("duplicate line ids")
for l in tl["lines"]:
    if l["who"] not in ("narrator", "david", "goliath", "saul", "soldiers"): bad.append(f"{l['id']} who {l['who']}")
    if re.search(r"[,.!?;:]", l["zh"]): bad.append(f"{l['id']} zh has half-width punctuation: {l['zh']}")
    for k in ("zh", "en", "maxSec", "ref"):
        if not l.get(k): bad.append(f"{l['id']} missing {k}")
rec("T1 timeline.json schema and consistency (CONTRACT §6)", "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 2. referenced ids exist
ev, bad = [], []
fxsrc = "".join(open(p).read() for p in glob.glob(f"{U}/Fx/*.cs"))
fx_impl = set(re.findall(r'Id\s*=>\s*"([a-z_]+)"', fxsrc))
fx_used = {f["id"] for f in tl["fx"]}
ev.append(f"fx ids used {len(fx_used)}, implemented (Id => \"...\") {len(fx_impl)}; missing={sorted(fx_used - fx_impl) or 'none'} extra={sorted(fx_impl - fx_used) or 'none'}")
bad += [f"fx {i} has no handler" for i in fx_used - fx_impl]
for kind, key, d in (("sfx", "id", "sfx"), ("music", "cue", "music")):
    used_ids = sorted({e[key] for e in tl[kind]})
    miss = []
    for i in used_ids:
        for ext in ("wav", "mp3"):
            if not os.path.isfile(f"{A}/audio/{d}/{i}.{ext}"): miss.append(f"{A}/audio/{d}/{i}.{ext}")
        if not os.path.isfile(f"{U}/Resources/DG/{d}/{i}.wav"): miss.append(f"{U}/Resources/DG/{d}/{i}.wav (Unity copy)")
    ev.append(f"{kind}: {len(used_ids)} ids, missing files: {miss or 'none'}")
    bad += miss
rec("T2 every fx / sfx / music id in timeline has a handler or file (source + Unity Resources)", "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 3. voice
ev, bad, warn = [], [], []
durj = json.load(open(f"{A}/audio/voice/durations.json"))
lines = tl["lines"]; rows = []
for lang in ("zh", "en"):
    for i, l in enumerate(lines):
        p = f"{A}/audio/voice/{lang}/{l['id']}.wav"
        if not os.path.isfile(p): bad.append(f"missing {p}"); continue
        if not os.path.isfile(p[:-4] + ".mp3"): bad.append(f"missing {p[:-4]}.mp3")
        if not os.path.isfile(f"{U}/Resources/DG/voice/{lang}/{l['id']}.wav"): bad.append(f"missing Unity copy {lang}/{l['id']}")
        else:
            h1 = hashlib.md5(open(p, "rb").read()).hexdigest(); h2 = hashlib.md5(open(f"{U}/Resources/DG/voice/{lang}/{l['id']}.wav", "rb").read()).hexdigest()
            if h1 != h2: bad.append(f"Unity copy of {lang}/{l['id']} differs from source (stale Setup?)")
        d, sr, ch, codec, _ = ffdur(p)
        if (sr, ch, codec) != (44100, 1, "pcm_s16le"): bad.append(f"{p}: {sr} Hz {ch} ch {codec}")
        nxt = lines[i + 1]["t"] if i + 1 < len(lines) else D
        end = l["t"] + d; slack_max = l["maxSec"] - d; gap = nxt - end
        if abs(durj[lang][l["id"]] - d) > 0.02: bad.append(f"durations.json {lang}/{l['id']}={durj[lang][l['id']]} vs ffprobe {d:.3f}")
        if d > l["maxSec"] + 1e-3: bad.append(f"{lang}/{l['id']} {d:.2f}s > maxSec {l['maxSec']}")
        if gap < 0.2 - 1e-3: bad.append(f"{lang}/{l['id']} ends {end:.2f}, next line {nxt}: gap {gap:.2f} < 0.2")
        rows.append((lang, l["id"], d, l["maxSec"], slack_max, gap))
tight = sorted(rows, key=lambda r: min(r[4], r[5]))[:5]
ev.append("tightest (lang id dur maxSec slack gapToNext): " + "; ".join(f"{r[0]} {r[1]} {r[2]:.2f}/{r[3]} {r[4]:+.2f} {r[5]:.2f}" for r in tight))
ev.append(f"checked {len(rows)} clips with ffprobe (not durations.json)")
# srt
for lang in ("zh", "en"):
    n = open(f"{A}/audio/voice/{lang}.srt", encoding="utf-8").read().count("-->")
    ev.append(f"{lang}.srt cues: {n}")
    if n != len(lines): bad.append(f"{lang}.srt has {n} cues, expected {len(lines)}")
rec("T3 every voice line exists in zh AND en (wav+mp3+Unity copy) and fits maxSec and the 0.2 s gap", "FAIL" if bad else "PASS", ev + bad)

# loudness of voice (ebur128) — spot all
ev, bad = [], []
def lufs(p):
    e = subprocess.run(["ffmpeg", "-nostats", "-i", p, "-filter_complex", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    return I, TP
vl = [lufs(f"{A}/audio/voice/{lang}/{l['id']}.wav") for lang in ("zh", "en") for l in lines]
ev.append(f"voice integrated LUFS min {min(v[0] for v in vl)} max {max(v[0] for v in vl)}; true peak max {max(v[1] for v in vl)} dBTP (target -16)")
if any(abs(v[0] + 16) > 1.0 for v in vl): bad.append("a voice clip is more than 1 LU from -16")
ml = {c: lufs(f"{A}/audio/music/{c}.wav") for c in sorted({m['cue'] for m in tl['music']})}
ev.append("music LUFS: " + ", ".join(f"{k} {v[0]}" for k, v in ml.items()) + " (target -20)")
if any(abs(v[0] + 20) > 1.0 for v in ml.values()): bad.append("a music cue is more than 1 LU from -20")
rec("T4 audio loudness vs CONTRACT §7 (voice -16 LUFS, music -20 LUFS)", "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 5. GLB bones
ev, bad = [], []
for src in ("model", "anim"):
    for c in ("david", "goliath"):
        p = f"{A}/{src}/{c}.glb"; j = glb_json(p)
        nodes = j["nodes"]
        joints = set()
        for s in j.get("skins", []): joints |= set(s["joints"])
        names = {nodes[i]["name"] for i in joints}
        parent = {}
        for i, n in enumerate(nodes):
            for ch in n.get("children", []): parent[nodes[ch]["name"]] = n["name"]
        want = set(BASE_BONES) | set(EXTRA[c])
        # root may be a node but not a skin joint; check node names too
        allnames = {n["name"] for n in nodes}
        missing = sorted(want - allnames)
        extra = sorted(names - want)
        wrongp = [f"{b}<-{parent.get(b)} (want {pp})" for b, pp in {**PARENT, **EXTRA[c]}.items() if b in allnames and parent.get(b) != pp]
        nwant = {"david": 33, "goliath": 32}[c]
        if len(joints) != nwant: bad.append(f"{p}: {len(joints)} joints, CONTRACT §11.6 says {nwant}")
        ev.append(f"{p}: {len(j.get('skins', []))} skin(s), {len(joints)} joints; missing={missing or 'none'}; extra joints={extra or 'none'}; parent mismatches={wrongp or 'none'}")
        if missing or extra or wrongp: bad.append(f"{p} bone set/hierarchy differs from CONTRACT §3")
rec("T5 bone names + hierarchy in model and anim GLBs equal CONTRACT §3 + §11.6 finger bones (David 33, Goliath 32)", "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 6. clips
ev, bad = [], []
for c in ("david", "goliath"):
    for p in (f"{A}/anim/{c}.glb", f"{U}/Models/{c}.glb"):
        j = glb_json(p); an = sorted(a["name"] for a in j.get("animations", []))
        want = sorted(f"{c}_{k}" for k in CLIPS[c])
        miss = sorted(set(want) - set(an)); extra = sorted(set(an) - set(want))
        ev.append(f"{p}: {len(an)} animations; missing={miss or 'none'} extra={extra or 'none'}")
        if miss: bad.append(f"{p} missing {miss}")
    h1 = hashlib.md5(open(f"{A}/anim/{c}.glb", "rb").read()).hexdigest(); h2 = hashlib.md5(open(f"{U}/Models/{c}.glb", "rb").read()).hexdigest()
    ev.append(f"{c}.glb Unity copy identical to assets/anim: {h1 == h2}")
    if h1 != h2: bad.append(f"Unity Models/{c}.glb is stale vs assets/anim")
h1 = hashlib.md5(open(f"{A}/model/desert.glb", "rb").read()).hexdigest(); h2 = hashlib.md5(open(f"{U}/Models/desert.glb", "rb").read()).hexdigest() if os.path.isfile(f"{U}/Models/desert.glb") else None
ev.append(f"desert.glb Unity copy identical to assets/model: {h1 == h2}")
if h1 != h2: bad.append("Unity Models/desert.glb missing or stale vs assets/model/desert.glb")
rec("T6 every CONTRACT §5 clip exists as an animation in the anim GLBs (and the Unity copies)", "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 7. template vs PNG
from PIL import Image
import numpy as np
ev, bad = [], []
T = json.load(open(f"{A}/sheet/template.json"))
for p in ("print/david-goliath-A4.png", f"{A}/sheet/reference.png", f"{A}/sheet/demo-sheet.png", f"{U}/Tracking/david-goliath-A4.png"):
    if not os.path.isfile(p): bad.append(f"missing {p}"); continue
    im = np.asarray(Image.open(p).convert("L")).astype(float)
    H, W = im.shape
    sx, sy = W / T["page"][0], H / T["page"][1]
    errs = []
    for (mx, my) in T["markers"]:
        cx, cy = mx * sx, my * sy; r = int(T["markerSize"] * sx * 0.9)
        win = im[int(cy - r):int(cy + r), int(cx - r):int(cx + r)]
        ys, xs = np.nonzero(win < 100)
        if len(xs) == 0: errs.append(None); continue
        # bbox centre of dark pixels in window
        bx = (xs.min() + xs.max()) / 2 + int(cx - r); by = (ys.min() + ys.max()) / 2 + int(cy - r)
        bw = (xs.max() - xs.min() + 1) / sx
        errs.append((float(round((bx - cx) / sx, 1)), float(round((by - cy) / sy, 1)), float(round(bw, 1))))
    ev.append(f"{p} {W}x{H}: marker (dx,dy,size) in template px = {errs}")
    if any(e is None or abs(e[0]) > 3 or abs(e[1]) > 3 or abs(e[2] - T['markerSize']) > 4 for e in errs): bad.append(f"{p}: marker off >3 px or wrong size")
    # art rect: inside should contain ink, border line? report darkness along art rect edges
    ax, ay, aw, ah = T["art"]
    ev.append(f"  art rect {T['art']} aspect {ah/aw:.4f}; ink fraction inside art {float((im[int(ay*sy):int((ay+ah)*sy), int(ax*sx):int((ax+aw)*sx)] < 128).mean()):.3f}")
angel = json.load(open("web/assets/template.json"))
same = all(angel[k] == T[k] for k in ("page", "art", "markers", "markerSize"))
ev.append(f"same page/art/markers as web/assets/template.json (angel): {same}")
if not same: bad.append("D&G template differs from angel template (capture reuse assumes equal)")
ev.append(f"Unity Data/template.json identical: {open(f'{U}/Data/template.json').read() == open(f'{A}/sheet/template.json').read()}")
rec("T7 sheet template.json consistent with the sheet PNGs (markers where they say)", "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 8. Unity references + copies
ev, bad = [], []
for src, dst in ((f"{A}/timeline.json", f"{U}/Resources/DG/timeline.json"), (f"{A}/audio/sfx/mix.json", f"{U}/Resources/DG/sfx_mix.json"),
                 (f"{A}/audio/music/cues.json", f"{U}/Resources/DG/music_cues.json"), (f"{A}/anim/clips.json", f"{U}/Data/clips.json"),
                 (f"{A}/design.json", f"{U}/Data/design.json"), ("print/david-goliath-A4.png", f"{U}/Tracking/david-goliath-A4.png"),
                 (f"{A}/sheet/reference.png", "print/david-goliath-A4.png"),
                 (f"{A}/sheet/demo-colored.png", f"{U}/Textures/dg-demo-colored.png"), (f"{A}/sheet/demo-sheet.png", f"{U}/Textures/dg-demo-sheet.png"),
                 (f"{A}/sheet/ground-mask.png", f"{U}/Textures/dg-ground-mask.png"),          # §12.4 (Sheet's fitted mask)
                 (f"{U}/Shaders/DGGround.shader", None),
                 ("unity/Assets/DoodLive/DavidGoliath/Fx/Resources/DGFx/DGFxUnlit.shader", None)):
    if not os.path.isfile(src): bad.append(f"missing {src}"); continue
    if dst is None: ev.append(f"{src} exists"); continue
    if not os.path.isfile(dst): bad.append(f"missing {dst}"); continue
    same = hashlib.md5(open(src, "rb").read()).hexdigest() == hashlib.md5(open(dst, "rb").read()).hexdigest()
    ev.append(f"{dst} == {src}: {same}")
    if not same: bad.append(f"{dst} stale vs {src}")
faces_needed = set()
dj = json.load(open(f"{A}/design.json"))
for c, fd in dj["faceDecals"].items():
    if not isinstance(fd, dict): continue
    for clip, ex in fd.get("clipExpression", {}).items():
        faces_needed.add(f"{c}_{ex}")
miss = [f for f in sorted(faces_needed) if not os.path.isfile(f"{U}/Faces/{f}.png")]
ev.append(f"face decals referenced by design.json clipExpression: {len(faces_needed)}; missing in Unity Faces/: {miss or 'none'}")
bad += miss
ref = open("unity/Assets/DoodLive/Tracking/ReferenceImages.asset").read()
ev.append(f"ReferenceImages.asset mentions david-goliath: {'david-goliath' in ref}; entries (m_Name lines): {len(re.findall(r'm_Name: ', ref)) - 1}")
rec("T8 files referenced by DGDirector / DGSetup exist and the Unity copies match their sources", "FAIL" if bad else "PASS", ev + bad)

json.dump(results, open(os.path.join(os.path.dirname(__file__), "qa_results.json"), "w"), indent=1, ensure_ascii=False)

# ------------------------------------------------------------------ 9. independent UV check (CONTRACT §4 / CLAUDE.md invariant 1)
def accessor(j, b, idx):
    a = j["accessors"][idx]; bv = j["bufferViews"][a["bufferView"]]
    comp = {"VEC2": 2, "VEC3": 3, "SCALAR": 1, "VEC4": 4}[a["type"]]
    dt = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}[a["componentType"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0) or comp * np.dtype(dt).itemsize
    raw = np.frombuffer(b, dtype=np.uint8, count=a["count"] * stride, offset=off).reshape(a["count"], stride)
    return raw[:, :comp * np.dtype(dt).itemsize].copy().view(dt).reshape(a["count"], comp).astype(float)
ev, bad = [], []
ASPECT = T["art"][3] / T["art"][2]
for c in ("david", "goliath"):
    p = f"{A}/model/{c}.glb"; raw = open(p, "rb").read(); j = glb_json(p)
    clen = struct.unpack_from("<I", raw, 12)[0]; boff = 20 + clen + 8; bin_ = raw[boff:]
    worst = []
    for mi, m in enumerate(j["meshes"]):
        for pr in m["primitives"]:
            at = pr["attributes"]
            if "TEXCOORD_0" not in at: worst.append((m.get("name"), "no UV0")); continue
            P = accessor(j, bin_, at["POSITION"]); UV = accessor(j, bin_, at["TEXCOORD_0"])
            # glTF v is top-down: v_gl = 1 - v.  The character file is centred on its own origin; its sheet x
            # (design.json) is a constant u offset, so fit it and report the residual spread.
            sy = dj["characters"][c].get("sheetY", 0.0)    # drawing lifted off the art bottom edge (CONTRACT §10 D4)
            off = UV[:, 0] - (P[:, 0] + 0.5); o = float(np.median(off))
            du = np.abs(off - o); dv = np.abs(UV[:, 1] - (1 - (P[:, 1] + sy) / ASPECT))
            worst.append((m.get("name"), float(du.max()), float(dv.max()), o))
    # node transforms: meshes must be at identity (else positions are not world)
    nonid = [n["name"] for n in j["nodes"] if "mesh" in n and any(k in n for k in ("translation", "rotation", "scale"))]
    mx = max((w[1] for w in worst if len(w) == 4), default=1); mv = max((w[2] for w in worst if len(w) == 4), default=1)
    ev.append(f"{p}: {len(worst)} primitives; u offset (= sheet x) per mesh {[round(w[3],4) for w in worst]}; residual max |du| = {mx:.4f}, max |dv| = {mv:.4f} "
              f"(1 unit = 1000 px, so {mx*1000:.1f} / {mv*1000:.1f} px); mesh nodes with own TRS: {nonid or 'none'}")
    sx_design = dj["characters"][c].get("sheetX", dj["characters"][c].get("sheet", {}).get("x")) if isinstance(dj["characters"][c], dict) else None
    ev.append(f"  design.json sheet x, y for {c}: {sx_design}, {dj['characters'][c].get('sheetY', 0.0)}")
    if mx > 0.01 or mv > 0.01: bad.append(f"{p}: UV0 deviates from page projection by > 0.01 (10 px)")
    offs = [w[3] for w in worst if len(w) == 4]
    if sx_design is not None and offs and max(abs(o - sx_design) for o in offs) > 0.002:
        bad.append(f"{p}: UV0 u offset {sorted(set(round(o, 4) for o in offs))} != design.json sheetX {sx_design} (CONTRACT §11.4)")
rec("T9 UV0 = front orthographic page projection (independent recomputation from GLB vertices)", "FAIL" if bad else ("WARN" if not ev else "PASS"), ev + bad)
json.dump(results, open(os.path.join(os.path.dirname(__file__), "qa_results.json"), "w"), indent=1, ensure_ascii=False)

# ------------------------------------------------------------------ 10. printed sheet: every region closed (QA T8b)
from PIL import Image as _Image
ev, bad = [], []
ax, ay, aw, ah = T["art"]
for pth in ("print/david-goliath-A4.png", "assets/david-goliath/sheet/reference.png"):
    g = np.asarray(_Image.open(pth).convert("L"))[ay:ay + ah, ax:ax + aw]
    ink = g < 128
    rows = np.nonzero(ink.any(axis=1))[0]; cols = np.nonzero(ink.any(axis=0))[0]
    m = {"bottom": int(ah - 1 - rows.max()), "top": int(rows.min()), "left": int(cols.min()), "right": int(aw - 1 - cols.max())}
    ev.append(f"{pth}: paper between the line art and the art-rect edge (px): {m}")
    if min(m.values()) < 6: bad.append(f"{pth}: line art within 6 px of the art-rect edge {m} (an outline cut by the edge leaves a region open)")
ck = json.load(open("assets/david-goliath/sheet/checks.json"))
ev.append(f"sheet/checks.json inkWithin6pxOfArtEdge = {ck.get('inkWithin6pxOfArtEdge')}, closed pieces = {ck.get('pieces')}")
rec("T10 printed sheet: line art keeps >= 6 px from the art-rect edge (every region closed)", "FAIL" if bad else "PASS", ev + bad)
json.dump(results, open(os.path.join(os.path.dirname(__file__), "qa_results.json"), "w"), indent=1, ensure_ascii=False)

# ================================================================== redraw checks (CONTRACT §11, 2026-10-27)
import math, calendar, time, zipfile
from scipy import ndimage
QA = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get("DG_WORK", "/tmp/dg_work")
PAPER_ACT = (-0.596, 0.596, -1.486, 0.22)          # D8: actors (x min/max, z min/max)
PAGE_EDGE_Z = (T["page"][1] - T["art"][1] - T["art"][3]) / T["art"][2]   # page front edge, art units (0.244)
PAPER_SET = (-0.596, 0.596, -1.486, PAGE_EDGE_Z)  # desert: zone B may reach the physical page edge (§11.9)
desert = dj["desert"]

def glb_bin(p):
    raw = open(p, "rb").read(); clen = struct.unpack_from("<I", raw, 12)[0]
    return glb_json(p), raw[20 + clen + 8:]

def tri_count(p):
    j = glb_json(p); n = 0; per = {}
    for nd in j["nodes"]:
        if "mesh" not in nd: continue
        t = 0
        for pr in j["meshes"][nd["mesh"]]["primitives"]:
            mode = pr.get("mode", 4)
            cnt = j["accessors"][pr["indices"]]["count"] if "indices" in pr else j["accessors"][pr["attributes"]["POSITION"]]["count"]
            t += cnt // 3 if mode == 4 else 0
        per[nd["name"]] = t; n += t
    return n, per

# ------------------------------------------------------------------ 11. triangle budgets (§11.5, §12.2: desert <= 20,000)
ev, bad = [], []
DESERT_TRIS = desert.get("budget", {}).get("maxTris", 20000)
for p, lim in ((f"{A}/model/david.glb", 20000), (f"{A}/model/goliath.glb", 20000), (f"{A}/anim/david.glb", 20000),
               (f"{A}/anim/goliath.glb", 20000), (f"{A}/model/desert.glb", DESERT_TRIS)):
    n, per = tri_count(p)
    big = sorted(per.items(), key=lambda kv: -kv[1])[:4]
    ev.append(f"{p}: {n:,} triangles (limit {lim:,}); largest nodes {big}")
    if n > lim: bad.append(f"{p}: {n} > {lim}")
    j = glb_json(p); mats = [m["name"] for m in j.get("materials", [])]
    ev.append(f"  materials {mats}")
rec(f"T11 triangle budgets: characters <= 20,000 each, desert <= {DESERT_TRIS:,} (CONTRACT §11.5, §12.2)", "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 12. stage band: all parts (§12.6) vs recomputed; marks / paths inside
def in_poly(poly, x, y):
    c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
ev, bad = [], []
from shapely.geometry import Point as _P, LineString as _L, Polygon as _Poly
from shapely.ops import unary_union as _union
sb = desert["stageBand"]
if "polygonSheet" in sb: bad.append("design.json desert.stageBand still has the removed single 'polygonSheet' field (§12.6)")
bands = sb.get("polygonsSheet", [])
_dband = _union([_Poly(b).buffer(0) for b in bands]) if bands else _Poly()
_R = {"david": 0.075, "goliath": 0.170}
_pp = {c: (dj["characters"][c]["sheetX"], 0.0) for c in _R}; _parts = [_P(_pp[c][0], 0).buffer(_R[c], 32) for c in _R]
for e in tl["acting"]:
    if "to" in e:
        a, b = _pp[e["who"]], tuple(e["to"]); _parts.append(_L([(a[0], -a[1]), (b[0], -b[1])]).buffer(_R[e["who"]], 32)); _pp[e["who"]] = b
QA_BAND = _union(_parts)
_geoms = list(getattr(QA_BAND, "geoms", [QA_BAND]))
miss_area = QA_BAND.difference(_dband.buffer(0.005)).area
ev.append(f"design.json polygonsSheet: {len(bands)} part(s) ({[len(b) for b in bands]} points), union area {_dband.area:.4f}; "
          f"recomputed band (§11.9 rule): {len(_geoms)} part(s), area {QA_BAND.area:.4f}; recomputed area not covered by design: {miss_area:.4f}")
if len(bands) < len(_geoms): bad.append(f"design.json has {len(bands)} stage-band parts, the timeline needs {len(_geoms)}")
if miss_area > 0.002: bad.append(f"{miss_area:.4f} units² of the recomputed stage band is missing from design.json polygonsSheet")
pos = {"david": (dj["characters"]["david"]["sheetX"], 0.0), "goliath": (dj["characters"]["goliath"]["sheetX"], 0.0)}
checked = 0
for c, p0 in pos.items():
    if not _dband.buffer(1e-6).contains(_P(p0[0], -p0[1])): bad.append(f"{c} start mark {p0} outside the design stage band")
    checked += 1
for e in tl["acting"]:
    if "to" not in e: continue
    a = pos[e["who"]]; b = tuple(e["to"])
    L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(2, int(L / 0.005))
    outs = [(round(a[0] + (b[0] - a[0]) * k / n, 3), round(a[1] + (b[1] - a[1]) * k / n, 3)) for k in range(n + 1)
            if not _dband.buffer(1e-6).contains(_P(a[0] + (b[0] - a[0]) * k / n, -(a[1] + (b[1] - a[1]) * k / n)))]
    checked += n + 1
    if outs: bad.append(f"t {e['t']} {e['who']} {e['clip']} {a} -> {b}: {len(outs)} path samples outside the band, e.g. {outs[:3]}")
    pos[e["who"]] = b
ev.append(f"{checked} start marks / targets / path samples tested against the union of polygonsSheet; final marks: {pos}")
rec("T12 stage band: design.json polygonsSheet has every part (§12.6), matches the recomputed band, every mark / path inside it",
    "FAIL" if bad else "PASS", ev + bad)

# ------------------------------------------------------------------ 13. actors on the paper + never inside the desert, every frame
EVAL = f"{WORK}/qa/blender_eval.json"; EVALZ = f"{WORK}/qa/blender_eval.npz"
srcs = [f"{A}/anim/david.glb", f"{A}/anim/goliath.glb", f"{A}/model/desert.glb", f"{A}/design.json", os.path.join(QA, "qa_blender_eval.py")]
if not os.path.isfile(EVALZ) or os.path.getmtime(EVAL) < max(os.path.getmtime(s_) for s_ in srcs):
    print("    (running headless Blender: qa_blender_eval.py)", flush=True)
    r = subprocess.run(["blender", "-b", "--factory-startup", "--python", os.path.join(QA, "qa_blender_eval.py"), "--", EVAL],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(EVALZ): print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit("qa_blender_eval.py failed")
BE = json.load(open(EVAL)); BZ = np.load(EVALZ)
HF, HX, HZ = BZ["heightField"], BZ["heightFieldX"], BZ["heightFieldZ"]
def hf_at(x, z):
    ix = np.clip(np.round((x - HX[0]) / (HX[1] - HX[0])).astype(int), 0, len(HX) - 1)
    iz = np.clip(np.round((z - HZ[0]) / (HZ[1] - HZ[0])).astype(int), 0, len(HZ) - 1)
    return HF[iz, ix]
clipsj = json.load(open(f"{A}/anim/clips.json"))
LOOP = {x["action"]: x["loop"] for x in clipsj["clips"]}
NAT = {"david_walk": 0.129, "david_run": 0.328, "goliath_walk": 0.071, "goliath_charge": 0.125}   # DGAnimFacts (DGTimeline.cs)
FPS = 30

def frame_idx(ch, clip, t):
    n = len(BE["characters"][ch]["clips"][f"{ch}_{clip}"]["frames"]) - 1
    k = t * FPS
    k = k % n if LOOP[f"{ch}_{clip}"] else min(k, n)
    return int(round(k)) % (n + 1)

class Actor:
    def __init__(s, x): s.pos = [x, 0.0]; s.yaw = 0.0; s.face = "viewer"; s.cur = "idle"; s.t0 = 0.0; s.rate = 1.0; s.prev = None; s.moving = False
acts = {c: Actor(dj["characters"][c]["sheetX"]) for c in ("david", "goliath")}
ev, bad = [], []
worst = {c: {"xmin": (9, 0), "xmax": (-9, 0), "zmin": (9, 0), "zmax": (-9, 0), "ymin": (9, 0)} for c in acts}
viol, gviol, mviol, bviol = [], [], [], []
pen = {c: (0.0, None) for c in acts}; pen_list = []
_aw = T["art"][2]
PAGE = (-0.5 - T["art"][0] / _aw, 0.5 + (T["page"][0] - T["art"][0] - _aw) / _aw, -(T["art"][1] + T["art"][3]) / _aw, PAGE_EDGE_Z)
acting = tl["acting"]; ia = 0; dt = 1.0 / FPS; now = 0.0; nframes = 0
while now <= D + 1e-6:
    while ia < len(acting) and acting[ia]["t"] <= now + 1e-4:
        e = acting[ia]; A_ = acts[e["who"]]
        keep = e["clip"] == A_.cur and LOOP[f"{e['who']}_{e['clip']}"]
        if not keep:
            A_.prev = (A_.cur, A_.t0, A_.rate, e["t"], max(0.01, e.get("blend", 0.25))); A_.cur = e["clip"]; A_.t0 = e["t"]
        A_.rate = 1.0
        if e.get("face"): A_.face = e["face"]
        A_.moving = False
        if "to" in e:
            t1 = next((x["t"] for x in acting[ia + 1:] if x["who"] == e["who"]), D)
            A_.mf, A_.mt, A_.m0, A_.m1 = list(A_.pos), list(e["to"]), e["t"], max(e["t"] + 0.05, t1)
            d_ = math.hypot(A_.mt[0] - A_.mf[0], A_.mt[1] - A_.mf[1])
            A_.moving = d_ > 1e-4
            k_ = f"{e['who']}_{e['clip']}"
            if A_.moving and k_ in NAT: A_.rate = min(1.5, max(0.5, d_ / (A_.m1 - A_.m0) / NAT[k_]))
        ia += 1
    for c, A_ in acts.items():
        trav = False
        if A_.moving:
            s_ = min(1, max(0, (now - A_.m0) / (A_.m1 - A_.m0)))
            A_.pos = [A_.mf[0] + (A_.mt[0] - A_.mf[0]) * s_, A_.mf[1] + (A_.mt[1] - A_.mf[1]) * s_]
            trav = s_ < 1
            if not trav: A_.moving = False
        if trav: want = math.degrees(math.atan2(A_.mt[0] - A_.mf[0], A_.mt[1] - A_.mf[1]))
        else:
            o = acts.get(A_.face)
            want = math.degrees(math.atan2(o.pos[0] - A_.pos[0], o.pos[1] - A_.pos[1])) if o and o is not A_ else 0.0
        k_ = 1.0 if now <= 0 else 1 - math.exp(-dt / 0.12)
        dlt = (want - A_.yaw + 180) % 360 - 180; A_.yaw += dlt * k_
    for c, A_ in acts.items():
        poses = [((A_.cur, (now - A_.t0) * A_.rate), True)]
        if A_.prev and now < A_.prev[3] + A_.prev[4]:
            wnew = (now - A_.prev[3]) / A_.prev[4]
            poses = [(poses[0][0], wnew >= 0.5), ((A_.prev[0], (now - A_.prev[1]) * A_.prev[2]), wnew < 0.5)]
        th = math.radians(A_.yaw); cs, sn = math.cos(th), math.sin(th)
        for (clip, tt), major in poses:
            fi = frame_idx(c, clip, tt); f = BE["characters"][c]["clips"][f"{c}_{clip}"]["frames"][fi]
            H = np.array(f["hull"]); X = A_.pos[0] + H[:, 0] * cs + H[:, 1] * sn; Z = A_.pos[1] - H[:, 0] * sn + H[:, 1] * cs
            w = worst[c]
            for key, val, better in (("xmin", X.min(), lambda a, b: a < b), ("xmax", X.max(), lambda a, b: a > b),
                                     ("zmin", Z.min(), lambda a, b: a < b), ("zmax", Z.max(), lambda a, b: a > b), ("ymin", f["minY"], lambda a, b: a < b)):
                if better(val, w[key][0]): w[key] = (round(float(val), 4), round(now, 2), clip)
            if X.min() < PAGE[0] or X.max() > PAGE[1] or Z.min() < PAGE[2] or Z.max() > PAGE[3]:
                viol.append((round(now, 2), c, clip, round(float(X.min()), 3), round(float(X.max()), 3), round(float(Z.min()), 3), round(float(Z.max()), 3)))
            if f["lowHull"]:
                Hl = np.array(f["lowHull"]); Xl = A_.pos[0] + Hl[:, 0] * cs + Hl[:, 1] * sn; Zl = A_.pos[1] - Hl[:, 0] * sn + Hl[:, 1] * cs
                if Xl.min() < PAGE[0] or Xl.max() > PAGE[1] or Zl.min() < PAGE[2] or Zl.max() > PAGE[3]:
                    (gviol if major else bviol).append((round(now, 2), c, clip, round(float(Zl.max()), 3)))
                elif Xl.min() < PAPER_ACT[0] or Xl.max() > PAPER_ACT[1] or Zl.min() < PAPER_ACT[2] or Zl.max() > PAPER_ACT[3]:
                    mviol.append((round(now, 2), c, clip, round(float(Zl.max()), 3)))
            if major:   # body vs desert: evaluated vertex subsample under the desert's top surface (ray-cast height field)
                Pp = BZ[f"{c}_{clip}__pts"][fi]
                Xp = A_.pos[0] + Pp[:, 0] * cs + Pp[:, 2] * sn; Zp = A_.pos[1] - Pp[:, 0] * sn + Pp[:, 2] * cs
                Hd = hf_at(Xp, Zp); dep = np.where(Hd > 0.010, Hd - Pp[:, 1], 0.0)
                k = int(np.argmax(dep)); dmax = float(dep[k])
                if dmax > pen[c][0]: pen[c] = (round(dmax, 4), (round(now, 2), clip, round(float(Xp[k]), 3), round(float(Zp[k]), 3), round(float(Pp[k, 1]), 3)))
                if dmax > 0.008: pen_list.append((round(now, 2), c, clip, round(dmax, 3), round(float(Xp[k]), 3), round(float(Zp[k]), 3)))
    nframes += 1
    now += dt
ev.append(f"simulated DGDirector placement at {FPS} fps over 0-{D} s ({nframes} frames; pos lerp, yaw LerpAngle tau 0.12 s, rate = "
          f"travel/natural clamped 0.5-1.5, cross-fade = both clips); per frame the convex hull (x, z) of ALL evaluated vertices, and "
          f"<= 600 evaluated vertices tested against the desert top surface (ray-cast height field, 0.004 grid) from {EVALZ}")
for c, w in worst.items(): ev.append(f"{c} extremes (value, t, clip): {w}")
ev.append(f"deepest actor vertex under the desert surface (depth, (t, clip, x, z, y)): {pen}")
ev.append(f"limits: D8 paper margin x {PAPER_ACT[0]}..{PAPER_ACT[1]}, z {PAPER_ACT[2]}..{PAPER_ACT[3]}; physical sheet "
          f"x {PAGE[0]:.3f}..{PAGE[1]:.3f}, z {PAGE[2]:.3f}..{PAGE[3]:.3f}")
def _first(vs, key=lambda v: (v[1], v[2])):
    fr_ = {}
    for v in vs: fr_.setdefault(key(v), v)
    return list(fr_.values())[:8]
warn_ = []
if gviol and len(gviol) <= 2 and max(v[3] for v in gviol) <= PAGE[3] + 0.010:
    warn_.append(f"{len(gviol)} frame(s) clip the sheet edge by <= 0.010 (t, who, clip, zmax): {_first(gviol)}"); gviol = []
if gviol: bad.append(f"{len(gviol)} actor-frames put a foot / knee / body ON the table past the sheet edge; first per clip (t, who, clip, zmax): {_first(gviol)}")
if mviol: warn_.append(f"{len(mviol)} actor-frames rest inside the 0.024 D8 margin but on the sheet (t, who, clip, zmax): {_first(mviol)}")
if bviol: warn_.append(f"{len(bviol)} cross-fade frames where the fading-out clip alone would touch the table past the edge (t, who, clip, zmax): {_first(bviol)}")
if viol: warn_.append(f"{len(viol)} actor-frames have a raised part overhanging the sheet edge in the air; first per clip "
                      f"(t, who, clip, xmin, xmax, zmin, zmax): {_first(viol)}")
deep = [v for v in pen_list if v[3] > 0.020]
if deep: bad.append(f"{len(deep)} actor-frames push a body part > 0.020 into a dune / rock / hill (t, who, clip, depth, x, z): {_first(deep)}")
elif pen_list: warn_.append(f"{len(pen_list)} actor-frames dip 0.008-0.020 under the desert surface (t, who, clip, depth, x, z): {_first(pen_list)}")
sink = [f"{c} {w['ymin']}" for c, w in worst.items() if w["ymin"][0] < -0.02]
if sink: bad.append(f"mesh sinks more than 0.02 below the page: {sink}")
rec("T13 every actor vertex stays on the paper and out of the dunes / rocks / hills in every frame of the 89 s play",
    "FAIL" if bad else ("WARN" if warn_ else "PASS"), ev + bad + warn_)

# ------------------------------------------------------------------ 14. desert.glb geometry: pieces, footprints, heights, caps, zones (§12.2)
ev, bad, warn = [], [], []
DE = BE["desert"]; nodes_ = DE["nodes"]
PIECES = {pc["id"]: pc for pc in desert["pieces"]}
gj_ = glb_json(f"{A}/model/desert.glb"); gnames = {n["name"] for n in gj_["nodes"]}
miss = [i for i in list(PIECES) + ["desert", "stone1", "stone2", "stone3", "stone4", "stone5"] if i not in gnames]
ev.append(f"{len(PIECES)} pieces in design.json v{dj.get('version')}; glb nodes missing: {miss or 'none'}; root 'desert' has TRS: {DE['rootHasTRS']}")
if miss: bad.append(f"desert.glb missing nodes {miss}")
if DE["rootHasTRS"]: bad.append("desert root carries a transform")
glb_anims = [a["name"] for a in gj_.get("animations", [])]
ev.append(f"animations: {glb_anims}")
if sorted(glb_anims) != ["bannerIsraelWave", "bannerPhilWave"]: bad.append(f"desert.glb animations {glb_anims} != the two banner waves")
def piece_nodes(pid):
    return [k for k in nodes_ if k == pid or k.startswith(pid + "_")]
lo = np.min([v["bbox"][:3] for v in nodes_.values()], 0); hi = np.max([v["bbox"][3:] for v in nodes_.values()], 0)
for nm, bb in DE["bannerClips"].items():
    lo = np.minimum(lo, bb["bbox"][:3]); hi = np.maximum(hi, bb["bbox"][3:])
ev.append(f"all desert vertices (incl. banner wave frames): x {lo[0]:.3f}..{hi[0]:.3f}, y {lo[1]:.4f}..{hi[1]:.3f}, z {lo[2]:.3f}..{hi[2]:.3f}; page x ±0.596, z {PAPER_SET[2]}..{PAPER_SET[3]:.3f}")
if lo[0] < PAPER_SET[0] or hi[0] > PAPER_SET[1] or lo[2] < PAPER_SET[2] or hi[2] > PAPER_SET[3]: bad.append("a desert vertex leaves the page")
if lo[1] < -0.003: bad.append(f"desert vertex more than 0.003 below the page: y {lo[1]}")
CAP = desert["heightCap"]
rows = []
for pid, pc in PIECES.items():
    nn = piece_nodes(pid)
    if not nn: continue
    bb = np.array([nodes_[k]["bbox"] for k in nn]); x0, y0, z0 = bb[:, :3].min(0); x1, y1, z1 = bb[:, 3:].max(0)
    cap = CAP.get(pid, CAP.get("duneFar" if pid == "duneFar" else pc["kind"], CAP.get(pc["kind"])))
    fx0, fys0, fx1, fys1 = pc["footprintSheet"]
    rows.append(f"{pid}: x {x0:.3f}..{x1:.3f} z {z0:.3f}..{z1:.3f} top {y1:.3f} (design {pc['heightMax']}, cap {cap})")
    if y1 > pc["heightMax"] + 0.003: bad.append(f"{pid} top {y1:.4f} > design heightMax {pc['heightMax']}")
    if cap is not None and y1 > cap + 1e-3: bad.append(f"{pid} top {y1:.4f} > cap {cap} (§12.2)")
    if pc["kind"] in ("hill", "dune", "rock", "shrub", "tent") and y1 < 0.85 * pc["heightMax"]:
        bad.append(f"{pid} only {y1:.3f} tall, design says {pc['heightMax']} (the boost is the height)")
    tol = 0.012
    if pc["kind"] != "banner" and (x0 < fx0 - tol or x1 > fx1 + tol):
        bad.append(f"{pid} x {x0:.3f}..{x1:.3f} outside footprint {fx0}..{fx1}")
    if pc["kind"] not in ("banner",) and (z0 < -fys1 - tol or z1 > -fys0 + tol):
        bad.append(f"{pid} z {z0:.3f}..{z1:.3f} outside footprint {-fys1}..{-fys0}")
ev.append("pieces (glb vs design, rest pose): " + "; ".join(rows))
_bt = max(b_["bbox"][4] for b_ in DE["bannerClips"].values()) if DE["bannerClips"] else 0
ev.append(f"banners over every frame of both wave clips (all banner meshes together): top {_bt:.3f} (cap {CAP['banner']})")
if _bt > CAP["banner"] + 1e-3: bad.append(f"a waving banner reaches {_bt:.3f} > cap {CAP['banner']}")
FZ = desert["frontZone"]
front_hi = {k: max(p_[2] for p_ in v["tallXZY"] if p_[1] > FZ["zBeyond"]) for k, v in nodes_.items()
            if any(p_[1] > FZ["zBeyond"] for p_ in v.get("tallXZY", []))}
ev.append(f"raised desert nearer the viewer than z {FZ['zBeyond']} (max y): {front_hi or 'none'} (cap {FZ['cap']})")
if any(v > FZ["cap"] + 1e-3 for v in front_hi.values()): bad.append(f"front zone cap {FZ['cap']} broken: {front_hi}")
from shapely import prepared as _prep
_pb = _prep.prep(QA_BAND.union(_dband))
inband = {}
for k, v in nodes_.items():
    hs = [p_[2] for p_ in v.get("tallXZY", []) if _pb.contains(_P(p_[0], -p_[1]))]
    if hs: inband[k] = max(hs)
ev.append(f"desert vertices above 0.010 inside the stage band (design polygonsSheet ∪ recomputed): {inband or 'none'}")
if inband: bad.append(f"desert higher than 0.010 inside the stage band: {inband}")
# the heightfield: dunes behind David really are tall (§12.8: 0.17-0.25 behind David)
behind_david = HF[np.ix_((HZ < -0.30) & (HZ > -1.0), HX < -0.15)]
ev.append(f"tallest desert behind David (x < -0.15, z -1.0..-0.30): {behind_david.max():.3f}; tallest panorama: {HF[HZ < -0.98].max():.3f}")
if behind_david.max() < 0.17: bad.append("no dune behind David reaches 0.17 (§12.8)")
rec("T14 desert.glb geometry: every §12 piece present, in its footprint, at its design height, under the caps, front zone <= 0.06, flat stage band",
    "FAIL" if bad else ("WARN" if warn else "PASS"), ev + bad + warn)

# ------------------------------------------------------------------ 15. desert UV0 per piece type (§12.1): front / constant / none
ev, bad, warn = [], [], []
REG = np.asarray(Image.open(f"{A}/sheet/regions.png"))
RJ = {r_["id"]: r_ for r_ in json.load(open(f"{A}/sheet/regions.json"))["ids"]}
_d, (_iy, _ix) = ndimage.distance_transform_edt(REG == 0, return_indices=True)
ARTH = dj.get("artHeightUnits", 1.227)
for node in sorted(nodes_):
    if f"{node}__UV" not in BZ.files:
        if node != "brook": bad.append(f"{node} has no UV0")
        continue
    P_ = BZ[f"{node}__P"].astype(float); UV = BZ[f"{node}__UV"].astype(float)
    pid = node.split("_")[0] if node.startswith("banner") else node
    pc = PIECES.get(pid)
    const = np.ptp(UV[:, 0]) < 1e-4 and np.ptp(UV[:, 1]) < 1e-4
    if node.startswith("stone"):
        su = desert["stoneUV"]
        ok = const and abs(UV[0, 0] - su[0]) < 1e-3 and abs(UV[0, 1] - su[1]) < 1e-3
        ev.append(f"{node}: constant UV ({UV[0,0]:.4f}, {UV[0,1]:.4f}) vs stoneUV {su}: {'ok' if ok else 'WRONG'}")
        if not ok: bad.append(f"{node} UV is not the constant stoneUV {su}")
        continue
    if node.endswith("_pole") or node == "brookBank":
        px_, py_ = int(UV[0, 0] * 1000), int((1 - UV[0, 1]) * 1227)
        r_ = RJ.get(int(REG[_iy[py_, px_], _ix[py_, px_]]), {})
        ev.append(f"{node}: constant={const}, UV ({UV[0,0]:.4f}, {UV[0,1]:.4f}) -> printed {r_.get('char')}.{r_.get('part')}:{r_.get('region')} "
                  f"({_d[py_, px_]:.1f} px from it)")
        if not const: bad.append(f"{node} UV should be constant")
        continue
    if pc is None or pc.get("mapping") != "front": warn.append(f"{node}: no front piece in design.json"); continue
    fu = pc["frontUV"]; sc, sx0, sy0 = fu["scale"], fu["sheetX"], fu["sheetY"]
    eu = P_[:, 0] / sc + sx0 + 0.5; evv = (P_[:, 1] / sc + sy0) / ARTH
    res = np.hypot(UV[:, 0] - eu, UV[:, 1] - evv)
    # where each loop samples the printed page: region id at (u, v), nearest region if it lands on a line
    px_ = np.clip((UV[:, 0] * 1000).astype(int), 0, 999); py_ = np.clip(((1 - UV[:, 1]) * 1227).astype(int), 0, 1226)
    ids_ = REG[_iy[py_, px_], _ix[py_, px_]]; dist_ = _d[py_, px_]
    # one mapping for the whole panorama (§12.1): where a pano piece is hidden behind a nearer pano piece in the front view,
    # it samples that nearer piece's drawing, exactly as the 3D overlap; count those as correct but report them
    nearer = {q["id"] for q in desert["pieces"] if pc.get("group") == "pano" and q.get("group") == "pano" and q["id"] != pid
              and q.get("depthZ", {}).get("front", -9) > pc["depthZ"]["front"] + 1e-6}
    parts_ = [RJ.get(int(i), {}).get("part") if RJ.get(int(i), {}).get("char") == "desert" else None for i in ids_]
    own = np.array([q_ == pid for q_ in parts_]); hid = np.array([q_ in nearer for q_ in parts_])
    # are the 'hidden' samples really hidden? the nearer piece's 3D surface must stand in front: compare front heights
    if hid.any():
        tp = {q["id"]: np.array(q["topProfile3D"]) for q in desert["pieces"] if q["id"] in nearer and q.get("topProfile3D") is not None and not isinstance(q.get("topProfile3D"), str)}
        vis_bad = 0
        for k in np.nonzero(hid)[0]:
            q_ = parts_[k]
            if q_ in tp and P_[k, 1] > np.interp(P_[k, 0], tp[q_][:, 0], tp[q_][:, 1]) + 0.004: vis_bad += 1
        if vis_bad: warn.append(f"{node}: {vis_bad} loops sample a nearer piece's drawing but stand above its 3D top (visible over it)")
    own = own | hid
    far = dist_ > 6
    regs = {}
    for i in ids_: rr = RJ.get(int(i), {}); regs[rr.get("region")] = regs.get(rr.get("region"), 0) + 1
    prec = own.mean(); offp = int((far).sum())
    ev.append(f"{node} (front, scale {sc}, sheetY {sy0}): {len(UV)} loops; |UV - formula| p50 {np.median(res)*1000:.1f} px, "
              f"p95 {np.percentile(res,95)*1000:.1f} px, max {res.max()*1000:.1f} px; samples its own printed piece {prec*100:.1f} % (of which behind a nearer pano piece {hid.mean()*100:.1f} %); "
              f"> 6 px off any region {offp}; regions {regs}")
    if prec < 0.97: bad.append(f"{node}: only {prec*100:.1f} % of its UVs sample its own printed drawing (colour lands on another piece)")
    if offp > 0.01 * len(UV): bad.append(f"{node}: {offp} UVs sample blank paper > 6 px from any printed region")
    if np.median(res) > 0.006: bad.append(f"{node}: median UV {np.median(res)*1000:.1f} px from the §12.1 front formula")
    elif np.percentile(res, 95) > 0.012: warn.append(f"{node}: 5 % of UVs > {np.percentile(res,95)*1000:.0f} px from the front formula (inset / tent-strip remap)")
    if pc["kind"] == "tent":
        dr = [RJ.get(int(i), {}).get("region") for i in ids_]
        if "tentDoor" not in dr: bad.append(f"{node}: no UV samples the printed tentDoor region")
    if pc["kind"] == "dune" and pid != "duneFar":
        if not any(RJ.get(int(i), {}).get("region") == "duneShade" for i in ids_): bad.append(f"{node}: slip face never samples duneShade")
ev.append(f"brook: material {nodes_['brook']['material']}, UV0 {'none' if 'uvRange' not in nodes_['brook'] else nodes_['brook']['uvRange']}")
if nodes_["brook"]["material"] != ["dg_water"]: bad.append("brook is not the dg_water material")
mats_ = {k: v["material"] for k, v in nodes_.items() if k != "brook"}
if any(m != ["dg_page"] for m in mats_.values()): bad.append(f"desert pieces not on dg_page: {[k for k, m in mats_.items() if m != ['dg_page']]}")
rec("T15 desert UV0 per piece type: front pieces = §12.1 front projection onto their OWN printed drawing (incl. tentDoor / duneShade), "
    "stones / poles / bank constant, brook none", "FAIL" if bad else ("WARN" if warn else "PASS"), ev + bad + warn)

# ------------------------------------------------------------------ 16. printed sheet: regions closed, desert regions printed, ink >= 6 mm (§12.3)
ev, bad, warn = [], [], []
pg = np.asarray(Image.open("print/david-goliath-A4.png").convert("L"))
paper = pg >= 128
lab, nlab = ndimage.label(paper)
border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
outside = np.isin(lab, list(border))
rj = json.load(open(f"{A}/sheet/regions.json"))
ax, ay, aw, ah = T["art"]
out_art = outside[ay:ay + ah, ax:ax + aw]
leaks, empty = [], []
for r_ in rj["ids"]:
    if r_.get("pageOnly"): continue
    m = REG == r_["id"]
    if not m.any():
        if r_["char"] == "desert": leaks.append(f"desert.{r_['part']}:{r_['region']} has no pixels")
        else: empty.append(f"{r_['char']}.{r_['part']}")
        continue
    k = int((m & out_art).sum())
    if k: leaks.append(f"{r_['char']}.{r_['part']}:{r_['region']} {k}px")
ev.append(f"print page: {nlab} paper components, {len(border)} touch the page border; regions.json {len(rj['ids'])} ids")
ev.append(f"regions open to the page border (or empty desert regions): {leaks or 'none'}")
ev.append(f"character parts with no front-view pixels (hidden behind another part in the rest-pose front drawing; unchanged since v2): {len(empty)}")
if leaks: bad.append(f"open / empty regions: {leaks}")
dm = np.asarray(Image.open(f"{A}/sheet/demo-sheet.png").convert("RGB")).astype(int)
col = ((dm.max(axis=2) - dm.min(axis=2)) > 25) & paper
ink_near = ndimage.binary_dilation(~paper, iterations=3)
lk = int((col & outside & ~ink_near).sum())
ev.append(f"demo-sheet coloured pixels (>= 3 px from ink) in the border-connected paper: {lk}")
if lk > 50: bad.append(f"{lk} coloured demo pixels outside every closed outline (a region leaks)")
used_regions = {r_["region"] for r_ in rj["ids"]}
missing_pal = [k for k in dj["palette"]["desert"] if k not in used_regions]
ev.append(f"palette.desert regions printed: {sorted(set(dj['palette']['desert']) & used_regions)}; missing: {missing_pal or 'none'}")
if missing_pal: bad.append(f"desert palette regions not printed: {missing_pal}")
# overlap: desert drawings never touch the character drawings (§12.3: >= 0.030)
dmask = np.isin(REG, [i for i, r_ in RJ.items() if r_["char"] == "desert"]); cmask = np.isin(REG, [i for i, r_ in RJ.items() if r_["char"] != "desert"])
dd = ndimage.distance_transform_edt(~cmask)[dmask].min() if dmask.any() else 999
ev.append(f"closest desert region pixel to a character region pixel: {dd:.1f} px (§12.3 wants >= 30 px between the drawings' outlines)")
if dd < 20: bad.append(f"desert drawing {dd:.1f} px from a character drawing")
ink = ~paper
mk = np.zeros_like(ink)
for (mx_, my_) in T["markers"]:
    r2 = T["markerSize"] // 2 + 4; mk[my_ - r2:my_ + r2, mx_ - r2:mx_ + r2] = True
ys_, xs_ = np.nonzero(ink & ~mk)
H_, W_ = ink.shape
mm = W_ / 210.0
marg = {"top": ys_.min() / mm, "bottom": (H_ - 1 - ys_.max()) / mm, "left": xs_.min() / mm, "right": (W_ - 1 - xs_.max()) / mm}
ev.append("ink (markers excluded) to the page edge, mm: " + ", ".join(f"{k} {v:.2f}" for k, v in marg.items()) + " (§12.3: >= 6 mm)")
if min(marg.values()) < 6.0 - 1e-6: bad.append(f"ink {min(marg.values()):.2f} mm from a page edge (< 6 mm)")
ev.append(f"markers (template, untouched): outer edge {min(mx_ - T['markerSize'] / 2 for mx_, _ in T['markers']) / mm:.1f} mm from the side edges")
ck = json.load(open(f"{A}/sheet/checks.json"))
ev.append(f"checks.json: slivers {ck.get('slivers(<6px)')}, thin strips {ck.get('thinStrips(<6px, region has a bigger cell)')}, "
          f"regions without colourable cell {ck.get('regionsWithoutColourableCell')}")
if ck.get("regionsWithoutColourableCell"): warn.append(f"uncolourable regions: {ck['regionsWithoutColourableCell']}")
small = []
for i, r_ in RJ.items():
    if r_["char"] != "desert" or r_.get("pageOnly"): continue
    m = REG == i
    if m.any():
        rad = ndimage.distance_transform_edt(np.pad(m, 1))[1:-1, 1:-1].max()
        if rad < 6: small.append(f"{r_['part']}:{r_['region']} {2*rad:.0f}px")
if small: warn.append(f"desert regions whose largest inscribed circle is < 12 px (hard with a crayon): {small}")
rec("T16 printed sheet: every region closed, desert regions printed, no overlap with the characters, all ink >= 6 mm from the page edges",
    "FAIL" if bad else ("WARN" if warn else "PASS"), ev + bad + warn)

# ------------------------------------------------------------------ 17. APK fresh: fingerprint newer than every input
ev, bad = [], []
apk = "unity/Builds/DoodLive.apk"
if not os.path.isfile(apk): bad.append("no APK")
else:
    fp = open(apk + ".fingerprint").read().strip()
    fpr = open("unity/Assets/DoodLive/Resources/build_fingerprint.txt").read().strip()
    m = re.match(r"([0-9a-f]+)(-dirty)?\.(\d{8})-(\d{4})", fp)
    t_fp = calendar.timegm(time.strptime(m.group(3) + m.group(4), "%Y%m%d%H%M"))
    head = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True).stdout.strip()
    aapt = sorted(glob.glob(os.path.expanduser("~/Library/Android/sdk/build-tools/*/aapt2")))
    vn = None
    if aapt:
        o_ = subprocess.run([aapt[-1], "dump", "badging", apk], capture_output=True, text=True).stdout
        mv_ = re.search(r"versionName='([^']+)'", o_); vn = mv_.group(1) if mv_ else None
    ev.append(f"{apk}: {os.path.getsize(apk):,} B, mtime {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(apk)))}; sha256 "
              f"{hashlib.sha256(open(apk, 'rb').read()).hexdigest()[:16]}…")
    ev.append(f"fingerprint file {fp}; Resources/build_fingerprint.txt {fpr}; aapt2 versionName {vn}; git HEAD {head}")
    if fp != fpr or (vn is not None and vn != fp): bad.append("fingerprint mismatch between .fingerprint / build_fingerprint.txt / versionName")
    if not fp.startswith(head): bad.append(f"fingerprint sha {fp[:7]} != HEAD {head}")
    t_build = min(t_fp + 59, os.path.getmtime(apk))   # fingerprint is minute-resolution (UTC); the APK file is written at the end
    inputs = [f"{A}/model/david.glb", f"{A}/model/goliath.glb", f"{A}/model/desert.glb", f"{A}/anim/david.glb", f"{A}/anim/goliath.glb",
              f"{A}/anim/clips.json", f"{A}/design.json", f"{A}/timeline.json", f"{A}/sheet/reference.png", f"{A}/sheet/demo-colored.png",
              f"{A}/sheet/demo-sheet.png", f"{A}/sheet/ground-mask.png", f"{U}/Models/david.glb", f"{U}/Models/goliath.glb", f"{U}/Models/desert.glb",
              f"{U}/Shaders/DGPaperLit.shader", f"{U}/Shaders/DGWater.shader", f"{U}/Shaders/DGGround.shader", f"{U}/Scripts/DGDirector.cs",
              f"{U}/Editor/DGSetup.cs", f"{U}/Textures/dg-ground-mask.png", f"{U}/Tracking/david-goliath-A4.png"]
    # Tracking/ReferenceImages.asset is not an input: DGSetup regenerates it on every Unity run (DGPreview too), which only
    # re-rolls the per-entry m_SerializedGuid; its texture GUIDs and the reference PNG it points to are checked instead + glob.glob(f"{U}/Faces/*.png")
    newer = [(p_, time.strftime('%H:%M:%S', time.localtime(os.path.getmtime(p_)))) for p_ in inputs if os.path.isfile(p_) and os.path.getmtime(p_) > t_build]
    missing_in = [p_ for p_ in inputs if not os.path.isfile(p_)]
    newest = max((p_ for p_ in inputs if os.path.isfile(p_)), key=os.path.getmtime)
    ev.append(f"build time {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t_build))} local; newest input {newest} "
              f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(newest)))}; inputs newer than the build: {newer or 'none'}")
    if newer: bad.append(f"APK is stale: {len(newer)} inputs changed after the build")
    if missing_in: bad.append(f"missing inputs {missing_in}")
    z = zipfile.ZipFile(apk); hits = {}
    want_s = [b"DGWater", b"DGPaperLit", b"DGGround", b"bannerIsraelWave", b"tentPhil3", b"duneFar", b"stone5", b"fingerTipsR"]
    for zi in z.infolist():
        if not zi.filename.startswith("assets/bin/Data/") or zi.file_size > 80_000_000: continue
        data = z.read(zi)
        for w_ in want_s:
            if w_ in data: hits.setdefault(w_.decode(), zi.filename.split("/")[-1])
    nf = [w_.decode() for w_ in want_s if w_.decode() not in hits]
    ev.append(f"strings found in APK assets/bin/Data: {hits}; not found: {nf or 'none'}")
    if any(k in nf for k in ("DGGround", "tentPhil3", "duneFar")): bad.append(f"APK lacks the v3 desert / sand ground: {nf}")
rec("T17 APK exists, fingerprint consistent, newer than every model / sheet / Unity input, contains the v3 desert + DGGround",
    "FAIL" if bad else "PASS", ev + bad)
# ------------------------------------------------------------------ 18. DGPreview phone view: the page reads as sand (§12.8), measured
ev, bad, warn = [], [], []
PV = "unity/Builds/dg-preview"
for f_ in sorted(glob.glob(f"{PV}/phone_*.png")) + sorted(glob.glob(f"{PV}/right_*.png"))[:1]:
    im = np.asarray(Image.open(f_).convert("RGB")).astype(int)
    bgc = im[2, 2]                                                     # clear colour (top-left corner is always background)
    fg = np.abs(im - bgc).sum(2) > 24
    white = fg & (im.min(2) > 0.86 * 255) & ((im.max(2) - im.min(2)) < 22)
    sandy = fg & (im[..., 0] > 190) & (im[..., 1] > 150) & (im[..., 2] < 0.85 * im[..., 0]) & (im[..., 0] - im[..., 2] > 35)
    ev.append(f"{f_.split('/')[-1]}: scene pixels {fg.mean()*100:.0f} %, paper-white {white.sum() / max(1, fg.sum()) * 100:.2f} % of the scene, "
              f"sand-coloured {sandy.sum() / max(1, fg.sum()) * 100:.0f} %; rendered {time.strftime('%H:%M', time.localtime(os.path.getmtime(f_)))}")
    if white.sum() / max(1, fg.sum()) > 0.03: bad.append(f"{f_}: more than 3 % of the scene is white paper")
if not ev: bad.append("no DGPreview phone renders")
rec("T18 DGPreview phone view reads as sand: paper-white < 3 % of the scene (§12.8; the eye check is in QA.md)",
    "FAIL" if bad else ("WARN" if warn else "PASS"), ev + bad + warn)
json.dump(results, open(os.path.join(os.path.dirname(__file__), "qa_results.json"), "w"), indent=1, ensure_ascii=False)
print("\nSUMMARY:", ", ".join(f"{r_['check'].split()[0]} {r_['status']}" for r_ in results))
