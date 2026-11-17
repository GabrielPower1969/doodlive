# Saul Sees the Light! — the road, the house on Straight Street and the basket (story pack)

Title (proposal, owner confirms at Gate 1): **扫罗变了！/ Saul Sees the Light!** (theme verse 2 Corinthians 5:17: anyone
who belongs to Christ is a new person). Fallback English title: *Saul Is Changed!* Id `saul`, script prefix `sa`, env
prefix `SA_`, set `damascus`, line ids `sa_01…sa_42`.

Source: Acts 9:1-31, with Acts 22:3-16 and 26:9-18 for detail and 2 Corinthians 11:32-33 for the basket
(public-domain text). Every line is our own child-friendly paraphrase with its verse; nothing is quoted from any film or
Bible translation. Audience 4-10, written first for a four-year-old. A reference viewing (Superbook S01E12) lent only
costume logic, set furniture and light per scene (see DESIGN.md); characters, words, set and music are original. None of
the reference episode's modern frame characters appear, and nothing of its Stephen scene or its search-and-arrest scenes
is used.

One-sentence moral: **God can change anyone's heart, and a heart that has been forgiven learns to forgive.**

## Cast

| Id | Who | On the sheet | Voice |
|---|---|---|---|
| `saul` | Saul: young (about 30), clever, quick, hot-headed; a frown and a march in the first half, a wide warm smile after. **One design; only the face changes** | yes, centre | new: a young man, strong and clear; sharp when angry, warm after |
| `ananias` | Ananias, a follower of Jesus in Damascus: small, round, older, kind and a bit fussy; frightened of Saul, brave anyway; the comic heart of the middle | yes, left | new: older, soft, a little fussy |
| `barnabas` | Barnabas ("son of encouragement", Acts 4:36): big, warm, generous; speaks up for Saul | yes, right | new: a big warm baritone |
| `judas` | Judas, Saul's host on Straight Street: a homely, kind man (fixed paint) | no | none (he only acts) |
| `priest` | the high priest in Jerusalem: old, calm, unsmiling; **kind-neutral, not a cartoon villain**; one shot (fixed paint) | no | new: an old, dry, calm voice |
| `tallguard` | a tall, thin temple guard who travels with Saul: nervous, curious, a little slow (fixed paint) | no | new: thin and high, comic |
| `shortguard` | a short, round temple guard: grumbles about his feet, boasts, dozes on duty (fixed paint) | no | new: round, gruff, comic |
| `peter` | Peter in Jerusalem. **Same design as Real Miracles**, fixed paint | no | same voice as `miracles` |
| `jesus` | **voice only**, never a body: a column of light on the road (`road_light`) and in Ananias's house (`angel_light`) | no | same voice as `miracles` (`cast_miracles.json`) |
| `narrator` | | | the family storyteller (same as every pack) |

## Beats (13 shots, estimate 4:03 by `build_timeline.py`; target 3:50-4:15)

