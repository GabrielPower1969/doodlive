// Paper & Crayon UI (docs/DESIGN-DIRECTION.md, Figma "DoodLive · Paper & Crayon redesign"), drawn with IMGUI.
// Same screens and rules as web/: the angel is the button, one chip for a new sheet, everything for grown-ups behind
// a 2 s hold on the lock. Colours come from DesignTokens (tools/gen_tokens.py), fonts and icons from Resources/.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.ARSubsystems;

namespace DoodLive
{
    public partial class ARColoringController
    {
        readonly List<Rect> uiRects = new List<Rect>();
        readonly Dictionary<string, float> fade = new Dictionary<string, float>();   // element -> 0..1 visibility
        string shownStatus = "", prevStatus = ""; float statusT = 1; float flashT = -9, titleBounce = -9;
        GUIStyle txtUi, txtZh, txtSmall, txtSmallZh, txtLogo, txtTitle, txtTag, fpStyle;
        GUIStyle boxPaper, boxShade, boxSun, boxInk, boxOk, boxLeaf, boxDeep;
        Texture2D white, dot, disc, ring;
        readonly Dictionary<string, Texture2D> icons = new Dictionary<string, Texture2D>();
        Font fUi, fZh, fDisplay;
        float u, lip, gateHeld; bool gateJustOpened;   // the finger that opened the gate must not also close it on release

        float Fade(string key, bool visible, float speed = 4f)
        {
            fade.TryGetValue(key, out var v);
            v = Mathf.MoveTowards(v, visible ? 1 : 0, Time.unscaledDeltaTime * speed);
            fade[key] = v; return v;
        }
        static float EaseOut(float x) => 1 - (1 - x) * (1 - x);
        static float BackOut(float x) { const float c = 1.7f; x -= 1; return 1 + (c + 1) * x * x * x + c * x * x; }

        Vector2? TapOutsideUI()
        {
            Vector2? p = null;
            if (Input.touchCount > 0 && Input.GetTouch(0).phase == TouchPhase.Began) p = Input.GetTouch(0).position;
            else if (Input.GetMouseButtonDown(0)) p = Input.mousePosition;
            if (p == null) return null;
            var gp = new Vector2(p.Value.x, Screen.height - p.Value.y);
            foreach (var r in uiRects) if (r.Contains(gp)) return null;
            return gp;
        }

        // ---------------- screen-space bounds of the angel body and of the 3D title ----------------
        Rect? ScreenRect(System.Func<Renderer, bool> pick)
        {
            if (!angel || !angel.gameObject.activeInHierarchy) return null;
            bool any = false; float x0 = 1e9f, y0 = 1e9f, x1 = -1e9f, y1 = -1e9f;
            foreach (var r in angel.GetComponentsInChildren<Renderer>())
            {
                if (!r.enabled || !r.gameObject.activeInHierarchy || !pick(r)) continue;
                var b = r.bounds;
                for (int i = 0; i < 8; i++)
                {
                    var c = new Vector3(i % 2 == 0 ? b.min.x : b.max.x, (i / 2) % 2 == 0 ? b.min.y : b.max.y, i / 4 == 0 ? b.min.z : b.max.z);
                    var sp = arCamera.WorldToScreenPoint(c); if (sp.z <= 0) continue;
                    any = true; x0 = Mathf.Min(x0, sp.x); x1 = Mathf.Max(x1, sp.x); y0 = Mathf.Min(y0, Screen.height - sp.y); y1 = Mathf.Max(y1, Screen.height - sp.y);
                }
            }
            return any ? new Rect(x0, y0, x1 - x0, y1 - y0) : (Rect?)null;
        }
        bool IsTitle(Renderer r) { var t = Titles; return t && r.transform.IsChildOf(t); }
        bool OnTitle(Vector2 gp) { var r = ScreenRect(IsTitle); if (!r.HasValue) return false; var x = r.Value; x.xMin -= 20; x.xMax += 20; x.yMin -= 20; x.yMax += 20; return x.Contains(gp); }

        void Buzz(long ms)
        {
            if (!haptics) return;
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                using var player = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
                using var activity = player.GetStatic<AndroidJavaObject>("currentActivity");
                using var vib = activity.Call<AndroidJavaObject>("getSystemService", "vibrator");
                vib.Call("vibrate", ms);
            }
            catch { Handheld.Vibrate(); }   // also makes Unity add the VIBRATE permission
#endif
        }

