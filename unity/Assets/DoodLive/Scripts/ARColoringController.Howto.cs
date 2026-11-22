// "How to play" on the library home (docs/LIBRARY.md): blank paper -> colour it -> scan with the phone -> it comes
// alive in 3D. First run: a card at the top of the shelf (above keep reading) until the child has watched it once or
// dismissed it (PlayerPrefs "lib.howto.seen"); afterwards a small "?" chip next to the language switch reopens it.
// The video plays fullscreen with Unity's VideoPlayer from StreamingAssets/howto/howto.mp4 (720x1280 portrait,
// H.264 + AAC); in English howto_en.mp4 is tried first when it exists. Tap = pause / resume, x = close, the end goes
// back to the library. A missing or broken file shows the four steps as pictures instead.
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Video;

namespace DoodLive
{
    public partial class ARColoringController
    {
        const string HowtoSeenKey = "lib.howto.seen";
        bool howtoOpen, howtoMissing, howtoMusicPaused;
        float howtoPrepT;
        VideoPlayer howtoVp;
        readonly List<string> howtoQueue = new List<string>();
        static readonly string[] HowtoIcons = { "home-sheet", "crayon", "camera", "home-angel" };

        static bool HowtoSeen => PlayerPrefs.GetInt(HowtoSeenKey, 0) == 1;
        static void MarkHowtoSeen() { PlayerPrefs.SetInt(HowtoSeenKey, 1); PlayerPrefs.Save(); }

        void OpenHowto()
        {
            Cue(cueClick); StopVoice(); moreOpen = false;
            howtoOpen = true; howtoMissing = false; MarkHowtoSeen();
            if (music && music.isPlaying) { music.Pause(); howtoMusicPaused = true; }
            howtoQueue.Clear();
            if (!L10n.IsZh) howtoQueue.Add("howto_en.mp4");
            howtoQueue.Add("howto.mp4");
            PlayNextHowto();
        }

        void PlayNextHowto()
        {
            while (howtoQueue.Count > 0)
            {
                string url = Path.Combine(Application.streamingAssetsPath, "howto", howtoQueue[0]);
                howtoQueue.RemoveAt(0);
                if (!Platform.Native.Storage.StreamingFileMayExist(url)) continue;   // Android: inside the APK, errorReceived / the timeout tell
                EnsureHowtoPlayer();
                howtoVp.url = url; howtoVp.Prepare(); howtoPrepT = Time.unscaledTime;
                Debug.Log("DoodLive howto: " + url);
                return;
            }
            howtoMissing = true;
            if (howtoVp) howtoVp.Stop();
            Debug.Log("DoodLive howto: no video in StreamingAssets/howto, showing the picture steps");
        }

        void EnsureHowtoPlayer()
        {
            if (howtoVp) return;
            var go = new GameObject("HowtoVideo");
            go.transform.SetParent(transform, false);
            howtoVp = go.AddComponent<VideoPlayer>();
            howtoVp.playOnAwake = false; howtoVp.isLooping = false; howtoVp.waitForFirstFrame = true; howtoVp.skipOnDrop = true;
            howtoVp.source = VideoSource.Url;
            howtoVp.renderMode = VideoRenderMode.APIOnly;          // IMGUI draws howtoVp.texture
            howtoVp.audioOutputMode = VideoAudioOutputMode.Direct;
            howtoVp.prepareCompleted += vp =>
            {
                if (!howtoOpen) { vp.Stop(); return; }
                for (ushort t = 0; t < vp.audioTrackCount; t++) vp.SetDirectAudioVolume(t, muted ? 0 : 1);
                vp.Play();
            };
            howtoVp.errorReceived += (vp, msg) => { Debug.LogWarning("DoodLive howto video error: " + msg); if (howtoOpen) PlayNextHowto(); };
            howtoVp.loopPointReached += vp => CloseHowto();
        }

        void CloseHowto()
        {
            if (!howtoOpen) return;
            howtoOpen = false; howtoQueue.Clear();
            if (howtoVp) howtoVp.Stop();
            if (howtoMusicPaused && music) music.UnPause();
            howtoMusicPaused = false;
        }

