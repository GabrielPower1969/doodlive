// Procedural crayon-on-paper sprite atlas for the David & Goliath effects (docs/david-goliath/FX.md).
// Pure C# (no UnityEngine) so it can be run and previewed outside Unity; DGFxRuntime turns it into a Texture2D.
// Every shape is a signed-distance field in cell space p in [-1, 1]^2 (bubble: x in [-2, 2]), filled with a
// waxy grain and, where it helps the paper look, a pencil-ink outline (DESIGN-DIRECTION ink #2B2118).
// Tinted cells are painted white so per-sprite vertex colours carry the crayon colour; the memory-bubble
// drawings (lion, bear, bubble) carry their own colours.
using System;

namespace DoodLive.DavidGoliath
{
    public static class DGFxPaint
    {
        public const int Size = 1024;

        // Cell ids. Rects are {x, y, w, h} in pixels, origin bottom-left (Texture2D.SetPixels order).
        public const int SoftDot = 0, Dust = 1, Star = 2, Sparkle = 3,
                         Ring = 4, ConfettiRect = 5, ConfettiDot = 6, Streak = 7,
                         Ribbon = 8, Pebble = 9, GlowDisc = 10, Puff = 11,
                         Lion = 12, Bear = 13, Bubble = 14;
        public const int CellCount = 15;

        public static readonly int[][] Cells =
        {
            new[] {   0, 768, 256, 256 }, new[] { 256, 768, 256, 256 }, new[] { 512, 768, 256, 256 }, new[] { 768, 768, 256, 256 },
            new[] {   0, 512, 256, 256 }, new[] { 256, 512, 256, 256 }, new[] { 512, 512, 256, 256 }, new[] { 768, 512, 256, 256 },
            new[] {   0, 256, 256, 256 }, new[] { 256, 256, 256, 256 }, new[] { 512, 256, 256, 256 }, new[] { 768, 256, 256, 256 },
            new[] {   0,   0, 256, 256 }, new[] { 256,   0, 256, 256 }, new[] { 512,   0, 512, 256 },
        };

        // Paper & Crayon palette (DESIGN-DIRECTION / DesignTokens), sRGB 0..1.
        static readonly float[] Ink = Hex(0x2B2118), Paper = Hex(0xFBF5E6), Orange = Hex(0xF59A2F), Sun = Hex(0xFFC93C),
                                Pink = Hex(0xF49AC1), Brown = Hex(0xA8693A), Tan = Hex(0xD9A066), White = { 1f, 1f, 1f };

        static float[] Hex(int rgb) => new[] { ((rgb >> 16) & 255) / 255f, ((rgb >> 8) & 255) / 255f, (rgb & 255) / 255f };

        /// <summary>RGBA, straight (not premultiplied) alpha, sRGB, row-major from the bottom row up.</summary>
        public static float[] Build()
        {
            var px = new float[Size * Size * 4];
            for (int id = 0; id < CellCount; id++) PaintCell(px, id);
            return px;
        }

        // ---------- noise ----------
        static float Hash(int x, int y, int s)
        {
            unchecked
            {
                uint h = (uint)x * 374761393u + (uint)y * 668265263u + (uint)s * 2246822519u;
                h = (h ^ (h >> 13)) * 1274126177u;
                h ^= h >> 16;
                return (h & 0xFFFFFF) / 16777216f;
            }
        }

        static float Value(float x, float y, int s)
        {
            int ix = (int)Math.Floor(x), iy = (int)Math.Floor(y);
            float fx = x - ix, fy = y - iy;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
            float a = Hash(ix, iy, s), b = Hash(ix + 1, iy, s), c = Hash(ix, iy + 1, s), d = Hash(ix + 1, iy + 1, s);
            return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
        }

        /// <summary>Wax grain: diagonal crayon strokes + paper tooth, around 0.62..1.</summary>
        static float Grain(int x, int y)
        {
            float streak = Value(x * 0.09f + y * 0.09f, (x - y) * 0.012f, 7);  // long diagonal strokes
            float tooth = Hash(x, y, 3);                                         // paper tooth speckle
            float g = 0.70f + 0.22f * streak + 0.12f * tooth;
            return g > 1f ? 1f : g;
        }

