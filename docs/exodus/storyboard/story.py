"""Exodus — the play, as beats relative to each other (docs/exodus/CONTRACT.md §5).

`tools/story/build_timeline.py exodus` turns this into assets/exodus/timeline.json, placing every line by the real
voice durations. Same helpers as Ruth: shot / line / act / fx / sfx / music / prop / pause.
Marks are art-width units on the page (x right, z toward the viewer; the set's marks are in CONTRACT.md §6).

Lines are spoken paraphrases of Exodus 1-15 for ages 4-10, written to be *said*, not read: short sentences, little
words people really use (呀、啦、呢、哎呀、咦、哇), characters talking to each other rather than a narrator explaining.
`dir` is the acting note for the voice. Child-friendly: no killing of the Egyptian, a comic plague montage, the last
plague is one gentle line, the chariots "could not follow any more" and Pharaoh is left soaked on the shore.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py

ID = "exodus"
CAST = ["moses", "pharaoh", "miriam"]
SET = "egypt"

# stage marks (CONTRACT.md §6)
PH_PALACE = (-0.36, -0.30)     # Pharaoh in front of his dais
PH_STEP = (-0.18, -0.24)       # Pharaoh's first chariot leg (keeps clear of the brick yard)
PH_CHASE = (-0.10, 0.05)       # Pharaoh at the front, behind the people
PH_SEA = (0.24, 0.07)          # his chariot reaches into the sea-bed
PH_SOGGY = (0.12, 0.03)        # washed back to the west beach
MI_BRICK = (-0.20, -0.06)      # Miriam at the edge of the brick yard
MI_ASIDE = (-0.18, 0.16)       # waypoint round the brick yard
MI_OFF = (-0.66, 0.19)         # off the left edge until S05
MI_DOOR = (-0.02, -0.32)       # in front of the Israelite houses
MO_IN = (0.64, -0.30)          # off the right edge, the wilderness path behind the sea
MO_PATH = (0.34, -0.30)
MO_BUSH = (0.04, -0.28)        # facing the bush at (0.14, -0.36)
MO_PALACE = (-0.18, -0.22)     # Moses before Pharaoh
MO_DOOR = (0.08, -0.30)
MO_SHORE = (0.12, 0.08)        # west beach
MI_SHORE = (0.02, 0.13)
MO_MID = (0.30, 0.07)          # the dry path between the walls
MI_MID = (0.27, 0.09)        # clear of the front water wall (inner face z ~0.13)
MO_FAR = (0.46, 0.04)          # the far shore
MI_FAR = (0.53, 0.12)

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "埃及的奴隶", "Slaves in Egypt", "orbit", "all", dist=0.9, height=0.40, yawDeg=-30,
         desc="Slow orbit over the page in hot hazy light: the pyramids, the palace, the brick yard full of workers."),
    music("slavery"),
    fx("dust_road", "stage", dur=8.0, dt=0.5),
    act("moses", "idle", to=MO_IN, face="viewer"),                      # parked off-page until S02
    act("pharaoh", "smug", to=PH_PALACE, face="viewer"),
    act("miriam", "carry_brick", to=MI_BRICK, face="viewer"),
    prop("moses/staff", show=True), prop("pharaoh/chariot", show=False),
    prop("miriam/tambourine", show=False), prop("egypt/doorMarks", show=False), prop("egypt/crowdShore", show=False),
    prop("egypt/crowdFar", show=False), prop("egypt/crowdWest", show=True), prop("egypt/looseWheel", show=False),
    prop("pharaoh/wheelL", show=True),
    sfx("bricks", dt=0.8),
    pause(1.4),
    line("ex_01", "narrator", "很久很久以前，以色列人住在埃及。埃及的王叫法老，他让以色列人做奴隶，天天做砖、搬砖，累得腰都直不起来。",
         "Long, long ago, God's people, the Israelites, lived in Egypt. The king of Egypt, Pharaoh, made them slaves. "
         "Every day they made bricks and carried bricks, until their backs ached.",
         "Exodus 1:8-14", dir="storyteller opening, slow and a little heavy; real weight on 累得腰都直不起来 / 'backs ached'",
         post=0.3),
    act("pharaoh", "point_order", face="miriam"),
    line("ex_02", "pharaoh", "快点！快点！今天的砖，一块都不许少！哼！",
         "Faster! Faster! Not one brick less today! Hmph!",
         "Exodus 5:6-8, 5:18", dir="pompous, bossy, loving the sound of his own voice; a snooty Hmph at the end",
         pre=0.3, post=0.4),
    act("pharaoh", "smug", face="viewer"),
    act("miriam", "pray_stand", face="viewer"),
    sfx("sigh_crowd", dt=0.2),
    line("ex_03", "miriam", "上帝啊……你听见我们在哭吗？求你救救我们吧！",
         "Oh God... can you hear us crying? Please, please save us!",
         "Exodus 2:23-24", dir="tired, quiet, from the heart; a breath before 求你 / 'please'; not melodramatic",
         pre=0.8, post=0.6),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "牧羊人摩西", "Moses the shepherd", "follow", "moses", dist=0.72, height=0.22, yawDeg=-25,
         desc="Dusk in the wilderness behind the sea: an old shepherd with a white beard walks in with his staff."),
    music("desert"),
    fx("sunset_glow", "stage", dur=44.0),
    sfx("sheep_bells", dt=0.3),
    act("miriam", "walk", to=MI_ASIDE, face="viewer"),                  # she leaves the page while Moses is in the wilderness
    act("miriam", "walk", to=MI_OFF, face="viewer", dt=2.0),           # (round the brick yard, off the left edge)
    act("moses", "walk_staff", to=MO_BUSH, face="viewer"),                # 0.60 at 0.066 u/s: ~9 s, arrives before S03
    line("ex_04", "narrator", "这时候，在很远很远的旷野里，有个放羊的老爷爷，名叫摩西。他小时候在埃及王宫里长大，现在胡子都白啦。",
         "Far away in the wilderness lived an old shepherd named Moses. He grew up in Pharaoh's palace "
         "when he was young, but now his beard was white.",
         "Exodus 2:10, 3:1, 7:7", dir="gentle, a small smile on 胡子都白啦 / 'his beard was white'", pre=1.0, post=0.2),
    pause(1.2),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "烧不坏的荆棘", "The bush that doesn't burn", "fixed", "moses", dist=0.62, height=0.18, yawDeg=30,
         desc="A thorn bush blazes with white-gold fire but nothing burns up. Moses stops, amazed."),
    music("bush"),
    fx("bush_fire", "egypt.bushFlame", dur=58.0, dt=-1.5),
    sfx("bush_whoosh", dt=-1.5),
    act("moses", "look_curious", face="egypt.bush"),
    line("ex_05", "moses", "咦？那丛荆棘着火了……怎么烧不坏呢？我过去看看。",
         "Hm? That bush is on fire... but it isn't burning up! I'll go and have a look.",
         "Exodus 3:2-3", dir="an old man's wonder; slow thinking 咦 / 'hm' first; quieter on 我过去看看", pre=0.6, post=0.5),
    act("moses", "walk_staff", to=(0.07, -0.30), face="egypt.bush"),
    line("ex_06", "god", "摩西，摩西！", "Moses! Moses!",
         "Exodus 3:4", dir="calm, deep, kind; not loud; like a father calling a child by name; a little space between the two",
         pre=0.6, post=0.4),
    act("moses", "startle", face="egypt.bush", dt=-1.2),
    act("moses", "kneel_bow", face="egypt.bush"),
    line("ex_07", "moses", "我……我在这里！", "I... I'm here!",
         "Exodus 3:4", dir="startled, then humble and soft", pre=0.3, post=0.6),
    fx("prayer_glow", "moses.chest", dur=6.0),
    line("ex_08", "god", "我看见我的百姓在埃及受苦，也听见了他们的哭声。现在你去见法老，把他们带出埃及吧。",
         "I have seen my people suffering in Egypt, and I have heard them crying. "
         "Now go to Pharaoh, and bring my people out of Egypt.",
         "Exodus 3:7-10", dir="steady, warm, compassionate on 听见了他们的哭声 / 'heard them crying'; firm and kind on the "
                            "sending", pre=0.4, post=0.6),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "我不行呀", "Who, me?", "fixed", "moses", dist=0.56, height=0.16, yawDeg=55,   # side-on: his face, the bush and the snake
         desc="Moses points at himself, shaking his head. His staff turns into a snake; he hops back; it turns back."),
    act("moses", "who_me", face="egypt.bush"),
    line("ex_09", "moses", "我？我算什么呀……而且我嘴笨，一说话就……就结结巴巴的。",
         "Me? Who am I?... And I'm no good at talking. When I speak, I... I get all mixed up.",
         "Exodus 3:11, 4:10", dir="nervous and shy, a little stammer on 就……就 / 'I... I'; a self-conscious laugh-sigh",
         pre=0.4, post=0.5),
    line("ex_10", "god", "你手里拿的是什么？把它丢在地上。",
         "What is that in your hand? Throw it on the ground.",
         "Exodus 4:2-3", dir="gentle, almost amused; patient", pre=0.3, post=0.3),
    act("moses", "throw_staff", face="egypt.bush"),
    prop("moses/staff", show=False, dt=0.55),
    fx("snake", "moses.handR", dur=5.6, dt=0.55),
    sfx("hiss", dt=0.9),
    act("moses", "jump_back", face="egypt.bush", dt=1.1),
    line("ex_11", "moses", "哇！蛇！蛇！", "Whoa! A snake! A snake!",
         "Exodus 4:3", dir="comic fright, quick and high, a squeak in it; the second 蛇 / 'snake' even higher", pre=0.5,
         post=0.3),
    line("ex_12", "god", "别怕，抓住它的尾巴。我会和你同在，教你该说什么话。",
         "Don't be afraid. Take it by the tail. I will be with you, and I will teach you what to say.",
         "Exodus 4:4, 4:12", dir="kind, reassuring, a smile in the voice; slower on 我会和你同在 / 'I will be with you'",
         pre=0.3, post=0.3),
    act("moses", "grab_tail", face="egypt.bush"),
    prop("moses/staff", show=True, dt=0.9),
    sfx("sparkle", dt=0.9),
    act("moses", "nod_brave", face="egypt.bush", dt=1.6),
    line("ex_13", "moses", "好……我去！", "All right... I'll go!",
         "Exodus 4:18-20", dir="a deep breath, then decided and brave; a little smile", pre=1.8, post=0.6),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "让我的百姓走", "Let my people go!", "fixed", "all", dist=0.66, height=0.22, yawDeg=20,
         desc="Pharaoh's palace in bright gold. Moses walks up with his staff and speaks out; Pharaoh laughs."),
    music("palace"),
    act("moses", "walk_staff", to=MO_PALACE, face="pharaoh"),
    act("pharaoh", "smug", face="moses"),
    act("miriam", "walk", to=(-0.10, -0.06), face="pharaoh", dt=0.5),   # path from the left edge stays clear of the brick yard
    pause(3.4),
    act("moses", "staff_raise", face="pharaoh"),
    line("ex_14", "moses", "法老！上帝说：让我的百姓走！",
         "Pharaoh! This is what God says: Let my people go!",
         "Exodus 5:1", dir="brave and clear, a strong voice now (the shy man is gone); a beat before 让我的百姓走 / "
                         "'Let my people go'", pre=0.6, post=0.4),
    act("pharaoh", "laugh", face="moses"),
    line("ex_15", "pharaoh", "哈哈哈！上帝？哪个上帝呀？我不认识！不放，就是不放！",
         "Ha ha ha! God? Which god? Never heard of him! No! I won't let them go!",
         "Exodus 5:2", dir="a big fake belly laugh first; mocking; then stubborn and childish on 就是不放 / 'I won't'",
         pre=0.2, post=0.5),
    act("pharaoh", "arms_crossed", face="moses"),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "青蛙来啦", "Here come the frogs!", "fixed", "pharaoh", dist=0.58, height=0.18, yawDeg=-25,
         desc="Montage on the palace: Moses raises his staff, the river runs red, frogs hop in, one lands on Pharaoh's crown."),
    music("plagues"),
    act("moses", "staff_raise", face="pharaoh"),
    fx("river_red", "egypt.nile", dur=5.0, dt=0.6), sfx("sting", dt=0.6),
    fx("frogs", "stage", dur=16.0, dt=3.0), sfx("croak", dt=3.4),
    fx("flies", "egypt.palace", dur=3.0, dt=6.2), sfx("buzz", dt=6.2),
    fx("hail", "stage", dur=3.0, dt=8.4), sfx("hail", dt=8.4),
    line("ex_16", "narrator", "于是，上帝降下了一样又一样的灾：河水变红了，到处都是青蛙，还有苍蝇、冰雹……",
         "So God sent trouble after trouble: the river turned red, frogs hopped everywhere, then came flies, and hail...",
         "Exodus 7-10", dir="brisk and lively, a list with rhythm; a little giggle on 青蛙 / 'frogs'", pre=0.4, post=0.4),
    fx("frog_on_head", "pharaoh.head", dur=7.0), sfx("croak"),
    act("pharaoh", "frog_panic", face="viewer", dt=0.6),
    line("ex_17", "pharaoh", "呱？……啊！青蛙！快拿走，快拿走！好好好，我放你们走！",
         "Ribbit?... Aaah! A frog! Get it off, get it off! All right, all right, you can go!",
         "Exodus 8:8", dir="comic: a puzzled 'ribbit?' then a squeal; flustered, fast, high; gives in in a panic",
         pre=1.0, post=0.5),
    act("pharaoh", "smug", face="viewer"),
    line("ex_18", "narrator", "可是青蛙一走，法老就又变卦了。",
         "But as soon as the frogs were gone, Pharaoh changed his mind.",
         "Exodus 8:15", dir="a knowing, teasing tone, like telling on a naughty child", pre=0.6, post=0.2),
    act("pharaoh", "sneaky_no", face="moses"),
    line("ex_19", "pharaoh", "嘿嘿……不放了！", "Heh heh... changed my mind!",
         "Exodus 8:15", dir="sly, smug, sing-song; a cheeky nyah-nyah feel", pre=0.3, post=0.8),
    act("moses", "sigh_head", face="pharaoh", dt=-0.4),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "门上的记号", "The sign on the door", "fixed", "miriam", dist=0.66, height=0.22, yawDeg=15,
         desc="Night. The Israelite houses have red marks above their doors that glow softly. Miriam hurries everyone."),
    music("passover"),
    fx("night", "stage", dur=34.0),
    sfx("crickets_night"),
    prop("egypt/doorMarks", show=True),
    fx("door_glow", "egypt.doorMarks", dur=30.0, dt=0.4),
    act("miriam", "walk", to=MI_DOOR, face="viewer"),
    act("moses", "walk_staff", to=MO_DOOR, face="miriam"),
    prop("egypt/crowdWest", show=False),
    line("ex_20", "narrator", "最后，上帝要降下最重的一灾。他叫以色列人在门上做记号，那一夜都待在家里，平平安安的。",
         "At last God said one more trouble would come, the worst of all. He told his people to put a mark on their doors "
         "and stay inside that night, and they would be safe.",
         "Exodus 12:7, 12:13, 12:22-23", dir="hushed and serious but safe and calm; warm on 平平安安的 / 'they would be safe'",
         pre=1.0, post=0.3),
    act("miriam", "hurry_wave", face="viewer"),
    line("ex_21", "miriam", "大家快吃饭，穿好鞋，拿好东西——今天晚上，我们就要出发啦！",
         "Everyone, eat up! Shoes on, bags packed! Tonight we're leaving!",
         "Exodus 12:11", dir="excited whisper, quick, bustling; a thrill on 出发啦 / 'leaving'", pre=0.3, post=0.6),
    act("pharaoh", "sad_sit", face="viewer"),
    line("ex_22", "pharaoh", "走吧……都走吧！带上你们的羊，统统走吧！",
         "Go... just go! Take your sheep and go, all of you!",
         "Exodus 12:31-32", dir="no comedy here: tired, sorrowful, defeated; a long breath first; quiet", pre=1.2, post=0.8),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "我们自由啦", "We're free!", "orbit", "all", dist=0.8, height=0.32, yawDeg=-15,
         desc="Morning. The people pour out; a soft column of cloud rises ahead of them."),
    music("exodus"),
    prop("egypt/crowdShore", show=True),
    fx("pillar_cloud", "egypt.pillarWest", dur=40.0, dt=1.0),
    act("pharaoh", "sad_sit", face="viewer"),
    act("moses", "walk_staff", to=MO_SHORE, face="viewer"),
    act("miriam", "walk", to=MI_SHORE, face="viewer", dt=0.4),
    sfx("cheer", dt=2.0),
    line("ex_23", "people", "我们自由啦！", "We're free!",
         "Exodus 12:41", dir="a crowd cheering together, joyful and ragged; some laughing", pre=2.4, post=0.4),
    act("miriam", "joy", face="moses"),
    line("ex_24", "narrator", "上帝白天用云柱、晚上用火柱，在前面给他们带路。",
         "God went ahead of them: a pillar of cloud by day, and a pillar of fire by night.",
         "Exodus 13:21", dir="wonder, warm and bright", pre=0.3, post=0.6),
    act("miriam", "idle", face="viewer"),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "法老后悔了", "Pharaoh changes his mind", "fixed", "pharaoh", dist=0.56, height=0.16, yawDeg=-30,
         desc="Pharaoh jumps up, stamps, and climbs into his golden chariot."),
    music("chase"),
    act("pharaoh", "tantrum", face="viewer"),
    line("ex_25", "pharaoh", "等等！他们都走了……谁给我做砖呀？备车！快追！",
         "Wait! They've all gone... then who's going to make my bricks? My chariot! After them!",
         "Exodus 14:5-7", dir="comic tantrum: realisation, then outraged, then bossy shouting; a stamp in the rhythm",
         pre=0.4, post=0.2),
    prop("pharaoh/chariot", show=True),
    sfx("chariot", dt=0.2),
    act("pharaoh", "ride", to=PH_STEP, face="viewer", dt=0.2),
    act("pharaoh", "ride", to=PH_CHASE, face="moses", dt=3.0),
    act("pharaoh", "ride_idle", face="moses", dt=5.6),                  # 0.30 at 0.134 u/s: arrives ~2.3 s after the move
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "前面是大海", "The sea is in the way", "fixed", "all", dist=0.64, height=0.2, yawDeg=25,
         desc="On the beach: the sea ahead, Pharaoh's chariot behind. Miriam is scared; Moses stands firm."),
    act("miriam", "scared", face="moses"),
    line("ex_26", "miriam", "摩西！前面是大海，后面是法老的兵车……我们怎么办呀？",
         "Moses! The sea is in front of us, and Pharaoh's chariots are behind us... what do we do?",
         "Exodus 14:10-11", dir="frightened, fast, breathless; pitch rising to the question", pre=0.4, post=0.3),
    act("moses", "brave_talk", face="miriam"),
    line("ex_27", "moses", "不要怕！站稳了，看上帝怎样救我们！",
         "Don't be afraid! Stand still, and watch how God will save us!",
         "Exodus 14:13", dir="calm and strong, the steadiest voice in the story; a hand on her shoulder in the voice",
         pre=0.3, post=0.6),
    act("miriam", "idle", face="moses"),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "海分开了", "The sea opens", "follow", "moses", dist=0.78, height=0.32, yawDeg=-25,
         desc="Moses stretches his staff over the sea; a great wind; the water stands up in two walls; a dry path."),
    music("sea"),
    act("moses", "staff_over_sea", face="egypt.sea"),
    fx("sea_wind", "egypt.sea", dur=9.0, dt=0.4), sfx("wind", dt=0.4),
    fx("sea_part", "egypt.sea", dur=4.5, dt=2.2), sfx("sea_rush", dt=2.2),
    line("ex_28", "narrator", "摩西向大海伸出手杖。上帝刮起大风，刮了一整夜——海水哗地分开了，中间出现了一条干干的路！",
         "Moses stretched out his staff over the sea. God sent a strong wind that blew all night, and whoosh! "
         "The water split apart, and there was a dry path right through the middle!",
         "Exodus 14:21-22", dir="building wonder; quick and big on 哗 / 'whoosh'; awe on 干干的路 / 'dry path'",
         pre=1.2, post=0.4),
    act("miriam", "wow", face="egypt.sea"),
    line("ex_29", "miriam", "哇……海水像两面墙一样！大家快走！",
         "Wow... the water is standing up like two walls! Come on, everyone, let's go!",
         "Exodus 14:22", dir="breathless wonder first, then a happy call to the crowd", pre=0.4, post=0.2),
    act("moses", "walk_staff", to=MO_MID, face="viewer"),
    act("miriam", "walk", to=MI_MID, face="viewer", dt=0.3),
    prop("egypt/crowdShore", show=False, dt=1.0),
    act("moses", "walk_staff", to=MO_FAR, face="viewer", dt=5.6),
    act("miriam", "walk", to=MI_FAR, face="viewer", dt=5.6),
    prop("egypt/crowdFar", show=True, dt=6.0),
    fx("pillar_fire", "egypt.pillarWest", dur=10.0, dt=4.0),
    pause(9.0),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "哗啦", "Splash!", "fixed", "pharaoh", dist=0.62, height=0.2, yawDeg=-35,
         desc="Pharaoh's chariot rattles onto the sea-bed; a wheel pops off; the walls roll back with a huge splash; "
              "Pharaoh is left sitting soaked on the beach."),
    act("pharaoh", "ride", to=PH_SEA, face="viewer"),
    line("ex_30", "pharaoh", "冲啊——咦？我的轮子！哎哎哎……哇啊啊！",
         "Charge! Huh? My wheel! Hey, hey, hey... waaah!",
         "Exodus 14:23-25", dir="comic: a proud battle-cry, then puzzled, then wobbling panic, then a long wail",
         pre=2.6, post=0.0),
    prop("pharaoh/wheelL", show=False, dt=-3.6), prop("egypt/looseWheel", show=True, dt=-3.6),
    sfx("wheel_pop", dt=-3.6),
    act("pharaoh", "wobble", face="viewer", dt=-3.4),
    fx("sea_close", "egypt.sea", dur=3.0, dt=-1.2), sfx("splash", dt=-0.8),
    fx("splash", "pharaoh.root", dur=2.0, dt=-0.6),
    prop("pharaoh/chariot", show=False, dt=0.4), prop("egypt/looseWheel", show=False, dt=0.4),
    act("pharaoh", "soggy_sit", to=PH_SOGGY, face="viewer", dt=0.4),
    fx("drips", "pharaoh.head", dur=12.0, dt=0.6),
    line("ex_31", "narrator", "海水合拢了，法老的兵车再也追不上了。以色列人平平安安地，走到了大海的那一边！",
         "The water came rushing back, and Pharaoh's chariots could not follow any more. "
         "God's people were safe on the other side of the sea!",
         "Exodus 14:26-29", dir="relief and joy; slow and warm on 平平安安地 / 'safe'", pre=1.6, post=0.4),
    act("pharaoh", "sneeze", face="viewer"),
    line("ex_32", "pharaoh", "阿……阿……阿嚏！", "Ah... ah... ACHOO!",
         "Exodus 14:30", dir="a soggy, sulky sneeze, comic build-up; small and silly, not loud", pre=0.6, post=0.6),
    sfx("drip"),
    # S13 --------------------------------------------------------------------------------------------------------
    shot("S13", "米利暗的歌", "Miriam's song", "orbit", "miriam", dist=0.6, height=0.22, yawDeg=20,
         desc="On the far shore Miriam lifts her tambourine and dances; the people sing with her."),
    music("song"),
    prop("miriam/tambourine", show=True),
    act("miriam", "tambourine_dance", face="viewer"),
    act("moses", "clap", face="miriam"),
    fx("sparkle", "egypt.sea", dur=2.0, dt=0.6),
    line("ex_33", "miriam", "唱歌吧，向上帝唱歌！他大大得胜，把马和兵车都抛在海里！",
         "Sing to the Lord, sing! He has won the victory! Horse and chariot, he threw into the sea!",
         "Exodus 15:20-21", dir="a joyful chant in rhythm with the tambourine, half-sung, laughing; bounce on every phrase",
         pre=1.041, post=0.3),                                          # clip's first sound on bar 2 of `song` (bar = 1.0714 s)
    line("ex_34", "people", "唱歌吧！向上帝唱歌！", "Sing to the Lord! Sing!",
         "Exodus 15:1", dir="the crowd echoing her chant, happy, in rhythm, slightly ragged", pre=0.483, post=0.6),  # bar 10
    sfx("cheer"),
    fx("confetti", "miriam.root", dur=4.0),
    # S14 --------------------------------------------------------------------------------------------------------
    shot("S14", "上帝带路", "God leads the way", "orbit", "all", dist=0.74, height=0.28, yawDeg=-10,
         desc="Moses and Miriam face the child on the far shore; golden rays; Moses raises his staff, Miriam waves."),
    music("finale"),
    act("miriam", "idle", face="viewer"),
    act("moses", "talk_warm", face="viewer"),
    line("ex_35", "moses", "上帝听见了我们的哭声，一路带着我们走。",
         "God heard us when we cried, and he led us all the way.",
         "Exodus 3:7, 15:13", dir="warm, grateful, a grandfather's smile; slow", pre=0.6, post=0.5),
    act("moses", "staff_raise", face="viewer"),
    act("miriam", "wave", face="viewer"),
    fx("golden_rays", "moses.root", dur=7.0, dt=0.2),
    line("ex_36", "narrator", "小朋友，遇到害怕的事，你也可以向上帝祷告。他会听见，也会给你带路哦！",
         "When you're scared, you can pray to God too. He hears you, and he'll show you the way!",
         "Exodus 14:13-14", dir="warm moral, speaking right to the child; smile on the last sentence", pre=0.6, post=2.2),
]