        // ---------------- textures and styles ----------------
        static Texture2D RoundRect(int size, int radius, Color fill, Color stroke, float strokeW)
        {
            var t = new Texture2D(size, size, TextureFormat.RGBA32, false) { wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear };
            float r = radius, half = size / 2f;
            for (int y = 0; y < size; y++) for (int x = 0; x < size; x++)
            {
                float px = Mathf.Abs(x + 0.5f - half) - (half - r), py = Mathf.Abs(y + 0.5f - half) - (half - r);
                float d = Mathf.Sqrt(Mathf.Max(px, 0) * Mathf.Max(px, 0) + Mathf.Max(py, 0) * Mathf.Max(py, 0)) + Mathf.Min(Mathf.Max(px, py), 0) - r;   // signed distance, <0 inside
                float inside = Mathf.Clamp01(0.5f - d), inner = Mathf.Clamp01(0.5f - (d + strokeW));
                var c = Color.Lerp(stroke, fill, inner); c.a *= inside; t.SetPixel(x, y, c);
            }
            t.Apply(); return t;
        }
        static GUIStyle Box(Texture2D t, int border) { var s = new GUIStyle { border = new RectOffset(border, border, border, border) }; s.normal.background = t; return s; }
        GUIStyle Text(Font f, float size, Color c, TextAnchor a = TextAnchor.MiddleCenter, bool wrap = true)
        { var s = new GUIStyle(GUI.skin.label) { font = f, fontSize = Mathf.RoundToInt(size), alignment = a, wordWrap = wrap, clipping = TextClipping.Overflow }; s.normal.textColor = c; return s; }
        Texture2D Icon(string name) { if (!icons.TryGetValue(name, out var t)) icons[name] = t = Resources.Load<Texture2D>("UI/" + name); return t; }

        void InitStyles()
        {
            u = Mathf.Min(Screen.width, Screen.height) / 12.5f; lip = Mathf.Max(3, u * 0.12f);
            fUi = Resources.Load<Font>("Fonts/Fredoka-SemiBold"); fZh = Resources.Load<Font>("Fonts/ZCOOLKuaiLe-Regular"); fDisplay = Resources.Load<Font>("Fonts/Grandstander-Black");
            float fs = u * 0.52f, stroke = 3.5f;
            white = Texture2D.whiteTexture;
            boxPaper = Box(RoundRect(64, 24, DesignTokens.Paper, DesignTokens.Ink, stroke), 28);
            boxShade = Box(RoundRect(64, 24, DesignTokens.PaperShade, DesignTokens.Ink, 2.5f), 28);
            boxSun = Box(RoundRect(64, 24, DesignTokens.Sun, DesignTokens.Ink, stroke), 28);
            boxOk = Box(RoundRect(64, 24, DesignTokens.Ok, DesignTokens.Ink, stroke), 28);
            boxLeaf = Box(RoundRect(64, 24, DesignTokens.Leaf, DesignTokens.Ink, 2.5f), 28);
            boxDeep = Box(RoundRect(64, 24, DesignTokens.PaperDeep, DesignTokens.Ink, 2.5f), 28);
            boxInk = Box(RoundRect(64, 24, DesignTokens.Ink, DesignTokens.Ink, 0), 28);
            disc = RoundRect(128, 64, Color.white, Color.white, 0);          // tinted circles (chips, dots, stamp)
            dot = RoundRect(32, 16, Color.white, Color.white, 0);
            ring = RoundRect(128, 64, new Color(1, 1, 1, 0), Color.white, 9);
            txtUi = Text(fUi, fs, DesignTokens.Ink); txtZh = Text(fZh, fs * 1.05f, DesignTokens.Ink);
            txtSmall = Text(fUi, fs * 0.72f, DesignTokens.InkSoft); txtSmallZh = Text(fZh, fs * 0.78f, DesignTokens.InkSoft);
            txtLogo = Text(fDisplay, u * 1.25f, DesignTokens.Ink, TextAnchor.MiddleCenter, false);
            txtTitle = Text(fDisplay, fs * 1.05f, DesignTokens.Ink, TextAnchor.MiddleLeft, false);
            txtTag = Text(fZh, fs * 0.8f, DesignTokens.Ink);
            fpStyle = Text(null, u * 0.26f, new Color(1, 1, 1, 0.5f), TextAnchor.LowerRight, false);
        }
        GUIStyle T(bool big = true) => L10n.IsZh ? (big ? txtZh : txtSmallZh) : (big ? txtUi : txtSmall);
        GUIStyle TOther(bool big = false) => L10n.IsZh ? (big ? txtUi : txtSmall) : (big ? txtZh : txtSmallZh);

