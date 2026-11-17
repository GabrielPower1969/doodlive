"""Real Miracles — the play, as beats relative to each other (docs/miracles/CONTRACT.md §5).

`tools/story/build_timeline.py miracles` turns this into assets/miracles/timeline.json, placing every line by the real
voice durations. Helpers: shot / line / act / fx / sfx / music / prop / pause (same as every pack).
Marks are art-width units on the page (x right, z toward the viewer); the set's marks are in CONTRACT.md §6.
`face` takes an actor id, "viewer", or a set node name ("house", "boat", "roofHole").

Two acts on one page: Peter's house in Capernaum (left; open at the front like a doll's house, flat roof at
y = ROOF, outside stair on its left wall) and the Sea of Galilee with Peter's boat (right back, deck y = DECK).

Staging rules (learned in Jonah, docs/jonah/FIXLOG-20261115.md):
- An actor who is not in a scene is HIDDEN with prop("<actor>", show=False) and moved with snap=True.
- No camera targets "all": shots target an actor or a set node.
- `orbit` turns 6 deg/s: orbit shots stay under ~10 s.
- Carrying: the man lies on his mat (`carried`, base y CARRY_Y so the mat poles are at the friends' hand height);
  friend1 walks 0.16 ahead of him, friend2 0.16 behind, all three given the same marks shifted along the walk and the
  same dt, so they move as one. friend3 / friend4 walk beside.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py

ID = "miracles"
CAST = ["jesus", "peter", "man", "friend1", "friend2", "friend3", "friend4"]
SET = "galilee"

ROOF = 0.40                    # the house's flat roof (walkable top)
DECK = 0.06                    # the boat's deck
CARRY_Y = 0.10                 # base height of the man while carried (mat at the friends' hand height, CONTRACT §4)
PARK = (0.80, 0.30)            # hidden actors wait here

# Act 1: the house (inside floor y 0; interior x -0.46..-0.04, z -0.56..-0.26; the front is open)
JESUS_IN = (-0.36, -0.46)      # Jesus teaching, at the back of the room
PETER_IN = (-0.12, -0.46)      # Peter inside, by the side door (right wall)
LAND = (-0.24, -0.38)          # where the mat comes down, right under the roof hole; 0.15 from Jesus
HOLE = LAND                    # the roof hole is directly above LAND (roof top y ROOF)
# the road and the yard (in front of the house)
ROAD_START = (0.20, 0.14)      # where the friends come in (front right)
YARD = (0.02, -0.12)           # in front of the side door, behind the crowd
STAIR_FOOT = (-0.53, -0.08)    # foot of the outside stair (left wall)
STAIR_TOP = (-0.53, -0.46)     # top of the stair, on the roof's back-left corner (y ROOF)
# friends on the roof, kneeling round the hole (all y ROOF)
R1 = (-0.36, -0.38)            # friend1, left of the hole
R2 = (-0.12, -0.38)            # friend2, right of the hole
R3 = (-0.32, -0.50)            # friend3, back-left
R4 = (-0.16, -0.50)            # friend4, back-right
MAN_HOME = (-0.10, 0.14)       # the healed man dances out to the front
# Act 2: the lake and the boat (deck y DECK; hull x 0.16..0.56 at z -0.34)
BOAT_PETER = (0.28, -0.32)     # Peter by the mast / oar, bow half
BOAT_STERN = (0.48, -0.34)     # Jesus asleep on the cushion at the stern
BOAT_WAKE = (0.38, -0.32)      # Peter 0.10 in front of the sleeping Jesus
BEACH_J = (0.18, 0.04)         # morning, on the beach
BEACH_P = (0.32, 0.06)
MAN_END = (-0.14, 0.10)        # the healed man, waving with his rolled mat at the end

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "挤满了人", "A full house", "orbit", "house", dist=0.95, height=0.45, yawDeg=-20,
         desc="Short orbit over the page: a flat-roofed house on the left full of people, a lake and a boat on the right. "
              "Inside, Jesus is talking; people crowd round the door."),
    music("capernaum"),
    act("jesus", "teach", to=JESUS_IN, face="viewer", snap=True),
    act("peter", "idle", to=PETER_IN, face="jesus", snap=True),
    act("man", "lie_mat", to=PARK, face="viewer", snap=True), prop("man", show=False),
    *[act("friend%d" % i, "idle", to=PARK, face="viewer", snap=True) for i in range(1, 5)],
    *[prop("friend%d" % i, show=False) for i in range(1, 5)],
    prop("galilee/roofHole", show=False), prop("galilee/rubble", show=False),
    prop("man/matRoll", show=False), prop("peter/bucket", show=False),
    pause(0.3),
    sfx("crowd_murmur"),
    line("mi_01", "narrator", "耶稣来到迦百农，住在彼得家。大家听说了，一下子全挤来了，屋里屋外都是人！",
         "Jesus came to the town of Capernaum and stayed at Peter's house. Everyone heard, and they all squeezed in. "
         "People inside, people outside, people everywhere!",
         "Mark 2:1-2", dir="storyteller opening, bright; speed up and pile on 屋里屋外都是人 / 'people everywhere'",
         post=0.2),
    shot("S01b", "挤满了人", "A full house", "fixed", "jesus", dist=0.55, height=0.16, yawDeg=10,
         desc="Low and close, under the roof: Jesus talks warmly to the crowd; Peter beside the door nods along."),
    line("mi_02", "jesus", "上帝爱你们每一个人。他的国，就在你们中间。",
         "God loves every one of you. His kingdom is right here among you.",
         "Mark 2:2; Luke 17:21", dir="warm and simple, smiling at the people; not preachy", pre=0.3, post=0.3),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "四个好朋友", "Four good friends", "follow", "man", dist=0.75, height=0.24, yawDeg=-30,
         desc="Four friends come up the road carrying a man on a mat: two hold the mat's poles, two lead the way."),
    music("friends"),
    prop("man", show=True), *[prop("friend%d" % i, show=True) for i in range(1, 5)],
    act("man", "carried", to=ROAD_START, y=CARRY_Y, face="house", snap=True),
    act("friend1", "carry_front", to=(0.10, 0.08), face="house", snap=True),
    act("friend2", "carry_back", to=(0.30, 0.20), face="house", snap=True),
    act("friend3", "walk", to=(0.02, 0.14), face="house", snap=True),
    act("friend4", "walk", to=(0.10, 0.20), face="house", snap=True),
    line("mi_03", "narrator", "这时候，路上来了四个好朋友，抬着一个人。这个人的腿不能走路，只能天天躺在褥子上。",
         "Just then, four good friends came down the road, carrying a man. His legs couldn't walk, so every day he "
         "had to lie on his mat.",
         "Mark 2:3", dir="warm, a little tender on 只能天天躺在褥子上 / 'every day he had to lie'", pre=0.3, post=0.1),
    act("man", "carried", to=(0.12, -0.04), y=CARRY_Y, face="house", dt=-3.0),
    act("friend1", "carry_front", to=(0.02, -0.10), face="house", dt=-3.0),
    act("friend2", "carry_back", to=(0.22, 0.02), face="house", dt=-3.0),
    act("friend3", "walk", to=(-0.04, 0.00), face="house", dt=-3.0),
    act("friend4", "walk", to=(0.08, 0.06), face="house", dt=-3.0),
    line("mi_04", "friend1", "加油！耶稣一定能帮你！",
         "Come on, we're nearly there! Jesus can help you, I know He can!",
         "Mark 2:3-5", dir="bright, panting a little from carrying; total certainty in 一定 / 'I know He can'",
         pre=0.2, post=0.2),
    line("mi_05", "man", "谢谢你们……我好紧张呀。",
         "Thank you, friends... I'm so nervous.",
         "Mark 2:3", dir="small, shy, a nervous little laugh", pre=0.2, post=0.3),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "进不去", "No way in", "fixed", "friend3", dist=0.62, height=0.2, yawDeg=-35,
         desc="At the side door: a wall of backs. friend3 tries to squeeze through and bounces back. They all stop and think."),
    music("no_way"),
    act("man", "carried", face="house"), act("friend1", "carry_front", face="house"),
    act("friend2", "carry_back", face="house"),
    act("friend3", "squeeze_bounce", to=YARD, face="house"),
    sfx("boing", dt=1.6),
    line("mi_06", "friend3", "请让一让！让一让——哎哟！",
         "Excuse me! Excuse me, please... oof!",
         "Mark 2:4", dir="polite and hopeful, then a comic 'oof' as he bounces off the crowd", pre=0.4, post=0.2),
    line("mi_07", "people", "别挤啦！进不去啦！",
         "No pushing! There's no room!",
         "Mark 2:4", dir="crowd of 8-10, grumbly but not nasty, overlapping", pre=0.1, post=0.3),
    act("friend4", "think", face="friend1"), act("friend3", "idle", face="friend1", dt=0.3),
    act("friend2", "carry_back", face="friend1"),
    line("mi_08", "friend2", "嗯……门进不去……",
         "Hmm... we can't get in the door...",
         "Mark 2:4", dir="big slow friend, thinking out loud, long 嗯 / 'hmm'", pre=0.6, post=0.3),
    act("friend1", "idea", face="viewer", dt=-0.2),
    sfx("ding", dt=0.1),
    line("mi_09", "friend1", "有了！我们从屋顶下去！",
         "I've got it! We'll go in through the roof!",
         "Mark 2:4", dir="sudden bright idea, finger up; a little gasp before 有了 / 'I've got it'", pre=0.1, post=0.3),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "爬上屋顶", "Up on the roof", "follow", "man", dist=0.75, height=0.36, yawDeg=-50,
         desc="They carry him up the outside stair onto the flat roof, then kneel and start digging: tiles and dust fly."),
    music("roof"),
    act("man", "carried", to=(-0.40, -0.06), y=CARRY_Y, face="viewer"),
    act("friend1", "carry_front", to=(-0.53, -0.08), face="viewer"),
    act("friend2", "carry_back", to=(-0.26, -0.06), face="viewer"),
    act("friend3", "walk", to=(-0.30, 0.02), face="viewer"),
    act("friend4", "walk", to=(-0.20, 0.02), face="viewer"),
    # up the stair: friend1 first, the man, friend2 (heights ease over the walks)
    act("friend1", "carry_front", to=(-0.53, -0.40), y=ROOF, face="galilee", dt=3.4),
    act("man", "carried", to=(-0.53, -0.24), y=ROOF * 0.5 + CARRY_Y, face="galilee", dt=3.4),
    act("friend2", "carry_back", to=(-0.53, -0.10), y=0.04, face="galilee", dt=3.4),
    act("friend1", "carry_front", to=(-0.40, -0.46), y=ROOF, face="roofHole", dt=6.6),
    act("man", "carried", to=(-0.40, -0.30), y=ROOF + CARRY_Y, face="roofHole", dt=6.6),
    act("friend2", "carry_back", to=(-0.53, -0.36), y=ROOF, face="roofHole", dt=6.6),
    act("friend3", "walk", to=STAIR_FOOT, face="galilee", dt=4.0),
    act("friend3", "walk", to=STAIR_TOP, y=ROOF, face="roofHole", dt=6.4),
    act("friend4", "walk", to=(-0.53, 0.0), face="galilee", dt=5.0),
    act("friend4", "walk", to=STAIR_TOP, y=ROOF, face="roofHole", dt=7.6),
    line("mi_10", "narrator", "他们抬着朋友，一步一步爬上了屋顶。那时候的屋顶是平的，用木头、树枝和泥土铺成。",
         "Step by step, they carried their friend up onto the roof. In those days roofs were flat, made of wood, "
         "branches and mud.",
         "Mark 2:4", dir="steady, a bit breathless with them on 一步一步 / 'step by step'; then explaining, friendly",
         pre=0.4, post=0.3),
    # the man is set down beside the hole; the friends kneel round it and dig
    act("man", "lie_mat", to=(-0.24, -0.30), y=ROOF, face="viewer", snap=True, dt=0.2),
    act("friend1", "dig", to=R1, y=ROOF, face="roofHole", dt=0.2),
    act("friend2", "dig", to=R2, y=ROOF, face="roofHole", dt=0.4),
    act("friend3", "dig", to=R3, y=ROOF, face="roofHole", dt=0.6),
    act("friend4", "dig", to=R4, y=ROOF, face="roofHole", dt=0.8),
    sfx("dig_loop", dt=0.6), fx("dig_dirt", "galilee.roofHole", dur=5.0, dt=0.6),
    line("mi_11", "friends", "挖呀挖，挖呀挖！",
         "Dig, dig, dig! Dig, dig, dig!",
         "Mark 2:4", dir="the four friends together, a cheerful work chant, rhythmic", pre=1.0, post=0.4),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "我的屋顶！", "My roof!", "fixed", "peter", dist=0.45, height=0.15, yawDeg=-15,
         desc="Inside: crumbs and dust trickle down onto Peter's head. A patch of sky opens in the ceiling. "
              "Peter clutches his head; Jesus looks up and smiles."),
    prop("galilee/roofPatch", show=False, dt=0.6), prop("galilee/roofHole", show=True, dt=0.6),
    prop("galilee/rubble", show=True, dt=0.8, grow=0.4),
    fx("dust_fall", "galilee.roofHole", dur=3.0, dt=0.2), sfx("crumble", dt=0.2),
    act("peter", "roof_shock", face="viewer", dt=0.6),
    line("mi_12", "peter", "哎！哎哎哎！我的屋顶！",
         "Hey! Hey, hey, HEY! My roof!",
         "Mark 2:4", dir="big comic panic; rising 哎 three times; 我的屋顶 / 'My roof!' almost a wail, funny", pre=1.4,
         post=0.3),
    act("peter", "dust_off", face="roofHole", dt=-0.4),
    act("jesus", "look_up_smile", face="roofHole", dt=-1.0),
    line("mi_13", "jesus", "哈哈，彼得，你看——有人来了。",
         "Ha ha! Peter, look... someone's coming.",
         "Mark 2:4-5", dir="amused, warm chuckle; gentle teasing to Peter; curious on 有人来了 / 'someone's coming'",
         pre=0.3, post=0.3),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "慢慢放下来", "Down he comes", "fixed", "jesus", dist=0.62, height=0.22, yawDeg=18,
         desc="Through the hole the mat comes down on four ropes, slowly swinging, until the man lies right in front of Jesus. "
              "The friends' faces peep down through the hole."),
    music("lowering"),
    act("man", "lowered", to=LAND, y=0.0, face="jesus", snap=True),
    act("friend1", "lower_rope", face="roofHole"), act("friend2", "lower_rope", face="roofHole"),
    act("friend3", "lower_rope", face="roofHole"), act("friend4", "lower_rope", face="roofHole"),
    sfx("rope_creak", dt=0.2),
    line("mi_14", "narrator", "他们在屋顶上挖了一个洞，用绳子把褥子慢慢地、慢慢地放下来，正好放在耶稣面前。",
         "They made a hole in the roof, and with ropes they let the mat down... slowly... slowly... right in front of "
         "Jesus.",
         "Mark 2:4", dir="hushed and suspenseful; stretch 慢慢地、慢慢地 / 'slowly... slowly'; land softly on 耶稣面前",
         pre=0.6, post=0.4),
    act("man", "lie_mat", face="jesus"),
    act("friend1", "peek", face="roofHole"), act("friend2", "peek", face="roofHole", dt=0.2),
    act("friend3", "peek", face="roofHole", dt=0.1), act("friend4", "peek", face="roofHole", dt=0.3),
    act("peter", "idle", face="man"),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "起来，走吧", "Get up and walk", "fixed", "man", dist=0.55, height=0.18, yawDeg=-8,
         desc="Jesus looks up at the four faces in the hole, then down at the man, and kneels beside him."),
    music("heal"),
    act("jesus", "kneel_kind", to=(-0.34, -0.40), face="man"),
    line("mi_15", "narrator", "耶稣抬头看见四个朋友，知道他们真的相信他。",
         "Jesus looked up at the four friends, and He saw how much they trusted Him.",
         "Mark 2:5", dir="warm and slow; a small smile in the voice on 真的相信 / 'trusted Him'", pre=0.6, post=0.3),
    line("mi_16", "jesus", "孩子，你的罪赦免了。",
         "Son, your sins are forgiven.",
         "Mark 2:5", dir="very tender, close, like a father; unhurried", pre=0.3, post=0.6),
    fx("heart_glow", "man.chest", dur=3.0, dt=-1.0),
    line("mi_17", "narrator", "有人在心里嘀咕：只有上帝才能赦罪啊！耶稣知道他们在想什么。",
         "Some people grumbled inside: only God can forgive sins! Jesus knew what they were thinking.",
         "Mark 2:6-8", dir="a touch of mystery on the grumble (lower voice), then plain", pre=0.3, post=0.3),
    act("jesus", "stand_talk", face="viewer"),
    line("mi_18", "jesus", "为了让你们知道，我有赦罪的权柄——",
         "So that you will know I have the power to forgive sins...",
         "Mark 2:9-10", dir="calm, clear, to the whole room; a pause at the dash", pre=0.3, post=0.4),
    act("jesus", "command_rise", face="man"),
    fx("golden_rays", "man.root", dur=5.0, dt=0.4), sfx("sparkle", dt=0.6),
    line("mi_19", "jesus", "起来！拿起你的褥子，回家去吧！",
         "Get up! Pick up your mat, and go home!",
         "Mark 2:11", dir="joyful command, bright and strong, a smile in it; not shouted", pre=0.1, post=0.4),
    act("man", "sit_up", face="jesus", dt=-0.4),
    act("man", "stand_wobbly", face="viewer", dt=1.4),
    line("mi_20", "man", "我……我的腿……我站起来了！我能走了！",
         "My... my legs... I'm standing! I can walk!",
         "Mark 2:12", dir="disbelief to laughter: stammer, a gasp, then pure joy on 我能走了 / 'I can walk!'",
         pre=1.6, post=0.2),
    act("man", "jump_joy", face="viewer", dt=-0.6),
    fx("sparkle", "man.root", dur=2.0, dt=-0.4), sfx("cheer", dt=-0.2),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "从来没见过", "Never seen anything like it", "follow", "man", dist=0.8, height=0.3, yawDeg=-20,
         desc="He rolls up his mat, slings it on his shoulder and dances out of the house to the front of the page; the "
              "friends jump and cheer on the roof; the crowd gasps."),
    music("joy"),
    act("man", "roll_mat", face="viewer"),
    prop("man/mat", show=False, dt=1.2), prop("man/matRoll", show=True, dt=1.2),
    act("friend1", "cheer", face="viewer", dt=0.4), act("friend2", "cheer", face="viewer", dt=0.6),
    act("friend3", "cheer", face="viewer", dt=0.5), act("friend4", "cheer", face="viewer", dt=0.7),
    act("man", "dance_mat", to=MAN_HOME, face="viewer", dt=2.0),
    line("mi_21", "people", "哇！我们从来没见过这样的事！",
         "Wow! We have never seen anything like this!",
         "Mark 2:12", dir="crowd of 8-10, amazed, overlapping gasps and a child's 哇", pre=0.6, post=0.2),
    line("mi_22", "narrator", "大家都很惊奇，一起赞美上帝。",
         "Everyone was amazed, and they all praised God.",
         "Mark 2:12", dir="warm and glowing", pre=0.2, post=0.2),
    act("peter", "laugh", face="roofHole", dt=-0.5),
    line("mi_23", "peter", "好吧好吧——这个洞，挖得值！",
         "All right, all right... that hole was worth it!",
         "Mark 2:4, 12", dir="big hearty laugh first, then shaking his head, delighted", pre=0.2, post=0.6),
    act("man", "wave", face="viewer", dt=-1.0),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "到对岸去", "To the other side", "fixed", "boat", dist=0.7, height=0.22, yawDeg=-25,
         desc="Evening on the lake. Peter's boat with Jesus and Peter aboard. Jesus, tired, lies down on a cushion at "
              "the back and falls asleep."),
    music("evening"),
    prop("man", show=False), *[prop("friend%d" % i, show=False) for i in range(1, 5)],
    act("man", "idle", to=PARK, snap=True), *[act("friend%d" % i, "idle", to=PARK, snap=True) for i in range(1, 5)],
    fx("sunset_glow", "stage", dur=16.0),
    act("jesus", "idle", to=(0.42, -0.34), y=DECK, face="peter", snap=True),
    act("peter", "steer", to=BOAT_PETER, y=DECK, face="viewer", snap=True),
    sfx("lake_lap"),
    line("mi_24", "narrator", "那天傍晚，耶稣对门徒说：我们到湖对岸去吧。他们就上了彼得的船。",
         "That evening, Jesus said to His friends: let's go across to the other side of the lake. So they got into "
         "Peter's boat.",
         "Mark 4:35-36", dir="calm, evening voice, a gentle lilt like the water", pre=0.4, post=0.3),
    act("jesus", "lie_sleep", to=BOAT_STERN, y=DECK, face="viewer"),
    fx("zzz", "jesus.head", dur=5.0, dt=1.6),
    line("mi_25", "narrator", "耶稣忙了一整天，累了，枕着一个枕头，在船尾睡着了。",
         "Jesus had been busy all day. He was tired, so He lay down on a cushion at the back of the boat and fell "
         "asleep.",
         "Mark 4:38", dir="soft, sleepy, smiling", pre=0.6, post=0.4),
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "大风暴", "The big storm", "fixed", "boat", dist=0.62, height=0.26, yawDeg=12,
         desc="Dark sky, rain, wind, waves splashing into the boat. Peter heaves at the oar, then bails with a bucket. "
              "Jesus sleeps on."),
    music("storm"),
    fx("storm_rain", "stage", dur=20.0), fx("tension_dim", "stage", dur=20.0),
    fx("wave_splash", "galilee.boat", dur=18.0, dt=0.8),
    sfx("thunder", dt=0.3), sfx("wind_loop"), sfx("thunder", dt=7.0),
    act("peter", "steer_hard", face="viewer"),
    line("mi_26", "narrator", "忽然，起了一阵大风暴！浪一个接一个打进船里，船里的水都快满了！",
         "Suddenly a huge storm came! Wave after wave crashed into the boat, and it was filling up with water!",
         "Mark 4:37", dir="exciting, faster, a little breathless; big on 大风暴 / 'huge storm'", pre=1.0, post=0.2),
    prop("peter/bucket", show=True, dt=0.2), act("peter", "bail", face="viewer", dt=0.2),
    line("mi_27", "peter", "舀水！快舀水！不行啦，水太多啦！",
         "Bail! Bail faster! It's no good, there's too much water!",
         "Mark 4:37", dir="comic panic, shouting over the wind, breathless; voice cracks on 不行啦 / 'no good'",
         pre=0.6, post=0.2),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "老师，快醒醒！", "Teacher, wake up!", "fixed", "jesus", dist=0.45, height=0.16, yawDeg=-30,
         desc="Close on the stern: Jesus is still asleep in the rain. Peter stumbles over and shakes Him."),
    prop("peter/bucket", show=False),
    act("peter", "walk", to=BOAT_WAKE, y=DECK, face="jesus"),
    act("peter", "shake_awake", face="jesus", dt=1.4),
    line("mi_28", "peter", "老师！老师，快醒醒！我们快要沉下去了，你不管我们吗？",
         "Teacher! Teacher, wake up! We're going to sink! Don't you care about us?",
         "Mark 4:38", dir="frantic, shaking Him; the last question hurt and scared, not angry", pre=1.6, post=0.3),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "安静吧！", "Quiet! Be still!", "fixed", "jesus", dist=0.6, height=0.2, yawDeg=8,
         desc="Jesus wakes, stands up in the rain at the stern and stretches out His arms over the water. The wind "
              "stops, the rain stops, the lake goes flat as glass; stars come out."),
    act("jesus", "wake_up", face="peter"),
    act("jesus", "calm_storm", face="viewer", dt=1.4),
    line("mi_29", "jesus", "风，停下来！浪，安静吧！",
         "Wind, stop! Waves... be still!",
         "Mark 4:39", dir="firm and strong but not angry; a small pause before 安静吧 / 'be still', then soft", pre=0.3,
         post=0.6),
    fx("calm_wave", "galilee.lake", dur=3.0, dt=-0.4), sfx("wind_stop", dt=-0.4),
    music("calm", dt=-0.2), fx("night", "stage", dur=14.0, dt=0.2), fx("sparkle", "galilee.lake", dur=2.5, dt=0.4),
    act("peter", "amazed", face="jesus", dt=0.6),
    act("jesus", "talk", face="peter", dt=1.6),
    line("mi_30", "jesus", "你们为什么害怕呢？还不相信我吗？",
         "Why were you so afraid? Do you still not trust Me?",
         "Mark 4:40", dir="very gentle, a small smile, like a friend; not a telling-off", pre=1.8, post=0.4),
    # S13 --------------------------------------------------------------------------------------------------------
    shot("S13", "他到底是谁？", "Who is He?", "fixed", "peter", dist=0.5, height=0.17, yawDeg=-20,
         desc="Peter, soaked, stares at the quiet lake and back at Jesus."),
    act("peter", "amazed", face="viewer"),
    line("mi_31", "peter", "他到底是谁？连风和浪都听他的话！",
         "Who is this? Even the wind and the waves do what He says!",
         "Mark 4:41", dir="awed whisper to himself, then louder with wonder on 连风和浪 / 'even the wind'", pre=0.4,
         post=0.4),
    shot("S13b", "他到底是谁？", "Who is He?", "fixed", "galilee", dist=0.95, height=0.48, yawDeg=6,
         desc="Morning: the whole page from the front. Jesus and Peter on the beach; the healed man comes skipping along "
              "the road with his rolled mat on his shoulder and waves. Golden light."),
    music("finale"),
    act("jesus", "wave", to=BEACH_J, y=0.0, face="viewer", snap=True),
    act("peter", "wave", to=BEACH_P, y=0.0, face="viewer", snap=True),
    prop("man", show=True), act("man", "wave", to=MAN_END, y=0.0, face="viewer", snap=True),
    fx("golden_rays", "jesus.root", dur=9.0, dt=0.3),
    line("mi_32", "narrator", "变魔术，是骗眼睛的。耶稣行的是真正的神迹：他让我们知道，他爱我们，也有能力帮助我们。",
         "A magic trick fools your eyes. But Jesus did real miracles. They show us that He loves us, and He is able "
         "to help us.",
         "Mark 2:10-12; Mark 4:41", dir="warm moral, straight to the child; slow and clear on the last sentence",
         pre=0.5, post=0.3),
    line("mi_33", "narrator", "就像那四个好朋友，我们也可以把需要帮助的人，带到耶稣面前。",
         "And just like the four good friends, we can bring people who need help to Jesus too.",
         "Mark 2:3-5", dir="encouraging, a smile; lift on 四个好朋友 / 'four good friends'", pre=0.3, post=0.4),
    pause(1.0),
]
