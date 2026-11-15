// Joseph (story pack, docs/joseph/FX.md) effects. Same engine as the earlier packs: every effect is a pure function of
// (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered in FxLibrary
// after the earlier packs (an existing id is never replaced), through the manifest `fx.class` = JosephFx.
// New: dream_cloud only. Reused unchanged: sparkle, steam, tension_dim, coins_spray, prayer_glow, night, zzz,
// golden_rays, famine_haze, sweat, heart_glow, confetti.
// Only managed UnityEngine value types are used (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no flash, no strobe, nothing bright or opaque over the picture it frames.
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Joseph registry and palette (docs/joseph/CONTRACT.md §8, DESIGN.md §4).</summary>
    public static class JosephFx
    {
        internal static FxDef[] Defs => new FxDef[] { new DreamCloud() };

        /// <summary>Half width and half height (art units, in the screen plane) of the empty window the ring leaves free
        /// round the node: the dream panels are 0.22-0.24 wide. The puffs sit just outside it. The effect only gets the
        /// node's position, so Integration may overwrite these two when it can read the panel's bounds.</summary>
        public static float RingRx = 0.175f, RingRy = 0.140f;

        /// <summary>Weight of a puff / star at ring angle `sinAng` (sin of its angle, +1 = top, -1 = bottom): 1 above
        /// the middle, fading to 0 by 35 % of the way down, so the lower arc of the ring stays empty.</summary>
        internal static float OpenBelow(float sinAng)
        {
            float w = Mathf.Clamp01((sinAng + 0.35f) / 0.35f);
            return w * w * (3f - 2f * w);
        }

        internal static readonly Color CloudWhite = new Color32(0xFF, 0xFC, 0xF4, 255), CloudLilac = new Color32(0xC9, 0xB9, 0xE6, 255),
                                       CloudShade = new Color32(0x84, 0x72, 0xB6, 255), StarGold = new Color32(0xFF, 0xD2, 0x5E, 255),
                                       Halo = new Color32(0xFF, 0xE6, 0xA8, 255);
    }

    // ------------------------------------------------------------------ dream panels: a ring of clouds and stars
    /// <summary>
    /// A frame of dream. 12 cloud puffs (a lilac shadow underneath, three white lobes, a bright top) stand on an ellipse
    /// around the node and turn slowly (one turn in 36 s), each breathing a little; 7 stars twinkle between and just
    /// outside them; the whole ring bobs 0.008. The puffs stand 0.02 BEHIND the node (the panel's depth test hides
    /// whatever overlaps), and the inside of the ellipse (JosephFx.RingRx / RingRy) stays empty, so it never covers the
    /// panel. A faint gold halo lies behind the ring. Fades in 0.8 s, out 0.8 s.
    /// The ring is open at the bottom (2026-11-15 review: the lower puffs hid Pharaoh's and Joseph's faces under the
    /// panels): a puff or star fades out as it turns below the panel's middle (JosephFx.OpenBelow), so nothing of the
    /// effect hangs lower than about a third of the ring's height under the node, and the people under a panel stay clear.
    /// </summary>
    public sealed class DreamCloud : FxDef
    {
        public override string Id => "dream_cloud";
        public override float DefaultDur => 6f;

        const int Puffs = 12, Stars = 7;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 0.8f);
            env = env * env * (3f - 2f * env);
            if (env <= 0) return;
            Vector3 away = -c.ToCamFlat(c.anchor);
            Vector3 o = c.anchor + away * 0.02f + Vector3.up * (0.008f * Mathf.Sin(c.t * Tau / 4.5f));
            Vector3 R = c.camRight, U = c.camUp;
            float rx = JosephFx.RingRx, ry = JosephFx.RingRy;

            // gold halo behind the ring (it frames the panel; the panel stays clear); raised and flattened so its lower
            // edge does not tint the faces under the panel
            b.Sprite(o + away * 0.004f + U * (0.35f * ry), 2f * (rx + 0.07f), 1.3f * (ry + 0.07f), A(JosephFx.Halo, 0.22f * env), DGFxPaint.GlowDisc, 0f, false, FxFace.Camera);

        
            float spin = c.t * Tau / 36f;
            var order = new float[Puffs]; var idx = new int[Puffs];
            for (int i = 0; i < Puffs; i++)
            {
                order[i] = Mathf.Sin(Tau * i / Puffs + spin); idx[i] = i;
                for (int j = i; j > 0 && order[j] > order[j - 1]; j--)             // insertion sort: top of the ring first
                { float f = order[j]; order[j] = order[j - 1]; order[j - 1] = f; int k = idx[j]; idx[j] = idx[j - 1]; idx[j - 1] = k; }
            }
            for (int j = 0; j < Puffs; j++)
            {
                int i = idx[j];
                float ang = Tau * i / Puffs + spin + 0.12f * FxRand.Signed(c.seed, i, 0);
                float breathe = 1f + 0.06f * Mathf.Sin(c.t * 0.9f + i * 1.9f);
                float s = Mathf.Lerp(0.050f, 0.070f, FxRand.H(c.seed, i, 1)) * breathe;
                float rr = 1f + 0.06f * FxRand.Signed(c.seed, i, 2);
                float open = JosephFx.OpenBelow(Mathf.Sin(ang));
                if (open <= 0.01f) continue;
                Vector3 p = o + R * (Mathf.Cos(ang) * (rx + 0.5f * s) * rr) + U * (Mathf.Sin(ang) * (ry + 0.5f * s) * rr);
                Puff(b, c, p, s * (0.6f + 0.4f * open), env * open, FxRand.H(c.seed, i, 3) > 0.5f ? 1f : -1f);
            }
            // stars between and outside the puffs
            for (int i = 0; i < Stars; i++)
            {
                float ang = Tau * (i + 0.5f + 0.25f * FxRand.Signed(c.seed, i, 10)) / Stars - spin * 0.6f;
                float rad = Mathf.Lerp(1.12f, 1.55f, FxRand.H(c.seed, i, 11));
                float open = JosephFx.OpenBelow(Mathf.Sin(ang));
                if (open <= 0.01f) continue;
                Vector3 p = o + R * (Mathf.Cos(ang) * (rx + 0.04f) * rad) + U * (Mathf.Sin(ang) * (ry + 0.04f) * rad) - c.ToCamFlat(c.anchor) * 0.012f;
                float tw = 0.5f + 0.5f * Mathf.Sin(c.t * Mathf.Lerp(1.4f, 2.6f, FxRand.H(c.seed, i, 12)) + Tau * FxRand.H(c.seed, i, 13));
                float sz = Mathf.Lerp(0.026f, 0.040f, FxRand.H(c.seed, i, 14)) * (0.8f + 0.3f * tw);
                b.Sprite(p, sz, A(JosephFx.StarGold, open * env * (0.7f + 0.3f * tw)), DGFxPaint.Star, 0.25f * Mathf.Sin(c.t * 0.7f + i), false);
                b.Sprite(p, sz * 1.9f, A(JosephFx.StarGold, open * 0.55f * env * tw), DGFxPaint.Sparkle, 0.785f * (i % 2), true);
            }
        }

        static void Puff(FxBatch b, FxCtx c, Vector3 p, float s, float env, float flip)
        {
            Vector3 R = c.camRight, U = Vector3.up;
            Vector3 q = p + U * (0.14f * s);
            Vector3 l0 = q - R * (flip * 0.44f * s) - U * (0.08f * s), l1 = q + R * (flip * 0.40f * s) - U * (0.12f * s), l2 = q + U * (0.06f * s);
            // a lilac crayon edge round the whole puff (so white on a pale picture still reads), then the white lobes
            b.Sprite(p - U * (0.22f * s), 2.8f * s, 1.3f * s, A(JosephFx.CloudShade, 0.50f * env), DGFxPaint.SoftDot, 0f, false, FxFace.Camera);
            b.Sprite(l0, 2.05f * s, A(JosephFx.CloudShade, 0.85f * env), DGFxPaint.SoftDot, 0f, false);
            b.Sprite(l1, 1.85f * s, A(JosephFx.CloudShade, 0.85f * env), DGFxPaint.SoftDot, 0f, false);
            b.Sprite(l2, 2.6f * s, A(JosephFx.CloudShade, 0.85f * env), DGFxPaint.SoftDot, 0f, false);
            b.Sprite(p - U * (0.10f * s), 2.1f * s, 1.2f * s, A(JosephFx.CloudLilac, 0.85f * env), DGFxPaint.SoftDot, 0f, false, FxFace.Camera);
            b.Sprite(l0, 1.65f * s, A(JosephFx.CloudWhite, env), DGFxPaint.SoftDot, 0f, false);
            b.Sprite(l1, 1.45f * s, A(JosephFx.CloudWhite, env), DGFxPaint.SoftDot, 0f, false);
            b.Sprite(l2, 2.1f * s, A(JosephFx.CloudWhite, env), DGFxPaint.SoftDot, 0f, false);
            b.Sprite(q + U * (0.10f * s), 1.4f * s, A(Color.white, 0.8f * env), DGFxPaint.SoftDot, 0f, false);
        }
    }
}
