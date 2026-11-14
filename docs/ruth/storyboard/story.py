"""Ruth — the play, as beats relative to each other (docs/ruth/CONTRACT.md §5).

`tools/story/build_timeline.py ruth` turns this into assets/ruth/timeline.json, placing every line by the real voice
durations. Same helpers as Esther: shot / line / act / fx / sfx / music / prop / pause (see docs/esther/storyboard/story.py).
Marks are art-width units on the page (x right, z toward the viewer; the set's marks are in docs/ruth/CONTRACT.md §6).

Lines are spoken paraphrases of the Book of Ruth for ages 4-10, written to be *said*, not read: short sentences,
little words that people really use (呀、啦、呢、哎呀、嘘), characters talking to each other rather than a narrator
explaining. `dir` is the acting note for the voice. Child-friendly: the deaths are one gentle sentence, the night at the
threshing floor is Ruth asking Boaz for help (no lying at his feet), the elders at the gate are one narrator line.
"""
from tools_story import shot, line, act, fx, sfx, music, prop, pause   # provided by build_timeline.py

ID = "ruth"
CAST = ["ruth", "naomi", "boaz"]
SET = "bethlehem"

# stage marks (CONTRACT.md §6)
ROAD_IN = (-0.62, 0.20)      # off the left edge of the page: the road from Moab
ROAD_A = (-0.40, 0.16)       # on the road, front left
ROAD_B = (-0.28, 0.14)
DOOR = (-0.30, -0.20)        # in front of Naomi's door
DOOR_RUTH = (-0.18, -0.16)
GLEAN = (0.14, 0.10)         # stubble at the front edge of the field, where Ruth gleans
GLEAN2 = (0.24, 0.12)        # a little further along
BOAZ_IN = (0.62, 0.18)       # off the right edge
BOAZ_A = (0.40, 0.16)        # Boaz in the field
BOAZ_TALK = (0.30, 0.13)     # Boaz talking with Ruth at the field edge
WATER = (-0.34, -0.02)       # water jars under the olive tree
THRESH = (0.14, -0.30)       # in front of the threshing floor
THRESH_RUTH = (0.00, -0.22)
WED_BOAZ = (0.06, 0.08)      # wedding marks, centre front
WED_RUTH = (-0.06, 0.08)
WED_NAOMI = (-0.24, -0.04)   # near her door: her tired walk is slow (0.037 u/s)

