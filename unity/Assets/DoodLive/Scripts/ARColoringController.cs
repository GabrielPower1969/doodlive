// DoodLive app flow — the state machine from docs/UX-PLAN.md §3 (Unity is the reference; web/app.js mirrors it).
//
//   Home ─► Permission ─► Scan.Search ─► Scan.Locked(1.5 s) ─► Reveal(≤4 s, uninterruptible) ─► Live.Idle
//                            │  └─30 s─► Scan.Help                                              │  ▲
//                            └──────────────────────────────── Live.Lost ◄── tracking lost 1.5 s ─┘  │
//                                                   Live.Blow / Live.Read / Live.Greet ───────────────┘
//   Paused: app in background — music fades out 0.3 s, back in 0.6 s, no re-scan.
//
// Stop/go rule: stop where the child must act (press, aim), go where the system can tell (locked 1.5 s, action
// finished). Every automatic step has visible progress and a timeout with a concrete hint. UI motion ≤ 300 ms,
// character motion ≤ 1.5 s; only Reveal blocks input. Sound: voice > sfx > music; voices never overlap.
//
// Capture: the camera frame is copied in screen space (ARCameraBackground material -> RenderTexture), so the tracked
// sheet's corners project with Camera.WorldToScreenPoint; the 4 printed markers are refined in that frame
// (PageWarp.RefineMarkers) and the art rectangle is warped to 1024².
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
        public Animator angel;
        public Material[] pageMaterials;
        public Texture2D demoTexture;
        [Tooltip("Angel height on the sheet, as a fraction of the art width (web: 0.75)")]
        public float scaleOnSheet = 0.75f;

        [Header("Sound")]
        public AudioSource sfx, voice, music;
        public float musicBed = 0.22f;
        public AudioClip fanfare, chime, hello, swell;
        public AudioClip[] lines;           // Blow lines, rotate
        public AudioClip[] greets;          // idle greetings (fly / wow / laugh)

        // ---------------- timings (seconds) — UX-PLAN §3/§4 ----------------
        const float LockSeconds = 1.5f, HelpAfter = 30f, LostAfter = 1.5f, GreetAfter = 20f, GreetEvery = 25f, GreetMax = 2;
        const float RevealSeconds = 1.4f, BlowSeconds = 3.3f, ReadStep = 1.3f;

        public enum State { Home, Permission, ScanSearch, ScanLocked, ScanHelp, Reveal, LiveIdle, LiveBlow, LiveRead, LiveGreet, LiveLost }
        public State state = State.Home;
        float stateT;                       // seconds in the current state
        bool paused;

        Template tpl;
        Transform holder;
        Texture2D pageTex;
        Color32[] rawPx, cleanPx;
        bool showLines, arReady, arUnsupported, showMode, capturing, moreOpen, muted;
        string statusKey = "", statusArg = "";
        float lockedFor, untracked, idleSince, lastGreet; int greetCount, lineIdx, greetIdx;
        static readonly int BlowId = Animator.StringToHash("Blow"), BlowState = Animator.StringToHash("Blow");

        public static string Fingerprint => Resources.Load<TextAsset>("build_fingerprint")?.text.Trim() ?? Application.version;

        // =====================================================================================================
        void Start()
        {
            Debug.Log($"DoodLive build {Fingerprint}");          // scripts/install-apk.sh greps this line
            tpl = Template.Load();
            pageTex = new Texture2D(TexSize, TexSize, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, name = "ScannedPage" };
            holder = new GameObject("AngelHolder").transform;
            angel.transform.SetParent(holder, false);
            angel.gameObject.SetActive(false);
            if (session) session.enabled = false;
            Screen.sleepTimeout = SleepTimeout.NeverSleep;
            muted = PlayerPrefs.GetInt("muted", 0) == 1; AudioListener.volume = muted ? 0 : 1;
            MakeCues();
            Go(State.Home);
        }

        void Go(State s)
        {
            if (state == s) return;
            Debug.Log($"DoodLive state {state} -> {s}");
            state = s; stateT = 0;
            switch (s)
            {
                case State.Home: statusKey = ""; angel.gameObject.SetActive(false); break;
                case State.Permission: statusKey = "openingCam"; StartCoroutine(Boot()); break;
                case State.ScanSearch: showMode = false; lockedFor = 0; angel.gameObject.SetActive(false); statusKey = "fit"; break;
                case State.ScanLocked: statusKey = "found"; Cue(cueLock); break;
                case State.ScanHelp: statusKey = ""; break;
                case State.Reveal: StartReveal(); break;
                case State.LiveIdle: idleSince = Time.time; if (statusKey != "lost") statusKey = "tap"; break;
                case State.LiveLost: statusKey = "lost"; Cue(cueLost); break;
            }
        }

        IEnumerator Boot()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera))
            {
                bool answered = false;
                var cb = new PermissionCallbacks();
                cb.PermissionGranted += _ => answered = true; cb.PermissionDenied += _ => answered = true; cb.PermissionDeniedAndDontAskAgain += _ => answered = true;
                Permission.RequestUserPermission(Permission.Camera, cb);
                while (!answered) yield return null;
            }
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera)) { statusKey = "noPerm"; Go(State.Home); statusKey = "noPerm"; yield break; }
#endif
            if (ARSession.state == ARSessionState.None || ARSession.state == ARSessionState.CheckingAvailability) yield return ARSession.CheckAvailability();
            if (ARSession.state == ARSessionState.NeedsInstall) yield return ARSession.Install();
            if (ARSession.state == ARSessionState.Unsupported || ARSession.state == ARSessionState.NeedsInstall)
            { arUnsupported = true; statusKey = "noAR"; Go(State.Home); statusKey = "noAR"; yield break; }
            session.enabled = true; arReady = true;
            Go(State.ScanSearch);
        }

        ARTrackedImage Sheet()
        {
            if (!trackedImages) return null;
            foreach (var t in trackedImages.trackables) if (t.trackingState == TrackingState.Tracking) return t;
            return null;
        }

        void Update()
        {
            float dt = Time.deltaTime; stateT += dt;
            TickAudio(dt);
            if (paused) return;
            switch (state)
            {
                case State.ScanSearch:
                    if (Sheet()) Go(State.ScanLocked);
                    else if (stateT > HelpAfter) Go(State.ScanHelp);
                    break;
                case State.ScanLocked:
                    if (!Sheet()) { lockedFor = 0; Go(State.ScanSearch); break; }
                    lockedFor += dt;
                    if (lockedFor >= LockSeconds && !capturing) StartCoroutine(Capture(Sheet()));
                    break;
                case State.ScanHelp:
                    if (Sheet()) Go(State.ScanLocked);
                    break;
                case State.Reveal:
                    if (stateT >= RevealSeconds) Go(State.LiveIdle);
                    break;
                case State.LiveIdle:
                    if (TrackingLost()) { untracked += dt; if (untracked > LostAfter) Go(State.LiveLost); } else untracked = 0;
                    if (Time.time - idleSince > GreetAfter && greetCount < GreetMax && Time.time - lastGreet > GreetEvery && !voice.isPlaying) Greet();
                    if (TappedOutsideUI()) Blow();
                    break;
                case State.LiveBlow:
                    if (stateT >= BlowSeconds) Go(State.LiveIdle);
                    break;
                case State.LiveGreet:
                    if (!voice.isPlaying && stateT > 0.5f) Go(State.LiveIdle);
                    break;
                case State.LiveLost:
                    if (!TrackingLost()) { untracked = 0; statusKey = "tap"; Go(State.LiveIdle); }
                    break;
            }
            if (Input.GetKeyDown(KeyCode.Escape)) Back();   // Android back button
        }

        bool TrackingLost() => !showMode && anchoredSheet && anchoredSheet.trackingState != TrackingState.Tracking;

        void Back()
        {
            if (state >= State.LiveIdle) Rescan();
            else if (state >= State.ScanSearch && state != State.Reveal) Go(State.Home);
            else if (state == State.Home) Application.Quit();
        }

        void Rescan()
        {
            StopVoice(); greetCount = 0; moreOpen = false;
            if (arReady) Go(State.ScanSearch); else Go(State.Home);
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
            var prev = RenderTexture.active; RenderTexture.active = rt;
            frameTex.ReadPixels(new Rect(0, 0, W, H), 0, 0, false);
            RenderTexture.active = prev; RenderTexture.ReleaseTemporary(rt);
            var frame = frameTex.GetPixels32(); Destroy(frameTex);

            var expected = new Vector2[4];
            for (int i = 0; i < 4; i++) { var s = arCamera.WorldToScreenPoint(sheet.transform.TransformPoint(PageToLocal(sheet, tpl.markers[i]))); expected[i] = new Vector2(s.x, s.y); }
            float markerPx = Vector2.Distance(expected[0], expected[1]) / Mathf.Max(1, tpl.markers[1].x - tpl.markers[0].x) * 64;
            float radius = Mathf.Max(16, markerPx * 1.5f);
            var pts = PageWarp.RefineMarkers(frame, W, H, expected, radius);
            if (pts == null)
            {
                var flipped = new Vector2[4];
                for (int i = 0; i < 4; i++) flipped[i] = new Vector2(expected[i].x, H - 1 - expected[i].y);
                var f = PageWarp.RefineMarkers(frame, W, H, flipped, radius);
                if (f != null) { for (int i = 0; i < 4; i++) f[i].y = H - 1 - f[i].y; FlipRows(frame, W, H); pts = f; }
            }
            bool refined = pts != null; if (!refined) pts = expected;
            Debug.Log($"DoodLive capture {W}x{H} markers refined={refined}");
            var Hm = PageWarp.Homography(tpl.markers, pts);
            if (Hm == null) { capturing = false; lockedFor = 0; Go(State.ScanSearch); yield break; }
            rawPx = PageWarp.WarpArt(frame, W, H, Hm, tpl.art, TexSize);
            PageWarp.WhiteBalance(rawPx);
            cleanPx = PageWarp.EraseLines(rawPx, TexSize, TexSize);
            ApplyPage();
            PlaceOnSheet(sheet);
            ShowTitle(sheet.referenceImage.name);
            capturing = false;
            statusKey = "recognised";
            Go(State.Reveal);
        }

        static void FlipRows(Color32[] px, int W, int H)
        {
            var row = new Color32[W];
            for (int y = 0; y < H / 2; y++)
            {
                System.Array.Copy(px, y * W, row, 0, W); System.Array.Copy(px, (H - 1 - y) * W, px, y * W, W); System.Array.Copy(row, 0, px, (H - 1 - y) * W, W);
            }
        }

        Vector3 PageToLocal(ARTrackedImage sheet, Vector2 px)
        {
            var size = sheet.size;
            return new Vector3((px.x / tpl.page.x - 0.5f) * size.x, 0, (0.5f - px.y / tpl.page.y) * size.y);
        }

        // ---------------- placement (LESSONS L14, L24, L25) ----------------
        ARTrackedImage anchoredSheet;
        Vector2 placePage; float placeFlat, placeYaw;

        void PlaceOnSheet(ARTrackedImage sheet)
        {
            var st = sheet.transform;
            placeFlat = Mathf.InverseLerp(0.45f, 0.85f, Mathf.Abs(Vector3.Dot(st.up, Vector3.up)));
            placePage = new Vector2(tpl.art.x + tpl.art.width / 2, tpl.art.y + tpl.art.height / 2);
            var pos = st.TransformPoint(PageToLocal(sheet, placePage));
            var toViewer = Vector3.ProjectOnPlane(arCamera.transform.position - pos, Vector3.up);
            if (toViewer.sqrMagnitude < 1e-4f) toViewer = Vector3.ProjectOnPlane(-st.forward, Vector3.up);
            placeYaw = Quaternion.LookRotation(toViewer.normalized, Vector3.up).eulerAngles.y;
            var oldAnchor = holder.parent && holder.parent.GetComponent<ARAnchor>() ? holder.parent.gameObject : null;
            holder.SetParent(st, false);
            if (oldAnchor) Destroy(oldAnchor);
            anchoredSheet = sheet;
            FitToSheet(1f);
        }

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
            if (state >= State.LiveIdle && !showMode && anchoredSheet && anchoredSheet.trackingState == TrackingState.Tracking)
                FitToSheet(Mathf.Clamp01(Time.deltaTime * 8f));
        }

        void AnchorHere()
        {
            if (!arReady) { holder.SetParent(null, true); return; }
            var go = new GameObject("AngelAnchor");
            go.transform.SetPositionAndRotation(holder.position, holder.rotation); go.AddComponent<ARAnchor>();
            var old = holder.parent; holder.SetParent(go.transform, true);
            if (old && old.GetComponent<ARAnchor>()) Destroy(old.gameObject);
            anchoredSheet = null;
        }

        void OnEnable() { if (trackedImages) trackedImages.trackedImagesChanged += OnImagesChanged; }
        void OnDisable() { if (trackedImages) trackedImages.trackedImagesChanged -= OnImagesChanged; }
        void OnImagesChanged(ARTrackedImagesChangedEventArgs e) { if (anchoredSheet && e.removed.Contains(anchoredSheet)) AnchorHere(); }

        void PlaceInFront()
        {
            var cam = arCamera.transform;
            var fwd = Vector3.ProjectOnPlane(cam.forward, Vector3.up); if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward; fwd.Normalize();
            holder.SetParent(null, false);
            holder.position = cam.position + cam.forward * 0.8f;
            holder.rotation = Quaternion.LookRotation(-fwd, Vector3.up);
            holder.localScale = Vector3.one * 0.35f;
            AnchorHere();
        }

        void ApplyPage()
        {
            if (rawPx == null) return;
            pageTex.SetPixels32(showLines ? rawPx : cleanPx); pageTex.Apply(false);
            foreach (var m in pageMaterials) m.SetTexture("_BaseMap", pageTex);
        }
        void UseDemoTexture() { rawPx = cleanPx = null; foreach (var m in pageMaterials) m.SetTexture("_BaseMap", demoTexture); }

        // ---------------- titles ----------------
        string titleKey = "angel";
        bool pinyinMode { get => PlayerPrefs.GetInt("titlePinyin", 1) == 1; set => PlayerPrefs.SetInt("titlePinyin", value ? 1 : 0); }
        Transform Titles => angel.transform.Find("titles");
        void ShowTitle(string sheetName)
        {
            if (sheetName != null) { titleKey = "angel"; foreach (var k in new[] { "fiery", "wrath", "holy" }) if (sheetName.StartsWith(k)) titleKey = k; }
            var titles = Titles; if (!titles) return;
            foreach (Transform t in titles)
            {
                t.gameObject.SetActive(t.name == titleKey || t.name.StartsWith("holder_") || t.name.StartsWith(titleKey + "_"));
                foreach (Transform part in t.GetComponentsInChildren<Transform>(true))
                {
                    if (part.name == "english") part.gameObject.SetActive(!pinyinMode);
                    if (part.name == "pinyin") part.gameObject.SetActive(pinyinMode);
                }
            }
        }

        // ---------------- flow actions ----------------
        void StartReveal()
        {
            angel.gameObject.SetActive(true);
            angel.Play("Enter", 0, 0);
            sfx.PlayOneShot(chime);
            if (swell) sfx.PlayOneShot(swell, 0.8f);
            if (music && !music.isPlaying) { music.volume = musicBed; music.Play(); }
            PlayVoice(hello, 0.9f);
            greetCount = 0; moreOpen = false; flashT = Time.time;
            statusKey = "tap";
        }

        void Blow()
        {
            if (state != State.LiveIdle) return;
            Cue(cueClick);
            Go(State.LiveBlow);
            angel.SetTrigger(BlowId);
            sfx.PlayOneShot(fanfare);
            if (lines != null && lines.Length > 0) PlayVoice(lines[lineIdx++ % lines.Length], fanfare.length * 0.95f);
            idleSince = Time.time;
        }

        void Greet()
        {
            if (greets == null || greets.Length == 0) { idleSince = Time.time; return; }
            Go(State.LiveGreet);
            greetCount++; lastGreet = Time.time; idleSince = Time.time;
            PlayVoice(greets[greetIdx++ % greets.Length], 0);
            titleBounce = Time.time;
        }

        IEnumerator ReadSequence()
        {
            // 汉字 → 拼音 → 英文: each part of the 3D title grows for a beat with a chime (voice comes in M3)
            Go(State.LiveRead);
            var titles = Titles;
            string[] order = { "hanzi", pinyinMode ? "pinyin" : "english", pinyinMode ? "english" : "pinyin" };
            string[] keys = { "readHanzi", pinyinMode ? "readPinyin" : "readEnglish", pinyinMode ? "readEnglish" : "readPinyin" };
            for (int i = 0; i < order.Length && titles; i++)
            {
                statusKey = keys[i]; sfx.PlayOneShot(chime, 0.5f);
                var part = FindPart(titles, order[i]);
                bool wasActive = part && part.gameObject.activeSelf;
                if (part) { part.gameObject.SetActive(true); StartCoroutine(Punch(part, ReadStep)); }
                yield return new WaitForSeconds(ReadStep);
                if (part && !wasActive) part.gameObject.SetActive(false);
            }
            statusKey = "tap"; idleSince = Time.time;
            Go(State.LiveIdle);
        }
        Transform FindPart(Transform titles, string name)
        {
            foreach (Transform t in titles) if (t.gameObject.activeSelf) foreach (var p in t.GetComponentsInChildren<Transform>(true)) if (p.name == name) return p;
            return null;
        }
        IEnumerator Punch(Transform t, float secs)
        {
            var s0 = t.localScale; float t0 = Time.time;
            while (Time.time - t0 < secs) { float k = (Time.time - t0) / secs; t.localScale = s0 * (1 + 0.18f * Mathf.Sin(Mathf.PI * Mathf.Clamp01(k * 1.25f))); yield return null; }
            t.localScale = s0;
        }

        void ShowDemo()
        {
            Cue(cueClick);
            showMode = true;
            if (!arReady)
            {   // no AR session: stop the pose driver (it would snap the camera back to the origin), sky backdrop, fixed camera
                var tpd = arCamera.GetComponent<UnityEngine.InputSystem.XR.TrackedPoseDriver>(); if (tpd) tpd.enabled = false;
                if (cameraBackground) cameraBackground.enabled = false;
                arCamera.clearFlags = CameraClearFlags.SolidColor; arCamera.backgroundColor = new Color(0.55f, 0.72f, 0.92f);
                arCamera.transform.SetPositionAndRotation(new Vector3(0, 1.2f, 0), Quaternion.identity);
            }
            UseDemoTexture(); PlaceInFront(); ShowTitle("angel");
            Go(State.Reveal);
        }

        public void Action() => Blow();

        // ---------------- audio director: voice > sfx > music, voices never overlap ----------------
        AudioSource voiceOld; float voiceFade;
        AudioClip cueClick, cueLock, cueLost;
        void PlayVoice(AudioClip clip, float delay)
        {
            if (!clip) return;
            if (voice.isPlaying)
            {   // hand the playing line to a fading source (150 ms) so the new one never overlaps it
                if (!voiceOld) { voiceOld = gameObject.AddComponent<AudioSource>(); voiceOld.playOnAwake = false; }
                voiceOld.clip = voice.clip; voiceOld.time = Mathf.Min(voice.time, Mathf.Max(0, voice.clip.length - 0.01f)); voiceOld.volume = voice.volume; voiceOld.Play(); voiceFade = 0.15f;
                voice.Stop();
            }
            voice.clip = clip; voice.volume = 1f;
            if (delay > 0) voice.PlayDelayed(delay); else voice.Play();
        }
        void StopVoice() { voice.Stop(); if (voiceOld) voiceOld.Stop(); }
        void TickAudio(float dt)
        {
            if (voiceOld && voiceOld.isPlaying) { voiceFade -= dt; voiceOld.volume = Mathf.Clamp01(voiceFade / 0.15f); if (voiceFade <= 0) voiceOld.Stop(); }
            if (music && music.isPlaying)
            {
                float target = paused ? 0 : (voice.isPlaying ? musicBed * 0.4f : musicBed);
                music.volume = Mathf.MoveTowards(music.volume, target, dt * (paused ? 0.8f : 0.4f));
            }
        }
        void Cue(AudioClip c) { if (c && sfx) sfx.PlayOneShot(c, 0.7f); }
        void MakeCues()
        {   // tiny synthesised UI sounds: click (wood tick), lock (bright ding), lost (low tock)
            cueClick = Tone("click", 0.045f, 1400, 0.9f, 60f);
            cueLock = Tone("lock", 0.28f, 1568, 0.6f, 9f);
            cueLost = Tone("lost", 0.16f, 220, 0.7f, 14f);
        }
        static AudioClip Tone(string name, float secs, float hz, float amp, float decay)
        {
            int sr = 44100, n = Mathf.RoundToInt(secs * sr); var d = new float[n];
            for (int i = 0; i < n; i++) { float t = i / (float)sr; d[i] = amp * Mathf.Exp(-decay * t) * Mathf.Sin(2 * Mathf.PI * hz * t) * Mathf.Min(1, i / 60f); }
            var c = AudioClip.Create(name, n, 1, sr, false); c.SetData(d, 0); return c;
        }
        void OnApplicationPause(bool p)
        {
            paused = p;
            if (p) { if (voice.isPlaying) voice.Pause(); } else { voice.UnPause(); idleSince = Time.time; }
        }

        // ---------------- UI: IMGUI with transitions (UX-PLAN §4) ----------------
        readonly List<Rect> uiRects = new List<Rect>();
        GUIStyle button, buttonPrimary, buttonGhost, label, small, segOn, segOff, card, cardText, h1;
        Texture2D pillGold, pillGhost, pillDark, white;
        readonly Dictionary<string, float> fade = new Dictionary<string, float>();   // element -> 0..1 visibility
        string shownStatus = "", prevStatus = ""; float statusT = 1; float flashT = -9, titleBounce = -9;

        float Fade(string key, bool visible, float speed = 4f)
        {
            fade.TryGetValue(key, out var v);
            v = Mathf.MoveTowards(v, visible ? 1 : 0, Time.unscaledDeltaTime * speed);
            fade[key] = v; return v;
        }
        static float EaseOut(float x) => 1 - (1 - x) * (1 - x);

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

        static Texture2D Pill(Color c)
        {
            const int S = 48; var t = new Texture2D(S, S, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp };
            for (int y = 0; y < S; y++) for (int x = 0; x < S; x++)
            {
                float dx = Mathf.Max(0, Mathf.Abs(x - S / 2f + 0.5f) - (S / 2f - 20)), dy = Mathf.Max(0, Mathf.Abs(y - S / 2f + 0.5f) - (S / 2f - 20));
                float d = Mathf.Sqrt(dx * dx + dy * dy); t.SetPixel(x, y, new Color(c.r, c.g, c.b, c.a * Mathf.Clamp01(19.5f - d)));
            }
            t.Apply(); return t;
        }

        void InitStyles()
        {
            var font = Font.CreateDynamicFontFromOSFont(new[] { "Noto Sans CJK SC", "Noto Sans SC", "SamsungOneUI", "Droid Sans Fallback", "PingFang SC", "sans-serif" }, 32);
            int fs = Mathf.RoundToInt(Mathf.Min(Screen.width, Screen.height) / 26f);
            pillGold = Pill(new Color(1f, 0.81f, 0.29f)); pillGhost = Pill(new Color(1, 1, 1, 0.16f)); pillDark = Pill(new Color(0.08f, 0.1f, 0.14f, 0.82f));
            white = Texture2D.whiteTexture;
            buttonPrimary = new GUIStyle(GUI.skin.label) { font = font, fontSize = fs, alignment = TextAnchor.MiddleCenter, fontStyle = FontStyle.Bold, border = new RectOffset(20, 20, 20, 20) };
            buttonPrimary.normal.background = pillGold; buttonPrimary.normal.textColor = new Color(0.16f, 0.11f, 0f);
            buttonGhost = new GUIStyle(buttonPrimary) { fontStyle = FontStyle.Normal }; buttonGhost.normal.background = pillGhost; buttonGhost.normal.textColor = Color.white;
            button = buttonGhost;
            label = new GUIStyle(GUI.skin.label) { font = font, fontSize = fs, alignment = TextAnchor.MiddleCenter, wordWrap = true }; label.normal.textColor = Color.white;
            small = new GUIStyle(label) { fontSize = Mathf.RoundToInt(fs * 0.7f) }; small.normal.textColor = new Color(1, 1, 1, 0.75f);
            h1 = new GUIStyle(label) { fontSize = Mathf.RoundToInt(fs * 2.2f), fontStyle = FontStyle.Bold }; h1.normal.textColor = new Color(1f, 0.85f, 0.45f);
            segOn = new GUIStyle(buttonPrimary) { fontSize = Mathf.RoundToInt(fs * 0.8f) };
            segOff = new GUIStyle(buttonGhost) { fontSize = Mathf.RoundToInt(fs * 0.8f) }; segOff.normal.textColor = new Color(0.85f, 0.88f, 0.92f);
            card = new GUIStyle(GUI.skin.box) { border = new RectOffset(20, 20, 20, 20) }; card.normal.background = pillDark;
            cardText = new GUIStyle(label) { alignment = TextAnchor.MiddleLeft, fontSize = Mathf.RoundToInt(fs * 0.85f) };
        }

        void OnGUI()
        {
            if (button == null) InitStyles();
            uiRects.Clear();
            float u = Mathf.Min(Screen.width, Screen.height) / 12.5f, w = Screen.width, h = Screen.height;
            float top = h - Screen.safeArea.yMax, bottom = Screen.safeArea.yMin;
            bool live = state >= State.LiveIdle, scanning = state == State.ScanSearch || state == State.ScanLocked || state == State.ScanHelp;

            // -- reveal flash (60 ms white) + lost dimming (30 %)
            float flash = Mathf.Clamp01(1 - (Time.time - flashT) / 0.25f);
            if (flash > 0) { GUI.color = new Color(1, 1, 1, flash * 0.9f); GUI.DrawTexture(new Rect(0, 0, w, h), white); }
            float dim = Fade("dim", state == State.LiveLost, 2.5f);
            if (dim > 0) { GUI.color = new Color(0, 0, 0, 0.3f * dim); GUI.DrawTexture(new Rect(0, 0, w, h), white); }
            GUI.color = Color.white;

            // -- status bar: text crossfades + slides 8 px (200 ms)
            string want = statusKey == "" ? "" : (statusKey == "camFail" || statusKey == "xrFail" ? L10n.T(statusKey, statusArg) : L10n.T(statusKey));
            if (want != shownStatus) { prevStatus = shownStatus; shownStatus = want; statusT = 0; }
            statusT = Mathf.Min(1, statusT + Time.unscaledDeltaTime / 0.2f);
            float barA = Fade("bar", shownStatus != "" && state != State.Home, 5f);
            if (barA > 0)
            {
                GUI.color = new Color(1, 1, 1, barA); GUI.Box(new Rect(0, top, w, u * 1.6f), GUIContent.none);
                float e = EaseOut(statusT);
                GUI.color = new Color(1, 1, 1, barA * (1 - e)); GUI.Label(new Rect(u * 0.3f, top - 8 * e, w - u * 0.6f, u * 1.6f), prevStatus, label);
                GUI.color = new Color(1, 1, 1, barA * e); GUI.Label(new Rect(u * 0.3f, top + 8 * (1 - e), w - u * 0.6f, u * 1.6f), shownStatus, label);
                GUI.color = Color.white;
                if (state == State.ScanLocked)   // lock progress (1.5 s) under the status text
                {
                    GUI.color = new Color(0.37f, 0.96f, 0.6f, 0.9f); GUI.DrawTexture(new Rect(0, top + u * 1.6f - 4, w * Mathf.Clamp01(lockedFor / LockSeconds), 4), white); GUI.color = Color.white;
                }
            }

            // -- top-right: 中/EN, mute (always), 拼音/ABC (live)
            float sw = u * 1.5f, sh = u * 0.95f, sy = top + (barA > 0.5f ? u * 1.9f : u * 0.4f), sx = w - u * 0.3f - sw;
            var rLang = new Rect(sx, sy, sw, sh); uiRects.Add(rLang);
            if (GUI.Button(rLang, L10n.IsZh ? "EN" : "中", segOff)) { Cue(cueClick); L10n.Toggle(); }
            var rMute = new Rect(sx - sw - 6, sy, sw, sh); uiRects.Add(rMute);
            if (GUI.Button(rMute, L10n.T(muted ? "unmute" : "mute"), segOff)) { muted = !muted; PlayerPrefs.SetInt("muted", muted ? 1 : 0); AudioListener.volume = muted ? 0 : 1; }
            float segA = Fade("seg", live && Titles, 4f);
            if (segA > 0)
            {
                GUI.color = new Color(1, 1, 1, segA);
                float ty = sy + sh + 8; var r1 = new Rect(w - u * 0.3f - sw * 2 - 6, ty, sw, sh); var r2 = new Rect(w - u * 0.3f - sw, ty, sw, sh);
                if (GUI.Button(r1, L10n.T("pinyin"), pinyinMode ? segOn : segOff)) { Cue(cueClick); pinyinMode = true; ShowTitle(null); }
                if (GUI.Button(r2, L10n.T("abc"), pinyinMode ? segOff : segOn)) { Cue(cueClick); pinyinMode = false; ShowTitle(null); }
                uiRects.Add(r1); uiRects.Add(r2); GUI.color = Color.white;
            }

            // -- Home panel
            float homeA = Fade("home", state == State.Home, 4f);
            if (homeA > 0)
            {
                GUI.color = new Color(0.06f, 0.08f, 0.13f, 0.92f * homeA); GUI.DrawTexture(new Rect(0, 0, w, h), white); GUI.color = new Color(1, 1, 1, homeA);
                float cy = h * 0.34f + 12 * (1 - EaseOut(homeA));
                GUI.Label(new Rect(0, cy - u * 2.4f, w, u * 2.2f), "DoodLive", h1);
                GUI.Label(new Rect(u, cy - u * 0.2f, w - 2 * u, u * 1.6f), L10n.T("tagline"), label);
                if (statusKey == "noPerm" || statusKey == "noAR") GUI.Label(new Rect(u, cy + u * 1.4f, w - 2 * u, u * 1.6f), L10n.T(statusKey), small);
                float bw = Mathf.Min(w - 2 * u, u * 6.5f), bx = (w - bw) / 2, by = h * 0.62f;
                var rScan = new Rect(bx, by, bw, u * 1.35f); var rDemo = new Rect(bx, by + u * 1.7f, bw, u * 1.2f);
                uiRects.Add(rScan); uiRects.Add(rDemo);
                if (GUI.Button(rScan, L10n.T(arUnsupported ? "scanLong" : "scanLong"), buttonPrimary)) { Cue(cueClick); Go(State.Permission); }
                if (GUI.Button(rDemo, L10n.T("demo"), buttonGhost)) ShowDemo();
                GUI.color = Color.white;
            }

            // -- Help card (30 s without a sheet)
            float helpA = Fade("help", state == State.ScanHelp, 4f);
            if (helpA > 0)
            {
                GUI.color = new Color(1, 1, 1, helpA);
                float cw = Mathf.Min(w - u, u * 9), ch = u * 6.2f, cx = (w - cw) / 2, cy = h * 0.5f - ch / 2 + 12 * (1 - EaseOut(helpA));
                GUI.Box(new Rect(cx, cy, cw, ch), GUIContent.none, card);
                GUI.Label(new Rect(cx + u * 0.5f, cy + u * 0.3f, cw - u, u), L10n.T("helpTitle"), label);
                for (int i = 1; i <= 3; i++) GUI.Label(new Rect(cx + u * 0.6f, cy + u * (0.5f + i * 1.0f), cw - u * 1.2f, u), $"{i}.  {L10n.T("help" + i)}", cardText);
                var rD = new Rect(cx + u * 0.6f, cy + ch - u * 1.55f, cw - u * 1.2f, u * 1.15f); uiRects.Add(rD);
                if (GUI.Button(rD, L10n.T("helpDemo"), buttonGhost)) ShowDemo();
                GUI.color = Color.white;
            }

            // -- bottom buttons: 3 primaries in Live, "更多" drawer for the rest; scan shows 看演示 only
            var main = new List<(string, System.Action, bool)>();
            if (scanning) main.Add((L10n.T("demo"), ShowDemo, false));
            if (live)
            {
                bool busy = state == State.LiveBlow || state == State.LiveRead || state == State.Reveal;
                main.Add((L10n.T("blow"), Blow, !busy && state == State.LiveIdle));
                main.Add((L10n.T("read"), () => { if (state == State.LiveIdle) { Cue(cueClick); StartCoroutine(ReadSequence()); } }, state == State.LiveIdle));
                main.Add((L10n.T("rescan"), () => { Cue(cueClick); Rescan(); }, !busy));
            }
            float groupA = Fade("buttons", main.Count > 0 && state != State.Reveal, 4.5f);
            if (groupA > 0 && main.Count > 0)
            {
                float bw = (w - u * 0.5f) / main.Count, y = h - bottom - u * 1.6f;
                for (int i = 0; i < main.Count; i++)
                {
                    float a = Mathf.Clamp01(groupA * 1.3f - i * 0.15f), e = EaseOut(a);
                    var r = new Rect(u * 0.25f + i * bw + 4, y + 12 * (1 - e), bw - 8, u * 1.3f); uiRects.Add(r);
                    bool enabled = main[i].Item3; GUI.color = new Color(1, 1, 1, a * (enabled ? 1 : 0.4f));
                    if (GUI.Button(r, main[i].Item1, i == 0 && live ? buttonPrimary : buttonGhost) && enabled) main[i].Item2();
                }
                GUI.color = Color.white;
            }
            if (live)
            {
                var rMore = new Rect(w - u * 0.3f - sw, h - bottom - u * 3.1f, sw, sh); uiRects.Add(rMore);
                if (GUI.Button(rMore, L10n.T(moreOpen ? "close" : "more"), segOff)) { Cue(cueClick); moreOpen = !moreOpen; }
                float moreA = Fade("more", moreOpen && live, 5f);
                if (moreA > 0)
                {
                    var extras = new List<(string, System.Action)>();
                    if (rawPx != null) extras.Add((L10n.T(showLines ? "linesOn" : "linesOff"), () => { showLines = !showLines; ApplyPage(); }));
                    if (arReady && !showMode) extras.Add((L10n.T("modeShow"), () => { showMode = true; PlaceInFront(); }));
                    GUI.color = new Color(1, 1, 1, moreA);
                    for (int i = 0; i < extras.Count; i++)
                    {
                        var r = new Rect(w - u * 0.3f - sw * 2.4f, h - bottom - u * (4.4f + i * 1.25f) + 10 * (1 - EaseOut(moreA)), sw * 2.4f, sh); uiRects.Add(r);
                        if (GUI.Button(r, extras[i].Item1, buttonGhost)) { Cue(cueClick); extras[i].Item2(); }
                    }
                    GUI.color = Color.white;
                }
            }
            uiRects.Add(new Rect(0, 0, w, top + u * 1.8f));

            // -- build fingerprint (bottom-right, 45 % white)
            var fpStyle = new GUIStyle(GUI.skin.label) { fontSize = Mathf.RoundToInt(u * 0.28f), alignment = TextAnchor.LowerRight }; fpStyle.normal.textColor = new Color(1, 1, 1, 0.45f);
            GUI.Label(new Rect(0, h - bottom - u * 0.4f, w - u * 0.2f, u * 0.4f), Fingerprint, fpStyle);
        }
    }
}
