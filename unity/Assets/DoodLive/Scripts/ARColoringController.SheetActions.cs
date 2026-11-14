// Book-page sheet actions (docs/LIBRARY.md, "Sheet actions"): save / share / print the book's colouring-sheet PDF
// with the phone's own screens. Two files per book: the blank sheet and the coloured sample; a two-way choice above
// the buttons picks one (blank first). The PDFs ride in the APK as StreamingAssets/sheets/<sheet>.pdf and
// <sheet>-colored.pdf and are listed in Resources/sheet_pdfs.json (all written by Editor/SheetPdfSetup.cs); a book
// without an entry shows no row, a book without a coloured PDF shows no choice.
// Android: Assets/Plugins/Android/DoodLiveShare.java (MediaStore.Downloads, ACTION_SEND chooser, PrintManager).
// Elsewhere (editor, desktop): log and open the PDF with the system viewer.
// Grown-up gate: same rule as the lock chip (UI.cs): a 2 s hold fires the action; while the grown-ups panel is open a
// plain tap does. A short tap only shows a hint, so a child poking the page never leaves the app.
using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace DoodLive
{
    public partial class ARColoringController
    {
        [Serializable] class SheetPdf { public string book, file, colored; }
        [Serializable] class SheetPdfIndex { public SheetPdf[] sheets; }

        Dictionary<string, string> sheetPdfs;          // library book id -> file name in StreamingAssets/sheets/
        Dictionary<string, string> sheetPdfsColored;   // library book id -> the coloured sample's file name (optional)
        bool sheetColored;                             // the book page's choice: false = blank sheet, true = coloured sample
        string sheetChoiceBook; int sheetChoiceFrame = -99;   // the choice returns to blank when a book page opens
        static readonly string[] SheetKindKeys = { "sheetBlank", "sheetColored" }, SheetKindNames = { "空白-Blank", "示范-Coloured" };
        readonly float[] sheetHold = new float[3];
        int sheetFired = -1;                           // the button whose hold already fired (until the finger lifts)
        string sheetNote; float sheetNoteT = -99;
        static readonly string[] SheetActs = { "save", "share", "print" }, SheetIcons = { "save-pdf", "share", "print" },
                                 SheetKeys = { "sheetSave", "sheetShare", "sheetPrint" };

        string SheetPdfFor(string book)
        {
            if (sheetPdfs == null)
            {
                sheetPdfs = new Dictionary<string, string>(); sheetPdfsColored = new Dictionary<string, string>();
                var j = Resources.Load<TextAsset>("sheet_pdfs");
                if (j) foreach (var s in JsonUtility.FromJson<SheetPdfIndex>(j.text).sheets ?? new SheetPdf[0])
                        if (!string.IsNullOrEmpty(s.book) && !string.IsNullOrEmpty(s.file))
                        {
                            sheetPdfs[s.book] = s.file;
                            if (!string.IsNullOrEmpty(s.colored)) sheetPdfsColored[s.book] = s.colored;
                        }
            }
            return book != null && sheetPdfs.TryGetValue(book, out var f) ? f : null;
        }

        /// <summary>The coloured sample's file (null: this book has the blank sheet only).</summary>
        string SheetColoredPdfFor(string book) => SheetPdfFor(book) != null && sheetPdfsColored.TryGetValue(book, out var f) ? f : null;

        // "DoodLive-出埃及-Exodus-空白-Blank.pdf" / "DoodLive-出埃及-Exodus-示范-Coloured.pdf": the Chinese title, the
        // story id in title case, then which of the two sheets it is
        static string SheetFileName(LibBook b, bool colored)
        {
            var parts = (b.id ?? "sheet").Split('-');
            for (int i = 0; i < parts.Length; i++) if (parts[i].Length > 0) parts[i] = char.ToUpperInvariant(parts[i][0]) + parts[i].Substring(1);
            string name = $"DoodLive-{b.zh}-{string.Join("-", parts)}-{SheetKindNames[colored ? 1 : 0]}.pdf";
            foreach (var c in Path.GetInvalidFileNameChars()) name = name.Replace(c, '_');
            return name;
        }

        /// <summary>Height the row needs at the bottom of the book page (0: this book has no PDF).</summary>
        float SheetRowHeight(LibBook b) => SheetPdfFor(b.id) == null ? 0 : u * 1.9f + (SheetColoredPdfFor(b.id) != null ? SheetChoiceH + u * 0.1f : 0);
        float SheetChoiceH => u * 0.7f;   // the blank / coloured choice, between the caption and the buttons

        // two halves on one paper button, the chosen half sun-yellow (the language switch's look); a plain tap, since
        // choosing a file does not leave the app
        void SheetChoice(Rect r)
        {
            bool clicked = Tap(PaperButton(r, "", boxPaper, txtTag, lip * 0.5f));
            float half = r.width / 2, off = Pressed(r) ? lip * 0.5f * 0.7f : 0;
            if (clicked) { bool pick = Event.current.mousePosition.x >= r.x + half; if (pick != sheetColored) { sheetColored = pick; Cue(cueClick); } }
            Tinted(dot, new Rect(r.x + (sheetColored ? half : 0) + r.height * 0.12f, r.y + off + r.height * 0.14f, half - r.height * 0.24f, r.height * 0.72f), DesignTokens.Sun);
            for (int i = 0; i < 2; i++)
                GUI.Label(new Rect(r.x + i * half, r.y + off, half, r.height), L10n.T(SheetKindKeys[i]), LS(L10n.IsZh, u * (L10n.IsZh ? 0.32f : 0.28f), DesignTokens.Ink, TextAnchor.MiddleCenter));
        }

        void SheetActionsRow(LibBook b, Rect area)
        {
            string file = SheetPdfFor(b.id); if (file == null) return;
            // caption: lock + "for grown-ups", small and soft so children read past it
            float cap = u * 0.42f;
            var lk = Icon("lock"); if (lk) { var o = GUI.color; GUI.color = new Color(1, 1, 1, 0.6f * o.a); GUI.DrawTexture(new Rect(area.x, area.y + cap * 0.1f, cap * 0.8f, cap * 0.8f), lk, ScaleMode.ScaleToFit); GUI.color = o; }
            GUI.Label(new Rect(area.x + cap, area.y, area.width - cap, cap), L10n.T("sheetGrownups"), LS(L10n.IsZh, u * 0.27f, DesignTokens.InkSoft));
            float gap = u * 0.25f, bh = u * 0.9f, bw = (area.width - gap * 2) / 3, by = area.y + cap + u * 0.1f;
            // which sheet: blank (default, again each time a book page opens) or the coloured sample
            string coloredFile = SheetColoredPdfFor(b.id);
            if (sheetChoiceBook != b.id || Time.frameCount - sheetChoiceFrame > 1) { sheetChoiceBook = b.id; sheetColored = false; }
            sheetChoiceFrame = Time.frameCount;
            if (coloredFile == null) sheetColored = false;
            else { SheetChoice(new Rect(area.x, by, area.width, SheetChoiceH)); by += SheetChoiceH + u * 0.1f; }
            if (sheetColored) file = coloredFile;
            bool repaint = Event.current.type == EventType.Repaint;
            for (int i = 0; i < 3; i++)
            {
                var r = new Rect(area.x + i * (bw + gap), by, bw, bh);
                bool clicked = PaperButton(r, "", boxPaper, txtTag, lip * 0.6f);
                bool down = Pressed(r);
                float off = down ? lip * 0.6f * 0.7f : 0, ic = bh * 0.62f;
                var icr = new Rect(r.x + u * 0.22f, r.y + off + (bh - ic) / 2, ic, ic);
                GUI.DrawTexture(icr, Icon(SheetIcons[i]), ScaleMode.ScaleToFit);
                GUI.Label(new Rect(icr.xMax + u * 0.15f, r.y + off, r.xMax - icr.xMax - u * 0.2f, bh), L10n.T(SheetKeys[i]), LS(L10n.IsZh, u * (L10n.IsZh ? 0.36f : 0.32f), DesignTokens.Ink));
                if (repaint)
                {
                    if (down && !moreOpen && sheetFired != i)
                    {
                        sheetHold[i] += Time.unscaledDeltaTime;
                        if (sheetHold[i] >= GateHold) { sheetFired = i; sheetHold[i] = 0; Cue(cueLock); SheetAction(SheetActs[i], b, file); }
                    }
                    else if (!down) { sheetHold[i] = 0; if (sheetFired == i) sheetFired = -1; }
                }
                if (sheetHold[i] > 0)   // the lock chip's red dots, around the icon
                {
                    int n = 24; float p = Mathf.Clamp01(sheetHold[i] / GateHold);
                    for (int k = 0; k < n * p; k++) { float ang = -Mathf.PI / 2 + k / (float)n * Mathf.PI * 2; var c = icr.center + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * ic * 0.72f; Tinted(dot, new Rect(c.x - u * 0.07f, c.y - u * 0.07f, u * 0.14f, u * 0.14f), DesignTokens.Red); }
                }
                if (clicked)
                {
                    if (moreOpen) { Cue(cueClick); SheetAction(SheetActs[i], b, file); }
                    else if (sheetFired != i) { Cue(cueClick); SheetNote(L10n.T("sheetHoldHint")); }
                }
            }
        }

        void SheetAction(string action, LibBook b, string file)
        {
            bool colored = file != SheetPdfFor(b.id);   // the coloured sample was chosen
            string name = SheetFileName(b, colored), title = "DoodLive – " + BookTitle(b) + (colored ? " · " + L10n.T("sheetColored") : "");
#if UNITY_ANDROID && !UNITY_EDITOR
            try
            {
                using var up = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
                using var act = up.GetStatic<AndroidJavaObject>("currentActivity");
                using var share = new AndroidJavaClass("today.onemorething.doodlive.share.DoodLiveShare");
                string r = share.CallStatic<string>("run", act, action, "sheets/" + file, name, action == "print" ? title : L10n.T("sheetShareTitle"));
                Debug.Log($"DoodLive sheet {action} {b.id}: {r}");
                if (r != null && r.StartsWith("saved")) SheetNote(L10n.T("sheetSaved"));
                else if (r == null || r.StartsWith("error")) SheetNote(L10n.T("sheetFailed"));
            }
            catch (Exception e) { Debug.LogWarning($"DoodLive sheet {action} {b.id} failed: {e.Message}"); SheetNote(L10n.T("sheetFailed")); }
#else
            string path = Path.Combine(Application.streamingAssetsPath, "sheets", file);
            Debug.Log($"DoodLive sheet {action} {b.id} ({name}): native {action} is Android only; opening {path}");
            if (File.Exists(path)) { Application.OpenURL(new Uri(path).AbsoluteUri); SheetNote(L10n.T("sheetDesktop")); }
            else SheetNote(L10n.T("sheetFailed"));
#endif
        }

        void SheetNote(string text) { sheetNote = text; sheetNoteT = Time.unscaledTime; }

        // a paper note above the bottom edge for 2.6 s (saved / hold hint / failed); drawn last on the library screens
        void SheetNoteGUI(float w, float h, float bottom)
        {
            float age = Time.unscaledTime - sheetNoteT;
            if (string.IsNullOrEmpty(sheetNote) || age > 2.6f) return;
            float a = Mathf.Clamp01(Mathf.Min(age / 0.15f, (2.6f - age) / 0.4f));
            var st = new GUIStyle(txtTag) { wordWrap = false };
            float pw = Mathf.Min(w - u, st.CalcSize(new GUIContent(sheetNote)).x + u * 1.0f), ph = u * 0.95f;
            var r = new Rect(w / 2 - pw / 2, h - bottom - u * 2.9f + u * 0.2f * (1 - EaseOut(a)), pw, ph);
            var c = GUI.color; GUI.color = new Color(1, 1, 1, a * c.a);
            Card(r, boxSun, lip * 0.7f); GUI.Label(r, sheetNote, st);
            GUI.color = c;
        }
    }
}
