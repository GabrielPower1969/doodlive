// He Is Risen! (story pack `risen`, docs/risen/FX.md) effects. Same engine as the earlier packs: every effect is a pure
// function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered in
// FxLibrary after the earlier packs (an existing id is never replaced), through the manifest `fx.class` = RisenFx.
// New: tomb_glow, butterflies (CONTRACT §8). Reused unchanged: angel_light, dawn_glow (Daniel), dust_burst, golden_rays
// (D&G), sunset_glow, lamp_flame, heart_glow (Ruth), run_dust (Prodigal), tension_dim (Esther). No aliases.
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no flash, no strobe; nothing bright or opaque stays over a face.
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>He Is Risen! registry, palette and garden layout (docs/risen/CONTRACT.md §6, §8; DESIGN.md §3).</summary>
    public static class RisenFx
    {
        internal static FxDef[] Defs => new FxDef[] { new TombGlow(), new Butterflies() };

        // the light inside the tomb: warm white with a gold edge (reads on the dark door #4A3440 and the rock #C9946A)
        internal static readonly Color WarmWhite = new Color32(0xFF, 0xF4, 0xD6, 255), Gold = new Color32(0xFF, 0xD2, 0x7A, 255),
                                       Amber = new Color32(0xF2, 0xB0, 0x52, 255);

        // butterflies in the flower colours (DESIGN §3: lilies #FFFFFF, poppies #D9483A, daisies #F2C94C) and one blue; the
        // atlas Pebble cell gives every wing a dark ink outline, so white and yellow wings read on lilies, grass and path (F4)
        internal static readonly Color[] Wing =
        {
            new Color32(0xFF, 0xFD, 0xF6, 255), new Color32(0xD9, 0x48, 0x3A, 255), new Color32(0xF2, 0xC9, 0x4C, 255),
            new Color32(0x5B, 0x8F, 0xD9, 255),
        };
        internal static readonly Color[] Spot =   // one small dot on each upper wing
        {
            new Color32(0xF2, 0xC9, 0x4C, 255), new Color32(0xFF, 0xF1, 0xD6, 255), new Color32(0xE8, 0x84, 0x3A, 255),
            new Color32(0xFF, 0xFF, 0xFF, 255),
        };
        internal static readonly Color Body = new Color32(0x3A, 0x2A, 0x22, 255);

        // The flower beds (CONTRACT §6 `flowers`): the front-left corner and the hill foot. The `flowers` node is two beds, so
        // its pivot says little: when the anchor lies on the beds' footprint (or at the set origin, a merged node's pivot)
        // the butterflies use both beds; any other node gets one bed centred on it.
        internal static readonly Vector4 BedFront = new Vector4(-0.60f, -0.30f, 0.04f, 0.20f);   // x0, x1, z0, z1
        internal static readonly Vector4 BedHill = new Vector4(-0.60f, -0.46f, -0.29f, -0.20f);
        internal static bool OnBeds(Vector3 a) =>
            (a.x > -0.64f && a.x < -0.26f && a.z > -0.33f && a.z < 0.24f && Mathf.Abs(a.y) < 0.06f)
            || (Mathf.Abs(a.x) < 0.01f && Mathf.Abs(a.z) < 0.01f && Mathf.Abs(a.y) < 0.01f);

        internal static float ScreenAngle(FxCtx c, Vector3 v) => Mathf.Atan2(Vector3.Dot(v, c.camUp), Vector3.Dot(v, c.camRight));
    }

    // ------------------------------------------------------------------ S04 / S07: light inside the open tomb
    /// <summary>
    /// A soft warm-white light from inside the open tomb door (node = the door centre, CONTRACT §6: (−0.33, 0.15, −0.30),
    /// opening 0.13 wide, 0.34 high, facing +Z): a glow filling the opening (brightest at the upper middle, so the folded
    /// cloths low on the ledge keep their shape), a faint warm halo on the rock round the door, a gentle pool on the ground
    /// in front, and slow golden motes drifting out and up. Breathes slowly (±8 %, 0.22 Hz); no flash. Fades in 0.8 s,
    /// out 0.8 s. Everything sits at or in front of the door plane and is depth-tested, so people peeking in stay in front.
    /// </summary>
    public sealed class TombGlow : FxDef
    {
        public override string Id => "tomb_glow";
        public override float DefaultDur => 9f;
        public override bool Follow => false;

        const float HalfW = 0.065f, HalfH = 0.17f;
        const int Motes = 10;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 0.8f);
            if (env <= 0) return;
            env = env * env * (3 - 2 * env);
            Vector3 d = c.start;                                    // the door centre
            float bottom = Mathf.Max(0f, d.y - HalfH);
            float zf = d.z + 0.003f;                                 // just in front of the door plane
            float breathe = 0.92f + 0.08f * Mathf.Sin(c.t * Tau * 0.22f);

            // the pool of light on the ground in front of the door (alpha so it reads warm on the reddish rock floor, then a
            // low additive heart)
            Vector3 pool = new Vector3(d.x, 0.003f, d.z + 0.055f);
            b.Sprite(pool, 0.22f, 0.12f, A(RisenFx.Gold, 0.38f * env * breathe), DGFxPaint.SoftDot, 0f, false, FxFace.Ground);
            b.Sprite(pool + Vector3.up * 0.001f, 0.14f, 0.07f, A(RisenFx.WarmWhite, 0.30f * env), DGFxPaint.SoftDot, 0f, true, FxFace.Ground);

            // a faint warm halo on the rock face round the opening
            Vector3 mid = new Vector3(d.x, bottom + HalfH, zf);
            b.Sprite(mid, 0.26f * breathe, 0.44f * breathe, A(RisenFx.Amber, 0.16f * env), DGFxPaint.SoftDot, 0f, true, FxFace.Camera);

            // the light filling the opening: a wide soft layer, then a brighter heart at the upper middle (the cloths lie low)
            Vector3 upper = new Vector3(d.x, bottom + HalfH * 1.15f, zf + 0.001f);
            b.Sprite(mid + Vector3.forward * 0.001f, 2.1f * HalfW, 1.9f * HalfH, A(RisenFx.Gold, 0.30f * env * breathe), DGFxPaint.SoftDot, 0f, true, FxFace.Camera);
            b.Sprite(upper, 1.4f * HalfW, 1.3f * HalfH, A(RisenFx.WarmWhite, 0.34f * env * breathe), DGFxPaint.SoftDot, 0f, true, FxFace.Camera);
            // the light along the door's floor, spilling out over the threshold
            b.Sprite(new Vector3(d.x, bottom + 0.012f, zf + 0.004f), 2.2f * HalfW, 0.04f, A(RisenFx.WarmWhite, 0.26f * env), DGFxPaint.SoftDot, 0f, true, FxFace.Camera);

            // slow golden motes drifting out of the door and up, swaying; every third twinkles slowly
            for (int i = 0; i < Motes; i++)
            {
                float period = Mathf.Lerp(3.2f, 4.6f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                int cyc = Mathf.FloorToInt(ph);
                float a = ph - cyc;
                int k = i * 31 + cyc;
                Vector3 s = new Vector3(d.x + HalfW * 0.8f * FxRand.Signed(c.seed, k, 2), bottom + Mathf.Lerp(0.03f, 0.26f, FxRand.H(c.seed, k, 3)),
                                        d.z - 0.01f);
                Vector3 p = s + new Vector3(0.015f * Mathf.Sin(a * 5f + i), 0.07f * a, 0.08f * OutCubic(a));
                float life = Mathf.Sin(Mathf.PI * a) * Sat(c.t / 0.6f);
                bool tw = i % 3 == 0;
                b.Sprite(p, tw ? 0.020f : 0.010f, A(i % 2 == 0 ? RisenFx.WarmWhite : RisenFx.Gold, 0.85f * life * env),
                         tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, tw ? c.t * 0.5f + i : 0f, true);
            }
        }
    }

    // ------------------------------------------------------------------ S09 / S12: butterflies rise from the flowers
    /// <summary>
    /// Eight butterflies (white, red, yellow like the flowers, and one blue) rise one after another (every ≈ 0.3 s) from
    /// blooms in the beds, then flutter in slow figure-eight loops 0.05-0.26 above the ground (one goes up to 0.30),
    /// staying over and just beside their bed. Wings beat about 3.5 times a second with short glides (wings held open);
    /// the beat changes the wing width only, never the brightness (no strobe). Three of them glide down and settle on a
    /// bloom for 2-3 s, wings opening and closing slowly; if that would run past the end they stay settled. All fade out
    /// over the last 0.8 s. Wingspan ≈ 0.04; every wing has a dark ink outline so the white and yellow ones read on
    /// lilies, grass and the pale path (F4). Joyful, never a swarm.
    /// </summary>
    public sealed class Butterflies : FxDef
    {
        public override string Id => "butterflies";
        public override float DefaultDur => 8f;
        public override bool Follow => false;

        const int N = 8;
        static readonly int[] ColourOf = { 0, 1, 2, 3, 0, 1, 2, 0 };     // white, red, yellow, blue, ...
        static bool Settler(int i) => i == 1 || i == 4 || i == 6;

        static Vector4 BedOf(FxCtx c, int i)
        {
            if (!RisenFx.OnBeds(c.start))
                return new Vector4(c.start.x - 0.12f, c.start.x + 0.12f, c.start.z - 0.07f, c.start.z + 0.07f);
            return i < 6 ? RisenFx.BedFront : RisenFx.BedHill;
        }

        static Vector3 InBed(FxCtx c, Vector4 bed, int i, int k, float inset)
        {
            // biased toward the bed's right (garden-side) end, where the people stand, so a two-shot there still sees them
            float x = Mathf.Lerp(bed.y - inset, bed.x + inset, Mathf.Pow(FxRand.H(c.seed, i, k), 1.6f));
            float z = Mathf.Lerp(bed.z + inset * 0.6f, bed.w - inset * 0.6f, FxRand.H(c.seed, i, k + 1));
            return new Vector3(x, 0f, z);
        }

        /// <summary>The free-flight path of butterfly i at time t (stage-local).</summary>
        static Vector3 Flight(FxCtx c, int i, Vector3 home, float t)
        {
            float ph = Tau * FxRand.H(c.seed, i, 10), w = Mathf.Lerp(0.9f, 1.3f, FxRand.H(c.seed, i, 11));
            float rx = Mathf.Lerp(0.035f, 0.05f, FxRand.H(c.seed, i, 12)), rz = Mathf.Lerp(0.02f, 0.03f, FxRand.H(c.seed, i, 13));
            float cruise = i == 2 ? 0.24f : Mathf.Lerp(0.08f, 0.19f, FxRand.H(c.seed, i, 14));
            Vector3 centre = home + new Vector3(0.025f * Mathf.Sin(0.31f * t + ph), 0f, 0.015f * Mathf.Cos(0.27f * t + ph));
            float y = cruise + 0.035f * Mathf.Sin(0.8f * t + 1.7f * ph);
            return centre + new Vector3(rx * Mathf.Sin(w * t + ph), y, rz * Mathf.Sin(2f * w * t + ph));
        }

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.05f, 0.8f);
            if (env <= 0) return;
            for (int i = 0; i < N; i++)
            {
                float t0 = 0.1f + 0.30f * i + 0.12f * FxRand.H(c.seed, i, 0);
                float age = c.t - t0;
                if (age < 0f) continue;
                Vector4 bed = BedOf(c, i);
                Vector3 home = InBed(c, bed, i, 1, 0.03f);
                Vector3 bloom = InBed(c, bed, i, 3, 0.02f) + Vector3.up * 0.035f;      // where it rises from
                Vector3 seat = InBed(c, bed, i, 5, 0.02f) + Vector3.up * 0.04f;        // where a settler lands (bloom top)

                // rise out of the bloom onto the flight path
                float rise = OutCubic(age / 0.9f);
                Vector3 p = Vector3.Lerp(bloom, Flight(c, i, home, c.t), rise);
                Vector3 pn = Vector3.Lerp(bloom, Flight(c, i, home, c.t + 0.05f), OutCubic((age + 0.05f) / 0.9f));

                // settle on a bloom for a while (glide down 0.8 s, take off 0.8 s), or stay if the end is near
                float sit = 0f;
                if (Settler(i))
                {
                    float ts = Mathf.Max(t0 + 1.6f, c.dur * Mathf.Lerp(0.35f, 0.5f, FxRand.H(c.seed, i, 7)));
                    float te = ts + Mathf.Lerp(2.2f, 3.2f, FxRand.H(c.seed, i, 8));
                    bool stay = te > c.dur - 2.0f;
                    sit = Smooth(ts, ts + 0.8f, c.t) * (stay ? 1f : 1f - Smooth(te, te + 0.8f, c.t));
                    p = Vector3.Lerp(p, seat, sit);
                    pn = Vector3.Lerp(pn, seat, sit);
                }

                // wings: a quick beat with short glides in flight; slow open-close when settled
                float beat = Mathf.Lerp(3.2f, 3.9f, FxRand.H(c.seed, i, 15));
                float flap = 0.5f + 0.5f * Mathf.Cos(c.t * Tau * beat + i * 1.9f);
                float glide = Smooth(0.55f, 0.85f, Mathf.Sin(0.7f * c.t + 2.3f * i));
                float open = Mathf.Lerp(flap, 1f, glide);
                float rest = 0.5f + 0.5f * Mathf.Sin(c.t * 2.0f + i);
                open = Mathf.Lerp(open, Mathf.Lerp(0.15f, 1f, rest), sit);
                p += Vector3.up * (0.004f * (open - 0.5f) * (1f - sit));                // a little bob with each beat

                float vx = Vector3.Dot(pn - p, c.camRight) / 0.05f;
                float tilt = Mathf.Clamp(-vx * 2.5f, -0.35f, 0.35f) * (1f - sit);
                float size = Mathf.Lerp(0.6f, 1f, OutCubic(age / 0.3f)) * Mathf.Lerp(0.92f, 1.08f, FxRand.H(c.seed, i, 16));
                float alpha = env * Sat(age / 0.2f);
                Draw(c, b, p, tilt, open, 0.040f * size, ColourOf[i], alpha);
            }
        }

        /// <summary>One butterfly in the screen plane, built from outlined ellipses (the Pebble cell: white fill, dark ink
        /// outline, tinted): lower wings, upper wings with a spot, a dark body and two antenna tips. open = 0 (wings
        /// edge-on) .. 1 (fully open); the beat only narrows the wings.</summary>
        static void Draw(FxCtx c, FxBatch b, Vector3 p, float tilt, float open, float L, int ci, float alpha)
        {
            if (alpha <= 0.004f) return;
            Vector3 B = c.camUp * Mathf.Cos(tilt) - c.camRight * Mathf.Sin(tilt);   // body axis (head up)
            Vector3 S = c.camRight * Mathf.Cos(tilt) + c.camUp * Mathf.Sin(tilt);   // across the body
            float ow = Mathf.Lerp(0.16f, 1f, open);
            Color wing = A(RisenFx.Wing[ci], alpha), spot = A(RisenFx.Spot[ci], alpha);
            for (int s = -1; s <= 1; s += 2)
            {
                Vector3 dl = (S * s * Mathf.Cos(0.6f) - B * Mathf.Sin(0.6f));            // lower wing: out and down
                b.Sprite(p - B * (0.12f * L) + S * (s * 0.20f * L * ow), 0.46f * L * ow + 0.06f * L, 0.34f * L, wing,
                         DGFxPaint.Pebble, RisenFx.ScreenAngle(c, dl), false, FxFace.Camera);
            }
            for (int s = -1; s <= 1; s += 2)
            {
                Vector3 du = (S * s * Mathf.Cos(0.45f) + B * Mathf.Sin(0.45f));          // upper wing: out and up
                Vector3 cu = p + B * (0.10f * L) + S * (s * 0.27f * L * ow);
                b.Sprite(cu, 0.60f * L * ow + 0.07f * L, 0.46f * L, wing, DGFxPaint.Pebble, RisenFx.ScreenAngle(c, du), false, FxFace.Camera);
                if (ow > 0.5f)
                    b.Sprite(cu + du * (0.10f * L * ow) + B * (0.03f * L), 0.13f * L, A(spot, Sat((ow - 0.5f) * 4f)), DGFxPaint.ConfettiDot, 0f);
            }
            b.Sprite(p, 0.11f * L, 0.56f * L, A(RisenFx.Body, alpha), DGFxPaint.Pebble, RisenFx.ScreenAngle(c, B), false, FxFace.Camera);
            for (int s = -1; s <= 1; s += 2)
                b.Sprite(p + B * (0.40f * L) + S * (s * 0.09f * L), 0.06f * L, A(RisenFx.Body, alpha), DGFxPaint.SoftDot, 0f);
        }
    }
}
