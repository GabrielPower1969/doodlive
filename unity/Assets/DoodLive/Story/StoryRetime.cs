// Runtime re-timing (docs/VOICE-SYSTEM.md section 5): the play adapts to whatever voice clips are installed, so a longer
// or shorter recording never needs tools/story/build_timeline.py or a new APK.
//
// tools/story/build_timeline.py writes an `anchor` {line, edge, dt} on every line, event and shot (the cursor segment
// it was authored in), `dur` (the voice length it was timed to) on every line and `durationAnchor` at the top. Rule:
// every element moves by the shift of its anchor; a line's shift is the shift of its own anchor, and the shift at a
// line's "end" edge is that shift plus (installed duration - dur). Timelines without anchors (David & Goliath) get
// them inferred (InferAnchors), with slots that only grow. This file is a port of tools/voice/retime.py; the test
// tools/voice/test_retime.py runs both on the same data.
//
// Core() and InferAnchors() are plain C# (no UnityEngine calls) so the test harness can run them under .NET.
#pragma warning disable 0649   // fields filled by JsonUtility
using System;
using System.Collections.Generic;
using System.Linq;
using DoodLive.DavidGoliath;
using UnityEngine;

namespace DoodLive.Story
{
    /// <summary>Where an element was authored: `dt` seconds after the origin, a line's voice start or its voice end.</summary>
    [Serializable]
    public class StoryAnchor
    {
        public string line, edge;    // edge: "origin" | "start" | "end"; empty = no anchor (infer one)
        public float dt;
        public bool IsSet => !string.IsNullOrEmpty(edge);
        public static StoryAnchor Origin(float dt) => new StoryAnchor { line = "", edge = "origin", dt = dt };
    }

    public static class StoryRetime
    {
        // ---------------- pure core (shared with the .NET test harness) ----------------
        public sealed class Item { public float t; public StoryAnchor anchor; }
        public sealed class LineItem { public string id; public float t, maxSec, dur; public StoryAnchor anchor; }

        /// <summary>Voice length the play was timed to; old timelines (no dur) use the whole slot and only grow.</summary>
        static float Baked(LineItem l, out bool legacy) { legacy = !(l.dur > 0); return legacy ? l.maxSec : l.dur; }

        /// <summary>Anchors for a timeline built before anchors existed. Fills only missing ones.</summary>
        public static void InferAnchors(LineItem[] lines, IEnumerable<Item> items, ref StoryAnchor durationAnchor, float duration)
        {
            var ls = lines.OrderBy(l => l.t).ToArray();
            for (int i = 0; i < ls.Length; i++)
            {
                if (ls[i].anchor != null && ls[i].anchor.IsSet) continue;
                if (i == 0) { ls[i].anchor = StoryAnchor.Origin(ls[i].t); continue; }
                var p = ls[i - 1];
                ls[i].anchor = new StoryAnchor { line = p.id, edge = "end", dt = ls[i].t - (p.t + Baked(p, out _)) };
            }
            StoryAnchor At(float x)
            {
                LineItem prev = null;
                foreach (var l in ls) { if (l.t <= x + 1e-6f) prev = l; else break; }
                if (prev == null) return StoryAnchor.Origin(x);
                float end = prev.t + Baked(prev, out _);
                return x < end - 1e-6f ? new StoryAnchor { line = prev.id, edge = "start", dt = x - prev.t }
                                       : new StoryAnchor { line = prev.id, edge = "end", dt = x - end };
            }
            foreach (var e in items) if (e.anchor == null || !e.anchor.IsSet) e.anchor = At(e.t);
            if (durationAnchor == null || !durationAnchor.IsSet) durationAnchor = At(duration);
        }

        /// <summary>Re-time in place. durationOf(lineId) = installed clip seconds, or &lt;= 0 when the line has no clip
        /// (it keeps its baked length). Items are shot starts and every event; returns the new play duration.
        /// Identity (bit-exact) when every duration equals the baked one.</summary>
        public static float Core(LineItem[] lines, Item[] items, StoryAnchor durationAnchor, float duration, Func<string, float> durationOf)
        {
            var start = new Dictionary<string, float>(); var delta = new Dictionary<string, float>();
            float Shift(StoryAnchor a)
            {
                if (a == null || string.IsNullOrEmpty(a.line) || !start.TryGetValue(a.line, out float s)) return 0;
                return a.edge == "end" ? s + delta[a.line] : s;
            }
            foreach (var l in lines.OrderBy(l => l.t).ToArray())    // anchors only point backwards: one pass in time order
            {
                float s = Shift(l.anchor);
                float d0 = Baked(l, out bool legacy);
                float d1 = durationOf != null ? durationOf(l.id) : 0;
                if (!(d1 > 0)) d1 = d0;
                if (legacy) d1 = Math.Max(d1, d0);
                start[l.id] = s; delta[l.id] = d1 - d0;
                l.t += s; l.maxSec += d1 - d0;
                if (!legacy) l.dur = d1;
            }
            foreach (var e in items) e.t = Math.Max(0f, e.t + Shift(e.anchor));
            return duration + Shift(durationAnchor);
        }

