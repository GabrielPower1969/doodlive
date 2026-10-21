// Procedural rigged angel, C# port of web/angel.js. Built once by DoodLiveSetup into Angel.prefab.
// Replace with a Blender FBX later: keep the bone names and the UV rule and nothing else changes.
//
// Contract (CLAUDE.md):
//  - model units: 1 = art width; UV0 = page position: u = X + 0.5, v = Y / (1384 / 1128).
//  - bones: hips spine neck head shoulderL/R elbowL/R wristL/R wingL/R (+mid, tip).
// three.js is right-handed (+Z towards the viewer), Unity is left-handed: every z is negated and
// triangle winding reversed, so the model still faces the viewer (-Z) and UVs are unchanged.
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive
{
    public static class AngelBuilder
    {
        public const float AW = 1128, AH = 1384, ASPECT = AH / AW;

        public static readonly string[] BoneNames =
        {
            "hips", "spine", "neck", "head", "shoulderL", "elbowL", "wristL", "shoulderR", "elbowR", "wristR",
            "wingL", "wingLmid", "wingLtip", "wingR", "wingRmid", "wingRtip",
        };

        /// <summary>Line-art pixel (y down) to model space. zThree is the three.js depth (towards the viewer).</summary>
        public static Vector3 P(float x, float y, float zThree = 0) => new Vector3((x - AW / 2) / AW, (AH - y) / AW, -zThree);
        static float PX(float px) => px / AW;

        public class Parts
        {
            public GameObject root, rig;
            public Dictionary<string, Transform> bones = new Dictionary<string, Transform>();
            public Transform halo, cloud;
            public List<Mesh> meshes = new List<Mesh>();
        }

        /// <summary>Materials by part: robe, skin, hair, wing, gold, halo, cloud.</summary>
        public static Parts Build(Dictionary<string, Material> M)
        {
            var A = new Parts();
            A.root = new GameObject("Angel");
            A.rig = new GameObject("rig");
            A.rig.transform.SetParent(A.root.transform, false);
            var rest = new Dictionary<string, Vector3>();

            void Bone(string name, Vector3 at, string parent)
            {
                var t = new GameObject(name).transform;
                t.SetParent(parent == null ? A.rig.transform : A.bones[parent], false);
                t.localPosition = at - (parent == null ? Vector3.zero : rest[parent]);
                rest[name] = at; A.bones[name] = t;
            }
            // Skeleton (rest pose = drawing pose)
            Bone("hips", P(565, 930), null);
            Bone("spine", P(560, 640), "hips");
            Bone("neck", P(535, 500), "spine");
            Bone("head", P(527, 420), "neck");
            Bone("shoulderL", P(350, 610), "spine");
            Bone("elbowL", P(285, 830), "shoulderL");
            Bone("wristL", P(175, 975), "elbowL");
            Bone("shoulderR", P(760, 620), "spine");
            Bone("elbowR", P(840, 840), "shoulderR");
            Bone("wristR", P(955, 1010), "elbowR");
            Bone("wingL", P(420, 560, -0.06f), "spine");
            Bone("wingLmid", P(210, 330, -0.06f), "wingL");
            Bone("wingLtip", P(20, 30, -0.06f), "wingLmid");
            Bone("wingR", P(708, 560, -0.06f), "spine");
            Bone("wingRmid", P(918, 330, -0.06f), "wingR");
            Bone("wingRtip", P(1108, 30, -0.06f), "wingRmid");

            int n = 0;
            void Attach(Geo g, string mat, string bone)
            {
                var r = bone == null ? Vector3.zero : rest[bone];
                var mesh = g.ToMesh("part" + (n++) + "_" + mat, -r, frontUV: true);
                var go = new GameObject(mesh.name);
                go.transform.SetParent(bone == null ? A.rig.transform : A.bones[bone], false);
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                go.AddComponent<MeshRenderer>().sharedMaterial = M[mat];
                A.meshes.Add(mesh);
            }

            // --- body ---
            const float D = 0.55f; // depth/width ratio of the robe
            float cx(float x) => PX(x - 564);
            Attach(Geo.Loft(new[] {
                new Ring(P(0, 1384).y - 0.02f, cx(550), PX(285), PX(285) * D, 0, 0.05f),
                new Ring(P(0, 1250).y, cx(555), PX(255), PX(255) * D, 0, 0.045f),
                new Ring(P(0, 1100).y, cx(560), PX(220), PX(220) * D, 0, 0.03f),
                new Ring(P(0, 950).y, cx(565), PX(185), PX(185) * D, 0, 0.01f),
                new Ring(P(0, 930).y, cx(565), PX(178), PX(178) * D),
            }), "robe", "hips");
            Attach(Geo.Loft(new[] {
                new Ring(P(0, 945).y, cx(565), PX(190), PX(190) * D),
                new Ring(P(0, 915).y, cx(565), PX(190), PX(190) * D),
            }, 40), "robe", "hips"); // belt
            Attach(Geo.Loft(new[] {
                new Ring(P(0, 935).y, cx(565), PX(178), PX(178) * D),
                new Ring(P(0, 800).y, cx(563), PX(200), PX(200) * D * 0.95f),
                new Ring(P(0, 640).y, cx(560), PX(205), PX(205) * D * 0.85f),
                new Ring(P(0, 545).y, cx(555), PX(175), PX(175) * D * 0.75f),
                new Ring(P(0, 505).y, cx(545), PX(90), PX(90) * 0.8f),
                new Ring(P(0, 500).y, cx(545), PX(1), PX(1)),
            }), "robe", "spine");
            Attach(Geo.Limb(P(537, 520), P(532, 440), PX(32), PX(30)), "skin", "neck");

            // --- head ---
            Attach(Geo.Ellipsoid(P(522, 330, 0.03f), PX(66), PX(92), PX(70)), "skin", "head");
            Attach(Geo.Ellipsoid(P(522, 312, 0.075f), PX(10), PX(18), PX(12), 12, 8), "skin", "head"); // nose
            Attach(Geo.Ellipsoid(P(535, 300, -0.02f), PX(140), PX(150), PX(105)), "hair", "head");
            Attach(Geo.Ellipsoid(P(535, 225, 0f), PX(120), PX(70), PX(95)), "hair", "head");

            // --- arms (wide sleeves + skin forearms) ---
            Attach(Geo.Limb(P(350, 600), P(285, 840), PX(62), PX(78)), "robe", "shoulderL");
            Attach(Geo.Limb(P(285, 830), P(180, 975), PX(30), PX(24)), "skin", "elbowL");
            Attach(Geo.Ellipsoid(P(140, 1010, 0.01f), PX(55), PX(35), PX(18)), "skin", "wristL");
            Attach(Geo.Limb(P(760, 610), P(840, 850), PX(62), PX(78)), "robe", "shoulderR");
            Attach(Geo.Limb(P(840, 840), P(950, 1005), PX(30), PX(24)), "skin", "elbowR");
            Attach(Geo.Ellipsoid(P(965, 1035, 0.01f), PX(32), PX(45), PX(30)), "skin", "wristR");

            // --- trumpet in the right hand ---
            Attach(Geo.Limb(P(940, 1300), P(1072, 540), PX(9), PX(5)), "gold", "wristR");
            Attach(Geo.Limb(P(945, 1270), P(905, 1355), PX(12), PX(60)), "gold", "wristR");

            // --- wings: skinned to a 3-bone chain each ---
            int[,] outline = { { 20, 30 }, { 130, 95 }, { 240, 200 }, { 330, 330 }, { 390, 450 }, { 430, 560 }, { 410, 650 }, { 340, 740 },
                { 250, 800 }, { 170, 770 }, { 90, 710 }, { 15, 650 }, { 0, 430 }, { 30, 330 }, { 80, 250 }, { 40, 120 } };
            foreach (var side in new[] { "L", "R" })
            {
                var pts = new Vector2[outline.GetLength(0)];
                for (int i = 0; i < pts.Length; i++)
                {
                    var p = side == "L" ? P(outline[i, 0], outline[i, 1]) : P(AW - outline[i, 0], outline[i, 1]);
                    pts[i] = new Vector2(p.x, p.y);
                }
                // three: extrude depth 0.012 (+bevel) then translate z -0.066 => slab z in [-0.066, -0.046] (three)
                var g = Geo.Slab(pts, 0.066f - 0.02f, 0.066f).Tessellate(0.03f);
                var chain = new[] { A.bones["wing" + side], A.bones["wing" + side + "mid"], A.bones["wing" + side + "tip"] };
                Vector3 r0 = rest["wing" + side], r2 = rest["wing" + side + "tip"], axis = r2 - r0;
                var weights = new BoneWeight[g.pos.Count];
                for (int i = 0; i < g.pos.Count; i++)
                {
                    float s = Mathf.Clamp01(Vector3.Dot(g.pos[i] - r0, axis) / axis.sqrMagnitude);
                    if (s < 0.5f) { float w = s / 0.5f; weights[i] = new BoneWeight { boneIndex0 = 0, weight0 = 1 - w, boneIndex1 = 1, weight1 = w }; }
                    else { float w = (s - 0.5f) / 0.5f; weights[i] = new BoneWeight { boneIndex0 = 1, weight0 = 1 - w, boneIndex1 = 2, weight1 = w }; }
                }
                var mesh = g.ToMesh("wing" + side, Vector3.zero, frontUV: true);
                mesh.boneWeights = weights;
                var go = new GameObject("wing" + side + "_mesh");
                go.transform.SetParent(A.rig.transform, false);
                var smr = go.AddComponent<SkinnedMeshRenderer>();
                var bind = new Matrix4x4[3];
                for (int i = 0; i < 3; i++) bind[i] = chain[i].worldToLocalMatrix * go.transform.localToWorldMatrix;
                mesh.bindposes = bind;
                smr.sharedMesh = mesh; smr.bones = chain; smr.rootBone = chain[0];
                smr.sharedMaterial = M["wing"];
                smr.updateWhenOffscreen = true;
                A.meshes.Add(mesh);
            }

            // --- halo + cloud ---
            var halo = new GameObject("halo").transform;
            halo.SetParent(A.bones["head"], false);
            halo.localPosition = P(527, 175, -0.04f) - rest["head"];
            halo.localRotation = Quaternion.Euler(1.15f * Mathf.Rad2Deg, 0, 0); // three rotation.x = -1.15, mirrored
            var hm = Geo.Torus(0.115f, 0.009f, 12, 64).ToMesh("halo", Vector3.zero, frontUV: false);
            halo.gameObject.AddComponent<MeshFilter>().sharedMesh = hm;
            halo.gameObject.AddComponent<MeshRenderer>().sharedMaterial = M["halo"];
            A.meshes.Add(hm); A.halo = halo;

            var cloud = new GameObject("cloud").transform;
            cloud.SetParent(A.root.transform, false);
            var puff = Geo.Ellipsoid(Vector3.zero, 1, 1, 1, 16, 12).ToMesh("puff", Vector3.zero, frontUV: false);
            A.meshes.Add(puff);
            uint seed = 7;
            for (int i = 0; i < 22; i++)
            {
                float a = Rnd(ref seed) * Mathf.PI * 2, r = 0.1f + Rnd(ref seed) * 0.32f, s = 0.05f + Rnd(ref seed) * 0.06f;
                var p = new GameObject("puff" + i).transform;
                p.SetParent(cloud, false);
                p.localPosition = new Vector3(Mathf.Cos(a) * r * 1.2f, -0.03f + Rnd(ref seed) * 0.04f, -Mathf.Sin(a) * r * 0.6f);
                p.localScale = Vector3.one * s;
                p.gameObject.AddComponent<MeshFilter>().sharedMesh = puff;
                p.gameObject.AddComponent<MeshRenderer>().sharedMaterial = M["cloud"];
            }
            A.cloud = cloud;
            return A;
        }

        // mulberry32, same sequence as angel.js
        static float Rnd(ref uint a)
        {
            unchecked
            {
                a += 0x6d2b79f5;
                uint t = a;
                t = (t ^ (t >> 15)) * (1 | t);
                t = (t + (t ^ (t >> 7)) * (61 | t)) ^ t;
                return (t ^ (t >> 14)) / 4294967296f;
            }
        }

        public struct Ring
        {
            public float y, cx, rx, rz, cz, folds;
            public Ring(float y, float cx, float rx, float rz, float cz = 0, float folds = 0) { this.y = y; this.cx = cx; this.rx = rx; this.rz = rz; this.cz = cz; this.folds = folds; }
        }

        /// <summary>Triangle soup / indexed geometry in model space (Unity handedness).</summary>
        public class Geo
        {
            public List<Vector3> pos = new List<Vector3>();
            public List<int> idx = new List<int>();

            // Indices below are written in three.js (CCW, right-handed) order; ToMesh reverses them.
            public Mesh ToMesh(string name, Vector3 offset, bool frontUV)
            {
                var m = new Mesh { name = name };
                if (pos.Count > 65000) m.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
                var v = new Vector3[pos.Count];
                var uv = new Vector2[pos.Count];
                for (int i = 0; i < v.Length; i++)
                {
                    uv[i] = new Vector2(pos[i].x + 0.5f, pos[i].y / ASPECT); // the colouring rule
                    v[i] = pos[i] + offset;
                }
                var tri = new int[idx.Count];
                for (int i = 0; i < tri.Length; i += 3) { tri[i] = idx[i]; tri[i + 1] = idx[i + 2]; tri[i + 2] = idx[i + 1]; }
                m.vertices = v;
                if (frontUV) m.uv = uv;
                m.triangles = tri;
                m.RecalculateNormals();
                m.RecalculateBounds();
                return m;
            }

            /// <summary>Ellipse-section tube through rings. Open bottom; the last ring closes the top.</summary>
            public static Geo Loft(Ring[] rings, int seg = 48)
            {
                var g = new Geo();
                foreach (var r in rings)
                    for (int s = 0; s <= seg; s++)
                    {
                        float a = (float)s / seg * Mathf.PI * 2;
                        float fold = r.folds != 0 ? 1 + r.folds * Mathf.Sin(a * 11) * Mathf.Max(0, Mathf.Cos(a - Mathf.PI / 2) * 0.5f + 0.5f) : 1;
                        // three: z = cz + sin(a) * rz * fold  -> Unity z negated
                        g.pos.Add(new Vector3(r.cx + Mathf.Cos(a) * r.rx * fold, r.y, -(r.cz + Mathf.Sin(a) * r.rz * fold)));
                    }
                for (int i = 0; i < rings.Length - 1; i++)
                    for (int s = 0; s < seg; s++)
                    {
                        int a = i * (seg + 1) + s, b = a + seg + 1;
                        g.idx.AddRange(new[] { a, b, a + 1, b, b + 1, a + 1 });
                    }
                return g;
            }

            /// <summary>Capped truncated cone from a (radius r0) to b (radius r1).</summary>
            public static Geo Limb(Vector3 a, Vector3 b, float r0, float r1, int seg = 20, int hseg = 4)
            {
                var g = new Geo();
                var dir = b - a;
                var rot = Quaternion.FromToRotation(Vector3.up, dir.normalized);
                float L = dir.magnitude;
                // built directly in Unity space; like the three-order input elsewhere, Cross(b-a, c-a) points
                // inward here and ToMesh's reversal turns it outward
                for (int h = 0; h <= hseg; h++)
                {
                    float t = (float)h / hseg, r = Mathf.Lerp(r0, r1, t);
                    for (int s = 0; s <= seg; s++)
                    {
                        float ang = (float)s / seg * Mathf.PI * 2;
                        g.pos.Add(a + rot * new Vector3(Mathf.Sin(ang) * r, t * L, Mathf.Cos(ang) * r));
                    }
                }
                for (int h = 0; h < hseg; h++)
                    for (int s = 0; s < seg; s++)
                    {
                        int i0 = h * (seg + 1) + s, i1 = i0 + seg + 1;
                        g.idx.AddRange(new[] { i0, i1, i0 + 1, i1, i1 + 1, i0 + 1 });
                    }
                Cap(g, a, rot, r0, 0, seg, false);
                Cap(g, a, rot, r1, L, seg, true);
                return g;
            }

            static void Cap(Geo g, Vector3 a, Quaternion rot, float r, float y, int seg, bool top)
            {
                int c = g.pos.Count;
                g.pos.Add(a + rot * new Vector3(0, y, 0));
                for (int s = 0; s <= seg; s++)
                {
                    float ang = (float)s / seg * Mathf.PI * 2;
                    g.pos.Add(a + rot * new Vector3(Mathf.Sin(ang) * r, y, Mathf.Cos(ang) * r));
                }
                for (int s = 0; s < seg; s++)
                    if (top) g.idx.AddRange(new[] { c, c + 1 + s + 1, c + 1 + s });
                    else g.idx.AddRange(new[] { c, c + 1 + s, c + 1 + s + 1 });
            }

            public static Geo Ellipsoid(Vector3 c, float rx, float ry, float rz, int ws = 32, int hs = 24)
            {
                var g = new Geo();
                for (int y = 0; y <= hs; y++)
                {
                    float v = (float)y / hs, th = v * Mathf.PI;
                    for (int x = 0; x <= ws; x++)
                    {
                        float u = (float)x / ws, ph = u * Mathf.PI * 2;
                        // three SphereGeometry: (-cos(ph) sin(th), cos(th), sin(ph) sin(th)); z negated
                        g.pos.Add(c + new Vector3(-Mathf.Cos(ph) * Mathf.Sin(th) * rx, Mathf.Cos(th) * ry, -Mathf.Sin(ph) * Mathf.Sin(th) * rz));
                    }
                }
                for (int y = 0; y < hs; y++)
                    for (int x = 0; x < ws; x++)
                    {
                        int a = y * (ws + 1) + x + 1, b = y * (ws + 1) + x, cc = (y + 1) * (ws + 1) + x, d = (y + 1) * (ws + 1) + x + 1;
                        if (y != 0) g.idx.AddRange(new[] { a, b, d });
                        if (y != hs - 1) g.idx.AddRange(new[] { b, cc, d });
                    }
                return g;
            }

            /// <summary>Torus around the local Z axis (three TorusGeometry).</summary>
            public static Geo Torus(float R, float r, int rs, int ts)
            {
                var g = new Geo();
                for (int j = 0; j <= rs; j++)
                    for (int i = 0; i <= ts; i++)
                    {
                        float u = (float)i / ts * Mathf.PI * 2, v = (float)j / rs * Mathf.PI * 2;
                        g.pos.Add(new Vector3((R + r * Mathf.Cos(v)) * Mathf.Cos(u), (R + r * Mathf.Cos(v)) * Mathf.Sin(u), -r * Mathf.Sin(v)));
                    }
                for (int j = 1; j <= rs; j++)
                    for (int i = 1; i <= ts; i++)
                    {
                        int a = (ts + 1) * j + i - 1, b = (ts + 1) * (j - 1) + i - 1, c = (ts + 1) * (j - 1) + i, d = (ts + 1) * j + i;
                        g.idx.AddRange(new[] { a, b, d, b, c, d });
                    }
                return g;
            }

            /// <summary>Flat polygon slab from Unity z = zf (side facing the viewer) to zb (zb &gt; zf = further back), as a triangle soup.</summary>
            public static Geo Slab(Vector2[] poly, float zf, float zb)
            {
                var g = new Geo();
                var tris = Triangulate(poly);
                void Tri(Vector3 a, Vector3 b, Vector3 c) { int k = g.pos.Count; g.pos.Add(a); g.pos.Add(b); g.pos.Add(c); g.idx.AddRange(new[] { k, k + 1, k + 2 }); }
                for (int i = 0; i < tris.Count; i += 3)
                {
                    Vector2 a = poly[tris[i]], b = poly[tris[i + 1]], c = poly[tris[i + 2]];
                    Tri(V(a, zf), V(b, zf), V(c, zf));     // front (faces the viewer)
                    Tri(V(a, zb), V(c, zb), V(b, zb));     // back
                }
                for (int i = 0; i < poly.Length; i++)
                {
                    Vector2 a = poly[i], b = poly[(i + 1) % poly.Length];
                    Tri(V(a, zf), V(a, zb), V(b, zb));
                    Tri(V(a, zf), V(b, zb), V(b, zf));
                }
                return g;

                Vector3 V(Vector2 p, float z) => new Vector3(p.x, p.y, z);
            }

            // Ear clipping; returns CCW (three order) triangles for either input winding.
            static List<int> Triangulate(Vector2[] p)
            {
                var res = new List<int>();
                var ix = new List<int>();
                float area = 0;
                for (int i = 0; i < p.Length; i++) { var a = p[i]; var b = p[(i + 1) % p.Length]; area += a.x * b.y - b.x * a.y; }
                for (int i = 0; i < p.Length; i++) ix.Add(area > 0 ? i : p.Length - 1 - i);
                int guard = 0;
                while (ix.Count > 3 && guard++ < 10000)
                {
                    bool clipped = false;
                    for (int i = 0; i < ix.Count; i++)
                    {
                        int i0 = ix[(i + ix.Count - 1) % ix.Count], i1 = ix[i], i2 = ix[(i + 1) % ix.Count];
                        Vector2 a = p[i0], b = p[i1], c = p[i2];
                        if ((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x) <= 0) continue;
                        bool inside = false;
                        foreach (int j in ix)
                            if (j != i0 && j != i1 && j != i2 && InTri(p[j], a, b, c)) { inside = true; break; }
                        if (inside) continue;
                        res.AddRange(new[] { i0, i1, i2 }); ix.RemoveAt(i); clipped = true; break;
                    }
                    if (!clipped) break;
                }
                if (ix.Count == 3) res.AddRange(new[] { ix[0], ix[1], ix[2] });
                return res;
            }

            static bool InTri(Vector2 p, Vector2 a, Vector2 b, Vector2 c)
            {
                float d1 = (p.x - b.x) * (a.y - b.y) - (a.x - b.x) * (p.y - b.y);
                float d2 = (p.x - c.x) * (b.y - c.y) - (b.x - c.x) * (p.y - c.y);
                float d3 = (p.x - a.x) * (c.y - a.y) - (c.x - a.x) * (p.y - a.y);
                bool neg = d1 < 0 || d2 < 0 || d3 < 0, pos = d1 > 0 || d2 > 0 || d3 > 0;
                return !(neg && pos);
            }

            /// <summary>Split long triangle edges so the skinned wing bends smoothly (triangle soup in, soup out).</summary>
            public Geo Tessellate(float maxEdge)
            {
                var tris = new List<Vector3>();
                for (int i = 0; i < idx.Count; i++) tris.Add(pos[idx[i]]);
                for (int pass = 0; pass < 6; pass++)
                {
                    var o = new List<Vector3>(); bool split = false;
                    for (int i = 0; i < tris.Count; i += 3)
                    {
                        Vector3 a = tris[i], b = tris[i + 1], c = tris[i + 2];
                        float e0 = (a - b).magnitude, e1 = (b - c).magnitude, e2 = (c - a).magnitude, m = Mathf.Max(e0, Mathf.Max(e1, e2));
                        if (m <= maxEdge) { o.Add(a); o.Add(b); o.Add(c); continue; }
                        split = true;
                        if (m == e0) { var mid = (a + b) / 2; o.AddRange(new[] { a, mid, c, mid, b, c }); }
                        else if (m == e1) { var mid = (b + c) / 2; o.AddRange(new[] { a, b, mid, a, mid, c }); }
                        else { var mid = (c + a) / 2; o.AddRange(new[] { a, b, mid, mid, b, c }); }
                    }
                    tris = o; if (!split) break;
                }
                var g = new Geo();
                // weld identical positions so normals are smooth across the subdivided faces
                var map = new Dictionary<Vector3, int>();
                foreach (var v in tris)
                {
                    if (!map.TryGetValue(v, out int k)) { k = g.pos.Count; map[v] = k; g.pos.Add(v); }
                    g.idx.Add(k);
                }
                return g;
            }
        }
    }
}