| Shot | Title zh / en | What happens | Verses |
|---|---|---|---|
| S01 | 生气的扫罗 / Angry Saul | Jerusalem: Saul stomps up to the high priest's porch; one narrator sentence (he was angry and wanted to arrest Jesus's followers); "give me letters!"; the high priest hands him a letter | Acts 22:3; 8:3; 9:1-2; 26:12 |
| S02 | 去大马士革 / The road to Damascus | the hot road; two temple guards puff behind him: "My feet are flat as pancakes!" "No rest! March!" | Acts 9:3, 7 |
| S03 | 天上的光 / A light from heaven | a light brighter than the sun pours down round Saul; he sits down hard in the road; the guards duck | Acts 9:3-4; 26:13 |
| S04 | 扫罗，扫罗 / Saul, Saul | the voice from the light: "Saul, Saul, why are you against Me?" "Lord, who are You?" "I am Jesus. When you are against My friends, you are against Me. Get up and go into the city." The guards hear a voice and see nobody | Acts 9:4-7; 22:8-10 |
| S05 | 看不见了 / I can't see | the light is gone; Saul's eyes are open but he cannot see; the tall guard leads him by the hand to the gate | Acts 9:8; 22:11 |
| S06 | 直街上的房子 / The house on Straight Street | three days at Judas's house: he cannot see, does not eat, prays ("Lord Jesus, I was wrong. What do You want me to do?") | Acts 9:9, 11; 22:10 |
| S07 | 亚拿尼亚 / Ananias | the Lord speaks to Ananias in a soft light: "Go to Judas's house on Straight Street." "Saul? THAT Saul?!" "Go! I have chosen him." "All... all right, Lord. I'll go." | Acts 9:10-17 |
| S08 | 扫罗弟兄 / Brother Saul | Ananias tiptoes to the door, a bit scared, and goes in anyway; hands on Saul's head: "Brother Saul..."; something like scales falls; "I can see! You called me brother?" "Now you are our brother!" | Acts 9:17-18 |
| S09 | 受洗 / Baptised | water from Ananias's jug: Saul is baptised; then Judas's bread: "Three days with nothing!" | Acts 9:18-19 |
| S10 | 耶稣是神的儿子 / Jesus is God's Son | on the synagogue steps Saul tells everyone Jesus is the Son of God; the two guards: "Isn't that the Saul who came to arrest people?" "He's completely changed!" | Acts 9:20-22 |
| S11 | 大筐子 / The big basket | night: angry men watch the gate; the short guard boasts, then dozes; behind the guards' backs a big basket comes down the wall from a window; Saul climbs out, whispers thank you and tiptoes away | Acts 9:23-25; 2 Cor 11:32-33 |
| S12 | 巴拿巴 / Barnabas | Jerusalem: Peter peeks out, afraid ("Has he come to arrest us?"); Barnabas: "Don't be afraid! He met Jesus, and Jesus changed his heart." Peter: "Then welcome, brother Saul!" A hug | Acts 9:26-28 |
| S13 | 心变了 / A changed heart | the whole page in sunshine, everyone waving, even the guards; Jesus turned his heart from anger to love; later he was called Paul; "Jesus forgave me. He can change anyone's heart!"; moral | Acts 9:28; 13:9; 1 Tim 1:13-16; 2 Cor 5:17; Eph 4:32 |

The lines, acting notes and every beat are in `storyboard/story.py` (single source; do not copy lines elsewhere).

## Child-friendly choices (do not undo)

- **Saul's anger is one narrator sentence** (`sa_01`): "he wanted to arrest everyone who followed Jesus". No Stephen,
  no stoning, no "threats and murder" (Acts 9:1 is softened to "arrest"), no prison, no chains, no one taken away on
  screen. In S01 he only asks for letters.
- **The light is wonderful, not scary**: warm white and gold, music shimmering, no thunder; Saul sits down hard (a comic
  bump, not a crash); the guards duck like children in a storm and peep out at once. Jesus's first words are sad and
  loving, never angry.
- **Jesus is a light and a voice, never a body** (Acts 9:7; 22:9). His words keep the gentle core of Acts 9:5: "When you
  are against My friends, you are against Me."
- **Blindness is gentle and short**: eyes open, nothing seen, said quietly; he is led by the hand. "Three days, no food"
  is said once, plainly (`sa_15`); the food comes back with a joke (`sa_27`).
- **"Scales" are a sparkle**, not a medical picture: tiny pale flakes that glint and vanish.
- **Ananias's fear is the comic beat** ("Saul? THAT Saul?!", knees knocking), and his courage is the lesson: he goes
  anyway and calls Saul "brother".
- **The plot to kill Saul (Acts 9:23) becomes "some angry men watched the gate to catch Saul"**; the guards are comic
  (boasting, dozing, a lantern); no weapons, no chase, no violence. The escape is a quiet, twinkly tiptoe.
- **The temple guards are the same two men all through** (travelling with Saul, leading him blind, puzzled at the
  synagogue, watching the gate) and **they wave in the finale**: the forgiveness of the moral reaches them too. Acts says
  only "the men travelling with him" (9:7) and "they watched the gates" (9:24); making them the same two is our choice.
- **Merged and shortened**: Saul's years in Arabia and his time in Damascus (Gal 1:17-18) are left out; Jerusalem meets
  him the same week on screen. Of the apostles only Peter appears (Gal 1:18). "Later he was called Paul" (Acts 13:9) is
  a one-line tag.
- The moral is one a four-year-old can hold: Jesus can change anyone's heart, even a very angry one; a forgiven heart
  forgives.

## Writing rules (same as Ruth / Daniel / Jonah / Miracles / The King Who Serves / He Is Risen!)

Said aloud to a child; people talk to each other, the narrator bridges; one light moment per act (the pancake feet, the
guards ducking and "nobody here", "THAT Saul?!", "three days with nothing!", the boasting guard who dozes, Peter's small
voice); every line keeps its verse reference; interjections stay inside a phrase with words (Qwen reads a bare 哈哈 as a
word; The King Who Serves VOICE.md). No line is a bare interjection.
