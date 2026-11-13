#!/usr/bin/env python3
"""David & Goliath storyboard: the single source for timeline.json, STORYBOARD.md and the frames.

Run from anywhere:  python3 docs/david-goliath/storyboard/build_storyboard.py
Writes (Story role's files only, CONTRACT section 1):
  assets/david-goliath/timeline.json            the performance (CONTRACT section 6)
  docs/david-goliath/STORYBOARD.md              shot table generated from the same data
  docs/david-goliath/storyboard/Sxx.svg/.png    one stick-figure frame per shot (headless Chrome)
  docs/david-goliath/storyboard/board.png       contact sheet of all frames
and validates the timeline (exit code 1 on any error).
"""
import json, math, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TIMELINE = os.path.join(ROOT, "assets", "david-goliath", "timeline.json")
BOARD_MD = os.path.join(ROOT, "docs", "david-goliath", "STORYBOARD.md")
STORY_MD = os.path.join(ROOT, "docs", "david-goliath", "STORY.md")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

DURATION = 89.0

# ---------------------------------------------------------------- page bounds (from the sheet template, not the art rect)
# Stage x = art-width units from the art centre, z = 0 on the art rectangle's bottom edge (+z toward the viewer).
# The page reaches 0.244 below the art (page px 1510 -> 1754) and 0.283 + 1.227 above it, 0.12 beside it.
_TPL = json.load(open(os.path.join(ROOT, "assets", "david-goliath", "sheet", "template.json")))
_AX, _AY, _AW, _AH = _TPL["art"]; _PW, _PH = _TPL["page"]
PAGE_MARGIN = 0.024                       # an actor's feet must stay this far inside the paper edge (z <= 0.22)
PAGE_X = (round(-(_AX + _AW / 2) / _AW + PAGE_MARGIN, 3), round((_PW - _AX - _AW / 2) / _AW - PAGE_MARGIN, 3))
PAGE_Z = (round(-(_AY + _AH) / _AW + PAGE_MARGIN, 3), round((_PH - _AY - _AH) / _AW - PAGE_MARGIN, 3))
FPS = 30

# ---------------------------------------------------------------- contract vocab (CONTRACT 3, 5)
CLIPS = {
    "david": {"idle", "walk", "talk", "kneel_pick", "sling_windup", "sling_release", "run", "victory", "pray"},
    "goliath": {"idle", "walk", "talk", "taunt", "laugh", "roar", "charge", "hit_react", "fall", "down"},
}
BONES = set("root hips spine chest neck head jaw shoulderL upperArmL forearmL handL shoulderR upperArmR forearmR "
            "handR thighL shinL footL toeL thighR shinR footR toeR".split())
EXTRA = {"david": {"slingCord1", "slingCord2", "slingPouch", "stone"}, "goliath": {"spear", "shield", "helmet"}}
WHO = {"narrator", "david", "goliath", "saul", "soldiers"}
FACE = {"david", "goliath", "viewer"}           # "viewer" = +Z (toward the phone); see STORYBOARD notes
CAM_TYPES, CAM_TARGETS = {"orbit", "fixed", "follow"}, {"david", "goliath", "both", "stone"}

# ---------------------------------------------------------------- shots
# key: time used for the storyboard frame; note: extra direction for Animation / FX / Integration.
SHOTS = [
    dict(id="S01", t0=0.0, t1=8.0, title_zh="以拉谷", title_en="The Valley of Elah",
         camera=dict(type="orbit", target="both", dist=1.6, height=0.45, yawDeg=-25), key=4.0,
         desc="Wide slow orbit over the page. Goliath stomps to his place at the back of the page; dust puffs at each step. "
              "David stands small at the front-left, watching.",
         note="Goliath keeps z = -0.25 (back of the page) until he falls; David stays in front (z >= 0)."),
    dict(id="S02", t0=8.0, t1=18.6, title_zh="巨人的挑战", title_en="The giant's challenge",
         camera=dict(type="fixed", target="goliath", dist=1.1, height=0.12, yawDeg=15), key=10.0,
         desc="Low hero angle looking up at Goliath. He taunts with his spear, shouts his challenge, then the narrator "
              "tells how big he is; he ends with a roar.",
         note="Low camera makes him feel huge. Roar at 17.6 is the button at the end of the shot."),
    dict(id="S03", t0=18.6, t1=26.4, title_zh="军队害怕了", title_en="The armies are afraid",
         camera=dict(type="orbit", target="goliath", dist=1.4, height=0.35, yawDeg=-40), key=23.5,
         desc="Off-screen soldiers gasp and murmur. Goliath laughs at them and mocks them.",
         note="Soldiers are voice + crowd SFX only; nothing is drawn for them."),
    dict(id="S04", t0=26.4, t1=38.0, title_zh="牧羊少年大卫", title_en="David the shepherd",
         camera=dict(type="follow", target="david", dist=0.8, height=0.25, yawDeg=30), key=33.0,
         desc="Music turns gentle. David walks forward to centre-left; a sheep bleats off-screen. He says he will go; "
              "King Saul (off-screen) says he is only a boy.",
         note="David faces the viewer while speaking to the (off-screen) Israelite army, then turns to Goliath."),
    dict(id="S05", t0=38.0, t1=51.4, title_zh="狮子、熊和盔甲", title_en="Lion, bear and armour",
         camera=dict(type="fixed", target="david", dist=0.7, height=0.22, yawDeg=0), key=41.0,
         desc="Close on David. A memory bubble shows a lion and a bear above his head while he tells Saul. Then an "
              "off-screen clank: he takes off Saul's heavy armour.",
         note="Armour is never modelled: voice + clank SFX only."),
    dict(id="S06", t0=51.4, t1=58.0, title_zh="五块光滑的石头", title_en="Five smooth stones",
         camera=dict(type="follow", target="david", dist=0.6, height=0.12, yawDeg=50), key=54.0,
         desc="David walks to the brook at the front-left of the page, kneels and picks stones (ripples, five clacks), "
              "then walks back to face Goliath.",
         note="kneel_pick is one clip; play it once (about 3 s). The five clacks are SFX, one stone per clack."),
    dict(id="S07", t0=58.0, t1=67.8, title_zh="我靠耶和华的名", title_en="In the name of the LORD",
         camera=dict(type="fixed", target="both", dist=1.3, height=0.3, yawDeg=90), key=63.5,
         desc="Side-on two-shot. Goliath laughs and sneers at the little boy. David answers with the key line; "
              "a warm glow rises around him and the music turns brave.",
         note="Heart of the story: no FX should hide David's face during dg_14."),
    dict(id="S08", t0=67.8, t1=72.6, title_zh="奔跑与甩石", title_en="The run and the sling",
         camera=dict(type="follow", target="david", dist=1.0, height=0.2, yawDeg=-60), key=71.4,
         desc="Goliath roars and lumbers forward; David runs to meet him and spins the sling over his head.",
         note="David runs toward Goliath (17:48), not away. Sling cord spins; trail FX on the pouch."),
    dict(id="S09", t0=72.6, t1=76.6, title_zh="一块石头", title_en="One stone",
         camera=dict(type="fixed", target="both", dist=1.6, height=0.6, yawDeg=44), key=73.2,
         desc="Release. Side-on two-shot, square to the line between them: the stone flies from the pouch to Goliath's "
              "forehead: flash, dizzy stars, then the "
              "giant topples forward onto the page toward the viewer. Dust bursts, the page shakes.",
         note="Stone flight 0.45 s from david.slingPouch to goliath.head (forehead). Goliath falls toward +Z (viewer), "
              "so he lands beside David, not on him (1 Sam 17:49 'fell upon his face')."),
    dict(id="S10", t0=76.6, t1=80.0, title_zh="巨人倒下了", title_en="The giant falls",
         camera=dict(type="orbit", target="both", dist=1.3, height=0.6, yawDeg=-30), key=79.0,
         desc="High slow orbit. Goliath lies still on the page (down loop). The off-screen army cheers.",
         note="Keep it gentle: no blood, no sword (17:51 is left out for ages 4-9)."),
    dict(id="S11", t0=80.0, t1=89.0, title_zh="勇气和信靠", title_en="Courage and trust",
         camera=dict(type="fixed", target="david", dist=0.8, height=0.4, yawDeg=-40), key=86.0,
         desc="David faces the viewer: victory jump, confetti, then he bows his head and prays while golden rays fall "
              "and the narrator gives the moral.",
         note="Ends on David praying; the app shows the replay chip after 89.0. Camera front-left of David so the "
              "fallen Goliath (lying toward +Z on the right) stays behind him, not in front of him."),
]

