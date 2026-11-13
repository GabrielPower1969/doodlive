// Core data for the David & Goliath effects: context, anchor track, sprite batch, mesh builder, maths.
// Only managed UnityEngine value types (Vector3, Vector2, Color, Mathf basics) are used here, no engine calls,
// so the same code is exercised by the off-Unity preview harness (see FX.md "How it was verified").
// Space: everything is in STAGE-LOCAL art-width units (CONTRACT §2): 1.0 = art width, y up, page at y = 0,
// +Z toward the viewer. The runtime parents each effect under DGFx.Stage, so the stage scale does the rest.
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive.DavidGoliath
{
    public enum FxFace : byte
    {
        Camera = 0,   // billboard facing the camera
        Ground = 1,   // lies flat on the page (XZ plane), rot about +Y
    }

    public struct FxSprite
    {
        public Vector3 pos;
        public float w, h, rot;
        public Color col;          // sRGB, straight alpha
        public int cell;           // DGFxPaint cell id
        public FxFace face;
        public bool add;           // additive (light) instead of alpha-blended (crayon)
    }

    public struct FxRibbonPoint
    {
        public Vector3 pos;
        public float width;
        public Color col;
    }

    public sealed class FxRibbon
    {
        public int cell;
        public bool add;
        public readonly List<FxRibbonPoint> points = new List<FxRibbonPoint>(32);
        public void Add(Vector3 p, float width, Color c) => points.Add(new FxRibbonPoint { pos = p, width = width, col = c });
    }

    /// <summary>What an effect draws this frame. Draw order inside each blend mode = call order.</summary>
    public sealed class FxBatch
    {
        public readonly List<FxSprite> sprites = new List<FxSprite>(128);
        public readonly List<FxRibbon> ribbons = new List<FxRibbon>(8);
        readonly List<FxRibbon> pool = new List<FxRibbon>(8);
        // ribbons and sprites interleave in call order; this records the order
        public readonly List<int> order = new List<int>(160);   // >= 0: sprite index, < 0: ~ribbon index

        public void Clear()
        {
            sprites.Clear(); order.Clear();
            foreach (var r in ribbons) { r.points.Clear(); pool.Add(r); }
            ribbons.Clear();
        }

        public void Sprite(Vector3 pos, float size, Color col, int cell, float rot = 0f, bool add = false, FxFace face = FxFace.Camera)
            => Sprite(pos, size, size, col, cell, rot, add, face);

        public void Sprite(Vector3 pos, float w, float h, Color col, int cell, float rot, bool add, FxFace face)
        {
            if (col.a <= 0.003f || w <= 1e-5f || h <= 1e-5f) return;
            order.Add(sprites.Count);
            sprites.Add(new FxSprite { pos = pos, w = w, h = h, rot = rot, col = col, cell = cell, face = face, add = add });
        }

        public FxRibbon Ribbon(int cell, bool add)
        {
            FxRibbon r;
            if (pool.Count > 0) { r = pool[pool.Count - 1]; pool.RemoveAt(pool.Count - 1); } else r = new FxRibbon();
            r.cell = cell; r.add = add;
            order.Add(~ribbons.Count);
            ribbons.Add(r);
            return r;
        }
    }

    /// <summary>Anchor positions over time (stage-local), for trails.</summary>
    public sealed class FxTrack
    {
        const int Cap = 256;
        readonly float[] ts = new float[Cap];
        readonly Vector3[] ps = new Vector3[Cap];
        int head, count;

        public void Clear() { head = 0; count = 0; }

        public void Add(float t, Vector3 p)
        {
            if (count > 0 && t <= ts[(head + Cap - 1) % Cap] + 1e-5f) { ps[(head + Cap - 1) % Cap] = p; return; }
            ts[head] = t; ps[head] = p;
            head = (head + 1) % Cap;
            if (count < Cap) count++;
        }

        public int Count => count;

        /// <summary>Position at time t (clamped to the recorded range, linear in between).</summary>
        public Vector3 Sample(float t)
        {
            if (count == 0) return Vector3.zero;
            int newest = (head + Cap - 1) % Cap;
            if (t >= ts[newest]) return ps[newest];
            for (int k = 1; k < count; k++)
            {
                int a = (head + Cap - 1 - k) % Cap, b = (a + 1) % Cap;
                if (t >= ts[a])
                {
                    float span = ts[b] - ts[a];
                    float f = span > 1e-6f ? (t - ts[a]) / span : 1f;
                    return Vector3.LerpUnclamped(ps[a], ps[b], f);
                }
            }
            return ps[(head + Cap - count) % Cap];
        }
    }

    /// <summary>Per-frame inputs to an effect. All vectors stage-local, unit directions normalised.</summary>
    public sealed class FxCtx
    {
        public float t;            // seconds since Play
        public float dur;          // requested duration (timeline "dur")
        public int seed;
        public Vector3 anchor;     // the 'at' transform now
        public Vector3 start;      // the 'at' transform when the effect started
        public Vector3 camPos;     // camera position
        public Vector3 camRight = Vector3.right, camUp = Vector3.up;
        public readonly FxTrack track = new FxTrack();

        public float N => dur > 1e-4f ? Mathf.Clamp01(t / dur) : 1f;
        public static Vector3 Ground(Vector3 p, float lift = 0.003f) => new Vector3(p.x, lift, p.z);

        /// <summary>Horizontal unit vector from p toward the camera (falls back to +Z, the viewer side).</summary>
        public Vector3 ToCamFlat(Vector3 p)
        {
            var d = camPos - p; d.y = 0;
            float m = d.magnitude;
            return m > 1e-4f ? d / m : new Vector3(0, 0, 1);
        }
    }

    /// <summary>Deterministic per-particle randomness: same (seed, i, k) -> same value every frame.</summary>
    public static class FxRand
    {
        public static float H(int seed, int i, int k)
        {
            unchecked
            {
                uint h = (uint)seed * 2654435761u ^ (uint)i * 2246822519u ^ (uint)k * 3266489917u;
                h ^= h >> 15; h *= 2246822519u; h ^= h >> 13; h *= 3266489917u; h ^= h >> 16;
                return (h & 0xFFFFFF) / 16777216f;
            }
        }
        public static float Range(int seed, int i, int k, float a, float b) => a + (b - a) * H(seed, i, k);
        public static float Signed(int seed, int i, int k) => H(seed, i, k) * 2f - 1f;
    }

    public static class FxMath
    {
        public const float Tau = 6.2831853f;
        public static float Sat(float x) => x < 0 ? 0 : x > 1 ? 1 : x;
        public static float Smooth(float e0, float e1, float x) { float t = Sat((x - e0) / (e1 - e0)); return t * t * (3 - 2 * t); }
        public static float OutCubic(float x) { x = 1 - Sat(x); return 1 - x * x * x; }
        public static float InCubic(float x) { x = Sat(x); return x * x * x; }
        public static float OutBack(float x)
        {
            x = Sat(x); const float c1 = 1.70158f, c3 = c1 + 1;
            float m = x - 1; return 1 + c3 * m * m * m + c1 * m * m;
        }
        /// <summary>Fade-in over 'fin' seconds, fade-out over the last 'fout' seconds of 'dur'.</summary>
        public static float Env(float t, float dur, float fin, float fout)
        {
            float a = fin > 0 ? Sat(t / fin) : 1f;
            float b = fout > 0 ? Sat((dur - t) / fout) : 1f;
            return Mathf.Min(a, b);
        }
        public static Color A(Color c, float a) { c.a *= Sat(a); return c; }
        public static Vector3 Flat(float ang, float r) => new Vector3(Mathf.Cos(ang) * r, 0, Mathf.Sin(ang) * r);

        /// <summary>Linear-drag ballistic motion (k = drag 1/s, g = gravity art/s^2 downward).</summary>
        public static Vector3 Ballistic(Vector3 p0, Vector3 v0, float g, float k, float t)
        {
            if (k < 1e-4f) return p0 + v0 * t + Vector3.down * (0.5f * g * t * t);
            float e = Mathf.Exp(-k * t), f = (1 - e) / k;
            return p0 + v0 * f + Vector3.down * (g / k * (t - f));
        }
    }

    /// <summary>
    /// Turns a batch into triangles: two index lists (0 = alpha-blended crayon, 1 = additive light).
    /// Pure maths so the preview harness can use exactly the same quads as the device.
    /// </summary>
    public static class FxMeshBuilder
    {
        public static void Build(FxBatch b, FxCtx c, Vector2[] cellMin, Vector2[] cellSize,
                                 List<Vector3> verts, List<Vector2> uvs, List<Color> cols,
                                 List<int> triAlpha, List<int> triAdd)
        {
            verts.Clear(); uvs.Clear(); cols.Clear(); triAlpha.Clear(); triAdd.Clear();
            foreach (int o in b.order)
            {
                if (o >= 0) Quad(b.sprites[o], c, cellMin, cellSize, verts, uvs, cols, b.sprites[o].add ? triAdd : triAlpha);
                else Strip(b.ribbons[~o], c, cellMin, cellSize, verts, uvs, cols, b.ribbons[~o].add ? triAdd : triAlpha);
            }
        }

        static void Quad(in FxSprite s, FxCtx c, Vector2[] mn, Vector2[] sz, List<Vector3> v, List<Vector2> uv, List<Color> col, List<int> tri)
        {
            Vector3 right, up;
            float cs = Mathf.Cos(s.rot), sn = Mathf.Sin(s.rot);
            if (s.face == FxFace.Ground)
            {
                right = new Vector3(cs, 0, -sn); up = new Vector3(sn, 0, cs);   // +Z is "up" in the texture
            }
            else
            {
                right = c.camRight * cs + c.camUp * sn;
                up = -c.camRight * sn + c.camUp * cs;
            }
            right *= s.w * 0.5f; up *= s.h * 0.5f;
            int i0 = v.Count;
            v.Add(s.pos - right - up); v.Add(s.pos + right - up); v.Add(s.pos + right + up); v.Add(s.pos - right + up);
            Vector2 m = mn[s.cell], z = sz[s.cell];
            uv.Add(m); uv.Add(new Vector2(m.x + z.x, m.y)); uv.Add(m + z); uv.Add(new Vector2(m.x, m.y + z.y));
            for (int k = 0; k < 4; k++) col.Add(s.col);
            tri.Add(i0); tri.Add(i0 + 2); tri.Add(i0 + 1);
            tri.Add(i0); tri.Add(i0 + 3); tri.Add(i0 + 2);
        }

        static void Strip(FxRibbon r, FxCtx c, Vector2[] mn, Vector2[] sz, List<Vector3> v, List<Vector2> uv, List<Color> col, List<int> tri)
        {
            var p = r.points;
            int n = p.Count;
            if (n < 2) return;
            Vector2 m = mn[r.cell], z = sz[r.cell];
            int i0 = v.Count;
            Vector3 lastSide = c.camUp;
            for (int k = 0; k < n; k++)
            {
                Vector3 a = p[k > 0 ? k - 1 : 0].pos, b = p[k < n - 1 ? k + 1 : n - 1].pos;
                Vector3 tan = b - a;
                Vector3 view = c.camPos - p[k].pos;
                Vector3 side = Vector3.Cross(tan, view);
                float mag = side.magnitude;
                side = mag > 1e-7f ? side / mag : lastSide;   // degenerate (still anchor): keep previous side
                lastSide = side;
                Vector3 off = side * (p[k].width * 0.5f);
                float u = m.x + z.x * (k / (float)(n - 1));
                v.Add(p[k].pos - off); uv.Add(new Vector2(u, m.y)); col.Add(p[k].col);
                v.Add(p[k].pos + off); uv.Add(new Vector2(u, m.y + z.y)); col.Add(p[k].col);
            }
            for (int k = 0; k < n - 1; k++)
            {
                int a = i0 + k * 2;
                tri.Add(a); tri.Add(a + 1); tri.Add(a + 3);
                tri.Add(a); tri.Add(a + 3); tri.Add(a + 2);
            }
        }
    }
}
