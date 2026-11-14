# Daniel — Daniel and the lions (story pack #4)

Fifth colouring sheet, fourth story pack (`docs/STORY-ARCHITECTURE.md`). The child colours the sheet, the app scans it
and the characters wearing the child's colours act out Daniel 6 on the page, in zh or en.

Source: the Book of Daniel, chapter 6 (public domain text). Every line is a child-friendly spoken paraphrase with the
verse it comes from; nothing is quoted from any film or other retelling. Audience: ages 4-10. Period research and mood
(Babylon under the Persians, blue glazed brick, mud-brick houses, a stone den sealed with the king's ring, sunset,
night, dawn) were taken from public historical sources and a reference viewing; characters, set, music and words are
original.

Title: **但以理与狮子 / Daniel and the Lions**.

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `daniel` | Daniel, the king's wise and honest servant; calm, kind, brave | front, left of centre | warm, gentle grown-up man, steady |
| `king` | King Darius, big-hearted, a little vain, then sorry and fretful, then overjoyed | front, centre | rich, round, regal baritone with a soft heart |
| `officer` | a jealous official: sulky, sly, a coward (comic villain, never frightening) | front, right | nasal, whiny, sly; comic shriek at the end |
| `lion` | the big maned lion; roars once, then purrs like a kitten | front, right (the child colours him) | roar / growl / purr are SFX |
| `lion2` | a lioness, his companion | not drawn (own painted texture, like Esther's guards) | SFX |
| `narrator` | | | storyteller |

## Beats (13 shots, about 3.5 minutes)

| Shot | Title zh / en | What happens |
|---|---|---|
| S01 | 巴比伦城 / The great city of Babylon | orbit over the city; Daniel loved God and prayed every day |
| S02 | 王的好朋友 / The king's good friend | the king praises Daniel and promotes him; Daniel: wisdom comes from God |
| S03 | 嫉妒的大臣 / A jealous official | the official grumbles to the child: "he's too honest!"; gets an idea |
| S04 | 一条新法令 / A new law | flattery; 30 days pray only to the king; the king, flattered, seals it |
| S05 | 窗前祷告 / Praying at the window | Daniel kneels at his west window, prays as always (and prays for the king) |
| S06 | 被抓到了 / Caught! | the official spies from behind the palm and runs to tell |
| S07 | 王好难过 / The king is so sorry | the king tries to save him; "a sealed law can't be changed"; "how foolish!" |
| S08 | 狮子坑 / The lions' den | sunset; "your God will save you" / "don't be afraid"; roar; stone; seal |
| S09 | 狮子坑里 / Inside the den | night; lions creep; Daniel prays; light; the lions yawn, lie down, purr |
| S10 | 王睡不着 / The king can't sleep | comic: the king paces all night by a torch |
| S11 | 天一亮 / First light | dawn run; "has your God saved you?" / "I'm fine!" |
| S12 | 一点伤都没有 / Not a scratch | Daniel comes out unhurt, hug; one roar sends the official running off the page |
| S13 | 活着的上帝 / The living God | the king's proclamation; moral: you can talk to God any time |

## Lines

The 29 lines, their acting notes and every beat live in `storyboard/story.py` (single source); the generated table
with timings is `STORYBOARD.md`. Writing rules are Ruth's (`docs/ruth/STORY.md`): said aloud to a child, people talk to
each other, the narrator bridges, a light moment in every act (the official's sulk and "I've got an idea!", the king's
"Seal it!", the purring lion, the sleepless king, the official's shriek), every line keeps its verse reference.

Child-friendly choices: the lions are scary for one roar and one growl, then funny; no blood, no bones in the den;
Daniel 6:24 (the accusers and their families thrown to the lions) is left out, the official is chased off the page by
a roar instead; Daniel prays for the king too (his kindness to the man who threw him in, after Jeremiah 29:7 / 9:3-4).