        // ---------- SDF helpers ----------
        static float Len(float x, float y) => (float)Math.Sqrt(x * x + y * y);
        static float Circle(float x, float y, float cx, float cy, float r) => Len(x - cx, y - cy) - r;
        static float Ellipse(float x, float y, float cx, float cy, float rx, float ry)
        {
            float dx = (x - cx) / rx, dy = (y - cy) / ry;
            return (Len(dx, dy) - 1f) * Math.Min(rx, ry);
        }
        static float Box(float x, float y, float hx, float hy, float r)
        {
            float qx = Math.Abs(x) - hx + r, qy = Math.Abs(y) - hy + r;
            return Len(Math.Max(qx, 0), Math.Max(qy, 0)) + Math.Min(Math.Max(qx, qy), 0) - r;
        }
        static float Star5(float x, float y, float r, float inner)
        {
            // polar star: radius alternates between r and r*inner, rounded by the cos blend
            double a = Math.Atan2(x, y);
            float k = (float)(0.5 + 0.5 * Math.Cos(a * 5));
            float rad = r * (inner + (1 - inner) * (float)Math.Pow(k, 1.6));
            return (Len(x, y) - rad) * 0.8f;
        }
        static float Smooth(float e0, float e1, float v)
        {
            float t = (v - e0) / (e1 - e0); t = t < 0 ? 0 : t > 1 ? 1 : t;
            return t * t * (3 - 2 * t);
        }
        static float Fill(float d, float aa) => 1f - Smooth(-aa, aa, d);
        static float Line(float d, float w, float aa) => 1f - Smooth(w - aa, w + aa, Math.Abs(d));

        // ---------- compositing ----------
        static void Over(float[] px, int i, float[] rgb, float a)
        {
            if (a <= 0) return;
            if (a > 1) a = 1;
            float da = px[i + 3], oa = a + da * (1 - a);
            if (oa <= 0) return;
            for (int k = 0; k < 3; k++) px[i + k] = (rgb[k] * a + px[i + k] * da * (1 - a)) / oa;
            px[i + 3] = oa;
        }

        static void PaintCell(float[] px, int id)
        {
            int[] c = Cells[id];
            int cx0 = c[0], cy0 = c[1], cw = c[2], ch = c[3];
            float half = ch * 0.5f;                       // 1 cell unit = half the cell height
            float aa = 1.5f / half;                       // ~1.5 px antialias
            for (int y = 0; y < ch; y++)
            for (int x = 0; x < cw; x++)
            {
                int gx = cx0 + x, gy = cy0 + y, i = (gy * Size + gx) * 4;
                float u = (x + 0.5f - cw * 0.5f) / half, v = (y + 0.5f - half) / half;
                float g = Grain(gx, gy);
                // keep a transparent 2 px border so mip-mapping never bleeds between cells
                if (x < 2 || y < 2 || x >= cw - 2 || y >= ch - 2) continue;
                PaintPixel(px, i, id, u, v, g, aa, gx, gy);
            }
        }

