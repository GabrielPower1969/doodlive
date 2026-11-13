// The eleven effect ids used by assets/david-goliath/timeline.json (docs/david-goliath/FX.md has the table).
// Each effect is a pure function of (time, anchor, camera, seed) -> sprites/ribbons, so pausing, frame drops and
// replays never change the look. Sizes and speeds are art-width units (David 0.30 tall, Goliath 0.80).
// Child-friendly rules: no red "blood" colours on impacts, no strobe (one soft flash at most), nothing covers
// David's face during his line in S07 (faith_glow stays behind / beside him).
using System.Collections.Generic;
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    public abstract class FxDef
    {
        public abstract string Id { get; }
        public abstract float DefaultDur { get; }
        /// <summary>True: 'anchor' follows the bone every frame. False: the effect stays where it started.</summary>
        public virtual bool Follow => true;
        /// <summary>Camera shake (art units) and screen flash (0..1) requested when the effect starts.</summary>
        public virtual float ShakeAmp => 0f;
        public virtual float ShakeDur => 0f;
        public virtual float Flash => 0f;
        public abstract void Emit(FxCtx c, FxBatch b);

        static readonly Color Ink = DesignTokens.Ink, InkSoft = DesignTokens.InkSoft;
        protected static Color Paper => DesignTokens.Paper;
        protected static Color PaperDeep => DesignTokens.PaperDeep;
        protected static Color Sun => DesignTokens.Sun;
        protected static Color Gold => DesignTokens.Gold;
        protected static Color Orange => DesignTokens.Orange;
        protected static Color Sky => DesignTokens.Sky;
        protected static Color SoftInk => InkSoft;
        protected static Color InkC => Ink;
        protected static readonly Color White = Color.white;
        protected static readonly Color Stone = new Color32(0xB9, 0xB4, 0xAA, 255);   // design.json david.stone

        protected static readonly Color[] Crayons =
        {
            DesignTokens.Red, DesignTokens.Orange, DesignTokens.Sun, DesignTokens.Leaf,
            DesignTokens.Sky, DesignTokens.Pink, DesignTokens.Grape,
        };
    }

    public static class FxLibrary
    {
        static Dictionary<string, FxDef> map;

        public static IReadOnlyDictionary<string, FxDef> All
        {
            get
            {
                if (map == null)
                {
                    map = new Dictionary<string, FxDef>();
                    foreach (var d in new FxDef[]
                             {
                                 new DustPuff(), new MemoryLionBear(), new BrookRipple(), new FaithGlow(), new SlingTrail(),
                                 new StoneTrail(), new HitFlash(), new DizzyStars(), new DustBurst(), new Confetti(), new GoldenRays(),
                             })
                        map[d.Id] = d;
                }
                return map;
            }
        }

        public static FxDef Get(string id) => id != null && All.TryGetValue(id, out var d) ? d : null;
    }

    // ------------------------------------------------------------------ S01: Goliath's footsteps
    public sealed class DustPuff : FxDef
    {
        public override string Id => "dust_puff";
        public override float DefaultDur => 0.6f;
        public override bool Follow => false;            // dust stays where the foot landed
        public override float ShakeAmp => 0.004f;
        public override float ShakeDur => 0.25f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            Vector3 g = FxCtx.Ground(c.start, 0.004f);
            float k = c.N;
            // ground ring first (drawn under the dust)
            b.Sprite(g, 0.04f + 0.24f * OutCubic(k), A(SoftInk, 0.6f * (1 - k)), DGFxPaint.Ring, k * 0.6f, false, FxFace.Ground);
            const int n = 10;
            for (int i = 0; i < n; i++)
            {
                float delay = 0.06f * FxRand.H(c.seed, i, 0);
                float life = c.dur * Mathf.Lerp(0.75f, 1f, FxRand.H(c.seed, i, 1)) - delay;
                float a = (c.t - delay) / Mathf.Max(0.05f, life);
                if (a <= 0 || a >= 1) continue;
                float ang = Tau * (i + 0.4f * FxRand.H(c.seed, i, 2)) / n;
                float e = OutCubic(a);
                Vector3 p = g + Flat(ang, 0.02f + Mathf.Lerp(0.07f, 0.12f, FxRand.H(c.seed, i, 3)) * e)
                              + Vector3.up * (0.008f + 0.035f * e * FxRand.H(c.seed, i, 4));
                float size = Mathf.Lerp(0.035f, 0.09f, e) * Mathf.Lerp(0.8f, 1.2f, FxRand.H(c.seed, i, 5));
                Color col = Color.Lerp(PaperDeep, SoftInk, 0.35f * FxRand.H(c.seed, i, 6));
                b.Sprite(p, size, A(col, 0.9f * Mathf.Pow(1 - a, 1.4f) * Sat(a * 8)), DGFxPaint.Dust,
                         FxRand.H(c.seed, i, 7) * Tau + a * 1.2f);
            }
        }
    }

    // ------------------------------------------------------------------ S05: David remembers the lion and the bear
    public sealed class MemoryLionBear : FxDef
    {
        public override string Id => "memory_lion_bear";
        public override float DefaultDur => 3.8f;

        // timeline: starts 38.8; lion_roar sfx 39.0 (t = 0.2); bear_growl sfx 40.4 (t = 1.6)
        const float LionAt = 0.2f, BearAt = 1.6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float t = c.t;
            float outK = 1 - InCubic((t - (c.dur - 0.45f)) / 0.45f);   // shrink away over the last 0.45 s
            if (outK <= 0) return;
            Vector3 head = c.anchor;
            Vector3 centre = head + Vector3.up * 0.17f + c.camRight * 0.03f;
            Vector3 toCam = (c.camPos - centre).normalized * 0.002f;   // animals float just in front of the bubble

            // three trailing puffs from the head up to the bubble
            for (int i = 0; i < 3; i++)
            {
                float pop = OutBack((t - 0.04f - 0.07f * i) / 0.18f) * outK;
                Vector3 p = Vector3.Lerp(head + Vector3.up * 0.055f + c.camRight * 0.01f, centre - Vector3.up * 0.075f, (i + 0.5f) / 3f);
                b.Sprite(p, (0.016f + 0.009f * i) * pop, White, DGFxPaint.Puff);
            }
            // bubble
            float bp = OutBack((t - 0.18f) / 0.3f) * outK;
            b.Sprite(centre, 0.33f * bp, 0.165f * bp, White, DGFxPaint.Bubble, 0, false, FxFace.Camera);
            Animal(b, c, centre - c.camRight * 0.075f + toCam, t - LionAt, outK, DGFxPaint.Lion);
            Animal(b, c, centre + c.camRight * 0.075f + toCam, t - BearAt, outK, DGFxPaint.Bear);
        }

        static void Animal(FxBatch b, FxCtx c, Vector3 p, float t, float outK, int cell)
        {
            if (t <= 0) return;
            float pop = OutBack(t / 0.25f) * outK;
            // a playful wiggle for 0.6 s while the roar / growl plays, then still
            float wig = 0.18f * Mathf.Sin(t * 26f) * (1 - Sat(t / 0.6f));
            float bounce = 0.006f * Mathf.Sin(t * 13f) * (1 - Sat(t / 0.6f));
            b.Sprite(p + c.camUp * bounce, 0.105f * pop, White, cell, wig);
        }
    }

    // ------------------------------------------------------------------ S06: five smooth stones from the brook
    public sealed class BrookRipple : FxDef
    {
        public override string Id => "brook_ripple";
        public override float DefaultDur => 2.4f;
        public override bool Follow => false;

        // ring starts relative to Play: splash at 0, then the five stone_clack sfx (+0.6 .. +2.2) minus a lead
        static readonly float[] Rings = { 0f, 0.55f, 0.95f, 1.35f, 1.75f };

        public override void Emit(FxCtx c, FxBatch b)
        {
            Vector3 g = FxCtx.Ground(c.start, 0.003f) + c.ToCamFlat(c.start) * 0.01f;
            float env = Env(c.t, c.dur, 0.25f, 0.5f);
            // a patch of brook water so the rings read as water on paper
            b.Sprite(g, 0.2f, 0.15f, A(Sky, 0.35f * env), DGFxPaint.GlowDisc, 0.3f, false, FxFace.Ground);
            for (int i = 0; i < Rings.Length; i++)
            {
                float a = (c.t - Rings[i]) / 0.9f;
                if (a <= 0 || a >= 1) continue;
                Vector3 p = g + new Vector3(FxRand.Signed(c.seed, i, 0), 0, FxRand.Signed(c.seed, i, 1)) * 0.015f;
                b.Sprite(p, 0.02f + 0.13f * OutCubic(a), A(Sky, 0.95f * (1 - a) * env), DGFxPaint.Ring, i * 1.3f, false, FxFace.Ground);
            }
            // splash droplets at the start
            for (int i = 0; i < 9; i++)
            {
                float life = 0.55f;
                float a = c.t / life;
                if (a >= 1) break;
                float ang = Tau * (i + FxRand.H(c.seed, i, 2)) / 9f;
                Vector3 v0 = Flat(ang, Mathf.Lerp(0.08f, 0.16f, FxRand.H(c.seed, i, 3))) + Vector3.up * Mathf.Lerp(0.25f, 0.4f, FxRand.H(c.seed, i, 4));
                Vector3 p = Ballistic(g, v0, 1.6f, 0f, c.t);
                if (p.y < 0.003f) continue;
                b.Sprite(p, 0.016f, A(Sky, 1 - a), DGFxPaint.ConfettiDot);
            }
        }
    }

    // ------------------------------------------------------------------ S07: "in the name of the LORD"
    public sealed class FaithGlow : FxDef
    {
        public override string Id => "faith_glow";
        public override float DefaultDur => 5.6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 1.0f);
            float breathe = 0.85f + 0.15f * Mathf.Sin(c.t * Tau * 0.7f);
            Vector3 chest = c.anchor;
            Vector3 g = FxCtx.Ground(chest, 0.004f);
            // warm pool of light on the page under him
            b.Sprite(g, 0.30f, A(Gold, 0.7f * env * breathe), DGFxPaint.GlowDisc, c.t * 0.2f, false, FxFace.Ground);
            // halo glow BEHIND him (pushed away from the camera; the depth test hides it where his body is)
            Vector3 away = (chest - c.camPos).normalized;
            b.Sprite(chest + away * 0.07f + Vector3.up * 0.02f, 0.36f, A(Sun, 0.45f * env * breathe), DGFxPaint.SoftDot, 0, false);
            // rising sparkles on a ring around him, kept off his face
            Vector3 toCam = c.ToCamFlat(chest);
            const int n = 18;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(1.4f, 2.0f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                float ang = Tau * (i + 0.5f * FxRand.H(c.seed, i, 2)) / n + 0.4f * a;
                float rad = Mathf.Lerp(0.08f, 0.115f, FxRand.H(c.seed, i, 3));
                Vector3 offset = Flat(ang, rad);
                float y = Mathf.Lerp(0.01f, 0.34f, a);
                // in front of his face? (camera side, face height) -> almost invisible
                float front = Vector3.Dot(offset / rad, toCam);
                float faceGuard = (y > 0.17f && front > 0.55f) ? 0.15f : 1f;
                Color col = i % 3 == 0 ? Orange : Gold;
                b.Sprite(g + offset + Vector3.up * y, 0.03f * Mathf.Sin(Mathf.PI * a) + 0.006f,
                         A(col, Mathf.Sin(Mathf.PI * a) * env * faceGuard), DGFxPaint.Sparkle, a * 2f, false);
            }
        }
    }

    // ------------------------------------------------------------------ S08: the sling spins
    public sealed class SlingTrail : FxDef
    {
        public override string Id => "sling_trail";
        public override float DefaultDur => 2.4f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.15f, 0.3f);
            const float span = 0.22f;                   // ~ half a turn of the 0.5 s windup loop
            const int pts = 14;
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);            // 0 = pouch now, 1 = oldest
                float ts = c.t - f * span;
                if (ts < 0 && k > 0) break;
                Color col = Color.Lerp(Orange, Sun, f);
                r.Add(c.track.Sample(ts), Mathf.Lerp(0.03f, 0.006f, f), A(col, env * (1 - f * 0.85f)));
            }
            // little sparkles dropped along the circle
            for (int j = 0; j < 40; j++)
            {
                float born = j * 0.06f;
                float age = c.t - born;
                if (born > c.t) break;
                if (age >= 0.45f) continue;
                float a = age / 0.45f;
                Vector3 p = c.track.Sample(born) + Vector3.down * (0.03f * a * a);
                b.Sprite(p, 0.022f * (1 - a), A(j % 2 == 0 ? Gold : Orange, env * (1 - a)), DGFxPaint.Sparkle, j, false);
            }
        }
    }

    // ------------------------------------------------------------------ S09: the stone flies
    public sealed class StoneTrail : FxDef
    {
        public override string Id => "stone_trail";
        public override float DefaultDur => 0.5f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.03f, 0.12f);
            const float span = 0.14f;
            const int pts = 12;
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);
                float ts = c.t - f * span;
                if (ts < 0 && k > 0) break;
                r.Add(c.track.Sample(ts), Mathf.Lerp(0.03f, 0.004f, f), A(Color.Lerp(Orange, Sun, f), env * (1 - f)));
            }
            // soft glow around the stone so a small grey pebble is visible against the page
            b.Sprite(c.anchor, 0.08f * (0.9f + 0.1f * Mathf.Sin(c.t * 40f)), A(Sun, 0.75f * env), DGFxPaint.SoftDot, 0, false);
            // two thin speed lines either side of the trail
            for (int s = -1; s <= 1; s += 2)
            {
                var l = b.Ribbon(DGFxPaint.Ribbon, false);
                for (int k = 0; k < 6; k++)
                {
                    float f = k / 5f;
                    float ts = c.t - 0.03f - f * 0.1f;
                    if (ts < 0 && k > 0) break;
                    l.Add(c.track.Sample(ts) + c.camUp * (0.024f * s), 0.006f, A(SoftInk, 0.55f * env * (1 - f)));
                }
            }
        }
    }

    // ------------------------------------------------------------------ S09: the stone hits the forehead
    public sealed class HitFlash : FxDef
    {
        public override string Id => "hit_flash";
        public override float DefaultDur => 0.4f;
        public override float ShakeAmp => 0.012f;
        public override float ShakeDur => 0.35f;
        public override float Flash => 0.35f;   // one soft flash, not a strobe

        public override void Emit(FxCtx c, FxBatch b)
        {
            float k = c.N;
            Vector3 p = c.anchor + (c.camPos - c.anchor).normalized * 0.05f;   // in front of the forehead
            float fade = 1 - Smooth(0.45f, 1f, k);
            b.Sprite(p, 0.34f * (0.6f + 0.4f * k), A(White, 0.8f * (1 - k)), DGFxPaint.SoftDot, 0, true);
            // radial crayon "pow" lines in the screen plane
            for (int i = 0; i < 8; i++)
            {
                float ang = Tau * i / 8f + 0.2f;
                Vector3 dir = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                float r0 = 0.05f + 0.10f * OutCubic(k), r1 = r0 + 0.07f * (1 - k) + 0.02f;
                var l = b.Ribbon(DGFxPaint.Ribbon, false);
                l.Add(p + dir * r0, 0.012f, A(Sun, fade));
                l.Add(p + dir * r1, 0.004f, A(Orange, fade));
            }
            // the big star pops with overshoot
            float s = 0.17f * OutBack(c.t / 0.12f);
            b.Sprite(p, s, A(Sun, fade), DGFxPaint.Star, 0.3f - 0.6f * k);
            // twinkles flying out
            for (int i = 0; i < 10; i++)
            {
                float ang = Tau * (i + FxRand.H(c.seed, i, 0)) / 10f;
                Vector3 dir = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                float d = 0.04f + Mathf.Lerp(0.12f, 0.2f, FxRand.H(c.seed, i, 1)) * OutCubic(k);
                b.Sprite(p + dir * d, 0.035f * (1 - k), A(i % 2 == 0 ? Sun : Orange, 1 - k), DGFxPaint.Sparkle, i, false);
            }
        }
    }

    // ------------------------------------------------------------------ S09: dizzy stars
    public sealed class DizzyStars : FxDef
    {
        public override string Id => "dizzy_stars";
        public override float DefaultDur => 1.0f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float pop = OutBack(c.t / 0.18f) * (1 - Smooth(0.75f, 1f, c.N));
            if (pop <= 0) return;
            Vector3 centre = c.anchor + Vector3.up * 0.07f;
            const int n = 4;
            for (int i = 0; i < n; i++)
            {
                float ang = Tau * i / n + c.t * Tau * 1.3f;
                Vector3 p = centre + Flat(ang, 0.085f) + Vector3.up * (0.012f * Mathf.Sin(ang * 2f));
                Color col = i % 2 == 0 ? Sun : DesignTokens.Pink;
                b.Sprite(p, 0.055f * pop, col, DGFxPaint.Star, c.t * 5f + i);
            }
            // tiny twinkles in between
            for (int i = 0; i < n; i++)
            {
                float ang = Tau * (i + 0.5f) / n + c.t * Tau * 1.3f;
                float tw = 0.5f + 0.5f * Mathf.Sin(c.t * 30f + i * 2f);
                b.Sprite(centre + Flat(ang, 0.085f), 0.025f * pop * tw, A(Sun, tw), DGFxPaint.Sparkle, 0, false);
            }
        }
    }

    // ------------------------------------------------------------------ S09: the giant lands on the page
    public sealed class DustBurst : FxDef
    {
        public override string Id => "dust_burst";
        public override float DefaultDur => 1.6f;
        public override bool Follow => false;
        public override float ShakeAmp => 0.03f;
        public override float ShakeDur => 0.9f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            // Goliath falls toward +Z (STORYBOARD conventions), so his body lies from about hips-0.3 to hips+0.35 in Z.
            Vector3 g = FxCtx.Ground(c.start, 0.005f);
            float k = c.N;
            b.Sprite(g, 0.08f + 0.5f * OutCubic(k), A(SoftInk, 0.6f * (1 - k)), DGFxPaint.Ring, 0.4f, false, FxFace.Ground);
            b.Sprite(g + new Vector3(0, 0, 0.3f), 0.06f + 0.4f * OutCubic(k * 1.2f), A(SoftInk, 0.5f * (1 - k)), DGFxPaint.Ring, 1.7f, false, FxFace.Ground);

            const int n = 38;
            for (int i = 0; i < n; i++)
            {
                float delay = 0.25f * FxRand.H(c.seed, i, 0) * FxRand.H(c.seed, i, 9);
                float life = c.dur * Mathf.Lerp(0.6f, 1f, FxRand.H(c.seed, i, 1));
                float a = (c.t - delay) / life;
                if (a <= 0 || a >= 1) continue;
                float along = Mathf.Lerp(-0.3f, 0.35f, FxRand.H(c.seed, i, 2));
                float side = FxRand.Signed(c.seed, i, 3);
                Vector3 basePos = g + new Vector3(side * 0.06f, 0, along);
                Vector3 outDir = new Vector3(side, 0, 0.35f * FxRand.Signed(c.seed, i, 4)).normalized;
                float e = OutCubic(a);
                Vector3 p = basePos + outDir * (Mathf.Lerp(0.08f, 0.2f, FxRand.H(c.seed, i, 5)) * e)
                          + Vector3.up * (0.01f + 0.08f * e * FxRand.H(c.seed, i, 6));
                float size = Mathf.Lerp(0.045f, 0.12f, e) * Mathf.Lerp(0.75f, 1.25f, FxRand.H(c.seed, i, 7));
                Color col = Color.Lerp(PaperDeep, SoftInk, 0.4f * FxRand.H(c.seed, i, 8));
                b.Sprite(p, size, A(col, 0.92f * Mathf.Pow(1 - a, 1.3f) * Sat(a * 10)), DGFxPaint.Dust, i + a * 1.5f);
            }
            // pebbles that hop once
            for (int i = 0; i < 10; i++)
            {
                float t = c.t;
                float ang = Tau * (i + FxRand.H(c.seed, i, 10)) / 10f;
                Vector3 p0 = g + new Vector3(0, 0, Mathf.Lerp(-0.2f, 0.3f, FxRand.H(c.seed, i, 11)));
                float vh = Mathf.Lerp(0.15f, 0.3f, FxRand.H(c.seed, i, 12)), vy = Mathf.Lerp(0.45f, 0.7f, FxRand.H(c.seed, i, 13));
                const float grav = 3.0f;
                float tLand = 2 * vy / grav;
                float y, hd;
                if (t < tLand) { y = vy * t - 0.5f * grav * t * t; hd = vh * t; }
                else
                {   // one smaller hop, then rest
                    float t2 = t - tLand, vy2 = vy * 0.35f, tLand2 = 2 * vy2 / grav;
                    y = t2 < tLand2 ? vy2 * t2 - 0.5f * grav * t2 * t2 : 0f;
                    hd = vh * tLand + vh * 0.5f * Mathf.Min(t2, tLand2);
                }
                Vector3 p = p0 + Flat(ang, hd) + Vector3.up * (y + 0.006f);
                b.Sprite(p, 0.016f, A(Stone, 1 - Smooth(0.7f, 1f, c.N)), DGFxPaint.Pebble, ang + t * 6f);
            }
        }
    }

    // ------------------------------------------------------------------ S11: victory confetti
    public sealed class Confetti : FxDef
    {
        public override string Id => "confetti";
        public override float DefaultDur => 3.0f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            Vector3 o = c.start + Vector3.up * 0.05f;
            float fade = 1 - Smooth(c.dur - 0.6f, c.dur, c.t);
            const int n = 64;
            for (int i = 0; i < n; i++)
            {
                float delay = 0.18f * FxRand.H(c.seed, i, 0);
                float t = c.t - delay;
                if (t <= 0) continue;
                float ang = Tau * FxRand.H(c.seed, i, 1);
                Vector3 v0 = Flat(ang, Mathf.Lerp(0.1f, 0.45f, FxRand.H(c.seed, i, 2))) + Vector3.up * Mathf.Lerp(0.7f, 1.15f, FxRand.H(c.seed, i, 3));
                Vector3 p = Ballistic(o, v0, 0.9f, 3.0f, t);   // terminal fall speed 0.3 art/s: flutters down
                float ph = FxRand.H(c.seed, i, 4) * Tau;
                p += new Vector3(Mathf.Sin(t * 5f + ph), 0, Mathf.Cos(t * 4f + ph)) * 0.012f * Sat(t * 2);
                bool landed = p.y <= 0.004f;
                if (landed) p.y = 0.004f;
                float flip = landed ? 1f : 0.25f + 0.75f * Mathf.Abs(Mathf.Cos(t * 7f + ph));
                Color col = Crayons[i % Crayons.Length];
                bool dot = i % 4 == 0;
                float w = dot ? 0.014f : 0.02f, h = dot ? 0.014f : 0.012f;
                b.Sprite(p, w, h * flip, A(col, fade * Sat(t * 12)), dot ? DGFxPaint.ConfettiDot : DGFxPaint.ConfettiRect,
                         landed ? ph : ph + t * 4f, false, landed ? FxFace.Ground : FxFace.Camera);
            }
        }
    }

    // ------------------------------------------------------------------ S11: golden rays while David prays
    public sealed class GoldenRays : FxDef
    {
        public override string Id => "golden_rays";
        public override float DefaultDur => 4.0f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.7f, 0.9f);
            Vector3 g = FxCtx.Ground(c.anchor, 0.005f);
            Vector3 toCam = c.ToCamFlat(g);
            Vector3 side = Vector3.Cross(Vector3.up, toCam).normalized;
            b.Sprite(g, 0.26f, A(Gold, 0.7f * env), DGFxPaint.GlowDisc, c.t * 0.15f, false, FxFace.Ground);

            const int n = 7;
            Vector3 sky = g + Vector3.up * 1.0f - toCam * 0.25f;   // light comes from above and slightly behind him
            for (int i = 0; i < n; i++)
            {
                float f = (i - (n - 1) * 0.5f) / ((n - 1) * 0.5f);   // -1..1
                Vector3 top = sky + side * (0.30f * f);
                Vector3 bottom = g + side * (0.07f * f) + toCam * (0.02f * Mathf.Abs(f));
                float pulse = 0.65f + 0.35f * Mathf.Sin(Tau * (0.45f * c.t + 0.37f * i));
                var r = b.Ribbon(DGFxPaint.Streak, false);
                Color col = i % 2 == 0 ? Gold : Sun;
                r.Add(top, 0.09f, A(col, 0.5f * env * pulse));
                r.Add(bottom, 0.035f, A(col, 0.5f * env * pulse));
            }
            // motes drifting down inside the rays
            for (int i = 0; i < 16; i++)
            {
                float period = Mathf.Lerp(1.8f, 2.6f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                float f = FxRand.Signed(c.seed, i, 2);
                Vector3 top = sky + side * (0.30f * f), bottom = g + side * (0.07f * f);
                Vector3 p = Vector3.Lerp(top, bottom, Mathf.Lerp(0.35f, 1f, a));
                b.Sprite(p, 0.024f, A(i % 2 == 0 ? Gold : Orange, Mathf.Sin(Mathf.PI * a) * env), DGFxPaint.Sparkle, a * 3f, false);
            }
        }
    }
}
