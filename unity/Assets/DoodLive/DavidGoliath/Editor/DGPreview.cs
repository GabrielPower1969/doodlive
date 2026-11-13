// Editor-only check of the David & Goliath integration without a phone: opens the generated scene, runs DGDirector
// over timeline.json in fixed 1/30 s steps (edit mode, no Update loop) and renders the shot-list camera to PNGs.
// Batch (needs graphics, so no -nographics):
//   Unity -batchmode -quit -projectPath unity -executeMethod DoodLive.EditorTools.DGPreview.Render -logFile -
// Output: unity/Builds/dg-preview/t_<sec>.png (+ portrait_<sec>.png, side_<sec>.png, phone_<sec>.png / low_<sec>.png
// = fixed views of the whole page with the desert set, as a child holding the phone would see it). Effects are not drawn (their meshes are built in
// LateUpdate, which edit mode does not run); everything else is the real runtime code path.
using System.IO;
using DoodLive.DavidGoliath;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DoodLive.EditorTools
{
    public static class DGPreview
    {
        const float Scale = 0.3f;
        static readonly float[] Times = { 0.5f, 3.0f, 9.0f, 20.0f, 28.0f, 30.0f, 33.0f, 41.0f, 54.5f, 55.9f, 60.0f, 69.5f, 71.5f, 72.9f, 73.3f, 75.0f, 77.0f, 81.0f, 86.0f, 88.9f };

        [MenuItem("DoodLive/David & Goliath/Render preview frames")]
        public static void Render()
        {
            EditorSceneManager.OpenScene("Assets/DoodLive/Scenes/DoodLive.unity");
            var ctl = Object.FindFirstObjectByType<ARColoringController>();
            var story = ctl ? ctl.story : null;
            if (!story) { Debug.LogError("DG preview: no DGDirector in the scene (run Setup)"); if (Application.isBatchMode) EditorApplication.Exit(1); return; }
            foreach (var c in Object.FindObjectsByType<Camera>(FindObjectsSortMode.None)) c.enabled = false;
            if (ctl.angel) ctl.angel.gameObject.SetActive(false);   // the controller hides her at Start; edit mode has no Start
            var cam = new GameObject("DGPreviewCam").AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color32(0x9C, 0x6B, 0x45, 0xFF);
            cam.nearClipPlane = 0.01f; cam.farClipPlane = 30;
            story.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            story.transform.localScale = Vector3.one * Scale;   // device size (demo holder 0.3 m per art width), so shadows match the phone
            story.gameObject.SetActive(true);
            foreach (var m in ctl.dgMaterials) m.SetTexture("_BaseMap", ctl.dgDemoTexture);
            story.EditorInit();
            // edit mode has no player loop, so skinning would stay at its first pose; recompute bone matrices per render
            foreach (var smr in story.GetComponentsInChildren<SkinnedMeshRenderer>(true)) smr.forceMatrixRecalculationPerRender = true;
            story.ShowDemoPage(true);
            story.cinematic = cam;
            string dir = Path.GetFullPath("Builds/dg-preview"); Directory.CreateDirectory(dir);
            foreach (var f in Directory.GetFiles(dir, "*.png")) File.Delete(f);
            void Shot(string name, int w, int h)
            {
                var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                cam.targetTexture = rt; cam.aspect = w / (float)h;
                story.EditorStep(0);                 // re-run the camera with this aspect
                cam.Render();
                var prev = RenderTexture.active; RenderTexture.active = rt;
                var tex = new Texture2D(w, h, TextureFormat.RGB24, false); tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply();
                RenderTexture.active = prev; cam.targetTexture = null;
                File.WriteAllBytes(Path.Combine(dir, name + ".png"), tex.EncodeToPNG());
                Object.DestroyImmediate(tex); rt.Release(); Object.DestroyImmediate(rt);
            }
            void ShotFixed(string name, int w, int h)
            {   // render without letting the shot-list camera move the camera
                var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                cam.targetTexture = rt; cam.aspect = w / (float)h; cam.Render();
                var prev = RenderTexture.active; RenderTexture.active = rt;
                var tex = new Texture2D(w, h, TextureFormat.RGB24, false); tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply();
                RenderTexture.active = prev; cam.targetTexture = null;
                File.WriteAllBytes(Path.Combine(dir, name + ".png"), tex.EncodeToPNG());
                Object.DestroyImmediate(tex); rt.Release(); Object.DestroyImmediate(rt);
            }
            story.Begin();
            float now = 0; const float dt = 1f / 30f;
            foreach (var T in Times)
            {
                while (now + dt <= T + 1e-4f) { story.EditorStep(dt); now += dt; }
                Shot($"t_{T:00.0}", 960, 540);
                if (T == 9.0f || T == 41.0f || T == 72.9f || T == 86.0f) Shot($"portrait_{T:00.0}", 540, 960);
                if (T == 0.5f || T == 30.0f || T == 55.9f || T == 60.0f || T == 75.0f || T == 77.0f || T == 86.0f)
                {   // "phone" view: what a child holding the phone over the page sees (desert rising from the page, §11.13)
                    story.cinematic = null;
                    var st = story.transform;
                    cam.transform.position = st.TransformPoint(new Vector3(0.08f, 0.95f, 1.15f));   // local +x = viewer's left
                    cam.transform.LookAt(st.TransformPoint(new Vector3(0.08f, 0.05f, -0.50f))); cam.fieldOfView = 55;
                    ShotFixed($"phone_{T:00.0}", 540, 960);
                    cam.transform.position = st.TransformPoint(new Vector3(-0.30f, 0.90f, 1.10f));   // phone moved to the right
                    cam.transform.LookAt(st.TransformPoint(new Vector3(-0.05f, 0.05f, -0.50f))); cam.fieldOfView = 55;
                    ShotFixed($"right_{T:00.0}", 540, 960);
                    cam.transform.position = st.TransformPoint(new Vector3(-0.15f, 0.30f, 0.95f));
                    cam.transform.LookAt(st.TransformPoint(new Vector3(0.05f, 0.18f, -0.30f))); cam.fieldOfView = 45;
                    ShotFixed($"low_{T:00.0}", 960, 540);
                    story.cinematic = cam;
                }
                if (T == 54.5f || T == 55.9f || T == 86.0f || T == 41.0f)
                {   // side close-up of David (checks the skinned pose, not just the bones)
                    story.cinematic = null;
                    var dp = story.david.transform.position;
                    cam.transform.position = dp + story.transform.TransformVector(new Vector3(-0.6f, 0.12f, 0.15f));
                    cam.transform.LookAt(dp + Vector3.up * 0.1f * Scale); cam.fieldOfView = 30;
                    var rt = new RenderTexture(640, 640, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB); cam.targetTexture = rt; cam.aspect = 1; cam.Render();
                    var prev = RenderTexture.active; RenderTexture.active = rt; var tex = new Texture2D(640, 640, TextureFormat.RGB24, false); tex.ReadPixels(new Rect(0, 0, 640, 640), 0, 0); tex.Apply();
                    RenderTexture.active = prev; cam.targetTexture = null; File.WriteAllBytes(Path.Combine(dir, $"side_{T:00.0}.png"), tex.EncodeToPNG());
                    story.cinematic = cam;
                }
                var d = story.david; var g = story.goliath;
                Debug.Log($"DG preview t={story.Now:F2} shot={story.Shot?.id} david {d.ClipName(d.cur)} pos=({d.pos.x:F3},{d.pos.y:F3}) yaw={d.yaw:F0} | goliath {g.ClipName(g.cur)} pos=({g.pos.x:F3},{g.pos.y:F3}) yaw={g.yaw:F0} | line={story.Line?.id} stone={(d.stone ? d.stone.enabled : false)} | david hips y={story.transform.InverseTransformPoint(d.Bone("hips").position).y:F3} head y={story.transform.InverseTransformPoint(d.Bone("head").position).y:F3} | shinL y={story.transform.InverseTransformPoint(d.Bone("shinL").position).y:F3} footL y={story.transform.InverseTransformPoint(d.Bone("footL").position).y:F3} footR y={story.transform.InverseTransformPoint(d.Bone("footR").position).y:F3} thighL rot={d.Bone("thighL").localRotation.eulerAngles} | goliath head y={story.transform.InverseTransformPoint(g.Bone("head").position).y:F3} | desert stones shown {(story.desertStones == null ? 0 : System.Linq.Enumerable.Count(story.desertStones, r => r && r.enabled))}/{story.desertStones?.Length ?? 0}");
            }
            story.Stop();
            Debug.Log($"DG preview: {Times.Length} frames -> {dir}");
        }
    }
}
