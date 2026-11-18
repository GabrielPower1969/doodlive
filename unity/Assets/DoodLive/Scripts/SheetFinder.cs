// Marker path of sheet detection: finds a sheet by its 4 printed corner markers in the camera image, tells which sheet
// it is by the title band, and keeps an anchored pose for it (docs/LESSONS.md L49).
//
//   every 0.15 s  camera image (screen space, short side 360 px) -> MarkerDetector.DetectTop
//   candidate     one full-resolution frame -> MarkerDetector.Refine + SheetIdentifier.Identify (title band, way up)
//   pose          homography of the 4 markers through the camera's rays (A4 assumed), then the depth/plane raycast at
//                 the page centre rescales it, so a sheet on a laptop or iPad screen lands at the right depth
//   anchor        the pose lives under an ARAnchor; later detections ease it towards the newest estimate
//
// The camera image is copied in screen space (ARCameraBackground material -> RenderTexture), exactly like the capture
// in ARColoringController, so marker points are screen pixels (y up) and project with the AR camera directly.
using System.Collections;
using System.Collections.Generic;
using DoodLive.Vision;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;

namespace DoodLive
{
    public class SheetFinder : MonoBehaviour
    {
        public ARCameraBackground cameraBackground;
        public Camera arCamera;
        public ARRaycastManager raycasts;

        /// <summary>Set by the controller: search while scanning or live, idle otherwise.</summary>
        public bool Active;
        /// <summary>The identified sheet, or null. Its Tracking turns false a second after the markers leave view.</summary>
        public SheetTarget Current { get; private set; }

        const float Interval = 0.15f;
        const int ShortSide = 360;
        static readonly Vector2 A4 = new Vector2(0.210f, 0.297f);
        List<SheetSignature> sigs;
        RenderTexture small; Texture2D smallTex; byte[] smallLum;
        RenderTexture fullRt; Texture2D fullTex; byte[] fullLum;
        Transform anchorGo, poseGo; float nextAt; bool busy;
        readonly List<float> scaleHist = new List<float>();

        void Start()
        {
            var json = Resources.Load<TextAsset>("sheet_signatures");
            if (json) sigs = SheetIdentifier.Parse(json.text);
            else Debug.LogError("SheetFinder: Resources/sheet_signatures.json missing (tools/make_sheet_signatures.py)");
        }

        /// <summary>Forget the current sheet (rescan).</summary>
        public void Forget()
        {
            Current = null; scaleHist.Clear();
            if (anchorGo) Destroy(anchorGo.gameObject);
            anchorGo = poseGo = null;
        }

        void Update()
        {
            if (!Active || busy || sigs == null || !cameraBackground || !cameraBackground.enabled || Time.time < nextAt) return;
            nextAt = Time.time + Interval;
            StartCoroutine(Tick());
        }

        IEnumerator Tick()
        {
            busy = true;
            yield return new WaitForEndOfFrame();                 // the displayed frame and this frame's camera pose
            try { Detect(); }
            catch (System.Exception e) { Debug.LogException(e); }
            busy = false;
        }

