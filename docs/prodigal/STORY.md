# The prodigal son — the son who came home (story pack #6)

Seventh colouring sheet, sixth story pack (`docs/STORY-ARCHITECTURE.md`). The child colours the sheet, the app scans
it and three rigged characters wearing the child's colours act out Jesus's parable of the lost son, in zh or en.

Source: Luke 15:11-32 (public domain text). Every line is a child-friendly spoken paraphrase with the verse it comes
from; nothing is quoted from any film or other retelling. Audience: ages 4-10. Period research and mood (a Galilean
farmstead, a Hellenistic "far country" city with a tavern, the pig pen in a famine, the long road home at evening, a
night feast with lamps) were taken from public sources and a reference viewing; characters, set, music and words are
original.

Title: **浪子回家 / The Son Who Came Home**

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `son` | the younger son: cocky and fun-loving, then broke and humbled, then overjoyed | front, centre | young man, bright and cheeky, later small and sorry |
| `father` | the father: grey beard, gentle, patient, runs to his son | front, left | warm older man, kind, with a catch in his voice |
| `brother` | the elder son: hard-working, a bit grumpy, feels left out | front, right | firm young man, grumbling, then softer |
| `friends` | the son's party friends in the far country (off-stage group) | not drawn | 3-4 voices, giggly then off-hand |
| `servants` | the father's servants (off-stage group) | not drawn | 2-3 voices, eager |
| `narrator` | | | storyteller (same as the other packs) |

## Beats (14 shots, about 4 minutes)

| Shot | Title zh / en | What happens |
|---|---|---|
| S01 | 爸爸和两个儿子 / A father and two sons | orbit over the farm; the big brother hoes the field; the little brother lazes |
| S02 | 把钱给我 / Give me my share | the son asks for his share; the father, sad, hands him a money bag |
| S03 | 出发去远方 / Off to a far country | the son waves and struts off down the road; the father waves; the brother shakes his head |
| S04 | 天天开派对 / Party every day | far-country tavern, lights; the son throws coins, the friends cheer |
| S05 | 钱花光了 / All gone | empty pockets; the friends say bye; famine haze falls |
| S06 | 喂猪 / Feeding the pigs | the son feeds noisy pigs; he is so hungry even the pig food looks good |
| S07 | 想家 / Thinking of home | he sits in the mud, then has an idea: "I'll go home!" |
| S08 | 练习道歉 / Practising sorry | walking home at evening, he practises his apology to himself (comic) |
| S09 | 爸爸跑过来 / The father runs | the father, looking down the road as every day, sees him far off and runs; the hug |
| S10 | 最好的袍子 / The best robe | "I'm sorry..."; the father calls for the robe, the ring, a feast |
| S11 | 宴席 / The feast | night lamps, music, dancing: "lost and now found!" |
| S12 | 哥哥生气了 / The big brother is cross | the brother comes in from the field, hears the music, stomps, won't go in |
| S13 | 爸爸出来劝他 / The father comes out | "you are always with me... but your brother was lost and is found"; a hand held out |
| S14 | 天父在等你 / God is waiting for you | moral to the child; golden rays |

## Lines

The lines, their acting notes and every beat live in `storyboard/story.py` (single source); the generated table with
timings is `STORYBOARD.md`. Writing rules (owner review 2026-11-13/14, same as Ruth and Exodus):

- Written to be **said aloud to a child**: short sentences, everyday words, 呀/啦/呢/哎/咦/哇 where a person would say them.
- **People talk to each other**, the narrator only bridges. Every scene has at least one exchange.
- **Light moments**: the coins and the party, the empty pockets and the friends who vanish, the noisy pigs and the
  pig food that looks tasty, the rehearsed apology (he never gets to finish it), the old father running with his robe
  hitched up.
- Each line keeps its verse reference. Luke 15:24 ("was lost and is found") stays close to the familiar wording.

Child-friendly choices: "wild living" (15:13, 15:30) becomes buying sweets, fancy clothes and parties for friends;
there is no prostitution and no drinking shown. The fattened calf is a feast table (no animal killed on screen). The
parable ends open in Luke (we never hear the elder brother's answer); we keep it open but hopeful: the father holds out
his hand and the brother, after a pause, takes it (shown, not said). The narrator says plainly that Jesus told this
story to show that God is like the father.
