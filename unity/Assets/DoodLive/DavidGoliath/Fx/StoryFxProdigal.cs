// The prodigal son (story pack #6, docs/prodigal/FX.md) effects. Same engine as the earlier packs: every effect is a pure
// function of (time, anchor, camera, seed) drawn by DGFxInstance, played through DGFx.Play(id, at, dur) and registered in
// FxLibrary after Exodus (an existing id is never replaced).
// New ids: coins_spray party_lights famine_haze run_dust music_notes lamps_flames.
// Reused unchanged: sparkle heart_glow golden_rays night sunset_glow (lamp_flame too, but it lights one point only, so the
// S11 lamps use lamps_flames: every `lampsFlame*` empty of the set, found by ProdigalStage in StoryFxProdigalRuntime.cs).
// famine_haze is a stage tint like Ruth's night: it posts a StoryTint request (drawn by StoryTintStage) and survives the
// director's BeginAt fast-forward the same way (EndSeek replays it with the time that is left; nothing to wire).
// Only managed UnityEngine value types are used here (no engine calls), so the off-Unity preview harness runs it.
// Child-friendly rules as before: no flash, no strobe, nothing bright over a face; the famine is dry and dusty, not scary.
using System.Collections.Generic;
using UnityEngine;
using static DoodLive.DavidGoliath.FxMath;

namespace DoodLive.DavidGoliath
{
    /// <summary>Prodigal registry, palette and CONTRACT §6 layout fallbacks (docs/prodigal/CONTRACT.md §6, §8).</summary>
    public static class ProdigalFx
    {
        internal static FxDef[] Defs => new FxDef[]
        {
            new PrCoinsSpray(), new PrPartyLights(), new PrFamineHaze(), new PrRunDust(), new PrMusicNotes(), new PrLampsFlames(),
        };

        /// <summary>Stage-local positions of every `lampsFlame*` empty of the set (filled by ProdigalStage; the preview fills
        /// it by hand). Empty: lamps_flames lights its anchor, or the CONTRACT §6 fallback points when the anchor is at the
        /// set origin.</summary>
        public static readonly List<Vector3> Lamps = new List<Vector3>(8);
        /// <summary>Set by lamps_flames every frame it draws; ProdigalStage rescans for lamp empties while it is set and the
        /// list is empty (a set that arrives after the effect started).</summary>
        public static bool LampsWanted;
        /// <summary>Name prefix of the lamp empties (CONTRACT §6 `lampsFlame`; Blender duplicates add .001 / _001).</summary>
        public const string LampPrefix = "lampsFlame";

        /// <summary>party_lights also posts a soft dusk tint (DESIGN.md: "the tavern glows ... in a dusk light").</summary>
        public static bool PartyDusk = true;

        // CONTRACT §6 positions (node origins sit on the ground at the object centre, as the earlier set scripts build them)
        internal static readonly Vector3 Tavern = new Vector3(0.40f, 0f, -0.47f);
        internal static readonly Vector3 House = new Vector3(-0.38f, 0f, -0.47f);
        /// <summary>Lamp fallback: three oil lamps on the feast table (-0.38, -0.16, top ~0.05) and two lanterns at the door.</summary>
        internal static readonly Vector3[] LampFallback =
        {
            new Vector3(-0.45f, 0.055f, -0.165f), new Vector3(-0.38f, 0.055f, -0.150f), new Vector3(-0.31f, 0.055f, -0.165f),
            new Vector3(-0.45f, 0.135f, -0.355f), new Vector3(-0.31f, 0.135f, -0.355f),
        };

        /// <summary>The anchor, or the fallback when the anchor sits at the stage / set origin (node missing).</summary>
        internal static Vector3 NodeOr(Vector3 p, Vector3 fallback) =>
            p.x * p.x + p.z * p.z < 0.03f * 0.03f && Mathf.Abs(p.y) < 0.03f ? fallback : p;

        internal static bool AtOrigin(Vector3 p) => p.x * p.x + p.z * p.z < 0.03f * 0.03f && Mathf.Abs(p.y) < 0.03f;

