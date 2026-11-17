// Saul Sees the Light! (story pack `saul`, docs/saul/FX.md) effects. Same engine as the earlier packs: every effect is a pure
// function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered in
// FxLibrary after the earlier packs (an existing id is never replaced), through the manifest `fx.class` = SaulFx.
// New: road_light, scales_fall (CONTRACT §8). Reused unchanged: angel_light, sparkle (Daniel), golden_rays, dust_burst (D&G),
// heart_glow, lamp_flame, night, dust_road (Ruth), prayer_glow (Esther), water_pour (The King Who Serves), zzz. No aliases.
// road_light only posts a small dim to Esther's StoryLight (StoryFxStage turns it into the overlay); it never uses the cold flash.
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no strobe, no cold flash; the light is warm and wonderful, never scary, and nothing
// bright stays in front of a face (the column, the halo and the motes stand behind Saul, the bloom lasts 1.5 s).
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Saul registry and palette (docs/saul/CONTRACT.md §8, DESIGN.md §4).</summary>
    public static class SaulFx
    {
        internal static FxDef[] Defs => new FxDef[] { new RoadLight(), new ScalesFall() };

        // warm white-gold light from heaven: reads on Saul's skin and red cloak and on the sand-gold road (F4: the pool and
        // the column are additive over a mid-tone, never over white)
        internal static readonly Color WarmWhite = new Color32(0xFF, 0xF6, 0xDC, 255), Gold = new Color32(0xFF, 0xD2, 0x7A, 255),
                                       Amber = new Color32(0xF5, 0xB8, 0x55, 255);
        // the scales: pale silver with a warm cast; the atlas Pebble cell gives each flake a dark ink outline, so they read
        // on Saul's skin and on the pale floor
        internal static readonly Color Silver = new Color32(0xF2, 0xF4, 0xF6, 255), Glint = new Color32(0xFF, 0xFB, 0xE8, 255);

        /// <summary>How much of Esther's dim (StoryLight.DimStrength, an evening-blue veil) road_light asks for: a gentle
        /// 30 % so the column stands out without the road turning cold. Set 0 to switch the dim off.</summary>
        public static float DimShare = 0.30f;
    }

    // ------------------------------------------------------------------ S03-S04: the light from heaven
    /// <summary>
    /// The light from heaven that stops Saul (node = saul.root; stays where it started; CONTRACT §8: ~33 s, S03 + S04).
    /// 0-1.5 s: one soft whole-frame warm bloom (rises in 0.3 s, eases away over the next 1.2 s; warm white, additive, no
    /// strobe, no cold flash), the brightest moment. From 0.2 s a strong column of warm white-gold light from 1.8 above
    /// onto the node (about 0.25 wide at the ground, soft edges: a wide gold layer, three slow shafts, a bright core), a
    /// pool of light on the road and slow gold motes falling inside it. The rest of the stage is gently dimmed through
    /// StoryLight (30 %). Fades out over the last 1.5 s. The column, its halo and the motes all stand BEHIND the node
    /// (depth-tested, so Saul and the guards cover them: backlight), and the motes keep off the face band, so his face
    /// stays readable. Breathes slowly (±8 % at 0.25 Hz).
    /// </summary>
    public sealed class RoadLight : FxDef
    {
        public override string Id => "road_light";
        public override float DefaultDur => 33f;
        public override bool Follow => false;

        const float Top = 1.80f;                       // the light comes from far above the page
        const float WTop = 0.14f, WBottom = 0.27f;     // full widths of the wide layer (≈ 0.25 at the ground)
        const float FaceLo = 0.05f, FaceHi = 0.40f;    // height band of Saul's head (seated and standing)
        const int Motes = 16;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float fadeOut = Sat((c.dur - c.t) / 1.5f);
            float colIn = Smooth(0.2f, 1.4f, c.t);
            float env = colIn * fadeOut;
            // the gentle dim of the rest of the stage (a soft shape; StoryLight drops it by itself when the effect ends)
            StoryLight.RequestDim(c.seed, StoryLight.DimStrength * SaulFx.DimShare * Smooth(0.4f, 2.0f, c.t) * fadeOut);
            if (c.t >= c.dur) return;

            Vector3 a = c.start;
            Vector3 g = FxCtx.Ground(a, 0.004f);
            Vector3 toCam = c.ToCamFlat(a);
            Vector3 side = Vector3.Cross(Vector3.up, toCam).normalized;
            float breathe = 0.92f + 0.08f * Mathf.Sin(c.t * Tau * 0.25f);

            // the whole-frame bloom: one big soft warm-white sprite between the camera and the stage (additive), rising
            // fast and easing away; no second pulse
            float bloom = Smooth(0f, 0.3f, c.t) * (1f - Smooth(0.3f, 1.5f, c.t));
            if (bloom > 0.003f)
            {
                Vector3 q = Vector3.Lerp(a + Vector3.up * 0.15f, c.camPos, 0.6f);
                float d2 = Mathf.Max(0.05f, (c.camPos - q).magnitude);
                b.Sprite(q, d2 * 3.2f, A(SaulFx.WarmWhite, 0.55f * bloom), DGFxPaint.SoftDot, 0f, true);
                b.Sprite(q, d2 * 2.0f, A(SaulFx.Gold, 0.28f * bloom), DGFxPaint.SoftDot, 0f, true);
            }
            if (env <= 0.003f) return;

            // the pool of light on the road (gold under, warm white over)
            b.Sprite(g, 0.46f * (0.96f + 0.04f * breathe), A(SaulFx.Gold, 0.34f * env * breathe), DGFxPaint.GlowDisc, c.t * 0.05f, false, FxFace.Ground);
            b.Sprite(g + Vector3.up * 0.001f, 0.28f, A(SaulFx.WarmWhite, 0.30f * env), DGFxPaint.SoftDot, 0f, true, FxFace.Ground);

            // the column, just behind him (away from the camera), straight down from far above
            Vector3 foot = g - toCam * 0.06f;
            Vector3 top = new Vector3(a.x, Top, a.z) - toCam * 0.14f;
            Beam(b, top, foot, side, 0f, WTop * 1.0f, WBottom, A(SaulFx.Gold, 0.26f * env * breathe), false);
            for (int i = 0; i < 3; i++)
            {
                float f = i - 1f;                                                     // -1, 0, +1
                float pulse = 0.65f + 0.35f * Mathf.Sin(Tau * (0.18f * c.t + 0.31f * i));
                Beam(b, top, foot, side, f * 0.7f, WTop * 0.55f, WBottom * 0.55f, A(i == 1 ? SaulFx.Amber : SaulFx.Gold, 0.20f * env * pulse), false);
            }
            Beam(b, top, foot, side, 0f, WTop * 0.35f, WBottom * 0.40f, A(SaulFx.WarmWhite, 0.30f * env * breathe), true);

            // the halo behind him, so the light rims his shape (backlight); wide and soft
            Vector3 mid = a + Vector3.up * 0.20f - toCam * 0.10f;
            b.Sprite(mid, 0.62f, 0.70f, A(SaulFx.Gold, 0.24f * env * breathe), DGFxPaint.SoftDot, 0f, false, FxFace.Camera);
            b.Sprite(mid, 0.36f, 0.44f, A(SaulFx.WarmWhite, 0.16f * env), DGFxPaint.SoftDot, 0f, true, FxFace.Camera);

            // slow gold motes falling inside the column (nothing crosses the face band; they stand behind the node)
            for (int i = 0; i < Motes; i++)
            {
                float period = Mathf.Lerp(3.4f, 5.2f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float u = ph - Mathf.Floor(ph);
                int k = i * 31 + Mathf.FloorToInt(ph);
                float y = Mathf.Lerp(0.85f, 0.01f, u);
                float lat = FxRand.Signed(c.seed, k, 2) * 0.115f + 0.012f * Mathf.Sin(u * 6f + i);
                if (Mathf.Abs(lat) < 0.09f && y > FaceLo && y < FaceHi) continue;
                Vector3 p = new Vector3(a.x, y, a.z) + side * lat - toCam * Mathf.Lerp(0.03f, 0.08f, FxRand.H(c.seed, k, 3));
                float life = Mathf.Sin(Mathf.PI * u) * env;
                bool tw = i % 3 == 0;
                b.Sprite(p, tw ? 0.030f : 0.016f, A(i % 2 == 0 ? SaulFx.Gold : SaulFx.Amber, 0.9f * life),
                         tw ? DGFxPaint.Sparkle : DGFxPaint.SoftDot, c.t * 0.6f + i, false);
                b.Sprite(p, tw ? 0.018f : 0.009f, A(SaulFx.WarmWhite, life), DGFxPaint.SoftDot, 0f, true);
            }
        }

        /// <summary>One vertical ribbon from top to foot (f = lateral position across the column, -1..1; widths are full
        /// widths at the top and at the foot).</summary>
        static void Beam(FxBatch b, Vector3 top, Vector3 foot, Vector3 side, float f, float wTop, float wBottom, Color col, bool add)
        {
            var r = b.Ribbon(DGFxPaint.Streak, add);
            const int pts = 6;
            for (int k = 0; k < pts; k++)
            {
                float s = k / (float)(pts - 1);
                Vector3 axis = Vector3.Lerp(top, foot, s);
                float half = Mathf.Lerp(WTop, WBottom, s) * 0.5f;
                r.Add(axis + side * (f * half), Mathf.Lerp(wTop, wBottom, s), col);
            }
        }
    }

    // ------------------------------------------------------------------ S08: the scales fall from Saul's eyes
    /// <summary>
    /// Eight tiny pale silver flakes fall from Saul's eyes (node = saul.head; 1.6 s). At the start a small warm sparkle burst
    /// (a soft warm glow that is gone by 0.4 s and five gold sparkles flying out and fading by 0.55 s). The flakes leave
    /// the two eyes one after another (every ≈ 0.09 s, from 0.05 s), drift outward to the side and drop 0.10-0.14 in
    /// 0.85 s, turning slowly; each glints once (a small warm star) at the middle of its fall and fades out before it
    /// has fallen 0.14, long before the ground. They start a touch in front of the eyes but move out and down at once, so
    /// after 0.5 s none of them is in front of the eyes. Dark-ink outline (atlas Pebble cell) so they read on skin (F4).
    /// Gentle, never a medical picture. The last flake is gone by 1.55 s.
    /// </summary>
    public sealed class ScalesFall : FxDef
    {
        public override string Id => "scales_fall";
        public override float DefaultDur => 1.6f;
        public override bool Follow => true;

        const int N = 8;
        const float Every = 0.09f, Start = 0.05f, Life = 0.85f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0f, 0.15f);
            if (env <= 0) return;
            Vector3 o = c.anchor;
            Vector3 toCam = (c.camPos - o); toCam.y = 0;
            toCam = toCam.sqrMagnitude > 1e-6f ? toCam.normalized : new Vector3(0, 0, 1);
            Vector3 eyes = o + Vector3.up * 0.012f + toCam * 0.03f;

            // the warm sparkle burst at the start
            float k0 = Sat(c.t / 0.55f);
            if (c.t < 0.55f)
            {
                float glow = Smooth(0f, 0.08f, c.t) * (1f - Smooth(0.08f, 0.4f, c.t));
                b.Sprite(eyes + toCam * 0.01f, 0.13f, A(SaulFx.Gold, 0.55f * glow * env), DGFxPaint.SoftDot, 0f, true);
                for (int i = 0; i < 5; i++)
                {
                    float ang = Tau * (i + 0.5f * FxRand.H(c.seed, i, 0)) / 5f + 0.4f;
                    float r = 0.025f + 0.06f * OutCubic(k0);
                    Vector3 p = eyes + c.camRight * (Mathf.Cos(ang) * r) + c.camUp * (Mathf.Sin(ang) * r * 0.8f);
                    b.Sprite(p, 0.024f * (1f - k0) + 0.006f, A(i % 2 == 0 ? SaulFx.WarmWhite : SaulFx.Gold, (1f - k0) * env),
                             DGFxPaint.Sparkle, ang + c.t * 2f, true);
                }
            }

            // the flakes
            for (int i = 0; i < N; i++)
            {
                float age = c.t - (Start + Every * i);
                if (age <= 0f || age >= Life) continue;
                float u = age / Life;
                float sgn = i % 2 == 0 ? -1f : 1f;                                       // left eye, right eye
                float ex = sgn * Mathf.Lerp(0.016f, 0.022f, FxRand.H(c.seed, i, 1));    // eye position across the face
                float outward = sgn * Mathf.Lerp(0.05f, 0.09f, FxRand.H(c.seed, i, 2)) * OutCubic(u);  // drifts out to the side
                float fall = Mathf.Lerp(0.10f, 0.14f, FxRand.H(c.seed, i, 3)) * (u * u * 0.6f + u * 0.4f);   // speeds up a little
                float sway = 0.006f * Mathf.Sin(u * 7f + i * 1.7f);
                Vector3 p = eyes + c.camRight * (ex + outward + sway) - c.camUp * fall + toCam * (0.012f * (1f - u));
                float alpha = Sat(u / 0.12f) * (1f - Smooth(0.7f, 1f, u)) * env;       // gone before it reaches the ground
                float size = 0.020f * Mathf.Lerp(0.8f, 1.2f, FxRand.H(c.seed, i, 4));
                float rot = Tau * FxRand.H(c.seed, i, 5) + u * 3.5f * (i % 2 == 0 ? 1f : -1f);
                b.Sprite(p, size * 1.3f, size * 0.8f, A(SaulFx.Silver, alpha), DGFxPaint.Pebble, rot, false, FxFace.Camera);
                // one small glint in the middle of the fall
                float gl = Smooth(0.35f, 0.5f, u) * (1f - Smooth(0.5f, 0.68f, u));
                if (gl > 0.01f)
                    b.Sprite(p + c.camUp * (0.004f), 0.026f * gl + 0.006f, A(SaulFx.Glint, gl * env), DGFxPaint.Sparkle, rot * 0.5f, true);
            }
        }
    }
}
