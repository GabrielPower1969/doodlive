// DoodLive app flow (port of web/app.js): camera permission -> ARCore check -> scan the tracked sheet ->
// warp the colouring onto the angel -> Enter -> Idle, tap = Blow (fanfare + voice).
//
// Capture: the camera frame is copied in screen space (ARCameraBackground material -> RenderTexture), so the
// tracked sheet's corners project with Camera.WorldToScreenPoint and no sensor-orientation math. The 4 printed
// markers are then refined in that frame (PageWarp.RefineMarkers) and the art rectangle is warped to 1024².
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.ARFoundation;
using UnityEngine.XR.ARSubsystems;
#if UNITY_ANDROID
using UnityEngine.Android;
#endif

namespace DoodLive
{
    public class ARColoringController : MonoBehaviour
    {
        public const int TexSize = 1024;

        [Header("AR")]
        public ARSession session;
        public ARTrackedImageManager trackedImages;
        public ARCameraManager cameraManager;
        public ARCameraBackground cameraBackground;
        public Camera arCamera;

        [Header("Angel")]
        public Animator angel;                  // Angel prefab instance (Enter -> Idle <-> Blow)
        public Material[] pageMaterials;        // every material that samples the scanned page
        public Texture2D demoTexture;           // assets/demo-colored.png (show mode / editor)
        [Tooltip("Angel height on the sheet, as a fraction of the art width (web: 0.75)")]
        public float scaleOnSheet = 0.75f;

        [Header("Sound")]
        public AudioSource sfx;
        public AudioSource voice;
        public AudioClip fanfare, chime, hello;
        public AudioClip[] lines;

        enum Mode { Boot, NoAR, Scan, Live }
        Mode mode = Mode.Boot;
        Template tpl;
        Transform holder;
        Texture2D pageTex;
        Color32[] rawPx, cleanPx;
        bool showLines, arReady, showMode, capturing;
        string status = "";
        float trackedFor;
        int lineIdx;
        static readonly int BlowId = Animator.StringToHash("Blow");
        static readonly int BlowState = Animator.StringToHash("Blow");

        void Start()
        {
            tpl = Template.Load();
            pageTex = new Texture2D(TexSize, TexSize, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = "ScannedPage" };
            holder = new GameObject("AngelHolder").transform;
            angel.transform.SetParent(holder, false);
            angel.gameObject.SetActive(false);
            if (session) session.enabled = false;
            Screen.sleepTimeout = SleepTimeout.NeverSleep;
            StartCoroutine(Boot());
        }

        IEnumerator Boot()
        {
            status = "正在打开相机…";
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera))
            {
                bool answered = false;
                var cb = new PermissionCallbacks();
                cb.PermissionGranted += _ => answered = true;
                cb.PermissionDenied += _ => answered = true;
                cb.PermissionDeniedAndDontAskAgain += _ => answered = true;
                Permission.RequestUserPermission(Permission.Camera, cb);
                while (!answered) yield return null;
            }
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera))
            {
                mode = Mode.NoAR;
                status = "没有相机权限。可以先看演示，或在系统设置里允许相机后再试";
                yield break;
            }
