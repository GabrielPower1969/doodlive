# Translation review list (2026-11-22)

The six new languages were translated by Claude in one pass each. These are the points the translators were not sure
about. A native speaker should look at them first; then listen to the lines that `assets/<story>/audio/voice/report-<lang>.json`
flags (word error above the limit, or too long).

## All languages

- **The angel's gender.** Chinese and English call the colour-in angel "she". "Ange" (fr), "Engel" (de), "anjo" (pt),
  "ملاك" (ar) are masculine nouns, so the UI mostly says "the angel" and avoids pronouns; a few strings still use the
  masculine (de: `tagline`, `tapXR`, `xrPlaced`; fr: `tagline`, `lost`, `tapXR`, `xrPlaced`, `howtoStep4`).
- **"AR"** is kept as "AR" in fr and ar, "RA" in pt.
- **`readEnglish`** is "English" in each language. It names the English word on the 3D word card, so that is correct.
- **Sound words** (hmph, splash, achoo, ribbit…) are guesses in every language: listen to them.

## French
- Shortened lines: `ex_34`, `ex_33`, `ex_02`, `ls_32`, `ls_08`, `es_04b`; `rs_30` "Paix à vous !", `rs_37` "Mon Seigneur, mon Dieu !".
- `ru_06`: Ruth calls Naomi "maman".

## German
- `modeShow` "Bühne" (alternative "Zeigen"); `readHanzi` "Schriftzeichen" (long).
- `pr_16` and `pr_20` no longer match word for word; `mi_16` "Kind, deine Sünden sind vergeben"; `rs_31`/`rs_32` "Geist".

## Japanese
- Many lines are terser than the English to fit the time (e.g. `mi_25`, `rs_04`, `es_17`).
- `sa_40` 「のちのパウロです。」 may be hard for a six-year-old; `jn_28`, `ex_14`; narrator ends in だ-style in `ex_18`, `ex_20`.
- UI words to check: `haptics` しんどう, `sheetBlank` まっ白, `dg_herald` おふれ役.

## Spanish
- Mixed tú / usted towards kings; "ustedes" (Latin American) throughout; `sa_05` "panqueques"; `rs_30` "¡Paz a ustedes!".
- `ga_02` "pequeño" is masculine.

## Arabic
- Dual forms in `rs_09`, `rs_10`, `rs_12`; `mi_20` "رجلاي"; Bible verses are simplified, not Van Dyck quotes.
- How Arabic and Latin text ("AR", "ABC") mix on screen: check on the phone.

## Portuguese
- `modeShow` "Exibição", `wordCard` "Cartão de palavras"; the angel speaks in the feminine in `hello`.
- The prodigal son says "você" to his father.
