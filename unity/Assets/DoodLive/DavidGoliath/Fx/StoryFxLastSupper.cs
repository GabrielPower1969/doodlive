// The King Who Serves (story pack `lastsupper`, docs/lastsupper/FX.md) effects. Same engine as the earlier packs: every
// effect is a pure function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur)
// and registered in FxLibrary after the earlier packs (an existing id is never replaced), through the manifest
// `fx.class` = LastSupperFx.
// New: palm_toss, doves_fly, water_pour (CONTRACT §8). Reused unchanged: golden_rays, sparkle, heart_glow, sunset_glow,
// night, dust_road, lamp_flame, coins_spray, music_notes. No aliases.
// The atlas has no leaf, bird or drop cell: fronds, doves and feathers are built from ribbons and dots (Lens / Stroke).
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no flash, no strobe; nothing bright or opaque stays over a face.
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>The King Who Serves registry, palette, road layout and shared drawing (docs/lastsupper/CONTRACT.md §6, §8).</summary>
    public static class LastSupperFx
    {
        internal static FxDef[] Defs => new FxDef[] { new PalmToss(), new DovesFly(), new WaterPour() };

        // palm fronds and the coats on the road (DESIGN §3: palm #5E9A48, coats red / blue / yellow)
        internal static readonly Color Palm = new Color32(0x5E, 0x9A, 0x48, 255), PalmLight = new Color32(0x9C, 0xC8, 0x6A, 255),
                                       PalmEdge = new Color32(0x2F, 0x58, 0x26, 255);
        internal static readonly Color[] Cloth =
        {
            new Color32(0xC2, 0x45, 0x3A, 255), new Color32(0x4E, 0x7F, 0xB8, 255), new Color32(0xE8, 0xC0, 0x4A, 255),
        };
        // doves: white with a cool grey pencil edge, so they read on the cream court paving (#EADFC4) and white temple (F4)
        internal static readonly Color DoveWhite = new Color32(0xFF, 0xFE, 0xFA, 255), DoveShade = new Color32(0xD9, 0xDE, 0xE8, 255),
                                       DoveEdge = new Color32(0x5E, 0x68, 0x7A, 255), DoveBeak = new Color32(0xE8, 0x92, 0x6A, 255),
                                       DoveEye = new Color32(0x2B, 0x21, 0x18, 255);
        // clear water: a mid blue body and a pale highlight that both read on amber lamp light and terracotta
        internal static readonly Color Water = new Color32(0x5E, 0xAE, 0xE8, 255), WaterLight = new Color32(0xD6, 0xF0, 0xFF, 255),
                                       WaterDeep = new Color32(0x2F, 0x7C, 0xC4, 255);

        // The straight stretch of `road` where `palmsRoad` lies (CONTRACT §6: x 0.08..0.56, z 0.05..0.16). The road node is
        // long and bent, so its pivot says little; when the anchor lies anywhere on the road's footprint the toss uses this
        // stretch. Any other node: the stretch is centred on the node.
        internal static readonly Vector3 RoadCentre = new Vector3(0.34f, 0f, 0.105f);
        internal const float RoadHalf = 0.21f;
        internal static Vector3 RoadOr(Vector3 a) =>
            a.x > -0.24f && a.x < 0.64f && a.z > -0.16f && a.z < 0.24f && Mathf.Abs(a.y) < 0.05f
                ? new Vector3(RoadCentre.x, a.y, RoadCentre.z) : a;

        /// <summary>A crayon stroke that stays solid to its end (the ribbon cell fades over its last 40 %: the fade is pushed
        /// into a short tail past p1).</summary>
        internal static void Stroke(FxBatch b, Vector3 p0, Vector3 p1, float w0, float w1, Color col, bool add = false)
        {
            var r = b.Ribbon(DGFxPaint.Ribbon, add);
            Vector3 d = p1 - p0;
            for (int k = 0; k <= 3; k++) r.Add(p0 + d * (k / 3f), Mathf.Lerp(w0, w1, k / 3f), col);
            r.Add(p1 + d * 0.05f, w1, col);
            r.Add(p1 + d * 0.10f, w1 * 0.8f, col);
        }

        /// <summary>A pointed leaf / wing / feather shape centred on p along D (bend sideways along N): a darker edge layer,
        /// then the fill. width = the widest point.</summary>
        internal static void Lens(FxBatch b, Vector3 p, Vector3 D, Vector3 N, float len, float width, float bend,
                                  Color fill, Color edge, float alpha, float blunt = 0.06f)
        {
            if (alpha <= 0.004f) return;
            for (int layer = 0; layer < 2; layer++)
            {
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                Color col = layer == 0 ? A(edge, 0.9f * alpha) : A(fill, alpha);
                float grow = layer == 0 ? 1.25f : 1f, pad = layer == 0 ? 0.004f : 0f;
                const int pts = 7;
                Vector3 last = p;
                for (int k = 0; k < pts; k++)
                {
                    float f = k / (float)(pts - 1);
                    float prof = Mathf.Pow(Mathf.Sin(Mathf.PI * (blunt + (0.92f - blunt) * Mathf.Pow(f, 0.8f))), 0.65f);
                    last = p + D * (len * (f - 0.5f) * (layer == 0 ? 1.06f : 1f)) + N * (bend * len * 4f * f * (1 - f));
                    r.Add(last, width * prof * grow + pad, col);
                }
                for (int k = 1; k <= 4; k++) r.Add(last + D * (len * 0.012f * k), 0.003f, col);   // the cell's fade lives here
            }
        }

        /// <summary>One palm frond centred on p: a green blade, a pale rib with a bare stem, and four leaflets.</summary>
        internal static void Frond(FxBatch b, Vector3 p, Vector3 D, Vector3 N, float len, float alpha)
        {
            if (alpha <= 0.004f) return;
            Lens(b, p, D, N, len, len * 0.24f, 0.05f, Palm, PalmEdge, alpha);
            for (int s = -1; s <= 1; s += 2)
                for (int j = 0; j < 2; j++)
                {
                    float f = 0.36f + 0.26f * j;
                    Vector3 root = p + D * (len * (f - 0.5f));
                    Vector3 tip = root + N * (s * len * 0.20f) + D * (len * 0.16f);
                    Stroke(b, root, tip, len * 0.09f, len * 0.04f, A(Color.Lerp(Palm, PalmEdge, 0.35f), alpha));
                }
            Stroke(b, p - D * (len * 0.66f), p + D * (len * 0.38f), len * 0.045f, len * 0.025f, A(PalmLight, alpha));
        }

        /// <summary>A small white feather centred on p in the screen plane (ang from camRight).</summary>
        internal static void Feather(FxCtx c, FxBatch b, Vector3 p, float len, float ang, float alpha)
        {
            if (alpha <= 0.004f) return;
            Vector3 D = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang), N = -c.camRight * Mathf.Sin(ang) + c.camUp * Mathf.Cos(ang);
            Lens(b, p, D, N, len, len * 0.40f, 0.10f, DoveWhite, Color.Lerp(DoveEdge, DoveShade, 0.45f), alpha * 0.95f);
            Stroke(b, p - D * (len * 0.62f), p + D * (len * 0.32f), len * 0.07f, len * 0.04f, A(DoveShade, 0.9f * alpha));
        }
    }

    // ------------------------------------------------------------------ S02: the crowd tosses palms on the road
    /// <summary>
    /// Palm fronds (and now and then a red, blue or yellow scrap of cloth) tossed from the crowd at the road's back edge (and
    /// the two children at the right front corner) over the road: about four a second, spread along the road's straight
    /// stretch. Each rises fast, tumbles, drifts down slowly with a little sway and lands flat on the road, lies there for
    /// 1.2 s and fades (the `palmsRoad` prop is the lasting layer). Nothing starts that would still be in the air at the
    /// end. Fades in 0.2 s, out 0.6 s.
    /// </summary>
    public sealed class PalmToss : FxDef
    {
        public override string Id => "palm_toss";
        public override float DefaultDur => 8f;
        public override bool Follow => false;

        const float Every = 0.25f, FlyMin = 1.1f, FlyMax = 1.5f, Lie = 1.2f, Fade = 0.6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.2f, 0.6f);
            if (env <= 0) return;
            Vector3 C = LastSupperFx.RoadOr(c.start);
            float half = LastSupperFx.RoadHalf;
            int last = Mathf.FloorToInt(c.t / Every);
            int back = Mathf.CeilToInt((FlyMax + Lie + Fade) / Every) + 1;
            for (int k = Mathf.Max(0, last - back); k <= last; k++)
            {
                float t0 = k * Every + 0.6f * Every * FxRand.H(c.seed, k, 0);
                float fly = Mathf.Lerp(FlyMin, FlyMax, FxRand.H(c.seed, k, 1));
                if (t0 + fly > c.dur - 0.1f) continue;                        // never cut off mid-air
                float age = c.t - t0;
                if (age < 0f || age > fly + Lie + Fade) continue;

                bool kid = FxRand.H(c.seed, k, 2) < 0.22f;                     // the two children at the right front corner
                float xs = kid ? Mathf.Lerp(0.70f, 1.0f, FxRand.H(c.seed, k, 3)) : FxRand.Signed(c.seed, k, 3);
                Vector3 from = C + new Vector3(xs * half, kid ? 0.11f : 0.18f, kid ? 0.085f : -0.115f);
                Vector3 to = C + new Vector3(xs * half + 0.05f * FxRand.Signed(c.seed, k, 4) - (kid ? 0.04f : 0f), 0.004f,
                                             0.045f * FxRand.Signed(c.seed, k, 5));
                float apex = Mathf.Max(from.y, to.y) + Mathf.Lerp(0.05f, 0.10f, FxRand.H(c.seed, k, 6));
                bool cloth = FxRand.H(c.seed, k, 7) < 0.18f;

                float u = Mathf.Min(age, fly), ta = 0.32f * fly;
                float hs = 1f - (1f - u / fly) * (1f - u / fly);               // air drag: fast out, slow in
                Vector3 p = Vector3.Lerp(from, to, hs);
                float fall = 0f;
                if (u < ta) { float r = 1f - u / ta; p.y = from.y + (apex - from.y) * (1f - r * r); }
                else { fall = (u - ta) / (fly - ta); p.y = apex + (to.y - apex) * Mathf.Pow(fall, 1.5f); }
                bool landed = age >= fly;
                if (!landed) p += c.camRight * (0.016f * Mathf.Sin(age * 5.5f + k) * Sat(fall * 3f));

                float alpha = env * Sat(age * 10f) * (landed ? 1f - Sat((age - fly - Lie) / Fade) : 1f);
                if (alpha <= 0.004f) continue;
                float rest = Tau * FxRand.H(c.seed, k, 8);                     // heading when it lies on the road
                float spin = FxRand.Signed(c.seed, k, 9) < 0 ? -1f : 1f;
                float ang = landed ? rest
                          : rest + spin * (u < ta ? 3.5f * u : 3.5f * ta) + (u >= ta ? 0.55f * Mathf.Sin(age * 5.5f + k) * Sat(fall * 3f) : 0f);

                if (cloth)
                {
                    Color col = LastSupperFx.Cloth[(int)(FxRand.H(c.seed, k, 10) * 2.999f)];
                    float flutter = landed ? 1f : 0.65f + 0.35f * Mathf.Abs(Mathf.Sin(age * 6f + k));   // the scrap turns in the air
                    if (landed)
                        b.Sprite(new Vector3(p.x, to.y + 0.002f, p.z), 0.040f, 0.026f, A(col, alpha), DGFxPaint.ConfettiRect, rest, false, FxFace.Ground);
                    else
                        b.Sprite(p, 0.040f, 0.026f * flutter, A(col, alpha), DGFxPaint.ConfettiRect, ang, false, FxFace.Camera);
                    continue;
                }

                float len = Mathf.Lerp(0.070f, 0.090f, FxRand.H(c.seed, k, 11));
                Vector3 D, N;
                if (landed) { D = Flat(ang, 1f); N = Flat(ang + 1.5708f, 1f); p.y = to.y + 0.003f; }
                else
                {
                    D = c.camRight * Mathf.Cos(ang) + c.camUp * Mathf.Sin(ang);
                    N = -c.camRight * Mathf.Sin(ang) + c.camUp * Mathf.Cos(ang);
                }
                LastSupperFx.Frond(b, p, D, N, len, alpha);
            }
        }
    }

    // ------------------------------------------------------------------ S05: the doves fly free
    /// <summary>
    /// Seven white doves burst up out of the node (the open cages), one after another over 0.4 s: each pops out small,
    /// flaps (about 2.4 beats a second, no strobe), spirals up (alternate doves turn opposite ways) and drifts a little
    /// back and sideways, leaving the top of the frame by about 2.5 s. Six small feathers puff up from the cages and drift
    /// down, swaying, fading out by 2.9 s. Doves are white with a cool grey pencil edge and a shaded far wing, so they
    /// read on the cream court. Fades out over the last 0.35 s.
    /// </summary>
    public sealed class DovesFly : FxDef
    {
        public override string Id => "doves_fly";
        public override float DefaultDur => 3f;
        public override bool Follow => false;

        const int Doves = 7, Feathers = 6;

        static Vector3 Path(FxCtx c, int i, Vector3 o, float age)
        {
            float a0 = Tau * FxRand.H(c.seed, i, 1);
            float dir = i % 2 == 0 ? 1f : -1f;
            float a = a0 + dir * (2.0f * age + 0.5f * age * age);
            float r = 0.012f + 0.13f * Sat(age / 1.8f);
            float h = 0.16f * age + 0.065f * age * age;               // ~0.22 at 1 s, ~0.8 at 2.5 s
            Vector3 s0 = o + new Vector3(0.065f * FxRand.Signed(c.seed, i, 2), 0.025f + 0.03f * FxRand.H(c.seed, i, 3),
                                         0.025f * FxRand.Signed(c.seed, i, 4));
            Vector3 drift = new Vector3(0.11f * FxRand.Signed(c.seed, i, 5), 0f, -0.05f) * age;   // the flock opens out
            return s0 + Flat(a, r) - Flat(a0, 0.012f) + Vector3.up * h + drift;
        }

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.05f, 0.35f);
            if (env <= 0) return;
            Vector3 o = c.start;

            // feathers first (behind the doves): a small puff up out of the cages, then a slow swaying fall
            for (int j = 0; j < Feathers; j++)
            {
                float t0 = 0.15f + 0.55f * FxRand.H(c.seed, j, 20);
                float age = c.t - t0;
                const float life = 2.1f;
                if (age < 0f || age > life) continue;
                Vector3 s = o + new Vector3(0.06f * FxRand.Signed(c.seed, j, 21), 0.06f + 0.05f * FxRand.H(c.seed, j, 22),
                                            0.04f * FxRand.Signed(c.seed, j, 23));
                float sway = Mathf.Sin(age * 3.0f + j * 1.7f);
                Vector3 p = s + Vector3.up * (0.05f * OutCubic(age / 0.3f) - 0.07f * Mathf.Max(0f, age - 0.3f))
                              + c.camRight * (0.022f * sway + 0.02f * FxRand.Signed(c.seed, j, 24) * age);
                float alpha = env * Sat(age * 8f) * Sat((life - age) / 0.6f);
                LastSupperFx.Feather(c, b, p, Mathf.Lerp(0.020f, 0.026f, FxRand.H(c.seed, j, 25)), -1.2f + 0.7f * sway, alpha);
            }

            for (int i = 0; i < Doves; i++)
            {
                float t0 = 0.05f + 0.40f * (i + 0.5f * FxRand.H(c.seed, i, 0)) / Doves;
                float age = c.t - t0;
                if (age < 0f) continue;
                Vector3 p = Path(c, i, o, age);
                Vector3 vel = (Path(c, i, o, age + 0.03f) - p) / 0.03f;
                float vx = Vector3.Dot(vel, c.camRight), vy = Vector3.Dot(vel, c.camUp);
                float facing = vx >= 0f ? 1f : -1f;
                float climb = Mathf.Clamp(Mathf.Atan2(vy, Mathf.Abs(vx) + 0.15f), 0.1f, 0.5f);
                float sc = Mathf.Lerp(0.55f, 1f, OutCubic(age / 0.3f)) * Mathf.Lerp(0.92f, 1.08f, FxRand.H(c.seed, i, 6));
                float flap = Mathf.Sin(age * 15f + i * 1.3f);
                Dove(c, b, p, facing, climb, flap, 0.040f * sc, env * Sat(age / 0.08f));
            }
        }

        /// <summary>One dove in the screen plane, built from outlined ellipses (ConfettiDot = a disc with a soft grey
        /// outline, tinted white): far wing (shaded), tail, body, head with eye and beak, near wing. Side view: the wings
        /// beat between above the back and below the belly and are foreshortened when level.</summary>
        static void Dove(FxCtx c, FxBatch b, Vector3 p, float facing, float climb, float flap, float L, float alpha)
        {
            if (alpha <= 0.004f) return;
            Vector3 R = c.camRight * facing, U = c.camUp;
            Vector3 D = R * Mathf.Cos(climb) + U * Mathf.Sin(climb);          // nose direction
            Vector3 N = -R * Mathf.Sin(climb) + U * Mathf.Cos(climb);         // the dove's "up"
            float rot = ScreenAngle(c, D);
            Vector3 shoulder = p + N * (0.12f * L) + D * (0.08f * L);
            float th = 0.35f + 0.85f * flap;                                   // -0.5 (down) .. 1.2 (up) rad

            void Wing(float a, float span, Color fill)
            {
                Vector3 w = (N * Mathf.Sin(a) - D * 0.45f).normalized;
                float len = span * (0.55f + 0.45f * Mathf.Abs(Mathf.Sin(a)));
                b.Sprite(shoulder + w * (0.45f * len), len, 0.36f * L, A(fill, alpha), DGFxPaint.ConfettiDot, ScreenAngle(c, w), false, FxFace.Camera);
            }
            Wing(th + 0.35f, 0.85f * L, LastSupperFx.DoveShade);               // far wing, a beat behind and shaded
            b.Sprite(p - D * (0.50f * L) - N * (0.04f * L), 0.50f * L, 0.24f * L, A(LastSupperFx.DoveWhite, alpha),
                     DGFxPaint.ConfettiDot, rot - 0.15f * facing, false, FxFace.Camera);   // tail
            b.Sprite(p, 1.0f * L, 0.56f * L, A(LastSupperFx.DoveWhite, alpha), DGFxPaint.ConfettiDot, rot, false, FxFace.Camera);
            Vector3 head = p + D * (0.46f * L) + N * (0.20f * L);
            b.Sprite(head + D * (0.21f * L) - N * (0.03f * L), 0.17f * L, 0.09f * L, A(LastSupperFx.DoveBeak, alpha), DGFxPaint.SoftDot, rot, false, FxFace.Camera);
            b.Sprite(head, 0.40f * L, A(LastSupperFx.DoveWhite, alpha), DGFxPaint.ConfettiDot, 0f);
            b.Sprite(head + D * (0.07f * L) + N * (0.04f * L), 0.08f * L, A(LastSupperFx.DoveEye, alpha), DGFxPaint.SoftDot, 0f);
            Wing(th, 0.95f * L, LastSupperFx.DoveWhite);                       // near wing over the body
        }

        static float ScreenAngle(FxCtx c, Vector3 v) => Mathf.Atan2(Vector3.Dot(v, c.camUp), Vector3.Dot(v, c.camRight));
    }

    // ------------------------------------------------------------------ S07 / S12: water poured into the basin
    /// <summary>
    /// A thin clear-blue stream from 0.09 above the node down into it (the node is the basin, or the jug: its mouth is the
    /// node + 0.012). The stream's front falls to the node in 0.15 s at the start and its tail falls after it in the last
    /// 0.22 s; its top fades in softly (no hard start in the air). Where it lands: three small ripple rings flat on the
    /// water (radius up to 0.034, inside a 0.08 basin), a soft pale glint and six drops hopping out and back. Follows the
    /// node (the jug moves with the hand). Fades in 0.05 s, out 0.2 s. No flash.
    /// </summary>
    public sealed class WaterPour : FxDef
    {
        public override string Id => "water_pour";
        public override float DefaultDur => 1.8f;
        public override bool Follow => true;

        const float H = 0.09f, Lip = 0.012f, Head = 0.15f, Tail = 0.22f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.05f, 0.2f);
            if (env <= 0) return;
            Vector3 bottom = c.anchor + Vector3.up * Lip, top = bottom + Vector3.up * H;

            // the stream: front falls in, tail falls after it (gravity, so both ease in)
            float hu = Sat(c.t / Head), tu = Sat((c.t - (c.dur - Tail)) / Tail);
            Vector3 a = Vector3.Lerp(top, bottom, tu * tu), z = Vector3.Lerp(top, bottom, hu * hu);
            if ((a - z).sqrMagnitude > 1e-8f)
            {
                var body = b.Ribbon(DGFxPaint.Ribbon, false);
                var hi = b.Ribbon(DGFxPaint.Ribbon, false);
                for (int k = 0; k <= 6; k++)
                {
                    float f = k / 6f;
                    Vector3 q = Vector3.Lerp(a, z, f);
                    float down = (top.y - q.y) / H;                            // 0 at the top .. 1 at the node
                    float src = tu > 0f ? 1f : Sat(down / 0.25f);              // soft top while still pouring
                    q += c.camRight * (0.0012f * Mathf.Sin(c.t * 21f + down * 9f) * down);
                    float w = Mathf.Lerp(0.012f, 0.008f, down);                 // falling water thins
                    body.Add(q, w, A(LastSupperFx.Water, 0.85f * env * src));
                    hi.Add(q - c.camRight * (0.0018f), w * 0.35f, A(LastSupperFx.WaterLight, 0.9f * env * src));
                }
                Vector3 d = (z - a).normalized * 0.004f;                       // push the cell's end fade below the surface
                body.Add(z + d, 0.007f, A(LastSupperFx.Water, 0.85f * env)); body.Add(z + 2f * d, 0.006f, A(LastSupperFx.Water, 0.85f * env));
                hi.Add(z + d, 0.0025f, A(LastSupperFx.WaterLight, 0.9f * env)); hi.Add(z + 2f * d, 0.002f, A(LastSupperFx.WaterLight, 0.9f * env));
            }

            // where it lands: from when the front arrives until the tail has gone in (+0.25 s)
            float on = Sat((c.t - Head * 0.8f) / 0.08f) * (1f - Sat((c.t - c.dur + 0.02f) / 0.25f));
            on *= env;
            if (on <= 0.004f) return;
            Vector3 w0 = bottom + Vector3.up * 0.002f;
            for (int i = 0; i < 3; i++)
            {
                float u = (c.t - Head) / 0.5f - i / 3f;                        // one ring every 0.17 s, 0.5 s each
                if (u < 0f) continue;
                u -= Mathf.Floor(u);
                float r = Mathf.Lerp(0.010f, 0.034f, OutCubic(u));
                b.Sprite(w0, r * 2f, A(Color.Lerp(LastSupperFx.WaterLight, LastSupperFx.Water, 0.3f), 0.75f * on * (1f - u)),
                         DGFxPaint.Ring, i * 1.3f, false, FxFace.Ground);
            }
            b.Sprite(w0 + Vector3.up * 0.003f, 0.022f, A(LastSupperFx.WaterLight, 0.35f * on * (0.85f + 0.15f * Mathf.Sin(c.t * 9f))),
                     DGFxPaint.SoftDot, 0f, true, FxFace.Camera);
            for (int i = 0; i < 6; i++)
            {
                float period = Mathf.Lerp(0.38f, 0.55f, FxRand.H(c.seed, i, 0));
                float ph = (c.t - Head) / period + FxRand.H(c.seed, i, 1);
                if (ph < FxRand.H(c.seed, i, 1)) continue;
                int cyc = Mathf.FloorToInt(ph); float uu = (ph - cyc) * period;
                int k = i * 13 + cyc;
                float vy = Mathf.Lerp(0.20f, 0.30f, FxRand.H(c.seed, k, 2)), g = 2.6f, flight = 2f * vy / g;
                if (uu > flight) continue;
                Vector3 v = Flat(Tau * FxRand.H(c.seed, k, 3), Mathf.Lerp(0.05f, 0.09f, FxRand.H(c.seed, k, 4)));
                Vector3 p = w0 + v * uu + Vector3.up * (vy * uu - 0.5f * g * uu * uu);
                float s = Mathf.Lerp(0.0055f, 0.0075f, FxRand.H(c.seed, k, 5));
                b.Sprite(p, s, A(LastSupperFx.WaterDeep, 0.95f * on), DGFxPaint.ConfettiDot, 0f);
                b.Sprite(p + c.camUp * (s * 0.18f) - c.camRight * (s * 0.15f), s * 0.45f, A(LastSupperFx.WaterLight, 0.9f * on), DGFxPaint.SoftDot, 0f);
            }
        }
    }
}