        // docs/prodigal/DESIGN.md demo colours + light colours (sRGB)
        internal static readonly Color CoinGold = new Color32(0xF2, 0xC2, 0x30, 255);
        internal static readonly Color CoinLight = new Color32(0xFF, 0xE4, 0x8A, 255);
        internal static readonly Color CoinDeep = new Color32(0xC9, 0x93, 0x22, 255);
        internal static readonly Color WarmWhite = new Color32(0xFF, 0xF1, 0xC8, 255);
        internal static readonly Color LampOrange = new Color32(0xFF, 0x9A, 0x3C, 255);
        internal static readonly Color LampPool = new Color32(0xFF, 0xC8, 0x6A, 255);
        internal static readonly Color Wire = new Color32(0x5A, 0x48, 0x3A, 255);
        internal static readonly Color Road = new Color32(0xE9, 0xD9, 0xB6, 255);      // pale dirt road
        internal static readonly Color Soil = new Color32(0xC9, 0xAE, 0x7E, 255);
        internal static readonly Color SoilDark = new Color32(0x9A, 0x6A, 0x43, 255);  // field soil
        internal static readonly Color Tawny = new Color32(0xD9, 0xB7, 0x7A, 255);     // far hills
        internal static readonly Color HazeVeil = new Color32(0xE8, 0xD2, 0xA4, 255);
        internal static readonly Color DustMote = new Color32(0xC8, 0xA2, 0x66, 255);
        internal static readonly Color HotHigh = new Color32(0xF4, 0xE6, 0xC4, 255);
        internal static readonly Color HotMid = new Color32(0xF5, 0xDA, 0xA4, 255);
        internal static readonly Color HotLow = new Color32(0xF0, 0xC8, 0x8A, 255);
        internal static readonly Color HotSun = new Color32(0xFF, 0xF6, 0xD8, 255);

        /// <summary>Bulb colours for the party strings (crayon set, no deep red next to a face).</summary>
        internal static readonly Color[] Bulbs =
        {
            new Color32(0xFF, 0xC9, 0x3C, 255), new Color32(0xF4, 0x9A, 0xC1, 255), new Color32(0x4B, 0xA3, 0xE3, 255),
            new Color32(0xF5, 0x9A, 0x2F, 255), new Color32(0x4D, 0xB3, 0x7A, 255), new Color32(0xB9, 0x9F, 0xE8, 255),
            new Color32(0xE8, 0x55, 0x3D, 255),
        };
        /// <summary>Music note colours: warm, readable on the night-blue courtyard.</summary>
        internal static readonly Color[] Notes =
        {
            new Color32(0xFF, 0xC9, 0x3C, 255), new Color32(0xF4, 0x9A, 0xC1, 255), new Color32(0x8E, 0xD3, 0xF5, 255),
            new Color32(0xF5, 0x9A, 0x2F, 255), new Color32(0x9F, 0xE0, 0x9A, 255), new Color32(0xFF, 0xF1, 0xC8, 255),
        };

        /// <summary>Multiply tints (sRGB) at full strength + rim colours (for shaders that read _DoodStageRim).</summary>
        public static Color FamineTint = new Color(1.00f, 0.88f, 0.70f, 1f);
        public static Color FamineRim = new Color(0.40f, 0.30f, 0.14f, 1f);
        public static Color PartyDuskTint = new Color(0.86f, 0.78f, 0.88f, 1f);
        public static Color PartyDuskRim = new Color(0.35f, 0.22f, 0.30f, 1f);

        // party strings (offsets from the tavern origin; CONTRACT §6: footprint 0.30 x 0.14, awning h <= 0.22, front z <= -0.36)
        public static float TavernHalfWidth = 0.155f, TavernFrontDz = 0.118f, StringY = 0.205f;

        internal static Color InkCol() => DesignTokens.Ink;
        internal static Color SoftInk() => DesignTokens.InkSoft;
    }

    // ------------------------------------------------------------------ S04: a handful of coins flung up high
    public sealed class PrCoinsSpray : FxDef
    {
        public override string Id => "coins_spray";
        public override float DefaultDur => 1.6f;
        public override bool Follow => false;   // the fountain starts at the hand and lives in the world

        const int N = 12;
        const float G = 3.0f, R = 0.0045f;      // gravity (art/s^2), rest height of a lying coin

