// Jonah (story pack, docs/jonah/FX.md) effects. Same engine as the earlier packs: every effect is a pure function of
// (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered in FxLibrary
// after the earlier packs (an existing id is never replaced), through the manifest `fx.class` = JonahFx.
// New: storm_rain, bubbles, deep_glow, sun_scorch. `plant_grow` is an alias of `sparkle` (manifest `fx.aliases`).
// Reused unchanged: golden_rays, sea_wind, splash, zzz, steam, sweat, tension_dim, prayer_glow, heart_glow.
// storm_rain / deep_glow / sun_scorch post to StoryTint (StoryFxRuth.cs) and storm_rain also to StoryLight's cold flash
// (StoryFxEsther.cs); both are already drawn by the stage runtime, so no runtime file is needed here.
// Only managed UnityEngine value types are used (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no strobe (flashes are soft, 6+ s apart), nothing bright or opaque over a face.
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Jonah registry and palette (docs/jonah/CONTRACT.md §8, DESIGN.md §4).</summary>
    public static class JonahFx
    {
        internal static FxDef[] Defs => new FxDef[] { new StormRain(), new Bubbles(), new DeepGlow(), new SunScorch() };

        // stage tints (multiply) and rim colours, sRGB
        public static Color StormTint = new Color(0.62f, 0.69f, 0.82f, 1f), StormRim = new Color(0.28f, 0.36f, 0.52f, 1f);
        public static Color DeepTint = new Color(0.22f, 0.47f, 0.54f, 1f), DeepRim = new Color(0.20f, 0.48f, 0.52f, 1f);
        public static Color ScorchTint = new Color(1.00f, 0.85f, 0.64f, 1f), ScorchRim = new Color(0.50f, 0.30f, 0.08f, 1f);
        /// <summary>Peak of a lightning flash as a share of StoryLight.FlashStrength (the cold flash's full opacity).</summary>
        public static float LightningLevel = 0.55f;
        /// <summary>Flash start times in seconds from the start of storm_rain; null = automatic (see StormRain.Flashes).</summary>
        public static float[] FlashTimes = null;

        // storm
        internal static readonly Color StormHigh = new Color32(0x4C, 0x58, 0x72, 255), StormMid = new Color32(0x63, 0x71, 0x8C, 255),
                                       StormLow = new Color32(0x86, 0x95, 0xAC, 255), StormCloud = new Color32(0x5A, 0x66, 0x80, 255),
                                       RainCol = new Color32(0xE4, 0xF0, 0xFF, 255), Bolt = new Color32(0xF2, 0xF8, 0xFF, 255);
        // water
        internal static readonly Color BubbleRim = new Color32(0x4E, 0x9C, 0xC4, 255), BubbleWhite = new Color32(0xF4, 0xFC, 0xFF, 255);
        internal static readonly Color DeepHigh = new Color32(0x0C, 0x3C, 0x48, 255), DeepMid = new Color32(0x12, 0x52, 0x5E, 255),
                                       DeepLow = new Color32(0x1C, 0x6A, 0x74, 255), Caustic = new Color32(0x9A, 0xF0, 0xE4, 255),
                                       Mote = new Color32(0xC8, 0xFF, 0xF2, 255);
        // sun
        internal static readonly Color SunCore = new Color32(0xFF, 0xB8, 0x2E, 255), SunHot = new Color32(0xFF, 0x7A, 0x1E, 255),
                                       SunWhite = new Color32(0xFF, 0xF0, 0xB8, 255), HeatLine = new Color32(0xFF, 0x9A, 0x3C, 255);

        /// <summary>A crayon stroke between two points that stays solid to its end (the ribbon cell fades over its last
        /// 40 %: the fade is pushed into a short tail past p1).</summary>
        internal static void Stroke(FxBatch b, Vector3 p0, Vector3 p1, float w0, float w1, Color col, bool add = false)
        {
            var r = b.Ribbon(DGFxPaint.Ribbon, add);
            Vector3 d = p1 - p0;
            for (int k = 0; k <= 3; k++) r.Add(p0 + d * (k / 3f), Mathf.Lerp(w0, w1, k / 3f), col);
            r.Add(p1 + d * 0.05f, w1, col);
            r.Add(p1 + d * 0.10f, w1 * 0.8f, col);
        }
    }

    // ------------------------------------------------------------------ S03-S04: the storm (stage)
    /// <summary>
    /// A storm over the whole page. A dark grey-blue sky band and a few heavy clouds behind the set; slanted rain
    /// streaks (about 90 in the air) over every depth of the page, ripples on the sea; 1-3 soft cool-white lightning
    /// flashes (at least 6 s apart, 0.12 s rise and 0.5 s fall: no strobe) with a thin bolt in the far sky. Asks StoryTint
    /// for a cool grey multiply. Fades in over 1 s, out over 1.5 s.
    /// </summary>
    public sealed class StormRain : FxDef
    {
        public override string Id => "storm_rain";
        public override float DefaultDur => 20f;
        public override bool Follow => false;

        const float Rise = 0.12f, Fall = 0.5f;

        /// <summary>Flash start times (seconds from the start): JonahFx.FlashTimes when set, else 5.7 s (the second thunder of
        /// the story, 6.0 s after the effect starts) and every 10.4 s after that, while 2.3 s of the run are left; at most 3.
        /// A run shorter than 8 s gets one flash at 40 % of its length.</summary>
        internal static int Flashes(FxCtx c, float[] times)
        {
            if (JonahFx.FlashTimes != null)
            {
                int m = 0;
                foreach (float f in JonahFx.FlashTimes) if (m < 3 && f < c.dur - 0.7f) times[m++] = f;
                return m;
            }
            if (c.dur < 8f) { times[0] = 0.4f * c.dur; return c.dur >= 4f ? 1 : 0; }
            int n = 0;
            for (float f = 5.7f; n < 3 && f < c.dur - 2.3f; f += 10.4f) times[n++] = f;
            return n;
        }

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1f, 1.5f);
            StoryTint.Request(c.seed, JonahFx.StormTint, 0.85f * env, JonahFx.StormRim);

            // lightning: a soft flash for the stage and a thin bolt far back in the sky
            var ft = new float[3];
            int nf = Flashes(c, ft);
            float flash = 0f, boltA = 0f; int bolt = -1;
            for (int k = 0; k < nf; k++)
            {
                float u = c.t - ft[k];
                if (u < 0f || u > Rise + Fall) continue;
                float f = u < Rise ? u / Rise : 1f - (u - Rise) / Fall;
                f = f * f * (3f - 2f * f);
                if (f > flash) { flash = f; bolt = k; }
                boltA = Mathf.Max(boltA, u < 0.35f ? 1f - u / 0.35f : 0f);
            }
            if (flash > 0f) StoryLight.RequestFlash(c.seed, StoryLight.FlashStrength * JonahFx.LightningLevel * flash * env);
            if (env <= 0) return;

            // dark sky behind the backdrop and three heavy clouds drifting across it
            RuthFx.SkyBand(b, 0.62f, 0.22f, JonahFx.StormHigh, 0.94f * env, 0.010f, c.t);
            RuthFx.SkyBand(b, 0.46f, 0.22f, JonahFx.StormMid, 0.92f * env, 0.012f, c.t);
            RuthFx.SkyBand(b, 0.31f, 0.20f, JonahFx.StormLow, 0.88f * env, 0.008f, c.t);
            for (int i = 0; i < 4; i++)
            {
                float span = 1.9f, ph = FxRand.H(c.seed, i, 1) + c.t * Mathf.Lerp(0.012f, 0.022f, FxRand.H(c.seed, i, 0)) / span;
                ph -= Mathf.Floor(ph);
                var p = new Vector3(-0.95f + span * ph, Mathf.Lerp(0.48f, 0.66f, FxRand.H(c.seed, i, 2)), RuthFx.SkyZ + 0.03f);
                float s = Mathf.Lerp(0.30f, 0.44f, FxRand.H(c.seed, i, 3)), e = Sat(ph * 6f) * Sat((1 - ph) * 6f);
                b.Sprite(p, 2.2f * s, 0.9f * s, A(JonahFx.StormHigh, 0.75f * env * e), DGFxPaint.SoftDot, 0f, false, FxFace.Camera);
                b.Sprite(p + new Vector3(-0.5f * s, -0.05f * s, 0.002f), 1.5f * s, 0.8f * s, A(JonahFx.StormCloud, 0.65f * env * e), DGFxPaint.SoftDot, 0f, false, FxFace.Camera);
                b.Sprite(p + new Vector3(0.55f * s, -0.07f * s, 0.002f), 1.4f * s, 0.7f * s, A(JonahFx.StormCloud, 0.60f * env * e), DGFxPaint.SoftDot, 0f, false, FxFace.Camera);
            }
            if (boltA > 0f)
            {
                float x0 = Mathf.Lerp(-0.45f, 0.35f, FxRand.H(c.seed, bolt, 91));
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                var g = b.Ribbon(DGFxPaint.Ribbon, true);
                Vector3 prev = new Vector3(x0, 0.70f, RuthFx.SkyZ + 0.05f);
                for (int k = 0; k <= 7; k++)
                {
                    Vector3 p = new Vector3(x0 + 0.05f * Mathf.Sin(k * 2.1f + bolt) + 0.012f * FxRand.Signed(c.seed, bolt * 9 + k, 92),
                                            Mathf.Lerp(0.70f, 0.30f, k / 7f), RuthFx.SkyZ + 0.05f);
                    float w = k % 2 == 0 ? 0.013f : 0.009f;
                    r.Add(p, w, A(JonahFx.Bolt, 0.95f * boltA * env)); g.Add(p, w * 2.6f, A(JonahFx.Bolt, 0.28f * boltA * env));
                    prev = p;
                }
                r.Add(prev + new Vector3(0, -0.01f, 0), 0.004f, A(JonahFx.Bolt, 0.9f * boltA * env));
                g.Add(prev + new Vector3(0, -0.01f, 0), 0.004f, A(JonahFx.Bolt, 0.2f * boltA * env));
            }

            // slanted rain over the whole page: heads fall at 0.55-0.85 s per run, 0.30 of slant to the right
            const int n = 90;
            const float slant = 0.30f, top = 0.95f, len = 0.085f;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(0.55f, 0.85f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                int cyc = (int)Mathf.Floor(ph); float u = ph - cyc;
                int k = i * 17 + cyc;
                float y = Mathf.Lerp(top, 0.0f, u);
                float x = Mathf.Lerp(-0.85f, 0.65f, FxRand.H(c.seed, k, 2)) + slant * (top - y);
                float z = Mathf.Lerp(-0.62f, 0.24f, FxRand.H(c.seed, k, 3));
                var head = new Vector3(x, y, z);
                var tail = head + new Vector3(-slant, 1f, 0f).normalized * len;
                float a = 0.55f * env * Sat(u * 8f) * (z > 0.10f ? 0.8f : 1f);
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                r.Add(head, 0.0040f, A(JonahFx.RainCol, a));
                r.Add(Vector3.Lerp(head, tail, 0.5f), 0.0034f, A(JonahFx.RainCol, a * 0.85f));
                r.Add(tail, 0.0022f, A(JonahFx.RainCol, a * 0.7f));
            }

            // ripples where the rain lands on the sea (x -0.60 .. 0.06)
            for (int i = 0; i < 14; i++)
            {
                float period = Mathf.Lerp(0.9f, 1.4f, FxRand.H(c.seed, i, 30));
                float ph = c.t / period + FxRand.H(c.seed, i, 31);
                int cyc = (int)Mathf.Floor(ph); float u = ph - cyc;
                int k = i * 13 + cyc;
                var p = new Vector3(Mathf.Lerp(-0.58f, 0.04f, FxRand.H(c.seed, k, 32)), 0.016f, Mathf.Lerp(-0.52f, 0.19f, FxRand.H(c.seed, k, 33)));
                b.Sprite(p, 0.02f + 0.07f * OutCubic(u), A(JonahFx.RainCol, 0.50f * env * (1f - u)), DGFxPaint.Ring, 0f, false, FxFace.Ground);
            }
        }
    }

    // ------------------------------------------------------------------ S05, S06: bubbles rising from a node
    /// <summary>
    /// Round bubbles (pale-blue crayon rim, a faint white fill, a bright highlight) leave the node every 0.16 s, rise
    /// 0.25 with a wobble and grow a little, then pop: a ring puff and four tiny droplets. Each bubble starts where the
    /// node was when it was born, so a swimming fish leaves a trail. Spawning stops early enough that every bubble pops
    /// before the end. Fades with the effect (0.3 s).
    /// </summary>
    public sealed class Bubbles : FxDef
    {
        public override string Id => "bubbles";
        public override float DefaultDur => 5f;

        const float Every = 0.16f, Pop = 0.14f, Height = 0.25f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.2f, 0.3f);
            if (env <= 0) return;
            Vector3 camFlat = c.ToCamFlat(c.anchor);
            int last = Mathf.FloorToInt(c.t / Every);
            for (int k = Mathf.Max(0, last - 14); k <= last; k++)
            {
                float t0 = k * Every + 0.4f * Every * FxRand.H(c.seed, k, 0);
                float life = Mathf.Lerp(1.0f, 1.5f, FxRand.H(c.seed, k, 1));
                if (t0 + life > c.dur + 0.1f) continue;                      // never cut off mid-air
                float age = c.t - t0;
                if (age < 0f || age > life + Pop) continue;
                float u = Sat(age / life);
                float rise = Height * OutCubic(u * 0.9f + 0.1f * u * u);
                Vector3 src = c.track.Count > 0 ? c.track.Sample(t0) : c.anchor;
                src += c.camRight * (0.035f * FxRand.Signed(c.seed, k, 2)) + camFlat * (0.015f * FxRand.Signed(c.seed, k, 3));
                float wob = (0.010f + 0.010f * u) * Mathf.Sin(Tau * (u * 1.5f + FxRand.H(c.seed, k, 4)));
                Vector3 p = src + Vector3.up * rise + c.camRight * wob;
                float r0 = Mathf.Lerp(0.016f, 0.036f, 0.5f * FxRand.H(c.seed, k, 5) + 0.5f * FxRand.H(c.seed, k, 6) * FxRand.H(c.seed, k, 6));
                float d = 2f * r0 * (0.75f + 0.45f * u);
                float squash = 1f + 0.08f * Mathf.Sin(Tau * (age * 2.2f + FxRand.H(c.seed, k, 7)));   // slight wobble of shape

                if (age <= life)
                {
                    float a = env * Sat(age / 0.15f);
                    b.Sprite(p, d * 1.22f * squash, d * 1.22f / squash, A(JonahFx.BubbleRim, 0.85f * a), DGFxPaint.Ring, 0f, false, FxFace.Camera);
                    b.Sprite(p, d * 1.12f * squash, d * 1.12f / squash, A(JonahFx.BubbleRim, 0.55f * a), DGFxPaint.Ring, 0f, false, FxFace.Camera);
                    b.Sprite(p, d * squash, d / squash, A(JonahFx.BubbleWhite, 0.34f * a), DGFxPaint.SoftDot, 0f, false, FxFace.Camera);
                    b.Sprite(p, d * 1.04f * squash, d * 1.04f / squash, A(JonahFx.BubbleWhite, 0.85f * a), DGFxPaint.Ring, 0f, false, FxFace.Camera);
                    b.Sprite(p + c.camRight * (-0.28f * d) + c.camUp * (0.28f * d), d * 0.26f, A(JonahFx.BubbleWhite, 0.95f * a), DGFxPaint.SoftDot, 0f, true);
                }
                else
                {   // the pop: a ring puff and four droplets flying out
                    float q = (age - life) / Pop;
                    float a = env * (1f - q);
                    b.Sprite(p, d * (1.1f + 1.1f * q), A(JonahFx.BubbleRim, 0.65f * a), DGFxPaint.Ring, 0f, false, FxFace.Camera);
                    b.Sprite(p, d * (1.0f + 0.9f * q), A(JonahFx.BubbleWhite, 0.8f * a), DGFxPaint.Ring, 0f, false, FxFace.Camera);
                    for (int j = 0; j < 4; j++)
                    {
                        float ang = Tau * (j + 0.3f * FxRand.H(c.seed, k, 8)) / 4f + 0.6f;
                        Vector3 dp = p + (c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang)) * (d * (0.55f + 0.9f * q));
                        b.Sprite(dp, d * 0.16f * (1f - 0.5f * q), A(JonahFx.BubbleWhite, 0.9f * a), DGFxPaint.SoftDot, 0f, false);
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ S06: inside the great fish (stage)
    /// <summary>
    /// The deep. A deep teal multiply tint over everything, teal bands behind the set (almost dark), slow caustic light
    /// lines wandering over the page, slow ripples of light spreading on the floor, and 28 motes drifting up and
    /// sideways. All light is faint and sits on the floor or behind the actors, so nothing brightens a face. Fades in and
    /// out over 1.5 s.
    /// </summary>
    public sealed class DeepGlow : FxDef
    {
        public override string Id => "deep_glow";
        public override float DefaultDur => 20f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.5f, 1.5f);
            env = env * env * (3f - 2f * env);
            StoryTint.Request(c.seed, JonahFx.DeepTint, 0.92f * env, JonahFx.DeepRim);
            if (env <= 0) return;
            RuthFx.SkyBand(b, 0.62f, 0.22f, JonahFx.DeepHigh, 0.92f * env, 0.008f, c.t * 0.6f);
            RuthFx.SkyBand(b, 0.46f, 0.22f, JonahFx.DeepMid, 0.90f * env, 0.010f, c.t * 0.6f);
            RuthFx.SkyBand(b, 0.31f, 0.20f, JonahFx.DeepLow, 0.86f * env, 0.008f, c.t * 0.6f);
            // a soft light from above, far behind: the surface a long way up
            b.Sprite(new Vector3(0.05f, 0.55f, RuthFx.SkyZ + 0.02f), 1.4f, 0.8f, A(JonahFx.Caustic, 0.16f * env * (0.9f + 0.1f * Mathf.Sin(c.t * 0.5f))), DGFxPaint.SoftDot, 0, true, FxFace.Camera);

            // caustics: 9 wavy light lines lying on the page, drifting and breathing
            for (int i = 0; i < 9; i++)
            {
                float z = Mathf.Lerp(-0.50f, 0.18f, (i + 0.5f) / 9f) + 0.02f * Mathf.Sin(c.t * 0.21f + i * 1.7f);
                float breathe = 0.5f + 0.5f * Mathf.Sin(c.t * Mathf.Lerp(0.35f, 0.6f, FxRand.H(c.seed, i, 0)) + i * 2.3f);
                var r = b.Ribbon(DGFxPaint.Ribbon, true);
                const int pts = 12;
                for (int k = 0; k < pts; k++)
                {
                    float f = k / (float)(pts - 1);
                    float x = Mathf.Lerp(-0.62f, 0.62f, f);
                    float zz = z + 0.035f * Mathf.Sin(x * 9f + c.t * 0.45f + i * 1.3f) + 0.015f * Mathf.Sin(x * 21f - c.t * 0.7f + i);
                    r.Add(new Vector3(x, 0.012f, zz), 0.012f + 0.012f * breathe, A(JonahFx.Caustic, 0.22f * (0.35f + 0.65f * breathe) * env * Mathf.Sin(Mathf.PI * f)));
                }
            }
            // slow ripples of light spreading over the floor
            for (int i = 0; i < 6; i++)
            {
                float period = Mathf.Lerp(5f, 7.5f, FxRand.H(c.seed, i, 10));
                float ph = c.t / period + FxRand.H(c.seed, i, 11);
                int cyc = (int)Mathf.Floor(ph); float u = ph - cyc;
                int k = i * 7 + cyc;
                var p = new Vector3(Mathf.Lerp(-0.45f, 0.45f, FxRand.H(c.seed, k, 12)), 0.014f, Mathf.Lerp(-0.40f, 0.12f, FxRand.H(c.seed, k, 13)));
                b.Sprite(p, 0.10f + 0.42f * OutCubic(u), A(JonahFx.Caustic, 0.34f * env * Mathf.Sin(Mathf.PI * u)), DGFxPaint.GlowDisc, 0f, true, FxFace.Ground);
            }
            // motes: slow, small, pale aqua; a few twinkle. None near head height in the middle of the page.
            for (int i = 0; i < 28; i++)
            {
                float period = Mathf.Lerp(7f, 12f, FxRand.H(c.seed, i, 20));
                float ph = c.t / period + FxRand.H(c.seed, i, 21);
                int cyc = (int)Mathf.Floor(ph); float u = ph - cyc;
                int k = i * 11 + cyc;
                var p = new Vector3(Mathf.Lerp(-0.60f, 0.60f, FxRand.H(c.seed, k, 22)) + 0.025f * Mathf.Sin(Tau * u * 1.3f + i),
                                    Mathf.Lerp(0.02f, 0.40f, u) + 0.02f * FxRand.H(c.seed, k, 23),
                                    Mathf.Lerp(-0.45f, 0.18f, FxRand.H(c.seed, k, 24)));
                float life = Mathf.Sin(Mathf.PI * u) * env;
                bool tw = i % 5 == 0;
                b.Sprite(p, tw ? 0.026f : 0.013f, A(JonahFx.Mote, 0.75f * life), tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, 0.6f * c.t + i, false);
                b.Sprite(p, tw ? 0.05f : 0.026f, A(JonahFx.Caustic, 0.35f * life), DGFxPaint.SoftDot, 0f, true);
            }
        }
    }

    // ------------------------------------------------------------------ S10-S11: the hot sun over a node
    /// <summary>
    /// A small hot sun hangs over the node (a yellow-orange crayon disc with a pulsing glow and ten short rays turning
    /// slowly), a little behind and well above the head, easing down a touch as the heat bears down. Wavy orange heat
    /// lines rise at both sides of the node (never in front of the face), shimmer lines lie on the ground, and a warm
    /// pool lights the floor round the node; asks StoryTint for a warm multiply. Fades in 0.8 s, out 1.2 s.
    /// </summary>
    public sealed class SunScorch : FxDef
    {
        public override string Id => "sun_scorch";
        public override float DefaultDur => 8f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 1.2f);
            env = env * env * (3f - 2f * env);
            StoryTint.Request(c.seed, JonahFx.ScorchTint, 0.75f * env, JonahFx.ScorchRim);
            if (env <= 0) return;
            Vector3 a = c.anchor;
            Vector3 away = -c.ToCamFlat(a);
            float pulse = 0.9f + 0.1f * Mathf.Sin(c.t * Tau * 0.35f);
            float lowering = 0.04f * Smooth(0f, c.dur, c.t);
            Vector3 sun = a + Vector3.up * (0.24f - lowering) + away * 0.05f;

            // warm pool on the floor round the node
            Vector3 g = FxCtx.Ground(a, 0.006f);
            b.Sprite(g, 0.55f, A(JonahFx.SunCore, 0.26f * env * pulse), DGFxPaint.GlowDisc, 0f, false, FxFace.Ground);
            b.Sprite(g + Vector3.up * 0.001f, 0.30f, A(JonahFx.SunHot, 0.18f * env), DGFxPaint.SoftDot, 0f, true, FxFace.Ground);

            // the sun: glow, rays, disc, bright centre
            b.Sprite(sun, 0.36f * pulse, A(JonahFx.SunCore, 0.34f * env), DGFxPaint.SoftDot, 0f, true);
            for (int i = 0; i < 10; i++)
            {
                float ang = Tau * i / 10f + c.t * 0.12f;
                Vector3 d = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                float r0 = 0.075f, r1 = r0 + (i % 2 == 0 ? 0.050f : 0.034f) * (0.85f + 0.3f * Mathf.Sin(c.t * 2.2f + i));
                JonahFx.Stroke(b, sun + d * r0, sun + d * r1, 0.014f, 0.006f, A(JonahFx.SunHot, 0.95f * env));
            }
            b.Sprite(sun + away * 0.004f, 0.135f, A(Color.Lerp(JonahFx.SunCore, Color.white, 0.12f), env), DGFxPaint.Puff, 0f, false);
            b.Sprite(sun, 0.07f, A(JonahFx.SunWhite, 0.55f * env), DGFxPaint.SoftDot, 0f, true);

            // heat lines: wavy, rising on both sides of the node; none within 0.075 of the middle
            for (int i = 0; i < 6; i++)
            {
                float side = i % 2 == 0 ? -1f : 1f;
                float lat = side * Mathf.Lerp(0.09f, 0.20f, ((i / 2) + 0.5f) / 3f);
                float ph = c.t * Mathf.Lerp(0.30f, 0.45f, FxRand.H(c.seed, i, 0)) + FxRand.H(c.seed, i, 1);
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                const int pts = 9;
                for (int k = 0; k < pts; k++)
                {
                    float f = k / (float)(pts - 1);
                    float y = -0.10f + 0.34f * f;
                    float x = lat + 0.011f * Mathf.Sin(f * 11f - ph * Tau) + 0.004f * Mathf.Sin(f * 27f + i);
                    r.Add(a + c.camRight * x + Vector3.up * y, 0.0085f, A(JonahFx.HeatLine, 0.55f * env * Mathf.Sin(Mathf.PI * f) * (0.75f + 0.25f * Mathf.Sin(ph * Tau + i))));
                }
            }
            // shimmer on the ground
            for (int i = 0; i < 3; i++)
            {
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                float z = Mathf.Lerp(-0.12f, 0.12f, i / 2f);
                const int pts = 10;
                for (int k = 0; k < pts; k++)
                {
                    float f = k / (float)(pts - 1);
                    float x = a.x - 0.30f + 0.60f * f;
                    float y = 0.026f + 0.010f * i + 0.005f * Mathf.Sin(x * 36f + c.t * 3f + i) + 0.002f * Mathf.Sin(x * 83f - c.t * 4.6f);
                    r.Add(new Vector3(x, y, a.z + z + 0.02f * Mathf.Sin(f * 3f + i)), 0.010f, A(JonahFx.HeatLine, 0.30f * env * Mathf.Sin(Mathf.PI * f)));
                }
            }
        }
    }
}