# ---------------------------------------------------------------- acting
# Start positions = CONTRACT 2 default marks (david -0.25,0  goliath 0.22,0). `to` = XZ target.
ACTING = [
    dict(t=0.0, who="david", clip="idle", face="goliath", blend=0.25),
    dict(t=0.0, who="goliath", clip="idle", face="david", blend=0.25),
    dict(t=1.0, who="goliath", clip="walk", to=[0.22, -0.25], face="david", blend=0.3),
    dict(t=1.0, who="david", clip="walk", to=[-0.30, 0.10], face="goliath", blend=0.3),
    dict(t=3.0, who="david", clip="idle", face="goliath", blend=0.3),
    dict(t=4.6, who="goliath", clip="idle", face="david", blend=0.3),
    # S02
    dict(t=8.0, who="goliath", clip="taunt", face="viewer", blend=0.25),
    dict(t=8.4, who="goliath", clip="talk", face="viewer", blend=0.2),
    dict(t=12.4, who="goliath", clip="idle", face="viewer", blend=0.3),
    dict(t=17.6, who="goliath", clip="roar", face="viewer", blend=0.2),
    # S03
    dict(t=19.4, who="goliath", clip="laugh", face="viewer", blend=0.25),
    dict(t=22.4, who="goliath", clip="talk", face="viewer", blend=0.2),
    dict(t=25.4, who="goliath", clip="idle", face="david", blend=0.3),
    # S04
    dict(t=26.6, who="david", clip="walk", to=[-0.20, 0.05], face="viewer", blend=0.3),
    dict(t=29.4, who="david", clip="idle", face="viewer", blend=0.3),
    dict(t=31.8, who="david", clip="talk", face="viewer", blend=0.2),
    dict(t=34.8, who="david", clip="idle", face="viewer", blend=0.3),
    # S05
    dict(t=38.4, who="david", clip="talk", face="viewer", blend=0.2),
    dict(t=46.8, who="david", clip="idle", face="viewer", blend=0.3),
    dict(t=47.4, who="david", clip="talk", face="viewer", blend=0.2),
    dict(t=50.8, who="david", clip="idle", face="goliath", blend=0.3),
    dict(t=47.0, who="goliath", clip="idle", face="david", blend=0.3),
    # S06
    dict(t=51.4, who="david", clip="walk", to=[-0.32, 0.20], face="viewer", blend=0.3),
    dict(t=53.0, who="david", clip="kneel_pick", face="viewer", blend=0.25),
    dict(t=56.2, who="david", clip="walk", to=[-0.22, 0.05], face="goliath", blend=0.3),
    dict(t=57.8, who="david", clip="idle", face="goliath", blend=0.3),
    # S07
    dict(t=58.0, who="goliath", clip="laugh", face="david", blend=0.25),
    dict(t=58.8, who="goliath", clip="talk", face="david", blend=0.2),
    dict(t=62.0, who="goliath", clip="idle", face="david", blend=0.3),
    dict(t=62.2, who="david", clip="talk", face="goliath", blend=0.2),
    dict(t=68.2, who="david", clip="idle", face="goliath", blend=0.2),
    # S08
    dict(t=67.8, who="goliath", clip="roar", face="david", blend=0.2),
    dict(t=69.0, who="goliath", clip="charge", to=[0.16, -0.22], face="david", blend=0.3),
    dict(t=68.6, who="david", clip="run", to=[-0.12, 0.05], face="goliath", blend=0.2),
    dict(t=70.2, who="david", clip="sling_windup", face="goliath", blend=0.2),
    dict(t=72.4, who="goliath", clip="idle", face="david", blend=0.2),
    # S09
    dict(t=72.6, who="david", clip="sling_release", face="goliath", blend=0.1),
    dict(t=73.05, who="goliath", clip="hit_react", face="david", blend=0.1),
    dict(t=74.0, who="goliath", clip="fall", face="viewer", blend=0.3),
    dict(t=74.0, who="david", clip="idle", face="goliath", blend=0.3),
    dict(t=75.8, who="goliath", clip="down", face="viewer", blend=0.3),
    # S10
    dict(t=77.2, who="david", clip="walk", to=[-0.20, 0.20], face="viewer", blend=0.3),
    dict(t=79.4, who="david", clip="idle", face="viewer", blend=0.3),
    # S11
    dict(t=80.0, who="david", clip="victory", face="viewer", blend=0.25),
    dict(t=81.4, who="david", clip="talk", face="viewer", blend=0.2),
    dict(t=84.2, who="david", clip="pray", face="viewer", blend=0.4),
]

