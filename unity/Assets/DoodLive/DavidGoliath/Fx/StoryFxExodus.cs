// Exodus (story pack, docs/exodus/FX.md) effects. Same engine as David & Goliath, Esther, Ruth and Daniel: every effect
// is a pure function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and
// registered in FxLibrary after the earlier packs (an existing id is never replaced).
// New ids: bush_fire snake river_red frogs frog_on_head flies hail door_glow pillar_cloud pillar_fire sea_wind
// sea_part sea_close splash drips, plus the internal `sea_hold` (the standing walls' foam, shimmer and caustics, spawned
// by ExodusStage while the sea is open). Reused unchanged: dust_road sunset_glow night prayer_glow sparkle confetti
// golden_rays.
// The sea state (how far the walls stand, 0 = rest .. 1 = parted) lives in ExodusSea and survives the effects that set
// it, so the walls keep standing between sea_part (S11) and sea_close (S12). ExodusStage (StoryFxExodusRuntime.cs) turns
// it into the set nodes' scale / visibility every frame and resets it on DGFx.StopAll (StoryLight.Epoch).
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no flash, no strobe, nothing bright over a face; frogs, flies and the snake are
// cartoon-cute, the burning bush never looks dangerous, the sea is wonder, not threat.
using System.Collections.Generic;
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>One actor as the Exodus effects see it (stage-local feet position, figure height).</summary>
    public struct ExodusActor
    {
        public Vector3 feet;
        public float height;
    }

    /// <summary>Exodus registry, palette, set layout fallbacks and shared drawing helpers (docs/exodus/CONTRACT.md §6, §8).</summary>
    public static class ExodusFx
    {
        internal static FxDef[] Defs => new FxDef[]
        {
            new ExBushFire(), new ExSnake(), new ExRiverRed(), new ExFrogs(), new ExFrogOnHead(), new ExFlies(), new ExHail(),
            new ExDoorGlow(), new ExPillar(false), new ExPillar(true), new ExSeaWind(), new ExSeaPart(), new ExSeaClose(),
            new ExSeaHold(), new ExSplash(), new ExDrips(),
        };

        /// <summary>Actors (frogs keep off their feet; the bush lights them). Filled by ExodusStage while an effect asks.</summary>
        public static readonly List<ExodusActor> Actors = new List<ExodusActor>(4);
        /// <summary>Set by effects that read <see cref="Actors"/>; ExodusStage fills the list while it is set.</summary>
        public static bool ActorsWanted;

        /// <summary>Stage-local bounds of set nodes measured by ExodusStage (nileWater, doorMarks, seaWaterLane, seaBed,
        /// seaWallBack / seaWallFront at full height). Missing entries fall back to the CONTRACT §6 numbers.</summary>
        public static readonly Dictionary<string, Bounds> Boxes = new Dictionary<string, Bounds>();
        public static bool TryBox(string node, out Bounds b) => Boxes.TryGetValue(node, out b);

        /// <summary>Head bone origin to the top of the head (Pharaoh with the nemes), for frog_on_head.</summary>
        public static float HeadTop = 0.062f;

        // CONTRACT §6 fallbacks (used when a node is missing and the director anchors the effect at the stage origin)
        internal static readonly Vector3 BushFlame = new Vector3(0.14f, 0.12f, -0.36f);
        internal static readonly Vector3 PillarWest = new Vector3(0.16f, 0f, -0.12f);
        internal static readonly Vector3 Palace = new Vector3(-0.36f, 0f, -0.48f);
        internal static readonly Bounds NileFallback = new Bounds(new Vector3(-0.55f, 0.006f, -0.045f), new Vector3(0.08f, 0.012f, 0.50f));
        internal static readonly Bounds DoorFallback = new Bounds(new Vector3(-0.02f, 0.045f, -0.408f), new Vector3(0.17f, 0.09f, 0.006f));

        /// <summary>The anchor, or the fallback when the anchor sits at the stage origin (node missing / origin at the set root).</summary>
        internal static Vector3 NodeOr(Vector3 p, Vector3 fallback) =>
            p.x * p.x + p.z * p.z < 0.03f * 0.03f && Mathf.Abs(p.y) < 0.03f ? fallback : p;

        // docs/exodus/DESIGN.md demo colours + light colours (sRGB)
        internal static readonly Color FlameWhite = new Color32(0xFF, 0xF8, 0xE2, 255);
        internal static readonly Color FlameGold = new Color32(0xFF, 0xD8, 0x66, 255);
        internal static readonly Color FlameAmber = new Color32(0xFF, 0xB3, 0x47, 255);
        internal static readonly Color Violet = new Color32(0xB9, 0x9F, 0xE8, 255);
        internal static readonly Color VioletPale = new Color32(0xE2, 0xD6, 0xFF, 255);
        internal static readonly Color NileRed = new Color32(0xA3, 0x2A, 0x2E, 255);
        internal static readonly Color NileRedDeep = new Color32(0x7A, 0x1E, 0x24, 255);
        internal static readonly Color FrogGreen = new Color32(0x7B, 0xC0, 0x43, 255);
        internal static readonly Color FrogDark = new Color32(0x4E, 0x8A, 0x2E, 255);
        internal static readonly Color FrogBelly = new Color32(0xE2, 0xF2, 0xA6, 255);
        internal static readonly Color SnakeGreen = new Color32(0x7A, 0x9A, 0x3A, 255);
        internal static readonly Color SnakeBrown = new Color32(0x8C, 0x74, 0x3E, 255);
        internal static readonly Color SnakeSpot = new Color32(0x4F, 0x66, 0x2A, 255);
        internal static readonly Color StaffWood = new Color32(0x8A, 0x5E, 0x3A, 255);
        internal static readonly Color TonguePink = new Color32(0xF0, 0x7A, 0x8C, 255);
        internal static readonly Color Hail = new Color32(0xF4, 0xFA, 0xFF, 255);
        internal static readonly Color Ice = new Color32(0xCF, 0xE6, 0xF7, 255);
        internal static readonly Color DoorWarm = new Color32(0xFF, 0xC8, 0x6A, 255);
        internal static readonly Color DoorRed = new Color32(0xFF, 0x8A, 0x5C, 255);
        internal static readonly Color Cloud = new Color32(0xF2, 0xF4, 0xFA, 255);
        internal static readonly Color CloudGrey = new Color32(0xB4, 0xBE, 0xD0, 255);
        internal static readonly Color Fire = new Color32(0xFF, 0x96, 0x3A, 255);
        internal static readonly Color FireCore = new Color32(0xFF, 0xE0, 0x8A, 255);
        internal static readonly Color Ember = new Color32(0xFF, 0x7A, 0x2E, 255);
        internal static readonly Color Sea = new Color32(0x2C, 0x7F, 0xA8, 255);
        internal static readonly Color SeaWall = new Color32(0x4F, 0xB3, 0xC9, 255);
        internal static readonly Color Foam = new Color32(0xF6, 0xFC, 0xFF, 255);
        internal static readonly Color Spray = new Color32(0xD2, 0xF1, 0xFA, 255);
        internal static readonly Color Caustic = new Color32(0xBF, 0xF4, 0xFF, 255);
        internal static readonly Color Drop = new Color32(0x9F, 0xD8, 0xEA, 255);
        internal static readonly Color WindWhite = new Color32(0xEE, 0xF6, 0xFF, 255);
        internal static readonly Color Sand = new Color32(0xE2, 0xC8, 0x94, 255);

        /// <summary>Cool multiply tints (sRGB) for hail and the S11 wind.</summary>
        public static Color HailTint = new Color(0.86f, 0.92f, 1.00f, 1f);
        public static Color WindTint = new Color(0.80f, 0.87f, 1.00f, 1f);

        internal static Vector3 Up => Vector3.up;

        /// <summary>A cartoon crayon frog (camera-facing): ink-outlined green body, pale belly, two goggle eyes on top.
        /// squash &gt; 1 = stretched tall (in the air), &lt; 1 = squashed (landing); throat 0..1 = croak bubble.</summary>
        internal static void Frog(FxBatch b, FxCtx c, Vector3 feet, float size, float squash, float throat, float blink, float alpha, bool shadow)
        {
            if (alpha <= 0.003f) return;
            Vector3 toCam = (c.camPos - feet).normalized;
            float w = size / Mathf.Sqrt(Mathf.Max(0.5f, squash)), h = 0.72f * size * squash;
            if (shadow)
                b.Sprite(FxCtx.Ground(feet, 0.003f), size * 1.1f, size * 0.7f, A(SoftInk(), 0.22f * alpha), DGFxPaint.SoftDot,
                         0, false, FxFace.Ground);
            Vector3 body = new Vector3(feet.x, Mathf.Max(feet.y, 0f) + h * 0.5f, feet.z);
            if (throat > 0.01f)
                b.Sprite(body - Up * (h * 0.22f) + toCam * 0.004f, size * (0.30f + 0.32f * throat), A(FrogBelly, 0.95f * alpha),
                         DGFxPaint.ConfettiDot, 0, false);
            b.Sprite(body, w, h, A(FrogGreen, alpha), DGFxPaint.Pebble, 0, false, FxFace.Camera);
            b.Sprite(body - Up * (h * 0.12f) + toCam * 0.003f, w * 0.52f, h * 0.42f, A(FrogBelly, 0.85f * alpha), DGFxPaint.SoftDot,
                     0, false, FxFace.Camera);
            if (throat > 0.01f)   // the croak sac in front of the body
                b.Sprite(body - Up * (h * 0.26f) + toCam * 0.007f, size * 0.42f * throat, size * 0.34f * throat,
                         A(FrogBelly, alpha), DGFxPaint.ConfettiDot, 0, false, FxFace.Camera);
            float eye = size * 0.36f;
            float lid = Mathf.Max(0.18f, 1f - blink);
            for (int s = -1; s <= 1; s += 2)
            {
                Vector3 e = body + Up * (h * 0.42f) + c.camRight * (s * w * 0.27f) + toCam * 0.004f;
                b.Sprite(e, eye, eye * lid, A(Color.white, alpha), DGFxPaint.Puff, 0, false, FxFace.Camera);
                if (lid > 0.5f)
                    b.Sprite(e + toCam * 0.002f + Up * (eye * 0.05f), eye * 0.38f, A(InkCol(), alpha), DGFxPaint.ConfettiDot, 0, false);
            }
        }

        /// <summary>A water drop: ink-outlined pale-blue crayon bead with a white glint.</summary>
        internal static void WaterDrop(FxBatch b, FxCtx c, Vector3 p, float size, float stretch, float alpha)
        {
            if (alpha <= 0.003f) return;
            b.Sprite(p, size, size * stretch, A(Drop, alpha), DGFxPaint.Pebble, 0, false, FxFace.Camera);
            b.Sprite(p + c.camUp * (size * 0.18f) - c.camRight * (size * 0.15f) + (c.camPos - p).normalized * 0.001f,
                     size * 0.35f, A(Color.white, alpha), DGFxPaint.SoftDot, 0, false);
        }

        /// <summary>A white crayon foam blob (Dust cell) that slowly turns.</summary>
        internal static void FoamPuff(FxBatch b, Vector3 p, float size, float alpha, float rot, bool soft = false)
        {
            if (soft) b.Sprite(p, size * 1.35f, A(Foam, alpha * 0.9f), DGFxPaint.SoftDot, 0, false);
            else b.Sprite(p, size, A(Foam, alpha), DGFxPaint.Dust, rot, false);
        }

        /// <summary>One flame tongue: a camera-facing ribbon, wide near the base, tapering and swaying at the tip.</summary>
        internal static void Tongue(FxBatch b, FxCtx c, Vector3 bs, float t, float height, float width, Color baseCol, Color tipCol,
                                    float phase, float alpha, bool add = false)
        {
            const int pts = 7;
            float h = height * (0.86f + 0.10f * Mathf.Sin(t * 5.3f + phase) + 0.06f * Mathf.Sin(t * 9.1f + phase * 2.1f));
            var r = b.Ribbon(DGFxPaint.Ribbon, add);
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);
                float sway = (0.6f * Mathf.Sin(t * 4.6f + phase - f * 3.2f) + 0.4f * Mathf.Sin(t * 8.3f + phase * 1.7f - f * 5f))
                             * 0.010f * f * f;
                Vector3 p = bs + c.camRight * sway + Vector3.up * (h * f);
                float wd = width * Mathf.Sin(Mathf.PI * Mathf.Lerp(0.35f, 1f, f));
                r.Add(p, Mathf.Max(wd, 0.001f), A(Color.Lerp(baseCol, tipCol, f), alpha));
            }
        }

        internal static float ScreenAngle(FxCtx c, Vector3 dir) => Mathf.Atan2(Vector3.Dot(dir, c.camUp), Vector3.Dot(dir, c.camRight));
        internal static Color SoftInk() => DesignTokens.InkSoft;
        internal static Color InkCol() => DesignTokens.Ink;

        // small reusable sort scratch (effects run on the main thread, one Emit at a time)
        internal static readonly float[] SortKey = new float[64];
        internal static readonly int[] SortIdx = new int[64];
        internal static void SortBackToFront(int n)
        {
            for (int i = 0; i < n; i++) SortIdx[i] = i;
            for (int i = 1; i < n; i++)
            {
                int v = SortIdx[i]; float k = SortKey[v]; int j = i - 1;
                while (j >= 0 && SortKey[SortIdx[j]] < k) { SortIdx[j + 1] = SortIdx[j]; j--; }
                SortIdx[j + 1] = v;
            }
        }
    }

    /// <summary>
    /// The sea (CONTRACT §6 `sea`): how far the walls stand, shared by sea_part / sea_close / sea_hold and the runtime that
    /// moves the set nodes. Open: 0 = rest (walls flat and hidden, lane water shown), 1 = parted (walls full height, lane
    /// hidden). It persists after the effect that set it ends and resets to 0 when DGFx.StopAll bumps StoryLight.Epoch.
    /// Fast-forward: the director calls ExodusStage.Seek(seekFx, t) (or SetState) after DGFx.StopAll (docs/exodus/FX.md).
    /// </summary>
    public static class ExodusSea
    {
        public static float Open { get; private set; }
        /// <summary>Seconds of un-paused play, advanced by ExodusStage; drives the gentle motion of the standing walls.</summary>
        public static float Clock;
        static int epoch;

        // CONTRACT §6 geometry (stage-local); ExodusStage overwrites it from the real wall meshes when they are found
        public static float X0 = 0.20f, X1 = 0.40f, ZBack = 0.02f, ZFront = 0.13f, BaseY = 0f, TopBackY = 0.24f, TopFrontY = 0.14f;
        public static float RestScale = 0.02f;   // the walls' rest scale.y relative to full height
        public static float LaneHideAt = 0.12f;  // Open above which seaWaterLane is hidden

        /// <summary>Snap the sea to rest (false) or parted (true). Call after DGFx.StopAll when seeking.</summary>
        public static void SetState(bool parted) { Sync(); Open = parted ? 1f : 0f; }

        /// <summary>Drop the state when DGFx.StopAll has run since the last call (new play, replay, seek, leaving the sheet).</summary>
        public static void Sync()
        {
            if (epoch == StoryLight.Epoch) return;
            epoch = StoryLight.Epoch; Open = 0f;
        }

        internal static void Drive(float open) { Sync(); Open = open; }

        public static bool LaneHidden(float open) => open > LaneHideAt;
        /// <summary>0 while rising / falling, 1 when the walls fully stand (gates the idle motion).</summary>
        public static float Standing(float open) => Smooth(0.85f, 1f, open);
        /// <summary>Wall height fraction 0..~1.04 now, including the slow surface swell of the standing walls.</summary>
        public static float Rise(float open, float clock) => open * (1f + 0.012f * Standing(open) * Mathf.Sin(clock * 1.6f));
        /// <summary>scale.y of a wall relative to its full-height scale (RestScale at rest).</summary>
        public static float ScaleY(float open, float clock) => Mathf.Lerp(RestScale, 1f, Rise(open, clock));
        internal static float Top(bool back, float open, float clock) =>
            BaseY + ((back ? TopBackY : TopFrontY) - BaseY) * ScaleY(open, clock);
        internal static float LaneZ => (ZBack + ZFront) * 0.5f;
        /// <summary>Inner face of a wall (the side facing the lane) and the direction toward the lane.</summary>
        internal static float Face(bool back) => back ? ZBack : ZFront;
        internal static float ToLane(bool back) => back ? 1f : -1f;
    }

    // ------------------------------------------------------------------ S03: the bush that burns and is not burnt (loop)
    public sealed class ExBushFire : FxDef
    {
        public override string Id => "bush_fire";
        public override float DefaultDur => 30f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.2f, 1.5f);
            if (env <= 0) return;
            ExodusFx.ActorsWanted = true;
            Vector3 o = ExodusFx.NodeOr(c.anchor, ExodusFx.BushFlame);
            float t = c.t + 10f * FxRand.H(c.seed, 0, 9);
            float br = 0.93f + 0.05f * Mathf.Sin(t * 1.7f) + 0.02f * Mathf.Sin(t * 4.3f + 1f);   // slow breathing, no flicker
            Vector3 toCam = (c.camPos - o).normalized;
            Vector3 flatCam = c.ToCamFlat(o);

            // halo: soft violet behind, warm gold around, a warm pool on the page and a wide faint glow that reaches the actors
            b.Sprite(FxCtx.Ground(o, 0.004f), 0.42f * br, A(ExodusFx.FlameGold, 0.26f * env), DGFxPaint.SoftDot, 0, false, FxFace.Ground);
            b.Sprite(FxCtx.Ground(o, 0.005f), 0.70f, A(ExodusFx.FlameGold, 0.10f * env * br), DGFxPaint.SoftDot, 0, true, FxFace.Ground);
            b.Sprite(o - toCam * 0.07f + Vector3.up * 0.02f, 0.40f * br, A(ExodusFx.Violet, 0.55f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(o - toCam * 0.04f + Vector3.up * 0.02f, 0.22f * br, A(ExodusFx.VioletPale, 0.30f * env), DGFxPaint.SoftDot, 0, false);

            // light on the actors nearby: a warm glow on their side that faces the bush (chest height, never on the face)
            foreach (var a in ExodusFx.Actors)
            {
                Vector3 d = o - a.feet; d.y = 0;
                float dist = d.magnitude;
                if (dist > 0.45f || dist < 1e-4f) continue;
                float k = (1 - dist / 0.45f); k *= k;
                float h = a.height > 0.05f ? a.height : 0.35f;
                Vector3 p = a.feet + Vector3.up * (h * 0.42f) + d / dist * 0.035f;
                b.Sprite(p, h * 0.55f, h * 0.75f, A(ExodusFx.FlameGold, 0.30f * k * env * br), DGFxPaint.SoftDot, 0, true, FxFace.Camera);
            }

            // flame tongues licking the crown, back ones first; outer amber-gold, inner white-gold
            const int n = 9;
            for (int j = 0; j < n; j++)
            {
                float ang = Tau * j / n + 0.5f * FxRand.H(c.seed, j, 1);
                Vector3 off = Flat(ang, 0.038f * Mathf.Lerp(0.55f, 1f, FxRand.H(c.seed, j, 2)));
                ExodusFx.SortKey[j] = -Vector3.Dot(off, flatCam);
            }
            ExodusFx.SortBackToFront(n);
            for (int q = 0; q < n; q++)
            {
                int j = ExodusFx.SortIdx[q];
                float ang = Tau * j / n + 0.5f * FxRand.H(c.seed, j, 1);
                Vector3 off = Flat(ang, 0.038f * Mathf.Lerp(0.55f, 1f, FxRand.H(c.seed, j, 2)));
                Vector3 bs = o + off + Vector3.up * (-0.045f + 0.015f * FxRand.H(c.seed, j, 3));
                float hgt = Mathf.Lerp(0.07f, 0.12f, FxRand.H(c.seed, j, 4));
                ExodusFx.Tongue(b, c, bs, t, hgt, Mathf.Lerp(0.022f, 0.030f, FxRand.H(c.seed, j, 5)),
                                ExodusFx.FlameAmber, ExodusFx.FlameGold, 1.3f * j, 0.80f * env);
            }
            ExodusFx.Tongue(b, c, o - Vector3.up * 0.03f + toCam * 0.01f, t, 0.095f, 0.036f, ExodusFx.FlameGold, ExodusFx.FlameWhite, 0.4f, 0.92f * env);
            ExodusFx.Tongue(b, c, o - Vector3.up * 0.02f + toCam * 0.015f, t, 0.055f, 0.020f, ExodusFx.FlameWhite, Color.white, 2.9f, env);
            b.Sprite(o + Vector3.up * 0.01f + toCam * 0.02f, 0.09f * br, A(ExodusFx.FlameGold, 0.45f * env), DGFxPaint.SoftDot, 0, true);

            // slow rising sparks: white-gold and pale violet, drifting and winking out
            for (int i = 0; i < 9; i++)
            {
                float period = Mathf.Lerp(2.4f, 3.6f, FxRand.H(c.seed, i, 10));
                float ph = c.t / period + FxRand.H(c.seed, i, 11);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                Vector3 s0 = o + Flat(Tau * FxRand.H(c.seed, i * 13 + cyc, 12), 0.035f * FxRand.H(c.seed, i * 13 + cyc, 13));
                float rise = Mathf.Lerp(0.14f, 0.24f, FxRand.H(c.seed, i * 13 + cyc, 14));
                Vector3 p = s0 + Vector3.up * (0.02f + rise * a) + c.camRight * (0.012f * Mathf.Sin(a * 6f + i));
                float al = Sat(a * 5f) * (1 - a) * env;
                Color col = i % 3 == 0 ? ExodusFx.VioletPale : (i % 3 == 1 ? ExodusFx.FlameWhite : ExodusFx.FlameGold);
                b.Sprite(p, 0.014f * (1 - 0.6f * a) + 0.004f, A(col, al), DGFxPaint.Sparkle, a * 2f + i, false);
            }
        }
    }

    // ------------------------------------------------------------------ S04: the staff becomes a snake, then a staff again
    public sealed class ExSnake : FxDef
    {
        public override string Id => "snake";
        public override float DefaultDur => 5.6f;

        const float Fall = 0.38f, Morph = 0.80f, RiseT = 0.9f, Len = 0.16f, StaffLen = 0.32f;
        const int Pts = 16;
        static readonly Vector3[] P = new Vector3[Pts];
        static readonly float[] W = new float[Pts];

        public override void Emit(FxCtx c, FxBatch b)
        {
            float t = c.t;
            float fadeOut = Sat((c.dur - t) / 0.15f);
            if (fadeOut <= 0) return;
            Vector3 feet = FxCtx.Ground(c.start, 0f);
            Vector3 fwd = c.ToCamFlat(feet);                                     // in front of Moses = toward the viewer
            Vector3 side = Vector3.Cross(Vector3.up, fwd).normalized;
            Vector3 lieDir = (fwd * 0.55f + side * 0.83f).normalized;            // diagonal, so the wriggle reads
            Vector3 foot = feet + fwd * 0.05f;                                   // staff foot on the page

            if (t < Fall)
            {   // the staff topples forward and lands with a puff
                float k = InCubic(t / Fall) * 0.92f + 0.08f * (t / Fall);
                float th = k * Mathf.PI * 0.5f;
                Vector3 dir = Vector3.up * Mathf.Cos(th) + lieDir * Mathf.Sin(th);
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                for (int i = 0; i < 6; i++)
                {
                    float f = i / 5f;
                    r.Add(foot + Vector3.up * 0.006f + dir * (StaffLen * f), 0.010f, A(ExodusFx.StaffWood, 1f));
                }
                return;
            }

            float tw = t - Fall;
            // wriggle pose (head = index 0)
            float wig = Sat((t - Fall) / (Morph - Fall));
            float heading = 0.55f * Mathf.Sin(0.45f * tw) + 0.25f * Mathf.Sin(0.17f * tw + 1f);
            float hc = Mathf.Cos(heading * wig), hs = Mathf.Sin(heading * wig);   // rotate lieDir about +Y (no engine call)
            Vector3 hd = new Vector3(lieDir.x * hc + lieDir.z * hs, 0f, -lieDir.x * hs + lieDir.z * hc);
            Vector3 hp = Vector3.Cross(Vector3.up, hd).normalized;
            Vector3 centre = foot + lieDir * (StaffLen * 0.5f) * (1 - wig) + lieDir * (Len * 0.55f) * wig
                           + hd * (0.018f * Mathf.Sin(0.6f * tw) * wig);
            float rise = t > c.dur - RiseT ? Smooth(0f, 1f, (t - (c.dur - RiseT)) / (RiseT - 0.2f)) : 0f;
            Vector3 top = c.anchor + Vector3.up * 0.17f, bottom = new Vector3(c.anchor.x, 0.006f, c.anchor.z);
            for (int i = 0; i < Pts; i++)
            {
                float s = i / (float)(Pts - 1);
                // staff pose (morph start): straight along lieDir from the foot, head at the far (crook) end
                Vector3 staff = foot + Vector3.up * 0.006f + lieDir * (StaffLen * (1 - s));
                float amp = 0.017f * (0.35f + 0.65f * s);
                float wave = Mathf.Sin(Tau * 1.15f * s - 5.2f * tw);
                Vector3 snake = centre + hd * (Len * (0.5f - s)) + hp * (amp * wave);
                snake.y = 0.007f + 0.030f * Smooth(0.30f, 0f, s) + 0.002f * Mathf.Sin(Tau * s * 2f - 4f * tw);
                Vector3 p = Vector3.Lerp(staff, snake, Smooth(0f, 1f, wig));
                if (rise > 0)
                {
                    float rk = Sat(rise * 1.25f - 0.25f * s);                    // the tail (held) straightens first
                    p = Vector3.Lerp(p, Vector3.Lerp(top, bottom, s), Smooth(0f, 1f, rk));
                }
                P[i] = p;
                float wSnake = s < 0.07f ? 0.019f : Mathf.Lerp(0.018f, 0.004f, Mathf.Pow((s - 0.07f) / 0.93f, 1.2f));
                W[i] = Mathf.Lerp(Mathf.Lerp(0.010f, wSnake, wig), 0.009f, rise);
            }
            float green = wig * (1 - rise);
            Color bodyCol = Color.Lerp(ExodusFx.StaffWood, ExodusFx.SnakeGreen, green);
            var body = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int i = 0; i < Pts; i++)
                body.Add(P[i], W[i], A(Color.Lerp(bodyCol, Color.Lerp(ExodusFx.StaffWood, ExodusFx.SnakeBrown, green), i / (float)Pts * 0.7f), fadeOut));
            // back pattern: little darker diamonds along the spine (only as a snake)
            if (green > 0.05f)
                for (int i = 3; i < Pts - 2; i += 2)
                {
                    Vector3 q = P[i] + (c.camPos - P[i]).normalized * 0.004f + Vector3.up * 0.002f;
                    b.Sprite(q, W[i] * 0.55f, A(ExodusFx.SnakeSpot, 0.85f * green * fadeOut), DGFxPaint.Pebble, i, false);
                }
            // head: a round friendly head with two goggle eyes and a flicking tongue
            if (green > 0.05f)
            {
                Vector3 dirHead = (P[0] - P[2]).normalized;
                Vector3 h0 = P[0] + dirHead * 0.006f;
                Vector3 toCam = (c.camPos - h0).normalized;
                float ang = ExodusFx.ScreenAngle(c, dirHead);
                float al = green * fadeOut;
                b.Sprite(h0 + toCam * 0.002f, 0.030f, 0.021f, A(ExodusFx.SnakeGreen, al), DGFxPaint.Pebble, ang, false, FxFace.Camera);
                for (int s = -1; s <= 1; s += 2)
                {
                    Vector3 e = h0 + Vector3.up * 0.008f + c.camRight * (0.006f * s) - dirHead * 0.003f + toCam * 0.004f;
                    b.Sprite(e, 0.010f, A(Color.white, al), DGFxPaint.Puff, 0, false);
                    b.Sprite(e + toCam * 0.001f + dirHead * 0.0015f, 0.0042f, A(ExodusFx.InkCol(), al), DGFxPaint.ConfettiDot, 0, false);
                }
                float fl = (tw % 1.4f) / 1.4f;
                if (fl > 0.15f && fl < 0.32f)
                {
                    float e = Mathf.Sin(Mathf.PI * (fl - 0.15f) / 0.17f);
                    Vector3 tip = h0 + dirHead * (0.014f + 0.012f * e);
                    var tg = b.Ribbon(DGFxPaint.Ribbon, false);
                    tg.Add(h0 + dirHead * 0.012f, 0.0025f, A(ExodusFx.TonguePink, al)); tg.Add(tip, 0.0022f, A(ExodusFx.TonguePink, al));
                    for (int s = -1; s <= 1; s += 2)
                    {
                        var fk = b.Ribbon(DGFxPaint.Ribbon, false);
                        fk.Add(tip, 0.002f, A(ExodusFx.TonguePink, al));
                        fk.Add(tip + dirHead * 0.005f + c.camRight * (0.003f * s), 0.0015f, A(ExodusFx.TonguePink, al));
                    }
                }
            }
            // a little dust puff where the staff lands, and the sparkle as it becomes a staff again
            float land = (t - Fall) / 0.6f;
            if (land < 1f)
                for (int i = 0; i < 5; i++)
                {
                    Vector3 q = foot + lieDir * (StaffLen * (0.2f + 0.16f * i)) + Vector3.up * (0.01f + 0.02f * land);
                    b.Sprite(q, 0.03f + 0.03f * land, A(ExodusFx.Sand, 0.6f * (1 - land)), DGFxPaint.Dust, i + land, false);
                }
            if (rise > 0.5f)
            {
                float k = Sat((rise - 0.5f) / 0.5f);
                Vector3 mid = Vector3.Lerp(top, bottom, 0.35f);
                for (int i = 0; i < 6; i++)
                {
                    float a = Tau * i / 6f + k * 1.5f;
                    Vector3 q = mid + c.camRight * (Mathf.Cos(a) * 0.035f * (0.6f + k)) + c.camUp * (Mathf.Sin(a) * 0.06f * (0.6f + k));
                    float al = Mathf.Sin(Mathf.PI * k) * fadeOut;
                    b.Sprite(q, 0.020f * (1 - 0.4f * k), A(i % 2 == 0 ? Sun : Color.white, al), DGFxPaint.Sparkle, k * 2f, false);
                }
                b.Sprite(mid, 0.10f, A(Sun, 0.35f * Mathf.Sin(Mathf.PI * k) * fadeOut), DGFxPaint.SoftDot, 0, true);
            }
        }
    }

    // ------------------------------------------------------------------ S06: the Nile turns red for a few seconds
    public sealed class ExRiverRed : FxDef
    {
        public override string Id => "river_red";
        public override float DefaultDur => 5f;
        public override bool Follow => false;

        // Draws a red layer just above the nileWater surface (DGPaperLit has no tint input, and the child's own blue must
        // turn red whatever it is): soft ground blobs that bloom outward from the middle in 0.6 s, hold, and fade in 1 s.
        public override void Emit(FxCtx c, FxBatch b)
        {
            float tout = Sat((c.dur - c.t) / 1.0f);
            if (tout <= 0) return;
            if (!ExodusFx.TryBox("nileWater", out Bounds box)) box = ExodusFx.NileFallback;
            float y = box.max.y + 0.0025f;
            float x0 = box.min.x, x1 = box.max.x, z0 = box.min.z, z1 = box.max.z;
            float width = Mathf.Max(0.03f, x1 - x0), len = Mathf.Max(0.05f, z1 - z0);
            float zc = (z0 + z1) * 0.5f;
            int n = Mathf.Clamp(Mathf.CeilToInt(len / 0.03f), 6, 22);
            float size = Mathf.Clamp(width * 1.25f, 0.05f, 0.18f);
            for (int i = 0; i < n; i++)
            {
                float f = (i + 0.5f) / n;
                float z = Mathf.Lerp(z0 + size * 0.3f, z1 - size * 0.3f, f);
                float delay = 0.32f * Mathf.Abs(z - zc) / (len * 0.5f);
                float a = Sat((c.t - delay) / 0.30f);
                float x = (x0 + x1) * 0.5f + 0.15f * width * Mathf.Sin(i * 1.9f + c.t * 0.8f) * 0.5f;
                b.Sprite(new Vector3(x, y, z), size, size * 1.15f, A(ExodusFx.NileRed, 0.80f * a * tout), DGFxPaint.SoftDot,
                         0.3f * i, false, FxFace.Ground);
                b.Sprite(new Vector3(x, y + 0.0003f, z), size * 0.62f, size * 0.9f, A(ExodusFx.NileRed, 0.75f * a * tout), DGFxPaint.SoftDot,
                         0.3f * i, false, FxFace.Ground);
            }
            // darker slow swirls drifting downstream (toward the viewer) for texture
            for (int i = 0; i < 6; i++)
            {
                float u = FxRand.H(c.seed, i, 0) + c.t * 0.025f / len;
                u -= Mathf.Floor(u);
                float z = Mathf.Lerp(z0 + 0.03f, z1 - 0.03f, u);
                float a = Sat((c.t - 0.25f) / 0.4f) * tout * Mathf.Sin(Mathf.PI * u);
                float x = (x0 + x1) * 0.5f + (FxRand.H(c.seed, i, 1) - 0.5f) * width * 0.4f;
                b.Sprite(new Vector3(x, y + 0.0005f, z), size * 0.45f, A(ExodusFx.NileRedDeep, 0.40f * a), DGFxPaint.Dust,
                         c.t * 0.5f * (i % 2 == 0 ? 1 : -1) + i, false, FxFace.Ground);
            }
            // the moment it turns: two ripple rings from the middle
            for (int k = 0; k < 2; k++)
            {
                float a = (c.t - 0.25f * k) / 0.9f;
                if (a <= 0 || a >= 1) continue;
                b.Sprite(new Vector3((x0 + x1) * 0.5f, y + 0.001f, zc), 0.03f + 0.14f * OutCubic(a),
                         A(ExodusFx.NileRedDeep, 0.6f * (1 - a)), DGFxPaint.Ring, 0, false, FxFace.Ground);
            }
        }
    }

    // ------------------------------------------------------------------ S06: frogs everywhere
    public sealed class ExFrogs : FxDef
    {
        public override string Id => "frogs";
        public override float DefaultDur => 16f;
        public override bool Follow => false;

        const int N = 12;
        const float Hop = 0.34f, Gap = 0.20f, Step = Hop + Gap, Size = 0.034f;
        static readonly Vector3[] Pos = new Vector3[N];
        static readonly float[] Sq = new float[N], Th = new float[N], Bl = new float[N], Al = new float[N];

        public override void Emit(FxCtx c, FxBatch b)
        {
            ExodusFx.ActorsWanted = true;
            if (!ExodusFx.TryBox("nileWater", out Bounds nile)) nile = ExodusFx.NileFallback;
            float riverX = nile.center.x;
            int shown = 0;
            for (int i = 0; i < N; i++)
            {
                Al[i] = 0;
                float zi = Mathf.Lerp(-0.27f, 0.17f, (i + 0.5f + 0.6f * FxRand.Signed(c.seed, i, 0)) / N);
                var start = new Vector3(riverX + 0.02f * FxRand.Signed(c.seed, i, 1), 0f, zi);
                var target = new Vector3(Mathf.Lerp(-0.44f, 0.12f, FxRand.H(c.seed, i, 2)), 0f, zi + 0.04f * FxRand.Signed(c.seed, i, 3));
                foreach (var a in ExodusFx.Actors)   // keep off the actors' feet
                {
                    Vector3 d = target - a.feet; d.y = 0;
                    float m = d.magnitude;
                    if (m < 0.075f) target = a.feet + (m > 1e-4f ? d / m : Vector3.forward) * 0.075f;
                }
                target.y = 0f;
                var exit = new Vector3(riverX - 0.03f, 0f, zi + 0.03f * FxRand.Signed(c.seed, i, 4));
                float t0 = 0.17f * i + 0.5f * FxRand.H(c.seed, i, 5);
                float tOut = c.dur - 1.6f + 0.5f * FxRand.H(c.seed, i, 6);
                float tt = c.t - t0;
                if (tt < 0) continue;
                const int hopsIn = 3, hopsOut = 2;
                Vector3 p; float sq = 1f, throat = 0f, alpha = 1f;
                if (tt < hopsIn * Step)
                {
                    int j = Mathf.Min((int)(tt / Step), hopsIn - 1);
                    float u = (tt - j * Step) / Hop;
                    Vector3 from = Vector3.Lerp(start, target, j / (float)hopsIn), to = Vector3.Lerp(start, target, (j + 1) / (float)hopsIn);
                    HopPose(from, to, u, 0.035f, out p, out sq);
                    if (j == 0) alpha = Sat(u * 3f);   // out of the river
                }
                else if (c.t < tOut)
                {
                    p = target;
                    float period = Mathf.Lerp(1.6f, 2.6f, FxRand.H(c.seed, i, 7));
                    float ph = (c.t + period * FxRand.H(c.seed, i, 8)) / period;
                    float a = ph - Mathf.Floor(ph);
                    if (a < 0.22f) { float k = Mathf.Sin(Mathf.PI * a / 0.22f); throat = k; sq = 1f + 0.06f * k; }
                }
                else
                {
                    float to2 = c.t - tOut;
                    int j = Mathf.Min((int)(to2 / Step), hopsOut - 1);
                    float u = (to2 - j * Step) / Hop;
                    Vector3 from = Vector3.Lerp(target, exit, j / (float)hopsOut), to = Vector3.Lerp(target, exit, (j + 1) / (float)hopsOut);
                    HopPose(from, to, u, 0.04f, out p, out sq);
                    if (j == hopsOut - 1) alpha = 1f - Sat((u - 0.4f) / 0.6f);
                    if (to2 > hopsOut * Step) alpha = 0;
                }
                float blinkPh = (c.t * 0.37f + FxRand.H(c.seed, i, 9)) % 1f;
                Pos[i] = p; Sq[i] = sq; Th[i] = throat; Bl[i] = blinkPh < 0.04f ? 1f : 0f; Al[i] = alpha;
                ExodusFx.SortKey[i] = (c.camPos - p).sqrMagnitude;
                shown++;
            }
            if (shown == 0) return;
            for (int i = 0; i < N; i++) if (Al[i] <= 0) ExodusFx.SortKey[i] = -1f;
            ExodusFx.SortBackToFront(N);
            for (int q = 0; q < N; q++)
            {
                int i = ExodusFx.SortIdx[q];
                if (Al[i] <= 0) continue;
                ExodusFx.Frog(b, c, Pos[i], Size * Mathf.Lerp(0.9f, 1.1f, FxRand.H(c.seed, i, 10)), Sq[i], Th[i], Bl[i], Al[i], true);
            }
        }

        /// <summary>One hop: an arc from 'from' to 'to' over u 0..1, then a little landing squash while u is 1..1.6.</summary>
        internal static void HopPose(Vector3 from, Vector3 to, float u, float height, out Vector3 p, out float squash)
        {
            if (u < 1f)
            {
                p = Vector3.Lerp(from, to, u) + Vector3.up * (height * Mathf.Sin(Mathf.PI * u));
                squash = u < 0.1f ? 1f - 0.2f * Mathf.Sin(Mathf.PI * u / 0.1f) : 1.16f;
            }
            else
            {
                p = to;
                squash = 1f - 0.18f * Mathf.Sin(Mathf.PI * Sat((u - 1f) / 0.55f));
            }
        }
    }

    // ------------------------------------------------------------------ S06: a frog lands on Pharaoh's head and croaks
    public sealed class ExFrogOnHead : FxDef
    {
        public override string Id => "frog_on_head";
        public override float DefaultDur => 7f;

        const float In = 0.55f, Out = 0.6f, Size = 0.040f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float t = c.t;
            Vector3 head = c.anchor + Vector3.up * ExodusFx.HeadTop + c.ToCamFlat(c.anchor) * 0.006f;
            Vector3 from = FxCtx.Ground(c.start, 0f) + c.camRight * 0.12f + c.ToCamFlat(c.start) * 0.05f;
            Vector3 to = FxCtx.Ground(c.anchor, 0f) - c.camRight * 0.13f + c.ToCamFlat(c.anchor) * 0.04f;
            Vector3 p; float sq = 1f, throat = 0f, alpha = 1f;
            if (t < In)
            {
                float u = t / In;
                p = Vector3.Lerp(from, head, u) + Vector3.up * (0.10f * Mathf.Sin(Mathf.PI * u));
                sq = 1.18f; alpha = Sat(u * 4f);
            }
            else if (t < c.dur - Out)
            {
                p = head;
                float s = t - In;
                if (s < 0.3f) sq = 1f - 0.2f * Mathf.Sin(Mathf.PI * s / 0.3f);   // landing squash
                // croaks: a puff of the throat and a little bounce, then a pause
                float ph = (s + 0.4f) / 1.7f;
                float a = ph - Mathf.Floor(ph);
                if (s > 0.3f && a < 0.28f)
                {
                    float k = Mathf.Sin(Mathf.PI * a / 0.28f);
                    throat = k; sq = 1f + 0.08f * k;
                    p += Vector3.up * (0.006f * k);
                }
            }
            else
            {
                float u = Sat((t - (c.dur - Out)) / (Out - 0.1f));
                p = Vector3.Lerp(head, to, u) + Vector3.up * (0.08f * Mathf.Sin(Mathf.PI * u));
                sq = 1.16f; alpha = 1f - Sat((u - 0.6f) / 0.4f);
            }
            float blink = ((t * 0.31f) % 1f) < 0.045f ? 1f : 0f;
            ExodusFx.Frog(b, c, p, Size, sq, throat, blink, alpha, false);
            if (throat > 0.6f)   // a tiny "croak" ring, comic
                b.Sprite(p + Vector3.up * 0.03f + c.camRight * 0.03f, 0.03f * throat, A(ExodusFx.FrogDark, 0.5f * (throat - 0.6f) / 0.4f),
                         DGFxPaint.Ring, 0, false);
        }
    }

    // ------------------------------------------------------------------ S06: a buzzing swarm of flies
    public sealed class ExFlies : FxDef
    {
        public override string Id => "flies";
        public override float DefaultDur => 3f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.4f, 0.5f);
            if (env <= 0) return;
            Vector3 o = ExodusFx.NodeOr(c.anchor, ExodusFx.Palace);
            o.y = 0;
            Vector3 centre = o + new Vector3(0f, 0.17f, 0.13f)
                           + new Vector3(0.025f * Mathf.Sin(c.t * 1.3f), 0.015f * Mathf.Sin(c.t * 1.9f + 1f), 0.02f * Mathf.Cos(c.t * 1.1f));
            const int n = 16;
            for (int i = 0; i < n; i++)
            {
                float r = Mathf.Lerp(0.03f, 0.075f, FxRand.H(c.seed, i, 0));
                float w = Mathf.Lerp(3.5f, 6.5f, FxRand.H(c.seed, i, 1)) * (i % 2 == 0 ? 1 : -1);
                float ph = Tau * FxRand.H(c.seed, i, 2);
                float tilt = FxRand.Signed(c.seed, i, 3) * 0.6f;
                float a = c.t * w + ph;
                Vector3 p = centre + new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a * 1.7f + i) * r * 0.45f + Mathf.Sin(a) * r * tilt, Mathf.Sin(a) * r);
                float appear = Sat((c.t - 0.12f * FxRand.H(c.seed, i, 4) * 3f) / 0.2f) * env;
                // wings: two pale blurs that flutter (alternating size, no strobe), then the dark body
                float buzz = 0.75f + 0.25f * Mathf.Sin(c.t * 47f + i * 2.3f);
                for (int s = -1; s <= 1; s += 2)
                    b.Sprite(p + c.camUp * 0.005f + c.camRight * (0.0045f * s), 0.011f * buzz, 0.008f, A(Color.white, 0.75f * appear),
                             DGFxPaint.SoftDot, 0, false, FxFace.Camera);
                b.Sprite(p, 0.010f, 0.008f, A(ExodusFx.InkCol(), 0.95f * appear), DGFxPaint.ConfettiDot, 0, false, FxFace.Camera);
            }
            // a few little "buzz" squiggles near the swarm (comic, crayon)
            for (int i = 0; i < 3; i++)
            {
                float a = c.t * 2.2f + i * 2.1f;
                Vector3 q = centre + c.camRight * (0.08f * Mathf.Cos(a)) + c.camUp * (0.05f + 0.02f * Mathf.Sin(a * 1.3f));
                var rb = b.Ribbon(DGFxPaint.Ribbon, false);
                for (int k = 0; k < 5; k++)
                    rb.Add(q + c.camRight * (0.006f * k) + c.camUp * (0.004f * (k % 2 == 0 ? 1 : -1)), 0.0018f,
                           A(ExodusFx.SoftInk(), 0.6f * env * Mathf.Abs(Mathf.Sin(a * 0.7f))));
            }
        }
    }

    // ------------------------------------------------------------------ S06: a short shower of bouncing hail
    public sealed class ExHail : FxDef
    {
        public override string Id => "hail";
        public override float DefaultDur => 3f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.4f, 0.8f);
            StoryTint.Request(c.seed, ExodusFx.HailTint, 0.85f * env, Color.black);
            if (env <= 0) return;
            const int n = 34;
            const float y0 = 0.55f, vFall = 1.4f, g = 2.2f;
            float tFall = y0 / vFall;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(0.9f, 1.3f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                int cyc = (int)Mathf.Floor(ph);
                float tl = (ph - cyc) * period;                          // seconds into this stone's cycle
                float tStart = c.t - tl;
                if (tStart > c.dur - 0.9f) continue;                     // stop dropping new stones near the end
                int key = i * 37 + cyc;
                var g0 = new Vector3(Mathf.Lerp(-0.56f, 0.56f, FxRand.H(c.seed, key, 2)), 0f, Mathf.Lerp(-0.46f, 0.18f, FxRand.H(c.seed, key, 3)));
                float size = Mathf.Lerp(0.013f, 0.021f, FxRand.H(c.seed, key, 4));
                float rad = size * 0.5f;
                Vector3 drift = new Vector3(FxRand.Signed(c.seed, key, 5), 0, FxRand.Signed(c.seed, key, 6)) * 0.05f;
                Vector3 p; float al = 1f;
                if (tl < tFall)
                {
                    p = g0 + Vector3.up * (y0 - vFall * tl + rad);
                    b.Sprite(p + Vector3.up * 0.02f, 0.006f, 0.04f, A(ExodusFx.Ice, 0.45f * env), DGFxPaint.Streak, Mathf.PI * 0.5f, false, FxFace.Camera);
                }
                else
                {
                    float s = tl - tFall;
                    // two bounces (0.24 s, 0.12 s), then rest and fade
                    float b1 = 0.24f, b2 = 0.12f;
                    float hgt = 0f;
                    if (s < b1) hgt = 0.5f * g * (s * (b1 - s)) * 0.9f;
                    else if (s < b1 + b2) { float u = s - b1; hgt = 0.5f * g * (u * (b2 - u)) * 0.9f; }
                    float slide = Sat(s / (b1 + b2));
                    p = g0 + drift * slide + Vector3.up * (rad + hgt);
                    al = 1f - Sat((s - 0.45f) / 0.25f);
                    if (s < 0.25f)
                        b.Sprite(FxCtx.Ground(g0, 0.003f), 0.01f + 0.05f * s / 0.25f, A(Color.white, 0.6f * (1 - s / 0.25f) * env),
                                 DGFxPaint.Ring, 0, false, FxFace.Ground);
                }
                if (al <= 0) continue;
                b.Sprite(p, size, A(ExodusFx.Hail, al * env), DGFxPaint.Puff, FxRand.H(c.seed, key, 7) * Tau, false);
            }
        }
    }

    // ------------------------------------------------------------------ S07: the door marks glow warm in the night
    public sealed class ExDoorGlow : FxDef
    {
        public override string Id => "door_glow";
        public override float DefaultDur => 30f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.2f, 1.2f);
            if (env <= 0) return;
            if (!ExodusFx.TryBox("doorMarks", out Bounds box)) box = ExodusFx.DoorFallback;
            float zf = box.max.z + 0.006f, top = box.max.y, bot = Mathf.Max(0f, box.min.y);
            bool two = box.size.x > 0.10f;
            for (int d = 0; d < (two ? 2 : 1); d++)
            {
                float x = two ? (d == 0 ? box.min.x + 0.03f : box.max.x - 0.03f) : box.center.x;
                float pulse = 0.86f + 0.14f * Mathf.Sin(c.t * Tau * 0.35f + d * 1.9f);
                Vector3 door = new Vector3(x, Mathf.Lerp(bot, top, 0.45f), zf);
                Vector3 lintel = new Vector3(x, top, zf + 0.002f);
                // warm light pouring out of the doorway onto the ground in front
                b.Sprite(new Vector3(x, 0.004f, zf + 0.05f), 0.16f, 0.12f, A(ExodusFx.DoorWarm, 0.55f * env * pulse), DGFxPaint.SoftDot,
                         0, false, FxFace.Ground);
                b.Sprite(door, 0.11f * pulse, 0.13f * pulse, A(ExodusFx.DoorWarm, 0.65f * env), DGFxPaint.SoftDot, 0, false, FxFace.Camera);
                b.Sprite(door + Vector3.forward * 0.004f, 0.05f, 0.07f, A(ExodusFx.FlameWhite, 0.55f * env * pulse), DGFxPaint.SoftDot, 0, true, FxFace.Camera);
                // the marks themselves: a soft red-gold glow along the lintel and both posts
                b.Sprite(lintel, 0.08f * pulse, 0.035f, A(ExodusFx.DoorRed, 0.75f * env), DGFxPaint.SoftDot, 0, true, FxFace.Camera);
                for (int s = -1; s <= 1; s += 2)
                    b.Sprite(new Vector3(x + s * 0.022f, Mathf.Lerp(bot, top, 0.55f), zf + 0.002f), 0.022f, 0.07f * pulse,
                             A(ExodusFx.DoorRed, 0.55f * env), DGFxPaint.SoftDot, 0, true, FxFace.Camera);
                // a few slow warm motes
                for (int i = 0; i < 3; i++)
                {
                    float period = Mathf.Lerp(3f, 4.5f, FxRand.H(c.seed, d * 7 + i, 0));
                    float ph = c.t / period + FxRand.H(c.seed, d * 7 + i, 1);
                    float a = ph - Mathf.Floor(ph);
                    Vector3 q = new Vector3(x + 0.03f * Mathf.Sin(a * 4f + i), bot + 0.02f + 0.10f * a, zf + 0.02f + 0.02f * i);
                    b.Sprite(q, 0.008f, A(ExodusFx.FlameWhite, Mathf.Sin(Mathf.PI * a) * env), DGFxPaint.SoftDot, 0, true);
                }
            }
        }
    }

    // ------------------------------------------------------------------ S08 / S11: the pillar of cloud / of fire
    public sealed class ExPillar : FxDef
    {
        readonly bool fire;
        public ExPillar(bool fire) { this.fire = fire; }
        public override string Id => fire ? "pillar_fire" : "pillar_cloud";
        public override float DefaultDur => 20f;
        public override bool Follow => false;

        const float H = 0.50f;
        const int N = 26;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.4f, 1.4f);
            if (env <= 0) return;
            Vector3 o = ExodusFx.NodeOr(c.start, ExodusFx.PillarWest); o.y = 0;
            Vector3 flatCam = c.ToCamFlat(o);
            Color body = fire ? ExodusFx.Fire : ExodusFx.Cloud, shade = fire ? ExodusFx.Ember : ExodusFx.CloudGrey;
            Color core = fire ? ExodusFx.FireCore : Color.white;
            float grow = Smooth(0f, 1f, c.t / 1.8f);   // the column builds up from the ground as it fades in

            // ground glow and a soft inner column of light
            b.Sprite(FxCtx.Ground(o, 0.004f), 0.26f, A(fire ? ExodusFx.FireCore : Color.white, (fire ? 0.40f : 0.30f) * env), DGFxPaint.SoftDot,
                     0, false, FxFace.Ground);
            for (int k = 0; k < 5; k++)
            {
                float y = H * (k + 0.5f) / 5f * grow;
                b.Sprite(o + Vector3.up * y - flatCam * 0.02f, 0.16f + 0.02f * k, 0.15f, A(core, (fire ? 0.30f : 0.22f) * env), DGFxPaint.SoftDot, 0,
                         false, FxFace.Camera);
            }
            // swirling puffs: two strands of a slow helix that rise forever; drawn back to front
            for (int i = 0; i < N; i++)
            {
                float u = (i / (float)N + c.t * 0.045f + 0.02f * FxRand.H(c.seed, i, 0)) % 1f;
                float y = u * H * grow;
                float strand = i % 2 == 0 ? 0f : Mathf.PI;
                float ang = u * 11f + c.t * 0.8f + strand;
                float r = Mathf.Lerp(0.030f, 0.058f, u);
                Vector3 off = new Vector3(Mathf.Cos(ang) * r, 0, Mathf.Sin(ang) * r);
                ExodusFx.SortKey[i] = -Vector3.Dot(off, flatCam);
            }
            ExodusFx.SortBackToFront(N);
            for (int q = 0; q < N; q++)
            {
                int i = ExodusFx.SortIdx[q];
                float u = (i / (float)N + c.t * 0.045f + 0.02f * FxRand.H(c.seed, i, 0)) % 1f;
                float y = u * H * grow;
                float strand = i % 2 == 0 ? 0f : Mathf.PI;
                float ang = u * 11f + c.t * 0.8f + strand;
                float r = Mathf.Lerp(0.030f, 0.058f, u);
                Vector3 off = new Vector3(Mathf.Cos(ang) * r, 0, Mathf.Sin(ang) * r);
                float front = 0.5f + 0.5f * Vector3.Dot(off.normalized, flatCam);
                float edge = Sat(u / 0.06f) * Sat((1 - u) / 0.14f);
                float size = Mathf.Lerp(0.075f, 0.105f, u) * Mathf.Lerp(0.9f, 1.1f, FxRand.H(c.seed, i, 1));
                Color col = Color.Lerp(shade, body, (fire ? 0.35f : 0.15f) + (fire ? 0.65f : 0.75f) * front);
                Vector3 p = o + off + Vector3.up * y;
                if (!fire && i % 4 == 0)   // a few crayon cloud outlines on the near side give the hand-drawn edge
                    b.Sprite(p + flatCam * 0.02f, size * 0.95f, size * 0.48f, A(col, 0.70f * edge * env), DGFxPaint.Bubble, 0.15f * Mathf.Sin(ang), false, FxFace.Camera);
                else
                    b.Sprite(p, size * 1.15f, A(col, (fire ? 0.70f : 0.85f) * edge * env), DGFxPaint.SoftDot, 0, false);
                if (fire && i % 2 == 0)
                    b.Sprite(p + flatCam * 0.01f, size * 0.55f, A(ExodusFx.FireCore, 0.45f * edge * env * front), DGFxPaint.SoftDot, 0, true);
            }
            // fire: tall flame tongues licking up the column
            if (fire)
                for (int k = 0; k < 4; k++)
                {
                    float ang = Tau * k / 4f + c.t * 0.4f;
                    Vector3 bs = o + new Vector3(Mathf.Cos(ang), 0, Mathf.Sin(ang)) * 0.025f + Vector3.up * (H * grow * (0.05f + 0.22f * k));
                    ExodusFx.Tongue(b, c, bs, c.t + k * 3f, 0.16f, 0.05f, ExodusFx.Fire, ExodusFx.FireCore, 1.7f * k, 0.75f * env);
                }
            // glow motes (cloud) / embers (fire) rising around the column
            int m = fire ? 12 : 7;
            for (int i = 0; i < m; i++)
            {
                float period = Mathf.Lerp(2.2f, 3.4f, FxRand.H(c.seed, i, 20));
                float ph = c.t / period + FxRand.H(c.seed, i, 21);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                float ang = Tau * FxRand.H(c.seed, i * 11 + cyc, 22) + a * 2f;
                float r = Mathf.Lerp(0.05f, 0.09f, FxRand.H(c.seed, i * 11 + cyc, 23));
                Vector3 p = o + new Vector3(Mathf.Cos(ang) * r, H * grow * Mathf.Lerp(0.05f, 0.9f, a), Mathf.Sin(ang) * r);
                float al = Mathf.Sin(Mathf.PI * a) * env;
                if (fire) b.Sprite(p, 0.010f * (1 - 0.5f * a) + 0.003f, A(i % 2 == 0 ? ExodusFx.FireCore : ExodusFx.Ember, al), DGFxPaint.Sparkle, a * 3f + i, false);
                else b.Sprite(p, 0.012f, A(Color.white, 0.8f * al), DGFxPaint.SoftDot, 0, true);
            }
        }
    }

    // ------------------------------------------------------------------ S11: the strong east wind over the sea
    public sealed class ExSeaWind : FxDef
    {
        public override string Id => "sea_wind";
        public override float DefaultDur => 9f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.2f, 1.5f);
            StoryTint.Request(c.seed, ExodusFx.WindTint, 0.85f * env, new Color(0.25f, 0.30f, 0.40f, 1f));
            if (env <= 0) return;
            float x0 = ExodusSea.X0, x1 = ExodusSea.X1;
            // wind streaks: wavy white ribbons racing from the far shore (+X, east) toward the west beach
            for (int i = 0; i < 12; i++)
            {
                float speed = Mathf.Lerp(0.32f, 0.48f, FxRand.H(c.seed, i, 0));
                float span = 0.95f;
                float u = FxRand.H(c.seed, i, 1) + c.t * speed / span;
                int lap = (int)Mathf.Floor(u);
                float f = u - lap;
                float head = 0.62f - f * span;
                float len = Mathf.Lerp(0.10f, 0.18f, FxRand.H(c.seed, i * 9 + lap, 2));
                float z = Mathf.Lerp(-0.26f, 0.20f, FxRand.H(c.seed, i * 9 + lap, 3));
                float y = Mathf.Lerp(0.03f, 0.24f, FxRand.H(c.seed, i * 9 + lap, 4));
                float al = Mathf.Sin(Mathf.PI * f) * env * 0.55f;
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                for (int k = 0; k < 6; k++)
                {
                    float s = k / 5f;
                    float x = head + len * s;
                    float yy = y + 0.008f * Mathf.Sin(s * 5f + c.t * 6f + i);
                    r.Add(new Vector3(x, yy, z), 0.006f * Mathf.Sin(Mathf.PI * Mathf.Lerp(0.1f, 1f, s)) + 0.001f,
                          A(ExodusFx.WindWhite, al * Mathf.Sin(Mathf.PI * s)));
                }
            }
            // spray torn off the waves, blown west in low arcs
            for (int i = 0; i < 22; i++)
            {
                float period = Mathf.Lerp(0.9f, 1.4f, FxRand.H(c.seed, i, 10));
                float ph = c.t / period + FxRand.H(c.seed, i, 11);
                int cyc = (int)Mathf.Floor(ph);
                float a = ph - cyc;
                int key = i * 23 + cyc;
                var s0 = new Vector3(Mathf.Lerp(x0, x1, FxRand.H(c.seed, key, 12)), 0.012f, Mathf.Lerp(-0.22f, 0.19f, FxRand.H(c.seed, key, 13)));
                float tt = a * period;
                Vector3 p = s0 + new Vector3(-0.30f * tt, 0.22f * tt - 0.35f * tt * tt, 0.02f * tt);
                if (p.y < 0.004f) continue;
                b.Sprite(p, 0.009f, A(ExodusFx.Spray, Mathf.Sin(Mathf.PI * a) * env), DGFxPaint.SoftDot, 0, false);
            }
            // white-cap streaks skimming the water surface
            for (int i = 0; i < 8; i++)
            {
                float u = FxRand.H(c.seed, i, 30) + c.t * 0.12f / (x1 - x0 + 0.1f);
                float f = u - Mathf.Floor(u);
                var p = new Vector3(x1 + 0.05f - f * (x1 - x0 + 0.1f), 0.014f, Mathf.Lerp(-0.22f, 0.19f, FxRand.H(c.seed, i, 31)));
                b.Sprite(p, 0.05f, 0.012f, A(Color.white, 0.55f * Mathf.Sin(Mathf.PI * f) * env), DGFxPaint.Streak, 0f, false, FxFace.Ground);
            }
            // sand grains from the far shore
            for (int i = 0; i < 8; i++)
            {
                float u = FxRand.H(c.seed, i, 40) + c.t * 0.38f / 1.0f;
                float f = u - Mathf.Floor(u);
                var p = new Vector3(0.62f - f * 1.0f, 0.02f + 0.06f * FxRand.H(c.seed, i, 41) + 0.01f * Mathf.Sin(c.t * 5f + i),
                                    Mathf.Lerp(-0.3f, 0.2f, FxRand.H(c.seed, i, 42)));
                b.Sprite(p, 0.012f, A(ExodusFx.Sand, 0.8f * Mathf.Sin(Mathf.PI * f) * env), DGFxPaint.Dust, c.t * 3f + i, false);
            }
        }
    }

    // ------------------------------------------------------------------ S11: the sea parts (the hero moment)
    public sealed class ExSeaPart : FxDef
    {
        public override string Id => "sea_part";
        public override float DefaultDur => 4.5f;
        public override bool Follow => false;
        public override float ShakeAmp => 0.0022f;   // a low, gentle rumble while the water stands up
        public override float ShakeDur => 3.2f;

        /// <summary>Wall height 0..1 over the effect's normalised time: waits, rises (accelerating then easing), a tiny
        /// overshoot, exactly 1 from n = 0.85 on.</summary>
        public static float Curve(float n)
        {
            float k = Sat((n - 0.10f) / 0.75f);
            if (k >= 1f) return 1f;
            float s = Smooth(0f, 1f, k);
            return s + 0.05f * Mathf.Sin(Mathf.PI * k) * k * k;
        }

        public override void Emit(FxCtx c, FxBatch b)
        {
            float n = c.N, t = c.t;
            float open = Curve(n);
            ExodusSea.Drive(open);
            float x0 = ExodusSea.X0, x1 = ExodusSea.X1, zc = ExodusSea.LaneZ;
            float halfLane = (ExodusSea.ZFront - ExodusSea.ZBack) * 0.5f;

            // 1. the split: a bright foam seam runs along the crossing lane from the west beach to the far shore
            float headK = Smooth(0f, 1f, (t - 0.05f) / 1.0f);
            float headX = Mathf.Lerp(x0 - 0.02f, x1 + 0.02f, headK);
            float seamA = 1f - Sat((t - 1.4f) / 0.6f);
            if (seamA > 0f)
            {
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                for (int k = 0; k < 8; k++)
                {
                    float x = Mathf.Lerp(x0 - 0.02f, headX, k / 7f);
                    r.Add(new Vector3(x, 0.016f, zc + 0.004f * Mathf.Sin(x * 60f + t * 8f)), 0.012f, A(ExodusFx.Foam, 0.9f * seamA));
                }
                if (headK < 1f)
                {
                    var hp = new Vector3(headX, 0.02f, zc);
                    b.Sprite(hp, 0.05f, A(ExodusFx.Caustic, 0.7f), DGFxPaint.SoftDot, 0, true);
                    b.Sprite(hp + Vector3.up * 0.005f, 0.03f, A(Color.white, 1f), DGFxPaint.Sparkle, t * 4f, false);
                }
                for (int k = 0; k < 5; k++)   // ripple rings left behind by the seam
                {
                    float xk = Mathf.Lerp(x0, x1, (k + 0.5f) / 5f);
                    float tk = 0.05f + 1.0f * Mathf.InverseLerp(x0 - 0.02f, x1 + 0.02f, xk);
                    float a = (t - tk) / 0.9f;
                    if (a <= 0 || a >= 1) continue;
                    b.Sprite(new Vector3(xk, 0.014f, zc), 0.02f + 0.10f * OutCubic(a), A(Color.white, 0.7f * (1 - a)), DGFxPaint.Ring, 0, false, FxFace.Ground);
                }
            }

            // 2. the lane opens: a burst of foam hides the moment the lane water goes (ExodusSea.LaneHideAt)
            for (int i = 0; i < 14; i++)
            {
                float d = 0.9f + 0.35f * FxRand.H(c.seed, i, 0);
                float a = (t - d) / 1.1f;
                if (a <= 0 || a >= 1) continue;
                var p = new Vector3(Mathf.Lerp(x0 + 0.01f, x1 - 0.01f, (i + FxRand.H(c.seed, i, 1)) / 14f),
                                    0.012f + 0.05f * OutCubic(a), zc + FxRand.Signed(c.seed, i, 2) * halfLane * 0.8f);
                ExodusFx.FoamPuff(b, p, 0.03f + 0.045f * OutCubic(a), 0.95f * (1 - a * a), i + a, i % 2 == 1);
            }

            // 3. spray thrown up by the rising crests (stronger while they rise fastest)
            const int nd = 28;
            for (int i = 0; i < nd; i++)
            {
                float period = 0.6f;
                float ph = t / period + FxRand.H(c.seed, i, 10);
                int cyc = (int)Mathf.Floor(ph);
                float age = (ph - cyc) * period;
                float tl = t - age;
                if (tl < 0) continue;
                float nl = tl / c.dur;
                float speed = (Curve(nl + 0.01f) - Curve(nl - 0.01f)) / 0.02f;   // d open / d n
                float strength = Sat(speed / 1.4f);
                if (strength <= 0.02f) continue;
                int key = i * 41 + cyc;
                bool back = FxRand.H(c.seed, key, 11) < 0.55f;
                float top = ExodusSea.Top(back, Curve(nl), ExodusSea.Clock);
                var s0 = new Vector3(Mathf.Lerp(x0, x1, FxRand.H(c.seed, key, 12)), top, ExodusSea.Face(back));
                var v0 = new Vector3(FxRand.Signed(c.seed, key, 13) * 0.08f, Mathf.Lerp(0.25f, 0.5f, FxRand.H(c.seed, key, 14)),
                                     ExodusSea.ToLane(back) * Mathf.Lerp(0.03f, 0.10f, FxRand.H(c.seed, key, 15)));
                Vector3 p = Ballistic(s0, v0, 1.6f, 0.3f, age);
                if (p.y < 0.01f) continue;
                float al = strength * (1 - age / period);
                if (i % 3 == 0) ExodusFx.FoamPuff(b, p, 0.020f, 0.9f * al, age * 4f + i);
                else b.Sprite(p, 0.010f, A(ExodusFx.Spray, al), DGFxPaint.SoftDot, 0, false);
            }

            // 4. mist along the rising walls, and twinkles on the crests once they stand
            float rising = Sat((Curve(n + 0.01f) - Curve(n - 0.01f)) / 0.02f / 1.4f);
            for (int w = 0; w < 2; w++)
            {
                bool back = w == 0;
                float top = ExodusSea.Top(back, open, ExodusSea.Clock);
                for (int k = 0; k < 3; k++)
                {
                    var p = new Vector3(Mathf.Lerp(x0, x1, (k + 0.5f) / 3f), top * 0.6f, ExodusSea.Face(back) + ExodusSea.ToLane(back) * 0.01f);
                    b.Sprite(p, 0.14f, 0.12f, A(ExodusFx.Caustic, 0.22f * rising), DGFxPaint.SoftDot, 0, true, FxFace.Camera);
                }
            }
            float path = Smooth(0.72f, 0.95f, n);   // a soft path of light runs along the opened lane, west to east
            if (path > 0f)
                for (int k = 0; k < 4; k++)
                {
                    float f = (k + 0.5f) / 4f;
                    float a = Sat((path - f * 0.6f) / 0.4f);
                    b.Sprite(new Vector3(Mathf.Lerp(x0, x1, f), 0.004f, zc), (x1 - x0) * 0.42f, halfLane * 2.2f,
                             A(ExodusFx.FlameWhite, 0.35f * a * (1f - 0.5f * Smooth(0.95f, 1f, n))), DGFxPaint.SoftDot, 0, true, FxFace.Ground);
                }
            if (n > 0.78f)
                for (int i = 0; i < 8; i++)
                {
                    float a = (n - 0.78f - 0.02f * i) / 0.14f;
                    if (a <= 0 || a >= 1) continue;
                    bool back = i % 2 == 0;
                    var p = new Vector3(Mathf.Lerp(x0 + 0.02f, x1 - 0.02f, FxRand.H(c.seed, i, 30)), ExodusSea.Top(back, open, ExodusSea.Clock) + 0.012f,
                                        ExodusSea.Face(back) + ExodusSea.ToLane(back) * 0.008f);
                    b.Sprite(p, 0.028f * Mathf.Sin(Mathf.PI * a), A(Color.white, Mathf.Sin(Mathf.PI * a)), DGFxPaint.Sparkle, a * 2f, false);
                }
        }
    }

    // ------------------------------------------------------------------ S12: the walls fall back
    public sealed class ExSeaClose : FxDef
    {
        public override string Id => "sea_close";
        public override float DefaultDur => 3f;
        public override bool Follow => false;
        public override float ShakeAmp => 0.003f;
        public override float ShakeDur => 1.3f;

        /// <summary>Seconds the walls take to drop (the splash sfx plays 0.4 s after the effect starts in story.py).</summary>
        public const float Drop = 0.5f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float t = c.t;
            float k = Sat(t / Drop);
            float open = 1f - k * k;
            if (t >= c.dur - 0.02f) open = 0f;
            ExodusSea.Drive(open);
            float x0 = ExodusSea.X0, x1 = ExodusSea.X1, zc = ExodusSea.LaneZ;
            float halfLane = (ExodusSea.ZFront - ExodusSea.ZBack) * 0.5f;
            float fade = Sat((c.dur - t) / 0.6f);

            // falling curtains of foam from both crests toward the middle of the lane
            if (t < Drop + 0.25f)
                for (int w = 0; w < 2; w++)
                {
                    bool back = w == 0;
                    float h0 = back ? ExodusSea.TopBackY : ExodusSea.TopFrontY;
                    for (int i = 0; i < 7; i++)
                    {
                        float u = Sat(t / (Drop + 0.1f));
                        var p = new Vector3(Mathf.Lerp(x0 + 0.01f, x1 - 0.01f, (i + 0.5f) / 7f),
                                            Mathf.Lerp(h0, 0.02f, u * u), Mathf.Lerp(ExodusSea.Face(back), zc, u));
                        ExodusFx.FoamPuff(b, p, 0.035f + 0.03f * u, 0.95f * (1 - Sat((t - Drop) / 0.25f)), i + t * 3f, i % 2 == 1);
                    }
                }

            // the crash: water leaps up along the whole lane, then falls back
            for (int i = 0; i < 26; i++)
            {
                float t0 = Drop * 0.75f + 0.1f * FxRand.H(c.seed, i, 0);
                float age = t - t0;
                if (age <= 0) continue;
                var s0 = new Vector3(Mathf.Lerp(x0, x1, FxRand.H(c.seed, i, 1)), 0.02f, zc + FxRand.Signed(c.seed, i, 2) * halfLane * 0.7f);
                var v0 = new Vector3(FxRand.Signed(c.seed, i, 3) * 0.12f, Mathf.Lerp(0.5f, 0.95f, FxRand.H(c.seed, i, 4)),
                                     FxRand.Signed(c.seed, i, 5) * 0.18f);
                Vector3 p = Ballistic(s0, v0, 1.9f, 0.4f, age);
                if (p.y < 0.008f) continue;
                if (i % 3 == 0) ExodusFx.FoamPuff(b, p, 0.024f, 0.95f * fade, age * 5f + i);
                else ExodusFx.WaterDrop(b, c, p, 0.011f, 1.25f, fade);
            }
            for (int i = 0; i < 10; i++)
            {
                float a = (t - Drop * 0.8f - 0.06f * i) / 1.2f;
                if (a <= 0 || a >= 1) continue;
                var p = new Vector3(Mathf.Lerp(x0 + 0.01f, x1 - 0.01f, (i + 0.5f) / 10f), 0.015f + 0.10f * Mathf.Sin(Mathf.PI * a * 0.8f),
                                    zc + FxRand.Signed(c.seed, i, 6) * halfLane * 0.5f);
                ExodusFx.FoamPuff(b, p, 0.04f + 0.05f * OutCubic(a), 0.95f * (1 - a * a), i + a * 2f, i % 2 == 1);
            }
            float mist = Sat((t - Drop * 0.7f) / 0.2f) * (1 - Sat((t - Drop) / 1.4f));
            if (mist > 0)
                for (int k2 = 0; k2 < 3; k2++)
                    b.Sprite(new Vector3(Mathf.Lerp(x0, x1, (k2 + 0.5f) / 3f), 0.06f, zc), 0.16f, 0.12f, A(ExodusFx.Spray, 0.35f * mist),
                             DGFxPaint.SoftDot, 0, false, FxFace.Camera);

            // ripples spreading over the whole sea and settling
            for (int i = 0; i < 7; i++)
            {
                float a = (t - Drop - 0.22f * i) / 1.3f;
                if (a <= 0 || a >= 1) continue;
                var p = new Vector3(Mathf.Lerp(x0 + 0.02f, x1 - 0.02f, FxRand.H(c.seed, i, 7)), 0.014f, Mathf.Lerp(-0.20f, 0.19f, FxRand.H(c.seed, i, 8)));
                b.Sprite(p, 0.03f + 0.13f * OutCubic(a), A(Color.white, 0.55f * (1 - a) * (1 - 0.1f * i)), DGFxPaint.Ring, 0, false, FxFace.Ground);
            }
        }
    }

    // ------------------------------------------------------------------ S11-S12: the standing walls (spawned by ExodusStage)
    /// <summary>Foam crests, light rippling up the inner faces, caustics on the sea-bed, a few fish glints. Draws whatever
    /// ExodusSea.Open says (grows with sea_part, falls with sea_close), so it needs no timing of its own.</summary>
    public sealed class ExSeaHold : FxDef
    {
        public override string Id => "sea_hold";
        public override float DefaultDur => 1e6f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            ExodusSea.Sync();
            float open = ExodusSea.Open;
            if (open <= 0.001f) return;
            float clock = ExodusSea.Clock;
            float A0 = Sat(c.t / 0.3f) * Smooth(0.04f, 0.5f, open);
            float stand = ExodusSea.Standing(open);
            float x0 = ExodusSea.X0, x1 = ExodusSea.X1, zc = ExodusSea.LaneZ;
            float halfLane = (ExodusSea.ZFront - ExodusSea.ZBack) * 0.5f;

            // caustics on the wet sand of the lane: a shimmering net of soft light rings, and a cool light pool
            float caus = A0 * Smooth(0.3f, 1f, open);
            b.Sprite(new Vector3((x0 + x1) * 0.5f, 0.003f, zc), (x1 - x0) * 1.05f, halfLane * 2.6f, A(ExodusFx.Caustic, 0.16f * caus),
                     DGFxPaint.SoftDot, 0, true, FxFace.Ground);
            for (int i = 0; i < 12; i++)
            {
                float fx = (i % 6 + 0.5f) / 6f, fz = i < 6 ? 0.3f : 0.72f;
                var p = new Vector3(Mathf.Lerp(x0, x1, fx) + 0.008f * Mathf.Sin(clock * 1.3f + i * 2.1f), 0.004f,
                                    Mathf.Lerp(ExodusSea.ZBack, ExodusSea.ZFront, fz) + 0.008f * Mathf.Cos(clock * 1.1f + i));
                float pulse = 0.5f + 0.5f * Mathf.Sin(clock * 2.3f + i * 1.7f);
                b.Sprite(p, 0.035f + 0.015f * pulse, A(ExodusFx.Caustic, (0.25f + 0.35f * pulse) * caus), DGFxPaint.Ring,
                         clock * 0.3f + i, true, FxFace.Ground);
            }

            for (int w = 0; w < 2; w++)
            {
                bool back = w == 0;
                float top = ExodusSea.Top(back, open, clock);
                float face = ExodusSea.Face(back), toLane = ExodusSea.ToLane(back);
                float baseY = ExodusSea.BaseY;
                // light rippling up the inner face (water lit from inside)
                for (int i = 0; i < 6; i++)
                {
                    float ph = clock * 0.10f + FxRand.H(c.seed, w * 17 + i, 0);
                    float a = ph - Mathf.Floor(ph);
                    var p = new Vector3(Mathf.Lerp(x0 + 0.02f, x1 - 0.02f, FxRand.H(c.seed, w * 17 + i, 1)) + 0.01f * Mathf.Sin(clock + i),
                                        Mathf.Lerp(baseY + 0.02f, top - 0.02f, a), face + toLane * 0.004f);
                    b.Sprite(p, 0.04f, 0.03f, A(ExodusFx.Caustic, 0.40f * Mathf.Sin(Mathf.PI * a) * A0), DGFxPaint.SoftDot, 0, true, FxFace.Camera);
                }
                // foam at the foot of the wall
                for (int i = 0; i < 5; i++)
                {
                    var p = new Vector3(Mathf.Lerp(x0 + 0.015f, x1 - 0.015f, (i + 0.5f) / 5f), baseY + 0.006f, face + toLane * 0.007f);
                    ExodusFx.FoamPuff(b, p, 0.018f + 0.003f * Mathf.Sin(clock * 2f + i), 0.75f * A0, clock * 0.5f + i, i % 2 == 1);
                }
                // the curling crest: a white foam line and bobbing foam blobs along the top
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                for (int k = 0; k < 10; k++)
                {
                    float x = Mathf.Lerp(x0, x1, k / 9f);
                    r.Add(new Vector3(x, top + 0.003f * Mathf.Sin(clock * 2.2f + x * 40f), face + toLane * 0.006f), 0.014f,
                          A(ExodusFx.Foam, 0.85f * A0));
                }
                for (int i = 0; i < 10; i++)
                {
                    float fx = (i + 0.5f) / 10f + 0.015f * Mathf.Sin(clock * 0.7f + i);
                    var p = new Vector3(Mathf.Lerp(x0 + 0.01f, x1 - 0.01f, fx), top + 0.006f + 0.004f * Mathf.Sin(clock * 3f + i * 1.7f),
                                        face + toLane * 0.008f);
                    ExodusFx.FoamPuff(b, p, Mathf.Lerp(0.016f, 0.026f, FxRand.H(c.seed, w * 13 + i, 2)), 0.92f * A0, clock * 0.4f + i, i % 3 != 0);
                }
                // now and then a little flick of spray off the crest
                for (int i = 0; i < 3; i++)
                {
                    float period = Mathf.Lerp(1.4f, 2.2f, FxRand.H(c.seed, w * 7 + i, 3));
                    float ph = clock / period + FxRand.H(c.seed, w * 7 + i, 4);
                    int cyc = (int)Mathf.Floor(ph);
                    float age = (ph - cyc) * period;
                    if (age > 0.7f) continue;
                    int key = (w * 7 + i) * 31 + cyc;
                    var s0 = new Vector3(Mathf.Lerp(x0, x1, FxRand.H(c.seed, key, 5)), top, face);
                    var v0 = new Vector3(0, Mathf.Lerp(0.12f, 0.2f, FxRand.H(c.seed, key, 6)), toLane * 0.06f);
                    Vector3 p = Ballistic(s0, v0, 1.2f, 0.3f, age);
                    b.Sprite(p, 0.008f, A(ExodusFx.Spray, (1 - age / 0.7f) * A0 * stand), DGFxPaint.SoftDot, 0, false);
                }
            }
            // fish glints sliding along inside the back wall
            for (int i = 0; i < 3; i++)
            {
                float u = (clock * 0.05f + FxRand.H(c.seed, i, 40)) % 1f;
                float top = ExodusSea.Top(true, open, clock);
                var p = new Vector3(Mathf.Lerp(x0 + 0.02f, x1 - 0.02f, (i % 2 == 0) ? u : 1 - u),
                                    Mathf.Lerp(ExodusSea.BaseY + 0.05f, top - 0.05f, FxRand.H(c.seed, i, 41)) + 0.006f * Mathf.Sin(clock * 2f + i),
                                    ExodusSea.ZBack + 0.003f);
                float g = Mathf.Pow(Sat(Mathf.Sin(clock * 1.7f + i * 2.4f)), 6f);
                b.Sprite(p, 0.018f * g + 0.004f, A(Color.white, (0.4f + 0.6f * g) * A0 * stand), DGFxPaint.Sparkle, 0.785f, false);
            }
        }
    }

    // ------------------------------------------------------------------ S12: a splash at Pharaoh's feet
    public sealed class ExSplash : FxDef
    {
        public override string Id => "splash";
        public override float DefaultDur => 2f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            Vector3 o = FxCtx.Ground(c.start, 0f);
            float t = c.t;
            for (int k = 0; k < 2; k++)
            {
                float a = (t - 0.22f * k) / 1.1f;
                if (a <= 0 || a >= 1) continue;
                b.Sprite(FxCtx.Ground(o, 0.004f + 0.001f * k), 0.04f + 0.16f * OutCubic(a), A(Color.white, 0.75f * (1 - a)), DGFxPaint.Ring,
                         0, false, FxFace.Ground);
                b.Sprite(FxCtx.Ground(o, 0.0035f), 0.03f + 0.10f * OutCubic(a), A(ExodusFx.Drop, 0.35f * (1 - a)), DGFxPaint.SoftDot,
                         0, false, FxFace.Ground);
            }
            for (int i = 0; i < 6; i++)
            {
                float a = (t - 0.03f * i) / 0.9f;
                if (a <= 0 || a >= 1) continue;
                Vector3 p = o + Flat(Tau * i / 6f, 0.03f + 0.02f * a) + Vector3.up * (0.01f + 0.035f * OutCubic(a));
                ExodusFx.FoamPuff(b, p, 0.03f + 0.03f * a, 0.9f * (1 - a * a), i + a, i % 2 == 1);
            }
            for (int i = 0; i < 20; i++)
            {
                float d = 0.04f * FxRand.H(c.seed, i, 0);
                float age = t - d;
                if (age <= 0) continue;
                float ang = Tau * (i + 0.5f * FxRand.H(c.seed, i, 1)) / 20f;
                var v0 = Flat(ang, Mathf.Lerp(0.14f, 0.32f, FxRand.H(c.seed, i, 2))) + Vector3.up * Mathf.Lerp(0.40f, 0.75f, FxRand.H(c.seed, i, 3));
                Vector3 p = Ballistic(o + Vector3.up * 0.02f, v0, 1.9f, 0.3f, age);
                if (p.y < 0.006f) continue;
                ExodusFx.WaterDrop(b, c, p, Mathf.Lerp(0.008f, 0.013f, FxRand.H(c.seed, i, 4)), 1.2f, Sat((c.dur - t) / 0.3f));
            }
        }
    }

    // ------------------------------------------------------------------ S12: soggy Pharaoh drips
    public sealed class ExDrips : FxDef
    {
        public override string Id => "drips";
        public override float DefaultDur => 8f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.2f, 0.6f);
            if (env <= 0) return;
            const int n = 6;
            const float g = 1.4f;
            for (int i = 0; i < n; i++)
            {
                float ang = Tau * (i + 0.3f * FxRand.H(c.seed, i, 0)) / n;
                Vector3 src = c.anchor + Flat(ang, 0.034f) + Vector3.up * (0.004f + 0.012f * FxRand.H(c.seed, i, 1));
                float period = Mathf.Lerp(1.3f, 2.1f, FxRand.H(c.seed, i, 2));
                float ph = c.t / period + FxRand.H(c.seed, i, 3);
                float tl = (ph - Mathf.Floor(ph)) * period;
                const float swell = 0.55f;
                if (tl < swell)
                {   // the drop gathers under the head-cloth edge
                    float k = tl / swell;
                    ExodusFx.WaterDrop(b, c, src - Vector3.up * (0.005f * k), 0.005f + 0.008f * k, 1f + 0.35f * k, env * Sat(k * 3f));
                    continue;
                }
                float tf = tl - swell;
                float y = src.y - 0.5f * g * tf * tf;
                if (y > 0.006f)
                {
                    Vector3 p = new Vector3(src.x, y, src.z);
                    ExodusFx.WaterDrop(b, c, p, 0.013f, 1.35f, env);
                }
                else
                {   // tiny ring where it lands
                    float tLand = Mathf.Sqrt(2f * Mathf.Max(0f, src.y - 0.006f) / g);
                    float a = (tf - tLand) / 0.35f;
                    if (a > 0 && a < 1)
                        b.Sprite(new Vector3(src.x, 0.004f, src.z), 0.012f + 0.03f * a, A(ExodusFx.Drop, 0.8f * (1 - a) * env), DGFxPaint.Ring,
                                 0, false, FxFace.Ground);
                }
            }
            // a little wet puddle growing under him
            b.Sprite(FxCtx.Ground(c.anchor, 0.0035f), 0.10f + 0.04f * Sat(c.t / 4f), A(ExodusFx.Drop, 0.35f * env), DGFxPaint.SoftDot, 0, false, FxFace.Ground);
        }
    }
}