        public override void Emit(FxCtx c, FxBatch b)
        {
            Vector3 o = c.start;
            float fadeAll = Sat((c.dur - c.t) / 0.35f);
            Vector3 fwd = c.ToCamFlat(o);

            // a little twinkle at the hand as the coins leave it
            if (c.t < 0.4f)
                for (int i = 0; i < 4; i++)
                {
                    float k = Sat((c.t - 0.04f * i) / 0.32f);
                    if (k <= 0 || k >= 1) continue;
                    var p = o + Vector3.up * (0.01f + 0.05f * k) + c.camRight * (0.025f * FxRand.Signed(c.seed, i, 40));
                    b.Sprite(p, 0.018f * (1 - k) + 0.006f, A(ProdigalFx.WarmWhite, (1 - k)), DGFxPaint.Sparkle, k * 2f + i, true);
                }

            for (int i = 0; i < N; i++)
            {
                float t0 = 0.02f + 0.22f * FxRand.H(c.seed, i, 0);
                float tau = c.t - t0;
                if (tau < 0) continue;
                float ang = Tau * FxRand.H(c.seed, i, 1);
                float hs = Mathf.Lerp(0.08f, 0.26f, FxRand.H(c.seed, i, 2));
                Vector3 v = Flat(ang, hs) + fwd * 0.07f;
                v.y = Mathf.Lerp(0.85f, 1.15f, FxRand.H(c.seed, i, 3));
                Vector3 p = o; bool rest = false;
                // up to two bounces, then the coin lies flat and slides to a stop
                float left = tau;
                for (int bounce = 0; bounce < 3; bounce++)
                {
                    float h0 = Mathf.Max(0f, p.y - R);
                    float tl = (v.y + Mathf.Sqrt(Mathf.Max(0f, v.y * v.y + 2f * G * h0))) / G;   // time to touch down
                    if (left < tl)
                    {   // still in the air
                        p += new Vector3(v.x, 0, v.z) * left;
                        p.y += v.y * left - 0.5f * G * left * left;
                        break;
                    }
                    p += new Vector3(v.x, 0, v.z) * tl; p.y = R;
                    float impact = G * tl - v.y;   // downward speed at touch-down
                    left -= tl;
                    float up = impact * (bounce == 0 ? 0.32f : 0.22f);
                    if (bounce == 2 || up < 0.12f)
                    {   // settles: a short slide, then it lies still
                        rest = true;
                        p += new Vector3(v.x, 0, v.z) * (0.45f * 0.08f * OutCubic(left / 0.25f));
                        break;
                    }
                    v = new Vector3(v.x * 0.45f, up, v.z * 0.45f);
                }
                if (p.y < R) p.y = R;

                float size = Mathf.Lerp(0.021f, 0.026f, FxRand.H(c.seed, i, 4));
                float alpha = fadeAll;
                // shadow on the page, smaller and fainter the higher the coin
                float hgt = Mathf.Max(0f, p.y - R);
                b.Sprite(FxCtx.Ground(p, 0.0025f), size * (1.1f - Sat(hgt * 3f) * 0.5f), A(ProdigalFx.SoftInk(), 0.20f * alpha * (1 - Sat(hgt * 3f))),
                         DGFxPaint.SoftDot, 0, false, FxFace.Ground);
                if (rest)
                {   // lying flat on the ground: ink-outlined gold disc with a lighter middle
                    float rot = Tau * FxRand.H(c.seed, i, 5);
                    b.Sprite(FxCtx.Ground(p, R), size, size * 0.96f, A(ProdigalFx.CoinGold, alpha), DGFxPaint.Puff, rot, false, FxFace.Ground);
                    b.Sprite(FxCtx.Ground(p, R + 0.0006f), size * 0.58f, A(ProdigalFx.CoinLight, alpha), DGFxPaint.ConfettiDot, rot, false, FxFace.Ground);
                    float gl = Sat(Mathf.Sin(c.t * 3.1f + i * 1.7f) * 3f - 2.2f);   // an occasional slow glint
                    if (gl > 0) b.Sprite(FxCtx.Ground(p, R + 0.004f) + c.camUp * 0.003f, 0.016f * gl, A(Color.white, gl * alpha), DGFxPaint.Sparkle, 0.4f, true);
                }
                else
                {   // spinning in the air: the disc narrows edge-on, a glint when it faces the camera
                    float spin = Tau * FxRand.H(c.seed, i, 6) + tau * Mathf.Lerp(10f, 18f, FxRand.H(c.seed, i, 7));
                    float face = Mathf.Abs(Mathf.Cos(spin));
                    float w = size * Mathf.Max(0.16f, face);
                    float tilt = 0.5f * FxRand.Signed(c.seed, i, 8);
                    b.Sprite(p, w, size, A(face > 0.35f ? ProdigalFx.CoinGold : ProdigalFx.CoinDeep, alpha), DGFxPaint.Puff, tilt, false, FxFace.Camera);
                    if (face > 0.45f)
                        b.Sprite(p + (c.camPos - p).normalized * 0.001f, w * 0.58f, size * 0.58f, A(ProdigalFx.CoinLight, alpha), DGFxPaint.ConfettiDot, tilt, false, FxFace.Camera);
                    float glint = Sat((face - 0.86f) / 0.14f);
                    if (glint > 0)
                        b.Sprite(p + c.camUp * (size * 0.2f) + c.camRight * (size * 0.15f), 0.020f * glint, A(Color.white, glint * alpha),
                                 DGFxPaint.Sparkle, 0.3f, true);
                }
            }
        }
    }

    // ------------------------------------------------------------------ S04: coloured string lights and confetti at the tavern
    public sealed class PrPartyLights : FxDef
    {
        public override string Id => "party_lights";
        public override float DefaultDur => 20f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.0f, 1.2f);
            if (ProdigalFx.PartyDusk) StoryTint.Request(c.seed, ProdigalFx.PartyDuskTint, 0.75f * env, ProdigalFx.PartyDuskRim);
            if (env <= 0) return;
            Vector3 o = ProdigalFx.NodeOr(c.start, ProdigalFx.Tavern); o.y = 0f;
            float hw = ProdigalFx.TavernHalfWidth, fz = o.z + ProdigalFx.TavernFrontDz, y = ProdigalFx.StringY;

