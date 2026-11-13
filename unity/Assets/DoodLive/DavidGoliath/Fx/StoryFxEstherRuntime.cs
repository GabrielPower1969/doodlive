// Runtime side of the Esther stage light (docs/esther/FX.md "tension_dim / truth_flash wiring").
// A hidden singleton resolves StoryLight requests once per frame and then:
//   1. sets the global shader values _DoodStageDim (0..1) and _DoodStageTint (white -> evening blue) every frame,
//      so a stage shader can tint itself if Integration wires it;
//   2. draws a camera-facing, soft-edged, translucent evening-blue quad over the stage (on by default, DimOverlay),
//      placed between the camera and the stage; effects (queue 3010+) draw after it, so fire and glows stay bright;
//   3. draws the cold white screen flash of truth_flash with IMGUI (when DGFx.DrawFlashOverlay is true);
//   4. copies StoryFxStage.BeamTarget (an actor bone, e.g. esther.chest) into EstherFx.BeamTarget for sceptre_beam.
using UnityEngine;
using UnityEngine.Rendering;

namespace DoodLive.DavidGoliath
{
    public sealed class StoryFxStage : MonoBehaviour
    {
        /// <summary>Draw the translucent dim quad. Set false once a stage shader reads _DoodStageTint instead.</summary>
        public static bool DimOverlay = true;

        /// <summary>Overlay colour (sRGB); its opacity is the current dim level (0..StoryLight.DimStrength).</summary>
        public static Color DimColour = new Color(0.07f, 0.10f, 0.28f, 1f);

        /// <summary>Full-dim value of _DoodStageTint (sRGB multiplier for stage albedo).</summary>
        public static Color CoolTint = new Color(0.45f, 0.52f, 0.80f, 1f);

        /// <summary>Cold flash colour (sRGB) for truth_flash.</summary>
        public static Color FlashColour = new Color(0.90f, 0.95f, 1f, 1f);

        /// <summary>Stage-local box (art units) the overlay must cover: the art rectangle (1 x ~1.23) plus the set height.</summary>
        public static Bounds DimBounds = new Bounds(new Vector3(0f, 0.33f, 0f), new Vector3(1.15f, 0.70f, 1.35f));

        /// <summary>Optional bone sceptre_beam aims at (e.g. esther.chest). Null: EstherFx.BeamTarget stays as set.</summary>
        public static Transform BeamTarget;

        /// <summary>Current dim level (0..1, already scaled by StoryLight.DimStrength) and cold flash opacity.</summary>
        public static float Dim { get; private set; }
        public static float ColdFlash { get; private set; }

        public const string DimProperty = "_DoodStageDim", TintProperty = "_DoodStageTint";
        static readonly int DimId = Shader.PropertyToID(DimProperty), TintId = Shader.PropertyToID(TintProperty);

        static StoryFxStage inst;
        int epoch;
        GameObject quadGo;
        Mesh quadMesh;
        MeshRenderer quadMr;
        Material quadMat;
        Texture2D quadTex;
        readonly Vector3[] qv = new Vector3[4];
        readonly Color[] qc = new Color[4];

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        public static void Ensure()
        {
            if (inst) return;
            var go = new GameObject("StoryFxStage") { hideFlags = HideFlags.HideInHierarchy };
            DontDestroyOnLoad(go);
            inst = go.AddComponent<StoryFxStage>();
        }

        void OnDestroy()
        {
            if (quadGo) Destroy(quadGo);
            if (quadMesh) Destroy(quadMesh);
            if (quadMat) Destroy(quadMat);
            if (quadTex) Destroy(quadTex);
            Shader.SetGlobalFloat(DimId, 0f);
            Shader.SetGlobalColor(TintId, Color.white);
        }

        void LateUpdate()
        {
            StoryLight.Resolve(out float dimReq, out float flashReq);
            if (epoch != StoryLight.Epoch) { epoch = StoryLight.Epoch; Dim = 0f; }   // DGFx.StopAll: lights up at once
            // rises with the effect's own fade-in; if the effect vanishes (stopped) the dim still eases out over ~0.4 s
            if (dimReq >= Dim) Dim = dimReq;
            else if (!DGFx.Paused) Dim = Mathf.Max(dimReq, Dim - Time.deltaTime * 1.2f);
            ColdFlash = flashReq;

            float full = StoryLight.DimStrength > 1e-4f ? Mathf.Clamp01(Dim / StoryLight.DimStrength) : 0f;
            Shader.SetGlobalFloat(DimId, Dim);
            Shader.SetGlobalColor(TintId, Color.Lerp(Color.white, CoolTint, full));

            var stage = DGFx.Stage;
            if (BeamTarget && stage) EstherFx.BeamTarget = stage.InverseTransformPoint(BeamTarget.position);

            UpdateQuad(stage);
        }

