// Runtime side of the effects: per-effect component (dynamic mesh), shared atlas + materials, shake/flash runner.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace DoodLive.DavidGoliath
{
    /// <summary>One playing effect. Lives under DGFx.Stage, rebuilds its mesh every LateUpdate, destroys itself at dur.</summary>
    [DisallowMultipleComponent]
    public sealed class DGFxInstance : MonoBehaviour
    {
        internal static readonly List<DGFxInstance> Live = new List<DGFxInstance>();

        public string Id => def != null ? def.Id : "";
        public float Time01 => ctx.N;

        FxDef def;
        Transform at;
        readonly FxCtx ctx = new FxCtx();
        readonly FxBatch batch = new FxBatch();
        Mesh mesh;
        readonly List<Vector3> verts = new List<Vector3>(512);
        readonly List<Vector2> uvs = new List<Vector2>(512);
        readonly List<Color> cols = new List<Color>(512);
        readonly List<int> triA = new List<int>(768), triB = new List<int>(768);
        bool started;

        internal void Init(FxDef d, Transform anchor, float dur, int seed)
        {
            def = d; at = anchor;
            ctx.dur = dur; ctx.seed = seed; ctx.t = 0;
            DGFxAssets.Ensure();
            mesh = new Mesh { name = "DGFx_" + d.Id };
            mesh.MarkDynamic();
            gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = gameObject.AddComponent<MeshRenderer>();
            mr.sharedMaterials = new[] { DGFxAssets.AlphaMat, DGFxAssets.AddMat };
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;
            mr.lightProbeUsage = LightProbeUsage.Off;
            mr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            Live.Add(this);
        }

        void OnDestroy()
        {
            Live.Remove(this);
            if (mesh) Destroy(mesh);
        }

        // Bones are posed by the Animator after Update, so sample them in LateUpdate.
        void LateUpdate()
        {
            if (def == null) return;
            if (!started)
            {
                started = true;
                ctx.start = ctx.anchor = AnchorLocal();
                ctx.track.Add(0, ctx.anchor);
            }
            else if (!DGFx.Paused)
            {
                ctx.t += Time.deltaTime * DGFx.TimeScale;
                if (def.Follow && at) ctx.anchor = AnchorLocal();
                if (at) ctx.track.Add(ctx.t, AnchorLocal());   // trails always record the moving bone
            }
            if (ctx.t >= ctx.dur) { Destroy(gameObject); return; }

            UpdateCamera();
            batch.Clear();
            def.Emit(ctx, batch);
            FxMeshBuilder.Build(batch, ctx, DGFxAssets.CellMin, DGFxAssets.CellSize, verts, uvs, cols, triA, triB);
            if (DGFxAssets.Linear) for (int i = 0; i < cols.Count; i++) cols[i] = DGFxAssets.ToLinear(cols[i]);

            mesh.Clear();
            mesh.SetVertices(verts);
            mesh.SetUVs(0, uvs);
            mesh.SetColors(cols);
            mesh.subMeshCount = 2;
            mesh.SetTriangles(triA, 0, false);
            mesh.SetTriangles(triB, 1, false);
            mesh.RecalculateBounds();
        }

        Vector3 AnchorLocal()
        {
            var p = at ? at.position : transform.position;
            return transform.parent ? transform.parent.InverseTransformPoint(p) : p;
        }

        void UpdateCamera()
        {
            var cam = Camera.main;
            var parent = transform.parent;
            if (!cam)
            {   // no camera (tests): look from the viewer side (+Z) of the stage
                ctx.camPos = ctx.anchor + new Vector3(0, 0.4f, 1.5f);
                ctx.camRight = Vector3.right; ctx.camUp = Vector3.up;
                return;
            }
            var ct = cam.transform;
            if (parent)
            {
                ctx.camPos = parent.InverseTransformPoint(ct.position);
                ctx.camRight = parent.InverseTransformDirection(ct.right).normalized;
                ctx.camUp = parent.InverseTransformDirection(ct.up).normalized;
            }
            else { ctx.camPos = ct.position; ctx.camRight = ct.right; ctx.camUp = ct.up; }
        }
    }

    /// <summary>Shared atlas texture and the two materials (alpha-blended crayon, additive light).</summary>
    public static class DGFxAssets
    {
        public static Texture2D Atlas { get; private set; }
        public static Material AlphaMat { get; private set; }
        public static Material AddMat { get; private set; }
        public static Vector2[] CellMin { get; private set; }
        public static Vector2[] CellSize { get; private set; }
        public static bool Linear { get; private set; }

        public static void Ensure()
        {
            if (Atlas && AlphaMat && AddMat) return;
            Linear = QualitySettings.activeColorSpace == ColorSpace.Linear;

            int n = DGFxPaint.CellCount, S = DGFxPaint.Size;
            CellMin = new Vector2[n]; CellSize = new Vector2[n];
            for (int i = 0; i < n; i++)
            {
                var c = DGFxPaint.Cells[i];
                CellMin[i] = new Vector2(c[0] / (float)S, c[1] / (float)S);
                CellSize[i] = new Vector2(c[2] / (float)S, c[3] / (float)S);
            }

            if (!Atlas)
            {
                var px = DGFxPaint.Build();
                var data = new Color32[S * S];
                for (int i = 0; i < data.Length; i++)
                    data[i] = new Color32(B(px[i * 4]), B(px[i * 4 + 1]), B(px[i * 4 + 2]), B(px[i * 4 + 3]));
                Atlas = new Texture2D(S, S, TextureFormat.RGBA32, true, false)   // sRGB colour data
                {
                    name = "DGFxAtlas", wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Trilinear, anisoLevel = 2,
                };
                Atlas.SetPixels32(data);
                Atlas.Apply(true, true);   // mips, then free the CPU copy
            }

            var shader = Resources.Load<Shader>("DGFx/DGFxUnlit");
            if (!shader || !shader.isSupported) shader = Shader.Find("DoodLive/DGFxUnlit");
            bool own = shader && shader.isSupported;
            if (!own)
            {
                shader = Shader.Find("Sprites/Default");
                Debug.LogWarning("[DGFx] DGFxUnlit shader missing; falling back to Sprites/Default (no additive light).");
            }
            AlphaMat = Make(shader, own, BlendMode.SrcAlpha, BlendMode.OneMinusSrcAlpha, "DGFx_Alpha", 3010);
            AddMat = Make(shader, own, BlendMode.SrcAlpha, BlendMode.One, "DGFx_Add", 3020);
        }

        static Material Make(Shader sh, bool own, BlendMode src, BlendMode dst, string name, int queue)
        {
            var m = new Material(sh) { name = name, mainTexture = Atlas, renderQueue = queue };
            if (own)
            {
                m.SetFloat("_SrcBlend", (float)src);
                m.SetFloat("_DstBlend", (float)dst);
            }
            return m;
        }

        static byte B(float v) => (byte)(v <= 0 ? 0 : v >= 1 ? 255 : (int)(v * 255f + 0.5f));

        /// <summary>sRGB -> linear for vertex colours (Unity does not convert mesh colours in Linear projects).</summary>
        public static Color ToLinear(Color c) => new Color(L(c.r), L(c.g), L(c.b), c.a);
        static float L(float v) => v <= 0.04045f ? v / 12.92f : Mathf.Pow((v + 0.055f) / 1.055f, 2.4f);
    }

    /// <summary>Hidden singleton: drives stage shake and the screen flash.</summary>
    public sealed class DGFxRunner : MonoBehaviour
    {
        struct ShakeEv { public float amp, dur, age; }
        static DGFxRunner inst;
        static readonly List<ShakeEv> shakes = new List<ShakeEv>();
        float noiseT;

        internal static void Ensure()
        {
            if (inst) return;
            var go = new GameObject("DGFxRunner") { hideFlags = HideFlags.HideInHierarchy };
            DontDestroyOnLoad(go);
            inst = go.AddComponent<DGFxRunner>();
        }

        internal static void AddShake(float amp, float dur) => shakes.Add(new ShakeEv { amp = amp, dur = dur });

        internal static void ClearShake()
        {
            shakes.Clear();
            DGFx.ShakeOffset = Vector3.zero;
            var t = DGFx.ShakeTarget;
            if (t) t.localPosition = DGFx.shakeRest;
        }

        void LateUpdate()
        {
            if (DGFx.Paused) return;
            float dt = Time.deltaTime * DGFx.TimeScale;
            noiseT += dt;
            float amp = 0;
            for (int i = shakes.Count - 1; i >= 0; i--)
            {
                var s = shakes[i];
                s.age += dt;
                if (s.age >= s.dur) { shakes.RemoveAt(i); continue; }
                float k = 1 - s.age / s.dur;
                amp += s.amp * k * k;
                shakes[i] = s;
            }
            // smooth noise, mostly vertical + sideways (the page thumps), ~18 Hz
            Vector3 off = amp <= 0 ? Vector3.zero : new Vector3(
                (Mathf.PerlinNoise(noiseT * 18f, 0.1f) - 0.5f) * 1.2f,
                (Mathf.PerlinNoise(0.7f, noiseT * 18f) - 0.5f) * 2.0f,
                (Mathf.PerlinNoise(noiseT * 18f, 3.3f) - 0.5f) * 0.8f) * amp;
            DGFx.ShakeOffset = off;
            var t = DGFx.ShakeTarget;
            if (t) t.localPosition = DGFx.shakeRest + off;

            if (DGFx.FlashAlpha > 0) DGFx.FlashAlpha = Mathf.Max(0, DGFx.FlashAlpha - dt / 0.3f);
        }

        void OnGUI()
        {
            if (!DGFx.DrawFlashOverlay || DGFx.FlashAlpha <= 0.001f || Event.current.type != EventType.Repaint) return;
            var old = GUI.color;
            GUI.depth = -1000;
            GUI.color = new Color(1f, 0.98f, 0.9f, DGFx.FlashAlpha);   // warm paper white, not pure white
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
            GUI.color = old;
        }
    }
}