# ---------------------------------------------------------------- lines
LINES = [
    dict(id="dg_01", t=0.5, who="narrator", maxSec=5.2, ref="1 Samuel 17:1-3",
         zh="很久以前，以色列人和非利士人，隔着山谷打仗。",
         en="Long ago, two armies faced each other across a valley."),
    dict(id="dg_02", t=8.4, who="goliath", maxSec=4.0, ref="1 Samuel 17:8-10",
         zh="我是歌利亚！派个人出来，跟我打！",
         en="I am Goliath! Send someone out to fight me!"),
    dict(id="dg_03", t=12.6, who="narrator", maxSec=4.4, ref="1 Samuel 17:4-7",
         zh="他差不多有三米高，穿着铜盔甲，拿着大枪。",
         en="He was almost three metres tall, in bronze armour!"),
    dict(id="dg_04", t=19.6, who="soldiers", maxSec=2.6, ref="1 Samuel 17:11, 24",
         zh="他太大了！谁也不敢去！",
         en="He's too big! No one dares!"),
    dict(id="dg_05", t=22.4, who="goliath", maxSec=3.0, ref="1 Samuel 17:10, 16",
         zh="哈哈！你们全是胆小鬼！",
         en="Ha ha! You're all too scared!"),
    dict(id="dg_06", t=26.6, who="narrator", maxSec=5.0, ref="1 Samuel 17:20-23",
         zh="这时，放羊的少年大卫来了。他一点也不怕。",
         en="Then David came, a young shepherd boy. He was not afraid."),
    dict(id="dg_07", t=31.8, who="david", maxSec=2.8, ref="1 Samuel 17:32",
         zh="大家别怕！我去跟他打！",
         en="Don't be afraid! I'll fight him!"),
    dict(id="dg_08", t=35.0, who="saul", maxSec=3.4, ref="1 Samuel 17:33",
         zh="你还是个孩子，怎么打得过他？",
         en="You're just a boy. How can you win?"),
    dict(id="dg_09", t=38.6, who="david", maxSec=4.3, ref="1 Samuel 17:34-36",
         zh="我放羊时，打败过狮子，也打败过熊！",
         en="I kept sheep. I beat a lion and a bear!"),
    dict(id="dg_10", t=43.1, who="david", maxSec=3.9, ref="1 Samuel 17:37",
         zh="上帝救过我，这次也会救我！",
         en="The LORD saved me then. He'll save me now!"),
    dict(id="dg_11", t=47.4, who="david", maxSec=3.3, ref="1 Samuel 17:38-39",
         zh="这盔甲太重了，我不穿了。",
         en="Too heavy! I'll go without this armour."),
    dict(id="dg_12", t=51.6, who="narrator", maxSec=4.0, ref="1 Samuel 17:40",
         zh="大卫在小溪边，挑了五块光滑的石头。",
         en="By the brook, David picked five smooth stones."),
    dict(id="dg_13", t=58.8, who="goliath", maxSec=3.2, ref="1 Samuel 17:42-44",
         zh="小不点，你也想跟我打？",
         en="Little boy, you want to fight me?"),
    dict(id="dg_14", t=62.2, who="david", maxSec=6.0, ref="1 Samuel 17:45",
         zh="你靠的是刀和枪，我靠的是耶和华的名！",
         en="You come with sword and spear. I come in the name of the LORD!"),
    dict(id="dg_15", t=68.6, who="narrator", maxSec=3.0, ref="1 Samuel 17:48-49",
         zh="大卫跑上前去，甩起了机弦！",
         en="David ran forward and swung his sling!"),
    dict(id="dg_16", t=76.6, who="narrator", maxSec=3.9, ref="1 Samuel 17:49-50",
         zh="石头打中额头，巨人咚地倒下了！",
         en="The stone hit his forehead. Down fell the giant!"),
    dict(id="dg_17", t=81.4, who="david", maxSec=2.6, ref="1 Samuel 17:47",
         zh="这场仗，是属于上帝的！",
         en="The battle belongs to the LORD!"),
    dict(id="dg_18", t=84.3, who="narrator", maxSec=4.3, ref="1 Samuel 17:45-47 (moral)",
         zh="个子小不要紧，勇气和信靠上帝更重要！",
         en="Courage and trust in God matter more than size!"),
]

# ---------------------------------------------------------------- fx / sfx / music
FX = [
    dict(t=1.3, id="dust_puff", at="goliath.footL", dur=0.6),
    dict(t=2.4, id="dust_puff", at="goliath.footR", dur=0.6),
    dict(t=3.5, id="dust_puff", at="goliath.footL", dur=0.6),
    dict(t=38.8, id="memory_lion_bear", at="david.head", dur=3.8),
    dict(t=53.6, id="brook_ripple", at="david.handR", dur=2.4),
    dict(t=62.2, id="faith_glow", at="david.chest", dur=5.6),
    dict(t=70.2, id="sling_trail", at="david.slingPouch", dur=2.4),
    dict(t=72.6, id="stone_trail", at="david.stone", dur=0.5),
    dict(t=73.05, id="hit_flash", at="goliath.head", dur=0.4),
    dict(t=73.3, id="dizzy_stars", at="goliath.head", dur=1.0),
    dict(t=75.2, id="dust_burst", at="goliath.hips", dur=1.6),
    dict(t=80.2, id="confetti", at="david.head", dur=3.0),
    dict(t=84.3, id="golden_rays", at="david.root", dur=4.0),
]
SFX = [
    dict(t=0.0, id="crowd_murmur"),
    dict(t=1.3, id="giant_step"), dict(t=2.4, id="giant_step"), dict(t=3.5, id="giant_step"),
    dict(t=8.3, id="spear_clang"),            # = goliath_taunt clang marker (taunt 8.0 + 0.30 s)
    dict(t=17.6, id="goliath_roar"),
    dict(t=19.0, id="crowd_gasp"),
    dict(t=19.4, id="goliath_laugh"),
    dict(t=27.2, id="sheep_baa"),
    dict(t=39.0, id="lion_roar"),
    dict(t=40.4, id="bear_growl"),
    dict(t=47.2, id="armour_clank"),
    dict(t=53.6, id="water_splash"),
    dict(t=54.2, id="stone_clack"), dict(t=54.6, id="stone_clack"), dict(t=55.0, id="stone_clack"),
    dict(t=55.4, id="stone_clack"), dict(t=55.8, id="stone_clack"),
    dict(t=58.0, id="goliath_laugh"),
    dict(t=67.8, id="goliath_roar"),
    dict(t=68.6, id="run_steps"),
    dict(t=69.0, id="giant_step"), dict(t=70.0, id="giant_step"), dict(t=71.0, id="giant_step"),
    dict(t=70.2, id="sling_whoosh"),
    dict(t=72.6, id="sling_snap"),
    dict(t=73.05, id="stone_hit"),
    dict(t=75.2, id="giant_fall"),
    dict(t=76.0, id="crowd_cheer"),
    dict(t=80.0, id="victory_chime"),
]
MUSIC = [
    dict(t=0.0, cue="theme_tension"),
    dict(t=26.4, cue="theme_shepherd"),
    dict(t=58.0, cue="theme_faith"),
    dict(t=67.8, cue="theme_battle"),
    dict(t=73.05, cue="sting_hit"),
    dict(t=76.0, cue="theme_victory"),
]
REQUESTED_CLIPS = []

