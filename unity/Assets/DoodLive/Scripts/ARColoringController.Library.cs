// The home screen is a children's library (docs/LIBRARY.md): a "keep reading" card that resumes the last story at the
// shot where the child stopped, a bookshelf of framed covers (two per row in portrait, four in landscape) with
// bilingual titles and a new / reading / finished mark, and one big scan button that is always in reach. Tapping a
// cover opens its page: big cover, title in both languages with pinyin, a short blurb, watch / continue / scan, and
// the chapters (the shots of its timeline) to jump into. Data: Resources/library.json + Resources/Covers/<id>.png
// (tools/story/make_covers.py); progress: PlayerPrefs "lib.*". Drawn with IMGUI in the Paper & Crayon style.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive
{
    public partial class ARColoringController
    {
        [Serializable] public class LibShot { public string zh, en; }
        [Serializable] public class LibBook { public string id, zh, en, pinyin, blurbZh, blurbEn; public float minutes; public LibShot[] shots; }
        [Serializable] class LibData { public LibBook[] books; }

        LibBook[] books;
        string libOpen;                       // the book whose page is open (null: the shelf)
        float libScroll, libScrollMax, libPressY, libPressScroll, libVel; bool libDragged, libPressing;
        int startShot;                        // the shot the next story start jumps to (0: the beginning)
        readonly Dictionary<string, Texture2D> covers = new Dictionary<string, Texture2D>();
        readonly Dictionary<string, GUIStyle> libStyles = new Dictionary<string, GUIStyle>();
        GUIStyle frameBox;   // 9-slice rounded rect: crisp corners at any size

        static readonly Color Wood = new Color32(0xB9, 0x80, 0x4E, 0xFF), WoodDark = new Color32(0x8A, 0x5A, 0x3B, 0xFF),
                              Mat = new Color32(0xFF, 0xF8, 0xE8, 0xFF);

        void LoadLibrary()
        {
            var j = Resources.Load<TextAsset>("library");
            books = j ? JsonUtility.FromJson<LibData>(j.text).books : new LibBook[0];
        }

        Texture2D Cover(string id)
        {
            if (!covers.TryGetValue(id, out var t)) covers[id] = t = Resources.Load<Texture2D>("Covers/" + id);
            return t;
        }

        LibBook Book(string id) { if (books != null) foreach (var b in books) if (b.id == id) return b; return null; }
        static string Key(string what, string id) => $"lib.{what}.{id}";
        static int ShotOf(string id) => PlayerPrefs.GetInt(Key("shot", id), 0);
        static bool Done(string id) => PlayerPrefs.GetInt(Key("done", id), 0) == 1;
        static bool Opened(string id) => PlayerPrefs.GetInt(Key("open", id), 0) == 1;
        string BookTitle(LibBook b) => L10n.IsZh ? b.zh : b.en;
        string ShotTitle(LibShot s) => L10n.IsZh ? s.zh : s.en;

        // ---------------- progress: called every frame from Update ----------------
        string lastSavedShotKey;
        void TrackProgress()
        {
            if (state < State.Reveal) return;
            if (dgMode && active != null && active.Running && active.Timeline != null)
            {
                string id = active.StoryId; var shots = active.Timeline.shots; int i = 0;
                if (active.Shot != null && shots != null) for (int k = 0; k < shots.Length; k++) if (shots[k] == active.Shot) { i = k; break; }
                bool fin = active.Finished;
                string key = id + ":" + (fin ? "end" : i.ToString());
                if (key == lastSavedShotKey) return;
                lastSavedShotKey = key;
                PlayerPrefs.SetString("lib.last", id); PlayerPrefs.SetInt(Key("open", id), 1);
                if (fin) { PlayerPrefs.SetInt(Key("done", id), 1); PlayerPrefs.SetInt(Key("shot", id), 0); }
                else PlayerPrefs.SetInt(Key("shot", id), i);
                PlayerPrefs.Save();
            }
            else if (!dgMode && angel && angel.gameObject.activeInHierarchy && lastSavedShotKey != "angel")
            {
                lastSavedShotKey = "angel";
                PlayerPrefs.SetString("lib.last", "angel"); PlayerPrefs.SetInt(Key("open", "angel"), 1); PlayerPrefs.SetInt(Key("done", "angel"), 1);
                PlayerPrefs.Save();
            }
        }

        void OpenBook(LibBook b, int shot)
        {
            libOpen = null; lastSavedShotKey = null;
            PlayerPrefs.SetString("lib.last", b.id); PlayerPrefs.SetInt(Key("open", b.id), 1); PlayerPrefs.Save();
            if (b.id == "angel") { ShowDemo(); return; }
            foreach (var p in Players()) if (p.StoryId == b.id) { startShot = Mathf.Max(0, shot); ShowDemoStory(p); return; }
        }

        void BackToLibrary()
        {
            Cue(cueClick); StopVoice(); moreOpen = false;
            if (finder) finder.Forget();
            StopStory(); angel.gameObject.SetActive(false); showMode = false;
            Go(State.Home);
        }

        // ---------------- scrolling the shelf (once per frame, from Update) ----------------
        void LibraryInput()
        {
            if (state != State.Home || libOpen != null || moreOpen) { libPressing = false; return; }
            bool down = Input.touchCount > 0 || Input.GetMouseButton(0);
            float y = Input.touchCount > 0 ? Screen.height - Input.GetTouch(0).position.y : Screen.height - Input.mousePosition.y;
            if (down && !libPressing) { libPressing = true; libDragged = false; libPressY = y; libPressScroll = libScroll; libVel = 0; }
            else if (down)
            {
                float d = libPressY - y;
                if (Mathf.Abs(d) > u * 0.3f) libDragged = true;
                if (libDragged) { float prev = libScroll; libScroll = Mathf.Clamp(libPressScroll + d, 0, libScrollMax); libVel = (libScroll - prev) / Mathf.Max(1e-3f, Time.unscaledDeltaTime); }
            }
            else
            {
                libPressing = false;
                if (Mathf.Abs(libVel) > 1) { libScroll = Mathf.Clamp(libScroll + libVel * Time.unscaledDeltaTime, 0, libScrollMax); libVel *= Mathf.Exp(-Time.unscaledDeltaTime * 5); }
            }
        }
        bool Tap(bool clicked) => clicked && !libDragged;

        // ---------------- drawing ----------------
        GUIStyle LS(bool zh, float size, Color c, TextAnchor a = TextAnchor.MiddleLeft, bool display = false)
        {
            string k = $"{zh}{size:0.0}{c}{a}{display}";
            if (!libStyles.TryGetValue(k, out var s)) libStyles[k] = s = Text(display ? fDisplay : zh ? fZh : fUi, size, c, a, true);
            return s;
        }

        void FramedCover(Rect r, string id, float tilt)
        {
            if (frameBox == null) frameBox = Box(RoundRect(64, 14, Color.white, Color.white, 0), 20);
            var m = GUI.matrix; if (tilt != 0) GUIUtility.RotateAroundPivot(tilt, r.center);
            float b = Mathf.Max(4, r.width * 0.045f);
            FrameBox(new Rect(r.x + u * 0.08f, r.y + u * 0.14f, r.width, r.height), DesignTokens.Ink, 0.18f);   // shadow
            FrameBox(r, WoodDark, 1);
            FrameBox(new Rect(r.x + b * 0.4f, r.y + b * 0.4f, r.width - b * 0.8f, r.height - b * 0.8f), Wood, 1);
            var mat = new Rect(r.x + b, r.y + b, r.width - 2 * b, r.height - 2 * b);
            Tinted(white, mat, Mat);
            var img = new Rect(mat.x + b * 0.6f, mat.y + b * 0.6f, mat.width - b * 1.2f, mat.height - b * 1.2f);
            var tex = Cover(id);
            if (tex) GUI.DrawTexture(img, tex, ScaleMode.ScaleAndCrop); else Tinted(white, img, DesignTokens.PaperShade);
            GUI.matrix = m;
        }

        void FrameBox(Rect r, Color c, float a)
        {
            var o = GUI.color; GUI.color = new Color(c.r, c.g, c.b, a * o.a); GUI.Box(r, GUIContent.none, frameBox); GUI.color = o;
        }

        // a heading in both languages: Chinese in the Chinese face, then the English in the Latin face
        void Bi(Rect r, string zh, string en, float size, Color c)
        {
            var sz = LS(true, size, c); var se = LS(false, size * 0.78f, c);
            float wz = sz.CalcSize(new GUIContent(zh)).x;
            GUI.Label(new Rect(r.x, r.y, wz + 4, r.height), zh, sz);
            GUI.Label(new Rect(r.x + wz + size * 0.5f, r.y, r.width - wz - size * 0.5f, r.height), "·  " + en, se);
        }

        void Bar(Rect r, float p, Color fill)
        {
            Tinted(dot, r, DesignTokens.Ink, 0.12f);
            if (p > 0) Tinted(dot, new Rect(r.x, r.y, Mathf.Max(r.height, r.width * Mathf.Clamp01(p)), r.height), fill);
        }

        void Badge(Rect r, string text, Color fill)
        {
            Tinted(disc, new Rect(r.x, r.y + r.height * 0.08f, r.width, r.height), DesignTokens.Ink);
            Tinted(disc, r, fill);
            GUI.Label(r, text, LS(text.Length <= 1, r.height * (text.Length <= 1 ? 0.42f : 0.27f), DesignTokens.Ink, TextAnchor.MiddleCenter));
        }

        void LibraryGUI(float w, float h, float top, float bottom, float edge, float chip, bool land, float alpha)
        {
            if (books == null) LoadLibrary();
            GUI.color = new Color(1, 1, 1, alpha);
            Tinted(white, new Rect(0, 0, w, h), DesignTokens.Paper);
            if (libOpen != null && Book(libOpen) is LibBook ob) BookPage(ob, w, h, top, bottom, edge, chip, land);
            else Shelf(w, h, top, bottom, edge, chip, land);
            GUI.color = Color.white;
        }

        void LangChip(Rect r)
        {
            if (Tap(PaperButton(r, "", boxPaper, txtTag, lip * 0.6f))) { Cue(cueClick); L10n.Toggle(); }
            float half = r.width / 2;
            var on = new Rect(r.x + (L10n.IsZh ? 0 : half) + r.height * 0.12f, r.y + r.height * 0.14f, half - r.height * 0.24f, r.height * 0.72f);
            Tinted(dot, on, DesignTokens.Sun);
            GUI.Label(new Rect(r.x, r.y, half, r.height), "中文", LS(true, r.height * 0.4f, DesignTokens.Ink, TextAnchor.MiddleCenter));
            GUI.Label(new Rect(r.x + half, r.y, half, r.height), "EN", LS(false, r.height * 0.4f, DesignTokens.Ink, TextAnchor.MiddleCenter));
        }

        void Shelf(float w, float h, float top, float bottom, float edge, float chip, bool land)
        {
            float pad = u * 0.55f, x0 = pad, x1 = w - pad;
            float y = top + edge;
            // header: logo + language switch (the lock chip is drawn by the chips block, top right)
            Logo(new Rect(x0 - u * 0.3f, y - u * 0.05f, u * 4.6f, chip));
            LangChip(new Rect(w - edge - chip - u * 0.3f - u * 2.6f, y + chip * 0.1f, u * 2.6f, chip * 0.8f));
            y += chip + u * 0.35f;

            float scanH = u * 1.35f, footer = bottom + scanH + u * 0.9f;
            var view = new Rect(0, y, w, h - footer - y);
            GUI.BeginGroup(view);
            float cy = -libScroll + u * 0.1f;

            // greeting, both languages
            GUI.Label(new Rect(x0, cy, x1 - x0, u * 0.8f), "今天想读哪个故事？", LS(true, u * 0.62f, DesignTokens.Ink));
            GUI.Label(new Rect(x0, cy + u * 0.72f, x1 - x0, u * 0.6f), "Which story shall we read today?", LS(false, u * 0.4f, DesignTokens.InkSoft));
            cy += u * 1.6f;

            // keep reading
            string last = PlayerPrefs.GetString("lib.last", "");
            var lb = Book(last);
            if (lb != null)
            {
                float ch = land ? u * 3.0f : u * 3.6f; var card = new Rect(x0, cy, x1 - x0, ch);
                Card(card, boxSun, lip);
                float cw = ch * 0.62f; FramedCover(new Rect(card.x + u * 0.3f, card.y + (ch - cw * 4f / 3f * 0.92f) / 2, cw * 0.92f, cw * 4f / 3f * 0.92f), lb.id, -3);
                float tx = card.x + u * 0.3f + cw + u * 0.35f, tw = card.xMax - tx - u * 2.1f;
                int sh = ShotOf(lb.id), n = lb.shots != null ? lb.shots.Length : 0; bool fin = Done(lb.id) && sh == 0;
                Bi(new Rect(tx, card.y + u * 0.25f, tw, u * 0.5f), fin ? "再读一遍" : "接着读", fin ? "Read it again" : "Keep reading", u * 0.36f, DesignTokens.InkSoft);
                GUI.Label(new Rect(tx, card.y + u * 0.72f, tw, u * 0.75f), lb.zh, LS(true, u * 0.62f, DesignTokens.Ink));
                GUI.Label(new Rect(tx, card.y + u * 1.38f, tw, u * 0.5f), lb.en, LS(false, u * 0.38f, DesignTokens.Ink));
                if (n > 0 && !fin)
                {
                    GUI.Label(new Rect(tx, card.y + u * 1.95f, tw, u * 0.5f), (L10n.IsZh ? $"第 {sh + 1}/{n} 幕 · " : $"Part {sh + 1} of {n} · ") + ShotTitle(lb.shots[Mathf.Min(sh, n - 1)]), LS(L10n.IsZh, u * 0.34f, DesignTokens.Ink));
                    Bar(new Rect(tx, card.y + u * 2.55f, tw, u * 0.26f), (sh + 0.5f) / n, DesignTokens.Leaf);
                }
                float ps = u * 1.6f; var play = new Rect(card.xMax - ps - u * 0.3f, card.center.y - ps / 2, ps, ps);
                if (Tap(Chip(play, Icon("play"), DesignTokens.Paper, 0.5f)) || Tap(GUI.Button(card, GUIContent.none, GUIStyle.none))) { Cue(cueClick); OpenBook(lb, fin ? 0 : sh); }
                cy += ch + u * 0.8f;
            }

            // the bookshelf
            Bi(new Rect(x0, cy, x1 - x0, u * 0.7f), "我的书架", "My bookshelf", u * 0.5f, DesignTokens.Ink);
            cy += u * 0.95f;
            int cols = land ? 4 : 2; float gap = u * 0.55f, bw = (x1 - x0 - gap * (cols - 1)) / cols;
            if (land) bw = Mathf.Min(bw, view.height * 0.62f * 3f / 4f);   // landscape: a whole row of covers in view
            float bh = bw * 4f / 3f, gx = x0 + (x1 - x0 - (cols * bw + (cols - 1) * gap)) / 2;
            for (int r0 = 0; r0 * cols < books.Length; r0++)   // shelf planks first, the frames stand on them
            {
                float py = cy + r0 * (bh + u * 2.2f) + bh;
                var plank = new Rect(x0 - u * 0.3f, py - u * 0.12f, x1 - x0 + u * 0.6f, u * 0.3f);
                Tinted(white, new Rect(plank.x, plank.yMax, plank.width, u * 0.12f), DesignTokens.Ink, 0.12f);
                Tinted(white, plank, Wood); Tinted(white, new Rect(plank.x, plank.y, plank.width, u * 0.07f), Mat, 0.45f);
            }
            for (int i = 0; i < books.Length; i++)
            {
                var b = books[i]; int c = i % cols, r = i / cols;
                float bx = gx + c * (bw + gap), by = cy + r * (bh + u * 2.2f);
                var cover = new Rect(bx, by, bw, bh);
                FramedCover(new Rect(cover.x, cover.y - u * 0.15f, cover.width, cover.height), b.id, (i % 2 == 0 ? -1f : 1f));
                // mark: new / finished / reading
                float bs = u * 1.05f;
                if (!Opened(b.id)) Badge(new Rect(cover.xMax - bs * 0.8f, cover.y - bs * 0.3f, bs, bs), L10n.IsZh ? "新" : "NEW", DesignTokens.Red);
                else if (Done(b.id)) { Chip(new Rect(cover.xMax - bs * 0.8f, cover.y - bs * 0.3f, bs, bs), Icon("check"), DesignTokens.Ok, 0.55f, false); }
                GUI.Label(new Rect(bx, by + bh + u * 0.2f, bw, u * 0.7f), b.zh, LS(true, u * 0.52f, DesignTokens.Ink, TextAnchor.MiddleCenter));
                GUI.Label(new Rect(bx, by + bh + u * 0.82f, bw, u * 0.5f), b.en, LS(false, u * 0.36f, DesignTokens.InkSoft, TextAnchor.MiddleCenter));
                int n = b.shots != null ? b.shots.Length : 0, s = ShotOf(b.id);
                if (n > 0 && Opened(b.id) && s > 0) Bar(new Rect(bx + bw * 0.2f, by + bh + u * 1.42f, bw * 0.6f, u * 0.18f), (s + 0.5f) / n, DesignTokens.Leaf);
                if (Tap(GUI.Button(new Rect(bx, by, bw, bh + u * 1.4f), GUIContent.none, GUIStyle.none))) { Cue(cueClick); libOpen = b.id; }
            }
            int rows = (books.Length + cols - 1) / cols;
            cy += rows * (bh + u * 2.2f);
            GUI.EndGroup();
            libScrollMax = Mathf.Max(0, cy + libScroll - view.height + u * 0.4f);

            // always-in-reach scan button, on a paper strip so the shelf scrolls under it
            Tinted(white, new Rect(0, h - footer + u * 0.2f, w, footer), DesignTokens.Paper);
            Tinted(white, new Rect(0, h - footer + u * 0.2f, w, 2), DesignTokens.Ink, 0.12f);
            var sb = new Rect(x0, h - bottom - scanH - u * 0.45f, x1 - x0, scanH);
            if (Tap(PaperButton(sb, "", boxSun, txtTag))) { Cue(cueClick); startShot = 0; Go(State.Permission); }
            float ic = scanH * 0.62f; GUI.DrawTexture(new Rect(sb.x + u * 0.5f, sb.y + (scanH - ic) / 2, ic, ic), Icon("camera"), ScaleMode.ScaleToFit);
            GUI.Label(new Rect(sb.x + u * 0.5f + ic + u * 0.3f, sb.y, sb.width - ic - u, scanH * 0.6f), "扫一扫我的画", LS(true, u * 0.55f, DesignTokens.Ink));
            GUI.Label(new Rect(sb.x + u * 0.5f + ic + u * 0.3f, sb.y + scanH * 0.5f, sb.width - ic - u, scanH * 0.42f), "Scan my colouring", LS(false, u * 0.36f, DesignTokens.Ink));
            if (statusKey == "noPerm" || statusKey == "noAR") GUI.Label(new Rect(u, sb.y - u * 1.1f, w - 2 * u, u), L10n.T(statusKey), T(false));
        }

        void BookPage(LibBook b, float w, float h, float top, float bottom, float edge, float chip, bool land)
        {
            if (Chip(new Rect(edge, top + edge, chip, chip), Icon("back"), DesignTokens.Paper, 0.5f)) { Cue(cueClick); libOpen = null; return; }
            float pad = u * 0.6f, cw = land ? h * 0.42f : Mathf.Min(w * 0.5f, u * 6.2f), chh = cw * 4f / 3f;
            float cx = land ? w * 0.08f : w / 2 - cw / 2, y = top + edge + chip * 0.4f;
            FramedCover(new Rect(cx, y, cw, chh), b.id, -2);
            float tx = land ? cx + cw + u * 1.0f : pad, tw = land ? w - tx - pad : w - 2 * pad, ty = land ? top + edge + chip * 0.3f : y + chh + u * 0.5f;
            var center = land ? TextAnchor.MiddleLeft : TextAnchor.MiddleCenter;
            if (!string.IsNullOrEmpty(b.pinyin)) GUI.Label(new Rect(tx, ty, tw, u * 0.45f), b.pinyin, LS(false, u * 0.34f, DesignTokens.Red, center));
            GUI.Label(new Rect(tx, ty + u * 0.4f, tw, u * 1.0f), b.zh, LS(true, u * 0.9f, DesignTokens.Ink, center));
            GUI.Label(new Rect(tx, ty + u * 1.35f, tw, u * 0.6f), b.en, LS(false, u * 0.5f, DesignTokens.Ink, center));
            float by = ty + u * 2.05f;
            GUI.Label(new Rect(tx, by, tw, u * 0.9f), b.blurbZh, LS(true, u * 0.38f, DesignTokens.InkSoft, center));
            GUI.Label(new Rect(tx, by + u * 0.85f, tw, u * 0.8f), b.blurbEn, LS(false, u * 0.32f, DesignTokens.InkSoft, center));
            if (b.minutes > 0) GUI.Label(new Rect(tx, by + u * 1.55f, tw, u * 0.5f), $"约 {b.minutes:0.#} 分钟 · about {b.minutes:0.#} min", LS(true, u * 0.3f, DesignTokens.InkSoft, center));
            y = by + u * 2.15f;

            // actions: watch from the start, continue where you stopped, scan your own sheet
            int sh = ShotOf(b.id), n = b.shots != null ? b.shots.Length : 0;
            float btnW = land ? Mathf.Min(tw, u * 7) : tw, bx = land ? tx : w / 2 - btnW / 2, bh = u * 1.1f;
            if (sh > 0 && n > 0)
            {
                if (Tap(PaperButton(new Rect(bx, y, btnW, bh), L10n.IsZh ? $"▶  接着看第 {sh + 1} 幕 · Continue" : $"▶  Continue from part {sh + 1} · 接着看", boxSun, txtTag))) OpenBook(b, sh);
                y += bh + u * 0.45f;
                if (Tap(PaperButton(new Rect(bx, y, btnW, bh), "从头看 · Start from the beginning", boxPaper, txtTag))) OpenBook(b, 0);
            }
            else if (Tap(PaperButton(new Rect(bx, y, btnW, bh), "▶  看故事 · Watch the story", boxSun, txtTag))) OpenBook(b, 0);
            y += bh + u * 0.45f;
            if (Tap(PaperButton(new Rect(bx, y, btnW, bh), "扫我画的这张 · Scan my sheet", boxPaper, txtTag))) { Cue(cueClick); libOpen = null; startShot = 0; Go(State.Permission); }
            y += bh + u * 0.7f;

            // chapters: the timeline's shots; read ones are green, the next one is sun-yellow
            if (n > 0 && y < h - bottom - u * 1.5f)
            {
                Bi(new Rect(land ? tx : w / 2 - u * 2.1f, y, u * 6, u * 0.6f), "章节", "Chapters", u * 0.42f, DesignTokens.Ink);
                y += u * 0.75f;
                int cols = land ? 4 : 3; float gap = u * 0.25f, cwid = (tw - gap * (cols - 1)) / cols, chH = u * 0.95f;
                for (int i = 0; i < n; i++)
                {
                    var r = new Rect(tx + (i % cols) * (cwid + gap), y + (i / cols) * (chH + gap), cwid, chH);
                    if (r.yMax > h - bottom - u * 0.2f) break;
                    var fill = i < sh || Done(b.id) ? boxLeaf : i == sh && sh > 0 ? boxSun : boxPaper;
                    if (Tap(PaperButton(r, "", fill, txtTag, lip * 0.5f))) OpenBook(b, i);
                    GUI.Label(new Rect(r.x + u * 0.12f, r.y, u * 0.5f, chH), (i + 1).ToString(), LS(false, u * 0.36f, DesignTokens.Ink, TextAnchor.MiddleCenter));
                    GUI.Label(new Rect(r.x + u * 0.55f, r.y, r.width - u * 0.65f, chH), ShotTitle(b.shots[i]), LS(L10n.IsZh, u * (L10n.IsZh ? 0.3f : 0.26f), DesignTokens.Ink));
                }
            }
        }
    }
}
