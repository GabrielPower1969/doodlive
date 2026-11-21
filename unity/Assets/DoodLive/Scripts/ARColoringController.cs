// DoodLive app flow — the state machine from docs/UX-PLAN.md §3 (Unity is the reference; web/app.js mirrors it).
//
//   Home ─► Permission ─► Scan.Search ─► Scan.Locked(1.5 s) ─► Reveal(≤4 s, uninterruptible) ─► Live.Idle
//                            │  └─30 s─► Scan.Help                                              │  ▲
//                            └──────────────────────────────── Live.Lost ◄── tracking lost 1.0 s ─┘  │
//                                                   Live.Blow / Live.Read / Live.Greet ───────────────┘
//   Paused: app in background — music fades out 0.3 s, back in 0.6 s, no re-scan.
//   David & Goliath sheet (or the home screen's D&G demo): same states, but Reveal starts DGDirector instead of the
//   angel; in Live a tap pauses / resumes the play, Live.Lost holds it, the end shows a replay button
//   (docs/david-goliath/INTEGRATION.md).
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
    public partial class ARColoringController : MonoBehaviour
    {
        public const int TexSize = 1024;

        [Header("AR")]
        public ARSession session;
        public ARTrackedImageManager trackedImages;   // image path: coloured pages, sheets on screens
        public SheetFinder finder;                    // marker path: any sheet, blank or coloured (LESSONS L49)
        public ARCameraManager cameraManager;
        public ARCameraBackground cameraBackground;
        public Camera arCamera;

        [Header("Angel")]
        public Animator angel;
        public Material[] pageMaterials;
        public Texture2D demoTexture;
        [Tooltip("Angel height on the sheet, as a fraction of the art width (web: 0.75)")]
        public float scaleOnSheet = 0.75f;

        [Header("David & Goliath (docs/david-goliath/INTEGRATION.md)")]
        public DavidGoliath.DGDirector story;
        public Material[] dgMaterials;        // page-coloured materials of both characters
        public Texture2D dgDemoTexture;       // assets/david-goliath/sheet/demo-colored.png
        public const string DGSheetPrefix = "david-goliath";
        [Header("Story packs (assets/stories.json, generic engine; docs/STORY-ARCHITECTURE.md)")]
        public Story.StoryDirector[] packs;
        Transform dgHolder; bool dgMode;      // dgMode: a story stage, not the angel, is on the page
        IStoryPlayer active;                  // the story on the page (David & Goliath or a pack)
        Transform Holder => dgMode && dgHolder ? dgHolder : holder;
        IEnumerable<IStoryPlayer> Players()
        {
            if (story) yield return story;
            if (packs != null) foreach (var p in packs) if (p) yield return p;
        }
        IStoryPlayer PlayerForSheet(string sheetName)
        {
            foreach (var p in Players()) if (sheetName.StartsWith(p.StoryId)) return p;
            return null;
        }

        [Header("Sound")]
        public AudioSource sfx, voice, music;
        public float musicBed = 0.22f;
        public AudioClip fanfare, chime, hello, swell;
        public AudioClip[] lines;           // Blow lines, rotate
        public AudioClip[] greets;          // idle greetings (fly / wow / laugh)
        [Header("English voice (recorded, web/assets/voice/recorded-en)")]
        public AudioClip helloEn; public AudioClip[] linesEn, greetsEn;
        AudioClip Hello => !L10n.IsZh && helloEn ? helloEn : hello;
        AudioClip[] Lines => !L10n.IsZh && linesEn != null && linesEn.Length > 0 ? linesEn : lines;
        AudioClip[] Greets => !L10n.IsZh && greetsEn != null && greetsEn.Length > 0 ? greetsEn : greets;

        // ---------------- timings (seconds) — UX-PLAN §3/§4 ----------------
        const float LockSeconds = 1.5f, HelpAfter = 30f, LostAfter = 1.0f, GreetAfter = 20f, GreetEvery = 25f, GreetMax = 2;
        const float RevealSeconds = 1.4f, BlowSeconds = 3.3f, ReadStep = 1.3f, HintAfter = 5f, GateHold = 2f;

        public enum State { Home, Permission, ScanSearch, ScanLocked, ScanHelp, Reveal, LiveIdle, LiveBlow, LiveRead, LiveGreet, LiveLost }
        public State state = State.Home;
        float stateT;                       // seconds in the current state
        bool paused;

        Template tpl;
        Transform holder;
        Texture2D pageTex;
        Color32[] rawPx, cleanPx;
        bool showLines, arReady, arUnsupported, showMode, capturing, moreOpen, muted, haptics = true;
        string statusKey = "", statusArg = "";
        float lockedFor, untracked, idleSince, lastGreet, lastTouch; int greetCount, lineIdx, greetIdx;
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
            dgHolder = new GameObject("StoryHolder").transform;   // every story stage hangs here; one is active at a time
            foreach (var p in Players()) { p.transform.SetParent(dgHolder, false); p.gameObject.SetActive(false); }
            if (session) session.enabled = false;
            Screen.sleepTimeout = SleepTimeout.NeverSleep;
            muted = PlayerPrefs.GetInt("muted", 0) == 1; AudioListener.volume = muted ? 0 : 1;
            haptics = PlayerPrefs.GetInt("haptics", 1) == 1; musicBed = PlayerPrefs.GetFloat("musicBed", musicBed);
            MakeCues();
            Go(State.Home);
            // QA / demo recording: `adb shell am start -n <pkg>/com.unity3d.player.UnityPlayerActivity --es demo esther`
            string autoDemo = null;
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                using (var up = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
                using (var act = up.GetStatic<AndroidJavaObject>("currentActivity"))
                using (var intent = act.Call<AndroidJavaObject>("getIntent"))
                {
                    autoDemo = intent.Call<string>("getStringExtra", "demo");
                    // diagnostics: `am start ... --ez noimages true` runs the marker path alone (frame-rate A/B on a device)
                    if (intent.Call<bool>("getBooleanExtra", "noimages", false) && trackedImages)
                    { noImages = true; trackedImages.enabled = false; Debug.Log("DoodLive: image tracking off (noimages)"); }
                }
            }
            catch (System.Exception e) { Debug.LogWarning("DoodLive: intent read failed " + e.Message); }
#endif
            if (!string.IsNullOrEmpty(autoDemo)) StartCoroutine(AutoDemo(autoDemo));
        }

        IEnumerator AutoDemo(string id)
        {
            yield return new WaitForSeconds(1.5f);
            foreach (var p in Players()) if (p.StoryId == id) { Debug.Log($"DoodLive auto demo '{id}'"); ShowDemoStory(p); yield break; }
            if (id == "angel") ShowDemo();
        }

        void Go(State s)
        {
            if (state == s) return;
            Debug.Log($"DoodLive state {state} -> {s}");
            if (state == State.Reveal && s == State.LiveIdle) Buzz(30);   // one soft bump when she lands (screen 05)
            state = s; stateT = 0;
            switch (s)
            {
                case State.Home:
                    statusKey = ""; angel.gameObject.SetActive(false); StopStory(); lastSavedShotKey = null;
                    DetachStage(); if (finder) finder.Forget();
                    if (session && arReady) { session.enabled = false; arReady = false; }   // the shelf needs no camera (battery, heat)
                    break;
                case State.Permission: statusKey = "openingCam"; StartCoroutine(Boot()); break;
                case State.ScanSearch: showMode = false; lockedFor = 0; angel.gameObject.SetActive(false); StopStory(); DetachStage(); statusKey = "fit"; break;
                case State.ScanLocked: statusKey = "found"; Cue(cueLock); break;
                case State.ScanHelp: statusKey = ""; break;
                case State.Reveal: StartReveal(); break;
                case State.LiveIdle: idleSince = Time.time; if (statusKey != "lost") statusKey = "tap"; break;
                case State.LiveLost: statusKey = "lost"; Cue(cueLost); break;
            }
        }

        // Camera permission and ARCore availability. arFail: null when AR can run, else the status key to show.
        string arFail;
        IEnumerator EnsureAr()
        {
            arFail = null;
#if UNITY_ANDROID && !UNITY_EDITOR
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera))
            {
                bool answered = false;
                var cb = new PermissionCallbacks();
                cb.PermissionGranted += _ => answered = true; cb.PermissionDenied += _ => answered = true; cb.PermissionDeniedAndDontAskAgain += _ => answered = true;
                Permission.RequestUserPermission(Permission.Camera, cb);
                while (!answered) yield return null;
            }
            if (!Permission.HasUserAuthorizedPermission(Permission.Camera)) { arFail = "noPerm"; yield break; }
