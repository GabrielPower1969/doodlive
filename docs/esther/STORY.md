# Esther — the brave queen (story pack #2)

Third colouring sheet, second story pack (`docs/STORY-ARCHITECTURE.md`). The child colours the sheet, the app scans it
and three rigged characters wearing the child's colours act out the story on the page, in zh or en, about 3.5 minutes.

Source: the Book of Esther (public domain text). Lines are child-friendly paraphrases with the verse each comes from;
nothing is quoted from any film or other retelling. Audience: ages 4-10, so the plot against the Jews is "wanted to
hurt God's people", nobody is hanged on screen (Haman is led away), and the fasting is "prayed for three days".

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `esther` | Queen Esther, young, brave, kind | front, centre | warm young woman |
| `king` | King Xerxes (Ahasuerus) with the golden sceptre | back, on the throne steps | deep, slow, kind when calm |
| `haman` | Haman, the king's proud official: a vain, cowardly peacock children laugh at (`HAMAN-REWORK.md`) | right side | comic actor: gloats, laughs, rages, wails; never scary |
| `mordecai` | Mordecai, Esther's cousin who raised her | not drawn (voice from off-stage) | gentle older man |
| `guard1`, `guard2` | the king's guards who take Haman away (S10) | not drawn: fixed painted texture | (no lines) |
| `herald` | court crier announcing Haman (S03) | off-stage | loud, ceremonial |
| `crowd` | people bowing to Haman (S03) | off-stage | many voices at once |
| `narrator` | | | storyteller (same voice as David & Goliath) |

## Beats (15 shots, ~3.5 min)

| Shot | Title zh / en | What happens |
|---|---|---|
| S01 | 书珊城的王宫 / The palace of Susa | slow orbit over the page: throne, columns, curtains, braziers |
| S02 | 新王后 / The new queen | Esther steps forward, the crown sparkles |
| S03 | 骄傲的哈曼 / Proud Haman | fanfare, herald, crowd bows; Haman parades, preens, laughs at his own greatness; Mordecai won't bow: tantrum with steam |
| S04 | 坏主意 / A bad plan | Haman whispers to the king; the king hands him his ring; Haman gloats at the audience |
| S05 | 为了这样的时候 / For such a time as this | Mordecai's voice from off-stage; Esther thinks |
| S06 | 勇敢的决定 / A brave choice | Esther prays, then stands tall |
| S07 | 走向王座 / Walking to the throne | tense walk up the steps, drums |
| S08 | 金杖 / The golden sceptre | the king holds out the sceptre: she lives! |
| S08b | 得意忘形 / Puffed up | invited to the banquet, Haman skips and boasts |
| S08c | 王要尊荣的人 / The man the king honours | Haman thinks the honour is his and describes a grand parade; it is for Mordecai |
| S08d | 满城大喊 / Through the streets | Haman sulks through the city leading Mordecai's horse, shouting through his teeth |
| S09 | 宴席 / The banquet | low table, goblets; Esther tells the truth |
| S10 | 真相 / The truth | the king stands up angry; Haman jumps, begs on his knees; guards drag him off kicking and wailing |
| S11 | 得救了 / Saved! | joy, confetti, music turns bright |
| S12 | 勇气和信靠 / Courage and trust | Esther and the king face the child; moral |

## Lines

The 32 lines, their delivery notes and every beat live in `storyboard/story.py` (single source); the generated table
with timings is `STORYBOARD.md`. They are spoken paraphrases, written to be read aloud to a child: short sentences,
natural pauses ("……"), small interjections ("哼！", "嗯……", "Hmph!"), and each character's own voice (Haman puffed-up
and comic, the king slow and deep, Esther hesitant then brave). Every line keeps its verse reference.

Child-friendly cuts: no gallows (7:9-10 becomes "taken away" by the guards, off the page), no killing in chapter 9, Vashti (chapter 1) is left
out. The en lines keep "Xerxes" (the name most children's Bibles use); zh keeps 亚哈随鲁 (和合本).
