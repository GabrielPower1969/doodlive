// Runtime side of the Ruth stage tints (docs/ruth/FX.md "Wiring for Integration").
// A hidden singleton resolves StoryTint requests (sunset_glow, night) once per frame, after StoryFxStage, and then:
//   1. draws a MULTIPLY overlay quad between the camera and the stage (queue 3004: after the opaque stage, the
//      characters and the AR background, before Esther's dim quad 3005 and every DGFx effect 3010/3020), so the set and
//      the actors take the night-blue / golden tint while lamp light, stars and glows stay untinted and pop;
//   2. sets the global shader values _DoodStageTint (Esther's cool dim x the Ruth tint), _DoodStageLight (0..1, any
//      tint active) and _DoodStageRim (rim colour x level), for stage shaders that tint themselves (then set
//      TintOverlay = false);
//   3. feeds RuthFx.Actors (stage-local feet + height of every DGActor under DGFx.Stage) for the moonlight halos.
// DGFx.StopAll() calls StoryLight.Reset(); this runtime watches StoryLight.Epoch and drops the tint at once.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace DoodLive.DavidGoliath
{
    [DefaultExecutionOrder(100)]   // after StoryFxStage (0), so the combined _DoodStageTint wins
    public sealed class StoryTintStage : MonoBehaviour
    {
        /// <summary>Draw the multiply overlay. Set false once the stage / character shaders read _DoodStageTint.</summary>
        public static bool TintOverlay = true;

        /// <summary>Stage-local box (art units) the overlay must cover (as StoryFxStage.DimBounds; also the sky bands).</summary>
        public static Bounds TintBounds = new Bounds(new Vector3(0f, 0.36f, -0.05f), new Vector3(1.40f, 0.76f, 1.45f));

        /// <summary>Current tint (sRGB multiplier), level 0..1 and rim colour (already x level).</summary>
        public static Color Tint { get; private set; } = Color.white;
        public static float Level { get; private set; }
        public static Color Rim { get; private set; } = Color.black;

        public const string TintProperty = "_DoodStageTint", LightProperty = "_DoodStageLight", RimProperty = "_DoodStageRim";
        static readonly int TintId = Shader.PropertyToID(TintProperty), LightId = Shader.PropertyToID(LightProperty),
                            RimId = Shader.PropertyToID(RimProperty);

        static StoryTintStage inst;
        int epoch;
        Color lastMul = Color.white, lastRim = Color.black;   // colour kept while easing out after the effect is gone
        float actorScan;
        DGActor[] actors = new DGActor[0];
        GameObject quadGo;
        Mesh quadMesh;
        MeshRenderer quadMr;
        Material quadMat;
        bool overlayBroken;
        readonly Vector3[] qv = new Vector3[8];
        readonly Color[] qc = new Color[8];

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        public static void Ensure()
        {
            if (inst) return;
            var go = new GameObject("StoryTintStage") { hideFlags = HideFlags.HideInHierarchy };
            DontDestroyOnLoad(go);
            inst = go.AddComponent<StoryTintStage>();
        }

        void OnDestroy()
        {
            if (quadGo) Destroy(quadGo);
            if (quadMesh) Destroy(quadMesh);
            if (quadMat) Destroy(quadMat);
            Shader.SetGlobalFloat(LightId, 0f);
            Shader.SetGlobalColor(RimId, Color.black);
        }

        void LateUpdate()
        {
            StoryTint.Resolve(out Color mul, out Color rim, out float req);
            if (epoch != StoryLight.Epoch) { epoch = StoryLight.Epoch; StoryTint.Clear(); Level = 0f; req = 0f; }   // DGFx.StopAll
            if (req > 0.0005f)
            {   // un-apply the level to remember the full-strength colour for a soft ease-out
                lastMul = InvLerpWhite(mul, req); lastRim = rim * (1f / req);
            }
            if (req >= Level) Level = req;
            else if (!DGFx.Paused) Level = Mathf.Max(req, Level - Time.deltaTime * 1.25f);
            Tint = Color.Lerp(Color.white, lastMul, Level);
            Rim = lastRim * Level; var rr = Rim; rr.a = 1f; Rim = rr;

            // globals: combine with Esther's cool dim (StoryFxStage writes _DoodStageTint earlier in the frame)
            float esther = StoryLight.DimStrength > 1e-4f ? Mathf.Clamp01(StoryFxStage.Dim / StoryLight.DimStrength) : 0f;
            Color combined = Color.Lerp(Color.white, StoryFxStage.CoolTint, esther) * Tint; combined.a = 1f;
            Shader.SetGlobalColor(TintId, combined);
            Shader.SetGlobalFloat(LightId, Mathf.Max(esther, Level));
            Shader.SetGlobalColor(RimId, Rim);

            var stage = DGFx.Stage;
            UpdateActors(stage);
            UpdateQuad(stage);
        }

        static Color InvLerpWhite(Color c, float k)
        {   // c = lerp(1, m, k)  ->  m = 1 - (1 - c) / k
            float s = 1f / Mathf.Max(k, 1e-3f);
            return new Color(Mathf.Clamp01(1f - (1f - c.r) * s), Mathf.Clamp01(1f - (1f - c.g) * s), Mathf.Clamp01(1f - (1f - c.b) * s), 1f);
        }

        void UpdateActors(Transform stage)
        {
            RuthFx.Actors.Clear();
            if (!stage || Level <= 0.0005f) return;
            actorScan -= Time.unscaledDeltaTime;
            if (actorScan <= 0f) { actorScan = 0.5f; actors = stage.GetComponentsInChildren<DGActor>(false); }
            foreach (var a in actors)
            {
                if (!a || !a.isActiveAndEnabled) continue;
                RuthFx.Actors.Add(new RuthActor { feet = stage.InverseTransformPoint(a.transform.position), height = a.height });
            }
        }

        void UpdateQuad(Transform stage)
        {
            var cam = Camera.main;
            if (!TintOverlay || overlayBroken || Level <= 0.002f || !stage || !cam) { if (quadMr) quadMr.enabled = false; return; }
            if (!quadGo || quadGo.transform.parent != stage) Build(stage);
            if (overlayBroken) return;

            var ct = cam.transform;
            Vector3 cp = stage.InverseTransformPoint(ct.position);
            Vector3 cf = stage.InverseTransformDirection(ct.forward).normalized;
            Vector3 cr = stage.InverseTransformDirection(ct.right).normalized;
            Vector3 cu = stage.InverseTransformDirection(ct.up).normalized;
            float scale = Mathf.Max(1e-5f, Mathf.Abs(stage.lossyScale.x));
            float near = cam.nearClipPlane / scale * 1.05f;

            Vector3 mn = TintBounds.min, mx = TintBounds.max;
            float nearest = float.MaxValue;
            for (int i = 0; i < 8; i++) nearest = Mathf.Min(nearest, Vector3.Dot(Corner(mn, mx, i) - cp, cf));
            float d = Mathf.Max(nearest * 0.9f, near);
            float x0 = float.MaxValue, x1 = float.MinValue, y0 = float.MaxValue, y1 = float.MinValue;
            for (int i = 0; i < 8; i++)
            {
                Vector3 q = Corner(mn, mx, i) - cp;
                float z = Vector3.Dot(q, cf);
                if (z < 1e-3f) { x0 = y0 = -1e3f; x1 = y1 = 1e3f; break; }   // camera inside / behind the box: cover the view
                float px = Vector3.Dot(q, cr) * d / z, py = Vector3.Dot(q, cu) * d / z;
                x0 = Mathf.Min(x0, px); x1 = Mathf.Max(x1, px); y0 = Mathf.Min(y0, py); y1 = Mathf.Max(y1, py);
            }
            // inner rectangle = full tint over the box; outer ring (+15 %) feathers back to white (no tint)
            float gx = (x1 - x0) * 0.15f, gy = (y1 - y0) * 0.15f;
            Vector3 o = cp + cf * d;
            qv[0] = o + cr * x0 + cu * y0; qv[1] = o + cr * x1 + cu * y0; qv[2] = o + cr * x1 + cu * y1; qv[3] = o + cr * x0 + cu * y1;
            qv[4] = o + cr * (x0 - gx) + cu * (y0 - gy); qv[5] = o + cr * (x1 + gx) + cu * (y0 - gy);
            qv[6] = o + cr * (x1 + gx) + cu * (y1 + gy); qv[7] = o + cr * (x0 - gx) + cu * (y1 + gy);
            Color inner = DGFxAssets.Linear ? DGFxAssets.ToLinear(Tint) : Tint; inner.a = 1f;
            for (int i = 0; i < 4; i++) { qc[i] = inner; qc[i + 4] = Color.white; }
            quadMesh.vertices = qv;
            quadMesh.colors = qc;
            quadMesh.RecalculateBounds();
            quadGo.layer = stage.gameObject.layer;
            quadMr.enabled = true;
        }

        static Vector3 Corner(Vector3 mn, Vector3 mx, int i) =>
            new Vector3((i & 1) == 0 ? mn.x : mx.x, (i & 2) == 0 ? mn.y : mx.y, (i & 4) == 0 ? mn.z : mx.z);

        void Build(Transform stage)
        {
            if (quadGo) Destroy(quadGo);
            DGFxAssets.Ensure();
            if (!quadMat)
            {
                quadMat = new Material(DGFxAssets.AlphaMat) { name = "StoryFx_Tint", mainTexture = Texture2D.whiteTexture, renderQueue = 3004 };
                if (!quadMat.HasProperty("_SrcBlend") || !quadMat.HasProperty("_DstBlend"))
                {   // fallback shader (Sprites/Default) cannot multiply: skip the overlay rather than paint a solid quad
                    overlayBroken = true;
                    Debug.LogWarning("[DGFx] DGFxUnlit not available; Ruth stage tint overlay disabled (globals still set).");
                    return;
                }
                quadMat.SetFloat("_SrcBlend", (float)BlendMode.DstColor);   // out = src * dst  (multiply)
                quadMat.SetFloat("_DstBlend", (float)BlendMode.Zero);
            }
            if (!quadMesh)
            {
                quadMesh = new Mesh { name = "StoryFx_Tint" };
                quadMesh.MarkDynamic();
                quadMesh.vertices = qv;
                quadMesh.uv = new Vector2[8];
                quadMesh.colors = qc;
                // inner quad + four feather strips between the inner (0-3) and outer (4-7) rectangles
                quadMesh.triangles = new[]
                {
                    0, 2, 1, 0, 3, 2,
                    4, 1, 5, 4, 0, 1,   // bottom
                    5, 2, 6, 5, 1, 2,   // right
                    6, 3, 7, 6, 2, 3,   // top
                    7, 0, 4, 7, 3, 0,   // left
                };
            }
            quadGo = new GameObject("StoryFx_Tint");
            var tr = quadGo.transform;
            tr.SetParent(stage, false);
            tr.localPosition = Vector3.zero; tr.localRotation = Quaternion.identity; tr.localScale = Vector3.one;
            quadGo.AddComponent<MeshFilter>().sharedMesh = quadMesh;
            quadMr = quadGo.AddComponent<MeshRenderer>();
            quadMr.sharedMaterial = quadMat;
            quadMr.shadowCastingMode = ShadowCastingMode.Off;
            quadMr.receiveShadows = false;
            quadMr.lightProbeUsage = LightProbeUsage.Off;
            quadMr.reflectionProbeUsage = ReflectionProbeUsage.Off;
        }
    }
}
