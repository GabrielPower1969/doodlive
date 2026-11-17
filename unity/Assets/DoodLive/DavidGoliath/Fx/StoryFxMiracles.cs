// Miracles (story pack, docs/miracles/FX.md) effects. Same engine as the earlier packs: every effect is a pure function
// of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered in FxLibrary
// after the earlier packs (an existing id is never replaced), through the manifest `fx.class` = MiraclesFx.
// New: dig_dirt, dust_fall, calm_wave. `wave_splash` is an alias of `splash` (manifest `fx.aliases`).
// Reused unchanged: dust_puff, golden_rays, heart_glow, sparkle, sunset_glow, zzz, storm_rain, tension_dim, night.
// calm_wave ends a running storm_rain and tension_dim at once: its first frame posts the ids to MiraclesFx.EndRequests and
// StoryFxMiraclesRuntime.cs (a hidden singleton, the same pattern as StoryFxStage) destroys those running instances.
// The stage tint / dim they posted expires by itself (StoryTint, StoryLight drop a request that is not renewed).
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no flash, no strobe; nothing bright or opaque over a face.
using System.Collections.Generic;
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Miracles registry and palette (docs/miracles/CONTRACT.md §8, DESIGN.md §4).</summary>
    public static class MiraclesFx
    {
        internal static FxDef[] Defs => new FxDef[] { new DigDirt(), new DustFall(), new CalmWave() };

        /// <summary>Effect ids that running instances must end now. Filled by calm_wave on its first frame, drained by
        /// StoryFxMiraclesRuntime. (Plain list: the stage is single-threaded.)</summary>
        public static readonly List<string> EndRequests = new List<string>(4);

        /// <summary>Ids calm_wave ends (CONTRACT §8: the storm is over, the night is clear).</summary>
        public static readonly string[] CalmEnds = { "storm_rain", "tension_dim" };

        // roof dirt: reads on the warm house interior (DESIGN §3 floor / wall tones are light sand and ochre)
        internal static readonly Color Crumb = new Color32(0x9A, 0x73, 0x4A, 255), CrumbDark = new Color32(0x6E, 0x4E, 0x30, 255),
                                       Shaft = new Color32(0xFF, 0xEE, 0xB8, 255), DustMote = new Color32(0xC4, 0xA2, 0x70, 255);
        // calm lake: pale blue rings that read on deep-blue night water, white-blue sheen
        internal static readonly Color Ripple = new Color32(0xBF, 0xDC, 0xF6, 255), Sheen = new Color32(0xE4, 0xF2, 0xFF, 255),
                                       SheenDeep = new Color32(0x7C, 0xB0, 0xE0, 255);

        /// <summary>Lift above the node for ground-lying sprites (the lake plane is the node's y).</summary>
        internal const float WaterLift = 0.006f;
    }

    // ------------------------------------------------------------------ S04: the friends dig through the roof
    /// <summary>
    /// Dirt tossed out of the hole while the friends dig: every 0.4 s (about 2.5 a second, jittered) a brown clod or a
    /// soft dust puff leaves the node up and sideways (either side, a little toward or away from the camera), flies a
    /// short arc under gravity and lands on the roof at the node's height, where a clod fades and a puff spreads and
    /// fades. A clod now and then brings a tiny second crumb. Nothing starts that would still be in the air at the end.
    /// Fades in over 0.3 s and out over 0.5 s.
    /// </summary>
    public sealed class DigDirt : FxDef
    {
        public override string Id => "dig_dirt";
        public override float DefaultDur => 5f;
        public override bool Follow => false;

        const float Every = 0.4f, G = 1.0f, Tail = 0.25f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.3f, 0.5f);
            if (env <= 0) return;
            Vector3 o = c.start;
            int last = Mathf.FloorToInt(c.t / Every);
            for (int k = Mathf.Max(0, last - 3); k <= last; k++)
            {
                float vy = Mathf.Lerp(0.22f, 0.34f, FxRand.H(c.seed, k, 1));
                float flight = 2f * vy / G;
                float t0 = k * Every + 0.5f * Every * FxRand.H(c.seed, k, 0);
                if (t0 + flight > c.dur + 0.05f) continue;                     // never cut off mid-air
                float age = c.t - t0;
                if (age < 0f || age > flight + Tail) continue;
                float vx = (FxRand.H(c.seed, k, 2) < 0.5f ? -1f : 1f) * Mathf.Lerp(0.06f, 0.14f, FxRand.H(c.seed, k, 3));
                float vz = 0.06f * FxRand.Signed(c.seed, k, 4);
                bool puff = FxRand.H(c.seed, k, 5) < 0.4f;
                float u = Mathf.Min(age, flight);
                Vector3 p = o + new Vector3(vx * u, vy * u - 0.5f * G * u * u + 0.004f, vz * u);
                float land = Sat((age - flight) / Tail);
                float spin = FxRand.H(c.seed, k, 6) * Tau + age * 5f * FxRand.Signed(c.seed, k, 7);
                if (puff)
                {
                    float size = 0.03f + 0.05f * OutCubic(Sat(age / (flight + Tail)));
                    b.Sprite(p, size, A(Color.Lerp(MiraclesFx.DustMote, MiraclesFx.Crumb, 0.3f), 0.8f * env * (1f - land) * Sat(age * 8f)),
                             DGFxPaint.Dust, spin);
                }
                else
                {
                    Color col = Color.Lerp(MiraclesFx.Crumb, MiraclesFx.CrumbDark, FxRand.H(c.seed, k, 8));
                    float size = Mathf.Lerp(0.016f, 0.026f, FxRand.H(c.seed, k, 9));
                    b.Sprite(p, size, A(col, 0.95f * env * (1f - land) * Sat(age * 10f)), DGFxPaint.Pebble, spin);
                    if (FxRand.H(c.seed, k, 10) < 0.5f)
                    {   // a tiny crumb that leaves a little later and a little wider
                        float a2 = Mathf.Max(0f, age - 0.04f), u2 = Mathf.Min(a2, flight);
                        Vector3 p2 = o + new Vector3(vx * 1.5f * u2, 0.8f * vy * u2 - 0.5f * G * u2 * u2 + 0.004f, -vz * u2);
                        b.Sprite(p2, 0.011f, A(MiraclesFx.CrumbDark, 0.9f * env * (1f - land) * Sat(a2 * 10f)), DGFxPaint.Pebble, -spin);
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ S05-S06: dirt falling through the hole
    /// <summary>
    /// A thin column of dirt falling from the node (the roof hole) to the floor (y = 0). A warm additive light shaft
    /// (narrow at the hole, a little wider at the floor, low opacity so it never hides the man's face) and about 28
    /// brown specks and crumbs that fall with a slight sway; each lands in a small soft puff on the floor. Fades in over
    /// 0.3 s and out over 0.7 s (specks fade with it).
    /// </summary>
    public sealed class DustFall : FxDef
    {
        public override string Id => "dust_fall";
        public override float DefaultDur => 3f;
        public override bool Follow => false;

        const int N = 28;
        const float FallMin = 0.55f, FallMax = 0.85f;   // seconds from the hole to the floor (accelerating)

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.3f, 0.7f);
            if (env <= 0) return;
            Vector3 top = c.start;
            Vector3 foot = new Vector3(top.x, 0.004f, top.z);

            // soft shaft of daylight: two ribbons, additive, drawn first (under the specks)
            float breathe = 0.92f + 0.08f * Mathf.Sin(c.t * 1.7f);
            var g = b.Ribbon(DGFxPaint.Ribbon, true);
            var g2 = b.Ribbon(DGFxPaint.Ribbon, true);
            for (int k = 0; k <= 4; k++)
            {
                float f = k / 4f;
                Vector3 p = Vector3.Lerp(top, foot, f);
                float a = Mathf.Lerp(0.20f, 0.12f, f) * env * breathe;
                g.Add(p, Mathf.Lerp(0.030f, 0.075f, f), A(MiraclesFx.Shaft, a));
                g2.Add(p, Mathf.Lerp(0.012f, 0.030f, f), A(Color.white, a * 0.8f));
            }
            // push the ribbon fade (last 40 %) past the floor so the shaft stays solid down to it
            Vector3 dn = (foot - top).normalized;
            g.Add(foot + dn * 0.01f, 0.075f, A(MiraclesFx.Shaft, 0.06f * env));
            g2.Add(foot + dn * 0.01f, 0.030f, A(Color.white, 0.05f * env));

            // falling specks and crumbs: each has its own period; one cycle = fall, land, fade
            for (int i = 0; i < N; i++)
            {
                float period = Mathf.Lerp(0.8f, 1.25f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                int cyc = (int)Mathf.Floor(ph); float u = ph - cyc;
                int k = i * 11 + cyc;
                float fall = Mathf.Lerp(FallMin, FallMax, FxRand.H(c.seed, k, 2)) / period;   // share of the cycle in the air
                float a = u / fall;
                float sway = 0.010f * Mathf.Sin(c.t * 5f + i * 1.9f) + 0.012f * FxRand.Signed(c.seed, k, 3);
                if (a < 1f)
                {
                    float y = Mathf.Lerp(top.y, 0.012f, a * a);       // accelerates (gravity)
                    var p = new Vector3(top.x + sway * (0.4f + a), y, top.z + 0.02f * FxRand.Signed(c.seed, k, 4));
                    bool crumb = FxRand.H(c.seed, k, 5) < 0.35f;
                    float size = crumb ? Mathf.Lerp(0.011f, 0.019f, FxRand.H(c.seed, k, 6)) : Mathf.Lerp(0.014f, 0.026f, FxRand.H(c.seed, k, 6));
                    Color col = Color.Lerp(MiraclesFx.Crumb, MiraclesFx.CrumbDark, FxRand.H(c.seed, k, 7));
                    if (!crumb) col = Color.Lerp(col, MiraclesFx.DustMote, 0.35f);
                    b.Sprite(p, size, A(col, 0.95f * env * Sat(a * 10f)), crumb ? DGFxPaint.Pebble : DGFxPaint.Dust,
                             FxRand.H(c.seed, k, 8) * Tau + c.t * 3f * FxRand.Signed(c.seed, k, 9));
                }
                else
                {   // landed: a small soft puff that spreads and fades over the rest of the cycle
                    float l = Sat((u - fall) / Mathf.Max(0.05f, 1f - fall));
                    var p = foot + new Vector3(0.025f * FxRand.Signed(c.seed, k, 10), 0.006f, 0.025f * FxRand.Signed(c.seed, k, 11));
                    b.Sprite(p, 0.022f + 0.05f * OutCubic(l), A(MiraclesFx.DustMote, 0.45f * env * (1f - l)),
                             DGFxPaint.Dust, FxRand.H(c.seed, k, 12) * Tau, false, FxFace.Ground);
                }
            }
        }
    }

    // ------------------------------------------------------------------ S12: "Peace, be still"
    /// <summary>
    /// The lake goes still. Five rings spread out from the node over the water (lying flat on the lake plane), each
    /// fainter and thinner than the last, then a glassy sheen: a pale-blue glow disc and a few long, slow, flat glints
    /// that fade in as the last ring dies and stay to the end. Fades out over the last 0.6 s. On its first frame it asks
    /// the runtime to end storm_rain and tension_dim (MiraclesFx.CalmEnds), so the night is clear. Draws nothing over
    /// the actors: everything is flat on the water, nothing is opaque.
    /// </summary>
    public sealed class CalmWave : FxDef
    {
        public override string Id => "calm_wave";
        public override float DefaultDur => 3f;
        public override bool Follow => false;

        const int Rings = 5;
        const float Step = 0.28f, Life = 1.25f, MaxR = 0.60f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            if (c.t <= 0f)
                foreach (string id in MiraclesFx.CalmEnds)
                    if (!MiraclesFx.EndRequests.Contains(id)) MiraclesFx.EndRequests.Add(id);

            float env = Env(c.t, c.dur, 0.15f, 0.6f);
            if (env <= 0) return;
            Vector3 w = new Vector3(c.start.x, c.start.y + MiraclesFx.WaterLift, c.start.z);

            // rings: calmer each time (alpha and reach shrink), crayon-pale on the dark water
            for (int i = 0; i < Rings; i++)
            {
                float u = (c.t - i * Step) / Life;
                if (u <= 0f || u >= 1f) continue;
                float calm = 1f - 0.6f * i / (Rings - 1);                   // 1 .. 0.4
                float r = (0.04f + MaxR * calm * OutCubic(u));
                float a = 0.55f * calm * env * Sat(u * 10f) * (1f - u) * (1f - u);
                b.Sprite(w, r * 2f, A(MiraclesFx.Ripple, a), DGFxPaint.Ring, 0.3f * i, false, FxFace.Ground);
                if (i < 3) b.Sprite(w, r * 1.55f, A(MiraclesFx.Sheen, a * 0.45f), DGFxPaint.Ring, 1.1f + i, true, FxFace.Ground);
            }

            // glassy sheen: starts when the third ring is half gone and stays (0 -> 1 over 0.9 s)
            float s0 = 1.0f;
            float sh = Smooth(s0, s0 + 0.9f, c.t) * env;
            if (sh <= 0f) return;
            b.Sprite(w, MaxR * 2.2f, A(MiraclesFx.SheenDeep, 0.20f * sh), DGFxPaint.GlowDisc, 0f, true, FxFace.Ground);
            for (int i = 0; i < 9; i++)
            {
                float ang = Tau * (i + 0.5f * FxRand.H(c.seed, i, 20)) / 9f;
                float rad = Mathf.Lerp(0.10f, 0.50f, FxRand.H(c.seed, i, 21));
                var p = w + Flat(ang, rad) + new Vector3(0.012f * Mathf.Sin(c.t * 0.9f + i), 0.001f, 0f);
                float tw = 0.5f + 0.5f * Mathf.Sin(c.t * 1.3f + i * 2.3f);   // slow glint, never a flash
                float len = Mathf.Lerp(0.07f, 0.14f, FxRand.H(c.seed, i, 22));
                b.Sprite(p, len, len * 0.14f, A(MiraclesFx.Sheen, 0.50f * sh * (0.35f + 0.65f * tw)), DGFxPaint.Streak, 0f, true, FxFace.Ground);
            }
        }
    }
}
