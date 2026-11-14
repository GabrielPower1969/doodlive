# Exodus — Let my people go! (story pack #5)

Sixth colouring sheet, fifth story pack (`docs/STORY-ARCHITECTURE.md`). The child colours the sheet, the app scans it
and three rigged characters wearing the child's colours act out the Exodus on the page, in zh or en.

Source: the Book of Exodus 1-15 (public domain text). Every line is a child-friendly spoken paraphrase with the verse
it comes from; nothing is quoted from any film or other retelling. Audience: ages 4-10. Period research and mood
(New Kingdom Egypt: mud-brick yards, a columned palace, the striped royal head-cloth, the Sinai wilderness at dusk,
the parted sea) were taken from public historical sources and a reference viewing; characters, set, music and words
are original.

Title: **出埃及 / Let My People Go!**

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `moses` | Moses, an old shepherd (white beard, staff), humble, a bit shy of speaking, then brave | front, centre-left | warm older man, gentle, a little hesitant early, steady later |
| `pharaoh` | the king of Egypt, vain, stubborn, comic villain (never frightening) | front, left | proud baritone, pompous, flips from blustering to whiny |
| `miriam` | Miriam, Moses's sister, lively, brave, leads the song | front, right | bright grown woman, quick, warm, sings the chant |
| `god` | God's voice from the bush (no actor) | not drawn | deep, calm, kind; never thunderous; light reverb |
| `people` | the Israelites (off-stage group) | not drawn | 4-6 voices together, slightly ragged |
| `narrator` | | | storyteller (same as the other packs) |

## Beats (14 shots, about 4 minutes)

| Shot | Title zh / en | What happens |
|---|---|---|
| S01 | 埃及的奴隶 / Slaves in Egypt | orbit over the page: palace, pyramids, brick yard; Pharaoh shouts "faster!"; Miriam prays |
| S02 | 牧羊人摩西 / Moses the shepherd | Moses walks in from the far right wilderness with his staff |
| S03 | 烧不坏的荆棘 / The bush that doesn't burn | the bush is on fire but not burnt; God calls "Moses, Moses!" |
| S04 | 我不行呀 / Who, me? | Moses says he can't speak well; the staff becomes a snake (he jumps!) and back again |
| S05 | 让我的百姓走 / Let my people go! | Moses before Pharaoh; Pharaoh laughs him off |
| S06 | 青蛙来啦 / Here come the frogs! | the river turns red, frogs everywhere, a frog on Pharaoh's crown; he says yes, then no |
| S07 | 门上的记号 / The sign on the door | night; the marked doors glow; Miriam: "shoes on, we leave tonight!"; Pharaoh gives up |
| S08 | 我们自由啦 / We're free! | morning; the people cheer; the pillar of cloud leads them |
| S09 | 法老后悔了 / Pharaoh changes his mind | tantrum; "Who will make my bricks? Chariot!" |
| S10 | 前面是大海 / The sea is in the way | Miriam is afraid; Moses: "Don't be afraid, stand and watch" |
| S11 | 海分开了 / The sea opens | wind, the water stands up like two walls, they walk through on dry ground |
| S12 | 哗啦！/ Splash! | Pharaoh's chariot follows, a wheel comes off, the water rolls back; he is left soggy on the shore, sneezing |
| S13 | 米利暗的歌 / Miriam's song | tambourine, dancing, the people join in |
| S14 | 上帝带路 / God leads the way | Moses: God heard us; moral to the child |

## Lines

The 36 lines, their acting notes and every beat live in `storyboard/story.py` (single source); the generated table with
timings is `STORYBOARD.md`. Writing rules (owner review 2026-11-13/14, same as Ruth):

- Written to be **said aloud to a child**: short sentences, everyday words, 呀/啦/呢/哎/咦/哇 where a person would say them.
- **People talk to each other**, the narrator only bridges. Every scene has at least one exchange.
- **Light moments**: the snake (Moses jumps back), the frog on Pharaoh's crown and his yes-no flip, the chariot wheel,
  the soggy sneeze. Pharaoh is a vain, silly king in the tradition of Esther's Haman; he is never cruel on screen.
- Each line keeps its verse reference. Exodus 5:1 ("Let my people go") and 14:13 stay close to the familiar wording.

Child-friendly choices: Moses's killing of the Egyptian is left out (he "lived in the palace when he was young");
the plagues are shown as a quick comic montage (red river, frogs, flies, hail) without boils, livestock or locust
damage; the final plague is one gentle sentence and a sorrowful Pharaoh, no deaths shown or named; the Israelites are
"safe at home" behind the marked doors (the lamb is not shown); at the sea, the chariots "could not follow any more"
and Pharaoh is left soaked on the shore (14:28 is not narrated). Aaron and the magicians are left out to keep the cast
at three; God's "I will be with your mouth" (4:12) answers Moses directly.
