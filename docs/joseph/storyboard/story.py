"""Joseph — the play, as beats relative to each other (docs/joseph/CONTRACT.md §5).

`tools/story/build_timeline.py joseph` turns this into assets/joseph/timeline.json, placing every line by the real
voice durations. Helpers: shot / line / act / fx / sfx / music / prop / pause (same as every pack).
Marks are art-width units on the page (x right, z toward the viewer); the set's marks are in CONTRACT.md §6.
`face` takes an actor id, "viewer", or a set node name ("pit", "throne", "granary").

Lines are spoken paraphrases of Genesis 37 and 39-46 for ages 4-10: short sentences, everyday words, people talking
to each other, the narrator only bridging. Child-friendly: no blood on the coat, no Potiphar's wife, no baker's
death, no silver-cup test; the brothers are jealous and then truly sorry. The four dreams are shown as floating
picture clouds (set props), so a child can colour the cows and the sheaves.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py

ID = "joseph"
CAST = ["joseph", "jacob", "brother", "pharaoh"]
SET = "twolands"

# Canaan, the left half of the page
JACOB_HOME = (-0.46, -0.20)   # in front of the tent
JOSEPH_HOME = (-0.345, -0.167)   # 0.12 from Jacob: give_coat is fitted to 0.12
BRO_HOME = (-0.16, -0.12)
PIT = (-0.34, 0.08)           # inside the dry well
PIT_EDGE = (-0.156, 0.075)    # the brother at the well's rim, 0.11 from Joseph at (-0.26, 0.04): grab_coat is fitted to 0.11
# Egypt, the right half
THRONE = (0.38, -0.30)        # Pharaoh, in front of his throne
COURT = (0.278, -0.236)       # whoever stands before Pharaoh, 0.12 from the throne mark: crown_him is fitted to 0.12
CELL = (0.10, -0.06)          # inside the prison cell
GRANARY = (0.42, 0.04)        # Joseph by the grain stores
BRO_EGYPT = (0.265, -0.045)   # the brother before the governor, 0.112 from GOV: lift_up / hug are fitted to 0.11-0.12.
GOV = (0.375, -0.065)         # Joseph as governor meeting his brother. Both marks sit 0.2 behind the sacks (round 2:
                              # the brother's fall pushed his legs into them) and on a diagonal, Joseph further back, so
                              # Joseph facing his brother turns toward the camera
MEET = (0.02, 0.12)           # the reunion, centre front
MEET_JACOB = (-0.097, 0.147)  # 0.12 from MEET on a diagonal (Jacob nearer the camera): Joseph faces 3/4 toward the camera
JACOB_S11 = (-0.29, -0.17)    # S11 opens with Jacob part of the way along (a cut), so walk_old stays <= 1.6x
JACOB_S03 = (-0.32, -0.25)    # S03: Jacob in front of the tent, clear of the olive (round 2: he wept behind its crown)
BRO_END = (0.135, 0.15)       # the brother beside the family at the end, 0.12 from Joseph at MEET
EXIT_W = (-0.58, 0.10)        # Joseph led away past the caravan to the left page edge (then hidden)
CARRY_A = (0.40, 0.06)        # Joseph's jar-carrying walk across the front of Egypt, A -> B
CARRY_B = (0.04, 0.08)
COURT_FAR = (0.20, -0.24)     # Joseph before Pharaoh in S06, 0.19 from the throne mark: two people, clear spacing
PARK = (0.80, 0.30)           # off the page
PARK_L = (-0.80, 0.30)
# Off-stage actors are HIDDEN (prop("<actor>", show=False), as Esther does) and parked at PARK_L; nobody waits in view
# off the page. The director's "all" camera target averages every actor, hidden or not, so a shot with someone parked
# aims at an actor or a set node instead (2026-11-15 review: S07 aimed at Canaan, Jacob floated beside the page).

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    # Pharaoh is hidden until his act (S05) and again S08-S11, so "all" frames only the people in the scene
    shot("S01", "一件彩衣", "A coat of many colours", "fixed", "all", dist=0.6, height=0.3, yawDeg=-8,
         desc="The family in Canaan: tents and sheep. Old Jacob holds out a wonderful striped coat; young Joseph puts "
              "it on and twirls. His big brother watches, arms folded."),
    music("home"),
    act("jacob", "idle", to=JACOB_HOME, face="joseph"),
    act("joseph", "idle", to=JOSEPH_HOME, face="jacob"),
    act("brother", "fold_arms", to=BRO_HOME, face="joseph"),
    act("pharaoh", "idle", to=THRONE, face="viewer"), prop("pharaoh", show=False),
    prop("joseph/coat", show=False), prop("joseph/nemes", show=False), prop("joseph/collar", show=False),
    prop("twolands/caravan", show=False), prop("twolands/cell", show=False), prop("twolands/grainPiles", show=False),
    prop("twolands/sacks", show=False),
    prop("twolands/dreamSheaves", show=False), prop("twolands/dreamSheaves2", show=False),
    prop("twolands/dreamStars", show=False),
    prop("twolands/dreamCows", show=False), prop("twolands/dreamGrain", show=False),
    sfx("sheep_baa", dt=0.6),
    pause(1.2),
    line("js_01", "narrator", "很久以前，雅各有十二个儿子。他最疼的，是小儿子约瑟。",
         "Long ago, Jacob had twelve sons. And the one he loved most of all was young Joseph.",
         "Genesis 37:3", dir="storyteller opening, warm; fond on 最疼的 / 'loved most of all'", post=0.3),
    act("jacob", "give_coat", face="joseph"),
    prop("joseph/coat", show=True, dt=1.2), fx("sparkle", "joseph.chest", dur=1.4, dt=1.2), sfx("sparkle", dt=1.2),
    line("js_02", "jacob", "约瑟，来！爸爸给你做了一件新衣服，你看——五颜六色的！",
         "Joseph, come here! Father has made you a new coat. Look... all the colours of the rainbow!",
         "Genesis 37:3", dir="an old, loving father, a little husky, delighted with his present; a happy chuckle",
         pre=0.3, post=0.3),
    act("joseph", "twirl", face="viewer", dt=-1.0),
    line("js_03", "joseph", "哇，太漂亮了！谢谢爸爸！",
         "Wow, it's beautiful! Thank you, Father!",
         "Genesis 37:3", dir="a bright boy of seventeen, thrilled, a laugh in the voice", pre=0.2, post=0.3),
    act("brother", "grumble", face="joseph"),
    line("js_04", "brother", "哼，又是他。爸爸什么好东西都给他！",
         "Hmph. Him again. Father gives him all the good things!",
         "Genesis 37:4", dir="muttering to himself, jealous, sour; a real 哼", pre=0.3, post=0.4),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "奇怪的梦", "Strange dreams", "fixed", "joseph", dist=0.6, height=0.22, yawDeg=20,
         desc="Joseph tells his dreams, acting them out. A picture cloud appears over his head: eleven sheaves bowing "
              "to one, then the sun, moon and eleven stars. The brother's ears go red."),
    music("dream"),
    act("joseph", "tell_dream", face="brother"),
    prop("twolands/dreamSheaves", show=True, dt=0.8), fx("dream_cloud", "twolands.dreamSheaves", dur=9.0, dt=0.8),
    sfx("harp_gliss", dt=0.8),
    line("js_05", "joseph", "哥哥，我做了一个梦！我们在田里捆麦子，你们的麦捆，都向我的麦捆鞠躬呢！",
         "Brothers, I had a dream! We were tying up bundles of wheat in the field, and all your bundles bowed down to mine!",
         "Genesis 37:5-7", dir="eager, innocent, no idea he is annoying anyone; quick and bright", pre=1.0, post=0.3),
    act("brother", "angry_point", face="joseph"),
    fx("steam", "brother.head", dur=1.6, dt=0.2),
    line("js_06", "brother", "什么？你是说，我们要向你下拜？做梦！",
         "What? You mean WE are going to bow down to YOU? Dream on!",
         "Genesis 37:8", dir="outraged, voice rising; snaps 做梦 / 'Dream on'", pre=0.3, post=0.3),
    prop("twolands/dreamSheaves", show=False), prop("twolands/dreamStars", show=True),
    fx("dream_cloud", "twolands.dreamStars", dur=6.0), sfx("harp_gliss"),
    line("js_07", "narrator", "约瑟又梦见太阳、月亮和十一颗星星，都向他下拜。哥哥们更生气了。",
         "Then Joseph dreamed that the sun, the moon and eleven stars all bowed down to him. His brothers were angrier than ever.",
         "Genesis 37:9-11", dir="a little amused, then lower and worried on 更生气了 / 'angrier than ever'", pre=0.4, post=0.4),
    prop("twolands/dreamStars", show=False, dt=-0.2),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "被卖到远方", "Sold far away", "fixed", "pit", dist=0.56, height=0.30, yawDeg=12,
         desc="Out in the fields the brother pulls off Joseph's coat and lowers him into a dry well. A camel caravan "
              "comes by; silver coins change hands; Joseph is led away. Back home, Jacob weeps."),
    music("betrayal"),
    act("jacob", "idle", to=JACOB_S03, face="viewer", snap=True),          # cut: in view for js_11
    fx("tension_dim", "stage", dur=26.0),
    act("joseph", "walk", to=(-0.26, 0.04), face="brother"),
    act("brother", "walk", to=PIT_EDGE, face="joseph", dt=0.2),
    act("brother", "grab_coat", face="joseph", dt=2.6),
    prop("joseph/coat", show=False, dt=3.4),
    act("joseph", "walk", to=PIT, face="brother", dt=3.5),               # walk him in first, then in_pit from the spot
    act("joseph", "in_pit", face="viewer", dt=4.3),
    line("js_08", "narrator", "有一天，哥哥们抢走了约瑟的彩衣，把他丢进一个干井里。",
         "One day, the brothers grabbed Joseph's beautiful coat and dropped him into a dry well.",
         "Genesis 37:23-24", dir="serious but gentle, not frightening; slower", pre=2.8, post=0.3),
    act("brother", "fold_arms", face="joseph"),                           # turns his back on the plea
    line("js_09", "joseph", "哥哥！别丢下我！",
         "Brothers! Please don't leave me!",
         "Genesis 42:21", dir="calling up from the well, frightened and pleading; short", pre=0.2, post=0.4),
    prop("twolands/caravan", show=True), sfx("camel_grunt", dt=0.2),
    act("brother", "take_coins", face="viewer", dt=1.0),
    fx("coins_spray", "brother.handR", dur=1.4, dt=1.6), sfx("coins", dt=1.6),
    line("js_10", "narrator", "这时来了一队骆驼商人。哥哥们收了二十块银子，就把约瑟卖了。商人把他带去了很远很远的埃及。",
         "Just then some traders came by with their camels. The brothers took twenty pieces of silver and sold Joseph. "
         "The traders took him far, far away, to Egypt.",
         "Genesis 37:25-28", dir="matter-of-fact, sad underneath; long and far on 很远很远 / 'far, far away'", pre=1.0, post=0.3),
    # led away: he gets up out of the well (a slow 0.8 s blend from the sitting pose) and walks, head down, past the
    # camel to the left page edge while the narrator says "took him far away"; then he and the caravan are gone
    act("joseph", "walk_sad", to=EXIT_W, face="viewer", blend=0.8, dt=-5.0),
    prop("joseph", show=False, dt=0.2), prop("twolands/caravan", show=False, dt=0.2),
    act("joseph", "idle", to=PARK_L, face="viewer", snap=True, dt=0.25),
    act("jacob", "weep", face="viewer"),
    line("js_11", "jacob", "我的约瑟……我的孩子不见了……",
         "My Joseph... my boy is gone...",
         "Genesis 37:34-35", dir="an old man's quiet weeping; broken, very soft; not wailing", pre=0.5, post=0.8),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "上帝与他同在", "God was with him", "follow", "joseph", dist=0.55, height=0.22, yawDeg=10,
         desc="Egypt. Joseph works hard carrying jars; then, though he did nothing wrong, he sits in a prison cell. "
              "A warm light stays on him."),
    music("prison"),
    prop("brother", show=False), prop("jacob", show=False),
    act("brother", "idle", to=PARK_L, face="viewer", snap=True),
    act("jacob", "idle", to=PARK_L, face="viewer", snap=True),
    prop("joseph", show=True), prop("joseph/coat", show=False), prop("joseph/nemes", show=False),
    prop("joseph/collar", show=False),
    act("joseph", "carry_work", to=CARRY_A, face="viewer", snap=True),   # a servant: carries a water jar across Egypt
    act("joseph", "carry_work", to=CARRY_B, face="viewer", dt=0.1),     # 0.36 at 0.076/s = 4.7 s of work on camera
    line("js_12", "narrator", "在埃及，约瑟做了仆人。他干活又认真又诚实。可是有人冤枉了他，把他关进了监牢。",
         "In Egypt, Joseph became a servant. He worked hard and he was honest. But someone told a lie about him, "
         "and he was put in prison.",
         "Genesis 39:1-20", dir="steady; proud of him on 又认真又诚实; a sigh on 关进了监牢 / 'put in prison'", pre=0.6, post=0.2),
    prop("twolands/cell", show=True, dt=-2.2), sfx("cell_door", dt=-2.2),
    act("joseph", "walk", to=CELL, face="viewer", dt=-4.0),
    act("joseph", "sit_cell", face="viewer", dt=-2.4),
    act("joseph", "ask_gently", face="viewer", blend=0.8, dt=0.3),      # he gets up and prays, hands clasped, soft nods
    fx("prayer_glow", "joseph.chest", dur=12.0, dt=0.3),
    line("js_13", "joseph", "上帝啊，我没有做错事。可我知道，你还和我在一起。",
         "Dear God, I didn't do anything wrong. But I know You are still with me.",
         "Genesis 39:21-23", dir="quiet, a little older now; sad but trusting; no self-pity", pre=0.6, post=0.3),
    fx("sparkle", "joseph.head", dur=1.4, dt=0.6),
    line("js_14", "narrator", "没错。就算在监牢里，上帝也和约瑟在一起。",
         "And He was. Even in prison, God was with Joseph.",
         "Genesis 39:21", dir="warm and sure, like a hand on the shoulder", pre=0.2, post=0.6),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "法老的怪梦", "Pharaoh's strange dream", "fixed", "pharaoh", dist=0.58, height=0.2, yawDeg=-20,
         desc="Night in the palace. Pharaoh nods off on his feet; a picture cloud shows seven fat cows and seven thin "
              "cows, then seven fat ears of grain and seven thin ones. He wakes with a jump."),
    music("pharaoh"), prop("pharaoh", show=True),
    fx("night", "stage", dur=20.0),
    act("pharaoh", "doze", face="viewer"),
    act("joseph", "sit_cell", face="viewer", dt=0.2),                    # night in the cell: he sits down to sleep
    fx("zzz", "pharaoh.head", dur=5.0, dt=0.4),
    prop("twolands/dreamCows", show=True, dt=1.4), fx("dream_cloud", "twolands.dreamCows", dur=9.0, dt=1.4),
    sfx("harp_gliss", dt=1.4), sfx("moo", dt=3.0),
    line("js_15", "narrator", "一天夜里，埃及的国王法老做了个怪梦：七头肥肥的牛从河里上来，接着七头瘦瘦的牛，把肥牛吃掉了！",
         "One night Pharaoh, the king of Egypt, had a strange dream. Seven fat cows came up out of the river. Then came "
         "seven skinny cows... and they ate the fat cows right up!",
         "Genesis 41:1-4", dir="spooky-funny bedtime voice; round on 肥肥的 / 'fat', thin on 瘦瘦的 / 'skinny'; a gasp on 吃掉了",
         pre=1.8, post=0.2),
    prop("twolands/dreamCows", show=False), prop("twolands/dreamGrain", show=True),
    fx("dream_cloud", "twolands.dreamGrain", dur=2.6), sfx("harp_gliss"),   # gone before Pharaoh wakes and speaks
    pause(2.6),
    prop("twolands/dreamGrain", show=False),
    act("pharaoh", "wake_jump", face="viewer"),
    line("js_16", "pharaoh", "啊！牛吃牛？麦穗吃麦穗？这是什么意思？谁能告诉我！",
         "Aah! Cows eating cows? Grain eating grain? What does it mean? Somebody tell me!",
         "Genesis 41:7-8", dir="a grand king in a panic, comic; high and flustered; bossy on the last sentence", pre=0.3, post=0.4),
    # S06 --------------------------------------------------------------------------------------------------------
    # camera aim: the sacks node (hidden here) lies in front of the pair, so the fixed camera centres Joseph and Pharaoh
    # side by side with the dream panel above them (aiming at either actor put the pair at the frame edge)
    shot("S06", "上帝会解梦", "God knows what dreams mean", "fixed", "sacks", dist=0.5, height=0.12, yawDeg=6,
         desc="Morning. Joseph is brought from the cell to stand before Pharaoh. He bows, points up to heaven, and explains."),
    music("reveal"),
    prop("twolands/cell", show=False), sfx("cell_door"),
    act("joseph", "walk", to=COURT_FAR, face="pharaoh"),
    act("pharaoh", "lean_ask", face="joseph", dt=1.6),
    line("js_17", "pharaoh", "听说你会解梦？",
         "I hear you can tell what dreams mean?",
         "Genesis 41:15", dir="hopeful, leaning forward; a king who has not slept", pre=2.4, post=0.3),
    act("joseph", "bow_point_up", face="pharaoh"),
    line("js_18", "joseph", "王啊，我不会。可是上帝会，他会告诉您。",
         "No, Your Majesty, I can't. But God can, and He will tell you.",
         "Genesis 41:16", dir="humble and calm; clear and sure on 上帝会 / 'God can'", pre=0.3, post=0.4),
    act("joseph", "explain", face="viewer"),                              # explains to the king AND the child
    prop("twolands/dreamCows", show=True, dt=0.6), fx("dream_cloud", "twolands.dreamCows", dur=10.0, dt=0.6),
    line("js_19", "joseph", "七头肥牛，是七个大丰收的年头。七头瘦牛，是七个闹饥荒的年头。请您趁丰收的时候，把粮食存起来！",
         "The seven fat cows are seven years with plenty of food. The seven skinny cows are seven years with no food at "
         "all. So store up grain in the good years, while you can!",
         "Genesis 41:25-36", dir="clear, like a kind teacher counting on his fingers; urgent and helpful at the end",
         pre=0.6, post=0.4),
    prop("twolands/dreamCows", show=False, dt=-0.3),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "约瑟当宰相", "Joseph the governor", "follow", "joseph", dist=0.62, height=0.24, yawDeg=25,
         desc="Pharaoh claps, takes off his own collar and sets a striped head-cloth on Joseph. Joseph stands tall: "
              "the head-cloth wears the colours of his lost coat."),
    music("plenty"),
    act("joseph", "walk", to=COURT, face="pharaoh"),                     # one step in: crown_him is fitted to 0.12
    act("pharaoh", "delighted", face="joseph"),
    line("js_20", "pharaoh", "太聪明了！上帝和你在一起。从今天起，你来管理整个埃及！",
         "How wise! God is with you. From today, you shall be in charge of all Egypt!",
         "Genesis 41:38-41", dir="overjoyed, booming, generous; arms wide on the last sentence", pre=0.4, post=0.3),
    act("pharaoh", "crown_him", face="joseph"),
    prop("joseph/nemes", show=True, dt=1.2), prop("joseph/collar", show=True, dt=1.2),
    fx("golden_rays", "joseph.root", dur=5.0, dt=1.2), sfx("fanfare", dt=1.0),
    act("joseph", "stand_proud", face="viewer", dt=1.6),
    pause(3.6),
    act("joseph", "walk", to=GRANARY, face="viewer"),
    prop("twolands/grainPiles", show=True, dt=2.0), fx("sparkle", "twolands.granary", dur=1.6, dt=2.0),
    line("js_21", "narrator", "丰收的七年里，约瑟把粮食存得满满的，像海边的沙那么多。",
         "For seven good years Joseph stored up grain, heaps and heaps of it, like the sand on the seashore.",
         "Genesis 41:47-49", dir="busy and bright; big on 满满的 / 'heaps and heaps'", pre=1.6, post=0.4),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "饥荒来了", "The hungry years", "follow", "brother", dist=0.72, height=0.24, yawDeg=20,
         desc="The land turns dusty. Far away in Canaan the food runs out, and Jacob sends the brothers to Egypt to buy grain."),
    music("famine"),
    fx("famine_haze", "stage", dur=14.0), sfx("wind_desert"),
    prop("jacob", show=True), prop("brother", show=True), prop("pharaoh", show=False),   # the governor's scenes
    act("jacob", "idle", to=JACOB_HOME, face="brother", snap=True),
    act("brother", "idle", to=BRO_HOME, face="jacob", snap=True),
    line("js_22", "narrator", "后来，饥荒真的来了，到处都没有饭吃。只有埃及有粮食。雅各就叫儿子们去埃及买粮。",
         "Then the hungry years really came. There was no food anywhere... except in Egypt. So Jacob sent his sons to "
         "Egypt to buy grain.",
         "Genesis 41:54-42:3", dir="dry and tired, then a lift of hope on 只有埃及有粮食 / 'except in Egypt'", pre=0.6, post=0.3),
    act("jacob", "talk", face="brother", dt=-5.0),                        # "go to Egypt and buy grain"
    act("brother", "walk", to=BRO_EGYPT, face="joseph", dt=-3.0),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "梦成真了", "The dream comes true", "fixed", "sacks", dist=0.5, height=0.18, yawDeg=4,
         desc="The brother kneels and bows low before the governor of Egypt. He has no idea who it is. Over Joseph's "
              "head the old dream flickers: the sheaves bowing."),
    music("brothers"),
    act("joseph", "walk", to=GOV, face="brother"),
    act("brother", "bow_low", face="joseph", dt=1.0),
    prop("twolands/sacks", show=True, dt=1.0),
    line("js_23", "brother", "大人，求求您，卖一点粮食给我们吧。我们一家人都快饿坏了。",
         "My lord, please, sell us a little grain. Our whole family is so hungry.",
         "Genesis 42:6-7", dir="humble, tired, nothing left of the old sneer; head down", pre=1.8, post=0.4),
    act("joseph", "recognise", face="brother"),
    prop("twolands/dreamSheaves2", show=True), fx("dream_cloud", "twolands.dreamSheaves2", dur=6.0),
    sfx("harp_gliss"),
    line("js_24", "narrator", "约瑟一眼就认出了哥哥们。可他们认不出约瑟。约瑟想起了小时候做的那个梦。",
         "Joseph knew his brothers at once. But they did not know him. And Joseph remembered the dream he had as a boy.",
         "Genesis 42:8-9", dir="hushed, a secret shared with the child; wonder on 那个梦 / 'the dream'", pre=0.4, post=0.4),
    prop("twolands/dreamSheaves2", show=False, dt=-0.2),
    # S10 --------------------------------------------------------------------------------------------------------
    # lower camera (the reveal throws the head back); during the talking the two "cheat" toward the camera (they face
    # the sacks node in front of them), so faces read; the touching clips (lift, hug) face each other
    shot("S10", "我就是约瑟", "I am Joseph", "fixed", "joseph", dist=0.5, height=0.12, yawDeg=0,
         desc="Joseph cannot hold it in. He pulls off the head-cloth: it is him. The brother falls back, terrified, "
              "and says sorry. Joseph lifts him up and hugs him."),
    music("iam"),
    act("joseph", "ask_gently", face="sacks"),
    line("js_25", "joseph", "你们的爸爸……他还好吗？",
         "Your father... is he well?",
         "Genesis 43:27", dir="trying to sound like a stranger, but the voice shakes; very soft", pre=0.4, post=0.6),
    act("joseph", "reveal", face="sacks"),
    prop("joseph/nemes", show=False, dt=0.9),
    line("js_26", "joseph", "哥哥，是我呀——我就是约瑟！",
         "Brothers, it's me... I am Joseph!",
         "Genesis 45:3-4", dir="the dam breaks: tears and joy at once; the name bursts out", pre=0.8, post=0.3),
    act("brother", "fall_back_scared", face="viewer", dt=-1.0),           # on the name; lands facing the camera
    fx("sweat", "brother.head", dur=1.4, dt=-0.8),
    act("joseph", "ask_gently", face="brother", dt=0.4),                  # leans toward him while he says sorry
    line("js_27", "brother", "约……约瑟？对不起！我们对你做了那么坏的事……",
         "J-Joseph? I'm sorry! We did such a terrible thing to you...",
         "Genesis 45:3; 50:17", dir="shaking, ashamed, close to tears; the apology is real", pre=0.3, post=0.4),
    act("joseph", "lift_up", face="brother", dt=-2.0),                    # takes his arms on the end of the apology
    act("brother", "stand_up", face="joseph", dt=-1.2),
    fx("heart_glow", "joseph.chest", dur=6.0, dt=-1.0, to="brother.chest"),
    act("joseph", "talk", face="brother", dt=1.0), act("brother", "idle", face="joseph", dt=1.0),   # no frozen pose
    line("js_28", "joseph", "别怕，别难过。你们本来想害我，可是上帝把坏事变成了好事，好救许多人的命。",
         "Don't be afraid, and don't be sad. You meant to hurt me, but God turned it into something good, to save many lives.",
         "Genesis 45:5-8; 50:20", dir="the heart of the story: gentle, completely forgiving, steady; slow on 把坏事变成了好事",
         pre=0.8, post=0.5),
    act("joseph", "hug", face="brother", dt=-3.6), act("brother", "hug", face="joseph", dt=-3.6),   # on 上帝把坏事变成了好事 (0.115 apart)
    sfx("soft_chime"),
    pause(1.4),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "一家团圆", "Together again", "follow", "jacob", dist=0.66, height=0.2, yawDeg=0,
         desc="Old Jacob comes all the way to Egypt on his stick. Joseph runs to him. A long hug."),
    music("reunion"),
    act("jacob", "idle", to=JACOB_S11, face="joseph", snap=True),        # (head-cloth stays off: his face in the hug)        # cut: already on his way (walk_old <= 1.6x)
    act("brother", "walk", to=(0.24, 0.12), face="jacob"),               # steps aside, out of Joseph's run
    act("joseph", "idle", face="jacob", dt=0.4),
    act("jacob", "walk_old", to=MEET_JACOB, face="joseph"),
    line("js_29", "narrator", "约瑟把爸爸和全家人都接到了埃及。",
         "Then Joseph brought his father and the whole family to live in Egypt.",
         "Genesis 46:5-7, 46:29", dir="glad, a little out of breath with happiness", pre=1.2, post=0.2),
    act("joseph", "run", to=MEET, face="jacob", dt=-0.6),
    act("joseph", "hug", face="jacob"), act("jacob", "hug", face="joseph"),
    line("js_30", "jacob", "约瑟！我的孩子……我又看见你了！",
         "Joseph! My boy... I can see you again!",
         "Genesis 46:30", dir="happy tears, laughing and crying together; an old voice full of light", pre=0.6, post=0.8),
    fx("golden_rays", "jacob.root", dur=6.0, dt=-2.0),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "坏事变好事", "God turns it to good", "fixed", "all", dist=0.78, height=0.36, yawDeg=4,
         desc="The family faces the child: Jacob, Joseph and his brother wave. Pharaoh waves from his throne."),
    music("finale"), prop("pharaoh", show=True), prop("joseph/nemes", show=True),
    act("joseph", "wave", face="viewer"),
    act("jacob", "idle", face="viewer"), act("brother", "walk", to=BRO_END, face="viewer"),
    act("brother", "wave", face="viewer", dt=1.6),
    act("pharaoh", "wave", face="viewer"),
    fx("confetti", "stage", dur=4.0, dt=0.4),
    line("js_31", "narrator", "在井里，在监牢里，在王宫里，上帝一直和约瑟在一起。遇到难过的事，你也不是一个人——上帝能把坏事变成好事。",
         "In the well, in the prison, in the palace, God was with Joseph all the way. When sad things happen to you, "
         "you are not alone either. God can turn bad things into good.",
         "Genesis 39:2, 39:21, 50:20; Romans 8:28", dir="warm moral, speaking right to the child; count the three places "
                                                      "gently; smile on the last sentence", pre=0.6, post=2.0),
]