        // once per frame (from LibraryInput): a file that never prepares counts as missing
        void HowtoTick()
        {
            if (!howtoOpen || howtoMissing || !howtoVp) return;
            if (!howtoVp.isPrepared && Time.unscaledTime - howtoPrepT > 8f) { Debug.LogWarning("DoodLive howto: prepare timed out"); howtoVp.Stop(); PlayNextHowto(); }
        }

        // the four steps as pictures with arrows between them; captions underneath when there is room
        void HowtoSteps(Rect r, bool captions, Color capColor)
        {
            float gapW = r.width * 0.07f, cell = (r.width - gapW * 3) / 4, ih = captions ? r.height * 0.66f : r.height;
            var back = Icon("back");
            for (int i = 0; i < 4; i++)
            {
                float x = r.x + i * (cell + gapW);
                var ir = new Rect(x, r.y, cell, ih);
                var tex = Icon(HowtoIcons[i]);
                if (tex) GUI.DrawTexture(ir, tex, ScaleMode.ScaleToFit);
                if (i == 3)   // "3D" sticker on the angel
                {
                    float s = Mathf.Min(cell, ih) * 0.42f; var br = new Rect(ir.xMax - s * 0.9f, ir.y, s, s);
                    Tinted(disc, br, DesignTokens.Sun);
                    GUI.Label(br, "3D", LS(false, s * 0.42f, DesignTokens.Ink, TextAnchor.MiddleCenter, true));
                }
                if (i < 3 && back)   // the back chevron turned around = "then"
                {
                    float s = gapW * 0.9f; var ar = new Rect(x + cell + gapW / 2 - s / 2, r.y + ih / 2 - s / 2, s, s);
                    var m = GUI.matrix; GUIUtility.RotateAroundPivot(180, ar.center);
                    var o = GUI.color; GUI.color = new Color(1, 1, 1, 0.55f * o.a); GUI.DrawTexture(ar, back, ScaleMode.ScaleToFit); GUI.color = o;
                    GUI.matrix = m;
                }
                if (captions)
                    GUI.Label(new Rect(x - gapW * 0.4f, r.y + ih + u * 0.05f, cell + gapW * 0.8f, r.height - ih), L10n.T("howtoStep" + (i + 1)),
                              LSL(L10n.Lang, u * (L10n.IsZh ? 0.3f : 0.26f), capColor, TextAnchor.UpperCenter));
            }
        }

        /// <summary>First-run card at the top of the shelf; returns the y below it.</summary>
        float HowtoCard(float x0, float x1, float cy, bool land)
        {
            float ch = land ? u * 3.0f : u * 3.5f; var card = new Rect(x0, cy, x1 - x0, ch);
            Card(card, boxPaper, lip);
            float ps = u * 1.4f, xs = u * 0.75f;
            var close = new Rect(card.xMax - xs - u * 0.2f, card.y + u * 0.2f, xs, xs);
            var play = new Rect(card.xMax - ps - u * 0.3f, card.y + ch - ps - u * 0.35f, ps, ps);
            // the small x dismisses (counts as seen); the play chip or the card itself plays the video
            if (Tap(Chip(close, Icon("close"), DesignTokens.Paper, 0.5f))) { Cue(cueClick); MarkHowtoSeen(); return cy; }
            bool go = Tap(Chip(play, Icon("play"), DesignTokens.Sun, 0.5f));
            BiKey(new Rect(card.x + u * 0.4f, card.y + u * 0.25f, card.width - xs - u * 1.0f, u * 0.6f), "howtoTitle", u * 0.48f, DesignTokens.Ink);
            GUI.Label(new Rect(card.x + u * 0.4f, card.y + u * 0.85f, card.width - xs - u * 1.0f, u * 0.5f), L10n.T("howtoLead"), LSL(L10n.Lang, u * 0.32f, DesignTokens.InkSoft));
            HowtoSteps(new Rect(card.x + u * 0.4f, card.y + u * 1.45f, card.width - ps - u * 1.1f, ch - u * 1.65f), true, DesignTokens.Ink);
            go |= Tap(GUI.Button(card, GUIContent.none, GUIStyle.none));
            if (go) OpenHowto();
            return cy + ch + u * 0.8f;
        }

