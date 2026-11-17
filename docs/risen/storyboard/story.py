"""He Is Risen! — the play, as beats relative to each other (docs/risen/CONTRACT.md §5).

`tools/story/build_timeline.py risen` turns this into assets/risen/timeline.json, placing every line by the real voice
durations (an estimate until the voices exist). Helpers: shot / line / act / fx / sfx / music / prop / pause (same as
every pack), plus `path()`, `hide()` and `appear()` below.
Marks are art-width units on the page (x right, z toward the viewer); the set's marks are in CONTRACT.md §6.
`face` takes an actor id, "viewer", or a set node name ("tombDoor", "tombStoneAside", "house", "lowTable").

One page, three places: the garden with the rock tomb (left back; the door faces the viewer, the stone rolls to its
right), the path along the front (from the house on the right to the garden gate), and the upstairs room (right back;
a doll's house open at the front, its floor at y = UPPER, a bench along the back wall so seated faces look at the phone).

Staging rules (learned in Jonah, Miracles and The King Who Serves):
- An actor who is not in a scene is HIDDEN and PARKED (`hide()`): moved with snap=True to PARK, beyond the page.
- No camera targets "all": shots target an actor or a set node. Start values here; the lead re-frames at staging so
  the speaker is never behind someone (S03, S08, S10 are the risky ones: two or three people close together).
- `orbit` turns 6 deg/s: orbit shots stay under ~10 s of motion that matters.
- Moves between places (garden -> room, room -> path) happen ON A SHOT CUT with snap=True; no clip carries an actor
  from one place to another.
- Multi-leg moves use `path()`: each leg starts when the previous one ends at the clip's planned speed (V_*), so
  StoryDirector never cuts a walk short. The planned speeds are guesses until `assets/risen/anim/clips.json` exists;
  after Animation the lead sets V_* to the real naturalSpeed and re-runs build_timeline.py (it warns on short walks).
- Appearing (`appear()`): Jesus is hidden while He is not on stage and pops in (grow 0.6) inside a soft light; He
  never walks in through a door (John 20:19, 26). He leaves the same way (shrink 0.5) on a cut or under the light.
- The angel only sits on the rolled-away stone (`sit_*` clips at base y ANGEL_Y, the `ride` method: hips touch the
  stone top). It never walks, so there is no hop-down to blend.
- Props take their colour from printed regions (CONTRACT §3); a prop is shown only while it is in a hand.
- SFX are one-shots sized to their scene (StoryDirector stops a loop only at a music cue; Miracles `dig_loop`).
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py
import math

ID = "risen"
CAST = ["jesus", "mary", "angel", "peter", "john", "thomas", "joanna"]
SET = "garden"

UPPER = 0.10                   # floor of the upstairs room (the ground storey under it is closed)
PARK = (0.80, 0.30)            # hidden actors wait here, beyond the page
STONE_TOP = 0.38               # top of the rolled-away stone (a disc 0.39 across on its edge; SET.md, lead-approved)
ANGEL_Y = 0.311                # seat top 0.38 minus the angel's rig-local hip-contact y 0.069 (RIG.md)
# planned travel speeds (art units / s); Animation writes the real ones in clips.json, the lead updates these
# naturalSpeed from assets/risen/anim/clips.json (2026-11-18); StoryDirector plays a travel clip at 1.0-1.6x of it
V_WALK = 0.090                 # women walking (mary / joanna walk, walk_jar); Jesus 0.097, Peter 0.111
V_RUN = 0.241                  # John's light run (the faster one)
V_PUFF = 0.166                 # Peter's heavy, puffing run
V_JOY = 0.197                  # Mary's / Joanna's run

# The garden (left; floor y 0). Rock hill x -0.60..-0.04, z -0.5875..-0.30; the tomb door is cut in its front face at
# x -0.395..-0.265 (centre -0.33), 0.34 high. The stone stands in a groove: closed at (-0.33, -0.285), aside at (-0.17, -0.285).
TOMB_DOOR = (-0.33, -0.24)     # just in front of the door (peeking / stooping in)
STONE_ASIDE = (-0.113, -0.410)  # the angel sits on top of it
GATE = (-0.06, 0.06)           # the gap in the low garden wall, where the path comes in
NEAR_TOMB = (-0.26, -0.10)     # the women stop here when the ground rumbles
MARY_T = (-0.30, -0.13)        # S03 / S04: the women in front of the tomb, the angel to their right
JOANNA_T = (-0.42, -0.12)
MARY_DOOR = (-0.30, -0.22)     # S04: they step up and peek in
JOANNA_DOOR = (-0.40, -0.21)
MARY_CRY = (-0.24, -0.05)      # S08: Mary alone in front of the flowers, facing the viewer
JESUS_G = (-0.10, -0.12)       # S08: Jesus behind her right shoulder (both faces seen from the front camera)
MARY_MEET = (-0.205, -0.075)   # S09: 0.11 from JESUS_G, turned to Him (the `hold_hands` pair distance)
JOHN_ASIDE = (-0.42, -0.15)    # S07: John steps aside for Peter, 0.127 from TOMB_DOOR (at (-0.40, -0.22) they touched)
# The path (front, y 0): from the house's ground-floor door to the garden gate
HOUSE_DOOR = (0.30, -0.15)     # in front of the house's ground-floor door (front wall z -0.22)
PETER_DOOR = (0.38, -0.13)     # Peter starts beside John, a step behind
PATH_R = (0.22, 0.08)
PATH_L = (0.04, 0.08)
WOMEN_START = {"mary": (0.36, 0.10), "joanna": (0.44, 0.12)}
# The upstairs room (right back; floor y UPPER; interior x 0.08..0.58, z -0.58..-0.22; front open; the outside stair
# comes up the house's left wall to a door in the room's left wall at z -0.30)
ROOM_DOOR = (0.12, -0.30)
BENCH = {"thomas": (0.20, -0.49), "john": (0.30, -0.49), "peter": (0.40, -0.49)}   # seated, facing the viewer
STAND = {"john": (0.20, -0.45), "peter": (0.40, -0.45)}   # standing in the room, either side behind ROOM_J
MARY_ROOM = (0.14, -0.33)
ROOM_J = (0.30, -0.30)         # Jesus appears here: front middle of the room, the friends behind Him and to the sides
TABLE_J = (0.41, -0.30)        # beside the low table (x 0.46..0.56, z -0.36..-0.26); the fish plate (0.50, -0.31) is 0.09 away
JOHN_S11 = (0.51, -0.45)       # S11: right of Peter (at STAND john he stood right behind Thomas from the camera)
THOMAS_TOUCH = (0.19, -0.30)   # 0.11 left of ROOM_J, same depth: the pair is seen in profile (`show_hands` / `reach`)


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


def appear(where, y=0.0, face="viewer", dt=0.0, clip="appear"):
    """Jesus appears: placed while hidden 1.0 s early so the light (which fades in over 1 s and stays where it starts)
    is anchored on Him and already bright when He grows in (1.0 s, not a 0.6 s pop) inside it."""
    out = [act("jesus", "idle", to=where, y=y, face=face, snap=True, dt=dt - 1.0),
           fx("angel_light", "jesus.root", dur=3.5, dt=dt - 0.9),
           prop("jesus", show=True, dt=dt + 0.1, grow=1.0), sfx("appear_chime", dt=dt + 0.1)]
    if clip != "idle":
        out.append(act("jesus", clip, face=face, dt=dt))
    return out


_mary_walk, T_WOMEN = path("mary", "walk_jar", [WOMEN_START["mary"], PATH_R, PATH_L, GATE, NEAR_TOMB], -6.0, V_WALK,
                          face="tombStone")
_jo_walk, _ = path("joanna", "walk_jar", [WOMEN_START["joanna"], (0.30, 0.11), (0.06, 0.11), GATE, JOANNA_T], -5.6,
                   V_WALK, face="tombStone")
# S06, the race (15.6 s of shot, ~4-5 s of running): John runs to the gate and waits, looking back; Peter puffs to a
# stop at PATH_R, 0.28 behind him ("faster than Peter!"); John waves him on (rs_17), runs on to the door; Peter runs on (rs_18).
# Same marks and straight legs as before (SET.md clearance), only stops in between.
_john_run1, T_JOHN1 = path("john", "run", [HOUSE_DOOR, PATH_R, PATH_L, GATE], 1.0, V_RUN, face="peter")
_john_run2, T_JOHN2 = path("john", "run", [GATE, TOMB_DOOR], 8.9, V_RUN, face="tombDoor")
_peter_run1, T_PETER1 = path("peter", "run_puff", [PETER_DOOR, PATH_R], 1.6, V_PUFF, face="john")
_peter_run2, T_PETER2 = path("peter", "run_puff", [PATH_R, PATH_L, GATE, (-0.22, -0.14)], 9.6, V_PUFF, face="tombDoor")
# S09: only the first leg (0.8 s); the cut to S10 comes 1.0 s after rs_27, the rest of the way is off screen
_mary_off, _ = path("mary", "run", [MARY_MEET, (-0.10, 0.04)], 0.0, V_JOY)

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "最难过的一天", "The saddest day", "fixed", "garden", dist=0.95, height=0.45, yawDeg=-10,
         desc="Over the page at dusk, the sky darkening: a quiet garden with a tomb in a rock and a big "
              "round stone across its door, a path, a house with an upstairs room. Two women stand by the closed tomb, "
              "heads bowed; upstairs, Peter and John sit very still on the bench. No cross is shown anywhere."),
    music("sad_day"),
    fx("tension_dim", "stage", dur=26.0),
    act("mary", "sad", to=MARY_T, face="tombStone", snap=True),
    act("joanna", "sad", to=JOANNA_T, face="tombStone", snap=True),
    act("peter", "sit_sad", to=BENCH["peter"], y=UPPER, face="viewer", snap=True),
    act("john", "sit_sad", to=BENCH["john"], y=UPPER, face="viewer", snap=True),
    *hide("jesus"), *hide("angel"), *hide("thomas"),
    prop("garden/tombStoneAside", show=False), prop("garden/fishOnPlate", show=True),
    prop("mary/jar", show=False), prop("joanna/jar", show=False), prop("jesus/fish", show=False),
    pause(0.6),
    line("rs_01", "narrator", "有人把耶稣抓走了，耶稣死在了十字架上。天黑了下来，他的朋友们好难过。",
         "Some men took Jesus away, and He died on a cross. The sky went dark, and His friends were very sad.",
         "Luke 23:33, 44-49; Matthew 27:45", dir="soft and slow, plain; no drama, no pause on the cross; a gentle hush on "
         "好难过 / 'very, very sad'", post=0.5),
    line("rs_02", "narrator", "朋友们把耶稣安放在花园里的坟墓里，一块又大又圆的石头挡住了门。",
         "His friends laid Him in a tomb in a garden, and a big round stone was rolled across the door.",
         "John 19:41-42; Matthew 27:59-60", dir="quiet, tender; a small weight on 又大又圆 / 'big round'", pre=0.3,
         post=0.6),
    act("mary", "walk", to=(-0.10, 0.02), dt=-2.0), act("joanna", "walk", to=(-0.18, 0.06), dt=-2.0),
    line("rs_03", "narrator", "可是，耶稣说过：“第三天，我要复活！”",
         "But Jesus had made a promise: 'On the third day, I will rise again!'",
         "Matthew 16:21; Luke 24:6-7", dir="the turn of the story: lift and brighten, a little secret smile; slower on "
         "第三天 / 'the third day'", pre=0.6, post=1.0),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "天刚亮", "Very early in the morning", "follow", "mary", dist=0.6, height=0.2, yawDeg=-30,
         desc="Dawn: pink and gold sky, birds. Mary Magdalene and her friend Joanna walk along the path from the town "
              "to the garden, each carrying a small jar of sweet spices, wondering about the stone."),
    music("dawn"),
    fx("dawn_glow", "stage", dur=55.2), sfx("birds_dawn", dt=0.5),          # S02-S04 at dawn; ends at the S05 cut (F2)
    act("mary", "idle_jar", to=WOMEN_START["mary"], face="house", snap=True),
    act("joanna", "idle_jar", to=WOMEN_START["joanna"], face="house", snap=True),
    prop("mary/jar", show=True), prop("joanna/jar", show=True),
    *hide("peter"), *hide("john"),
    line("rs_04", "narrator", "第三天一大早，马利亚和她的朋友约亚拿带着香膏，往花园走去。",
         "Very early on the third day, Mary Magdalene and her friend Joanna carried sweet spices to the garden.",
         "Mark 16:1-2; Luke 24:1, 10", dir="morning-fresh, a hint of hope; unhurried", pre=0.8, post=0.2),
    *_mary_walk, *_jo_walk,
    line("rs_05", "joanna", "那块石头那么大，谁能帮我们滚开呢？",
         "That stone is so big! Who will roll it away for us?",
         "Mark 16:3", dir="worried but practical, a little out of breath from walking", pre=0.4, post=0.3),
    line("rs_06", "mary", "我也不知道……我只是想离耶稣近一点。",
         "I don't know... I just want to be near Jesus.",
         "John 20:1", dir="soft, a little sad, loving", pre=0.2, post=0.6),
    pause(max(0.0, T_WOMEN - 6.0)),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "石头滚开了！", "The stone rolls away!", "fixed", "tombHill", dist=0.6, height=0.22, yawDeg=40,
         desc="In front of the tomb the ground rumbles gently; a flash of white light; when it clears, the big stone "
              "has rolled to one side and a shining angel sits on top of it, legs dangling, smiling. The women gasp."),
    music("stone"),
    act("mary", "idle_jar", to=MARY_T, face="tombStone", snap=True),
    act("joanna", "idle_jar", to=JOANNA_T, face="tombStone", snap=True),
    # nobody sees the stone roll (PLAN risk 3): a light column on the closed stone (bright from 1.8 s) and one on the
    # rolled-aside place (bright from 2.2 s); the closed stone shrinks away inside the first (2.0-2.3), the rolled one
    # and then the angel grow inside the second. The angel never turns on the stone: every angel act faces "viewer"
    # (the seated clips turn chest and head to the women and point at the door themselves; ANIMATION.md §4.1).
    fx("dust_burst", "garden.tombStone", dur=1.6, dt=0.8), sfx("rumble", dt=0.6),
    fx("angel_light", "garden.tombStone", dur=3.0, dt=0.8),
    fx("angel_light", "garden.tombStoneAside", dur=4.0, dt=1.2), sfx("stone_roll", dt=1.4),
    prop("garden/tombStone", show=False, dt=2.0, grow=0.3), prop("garden/tombStoneAside", show=True, dt=2.2, grow=0.4),
    act("angel", "sit_stone", to=STONE_ASIDE, y=ANGEL_Y, face="viewer", snap=True, dt=2.0),
    prop("angel", show=True, dt=2.4, grow=0.6), act("angel", "wings_open", face="viewer", dt=2.5),
    act("angel", "sit_stone", face="viewer", dt=4.1),
    act("mary", "gasp", face="angel", dt=1.2), act("joanna", "gasp", face="angel", dt=1.4),
    act("mary", "idle_jar", face="angel", dt=2.6), act("joanna", "idle_jar", face="angel", dt=2.8),
    line("rs_07", "narrator", "忽然，地动了一下，大石头滚开了！一位天使坐在上面，全身发亮，像闪电一样！",
         "Suddenly the ground shook, and the big stone rolled away! An angel sat on it, shining like lightning!",
         "Matthew 28:2-3", dir="wonder, building quickly; not scary; a delighted lift on 滚开了 / 'rolled away'",
         pre=3.4, post=0.3),
    line("rs_08", "mary", "石头……滚开了！",
         "The stone... it's rolled away!",
         "Mark 16:4", dir="a breathless, amazed whisper", pre=0.2, post=0.5),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "他不在这里", "He is not here!", "fixed", "angel", dist=0.55, height=0.2, yawDeg=-25,
         desc="The angel, seated on the stone, speaks kindly to the women and points to the open door. They step up "
              "and peek in: a soft light inside, only the folded linen cloths on the stone ledge. The tomb is empty."),
    music("risen"),
    act("angel", "sit_talk", face="viewer"),
    line("rs_09", "angel", "不要害怕！耶稣不在这里，他复活了，就像他说过的！",
         "Don't be afraid! Jesus is not here. He is risen, just as He said!",
         "Matthew 28:5-6; Luke 24:6", dir="kind, strong and calm, a big smile in the voice; the heart of the story: "
         "slow and joyful on 他复活了 / 'He is risen'", pre=0.4, post=0.3),
    act("angel", "sit_point", face="viewer", dt=-0.4),
    line("rs_10", "angel", "来，看看安放他的地方。",
         "Come and see the place where He lay.",
         "Matthew 28:6", dir="gentle invitation", pre=0.1, post=0.2),
    act("mary", "walk_jar", to=MARY_DOOR, face="tombDoor", dt=0.0),
    act("joanna", "walk_jar", to=JOANNA_DOOR, face="tombDoor", dt=0.1),
    act("mary", "peek", face="tombDoor", dt=1.2), act("joanna", "peek", face="tombDoor", dt=1.3),
    fx("tomb_glow", "garden.tombDoor", dur=9.0, dt=1.0),
    line("rs_11", "joanna", "真的空了！只有叠好的细麻布！",
         "It's empty! There's only the cloth, folded up!",
         "Luke 24:3; John 20:6-7", dir="amazed, rising to joy", pre=2.0, post=0.3),
    act("angel", "sit_talk", face="viewer", dt=-0.4),
    act("mary", "idle_jar", face="angel", dt=-0.2), act("joanna", "idle_jar", face="angel", dt=-0.1),
    line("rs_12", "angel", "快去告诉他的朋友们：耶稣活了！",
         "Hurry! Go and tell His friends: Jesus is alive!",
         "Matthew 28:7; Mark 16:7", dir="bright, urgent in a happy way", pre=0.3, post=0.3),
    act("mary", "run", to=(-0.10, 0.02), dt=-0.5), act("joanna", "run", to=(-0.18, 0.08), dt=-0.35),   # 1.0x / 1.2x
    act("angel", "sit_wave", face="viewer", dt=-0.4),
    pause(1.2),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "他活了！", "He's alive!", "fixed", "house", dist=0.55, height=0.22, yawDeg=-10,
         desc="The upstairs room, morning light. Peter and John sit sadly on the bench along the back wall. Mary "
              "bursts in through the side door, breathless, and tells them; they jump up."),
    music("news"),
    *hide("angel"), *hide("joanna"),
    prop("mary/jar", show=False), prop("joanna/jar", show=False),
    prop("peter", show=True), prop("john", show=True),
    act("peter", "sit_sad", to=BENCH["peter"], y=UPPER, face="viewer", snap=True),
    act("john", "sit_sad", to=BENCH["john"], y=UPPER, face="viewer", snap=True),
    act("mary", "run", to=ROOM_DOOR, y=UPPER, face="peter", snap=True),
    act("mary", "run", to=MARY_ROOM, face="peter", dt=0.3),
    act("mary", "tell", face="peter", dt=0.9),
    line("rs_13", "mary", "彼得！约翰！坟墓空了！天使说，耶稣复活了！",
         "Peter! John! The tomb is empty! An angel said Jesus is alive!",
         "Luke 24:9-10; John 20:2", dir="breathless, tumbling out fast, bursting with joy", pre=1.0, post=0.3),
    act("peter", "jump_up", face="mary", dt=-1.0), act("john", "jump_up", face="mary", dt=-0.8),
    act("peter", "talk", face="mary", dt=0.4), act("john", "idle", face="mary", dt=0.6),
    line("rs_14", "peter", "复活了？这……这怎么可能？",
         "Alive? That... that can't be true!",
         "Luke 24:11", dir="stunned, big and blustery; half hoping", pre=0.6, post=0.2),
    act("john", "wave_hurry", face="peter", dt=0.0),
    line("rs_15", "john", "彼得，别站着了，快去看看！",
         "Peter, don't just stand there! Let's go and see!",
         "John 20:3", dir="young, quick, already moving", pre=0.1, post=0.4),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "赛跑", "The race", "follow", "john", dist=0.65, height=0.2, yawDeg=-35,
         desc="Peter and John run along the path to the garden, dust puffing at their feet. Young John is quicker and "
              "pulls ahead, waving Peter on; Peter puffs along behind, red-faced."),
    music("race"),
    *hide("mary"),
    act("john", "idle", to=HOUSE_DOOR, y=0.0, face="house", snap=True),
    act("peter", "idle", to=PETER_DOOR, y=0.0, face="house", snap=True),
    *_john_run1, *_peter_run1,
    act("peter", "puff", face="john", dt=round(1.6 + T_PETER1, 2)),
    act("john", "wave_hurry", face="peter", dt=7.2),
    *_john_run2, *_peter_run2,
    act("peter", "puff", face="tombDoor", dt=round(9.6 + T_PETER2, 2)),
    fx("run_dust", "john.root", dur=round(T_JOHN1, 1), dt=1.0), fx("run_dust", "peter.root", dur=round(T_PETER1, 1), dt=1.6),
    fx("run_dust", "john.root", dur=round(T_JOHN2, 1), dt=8.9), fx("run_dust", "peter.root", dur=round(T_PETER2, 1), dt=9.6),
    sfx("run_steps", dt=1.0),
    line("rs_16", "narrator", "彼得和约翰拼命地跑。可是约翰年轻，跑得比彼得快！",
         "Peter and John ran as fast as they could. But John was younger, and he ran faster than Peter!",
         "John 20:3-4", dir="lively, quick; a grin on 跑得比彼得快 / 'faster than Peter'", pre=0.6, post=0.1),
    line("rs_17", "john", "快点儿，彼得！",
         "Hurry up, Peter!",
         "John 20:4", dir="cheeky, calling back over his shoulder", pre=0.1, post=0.1),
    line("rs_18", "peter", "等……等等我！我的腿……没你的年轻！",
         "Wait... wait for me! My legs... aren't as young as yours!",
         "John 20:4", dir="puffing and panting between the words, comic; a laugh in it", pre=0.1, post=0.4),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "空空的坟墓", "The empty tomb", "fixed", "tombDoor", dist=0.5, height=0.18, yawDeg=20,
         desc="John reaches the tomb first and stops at the door, peeking in. Peter puffs up behind him and goes "
              "straight in, bending under the low doorway. Light inside; the linen cloths lie folded on the ledge."),
    music("empty"),
    act("john", "peek", to=TOMB_DOOR, face="tombDoor", snap=True),
    act("peter", "puff", to=(-0.22, -0.14), face="tombDoor", snap=True),
    fx("tomb_glow", "garden.tombDoor", dur=19.3),   # ends at the S08 cut (F2)
    line("rs_19", "narrator", "约翰先到，往里看。彼得呼哧呼哧赶到，一头钻了进去！",
         "John got there first and looked in. Then Peter came puffing up and went straight inside!",
         "John 20:5-6", dir="playful storyteller; a comic beat on 一头钻了进去 / 'went straight inside'", pre=0.6,
         post=0.1),
    act("john", "run", to=JOHN_ASIDE, face="tombDoor", dt=-2.4),   # 0.127 in 0.5 s, then idle (no glide, A2)
    act("peter", "walk", to=TOMB_DOOR, face="tombDoor", dt=-2.2),
    act("peter", "stoop_look", face="tombDoor", dt=-1.0),
    line("rs_20", "peter", "细麻布还在这儿，叠得整整齐齐……可是耶稣不在！",
         "The cloths are here, folded up neatly... but Jesus isn't!",
         "John 20:6-7", dir="half inside the doorway, puzzled wonder; the last words a hushed gasp", pre=1.0, post=0.3),
    act("peter", "amazed", face="john", dt=0.0), act("john", "amazed", face="peter", dt=0.1),
    line("rs_21", "john", "他说过他会复活……他真的做到了！",
         "He said He would rise again... and He did!",
         "John 20:8-9", dir="the penny drops: slow wonder, then a happy rush", pre=0.4, post=0.6),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "你为什么哭？", "Why are you crying?", "fixed", "mary", dist=0.5, height=0.17, yawDeg=0,
         desc="Later. Mary stands alone in the garden by the flowers, crying, her eyes so full of tears she cannot see "
              "clearly. A man stands quietly behind her: it is Jesus, but she thinks He is the gardener."),
    music("garden_tears"),
    *hide("peter"), *hide("john"),
    act("mary", "cry", to=MARY_CRY, y=0.0, face="viewer", snap=True), prop("mary", show=True),
    line("rs_22", "narrator", "后来，马利亚回到花园。她太想耶稣了，一直在哭。",
         "Later, Mary came back to the garden. She missed Jesus so much, she cried and cried.",
         "John 20:11", dir="tender, slow; a soft ache, not heavy", pre=0.6, post=0.3),
    *appear(JESUS_G, face="mary", clip="idle", dt=-1.2),
    act("jesus", "talk", face="mary", dt=0.2),
    line("rs_23", "jesus", "你为什么哭？你在找谁呢？",
         "Why are you crying? Who are you looking for?",
         "John 20:15", dir="very gentle, warm, a hidden smile (He knows!)", pre=0.6, post=0.3),
    act("mary", "talk_down", face="viewer", dt=-0.1),
    line("rs_24", "mary", "先生，你是看园子的吧？要是你把他搬走了，请告诉我放在哪里！",
         "Sir, are you the gardener? If you took Him away, please tell me where He is!",
         "John 20:15", dir="tearful, not looking up, earnest; a small comic innocence in 看园子的 / 'the gardener'",
         pre=0.2, post=0.6),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "马利亚！", "Mary!", "fixed", "jesus", dist=0.5, height=0.17, yawDeg=25,
         desc="Jesus says her name. Mary looks up and knows Him at once; she runs to Him and takes His hands, laughing "
              "and crying together. Butterflies rise from the flowers; warm sunlight. Then she runs off to tell."),
    music("mary"),
    act("jesus", "call_name", face="mary"), act("jesus", "idle", face="mary", dt=1.6),
    line("rs_25", "jesus", "马利亚。",
         "Mary.",
         "John 20:16", dir="one word, soft and full of love, the way only He says it", pre=0.6, post=0.5),
    act("mary", "turn_joy", face="jesus", dt=-0.2), act("mary", "talk", face="jesus", dt=1.1),
    line("rs_26", "mary", "老师！是你！真的是你！",
         "Teacher! It's You! It's really You!",
         "John 20:16", dir="a gasp, then pure joy, laughing through tears", pre=0.3, post=0.2),
    act("mary", "walk", to=MARY_MEET, face="jesus", dt=-0.4),
    act("mary", "hold_hands", face="jesus", dt=0.6), act("jesus", "hold_hands", face="mary", dt=0.6),
    fx("butterflies", "mary.root", dur=6.5, dt=0.4), fx("golden_rays", "jesus.root", dur=6.3, dt=0.6),   # end at the cut
    sfx("sparkle_up", dt=0.6),
    act("jesus", "talk", face="mary", dt=2.4), act("mary", "idle", face="jesus", dt=2.4),   # hands let go together
    line("rs_27", "jesus", "去告诉我的朋友们：我活着！",
         "Go and tell My friends: I am alive!",
         "John 20:17; Matthew 28:10", dir="warm, glad, a bright smile", pre=2.6, post=0.3),
    act("mary", "cheer", face="jesus", dt=-1.6),       # hops through "I am alive!" (1.6 s), then runs off
    act("jesus", "wave", face="mary", dt=0.1),
    *_mary_off,
    pause(1.0),                                        # Jesus stays; the cut hides Him (S10 starts hidden)
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "愿你们平安", "Peace be with you", "fixed", "house", dist=0.55, height=0.24, yawDeg=-15,
         desc="Evening in the upstairs room, lamps lit, the door locked. Mary tells Peter and John that she has seen "
              "Jesus. Suddenly Jesus is standing right there with them. They jump; John thinks He is a ghost. Jesus "
              "laughs, holds out His hands, and eats a piece of fish to show He is real."),
    music("peace"),
    fx("sunset_glow", "stage", dur=31.9), fx("lamp_flame", "garden.lamp1", dur=31.9),   # durations end at the cut (F2),
    fx("lamp_flame", "garden.lamp2", dur=31.9),                                          # set from the voiced timeline
    *hide("jesus"),
    act("mary", "tell", to=MARY_ROOM, y=UPPER, face="peter", snap=True),
    act("peter", "idle", to=STAND["peter"], y=UPPER, face="mary", snap=True), prop("peter", show=True),
    act("john", "idle", to=STAND["john"], y=UPPER, face="mary", snap=True), prop("john", show=True),
    line("rs_28", "mary", "我真的看见耶稣了！他活着！他叫了我的名字！",
         "I really saw Jesus! He's alive! He said my name!",
         "John 20:18", dir="glowing, sure, happy", pre=0.6, post=0.3),
    line("rs_29", "narrator", "门关得紧紧的，可是忽然，耶稣就站在他们中间！",
         "The door was locked tight. But suddenly, Jesus was standing right there!",
         "John 20:19", dir="hushed, then a magical lift on 忽然 / 'Suddenly'", pre=0.3, post=0.1),
    *appear(ROOM_J, y=UPPER, face="viewer", dt=-1.4),
    act("jesus", "peace", face="viewer", dt=0.1),
    line("rs_30", "jesus", "愿你们平安！",
         "Peace be with you!",
         "John 20:19; Luke 24:36", dir="warm, calm, smiling, arms open", pre=0.3, post=0.2),
    act("john", "shock", face="jesus", dt=-0.8), act("peter", "shock", face="jesus", dt=-0.6),
    act("mary", "cheer", face="jesus", dt=-0.4),
    line("rs_31", "john", "鬼……鬼啊？",
         "A g-g-ghost?",
         "Luke 24:37", dir="squeaky, teeth chattering, comic, not truly scared", pre=0.3, post=0.3),
    act("jesus", "show_hands", face="viewer", dt=-0.1),   # to John's side He would turn His back to the camera
    act("john", "idle", face="jesus", dt=0.1), act("peter", "idle", face="jesus", dt=0.3),
    act("mary", "idle", face="jesus", dt=0.5),
    line("rs_32", "jesus", "哈哈，是我呀！鬼可没有手和脚。你们有吃的吗？",
         "Ha ha, it's Me! A ghost doesn't have hands and feet. Got anything to eat?",
         "Luke 24:38-41", dir="laughing warmly, playful; the food question light and homely", pre=0.2, post=0.3),
    act("jesus", "walk", to=TABLE_J, face="lowTable", dt=0.0),
    act("jesus", "eat_fish", face="lowTable", dt=1.0),
    prop("garden/fishOnPlate", show=False, dt=1.6), prop("jesus/fish", show=True, dt=1.6),
    sfx("munch", dt=2.6), act("jesus", "idle", face="viewer", dt=5.1),
    act("peter", "laugh", face="jesus", dt=2.8), act("john", "laugh", face="jesus", dt=3.0),
    line("rs_33", "peter", "哈哈！他在吃我们的鱼！真的是耶稣！",
         "Ha ha! He's eating our fish! It really is Jesus!",
         "Luke 24:42-43", dir="a big delighted belly laugh, tears of joy", pre=3.2, post=0.6),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "多马", "Thomas", "fixed", "thomas", dist=0.5, height=0.2, yawDeg=-20,
         desc="A week later, the same room. Thomas, who was not there, stands with his arms crossed, shaking his "
              "head. Jesus appears again, turns to him and holds out His hands; Thomas gently touches them and kneels "
              "with joy."),
    music("thomas"),
    *hide("jesus"), *hide("mary"),
    fx("sunset_glow", "stage", dur=26.6), fx("lamp_flame", "garden.lamp1", dur=26.6),
    fx("lamp_flame", "garden.lamp2", dur=26.6),
    prop("jesus/fish", show=False), prop("garden/fishOnPlate", show=True),
    act("thomas", "doubt", to=THOMAS_TOUCH, y=UPPER, face="peter", snap=True), prop("thomas", show=True),
    act("peter", "talk", to=STAND["peter"], y=UPPER, face="thomas", snap=True),
    act("john", "idle", to=JOHN_S11, y=UPPER, face="thomas", snap=True),
    line("rs_34", "narrator", "一个星期以后。那天晚上多马不在，大家告诉他，他直摇头。",
         "A week later. Thomas had not been there that night, and when they told him, he shook his head.",
         "John 20:24-26", dir="plain storyteller, a little knowing smile", pre=0.6, post=0.2),
    act("peter", "idle", face="thomas", dt=-0.2),
    line("rs_35", "thomas", "除非我亲眼看见他的手，我才信！",
         "Unless I see His hands myself, I won't believe it!",
         "John 20:25", dir="stubborn but not grumpy; arms crossed; a small frown", pre=0.2, post=0.4),
    *appear(ROOM_J, y=UPPER, face="thomas", clip="idle", dt=0.2),
    act("thomas", "shock", face="jesus", dt=1.0),
    act("jesus", "show_hands", face="thomas", dt=1.4), act("thomas", "idle", face="jesus", dt=2.4),
    line("rs_36", "jesus", "多马，来看看我的手，摸一摸。不要疑惑，要信！",
         "Thomas, look at My hands. Touch them. Don't doubt: believe!",
         "John 20:27", dir="very gentle, patient, a loving invitation; no reproach", pre=2.0, post=0.3),
    act("thomas", "reach", face="jesus", dt=-1.0),          # touch at 1.13 s
    act("thomas", "kneel_worship", face="jesus", dt=0.8),
    fx("heart_glow", "thomas.chest", dur=2.6, dt=1.0),     # ends at the S12 cut
    line("rs_37", "thomas", "我的主！我的上帝！",
         "My Lord and my God!",
         "John 20:28", dir="overwhelmed, a happy sob of faith; from the heart", pre=1.2, post=0.6),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "他活着！", "He is alive!", "fixed", "garden", dist=0.95, height=0.48, yawDeg=6,
         desc="The whole page in bright morning sun: the open, empty tomb glowing softly, butterflies over the "
              "flowers. Jesus stands in the garden with His friends round Him, all smiling and waving to the child."),
    music("finale"),
    act("jesus", "wave", to=(-0.12, -0.04), y=0.0, face="viewer", snap=True), prop("jesus", show=True),
    act("mary", "cheer", to=(-0.24, 0.02), y=0.0, face="viewer", snap=True), prop("mary", show=True),
    act("peter", "cheer", to=(0.06, 0.02), y=0.0, face="viewer", snap=True),      # one row, no one behind another
    act("john", "cheer", to=(0.20, 0.06), y=0.0, face="viewer", snap=True),
    act("thomas", "cheer", to=(-0.36, -0.08), y=0.0, face="viewer", snap=True),
    fx("golden_rays", "garden.tombDoor", dur=14.0, dt=0.3), fx("butterflies", "garden.flowers", dur=14.0, dt=0.5),
    line("rs_38", "narrator", "耶稣死了，可是死亡留不住他。他复活了，今天还活着！",
         "Jesus died, but death could not keep Him. He rose again, and He is alive today!",
         "Matthew 28:6; Luke 24:5-6", dir="joyful and sure, straight to the child; slow and clear", pre=0.8, post=0.3),
    line("rs_39", "narrator", "耶稣说到做到。他还说：“我天天和你们在一起。”",
         "Jesus always keeps His promises. And He said: 'I am with you always.'",
         "Matthew 28:20; John 20:29", dir="warm, a smile, a hush on the promise at the end", pre=0.3, post=0.4),
    act("jesus", "wave", face="viewer", dt=-0.2), sfx("sparkle_up", dt=0.0),
    pause(1.2),
]
