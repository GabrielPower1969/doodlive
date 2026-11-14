// Daniel (story pack #4) effects, docs/daniel/FX.md. Same engine as David & Goliath, Esther and Ruth: every effect is a
// pure function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and
// registered in FxLibrary after the D&G, Esther and Ruth ids (an existing id is never replaced).
// New: roar_shake, angel_light, zzz, dawn_glow. `dust_puff` already exists (D&G, Goliath's footsteps) and is reused as
// is. `steam` and `sweat` are aliases of Esther's `anger_steam` / `sweat_drops` (resolved by id at play time, so this
// file does not depend on Esther's class names). Reused unchanged: sparkle, prayer_glow, tension_dim, golden_rays,
// confetti, sunset_glow, night, lamp_flame.
// dawn_glow posts a request to StoryTint (StoryFxRuth.cs); StoryTintStage (StoryFxRuthRuntime.cs) already turns any
// request into the multiply overlay and the global shader values, so no runtime file is needed here.
// Only managed UnityEngine value types are used (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no flash, no strobe, nothing bright over a face; the roar is warm, not scary.
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Daniel registry and palette (docs/daniel/CONTRACT.md §8, DESIGN.md "Light and mood per part").</summary>
    public static class DanielFx
    {
        internal static FxDef[] Defs => new FxDef[]
        {
            new RoarShake(), new AngelLight(), new ZzzFloat(), new DawnGlow(),
            new StoryFxAlias("steam", "anger_steam"), new StoryFxAlias("sweat", "sweat_drops"),
        };

        // Paper & Crayon tokens + Babylon demo colours (sRGB)
        internal static readonly Color Sand = new Color32(0xE6, 0xCF, 0x9E, 255);        // den floor / courtyard dust
        internal static readonly Color SandDeep = new Color32(0xC9, 0xA8, 0x6E, 255);
        internal static readonly Color DustBrown = new Color32(0xA8, 0x86, 0x5A, 255);    // roar dust (reads on sand)
        internal static readonly Color WarmWhite = new Color32(0xFF, 0xF4, 0xD6, 255);   // angel light
        internal static readonly Color AngelGold = new Color32(0xFF, 0xE0, 0x96, 255);
        internal static readonly Color SleepFill = new Color32(0xF4, 0xF7, 0xFF, 255);   // zzz letters
        internal static readonly Color SleepEdge = new Color32(0x3E, 0x52, 0x9A, 255);
        internal static readonly Color DawnHigh = new Color32(0xB8, 0xA6, 0xDE, 255);    // lilac
        internal static readonly Color DawnMid = new Color32(0xF6, 0xA9, 0xBE, 255);     // pink
        internal static readonly Color DawnLow = new Color32(0xFF, 0xD3, 0x8C, 255);     // gold
        internal static readonly Color DawnSun = new Color32(0xFF, 0xC4, 0x7A, 255);

        /// <summary>Dawn multiply tint (sRGB) at full strength and its rim colour (for shaders that read _DoodStageRim).</summary>
        public static Color DawnTint = new Color(1.00f, 0.87f, 0.86f, 1f);
        public static Color DawnRim = new Color(0.40f, 0.24f, 0.22f, 1f);

        /// <summary>A horizontal crayon sky band behind the city wall (front z ~ -0.56, top <= 0.30), at RuthFx.SkyZ + dz.</summary>
        internal static void SkyBand(FxBatch b, float y, float width, Color col, float alpha, float wave, float t, float dz)
        {
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            const int pts = 9;
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);
                float x = Mathf.Lerp(-0.82f, 0.82f, f);
                float yy = y + wave * Mathf.Sin(f * 4.3f + y * 11f + t * 0.2f);
                r.Add(new Vector3(x, yy, RuthFx.SkyZ + dz - 0.01f * f), width, A(col, alpha));
            }
        }
    }

    /// <summary>Plays another registered effect under a second id (aliases for ids a story names differently).</summary>
    public sealed class StoryFxAlias : FxDef
    {
        readonly string id, target;
        public StoryFxAlias(string id, string target) { this.id = id; this.target = target; }
        FxDef T => target != id ? FxLibrary.Get(target) : null;
        public override string Id => id;
        public override float DefaultDur => T?.DefaultDur ?? 1f;
        public override bool Follow => T?.Follow ?? true;
        public override float ShakeAmp => T?.ShakeAmp ?? 0f;
        public override float ShakeDur => T?.ShakeDur ?? 0f;
        public override float Flash => T?.Flash ?? 0f;
        public override void Emit(FxCtx c, FxBatch b) => T?.Emit(c, b);
    }

    // ------------------------------------------------------------------ S08 / S12: the lion roars
    /// <summary>
    /// No camera shake: the head throws out a ring of sandy dust and a fainter second ring, warm "roar" dashes fly
    /// outward, and cartoon shake arcs "(( ))" jitter either side of the head. Small, readable, not scary.
    /// </summary>
    public sealed class RoarShake : FxDef
    {
        public override string Id => "roar_shake";
        public override float DefaultDur => 1.2f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float t = c.t;
            float outK = 1 - Smooth(c.dur - 0.3f, c.dur, t);
            if (outK <= 0) return;
            Vector3 head = c.anchor + (c.camPos - c.anchor).normalized * 0.02f;   // just in front of the mane

            // two dust rings in the screen plane: a big one at once, a smaller echo
            for (int ring = 0; ring < 2; ring++)
            {
                float t0 = ring == 0 ? 0.02f : 0.32f;
                float life = ring == 0 ? 0.75f : 0.6f;
                float a = (t - t0) / life;
                if (a <= 0 || a >= 1) continue;
                float e = OutCubic(a);
                float rMax = ring == 0 ? 0.13f : 0.10f;
                b.Sprite(head, 2f * (0.04f + rMax * e), A(DanielFx.DustBrown, (ring == 0 ? 0.75f : 0.5f) * (1 - a) * outK),
                         DGFxPaint.Ring, a * 0.8f + ring, false, FxFace.Camera);
                const int n = 11;
                for (int i = 0; i < n; i++)
                {
                    int id = ring * 32 + i;
                    float ang = Tau * (i + 0.45f * FxRand.H(c.seed, id, 0)) / n + ring * 0.3f;
                    Vector3 dir = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                    float rad = (0.035f + rMax * e) * Mathf.Lerp(0.85f, 1.1f, FxRand.H(c.seed, id, 1));
                    Vector3 p = head + dir * rad + Vector3.down * (0.02f * a * a);       // dust sinks a little as it slows
                    float size = Mathf.Lerp(0.03f, 0.062f, e) * Mathf.Lerp(0.8f, 1.2f, FxRand.H(c.seed, id, 2)) * (ring == 0 ? 1f : 0.8f);
                    Color col = Color.Lerp(DanielFx.SandDeep, DanielFx.DustBrown, 0.6f * FxRand.H(c.seed, id, 3));
                    b.Sprite(p, size, A(col, 0.9f * Mathf.Pow(1 - a, 1.2f) * Sat(a * 10f) * outK), DGFxPaint.Dust,
                             FxRand.H(c.seed, id, 4) * Tau + a);
                }
            }

            // warm roar dashes shooting outward (upper half, so they do not hide the paws)
            for (int i = 0; i < 7; i++)
            {
                float t0 = 0.04f + 0.03f * (i % 3);
                float a = (t - t0) / 0.45f;
                if (a <= 0 || a >= 1) continue;
                float ang = Mathf.Lerp(-0.35f, Mathf.PI + 0.35f, (i + 0.5f) / 7f);
                Vector3 dir = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                float r0 = 0.07f + 0.12f * OutCubic(a), r1 = r0 + 0.06f * (1 - a) + 0.015f;
                var l = b.Ribbon(DGFxPaint.Ribbon, false);
                l.Add(head + dir * r0, 0.018f, A(i % 2 == 0 ? Orange : Sun, (1 - a) * outK));
                l.Add(head + dir * r1, 0.007f, A(Sun, 0.9f * (1 - a) * outK));
            }

            // cartoon shake arcs either side of the head, jittering while the head shakes
            float shake = 1 - Smooth(0.7f * c.dur, 0.9f * c.dur, t);
            float pop = OutBack(t / 0.12f);
            if (shake > 0)
            {
                float jit = (Mathf.Sin(t * 95f) > 0 ? 1f : -1f) * 0.005f;
                for (int side = -1; side <= 1; side += 2)
                {
                    for (int k = 0; k < 2; k++)
                    {
                        float cx = 0.075f + 0.02f * k;
                        float h = (0.032f - 0.008f * k) * pop;
                        var arc = b.Ribbon(DGFxPaint.Ribbon, false);
                        for (int j = 0; j < 5; j++)
                        {
                            float f = j / 4f * 2f - 1f;                               // -1..1 along the arc
                            float bow = (1 - f * f) * 0.012f;                         // bulges outward
                            Vector3 p = head + c.camRight * (side * (cx + bow + jit)) + c.camUp * (f * h + 0.01f);
                            arc.Add(p, 0.008f, A(SoftInk, 0.85f * shake * outK * (k == 0 ? 1f : 0.7f)));
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ S09: the angel's light in the den
    /// <summary>
    /// The emotional peak: a soft warm-white column of light falling from above onto Daniel, a glowing pool on the den
    /// floor, motes drifting down and swirling in the beam, and a faint winged shape of light above him. Fades in 1 s,
    /// holds, fades out 1.2 s. Stays where it started (Daniel kneels; the column must not wobble).
    /// </summary>
    public sealed class AngelLight : FxDef
    {
        public override string Id => "angel_light";
        public override float DefaultDur => 8f;
        public override bool Follow => false;

        /// <summary>Height of the winged shape's centre above the den floor (Daniel kneels ~0.22 tall). Lower it if the
        /// S09 framing cuts the wings off on device.</summary>
        public static float AngelHeight = 0.31f;

        const float Top = 0.95f;          // the column comes from well above the page
        const float RTop = 0.075f, RBottom = 0.15f;   // half widths: a soft cone, wider on the floor

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.0f, 1.2f);
            if (env <= 0) return;
            env = env * env * (3 - 2 * env);    // smooth in and out
            Vector3 g = FxCtx.Ground(c.start, 0.004f);
            Vector3 toCam = c.ToCamFlat(g);
            Vector3 side = Vector3.Cross(Vector3.up, toCam).normalized;
            float breathe = 0.9f + 0.1f * Mathf.Sin(c.t * Tau * 0.3f);

            // the pool of light on the den floor (alpha so it reads warm on the night-blue sand, then an additive heart)
            b.Sprite(g, 2f * RBottom * 1.5f, A(DanielFx.AngelGold, 0.55f * env * breathe), DGFxPaint.GlowDisc, c.t * 0.1f, false, FxFace.Ground);
            b.Sprite(g + Vector3.up * 0.001f, 2f * RBottom * 1.1f, A(DanielFx.WarmWhite, 0.45f * env), DGFxPaint.SoftDot, 0, true, FxFace.Ground);

            // the column: a wide soft veil, then layered vertical beams that shimmer slowly, then a bright core
            Vector3 top = g + Vector3.up * Top - toCam * 0.06f;   // tilted a touch away from the viewer
            Beam(b, top, g, side, 0f, RTop * 2.2f, RBottom * 2.3f, A(DanielFx.WarmWhite, 0.30f * env), false);
            const int n = 5;
            for (int i = 0; i < n; i++)
            {
                float f = (i - (n - 1) * 0.5f) / ((n - 1) * 0.5f);   // -1..1 across the column
                float pulse = 0.6f + 0.4f * Mathf.Sin(Tau * (0.22f * c.t + 0.31f * i));
                Color col = i % 2 == 0 ? DanielFx.WarmWhite : DanielFx.AngelGold;
                Beam(b, top, g, side, f, RTop * 0.75f, RBottom * 0.8f, A(col, 0.26f * env * pulse), true);
            }
            Beam(b, top, g, side, 0f, RTop * 0.6f, RBottom * 0.6f, A(DanielFx.WarmWhite, 0.30f * env * breathe), true);

            // a soft glow behind Daniel (depth-tested: his body hides the centre, so it reads as a rim)
            Vector3 mid = g + Vector3.up * 0.13f - toCam * 0.06f;
            b.Sprite(mid, 0.30f, 0.36f, A(DanielFx.AngelGold, 0.42f * env * breathe), DGFxPaint.SoftDot, 0, false, FxFace.Camera);

            // motes drifting down the beam on slow spirals, a twinkle every third
            const int m = 24;
            for (int i = 0; i < m; i++)
            {
                float period = Mathf.Lerp(3.2f, 5.0f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                float y = Mathf.Lerp(0.62f, 0.02f, a);
                float rr = Mathf.Lerp(RTop, RBottom, 1 - y / Top) * Mathf.Lerp(0.25f, 0.95f, FxRand.H(c.seed, i, 2));
                float ang = Tau * FxRand.H(c.seed, i, 3) + c.t * Mathf.Lerp(0.4f, 0.9f, FxRand.H(c.seed, i, 4)) * (i % 2 == 0 ? 1 : -1);
                Vector3 p = Vector3.Lerp(g, top, y / Top) + Vector3.up * 0f;
                p.y = g.y + y;
                p += side * (Mathf.Cos(ang) * rr) + toCam * (Mathf.Sin(ang) * rr);
                float life = Mathf.Sin(Mathf.PI * a);
                bool tw = i % 3 == 0;
                b.Sprite(p, tw ? 0.026f : 0.015f, A(i % 2 == 0 ? DanielFx.WarmWhite : DanielFx.AngelGold, life * env),
                         tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, c.t * 0.8f + i, tw);
            }

            // the faint winged shape of light, above and a little behind Daniel; appears after the column, leaves first
            float w = Sat((c.t - 0.9f) / 1.4f) * Sat((c.dur - 0.9f - c.t) / 1.0f);
            if (w > 0) Angel(c, b, g + Vector3.up * AngelHeight - toCam * 0.09f, w * w * (3 - 2 * w));
        }

        /// <summary>One vertical beam from 'top' to the floor at lateral position f (-1..1) of the cone.</summary>
        static void Beam(FxBatch b, Vector3 top, Vector3 g, Vector3 side, float f, float wTop, float wBottom, Color col, bool add)
        {
            var r = b.Ribbon(DGFxPaint.Streak, add);
            const int pts = 5;
            for (int k = 0; k < pts; k++)
            {
                float s = k / (float)(pts - 1);                          // 0 top .. 1 floor
                Vector3 axis = Vector3.Lerp(top, g + Vector3.up * 0.002f, s);
                float half = Mathf.Lerp(RTop, RBottom, s) * 0.7f;
                float fade = Sat(s * 3.5f) * (1f - 0.35f * Smooth(0.85f, 1f, s));   // soft top end, slightly softer at the floor
                r.Add(axis + side * (f * half), Mathf.Lerp(wTop, wBottom, s), A(col, col.a * fade));
            }
        }

        /// <summary>The winged shape: a soft body, a head glow and two wings of four feather strokes, gently beating.</summary>
        static void Angel(FxCtx c, FxBatch b, Vector3 o, float a)
        {
            Vector3 R = c.camRight, U = c.camUp;
            float beat = 0.10f * Mathf.Sin(c.t * Tau * 0.32f);
            b.Sprite(o + U * 0.05f, 0.30f, 0.30f, A(DanielFx.AngelGold, 0.22f * a), DGFxPaint.SoftDot, 0, true, FxFace.Camera);    // aura
            b.Sprite(o - U * 0.01f, 0.05f, 0.15f, A(DanielFx.WarmWhite, 0.55f * a), DGFxPaint.SoftDot, 0, true, FxFace.Camera);    // robe
            b.Sprite(o + U * 0.085f, 0.045f, A(DanielFx.WarmWhite, 0.6f * a), DGFxPaint.SoftDot, 0, true, FxFace.Camera);          // head
            b.Sprite(o + U * 0.09f, 0.09f, A(DanielFx.AngelGold, 0.35f * a), DGFxPaint.SoftDot, 0, true, FxFace.Camera);          // head glow
            Vector3 shoulder = o + U * 0.045f;
            for (int s = -1; s <= 1; s += 2)
            {
                // leading edge: from the shoulder up and out to the wing tip, a gentle arc
                float lift = 1.25f + beat;
                var edge = b.Ribbon(DGFxPaint.Ribbon, true);
                const int pts = 6;
                for (int j = 0; j < pts; j++)
                {
                    float f = j / (float)(pts - 1);
                    edge.Add(WingEdge(shoulder, R, U, s, lift, f), Mathf.Lerp(0.024f, 0.010f, f), A(DanielFx.WarmWhite, 0.5f * a));
                }
                // five feathers hang from the edge, down and out, longest near the middle
                for (int k = 0; k < 5; k++)
                {
                    float f = Mathf.Lerp(0.22f, 1f, k / 4f);
                    Vector3 root = WingEdge(shoulder, R, U, s, lift, f);
                    float ang = Mathf.Lerp(-1.65f, -0.35f, k / 4f) - 0.4f * beat;   // pointing down-in near the body, out at the tip
                    Vector3 dir = R * (s * Mathf.Cos(ang)) + U * Mathf.Sin(ang);
                    float len = Mathf.Lerp(0.055f, 0.095f, Mathf.Sin(Mathf.PI * Mathf.Lerp(0.25f, 0.85f, k / 4f)));
                    var r = b.Ribbon(DGFxPaint.Ribbon, true);
                    for (int j = 0; j < 4; j++)
                    {
                        float q = j / 3f;
                        r.Add(root + dir * (len * q) + R * (s * 0.008f * q * q), Mathf.Lerp(0.032f, 0.010f, q),
                              A(Color.Lerp(DanielFx.WarmWhite, DanielFx.AngelGold, q * 0.7f), 0.30f * a * (1f - 0.5f * q)));
                    }
                }
            }
        }

        static Vector3 WingEdge(Vector3 shoulder, Vector3 R, Vector3 U, int s, float lift, float f)
        {
            float ang = Mathf.Lerp(0.45f, lift, f);            // starts nearly level, curls up toward the tip
            float len = 0.13f * f;
            return shoulder + R * (s * (0.012f + len * Mathf.Cos(ang * 0.8f))) + U * (len * Mathf.Sin(ang) * 0.9f);
        }
    }

    // ------------------------------------------------------------------ S09: the lioness dozes off (loop)
    /// <summary>Cartoon "Z z z": cream letters with a soft blue crayon edge float up from the head, growing, wobbling and
    /// tilting, one every 0.8 s; each pops in with a little overshoot and fades near the top.</summary>
    public sealed class ZzzFloat : FxDef
    {
        public override string Id => "zzz";
        public override float DefaultDur => 6f;

        const float Every = 0.9f, Life = 2.6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.2f, 0.6f);
            if (env <= 0) return;
            Vector3 o = c.anchor + Vector3.up * 0.035f + c.camRight * 0.025f;
            int last = Mathf.FloorToInt(c.t / Every);
            for (int k = Mathf.Max(0, last - 4); k <= last; k++)
            {
                float a = (c.t - k * Every) / Life;
                if (a <= 0 || a >= 1) continue;
                float pop = OutBack(a * Life / 0.3f);
                float size = Mathf.Lerp(0.028f, 0.056f, a) * pop * (k % 3 == 1 ? 0.85f : 1f);
                float wob = Mathf.Sin(a * Tau * 1.1f + k * 1.7f);
                Vector3 p = o + Vector3.up * (0.16f * a) + c.camRight * (0.07f * a * a + 0.016f * wob);
                float tilt = -0.25f + 0.18f * wob;
                float alpha = Sat(a * 10f) * (1 - Smooth(0.65f, 1f, a)) * env;
                Letter(c, b, p, size, tilt, alpha);
            }
        }

        static void Letter(FxCtx c, FxBatch b, Vector3 p, float size, float tilt, float alpha)
        {
            float cs = Mathf.Cos(tilt), sn = Mathf.Sin(tilt);
            Vector3 R = c.camRight * cs + c.camUp * sn, U = -c.camRight * sn + c.camUp * cs;
            float h = size * 0.5f;
            // Z corners: top-left, top-right, bottom-left, bottom-right (slightly playful: top bar tilts up)
            Vector3 tl = p - R * h + U * (h * 0.95f), tr = p + R * h + U * (h * 1.08f);
            Vector3 bl = p - R * h - U * h, br = p + R * (h * 1.05f) - U * (h * 0.98f);
            Vector3 z = (c.camPos - p).normalized * 0.001f;   // fill sits just in front of its edge
            float edge = size * 0.5f, fill = size * 0.31f;
            Seg(b, tl, tr, edge, A(DanielFx.SleepEdge, alpha), Vector3.zero);
            Seg(b, tr, bl, edge, A(DanielFx.SleepEdge, alpha), Vector3.zero);
            Seg(b, bl, br, edge, A(DanielFx.SleepEdge, alpha), Vector3.zero);
            Seg(b, tl, tr, fill, A(DanielFx.SleepFill, alpha), z);
            Seg(b, tr, bl, fill, A(DanielFx.SleepFill, alpha), z);
            Seg(b, bl, br, fill, A(DanielFx.SleepFill, alpha), z);
        }

        static void Seg(FxBatch b, Vector3 a, Vector3 e, float w, Color col, Vector3 dz)
        {
            // extend each stroke a little past the corners so the joins close
            Vector3 d = (e - a) * 0.08f;
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            r.Add(a - d + dz, w, col);
            r.Add(Vector3.Lerp(a, e, 0.5f) + dz, w, col);
            r.Add(e + d + dz, w, col);
        }
    }

    // ------------------------------------------------------------------ S11: first light
    /// <summary>
    /// Stage tint to pink-gold dawn (multiply DanielFx.DawnTint) with lilac / pink / gold crayon sky bands behind the city
    /// wall (in front of night's bands, so dawn wins while both run), a sun rising slowly over the wall top, a rosy
    /// back-halo behind each actor and a few warm motes. Fades in 1.2 s, out 1.5 s.
    /// </summary>
    public sealed class DawnGlow : FxDef
    {
        public override string Id => "dawn_glow";
        public override float DefaultDur => 10f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.2f, 1.5f);
            StoryTint.Request(c.seed, DanielFx.DawnTint, env, DanielFx.DawnRim);
            if (env <= 0) return;
            DanielFx.SkyBand(b, 0.62f, 0.22f, DanielFx.DawnHigh, 0.70f * env, 0.010f, c.t, 0.006f);
            DanielFx.SkyBand(b, 0.46f, 0.22f, DanielFx.DawnMid, 0.78f * env, 0.012f, c.t, 0.006f);
            DanielFx.SkyBand(b, 0.31f, 0.20f, DanielFx.DawnLow, 0.85f * env, 0.008f, c.t, 0.006f);

            // the sun peeps over the wall and rises a little (the depth test hides the part behind the wall)
            float rise = Smooth(0f, Mathf.Max(1f, c.dur), c.t);
            var sun = new Vector3(-0.36f, Mathf.Lerp(0.25f, 0.33f, rise), RuthFx.SkyZ + 0.03f);
            float pulse = 0.94f + 0.06f * Mathf.Sin(c.t * 0.9f);
            b.Sprite(sun, 0.46f * pulse, A(DanielFx.DawnMid, 0.45f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(sun + Vector3.forward * 0.005f, 0.10f, A(DanielFx.DawnSun, env), DGFxPaint.Puff, 0, false);
            b.Sprite(sun + Vector3.forward * 0.01f, 0.22f * pulse, A(Sun, 0.30f * env), DGFxPaint.SoftDot, 0, true);
            // three soft sunbeams fanning up from the sun
            for (int i = 0; i < 3; i++)
            {
                float ang = Mathf.Lerp(0.55f, 2.2f, i / 2f);
                Vector3 d = new Vector3(Mathf.Cos(ang), Mathf.Sin(ang), 0);
                var r = b.Ribbon(DGFxPaint.Streak, true);
                float pul = 0.7f + 0.3f * Mathf.Sin(c.t * 0.7f + i * 2f);
                r.Add(sun + Vector3.forward * 0.004f + d * 0.05f, 0.05f, A(DanielFx.DawnLow, 0.30f * env * pul));
                r.Add(sun + Vector3.forward * 0.004f + d * 0.30f, 0.12f, A(DanielFx.DawnLow, 0f));
            }

            RuthFx.Halos(c, b, DanielFx.DawnMid, 0.26f * env);
            for (int i = 0; i < 14; i++)
            {
                float period = Mathf.Lerp(5f, 8f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                var p = new Vector3(Mathf.Lerp(-0.50f, 0.50f, FxRand.H(c.seed, i * 7 + cyc, 2)) + 0.04f * a,
                                    Mathf.Lerp(0.05f, 0.30f, FxRand.H(c.seed, i * 7 + cyc, 3)) + 0.03f * Mathf.Sin(Tau * a),
                                    Mathf.Lerp(-0.35f, 0.15f, FxRand.H(c.seed, i * 7 + cyc, 4)));
                b.Sprite(p, 0.011f, A(i % 2 == 0 ? DanielFx.DawnLow : DanielFx.DawnMid, Mathf.Sin(Mathf.PI * a) * env * 0.9f),
                         DGFxPaint.SoftDot, 0, true);
            }
        }
    }
}
