"""Gabriel — the archangel, the play (docs/gabriel/CONTRACT.md §5). Replaces the old trumpet-angel book.

`tools/story/build_timeline.py gabriel` turns this into assets/gabriel/timeline.json, placed by the real voice
durations. Same helpers as Daniel / Ruth / Esther: shot / line / act / fx / sfx / music / prop / pause.
Marks are art-width units on the page (x right, z toward the viewer); the set's marks are in CONTRACT.md §6.

One hero, about two minutes: the archangel Gabriel comes down from the heavenly city, tells the child not to be
afraid, tells who he is and which good news he carried (Daniel 9, Luke 1), blows the golden trumpet, blesses the
child and flies home. Lines are spoken paraphrases of Scripture for ages 4-10: short, warm, said *to* the child.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py

ID = "gabriel"
CAST = ["gabriel"]
SET = "heaven"

SKY = (0.00, 0.02)        # where he lands: page centre, a little forward
FRONT = (0.00, 0.10)      # one step toward the child
GATE = (0.00, -0.40)      # in front of the heavenly gate (far back)

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "天上的城", "The city of light", "orbit", "all", dist=0.95, height=0.46, yawDeg=-20,
         desc="Slow orbit over a sea of golden clouds; the shining gate at the back; rays of light. A bright point "
              "high in the sky grows into a winged figure coming down."),
    music("heaven"),
    fx("heaven_rays", "stage", dur=999),
    fx("cloud_drift", "stage", dur=999),
    act("gabriel", "hover", to=SKY, face="viewer"),
    prop("gabriel/trumpet", show=False), prop("gabriel/sword", show=True),
    pause(1.2),
    line("ga_01", "narrator", "在天上，有一座发光的城。那里住着上帝的天使。其中有一位大天使，名字叫加百列。",
         "High above, there is a city full of light, where God's angels live. One of them is a great archangel. "
         "His name is Gabriel.",
         "Revelation 21:23; Luke 1:19", dir="hushed wonder, like opening a treasure box; slow, a smile on the name "
                                          "加百列 / 'Gabriel'", post=0.3),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "从天而降", "Down from heaven", "follow", "gabriel", dist=0.7, height=0.3, yawDeg=15,
         desc="Gabriel comes down through a column of light with slow, huge wing beats, lands softly on the clouds, "
              "folds his wings and looks at the child."),
    music("descend"),
    act("gabriel", "fly_down", face="viewer"),
    fx("descend_light", "gabriel.root", dur=6.4),
    sfx("wing_flap", dt=0.4), sfx("wing_flap", dt=1.6), sfx("wing_flap", dt=2.8),
    fx("feather_fall", "gabriel.chest", dur=6.0, dt=1.0),
    sfx("whoosh_land", dt=4.1), fx("wing_gust", "gabriel.root", dur=1.4, dt=4.17),
    act("gabriel", "fold_wings", face="viewer", dt=5.0), sfx("wing_fold", dt=5.2),
    pause(6.4),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "不要怕", "Do not be afraid", "fixed", "gabriel", dist=0.55, height=0.22, yawDeg=-10,
         desc="He steps forward and goes down on one knee to the child's height, smiling."),
    music("gentle"),
    act("gabriel", "walk", to=FRONT, face="viewer"),
    act("gabriel", "kneel_down", face="viewer", dt=1.6),
    act("gabriel", "kneel_talk", face="viewer", dt=2.8),
    line("ga_02", "gabriel", "不要怕，小朋友！我是加百列，是站在上帝面前的天使。",
         "Don't be afraid, little one! I am Gabriel. I stand in the presence of God.",
         "Luke 1:13, 1:19", dir="warm, strong and gentle at once, a big brother kneeling down to a small child; "
                               "a smile in the voice; the name said with quiet joy", pre=2.0, post=0.5),
    line("ga_03", "gabriel", "上帝常常派我，把他的好消息，送给他爱的人。",
         "God sends me to carry His good news to the people He loves.",
         "Luke 1:19", dir="kind, like telling a secret about his job; a little proud and happy", pre=0.3, post=0.6),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "送信的天使", "The messenger", "orbit", "gabriel", dist=0.62, height=0.24, yawDeg=25,
         desc="He stands, points back toward the earth, then up to heaven while he remembers."),
    music("story"),
    act("gabriel", "stand_up", face="viewer"),
    act("gabriel", "talk", face="viewer", dt=1.2),
    line("ga_04", "gabriel", "很久以前，但以理在祷告，我就飞去告诉他：上帝很爱你！",
         "Long ago, when Daniel was praying, I flew to him to tell him: God loves you very much!",
         "Daniel 9:21-23", dir="storytelling, bright; a little lift on 飞去 / 'flew'; tender on 很爱你 / 'loves you'",
         pre=1.4, post=0.5),
    act("gabriel", "point_up", face="viewer"),
    fx("sparkle", "gabriel.handR", dur=1.2, dt=0.4), sfx("sparkle", dt=0.4),
    line("ga_05", "gabriel", "后来，我又去见一个叫马利亚的女孩，告诉她：你要生一个儿子，给他起名叫耶稣！",
         "Later, I went to a young woman named Mary, and told her: you will have a baby boy, and you will name him "
         "Jesus!",
         "Luke 1:26-31", dir="joyful and full of wonder; slow and glowing on 耶稣 / 'Jesus'", pre=0.6, post=0.6),
    act("gabriel", "idle", face="viewer"),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "最好的消息", "The best news of all", "fixed", "gabriel", dist=0.6, height=0.18, yawDeg=-25,
         desc="He lifts the golden trumpet, spreads his wings wide and blows a great call; golden notes and light "
              "burst over the clouds."),
    music("fanfare"),
    prop("gabriel/trumpet", show=True),
    act("gabriel", "raise_trumpet", face="viewer"),
    line("ga_06", "gabriel", "这是全世界最好的消息！听——",
         "It's the best news in the whole world! Listen...",
         "Luke 2:10", dir="excited, building; a breath and a hush on 听 / 'Listen'", pre=0.8, post=0.2),
    act("gabriel", "blow_trumpet", face="viewer"),
    sfx("trumpet_call", dt=0.5),
    fx("trumpet_notes", "gabriel.trumpet", dur=4.5, dt=0.5),
    fx("golden_rays", "gabriel.root", dur=5.0, dt=0.6),
    fx("feather_fall", "gabriel.chest", dur=5.0, dt=1.0),
    pause(5.4),
    act("gabriel", "spread_wings", face="viewer"),
    sfx("choir_ah", dt=0.2),
    pause(2.4),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "你很安全", "You are safe", "orbit", "gabriel", dist=0.58, height=0.2, yawDeg=10,
         desc="Wings wide, he lowers the trumpet and lays a hand on his heart, then opens his palm toward the child."),
    music("gentle"),
    prop("gabriel/trumpet", show=False),
    act("gabriel", "bless", face="viewer"),
    fx("bless_glow", "gabriel.chest", dur=5.0, dt=0.6),
    line("ga_07", "gabriel", "上帝爱你。不管你在哪里，他都看顾你。所以，不要怕！",
         "God loves you. Wherever you are, He is watching over you. So don't be afraid!",
         "Isaiah 41:10; Psalm 121:7-8", dir="the heart of the story: slow, warm, very sure; a soft pause before "
                                           "所以 / 'So'", pre=1.2, post=0.6),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "涂上你的颜色", "Colour me in", "orbit", "all", dist=0.85, height=0.34, yawDeg=-15,
         desc="He waves, crouches, springs up and flies back toward the gate of light; feathers drift down."),
    music("finale"),
    act("gabriel", "wave", face="viewer"),
    line("ga_08", "gabriel", "下次，把我涂上你最喜欢的颜色吧！再见啦！",
         "Next time, colour me in with your favourite colours! Goodbye for now!",
         "", dir="playful and warm, a laugh in it; big friendly goodbye", pre=0.4, post=0.3),
    act("gabriel", "fly_up", face="viewer"),
    sfx("wing_flap", dt=0.6), sfx("wing_flap", dt=1.5),
    fx("wing_gust", "gabriel.root", dur=1.2, dt=0.6),
    fx("feather_fall", "stage", dur=6.0, dt=1.4),
    line("ga_09", "narrator", "加百列飞回了天上。上帝的好消息，也是给你的哦！",
         "Gabriel flew back up to heaven. And God's good news is for you, too!",
         "Luke 2:10", dir="warm closing, speaking right to the child; smile on the last words", pre=2.6, post=2.4),
]