        void Detect()
        {
            int W = Screen.width, H = Screen.height;
            float k = Mathf.Max(1f, Mathf.Min(W, H) / (float)ShortSide);
            int sw = Mathf.RoundToInt(W / k), sh = Mathf.RoundToInt(H / k);
            Grab(ref small, ref smallTex, ref smallLum, sw, sh);
            var cands = MarkerDetector.DetectTop(smallLum, sw, sh, 6, 0.5, yDown: false);
            if (cands.Count == 0) return;

            // known sheet: follow it with the best candidate whose corners sit near the last ones (no full-res read)
            if (Current != null && Current.ScreenMarkers != null)
            {
                foreach (var c in cands)
                {
                    var pts = Order(c.Points, k, Current.ScreenMarkers);
                    if (pts != null) { Track(pts, Current.Name); return; }
                }
            }

            // new sheet: identify on a full-resolution frame
            // full-res buffers are kept between reads: a new 10 MB texture + array every 0.15 s means GC pauses on mid-range phones
            Grab(ref fullRt, ref fullTex, ref fullLum, W, H);
            var full = fullLum;
            SheetMatch best = null;
            foreach (var c in cands)
            {
                var p = new P2[4];
                for (int i = 0; i < 4; i++) p[i] = new P2((c.Points[i].X + 0.5) * k - 0.5, (c.Points[i].Y + 0.5) * k - 0.5);
                p = MarkerDetector.Refine(full, W, H, p, c.MarkerPx * k * 0.9);
                var m = SheetIdentifier.Identify(full, W, H, p, sigs, yDown: false);
                if (m != null && (best == null || m.Ncc > best.Ncc)) best = m;
            }
            if (best == null) { pendingName = null; return; }
            // a new sheet must be read the same way on two identifications in a row: one frame in ~300 misreads the
            // title band (tests/vision), and a wrong story is worse than ~0.15 s more latency
            if (Current == null || Current.Name != best.Sheet.Name)
            {
                if (pendingName != best.Sheet.Name) { pendingName = best.Sheet.Name; return; }
            }
            pendingName = null;
            var sp = new Vector2[4];
            for (int i = 0; i < 4; i++) sp[i] = new Vector2((float)best.Points[i].X, (float)best.Points[i].Y);
            Debug.Log($"DoodLive markers: '{best.Sheet.Name}' ncc {best.Ncc:0.00} (story margin {best.Margin:0.00}, way-up margin {best.OrientMargin:0.00})");
            if (Current == null || Current.Name != best.Sheet.Name) { Forget(); }
            Track(sp, best.Sheet.Name);
        }

        string pendingName;   // first read of a new sheet, waiting for a second matching read

        // Match a candidate (small-frame points) to the last known screen corners; null if it is not the same sheet.
        static Vector2[] Order(P2[] pts, float k, Vector2[] last)
        {
            float tol = Vector2.Distance(last[0], last[2]) * 0.25f;
            var used = new bool[4]; var o = new Vector2[4];
            for (int i = 0; i < 4; i++)
            {
                int bj = -1; float bd = tol;
                for (int j = 0; j < 4; j++)
                {
                    if (used[j]) continue;
                    var s = new Vector2((float)((pts[j].X + 0.5) * k - 0.5), (float)((pts[j].Y + 0.5) * k - 0.5));
                    float d = Vector2.Distance(s, last[i]); if (d < bd) { bd = d; bj = j; }
                }
                if (bj < 0) return null;
                used[bj] = true; o[i] = new Vector2((float)((pts[bj].X + 0.5) * k - 0.5), (float)((pts[bj].Y + 0.5) * k - 0.5));
            }
            return o;
        }

        // ---- pose ----
        void Track(Vector2[] screen, string name)
        {
            if (!Pose(screen, out var pos, out var rot, out float scale)) return;
            if (!anchorGo)
            {
                anchorGo = new GameObject("SheetAnchor").transform;
                anchorGo.SetPositionAndRotation(pos, rot);
                anchorGo.gameObject.AddComponent<ARAnchor>();
                poseGo = new GameObject("Sheet (markers)").transform; poseGo.SetParent(anchorGo, false);
                Current = new SheetTarget(poseGo, name);
            }
            else
            {   // ease towards the newest estimate; a big jump (sheet moved) is taken at once
                bool jump = Vector3.Distance(poseGo.position, pos) > 0.15f * scale;
                float t = jump ? 1f : 0.35f;
                poseGo.SetPositionAndRotation(Vector3.Lerp(poseGo.position, pos, t), Quaternion.Slerp(poseGo.rotation, rot, t));
            }
            Current.Name = name; Current.ScreenMarkers = screen; Current.LastSeen = Time.time;
            Current.MarkerSize = A4 * scale;
        }