ZH_RATE, EN_RATE, MARGIN, GAP = 4.5, 2.6, 1.1, 0.2


def zh_chars(s):
    return len(re.findall(r"[一-鿿]", s))


def en_words(s):
    return len(re.findall(r"[A-Za-z']+", s))


def est(line):
    return zh_chars(line["zh"]) / ZH_RATE, en_words(line["en"]) / EN_RATE


# ---------------------------------------------------------------- timeline + validation
def build_timeline():
    r = lambda v: round(v, 2)
    shots = [{k: (r(v) if isinstance(v, float) else v) for k, v in s.items() if k not in ("key", "note")} for s in SHOTS]
    lines = [{**l, "t": r(l["t"])} for l in LINES]
    return {"version": 1, "duration": DURATION, "fps": FPS, "shots": shots,
            "acting": sorted(ACTING, key=lambda a: (a["t"], a["who"])),
            "lines": lines, "fx": sorted(FX, key=lambda f: f["t"]), "sfx": sorted(SFX, key=lambda f: f["t"]),
            "music": MUSIC, "requestedClips": REQUESTED_CLIPS}


def validate(tl):
    err = []
    D = tl["duration"]
    if not 60 <= D <= 90: err.append(f"duration {D} outside 60-90 s")
    sh = tl["shots"]
    if sh[0]["t0"] != 0 or abs(sh[-1]["t1"] - D) > 1e-6: err.append("shots must cover 0..duration")
    for a, b in zip(sh, sh[1:]):
        if abs(a["t1"] - b["t0"]) > 1e-6: err.append(f"gap/overlap between {a['id']} and {b['id']}")
    for s in sh:
        c = s["camera"]
        if s["t1"] <= s["t0"]: err.append(f"{s['id']} empty")
        if c["type"] not in CAM_TYPES or c["target"] not in CAM_TARGETS: err.append(f"{s['id']} camera {c}")
    for key in ("acting", "lines", "fx", "sfx", "music"):
        ts = [e["t"] for e in tl[key]]
        if ts != sorted(ts): err.append(f"{key} not sorted by t")
        for e in tl[key]:
            if not 0 <= e["t"] < D: err.append(f"{key} t={e['t']} outside duration")
    for a in tl["acting"]:
        if a["clip"] not in CLIPS[a["who"]] | set(tl["requestedClips"]):
            err.append(f"illegal clip {a['who']}.{a['clip']} at {a['t']}")
        if a.get("face") not in FACE: err.append(f"illegal face {a.get('face')} at {a['t']}")
        if "to" in a:
            x, z = a["to"]
            if not (PAGE_X[0] <= x <= PAGE_X[1] and PAGE_Z[0] <= z <= PAGE_Z[1]):
                err.append(f"`to` {a['to']} at {a['t']} leaves the page (x in {PAGE_X}, z in {PAGE_Z}, "
                           f"page edge minus {PAGE_MARGIN})")
    ids = [l["id"] for l in tl["lines"]]
    if len(ids) != len(set(ids)): err.append("duplicate line ids")
    for i, l in enumerate(tl["lines"]):
        if l["who"] not in WHO: err.append(f"{l['id']} who={l['who']}")
        if not re.fullmatch(r"dg_\d\d", l["id"]): err.append(f"bad id {l['id']}")
        z, e = est(l)
        need = max(z, e) * MARGIN
        if l["maxSec"] < need: err.append(f"{l['id']} maxSec {l['maxSec']} < needed {need:.2f} (zh {z:.2f}s, en {e:.2f}s)")
        end = l["t"] + l["maxSec"]
        if end > D: err.append(f"{l['id']} ends after duration")
        if i + 1 < len(tl["lines"]) and end + GAP > tl["lines"][i + 1]["t"] + 1e-6:
            err.append(f"{l['id']} (ends {end:.2f}) overlaps {tl['lines'][i+1]['id']} at {tl['lines'][i+1]['t']}")
        if re.search(r"[,.!?;:]", l["zh"]): err.append(f"{l['id']} zh has half-width punctuation")
    for f in tl["fx"]:
        who, _, bone = f["at"].partition(".")
        if who not in CLIPS or bone not in BONES | EXTRA[who]: err.append(f"fx at {f['at']} not a contract bone")
        if f["t"] + f["dur"] > D: err.append(f"fx {f['id']} runs past the end")
    for name in ("fx", "sfx"):
        for f in tl[name]:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", f["id"]): err.append(f"{name} id {f['id']}")
    for m in tl["music"]:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", m["cue"]): err.append(f"music cue {m['cue']}")
    # who is talking must be in a talk-ish clip; lines by actors need jaw
    for l in tl["lines"]:
        if l["who"] in ("david", "goliath"):
            cur = [a for a in tl["acting"] if a["who"] == l["who"] and a["t"] <= l["t"] + 0.01]
            if not cur or cur[-1]["clip"] != "talk": err.append(f"{l['id']}: {l['who']} not in talk at {l['t']}")
    used = {(a["who"], a["clip"]) for a in tl["acting"]}
    unused = [f"{w}_{c}" for w in CLIPS for c in sorted(CLIPS[w]) if (w, c) not in used]
    return err, unused


