#!/usr/bin/env python3
"""music_polish: the finishing passes the story packs' music scripts share (2026-11-15 pass over jonah and joseph).

Three small tools, none of them touches music_kit.py:
  pocket(x)            a wide cut where speech lives (900 Hz and 2.4 kHz), so the score sits behind the voices instead
                       of on top of them (the kit's `dip` was written for this but no pack used it).
  underscore(n, hits)  a gain curve (linear, length n samples) for the composed span: the score breathes at
                       `base_db` under the story and swells back to 0 dB around its hits (thunder, splash, gulp,
                       glow ...) and at its final cadence. The cue is then normalised to the contract loudness, so the
                       quiet part ends up quieter and the hits stay big. Language independent (it follows the hits,
                       not the lines).
  sfx_shape(x, hold, tau)  sound effects are not ducked by the engine (StoryDirector plays them at gainDb on top of
                       speech); a punchy front with a short tail keeps them out of the voice's way.
All times in seconds, relative to the start of the file.
"""
import numpy as np
from music_kit import SR, dip


def pocket(x):
    """Speech pocket: -1.5 dB at 900 Hz (wide), -3.5 dB at 2.4 kHz (wide). Linear, level-neutral elsewhere."""
    return dip(dip(np.asarray(x, np.float64), 900, -1.5, 0.8), 2400, -3.5, 0.7).astype(np.float64)


def underscore(n, hits, base_db=-7.0, pre=0.8, hold=0.2, post=1.2, end_at=None, end_pre=2.0, floor_from=0.0):
    """Gain curve: base_db everywhere, 0 dB from `pre` s before each hit to `hold` s after it, back down over `post` s
    (cosine ramps). `end_at` adds one more hit at the cue's final cadence."""
    t = np.arange(n) / SR; up = np.full(n, base_db, np.float64)
    hs = list(hits) + ([end_at] if end_at is not None else [])
    for h in hs:
        pr = end_pre if h == end_at else pre
        a = np.clip((t - (h - pr)) / pr, 0, 1); b = np.clip((t - (h + hold)) / post, 0, 1)
        w = 0.5 - 0.5 * np.cos(np.pi * a); w = np.where(t > h + hold, 0.5 + 0.5 * np.cos(np.pi * b), w)
        up = np.maximum(up, base_db * (1 - w))
    return 10 ** (up / 20)


def sfx_shape(x, hold, tau):
    """Keep `hold` seconds untouched, then decay with time constant `tau` (s)."""
    t = np.arange(len(x)) / SR
    return x * np.where(t < hold, 1.0, np.exp(-(t - hold) / tau))


def dips(n, spans, ramp=0.4):
    """Extra gain dips under speech that the score cannot get out of the way of: spans = [(t0, t1, dB), ...] (seconds in
    the file, taken from the Chinese re-timed timeline); 0.4 s cosine ramps. Language-dependent by a second or two in
    English; the dips are shallow (-2.5 to -6 dB) so a miss is inaudible."""
    t = np.arange(n) / SR; g = np.zeros(n)
    for t0, t1, db in spans:
        w = np.clip((t - t0) / ramp, 0, 1) * np.clip((t1 - t) / ramp, 0, 1)
        g = np.minimum(g, db * (0.5 - 0.5 * np.cos(np.pi * w)))
    return 10 ** (g / 20)
