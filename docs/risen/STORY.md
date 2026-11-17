# He Is Risen! — the garden at sunrise (story pack)

Title: **他复活了！/ He Is Risen!** (the angel's words, Matthew 28:6). Id `risen`, script prefix `rs`, env prefix `RS_`,
set `garden`, line ids `rs_01…rs_39`.

Source: Matthew 27:59-60, 28:1-10, 20; Mark 16:1-7; Luke 23:44-49, 24:1-12, 36-43; John 19:41-42, 20:1-29
(public-domain text). Every line is our own child-friendly paraphrase with its verse; nothing is quoted from any film or
Bible translation. Audience 4-10, written first for a four-year-old. A reference viewing (Superbook S01E11) lent only
costume logic, set furniture and light per scene (see DESIGN.md); characters, words, set and music are original. None
of the reference episode's modern frame characters appear, and nothing of its arrest, trial or crucifixion scenes is
used.

One-sentence moral: **Jesus is alive: death could not keep Him, and He always keeps His promises.**

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `jesus` | Jesus, risen: calm, warm, glad, a hidden smile with Mary, laughing in the room. **Same design as Real Miracles / The King Who Serves** (no wounds drawn, no new costume) | yes, centre | same voice as `miracles` |
| `mary` | Mary Magdalene: young, loving, quick to tears and quick to joy; the heart of the garden scenes | yes, right | warm young woman |
| `angel` | the angel at the tomb: tall, kind, shining, a big friendly smile; sits on the rolled-away stone the whole time (Matt 28:2) | yes, left | strong, calm, warm (not booming) |
| `peter` | Peter: big, loud, slower runner, puffing; bursts into the tomb; laughs loudest at the fish. **Same design as Real Miracles**, here in fixed paint | no | same voice as `miracles` |
| `john` | John: the youngest disciple, quick and cheeky, wins the race, the first to understand. **Same design as The King Who Serves** (fixed paint) | no | same voice as `lastsupper` |
| `thomas` | Thomas: sensible, stubborn, arms crossed; then the most heartfelt "My Lord and my God!" (fixed paint) | no | steady baritone |
| `joanna` | Joanna, Mary's friend (Luke 24:10): practical, a bit worried about the stone (fixed paint) | no | brisk, kind woman |
| `narrator` | | | the family storyteller (same as every pack) |

## Beats (12 shots, estimate 3:53 by `build_timeline.py`; target 3:45-4:15)

| Shot | Title zh / en | What happens | Verses |
|---|---|---|---|
| S01 | 最难过的一天 / The saddest day | dusk orbit over the page; the tomb is closed; two women stand by it, Peter and John sit upstairs; two gentle narrator sentences (He died on a cross, the sky went dark, His friends were very sad; laid in a tomb in a garden, a big stone); then the promise: "On the third day I will rise!" | Luke 23:33, 44-49; John 19:41-42; Matt 27:59-60; 16:21 |
| S02 | 天刚亮 / Very early in the morning | dawn, birds; Mary and Joanna walk the path with spice jars; "Who will roll the stone away?" "I just want to be near Jesus." | Mark 16:1-3; Luke 24:1, 10; John 20:1 |
| S03 | 石头滚开了！/ The stone rolls away! | a gentle rumble, a flash of light: the stone has rolled aside and a shining angel sits on it; the women gasp | Matt 28:2-3; Mark 16:4 |
| S04 | 他不在这里 / He is not here! | the angel: "Don't be afraid! He is not here. He is risen, just as He said! Come and see." The women peek in: empty, only the folded cloth. "Go and tell His friends!" | Matt 28:5-7; Luke 24:3-6; Mark 16:6-7 |
| S05 | 他活了！/ He's alive! | the upstairs room: Peter and John sit sadly; Mary bursts in with the news; Peter can't believe it; John: "Let's go and see!" | Luke 24:9-11; John 20:2-3 |
| S06 | 赛跑 / The race | Peter and John run to the garden; young John is faster ("Hurry up, Peter!" / "Wait for me! My legs aren't as young as yours!") | John 20:3-4 |
| S07 | 空空的坟墓 / The empty tomb | John peeks in at the door; Peter puffs up and goes straight in; "The cloths are folded... but Jesus isn't here!"; John understands: "He said He would rise... and He did!" | John 20:5-9 |
| S08 | 你为什么哭？/ Why are you crying? | Mary alone in the garden, crying; Jesus stands behind her; she thinks He is the gardener | John 20:11-15 |
| S09 | 马利亚！/ Mary! | Jesus says her name; she knows Him at once, runs to Him and takes His hands; butterflies; "Go and tell My friends: I am alive!" | John 20:16-17; Matt 28:10 |
| S10 | 愿你们平安 / Peace be with you | evening, the locked room; Mary tells; Jesus is suddenly there: "Peace be with you!"; John: "A g-g-ghost?"; Jesus laughs, "Got anything to eat?", eats a piece of fish; Peter roars with laughter | John 20:18-19; Luke 24:36-43 |
| S11 | 多马 / Thomas | a week later: Thomas wasn't there and won't believe; Jesus comes again and holds out His hands; Thomas touches them gently and kneels: "My Lord and my God!" | John 20:24-28 |
| S12 | 他活着！/ He is alive! | the whole page in morning sun, the open tomb glowing, everyone waving; moral: death could not keep Him; He keeps His promises; "I am with you always" | Matt 28:6, 20; Luke 24:5-6; John 20:29 |

The lines, acting notes and every beat are in `storyboard/story.py` (single source; do not copy lines elsewhere).

## Child-friendly choices (do not undo)

- **The cross is two narrator sentences and nothing on screen** (`rs_01`, `rs_02`): no arrest, no soldiers, no
  trial, no cross, no body, no wounds anywhere on the page or in any shot. S01 shows only a quiet garden at dusk, a
  closed tomb and sad friends; the third sentence (`rs_03`) already turns to the promise.
- **No guards at the tomb** (Matt 27:62-66, 28:4, 11-15 left out): nobody faints, nobody is afraid of soldiers.
- **The earthquake is a small rumble** with a dust puff; the angel's light is soft and warm, and the angel's first words
  are "Don't be afraid!" with a smile. The angel never stands over the women; it sits on the stone.
- **Mary's tears are short and gentle** (S08 ~20 s) and turn to joy as soon as He says her name.
- **"A ghost?" is a joke**: John squeaks, Jesus laughs, eats a fish, everyone laughs.
- **Thomas's hands are gentle.** Jesus's hands are drawn as always (no marks); He holds them out, Thomas touches them,
  a soft glow. The words say "look at My hands", never "wounds" / "nail holes".
- **Merged accounts, one story**: the angel speaks to Mary and Joanna (Matthew / Mark / Luke); Mary runs to Peter and
  John (John 20:2; Luke 24:10-12); the race and the folded cloth (John 20:3-8); Mary meets Jesus in the garden
  (John 20:11-17); the room (John 20:19; Luke 24:36-43); Thomas a week later (John 20:24-28). The other women and the
  other disciples are left out to keep seven actors.
- The moral is one a four-year-old can hold: Jesus is alive, He keeps His promises, He is with you every day.

## Writing rules (same as Ruth / Daniel / Jonah / Miracles / The King Who Serves)

Said aloud to a child; people talk to each other, the narrator bridges; one light moment per act (the angel sitting on
the stone, the race and "my legs aren't as young as yours", "the gardener", "a g-g-ghost?", the fish); every line keeps
its verse reference; interjections stay inside a phrase with words (Qwen reads a bare 哈哈 as a word; The King Who
Serves VOICE.md).