        // ---------------- drawing helpers ----------------
        void Card(Rect r, GUIStyle fill, float l)
        {
            if (l > 0) GUI.Box(new Rect(r.x, r.y + l, r.width, r.height), GUIContent.none, boxInk);
            GUI.Box(r, GUIContent.none, fill);
        }
        bool Pressed(Rect r) => Input.GetMouseButton(0) && r.Contains(Event.current.mousePosition);
        // pencil outline + solid lip; the face sinks onto the lip while pressed
        bool PaperButton(Rect r, string text, GUIStyle fill, GUIStyle style, float l = -1)
        {
            if (l < 0) l = lip; uiRects.Add(new Rect(r.x, r.y, r.width, r.height + l));
            float off = Pressed(r) ? l * 0.7f : 0;
            GUI.Box(new Rect(r.x, r.y + l, r.width, r.height), GUIContent.none, boxInk);
            var face = new Rect(r.x, r.y + off, r.width, r.height);
            GUI.Box(face, GUIContent.none, fill);
            if (!string.IsNullOrEmpty(text)) GUI.Label(face, text, style);
            return GUI.Button(new Rect(r.x, r.y, r.width, r.height + l), GUIContent.none, GUIStyle.none);
        }
        bool Chip(Rect r, Texture2D icon, Color fill, float iconScale = 0.55f, bool interactive = true)
        {
            float l = r.width * 0.07f; if (interactive) uiRects.Add(new Rect(r.x, r.y, r.width, r.height + l));
            float off = interactive && Pressed(r) ? l * 0.7f : 0;
            var c = GUI.color;
            GUI.color = new Color(DesignTokens.Ink.r, DesignTokens.Ink.g, DesignTokens.Ink.b, c.a); GUI.DrawTexture(new Rect(r.x, r.y + l, r.width, r.height), disc);
            GUI.DrawTexture(new Rect(r.x, r.y + off, r.width, r.height), disc);
            var inner = new Rect(r.x + r.width * 0.035f, r.y + off + r.height * 0.035f, r.width * 0.93f, r.height * 0.93f);
            GUI.color = new Color(fill.r, fill.g, fill.b, c.a); GUI.DrawTexture(inner, disc);
            GUI.color = c;
            if (icon) { float s = r.width * iconScale; GUI.DrawTexture(new Rect(r.center.x - s / 2, r.center.y - s / 2 + off, s, s), icon, ScaleMode.ScaleToFit); }
            return interactive && GUI.Button(new Rect(r.x, r.y, r.width, r.height + l), GUIContent.none, GUIStyle.none);
        }
        void Tinted(Texture2D t, Rect r, Color c, float a = 1) { var o = GUI.color; GUI.color = new Color(c.r, c.g, c.b, c.a * a * o.a); GUI.DrawTexture(r, t); GUI.color = o; }
        // crayon dots along a line; solid = one thick bar
        void Stroke(Vector2 a, Vector2 b, float width, Color c, bool dotted)
        {
            float len = Vector2.Distance(a, b); if (len < 1) return;
            if (!dotted) { int n = Mathf.CeilToInt(len / (width * 0.35f)); for (int i = 0; i <= n; i++) { var p = Vector2.Lerp(a, b, i / (float)n); Tinted(dot, new Rect(p.x - width / 2, p.y - width / 2, width, width), c); } return; }
            int k = Mathf.Max(1, Mathf.RoundToInt(len / (width * 1.9f)));
            for (int i = 0; i <= k; i++) { var p = Vector2.Lerp(a, b, i / (float)k); Tinted(dot, new Rect(p.x - width / 2, p.y - width / 2, width, width), c); }
        }
        // what she says (and the other language underneath), in a paper speech bubble
        void Bubble(string main, string other, Rect area, float a)
        {
            if (a <= 0 || string.IsNullOrEmpty(main)) return;
            var c = GUI.color; GUI.color = new Color(1, 1, 1, a);
            var sMain = T(); var sOther = TOther();
            float w = Mathf.Min(area.width, Mathf.Max(sMain.CalcSize(new GUIContent(main)).x, sOther.CalcSize(new GUIContent(other ?? "")).x) + u * 0.9f);
            float h1 = sMain.CalcHeight(new GUIContent(main), w - u * 0.7f), h2 = string.IsNullOrEmpty(other) ? 0 : sOther.CalcHeight(new GUIContent(other), w - u * 0.7f);
            float h = h1 + h2 + u * 0.45f, y = area.yMax - h + u * 0.15f * (1 - EaseOut(a));
            var r = new Rect(area.center.x - w / 2, y, w, h);
            Card(r, boxPaper, lip * 0.8f);
            GUI.Label(new Rect(r.x + u * 0.35f, r.y + u * 0.2f, w - u * 0.7f, h1), main, sMain);
            if (h2 > 0) GUI.Label(new Rect(r.x + u * 0.35f, r.y + u * 0.2f + h1, w - u * 0.7f, h2), other, sOther);
            GUI.color = c;
        }
        // the four crayon corners of the scan frame; dotted while searching, solid green when found
        void ScanCorners(Rect f, bool ok, float a)
        {
            var c = GUI.color; GUI.color = new Color(1, 1, 1, a);
            float L = Mathf.Min(f.width, f.height) * 0.16f, wdt = u * 0.26f;
            var col = ok ? DesignTokens.Ok : DesignTokens.Paper;
            Vector2[] corners = { new Vector2(f.xMin, f.yMin), new Vector2(f.xMax, f.yMin), new Vector2(f.xMax, f.yMax), new Vector2(f.xMin, f.yMax) };
            Vector2[] dirs = { new Vector2(1, 1), new Vector2(-1, 1), new Vector2(-1, -1), new Vector2(1, -1) };
            for (int i = 0; i < 4; i++)
            {
                var p = corners[i]; var d = dirs[i];
                Stroke(p, p + new Vector2(d.x * L, 0), wdt, col, !ok); Stroke(p, p + new Vector2(0, d.y * L), wdt, col, !ok);
            }
            GUI.color = c;
        }
        void Logo(Rect r)
        {
            string word = "DoodLive";
            Color[] cols = { DesignTokens.Red, DesignTokens.Orange, DesignTokens.Sun, DesignTokens.Leaf, DesignTokens.Sky, DesignTokens.Grape, DesignTokens.Pink, DesignTokens.Red };
            float[] rot = { -6, 4, -3, 5, -4, 6, -5, 3 };
            float total = 0; var widths = new float[word.Length];
            for (int i = 0; i < word.Length; i++) { widths[i] = txtLogo.CalcSize(new GUIContent(word[i].ToString())).x * 0.92f; total += widths[i]; }
            float x = r.center.x - total / 2, o = Mathf.Max(2, u * 0.06f);
            var m = GUI.matrix; var c0 = txtLogo.normal.textColor;
            for (int i = 0; i < word.Length; i++)
            {
                var lr = new Rect(x, r.y, widths[i] / 0.92f, r.height); var piv = lr.center;
                GUIUtility.RotateAroundPivot(rot[i], piv);
                txtLogo.normal.textColor = DesignTokens.Ink;   // outline + lip: ink copies behind
                for (int k = 0; k < 8; k++) { float ang = k * Mathf.PI / 4; GUI.Label(new Rect(lr.x + Mathf.Cos(ang) * o, lr.y + Mathf.Sin(ang) * o, lr.width, lr.height), word[i].ToString(), txtLogo); }
                GUI.Label(new Rect(lr.x, lr.y + o * 2.6f, lr.width, lr.height), word[i].ToString(), txtLogo);
                txtLogo.normal.textColor = cols[i]; GUI.Label(lr, word[i].ToString(), txtLogo);
                GUI.matrix = m; x += widths[i];
            }
            txtLogo.normal.textColor = c0;
        }