SEQUENCE = [
    # S01 --------------------------------------------------------------------------------------------------------
    shot("S01", "从摩押回家", "The long road home", "orbit", "all", dist=0.9, height=0.40, yawDeg=-30,
         desc="Slow orbit over the page in pale dawn light: Bethlehem's hills, the stone house, the golden field. "
              "Two small figures come in on the road at the left edge."),
    music("road_sad"),
    fx("dust_road", "stage", dur=6.0, dt=1.0),
    act("boaz", "idle", to=(0.70, 0.18), face="viewer"),               # parked off-page until S05
    act("naomi", "walk_tired", to=ROAD_A, face="viewer"),
    act("ruth", "walk", to=ROAD_B, face="viewer", dt=0.4),
    prop("ruth/sheaf", show=False), prop("ruth/stalks", show=False), prop("naomi/baby", show=False), prop("naomi/staff", show=True),
    prop("boaz/stalks", show=False), prop("bethlehem/dropped", show=False), prop("bethlehem/canopy", show=False),
    pause(1.6),
    line("ru_01", "narrator", "很久以前，拿俄米的丈夫和两个儿子……都去世了。只剩下儿媳妇路得，陪着她。",
         "Long ago, Naomi's husband and her two sons died... and only Ruth, her son's wife, stayed with her.",
         "Ruth 1:1-5", dir="storyteller opening; soft and slow, a real pause before 都去世了 / 'had died'; tender, never gloomy",
         post=0.4),
    act("naomi", "sad", face="ruth"),
    act("ruth", "idle", face="naomi"),
    # S02 --------------------------------------------------------------------------------------------------------
    shot("S02", "你往哪里去", "Where you go, I will go", "fixed", "naomi", dist=0.6, height=0.18, yawDeg=25,
         desc="Close on the two women on the road. Naomi gently pushes Ruth away; Ruth will not go."),
    act("naomi", "send_away", face="ruth"),
    line("ru_02", "naomi", "路得啊……我要回伯利恒老家了。你还年轻，回你娘家去吧，啊？",
         "Ruth, my dear... I'm going home to Bethlehem. You're still young. Go back to your mother's house, all right?",
         "Ruth 1:8-9", dir="tired, loving, a little choked; a sigh before she starts; the last 啊 / 'all right' is soft, almost begging",
         pre=0.5, post=0.6),
    act("ruth", "shake_head", face="naomi", dt=-0.4),
    act("ruth", "hold_hands", face="naomi", dt=0.6),
    act("naomi", "listen_moved", face="ruth", dt=0.6),
    fx("heart_glow", "ruth.chest", dur=6.0, dt=2.4, to="naomi.chest"),
    line("ru_03", "ruth", "不，我不走！你往哪里去，我也往哪里去；你住在哪里，我也住在哪里。你的上帝……就是我的上帝。",
         "No, I won't leave you! Where you go, I will go. Where you stay, I will stay. Your God... will be my God.",
         "Ruth 1:16", dir="heartfelt, close to tears but steady; quick and firm on 不我不走, then slower and warmer; "
                         "a breath before 你的上帝 / 'Your God'; the most important line in the story",
         pre=0.9, post=0.6),
    act("naomi", "hug", face="ruth"),
    act("ruth", "hug", face="naomi"),
    sfx("soft_chime"),
    pause(1.4),
    # S03 --------------------------------------------------------------------------------------------------------
    shot("S03", "回到伯利恒", "Back in Bethlehem", "follow", "naomi", dist=0.78, height=0.26, yawDeg=-20,
         desc="They walk on together to the stone house; the barley field shines gold behind them."),
    music("journey"),
    act("naomi", "walk_tired", to=DOOR, face="viewer"),
    act("ruth", "walk", to=DOOR_RUTH, face="naomi", dt=0.3),
    line("ru_04", "narrator", "她们走呀走，走了好远好远的路，终于回到了伯利恒。那时候，正是收大麦的季节。",
         "They walked and walked, a long, long way, and at last they came to Bethlehem. "
         "It was barley harvest time.",
         "Ruth 1:19, 1:22", dir="the walking rhythm in the voice (走呀走); brighter on 终于 / 'at last'; "
                                 "a small smile on the harvest", pre=0.3, post=0.3),
    act("naomi", "sad", face="viewer"),
    line("ru_05", "naomi", "唉……我走的时候，什么都有。回来的时候……什么都没有了。",
         "Oh... when I left, I had everything. Now I've come home... with nothing.",
         "Ruth 1:21", dir="a long sigh first; quiet, empty; slow, with a break before the second half", pre=0.6, post=0.5),
    act("ruth", "cheer_up", face="naomi"),
    line("ru_06", "ruth", "婆婆，别难过。我去田里拾麦穗，咱们就有饭吃啦！",
         "Don't be sad, Mother. I'll go and pick up grain in the fields, then we'll have food to eat!",
         "Ruth 2:2", dir="gentle first, then bright and eager, a little smile; quicker at the end", pre=0.3, post=0.4),
    act("naomi", "nod", face="ruth"),
    pause(0.4),
    # S04 --------------------------------------------------------------------------------------------------------
    shot("S04", "拾麦穗", "Gleaning", "orbit", "ruth", dist=0.62, height=0.2, yawDeg=30,
         desc="Morning light over the field. Ruth kneels at the edge and picks up the stalks the reapers left, one by one."),
    music("field"),
    fx("chaff", "bethlehem.field", dur=999),
    sfx("birds", dt=0.2),
    act("naomi", "idle", to=(-0.40, -0.22), face="viewer"),
    act("ruth", "walk", to=GLEAN, face="viewer"),
    act("ruth", "kneel", face="viewer", dt=2.6),
    act("ruth", "glean", face="viewer", dt=3.6),
    prop("ruth/stalks", show=True, dt=4.4),
    sfx("rustle", dt=4.4),
    line("ru_07", "narrator", "在以色列，割麦子的人会故意留下一些麦穗，给穷人捡。路得就跪在田边，一根一根地拾。",
         "In Israel, the harvesters left some grain behind for poor people to pick up. "
         "So Ruth knelt at the edge of the field and picked it up, one stalk at a time.",
         "Ruth 2:2-3; Leviticus 19:9-10", dir="calm and explaining, like a parent pointing at a picture; "
                                             "slow on 一根一根 / 'one stalk at a time'", pre=2.0, post=0.4),
    sfx("rustle", dt=-1.6),
    # S05 --------------------------------------------------------------------------------------------------------
    shot("S05", "田的主人", "The owner of the field", "follow", "boaz", dist=0.72, height=0.16, yawDeg=-25,
         desc="Boaz strides in from the right, greeting his workers; then he notices the young woman."),
    music("boaz"),
    act("boaz", "walk", to=BOAZ_A, face="viewer"),
    line("ru_08", "narrator", "这块田的主人，叫波阿斯。他是个又有钱、又善良的好人。",
         "The field belonged to a man named Boaz. He was rich, and he was very kind.",
         "Ruth 2:1, 2:3", dir="warm, a little admiring", pre=0.6, post=0.2),
    act("boaz", "greet", face="viewer"),
    line("ru_09", "boaz", "大家辛苦啦！愿上帝和你们同在！",
         "Good morning, everyone! The Lord be with you!",
         "Ruth 2:4", dir="hearty and friendly, loud enough to carry across a field; a big smile", pre=0.3, post=0.1),
    line("ru_10", "reapers", "也愿上帝赐福给你！",
         "The Lord bless you too!",
         "Ruth 2:4", dir="three or four workers answering together from across the field, cheerful, slightly ragged, "
                         "not in perfect unison", pre=0.1, post=0.4),
    act("boaz", "look_curious", face="ruth"),
    line("ru_11", "boaz", "咦？那个姑娘是谁呀？",
         "Hm? Who's that young woman over there?",
         "Ruth 2:5", dir="he stops mid-step, curious and gentle; a thinking 咦 / 'hm' first", pre=0.8, post=0.3),
    pause(0.3),
    # S06 --------------------------------------------------------------------------------------------------------
    shot("S06", "你为什么对我这么好", "Why are you so kind?", "fixed", "all", dist=0.62, height=0.18, yawDeg=15,
         desc="Boaz walks over to Ruth. She stands, then bows low, surprised he notices her."),
    act("boaz", "walk", to=BOAZ_TALK, face="ruth"),
    act("ruth", "stand_up", face="boaz", dt=0.4),
    act("boaz", "talk_kind", face="ruth", dt=1.6),
    line("ru_12", "boaz", "姑娘，你就在我的田里拾吧，别去别处了。渴了，就去那边罐子里喝水。",
         "Stay here and gather in my field. Don't go anywhere else. And when you're thirsty, "
         "go and drink from the water jars.",
         "Ruth 2:8-9", dir="kind, fatherly, unhurried; points toward the jars on 那边 / 'water jars'", pre=1.8, post=0.4),
    act("ruth", "bow_kneel", face="boaz"),
    line("ru_13", "ruth", "我是外地来的……您为什么对我这么好呢？",
         "I'm a stranger here... why are you so kind to me?",
         "Ruth 2:10", dir="shy, amazed, almost a whisper; the question rises gently", pre=0.6, post=0.4),
    act("boaz", "hand_on_heart", face="ruth"),
    line("ru_14", "boaz", "你对婆婆的好，我都听说了。愿上帝好好报答你！",
         "I've heard all about how good you've been to Naomi. May God reward you for it!",
         "Ruth 2:11-12", dir="warm and moved; a smile in the voice; the blessing a little slower", pre=0.3, post=0.5),
    act("ruth", "stand_up", face="boaz"),
    act("ruth", "shy", face="boaz", dt=1.8),
    pause(0.5),
    # S07 --------------------------------------------------------------------------------------------------------
    shot("S07", "故意掉麦穗", "Oops, more grain!", "fixed", "boaz", dist=0.58, height=0.14, yawDeg=-35,
         desc="Comic beat: Boaz looks left and right, then 'accidentally' drops handfuls of barley behind his back for Ruth."),
    music("sneaky"),
    act("ruth", "walk", to=GLEAN2, face="viewer"),
    act("ruth", "kneel", face="viewer", dt=1.2),
    act("ruth", "glean", face="viewer", dt=2.2),
    act("boaz", "walk", to=(0.38, 0.06), face="viewer", dt=0.2),
    act("boaz", "sneaky_drop", face="viewer", dt=1.2),
    prop("boaz/stalks", show=True, dt=1.2),
    prop("boaz/stalks", show=False, dt=4.67), prop("bethlehem/dropped", show=True, dt=4.67),
    fx("stalks_fall", "boaz.handR", dur=1.2, dt=4.57), sfx("stalks_drop", dt=4.75),
    line("ru_15", "boaz", "嘘——割麦子的时候，故意多掉一些……留给她捡！嘿嘿。",
         "Listen... when you cut the barley, drop a little extra on purpose... for her to pick up! Heh heh.",
         "Ruth 2:15-16", dir="stage whisper, playful, a grin; slow and secretive, then a cheeky lift on 留给她捡 / 'for her'",
         pre=1.4, post=0.2),
    act("boaz", "chuckle", face="viewer", dt=-1.0),
    pause(1.6),
    # S08 --------------------------------------------------------------------------------------------------------
    shot("S08", "满满一大捆", "A great big bundle", "follow", "ruth", dist=0.7, height=0.22, yawDeg=20,
         desc="Golden evening. Ruth carries a huge bundle of barley home; Naomi's eyes go wide."),
    music("home"),
    fx("sunset_glow", "stage", dur=26.0),
    sfx("crickets_dusk", dt=0.5),
    prop("ruth/stalks", show=False), prop("bethlehem/dropped", show=False),
    prop("ruth/sheaf", show=True),
    act("ruth", "carry_walk", to=DOOR_RUTH, face="naomi"),
    act("boaz", "walk", to=(0.08, 0.03), face="viewer", dt=0.5),       # off-camera: round the field, not through it
    act("naomi", "walk_tired", to=DOOR, face="ruth"),
    act("naomi", "idle", face="ruth", dt=3.4),
    line("ru_16", "narrator", "到了晚上，路得捡了满满一大捆大麦！",
         "By evening, Ruth had gathered a great big bundle of barley!",
         "Ruth 2:17", dir="building delight; big and round on 满满一大捆 / 'great big bundle'", pre=0.6, post=0.2),
    act("ruth", "show_bundle", face="naomi"),
    act("naomi", "surprised", face="ruth", dt=0.3),
    line("ru_17", "naomi", "哇！这么多呀！你今天……在谁的田里拾的？",
         "Oh my! So much! Whose field were you working in today?",
         "Ruth 2:19", dir="genuinely amazed, the first time she sounds happy; laughs a little on 这么多呀 / 'so much'",
         pre=0.6, post=0.3),
    act("ruth", "talk", face="naomi"),
    line("ru_18", "ruth", "一个叫波阿斯的人。他对我可好啦！",
         "A man called Boaz. He was so kind to me!",
         "Ruth 2:19", dir="happy, a bit breathless, proud", pre=0.2, post=0.3),
    act("boaz", "walk", to=THRESH, face="viewer"),                      # off-camera, left of the field wall
    act("naomi", "bless_up", face="viewer"),
    fx("sparkle", "naomi.head", dur=1.6, dt=0.8), sfx("sparkle", dt=0.8),
    line("ru_19", "naomi", "波阿斯？他是我们的亲人哪！感谢上帝……他没有忘记我们！",
         "Boaz? Why, he's family! Thank God... He hasn't forgotten us!",
         "Ruth 2:20", dir="surprise turning into joy and thankful tears; a catch in the voice before 他没有忘记我们", pre=0.3,
         post=0.6),
    act("naomi", "idle", face="ruth"),
    act("ruth", "joy", face="naomi"),
    # S09 --------------------------------------------------------------------------------------------------------
    shot("S09", "打谷场的夜晚", "Night at the threshing floor", "fixed", "boaz", dist=0.7, height=0.24, yawDeg=-20,
         desc="Night. Stars, a little oil lamp by the grain heap. Ruth comes quietly to Boaz and asks for help."),
    music("night"),
    fx("night", "stage", dur=24.0),
    fx("lamp_flame", "bethlehem.lampFlame", dur=24.0),
    sfx("crickets_night"),
    prop("ruth/sheaf", show=False),
    act("boaz", "idle", to=THRESH, face="viewer"),
    act("naomi", "idle", face="ruth"),
    line("ru_20", "narrator", "拿俄米想：要是波阿斯能照顾路得，那该多好啊！一天晚上，路得去打谷场找波阿斯。",
         "Naomi thought, 'If only Boaz would take care of Ruth!' So one night, Ruth went to find Boaz at the threshing floor.",
         "Ruth 3:1-6", dir="hushed, night-time, a little secret and hopeful", pre=0.8, post=0.2),
    act("ruth", "walk", to=THRESH_RUTH, face="boaz", dt=-3.4),
    act("ruth", "ask_humble", face="boaz"),
    act("boaz", "listen", face="ruth"),
    line("ru_21", "ruth", "波阿斯，您是我们的亲人……求您照顾我们一家，好吗？",
         "Boaz, you're part of our family... will you please take care of us?",
         "Ruth 3:9", dir="soft, nervous, brave; small breath before 求您 / 'will you please'", pre=0.5, post=0.5),
    act("boaz", "talk_kind", face="ruth"),
    line("ru_22", "boaz", "女儿，别怕。大家都知道，你是个好女子。我一定照顾你们！",
         "Don't be afraid, my daughter. Everyone knows you're a good woman. I will take care of you, I promise!",
         "Ruth 3:10-11", dir="very gentle, then firm and sure on the promise; a smile", pre=0.3, post=0.6),
    act("ruth", "shy", face="boaz"),
    pause(0.6),
    # S10 --------------------------------------------------------------------------------------------------------
    shot("S10", "婚礼", "The wedding", "orbit", "all", dist=0.66, height=0.3, yawDeg=25,
         desc="Morning again: a canopy with flowers. Boaz and Ruth stand together; petals fall; Naomi claps."),
    music("wedding"),
    prop("bethlehem/canopy", show=True),
    act("boaz", "walk", to=WED_BOAZ, face="ruth"),
    act("ruth", "walk", to=WED_RUTH, face="boaz", dt=0.2),
    act("naomi", "walk_tired", to=WED_NAOMI, face="ruth", dt=0.2),
    fx("petals", "bethlehem.canopy", dur=6.0, dt=1.6), sfx("cheer", dt=1.6),
    act("boaz", "joy", face="ruth", dt=2.4), act("ruth", "joy", face="boaz", dt=2.4),
    act("naomi", "clap", face="ruth", dt=4.4), prop("naomi/staff", show=False, dt=4.4),
    line("ru_23", "narrator", "后来，波阿斯娶了路得。全城的人都来祝福他们！",
         "And so Boaz married Ruth. The whole town came to celebrate with them!",
         "Ruth 4:9-13", dir="bright and happy, a smile you can hear", pre=2.4, post=0.6),
    sfx("tambourine", dt=-1.0),
    # S11 --------------------------------------------------------------------------------------------------------
    shot("S11", "小宝宝", "A baby boy", "fixed", "naomi", dist=0.55, height=0.2, yawDeg=-15,
         desc="Naomi holds the new baby and rocks him; Ruth and Boaz beside her."),
    music("lullaby"),
    prop("bethlehem/canopy", show=False),
    prop("naomi/baby", show=True),
    act("naomi", "hold_baby", face="viewer"),
    act("ruth", "idle", face="naomi"), act("boaz", "idle", face="naomi"),
    fx("sparkle", "naomi.baby", dur=1.8, dt=0.4), sfx("baby_coo", dt=0.6),
    line("ru_24", "narrator", "不久，他们生了一个小宝宝，名字叫俄备得。",
         "Before long, they had a baby boy. They named him Obed.",
         "Ruth 4:13, 4:17", dir="soft and tender, like looking into a cradle; slow on the name", pre=1.0, post=0.3),
    line("ru_25", "naomi", "我的小孙子……上帝真的没有忘记我！",
         "My little grandson... God really didn't forget me!",
         "Ruth 4:14-16", dir="happy tears, half laughing; rocking rhythm; the last words full of wonder", pre=0.4, post=0.6),
    # S12 --------------------------------------------------------------------------------------------------------
    shot("S12", "大卫的曾祖母", "David's great-grandmother", "orbit", "all", dist=0.72, height=0.26, yawDeg=-10,
         desc="The family faces the child; golden rays; Ruth waves."),
    music("finale"),
    act("ruth", "walk", to=(-0.02, 0.14), face="viewer"),
    act("boaz", "walk", to=(0.14, 0.08), face="viewer"),
    act("boaz", "idle", face="viewer", dt=1.2),
    act("naomi", "hold_baby", face="viewer"),
    line("ru_26", "narrator", "你知道吗？俄备得长大以后，有个孙子叫大卫——就是打败歌利亚的那个大卫！",
         "And guess what? When Obed grew up, he had a grandson named David. Yes, the David who beat Goliath!",
         "Ruth 4:17, 4:22", dir="playful, leaning in to share a secret; a big happy reveal on 大卫 / 'David'", pre=0.6, post=0.5),
    act("ruth", "wave", face="viewer"),
    fx("golden_rays", "ruth.root", dur=7.0, dt=0.2),
    line("ru_27", "narrator", "路得对婆婆不离不弃，上帝也一直看顾着她们。你也可以好好爱你的家人哦！",
         "Ruth never left Naomi, and God took care of them all along. You can love your family like that too!",
         "Ruth 1:16, 2:12", dir="warm moral, speaking right to the child; smile on the last sentence", pre=0.6, post=2.2),
]