        void UpdateQuad(Transform stage)
        {
            var cam = Camera.main;
            if (!DimOverlay || Dim <= 0.002f || !stage || !cam) { if (quadMr) quadMr.enabled = false; return; }
            if (!quadGo || quadGo.transform.parent != stage) Build(stage);

            // plane perpendicular to the camera's forward axis, just in front of the nearest stage corner
            var ct = cam.transform;
            Vector3 cp = stage.InverseTransformPoint(ct.position);
            Vector3 cf = stage.InverseTransformDirection(ct.forward).normalized;
            Vector3 cr = stage.InverseTransformDirection(ct.right).normalized;
            Vector3 cu = stage.InverseTransformDirection(ct.up).normalized;
            float scale = Mathf.Max(1e-5f, Mathf.Abs(stage.lossyScale.x));
            float near = cam.nearClipPlane / scale * 1.05f;

            Vector3 mn = DimBounds.min, mx = DimBounds.max;
            float nearest = float.MaxValue;
            for (int i = 0; i < 8; i++)
            {
                var corner = new Vector3((i & 1) == 0 ? mn.x : mx.x, (i & 2) == 0 ? mn.y : mx.y, (i & 4) == 0 ? mn.z : mx.z);
                nearest = Mathf.Min(nearest, Vector3.Dot(corner - cp, cf));
            }
            float d = Mathf.Max(nearest * 0.9f, near);
            float x0 = float.MaxValue, x1 = float.MinValue, y0 = float.MaxValue, y1 = float.MinValue;
            for (int i = 0; i < 8; i++)
            {
                var corner = new Vector3((i & 1) == 0 ? mn.x : mx.x, (i & 2) == 0 ? mn.y : mx.y, (i & 4) == 0 ? mn.z : mx.z);
                Vector3 q = corner - cp;
                float z = Vector3.Dot(q, cf);
                if (z < 1e-3f) { x0 = y0 = -1e3f; x1 = y1 = 1e3f; break; }   // stage around / behind the camera: cover the view
                float px = Vector3.Dot(q, cr) * d / z, py = Vector3.Dot(q, cu) * d / z;
                x0 = Mathf.Min(x0, px); x1 = Mathf.Max(x1, px); y0 = Mathf.Min(y0, py); y1 = Mathf.Max(y1, py);
            }
            // grow by 12 % so the feathered edge falls outside the stage
            float gx = (x1 - x0) * 0.12f, gy = (y1 - y0) * 0.12f;
            x0 -= gx; x1 += gx; y0 -= gy; y1 += gy;
            Vector3 o = cp + cf * d;
            qv[0] = o + cr * x0 + cu * y0; qv[1] = o + cr * x1 + cu * y0; qv[2] = o + cr * x1 + cu * y1; qv[3] = o + cr * x0 + cu * y1;
            Color col = DimColour; col.a = Dim;
            if (DGFxAssets.Linear) col = DGFxAssets.ToLinear(col);
            for (int i = 0; i < 4; i++) qc[i] = col;
            quadMesh.vertices = qv;
            quadMesh.colors = qc;
            quadMesh.RecalculateBounds();
            quadGo.layer = stage.gameObject.layer;
            quadMr.enabled = true;
        }

        void Build(Transform stage)
        {
            if (quadGo) Destroy(quadGo);
            DGFxAssets.Ensure();
            if (!quadTex)
            {   // white with feathered edges (alpha), 64x64
                const int S = 64;
                quadTex = new Texture2D(S, S, TextureFormat.RGBA32, false, false)
                {
                    name = "StoryFxDim", wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear,
                };
                var px = new Color32[S * S];
                for (int y = 0; y < S; y++)
                for (int x = 0; x < S; x++)
                {
                    float u = (x + 0.5f) / S, v = (y + 0.5f) / S;
                    float e = Mathf.Min(Mathf.Min(u, 1 - u), Mathf.Min(v, 1 - v));
                    float a = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(e / 0.12f));
                    px[y * S + x] = new Color32(255, 255, 255, (byte)Mathf.RoundToInt(a * 255f));
                }
                quadTex.SetPixels32(px);
                quadTex.Apply(false, true);
            }
            if (!quadMat)
                quadMat = new Material(DGFxAssets.AlphaMat) { name = "StoryFx_Dim", mainTexture = quadTex, renderQueue = 3005 };
            if (!quadMesh)
            {
                quadMesh = new Mesh { name = "StoryFx_Dim" };
                quadMesh.MarkDynamic();
                quadMesh.vertices = qv;
                quadMesh.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };
                quadMesh.colors = qc;
                quadMesh.triangles = new[] { 0, 2, 1, 0, 3, 2 };
            }
            quadGo = new GameObject("StoryFx_Dim");
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

        void OnGUI()
        {
            if (!DGFx.DrawFlashOverlay || ColdFlash <= 0.001f || Event.current.type != EventType.Repaint) return;
            var old = GUI.color;
            GUI.depth = -1000;
            var c = FlashColour; c.a = ColdFlash;
            GUI.color = c;
            GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), Texture2D.whiteTexture);
            GUI.color = old;
        }
    }
}
