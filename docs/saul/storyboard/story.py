"""Saul Sees the Light! — the play, as beats relative to each other (docs/saul/CONTRACT.md §5).

`tools/story/build_timeline.py saul` turns this into assets/saul/timeline.json, placing every line by the real voice
durations (an estimate until the voices exist). Helpers: shot / line / act / fx / sfx / music / prop / pause (same as
every pack), plus `path()`, `hide()` and `voice_light()` below.
Marks are art-width units on the page (x right, z toward the viewer); the set's marks are in CONTRACT.md §6.
`face` takes an actor id, "viewer", or a set node name ("priestPorch", "judasHouse", "cityGate", "jerusalemDoor").

One page, three places: Jerusalem (right back: the high priest's porch and a small house), the desert road (right
and front: from the porch round the front of the page to the city gate), and Damascus (left half, behind a city wall
that runs front-to-back at x = 0 with the gate in it and a window high in its outside face; inside, along Straight
Street, Ananias's house, the synagogue steps and Judas's house, the two houses open at the front like doll's houses).

Staging rules (learned in Jonah, Miracles, The King Who Serves and He Is Risen!):
- An actor who is not in a scene is HIDDEN and PARKED (`hide()`): moved with snap=True to PARK, beyond the page.
- No camera targets "all": shots target an actor or a set node. Start values here; the lead re-frames at staging so
  the speaker is never behind someone (S05 the lead-by-the-hand pair, S08 Ananias at the seated Saul, S10 the
  listeners round the steps, S12 the three at the door are the risky ones).
- `orbit` turns 6 deg/s: no orbit shot in this pack.
- Moves between places (Jerusalem -> road -> Damascus -> Jerusalem) happen ON A SHOT CUT with snap=True; no clip
  carries an actor from one place to another.
- Multi-leg moves use `path()`: each leg starts when the previous one ends at the clip's planned speed (V_*), so
  StoryDirector never cuts a walk short. The planned speeds are guesses until `assets/saul/anim/clips.json` exists;
  after Animation the lead sets V_* to the real naturalSpeed and re-runs build_timeline.py (it warns on short walks).
- Jesus is never shown in body: He is a light (`road_light` on the road, `angel_light` in Ananias's house) and His
  voice (who="jesus", not in CAST; StoryDirector skips the talking-head for a speaker with no actor).
- The basket: Saul's own prop (`saul/basket`, with two ropes up to the window); the descent is inside the one-shot
  clip `basket_down` (the base stays on the ground at BASKET_DOWN; the clip lowers hips and basket from the window
  to the ground and stretches the ropes; RIG.md / ANIMATION.md say how). Nobody glides.
- Props take their colour from printed regions (CONTRACT §3); a prop is shown only while it is in a hand.
- SFX are one-shots sized to their scene (StoryDirector stops a loop only at a music cue).
- Effect durations end at the shot change (F2); they are set from the estimate and re-set after the voices re-time.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py
import math

ID = "saul"
CAST = ["saul", "ananias", "barnabas", "judas", "priest", "tallguard", "shortguard", "peter"]
SET = "damascus"

PARK = (0.80, 0.30)            # hidden actors wait here, beyond the page
PORCH_Y = 0.04                 # floor of the high priest's porch (two steps up)
STEP_Y = 0.04                  # top step of the synagogue
# planned travel speeds (art units / s); Animation writes the real ones in clips.json, the lead updates these
V_MARCH = 0.110                # Saul's angry stomping march (the fastest walker in the first half)
V_PUFF = 0.085                 # the guards trotting behind him, puffing
V_WALK = 0.090                 # an ordinary walk (Saul after he changes, Barnabas, Judas, Peter)
V_BLIND = 0.050                # Saul led by the hand, slow and careful (and the guard leading him)
V_TIPTOE = 0.060               # Ananias's nervous tiptoe; Saul tiptoeing away from the wall

# Jerusalem (right back; floor y 0). The porch x 0.34..0.60, z -0.5875..-0.36, floor PORCH_Y, steps down to z -0.30.
PRIEST = (0.47, -0.42)         # on the porch, under the columns, facing the steps
SAUL_PORCH = (0.42, -0.24)     # at the foot of the steps (the lower step's front edge is z -0.30)
JHOUSE_DOOR = (0.24, -0.33)    # the believers' house (x 0.16..0.32, front face z -0.423): outside its door (at -0.37
                               # and -0.35 Peter's left arm went into the house front in `peek_afraid`)
# The road (front and right; y 0): porch -> right side -> front -> the light -> the city gate
ROAD_A = (0.46, -0.22)
ROAD_B = (0.48, -0.02)
ROAD_C = (0.40, 0.12)
ROAD_STOP = (0.30, 0.13)       # S02: Saul stops and turns back to scold the guards
LIGHT = (0.18, 0.08)           # S03-S04: where the light finds him (the open front, nothing tall near)
ROAD_D = (0.13, -0.01)
ROAD_E = (0.10, -0.10)
GATE_OUT = (0.09, -0.16)       # just outside the gate (the gateway is z -0.22..-0.10 through the wall x -0.03..0.03)
GATE_IN = (-0.09, -0.16)       # just inside it, on Straight Street
# Damascus (left; floor y 0). Straight Street z -0.28..-0.08 from the gate to the left edge.
ANANIAS_HOME = (-0.465, 0.08)  # inside Ananias's house (front left: x -0.60..-0.33, room 0.24 wide, open front z 0.20)
SYN_STEP = (-0.37, -0.36)      # top step of the synagogue (facade x -0.44..-0.30 at z -0.40), y STEP_Y
SAUL_MAT = (-0.15, -0.46)      # inside Judas's house (x -0.28..-0.03, open front at z -0.30): the prayer mat
JUDAS_IN = (-0.21, -0.37)      # Judas inside, left of the doorway (not used after staging: it is between the camera and Saul)
JUDAS_SIDE = (-0.22, -0.42)    # S06 / S08: Judas beside the seated Saul, on his left (= ANANIAS_POUR, 0.081 from Saul)
JUDAS_DOOR = (-0.13, -0.27)    # in front of the door frame (posts at x -0.20 and -0.06 on the open front), street side
ANANIAS_TOUCH = (-0.08, -0.42) # beside the seated Saul, 0.08 away (`hands_on` pair distance)
ANANIAS_POUR = (-0.22, -0.42)  # S09: left of the kneeling Saul, 0.08 away, the jug over his head
# Outside the wall (right of x 0.03): the window is high in the wall's outside face at z -0.46, y 0.20..0.27
BASKET_DOWN = (0.095, -0.46)   # the basket (0.10 across) lands here, 0.015 clear of the wall face; the house starts at x 0.16
SAUL_BASKET = (0.095, -0.38)   # Saul's root for basket_wait / basket_down / basket_out (the basket hangs 0.08 behind him)
TALL_GATE = (0.12, -0.04)      # S11: the tall guard in front of the gate, lantern up, looking down the road
SHORT_GATE = (0.19, -0.11)     # S11: the short guard right of the gate (at (0.11, -0.27) his arm went into the back
                               # tower); Saul tiptoes behind his back


def path(who, clip, pts, dt, v, face=None):
    """Walk / run `who` through the marks `pts` (the first is where it stands): one act per leg, each leg timed at the
    planned speed v so the next leg starts when this one ends. The last leg faces `face` (else the direction of travel
    is left to the director). Returns (events, seconds)."""
    out, t = [], dt
    for a, b in zip(pts, pts[1:]):
        out.append(act(who, clip, to=b, face=face if b == pts[-1] else None, dt=round(t, 3)))
        t += math.dist(a, b) / v
    return out, round(t - dt, 3)


def hide(who, dt=0.0):
    """Park an actor beyond the page and hide it (on a cut)."""
    return [act(who, "idle", to=PARK, snap=True, dt=dt), prop(who, show=False, dt=dt)]


def show(who, clip, to, face, y=0.0, dt=0.0):
    """Place an actor on a cut and make sure it is visible."""
    return [act(who, clip, to=to, y=y, face=face, snap=True, dt=dt), prop(who, show=True, dt=dt)]


def voice_light(at, dur, dt=0.0):
    """The Lord speaks from a light (never a body): a soft column on `at` with a warm chime."""
    return [fx("angel_light", at, dur=dur, dt=dt), sfx("appear_chime", dt=dt + 0.2)]


# S01: Saul paces angrily up and down in front of the porch while the narrator introduces him (his idle face is the
# kind one, faces.json, so he never idles before S06), and stops facing the priest just before he speaks
PACE_B = (0.52, -0.17)
_pace, T_PACE = path("saul", "march", [(0.44, -0.10), SAUL_PORCH, PACE_B, SAUL_PORCH, PACE_B, SAUL_PORCH, PACE_B,
                                       SAUL_PORCH], 0.4, V_MARCH, face="priest")
# S02: Saul marches round the road and stops at ROAD_STOP; the guards puff after him and stop behind (0.14 / 0.22)
_saul_march, T_MARCH = path("saul", "march", [ROAD_A, ROAD_B, ROAD_C, ROAD_STOP], 0.0, V_MARCH, face="shortguard")
_short_puff, T_SHORT = path("shortguard", "walk_puff", [(0.38, -0.26), (0.44, -0.04), (0.44, 0.08)], 1.4, V_PUFF,
                            face="saul")
_tall_puff, T_TALL = path("tallguard", "walk_puff", [(0.56, -0.25), (0.53, -0.02), (0.53, 0.03)], 1.0, V_PUFF,
                          face="saul")
# S05: the tall guard leads Saul by the hand to the gate and through it, 0.14 ahead on the same line (ANIMATION.md §2:
# at 0.14 the hands meet). Saul starts 0.76 s after the guard (LIGHT -> ROAD_D is 0.103 at V_BLIND) and ends in the
# gateway, still 0.14 behind him. The short guard follows at walking pace, starting late enough to stay >= 0.12 behind.
_lead, T_LEAD = path("tallguard", "lead_hand", [ROAD_D, ROAD_E, GATE_OUT, GATE_IN], 0.0, V_BLIND, face="cityGate")
_blind, T_BLIND = path("saul", "walk_blind", [LIGHT, ROAD_D, ROAD_E, GATE_OUT, (0.05, -0.16)], 0.76, V_BLIND,
                       face="tallguard")
_follow, _ = path("shortguard", "walk", [(0.33, 0.03), LIGHT, ROAD_D], 2.6, V_WALK, face="saul")
# S08: Ananias tiptoes along Straight Street to Judas's doorway
# (3.3 s: it ends while the narrator's sa_21 is still speaking, so the knock can follow that line)
_tiptoe, T_TIPTOE = path("ananias", "tiptoe", [(-0.30, -0.20), (-0.20, -0.23), JUDAS_DOOR], 0.2, V_TIPTOE,
                         face="judasHouse")
# S11: out of the basket, Saul tiptoes away from the wall foot, behind the dozing guard's back. One leg (1.0 s), timed
# to end just before the cut (a later leg would fire after the S12 snap and walk him in Jerusalem).
_away, T_AWAY = path("saul", "tiptoe", [SAUL_BASKET, (0.13, -0.33)], 1.55, V_TIPTOE)

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "生气的扫罗", "Angry Saul", "fixed", "priestPorch", dist=0.6, height=0.24, yawDeg=25,
         desc="Jerusalem, a bright morning. Saul, a young man with a dark beard and a frown, stomps up to the high "
              "priest's porch, fists tight. The old high priest, calm and unsmiling, hands him a rolled-up letter. "
              "Saul holds it up and marches off."),
    music("angry_march"),
    act("saul", "march", to=(0.44, -0.10), face="priest", snap=True),
    *_pace,
    act("priest", "idle", to=PRIEST, y=PORCH_Y, face="saul", snap=True),
    *hide("ananias"), *hide("barnabas"), *hide("judas"), *hide("peter"), *hide("tallguard"), *hide("shortguard"),
    prop("saul/letters", show=False), prop("saul/basket", show=False), prop("saul/bread", show=False),
    prop("ananias/jug", show=False), prop("judas/bread", show=False), prop("tallguard/lantern", show=False),
    pause(0.6),
    line("sa_01", "narrator", "耶路撒冷有个年轻人叫扫罗。他很生气，想把跟随耶稣的人都抓起来。",
         "In Jerusalem lived a young man called Saul. He was angry, and wanted to arrest everyone who followed Jesus.",
         "Acts 22:3; 8:3; 9:1-2", dir="storyteller, clear and lively; plain and calm on 抓 / 'arrest' (the only "
         "sentence about it), a small frown on 生气 / 'angry'", post=0.3),
    act("saul", "angry_talk", face="priest", dt=-2.4),            # fumes from the end of his pacing
    line("sa_02", "saul", "大祭司，给我写几封信吧！我要去大马士革，把他们都带回来！",
         "High priest, give me letters! I'll go to Damascus and bring them all back!",
         "Acts 9:1-2; 22:5", dir="young, hot-headed, sure of himself; loud but not shouting; a stamp on 都 / 'all'",
         pre=0.2, post=0.2),
    act("priest", "give_letters", face="saul", dt=-0.3), prop("saul/letters", show=True, dt=1.13),   # take_letters `grab`
    act("saul", "take_letters", face="priest", dt=0.8),
    line("sa_03", "priest", "好吧，信在这里。去吧。",
         "Very well. Here are your letters. Go.",
         "Acts 9:2; 26:12", dir="an old, dry, calm voice; neither kind nor cruel; unhurried", pre=1.2, post=0.2),
    act("saul", "march", to=(0.46, -0.12), face="viewer", dt=-0.2),   # arrives before the cut
    pause(0.6),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "去大马士革", "The road to Damascus", "follow", "saul", dist=0.6, height=0.2, yawDeg=30,
         desc="The hot desert road: sand, rocks, one palm. Saul marches ahead with the letter in his belt; two temple "
              "guards, one tall and thin, one short and round, puff along behind him. He stops and scolds them."),
    music("road"),
    *hide("priest"),
    act("saul", "march", to=ROAD_A, face="viewer", snap=True),
    *show("shortguard", "idle", (0.38, -0.26), "saul"), *show("tallguard", "idle", (0.56, -0.25), "saul"),
    *_saul_march, *_short_puff, *_tall_puff,
    act("saul", "angry_talk", face="shortguard", dt=round(T_MARCH, 2)),
    act("shortguard", "puff", face="saul", dt=round(1.4 + T_SHORT, 2)),
    act("tallguard", "puff", face="saul", dt=round(1.0 + T_TALL, 2)),
    fx("dust_road", "saul.root", dur=round(T_MARCH, 1), dt=0.0), sfx("march_steps", dt=0.0),
    line("sa_04", "narrator", "扫罗带着两个卫兵出发了。路又长又热。",
         "Saul set off with two guards. The road was long and hot.",
         "Acts 9:3, 7; 26:12", dir="brisk, a marching rhythm in the words",
         pre=0.6, post=0.2),
    act("shortguard", "talk", face="saul", dt=0.0),
    line("sa_05", "shortguard", "扫罗大人，歇一会儿吧！我的脚都走扁了！",
         "Master Saul, can we rest? My feet are flat as pancakes!",
         "Acts 9:3", dir="a round, puffing comic voice; out of breath; whiny, funny", pre=0.2, post=0.2),
    line("sa_06", "saul", "不歇！大马士革就在前面。走！",
         "No rest! Damascus is just ahead. March!",
         "Acts 9:3", dir="impatient, bossy, clipped", pre=0.1, post=0.2),
    act("saul", "march", to=LIGHT, face="viewer", dt=0.55),          # arrives just before the cut
    act("tallguard", "shrug", face="shortguard", dt=0.1), act("shortguard", "idle", face="tallguard", dt=0.3),
    pause(1.6),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "天上的光", "A light from heaven", "fixed", "saul", dist=0.7, height=0.34, yawDeg=15,
         desc="Near the city, at noon. Suddenly a great light, brighter than the sun, pours down from the sky all "
              "round Saul: warm white and gold, wonderful, not frightening. Saul shields his eyes and sits down hard "
              "in the road; the two guards duck and cover their heads."),
    music("light"),
    act("saul", "march", to=(0.27, 0.10), face="viewer", snap=True),   # marches into the light (0.092 in 0.84 s)
    act("saul", "march", to=LIGHT, face="viewer", dt=0.4),
    act("shortguard", "walk_puff", to=(0.40, 0.05), face="saul", snap=True),
    act("tallguard", "walk_puff", to=(0.45, 0.13), face="saul", snap=True),
    act("shortguard", "walk_puff", to=(0.33, 0.03), face="saul", dt=0.4),
    act("tallguard", "walk_puff", to=(0.38, 0.12), face="saul", dt=0.6),
    fx("road_light", "saul.root", dur=31.59, dt=0.9),          # S03 + S04; ends at the S05 cut (F2)
    sfx("light_whoosh", dt=0.9),
    act("saul", "fall_down", face="viewer", dt=1.3), sfx("sit_thud", dt=2.0),
    act("shortguard", "duck", face="saul", dt=1.5), act("tallguard", "duck", face="saul", dt=1.7),
    line("sa_07", "narrator", "忽然，一道比太阳还亮的光从天上照下来！扫罗一下子坐倒在地上。",
         "Suddenly a light brighter than the sun shone from heaven, and Saul fell to the ground.",
         "Acts 9:3-4; 26:13", dir="wonder, building fast; bright and amazed, never scary; a soft drop on the fall",
         pre=2.6, post=0.5),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "扫罗，扫罗", "Saul, Saul", "fixed", "saul", dist=0.5, height=0.22, yawDeg=-20,
         desc="Saul sits in the road inside the light, one arm up against the brightness, looking up. A voice speaks "
              "from the light: it is Jesus. Behind him the guards peep out from under their arms: they hear a sound "
              "but see no one."),
    act("saul", "sit_look_up", face="viewer"),
    line("sa_08", "jesus", "扫罗，扫罗，你为什么跟我作对？",
         "Saul, Saul, why are you against Me?",
         "Acts 9:4", dir="calm, warm, very clear; sad and loving, not angry; the same Jesus as in Real Miracles",
         pre=0.6, post=0.4),
    line("sa_09", "saul", "主啊，你是谁？",
         "Lord... who are You?",
         "Acts 9:5", dir="small and shaken, all the anger gone; almost a whisper", pre=0.2, post=0.4),
    line("sa_10", "jesus", "我就是耶稣。你跟我的朋友作对，就是跟我作对。",
         "I am Jesus. When you are against My friends, you are against Me.",
         "Acts 9:5; 22:8", dir="gentle and firm; the heart of the scene; slow on 我就是耶稣 / 'I am Jesus'",
         pre=0.3, post=0.3),
    line("sa_11", "jesus", "起来，进城去，会有人告诉你该做什么。",
         "Get up and go into the city. You will be told what to do.",
         "Acts 9:6; 22:10", dir="kind, a fresh start in the voice", pre=0.2, post=0.3),
    act("tallguard", "amazed", face="shortguard", dt=0.0), act("shortguard", "amazed", face="tallguard", dt=0.2),
    line("sa_12", "tallguard", "有声音……可是一个人也没有！",
         "I heard a voice... but there's nobody here!",
         "Acts 9:7", dir="whispered, wide-eyed, comic", pre=0.4, post=0.4),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "看不见了", "I can't see", "follow", "saul", dist=0.6, height=0.2, yawDeg=25,
         desc="The light is gone. Saul stands up with his eyes open but sees nothing; he holds his hands out. The "
              "tall guard takes his hand and leads him slowly to the city gate; the short guard walks behind."),
    music("dark_walk"),
    act("saul", "get_up_blind", face="viewer", dt=0.2),
    # on the cut the tall guard stands behind Saul (from (0.34, 0.13) a walk to ROAD_D passed 0.05 from Saul and the
    # short guard); he walks round behind Saul to ROAD_D (0.149 in 1.7 s), ready to take his hand
    act("tallguard", "idle", to=(0.27, -0.05), face="saul", snap=True),
    act("tallguard", "walk", to=ROAD_D, face="saul", dt=0.6),
    act("tallguard", "idle", face="saul", dt=3.6),
    line("sa_13", "saul", "我睁着眼睛，可是……什么也看不见。",
         "My eyes are open... but I can't see anything.",
         "Acts 9:8", dir="quiet, puzzled, not afraid; slow", pre=1.6, post=0.3),
    *_lead, *_blind, *_follow,
    line("sa_14", "narrator", "卫兵拉着扫罗的手，慢慢把他领进了大马士革。",
         "So the guards took Saul by the hand and led him into Damascus.",
         "Acts 9:8; 22:11", dir="tender, slow, walking pace", pre=0.6, post=1.2),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "直街上的房子", "The house on Straight Street", "fixed", "judasHouse", dist=0.5, height=0.22,
         yawDeg=0,
         desc="Inside Judas's house on Straight Street. Saul sits on a mat with his eyes closed, praying, a soft glow "
              "round him. Kind Judas offers him bread; Saul gently shakes his head and goes on praying."),
    music("three_days"),
    *hide("tallguard"), *hide("shortguard"),
    act("saul", "sit_pray", to=SAUL_MAT, face="viewer", snap=True),
    *show("judas", "idle", JUDAS_SIDE, "saul"), prop("judas/bread", show=True),
    prop("saul/letters", show=False),
    fx("prayer_glow", "saul.root", dur=11.82, dt=0.6),        # ends at the S07 cut (F2)
    act("judas", "offer_bread", face="saul", dt=3.0),     # in place (Judas has no walk clip; `to` would glide)
    act("judas", "idle", face="saul", dt=7.0),
    line("sa_15", "narrator", "在犹大家里，扫罗三天看不见，不吃也不喝，一直祷告。",
         "At Judas's house, Saul could not see for three days. He did not eat; he prayed.",
         "Acts 9:9, 11", dir="gentle, unhurried; no sadness on 不吃也不喝 / 'did not eat'", pre=0.8, post=0.3),
    line("sa_16", "saul", "主耶稣，我错了。你要我做什么？",
         "Lord Jesus, I was wrong. What do You want me to do?",
         "Acts 9:11; 22:10", dir="a quiet, honest prayer; humble, eyes closed; no tears", pre=0.3, post=0.8),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "亚拿尼亚", "Ananias", "fixed", "ananiasHouse", dist=0.5, height=0.2, yawDeg=10,
         desc="Ananias's little house down the street. Ananias, a small round man with a grey beard, kneels to pray. "
              "A soft light fills the room and the Lord speaks to him. When he hears the name Saul he jumps up, "
              "knees knocking; then he swallows hard and goes."),
    music("ananias"),
    *hide("judas"), prop("judas/bread", show=False),
    *show("ananias", "kneel_pray", ANANIAS_HOME, "viewer"),
    *voice_light("damascus.ananiasHouse", dur=24.92, dt=0.4),  # ends at the S08 cut (F2)
    act("ananias", "kneel_look_up", face="viewer", dt=1.0),
    line("sa_17", "jesus", "亚拿尼亚，去直街犹大的家，找一个叫扫罗的人。他正在祷告。",
         "Ananias, go to Judas's house on Straight Street. Saul is there, praying.",
         "Acts 9:10-12", dir="calm, kind, calling a friend", pre=1.4, post=0.3),
    act("ananias", "startle", face="viewer", dt=-0.2),
    line("sa_18", "ananias", "扫罗？是那个扫罗？！主啊，他是来抓你的人的呀！",
         "Saul? THAT Saul?! But Lord, he came to arrest Your people!",
         "Acts 9:13-14", dir="the comic beat: an older, fussy voice squeaking in alarm, words tumbling out; "
         "frightened in a funny way", pre=0.6, post=0.3),
    act("ananias", "nervous", face="viewer", dt=0.2),
    line("sa_19", "jesus", "去吧！我拣选了他，要他把我告诉全世界。",
         "Go! I have chosen him to tell the whole world about Me.",
         "Acts 9:15", dir="patient, warm, a smile in it; no scolding", pre=0.3, post=0.3),
    line("sa_20", "ananias", "好……好吧，主，我去。",
         "All... all right, Lord. I'll go.",
         "Acts 9:17", dir="a big gulp, then brave; a little laugh at himself at the end", pre=0.3, post=0.6),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "扫罗弟兄", "Brother Saul", "fixed", "judasHouse", dist=0.55, height=0.22, yawDeg=0,
         desc="Ananias tiptoes along Straight Street to Judas's door and knocks. Inside, he puts his hands gently on "
              "Saul's head. Something like little scales falls from Saul's eyes, sparkling; Saul blinks and sees. "
              "His face lights up."),
    music("brother"),
    act("ananias", "tiptoe", to=(-0.30, -0.20), face="judasHouse", snap=True),
    *show("judas", "idle", JUDAS_SIDE, "viewer"),
    act("saul", "sit_pray", to=SAUL_MAT, face="viewer", snap=True),
    *_tiptoe,
    line("sa_21", "narrator", "亚拿尼亚有点害怕，可他还是去了。",
         "Ananias was a bit scared, but he went.",
         "Acts 9:17", dir="playful storyteller, a twinkle", pre=0.6, post=0.2),
    act("ananias", "knock", face="judasHouse", dt=0.0), sfx("knock", dt=0.2),
    act("judas", "idle", face="ananias", dt=0.8),
    act("ananias", "walk", to=ANANIAS_TOUCH, face="saul", dt=1.2),   # through the doorway, 0.15 in 1.7 s
    act("ananias", "hands_on", face="saul", dt=3.0),
    line("sa_22", "ananias", "扫罗弟兄，主耶稣差我来，叫你能再看见，被圣灵充满。",
         "Brother Saul, Jesus sent me, so you can see again and be filled with the Holy Spirit.",
         "Acts 9:17", dir="gentle and brave; a warm weight on 弟兄 / 'Brother'", pre=3.4, post=0.2),
    fx("scales_fall", "saul.head", dur=1.6, dt=0.2), sfx("sparkle_up", dt=0.2),
    act("saul", "see_again", face="ananias", dt=0.4),
    line("sa_23", "narrator", "立刻，好像有鳞片从扫罗的眼睛上掉了下来！",
         "At once, something like scales fell from Saul's eyes!",
         "Acts 9:18", dir="a delighted lift, wonder", pre=0.2, post=0.2),
    line("sa_24", "saul", "我看见了！你……你叫我弟兄？",
         "I can see! You... you called me brother?",
         "Acts 9:18; 9:17", dir="joy bursting out; then quiet, moved, amazed at 弟兄 / 'brother'", pre=0.2, post=0.2),
    act("ananias", "talk", face="saul", dt=0.0),
    fx("heart_glow", "saul.chest", dur=4.06, dt=0.4),         # ends at the S09 cut (F2)
    line("sa_25", "ananias", "是啊，现在你是我们的弟兄了！",
         "Yes! Now you are our brother!",
         "Acts 9:17", dir="warm, glad, a happy chuckle inside the words", pre=0.2, post=0.5),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "受洗", "Baptised", "fixed", "saul", dist=0.5, height=0.2, yawDeg=0,
         desc="Saul kneels and Ananias pours water over his head from a jug: he is baptised, and he laughs. Then "
              "Judas brings bread, and Saul eats hungrily and happily."),
    music("baptism"),
    act("saul", "kneel", to=SAUL_MAT, face="viewer", snap=True),
    act("ananias", "idle", to=ANANIAS_POUR, face="saul", snap=True), prop("ananias/jug", show=True),
    act("judas", "idle", to=(-0.08, -0.43), face="saul", snap=True), prop("judas/bread", show=True),   # beside, not in front
    act("ananias", "pour", face="saul", dt=0.4),
    fx("water_pour", "ananias.jug", dur=2.0, dt=1.0), sfx("water_splash", dt=1.2),
    fx("sparkle", "saul.head", dur=1.6, dt=2.0),
    line("sa_26", "narrator", "扫罗受了洗，又吃了饭，力气也回来了。",
         "Saul was baptised. Then he ate, and his strength came back.",
         "Acts 9:18-19", dir="bright and happy", pre=0.8, post=0.2),
    prop("ananias/jug", show=False, dt=-1.0), act("ananias", "cheer", face="saul", dt=-0.8),
    act("judas", "offer_bread", face="saul", dt=-1.6),    # in place, beside Saul from the start of the shot
    prop("judas/bread", show=False, dt=-0.2), prop("saul/bread", show=True, dt=-0.2),
    act("saul", "eat_bread", face="viewer", dt=-0.1), sfx("munch", dt=1.1),
    act("judas", "laugh", face="saul", dt=0.8),
    line("sa_27", "saul", "这饼真香！三天没吃了！",
         "This bread is so good! Three days with nothing!",
         "Acts 9:19", dir="mouth half full, laughing, a big grin; the old anger quite gone", pre=1.4, post=0.5),
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "耶稣是神的儿子", "Jesus is God's Son", "fixed", "synagogue", dist=0.6, height=0.22, yawDeg=10,
         desc="The synagogue steps on Straight Street. Saul stands on the top step, arms open, telling everyone "
              "about Jesus. The two temple guards stand at the side, scratching their heads: is this the same Saul?"),
    music("new_saul"),
    prop("saul/bread", show=False), prop("judas/bread", show=False),
    act("saul", "preach", to=SYN_STEP, y=STEP_Y, face="viewer", snap=True),
    # the two guards listen right of the synagogue (Ananias's house now stands at the front left and hides the left
    # part of the street from the front). Ananias and Judas sit this shot out: in Judas's doorway they stood right
    # behind the guards and were never seen (blocking renders); all of them wave together in S13
    *show("tallguard", "listen", (-0.165, -0.20), "saul"), *show("shortguard", "listen", (-0.07, -0.19), "saul"),
    *hide("judas"), *hide("ananias"), prop("ananias/jug", show=False),
    line("sa_28", "saul", "耶稣是神的儿子！他救了我，他也爱你们！",
         "Jesus is the Son of God! He saved me, and He loves you too!",
         "Acts 9:20, 22", dir="glad, warm, strong; the same voice as the angry Saul, now full of joy", pre=0.8,
         post=0.3),
    act("tallguard", "scratch_head", face="saul", dt=-0.2),
    line("sa_29", "tallguard", "咦，这不是那个来抓人的扫罗吗？",
         "Hey, isn't that the Saul who came to arrest people?",
         "Acts 9:21", dir="thin, puzzled, comic", pre=0.3, post=0.2),
    act("shortguard", "amazed", face="saul", dt=-0.3),
    line("sa_30", "shortguard", "他……他完全变了！",
         "He's... he's completely changed!",
         "Acts 9:21-22", dir="gruff, baffled, comic", pre=0.2, post=0.6),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "大筐子", "The big basket", "fixed", "wallWindow", dist=0.6, height=0.26, yawDeg=25,
         desc="Night outside the city wall, torches by the gate. The short guard boasts, then dozes on his feet; the "
              "tall guard holds up a lantern and peers down the road. Behind their backs a big basket comes down the "
              "wall on two ropes from a high window. Saul climbs out, waves up to the window and tiptoes away."),
    music("basket"),
    *hide("judas"), *hide("ananias"),
    fx("night", "stage", dur=30.6), fx("lamp_flame", "damascus.torch1", dur=30.6),   # end at the S12 cut (F2)
    fx("lamp_flame", "damascus.torch2", dur=30.6),
    act("saul", "basket_wait", to=SAUL_BASKET, y=0.0, face="viewer", snap=True), prop("saul/basket", show=True),
    act("tallguard", "lantern_peer", to=TALL_GATE, face="viewer", snap=True), prop("tallguard/lantern", show=True),
    fx("lamp_flame", "tallguard.lantern", dur=30.6),
    act("shortguard", "boast", to=SHORT_GATE, face="viewer", snap=True),
    line("sa_31", "narrator", "有些人很生气，日夜守着城门，要抓扫罗。",
         "Now some angry men watched the gate day and night, to catch Saul.",
         "Acts 9:23-24", dir="a little hush, mock-suspense; not scary", pre=0.8, post=0.2),
    line("sa_32", "shortguard", "有我们守着，连一只老鼠也跑不掉！",
         "Nobody gets past us. Not even a mouse!",
         "Acts 9:24", dir="puffed-up, boastful, comic; a yawn creeping into the end", pre=0.2, post=0.2),
    act("shortguard", "doze", face="viewer", dt=0.2), fx("zzz", "shortguard.head", dur=18.69, dt=0.8),
    sfx("snore", dt=1.0),
    line("sa_33", "narrator", "可是夜里，朋友们让扫罗坐进大筐子，从城墙的窗户里放了下去！",
         "But at night, his friends let Saul down from a window in the wall, in a big basket!",
         "Acts 9:25; 2 Corinthians 11:32-33", dir="tiptoe storytelling, quiet and twinkly", pre=1.0, post=0.2),
    line("sa_34", "ananias", "慢一点……慢一点……好，到地了！",
         "Slowly... slowly... there, he's down!",
         "Acts 9:25", dir="from up in the window, a loud whisper, fussy and kind", pre=0.2, post=0.2),
    # basket_down (6.0 s, touchdown `land` at 5.6 s) anchored to the end of sa_34 so it lands 0.4 s before "he's down"
    # ends and basket_out starts as the clip ends
    act("saul", "basket_down", face="viewer", dt=-6.0), sfx("rope_creak", dt=-5.8),
    sfx("basket_land", dt=-0.4),
    act("saul", "basket_out", face="viewer", dt=0.0), prop("saul/basket", show=False, dt=1.4, grow=0.4),
    act("saul", "wave", face="viewer", dt=1.4),                       # waves up to the window through sa_35
    line("sa_35", "saul", "谢谢你们，弟兄们！",
         "Thank you, brothers!",
         "Acts 9:25", dir="a happy whisper up to the window", pre=1.0, post=0.2),
    *_away,
    pause(2.4),                                        # cut while he tiptoes behind the dozing guard
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "巴拿巴", "Barnabas", "fixed", "jerusalemDoor", dist=0.55, height=0.2, yawDeg=-25,
         desc="Back in Jerusalem, at the door of the believers' house. Peter peeks out and shrinks back, afraid of "
              "Saul. Big, kind Barnabas comes up and speaks up for Saul. Peter smiles and hugs him."),
    music("barnabas"),
    *hide("tallguard"), *hide("shortguard"), prop("tallguard/lantern", show=False),
    act("saul", "walk", to=(0.40, -0.06), y=0.0, face="jerusalemDoor", snap=True),
    act("saul", "walk", to=(0.40, -0.24), face="jerusalemDoor", dt=0.2),
    *show("peter", "idle", JHOUSE_DOOR, "viewer"),                   # in the doorway, half in the shadow
    *show("barnabas", "idle", (0.14, 0.02), "saul"),
    line("sa_36", "narrator", "扫罗回到耶路撒冷，可是大家都很怕他。",
         "Back in Jerusalem, Jesus's friends were afraid of Saul.",
         "Acts 9:26", dir="gentle, a small worry in it", pre=0.6, post=0.2),
    act("peter", "peek_afraid", face="saul", dt=-1.6),
    act("barnabas", "walk", to=(0.30, -0.22), face="peter", dt=-1.2),  # 0.28 in 3.1 s
    line("sa_37", "peter", "扫罗？他……他是来抓我们的吧？",
         "Saul? Has he... has he come to arrest us?",
         "Acts 9:26", dir="big Peter, small voice; worried, comic", pre=0.2, post=0.3),
    act("barnabas", "talk", face="peter", dt=0.4),
    act("saul", "idle", face="peter", dt=0.4),
    act("barnabas", "arm_round", face="peter", dt=2.4),             # Saul 0.10 at his right, both facing Peter
    line("sa_38", "barnabas", "彼得，别怕！他遇见了耶稣，耶稣改变了他的心。",
         "Don't be afraid, Peter! He met Jesus, and Jesus changed his heart.",
         "Acts 9:27", dir="big, warm, encouraging; a friend's arm in the voice", pre=0.6, post=0.3),
    act("peter", "idle", face="saul", dt=0.2),
    act("barnabas", "laugh", face="saul", dt=0.6),                   # the arm comes off, then Saul walks to Peter
    act("saul", "walk", to=(0.335, -0.30), face="peter", dt=0.7),    # 0.094 in 1.0 s; 0.0995 from Peter for the hug
    line("sa_39", "peter", "那……欢迎你，扫罗弟兄！",
         "Then... welcome, brother Saul!",
         "Acts 9:27-28", dir="a slow smile, then a big glad welcome", pre=0.6, post=0.2),
    act("peter", "hug", face="saul", dt=0.0), act("saul", "hug", face="peter", dt=0.0),
    pause(1.8),
    # S13 --------------------------------------------------------------------------------------------------------
    shot("S13", "心变了", "A changed heart", "fixed", "cityWall", dist=0.95, height=0.46, yawDeg=0,
         desc="The whole page in warm sunshine: Damascus, the road, Jerusalem. Everyone stands in a row along the "
              "front and waves to the child: Ananias, Judas, Saul, Barnabas, Peter, and even the two guards, "
              "who have stopped frowning."),
    music("finale"),
    act("ananias", "wave", to=(-0.27, 0.08), y=0.0, face="viewer", snap=True), prop("ananias", show=True),
    act("judas", "wave", to=(-0.17, 0.10), y=0.0, face="viewer", snap=True), prop("judas", show=True),
    act("saul", "cheer", to=(-0.07, 0.10), y=0.0, face="viewer", snap=True),
    act("barnabas", "wave", to=(0.06, 0.10), face="viewer", snap=True),
    act("peter", "wave", to=(0.18, 0.10), face="viewer", snap=True),
    *show("tallguard", "scratch_head", (0.32, 0.10), "viewer"), *show("shortguard", "idle", (0.44, 0.10), "viewer"),
    fx("golden_rays", "damascus.cityWall", dur=21.31, dt=0.3), fx("heart_glow", "saul.chest", dur=3.0, dt=0.6),
    line("sa_40", "narrator", "耶稣把扫罗的心从生气变成了爱。后来，他叫保罗。",
         "Jesus turned Saul's heart from anger to love. Later, he was called Paul.",
         "Acts 9:28; 13:9", dir="joyful and sure; a happy surprise on 保罗 / 'Paul'", pre=0.8, post=0.3),
    act("saul", "talk", face="viewer", dt=-0.2),
    line("sa_41", "saul", "耶稣原谅了我。他能改变任何人的心！",
         "Jesus forgave me. He can change anyone's heart!",
         "1 Timothy 1:13-16", dir="straight to the child, warm, amazed and glad", pre=0.3, post=0.3),
    act("tallguard", "wave", face="viewer", dt=0.0), act("shortguard", "wave", face="viewer", dt=0.3),
    act("saul", "wave", face="viewer", dt=0.2),
    line("sa_42", "narrator", "上帝能改变每一个人的心。被原谅的心，也会原谅别人。",
         "God can change anyone's heart. And a forgiven heart learns to forgive.",
         "2 Corinthians 5:17; Ephesians 4:32", dir="warm, slow, a hush on the last words", pre=0.4, post=0.4),
    sfx("sparkle_up", dt=0.0),
    pause(1.2),
]