        // ---------------- Unity side: timeline.json -> re-timed DGTimeline ----------------
        [Serializable] class AEv { public float t; public StoryAnchor anchor; }
        [Serializable] class AShot { public float t0; public StoryAnchor anchor; }
        [Serializable] class ALine { public string id; public float t, maxSec, dur; public StoryAnchor anchor; }
        [Serializable] class AView
        {
            public ALine[] lines; public AShot[] shots; public AEv[] acting, fx, sfx, music, props;
            public StoryAnchor durationAnchor;
        }

        /// <summary>Drop-in for DGTimeline.Load(json): parses, re-times to durationOf (null = no change), sorts.
        /// Log = one line per re-time for the device log.</summary>
        public static DGTimeline Load(string json, Func<string, float> durationOf)
        {
            var tl = JsonUtility.FromJson<DGTimeline>(json);           // JSON order, index-aligned with the anchor view
            var av = JsonUtility.FromJson<AView>(json);
            tl.props = tl.props ?? new DGProp[0]; tl.acting = tl.acting ?? new DGActing[0]; tl.lines = tl.lines ?? new DGLine[0];
            tl.fx = tl.fx ?? new DGFxCue[0]; tl.sfx = tl.sfx ?? new DGSfxCue[0]; tl.music = tl.music ?? new DGMusicCue[0];
            tl.shots = tl.shots ?? new DGShot[0];
            if (durationOf != null)
            {
                var lines = new LineItem[tl.lines.Length];
                for (int i = 0; i < lines.Length; i++)
                {
                    var a = av.lines != null && i < av.lines.Length ? av.lines[i] : null;
                    lines[i] = new LineItem { id = tl.lines[i].id, t = tl.lines[i].t, maxSec = tl.lines[i].maxSec, dur = a?.dur ?? 0, anchor = a?.anchor };
                }
                Item[] Items(int n, Func<int, float> t, AEv[] a)
                {
                    var r = new Item[n];
                    for (int i = 0; i < n; i++) r[i] = new Item { t = t(i), anchor = a != null && i < a.Length ? a[i].anchor : null };
                    return r;
                }
                var act = Items(tl.acting.Length, i => tl.acting[i].t, av.acting);
                var fx = Items(tl.fx.Length, i => tl.fx[i].t, av.fx);
                var sfx = Items(tl.sfx.Length, i => tl.sfx[i].t, av.sfx);
                var mus = Items(tl.music.Length, i => tl.music[i].t, av.music);
                var prp = Items(tl.props.Length, i => tl.props[i].t, av.props);
                var shots = new Item[tl.shots.Length];
                for (int i = 0; i < shots.Length; i++) shots[i] = new Item { t = tl.shots[i].t0, anchor = av.shots != null && i < av.shots.Length ? av.shots[i].anchor : null };
                var all = act.Concat(fx).Concat(sfx).Concat(mus).Concat(prp).Concat(shots).ToArray();
                var durA = av.durationAnchor;
                InferAnchors(lines, all, ref durA, tl.duration);
                float before = tl.duration;
                tl.duration = Core(lines, all, durA, tl.duration, durationOf);
                for (int i = 0; i < lines.Length; i++) { tl.lines[i].t = lines[i].t; tl.lines[i].maxSec = lines[i].maxSec; }
                for (int i = 0; i < act.Length; i++) tl.acting[i].t = act[i].t;
                for (int i = 0; i < fx.Length; i++) tl.fx[i].t = fx[i].t;
                for (int i = 0; i < sfx.Length; i++) tl.sfx[i].t = sfx[i].t;
                for (int i = 0; i < mus.Length; i++) tl.music[i].t = mus[i].t;
                for (int i = 0; i < prp.Length; i++) tl.props[i].t = prp[i].t;
                for (int i = 0; i < shots.Length; i++) tl.shots[i].t0 = shots[i].t;
                if (Mathf.Abs(tl.duration - before) > 1e-3f)
                    Debug.Log($"StoryRetime {tl.story}: {before:0.00} s -> {tl.duration:0.00} s for the installed voices");
            }
            // stable sorts (DGTimeline.Load uses Array.Sort, which is not stable; same order for distinct times)
            tl.acting = tl.acting.OrderBy(a => a.t).ToArray();
            tl.lines = tl.lines.OrderBy(a => a.t).ToArray();
            tl.fx = tl.fx.OrderBy(a => a.t).ToArray();
            tl.sfx = tl.sfx.OrderBy(a => a.t).ToArray();
            tl.music = tl.music.OrderBy(a => a.t).ToArray();
            tl.props = tl.props.OrderBy(a => a.t).ToArray();
            tl.shots = tl.shots.OrderBy(s => s.t0).ToArray();
            for (int i = 0; i < tl.shots.Length; i++) tl.shots[i].t1 = i + 1 < tl.shots.Length ? tl.shots[i + 1].t0 : tl.duration;
            return tl;
        }
    }
}
