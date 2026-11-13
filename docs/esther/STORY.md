# Esther — the brave queen (story pack #2)

Third colouring sheet, second story pack (`docs/STORY-ARCHITECTURE.md`). The child colours the sheet, the app scans it
and three rigged characters wearing the child's colours act out the story on the page, in zh or en, about 95 s.

Source: the Book of Esther (public domain text). Lines are child-friendly paraphrases with the verse each comes from;
nothing is quoted from any film or other retelling. Audience: ages 4-10, so the plot against the Jews is "wanted to
hurt God's people", nobody is hanged on screen (Haman is led away), and the fasting is "prayed for three days".

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `esther` | Queen Esther, young, brave, kind | front, centre | warm young woman |
| `king` | King Xerxes (Ahasuerus) with the golden sceptre | back, on the throne steps | deep, slow, kind when calm |
| `haman` | Haman, the king's proud official | right side | sly, high-ish, never scary |
| `mordecai` | Mordecai, Esther's cousin who raised her | not drawn (voice from off-stage) | gentle older man |
| `narrator` | | | storyteller (same voice as David & Goliath) |

## Beats (12 shots, ~95 s)

| Shot | Title zh / en | What happens |
|---|---|---|
| S01 | 书珊城的王宫 / The palace of Susa | slow orbit over the page: throne, columns, curtains, braziers |
| S02 | 新王后 / The new queen | Esther steps forward, the crown sparkles |
| S03 | 骄傲的哈曼 / Proud Haman | Haman struts, demands bows |
| S04 | 坏主意 / A bad plan | Haman whispers to the king; the king hands him his ring |
| S05 | 为了这样的时候 / For such a time as this | Mordecai's voice from off-stage; Esther thinks |
| S06 | 勇敢的决定 / A brave choice | Esther prays, then stands tall |
| S07 | 走向王座 / Walking to the throne | tense walk up the steps, drums |
| S08 | 金杖 / The golden sceptre | the king holds out the sceptre: she lives! |
| S09 | 宴席 / The banquet | low table, goblets; Esther tells the truth |
| S10 | 真相 / The truth | the king stands up angry; Haman shrinks and is led away |
| S11 | 得救了 / Saved! | joy, confetti, music turns bright |
| S12 | 勇气和信靠 / Courage and trust | Esther and the king face the child; moral |

## Lines

The 18 lines, their delivery notes and every beat live in `storyboard/story.py` (single source); the generated table
with timings is `STORYBOARD.md`. They are spoken paraphrases, written to be read aloud to a child: short sentences,
natural pauses ("……"), small interjections ("哼！", "嗯……", "Hmph!"), and each character's own voice (Haman puffed-up
and comic, the king slow and deep, Esther hesitant then brave). Every line keeps its verse reference.

Child-friendly cuts: no gallows (7:9-10 becomes "taken away"), no killing in chapter 9, Vashti (chapter 1) is left
out. The en lines keep "Xerxes" (the name most children's Bibles use); zh keeps 亚哈随鲁 (和合本).
