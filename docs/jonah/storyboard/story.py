"""Jonah — the play, as beats relative to each other (docs/jonah/CONTRACT.md §5).

`tools/story/build_timeline.py jonah` turns this into assets/jonah/timeline.json, placing every line by the real
voice durations. Helpers: shot / line / act / fx / sfx / music / prop / pause (same as every pack).
Marks are art-width units on the page (x right, z toward the viewer); the set's marks are in CONTRACT.md §6.
`face` takes an actor id, "viewer", or a set node name ("ship", "gate", "plantBig").

Lines are spoken paraphrases of the Book of Jonah for ages 4-10: short sentences, everyday words, people talking to
each other, the narrator only bridging. Child-friendly: the sailors are kind (they do not want to throw him), the
storm is exciting not terrifying, the fish is funny (gulp, burp, "pfft"), nobody dies. God speaks as a warm
off-stage voice (`god`, as in the Exodus pack).

Staging rules of this pack (fix pass 2026-11-15, docs/jonah/FIXLOG-20261115.md):
- An actor who is not in a scene is HIDDEN (`prop("<actor>", show=False)`, as Esther hides Haman and the guards) and
  moved with `snap=True`; parking it visibly off the page made it float over the table. It is shown again at a cut
  or at the beat it enters (`prop("<actor>", show=True)`).
- No camera targets "all": StoryDirector averages every actor, hidden ones included. Shots target an actor or a set
  node ("beach" = the page centre, "belly", "hill", "gate", "ship", "worm"). A `fixed` camera locks on its target at
  the shot's first frame, so whoever it frames is snapped to the mark before the shot starts.
- `orbit` turns 6 deg/s: an orbit shot is kept under ~10 s, or the speaker ends up behind the camera's back.
- The fish swims sideways in its lane (z -0.06..0.21, facing +X / -X); facing the viewer its tail cut into the hull.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py

ID = "jonah"
CAST = ["jonah", "captain", "fish"]
SET = "coast"

DECK = 0.10                    # ship deck height (CONTRACT §6): actors on the ship stand at y = DECK
ROAD = (0.28, 0.14)            # where the story starts: the road on the shore, right of centre
BEACH = (0.12, 0.10)           # on the sand, by the gangplank
JONAH_DECK = (-0.26, -0.22)    # on the deck, right of the mast
CAPT_DECK = (-0.44, -0.22)     # on the deck, left of the mast, by the steering oar
CARGO = (-0.30, -0.26)         # behind the cargo sacks, where Jonah sleeps
RAIL = (-0.22, -0.16)          # at the ship's rail, viewer side
PLANK_FOOT = (0.08, -0.20)     # the foot of the gangplank (on its stone)
PLANK_MID = (-0.04, -0.21)     # half way up the plank (y 0.04: the base height steps up in three small steps)
PLANK_TOP = (-0.16, -0.22)     # the plank's top on the bow (y 0.08)
SHAKE = (-0.49, -0.26)         # captain shaking Jonah awake: 0.19 from Jonah at CARGO, on his -X side
HEAVE = (-0.22, -0.26)         # captain 0.10 behind Jonah at the rail
PARK = (0.80, 0.30)            # hidden actors wait here (never visible: always hidden with prop(..., show=False))
SINK = (-0.06, 0.04)           # Jonah afloat in front of the fish, holding his nose (bubbles round him)
SINK_Y = 0.0                   # round 3: at -0.10 his feet showed under the paper; he now floats on the water
FISH_HIDE = (-0.62, 0.08)      # hidden fish waits here, just off the left edge of the sea
FISH_IN = (-0.62, 0.04)        # the fish enters from the left edge (the camera does not see x < -0.55)
FISH_GULP = (-0.34, 0.04)      # facing +X its mouth (0.24 ahead) is at -0.10, the 0.08 lunge reaches SINK
FISH_IN_SHORE = (-0.62, 0.10)
FISH_SHORE = (-0.30, 0.10)     # facing +X, its mouth is at the water's edge (x -0.06) in front of the beach
FISH_END = (-0.34, 0.08)       # the ending: low in the water at the left, waving to Jonah
FISH_END_Y = -0.05
BELLY = (-0.20, 0.08)          # inside the fish: the centre of the `belly` dome
GATE_SIDE = (0.16, -0.10)      # S09: he steps aside, so the kneeling townsfolk are not hidden behind him
GATE = (0.32, -0.16)           # in front of Nineveh's gate, well clear of the gatehouse (front z -0.378)
HILL = (0.42, 0.08)            # sitting under the shelter / plant on the hill
HILL_Y = 0.03                  # the hill top: seated clips must not sink into it

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "上帝的差事", "A job from God", "orbit", "beach", dist=0.9, height=0.42, yawDeg=-28,
         desc="Short orbit over the page: the sea and a little ship on the left, the great city on the right. "
              "Jonah stands on the road. A warm light falls on him: God is speaking."),
    music("call"),
    act("jonah", "idle", to=ROAD, face="viewer"),
    act("captain", "idle", to=CAPT_DECK, y=DECK, face="viewer"),
    act("fish", "idle", to=FISH_HIDE, face="viewer", snap=True), prop("fish", show=False),
    prop("coast/belly", show=False), prop("coast/plantSmall", show=False), prop("coast/plantBig", show=False),
    prop("coast/plantDry", show=False), prop("coast/worm", show=False), prop("coast/shelter", show=False),
    *[prop("coast/folk%d" % i, show=False) for i in range(1, 10)],
    prop("jonah/seaweed", show=False),
    pause(0.3),
    line("jn_01", "narrator", "很久以前，上帝对一个叫约拿的人说话了。",
         "Long ago, God spoke to a man called Jonah.",
         "Jonah 1:1", dir="storyteller opening, warm and curious, in one breath; a little lift on 上帝 / 'God spoke'",
         post=0.2),
    shot("S01b", "上帝的差事", "A job from God", "fixed", "jonah", dist=0.5, height=0.18, yawDeg=12,
         desc="Close on Jonah on the road, the city behind him. God's light falls on him; he looks up, then refuses."),
    fx("golden_rays", "jonah.root", dur=6.0), sfx("soft_chime"),
    act("jonah", "listen_up", face="viewer"),
    line("jn_02", "god", "约拿，起来！去尼尼微大城，告诉那里的人：不可以再做坏事了。",
         "Jonah, get up! Go to the great city of Nineveh, and tell the people there to stop doing wrong.",
         "Jonah 1:2", dir="God's voice: warm, calm, big but kind, like a loving father; never stern or echoing-scary",
         pre=0.4, post=0.3),
    act("jonah", "refuse", face="viewer"),
    line("jn_03", "jonah", "尼尼微？那些坏人？我才不去呢！",
         "Nineveh? Those bad people? No way. I'm not going!",
         "Jonah 1:3; 4:2", dir="grumpy and stubborn, arms crossed; a snort before 我才不去呢 / 'No way'; funny, not angry",
         pre=0.3, post=0.2),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "偷偷上船", "Running away", "follow", "jonah", dist=0.7, height=0.2, yawDeg=-25,
         desc="Jonah tiptoes the wrong way: down to the beach and up the gangplank onto a ship. The captain greets him."),
    music("runaway"),
    act("jonah", "tiptoe", to=BEACH, face="ship"),
    act("jonah", "walk", to=PLANK_FOOT, face="ship", dt=1.8),
    act("jonah", "walk", to=PLANK_MID, y=0.04, face="ship", dt=4.4),       # up the gangplank, not through the bow
    act("jonah", "walk", to=PLANK_TOP, y=0.08, face="ship", dt=5.2),
    act("jonah", "walk", to=JONAH_DECK, y=DECK, face="captain", dt=6.0),
    act("captain", "greet", face="jonah", dt=6.6),
    line("jn_04", "narrator", "约拿没有去尼尼微。他偷偷跑到海边，上了一条往相反方向开的船！",
         "But Jonah didn't go to Nineveh. He sneaked down to the sea and got on a ship going the opposite way!",
         "Jonah 1:3", dir="amused, a little conspiratorial; surprise on 相反方向 / 'the opposite way'", pre=0.3, post=0.2),
    line("jn_05", "captain", "欢迎上船！坐稳喽——开船啦！",
         "Welcome aboard! Hold on tight... we're off!",
         "Jonah 1:3", dir="a jolly, loud sea captain; big chest voice, a laugh in it; calls 开船啦 / 'we're off' like a shout "
                          "across the deck", pre=0.4, post=0.2),
    sfx("seagulls", dt=-1.0), fx("sea_wind", "stage", dur=5.0),
    act("jonah", "walk", to=CARGO, y=DECK, face="viewer", dt=-1.2),
    act("jonah", "lie_down", face="viewer", dt=-0.4),                     # lead-in: standing -> lying (1.33 s)
    act("jonah", "sleep_curl", face="viewer", dt=0.95),
    fx("zzz", "jonah.head", dur=6.0, dt=1.4),
    line("jn_06", "narrator", "约拿躲到货物后面，呼噜呼噜睡着了。",
         "Jonah hid behind the cargo, and soon he was snoring away.",
         "Jonah 1:5", dir="soft and sleepy, smiling; draw out 呼噜呼噜 / 'snoring'", pre=0.5, post=0.4),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "大风暴", "The big storm", "fixed", "ship", dist=0.66, height=0.28, yawDeg=-12,
         desc="The sky goes dark, rain and lightning, big waves. The captain fights the steering oar, then shakes Jonah awake."),
    music("storm"),
    fx("storm_rain", "stage", dur=14.0), fx("tension_dim", "stage", dur=14.0),   # first half: covers jn_07
    sfx("thunder", dt=0.3), sfx("rain_loop"), sfx("thunder", dt=6.0),
    act("captain", "steer_hard", face="viewer"),
    line("jn_07", "narrator", "忽然，上帝刮起了大风。轰隆隆！船摇啊摇，快要散架了！",
         "Suddenly God sent a great wind. Crash! Boom! The ship rocked and nearly broke apart!",
         "Jonah 1:4", dir="exciting, quick, wide-eyed; big on 轰隆隆 / 'Crash! Boom!'; thrilling, never frightening",
         pre=0.6, post=0.2),
    # second half, anchored to jn_07's end so it ends at the splash (+0.3 s) in zh and en alike; jn_07's new take is
    # shorter, so a fixed 34 s storm from S03's start ran on after "the wind stopped". The halves overlap a little
    # (the storm grows while the captain shakes Jonah).
    fx("storm_rain", "stage", dur=28.5, dt=-2.0), fx("tension_dim", "stage", dur=28.5, dt=-2.0),
    act("captain", "walk", to=SHAKE, y=DECK, face="jonah", dt=-1.0),
    act("captain", "shake_awake", face="jonah", dt=-0.2),
    line("jn_08", "captain", "喂！醒醒！这么大的风浪，你怎么还睡得着？快向你的上帝祷告啊！",
         "Hey! Wake up! How can you sleep in a storm like this? Get up and pray to your God!",
         "Jonah 1:6", dir="shouting over the wind, urgent, amazed; not angry at him, just desperate", pre=0.5, post=0.3),
    act("jonah", "wake_startled", face="captain", dt=-2.4),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "是我的错", "It's my fault", "fixed", "jonah", dist=0.58, height=0.2, yawDeg=18,
         desc="Jonah stands at the rail, head low. He owns up. The captain does not want to do it, but at last helps "
              "him over the side."),
    act("jonah", "walk", to=RAIL, y=DECK, face="captain"),
    act("captain", "walk", to=CAPT_DECK, y=DECK, face="jonah", dt=0.1),   # round 3: off Jonah's back, 0.23 apart
    act("captain", "idle", face="jonah", dt=0.9),
    act("jonah", "ashamed", face="captain", dt=1.3),
    line("jn_09", "jonah", "这风暴……是因为我。我在躲着上帝。把我扔进海里，风浪就会停了。",
         "This storm... it's because of me. I'm running away from God. Throw me into the sea, and the storm will stop.",
         "Jonah 1:9-12", dir="quiet, ashamed, honest; a swallow before 是因为我 / 'because of me'; brave on the last sentence",
         pre=1.4, post=0.4),
    act("captain", "refuse_hands", face="jonah"),
    line("jn_10", "captain", "扔下去？不行不行！……唉，上帝啊，请原谅我们！",
         "Throw you in? No, no, I can't! ...Oh, God, please forgive us!",
         "Jonah 1:13-14", dir="shocked, kind-hearted, torn; a groan on 唉; the prayer is a real plea", pre=0.3, post=0.0),
    act("captain", "walk", to=HEAVE, y=DECK, face="jonah", dt=-3.4),     # tandem: 0.10 behind Jonah at the rail
    act("captain", "heave", face="jonah", dt=-1.6),                      # eyes shut on "please forgive us"
    act("jonah", "fall_in", face="viewer", dt=-0.9),
    sfx("splash_big", dt=0.5), fx("splash", "coast.sea", dur=1.6, dt=0.5),
    sfx("rain_stop", dt=0.6), music("deep", dt=0.8),
    act("jonah", "sit_hold_nose", to=SINK, y=SINK_Y, face="viewer", dt=1.0, snap=True),   # afloat, holding his breath
    fx("bubbles", "jonah.root", dur=5.0, dt=1.1), fx("splash", "jonah.root", dur=1.0, dt=1.0),
    line("jn_11", "narrator", "扑通！约拿一掉进海里，风就停了，浪也静了。",
         "Splash! The moment Jonah hit the water, the wind stopped and the waves went calm.",
         "Jonah 1:15", dir="a pop on 扑通 / 'Splash', then hushed and amazed as everything goes still", pre=0.6, post=0.3),
    act("captain", "amazed", face="viewer", dt=-2.0),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "大鱼来了", "Here comes the fish", "fixed", "belly", dist=0.56, height=0.2, yawDeg=30,
         desc="Jonah bobs in the water holding his nose. A huge fish glides in from the left, rises, opens its "
              "enormous mouth... GULP. Then a little burp and a bubble."),
    line("jn_12", "narrator", "约拿往下沉啊沉……上帝派来了一条好大好大的鱼！",
         "Down, down sank Jonah... then God sent a great big fish!",
         "Jonah 1:17", dir="slow and floaty on the sinking; then wonder and a smile on 好大好大的鱼 / 'great big fish'",
         pre=0.3, post=0.2),
    act("fish", "swim", to=FISH_IN, face="jonah", dt=-4.6, snap=True), prop("fish", show=True, dt=-4.6),
    act("fish", "swim", to=FISH_GULP, face="jonah", dt=-4.5),
    fx("bubbles", "fish.jaw", dur=3.0, dt=-3.0), sfx("bubbles", dt=-3.0),
    act("fish", "gulp", face="jonah"),
    sfx("gulp", dt=1.15),
    prop("jonah", show=False, dt=1.27),                                   # `gulp` marker: the jaws snap shut on him
    act("jonah", "sit_hold_nose", to=BELLY, y=0.0, face="viewer", dt=1.3, snap=True),
    line("jn_13", "narrator", "啊呜——一口就把他吞进了肚子里！",
         "GULP! It swallowed him in one bite!",
         "Jonah 1:17", dir="big, comic, delighted; a real 啊呜 / 'gulp' sound", pre=1.0, post=0.1),
    act("fish", "burp", face="jonah"),                                    # stays side-on (facing the viewer its tail cut the hull)
    sfx("burp", dt=0.6), fx("bubbles", "fish.jaw", dur=2.0, dt=0.6),
    pause(0.8),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "鱼肚子里", "Inside the fish", "fixed", "jonah", dist=0.5, height=0.22, yawDeg=0,
         desc="Dark teal. Jonah sits inside the ribs of the fish, holds his nose, then sits back on his heels and "
              "prays. A soft light grows."),
    music("prayer"),
    prop("coast/belly", show=True),
    prop("fish", show=False), act("fish", "idle", to=FISH_HIDE, face="viewer", snap=True),
    prop("captain", show=False), act("captain", "idle", to=PARK, face="viewer", snap=True),
    prop("jonah", show=True),
    line("jn_14", "jonah", "呃……这里又黑又臭，还滑溜溜的！",
         "Ugh... it's dark in here, and stinky, and so slimy!",
         "Jonah 1:17", dir="comic disgust, holding his nose (nasal voice); a shudder on 滑溜溜 / 'slimy'", pre=0.5, post=0.3),
    # anchored to jn_14 (not to the shot) so it has faded out (1.5 s) before the cut to S07 in zh and en: when it ran
    # on into S07 its sky band showed as a hard-edged teal square from S07's camera (review item 11)
    fx("deep_glow", "stage", dur=22.0, dt=-4.0),
    line("jn_15", "narrator", "约拿在鱼肚子里待了三天三夜。他终于安静下来，向上帝祷告。",
         "Jonah stayed inside the fish for three days and three nights. At last he grew quiet, and he prayed.",
         "Jonah 1:17; 2:1", dir="calm, slowing down; gentle on 向上帝祷告 / 'he prayed'", pre=0.3, post=0.3),
    act("jonah", "kneel_pray", face="viewer", dt=-2.4),
    fx("prayer_glow", "jonah.chest", dur=10.0, dt=-1.0),
    line("jn_16", "jonah", "上帝啊，对不起，我不该逃跑。谢谢你没有丢下我。你说什么，我都愿意去做。",
         "Dear God, I'm sorry. I should not have run away. Thank You for not letting go of me. Whatever You say, I will do.",
         "Jonah 2:2-9", dir="a real prayer, soft and close; truly sorry, then thankful, then steady; breath before 谢谢你",
         pre=0.6, post=0.4),
    # S07 --------------------------------------------------------------------------------------------------------
    prop("jonah", show=False), act("jonah", "idle", to=BEACH, y=0.0, face="viewer", snap=True),   # hidden at the landing spot
    shot("S07", "吐到岸上", "Pfft! Onto the beach", "fixed", "beach", dist=0.62, height=0.24, yawDeg=28,
         desc="Daylight again. The fish swims to the shore and spits Jonah onto the sand. He sits up with seaweed on his head."),
    music("shore"),
    prop("coast/belly", show=False),
    prop("fish", show=True), act("fish", "swim", to=FISH_IN_SHORE, face="jonah", snap=True),
    act("fish", "swim", to=FISH_SHORE, face="jonah", dt=0.1),
    line("jn_17", "narrator", "上帝吩咐大鱼，大鱼就游到岸边——",
         "Then God spoke to the fish, and the fish swam up to the shore...",
         "Jonah 2:10", dir="building up to a joke; hold the last word", pre=0.6, post=0.1),
    act("fish", "spit", face="jonah"),
    sfx("spit_pop", dt=0.7), fx("splash", "coast.beach", dur=1.2, dt=0.8),
    prop("jonah", show=True, dt=0.7), prop("jonah/seaweed", show=True, dt=0.7),
    act("jonah", "tumble_out", to=BEACH, face="viewer", dt=0.7),
    line("jn_18", "narrator", "呸！把约拿吐在了沙滩上。",
         "PFFT! And spat Jonah out onto the sand.",
         "Jonah 2:10", dir="the punchline: a real 呸 / 'pfft', then a chuckle", pre=0.6, post=0.3),
    act("jonah", "sit_dazed", face="viewer"),
    act("fish", "wave_fin", face="jonah", dt=0.2),
    sfx("seagulls", dt=0.4),
    pause(0.6),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "这次我去", "This time I'll go", "follow", "jonah", dist=0.7, height=0.24, yawDeg=25,
         desc="God speaks again. Jonah stands, shakes off the seaweed, and marches to the great gate of Nineveh."),
    music("call"),
    prop("fish", show=False), act("fish", "idle", to=FISH_HIDE, face="viewer", snap=True),
    fx("golden_rays", "jonah.root", dur=5.0),
    act("jonah", "stand_up", face="viewer"),
    line("jn_19", "god", "约拿，起来，去尼尼微，把我的话告诉他们。",
         "Jonah, get up. Go to Nineveh, and give them My message.",
         "Jonah 3:1-2", dir="the same warm voice as before, patient, a hint of a smile: a second chance", pre=0.6, post=0.3),
    prop("jonah/seaweed", show=False),
    act("jonah", "nod_ok", face="viewer"),
    line("jn_20", "jonah", "好，上帝。这一次，我去。",
         "Yes, God. This time, I'll go.",
         "Jonah 3:3", dir="humble and sure; short; a deep breath first", pre=0.3, post=0.2),
    music("nineveh"),
    act("jonah", "walk", to=GATE, face="viewer", dt=-1.6),
    act("jonah", "proclaim", face="viewer", dt=1.5),
    line("jn_21", "jonah", "尼尼微的人哪，听着！你们做了太多坏事。再过四十天，这座城就要完了！",
         "People of Nineveh, listen! You have done so many wrong things. In forty days, this city will be destroyed!",
         "Jonah 3:4", dir="calling out to a whole city, hands cupped; loud and serious but not cruel", pre=1.8, post=0.3),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "全城都说对不起", "The whole city says sorry", "fixed", "gate", dist=0.62, height=0.26, yawDeg=-10,
         desc="The people of Nineveh come out in sackcloth and kneel in front of the gate, one after another, the king "
              "and the children too. Jonah, in front of them, blinks in surprise."),
    music("repent"),
    act("jonah", "walk", to=GATE_SIDE, face="viewer"),
    act("jonah", "surprised", face="viewer", dt=1.8),
    # set nodes folk1..9 (pipeline/jn_coast.py FOLK): kneeling townsfolk in sackcloth, popped in one by one
    prop("coast/folk2", show=True, dt=0.2, grow=0.5), prop("coast/folk5", show=True, dt=0.7, grow=0.5),
    prop("coast/folk8", show=True, dt=1.2, grow=0.5), prop("coast/folk1", show=True, dt=1.8, grow=0.5),
    prop("coast/folk4", show=True, dt=2.4, grow=0.5), prop("coast/folk6", show=True, dt=3.0, grow=0.5),
    prop("coast/folk3", show=True, dt=3.6, grow=0.5), prop("coast/folk9", show=True, dt=4.3, grow=0.5),
    line("jn_22", "people", "我们错了！上帝啊，求你原谅我们！",
         "We were wrong! O God, please forgive us!",
         "Jonah 3:5-9", dir="a big crowd behind a wall: men, women and children, ragged, heartfelt, not in unison", pre=0.5,
         post=0.3),
    act("jonah", "idle", face="viewer", dt=-3.0),
    shot("S09b", "全城都说对不起", "The whole city says sorry", "orbit", "gate", dist=0.62, height=0.3, yawDeg=-26,
         desc="A slow turn over the kneeling city as God's light breaks over it; Jonah watches, frowning."),
    prop("coast/folk7", show=True, dt=1.6, grow=0.5),                     # "...to the smallest child"
    line("jn_23", "narrator", "从国王到小孩子，全城的人都不再做坏事了。上帝看见了，就原谅了他们。",
         "From the king to the smallest child, everyone in the city stopped doing wrong. God saw it, and He forgave them.",
         "Jonah 3:5-10", dir="glad and gentle; warm and slow on 就原谅了他们 / 'He forgave them'", pre=0.3, post=0.2),
    fx("golden_rays", "coast.gate", dur=6.0, dt=-4.0), sfx("soft_chime", dt=-4.0),
    act("jonah", "stomp_walk", to=HILL, y=HILL_Y, face="viewer", dt=-1.8),   # he stomps off as God forgives them   # the kneeling townsfolk stay: the saved city is in the last shot
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "约拿生气了", "Jonah sulks", "fixed", "hill", dist=0.55, height=0.2, yawDeg=-25,
         desc="Jonah stomps up the little hill, plonks himself down and sulks, arms folded, steam over his head."),
    music("sulk"),
    prop("coast/shelter", show=True),
    act("jonah", "sit_sulk", face="viewer", dt=0.8),
    fx("steam", "jonah.head", dur=1.8, dt=1.3),
    line("jn_24", "jonah", "哼！我就知道！你太好心了，肯定会原谅他们。他们可是坏人哪！",
         "Hmph! I knew it! You are too kind. I knew You would forgive them. But they're the bad guys!",
         "Jonah 4:1-2", dir="sulky like a child who lost a game; loud 哼; whiny on the last sentence; funny", pre=1.3, post=0.3),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "一棵树和一条虫", "A plant and a worm", "fixed", "hill", dist=0.66, height=0.3, yawDeg=15,
         desc="A leafy plant shoots up beside Jonah and shades him: bliss. Next morning a little worm munches it. "
              "The plant droops, the sun beats down, Jonah wails."),
    music("plant"),
    # round 3: a sprout pops up (1.4 s), then the whole vine grows out of it (2.6 s) while the narrator says so
    prop("coast/plantSmall", show=True, dt=0.2, grow=1.4),
    fx("plant_grow", "coast.plantSmall", dur=1.6, dt=0.2),
    prop("coast/plantSmall", show=False, dt=1.9), prop("coast/plantBig", show=True, dt=1.9, grow=2.6),
    fx("plant_grow", "coast.plantBig", dur=2.6, dt=1.9),
    sfx("grow_whoosh", dt=0.2), sfx("grow_whoosh", dt=1.9),
    act("jonah", "relax_happy", face="viewer", dt=4.0),
    line("jn_25", "narrator", "上帝让一棵树长出来，给约拿遮太阳。约拿可高兴了：啊，真凉快！",
         "God made a leafy plant grow up to shade Jonah from the sun. Jonah was so happy. Ahh, lovely and cool!",
         "Jonah 4:6", dir="light and playful; a contented sigh on 啊真凉快 / 'lovely and cool'", pre=0.6, post=0.3),
    shot("S11b", "一棵树和一条虫", "A plant and a worm", "fixed", "worm", dist=0.32, height=0.1, yawDeg=-25,
         desc="Close on the stem: a little worm pops out and munches, munch, munch. The leaves go limp and dry."),
    prop("coast/worm", show=True, dt=1.6, grow=0.4),
    sfx("munch", dt=3.8),
    line("jn_26", "narrator", "可是第二天，来了一条小虫子。咔嚓咔嚓——把树咬坏了。太阳晒得约拿头都晕了。",
         "But the next day, along came a little worm. Munch, munch... and the plant dried up. The hot sun beat down on "
         "Jonah's head.",
         "Jonah 4:7-8", dir="mischievous on the worm (咔嚓咔嚓 / 'munch munch'), then hot and droopy", pre=0.3, post=0.2),
    prop("coast/plantBig", show=False, dt=-4.2), prop("coast/plantDry", show=True, dt=-4.2),
    prop("coast/worm", show=False, dt=-3.0),
    fx("sun_scorch", "jonah.head", dur=7.0, dt=-2.8), sfx("cicadas_heat", dt=-2.8),
    act("jonah", "wail", face="plantDry", dt=-2.6),
    shot("S11c", "一棵树和一条虫", "A plant and a worm", "fixed", "hill", dist=0.55, height=0.22, yawDeg=-12,
         desc="Jonah throws up his arms at the dry plant and wails."),
    fx("sweat", "jonah.head", dur=1.4, dt=0.1),
    line("jn_27", "jonah", "我的树！我可怜的树啊！",
         "My plant! My poor, poor plant!",
         "Jonah 4:8-9", dir="over-the-top wailing, comic; voice cracks", pre=0.2, post=0.4),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "上帝的心", "God's big heart", "fixed", "hill", dist=0.58, height=0.22, yawDeg=22,
         desc="Golden light. Jonah, still sitting under the dry vine, looks up and listens, and slowly understands."),
    music("mercy"),
    fx("golden_rays", "jonah.root", dur=8.0),
    # round 3: he stays seated (standing up under the dry vine, its limp leaves went through him) and the camera is
    # on his right, so the vine is behind him, not across his face
    act("jonah", "relax_happy", face="viewer"),
    line("jn_28", "god", "约拿，你心疼这棵树。尼尼微有十二万多人，还有好多牛羊，我能不心疼吗？",
         "Jonah, you care about this plant. Nineveh has over a hundred and twenty thousand people, and many animals "
         "too. Should I not care about them?",
         "Jonah 4:10-11", dir="very gentle, a father explaining; a small smile on 还有好多牛羊 / 'animals too'; the question "
                            "is tender, not scolding", pre=0.6, post=0.5),
    fx("heart_glow", "jonah.chest", dur=5.0, dt=-1.5),
    shot("S12b", "上帝的心", "God's big heart", "fixed", "beach", dist=0.95, height=0.5, yawDeg=8,
         desc="The whole page from the front: Jonah turns to the child and waves; far out at sea the fish waves a fin."),
    prop("fish", show=True), act("fish", "wave_fin", to=FISH_END, y=FISH_END_Y, face="jonah", snap=True),
    prop("coast/plantDry", show=False, grow=1.0),                         # the dry vine shrivels away; then he stands
    act("jonah", "stand_up", face="viewer", dt=0.4),
    act("jonah", "wave", face="viewer", dt=2.4),
    line("jn_29", "narrator", "上帝爱每一个人，做错了事，他也愿意再给一次机会。约拿是这样，你和我也是。",
         "God loves every person. When we do wrong, He gives another chance. He did for Jonah, and He does for you "
         "and me.",
         "Jonah 4:2, 4:11", dir="warm moral, speaking right to the child; smile on the last sentence", pre=0.5, post=0.4),
    pause(1.0),
]
