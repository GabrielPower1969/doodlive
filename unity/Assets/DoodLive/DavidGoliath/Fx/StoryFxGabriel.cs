// Gabriel (story pack: the archangel) effects, docs/gabriel/FX.md. Same engine as the earlier packs: every effect is a
// pure function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and
// registered in FxLibrary after the earlier packs (an existing id is never replaced).
// New: heaven_rays, cloud_drift, descend_light, feather_fall, wing_gust, trumpet_notes, and bless_glow (the
// "heart_glow toward the viewer" of S06: Ruth's heart_glow sends its warmth to a second actor, and the director does
// not pass `to`, so with no second actor it would light a point in the air beside him).
// Reused unchanged: sparkle, heart_glow (Ruth), golden_rays (D&G).
// heaven_rays posts a mild golden-hour request to StoryTint (StoryFxRuth.cs); StoryTintStage already draws it, so no
// runtime file is needed. Only managed UnityEngine value types are used, so the off-Unity preview harness runs it.
// The atlas has no feather or note cell, so feathers and notes are built from ribbons and dots (GabrielFx.Feather / Note).
// Child-friendly rules as before: no flash, no strobe, nothing bright or opaque over the face.
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Gabriel registry, palette, stage points and the shared feather / note / stroke drawing.</summary>
    public static class GabrielFx
    {
        internal static FxDef[] Defs => new FxDef[]
        {
            new HeavenRays(), new CloudDrift(), new DescendLight(), new FeatherFall(), new WingGust(), new TrumpetNotes(),
            new BlessGlow(),
        };

        // ---- stage points (docs/gabriel/CONTRACT.md §6), stage-local art-width units; Integration may overwrite them
        /// <summary>Centre of the rosette glow over the gate arch (`gateGlow`): the source of heaven_rays.</summary>
        public static Vector3 GateGlow = new Vector3(0f, 0.30f, -0.49f);
        /// <summary>Top of the cloud floor in the centre stage. Ground effects sit just above it.</summary>
        public static float CloudTop = 0.04f;
        /// <summary>From the `trumpet` node to the bell while he blows (bell up and toward the viewer), stage-local.
        /// Zero it if the node already sits at the bell.</summary>
        public static Vector3 BellOffset = new Vector3(0f, 0.08f, 0.16f);
        /// <summary>Golden-hour multiply tint that heaven_rays requests (0 = no tint).</summary>
        public static float GoldenHour = 1f;
        public static Color GoldenTint = new Color(1.00f, 0.955f, 0.86f, 1f);
        public static Color GoldenRim = new Color(0.36f, 0.25f, 0.08f, 1f);

        // ---- palette (docs/gabriel/DESIGN.md demo colours + Paper & Crayon tokens), sRGB
        internal static readonly Color WarmWhite = new Color32(0xFF, 0xF6, 0xDC, 255);
        internal static readonly Color RayGold = new Color32(0xFF, 0xCF, 0x6E, 255);
        internal static readonly Color Amber = new Color32(0xF2, 0xA4, 0x3A, 255);       // the gate's arch glow
        internal static readonly Color CloudWhite = new Color32(0xFF, 0xFB, 0xF0, 255);
        internal static readonly Color CloudPeach = new Color32(0xF7, 0xDD, 0xB0, 255);
        internal static readonly Color CloudShade = new Color32(0xDD, 0xB3, 0x7C, 255);
        internal static readonly Color FeatherWhite = new Color32(0xFF, 0xFD, 0xF6, 255);
        internal static readonly Color FeatherCream = new Color32(0xF6, 0xEC, 0xD2, 255);
        internal static readonly Color FeatherEdge = new Color32(0xA8, 0x8C, 0x5E, 255);
        internal static readonly Color FeatherShaft = new Color32(0xC9, 0xAE, 0x7C, 255);
        internal static readonly Color NoteGold = new Color32(0xF4, 0xB9, 0x2E, 255);
        internal static readonly Color NoteEdge = new Color32(0x9A, 0x66, 0x14, 255);
        internal static readonly Color Rose = new Color32(0xF4, 0xA6, 0xB8, 255);
        internal static readonly Color Blush = new Color32(0xFB, 0xD3, 0xDF, 255);

        /// <summary>A crayon stroke that stays solid to its end (the ribbon cell fades over its last 40 %: the fade is
        /// pushed into a short tail past p1).</summary>
        internal static void Stroke(FxBatch b, Vector3 p0, Vector3 p1, float w0, float w1, Color col, bool add = false)
        {
            var r = b.Ribbon(DGFxPaint.Ribbon, add);
            Vector3 d = p1 - p0;
            for (int k = 0; k <= 3; k++) r.Add(p0 + d * (k / 3f), Mathf.Lerp(w0, w1, k / 3f), col);
            r.Add(p1 + d * 0.05f, w1, col);
            r.Add(p1 + d * 0.10f, w1 * 0.8f, col);
        }

        /// <summary>A soft cloud puff: a peach shadow under three white lobes, with a light crayon rim (the Dust cell
        /// alone has a pencil outline that reads as a stone on the cream cloud floor).</summary>
        internal static void Puff(FxCtx c, FxBatch b, Vector3 p, float size, Color col, float alpha, float rot)
        {
            if (alpha <= 0.004f) return;
            Vector3 R = c.camRight, U = Vector3.up;
            float flip = Mathf.Sin(rot * 7.3f) > 0 ? 1f : -1f;
            // warm underside with a crayon edge, then the white top a little higher, so a tan crescent shows underneath
            b.Sprite(p - U * (0.22f * size), 2.7f * size, 1.2f * size, A(CloudShade, 0.45f * alpha), DGFxPaint.SoftDot, 0, false, FxFace.Camera);
            b.Sprite(p - U * (0.12f * size), 2.0f * size, 1.25f * size, A(Color.Lerp(CloudPeach, CloudShade, 0.55f), 0.60f * alpha), DGFxPaint.Dust, flip * 0.2f, false, FxFace.Camera);
            Vector3 q = p + U * (0.16f * size);
            b.Sprite(q - R * (flip * 0.44f * size) - U * (0.08f * size), 1.7f * size, A(col, alpha), DGFxPaint.SoftDot, 0, false);
            b.Sprite(q + R * (flip * 0.40f * size) - U * (0.12f * size), 1.5f * size, A(col, alpha), DGFxPaint.SoftDot, 0, false);
            b.Sprite(q + U * (0.06f * size), 2.2f * size, A(col, alpha), DGFxPaint.SoftDot, 0, false);
            b.Sprite(q + U * (0.10f * size), 1.5f * size, A(Color.white, 0.8f * alpha), DGFxPaint.SoftDot, 0, false);
        }

        /// <summary>
        /// One white feather in the screen plane, centred on p: a warm pencil edge, a white vane and a shaft line.
        /// ang = direction of the shaft (radians from camRight), flat = 0..1 how much of the vane faces the viewer
        /// (the tumble), bend = sideways curve as a fraction of the length.
        /// </summary>
        internal static void Feather(FxCtx c, FxBatch b, Vector3 p, float len, float ang, float flat, float bend, Color fill, float alpha)
        {
            if (alpha <= 0.004f) return;
            float cs = Mathf.Cos(ang), sn = Mathf.Sin(ang);
            Vector3 D = c.camRight * cs + c.camUp * sn, N = -c.camRight * sn + c.camUp * cs;
            float W = len * 0.62f * Mathf.Lerp(0.30f, 1f, Sat(flat));
            for (int layer = 0; layer < 2; layer++)
            {
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                Color col = layer == 0 ? A(FeatherEdge, 0.85f * alpha) : A(fill, alpha);
                float grow = layer == 0 ? 1.28f : 1f, pad = layer == 0 ? 0.009f : 0f;
                const int pts = 7;
                Vector3 last = p;
                for (int k = 0; k < pts; k++)
                {
                    float f = k / (float)(pts - 1);                                  // 0 quill .. 1 tip
                    float prof = Mathf.Pow(Mathf.Sin(Mathf.PI * (0.06f + 0.86f * Mathf.Pow(f, 0.8f))), 0.65f);
                    last = p + D * (len * (f - 0.5f)) + N * (bend * len * 4f * f * (1 - f));
                    r.Add(last, W * prof * grow + pad, col);
                }
                for (int k = 1; k <= 4; k++) r.Add(last + D * (len * 0.012f * k), 0.004f, col);   // the cell's fade lives here
            }
            // shaft, with a little bare quill sticking out
            Vector3 q0 = p - D * (len * 0.62f), q1 = p + D * (len * 0.36f) + N * (bend * len * 0.5f);
            Stroke(b, q0, q1, 0.0065f, 0.0035f, A(FeatherShaft, 0.9f * alpha));
        }

        /// <summary>A golden musical note in the screen plane: kind 0 = eighth (flag), 1 = two beamed eighths, 2 = quarter.
        /// s = head width; p = centre of the (first) head.</summary>
        internal static void Note(FxCtx c, FxBatch b, Vector3 p, float s, float tilt, int kind, float alpha)
        {
            if (alpha <= 0.004f || s <= 1e-4f) return;
            float cs = Mathf.Cos(tilt), sn = Mathf.Sin(tilt);
            Vector3 R = c.camRight * cs + c.camUp * sn, U = -c.camRight * sn + c.camUp * cs;
            Color edge = A(NoteEdge, alpha), fill = A(NoteGold, alpha);
            int heads = kind == 1 ? 2 : 1;
            Vector3 top0 = p, top1 = p;
            for (int h = 0; h < heads; h++)
            {
                Vector3 hc = p + R * (h * 1.15f * s) + U * (h * 0.22f * s);
                Vector3 foot = hc + R * (0.40f * s) + U * (0.06f * s), top = foot + U * (1.75f * s);
                Stroke(b, foot, top, 0.17f * s, 0.15f * s, edge);
                b.Sprite(hc, 1.12f * s, 0.84f * s, edge, DGFxPaint.SoftDot, tilt + 0.35f, false, FxFace.Camera);     // soft shadow rim
                b.Sprite(hc, s, 0.74f * s, fill, DGFxPaint.ConfettiDot, tilt + 0.35f, false, FxFace.Camera);
                if (h == 0) top0 = top; else top1 = top;
            }
            if (kind == 0)
            {   // flag: curls right and down from the stem top
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                r.Add(top0 + U * (0.04f * s), 0.24f * s, edge);
                r.Add(top0 + R * (0.30f * s) - U * (0.18f * s), 0.22f * s, edge);
                r.Add(top0 + R * (0.52f * s) - U * (0.50f * s), 0.18f * s, edge);
                r.Add(top0 + R * (0.56f * s) - U * (0.80f * s), 0.12f * s, edge);
                r.Add(top0 + R * (0.50f * s) - U * (0.95f * s), 0.08f * s, edge);
                r.Add(top0 + R * (0.46f * s) - U * (1.02f * s), 0.05f * s, edge);
            }
            else if (kind == 1)
            {
                Vector3 d = (top1 - top0) * 0.06f;
                Stroke(b, top0 - d - U * (0.08f * s), top1 + d - U * (0.08f * s), 0.34f * s, 0.34f * s, edge);
            }
        }
    }

    // ------------------------------------------------------------------ all play: god rays from the gate (loop)
    /// <summary>
    /// Golden hour. A breathing glow on the gate's rosette; a fan of soft god rays from it, up and out and leaning a
    /// little toward the viewer (they stay behind the centre stage, so the actor always stands in front of them); pale
    /// shafts lying over the cloud floor either side of the centre; slow haze bands and floating motes. Also asks
    /// StoryTint for a mild warm multiply (GabrielFx.GoldenHour). Fades in / out over 1.5 s.
    /// </summary>
    public sealed class HeavenRays : FxDef
    {
        public override string Id => "heaven_rays";
        public override float DefaultDur => 999f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.5f, 1.5f);
            env = env * env * (3 - 2 * env);
            StoryTint.Request(c.seed, GabrielFx.GoldenTint, env * GabrielFx.GoldenHour, GabrielFx.GoldenRim);
            if (env <= 0) return;
            Vector3 o = GabrielFx.GateGlow + new Vector3(0, 0, 0.012f);
            float breathe = 0.86f + 0.14f * Mathf.Sin(c.t * Tau * 0.11f);

            // haze bands hanging in front of the wall: the rays pass through them
            for (int i = 0; i < 5; i++)
            {
                float span = 1.5f, sp = Mathf.Lerp(0.010f, 0.018f, FxRand.H(c.seed, 40 + i, 0));
                float ph = FxRand.H(c.seed, 40 + i, 1) + c.t * sp / span; ph -= Mathf.Floor(ph);
                var p = new Vector3(-0.75f + span * ph, Mathf.Lerp(0.10f, 0.36f, FxRand.H(c.seed, 40 + i, 2)),
                                    Mathf.Lerp(-0.46f, -0.34f, FxRand.H(c.seed, 40 + i, 3)));
                float edge = Sat(ph * 5f) * Sat((1 - ph) * 5f);
                b.Sprite(p, 0.62f, 0.15f, A(GabrielFx.WarmWhite, 0.22f * env * edge), DGFxPaint.SoftDot, 0, false, FxFace.Camera);
            }

            // the glow on the rosette
            b.Sprite(o, 0.50f * breathe, A(GabrielFx.Amber, 0.42f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(o + Vector3.forward * 0.004f, 0.24f, A(GabrielFx.WarmWhite, 0.60f * env * breathe), DGFxPaint.SoftDot, 0, true);

            // the fan
            const int n = 11;
            float sway = 0.05f * Mathf.Sin(c.t * Tau * 0.035f);
            for (int i = 0; i < n; i++)
            {
                float ang = Mathf.Lerp(0.10f, Mathf.PI - 0.10f, (i + 0.5f) / n) + sway + 0.07f * FxRand.Signed(c.seed, i, 0);
                float tilt = Mathf.Lerp(0.08f, 0.26f, FxRand.H(c.seed, i, 1));
                var dir = new Vector3(Mathf.Cos(ang) * Mathf.Cos(tilt), Mathf.Sin(ang) * Mathf.Cos(tilt), Mathf.Sin(tilt));
                float len = Mathf.Lerp(0.72f, 1.10f, FxRand.H(c.seed, i, 2));
                float pulse = 0.55f + 0.45f * Mathf.Sin(Tau * (c.t / Mathf.Lerp(7f, 11f, FxRand.H(c.seed, i, 3)) + FxRand.H(c.seed, i, 4)));
                float wEnd = i % 3 == 0 ? 0.26f : 0.15f;
                Color col = i % 2 == 0 ? GabrielFx.RayGold : GabrielFx.Amber;
                var r = b.Ribbon(DGFxPaint.Streak, false);
                var g = b.Ribbon(DGFxPaint.Streak, true);
                const int pts = 5;
                for (int k = 0; k < pts; k++)
                {
                    float s = k / (float)(pts - 1);
                    Vector3 p = o + dir * (0.02f + len * s);
                    r.Add(p, Mathf.Lerp(0.04f, wEnd, s), A(col, 0.34f * env * pulse * (1f - 0.55f * s)));
                    g.Add(p, Mathf.Lerp(0.02f, wEnd * 0.45f, s), A(GabrielFx.WarmWhite, 0.26f * env * pulse * (1f - 0.5f * s)));
                }
            }

            // shafts lying over the clouds from the foot of the stair, never down the middle (the actor's marks)
            float y = GabrielFx.CloudTop + 0.022f;
            for (int i = 0; i < 6; i++)
            {
                float a = (i < 3 ? -1f : 1f) * Mathf.Lerp(0.20f, 0.95f, (i % 3) / 2f) + sway * 0.6f;
                var d = new Vector3(Mathf.Sin(a), 0, Mathf.Cos(a));
                var p0 = new Vector3(GabrielFx.GateGlow.x + 0.10f * Mathf.Sin(a), y, -0.37f);
                float pulse = 0.6f + 0.4f * Mathf.Sin(Tau * (c.t / Mathf.Lerp(6f, 9f, FxRand.H(c.seed, 60 + i, 0)) + 0.17f * i));
                var r = b.Ribbon(DGFxPaint.Streak, false);
                for (int k = 0; k < 4; k++)
                {
                    float s = k / 3f;
                    r.Add(p0 + d * (0.60f * s), Mathf.Lerp(0.03f, 0.11f, s), A(GabrielFx.RayGold, 0.30f * env * pulse));
                }
            }

            // motes floating in the light, behind the centre stage
            for (int i = 0; i < 18; i++)
            {
                float period = Mathf.Lerp(6f, 10f, FxRand.H(c.seed, 80 + i, 0));
                float ph = c.t / period + FxRand.H(c.seed, 80 + i, 1);
                float a = ph - Mathf.Floor(ph); int cyc = (int)Mathf.Floor(ph);
                var p = new Vector3(Mathf.Lerp(-0.52f, 0.52f, FxRand.H(c.seed, 80 + i * 7 + cyc, 2)) + 0.02f * Mathf.Sin(Tau * a + i),
                                    Mathf.Lerp(0.10f, 0.62f, FxRand.H(c.seed, 80 + i * 7 + cyc, 3)) + 0.05f * a,
                                    Mathf.Lerp(-0.46f, -0.20f, FxRand.H(c.seed, 80 + i * 7 + cyc, 4)));
                float life = Mathf.Sin(Mathf.PI * a) * env;
                bool tw = i % 4 == 0;
                b.Sprite(p, tw ? 0.026f : 0.014f, A(GabrielFx.RayGold, 0.9f * life), tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, c.t * 0.5f + i, false);
                b.Sprite(p, tw ? 0.016f : 0.008f, A(GabrielFx.WarmWhite, life), DGFxPaint.SoftDot, 0, true);
            }
        }
    }

    // ------------------------------------------------------------------ all play: low wisps crossing the page (loop)
    /// <summary>Low cloud wisps drifting slowly across the page, just above the cloud floor (never higher than a knee):
    /// each is a tapering white streak with a peach shadow under it and two or three soft lumps.</summary>
    public sealed class CloudDrift : FxDef
    {
        public override string Id => "cloud_drift";
        public override float DefaultDur => 999f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.5f, 1.5f);
            if (env <= 0) return;
            const int n = 8;
            const float span = 1.60f;
            for (int j = 0; j < n; j++)
            {
                int i = (j * 3) % n;                                   // far ones first (drawn under the near ones)
                float z = Mathf.Lerp(-0.42f, 0.19f, i / (float)(n - 1));
                float sp = Mathf.Lerp(0.020f, 0.036f, FxRand.H(c.seed, i, 0));
                float ph = FxRand.H(c.seed, i, 1) + c.t * sp / span; ph -= Mathf.Floor(ph);
                float scale = Mathf.Lerp(0.8f, 1.3f, FxRand.H(c.seed, i, 2));
                float y = GabrielFx.CloudTop + Mathf.Lerp(0.016f, 0.050f, FxRand.H(c.seed, i, 3)) + 0.005f * Mathf.Sin(c.t * 0.5f + i * 1.3f);
                float edge = Sat(ph * 7f) * Sat((1 - ph) * 7f);
                float alpha = env * edge * (z > 0.05f ? 0.72f : 0.9f);
                var p = new Vector3(-0.80f + span * ph, y, z);
                float L = 0.34f * scale;
                for (int layer = 0; layer < 2; layer++)
                {
                    var r = b.Ribbon(DGFxPaint.Streak, false);
                    Color col = layer == 0 ? A(GabrielFx.CloudShade, 0.55f * alpha) : A(GabrielFx.CloudWhite, 0.95f * alpha);
                    for (int k = 0; k < 6; k++)
                    {
                        float f = k / 5f;
                        float wave = 0.006f * Mathf.Sin(f * 5f + c.t * 0.4f + i);
                        r.Add(p + new Vector3(L * (f - 0.5f), wave - (layer == 0 ? 0.010f : 0f), 0),
                              (layer == 0 ? 0.050f : 0.044f) * scale * (0.45f + 0.55f * Mathf.Sin(Mathf.PI * f)), col);
                    }
                }
                for (int k = 0; k < 3; k++)
                {
                    float f = Mathf.Lerp(0.30f, 0.72f, k / 2f) + 0.05f * FxRand.Signed(c.seed, i * 5 + k, 4);
                    float s = Mathf.Lerp(0.042f, 0.066f, FxRand.H(c.seed, i * 5 + k, 5)) * scale;
                    GabrielFx.Puff(c, b, p + new Vector3(L * (f - 0.5f), 0.012f + 0.25f * s, 0.002f), s * (k == 1 ? 1f : 0.8f),
                                   GabrielFx.CloudWhite, 0.9f * alpha, 0.3f * k + i);
                }
            }
        }
    }

    // ------------------------------------------------------------------ S02: the column of light he comes down in
    /// <summary>
    /// A warm column of light that follows the node down. The column and its halo stand just BEHIND him (the depth
    /// test lets him and his wings cover them, so they read as backlight and nothing washes out his face); a pool of
    /// light on the clouds grows as he nears the page; motes spiral down round him. Fades in 0.8 s, out 1.2 s.
    /// </summary>
    public sealed class DescendLight : FxDef
    {
        public override string Id => "descend_light";
        public override float DefaultDur => 6f;

        const float Top = 1.80f;                     // the light comes from far above the page
        const float RTop = 0.10f, RBottom = 0.21f;   // half widths

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 1.2f);
            if (env <= 0) return;
            env = env * env * (3 - 2 * env);
            Vector3 a = c.anchor;
            Vector3 g = FxCtx.Ground(a, GabrielFx.CloudTop + 0.006f);
            Vector3 toCam = c.ToCamFlat(a);
            Vector3 side = Vector3.Cross(Vector3.up, toCam).normalized;
            float near = 1f - Sat((a.y - g.y) / 0.55f);                 // 0 high in the air .. 1 landed
            float breathe = 0.9f + 0.1f * Mathf.Sin(c.t * Tau * 0.3f);

            // the pool on the clouds
            float pr = 2f * RBottom * (0.9f + 0.7f * near);
            b.Sprite(g, pr, A(GabrielFx.RayGold, (0.30f + 0.38f * near) * env * breathe), DGFxPaint.GlowDisc, c.t * 0.08f, false, FxFace.Ground);
            b.Sprite(g + Vector3.up * 0.001f, pr * 0.7f, A(GabrielFx.WarmWhite, (0.18f + 0.34f * near) * env), DGFxPaint.SoftDot, 0, true, FxFace.Ground);

            // the column, behind him and leaning a touch away from the viewer
            Vector3 foot = g - toCam * 0.10f;
            Vector3 top = new Vector3(a.x, Top, a.z) - toCam * 0.22f;
            Beam(b, top, foot, side, 0f, RTop * 2.3f, RBottom * 2.4f, A(GabrielFx.RayGold, 0.30f * env), false);
            const int n = 5;
            for (int i = 0; i < n; i++)
            {
                float f = (i - (n - 1) * 0.5f) / ((n - 1) * 0.5f);
                float pulse = 0.6f + 0.4f * Mathf.Sin(Tau * (0.20f * c.t + 0.31f * i));
                Beam(b, top, foot, side, f, RTop * 0.8f, RBottom * 0.8f, A(i % 2 == 0 ? GabrielFx.Amber : GabrielFx.RayGold, 0.22f * env * pulse), false);
                Beam(b, top, foot, side, f, RTop * 0.5f, RBottom * 0.5f, A(GabrielFx.WarmWhite, 0.24f * env * pulse), true);
            }

            // the halo behind him: bigger than the wings, so it rims their edge
            Vector3 mid = a + Vector3.up * 0.44f - toCam * 0.12f;
            b.Sprite(mid, 1.45f, 1.15f, A(GabrielFx.RayGold, 0.50f * env * breathe), DGFxPaint.SoftDot, 0, false, FxFace.Camera);
            b.Sprite(mid, 0.9f, 0.9f, A(GabrielFx.WarmWhite, 0.30f * env), DGFxPaint.SoftDot, 0, true, FxFace.Camera);

            // motes spiralling down round him (kept off the face: nothing crosses the middle at head height)
            const int m = 26;
            for (int i = 0; i < m; i++)
            {
                float period = Mathf.Lerp(2.6f, 4.2f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float u = ph - Mathf.Floor(ph);
                float y = Mathf.Lerp(a.y + 1.05f, Mathf.Max(g.y, a.y - 0.04f), u);
                float rr = Mathf.Lerp(0.13f, 0.40f, FxRand.H(c.seed, i, 2)) * Mathf.Lerp(0.75f, 1.1f, u);
                float ang = Tau * FxRand.H(c.seed, i, 3) + c.t * Mathf.Lerp(0.35f, 0.8f, FxRand.H(c.seed, i, 4)) * (i % 2 == 0 ? 1 : -1);
                float lat = Mathf.Cos(ang) * rr;
                if (Mathf.Abs(lat) < 0.085f && y > a.y + 0.40f && y < a.y + 0.68f) continue;
                Vector3 p = new Vector3(a.x, y, a.z) + side * lat + toCam * (Mathf.Sin(ang) * rr * 0.6f);
                float life = Mathf.Sin(Mathf.PI * u) * env;
                bool tw = i % 3 == 0;
                b.Sprite(p, tw ? 0.034f : 0.018f, A(i % 2 == 0 ? GabrielFx.RayGold : GabrielFx.Amber, life),
                         tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, c.t * 0.8f + i, false);
                b.Sprite(p, tw ? 0.02f : 0.01f, A(GabrielFx.WarmWhite, life), DGFxPaint.SoftDot, 0, true);
            }
        }

        static void Beam(FxBatch b, Vector3 top, Vector3 foot, Vector3 side, float f, float wTop, float wBottom, Color col, bool add)
        {
            var r = b.Ribbon(DGFxPaint.Streak, add);
            const int pts = 6;
            for (int k = 0; k < pts; k++)
            {
                float s = k / (float)(pts - 1);
                Vector3 axis = Vector3.Lerp(top, foot, s);
                float half = Mathf.Lerp(RTop, RBottom, s) * 0.75f;
                r.Add(axis + side * (f * half), Mathf.Lerp(wTop, wBottom, s), col);
            }
        }
    }

    // ------------------------------------------------------------------ S02 / S05 / S07: feathers let go
    /// <summary>
    /// White feathers, a few at a time. On a node (gabriel.chest) each one leaves a wing where the wing was at that
    /// moment (0.15-0.44 to the side of the node and just in front of the wing, never in front of the face) and then falls by itself: a slow
    /// pendulum sway, tilting into each swing, turning its face to and from the viewer; the ones that reach the cloud
    /// floor settle flat and fade, the ones still high after 3.3 s fade in the air. Played on `stage` (anchor on the
    /// page) they drift down from above the whole stage instead.
    /// </summary>
    public sealed class FeatherFall : FxDef
    {
        public override string Id => "feather_fall";
        public override float DefaultDur => 6f;

        const float Every = 0.5f, Air = 3.3f, Rest = 0.6f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0f, 0.5f);
            if (env <= 0) return;
            bool stage = c.start.y < 0.06f;                               // `stage` (or a node on the page): fall from the sky
            float floor = GabrielFx.CloudTop + 0.012f;
            float lastSpawn = Mathf.Max(Every, c.dur - 1.6f);
            int last = Mathf.FloorToInt(Mathf.Min(c.t, lastSpawn) / Every);
            for (int k = Mathf.Max(0, last - 9); k <= last; k++)
            {
                float t0 = k * Every + 0.25f * Every * FxRand.H(c.seed, k, 0);
                float age = c.t - t0;
                if (age <= 0 || age >= Air + Rest) continue;

                Vector3 src; Vector3 sideV, toCam;
                float sgn = k % 2 == 0 ? 1f : -1f;
                if (stage)
                {
                    toCam = c.ToCamFlat(Vector3.zero);
                    sideV = Vector3.Cross(Vector3.up, toCam).normalized;
                    src = new Vector3(sgn * Mathf.Lerp(0.12f, 0.46f, FxRand.H(c.seed, k, 1)),
                                      Mathf.Lerp(0.50f, 0.72f, FxRand.H(c.seed, k, 2)),
                                      Mathf.Lerp(-0.22f, 0.12f, FxRand.H(c.seed, k, 3)));
                }
                else
                {
                    Vector3 node = c.track.Count > 0 ? c.track.Sample(t0) : c.anchor;   // where the wing was when it let go
                    toCam = c.ToCamFlat(node);
                    sideV = Vector3.Cross(Vector3.up, toCam).normalized;
                    src = node + sideV * (sgn * Mathf.Lerp(0.15f, 0.44f, FxRand.H(c.seed, k, 1)))
                               + Vector3.up * Mathf.Lerp(-0.10f, 0.30f, FxRand.H(c.seed, k, 2))
                               + toCam * Mathf.Lerp(0.05f, 0.14f, FxRand.H(c.seed, k, 3));   // in front of the wing, or the wing hides it
                }

                float v = Mathf.Lerp(0.10f, 0.15f, FxRand.H(c.seed, k, 4));
                float tLand = Mathf.Max(0.2f, (src.y - floor) / v);
                bool lands = tLand <= Air;
                float fly = Mathf.Min(age, lands ? tLand : Air);
                float period = Mathf.Lerp(1.5f, 2.1f, FxRand.H(c.seed, k, 5));
                float ph = Tau * (fly / period + FxRand.H(c.seed, k, 6));
                float amp = Mathf.Lerp(0.035f, 0.060f, FxRand.H(c.seed, k, 7)) * Sat(fly * 1.5f);
                Vector3 p = src + sideV * (amp * Mathf.Sin(ph) + sgn * 0.018f * fly)
                                + toCam * (0.02f * Mathf.Cos(ph * 0.7f))
                                + Vector3.down * (v * fly + 0.010f * (1f - Mathf.Cos(2f * ph)) * Sat(fly));
                if (p.y < floor) p.y = floor;

                float ang = sgn * 0.35f + 0.80f * Mathf.Cos(ph) + 0.25f * Mathf.Sin(fly * 0.9f + k);    // tilts into the swing
                float flat = 0.5f + 0.5f * Mathf.Abs(Mathf.Cos(fly * 1.7f + k * 2.1f));                 // the tumble
                float alpha = Sat(age * 5f) * env;
                if (lands && age > tLand)
                {
                    float r = (age - tLand) / Rest;
                    ang = Mathf.Lerp(ang, sgn * 0.12f, Sat((age - tLand) / 0.25f));
                    flat = Mathf.Lerp(flat, 0.55f, Sat((age - tLand) / 0.25f));
                    alpha *= 1f - Smooth(0.25f, 1f, r);
                }
                else if (!lands) alpha *= 1f - Smooth(Air - 0.7f, Air, age);
                else if (age >= tLand + Rest) continue;

                float len = Mathf.Lerp(0.090f, 0.130f, FxRand.H(c.seed, k, 8));
                float bend = 0.10f * (k % 3 - 1) + 0.04f * Mathf.Sin(ph);
                GabrielFx.Feather(c, b, p, len, ang, flat, bend, k % 3 == 1 ? GabrielFx.FeatherCream : GabrielFx.FeatherWhite, alpha);
            }
        }
    }

    // ------------------------------------------------------------------ S02 landing / S07 take-off
    /// <summary>The wings push the clouds away: a ring of cloud puffs rolls outward over the page from where the node
    /// was, with a faint ring line, a smaller second wave and short speed strokes. All of it stays below the knee.</summary>
    public sealed class WingGust : FxDef
    {
        public override string Id => "wing_gust";
        public override float DefaultDur => 1.4f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float a = c.N;
            if (a >= 1) return;
            Vector3 g = FxCtx.Ground(c.start, GabrielFx.CloudTop + 0.008f);
            for (int wave = 0; wave < 2; wave++)
            {
                float aw = wave == 0 ? a : (a - 0.16f) / 0.84f;
                if (aw <= 0 || aw >= 1) continue;
                float e = OutCubic(aw);
                float rMax = wave == 0 ? 0.40f : 0.26f;
                float ringD = 2f * (0.08f + rMax * e) * 1.18f, ringA = (wave == 0 ? 1f : 0.6f) * Mathf.Pow(1 - aw, 1.4f);
                b.Sprite(g, ringD * 1.25f, A(GabrielFx.CloudWhite, 0.55f * ringA), DGFxPaint.GlowDisc, aw * 0.5f + wave, false, FxFace.Ground);
                b.Sprite(g, ringD, A(GabrielFx.CloudShade, 0.30f * ringA), DGFxPaint.Ring, aw * 0.5f + wave, false, FxFace.Ground);
                int n = wave == 0 ? 13 : 8;
                for (int i = 0; i < n; i++)
                {
                    int id = wave * 40 + i;
                    float ang = Tau * (i + 0.5f * FxRand.H(c.seed, id, 0)) / n + wave * 0.4f;
                    float rad = 0.08f + rMax * e * Mathf.Lerp(0.82f, 1.12f, FxRand.H(c.seed, id, 1));
                    float size = Mathf.Lerp(0.060f, 0.135f, e) * Mathf.Lerp(0.8f, 1.25f, FxRand.H(c.seed, id, 2)) * (wave == 0 ? 1f : 0.75f);
                    Vector3 p = g + Flat(ang, rad) + Vector3.up * (0.22f * size + 0.03f * Mathf.Sin(Mathf.PI * aw) * FxRand.H(c.seed, id, 3));
                    Color col = Color.Lerp(GabrielFx.CloudWhite, GabrielFx.CloudPeach, 0.6f * FxRand.H(c.seed, id, 4));
                    float alpha = 0.95f * Mathf.Pow(1 - aw, 1.2f) * Sat(aw * 12f);
                    GabrielFx.Puff(c, b, p, 0.62f * size, col, alpha, FxRand.H(c.seed, id, 5) * Tau);
                }
            }
            // speed strokes skimming the clouds
            float as_ = a / 0.55f;
            if (as_ < 1)
            {
                for (int i = 0; i < 10; i++)
                {
                    float ang = Tau * (i + 0.5f) / 10f + 0.2f;
                    float r0 = 0.12f + 0.36f * OutCubic(as_), r1 = r0 + 0.08f * (1 - as_) + 0.01f;
                    Vector3 up = Vector3.up * 0.02f;
                    GabrielFx.Stroke(b, g + Flat(ang, r0) + up, g + Flat(ang, r1) + up, 0.016f, 0.008f, A(GabrielFx.CloudWhite, 0.9f * (1 - as_)));
                }
            }
        }
    }

    // ------------------------------------------------------------------ S05: the trumpet call
    /// <summary>
    /// Golden notes (eighths, beamed pairs, quarters) pop out of the trumpet bell one after another and float up and
    /// out in a fan, growing and rocking, while soft sound arcs widen from the bell and a warm glow pulses on it.
    /// Everything leaves the bell upward and outward, away from the face. Follows the node (he leans as he blows).
    /// </summary>
    public sealed class TrumpetNotes : FxDef
    {
        public override string Id => "trumpet_notes";
        public override float DefaultDur => 4.5f;

        const float NoteEvery = 0.26f, NoteLife = 1.9f, ArcEvery = 0.55f, ArcLife = 1.5f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.15f, 0.6f);
            if (env <= 0) return;
            Vector3 bell = c.anchor + GabrielFx.BellOffset;
            Vector3 toCam = (c.camPos - bell).normalized;
            Vector3 R = c.camRight, U = c.camUp;
            float phrase = 0.75f + 0.25f * Mathf.Sin(c.t * Tau * 0.9f);

            // glow on the bell
            b.Sprite(bell + toCam * 0.01f, 0.17f * phrase, A(GabrielFx.RayGold, 0.45f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(bell + toCam * 0.012f, 0.09f * phrase, A(GabrielFx.WarmWhite, 0.55f * env), DGFxPaint.SoftDot, 0, true);

            // sound arcs: open at the bottom, so nothing sweeps down over the face
            float stopSpawn = c.dur - 0.9f;
            int lastArc = Mathf.FloorToInt(Mathf.Min(c.t, stopSpawn) / ArcEvery);
            for (int k = Mathf.Max(0, lastArc - 3); k <= lastArc; k++)
            {
                float a = (c.t - k * ArcEvery) / ArcLife;
                if (a <= 0 || a >= 1) continue;
                float rad = 0.04f + 0.27f * OutCubic(a);
                Vector3 centre = bell + toCam * 0.015f + U * (0.035f * a);
                Color col = A(k % 2 == 0 ? GabrielFx.NoteGold : GabrielFx.RayGold, 0.70f * Mathf.Pow(1 - a, 1.3f) * Sat(a * 8f) * env);
                float w = Mathf.Lerp(0.020f, 0.009f, a);
                for (int s = -1; s <= 1; s += 2)
                {   // two halves from the top: each ribbon fades toward its lower end
                    var r = b.Ribbon(DGFxPaint.Ribbon, false);
                    const int pts = 9;
                    for (int j = 0; j < pts; j++)
                    {
                        float ang = Mathf.PI * 0.5f - s * Mathf.Lerp(-0.04f, 1.95f, j / (float)(pts - 1));
                        r.Add(centre + (R * Mathf.Cos(ang) + U * (Mathf.Sin(ang) * 0.92f)) * rad, w, col);
                    }
                }
            }

            // the notes
            int lastNote = Mathf.FloorToInt(Mathf.Min(c.t, stopSpawn) / NoteEvery);
            for (int k = Mathf.Max(0, lastNote - 8); k <= lastNote; k++)
            {
                float age = c.t - k * NoteEvery;
                float a = age / NoteLife;
                if (a <= 0 || a >= 1) continue;
                float fan = k * 0.618034f; fan -= Mathf.Floor(fan);                       // golden-ratio spread: neighbours go different ways
                float th = Mathf.Lerp(0.32f, Mathf.PI - 0.32f, fan);
                float dist = 0.07f + 0.36f * OutCubic(a) * Mathf.Lerp(0.75f, 1.1f, FxRand.H(c.seed, k, 0));
                Vector3 p = bell + (R * Mathf.Cos(th) + U * (Mathf.Sin(th) * 0.85f)) * dist
                          + U * (0.06f * a) + R * (0.010f * Mathf.Sin(age * 5f + k))
                          + toCam * (0.03f + 0.08f * a);
                float size = Mathf.Lerp(0.036f, 0.058f, a) * OutBack(age / 0.25f);
                float tilt = 0.28f * Mathf.Sin(age * 3.2f + k * 1.9f);
                float alpha = Sat(a * 12f) * (1 - Smooth(0.62f, 1f, a)) * env;
                GabrielFx.Note(c, b, p, size, tilt, k % 3, alpha);
                if (k % 2 == 0)
                    b.Sprite(p - (R * Mathf.Cos(th) + U * Mathf.Sin(th)) * (0.05f + 0.02f * a) + toCam * 0.005f, 0.030f,
                             A(GabrielFx.WarmWhite, alpha), DGFxPaint.Sparkle, age * 2f + k, true);
            }
        }
    }

    // ------------------------------------------------------------------ S06: the blessing goes out to the child
    /// <summary>
    /// heart_glow toward the viewer. A warm glow at his chest (gold behind him, a small rose-gold heart of light on
    /// the cuirass, below the chin) and little lights that leave the chest toward the camera, opening left and right
    /// and a little down like open arms, growing as they come and fading before they reach the viewer.
    /// </summary>
    public sealed class BlessGlow : FxDef
    {
        public override string Id => "bless_glow";
        public override float DefaultDur => 5f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 1.0f);
            if (env <= 0) return;
            float breathe = 0.85f + 0.15f * Mathf.Sin(c.t * Tau * 0.45f);
            Vector3 chest = c.anchor;
            Vector3 toCam = (c.camPos - chest).normalized;
            Vector3 front = chest + toCam * 0.085f;

            b.Sprite(chest - toCam * 0.08f, 0.46f, A(GabrielFx.RayGold, 0.42f * env * breathe), DGFxPaint.SoftDot, 0, false);
            b.Sprite(front, 0.15f, A(GabrielFx.Rose, 0.46f * env * breathe), DGFxPaint.SoftDot, 0, false);
            b.Sprite(front + toCam * 0.004f, 0.085f, A(GabrielFx.RayGold, 0.55f * env * breathe), DGFxPaint.SoftDot, 0, false);
            b.Sprite(front + toCam * 0.006f, 0.05f, A(GabrielFx.WarmWhite, 0.45f * env * breathe), DGFxPaint.SoftDot, 0, true);

            const int n = 16;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(2.2f, 3.0f, FxRand.H(c.seed, i, 0));
                float tt = c.t - 0.5f - period * FxRand.H(c.seed, i, 1);
                if (tt < 0) continue;
                float ph = tt / period;
                float a = ph - Mathf.Floor(ph);
                float sgn = i % 2 == 0 ? 1f : -1f;
                Vector3 dir = (toCam + c.camRight * (sgn * Mathf.Lerp(0.30f, 0.95f, FxRand.H(c.seed, i, 2)))
                                     + c.camUp * Mathf.Lerp(-0.40f, 0.02f, FxRand.H(c.seed, i, 3))).normalized;
                Vector3 p = front + dir * (0.02f + 0.36f * Smooth(0f, 1f, a))
                          + c.camUp * (0.008f * Mathf.Sin(tt * 4f + i)) + c.camRight * (0.006f * Mathf.Cos(tt * 3f + i * 2f));
                float life = Sat(a * 6f) * Sat((1 - a) * 3f) * env;
                bool tw = i % 3 == 0;
                Color col = i % 3 == 1 ? GabrielFx.Rose : (i % 3 == 2 ? GabrielFx.Blush : GabrielFx.RayGold);
                float size = Mathf.Lerp(0.018f, 0.038f, a) * (tw ? 1.4f : 1f);
                b.Sprite(p, size, A(col, life), tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, tt * 1.5f, false);
                b.Sprite(p, size * 0.45f, A(GabrielFx.WarmWhite, life), DGFxPaint.SoftDot, 0, true);
            }
        }
    }
}
