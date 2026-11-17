"""The King Who Serves — the play, as beats relative to each other (docs/lastsupper/CONTRACT.md §5).

`tools/story/build_timeline.py lastsupper` turns this into assets/lastsupper/timeline.json, placing every line by the
real voice durations. Helpers: shot / line / act / fx / sfx / music / prop / pause (same as every pack).
Marks are art-width units on the page (x right, z toward the viewer); the set's marks are in CONTRACT.md §6.
`face` takes an actor id, "viewer", or a set node name ("house", "temple", "table2", "stones").

One page, three places: the road into Jerusalem (front, right to left), the temple court (right back, two sellers'
tables) and the upstairs room (left back; a doll's house open at the front, its floor at y = UPPER).

Staging rules (learned in Jonah and Miracles):
- An actor who is not in a scene is HIDDEN with prop("<actor>", show=False) and moved with snap=True.
- No camera targets "all": shots target an actor or a set node.
- `orbit` turns 6 deg/s: orbit shots stay under ~10 s.
- Moves between places (dismounting, entering the room, sitting down for supper) happen ON A SHOT CUT with snap=True;
  no clip has to carry an actor from one place to another.
- Riding (`ride()` below): Jesus (`ride` / `ride_wave` / `ride_talk`, base y RIDE_Y) and the donkey (`walk`) get the
  same marks, the same dt and the same face target, so they move as one (Miracles' carry-group method). StoryDirector
  (StoryDirector.cs Act / Move) moves the donkey's `walk` at its naturalSpeed (linear, x1-1.6 when its next beat comes
  sooner) but glides Jesus (ride clips have no naturalSpeed: eased, max(0.6 s, dist / 0.12)). So a ride is cut into
  equal steps of 0.6 s (0.6875 s for a 0.0825 step) whose length is >= RIDE_V x 0.6 x 1.03: the donkey's rate is then
  1.03-1.34, it ends each step exactly on its next beat, and the rider's glide ends on the same frame (measured drift
  <= 0.008 against 0.061 before). After the last step the donkey gets an `idle` beat at the same moment, the rider
  keeps his ride clip (he never takes the standing `idle` on the donkey's back). The rider never turns away from the
  donkey's heading: every ride beat has the donkey's face target ("house").
- Kneeling down: there is no kneel-down clip; `kneel_wash` from a walk uses blend 0.8 (ANIMATION.md §4.3). Jesus's
  `basin` bone lies on the floor in front of Him in every clip but `rise_towel`, so it is hidden while He walks.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py
import math

ID = "lastsupper"
CAST = ["jesus", "peter", "donkey", "john", "james", "andrew", "seller1", "seller2"]
SET = "jerusalem"

UPPER = 0.10                   # floor of the upstairs room (the ground storey under it is closed)
RIDE_Y = 0.12                  # Jesus's base height while riding (seat on the donkey's back, CONTRACT §4)
PARK = (0.80, 0.30)            # hidden actors wait here
RIDE_V = 0.0896                # donkey `walk` naturalSpeed = the ride clips' rideSpeed (assets/lastsupper/anim/clips.json)

# The road (front of the page, y 0): the procession comes in from the right and stops at the bend by the court gate
DONKEY_START = (0.46, 0.13)
DONKEY_MID = (0.26, 0.11)
BEND = (0.10, 0.07)            # the procession stops here (S03)
STONES = (0.05, 0.17)          # the little heap of roadside stones (set node `stones`)
PETER_STONES = (0.13, 0.18)    # Peter bends to listen to the stones, 0.08 from them
DONKEY_TIE = (-0.04, 0.07)     # the donkey grazes here from S04 to the end (front of the house)
# The temple court (right back, floor y 0; low front wall at z -0.12 with a gate x 0.08..0.22)
GATE = (0.14, -0.06)           # Jesus steps in through the gate (S04)
J_T2 = (0.36, -0.26)           # Jesus at the money table (table2, x 0.42..0.50, z -0.31..-0.25)
J_T1 = (0.28, -0.42)           # Jesus at the dove table (table1, x 0.34..0.46, z -0.45..-0.39)
SELLER1 = (0.40, -0.50)        # behind the dove table
SELLER2 = (0.46, -0.37)        # behind the money table
SELLER2_SIDE = (0.57, -0.38)   # round the table's right end (SET.md §3: (0.56, -0.30) clipped table2's corner)
COINS = (0.53, -0.18)          # where the spilled coins end up (set node `coinsFloor`)
COINS2 = (0.58, -0.26)         # he scuttles on after the coins while his line lasts (away from Jesus's walk to J_T1)
P_COURT = (0.08, -0.22)        # disciples just inside the gate
JN_COURT = (0.14, -0.30)
JA_COURT = (0.05, -0.34)
# The upstairs room (left back; floor y UPPER; interior x -0.58..-0.08, z -0.58..-0.22; front open)
STAND = (-0.15, -0.46)         # in front of the basin stand (`basinStand` at (-0.115, -0.535))
ROOM_J = STAND                 # S06: Jesus by the basin (SET.md §3: (-0.15, -0.50) was inside the stand)
WAY = (-0.15, -0.36)           # waypoint right of the supper table (SET.md §3: STAND -> ROUND crossed `lowTable`)
ROUND = (-0.40, -0.36)         # waypoint in front of the supper table, so the walk does not cross it
# the four standing and squabbling (S06)
ARGUE = {"andrew": (-0.48, -0.32), "james": (-0.39, -0.35), "john": (-0.30, -0.33), "peter": (-0.21, -0.36)}
# the bench along the left wall (seat y UPPER + 0.04); they sit facing +X, toward Jesus
BENCH = {"andrew": (-0.54, -0.50), "james": (-0.54, -0.42), "john": (-0.54, -0.34), "peter": (-0.54, -0.27)}
WASH = {k: (-0.43, v[1]) for k, v in BENCH.items()}   # Jesus kneels 0.11 in front of each seat, facing -X
# supper round the low table (`lowTable` x -0.36..-0.18, z -0.50..-0.42); Peter sits at its front-left corner, next to
# his brother Andrew, so in S12 he only has to turn and kneel
SUP = {"james": (-0.34, -0.54), "jesus": (-0.27, -0.54), "john": (-0.20, -0.54),
       "andrew": (-0.41, -0.46), "peter": (-0.41, -0.35)}
# S12: Peter scoots to Andrew's front-left (30 deg off his front) and kneels 0.11 from him, both turned to each other,
# so the pair is seen side-on from the S12 camera (yaw 55, through the open front). Kneeling where he sat put his back
# between the camera and Andrew (ANIMATION.md §4.6); further left his toes would reach the bench.
PETER_SERVE = (round(SUP["andrew"][0] - 0.11 * 0.5, 3), round(SUP["andrew"][1] + 0.11 * 0.866, 3))


def ride(frm, to, dt, clip="ride", face="house"):
    """The donkey and its rider travel frm -> to as one (see the docstring): equal steps, the same dt, the same face."""
    d = math.dist(frm, to)
    n = max(1, int(d / (RIDE_V * 0.6 * 1.03)))
    seg = d / n; T = round(max(0.6, seg / 0.12), 4)
    out = []
    for k in range(1, n + 1):
        p = (frm[0] + (to[0] - frm[0]) * k / n, frm[1] + (to[1] - frm[1]) * k / n)
        out += [act("donkey", "walk", to=p, face=face, dt=dt + (k - 1) * T),
                act("jesus", clip, to=p, y=RIDE_Y, face=face, dt=dt + (k - 1) * T)]
    out.append(act("donkey", "idle", face=face, dt=dt + n * T))
    return out

DISCIPLES = ("peter", "john", "james", "andrew")

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "国王来了", "Here comes the King", "orbit", "road", dist=0.95, height=0.45, yawDeg=-20,
         desc="Short orbit over the page: a city with a temple court on the right, a house with an upstairs room on "
              "the left, a road along the front. From the right, Jesus rides in on a little donkey, His friends "
              "walking behind; two sellers shout in the temple court."),
    music("road"),
    act("donkey", "idle", to=DONKEY_START, face="house", snap=True),
    act("jesus", "ride", to=DONKEY_START, y=RIDE_Y, face="house", snap=True),
    act("peter", "idle", to=(0.56, 0.06), face="house", snap=True),
    act("john", "idle", to=(0.56, 0.17), face="house", snap=True),
    act("james", "idle", to=(0.63, 0.05), face="house", snap=True),
    act("andrew", "idle", to=(0.63, 0.16), face="house", snap=True),
    act("seller1", "shout", to=SELLER1, face="viewer", snap=True),
    act("seller2", "idle", to=SELLER2, face="viewer", snap=True),
    prop("jerusalem/palmsRoad", show=False),
    prop("jerusalem/table2Tipped", show=False), prop("jerusalem/coinsFloor", show=False),
    prop("jerusalem/cagesOpen", show=False),
    prop("jesus/towel", show=False), prop("jesus/basin", show=False), prop("jesus/bread", show=False),
    prop("jesus/cup", show=False), prop("peter/palm", show=True), prop("peter/towel", show=False),
    prop("peter/jug", show=False),
    pause(0.3),
    sfx("crowd_far"),
    line("ls_01", "narrator", "逾越节快到了，好多人去耶路撒冷过节。耶稣也来了，不骑高头大马，骑的是一头小驴。",
         "Passover was near, and crowds went up to Jerusalem. Jesus came too, not on a proud horse, but on a little donkey.",
         "Matthew 21:1-7; Mark 11:1-7", dir="storyteller opening, bright; a smile and a little surprise on 小驴 / "
         "'a little donkey'", post=0.2),
    *ride(DONKEY_START, DONKEY_MID, -3.0),
    act("peter", "walk", to=(0.38, 0.05), face="house", dt=-3.0),
    act("john", "walk", to=(0.38, 0.17), face="house", dt=-3.0),
    act("james", "walk", to=(0.46, 0.04), face="house", dt=-3.0),
    act("andrew", "walk", to=(0.46, 0.17), face="house", dt=-3.0),
    act("donkey", "hee_haw", face="house", dt=0.1), sfx("hee_haw", dt=0.3),   # the bray reads in profile
    pause(0.9),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "和散那！", "Hosanna!", "follow", "donkey", dist=0.7, height=0.22, yawDeg=-35,
         desc="People pour out along the road waving palm branches; coats and branches appear on the road in front of "
              "the donkey. Jesus waves from the donkey; Peter waves his palm branch higher than anyone."),
    music("hosanna"),
    prop("jerusalem/palmsRoad", show=True, grow=0.5), fx("palm_toss", "jerusalem.road", dur=8.0),
    *ride(DONKEY_MID, (0.18, 0.09), 0.0, clip="ride_wave"),
    act("peter", "walk", to=(0.30, 0.04), face="house"),
    act("john", "walk", to=(0.30, 0.17), face="house"),
    act("james", "walk", to=(0.40, 0.04), face="house"),
    act("andrew", "walk", to=(0.40, 0.17), face="house"),
    fx("dust_road", "donkey.root", dur=2.0),
    sfx("crowd_cheer", dt=0.2),
    line("ls_02", "narrator", "大家都跑出来欢迎他，挥着棕树枝，把衣服铺在路上。",
         "People ran out to welcome Him, waving palm branches and spreading their coats on the road.",
         "John 12:12-13; Mark 11:8", dir="lively, building; quicker on the second half", pre=0.4, post=0.1),
    line("ls_03", "people", "和散那！欢迎我们的王！他是上帝派来的！",
         "Hosanna! Hooray for our King! God has sent Him!",
         "John 12:13; Mark 11:9-10", dir="crowd of 8-10 incl. children, joyful, overlapping; a child's voice on top",
         pre=0.2, post=0.3),
    act("peter", "cheer", face="viewer", dt=-0.4), act("john", "cheer", face="viewer", dt=-0.2),
    line("ls_04", "peter", "哈哈，大家都知道他是王啦！我们也要当大人物了！",
         "Ha ha! Everyone knows He's the King! Soon we'll be important too!",
         "Luke 19:37; Mark 10:37", dir="bursting with pride, waving the palm; big grin on 大人物 / 'important'",
         pre=0.1, post=0.4),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "石头也会喊", "Even the stones", "fixed", "jesus", dist=0.5, height=0.15, yawDeg=-95,
         desc="At the bend by the temple gate the procession stops. Jesus answers the grumblers from the donkey; Peter "
              "bends down to a heap of roadside stones and listens."),
    music("stones"),
    *ride((0.18, 0.09), BEND, 0.0),
    act("peter", "walk", to=PETER_STONES, face="stones"),
    act("john", "walk", to=(0.24, 0.17), face="jesus"),
    act("james", "walk", to=(0.30, 0.03), face="jesus"),
    act("andrew", "walk", to=(0.34, 0.15), face="jesus"),
    act("donkey", "idle", face="house", dt=3.4), act("jesus", "ride", face="house", dt=3.4),
    *[act(d, "idle", face="jesus", dt=3.0) for d in ("john", "james", "andrew")],
    line("ls_05", "narrator", "有几个宗教领袖不高兴：老师，快叫他们安静！",
         "Some leaders grumbled: 'Teacher, make them be quiet!'",
         "Luke 19:39", dir="the grumble in a lower, prim voice; not scary", pre=0.6, post=0.3),
    act("jesus", "ride_talk", face="house", dt=-0.2),   # the clip turns His chest and head to the viewer
    line("ls_06", "jesus", "我告诉你们，他们要是不出声，这些石头都会喊起来！",
         "I tell you, if they keep quiet, these stones will shout out!",
         "Luke 19:40", dir="calm and sure, a twinkle in it; not cross", pre=0.2, post=0.5),
    act("peter", "listen_stone", face="stones", dt=-0.2),
    fx("sparkle", "jerusalem.stones", dur=1.5, dt=2.4), sfx("ding", dt=2.4),
    line("ls_07", "peter", "石头……会喊？喂，石头，你说句话呀？",
         "The stones... would shout? Hey, stone! Say something!",
         "Luke 19:40", dir="puzzled, then leaning in and whispering to the stone, very comic", pre=0.3, post=0.8),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "祷告的殿", "A house of prayer", "fixed", "temple", dist=0.62, height=0.24, yawDeg=20,
         desc="The temple court: stalls, cages of doves, piles of coins; the two sellers shout prices. Jesus steps in "
              "through the gate and stops; His face grows sad. The donkey grazes outside by the house."),
    music("market"),
    act("donkey", "graze", to=DONKEY_TIE, face="viewer", snap=True), prop("peter/palm", show=False),
    prop("jerusalem/crowd", show=False),   # the crowd line would hide both tables (SET.md §4); the procession is over
    act("jesus", "walk", to=GATE, y=0.0, face="temple", snap=True),
    act("peter", "idle", to=P_COURT, face="jesus", snap=True),
    act("john", "idle", to=JN_COURT, face="jesus", snap=True),
    act("james", "idle", to=JA_COURT, face="jesus", snap=True),
    act("andrew", "idle", to=PARK, snap=True), prop("andrew", show=False),
    act("jesus", "walk", to=J_T2, face="table2", dt=0.2),
    sfx("market_bustle"),
    act("seller1", "shout", face="viewer"),
    line("ls_08", "seller1", "卖鸽子咯！便宜卖啦——嗯，其实也不太便宜！",
         "Doves! Doves for sale! Cheap, cheap! ...Well, not that cheap!",
         "Mark 11:15", dir="loud market cry, then a sly aside to himself; comic, not nasty", pre=0.4, post=0.1),
    act("seller2", "shout", face="viewer", dt=-1.2), sfx("coins_clink", dt=-1.0),
    act("jesus", "sad_look", face="temple", dt=-0.3),
    line("ls_09", "narrator", "圣殿是祷告的地方，可现在吵得像菜市场，还有人骗钱。",
         "God's house was for praying. But now it was as noisy as a market, and some sellers cheated.",
         "Mark 11:15-17", dir="quieter, a little sad; slow on 上帝的家 / 'God's house'", pre=0.4, post=0.3),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "掀翻桌子", "Over go the tables", "fixed", "jesus", dist=0.55, height=0.2, yawDeg=28,
         desc="Jesus, firm, tips the money table over: coins roll everywhere. He opens the dove cages: the doves fly up "
              "and away. The sellers scramble. Nobody is hurt."),
    music("prayer_house"),
    act("jesus", "tip_table", face="table2"),
    prop("jerusalem/table2", show=False, dt=0.9), prop("jerusalem/table2Tipped", show=True, dt=0.9),
    prop("jerusalem/coinsFloor", show=True, dt=1.0, grow=0.4),
    fx("coins_spray", "jerusalem.table2", dur=1.6, dt=0.9), sfx("table_tip", dt=0.9), sfx("coins_scatter", dt=1.0),
    act("seller2", "shock", face="jesus", dt=1.0),
    act("jesus", "firm_talk", face="viewer", dt=2.0),
    line("ls_10", "jesus", "这是我父的家！是让大家祷告的地方，不是骗钱的地方！",
         "This is My Father's house, a place for everyone to pray, not to cheat people!",
         "Mark 11:17; John 2:16", dir="firm and strong, clear; sad underneath, never shouting in rage", pre=2.4, post=0.3),
    act("seller2", "walk", to=SELLER2_SIDE, face="viewer", dt=-0.6),
    act("seller2", "chase_coins", to=COINS, face="viewer", dt=0.6),
    act("seller2", "chase_coins", to=COINS2, face="viewer", dt=3.4),
    line("ls_11", "seller2", "哎呀，我的钱！别滚，别滚啦！",
         "Oh no, my money! Stop rolling! Stop rolling!",
         "Matthew 21:12", dir="comic panic, bent double chasing coins", pre=0.2, post=0.2),
    act("jesus", "walk", to=J_T1, face="table1", dt=-0.4),
    act("jesus", "open_cage", face="table1", dt=1.0),
    prop("jerusalem/cages", show=False, dt=1.6), prop("jerusalem/cagesOpen", show=True, dt=1.6),
    fx("doves_fly", "jerusalem.cagesOpen", dur=3.0, dt=1.7), sfx("dove_flutter", dt=1.7),
    act("seller1", "flap", face="cagesOpen", dt=1.9),
    line("ls_12", "seller1", "我的鸽子……都飞走啦！",
         "My doves... they've all flown away!",
         "Mark 11:15", dir="wailing, comic, flapping his arms like a bird", pre=2.4, post=0.4),
    act("jesus", "talk", face="viewer"),
    fx("golden_rays", "jesus.root", dur=7.0, dt=1.0), fx("music_notes", "jerusalem.temple", dur=6.0, dt=4.0),
    line("ls_13", "narrator", "耶稣爱上帝的家。后来病人来找他，他医好他们；小孩子们唱：和散那！",
         "Jesus loved God's house. Soon sick people came and He healed them, and children sang: 'Hosanna!'",
         "Matthew 21:14-15", dir="warm, Jesus was not just angry: He loved God's house; lift into the children's 和散那 / 'Hosanna' at the end", pre=0.6,
         post=0.6),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "谁最大？", "Who is the greatest?", "fixed", "peter", dist=0.55, height=0.2, yawDeg=20,
         desc="Evening. The upstairs room: a low table set for supper, a bench along the wall, lamps. The four "
              "disciples stand in the middle and squabble, chests out. Jesus stands quietly at the back by the basin."),
    music("argue"),
    # the tied donkey sits in front of the low indoor cameras (S06-S12): park it, bring it back for S13
    act("donkey", "idle", to=PARK, snap=True), prop("donkey", show=False),
    prop("seller1", show=False), prop("seller2", show=False),
    act("seller1", "idle", to=PARK, snap=True), act("seller2", "idle", to=PARK, snap=True),
    prop("andrew", show=True),
    fx("sunset_glow", "stage", dur=20.0),
    act("jesus", "idle", to=ROOM_J, y=UPPER, face="peter", snap=True),
    *[act(d, "idle", to=ARGUE[d], y=UPPER, face="viewer", snap=True) for d in DISCIPLES],
    line("ls_14", "narrator", "晚上，他们在楼上吃逾越节的晚餐。可是一路上，门徒们在争一件事……",
         "That evening they met upstairs for the Passover supper. But on the way, the disciples were arguing...",
         "Luke 22:7-14, 24", dir="cosy evening voice, then a knowing little pause at the end", pre=0.4, post=0.2),
    act("james", "boast", face="john", dt=-0.2),
    line("ls_15", "james", "等耶稣当了王，我要坐在他的右边！",
         "When Jesus is King, I'm going to sit on His right side!",
         "Mark 10:35-37", dir="puffed up, pleased with himself", pre=0.1, post=0.1),
    act("john", "boast", face="james"),
    line("ls_16", "john", "那我就坐左边！",
         "Then I'll sit on His left!",
         "Mark 10:37", dir="the youngest, quick and cheeky", pre=0.1, post=0.2),
    act("peter", "boast", face="james"),
    line("ls_17", "peter", "喂喂喂！我是第一个跟耶稣的，我才是最大的！",
         "Hey, hey, hey! I was the first one to follow Jesus. I'm the greatest!",
         "Mark 1:16-18; Luke 22:24", dir="big and loud, thumbs at his chest", pre=0.1, post=0.3),
    act("andrew", "talk", face="peter"),
    line("ls_18", "andrew", "哥，其实……是我先带你去见耶稣的。",
         "Um, brother... actually, I'm the one who took you to meet Jesus.",
         "John 1:40-42", dir="mild, a little shy, deadpan; the joke is in how calm he is", pre=0.4, post=0.3),
    act("peter", "argue", face="andrew"),
    line("ls_19", "peter", "呃……那、那个不算！",
         "Er... that... that doesn't count!",
         "Luke 22:24", dir="caught out, flustered, comic", pre=0.2, post=0.6),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "一盆水，一条毛巾", "A bowl and a towel", "fixed", "lowTable", dist=0.6, height=0.22, yawDeg=25,
         desc="Night, lamps lit. The disciples sit on the bench along the wall with dusty feet. Jesus quietly ties a "
              "towel round His waist, pours water into a bowl, carries it over and kneels in front of Andrew."),
    music("towel"),
    fx("night", "stage", dur=200.0), fx("lamp_flame", "jerusalem.lamp1", dur=200.0),
    fx("lamp_flame", "jerusalem.lamp2", dur=200.0),
    *[act(d, "sit_bench", to=BENCH[d], y=UPPER, face="jesus", snap=True) for d in DISCIPLES],
    act("jesus", "idle", to=STAND, y=UPPER, face="viewer", snap=True),
    line("ls_20", "narrator", "平常会有仆人给客人洗脏脏的脚。可是今天晚上，谁也不愿意做仆人。",
         "Usually a servant washed the guests' dusty feet. But that night, nobody wanted to be the servant.",
         "John 13:2-5", dir="plain and gentle; a small sigh on 谁也不愿意 / 'nobody wanted'", pre=0.6, post=0.3),
    act("jesus", "rise_towel", face="basinStand"),
    prop("jesus/towel", show=True, dt=0.8),
    prop("jerusalem/basinJug", show=False, dt=1.6), prop("jesus/basin", show=True, dt=1.6),
    fx("water_pour", "jesus.basin", dur=1.8, dt=1.8), sfx("water_pour", dt=1.8),
    line("ls_21", "narrator", "耶稣在腰上束了一条毛巾，把水倒进盆里……然后跪下来，给门徒洗脚。",
         "Jesus tied a towel round His waist, poured water into a bowl... then knelt down and began to wash their feet.",
         "John 13:4-5", dir="hushed, slow, with wonder; long pause at the dots", pre=0.6, post=0.2),
    act("jesus", "walk", to=WAY, face="andrew", dt=-4.5), prop("jesus/basin", show=False, dt=-4.5, grow=0.3),
    act("jesus", "walk", to=ROUND, face="andrew", dt=-3.5),
    act("jesus", "walk", to=WASH["andrew"], face="andrew", dt=-1.0),
    act("jesus", "kneel_wash", face="andrew", blend=0.8, dt=0.6), prop("jesus/basin", show=True, dt=0.6, grow=0.4),
    sfx("splash_small", dt=1.6),
    *[act(d, "amazed", face="jesus", dt=0.6 + 0.2 * i) for i, d in enumerate(("andrew", "james", "john", "peter"))],
    line("ls_22", "james", "老师……在给我们洗脚？",
         "The Teacher... is washing our feet?",
         "John 13:5", dir="a stunned whisper", pre=2.0, post=0.6),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "不要洗我的脚！", "Not my feet!", "fixed", "peter", dist=0.45, height=0.15, yawDeg=5,
         desc="Jesus moves along the bench to Peter and kneels. Peter jerks his feet back, waving his hands; then "
              "throws out his hands and pushes his head forward: wash all of me!"),
    music("not_my_feet"),
    act("jesus", "walk", to=WASH["peter"], face="peter", blend=0.6),   # one straight move along the lane (0.23 in 2.2 s)
    prop("jesus/basin", show=False, grow=0.3),
    act("jesus", "kneel_wash", face="peter", blend=0.8, dt=2.2), prop("jesus/basin", show=True, dt=2.2, grow=0.4),
    act("peter", "refuse", face="jesus", dt=2.4),
    line("ls_23", "peter", "主啊，你要给我洗脚？不行！永远不行！",
         "Lord, You're going to wash MY feet? No! Never, ever!",
         "John 13:6-8", dir="shocked and embarrassed, hands up, pulling his feet back; loud", pre=1.8, post=0.3),
    act("jesus", "kneel_talk", face="peter"),
    line("ls_24", "jesus", "彼得，我若不洗你，你就不能和我在一起了。",
         "Peter, if I don't wash you, you can't belong with Me.",
         "John 13:8", dir="very gentle, patient, looking up at him", pre=0.3, post=0.4),
    act("peter", "offer_all", face="jesus"),
    line("ls_25", "peter", "啊？那不光洗脚！手也洗，头也洗，全身都洗吧！",
         "What? Then not just my feet! My hands and my head too! Wash all of me!",
         "John 13:9", dir="all in at once, comic over-eagerness, voice rising", pre=0.2, post=0.2),
    act("jesus", "kneel_laugh", face="peter", dt=-0.2),
    line("ls_26", "jesus", "哈哈，彼得，洗洗脚就够啦。",
         "Ha ha! Peter, your feet are enough.",
         "John 13:10", dir="a warm, real laugh; fond", pre=0.1, post=0.2),
    act("peter", "sit_wash", face="jesus"), sfx("splash_small", dt=0.4),
    line("ls_27", "narrator", "犹大也在这里；他已经决定背叛耶稣，耶稣知道，却还是给他洗了脚。",
         "Judas was there too; he had already turned against Jesus, yet Jesus washed his feet as well.",
         "John 13:2, 11, 21", dir="quiet and plain, no drama; a soft weight on 还是 / 'as well'", pre=0.8, post=0.6),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "照着我做", "Do what I did", "fixed", "jesus", dist=0.6, height=0.35, yawDeg=-20,
         desc="Jesus stands up with the towel still round His waist and speaks to them all. The four look at each "
              "other, a bit ashamed."),
    music("serve"),
    prop("jesus/basin", show=False),
    act("jesus", "stand_talk", face="viewer"),
    line("ls_28", "jesus", "你们叫我老师，叫我主。我给你们洗了脚，你们也要这样彼此服侍。",
         "You call Me Teacher and Lord. I washed your feet, so now you should serve each other too.",
         "John 13:13-15", dir="warm, clear, unhurried; to all four", pre=0.6, post=0.4),
    *[act(d, "ashamed", face="viewer", dt=-0.6 + 0.2 * i) for i, d in enumerate(DISCIPLES)],
    line("ls_29", "jesus", "最大的人，要像仆人一样，帮助大家。",
         "The greatest one is the one who serves, like a helper to everyone.",
         "Luke 22:26-27; Mark 10:43-45", dir="simple and gentle, the heart of the story; slow", pre=0.4, post=0.8),
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "饼", "The bread", "fixed", "jesus", dist=0.5, height=0.17, yawDeg=0,
         desc="At the low table, lamps glowing. Jesus, in the middle, takes the round flat bread, looks up and thanks "
              "God, breaks it and passes it to His friends."),
    music("supper"),
    prop("jesus/towel", show=False),
    *[act(k, "sit_supper", to=v, y=UPPER, face="jesus" if k != "jesus" else "viewer", snap=True)
      for k, v in SUP.items()],
    line("ls_30", "narrator", "吃晚饭的时候，耶稣拿起饼来，感谢上帝，把饼掰开，分给门徒。",
         "During supper, Jesus took the bread, thanked God for it, broke it, and gave it to His disciples.",
         "Luke 22:19", dir="reverent and simple; slow, each action its own beat", pre=0.6, post=0.2),
    act("jesus", "bless_bread", face="viewer", dt=-4.0),
    prop("jerusalem/breadLoaf", show=False, dt=-3.8), prop("jesus/bread", show=True, dt=-3.8),
    line("ls_31", "jesus", "这饼是我的身体，是为你们舍的。以后你们一起吃饼的时候，要记得我。",
         "This bread is My body, given for you. Whenever you eat it together, remember Me.",
         "Luke 22:19", dir="quiet, tender, deliberate; looking at each of them", pre=0.4, post=0.6),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "杯", "The cup", "fixed", "jesus", dist=0.45, height=0.16, yawDeg=-10,
         desc="Jesus lifts the cup with both hands. A soft warm glow. The disciples are very still."),
    prop("jesus/bread", show=False),
    act("jesus", "lift_cup", face="viewer"),
    prop("jerusalem/cupTable", show=False, dt=0.4), prop("jesus/cup", show=True, dt=0.4),
    fx("heart_glow", "jesus.chest", dur=6.0, dt=1.2),
    line("ls_32", "jesus", "这杯是上帝新的约定。我要为你们舍命，让大家的罪得到赦免。",
         "This cup is God's new promise. I give My life for you, so that sins can be forgiven.",
         "Luke 22:20; Matthew 26:28", dir="very gentle and calm; not sad, full of love", pre=1.0, post=0.6),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "轮到我了", "My turn now", "fixed", "peter", dist=0.5, height=0.17, yawDeg=55,
         desc="Peter gets up, picks up the towel and the water jug, and kneels down in front of his brother Andrew. "
              "Andrew giggles; James and John grin and nudge each other."),
    music("my_turn"),
    prop("jesus/cup", show=False), prop("jerusalem/cupTable", show=True),
    act("jesus", "sit_supper", face="viewer"),   # lift_cup holds its last frame: put the hands down with the cup
    act("peter", "serve_rise", to=PETER_SERVE, y=UPPER, face="andrew"),
    prop("peter/towel", show=True, dt=0.8), prop("peter/jug", show=True, dt=0.8),
    line("ls_33", "peter", "王都给我洗脚了……安得烈，来，把脚伸出来——这回轮到我了！",
         "The King washed my feet... Andrew, come on, feet out! It's my turn now!",
         "John 13:14-15", dir="first slow and thoughtful, then a warm, cheerful decision", pre=0.4, post=0.2),
    act("peter", "kneel_serve", face="andrew", dt=-0.8),
    act("andrew", "sit_wash", face="peter", dt=-1.4),
    fx("water_pour", "andrew.footR", dur=1.4, dt=0.2), sfx("splash_small", dt=0.6),
    line("ls_34", "andrew", "哈哈，好痒！哥，你洗得比耶稣还慢！",
         "Ha ha, that tickles! Brother, you're even slower than Jesus!",
         "John 13:14", dir="giggling, teasing his big brother", pre=0.8, post=0.2),
    act("james", "nudge", face="viewer", dt=-0.6), act("john", "nudge", face="viewer", dt=-0.4),   # the clip jabs sideways
    act("jesus", "smile", face="peter", dt=-0.6),
    # S13 --------------------------------------------------------------------------------------------------------
    shot("S13", "真正的大人物", "Truly great", "fixed", "jerusalem", dist=0.95, height=0.48, yawDeg=6,
         desc="The whole page at night: the lit upstairs room with Jesus and His friends at the table, the quiet temple "
              "court, the donkey dozing by the house. A warm glow from the room."),
    music("finale"),
    act("donkey", "graze", to=DONKEY_TIE, face="viewer", snap=True), prop("donkey", show=True),
    fx("golden_rays", "jerusalem.house", dur=12.0, dt=0.3),
    line("ls_35", "narrator", "耶稣是最大的王，可他没有等别人来伺候他，他自己弯下腰，来服侍别人。",
         "Jesus is the greatest King of all. But He didn't wait for others to serve Him. He bent down and served them.",
         "Mark 10:45; John 13:15", dir="warm moral, straight to the child; slow and clear", pre=0.6, post=0.3),
    line("ls_36", "narrator", "你也可以像耶稣一样：帮忙摆碗筷，让朋友先玩。爱帮助别人的，才是真正的大人物！",
         "You can serve like Jesus too: help set the table, let a friend go first. Helpers are the truly great ones!",
         "John 13:15-17; Luke 22:26", dir="encouraging, a smile; lift on 真正的大人物 / 'truly great'", pre=0.3,
         post=0.4),
    act("donkey", "hee_haw", face="viewer", dt=-0.2), sfx("hee_haw", dt=0.0),
    pause(1.2),
]