#endif
            if (ARSession.state == ARSessionState.None || ARSession.state == ARSessionState.CheckingAvailability) yield return ARSession.CheckAvailability();
            if (ARSession.state == ARSessionState.NeedsInstall) yield return ARSession.Install();
            if (ARSession.state == ARSessionState.Unsupported || ARSession.state == ARSessionState.NeedsInstall) { arUnsupported = true; arFail = "noAR"; }
        }

        // A demo waiting for the camera: called with true when AR runs, false to play it as a film instead.
        System.Action<bool> pendingDemo;

        IEnumerator Boot()
        {
            yield return EnsureAr();
            var demo = pendingDemo; pendingDemo = null;
            if (arFail != null)
            {
                if (demo != null) { demo(false); yield break; }   // no camera: the book still plays, as a film
                var key = arFail; statusKey = key; Go(State.Home); statusKey = key; yield break;
            }
            RestoreArCamera();
            session.enabled = true; arReady = true;
            if (demo != null) { demo(true); yield break; }
            Go(State.ScanSearch);
        }

        // A sheet seen now: the markers first (their title-band read tells the sheets apart), else ARCore image tracking.
        // ARCore matches the whole page, and every sheet shares the same frame and corner markers, so a coloured page
        // was read as the most detailed reference (the coloured Gabriel sample) - LESSONS 2026-11-18.
        SheetTarget imageSheet;
        bool noImages;   // diagnostics flag: image tracking stays off
        SheetTarget Sheet()
        {
            if (finder && finder.Current != null && finder.Current.Tracking) return finder.Current;
            if (trackedImages)
                foreach (var t in trackedImages.trackables)
                    if (t.trackingState == TrackingState.Tracking)
                    {
                        if (imageSheet == null || imageSheet.Image != t) imageSheet = new SheetTarget(t);
                        return imageSheet;
                    }
            return null;
        }

        void Update()
        {
            float dt = Time.deltaTime; stateT += dt;
            TickAudio(dt);
            if (dgMode && active != null)
            {   // the play holds while the app is away, the sheet is lost or the grown-ups panel is open
                active.Hold = paused || state == State.LiveLost || moreOpen;
                active.MusicGain = Mathf.Clamp(musicBed / 0.22f, 0, 2);
            }
            if (finder)
            {
                finder.Active = arReady && !paused && !showMode && state >= State.ScanSearch && state != State.Reveal;
                finder.Interval = state >= State.Reveal ? 0.35f : 0.15f;   // live: only refines the anchor, so a slower pace
            }
            // image tracking costs a lot on mid-range phones: only while scanning, or when the stage follows an image
            if (trackedImages && !noImages && arReady)
            {
                bool want = !showMode && (state < State.Reveal || (anchoredSheet != null && anchoredSheet.Image));
                if (trackedImages.enabled != want) trackedImages.enabled = want;
            }
            if (paused) return;
            StageGestures();
            switch (state)
            {
                case State.ScanSearch:
                    if (Sheet() != null) Go(State.ScanLocked);
                    else if (stateT > HelpAfter) Go(State.ScanHelp);
                    break;
                case State.ScanLocked:
                    if (Sheet() == null) { lockedFor = 0; Go(State.ScanSearch); break; }
                    lockedFor += dt;
                    if (lockedFor >= LockSeconds && !capturing) StartCoroutine(Capture(Sheet()));
                    break;
                case State.ScanHelp:
                    if (Sheet() != null) Go(State.ScanLocked);
                    break;
                case State.Reveal:
                    if (stateT >= RevealSeconds) Go(State.LiveIdle);
                    break;
                case State.LiveIdle:
                    if (!dgMode && Time.time - idleSince > GreetAfter && greetCount < GreetMax && Time.time - lastGreet > GreetEvery && !voice.isPlaying) Greet();
                    var tap = TapOutsideUI();
                    if (tap.HasValue && dgMode)
                    {   // the play is the button: tap = pause / resume (the replay button sits in the UI at the end)
                        lastTouch = Time.time; moreOpen = false;
                        if (active != null && !active.Finished) { Cue(cueClick); active.TogglePause(); }
                    }
                    else if (tap.HasValue)
                    {   // the angel is the button (screen 06): tap the 3D title = read it, anywhere else = trumpet
                        lastTouch = Time.time; moreOpen = false;
                        if (OnTitle(tap.Value)) { Cue(cueClick); StartCoroutine(ReadSequence()); } else Blow();
                    }
                    break;
                case State.LiveBlow:
                    if (stateT >= BlowSeconds) Go(State.LiveIdle);
                    break;
                case State.LiveGreet:
                    if (!voice.isPlaying && stateT > 0.5f) Go(State.LiveIdle);
                    break;
                case State.LiveLost:   // no longer entered: the stage stays anchored in the room (docs/ANCHORING-DESIGN.md)
                    statusKey = "tap"; Go(State.LiveIdle);
                    break;
            }
            LibraryInput(); TrackProgress();
            if (Input.GetKeyDown(KeyCode.Escape)) Back();   // Android back button
        }


        void Back()
        {
            if (howtoOpen) { CloseHowto(); return; }   // the how-to video (ARColoringController.Howto.cs)
            if (state >= State.LiveIdle) { if (showMode) BackToLibrary(); else Rescan(); }
            else if (state >= State.ScanSearch && state != State.Reveal) Go(State.Home);
            else if (state == State.Home && libOpen != null) libOpen = null;
            else if (state == State.Home) Application.Quit();
        }

        void Rescan()
        {
            StopVoice(); greetCount = 0; moreOpen = false;
            DetachStage();
            if (finder) finder.Forget();
            if (arReady) Go(State.ScanSearch); else Go(State.Permission);
        }

        // ---------------- capture / bake ----------------
        IEnumerator Capture(SheetTarget sheet)
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
            if (sheet.ScreenMarkers != null) System.Array.Copy(sheet.ScreenMarkers, expected, 4);   // marker path: measured, way up known
            else for (int i = 0; i < 4; i++) { var s = arCamera.WorldToScreenPoint(sheet.transform.TransformPoint(PageToLocal(sheet, tpl.markers[i]))); expected[i] = new Vector2(s.x, s.y); }
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
            active = PlayerForSheet(sheet.Name);
            dgMode = active != null;
            Debug.Log($"DoodLive sheet '{sheet.Name}' ({(sheet.Image ? "image" : "markers")}) -> {(dgMode ? active.StoryId : "angel")}");
            ApplyPage();
            PlaceOnSheet(sheet);
            ShowTitle(sheet.Name);
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

        Vector3 PageToLocal(SheetTarget sheet, Vector2 px)
        {
            var size = sheet.size;
            return new Vector3((px.x / tpl.page.x - 0.5f) * size.x, 0, (0.5f - px.y / tpl.page.y) * size.y);
        }

        // ---------------- placement (LESSONS L14, L24, L25) ----------------
        SheetTarget anchoredSheet;
        Vector2 placePage; float placeFlat, placeYaw;

        void PlaceOnSheet(SheetTarget sheet)
        {
            var st = sheet.transform;
            placeFlat = Mathf.InverseLerp(0.45f, 0.85f, Mathf.Abs(Vector3.Dot(st.up, Vector3.up)));
            // angel: art centre; D&G: the feet line of the drawing (art rectangle's bottom edge), where the figures stand
            placePage = new Vector2(tpl.art.x + tpl.art.width / 2, tpl.art.y + (dgMode ? tpl.art.height : tpl.art.height / 2));
            var pos = st.TransformPoint(PageToLocal(sheet, placePage));
            var toViewer = Vector3.ProjectOnPlane(arCamera.transform.position - pos, Vector3.up);
            if (toViewer.sqrMagnitude < 1e-4f) toViewer = Vector3.ProjectOnPlane(-st.forward, Vector3.up);
            // D&G keeps the page's layout (Goliath at the back, David at the front-left), so on a flat sheet the stage
            // faces the page's bottom edge (sheet -Z), still yawing about gravity only (LESSONS L14)
            var pageBottom = Vector3.ProjectOnPlane(-st.forward, Vector3.up);
            var facing = dgMode && placeFlat >= 0.5f && pageBottom.sqrMagnitude > 0.05f ? pageBottom : toViewer;
            placeYaw = Quaternion.LookRotation(facing.normalized, Vector3.up).eulerAngles.y;
            placeOnFlat = placeFlat >= 0.5f;
            sheetHeading0 = SheetHeading(st);
            // the stage gets its own anchor in the room; the sheet only refines it (ARColoringController.Stage.cs)
            DetachStage();
            anchoredSheet = sheet; stageMode = StageMode.Sheet;
            SheetStagePose(sheet, out var p, out var y, out var s);
            MoveStage(p, y, s, false);
        }

        void LateUpdate() => StageLateUpdate();

        void OnEnable() { if (trackedImages) trackedImages.trackablesChanged.AddListener(OnImagesChanged); }
        void OnDisable() { if (trackedImages) trackedImages.trackablesChanged.RemoveListener(OnImagesChanged); }
        void OnImagesChanged(ARTrackablesChangedEventArgs<ARTrackedImage> e)
        {   // the tracked image is gone: the stage stays where it is, it just stops refining
            if (anchoredSheet == null || !anchoredSheet.Image) return;
            foreach (var r in e.removed) if (r.Key == anchoredSheet.Image.trackableId) { anchoredSheet = null; return; }
        }

        void ApplyPage()
        {
            if (rawPx == null) return;
            pageTex.SetPixels32(showLines ? rawPx : cleanPx); pageTex.Apply(false);
            foreach (var m in pageMaterials) m.SetTexture("_BaseMap", pageTex);
            if (dgMaterials != null) foreach (var m in dgMaterials) if (m) m.SetTexture("_BaseMap", pageTex);
            if (packs != null) foreach (var p in packs) if (p && p.pageMaterials != null) foreach (var m in p.pageMaterials) if (m) m.SetTexture("_BaseMap", pageTex);
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
            if (dgMode && active != null)
            {   // a story: the director owns music and voice; the angel's theme must not play under it
                angel.gameObject.SetActive(false); StopVoice(); if (music) music.Stop();
                foreach (var p in Players()) if (p != active) p.gameObject.SetActive(false);
                active.gameObject.SetActive(true);
                active.MusicGain = Mathf.Clamp(musicBed / 0.22f, 0, 2);
                if (startShot > 0) active.BeginAt(startShot); else active.Begin();   // library: keep reading at a shot
                startShot = 0;
                sfx.PlayOneShot(chime);
                moreOpen = false; flashT = Time.time; lastTouch = Time.time + 1.5f; statusKey = "";
                return;
            }
            angel.gameObject.SetActive(true);
            angel.Play("Enter", 0, 0);
            sfx.PlayOneShot(chime);
            if (swell) sfx.PlayOneShot(swell, 0.8f);
            if (music && !music.isPlaying) { music.volume = musicBed; music.Play(); }
            PlayVoice(Hello, 0.9f, "hello");
            greetCount = 0; moreOpen = false; flashT = Time.time; lastTouch = Time.time + 1.5f;
            statusKey = "tap";
        }

        void Blow()
        {
            if (state != State.LiveIdle) return;
            Cue(cueClick);
            Go(State.LiveBlow);
            angel.SetTrigger(BlowId);
            sfx.PlayOneShot(fanfare);
            var L = Lines; if (L != null && L.Length > 0) { int i = lineIdx++ % L.Length; PlayVoice(L[i], fanfare.length * 0.95f, "line" + i); }
            idleSince = Time.time;
        }

        void Greet()
        {
            var G = Greets; if (G == null || G.Length == 0) { idleSince = Time.time; return; }
            Go(State.LiveGreet);
            greetCount++; lastGreet = Time.time; idleSince = Time.time;
            int g = greetIdx++ % G.Length; PlayVoice(G[g], 0, "greet" + g);
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
                statusKey = keys[i]; readKey = keys[i]; sfx.PlayOneShot(chime, 0.5f);
                var part = FindPart(titles, order[i]);
                bool wasActive = part && part.gameObject.activeSelf;
                if (part) { part.gameObject.SetActive(true); StartCoroutine(Punch(part, ReadStep)); }
                yield return new WaitForSeconds(ReadStep);
                if (part && !wasActive) part.gameObject.SetActive(false);
            }
            statusKey = "tap"; readKey = null; idleSince = Time.time; lastTouch = Time.time;
            Go(State.LiveIdle);
        }
        string readKey;
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

        // Demo (a book from the shelf, or the angel): in AR when the phone can (the stage stands in the room, on the
        // table once one is found); as a film when it cannot or the grown-ups chose film (docs/ANCHORING-DESIGN.md).
        void ShowDemo()
        {
            Cue(cueClick);
            if (!arReady && !arUnsupported && !PreferFilm) { pendingDemo = StartDemoAngel; Go(State.Permission); return; }
            StartDemoAngel(arReady && !PreferFilm);
        }

        void StartDemoAngel(bool ar)
        {
            StopStory(); DetachStage();
            showMode = true;
            if (!ar) { if (arReady) { session.enabled = false; arReady = false; } NoArCamera(); }
            UseDemoTexture(); ShowTitle("angel");
            if (ar) StartCoroutine(StartArStage(0.3f, true));
            else { PlaceInFrontFixed(); Go(State.Reveal); }
        }

        // NoArCamera's changes, kept so the scan can undo them: without this, watching a book from the shelf before the
        // first scan left the camera feed and pose driver off, and "Scan my colouring" showed a brown screen (2026-11-21)
        bool noArSaved; CameraClearFlags arClear; Color arBg; float arFov; Vector3 arPos; Quaternion arRot;
        void NoArCamera()
        {
            if (arReady) return;
            if (!noArSaved)
            {
                noArSaved = true; arClear = arCamera.clearFlags; arBg = arCamera.backgroundColor; arFov = arCamera.fieldOfView;
                arPos = arCamera.transform.position; arRot = arCamera.transform.rotation;
            }
            // no AR session: stop the pose driver (it would snap the camera back to the origin), sky backdrop, fixed camera
            var tpd = arCamera.GetComponent<UnityEngine.InputSystem.XR.TrackedPoseDriver>(); if (tpd) tpd.enabled = false;
            if (cameraBackground) cameraBackground.enabled = false;
            arCamera.clearFlags = CameraClearFlags.SolidColor; arCamera.backgroundColor = new Color32(0x9C, 0x6B, 0x45, 0xFF);   // warm table (Paper & Crayon mocks)
            arCamera.transform.SetPositionAndRotation(new Vector3(0, 1.2f, 0), Quaternion.identity);
            arCamera.fieldOfView = 60;
        }

        void RestoreArCamera(bool stopStory = true)
        {
            if (stopStory)
            {
                StopStory();                                // a demo's cinematic must not keep driving the camera
                foreach (var p in Players()) p.Cinematic = null;
            }
            var tpd = arCamera.GetComponent<UnityEngine.InputSystem.XR.TrackedPoseDriver>(); if (tpd) tpd.enabled = true;
            if (cameraBackground) cameraBackground.enabled = true;
            if (!noArSaved) return;
            noArSaved = false;
            arCamera.clearFlags = arClear; arCamera.backgroundColor = arBg; arCamera.fieldOfView = arFov;
            arCamera.transform.SetPositionAndRotation(arPos, arRot);
        }

        // Home screen's David & Goliath entry: the play with the sample colouring (assets/david-goliath/sheet/demo-colored.png)
        // on a printed page. Without AR the shot list's camera hints drive the view; in AR the phone is the camera.
        void ShowDemoDG() => ShowDemoStory(story);

        // Home screen's story entries: the play with the pack's sample colouring on a printed page. Without AR the
        // shot list's camera hints drive the view; in AR the phone is the camera.
        void ShowDemoStory(IStoryPlayer p)
        {
            if (p == null || (p is UnityEngine.Object o && !o)) return;
            Cue(cueClick);
            if (!arReady && !arUnsupported && !PreferFilm) { pendingDemo = ar => StartDemoStory(p, ar); Go(State.Permission); return; }
            StartDemoStory(p, arReady && !PreferFilm);
        }

        void StartDemoStory(IStoryPlayer p, bool ar)
        {
            StopStory(); DetachStage();
            showMode = true; active = p; dgMode = true;
            if (!ar) { if (arReady) { session.enabled = false; arReady = false; } NoArCamera(); }
            rawPx = cleanPx = null;
            if (p == (IStoryPlayer)story) { if (dgMaterials != null) foreach (var m in dgMaterials) if (m) m.SetTexture("_BaseMap", LineFree(dgDemoTexture)); }
            else if (p is Story.StoryDirector sd && sd.pageMaterials != null) foreach (var m in sd.pageMaterials) if (m) m.SetTexture("_BaseMap", LineFree(sd.demoTexture));
            p.ShowDemoPage(true);
            if (ar) { p.Cinematic = null; StartCoroutine(StartArStage(0.3f, true)); }
            else { PlaceInFrontFixed(); p.Cinematic = arCamera; Go(State.Reveal); }
        }

        // The sample colouring still carries the printed ink lines. A real scan has them erased (EraseLines in the
        // capture path) before it reaches the models, so the demo must too: otherwise the printed eyes and mouth sit
        // under the face decal and every character shows two faces (owner 2026-11-14, "双面"). Done once per texture
        // through a RenderTexture, because the imported demo textures are not CPU-readable.
        readonly Dictionary<Texture2D, Texture2D> lineFree = new Dictionary<Texture2D, Texture2D>();
        Texture2D LineFree(Texture2D src)
        {
            if (!src) return src;
            if (lineFree.TryGetValue(src, out var done) && done) return done;
            int w = src.width, h = src.height;
            var rt = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            Graphics.Blit(src, rt);
            var prev = RenderTexture.active; RenderTexture.active = rt;
            var tmp = new Texture2D(w, h, TextureFormat.RGBA32, false);
            tmp.ReadPixels(new Rect(0, 0, w, h), 0, 0); tmp.Apply(false);
            RenderTexture.active = prev; RenderTexture.ReleaseTemporary(rt);
            tmp.SetPixels32(PageWarp.EraseLines(tmp.GetPixels32(), w, h)); tmp.Apply(false);
            tmp.wrapMode = src.wrapMode; tmp.filterMode = src.filterMode; tmp.name = src.name + " (line-free)";
            lineFree[src] = tmp;
            return tmp;
        }

        void StopStory()
        {
            foreach (var p in Players()) { p.Stop(); p.ShowDemoPage(false); p.gameObject.SetActive(false); }
            dgMode = false; active = null;
        }

        public void Action() => Blow();

        // ---------------- audio director: voice > sfx > music, voices never overlap ----------------
        AudioSource voiceOld; float voiceFade;
        AudioClip cueClick, cueLock, cueLost;
        string voiceKey; float voiceFrom;   // what she is saying, for the speech bubble
        void PlayVoice(AudioClip clip, float delay, string key = null)
        {
            if (!clip) return;
            voiceKey = key; voiceFrom = Time.time + delay;
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
            if (dgMode && active != null) active.Hold = p || state == State.LiveLost || moreOpen;
        }

        // UI lives in ARColoringController.UI.cs (Paper & Crayon, docs/DESIGN-DIRECTION.md)
    }
}