        // =====================================================================================================
        void OnGUI()
        {
            if (boxPaper == null || Mathf.Abs(u - Mathf.Min(Screen.width, Screen.height) / 12.5f) > 0.5f) InitStyles();
            uiRects.Clear();
            float w = Screen.width, h = Screen.height, top = h - Screen.safeArea.yMax, bottom = Screen.safeArea.yMin;
            bool land = w > h, live = state >= State.LiveIdle, scanning = state == State.ScanSearch || state == State.ScanLocked || state == State.ScanHelp;
            float chip = u * 1.15f, edge = u * 0.35f;

            // -- reveal flash + lost dimming
            float flash = Mathf.Clamp01(1 - (Time.time - flashT) / 0.25f);
            if (flash > 0) Tinted(white, new Rect(0, 0, w, h), new Color(1f, 0.97f, 0.86f), flash * 0.9f);
            float dim = Fade("dim", state == State.LiveLost, 2.5f);
            if (dim > 0) Tinted(white, new Rect(0, 0, w, h), DesignTokens.Ink, 0.45f * dim);

            // -- status pill (scan states only; in Live the angel and the hint do the teaching)
            string want = statusKey == "" || (live && state != State.LiveLost) || state == State.Reveal || state == State.ScanHelp ? ""
                        : (statusKey == "camFail" || statusKey == "xrFail" ? L10n.T(statusKey, statusArg) : L10n.T(statusKey));
            if (state == State.LiveLost) want = "";   // the lost bubble says it
            if (want != shownStatus) { prevStatus = shownStatus; shownStatus = want; statusT = 0; }
            statusT = Mathf.Min(1, statusT + Time.unscaledDeltaTime / 0.2f);
            float barA = Fade("bar", shownStatus != "" && state != State.Home, 5f);
            if (barA > 0)
            {
                var st = T(); string s = shownStatus != "" ? shownStatus : prevStatus;
                float pw = Mathf.Min(w - chip * 2 - edge * 4, st.CalcSize(new GUIContent(s)).x + u * 0.9f);
                float ph = st.CalcHeight(new GUIContent(s), pw - u * 0.6f) + u * 0.4f;
                var r = new Rect(w / 2 - pw / 2, top + edge + 8 * (1 - EaseOut(statusT)), pw, ph);
                GUI.color = new Color(1, 1, 1, barA); Card(r, boxPaper, lip * 0.8f);
                GUI.Label(new Rect(r.x + u * 0.3f, r.y, pw - u * 0.6f, ph), s, st); GUI.color = Color.white;
                uiRects.Add(r);
            }

            // -- 01 Home: a sheet of paper; the angel is already climbing out of the drawing
            float homeA = Fade("home", state == State.Home, 4f);
            if (homeA > 0)
            {
                GUI.color = new Color(1, 1, 1, homeA);
                Tinted(white, new Rect(0, 0, w, h), DesignTokens.Paper);
                float rise = 14 * (1 - EaseOut(homeA));
                if (!land)
                {
                    Logo(new Rect(0, top + h * 0.08f + rise, w, u * 1.6f));
                    GUI.Label(new Rect(u, top + h * 0.08f + u * 1.75f + rise, w - 2 * u, u * 0.8f), L10n.T("tagline"), T(false));
                    HomeStage(new Rect(w / 2 - u * 3.6f, top + h * 0.23f + rise, u * 7.2f, u * 6.6f));
                    HomeActions(w / 2, h * 0.69f + rise);
                }
                else
                {
                    Logo(new Rect(0, top + u * 0.5f + rise, w, u * 1.5f));
                    HomeStage(new Rect(w * 0.12f, top + u * 2.4f + rise, u * 5.4f, h - top - bottom - u * 3.2f));
                    HomeActions(w * 0.66f, h * 0.42f + rise);
                }
                if (statusKey == "noPerm" || statusKey == "noAR") GUI.Label(new Rect(u, h - bottom - u * 1.6f, w - 2 * u, u * 1.2f), L10n.T(statusKey), T(false));
                GUI.color = Color.white;
            }

            // -- 02/03 Scan: crayon corners, coach phone, ✓ stamp + shutter ring when found
            float scanA = Fade("scan", state == State.ScanSearch || state == State.ScanLocked, 4f);
            if (scanA > 0)
            {
                float fw = land ? h * 0.62f * 0.82f : w * 0.78f, fh = fw / 0.82f;
                if (fh > h * 0.62f) { fh = h * 0.62f; fw = fh * 0.82f; }
                var frame = new Rect(w / 2 - fw / 2, h * 0.47f - fh / 2, fw, fh);
                ScanCorners(frame, state == State.ScanLocked, scanA);
                float coachA = Fade("coach", state == State.ScanSearch, 3f);
                if (coachA > 0)
                {
                    float t = Time.time * 2.4f, cw = u * 2.4f, chh = cw * 1.25f;
                    var cr = new Rect(w / 2 - cw / 2 + Mathf.Sin(t) * u * 0.7f, frame.center.y - chh / 2 + Mathf.Cos(t) * u * 0.25f, cw, chh);
                    var m = GUI.matrix; GUIUtility.RotateAroundPivot(Mathf.Sin(t) * 8, cr.center);
                    GUI.color = new Color(1, 1, 1, coachA * scanA); GUI.DrawTexture(cr, Icon("coach"), ScaleMode.ScaleToFit); GUI.color = Color.white; GUI.matrix = m;
                }
                float stampA = Fade("stamp", state == State.ScanLocked, 6f);
                if (stampA > 0)
                {
                    float s = u * 2.3f * BackOut(stampA); var sr = new Rect(w / 2 - s / 2, frame.center.y - s / 2, s, s);
                    var m = GUI.matrix; GUIUtility.RotateAroundPivot(-8 - 22 * (1 - stampA), sr.center);
                    GUI.color = new Color(1, 1, 1, stampA); Chip(sr, Icon("check"), DesignTokens.Ok, 0.55f, false); GUI.color = Color.white; GUI.matrix = m;
                }
                // the shutter is a progress dial here (capture is automatic); green dots fill as the lock holds
                float sz = u * 2.2f; var sh = new Rect(w / 2 - sz / 2, h - bottom - sz - u * 0.8f, sz, sz);
                if (land) sh = new Rect(w - edge - sz, h / 2 - sz / 2, sz, sz);
                GUI.color = new Color(1, 1, 1, scanA * (state == State.ScanLocked ? 1 : 0.5f)); Chip(sh, Icon("camera"), DesignTokens.Sun, 0.5f, false);
                if (state == State.ScanLocked)
                {
                    float p = Mathf.Clamp01(lockedFor / LockSeconds); int n = 28;
                    for (int i = 0; i < n * p; i++) { float ang = -Mathf.PI / 2 + i / (float)n * Mathf.PI * 2, rr = sz * 0.66f; var c = sh.center + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * rr; Tinted(dot, new Rect(c.x - u * 0.13f, c.y - u * 0.13f, u * 0.26f, u * 0.26f), DesignTokens.Ok); }
                }
                GUI.color = Color.white;
            }

            // -- 04 Help: the angel peeks over a paper card and thinks in pictures
            float helpA = Fade("help", state == State.ScanHelp, 4f);
            if (helpA > 0)
            {
                GUI.color = new Color(1, 1, 1, helpA);
                Tinted(white, new Rect(0, 0, w, h), DesignTokens.Ink, 0.35f * helpA);
                float cw = Mathf.Min(w - edge * 2, u * 10.5f), ch = u * 6.1f, cx = w / 2 - cw / 2, cy = h - bottom - ch - edge + u * 0.6f * (1 - EaseOut(helpA));
                var peek = Icon("home-angel"); if (peek && !land) { float pw = u * 3.2f, ph = pw * peek.height / peek.width; GUI.DrawTexture(new Rect(cx + cw - pw - u * 0.2f, cy - ph * 0.62f, pw, ph), peek); }
                var card = new Rect(cx, cy, cw, ch); Card(card, boxPaper, lip); uiRects.Add(card);
                var th = new Rect(cx + u * 0.4f, cy + u * 0.4f, cw - u * 0.8f, u * 2.9f); Card(th, boxPaper, 0);
                string[] ic = { "help-lift", "help-light", "help-squares" }, cap = { "helpLift", "helpLight", "helpSquares" };
                for (int i = 0; i < 3; i++)
                {
                    float colW = th.width / 3, ix = th.x + colW * i;
                    GUI.DrawTexture(new Rect(ix + colW / 2 - u * 0.7f, th.y + u * 0.3f, u * 1.4f, u * 1.4f), Icon(ic[i]), ScaleMode.ScaleToFit);
                    GUI.Label(new Rect(ix, th.y + u * 1.8f, colW, u * 0.8f), L10n.T(cap[i]), T(false));
                }
                GUI.Label(new Rect(cx, cy + u * 3.45f, cw, u * 0.9f), L10n.T("helpTitle"), T());
                float bw = Mathf.Min(cw - u, u * 5.2f);
                if (PaperButton(new Rect(w / 2 - bw / 2, cy + ch - u * 1.6f, bw, u * 1.05f), L10n.T("helpDemo"), boxPaper, txtTag)) ShowDemo();
                GUI.color = Color.white;
            }

            // -- 05 Reveal: crayon stars burst out of the page
            if (state == State.Reveal || (live && stateT < 0.1f && Time.time - flashT < 2f))
            {
                float t = Time.time - flashT - 0.35f;
                if (t > 0 && t < 1.6f)
                {
                    var center = ScreenRect(r => !IsTitle(r))?.center ?? new Vector2(w / 2, h * 0.6f);
                    Color[] cols = { DesignTokens.Sun, DesignTokens.Red, DesignTokens.Sky, DesignTokens.Pink, DesignTokens.Leaf, DesignTokens.Grape, DesignTokens.Orange };
                    float k = EaseOut(t / 1.6f), a = 1 - Mathf.Clamp01((t - 0.9f) / 0.7f);
                    for (int i = 0; i < 14; i++)
                    {
                        float ang = i / 14f * Mathf.PI * 2 + i * 0.37f, d = u * (2.6f + (i % 4) * 0.7f) * k, s = u * (i % 3 == 0 ? 0.35f : 0.7f);
                        var p = center + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * d - new Vector2(0, u * 1.2f * k);
                        var m = GUI.matrix; GUIUtility.RotateAroundPivot(i * 47 + t * 120, p);
                        Tinted(i % 3 == 0 ? dot : Icon("star"), new Rect(p.x - s / 2, p.y - s / 2, s, s), cols[i % cols.Length], a); GUI.matrix = m;
                    }
                }
            }

            // -- 06 Live: tap hint (dotted gold ring + hand) after 5 s without a touch
            bool hintWanted = state == State.LiveIdle && !voice.isPlaying && Time.time - Mathf.Max(lastTouch, idleSince) > HintAfter && !moreOpen;
            float hintA = Fade("hint", hintWanted, 3f);
            if (hintA > 0 && ScreenRect(r => !IsTitle(r)) is Rect ar)
            {
                ar.xMin = Mathf.Max(edge, ar.xMin - u * 0.2f); ar.xMax = Mathf.Min(w - edge - chip, ar.xMax + u * 0.2f);
                ar.yMin = Mathf.Max(top + edge, ar.yMin - u * 0.2f); ar.yMax = Mathf.Min(h - bottom - u * 2f, ar.yMax + u * 0.2f);
                float pulse = 1 + 0.03f * Mathf.Sin(Time.time * 4f); var c = ar.center; ar.width *= pulse; ar.height *= pulse; ar.center = c;
                int n = 44; for (int i = 0; i < n; i++)
                { float ang = i / (float)n * Mathf.PI * 2; var p = c + new Vector2(Mathf.Cos(ang) * ar.width / 2, Mathf.Sin(ang) * ar.height / 2); Tinted(dot, new Rect(p.x - u * 0.09f, p.y - u * 0.09f, u * 0.18f, u * 0.18f), DesignTokens.Sun, hintA); }
                float tap = Mathf.Abs(Mathf.Sin(Time.time * 2f)); var hand = Icon("hand");
                GUI.color = new Color(1, 1, 1, hintA); GUI.DrawTexture(new Rect(ar.xMax - u * 1.0f - tap * u * 0.15f, c.y + ar.height * 0.08f - tap * u * 0.15f, u * 1.0f, u * 1.15f), hand, ScaleMode.ScaleToFit);
                string tagTxt = L10n.T("tapHer"); var tr = new Rect(c.x - u * 1.4f, ar.yMax - u * 0.4f, u * 2.8f, u * 0.8f);
                Card(tr, boxSun, lip * 0.6f); GUI.Label(tr, tagTxt, txtTag); GUI.color = Color.white;
            }

            // -- 06 speech bubble: what she says, other language underneath; 07 read step names; 08 lost line
            string bubbleKey = state == State.LiveRead ? readKey : state == State.LiveLost ? "lost" : (voiceKey != null && voice.isPlaying && Time.time >= voiceFrom ? voiceKey : null);
            float bubA = Fade("bubble", bubbleKey != null, 4f);
            if (bubbleKey != null) lastBubble = bubbleKey;
            if (bubA > 0 && lastBubble != null)
            {
                var area = land ? new Rect(w * 0.58f, h * 0.18f, w * 0.3f, h * 0.5f) : new Rect(edge, top, w - edge * 2, h - bottom - edge - chip - lip - u * 0.35f - top);
                Bubble(L10n.T(lastBubble), L10n.Other(lastBubble), area, bubA);
            }

            // -- 08 Lost: a drawn sheet + arrow shows where the paper goes
            if (dim > 0)
            {
                float s = u * 3f, bob = Mathf.Sin(Time.time * 4f) * u * 0.12f;
                GUI.color = new Color(1, 1, 1, dim); GUI.DrawTexture(new Rect(w / 2 - s / 2, h * 0.42f - s * 0.62f + bob, s, s * 1.25f), Icon("lost-sheet"), ScaleMode.ScaleToFit); GUI.color = Color.white;
            }

            // -- chips: new sheet (Live) and the grown-up lock (Home + Live); 2 s hold opens the grown-ups panel (09)
            float chipA = Fade("chips", live || state == State.Home, 4f);
            if (chipA > 0)
            {
                GUI.color = new Color(1, 1, 1, chipA);
                var rLock = new Rect(w - edge - chip, top + edge, chip, chip);
                bool holding = !moreOpen && Pressed(rLock);
                gateHeld = holding ? gateHeld + Time.unscaledDeltaTime : 0;
                if (Chip(rLock, Icon("lock"), DesignTokens.Paper, 0.48f) && moreOpen) { if (gateJustOpened) gateJustOpened = false; else { Cue(cueClick); moreOpen = false; } }
                if (gateHeld > 0)
                {
                    int n = 30; float p = Mathf.Clamp01(gateHeld / GateHold);
                    for (int i = 0; i < n * p; i++) { float ang = -Mathf.PI / 2 + i / (float)n * Mathf.PI * 2; var c = rLock.center + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * chip * 0.66f; Tinted(dot, new Rect(c.x - u * 0.1f, c.y - u * 0.1f, u * 0.2f, u * 0.2f), DesignTokens.Red); }
                    if (gateHeld >= GateHold) { moreOpen = true; gateJustOpened = true; gateHeld = 0; Cue(cueLock); }
                }
                if (live && state != State.Reveal)
                {
                    var rNew = land ? new Rect(w - edge - chip, h - bottom - edge - chip - lip, chip, chip) : new Rect(w - edge - chip, h - bottom - edge - chip - lip, chip, chip);
                    if (Chip(rNew, Icon("new-sheet"), DesignTokens.Paper, 0.55f)) { Cue(cueClick); Rescan(); }
                }
                GUI.color = Color.white;
            }
            float panelA = Fade("panel", moreOpen && (live || state == State.Home), 5f);
            if (panelA > 0) GrownUps(panelA, w, top + edge + chip + u * 0.35f, edge);

            // -- build fingerprint
            fpStyle.normal.textColor = state == State.Home ? new Color(0.17f, 0.13f, 0.09f, 0.45f) : new Color(1, 1, 1, 0.5f);
            GUI.Label(new Rect(0, h - bottom - u * 0.4f, w - u * 0.2f, u * 0.4f), Fingerprint, fpStyle);
        }
        string lastBubble;