# ---------------------------------------------------------------- stick figures
# Pose = angles in degrees from straight down, + = toward the way the figure faces.
# (lean, armL:(shoulder, elbow), armR, legL:(hip, knee), legR, hipDrop, mouth)
POSES = {
    "idle": (0, (-15, 0), (15, 0), (-6, 0), (6, 0), 0, False),
    "walk": (5, (-25, 10), (25, 20), (-20, 10), (20, 0), 0, False),
    "talk": (0, (-15, 0), (60, 60), (-6, 0), (6, 0), 0, True),
    "taunt": (-5, (-20, 0), (150, 20), (-10, 0), (10, 0), 0, True),
    "laugh": (-15, (-40, 60), (40, 60), (-8, 0), (8, 0), 0, True),
    "roar": (5, (-120, -20), (120, 20), (-15, 0), (15, 0), 0, True),
    "charge": (25, (60, 30), (80, 0), (-30, 20), (35, 0), 0.02, True),
    "hit_react": (-25, (-80, 30), (-60, 30), (-10, 0), (15, 0), 0, True),
    "fall": (0, (60, 0), (80, 0), (0, 0), (5, 0), 0, False),
    "down": (0, (170, 0), (175, 0), (0, 0), (5, 0), 0, False),
    "kneel_pick": (25, (-10, 0), (45, 0), (90, -90), (0, -90), 0.25, False),
    "sling_windup": (-5, (40, 40), (175, 0), (-15, 0), (15, 0), 0, False),
    "sling_release": (20, (-40, 0), (95, 0), (-25, 0), (30, 0), 0, False),
    "run": (20, (-50, 80), (50, 80), (-40, 50), (40, 10), 0.02, False),
    "victory": (0, (-160, 0), (160, 0), (-12, 0), (12, 0), 0, True),
    "pray": (10, (30, 120), (35, 120), (-6, 0), (6, 0), 0, False),
}


def figure(who, clip, sx, sy, h, facing):
    """SVG for one stick figure standing at screen (sx, sy) with screen height h; facing = +1 right / -1 left / 0 viewer."""
    lean, aL, aR, lL, lR, drop, mouth = POSES[clip]
    col = "#2b6cb0" if who == "david" else "#9c5b18"
    w = max(2.0, h * (0.035 if who == "david" else 0.03))
    f = facing if facing else 1
    out = []
    pts = {}
    hip = (0.0, 0.5 - drop)

    def P(ang, length, base):
        a = math.radians(ang)
        return (base[0] + f * math.sin(a) * length, base[1] - math.cos(a) * length)  # y-up local

    def Pu(ang, length, base):  # upward-measured for the spine
        a = math.radians(ang)
        return (base[0] + f * math.sin(a) * length, base[1] + math.cos(a) * length)

    neck = Pu(lean, 0.32, hip)
    headc = Pu(lean, 0.42, hip)
    sh = Pu(lean, 0.28, hip)
    segs = []
    for (s, e) in (aL, aR):
        if facing == 0:
            pass
        el = P(s + lean, 0.16, sh); hd = P(s + e + lean, 0.15, el); segs.append((sh, el, hd))
    legs = []
    for (s, k) in (lL, lR):
        kn = P(s, 0.25, hip); ft = P(s + k, 0.25, kn); legs.append((hip, kn, ft))
    # whole-body rotation for fall / down (pivot at feet)
    rot = {"fall": 50, "down": 88}.get(clip, 0)

    def T(p):
        x, y = p
        if rot:
            a = math.radians(rot) * f
            x, y = x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)
            if clip == "down": y += 0.06
        return (sx + x * h, sy - y * h)

    def line(a, b, ww=w, c=col):
        A, B = T(a), T(b)
        out.append(f'<line x1="{A[0]:.1f}" y1="{A[1]:.1f}" x2="{B[0]:.1f}" y2="{B[1]:.1f}" stroke="{c}" stroke-width="{ww:.1f}" stroke-linecap="round"/>')

    line(hip, neck)
    for a, b, c in segs + legs:
        line(a, b); line(b, c)
    hc = T(headc); r = 0.09 * h
    out.append(f'<circle cx="{hc[0]:.1f}" cy="{hc[1]:.1f}" r="{r:.1f}" fill="#fff" stroke="{col}" stroke-width="{w:.1f}"/>')
    if mouth:
        out.append(f'<ellipse cx="{hc[0] + f*r*0.35:.1f}" cy="{hc[1] + r*0.35:.1f}" rx="{r*0.28:.1f}" ry="{r*0.22:.1f}" fill="{col}"/>')
    if who == "goliath":
        out.append(f'<path d="M{hc[0]-r*1.1:.1f},{hc[1]-r*0.1:.1f} A{r*1.1:.1f},{r*1.1:.1f} 0 0 1 {hc[0]+r*1.1:.1f},{hc[1]-r*0.1:.1f} Z" fill="#c9a227" stroke="{col}" stroke-width="{w*0.6:.1f}"/>')
        hand_l, hand_r = segs[0][2], segs[1][2]
        if clip not in ("fall", "down"):
            sp0 = T((hand_r[0], hand_r[1] - 0.25)); sp1 = T((hand_r[0], hand_r[1] + 0.55))
            out.append(f'<line x1="{sp0[0]:.1f}" y1="{sp0[1]:.1f}" x2="{sp1[0]:.1f}" y2="{sp1[1]:.1f}" stroke="#555" stroke-width="{w*0.7:.1f}"/>')
            tip = sp1
            out.append(f'<path d="M{tip[0]-w*1.5:.1f},{tip[1]+w*2:.1f} L{tip[0]:.1f},{tip[1]-w*3:.1f} L{tip[0]+w*1.5:.1f},{tip[1]+w*2:.1f} Z" fill="#888"/>')
        hl = T(hand_l)
        out.append(f'<circle cx="{hl[0]:.1f}" cy="{hl[1]:.1f}" r="{0.11*h:.1f}" fill="#d9b26f" fill-opacity="0.85" stroke="{col}" stroke-width="{w*0.6:.1f}"/>')
    if who == "david" and clip in ("sling_windup", "sling_release", "idle", "talk", "run", "walk"):
        hr = T(segs[1][2])
        if clip == "sling_windup":
            out.append(f'<ellipse cx="{hr[0]:.1f}" cy="{hr[1]-0.05*h:.1f}" rx="{0.18*h:.1f}" ry="{0.06*h:.1f}" fill="none" stroke="#7a4b20" stroke-width="{w*0.5:.1f}" stroke-dasharray="4 3"/>')
        elif clip == "sling_release":
            out.append(f'<circle cx="{hr[0]+f*0.25*h:.1f}" cy="{hr[1]:.1f}" r="{0.03*h:.1f}" fill="#777"/>')
    return "\n".join(out)


