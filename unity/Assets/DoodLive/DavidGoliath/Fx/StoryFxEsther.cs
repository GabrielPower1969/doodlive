// Esther (story pack #2) effects, docs/esther/FX.md. Same engine as David & Goliath: every effect is a pure function
// of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered in
// FxLibrary next to the D&G ids (D&G ids win on a clash; `confetti` and `golden_rays` are shared, not redefined).
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// The two stage-light effects (tension_dim, truth_flash) only post requests to StoryLight; StoryFxStage
// (StoryFxEstherRuntime.cs) turns them into the dim overlay, the global shader values and the cold screen flash.
// Child-friendly rules as in D&G: one soft flash at most per beat, no strobe, nothing bright over Esther's face.
using System.Collections.Generic;
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Esther registry, palette and the one tunable target (the sceptre beam end).</summary>
    public static class EstherFx
    {
        /// <summary>Effects added to FxLibrary (CONTRACT §8 of docs/esther; confetti / golden_rays come from D&G).</summary>
        internal static FxDef[] Defs => new FxDef[]
        {
            new BrazierFire(), new CrownSparkle(), new RingGlint(), new PrayerGlow(),
            new SceptreBeam(), new TensionDim(), new TruthFlash(), new Petals(),
            new AngerSteam(), new SweatDrops(), new DustDrag(),
        };

        /// <summary>Stage-local point (art units) that sceptre_beam reaches toward. Default: Esther's chest standing at the
        /// foot of the steps (CONTRACT §6 mark (0, -0.12), chest ~0.24 high). StoryFxStage.BeamTarget overrides it every frame.</summary>
        public static readonly Vector3 DefaultBeamTarget = new Vector3(0f, 0.24f, -0.12f);   // declared first: static init is in text order
        public static Vector3 BeamTarget = DefaultBeamTarget;

        // docs/esther/DESIGN.md demo colours + Paper & Crayon tokens (sRGB)
        internal static readonly Color Flame = new Color32(0xFF, 0x8A, 0x3D, 255);     // brazier flame
        internal static readonly Color Ember = new Color32(0xE8, 0x55, 0x3D, 255);     // DesignTokens.Red, flame base
        internal static readonly Color WarmWhite = new Color32(0xFF, 0xF1, 0xC8, 255); // flame core, beam core
        internal static readonly Color Ice = new Color32(0xD6, 0xEA, 0xFF, 255);       // truth_flash
        internal static readonly Color Rose = new Color32(0xE8, 0x60, 0x7A, 255);
        internal static readonly Color Crimson = new Color32(0xC8, 0x32, 0x3F, 255);   // Esther's cape
        internal static readonly Color Blush = new Color32(0xFB, 0xD3, 0xDF, 255);
        internal static readonly Color SteamRed = new Color32(0xF2, 0x8C, 0x7E, 255);  // hot steam (DesignTokens.Red, softened)
        internal static readonly Color SweatBlue = new Color32(0x9F, 0xD4, 0xF5, 255); // sweat drop fill (Sky, lightened)
        internal static readonly Color SweatRim = new Color32(0x4B, 0x93, 0xD0, 255);  // sweat drop crayon edge
        internal static readonly Color DragDust = new Color32(0xE6, 0xD2, 0xA8, 255);  // beige dust (PaperDeep, a bit warmer)
    }

    /// <summary>
    /// Stage light requests from the effects (pure, no engine calls). Each running tension_dim / truth_flash posts its
    /// current level every frame under its seed; StoryFxStage resolves the maximum once per frame. A request that is not
    /// renewed for two resolves disappears, so stopping or destroying the effect releases the light by itself.
    /// </summary>
    public static class StoryLight
    {
        /// <summary>Peak opacity of the evening-blue dim (0..1) and of the cold flash.</summary>
        public static float DimStrength = 0.45f;
        public static float FlashStrength = 0.5f;

        /// <summary>Incremented by Reset (DGFx.StopAll); the runtime drops the current dim at once when it changes.</summary>
        public static int Epoch { get; private set; }

        struct Req { public float v; public int tick; }
        static readonly Dictionary<int, Req> dims = new Dictionary<int, Req>();
        static readonly Dictionary<int, Req> flashes = new Dictionary<int, Req>();
        static readonly List<int> stale = new List<int>();
        static int tick;

        public static void RequestDim(int key, float level) => dims[key] = new Req { v = Sat(level), tick = tick };
        public static void RequestFlash(int key, float level) => flashes[key] = new Req { v = Sat(level), tick = tick };

        /// <summary>Called once per frame by the runtime: the strongest live requests (0..1 each).</summary>
        public static void Resolve(out float dim, out float flash)
        {
            dim = Max(dims);
            flash = Max(flashes);
            tick++;
        }

        public static void Reset()
        {
            dims.Clear(); flashes.Clear();
            Epoch++;
        }

        static float Max(Dictionary<int, Req> d)
        {
            float m = 0f;
            stale.Clear();
            foreach (var kv in d)
            {
                if (kv.Value.tick < tick - 1) stale.Add(kv.Key);
                else if (kv.Value.v > m) m = kv.Value.v;
            }
            foreach (int k in stale) d.Remove(k);
            return m;
        }
    }

    // ------------------------------------------------------------------ S01-S07: the two braziers (loop)
    public sealed class BrazierFire : FxDef
    {
        public override string Id => "brazier_fire";
        public override float DefaultDur => 999f;      // "until stopped": DGFx.StopAll() ends it
        static readonly Color Flame = EstherFx.Flame, Ember = EstherFx.Ember;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.5f, 0.6f);
            if (env <= 0) return;
            float ph = 20f * FxRand.H(c.seed, 0, 99);   // own phase so flameL and flameR never flicker in step
            float t = c.t + ph;
            float fl = Flicker(t);                       // ~0.78..1.05
            Vector3 o = c.anchor;
            Vector3 away = (o - c.camPos).normalized;

            // warm pool of light on the page under the brazier, and a soft glow behind the flame
            b.Sprite(FxCtx.Ground(o, 0.004f), 0.22f * (0.96f + 0.04f * fl), A(Flame, 0.30f * env * fl), DGFxPaint.GlowDisc,
                     c.t * 0.1f, false, FxFace.Ground);
            b.Sprite(o + Vector3.up * 0.04f + away * 0.02f, 0.17f * fl, A(Sun, 0.38f * env), DGFxPaint.SoftDot, 0, false);

            // flame tongues, back to front: three red-orange outer tongues, an orange-sun inner one, a warm-white core
            Vector3 bs = o - Vector3.up * 0.004f;
            Tongue(b, c, bs, t, -0.013f, 0.060f, 0.032f, Ember, Flame, 1.7f, 0.85f * env);
            Tongue(b, c, bs, t, 0.013f, 0.055f, 0.032f, Ember, Flame, 4.1f, 0.85f * env);
            Tongue(b, c, bs, t, 0f, 0.090f, 0.050f, Ember, Sun, 0f, 0.95f * env);
            Tongue(b, c, bs, t, 0.002f, 0.062f, 0.030f, Flame, Sun, 2.6f, env);
            Tongue(b, c, bs, t, 0f, 0.032f, 0.014f, Sun, EstherFx.WarmWhite, 5.3f, env);
            // small additive core: lifts the flame where the set behind it is coloured (invisible on white paper)
            b.Sprite(o + Vector3.up * 0.022f, 0.05f * fl, A(Sun, 0.35f * env), DGFxPaint.SoftDot, 0, true);

            // sparks that rise, drift and wink out
            const int n = 7;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(1.1f, 1.7f, FxRand.H(c.seed, i, 0));
                float p = c.t / period + FxRand.H(c.seed, i, 1);
                float a = p - Mathf.Floor(p);
                int cycle = (int)Mathf.Floor(p);
                float sx = FxRand.Signed(c.seed, i * 31 + cycle, 2) * 0.014f;
                float rise = Mathf.Lerp(0.10f, 0.18f, FxRand.H(c.seed, i * 31 + cycle, 3));
                Vector3 q = o + c.camRight * (sx + 0.012f * Mathf.Sin(a * 7f + i)) + Vector3.up * (0.03f + rise * a);
                float alpha = Sat(a * 6f) * (1 - a) * env;
                b.Sprite(q, 0.016f * (1 - a) + 0.004f, A(i % 2 == 0 ? Sun : Flame, alpha), DGFxPaint.Sparkle, a * 3f + i, false);
            }
        }

        static float Flicker(float t) =>
            0.92f + 0.06f * Mathf.Sin(t * 9.1f) + 0.04f * Mathf.Sin(t * 15.7f + 1.3f) + 0.03f * Mathf.Sin(t * 27.3f + 0.4f);

        /// <summary>One crayon flame tongue: a camera-facing ribbon, wide near the base, tapering and swaying at the tip.</summary>
        static void Tongue(FxBatch b, FxCtx c, Vector3 bs, float t, float side, float height, float width,
                           Color baseCol, Color tipCol, float phase, float alpha)
        {
            const int pts = 8;
            float h = height * (0.86f + 0.10f * Mathf.Sin(t * 7.3f + phase) + 0.06f * Mathf.Sin(t * 12.9f + phase * 2.1f));
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);
                float sway = (0.6f * Mathf.Sin(t * 6.5f + phase - f * 3.2f) + 0.4f * Mathf.Sin(t * 11.3f + phase * 1.7f - f * 5f))
                             * 0.012f * f * f;
                Vector3 p = bs + c.camRight * (side * (1 - 0.6f * f) + sway) + Vector3.up * (h * f);
                float w = width * Mathf.Sin(Mathf.PI * Mathf.Lerp(0.35f, 1f, f));   // bulb near the base, point at the tip
                r.Add(p, Mathf.Max(w, 0.001f), A(Color.Lerp(baseCol, tipCol, f), alpha));
            }
        }
    }

    // ------------------------------------------------------------------ the king's crown twinkles
    public sealed class CrownSparkle : FxDef
    {
        public override string Id => "crown_sparkle";
        public override float DefaultDur => 1.6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.15f, 0.35f);
            Vector3 centre = c.anchor + Vector3.up * 0.03f;
            Vector3 away = (centre - c.camPos).normalized;
            b.Sprite(centre + away * 0.03f, 0.12f, A(Gold, 0.25f * env), DGFxPaint.SoftDot, 0, false);
            const int n = 7;
            float span = Mathf.Max(0.2f, c.dur - 0.5f);
            for (int i = 0; i < n; i++)
            {
                float t0 = span * (i + 0.6f * FxRand.H(c.seed, i, 0)) / n;
                float a = (c.t - t0) / 0.5f;
                if (a <= 0 || a >= 1) continue;
                float ang = Tau * (i * 0.382f + FxRand.H(c.seed, i, 1));
                Vector3 p = centre + Flat(ang, Mathf.Lerp(0.025f, 0.042f, FxRand.H(c.seed, i, 2)))
                                   + Vector3.up * Mathf.Lerp(-0.012f, 0.035f, FxRand.H(c.seed, i, 3));
                float pop = Mathf.Sin(Mathf.PI * a);
                Color col = i % 3 == 0 ? EstherFx.WarmWhite : (i % 3 == 1 ? Sun : Gold);
                b.Sprite(p, 0.055f * pop, A(col, pop * env), DGFxPaint.Sparkle, a * 1.5f, false);
            }
            // one bigger twinkle on top of the crown at the start
            float k = c.t / 0.55f;
            if (k < 1) b.Sprite(centre + Vector3.up * 0.035f, 0.075f * Mathf.Sin(Mathf.PI * k), A(Sun, env), DGFxPaint.Sparkle, k * 0.8f, false);
        }
    }

    // ------------------------------------------------------------------ the signet ring catches the light (S04)
    public sealed class RingGlint : FxDef
    {
        public override string Id => "ring_glint";
        public override float DefaultDur => 0.8f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float k = c.N;
            float pop = Mathf.Pow(Mathf.Sin(Mathf.PI * k), 0.7f);
            Vector3 p = c.anchor + (c.camPos - c.anchor).normalized * 0.012f;   // just in front of the ring
            b.Sprite(p, 0.07f * pop, A(Gold, 0.45f * pop), DGFxPaint.SoftDot, 0, false);
            b.Sprite(p, 0.075f * pop, A(Sun, pop), DGFxPaint.Sparkle, 0.6f * k, false);
            b.Sprite(p, 0.04f * pop, A(EstherFx.WarmWhite, pop), DGFxPaint.Sparkle, 0.785f + 0.6f * k, false);
            for (int i = 0; i < 3; i++)
            {
                float ang = Tau * (i / 3f + 0.1f) + k;
                Vector3 dir = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                float a = Sat((k - 0.15f) / 0.85f);
                b.Sprite(p + dir * (0.015f + 0.035f * OutCubic(a)), 0.016f * (1 - a), A(Gold, 1 - a), DGFxPaint.Sparkle, i, false);
            }
        }
    }

    // ------------------------------------------------------------------ S05-S06: Esther prays
    public sealed class PrayerGlow : FxDef
    {
        public override string Id => "prayer_glow";
        public override float DefaultDur => 6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.0f, 1.2f);
            float breathe = 0.85f + 0.15f * Mathf.Sin(c.t * Tau * 0.4f);
            Vector3 chest = c.anchor;
            Vector3 away = (chest - c.camPos).normalized;
            // warm pool on the page, a halo BEHIND her (the depth test hides it where her body is), a soft warmth at the chest
            b.Sprite(FxCtx.Ground(chest, 0.004f), 0.24f, A(Gold, 0.5f * env * breathe), DGFxPaint.GlowDisc, c.t * 0.1f, false, FxFace.Ground);
            b.Sprite(chest + away * 0.06f + Vector3.up * 0.01f, 0.28f, A(Sun, 0.40f * env * breathe), DGFxPaint.SoftDot, 0, false);
            b.Sprite(chest + away * 0.025f, 0.11f, A(Gold, 0.22f * env * breathe), DGFxPaint.SoftDot, 0, false);

            // slow motes rising around her chest; dimmed where they would pass in front of her face
            Vector3 toCam = c.ToCamFlat(chest);
            const int n = 14;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(2.8f, 4.2f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                float ang = Tau * (i + 0.5f * FxRand.H(c.seed, i, 2)) / n + 0.25f * a;
                float rad = Mathf.Lerp(0.06f, 0.10f, FxRand.H(c.seed, i, 3));
                Vector3 off = Flat(ang, rad);
                float y = Mathf.Lerp(-0.07f, 0.14f, a);
                float front = Vector3.Dot(off / rad, toCam);
                float faceGuard = (y > 0.05f && front > 0.5f) ? 0.2f : 1f;
                float life = Mathf.Sin(Mathf.PI * a);
                bool twinkle = i % 3 == 0;
                b.Sprite(chest + off + Vector3.up * y, twinkle ? 0.022f * life + 0.004f : 0.026f,
                         A(i % 2 == 0 ? Sun : Gold, life * env * faceGuard * (twinkle ? 1f : 0.8f)),
                         twinkle ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, a * 2f, false);
            }
        }
    }

    // ------------------------------------------------------------------ S08: the king holds out the golden sceptre
    public sealed class SceptreBeam : FxDef
    {
        public override string Id => "sceptre_beam";
        public override float DefaultDur => 4f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.25f, 0.8f);
            Vector3 tip = c.anchor;
            Vector3 to = EstherFx.BeamTarget - tip;
            float len = to.magnitude;
            Vector3 dir = len > 1e-4f ? to / len : Vector3.forward;
            float reach = OutCubic(c.t / 0.6f);                      // the beam grows out of the tip in 0.6 s
            float stop = Mathf.Max(0f, len - 0.03f);                 // ends just short of her
            Vector3 end = tip + dir * (stop * reach);
            float pulse = 0.9f + 0.1f * Mathf.Sin(c.t * Tau * 1.1f);

            // glow on her side (behind her, away from the camera), then the beam, widest and softest first
            Vector3 tgtGlow = EstherFx.BeamTarget + (EstherFx.BeamTarget - c.camPos).normalized * 0.05f;
            b.Sprite(tgtGlow, 0.18f, A(Gold, 0.32f * env * reach), DGFxPaint.SoftDot, 0, false);
            if (stop > 0.02f && reach > 0.02f)
            {
                Beam(b, tip, end, 0.075f * pulse, A(Gold, 0.38f * env));
                Beam(b, tip, end, 0.036f * pulse, A(Sun, 0.62f * env));
                Beam(b, tip, end, 0.012f, A(EstherFx.WarmWhite, 0.85f * env));
            }

            // sparkles gliding along the beam from the sceptre to Esther
            const int n = 12;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(1.0f, 1.4f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                float along = a * stop;
                if (along > stop * reach) continue;
                Vector3 p = tip + dir * along + c.camUp * (0.012f * Mathf.Sin(a * 9f + i)) + c.camRight * (0.006f * FxRand.Signed(c.seed, i, 2));
                float life = Mathf.Sin(Mathf.PI * a);
                b.Sprite(p, 0.028f * life + 0.005f, A(i % 2 == 0 ? Sun : Gold, life * env), DGFxPaint.Sparkle, a * 4f + i, false);
            }

            // the knob shines: soft gold halo, a slow four-point star, a small additive core
            b.Sprite(tip, 0.13f * pulse, A(Sun, 0.5f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(tip, 0.085f * pulse * OutBack(c.t / 0.35f), A(Sun, env), DGFxPaint.Sparkle, 0.4f * c.t, false);
            b.Sprite(tip, 0.06f, A(EstherFx.WarmWhite, 0.4f * env), DGFxPaint.SoftDot, 0, true);

            // opening burst: ten twinkles fly out of the knob (pairs with the bell sparkle in the music)
            float k = c.t / 0.7f;
            if (k < 1)
            {
                for (int i = 0; i < 10; i++)
                {
                    float ang = Tau * (i + FxRand.H(c.seed, i, 5)) / 10f;
                    Vector3 d = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                    float r = 0.02f + Mathf.Lerp(0.07f, 0.11f, FxRand.H(c.seed, i, 6)) * OutCubic(k);
                    b.Sprite(tip + d * r, 0.03f * (1 - k), A(i % 2 == 0 ? Sun : Gold, (1 - k) * env), DGFxPaint.Sparkle, i + k, false);
                }
            }
        }

        static void Beam(FxBatch b, Vector3 a, Vector3 e, float width, Color col)
        {
            var r = b.Ribbon(DGFxPaint.Streak, false);   // streak cell: soft at both ends
            r.Add(a, width, col);
            r.Add(Vector3.Lerp(a, e, 0.5f), width, col);
            r.Add(e, width * 0.8f, col);
        }
    }

    // ------------------------------------------------------------------ S03-S07, S10: evening blue tension
    public sealed class TensionDim : FxDef
    {
        public override string Id => "tension_dim";
        public override float DefaultDur => 8f;
        public override bool Follow => false;

        // Draws nothing itself: posts its level to StoryLight; StoryFxStage draws the overlay / sets the shader globals.
        public override void Emit(FxCtx c, FxBatch b)
        {
            StoryLight.RequestDim(c.seed, StoryLight.DimStrength * Env(c.t, c.dur, 1.2f, 1.5f));
        }
    }

    // ------------------------------------------------------------------ S10: the truth is told
    public sealed class TruthFlash : FxDef
    {
        public override string Id => "truth_flash";
        public override float DefaultDur => 0.6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float f = 1 - Sat(c.t / 0.35f);
            StoryLight.RequestFlash(c.seed, StoryLight.FlashStrength * f * f);   // one cold flash, no strobe

            float k = c.N;
            float fade = 1 - Smooth(0.4f, 1f, k);
            Vector3 p = c.anchor + (c.camPos - c.anchor).normalized * 0.04f;
            b.Sprite(p, 0.25f * (0.6f + 0.4f * k), A(White, 0.75f * (1 - k)), DGFxPaint.SoftDot, 0, false);
            b.Sprite(p, 0.06f + 0.30f * OutCubic(k), A(Color.Lerp(EstherFx.Ice, Sky, 0.4f), 0.9f * (1 - k)), DGFxPaint.Ring, 0.5f, false);
            float k2 = Sat((c.t - 0.08f) / Mathf.Max(0.1f, c.dur - 0.08f));
            if (k2 > 0) b.Sprite(p, 0.04f + 0.20f * OutCubic(k2), A(EstherFx.Ice, 0.8f * (1 - k2)), DGFxPaint.Ring, 2.1f, false);
            for (int i = 0; i < 8; i++)
            {
                float ang = Tau * i / 8f + 0.39f;
                Vector3 d = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                float r0 = 0.04f + 0.12f * OutCubic(k), r1 = r0 + 0.06f * (1 - k) + 0.02f;
                var l = b.Ribbon(DGFxPaint.Ribbon, false);
                l.Add(p + d * r0, 0.011f, A(EstherFx.Ice, fade));
                l.Add(p + d * r1, 0.003f, A(Sky, fade));
            }
            for (int i = 0; i < 6; i++)
            {
                float ang = Tau * (i + FxRand.H(c.seed, i, 0)) / 6f;
                Vector3 d = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                float r = 0.03f + Mathf.Lerp(0.12f, 0.18f, FxRand.H(c.seed, i, 1)) * OutCubic(k);
                b.Sprite(p + d * r, 0.03f * (1 - k), A(i % 2 == 0 ? EstherFx.Ice : White, 1 - k), DGFxPaint.Sparkle, i, false);
            }
        }
    }

    // ------------------------------------------------------------------ S11-S12: rose petals around the banquet table
    public sealed class Petals : FxDef
    {
        public override string Id => "petals";
        public override float DefaultDur => 5f;
        public override bool Follow => false;            // petals stay where they fell

        static readonly Color[] Palette =
        {
            DesignTokens.Pink, EstherFx.Rose, EstherFx.Blush, DesignTokens.Pink, EstherFx.Crimson, EstherFx.Rose,
        };

        public override void Emit(FxCtx c, FxBatch b)
        {
            Vector3 o = c.start;
            float fade = 1 - Smooth(c.dur - 0.8f, c.dur, c.t);
            float spawnSpan = Mathf.Max(0.2f, c.dur * 0.55f);
            const int n = 36;
            for (int i = 0; i < n; i++)
            {
                float t = c.t - spawnSpan * FxRand.H(c.seed, i, 0);
                if (t <= 0) continue;
                float ang = Tau * FxRand.H(c.seed, i, 1);
                float rad = Mathf.Lerp(0.05f, 0.26f, Mathf.Sqrt(FxRand.H(c.seed, i, 2)));
                float y0 = o.y + Mathf.Lerp(0.32f, 0.48f, FxRand.H(c.seed, i, 3));
                float vs = Mathf.Lerp(0.07f, 0.11f, FxRand.H(c.seed, i, 4));   // slow, papery fall (art units / s)
                float tLand = Mathf.Max(0f, (y0 - 0.004f) / vs);
                bool landed = t >= tLand;
                float ts = landed ? tLand : t;
                float ph = Tau * FxRand.H(c.seed, i, 5);
                float ease = Sat(ts * 1.5f);
                Vector3 p = o + Flat(ang, rad)
                          + new Vector3(Mathf.Sin(ts * 2.2f + ph) * 0.025f, 0, Mathf.Cos(ts * 1.7f + ph) * 0.015f) * ease;
                p.y = landed ? 0.004f : y0 - vs * t;
                float flip = landed ? 1f : 0.3f + 0.7f * Mathf.Abs(Mathf.Cos(t * 3f + ph));
                Color col = Palette[i % Palette.Length];
                b.Sprite(p, 0.03f, 0.019f * flip, A(col, fade * Sat(t * 4f)), DGFxPaint.ConfettiDot,
                         ph + ts * 1.6f, false, landed ? FxFace.Ground : FxFace.Camera);
            }
        }
    }

    // ------------------------------------------------------------------ S03: Haman's tantrum, steam from both ears
    public sealed class AngerSteam : FxDef
    {
        public override string Id => "anger_steam";
        public override float DefaultDur => 3.6f;

        const float Period = 0.55f;        // one "pfff" per side every 0.55 s, like a kettle on the boil
        const int PerBurst = 4;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.05f, 0.45f);
            if (env <= 0) return;
            Vector3 head = c.anchor;
            float lastStart = Mathf.Max(0.05f, c.dur - 0.5f);
            int bursts = Mathf.FloorToInt(lastStart / Period) + 1;
            // oldest first so the newest puffs draw on top
            for (int k = 0; k < bursts; k++)
            {
                float tb = 0.05f + k * Period;
                if (tb > c.t) break;
                if (c.t - tb > 1.3f) continue;
                for (int side = -1; side <= 1; side += 2)
                {
                    int sid = side < 0 ? 0 : 1;
                    float tSide = tb + (sid == 1 ? 0.07f : 0f);             // right ear a hair later: lively, not mirrored
                    Vector3 ear = head + c.camRight * (side * 0.042f) + Vector3.up * 0.012f;
                    // hotter at the start of the tantrum, cooler (whiter) later
                    float heat = Mathf.Lerp(1f, 0.45f, Sat(tb / Mathf.Max(0.5f, c.dur)));

                    // the jet: a short white streak shooting out of the ear in the first 0.18 s of the burst
                    float jk = (c.t - tSide) / 0.18f;
                    if (jk > 0 && jk < 1)
                    {
                        Vector3 jd = (c.camRight * side * 0.85f + Vector3.up * 0.55f).normalized;
                        var r = b.Ribbon(DGFxPaint.Streak, false);
                        float len = 0.05f * OutCubic(jk);
                        Color jc = Color.Lerp(EstherFx.SteamRed, White, 0.5f);
                        r.Add(ear + jd * (0.004f + len * 0.25f * jk), 0.016f, A(jc, 0.8f * (1 - jk) * env));
                        r.Add(ear + jd * (0.004f + len), 0.012f, A(White, 0.8f * (1 - jk) * env));
                    }

                    for (int j = 0; j < PerBurst; j++)
                    {
                        int id = (k * 2 + sid) * PerBurst + j;
                        float t0 = tSide + 0.03f * j + 0.02f * FxRand.H(c.seed, id, 0);
                        float life = Mathf.Lerp(0.85f, 1.1f, FxRand.H(c.seed, id, 1));
                        float a = (c.t - t0) / life;
                        if (a <= 0 || a >= 1) continue;
                        // all puffs of one burst leave on nearly the same line so they read as one cloud
                        float el = 0.45f + 0.35f * FxRand.Signed(c.seed, k * 2 + sid, 2) * 0.5f + 0.18f * (j - 1);
                        Vector3 dir = c.camRight * (side * Mathf.Cos(el)) + Vector3.up * Mathf.Sin(el);
                        float e = OutCubic(a * 1.25f);
                        float dist = (0.05f + 0.018f * j) * e;
                        Vector3 p = ear + dir * (0.006f + dist) + Vector3.up * (0.06f * a * a)         // shoots out, then drifts up
                                  + c.camUp * (0.013f * FxRand.Signed(c.seed, id, 3));
                        float size = Mathf.Lerp(0.022f, 0.075f - 0.006f * j, e) * Mathf.Lerp(0.9f, 1.1f, FxRand.H(c.seed, id, 5))
                                     * (0.7f + 0.3f * OutBack(a * 5f));
                        float hot = heat * (1 - Smooth(0.0f, 0.6f, a));
                        Color col = Color.Lerp(White, EstherFx.SteamRed, 0.8f * hot);
                        float alpha = Sat(a * 12f) * (1 - Smooth(0.55f, 1f, a)) * env;      // solid puff, thins out at the end
                        b.Sprite(p, size, A(col, alpha), DGFxPaint.Dust, FxRand.H(c.seed, id, 6) * Tau + a * 0.8f);
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ S10: Haman is exposed, cartoon sweat drops
    public sealed class SweatDrops : FxDef
    {
        public override string Id => "sweat_drops";
        public override float DefaultDur => 2f;

        const float Grav = 2.2f;           // art units / s^2: a lazy cartoon arc, not a real fall

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0f, 0.3f);
            if (env <= 0) return;
            int n = 3 + Mathf.Min(3, (int)(FxRand.H(c.seed, 99, 0) * 4f));   // 3..6 drops
            float span = Mathf.Max(0.3f, Mathf.Min(1.1f, c.dur * 0.55f));
            for (int i = 0; i < n; i++)
            {
                float t0 = 0.04f + span * (i + 0.6f * FxRand.H(c.seed, i, 0)) / n;
                float ts = c.t - t0;
                if (ts <= 0) continue;
                float side = (i % 2 == 0 ? 1f : -1f) * (FxRand.H(c.seed, i, 9) < 0.2f ? -1f : 1f);
                Vector3 head = c.track.Count > 0 ? c.track.Sample(t0) : c.anchor;   // flicked off where the head WAS
                Vector3 p0 = head + c.camRight * (side * Mathf.Lerp(0.035f, 0.05f, FxRand.H(c.seed, i, 1)))
                                  + Vector3.up * Mathf.Lerp(0.015f, 0.04f, FxRand.H(c.seed, i, 2));
                Vector3 v0 = c.camRight * (side * Mathf.Lerp(0.12f, 0.22f, FxRand.H(c.seed, i, 3)))
                           + Vector3.up * Mathf.Lerp(0.30f, 0.45f, FxRand.H(c.seed, i, 4))
                           + c.ToCamFlat(head) * (0.08f * FxRand.Signed(c.seed, i, 5));
                // time to reach the page (y = 0.004): y0 + vy t - g t^2 / 2 = 0.004
                float y0 = p0.y - 0.004f, vy = v0.y;
                float tLand = (vy + Mathf.Sqrt(Mathf.Max(0f, vy * vy + 2f * Grav * y0))) / Grav;
                if (ts < tLand)
                {
                    Vector3 p = p0 + v0 * ts + Vector3.down * (0.5f * Grav * ts * ts);
                    Vector3 vel = v0 + Vector3.down * (Grav * ts);
                    float pop = OutBack(ts / 0.12f);
                    Drop(b, c, p, vel, 0.034f * pop, env);
                }
                else
                {   // tiny splash on the page: a flat ring, a wet spot that fades, three droplets that hop out
                    float k = (ts - tLand) / 0.4f;
                    if (k >= 1) continue;
                    Vector3 g = p0 + v0 * tLand; g.y = 0.004f;
                    b.Sprite(g, 0.022f * (1 - k) + 0.012f, A(EstherFx.SweatBlue, 0.55f * (1 - k) * env), DGFxPaint.SoftDot,
                             0, false, FxFace.Ground);
                    b.Sprite(g, 0.012f + 0.035f * OutCubic(k), A(EstherFx.SweatRim, 0.8f * (1 - k) * env), DGFxPaint.Ring,
                             i, false, FxFace.Ground);
                    for (int s = 0; s < 3; s++)
                    {
                        float ang = Tau * (s / 3f + FxRand.H(c.seed, i * 7 + s, 6));
                        float hop = Mathf.Sin(Mathf.PI * Sat(k * 1.6f));
                        Vector3 q = g + Flat(ang, 0.006f + 0.022f * OutCubic(k)) + Vector3.up * (0.012f * hop);
                        b.Sprite(q, 0.008f * (1 - k), A(EstherFx.SweatBlue, (1 - k) * env), DGFxPaint.ConfettiDot, 0, false);
                    }
                }
            }
        }

        /// <summary>A cartoon teardrop: round front, pointed tail trailing behind the motion, crayon edge, white shine.</summary>
        static void Drop(FxBatch b, FxCtx c, Vector3 p, Vector3 vel, float size, float alpha)
        {
            if (size <= 1e-4f) return;
            // the direction of travel projected on the screen, so the tail always points back along the arc
            Vector3 vs = c.camRight * Vector3.Dot(vel, c.camRight) + c.camUp * Vector3.Dot(vel, c.camUp);
            Vector3 fwd = vs.sqrMagnitude > 1e-6f ? vs.normalized : -c.camUp;
            float R = size * 0.42f, L = size * 1.25f;          // bulb radius, total length (front tip to tail tip)
            DropRibbon(b, p, fwd, R + 0.005f, L + 0.008f, A(EstherFx.SweatRim, alpha));   // edge first
            DropRibbon(b, p, fwd, R, L, A(EstherFx.SweatBlue, alpha));
            Vector3 side = Vector3.Cross(fwd, (c.camPos - p).normalized).normalized;
            b.Sprite(p - fwd * (R * 0.9f) + side * (R * 0.35f), R * 0.75f, A(White, 0.9f * alpha), DGFxPaint.SoftDot, 0, false);
        }

        static void DropRibbon(FxBatch b, Vector3 p, Vector3 fwd, float R, float L, Color col)
        {
            // points run from the front tip (round end) to the tail tip; the ribbon cell fades at the last point
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            const int pts = 9;
            Vector3 front = p + fwd * (R * 0.2f);
            for (int k = 0; k < pts; k++)
            {
                float x = L * k / (pts - 1);
                float w = x < R ? 2f * Mathf.Sqrt(Mathf.Max(0f, R * R - (R - x) * (R - x)))
                                : 2f * R * (1f - (x - R) / (L - R));
                r.Add(front - fwd * x, Mathf.Max(w * 1.15f, 0.0008f), col);
            }
        }
    }

    // ------------------------------------------------------------------ S10: guards drag Haman away, dust at his feet
    public sealed class DustDrag : FxDef
    {
        public override string Id => "dust_drag";
        public override float DefaultDur => 4f;

        const float Step = 0.09f;          // a puff pair every 0.09 s of travel
        const float Life = 1.1f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0f, 0.6f);
            if (env <= 0 || c.track.Count == 0) return;
            int first = Mathf.Max(0, Mathf.FloorToInt((c.t - Life * 1.4f) / Step));
            int last = Mathf.FloorToInt(Mathf.Min(c.t, c.dur - 0.4f) / Step);
            for (int k = first; k <= last; k++)
            {
                float ts = k * Step;
                float age = c.t - ts;
                if (age < 0) continue;
                Vector3 p = c.track.Sample(ts), q = c.track.Sample(ts - 0.1f);
                Vector3 mv = p - q; mv.y = 0;
                float speed = mv.magnitude / 0.1f;
                float strength = Smooth(0.015f, 0.09f, speed);        // standing still: no dust
                if (strength < 0.05f) continue;
                Vector3 back = mv / Mathf.Max(1e-5f, mv.magnitude);
                Vector3 across = new Vector3(-back.z, 0, back.x);
                back = -back;
                Vector3 g = FxCtx.Ground(p, 0.004f);

                // the scuff left on the page: a flat beige smudge that lingers a little longer than the puffs
                float sa = age / (Life * 1.4f);
                if (sa < 1)
                    b.Sprite(g + across * (0.008f * FxRand.Signed(c.seed, k, 0)), Mathf.Lerp(0.03f, 0.05f, OutCubic(sa)) * (0.6f + 0.4f * strength),
                             A(EstherFx.DragDust, 0.45f * strength * Sat(sa * 8f) * (1 - sa) * env), DGFxPaint.Dust,
                             FxRand.H(c.seed, k, 1) * Tau, false, FxFace.Ground);

                for (int s = 0; s < 2; s++)
                {
                    int id = k * 2 + s;
                    float life = Life * Mathf.Lerp(0.75f, 1f, FxRand.H(c.seed, id, 2));
                    float a = age / life;
                    if (a >= 1) continue;
                    float e = OutCubic(a);
                    float sideSign = s == 0 ? -1f : 1f;
                    float hump = 4f * a * (1 - a);                       // up a little, then settles back on the page
                    Vector3 pos = g + back * (0.025f * e * Mathf.Lerp(0.6f, 1.2f, FxRand.H(c.seed, id, 3)))
                                    + across * (sideSign * (0.008f + 0.022f * e) * Mathf.Lerp(0.6f, 1.2f, FxRand.H(c.seed, id, 4)))
                                    + Vector3.up * (0.006f + 0.028f * hump * Mathf.Lerp(0.5f, 1f, FxRand.H(c.seed, id, 5)) * strength);
                    float size = Mathf.Lerp(0.018f, 0.06f, e) * Mathf.Lerp(0.8f, 1.2f, FxRand.H(c.seed, id, 6)) * (0.6f + 0.4f * strength);
                    Color col = Color.Lerp(EstherFx.DragDust, PaperDeep, 0.5f * FxRand.H(c.seed, id, 7));
                    b.Sprite(pos, size, A(col, 0.9f * strength * Sat(a * 8f) * Mathf.Pow(1 - a, 1.3f) * env), DGFxPaint.Dust,
                             FxRand.H(c.seed, id, 8) * Tau + a * 1.2f);
                }
            }
        }
    }
}