        void HomeStage(Rect r)
        {
            var sheet = Icon("home-sheet"); var climber = Icon("home-angel");
            if (sheet)
            {
                float sw = r.width * 0.64f, sh = sw * sheet.height / sheet.width; var sr = new Rect(r.x + r.width * 0.02f, r.y + r.height * 0.06f, sw, sh);
                var m = GUI.matrix; GUIUtility.RotateAroundPivot(-4, sr.center);
                Tinted(white, new Rect(sr.x + 3, sr.y + 6, sr.width, sr.height), DesignTokens.Ink, 0.12f);
                GUI.DrawTexture(sr, sheet);
                Tinted(white, new Rect(sr.x + sw * 0.05f, sr.y - u * 0.15f, sw * 0.32f, u * 0.38f), new Color(0.97f, 0.89f, 0.63f), 0.85f);
                Tinted(white, new Rect(sr.x + sw * 0.6f, sr.y - u * 0.2f, sw * 0.32f, u * 0.38f), new Color(0.97f, 0.89f, 0.63f), 0.85f);
                GUI.matrix = m;
            }
            if (climber)
            {
                float cw = r.width * 0.52f, ch = cw * climber.height / climber.width, bob = Mathf.Sin(Time.time * 2f) * u * 0.08f;
                var cr = new Rect(r.xMax - cw, r.y + r.height * 0.02f + bob, cw, ch);
                var m = GUI.matrix; GUIUtility.RotateAroundPivot(Mathf.Sin(Time.time * 2f) * 2, new Vector2(cr.center.x, cr.yMax)); GUI.DrawTexture(cr, climber); GUI.matrix = m;
            }
        }
        void HomeActions(float cx, float y)
        {
            float s = u * 2.4f;
            if (Chip(new Rect(cx - s / 2, y, s, s), Icon("camera"), DesignTokens.Sun, 0.5f)) { Cue(cueClick); Go(State.Permission); }
            GUI.Label(new Rect(cx - u * 4, y + s + u * 0.25f, u * 8, u * 0.9f), L10n.T("scan"), new GUIStyle(T()) { fontSize = Mathf.RoundToInt(u * 0.75f) });
            GUI.Label(new Rect(cx - u * 4, y + s + u * 1.05f, u * 8, u * 0.6f), L10n.T("scanLong"), T(false));
            float bw = u * 5.4f;
            if (PaperButton(new Rect(cx - bw / 2, y + s + u * 1.85f, bw, u * 1.05f), L10n.T("demo"), boxPaper, txtTag)) ShowDemo();
        }