        /// <summary>The "?" chip next to the language switch (after the first viewing).</summary>
        void HowtoChip(Rect r)
        {
            if (Tap(Chip(r, null, DesignTokens.Paper, 0))) OpenHowto();
            GUI.Label(new Rect(r.x, r.y - r.height * 0.04f, r.width, r.height), "?", LS(false, r.height * 0.5f, DesignTokens.Ink, TextAnchor.MiddleCenter, true));
        }

        // fullscreen player; drawn instead of every other screen while open (OnGUI returns after it)
        void HowtoGUI(float w, float h, float top, float bottom, float edge, float chip)
        {
            Tinted(white, new Rect(0, 0, w, h), DesignTokens.Ink);
            var tex = howtoVp && !howtoMissing && howtoVp.isPrepared ? howtoVp.texture : null;
            if (tex)
            {
                float vw = tex.width, vh = tex.height, s = Mathf.Min(w / vw, (h - top - bottom) / vh);
                GUI.DrawTexture(new Rect(w / 2 - vw * s / 2, top + (h - top - bottom) / 2 - vh * s / 2, vw * s, vh * s), tex, ScaleMode.StretchToFill);
                double len = howtoVp.length;
                if (len > 0) Bar(new Rect(u * 0.6f, h - bottom - u * 0.45f, w - u * 1.2f, u * 0.14f), (float)(howtoVp.time / len), DesignTokens.Sun);
            }
            else if (howtoMissing)
            {   // no video yet: the same four steps, big, with words
                float cw = Mathf.Min(w - edge * 4, u * 11f), ch = u * 5.4f;
                var card = new Rect(w / 2 - cw / 2, h / 2 - ch / 2, cw, ch);
                Card(card, boxPaper, lip);
                BiKey(new Rect(card.x + u * 0.5f, card.y + u * 0.3f, cw - u, u * 0.7f), "howtoTitle", u * 0.55f, DesignTokens.Ink);
                HowtoSteps(new Rect(card.x + u * 0.5f, card.y + u * 1.25f, cw - u, u * 2.8f), true, DesignTokens.Ink);
                GUI.Label(new Rect(card.x, card.yMax - u * 1.0f, cw, u * 0.7f), L10n.T("howtoSoon"), LSL(L10n.Lang, u * 0.36f, DesignTokens.InkSoft, TextAnchor.MiddleCenter));
            }
            else
            {   // preparing: three crayon dots
                for (int i = 0; i < 3; i++)
                {
                    float k = 0.5f + 0.5f * Mathf.Sin(Time.unscaledTime * 5f - i * 0.9f), s = u * (0.25f + 0.12f * k);
                    Tinted(dot, new Rect(w / 2 + (i - 1) * u * 0.6f - s / 2, h / 2 - s / 2, s, s), DesignTokens.Paper, 0.5f + 0.5f * k);
                }
            }
            bool vidPaused = howtoVp && !howtoMissing && howtoVp.isPrepared && !howtoVp.isPlaying;
            if (vidPaused)
            {
                float cw = u * 4.6f, ch = u * 2.3f; var r = new Rect(w / 2 - cw / 2, h * 0.45f - ch / 2, cw, ch);
                Card(r, boxPaper, lip);
                float bar = u * 0.32f, bh = u * 0.95f, bx = r.center.x - bar * 1.6f, byy = r.y + u * 0.3f;
                Tinted(white, new Rect(bx, byy, bar, bh), DesignTokens.Ink); Tinted(white, new Rect(bx + bar * 2.2f, byy, bar, bh), DesignTokens.Ink);
                GUI.Label(new Rect(r.x, r.y + u * 1.35f, cw, u * 0.8f), L10n.T("howtoPaused"), T(false));
            }
            // close first, so it wins over the full-screen pause catcher drawn after it
            if (Chip(new Rect(w - edge - chip, top + edge, chip, chip), Icon("close"), DesignTokens.Paper, 0.5f)) { Cue(cueClick); CloseHowto(); return; }
            if (GUI.Button(new Rect(0, 0, w, h), GUIContent.none, GUIStyle.none))
            {
                if (howtoMissing) { Cue(cueClick); CloseHowto(); }
                else if (howtoVp && howtoVp.isPrepared) { Cue(cueClick); if (howtoVp.isPlaying) howtoVp.Pause(); else howtoVp.Play(); }
            }
        }
    }
}