        static void PaintPixel(float[] px, int i, int id, float x, float y, float g, float aa, int gx, int gy)
        {
            float r = Len(x, y);
            switch (id)
            {
                case SoftDot:
                {   // soft radial light, additive glow
                    float a = (float)Math.Exp(-r * r * 4.2) * Smooth(1f, 0.85f, r);
                    Over(px, i, White, a);
                    break;
                }
                case Dust:
                {   // lumpy crayon cloud with a soft pencil rim
                    double ang = Math.Atan2(y, x);
                    float wob = 0.10f * Value((float)(ang * 2.2 + 10), 0.5f, 11) + 0.06f * (float)Math.Sin(ang * 5 + 1.3);
                    float d = r - (0.70f + wob);
                    Over(px, i, White, Fill(d, aa * 2) * g * 0.95f);
                    Over(px, i, new[] { 0.55f, 0.52f, 0.48f }, Line(d, 0.035f, aa) * g * 0.8f);
                    break;
                }
                case Star:
                {
                    float d = Star5(x, y + 0.04f, 0.86f, 0.46f);
                    Over(px, i, White, Fill(d, aa) * (0.82f + 0.18f * g));
                    Over(px, i, Ink, Line(d, 0.05f, aa));
                    Over(px, i, White, Fill(Circle(x, y, -0.18f, 0.22f, 0.10f), aa) * 0.9f);   // shine
                    break;
                }
                case Sparkle:
                {   // four-point twinkle: two thin crossed diamonds + core
                    float ax = Math.Abs(x), ay = Math.Abs(y);
                    float arm = Math.Max(Fill(ax * 6.5f + ay - 0.95f, aa * 3), Fill(ay * 6.5f + ax - 0.95f, aa * 3));
                    float core = (float)Math.Exp(-r * r * 18);
                    Over(px, i, White, Math.Max(arm, core));
                    break;
                }
                case Ring:
                {   // crayon stroke ring with a couple of lighter breaks (hand-drawn)
                    double ang = Math.Atan2(y, x);
                    float wob = 0.025f * (float)Math.Sin(ang * 3 + 0.7);
                    float d = r - (0.80f + wob);
                    float breaks = Smooth(0.18f, 0.45f, Value((float)(ang * 1.6 + 20), 3.3f, 5));
                    Over(px, i, White, Line(d, 0.075f, aa * 2) * g * (0.55f + 0.45f * breaks));
                    break;
                }
                case ConfettiRect:
                {
                    float d = Box(x, y, 0.82f, 0.50f, 0.10f);
                    Over(px, i, White, Fill(d, aa) * g);
                    Over(px, i, new[] { 0.3f, 0.3f, 0.3f }, Line(d, 0.06f, aa));   // tinted -> darker crayon edge
                    break;
                }
                case ConfettiDot:
                {
                    float d = r - 0.78f;
                    Over(px, i, White, Fill(d, aa) * g);
                    Over(px, i, new[] { 0.3f, 0.3f, 0.3f }, Line(d, 0.06f, aa));
                    break;
                }
                case Streak:
                case Ribbon:
                {   // strip: x = along (−1 head .. +1 tail), y = across; long crayon hatching along the strip
                    float across = 1f - Smooth(0.35f, 0.95f, Math.Abs(y));
                    float along = id == Streak ? Smooth(-1f, -0.4f, x) * Smooth(1f, 0.75f, x) : Smooth(1f, 0.2f, x);
                    float hatch = 0.72f + 0.28f * Value(gx * 0.02f, gy * 0.35f, 9);
                    Over(px, i, White, across * along * hatch);
                    break;
                }
                case Pebble:
                {
                    float d = Ellipse(x, y, 0, 0, 0.82f, 0.62f);
                    Over(px, i, White, Fill(d, aa) * g);
                    Over(px, i, Ink, Line(d, 0.07f, aa));
                    break;
                }
                case GlowDisc:
                {   // flat ground glow: soft ring + faint core
                    float ring = (float)Math.Exp(-Math.Pow((r - 0.62) / 0.20, 2));
                    float core = 0.45f * (float)Math.Exp(-r * r * 3.0);
                    Over(px, i, White, Math.Min(1f, ring + core) * Smooth(1f, 0.9f, r) * (0.85f + 0.15f * g));
                    break;
                }
                case Puff:
                {   // small thought-bubble dot
                    float d = r - 0.80f;
                    Over(px, i, Paper, Fill(d, aa) * 0.97f);
                    Over(px, i, Ink, Line(d, 0.08f, aa));
                    break;
                }
                case Bubble:
                {   // thought cloud, cell space x in [-2, 2], y in [-1, 1]
                    float d = BubbleSdf(x, y);
                    Over(px, i, Paper, Fill(d, aa) * 0.97f);
                    Over(px, i, Ink, Line(d, 0.035f, aa));
                    break;
                }
                case Lion: PaintLion(px, i, x, y, g, aa); break;
                case Bear: PaintBear(px, i, x, y, g, aa); break;
            }
        }

        static float BubbleSdf(float x, float y)
        {
            // scalloped cloud: union of lobes around an ellipse
            float d = Ellipse(x, y, 0, 0, 1.55f, 0.62f);
            const int lobes = 11;
            for (int k = 0; k < lobes; k++)
            {
                double a = k * Math.PI * 2 / lobes + 0.2;
                float lx = 1.50f * (float)Math.Cos(a), ly = 0.58f * (float)Math.Sin(a);
                d = Math.Min(d, Circle(x, y, lx, ly, k % 2 == 0 ? 0.36f : 0.30f));
            }
            return d;
        }