def state_at(t):
    """Approximate actor state (pos, clip, face) at time t for the frame."""
    st = {"david": dict(pos=[-0.25, 0.0], clip="idle", face="goliath"),
          "goliath": dict(pos=[0.22, 0.0], clip="idle", face="david")}
    for a in sorted(ACTING, key=lambda a: a["t"]):
        if a["t"] <= t:
            s = st[a["who"]]; s["clip"] = a["clip"]; s["face"] = a["face"]
            if "to" in a: s["pos"] = list(a["to"])
    return st


def line_at(t0, t1, key):
    ls = [l for l in LINES if t0 <= l["t"] < t1]
    if not ls: return None
    return min(ls, key=lambda l: abs(l["t"] - key))


W, H = 640, 400
STAGE_H = 300


def frame_svg(shot):
    key = shot["key"]; cam = shot["camera"]; st = state_at(key)
    tgt = cam["target"]
    group = [tgt] if tgt in ("david", "goliath") else ["david", "goliath"]
    xs = [st[w]["pos"][0] for w in group]
    cx = (min(xs) + max(xs)) / 2
    tall = max((0.30 if w == "david" else (0.62 if st[w]["clip"] == "down" else 0.80)) for w in group)
    ground = 230 + cam["height"] * 40
    S = min((ground - 62) / (tall * 1.08), (W - 60) / (max(xs) - min(xs) + 0.35))  # px per art-width unit, fits the target
    horizon = 70 + cam["height"] * 140       # higher camera -> page shows more depth
    depth = 0.25 + cam["height"] * 0.6       # z foreshortening
    X = lambda x: W / 2 + (x - cx) * S
    Z = lambda z: ground + z * S * depth * 0.5
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
         f'<rect width="{W}" height="{H}" fill="#fdf8ee"/>',
         f'<clipPath id="stage"><rect y="46" width="{W}" height="{STAGE_H-46}"/></clipPath><g clip-path="url(#stage)">',
         f'<rect y="0" width="{W}" height="{STAGE_H}" fill="#efe3c8"/>',
         f'<rect y="{horizon:.0f}" width="{W}" height="{STAGE_H-horizon:.0f}" fill="#d8bf93"/>']
    # page (art rect) as a trapezoid-ish quad
    pz0, pz1 = -0.6, 0.6
    quad = [(X(-0.5), Z(pz0)), (X(0.5), Z(pz0)), (X(0.5), Z(pz1)), (X(-0.5), Z(pz1))]
    o.append('<polygon points="' + " ".join(f"{a:.0f},{b:.0f}" for a, b in quad) + '" fill="#fff" stroke="#b9a37a"/>')
    # brook doodle at the front-left
    bx, bz = -0.36, 0.36
    o.append(f'<path d="M{X(bx-0.12):.0f},{Z(bz):.0f} q{0.04*S:.0f},-6 {0.08*S:.0f},0 t{0.08*S:.0f},0 t{0.08*S:.0f},0" fill="none" stroke="#5aa9e6" stroke-width="4" stroke-linecap="round"/>')
    # actors, back to front
    for who in sorted(st, key=lambda w: st[w]["pos"][1]):
        s = st[who]; x, z = s["pos"]
        h = (0.30 if who == "david" else 0.80) * S
        other = "goliath" if who == "david" else "david"
        facing = 0 if s["face"] == "viewer" else (1 if st[other]["pos"][0] > x else -1)
        if s["face"] == "viewer": facing = 1 if who == "david" else -1
        o.append(f'<ellipse cx="{X(x):.0f}" cy="{Z(z):.0f}" rx="{0.08*S*(2 if who=="goliath" else 1):.0f}" ry="5" fill="#000" fill-opacity="0.12"/>')
        if who == "goliath" and s["clip"] == "down":   # lying on his face, head toward the viewer (+Z)
            fx0, fy0 = X(x), Z(z); hx, hy = X(x + 0.05), Z(z + 0.72)
            col = "#9c5b18"; w = max(3, 0.026 * S)
            for dx in (-0.04, 0.04):
                o.append(f'<line x1="{X(x+dx):.0f}" y1="{fy0:.0f}" x2="{(fx0+hx)/2:.0f}" y2="{(fy0+hy)/2:.0f}" stroke="{col}" stroke-width="{w:.1f}" stroke-linecap="round"/>')
            o.append(f'<line x1="{(fx0+hx)/2:.0f}" y1="{(fy0+hy)/2:.0f}" x2="{hx:.0f}" y2="{hy:.0f}" stroke="{col}" stroke-width="{w*1.3:.1f}" stroke-linecap="round"/>')
            o.append(f'<circle cx="{hx - 0.1*S:.0f}" cy="{(fy0+hy)/2+8:.0f}" r="{0.08*S:.0f}" fill="#d9b26f" stroke="{col}" stroke-width="2"/>')
            o.append(f'<line x1="{X(x+0.15):.0f}" y1="{Z(z+0.05):.0f}" x2="{X(x+0.05):.0f}" y2="{Z(z+0.7):.0f}" stroke="#555" stroke-width="{w*0.6:.1f}"/>')
            o.append(f'<circle cx="{hx:.0f}" cy="{hy:.0f}" r="{0.07*S:.0f}" fill="#fff" stroke="{col}" stroke-width="{w:.1f}"/>')
            o.append(f'<path d="M{hx-0.07*S:.0f},{hy:.0f} A{0.07*S:.0f},{0.07*S:.0f} 0 0 1 {hx+0.07*S:.0f},{hy:.0f} Z" fill="#c9a227"/>')
            o.append(f'<text x="{hx+0.09*S:.0f}" y="{hy-0.06*S:.0f}" font-size="18" fill="#c9a227">★ ★</text>')
        else:
            o.append(figure(who, s["clip"], X(x), Z(z), h, facing))
    o.append("</g>")
    # fx / sfx badges active around the key time
    fx = [f["id"] for f in FX if f["t"] - 0.6 <= key <= f["t"] + f["dur"] + 0.6]
    sfx = sorted({f["id"] for f in SFX if shot["t0"] <= f["t"] < shot["t1"]})
    mus = [m["cue"] for m in MUSIC if m["t"] <= key][-1]
    stone_fx = shot["id"] == "S09"
    if stone_fx:  # draw the stone path
        d, g = st["david"]["pos"], st["goliath"]["pos"]
        x0, y0 = X(d[0]) + 0.08 * S, Z(d[1]) - 0.30 * S
        x1, y1 = X(g[0]), Z(g[1]) - 0.74 * S
        o.append(f'<path d="M{x0:.0f},{y0:.0f} Q{(x0+x1)/2:.0f},{min(y0,y1)-40:.0f} {x1:.0f},{y1:.0f}" fill="none" stroke="#e4572e" stroke-width="3" stroke-dasharray="6 5"/>')
        o.append(f'<circle cx="{x1:.0f}" cy="{y1:.0f}" r="14" fill="#ffd166" fill-opacity="0.8"/>')
    # header
    o.append(f'<rect x="0" y="0" width="{W}" height="46" fill="#fdf8ee"/>')
    o.append(f'<text x="18" y="31" font-family="PingFang SC, Hiragino Sans GB, sans-serif" font-size="17" font-weight="700" fill="#333">'
             f'{shot["id"]}  {shot["t0"]:.1f}–{shot["t1"]:.1f}s  {shot["title_zh"]} · {shot["title_en"]}</text>')
    o.append(f'<text x="{W-18}" y="31" text-anchor="end" font-family="Menlo, monospace" font-size="12" fill="#666">'
             f'CAM {cam["type"]}→{cam["target"]}</text>')
    tags = [("FX", "#e4572e", fx), ("SFX", "#2a9d8f", sfx[:4] + (["…"] if len(sfx) > 4 else [])), ("♪", "#7b2cbf", [mus])]
    y = STAGE_H - 12 - 22 * (len([t for t in tags if t[2]]) - 1)
    for lab, c, items in tags:
        if not items: continue
        txt = f'{lab}: ' + ", ".join(items)
        o.append(f'<text x="14" y="{y:.0f}" font-family="Menlo, monospace" font-size="12" fill="{c}" stroke="#fff" stroke-width="3" paint-order="stroke">{txt}</text>')
        y += 22
    ln = line_at(shot["t0"], shot["t1"], key)
    if ln:
        who = {"narrator": "旁白 Narrator", "david": "大卫 David", "goliath": "歌利亚 Goliath", "saul": "扫罗 Saul",
               "soldiers": "士兵 Soldiers"}[ln["who"]]
        o.append(f'<text x="16" y="{STAGE_H+28}" font-family="PingFang SC, Hiragino Sans GB, sans-serif" font-size="15" fill="#555">{ln["id"]} · {who}</text>')
        o.append(f'<text x="16" y="{STAGE_H+55}" font-family="PingFang SC, Hiragino Sans GB, sans-serif" font-size="19" fill="#222">{ln["zh"]}</text>')
        o.append(f'<text x="16" y="{STAGE_H+82}" font-family="Helvetica, Arial, sans-serif" font-size="16" fill="#222">{ln["en"]}</text>')
    else:
        o.append(f'<text x="16" y="{STAGE_H+55}" font-family="Helvetica, sans-serif" font-size="16" font-style="italic" fill="#666">(no line: action and sound only)</text>')
    o.append("</svg>")
    return "\n".join(o)


