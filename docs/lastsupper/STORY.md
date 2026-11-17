# The King Who Serves — the donkey, the temple and the towel (story pack)

Title: **服侍人的王 / The King Who Serves**. Id `lastsupper`, script prefix `ls`, env prefix `LS_`, set `jerusalem`,
line ids `ls_01…ls_36`.

Source: Matthew 21:1-16, Mark 11:1-17, Luke 19:37-40, Luke 22:7-27, John 12:12-15, John 13:1-17 (public-domain text;
also Mark 10:35-45 and John 1:40-42 for the disciples' squabble). Every line is our own child-friendly paraphrase with
its verse; nothing is quoted from any film or Bible translation. Audience 4-10. A reference viewing lent only costume
logic, set furniture and light per scene (see DESIGN.md); characters, words, set and music are original. None of the
reference episode's modern frame characters appear.

One-sentence moral: **Jesus is the greatest King, and He came to serve; being truly great means being glad to help
others.**

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `jesus` | Jesus: calm, warm, smiles easily; firm (never in a rage) in the temple; tender at the supper. **Same design as Real Miracles** | yes, front centre | same voice as `miracles` |
| `peter` | Simon Peter: big, loud, proud, big-hearted; the comedy (the stones, "Not my feet!" → "wash all of me!") and the turn at the end (he serves first). **Same design as Real Miracles** | yes, front right | same voice as `miracles` |
| `donkey` | the young donkey Jesus rides: small, grey, patient, ears that talk; one comic "hee-haw" at the start and the end | yes, front left (side view) | none (SFX only) |
| `john` | John: the youngest disciple, quick and cheeky, then thoughtful (fixed colours, not on the sheet) | no | bright young man |
| `james` | James: John's big brother, puffed up (fixed colours) | no | confident tenor |
| `andrew` | Andrew: Peter's little brother, calm, dry, the one who first took Peter to Jesus (fixed colours) | no | mild, soft-spoken |
| `seller1` | the dove seller in the temple court: round, loud, comic (fixed colours) | no | jolly market voice |
| `seller2` | the money changer: thin, quick patter, chases his coins (fixed colours) | no | nasal, fast |
| `people` | the crowd on the road (off-stage group) | no | 8-10 mixed voices incl. children |
| `narrator` | | | the family storyteller (same as every pack) |

## Beats (13 shots, estimate 4:03 by `build_timeline.py`; target 3:45-4:15)

| Shot | Title zh / en | What happens | Verses |
|---|---|---|---|
| S01 | 国王来了 / Here comes the King | orbit over the page: a road, a temple court, a house with an upstairs room; Jesus rides in on a little donkey; the donkey hee-haws | Matt 21:1-7; Mark 11:1-7 |
| S02 | 和散那！/ Hosanna! | palms and coats on the road; the crowd: "Hosanna! Hooray for our King!"; Peter, waving his palm: "we'll be important too!" | John 12:12-13; Mark 11:8-10 |
| S03 | 石头也会喊 / Even the stones | leaders grumble (narrator); Jesus: "these stones will shout out!"; Peter bends down and asks a stone to say something (ding) | Luke 19:39-40 |
| S04 | 祷告的殿 / A house of prayer | the noisy temple court; the dove seller cries his prices; Jesus grows sad: God's house was for praying | Mark 11:15-17 |
| S05 | 掀翻桌子 / Over go the tables | Jesus, firm, tips the money table (coins roll, the changer chases them) and opens the dove cages (doves fly free); "This is My Father's house..."; the sick are healed, children sing | Mark 11:15-17; John 2:16; Matt 21:12-15 |
| S06 | 谁最大？/ Who is the greatest? | evening, the upstairs room; James: right side, John: left side, Peter: "I'm the greatest!"; Andrew: "I took you to Jesus"; Peter: "That doesn't count!" | Luke 22:24; Mark 10:35-37; John 1:40-42 |
| S07 | 一盆水，一条毛巾 / A bowl and a towel | night; nobody wants the servant's job; Jesus ties a towel, pours water, kneels and washes Andrew's feet; James whispers in wonder | John 13:2-5 |
| S08 | 不要洗我的脚！/ Not my feet! | Peter: "Never, ever!" → Jesus: "you can't belong with Me" → Peter: "wash all of me!" → Jesus laughs; Judas in one narrator sentence | John 13:6-11 |
| S09 | 照着我做 / Do what I did | Jesus: "serve each other"; "the greatest one is the one who serves"; the four look sheepish | John 13:13-15; Luke 22:26-27 |
| S10 | 饼 / The bread | at the low table Jesus gives thanks, breaks the bread: "remember Me" | Luke 22:19 |
| S11 | 杯 / The cup | Jesus lifts the cup: God's new promise; "I give My life for you, so that sins can be forgiven" | Luke 22:20; Matt 26:28 |
| S12 | 轮到我了 / My turn now | Peter takes the towel and jug and kneels at his brother Andrew's feet: "It's my turn now!"; Andrew giggles | John 13:14-15 |
| S13 | 真正的大人物 / Truly great | the whole page at night; moral: the King who served; you can serve too; the donkey hee-haws goodnight | Mark 10:45; John 13:15-17 |

The lines, acting notes and every beat are in `storyboard/story.py` (single source; do not copy lines elsewhere).

## Child-friendly choices (do not undo)

- **The temple is non-violent.** No whip (John 2:15 is left out). Jesus is firm and sad, not raging; He tips one table
  and opens the cages; the doves fly free; the money changer's chase is the comedy. Nobody is touched, nobody is hurt.
- **Judas is one narrator sentence** (ls_27): he was there, he had turned against Jesus, and Jesus washed his feet too.
  No Judas on stage, no silver, no betrayal scene.
- **No arrest, no Gethsemane, no cross** in this pack. The cup line says "I give My life for you" once, gently; the
  word 血 / "blood" is not used. The story ends at the supper table, warm and lit.
- **Mary's perfume at Bethany is left out**: it needs her "for My burial" explanation and a fourth place; one lesson per
  pack.
- The squabble is comic and harmless (Andrew's deadpan is the joke); the payoff is Peter serving his own brother.
- The moral names everyday serving a four-year-old can do (set the table, let a friend go first).

## Writing rules (same as Ruth / Daniel / Jonah / Miracles)

Said aloud to a child; people talk to each other, the narrator bridges; one light moment per act (the hee-haw, the
talking stone, "Stop rolling!", "That doesn't count!", "wash all of me!", "that tickles!"); every line keeps its verse
reference.
