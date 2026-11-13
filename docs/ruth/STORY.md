# Ruth — where you go, I will go (story pack #3)

Fourth colouring sheet, third story pack (`docs/STORY-ARCHITECTURE.md`). The child colours the sheet, the app scans it
and three rigged characters wearing the child's colours act out the story of Ruth on the page, in zh or en.

Source: the Book of Ruth (public domain text). Every line is a child-friendly spoken paraphrase with the verse it comes
from; nothing is quoted from any film or other retelling. Audience: ages 4-10. Period research and mood (barley
harvest at Bethlehem, golden evening light, stone houses, threshing floor at night) were taken from public historical
sources and a reference viewing; characters, set, music and words are original.

Title: **忠心的路得 / Faithful Ruth**.

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `ruth` | Ruth, young widow from Moab, loyal, hard-working, a little shy | front, left of centre | warm young woman, gentle, brave |
| `naomi` | Naomi, her mother-in-law, older, tired and sad, then joyful | front, left | older woman, soft, a little husky, warm |
| `boaz` | Boaz, owner of the barley field, kind, a bit playful | front, right | warm baritone, hearty, fatherly |
| `reapers` | the field workers (one line, off-stage) | not drawn | 3-4 voices together |
| `narrator` | | | storyteller |

## Beats (12 shots, about 3 minutes)

| Shot | Title zh / en | What happens |
|---|---|---|
| S01 | 从摩押回家 / The long road home | dawn orbit over Bethlehem; Naomi and Ruth come in on the road |
| S02 | 你往哪里去 / Where you go, I will go | Naomi sends Ruth home; Ruth holds her hands and won't go (1:16) |
| S03 | 回到伯利恒 / Back in Bethlehem | they reach the house; Naomi is empty; Ruth cheers her up |
| S04 | 拾麦穗 / Gleaning | Ruth kneels at the field edge picking up stalks |
| S05 | 田的主人 / The owner of the field | Boaz greets the reapers, they answer; "who's that?" |
| S06 | 你为什么对我这么好 / Why are you so kind? | Boaz invites her to stay; she bows; he blesses her |
| S07 | 故意掉麦穗 / Oops, more grain! | comic: Boaz sneaks extra barley behind his back for her |
| S08 | 满满一大捆 / A great big bundle | golden evening; Naomi amazed; "he's family!" |
| S09 | 打谷场的夜晚 / Night at the threshing floor | stars, a lamp; Ruth asks Boaz for help; "don't be afraid" |
| S10 | 婚礼 / The wedding | flower arch, petals, cheering |
| S11 | 小宝宝 / A baby boy | Naomi rocks baby Obed |
| S12 | 大卫的曾祖母 / David's great-grandmother | Obed is King David's grandfather (the David of pack #1); moral |

## Lines

The 27 lines, their acting notes and every beat live in `storyboard/story.py` (single source); the generated table with
timings is `STORYBOARD.md`. Writing rules (owner review 2026-11-13/14: David & Goliath's lines were "stiff"):

- Written to be **said aloud to a child**: short sentences, everyday words, 呀/啦/呢/哎/嘘 where a person would say them.
- **People talk to each other**, the narrator only bridges. Every scene has at least one exchange.
- One **light moment** per act: Boaz's sneaky barley drop (2:16), Naomi's "so much!" (2:19).
- Each line keeps its verse reference. Ruth 1:16 stays close to the familiar wording on purpose.

Child-friendly choices: the deaths are one gentle sentence; Orpah is left out; at the threshing floor Ruth simply asks
Boaz for help (no lying at his feet); the nearer kinsman and the sandal at the gate (4:1-8) are left out; Obed's link
to David closes the loop with pack #1.
