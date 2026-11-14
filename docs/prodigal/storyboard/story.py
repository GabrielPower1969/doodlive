"""The prodigal son — the play, as beats relative to each other (docs/prodigal/CONTRACT.md §5).

`tools/story/build_timeline.py prodigal` turns this into assets/prodigal/timeline.json, placing every line by the real
voice durations. Same helpers as Ruth / Exodus: shot / line / act / fx / sfx / music / prop / pause.
Marks are art-width units on the page (x right, z toward the viewer; the set's marks are in CONTRACT.md §6).

Lines are spoken paraphrases of Luke 15:11-32 for ages 4-10, written to be *said*, not read. Child-friendly: "wild
living" is sweets, fancy clothes and parties; the feast is a table, not a calf; the ending stays open but hopeful (the
brother takes his father's hand, shown not said).
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py

ID = "prodigal"
CAST = ["son", "father", "brother"]
SET = "homeland"

# stage marks (CONTRACT.md §6)
FA_DOOR = (-0.30, -0.24)       # father at his front door
SON_HOME = (-0.16, -0.20)      # the son in the courtyard
BRO_FIELD = (0.02, -0.34)      # the brother hoeing the field behind the courtyard
BRO_FIELD2 = (0.20, -0.32)     # further along the field, clear of the hug sightline
ROAD_A = (-0.02, -0.04)        # the road from the gate toward the far country
ROAD_B = (0.16, 0.06)
TAVERN = (0.32, -0.26)         # in front of the far-country tavern
PIGPEN = (0.34, 0.04)          # inside the pig pen gate
PIG_SIT = (0.30, 0.10)
ROAD_C = (0.14, 0.12)          # on the way home (front)
MEET = (0.00, 0.06)            # where the father reaches him
FA_LOOK = (-0.16, -0.06)       # the father's lookout at the gate, every day
FEAST_SON = (-0.32, -0.12)     # the feast in the courtyard (table at (-0.38, -0.16))
FEAST_FA = (-0.22, -0.10)
BRO_OUT = (-0.02, 0.10)        # outside the courtyard wall at night
FA_OUT = (-0.12, 0.08)
OFF_RIGHT = (0.64, 0.12)

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "爸爸和两个儿子", "A father and two sons", "orbit", "all", dist=0.9, height=0.40, yawDeg=-35,
         desc="Slow orbit over the page in soft morning light: the farmhouse, the field, the road winding away to a "
              "far-off city and a pig pen."),
    music("home"),
    sfx("birds", dt=0.3),
    act("father", "idle", to=FA_DOOR, face="viewer"),
    act("brother", "work_field", to=BRO_FIELD, face="viewer"),
    act("son", "laze", to=SON_HOME, face="viewer"),
    prop("father/purse", show=False), prop("son/purse", show=False), prop("son/robe", show=False),
    prop("son/ring", show=False), prop("brother/hoe", show=True), prop("homeland/feast", show=False),
    prop("homeland/lamps", show=False), prop("homeland/pods", show=True),
    pause(1.2),
    line("pr_01", "narrator", "耶稣讲过一个故事。有个爸爸，他有两个儿子。哥哥天天在田里干活，弟弟呢……就爱玩。",
         "Jesus once told a story. There was a father who had two sons. The big brother worked in the field every day. "
         "The little brother... just liked to play.",
         "Luke 15:11", dir="storyteller opening, warm; a little smile and a pause before 就爱玩 / 'just liked to play'",
         post=0.4),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "把钱给我", "Give me my share", "fixed", "father", dist=0.6, height=0.18, yawDeg=20,
         desc="The son strolls up to his father, hand out. The father's face falls; slowly he gives him a money bag."),
    act("son", "walk", to=(-0.22, -0.20), face="father"),
    act("son", "ask_money", face="father", dt=1.4),
    line("pr_02", "son", "爸爸！把我该得的那份家产给我吧。我要去远方，好好玩一玩！",
         "Dad! Give me my share of everything now. I want to go far away and have some fun!",
         "Luke 15:12", dir="cheeky, breezy, a bit spoilt; bright on 好好玩一玩 / 'have some fun'", pre=1.6, post=0.5),
    act("father", "sad_give", face="son"),
    prop("father/purse", show=True),
    prop("father/purse", show=False, dt=2.2), prop("son/purse", show=True, dt=2.2),
    sfx("coins", dt=2.2),
    line("pr_03", "father", "唉……好吧，孩子。这是你的。你……要小心啊。",
         "Oh... all right, my son. Here it is. Please... be careful.",
         "Luke 15:12", dir="a sad sigh first; loving, slow; a catch in the voice before 要小心啊 / 'be careful'",
         pre=0.4, post=0.6),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "出发去远方", "Off to a far country", "follow", "son", dist=0.75, height=0.24, yawDeg=-20,
         desc="The son swaggers down the road with his bag, waving; behind him the father waves slowly."),
    music("leaving"),
    act("son", "wave_bye", face="father"),
    line("pr_04", "son", "拜拜！我要去过好日子啦！",
         "Bye-bye! I'm off to live the good life!",
         "Luke 15:13", dir="carefree, sing-song, already walking away", pre=0.3, post=0.2),
    act("son", "strut", to=ROAD_A, face="viewer"),
    act("son", "strut", to=ROAD_B, face="viewer", dt=2.2),
    act("son", "strut", to=TAVERN, face="viewer", dt=4.4),
    act("father", "walk", to=FA_LOOK, face="son", dt=0.6),              # walk to the gate, then wave (no glide)
    act("father", "wave_sad", face="son", dt=3.8),
    act("brother", "shake_head", face="son", dt=1.4),
    line("pr_05", "brother", "哼，就知道玩。", "Hmph. All he thinks about is having fun.",
         "Luke 15:12-13", dir="grumbling under his breath, leaning on his hoe", pre=1.6, post=0.3),
    act("brother", "work_field", face="viewer"),
    pause(2.6),                                                          # time for the last strut leg
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "天天开派对", "Party every day", "fixed", "son", dist=0.6, height=0.2, yawDeg=-25,
         desc="Far-country tavern, coloured lights. The son tosses coins in the air; off-stage friends cheer."),
    music("party"),
    fx("party_lights", "homeland.tavern", dur=16.0),
    act("son", "toss_coins", face="viewer"),
    act("son", "party_dance", face="viewer", dt=2.4),                   # dance while the narrator talks
    fx("coins_spray", "son.handR", dur=1.6, dt=0.6), sfx("coins", dt=0.6),
    line("pr_06", "narrator", "到了远方，他天天请客、买糖、买新衣服，花钱像流水一样。",
         "In the far country he threw parties every day, bought sweets and fancy clothes, and spent money like water.",
         "Luke 15:13", dir="lively and a bit disapproving, like telling about a naughty friend", pre=1.0, post=0.2),
    line("pr_07", "son", "大家随便吃！今天我请客！", "Eat whatever you like, everyone! It's on me!",
         "Luke 15:13", dir="show-off, loud, laughing", pre=0.2, post=0.1),
    line("pr_08", "friends", "好耶！你最好啦！", "Yay! You're the best!",
         "Luke 15:13", dir="three or four friends cheering together, giggly, a bit greedy", pre=0.1, post=0.3),
    sfx("cheer", dt=-0.4),
    pause(1.2),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "钱花光了", "All gone", "fixed", "son", dist=0.55, height=0.16, yawDeg=15,
         desc="He reaches into his bag: nothing. He turns out his pockets. The lights go out; a dry haze falls."),
    music("broke"),
    act("son", "empty_pockets", face="viewer"),
    prop("son/purse", show=False, dt=2.6),
    line("pr_09", "son", "咦？钱呢？……一个都没有了？", "Huh? Where's my money?... There's none left?",
         "Luke 15:14", dir="puzzled, then dawning horror; small voice on 一个都没有了 / 'none left'", pre=1.2, post=0.2),
    line("pr_10", "friends", "没钱了？那……我们走啦，拜拜！", "No money? Oh... well, we're off then. Bye!",
         "Luke 15:13-14", dir="suddenly cool and off-hand, drifting away, voices fading", pre=0.2, post=0.6),
    act("son", "sad_idle", face="viewer"),
    fx("famine_haze", "stage", dur=31.0, dt=0.4), sfx("wind_dry", dt=0.4),   # dur: until S08 starts (set from the voiced timeline)
    line("pr_11", "narrator", "偏偏这时候，那地方闹了大饥荒，什么吃的都没有了。",
         "And just then a great famine came to that land. There was nothing to eat.",
         "Luke 15:14", dir="slower, serious, a dry hush", pre=1.0, post=0.4),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "喂猪", "Feeding the pigs", "fixed", "son", dist=0.56, height=0.18, yawDeg=-30,
         desc="The son in a muddy pig pen scatters pods from a sack; the pigs shove and oink. He eyes the pods."),
    music("pigs"),
    act("son", "sad_walk", to=PIGPEN, face="viewer"),
    sfx("oink", dt=1.6),
    line("pr_12", "narrator", "他只好去给人家喂猪。", "So he had to take a job feeding pigs.",
         "Luke 15:15", dir="matter-of-fact with a tiny wince on 喂猪 / 'pigs'", pre=1.0, post=0.2),
    act("son", "feed_pigs", face="viewer"),
    sfx("oink", dt=0.6), sfx("oink", dt=2.0),
    act("son", "hungry_look", face="homeland.pods", dt=3.0),
    line("pr_13", "son", "好饿呀……连猪吃的豆荚，看起来都好香……", "I'm so hungry... even the pigs' pods look yummy...",
         "Luke 15:16", dir="weak, sorry for himself; a stomach-rumble pause; comic longing on 好香 / 'yummy'", pre=3.4,
         post=0.3),
    sfx("tummy", dt=-0.6),
    sfx("oink", dt=0.2),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "想家", "Thinking of home", "fixed", "son", dist=0.5, height=0.14, yawDeg=20,
         desc="He sits down in the mud, head in hands; then he looks up: an idea."),
    music("homesick"),
    act("son", "sad_walk", to=PIG_SIT, face="viewer"),
    act("brother", "walk_hoe", to=BRO_FIELD2, face="viewer"),           # off camera: move along the field so he isn't behind the hug
    act("brother", "work_field", face="viewer", dt=2.0),
    act("son", "sit_sad", face="viewer", dt=1.3),
    line("pr_14", "son", "我爸爸家里的工人，个个都有饭吃……我却在这里饿肚子。",
         "Even the workers at my dad's house have plenty to eat... and here I am, starving.",
         "Luke 15:17", dir="quiet, realising, close to tears", pre=1.4, post=0.6),
    act("son", "idea_stand", face="viewer"),
    fx("sparkle", "son.head", dur=1.2, dt=0.5), sfx("sparkle", dt=0.5),
    line("pr_15", "son", "对了！我要回家！", "That's it! I'll go home!",
         "Luke 15:18", dir="sudden resolve, hope in the voice", pre=0.7, post=0.4),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "练习道歉", "Practising sorry", "follow", "son", dist=0.7, height=0.2, yawDeg=25,
         desc="Golden evening. He trudges home along the road, rehearsing his speech, trying different gestures."),
    music("road_home"),
    fx("sunset_glow", "stage", dur=44.8),                               # dur: until S11 starts
    act("son", "practise", to=ROAD_C, face="viewer"),
    line("pr_16", "son", "爸爸，我错了……我得罪了上帝，也得罪了你。我不配做你的儿子了，让我做你的工人吧。",
         "Dad, I was wrong... I sinned against God and against you. I don't deserve to be your son. "
         "Let me be one of your workers.",
         "Luke 15:18-19", dir="trying it out, earnest, a little clumsy; a breath between sentences", pre=0.6,
         post=0.3),
    line("pr_17", "son", "嗯……就这么说。", "Hmm... yes. I'll say that.",
         "Luke 15:19", dir="to himself, nodding, nervous", pre=0.2, post=0.4),
    act("son", "sad_idle", face="viewer"),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "爸爸跑过来", "The father runs", "follow", "father", dist=0.76, height=0.24, yawDeg=-25,
         desc="At the gate the father shades his eyes and looks down the road, as he has every day. He sees a small "
              "figure, gasps, hitches up his robe and runs."),
    act("father", "look_far", to=FA_LOOK, face="son"),
    act("son", "walk_tired", to=(0.10, 0.08), face="father"),           # hug distance 0.10 from MEET
    act("son", "sad_idle", face="father", dt=1.4),
    line("pr_18", "narrator", "爸爸每天都站在路口，往远处看。",
         "Every day, the father stood at the gate and looked down the road.",
         "Luke 15:20", dir="tender, slow, a longing in it", pre=0.8, post=0.4),
    act("father", "see_son", face="son"),
    line("pr_19", "father", "那是……那是我的孩子！", "Is that... is that my boy?!",
         "Luke 15:20", dir="disbelief turning into joy; breath catching; rising", pre=0.4, post=0.1),
    music("run"),
    act("father", "run", to=MEET, face="son", dt=0.2),
    fx("run_dust", "father.root", dur=2.8, dt=0.2), sfx("footsteps_run", dt=0.2),
    act("son", "idle", face="father", dt=0.4),
    act("father", "hug", face="son", dt=1.5),                           # the run (0.20 at 0.156 u/s) lands straight in the hug
    act("son", "hug", face="father", dt=1.5),
    fx("heart_glow", "father.chest", dur=5.0, dt=1.7, to="son.chest"),
    pause(3.6),
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "最好的袍子", "The best robe", "fixed", "all", dist=0.56, height=0.16, yawDeg=20,
         desc="Still in his father's arms, the son starts his speech; the father doesn't let him finish."),
    act("son", "sorry_head", face="father"),
    line("pr_20", "son", "爸爸，我错了，我不配做你的儿子……", "Dad, I was wrong. I don't deserve to be your son...",
         "Luke 15:21", dir="crying softly, small; trails off as he's interrupted", pre=0.6, post=0.0),
    act("father", "call_servants", face="viewer"),
    line("pr_21", "father", "快！拿最好的袍子给他穿上，把戒指给他戴上！我们要摆宴席，好好庆祝！",
         "Quick! Bring the best robe and put it on him! Put a ring on his finger! We're going to have a feast!",
         "Luke 15:22-23", dir="cutting in happily, laughing through tears, loud and bustling", pre=0.1, post=0.1),
    line("pr_22", "servants", "是，主人！", "Yes, master!",
         "Luke 15:22", dir="two or three servants answering eagerly, off-stage", pre=0.1, post=0.3),
    prop("son/robe", show=True, dt=0.2), prop("son/ring", show=True, dt=0.6),
    fx("sparkle", "son.chest", dur=1.4, dt=0.2), sfx("sparkle", dt=0.2),
    act("son", "amazed", face="father", dt=0.4),
    pause(3.0),                                                          # let `amazed` reach the ring and the spread hands
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "宴席", "The feast", "orbit", "all", dist=0.7, height=0.3, yawDeg=20,
         desc="Night in the courtyard: lamps, a long table of food, music. Father and son dance."),
    music("feast"),
    sfx("crickets_night", dt=0.5),                                       # ambience bed; mix.json stops it at `finale`
    fx("night", "stage", dur=60.4),                                     # dur: until S14 starts
    prop("homeland/feast", show=True), prop("homeland/lamps", show=True),
    fx("lamps_flames", "homeland.lamps", dur=60.4),
    act("father", "walk", to=FEAST_FA, face="son"),
    act("son", "walk", to=FEAST_SON, face="father", dt=0.3),
    act("father", "feast_cheer", face="viewer", dt=4.0),
    line("pr_23", "father", "我这个儿子，是死而复活，失而又得的！",
         "This son of mine was dead and is alive again! He was lost, and now he is found!",
         "Luke 15:24", dir="joyful announcement to everyone, slow and big on 失而又得 / 'lost... found'", pre=4.2,
         post=0.3),
    act("son", "dance", face="viewer"),
    act("father", "dance", face="viewer", dt=0.4),
    fx("music_notes", "homeland.house", dur=49.6), sfx("cheer", dt=0.2),
    pause(1.6),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "哥哥生气了", "The big brother is cross", "follow", "brother", dist=0.66, height=0.2, yawDeg=-30,
         desc="Outside the wall in the dark the brother comes back from the field, hoe on shoulder, hears the music, "
              "and stops. He crosses his arms."),
    music("brother"),
    act("brother", "walk_hoe", to=BRO_OUT, face="viewer"),
    act("brother", "listen_music", face="homeland.house", dt=4.0),
    line("pr_24", "brother", "咦？家里怎么这么热闹？……什么？弟弟回来了，爸爸还给他摆宴席？",
         "Huh? What's all that noise at home?... What? My brother's back, and Dad's throwing him a party?",
         "Luke 15:25-27", dir="puzzled, then outraged disbelief", pre=4.4, post=0.2),
    act("brother", "stomp_cross", face="viewer"),
    line("pr_25", "brother", "哼！我才不进去！", "Hmph! I'm not going in!",
         "Luke 15:28", dir="sulky, stubborn, loud", pre=0.6, post=0.6),
    # S13 --------------------------------------------------------------------------------------------------------
    shot("S13", "爸爸出来劝他", "The father comes out", "fixed", "all", dist=0.6, height=0.18, yawDeg=20,
         desc="The father comes out to him and pleads. The brother complains. The father holds out his hand; after a "
              "long moment, the brother takes it."),
    act("father", "walk", to=FA_OUT, face="brother"),
    act("father", "plead", face="brother", dt=2.6),
    act("brother", "complain", face="father", dt=2.6),
    line("pr_26", "brother", "我天天给你干活，从来没有不听话。可你连一只小山羊都没给过我！",
         "I've worked for you every single day and never disobeyed you. But you never even gave me a little goat!",
         "Luke 15:29-30", dir="hurt and angry, voice cracking a little at the end", pre=2.8, post=0.4),
    act("father", "arm_out", face="brother"),
    line("pr_27", "father", "孩子，你一直和我在一起，我的一切都是你的。可你弟弟是失而又得的，我们怎么能不高兴呢？",
         "My son, you are always with me, and everything I have is yours. But your brother was lost and is found. "
         "How can we not be glad?",
         "Luke 15:31-32", dir="very gentle, patient, loving both sons; slow; hopeful question", pre=0.4, post=1.2),
    act("brother", "soften", face="father"),
    act("brother", "take_hand", face="father", dt=2.2),
    fx("heart_glow", "father.chest", dur=4.0, dt=2.6, to="brother.chest"),
    pause(4.4),                                                          # the hands meet 1.7 s into take_hand
    # S14 --------------------------------------------------------------------------------------------------------
    shot("S14", "天父在等你", "God is waiting for you", "orbit", "all", dist=0.74, height=0.28, yawDeg=-10,
         desc="All three by the courtyard; golden rays; the son waves to the child."),
    music("finale"),
    act("son", "walk", to=(0.06, 0.12), face="viewer"),
    act("father", "idle", face="viewer", dt=0.6),
    act("brother", "idle", face="viewer", dt=0.6),
    line("pr_28", "narrator", "耶稣讲这个故事，是要告诉我们：天父就像这个爸爸。不管你走多远，他都在等你回家。",
         "Jesus told this story to show us that God our Father is like this dad. However far you go, he is waiting "
         "for you to come home.",
         "Luke 15:20, 15:24", dir="warm moral, speaking right to the child", pre=1.0, post=0.4),
    act("son", "wave", face="viewer"),
    fx("golden_rays", "father.root", dur=7.0, dt=0.2),
    line("pr_29", "narrator", "做错了事，说一声「对不起」，回到他身边，他会张开手臂抱你哦！",
         "If you've done something wrong, say sorry and come back to him. He'll run to give you a big hug!",
         "Luke 15:20-21", dir="smiling, gentle encouragement; last words like a hug", pre=0.4, post=2.2),
]