            // the tavern glows: a warm pool on the ground in front and a soft warm wash behind the strings
            b.Sprite(new Vector3(o.x, 0.004f, fz + 0.07f), 0.44f, 0.24f, A(ProdigalFx.LampPool, 0.30f * env), DGFxPaint.SoftDot, 0, false, FxFace.Ground);
            b.Sprite(new Vector3(o.x, 0.10f, fz - 0.02f), 0.42f, 0.24f, A(ProdigalFx.LampPool, 0.12f * env), DGFxPaint.SoftDot, 0, true, FxFace.Camera);

            // two swags of bulbs: along the awning front, and a lower one from the left column out to the market stall
            Swag(c, b, new Vector3(o.x - hw, y, fz + 0.004f), new Vector3(o.x + hw, y, fz + 0.004f), 0.036f, 11, 0, env);
            Swag(c, b, new Vector3(o.x - hw + 0.01f, y - 0.045f, fz + 0.012f), new Vector3(o.x + 0.14f, y - 0.08f, fz + 0.035f), 0.028f, 8, 3, env);

            // confetti specks bobbing and fluttering down in front of the tavern
            const int n = 20;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(4.0f, 6.0f, FxRand.H(c.seed, i, 10));
                float ph = c.t / period + FxRand.H(c.seed, i, 11);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                int k = i * 13 + cyc;
                var p = new Vector3(o.x + hw * 1.15f * FxRand.Signed(c.seed, k, 12),
                                    Mathf.Lerp(0.09f, 0.21f, FxRand.H(c.seed, k, 13)) - 0.08f * a,
                                    fz + Mathf.Lerp(0.02f, 0.18f, FxRand.H(c.seed, k, 14)));
                p += c.camRight * (0.010f * Mathf.Sin(c.t * 2.3f + i)) + Vector3.up * (0.006f * Mathf.Sin(c.t * 3.1f + i * 1.3f));
                float life = Sat(a * 6f) * Sat((1 - a) * 5f);
                var col = ProdigalFx.Bulbs[(i + cyc) % ProdigalFx.Bulbs.Length];
                if (i % 3 == 0)
                    b.Sprite(p, 0.0075f, A(col, life * env), DGFxPaint.ConfettiDot, 0, false);
                else
                {
                    float flip = Mathf.Abs(Mathf.Sin(c.t * 4.2f + i * 0.9f));   // the paper turns over as it flutters
                    b.Sprite(p, 0.010f, 0.006f * Mathf.Max(0.25f, flip), A(col, life * env), DGFxPaint.ConfettiRect,
                             c.t * 1.3f + i, false, FxFace.Camera);
                }
            }
        }

        /// <summary>One sagging string of bulbs from a to b: a thin dark wire and n bulbs (crayon dot + soft additive glow) that
        /// brighten in a slow travelling wave (0.78..1, never off: no strobe).</summary>
        static void Swag(FxCtx c, FxBatch b, Vector3 a, Vector3 e, float sag, int n, int colOff, float env)
        {
            const int pts = 9;
            float sway = 0.0025f * Mathf.Sin(c.t * 1.1f + a.x * 9f);
            var wire = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k < pts; k++)
            {
                float f = k / (float)(pts - 1);
                wire.Add(Hang(a, e, sag, f, sway), 0.0022f, A(ProdigalFx.Wire, 0.75f * env));
            }
            for (int i = 0; i < n; i++)
            {
                float f = (i + 0.5f) / n;
                Vector3 p = Hang(a, e, sag, f, sway) + Vector3.down * 0.007f;
                float bright = 0.78f + 0.22f * Mathf.Sin(c.t * 1.6f - f * 7f + colOff);
                var col = ProdigalFx.Bulbs[(i + colOff) % ProdigalFx.Bulbs.Length];
                b.Sprite(p, 0.055f * bright, A(col, 0.30f * bright * env), DGFxPaint.SoftDot, 0, true);
                b.Sprite(p, 0.012f, A(Color.Lerp(col, Color.white, 0.25f * bright), env), DGFxPaint.ConfettiDot, 0, false);
                b.Sprite(p + c.camUp * 0.0015f, 0.005f, A(Color.white, 0.8f * bright * env), DGFxPaint.SoftDot, 0, true);
            }
        }

        static Vector3 Hang(Vector3 a, Vector3 e, float sag, float f, float sway)
        {
            var p = Vector3.Lerp(a, e, f);
            float s = 4f * f * (1 - f);
            p.y -= sag * s;
            p.z += sway * s;
            return p;
        }
    }

    // ------------------------------------------------------------------ S05-S07: famine (stage tint, survives fast-forward)
    public sealed class PrFamineHaze : FxDef
    {
        public override string Id => "famine_haze";
        public override float DefaultDur => 40f;
        public override bool Follow => false;

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 1.6f, 1.4f);
            StoryTint.Request(c.seed, ProdigalFx.FamineTint, 0.9f * env, ProdigalFx.FamineRim);
            if (env <= 0) return;

            // bleached hot sky behind the backdrop and a pale white-hot sun
            RuthFx.SkyBand(b, 0.60f, 0.22f, ProdigalFx.HotHigh, 0.60f * env, 0.008f, c.t);
            RuthFx.SkyBand(b, 0.45f, 0.20f, ProdigalFx.HotMid, 0.62f * env, 0.010f, c.t);
            RuthFx.SkyBand(b, 0.31f, 0.20f, ProdigalFx.HotLow, 0.66f * env, 0.008f, c.t);
            var sun = new Vector3(0.30f, 0.56f, RuthFx.SkyZ + 0.02f);
            b.Sprite(sun, 0.34f, A(ProdigalFx.HotSun, 0.45f * env), DGFxPaint.SoftDot, 0, true);
            b.Sprite(sun + Vector3.forward * 0.005f, 0.075f, A(ProdigalFx.HotSun, 0.9f * env), DGFxPaint.Puff, 0, false);

            // washed-out distance: depth-tested veils behind the actors fade the backdrop, tavern and field toward dust
            b.Sprite(new Vector3(0.12f, 0.13f, -0.50f), 1.45f, 0.46f, A(ProdigalFx.HazeVeil, 0.36f * env), DGFxPaint.SoftDot, 0, false, FxFace.Camera);
            b.Sprite(new Vector3(0.24f, 0.07f, -0.30f), 0.95f, 0.22f, A(ProdigalFx.HazeVeil, 0.20f * env), DGFxPaint.SoftDot, 0, false, FxFace.Camera);

            // low dust banks drifting west across the far country
            for (int i = 0; i < 8; i++)
            {
                float period = Mathf.Lerp(9f, 13f, FxRand.H(c.seed, i, 0));
                float ph = c.t / period + FxRand.H(c.seed, i, 1);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                var p = new Vector3(Mathf.Lerp(0.66f, -0.12f, a), 0.035f + 0.012f * FxRand.H(c.seed, i * 9 + cyc, 2),
                                    Mathf.Lerp(-0.42f, 0.16f, FxRand.H(c.seed, i * 9 + cyc, 3)));
                float life = Mathf.Sin(Mathf.PI * a);
                b.Sprite(p, Mathf.Lerp(0.30f, 0.46f, FxRand.H(c.seed, i, 4)), Mathf.Lerp(0.09f, 0.13f, FxRand.H(c.seed, i, 5)),
                         A(ProdigalFx.HazeVeil, 0.24f * life * env), DGFxPaint.SoftDot, 0, false, FxFace.Camera);
            }

            // heat shimmer: faint wavy light lines just above the hot ground
            for (int i = 0; i < 4; i++)
            {
                float z = Mathf.Lerp(-0.34f, 0.12f, (i + 0.5f) / 4f);
                float yb = 0.022f + 0.012f * i;
                float pulse = 0.6f + 0.4f * Mathf.Sin(c.t * 1.7f + i * 2.1f);
                var r = b.Ribbon(DGFxPaint.Ribbon, false);
                const int pts = 10;
                for (int k = 0; k < pts; k++)
                {
                    float f = k / (float)(pts - 1);
                    float x = Mathf.Lerp(0.04f, 0.60f, f);
                    float yy = yb + 0.0045f * Mathf.Sin(x * 38f + c.t * 3.2f + i) + 0.002f * Mathf.Sin(x * 91f - c.t * 5.1f);
                    r.Add(new Vector3(x, yy, z + 0.02f * Mathf.Sin(f * 3f + i)), 0.010f, A(ProdigalFx.WarmWhite, 0.11f * pulse * env * Mathf.Sin(Mathf.PI * f)));
                }
            }

            // dust motes drifting on the dry wind, bobbing
            const int n = 28;
            for (int i = 0; i < n; i++)
            {
                float period = Mathf.Lerp(5f, 8f, FxRand.H(c.seed, i, 20));
                float ph = c.t / period + FxRand.H(c.seed, i, 21);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                int k = i * 11 + cyc;
                var p = new Vector3(Mathf.Lerp(0.62f, -0.18f, FxRand.H(c.seed, k, 22)) - 0.16f * a,
                                    Mathf.Lerp(0.015f, 0.24f, FxRand.H(c.seed, k, 23) * FxRand.H(c.seed, k, 24)) + 0.012f * Mathf.Sin(c.t * 1.9f + i),
                                    Mathf.Lerp(-0.44f, 0.18f, FxRand.H(c.seed, k, 25)));
                float life = Mathf.Sin(Mathf.PI * a);
                float s = Mathf.Lerp(0.006f, 0.013f, FxRand.H(c.seed, i, 26));
                b.Sprite(p, s, A(i % 3 == 0 ? ProdigalFx.Tawny : ProdigalFx.DustMote, 0.75f * life * env), DGFxPaint.Dust, c.t * 0.6f + i, false);
            }

            // now and then a gust lifts a little dust off the ground (left to right puffs, as dust_road)
            for (int i = 0; i < 6; i++)
            {
                float period = Mathf.Lerp(3.2f, 4.4f, FxRand.H(c.seed, i, 30));
                float ph = c.t / period + FxRand.H(c.seed, i, 31);
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                var p = new Vector3(Mathf.Lerp(0.10f, 0.58f, FxRand.H(c.seed, i * 5 + cyc, 32)) - 0.10f * a, 0.012f + 0.03f * a,
                                    Mathf.Lerp(-0.30f, 0.16f, FxRand.H(c.seed, i * 5 + cyc, 33)));
                b.Sprite(p, Mathf.Lerp(0.03f, 0.075f, a), A(ProdigalFx.Soil, 0.45f * Mathf.Sin(Mathf.PI * a) * env), DGFxPaint.Dust, i + a, false);
            }
        }
    }

    // ------------------------------------------------------------------ S09: dust kicked up behind the running father
    public sealed class PrRunDust : FxDef
    {
        public override string Id => "run_dust";
        public override float DefaultDur => 2.8f;

        const float Interval = 0.075f, Life = 0.75f, MinSpeed = 0.06f;

        public override void Emit(FxCtx c, FxBatch b)
        {
            int last = Mathf.FloorToInt(c.t / Interval);
            int first = Mathf.Max(0, Mathf.CeilToInt((c.t - Life) / Interval));
            float fadeAll = Sat((c.dur - c.t) / 0.3f);
            for (int k = first; k <= last; k++)
            {
                float ts = k * Interval, age = c.t - ts;
                if (age < 0 || age >= Life) continue;
                Vector3 p0 = c.track.Sample(ts), pp = c.track.Sample(ts - 0.12f);
                Vector3 vel = (p0 - pp) / 0.12f; vel.y = 0;
                float speed = vel.magnitude;
                if (speed < MinSpeed) continue;
                Vector3 dir = vel / speed;
                Vector3 side = new Vector3(-dir.z, 0, dir.x);
                float strength = Sat((speed - MinSpeed) / 0.25f) * fadeAll;
                float a = age / Life;
                float foot = (k % 2 == 0 ? 1f : -1f) * 0.013f;
                Vector3 bs = new Vector3(p0.x, 0f, p0.z) + side * foot - dir * 0.018f;
                // the puff rolls back and up, grows, thins out
                Vector3 p = bs - dir * (0.055f * OutCubic(a * 1.6f)) + side * (foot * 0.8f * a) + Vector3.up * (0.010f + 0.030f * OutCubic(a));
                float size = Mathf.Lerp(0.030f, 0.080f, OutCubic(a)) * Mathf.Lerp(0.8f, 1.15f, FxRand.H(c.seed, k, 0));
                float alpha = Mathf.Pow(1 - a, 1.2f) * strength;
                if (k % 3 == 0)
                    b.Sprite(p, size * 1.25f, A(ProdigalFx.Road, 0.55f * alpha), DGFxPaint.SoftDot, 0, false);
                else
                    b.Sprite(p, size, A(Color.Lerp(ProdigalFx.Road, ProdigalFx.Soil, FxRand.H(c.seed, k, 1) * 0.6f), 0.80f * alpha),
                             DGFxPaint.Dust, FxRand.H(c.seed, k, 2) * Tau + a * 0.8f, false);
                // two grains flicked back in little arcs
                if (age < 0.4f)
                    for (int g = 0; g < 2; g++)
                    {
                        Vector3 v0 = -dir * Mathf.Lerp(0.10f, 0.18f, FxRand.H(c.seed, k, 3 + g)) + side * (0.06f * FxRand.Signed(c.seed, k, 5 + g))
                                   + Vector3.up * Mathf.Lerp(0.22f, 0.32f, FxRand.H(c.seed, k, 7 + g));
                        Vector3 q = Ballistic(bs + Vector3.up * 0.004f, v0, 2.4f, 0.5f, age);
                        if (q.y < 0.002f) continue;
                        b.Sprite(q, 0.0055f, A(ProdigalFx.SoilDark, strength * Sat((0.4f - age) / 0.12f)), DGFxPaint.ConfettiDot, 0, false);
                    }
            }
        }
    }

    // ------------------------------------------------------------------ S11-S13: music notes floating up from the house
    public sealed class PrMusicNotes : FxDef
    {
        public override string Id => "music_notes";
        public override float DefaultDur => 40f;
        public override bool Follow => false;

        // emitters, offsets from the house origin: the door (front face z ~ -0.37), the two windows, the roof edge
        static readonly Vector3[] From =
        {
            new Vector3(0.00f, 0.10f, 0.108f), new Vector3(-0.08f, 0.13f, 0.105f), new Vector3(0.08f, 0.13f, 0.105f),
            new Vector3(-0.04f, 0.215f, 0.06f), new Vector3(0.05f, 0.215f, 0.05f),
        };

        public override void Emit(FxCtx c, FxBatch b)
        {
            float env = Env(c.t, c.dur, 0.8f, 1.2f);
            if (env <= 0) return;
            Vector3 o = ProdigalFx.NodeOr(c.start, ProdigalFx.House); o.y = 0f;
            const int slots = 9;
            for (int i = 0; i < slots; i++)
            {
                float period = Mathf.Lerp(3.4f, 4.2f, FxRand.H(c.seed, i, 0));
                float tt = c.t - period * (i / (float)slots) * 0.9f;   // stagger the first notes, then a steady stream
                if (tt < 0) continue;
                float ph = tt / period;
                float a = ph - Mathf.Floor(ph);
                int cyc = (int)Mathf.Floor(ph);
                int k = i * 7 + cyc;
                Vector3 e = o + From[(int)(FxRand.H(c.seed, k, 1) * From.Length) % From.Length];
                float sw = FxRand.Signed(c.seed, k, 2);
                // up, drifting toward the viewer and the courtyard, swaying side to side
                Vector3 p = e + Vector3.up * (0.20f * a) + new Vector3(0.05f * sw * a, 0, 0.12f * a)
                          + c.camRight * (0.016f * Mathf.Sin(a * 7f + i));
                float grow = OutBack(a / 0.14f);
                float alpha = Sat(a / 0.08f) * Sat((1 - a) / 0.3f) * env;
                float h = 0.030f * Mathf.Lerp(0.85f, 1.15f, FxRand.H(c.seed, k, 3)) * grow;
                float rot = 0.28f * Mathf.Sin(c.t * 2.1f + i * 1.9f);
                var col = ProdigalFx.Notes[(int)(FxRand.H(c.seed, k, 4) * ProdigalFx.Notes.Length) % ProdigalFx.Notes.Length];
                int kind = (int)(FxRand.H(c.seed, k, 5) * 3f);   // 0 quarter, 1 eighth (flag), 2 two beamed eighths
                Note(c, b, p, h, rot, col, kind, alpha);
            }
        }

        /// <summary>A crayon music note facing the camera: ink-outlined coloured head, ink stem, flag or beam, soft glow behind.</summary>
        static void Note(FxCtx c, FxBatch b, Vector3 p, float h, float rot, Color col, int kind, float alpha)
        {
            if (alpha <= 0.003f || h <= 1e-4f) return;
            float cs = Mathf.Cos(rot), sn = Mathf.Sin(rot);
            Vector3 R = c.camRight * cs + c.camUp * sn, U = -c.camRight * sn + c.camUp * cs;
            Vector3 toCam = (c.camPos - p).normalized;
            Color ink = Color.Lerp(col, ProdigalFx.InkCol(), 0.4f);   // coloured stems stay readable on the night blue
            float span = kind == 2 ? 0.62f * h : 0f;
            Vector3 mid = p + R * (span * 0.5f) + U * (0.35f * h);
            b.Sprite(mid - toCam * 0.004f, 1.9f * h + span, A(col, 0.38f * alpha), DGFxPaint.SoftDot, 0, true);
            int heads = kind == 2 ? 2 : 1;
            for (int j = 0; j < heads; j++)
            {
                Vector3 hd = p + R * (j * span) + U * (j * 0.06f * h);
                b.Sprite(hd, 0.54f * h, 0.40f * h, A(col, alpha), DGFxPaint.Puff, rot + 0.38f, false, FxFace.Camera);
                // stem from the right of the head up to the top
                Vector3 stem = hd + R * (0.23f * h) + U * (0.48f * h) + toCam * 0.0008f;
                b.Sprite(stem, 0.09f * h, 0.92f * h, A(ink, alpha), DGFxPaint.ConfettiRect, rot, false, FxFace.Camera);
            }
            Vector3 top = p + R * (0.23f * h) + U * (0.92f * h) + toCam * 0.001f;
            if (kind == 1)
                b.Sprite(top + R * (0.12f * h) - U * (0.12f * h), 0.08f * h, 0.40f * h, A(ink, alpha), DGFxPaint.ConfettiRect, rot + 0.75f, false, FxFace.Camera);
            else if (kind == 2)
                b.Sprite(top + R * (span * 0.5f) + U * (0.03f * h), span + 0.08f * h, 0.13f * h, A(ink, alpha), DGFxPaint.ConfettiRect,
                         rot + 0.10f, false, FxFace.Camera);
        }
    }

    // ------------------------------------------------------------------ S11-S13: every lamp and lantern lit (one call)
    public sealed class PrLampsFlames : FxDef
    {
        public override string Id => "lamps_flames";
        public override float DefaultDur => 24f;
        public override bool Follow => false;

        static readonly List<Vector3> pts = new List<Vector3>(8);

        public override void Emit(FxCtx c, FxBatch b)
        {
            ProdigalFx.LampsWanted = true;
            float env = Env(c.t, c.dur, 0.6f, 0.8f);
            if (env <= 0) return;
            pts.Clear();
            if (ProdigalFx.Lamps.Count > 0) pts.AddRange(ProdigalFx.Lamps);
            else if (!ProdigalFx.AtOrigin(c.start)) pts.Add(c.start);
            else pts.AddRange(ProdigalFx.LampFallback);
            int n = Mathf.Min(pts.Count, 12);
            float share = 1f / Mathf.Sqrt(Mathf.Max(1, n));   // several pools overlap: keep their sum close to one lamp's
            for (int i = 0; i < n; i++) Lamp(c, b, pts[i], i, env, share);
        }

        // Ruth's lamp_flame look (same colours and flame), with the ground pool shared out between the lamps
        static void Lamp(FxCtx c, FxBatch b, Vector3 o, int i, float env, float share)
        {
            float t = c.t + 10f * FxRand.H(c.seed, i, 9);
            float fl = 0.93f + 0.04f * Mathf.Sin(t * 8.3f) + 0.03f * Mathf.Sin(t * 13.9f + 1.1f) + 0.02f * Mathf.Sin(t * 23.1f);
            Vector3 away = (o - c.camPos).normalized;
            float lift = Sat(o.y / 0.12f);   // hanging lanterns throw a wider, fainter pool
            b.Sprite(FxCtx.Ground(o, 0.004f), Mathf.Lerp(0.30f, 0.36f, lift) * (0.97f + 0.03f * fl),
                     A(ProdigalFx.LampPool, 0.48f * share * env * fl * Mathf.Lerp(1f, 0.7f, lift)), DGFxPaint.SoftDot, 0, false, FxFace.Ground);
            b.Sprite(FxCtx.Ground(o, 0.005f), 0.14f, A(ProdigalFx.LampOrange, 0.30f * share * env * fl), DGFxPaint.SoftDot, 0, true, FxFace.Ground);
            b.Sprite(o + away * 0.02f, 0.16f * fl, A(ProdigalFx.LampPool, 0.30f * env), DGFxPaint.SoftDot, 0, false);
            b.Sprite(o + Vector3.up * 0.01f, 0.08f * fl, A(Sun, 0.55f * env), DGFxPaint.SoftDot, 0, true);
            Tongue(b, c, o, t, 0.032f * fl, 0.016f, ProdigalFx.LampOrange, Sun, 0f, env);
            Tongue(b, c, o, t, 0.018f * fl, 0.0085f, Sun, ProdigalFx.WarmWhite, 2.1f, env);
            // now and then a tiny spark
            float period = Mathf.Lerp(1.6f, 2.6f, FxRand.H(c.seed, i, 0));
            float ph = c.t / period + FxRand.H(c.seed, i, 1);
            float a = ph - Mathf.Floor(ph);
            if (a < 0.5f)
            {
                float k = a / 0.5f;
                Vector3 q = o + c.camRight * (0.006f * Mathf.Sin(k * 6f + i)) + Vector3.up * (0.03f + 0.05f * k);
                b.Sprite(q, 0.008f * (1 - k) + 0.003f, A(Sun, (1 - k) * env), DGFxPaint.Sparkle, k * 3f, false);
            }
        }

        static void Tongue(FxBatch b, FxCtx c, Vector3 bs, float t, float height, float width, Color baseCol, Color tipCol, float phase, float alpha)
        {
            const int n = 6;
            var r = b.Ribbon(DGFxPaint.Ribbon, false);
            for (int k = 0; k < n; k++)
            {
                float f = k / (float)(n - 1);
                float sway = (0.6f * Mathf.Sin(t * 5.5f + phase - f * 3f) + 0.4f * Mathf.Sin(t * 9.7f + phase - f * 4f)) * 0.004f * f * f;
                Vector3 p = bs + c.camRight * sway + Vector3.up * (height * f - 0.003f);
                float w = width * Mathf.Sin(Mathf.PI * Mathf.Lerp(0.35f, 1f, f));
                r.Add(p, Mathf.Max(w, 0.0008f), A(Color.Lerp(baseCol, tipCol, f), alpha));
            }
        }
    }
}