#endif
            if (ARSession.state == ARSessionState.None || ARSession.state == ARSessionState.CheckingAvailability)
                yield return ARSession.CheckAvailability();
            if (ARSession.state == ARSessionState.NeedsInstall)
                yield return ARSession.Install();
            if (ARSession.state == ARSessionState.Unsupported || ARSession.state == ARSessionState.NeedsInstall)
            {
                mode = Mode.NoAR;
                status = "这台设备用不了 ARCore。可以先看演示";
                yield break;
            }
            session.enabled = true;
            arReady = true;
            StartScan();
        }

        void StartScan()
        {
            mode = Mode.Scan;
            showMode = false;
            trackedFor = 0;
            angel.gameObject.SetActive(false);
            status = "把整张涂色纸平放，用手机对准它";
        }

        ARTrackedImage Sheet()
        {
            if (!trackedImages) return null;
            foreach (var t in trackedImages.trackables)
                if (t.trackingState == TrackingState.Tracking) return t;
            return null;
        }

        void Update()
        {
            if (mode == Mode.Scan && !capturing)
            {
                var sheet = Sheet();
                trackedFor = sheet ? trackedFor + Time.deltaTime : 0;
                status = sheet ? "找到了！拿稳别动…" : "把整张涂色纸平放，用手机对准它";
                if (sheet && trackedFor > 1.5f) StartCoroutine(Capture(sheet));   // let ARCore settle pose + size first
            }
            if (mode == Mode.Live && TappedOutsideUI()) Blow();
        }

        // ---------------- capture / bake ----------------
        IEnumerator Capture(ARTrackedImage sheet)
        {
            capturing = true;
            yield return new WaitForEndOfFrame();
            int W = Screen.width, H = Screen.height;
            var rt = RenderTexture.GetTemporary(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            Graphics.Blit(null, rt, cameraBackground.material);
            var frameTex = new Texture2D(W, H, TextureFormat.RGBA32, false);
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            frameTex.ReadPixels(new Rect(0, 0, W, H), 0, 0, false);
            RenderTexture.active = prev;
            RenderTexture.ReleaseTemporary(rt);
            var frame = frameTex.GetPixels32();
            Destroy(frameTex);

            // template markers -> world (on the tracked image plane) -> screen px (y up)
            var expected = new Vector2[4];
            for (int i = 0; i < 4; i++)
            {
                var s = arCamera.WorldToScreenPoint(sheet.transform.TransformPoint(PageToLocal(sheet, tpl.markers[i])));
                expected[i] = new Vector2(s.x, s.y);
            }
            float markerPx = Vector2.Distance(expected[0], expected[1]) / Mathf.Max(1, tpl.markers[1].x - tpl.markers[0].x) * 64;
            float radius = Mathf.Max(16, markerPx * 1.5f);
            var pts = PageWarp.RefineMarkers(frame, W, H, expected, radius);
            if (pts == null)
            {
                // Some GLES drivers return the blit upside down: try the mirrored guess before falling back.
                var flipped = new Vector2[4];
                for (int i = 0; i < 4; i++) flipped[i] = new Vector2(expected[i].x, H - 1 - expected[i].y);
                var f = PageWarp.RefineMarkers(frame, W, H, flipped, radius);
                if (f != null) { for (int i = 0; i < 4; i++) f[i].y = H - 1 - f[i].y; FlipRows(frame, W, H); pts = f; }
            }
            bool refined = pts != null;
            if (!refined) pts = expected;
            Debug.Log($"DoodLive capture {W}x{H} markers refined={refined} pts={string.Join(" ", pts)}");

            var Hm = PageWarp.Homography(tpl.markers, pts);
            if (Hm == null) { capturing = false; trackedFor = 0; yield break; }
            rawPx = PageWarp.WarpArt(frame, W, H, Hm, tpl.art, TexSize);
            PageWarp.WhiteBalance(rawPx);
            cleanPx = PageWarp.EraseLines(rawPx, TexSize, TexSize);
            ApplyPage();

            PlaceOnSheet(sheet);
            capturing = false;
            Reveal();
        }

        static void FlipRows(Color32[] px, int W, int H)
        {
            var row = new Color32[W];
            for (int y = 0; y < H / 2; y++)
            {
                System.Array.Copy(px, y * W, row, 0, W);
                System.Array.Copy(px, (H - 1 - y) * W, px, y * W, W);
                System.Array.Copy(row, 0, px, (H - 1 - y) * W, W);
            }
        }

        /// <summary>Template px (y down from the sheet's top-left) to the tracked image's local plane (XZ, +Z = top).</summary>
        Vector3 PageToLocal(ARTrackedImage sheet, Vector2 px)
        {
            var size = sheet.size;
            return new Vector3((px.x / tpl.page.x - 0.5f) * size.x, 0, (0.5f - px.y / tpl.page.y) * size.y);
        }

        // Where she stands: the centre of the drawing (paper or tablet screen), up = gravity (never the sheet normal,
        // LESSONS L14), facing the viewer. She is parented to the tracked sheet: ARCore treats an augmented image as an
        // anchor, keeps refining its pose and remembers it when you walk away, so she stays on the page instead of
        // drifting with the world map (LESSONS L24). If ARCore drops the image we fall back to a plain ARAnchor.
        ARTrackedImage anchoredSheet;
        Vector2 placePage;          // where she stands, in template px
        float placeFlat, placeYaw;  // 1 = sheet lying flat; world yaw facing the viewer at placement

        void PlaceOnSheet(ARTrackedImage sheet)
        {
            var st = sheet.transform;
            placeFlat = Mathf.InverseLerp(0.45f, 0.85f, Mathf.Abs(Vector3.Dot(st.up, Vector3.up)));
            placePage = new Vector2(tpl.art.x + tpl.art.width / 2, tpl.art.y + tpl.art.height / 2);
            var pos = st.TransformPoint(PageToLocal(sheet, placePage));
            var toViewer = Vector3.ProjectOnPlane(arCamera.transform.position - pos, Vector3.up);
            if (toViewer.sqrMagnitude < 1e-4f) toViewer = Vector3.ProjectOnPlane(-st.forward, Vector3.up);   // towards the sheet's bottom edge
            placeYaw = Quaternion.LookRotation(toViewer.normalized, Vector3.up).eulerAngles.y;
            var oldAnchor = holder.parent && holder.parent.GetComponent<ARAnchor>() ? holder.parent.gameObject : null;
            holder.SetParent(st, false);
            if (oldAnchor) Destroy(oldAnchor);
            anchoredSheet = sheet;
            FitToSheet(1f);
        }

        // Re-fit every frame to ARCore's latest estimate of the sheet (pose AND physical size both get refined after
        // placement). Position/scale follow the sheet; rotation stays gravity-up at the placement yaw.
        void FitToSheet(float k)
        {
            var sheet = anchoredSheet; if (!sheet) return;
            var st = sheet.transform;
            var pos = st.TransformPoint(PageToLocal(sheet, placePage)) + st.up * (0.03f * (1 - placeFlat) * sheet.size.x);
            float scale = tpl.art.width / tpl.page.x * sheet.size.x * Mathf.Lerp(1f, scaleOnSheet, placeFlat);
            holder.position = Vector3.Lerp(holder.position, pos, k);
            holder.rotation = Quaternion.Euler(0, placeYaw, 0);
            var ls = holder.parent ? holder.parent.lossyScale : Vector3.one;
            holder.localScale = Vector3.Lerp(holder.localScale, Vector3.one * scale / Mathf.Max(1e-4f, ls.x), k);
        }

        void LateUpdate()
        {
            if (mode == Mode.Live && !showMode && anchoredSheet && anchoredSheet.trackingState != TrackingState.None)
                FitToSheet(Mathf.Clamp01(Time.deltaTime * 8f));   // smooth out per-frame jitter
        }

        /// <summary>Pin the angel to a world anchor at her current pose (show mode, or the sheet trackable went away).</summary>
        void AnchorHere()
        {
            if (!arReady) { holder.SetParent(null, true); return; }
            var go = new GameObject("AngelAnchor");
            go.transform.SetPositionAndRotation(holder.position, holder.rotation);
            go.AddComponent<ARAnchor>();
            var old = holder.parent;
            holder.SetParent(go.transform, true);
            if (old && old.GetComponent<ARAnchor>()) Destroy(old.gameObject);
            anchoredSheet = null;
        }

        void OnEnable() { if (trackedImages) trackedImages.trackedImagesChanged += OnImagesChanged; }
        void OnDisable() { if (trackedImages) trackedImages.trackedImagesChanged -= OnImagesChanged; }
        void OnImagesChanged(ARTrackedImagesChangedEventArgs e)
        {
            if (anchoredSheet && e.removed.Contains(anchoredSheet)) AnchorHere();   // never let her be destroyed with it
        }

        void PlaceInFront()
        {
            var cam = arCamera.transform;
            var fwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up);
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
            fwd.Normalize();
            holder.SetParent(null, false);
            holder.position = cam.position + fwd * 0.7f - Vector3.up * 0.25f;
            holder.rotation = Quaternion.LookRotation(fwd, Vector3.up);
            holder.localScale = Vector3.one * 0.35f;
            AnchorHere();   // stays where it appeared when you walk around
        }

        void ApplyPage()
        {
            pageTex.SetPixels32(showLines ? rawPx : cleanPx);
            pageTex.Apply(false);
            foreach (var m in pageMaterials) m.SetTexture("_BaseMap", pageTex);
        }

        void UseDemoTexture()
        {
            rawPx = cleanPx = null;
            foreach (var m in pageMaterials) m.SetTexture("_BaseMap", demoTexture);
        }

        // ---------------- flow ----------------
        void Reveal()
        {
            mode = Mode.Live;
            angel.gameObject.SetActive(true);
            angel.Play("Enter", 0, 0);
            sfx.PlayOneShot(chime);
            voice.Stop(); voice.clip = hello; voice.PlayDelayed(0.9f);
            status = "点一下天使，听她吹响号角";
        }

        void Blow()
        {
            var st = angel.GetCurrentAnimatorStateInfo(0);
            if (st.shortNameHash == BlowState || angel.IsInTransition(0)) return;
            angel.SetTrigger(BlowId);
            sfx.PlayOneShot(fanfare);
            if (lines.Length > 0) { voice.Stop(); voice.clip = lines[lineIdx++ % lines.Length]; voice.PlayDelayed(fanfare.length * 0.95f); }
        }

        void ShowDemo()
        {
            showMode = true;
            if (!arReady)
            {
                // no camera feed: plain sky backdrop instead of a black frame
                if (cameraBackground) cameraBackground.enabled = false;
                arCamera.clearFlags = CameraClearFlags.SolidColor;
                arCamera.backgroundColor = new Color(0.55f, 0.72f, 0.92f);
                arCamera.transform.SetPositionAndRotation(new Vector3(0, 1.2f, 0), Quaternion.identity);
            }
            UseDemoTexture();
            PlaceInFront();
            Reveal();
        }

        public void Action() => Blow(); // for tests / remote debugging

        // ---------------- UI (IMGUI keeps the prototype scene-free) ----------------
        readonly List<Rect> uiRects = new List<Rect>();
        GUIStyle button, label;

        bool TappedOutsideUI()
        {
            Vector2? p = null;
            if (Input.touchCount > 0 && Input.GetTouch(0).phase == TouchPhase.Began) p = Input.GetTouch(0).position;
            else if (Input.GetMouseButtonDown(0)) p = Input.mousePosition;
            if (p == null) return false;
            var gp = new Vector2(p.Value.x, Screen.height - p.Value.y);
            foreach (var r in uiRects) if (r.Contains(gp)) return false;
            return true;
        }

        void OnGUI()
        {
            if (button == null)
            {
                var font = Font.CreateDynamicFontFromOSFont(new[] { "Noto Sans CJK SC", "Noto Sans SC", "SamsungOneUI", "Droid Sans Fallback", "PingFang SC", "sans-serif" }, 32);
                int fs = Mathf.RoundToInt(Mathf.Min(Screen.width, Screen.height) / 26f);   // same in portrait and landscape
                button = new GUIStyle(GUI.skin.button) { font = font, fontSize = fs };
                label = new GUIStyle(GUI.skin.label) { font = font, fontSize = fs, alignment = TextAnchor.MiddleCenter, wordWrap = true };
                label.normal.textColor = Color.white;
            }
            uiRects.Clear();
            float u = Mathf.Min(Screen.width, Screen.height) / 12.5f, w = Screen.width;
            float top = Screen.height - Screen.safeArea.yMax, bottom = Screen.safeArea.yMin; // safeArea is y-up, GUI is y-down
            GUI.Box(new Rect(0, top, w, u * 1.6f), GUIContent.none);
            GUI.Label(new Rect(u * 0.3f, top, w - u * 0.6f, u * 1.6f), status, label);

            var buttons = new List<(string, System.Action)>();
            if (mode == Mode.NoAR || mode == Mode.Scan) buttons.Add(("看演示", ShowDemo));
            if (mode == Mode.Scan && Sheet() && !capturing) buttons.Add(("拍下来", () => StartCoroutine(Capture(Sheet()))));
            if (mode == Mode.Live)
            {
                buttons.Add(("吹号角", Blow));
                if (arReady) buttons.Add(("重新扫描", StartScan));
                if (rawPx != null) buttons.Add((showLines ? "线条：显示" : "线条：隐藏", () => { showLines = !showLines; ApplyPage(); }));
                if (arReady && !showMode) buttons.Add(("展示模式", () => { showMode = true; PlaceInFront(); }));
            }
            float bw = (w - u * 0.5f) / Mathf.Max(1, buttons.Count), y = Screen.height - bottom - u * 1.6f;
            for (int i = 0; i < buttons.Count; i++)
            {
                var r = new Rect(u * 0.25f + i * bw + 4, y, bw - 8, u * 1.3f);
                uiRects.Add(r);
                if (GUI.Button(r, buttons[i].Item1, button)) buttons[i].Item2();
            }
            uiRects.Add(new Rect(0, 0, w, top + u * 1.8f));
        }
    }
}