        // Plane pose from the 4 marker rays (A4 page), rescaled by the depth/plane hit at the page centre.
        bool Pose(Vector2[] screen, out Vector3 pos, out Quaternion rot, out float scale)
        {
            pos = default; rot = default; scale = 1;
            var cam = arCamera.transform; float s = A4.x / 1240f;
            var src = new P2[4]; var dst = new P2[4];
            for (int i = 0; i < 4; i++)
            {
                var m = MarkerDetector.TemplateMarkers[i];
                src[i] = new P2((m.X - 620) * s, (877 - m.Y) * s);                       // page metres, y up, origin = centre
                var d = cam.InverseTransformDirection(arCamera.ScreenPointToRay(screen[i]).direction);
                if (d.z <= 1e-4f) return false;
                dst[i] = new P2(d.x / d.z, d.y / d.z);                                   // normalised camera coordinates
            }
            var Hm = Homography.Solve(src, dst);
            if (Hm == null) return false;
            var h1 = new Vector3((float)Hm[0], (float)Hm[3], (float)Hm[6]);
            var h2 = new Vector3((float)Hm[1], (float)Hm[4], (float)Hm[7]);
            var h3 = new Vector3((float)Hm[2], (float)Hm[5], (float)Hm[8]);
            float lam = 2f / (h1.magnitude + h2.magnitude);
            var r1 = h1 * lam; var r2 = h2 * lam; var t = h3 * lam;
            if (t.z < 0) { r1 = -r1; r2 = -r2; t = -t; }
            r1.Normalize(); r2 = (r2 - Vector3.Dot(r1, r2) * r1).normalized;
            var n = Vector3.Cross(r1, r2).normalized; if (Vector3.Dot(n, -t) < 0) n = -n;   // out of the page, toward the camera
            pos = cam.TransformPoint(t);
            rot = cam.rotation * Quaternion.LookRotation(r2, n);

            // real size: a screen-shown sheet is smaller (and nearer) than A4 — trust the depth / plane hit when there is one
            if (raycasts)
            {
                var hits = new List<ARRaycastHit>();
                var c = arCamera.WorldToScreenPoint(pos);
                if (raycasts.Raycast(new Vector2(c.x, c.y), hits, TrackableType.Planes | TrackableType.FeaturePoint | TrackableType.Depth) && hits.Count > 0)
                {
                    float dHit = hits[0].distance, dPnp = Vector3.Distance(cam.position, pos);
                    float k = dHit / Mathf.Max(1e-3f, dPnp);
                    if (k > 0.2f && k < 3f) { scaleHist.Add(k); if (scaleHist.Count > 7) scaleHist.RemoveAt(0); }
                }
            }
            if (scaleHist.Count > 0) { var sorted = new List<float>(scaleHist); sorted.Sort(); scale = sorted[sorted.Count / 2]; }
            pos = cam.position + (pos - cam.position) * scale;
            return true;
        }

        // ---- frames ----
        void Grab(ref RenderTexture rt, ref Texture2D tex, ref byte[] lum, int w, int h)
        {
            if (!rt || rt.width != w || rt.height != h)
            {
                if (rt) { rt.Release(); Destroy(rt); }
                rt = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            }
            if (!tex || tex.width != w || tex.height != h) { if (tex) Destroy(tex); tex = new Texture2D(w, h, TextureFormat.RGBA32, false); }
            Graphics.Blit(null, rt, cameraBackground.material);
            var prev = RenderTexture.active; RenderTexture.active = rt;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
            RenderTexture.active = prev;
            var px = tex.GetRawTextureData<Color32>();                 // no managed copy (GetPixels32 allocated w*h*4 bytes)
            if (lum == null || lum.Length != w * h) lum = new byte[w * h];
            for (int i = 0; i < lum.Length; i++) { var c = px[i]; lum[i] = (byte)((c.r * 77 + c.g * 150 + c.b * 29) >> 8); }
        }

        void OnDestroy()
        {
            if (small) { small.Release(); Destroy(small); }
            if (smallTex) Destroy(smallTex);
            if (fullRt) { fullRt.Release(); Destroy(fullRt); }
            if (fullTex) Destroy(fullTex);
        }
    }
}