def render_frames():
    tmp = tempfile.mkdtemp()
    pngs = []
    for s in SHOTS:
        svg = frame_svg(s)
        p_svg = os.path.join(HERE, f"{s['id']}.svg"); open(p_svg, "w").write(svg)
        html = os.path.join(tmp, f"{s['id']}.html")
        open(html, "w").write(f'<html><head><meta charset="utf-8"></head><body style="margin:0">{svg}</body></html>')
        png = os.path.join(HERE, f"{s['id']}.png")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                        f"--screenshot={png}", f"file://{html}"], check=True, capture_output=True)
        pngs.append(png)
    cols = 3; rows = math.ceil(len(pngs) / cols); pad = 16; th = 56
    board = Image.new("RGB", (cols * W + (cols + 1) * pad, rows * H + (rows + 1) * pad + th), "#fdf8ee")
    d = ImageDraw.Draw(board)
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 30)
    except Exception:
        font = None
    d.text((pad, 12), f"大卫与歌利亚 · David & Goliath — storyboard ({DURATION:.0f} s, {len(SHOTS)} shots)", fill="#333", font=font)
    for i, p in enumerate(pngs):
        im = Image.open(p).convert("RGB")
        board.paste(im, (pad + (i % cols) * (W + pad), th + pad + (i // cols) * (H + pad)))
    board.save(os.path.join(HERE, "board.png"))
    return pngs


# ---------------------------------------------------------------- STORYBOARD.md
WHO_NAME = {"narrator": "Narrator", "david": "David", "goliath": "Goliath", "saul": "Saul (off)", "soldiers": "Soldiers (off)"}


def write_board_md(tl):
    o = ["# David & Goliath — storyboard", "",
         "> Generated by `docs/david-goliath/storyboard/build_storyboard.py` from the same data as "
         "`assets/david-goliath/timeline.json`. Edit the script, not this file.", "",
         f"Duration **{DURATION} s**, {len(SHOTS)} shots, {len(LINES)} lines. Contact sheet: "
         "[`storyboard/board.png`](storyboard/board.png). Story and line list: [STORY.md](STORY.md).", "",
         "## Conventions for every role", "",
         "- Positions are CONTRACT section 2 art-width units (XZ on the page). Both actors start on their default marks "
         "(David −0.25, 0; Goliath 0.22, 0).",
         "- **Staging:** Goliath stays at the back of the page (z ≈ −0.25), David in front (z ≥ 0). Goliath falls toward "
         "+Z (the viewer), so his 0.8-tall body lands beside David, never on him.",
         "- `acting` entries start a clip at `t` and hold it until the next entry for that actor. A one-shot clip that ends "
         "early should hold its last frame (except `fall`, which hands over to `down`). Walking to `to` uses the clip's "
         "own speed; the next entry for that actor is the latest arrival time.",
         "- `face` is `david`, `goliath` or `viewer` (+Z, toward the phone). `viewer` is a contract clarification, see the "
         "request in the Story report.",
         "- `camera` is a hint for the demo / cinematic view (as in `web/battle`); in live AR the phone is the camera and "
         "Integration may ignore it. `yawDeg` 0 = looking from +Z; positive = orbiting toward +X. Orbit speed: about 8°/s.",
         "- Music: a new cue crossfades out the previous one (0.6 s). `sting_hit` is a one-shot; silence after it until "
         "`theme_victory`.",
         "- Lines: subtitles show the current language only; `maxSec` is the hard budget for the recorded clip. A line by "
         "David or Goliath runs while that actor is in `talk` (jaw flap).", "",
         "## Expected clip lengths (for Animation)", "",
         "| Clip | Length | Clip | Length |", "|---|---|---|---|",
         "| david_kneel_pick | 3.0 s (one stone lifted) | goliath_taunt | ≤ 1.2 s (spear shake) |",
         "| david_sling_release | 0.6 s, stone leaves pouch at 0.15 s | goliath_laugh | 1.2–2.0 s |",
         "| david_victory | ≤ 2.0 s (jump, arms up) | goliath_roar | 1.2 s |",
         "| david_pray | loop or hold (head bowed, hands together) | goliath_hit_react | 0.9 s (head snaps back) |",
         "| david_run | loop, ~0.6 art-width/s | goliath_fall | 1.6 s, forward onto the face, lands at +1.2 s |",
         "| david_sling_windup | loop, 1 turn ≈ 0.5 s | goliath_charge | loop, slow, ~0.1 art-width/s |", "",
         "## Shots", ""]
    for s in SHOTS:
        c = s["camera"]
        acts = [a for a in tl["acting"] if s["t0"] <= a["t"] < s["t1"]]
        o += [f"### {s['id']} · {s['t0']:.1f}–{s['t1']:.1f} s · {s['title_zh']} / {s['title_en']}", "",
              f"![{s['id']}](storyboard/{s['id']}.png)", "",
              f"- **Camera:** {c['type']} on {c['target']}, dist {c['dist']}, height {c['height']}, yaw {c['yawDeg']}°",
              f"- **Action:** {s['desc']}",
              f"- **Direction:** {s['note']}",
              "- **Acting:** " + "; ".join(
                  f"{a['t']:.2f} {a['who']} `{a['clip']}`" + (f" → ({a['to'][0]}, {a['to'][1]})" if 'to' in a else "")
                  + (f" face {a['face']}") for a in acts)]
        ls = [l for l in LINES if s["t0"] <= l["t"] < s["t1"]]
        for l in ls:
            o.append(f"- **Line `{l['id']}`** {l['t']:.1f} s ({l['maxSec']} s max) · {WHO_NAME[l['who']]}: "
                     f"「{l['zh']}」 / “{l['en']}” — {l['ref']}")
        if not ls: o.append("- **Line:** none (action and sound only)")
        fx = [f"{f['t']:.2f} `{f['id']}` @ {f['at']} {f['dur']} s" for f in FX if s["t0"] <= f["t"] < s["t1"]]
        sfx = [f"{f['t']:.2f} `{f['id']}`" for f in SFX if s["t0"] <= f["t"] < s["t1"]]
        mus = [f"{m['t']:.2f} `{m['cue']}`" for m in MUSIC if s["t0"] <= m["t"] < s["t1"]]
        o.append("- **FX:** " + ("; ".join(fx) or "—"))
        o.append("- **SFX:** " + ("; ".join(sfx) or "—"))
        o.append("- **Music:** " + ("; ".join(mus) or "(continues)"))
        o.append("")
    o += ["## Delivery lists", "",
          "**FX ids (Effects → `DGFx.Play`):** " + ", ".join(f"`{i}`" for i in dict.fromkeys(f["id"] for f in FX)), "",
          "**SFX ids (Music & SFX → `audio/sfx/<id>.wav`):** " + ", ".join(f"`{i}`" for i in dict.fromkeys(f["id"] for f in SFX)), "",
          "**Music cues (Music & SFX → `audio/music/<cue>.wav`):** " + ", ".join(
              f"`{m['cue']}` ({m['t']:.1f}–{(MUSIC[i+1]['t'] if i+1 < len(MUSIC) else DURATION):.1f} s)" for i, m in enumerate(MUSIC)), "",
          "**Voice lines (Voice → `audio/voice/{zh,en}/<id>.wav`):** " + ", ".join(f"`{l['id']}`" for l in LINES), ""]
    open(BOARD_MD, "w").write("\n".join(o))


def write_story_lines():
    """Replace the block between the LINES markers in STORY.md with the current line list."""
    start, end = "<!-- LINES:BEGIN (generated by storyboard/build_storyboard.py) -->", "<!-- LINES:END -->"
    md = open(STORY_MD).read()
    rows = ["| id | time | who | 中文 | English | ref | max s (zh est / en est) |", "|---|---|---|---|---|---|---|"]
    for l in LINES:
        z, e = est(l)
        rows.append(f"| `{l['id']}` | {l['t']:.1f} | {WHO_NAME[l['who']]} | {l['zh']} | {l['en']} | {l['ref']} | "
                    f"{l['maxSec']} ({z:.1f} / {e:.1f}) |")
    a, b = md.index(start) + len(start), md.index(end)
    open(STORY_MD, "w").write(md[:a] + "\n" + "\n".join(rows) + "\n" + md[b:])


def main():
    tl = build_timeline()
    err, unused = validate(tl)
    for l in LINES:
        z, e = est(l)
        print(f"{l['id']} t={l['t']:5.1f} max={l['maxSec']:.1f} zh={zh_chars(l['zh']):2d}ch {z:.2f}s en={en_words(l['en']):2d}w {e:.2f}s")
    if unused: print("unused clips:", ", ".join(unused))
    if err:
        print("INVALID:"); [print("  -", e) for e in err]; sys.exit(1)
    os.makedirs(os.path.dirname(TIMELINE), exist_ok=True)
    with open(TIMELINE, "w") as f:
        json.dump(tl, f, ensure_ascii=False, indent=1)
        f.write("\n")
    write_board_md(tl)
    write_story_lines()
    if "--no-frames" not in sys.argv:
        pngs = render_frames()
        print("frames:", len(pngs), "board:", Image.open(os.path.join(HERE, "board.png")).size)
    print("timeline OK:", TIMELINE)


if __name__ == "__main__":
    main()
