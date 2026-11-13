// Ruth (story pack #3) effects, docs/ruth/FX.md. Same engine as David & Goliath and Esther: every effect is a pure
// function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered
// in FxLibrary after the D&G and Esther ids (an existing id is never replaced). Reused, not redefined: petals,
// golden_rays, confetti, prayer_glow, tension_dim. `sparkle` is Esther's crown_sparkle under a generic id.
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// The two stage tints (sunset_glow, night) post requests to StoryTint; StoryTintStage (StoryFxRuthRuntime.cs) turns them
// into a multiply overlay over the stage and the global shader values. Their sky bands, sun, moon, stars, fireflies
// and the actors' moonlight halos are ordinary sprites drawn here (after the overlay, so they are never tinted).
// Child-friendly rules as before: no flash, no strobe, nothing bright over a face.
using System.Collections.Generic;
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>One actor as the night / sunset effects see it (stage-local feet position, figure height).</summary>
    public struct RuthActor
    {
        public Vector3 feet;
        public float height;
    }

    /// <summary>Ruth registry, palette and stage layout (docs/ruth/CONTRACT.md §6, §8).</summary>
    public static class RuthFx
    {
        internal static FxDef[] Defs => new FxDef[]
        {
            new DustRoad(), new HeartGlow(), new Chaff(), new StalksFall(),
            new SunsetGlow(), new NightSky(), new LampFlame(), new SparkleBurst(),
        };

        /// <summary>Actors that get a moonlight / golden back-halo during night / sunset_glow. Filled every frame by
        /// StoryTintStage from the DGActors under DGFx.Stage; the preview harness fills it by hand.</summary>
        public static readonly List<RuthActor> Actors = new List<RuthActor>(4);

        /// <summary>Draw the halo behind each actor while night / sunset_glow play (the overlay-mode stand-in for a rim light).
        /// Set false once the character shader adds _DoodStageRim itself.</summary>
        public static bool ActorHalo = true;

        /// <summary>Field centre used by chaff when the 'field' node's origin sits at the set origin (CONTRACT §6 field rect).</summary>
        public static readonly Vector3 FieldCentre = new Vector3(0.37f, 0f, -0.11f);

        // CONTRACT §6 road: pale track from (-0.60, 0.18) through the road marks, curving toward the door
        internal static readonly Vector2[] Road =
        {
            new Vector2(-0.68f, 0.19f), new Vector2(-0.52f, 0.178f), new Vector2(-0.40f, 0.16f),
            new Vector2(-0.28f, 0.14f), new Vector2(-0.21f, 0.07f), new Vector2(-0.20f, -0.02f),
        };

        // Back of the stage: hills front face z ~ -0.56, top <= 0.30. Sky bands hang just behind them.
        internal const float SkyZ = -0.70f;

        // docs/ruth/DESIGN.md demo colours + Paper & Crayon tokens (sRGB)
        internal static readonly Color Barley = new Color32(0xE8, 0xB8, 0x4A, 255);
        internal static readonly Color Straw = new Color32(0xE9, 0xD0, 0x8A, 255);
        internal static readonly Color SheafGold = new Color32(0xE2, 0xA9, 0x3B, 255);
        internal static readonly Color Stem = new Color32(0xD4, 0xB2, 0x62, 255);
        internal static readonly Color RoadDust = new Color32(0xE9, 0xD9, 0xB6, 255);   // road
        internal static readonly Color Ochre = new Color32(0xD9, 0xB7, 0x7A, 255);      // ground
        internal static readonly Color WarmWhite = new Color32(0xFF, 0xF1, 0xC8, 255);
        internal static readonly Color Blush = new Color32(0xFB, 0xD3, 0xDF, 255);
        internal static readonly Color Rose = new Color32(0xF4, 0xA6, 0xB8, 255);       // wedding flower pink
        internal static readonly Color LampOrange = new Color32(0xFF, 0x9A, 0x3C, 255);
        internal static readonly Color LampPool = new Color32(0xFF, 0xC8, 0x6A, 255);
        internal static readonly Color Moon = new Color32(0xFF, 0xF4, 0xCC, 255);
        internal static readonly Color MoonLight = new Color32(0xA8, 0xC0, 0xFF, 255);   // cool halo
        internal static readonly Color Firefly = new Color32(0xE8, 0xF5, 0x7A, 255);
        internal static readonly Color NightHigh = new Color32(0x12, 0x18, 0x4A, 255);
        internal static readonly Color NightMid = new Color32(0x1E, 0x2B, 0x6E, 255);
        internal static readonly Color NightLow = new Color32(0x34, 0x47, 0x8C, 255);
        internal static readonly Color DuskHigh = new Color32(0xE8, 0x8F, 0x8C, 255);
        internal static readonly Color DuskMid = new Color32(0xF5, 0xA2, 0x5A, 255);
        internal static readonly Color DuskLow = new Color32(0xFF, 0xC9, 0x6A, 255);

        /// <summary>Multiply tints (sRGB) at full strength, and the rim colour for shaders that read _DoodStageRim.</summary>
        public static Color NightTint = new Color(0.46f, 0.54f, 0.90f, 1f);
        public static Color NightRim = new Color(0.45f, 0.55f, 0.85f, 1f);
        public static Color SunsetTint = new Color(1.00f, 0.86f, 0.66f, 1f);
        public static Color SunsetRim = new Color(0.45f, 0.30f, 0.10f, 1f);

        /// <summary>Stage-local end point of heart_glow: the director's `to` (copied by StoryFxStage into
        /// EstherFx.BeamTarget); when nobody set it, a point 0.12 to the right of the anchor.</summary>
        internal static Vector3 Target(FxCtx c)
        {
            var t = EstherFx.BeamTarget;
            if ((t - EstherFx.DefaultBeamTarget).sqrMagnitude < 1e-8f) return c.anchor + c.camRight * 0.12f;
            return t;
        }

        internal static Vector3 RoadPoint(float s)   // s in 0..1 along the road polyline
        {
            s = Sat(s) * (Road.Length - 1);
            int i = Mathf.Min((int)s, Road.Length - 2);
            var p = Vector2.Lerp(Road[i], Road[i + 1], s - i);
            return new Vector3(p.x, 0f, p.y);
        }

        /// <summary>A horizontal crayon sky band (ribbon) at height y, behind the hills.</summary>
        internal static void SkyBand(FxBatch b, float y, float width, Color col, float alpha, float wave, float t)
        {
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            const int pts = 9;
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);
                float x = Mathf.Lerp(-0.82f, 0.82f, f);
                float yy = y + wave * Mathf.Sin(f * 5.1f + y * 13f + t * 0.15f);
                r.Add(new Vector3(x, yy, SkyZ - 0.01f * f), width, A(col, alpha));
            }
        }

        /// <summary>A soft halo behind each actor (depth-tested, so the body hides its centre and it shows as a rim).</summary>
        internal static void Halos(FxCtx c, FxBatch b, Color col, float alpha)
        {
            if (!ActorHalo) return;
            foreach (var a in Actors)
            {
                float h = a.height > 0.05f ? a.height : 0.33f;
                Vector3 mid = a.feet + Vector3.up * (h * 0.56f);
                Vector3 away = (mid - c.camPos).normalized;
                b.Sprite(mid + away * 0.07f, h * 0.95f, h * 1.45f, A(col, alpha), DGFxPaint.SoftDot, 0, false, FxFace.Camera);
            }
        }

        internal static float ScreenAngle(FxCtx c, Vector3 dir) => Mathf.Atan2(Vector3.Dot(dir, c.camUp), Vector3.Dot(dir, c.camRight));
    }

    /// <summary>
    /// Stage tint requests (pure). Each running sunset_glow / night posts its multiply colour, level and rim colour every
    /// frame under its seed; StoryTintStage resolves them once per frame. A request not renewed for two resolves
    /// disappears, so stopping the effect releases the tint by itself. DGFx.StopAll() (StoryLight.Reset) clears it at once.
    /// </summary>
    public static class StoryTint
    {
        struct Req { public Color mul, rim; public float level; public int tick; }
        static readonly Dictionary<int, Req> reqs = new Dictionary<int, Req>();
        static readonly List<int> stale = new List<int>();
        static int tick;

        public static void Request(int key, Color mul, float level, Color rim)
            => reqs[key] = new Req { mul = mul, rim = rim, level = Sat(level), tick = tick };

        /// <summary>tint = product of lerp(white, mul, level); rim = sum of rim * level; level = strongest request.</summary>
        public static void Resolve(out Color tint, out Color rim, out float level)
        {
            tint = Color.white; rim = Color.black; level = 0f;
            stale.Clear();
            foreach (var kv in reqs)
            {
                var r = kv.Value;
                if (r.tick < tick - 1) { stale.Add(kv.Key); continue; }
                tint *= Color.Lerp(Color.white, r.mul, r.level);
                rim += r.rim * r.level;
                level = Mathf.Max(level, r.level);
            }
            foreach (int k in stale) reqs.Remove(k);
            tint.a = 1f; rim.a = 1f;
            tick++;
        }

        public static void Clear() => reqs.Clear();
    }

    // ------------------------------------------------------------------ S01: dust on the road from Moab
    public sealed class DustRoad : FxDef
    {
        public override string Id => "dust_road";
        public override float DefaultDur => 6f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 0.8f);
            if (env <= 0) return;
            Vector3 o = c.start; o.y = 0;   // "stage": the origin; the road is in stage coordinates
            // low haze that drifts along the road (wind from Moab, left to right)
            const int n = 14;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(2.6f, 3.6f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                float s0 = FxRand.H(c.seed, i * 17 + cyc, 2) * 0.85f;
                Vector3 p = o + RuthFx.RoadPoint(s0 + a * 0.16f);
                p += new Vector3(0, 0, FxRand.Signed(c.seed, i * 17 + cyc, 3) * 0.03f);
                p.y = 0.012f + 0.035f * a;
                float life = Mathf.Sin(Mathf.PI * a);
                bool big = i % 3 == 0;
                if (big)
                    b.Sprite(p, Mathf.Lerp(0.10f, 0.18f, a), A(RuthFx.RoadDust, 0.55f * life * env), DGFxPaint.SoftDot, 0, false);
                else
                    b.Sprite(p, Mathf.Lerp(0.034f, 0.07f, a), A(Color.Lerp(RuthFx.RoadDust, RuthFx.Ochre, 0.35f), 0.7f * life * env),
                             DGFxPaint.Dust, i + a * 0.8f, false);
            }
            // tiny sunlit motes floating above the haze
            for (int i = 0; i < 9; i++)
            {
                float period = Mathf.Lerp(3.0f, 4.4f, FxRand.H(c.seed, i, 10));
                float ph = c.t / period + FxRand.H(c.seed, i, 11);
                float a = ph - Mathf.Floor(ph);
                Vector3 p = o + RuthFx.RoadPoint(FxRand.H(c.seed, i, 12) * 0.8f + a * 0.12f);
                p.y = 0.03f + 0.06f * a + 0.01f * Mathf.Sin(c.t * 2f + i);
                b.Sprite(p, 0.010f, A(WarmTint, Mathf.Sin(Mathf.PI * a) * env * 0.9f), DGFxPaint.SoftDot, 0, false);
            }
        }

        static readonly Color WarmTint = new Color32(0xFF, 0xE3, 0xA8, 255);
    }

    // ------------------------------------------------------------------ S02: "Where you go, I will go"
    public sealed class HeartGlow : FxDef
    {
        public override string Id => "heart_glow";
        public override float DefaultDur => 6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 1.0f);
            if (env <= 0) return;
            float breathe = 0.85f + 0.15f * Mathf.Sin(c.t * Tau * 0.45f);
            Vector3 chest = c.anchor;
            Vector3 target = RuthFx.Target(c);
            Vector3 toCam = (c.camPos - chest).normalized;

            // warm glow at her chest (a little in front so it reads over the dress), and behind her
            b.Sprite(chest - toCam * 0.05f, 0.24f, A(Gold, 0.34f * env * breathe), DGFxPaint.SoftDot, 0, false);
            b.Sprite(chest + toCam * 0.02f, 0.11f, A(RuthFx.Rose, 0.40f * env * breathe), DGFxPaint.SoftDot, 0, false);
            b.Sprite(chest + toCam * 0.025f, 0.04f, A(Sun, 0.25f * env * breathe), DGFxPaint.SoftDot, 0, true);

            // the warmth arrives at Naomi: her glow grows as the motes reach her
            float arrive = Sat((c.t - 1.4f) / 2.0f) * env;
            Vector3 tToCam = (c.camPos - target).normalized;
            b.Sprite(target - tToCam * 0.05f, 0.20f, A(Sun, 0.26f * arrive * breathe), DGFxPaint.SoftDot, 0, false);
            b.Sprite(target + tToCam * 0.02f, 0.08f, A(RuthFx.Blush, 0.38f * arrive * breathe), DGFxPaint.SoftDot, 0, false);

            // tiny light motes drifting along a soft arc from her chest to Naomi's
            const int n = 12;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(2.0f, 2.8f, FxRand.H(c.seed, i, 0));
                float tt = c.t - 0.4f - period * FxRand.H(c.seed, i, 1);
                if (tt < 0) continue;
                float ph = tt / period;
                float a = ph - Mathf.Floor(ph);
                float s = Smooth(0f, 1f, a);
                Vector3 p = Vector3.Lerp(chest, target, s)
                          + Vector3.up * (Mathf.Sin(Mathf.PI * s) * Mathf.Lerp(0.03f, 0.06f, FxRand.H(c.seed, i, 2)))
                          + c.camUp * (0.008f * Mathf.Sin(tt * 5f + i)) + c.camRight * (0.006f * Mathf.Cos(tt * 4f + i * 2f))
                          + toCam * 0.03f;
                float life = Sat(a * 6f) * Sat((1 - a) * 4f);
                bool tw = i % 3 == 0;
                Color col = i % 2 == 0 ? Sun : (i % 3 == 1 ? RuthFx.Rose : RuthFx.Blush);
                b.Sprite(p, tw ? 0.022f : 0.016f, A(col, life * env * (tw ? 1f : 0.9f)), tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot,
                         tt * 1.5f, false);
                if (!tw) b.Sprite(p, 0.007f, A(RuthFx.WarmWhite, life * env), DGFxPaint.SoftDot, 0, true);
            }
        }
    }

    // ------------------------------------------------------------------ S04-S07: chaff and pollen over the barley (loop)
    public sealed class Chaff : FxDef
    {
        public override string Id => "chaff";
        public override float DefaultDur => 999f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 0.8f);
            if (env <= 0) return;
            Vector3 o = c.start; o.y = 0;
            if (new Vector2(o.x, o.z).sqrMagnitude < 0.05f * 0.05f) o = RuthFx.FieldCentre;   // node origin at the set origin
            const float W = 0.42f, D = 0.26f;   // drift box over the field rect (x 0.20..0.54, z -0.22..0.00) + spill
            const int n = 34;
            for (int i = 0; i < n; i++)
            {
                float speed = Mathf.Lerp(0.018f, 0.032f, FxRand.H(c.seed, i, 0));       // wind along +x
                float u = FxRand.H(c.seed, i, 1) + c.t * speed / W;
                float fx = u - Mathf.Floor(u);
                int lap = (int)Mathf.Floor(u);
                float z = o.z + FxRand.Signed(c.seed, i * 13 + lap, 2) * D * 0.5f;
                float y = Mathf.Lerp(0.06f, 0.19f, FxRand.H(c.seed, i * 13 + lap, 3))
                        + 0.018f * Mathf.Sin(c.t * Mathf.Lerp(0.9f, 1.6f, FxRand.H(c.seed, i, 4)) + i);
                Vector3 p = new Vector3(o.x - W * 0.5f + fx * W, y, z)
                          + c.camRight * (0.006f * Mathf.Sin(c.t * 2.3f + i * 1.7f));
                float edge = Mathf.Sin(Mathf.PI * fx);   // fade in / out at the ends of the drift box
                float a = edge * env;
                int kind = i % 4;
                if (kind == 0)        // pollen speck that catches the sun now and then
                {
                    float glint = Mathf.Pow(Sat(Mathf.Sin(c.t * 1.3f + i * 2.1f)), 8f);
                    b.Sprite(p, 0.013f, A(Sun, 0.9f * a), DGFxPaint.SoftDot, 0, false);
                    if (glint > 0.05f) b.Sprite(p, 0.022f * glint, A(RuthFx.WarmWhite, glint * a), DGFxPaint.Sparkle, c.t + i, false);
                }
                else                  // chaff sliver, tumbling slowly
                {
                    float rot = c.t * Mathf.Lerp(-2.2f, 2.2f, FxRand.H(c.seed, i, 5)) + i;
                    float flip = 0.45f + 0.55f * Mathf.Abs(Mathf.Cos(c.t * 2.5f + i));
                    Color col = kind == 1 ? RuthFx.Barley : (kind == 2 ? RuthFx.Straw : RuthFx.SheafGold);
                    if (kind == 3)   // a few crayon husks with the pencil edge
                        b.Sprite(p, 0.018f, 0.007f * flip, A(col, 0.8f * a), DGFxPaint.Pebble, rot, false, FxFace.Camera);
                    else             // soft golden slivers
                        b.Sprite(p, 0.032f, 0.010f * flip, A(col, 0.95f * a), DGFxPaint.Streak, rot, false, FxFace.Camera);
                }
            }
        }
    }

    // ------------------------------------------------------------------ S07: Boaz drops barley "by accident"
    public sealed class StalksFall : FxDef
    {
        public override string Id => "stalks_fall";
        public override float DefaultDur => 1.2f;
        public override bool Follow => false;   // the stalks fall from where the hand opened

        public override void Emit(FxCtx c, FxBatch b)
        {
            Vector3 o = c.start;
            float fade = 1 - Smooth(c.dur - 0.3f, c.dur, c.t);
            const int n = 5;
            const float g = 1.5f;
            for (int i = 0; i < n; i++)
            {
                float t = c.t - 0.05f * i;
                if (t <= 0) continue;
                float head = Tau * FxRand.H(c.seed, i, 0);
                Vector3 hd = new Vector3(Mathf.Cos(head), 0, Mathf.Sin(head));
                var v0 = new Vector3(FxRand.Signed(c.seed, i, 1) * 0.07f, Mathf.Lerp(0.02f, 0.08f, FxRand.H(c.seed, i, 2)),
                                     FxRand.Signed(c.seed, i, 3) * 0.05f);
                float len = Mathf.Lerp(0.05f, 0.068f, FxRand.H(c.seed, i, 4));
                Vector3 p0 = o + hd * 0.006f;
                // time the stalk centre reaches the page: y0 + vy t - g t^2/2 = lift
                float y0 = p0.y - 0.006f;
                float tl = (v0.y + Mathf.Sqrt(v0.y * v0.y + 2 * g * Mathf.Max(0f, y0))) / g;
                bool landed = t >= tl;
                float ts = landed ? tl : t;
                Vector3 p = p0 + new Vector3(v0.x * ts, v0.y * ts - 0.5f * g * ts * ts, v0.z * ts);
                // tumble in a vertical plane, settle flat on landing (plus a small hop)
                float theta0 = Mathf.Lerp(0.9f, 1.4f, FxRand.H(c.seed, i, 5));   // starts nearly upright (as held)
                float spin = Mathf.Lerp(4f, 7f, FxRand.H(c.seed, i, 6)) * (i % 2 == 0 ? 1 : -1);
                float theta = theta0 + spin * ts;
                if (landed)
                {
                    float k = Sat((t - tl) / 0.12f);
                    float flat = Mathf.Round(theta / Mathf.PI) * Mathf.PI;
                    theta = Mathf.Lerp(theta, flat, OutCubic(k));
                    p.y = 0.006f + 0.01f * Mathf.Sin(Mathf.PI * k) * (1 - k);
                }
                Vector3 dir = (hd * Mathf.Cos(theta) + Vector3.up * Mathf.Sin(theta)).normalized;
                Stalk(b, c, p, dir, len, fade * Sat(t * 12f));
            }
        }

        /// <summary>One barley stalk: a straw stem ribbon and a bearded ear of crayon grains (Pebble cells).</summary>
        static void Stalk(FxBatch b, FxCtx c, Vector3 mid, Vector3 dir, float len, float alpha)
        {
            Vector3 a = mid - dir * (len * 0.5f), tip = mid + dir * (len * 0.5f);
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k < 4; k++)
            {
                float f = k / 3f * 0.62f;
                r.Add(Vector3.Lerp(a, tip, f), 0.0050f, A(RuthFx.Stem, alpha));
            }
            float ang = RuthFx.ScreenAngle(c, dir);
            // the ear: a plump gold crayon stroke, slightly knobbly (grains), pointed at the tip
            var ear = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k <= 7; k++)
            {
                float f = 0.56f + 0.44f * k / 7f;
                float w = 0.0105f * Mathf.Sin(Mathf.PI * Mathf.Lerp(0.15f, 0.95f, k / 7f)) * (k % 2 == 0 ? 1f : 0.82f);
                ear.Add(Vector3.Lerp(a, tip, f), Mathf.Max(w, 0.002f), A(Color.Lerp(RuthFx.SheafGold, RuthFx.Barley, k / 7f), alpha));
            }
            // the beard: two thin awns past the tip
            Vector3 side = (c.camRight * -Mathf.Sin(ang) + c.camUp * Mathf.Cos(ang)) * 0.006f;
            for (int s = -1; s <= 1; s += 2)
            {
                var aw = b.Ribbon(DGFxPaint.Ribbon, false);
                aw.Add(tip - dir * 0.008f, 0.0018f, A(RuthFx.Stem, alpha));
                aw.Add(tip + dir * 0.018f + side * s, 0.0012f, A(RuthFx.Stem, alpha * 0.8f));
            }
        }
    }

    // ------------------------------------------------------------------ S08: golden hour
    public sealed class SunsetGlow : FxDef
    {
        public override string Id => "sunset_glow";
        public override float DefaultDur => 26f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 0.8f);
            StoryTint.Request(c.seed, RuthFx.SunsetTint, env, RuthFx.SunsetRim);
            if (env <= 0) return;
            // warm sky behind the hills: rose on top, orange, then gold at the horizon
            RuthFx.SkyBand(b, 0.60f, 0.20f, RuthFx.DuskHigh, 0.55f * env, 0.010f, c.t);
            RuthFx.SkyBand(b, 0.45f, 0.20f, RuthFx.DuskMid, 0.62f * env, 0.012f, c.t);
            RuthFx.SkyBand(b, 0.31f, 0.20f, RuthFx.DuskLow, 0.70f * env, 0.008f, c.t);
            // the low sun, half behind the hills (the depth test hides its lower part)
            var sun = new Vector3(0.38f, 0.26f, RuthFx.SkyZ + 0.02f);
            float pulse = 0.94f + 0.06f * Mathf.Sin(c.t * 0.8f);
            b.Sprite(sun, 0.42f * pulse, A(RuthFx.DuskLow, 0.55f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(sun + Vector3.forward * 0.005f, 0.11f, A(new Color(1f, 0.78f, 0.38f), env), DGFxPaint.Puff, 0, false);
            b.Sprite(sun + Vector3.forward * 0.01f, 0.20f * pulse, A(Sun, 0.35f * env), DGFxPaint.SoftDot, 0, true);
            // golden back-light around the actors and golden dust floating in the low light
            RuthFx.Halos(c, b, RuthFx.DuskLow, 0.30f * env);
            for (int i = 0; i < 16; i++)
            {
                float period = Mathf.Lerp(5f, 8f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                var p = new Vector3(Mathf.Lerp(-0.50f, 0.50f, FxRand.H(c.seed, i * 7 + cyc, 2)) + 0.05f * a,
                                    Mathf.Lerp(0.05f, 0.30f, FxRand.H(c.seed, i * 7 + cyc, 3)) + 0.03f * Mathf.Sin(Tau * a),
                                    Mathf.Lerp(-0.35f, 0.15f, FxRand.H(c.seed, i * 7 + cyc, 4)));
                b.Sprite(p, 0.011f, A(i % 2 == 0 ? Sun : RuthFx.DuskLow, Mathf.Sin(Mathf.PI * a) * env * 0.9f), DGFxPaint.SoftDot, 0, true);
            }
        }
    }

    // ------------------------------------------------------------------ S09: night at the threshing floor
    public sealed class NightSky : FxDef
    {
        public override string Id => "night";
        public override float DefaultDur => 24f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 0.8f);
            StoryTint.Request(c.seed, RuthFx.NightTint, env, RuthFx.NightRim);
            if (env <= 0) return;
            // deep-blue crayon sky behind the hills, darker toward the top
            RuthFx.SkyBand(b, 0.62f, 0.22f, RuthFx.NightHigh, 0.92f * env, 0.010f, c.t);
            RuthFx.SkyBand(b, 0.46f, 0.22f, RuthFx.NightMid, 0.92f * env, 0.012f, c.t);
            RuthFx.SkyBand(b, 0.31f, 0.20f, RuthFx.NightLow, 0.88f * env, 0.008f, c.t);

            // a friendly crayon moon (cream disc with the ink rim) and its glow
            var moon = new Vector3(-0.40f, 0.58f, RuthFx.SkyZ + 0.02f);
            b.Sprite(moon, 0.20f, A(RuthFx.MoonLight, 0.35f * env), DGFxPaint.SoftDot, 0, true);
            b.Sprite(moon + Vector3.forward * 0.005f, 0.065f, A(RuthFx.Moon, env), DGFxPaint.Puff, 0, false);

            // stars: many tiny twinkles and a few bigger crayon stars, in front of the sky bands
            const int n = 44;
            for (int i = 0; i < n; i++)
            {
                float x = Mathf.Lerp(-0.74f, 0.74f, (i + FxRand.H(c.seed, i, 0)) / n);
                float y = Mathf.Lerp(0.30f, 0.72f, FxRand.H(c.seed, i, 1));
                var p = new Vector3(x, y, RuthFx.SkyZ + 0.015f);
                if ((p - moon).sqrMagnitude < 0.07f * 0.07f) continue;
                float tw = 0.55f + 0.45f * Mathf.Sin(c.t * Mathf.Lerp(1.2f, 3.0f, FxRand.H(c.seed, i, 2)) + Tau * FxRand.H(c.seed, i, 3));
                float appear = Sat((c.t - 0.3f - 0.9f * FxRand.H(c.seed, i, 4)) / 0.4f);   // stars come out one by one
                float size = Mathf.Lerp(0.012f, 0.028f, FxRand.H(c.seed, i, 5) * FxRand.H(c.seed, i, 6));
                if (i % 7 == 0)
                    b.Sprite(p, 0.034f, A(RuthFx.Moon, env * appear * (0.8f + 0.2f * tw)), DGFxPaint.Star, 0.2f * Mathf.Sin(c.t + i), false);
                else
                    b.Sprite(p, size * (0.8f + 0.3f * tw), A(i % 3 == 0 ? RuthFx.Moon : Color.white, env * appear * tw), DGFxPaint.Sparkle,
                             0.785f * (i % 2), false);
            }

            // moonlight back-halo around each actor (keeps the figures readable against the dark)
            RuthFx.Halos(c, b, RuthFx.MoonLight, 0.50f * env);

            // a few fireflies blinking over the barley
            for (int i = 0; i < 7; i++)
            {
                float blink = Mathf.Pow(Sat(Mathf.Sin(c.t * Mathf.Lerp(0.7f, 1.2f, FxRand.H(c.seed, i, 20)) + Tau * FxRand.H(c.seed, i, 21))), 3f);
                var p = new Vector3(Mathf.Lerp(0.20f, 0.56f, FxRand.H(c.seed, i, 22)) + 0.03f * Mathf.Sin(c.t * 0.5f + i),
                                    Mathf.Lerp(0.04f, 0.13f, FxRand.H(c.seed, i, 23)) + 0.015f * Mathf.Sin(c.t * 0.8f + i * 2f),
                                    Mathf.Lerp(-0.22f, 0.04f, FxRand.H(c.seed, i, 24)) + 0.02f * Mathf.Cos(c.t * 0.6f + i));
                b.Sprite(p, 0.035f, A(RuthFx.Firefly, 0.55f * blink * env), DGFxPaint.SoftDot, 0, true);
                b.Sprite(p, 0.009f, A(RuthFx.Firefly, blink * env), DGFxPaint.SoftDot, 0, false);
            }
        }
    }

    // ------------------------------------------------------------------ S09: the little oil lamp by the grain heap (loop)
    public sealed class LampFlame : FxDef
    {
        public override string Id => "lamp_flame";
        public override float DefaultDur => 24f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.6f, 0.8f);
            if (env <= 0) return;
            float t = c.t + 10f * FxRand.H(c.seed, 0, 9);
            float fl = 0.93f + 0.04f * Mathf.Sin(t * 8.3f) + 0.03f * Mathf.Sin(t * 13.9f + 1.1f) + 0.02f * Mathf.Sin(t * 23.1f);
            Vector3 o = c.anchor;
            Vector3 away = (o - c.camPos).normalized;

            // the warm pool on the page (alpha, so it reads warm over the night-blue ground) + an additive heart
            b.Sprite(FxCtx.Ground(o, 0.004f), 0.46f * (0.97f + 0.03f * fl), A(RuthFx.LampPool, 0.48f * env * fl), DGFxPaint.SoftDot,
                     0, false, FxFace.Ground);
            b.Sprite(FxCtx.Ground(o, 0.005f), 0.20f, A(RuthFx.LampOrange, 0.30f * env * fl), DGFxPaint.SoftDot, 0, true, FxFace.Ground);
            // light spilling over the grain heap and the stones around it (camera-facing, behind the flame)
            b.Sprite(o + away * 0.02f, 0.22f * fl, A(RuthFx.LampPool, 0.30f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(o + Vector3.up * 0.01f, 0.09f * fl, A(Sun, 0.55f * env), DGFxPaint.SoftDot, 0, true);

            // the flame: an orange tongue and a warm-white core (small: an oil lamp, not a brazier)
            Tongue(b, c, o, t, 0.034f * fl, 0.017f, RuthFx.LampOrange, Sun, 0f, env);
            Tongue(b, c, o, t, 0.019f * fl, 0.009f, Sun, RuthFx.WarmWhite, 2.1f, env);

            // now and then a tiny spark
            for (int i = 0; i < 3; i++)
            {
                float period = Mathf.Lerp(1.6f, 2.4f, FxRand.H(c.seed, i, 0));
                float p = c.t / period + FxRand.H(c.seed, i, 1);
                float a = p - Mathf.Floor(p);
                if (a > 0.5f) continue;
                float k = a / 0.5f;
                Vector3 q = o + c.camRight * (0.006f * Mathf.Sin(k * 6f + i)) + Vector3.up * (0.03f + 0.06f * k);
                b.Sprite(q, 0.008f * (1 - k) + 0.003f, A(Sun, (1 - k) * env), DGFxPaint.Sparkle, k * 3f, false);
            }
        }

        static void Tongue(FxBatch b, FxCtx c, Vector3 bs, float t, float height, float width, Color baseCol, Color tipCol, float phase, float alpha)
        {
            const int pts = 6;
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);
                float sway = (0.6f * Mathf.Sin(t * 5.5f + phase - f * 3f) + 0.4f * Mathf.Sin(t * 9.7f + phase - f * 4f)) * 0.004f * f * f;
                Vector3 p = bs + c.camRight * sway + Vector3.up * (height * f - 0.003f);
                float w = width * Mathf.Sin(Mathf.PI * Mathf.Lerp(0.35f, 1f, f));
                r.Add(p, Mathf.Max(w, 0.0008f), A(Color.Lerp(baseCol, tipCol, f), alpha));
            }
        }
    }

    // ------------------------------------------------------------------ S08 / S11: a small twinkle burst (reuses crown_sparkle)
    public sealed class SparkleBurst : FxDef
    {
        readonly CrownSparkle look = new CrownSparkle();
        public override string Id => "sparkle";
        public override float DefaultDur => 1.6f;
        public override void Emit(FxCtx c, FxBatch b) => look.Emit(c, b);
    }
}