        static void Smile(float[] px, int i, float x, float y, float cx, float cy, float rad, float w, float aa)
        {
            float d = Circle(x, y, cx, cy, rad);
            if (y < cy) Over(px, i, Ink, Line(d, w, aa));
        }

        static void PaintLion(float[] px, int i, float x, float y, float g, float aa)
        {   // friendly cartoon lion face: scalloped mane, round face, rosy cheeks, smile
            double ang = Math.Atan2(y, x);
            float mane = Len(x, y) - (0.84f + 0.08f * (float)Math.Cos(ang * 12));
            Over(px, i, Orange, Fill(mane, aa) * (0.8f + 0.2f * g));
            Over(px, i, Ink, Line(mane, 0.035f, aa));
            for (int s = -1; s <= 1; s += 2)
            {
                float ear = Circle(x, y, 0.40f * s, 0.43f, 0.15f);
                Over(px, i, Sun, Fill(ear, aa)); Over(px, i, Ink, Line(ear, 0.03f, aa));
            }
            float face = Circle(x, y, 0, -0.04f, 0.55f);
            Over(px, i, Sun, Fill(face, aa) * (0.85f + 0.15f * g));
            Over(px, i, Ink, Line(face, 0.035f, aa));
            for (int s = -1; s <= 1; s += 2)
            {
                Over(px, i, Pink, Fill(Circle(x, y, 0.32f * s, -0.15f, 0.09f), aa) * 0.6f);
                Over(px, i, Ink, Fill(Circle(x, y, 0.19f * s, 0.08f, 0.07f), aa));
                Over(px, i, White, Fill(Circle(x, y, 0.19f * s - 0.02f, 0.11f, 0.022f), aa));
            }
            Over(px, i, Ink, Fill(Ellipse(x, y, 0, -0.12f, 0.10f, 0.065f), aa));
            Smile(px, i, x, y, -0.075f, -0.19f, 0.075f, 0.022f, aa);
            Smile(px, i, x, y, 0.075f, -0.19f, 0.075f, 0.022f, aa);
        }

        static void PaintBear(float[] px, int i, float x, float y, float g, float aa)
        {   // friendly cartoon bear face: round ears, muzzle, smile
            for (int s = -1; s <= 1; s += 2)
            {
                float ear = Circle(x, y, 0.50f * s, 0.50f, 0.22f);
                Over(px, i, Brown, Fill(ear, aa) * (0.85f + 0.15f * g)); Over(px, i, Ink, Line(ear, 0.035f, aa));
                Over(px, i, Tan, Fill(Circle(x, y, 0.50f * s, 0.50f, 0.11f), aa));
            }
            float head = Circle(x, y, 0, -0.02f, 0.68f);
            Over(px, i, Brown, Fill(head, aa) * (0.85f + 0.15f * g));
            Over(px, i, Ink, Line(head, 0.035f, aa));
            float snout = Ellipse(x, y, 0, -0.24f, 0.32f, 0.24f);
            Over(px, i, Tan, Fill(snout, aa)); Over(px, i, Ink, Line(snout, 0.025f, aa));
            for (int s = -1; s <= 1; s += 2)
            {
                Over(px, i, Pink, Fill(Circle(x, y, 0.40f * s, -0.14f, 0.09f), aa) * 0.55f);
                Over(px, i, Ink, Fill(Circle(x, y, 0.24f * s, 0.12f, 0.07f), aa));
                Over(px, i, White, Fill(Circle(x, y, 0.24f * s - 0.02f, 0.15f, 0.022f), aa));
            }
            Over(px, i, Ink, Fill(Ellipse(x, y, 0, -0.15f, 0.11f, 0.07f), aa));
            Smile(px, i, x, y, -0.07f, -0.27f, 0.07f, 0.02f, aa);
            Smile(px, i, x, y, 0.07f, -0.27f, 0.07f, 0.02f, aa);
        }
    }
}