        void GrownUps(float a, float w, float y, float edge)
        {
            GUI.color = new Color(1, 1, 1, a);
            float pw = Mathf.Min(w - edge * 2, u * 8.6f), row = u * 1.12f, x = w - edge - pw;
            var extras = new List<(string, System.Action)>();
            if (rawPx != null) extras.Add((L10n.T(showLines ? "linesOn" : "linesOff"), () => { showLines = !showLines; ApplyPage(); }));
            if (arReady && !showMode && state >= State.LiveIdle) extras.Add((L10n.T("modeShow"), () => { showMode = true; PlaceInFront(); }));
            float ph = u * 1.1f + row * 5 + extras.Count * (row * 0.95f) + u * 1.6f;
            ph = Mathf.Min(ph, Screen.height - y - edge);
            var r = new Rect(x, y - u * 0.25f * (1 - EaseOut(a)), pw, ph); Card(r, boxPaper, lip); uiRects.Add(r);
            float ix = r.x + u * 0.45f, iw = pw - u * 0.9f, cy = r.y + u * 0.3f;
            GUI.Label(new Rect(ix, cy, iw, u * 0.8f), L10n.T("grownups"), L10n.IsZh ? new GUIStyle(txtZh) { alignment = TextAnchor.MiddleLeft } : txtTitle); cy += u * 1.0f;
            GUIStyle left = new GUIStyle(T(false)) { alignment = TextAnchor.MiddleLeft }; left.normal.textColor = DesignTokens.Ink;
            void Seg(string label, string a1, string a2, bool firstOn, System.Action<bool> pick)
            {
                GUI.Label(new Rect(ix, cy, iw * 0.45f, row * 0.8f), label, left);
                float sw = iw * 0.52f, sx = ix + iw - sw; var sr = new Rect(sx, cy + row * 0.05f, sw, row * 0.72f);
                Card(sr, boxShade, lip * 0.5f); uiRects.Add(sr);
                var on = firstOn ? new Rect(sr.x + 4, sr.y + 4, sw / 2 - 4, sr.height - 8) : new Rect(sr.x + sw / 2, sr.y + 4, sw / 2 - 4, sr.height - 8);
                GUI.Box(on, GUIContent.none, boxSun);
                if (GUI.Button(new Rect(sr.x, sr.y, sw / 2, sr.height), a1, txtTag)) pick(true);
                if (GUI.Button(new Rect(sr.x + sw / 2, sr.y, sw / 2, sr.height), a2, txtTag)) pick(false);
                cy += row;
            }
            void Toggle(string label, bool on, System.Action flip)
            {
                GUI.Label(new Rect(ix, cy, iw * 0.6f, row * 0.8f), label, left);
                var tr = new Rect(ix + iw - u * 1.5f, cy + row * 0.1f, u * 1.5f, row * 0.62f);
                Card(tr, on ? boxLeaf : boxDeep, lip * 0.5f); uiRects.Add(tr);
                float k = tr.height - 8; Chip(new Rect(on ? tr.xMax - k - 4 : tr.x + 4, tr.y + 4, k, k), null, DesignTokens.Paper, 0, false);
                if (GUI.Button(tr, GUIContent.none, GUIStyle.none)) { Cue(cueClick); flip(); }
                cy += row;
            }
            Seg(L10n.T("language"), "中文", "EN", L10n.IsZh, zh => { if (zh != L10n.IsZh) { L10n.Toggle(); Cue(cueClick); } });
            Seg(L10n.T("wordCard"), L10n.T("pinyin"), "ABC", pinyinMode, py => { Cue(cueClick); pinyinMode = py; ShowTitle(null); });
            Toggle(L10n.T("sound"), !muted, () => { muted = !muted; PlayerPrefs.SetInt("muted", muted ? 1 : 0); AudioListener.volume = muted ? 0 : 1; });
            Toggle(L10n.T("haptics"), haptics, () => { haptics = !haptics; PlayerPrefs.SetInt("haptics", haptics ? 1 : 0); Buzz(20); });
            GUI.Label(new Rect(ix, cy, iw * 0.45f, row * 0.8f), L10n.T("music"), left);
            var slr = new Rect(ix + iw * 0.48f, cy + row * 0.15f, iw * 0.52f, row * 0.5f); uiRects.Add(slr);
            float nb = GUI.HorizontalSlider(slr, musicBed, 0f, 0.5f);
            if (!Mathf.Approximately(nb, musicBed)) { musicBed = nb; PlayerPrefs.SetFloat("musicBed", musicBed); }
            cy += row;
            foreach (var (label, act) in extras) { if (PaperButton(new Rect(ix, cy, iw, row * 0.78f), label, boxPaper, txtTag, lip * 0.6f)) { Cue(cueClick); act(); } cy += row * 0.95f; }
            if (PaperButton(new Rect(ix, r.yMax - u * 1.45f, iw, u * 0.95f), L10n.T("done"), boxSun, txtTag)) { Cue(cueClick); moreOpen = false; }
            GUI.color = Color.white;
        }
    }
}
