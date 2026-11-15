// Data side of the David & Goliath performance: assets/david-goliath/timeline.json (CONTRACT §6, written by the Story
// role) and the two audio manifests, parsed with JsonUtility. Copied into Resources/DG/ by DGSetup; never edited here.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace DoodLive.DavidGoliath
{
    [Serializable]
    public class DGCamera { public string type = "orbit", target = "both"; public float dist = 1.2f, height = 0.35f, yawDeg; }

    [Serializable]
    public class DGShot { public string id, title_zh, title_en, desc; public float t0, t1; public DGCamera camera; }

    [Serializable]
    public class DGActing
    {
        public float t; public string who, clip, face; public float blend = 0.25f;
        public float[] to;                                   // XZ target in art-width units (design axes); empty = stay put
        public bool HasTarget => to != null && to.Length >= 2;
        public float y = float.NaN;                          // story packs: base height for this mark (the king on the dais)
        public bool snap;                                    // place at `to` at once instead of walking (off-page moves)
    }

    [Serializable]
    public class DGLine { public string id, who, zh, en, @ref, voice, dir; public float t, maxSec; }

    /// <summary>Story packs: show / hide a node ("king/ring", "palace/table") at t (docs/esther/CONTRACT.md §5).
    /// grow &gt; 0: pop in (scale ~0 → 1, ease-out-back) on show, shrink away on hide, over grow seconds; 0 = instant.</summary>
    [Serializable]
    public class DGProp { public float t; public string node; public bool show; public float grow; }

    [Serializable]
    public class DGFxCue { public float t, dur; public string id, at, to; }   // to: optional far end (sceptre_beam)

    [Serializable]
    public class DGSfxCue { public float t; public string id; }

    [Serializable]
    public class DGMusicCue { public float t; public string cue; }

    [Serializable]
    public class DGTimeline
    {
        public int version, fps;
        public float duration;
        public string story, set;                            // story packs (docs/STORY-ARCHITECTURE.md); empty for David & Goliath
        public string[] cast;
        public DGProp[] props;
        public DGShot[] shots;
        public DGActing[] acting;
        public DGLine[] lines;
        public DGFxCue[] fx;
        public DGSfxCue[] sfx;
        public DGMusicCue[] music;
        public string[] requestedClips;

        public static DGTimeline Load(string json)
        {
            var t = JsonUtility.FromJson<DGTimeline>(json);
            // The Story role keeps every list sorted; sort again anyway, the director walks them with one cursor each.
            Array.Sort(t.acting, (a, b) => a.t.CompareTo(b.t));
            Array.Sort(t.lines, (a, b) => a.t.CompareTo(b.t));
            Array.Sort(t.fx, (a, b) => a.t.CompareTo(b.t));
            Array.Sort(t.sfx, (a, b) => a.t.CompareTo(b.t));
            Array.Sort(t.music, (a, b) => a.t.CompareTo(b.t));
            if (t.props == null) t.props = new DGProp[0];
            Array.Sort(t.props, (a, b) => a.t.CompareTo(b.t));
            return t;
        }

        public DGShot ShotAt(float time)
        {
            foreach (var s in shots) if (time >= s.t0 && time < s.t1) return s;
            return shots.Length > 0 ? shots[shots.Length - 1] : null;
        }
    }

    // assets/david-goliath/audio/sfx/mix.json (Music role): recommended playback gain per id and the loop flag.
    [Serializable] public class DGSfxMixEntry { public string id; public float gainDb; public bool loop; public float secs; }
    [Serializable] public class DGSfxMix { public DGSfxMixEntry[] sfx; }

    // assets/david-goliath/audio/music/cues.json: crossfade length; sting_hit is a one-shot.
    [Serializable] public class DGCueEntry { public string cue; public bool oneShot, loop; }
    [Serializable] public class DGCues { public float crossfadeSec = 0.6f; public DGCueEntry[] cues; }

    // assets/david-goliath/anim/clips.json (Animation role): clip lengths, loop flags, markers.
    [Serializable] public class DGClipInfo
    {
        public string action, @char, clip; public int frames; public float seconds, naturalSpeed; public bool loop, rootMotion, backwards;   // naturalSpeed: story packs, in-place locomotion (art units / s)
        public DGClipMarkers markers;
        public DGDesertEvent[] desertEvents;                  // david_kneel_pick: hide desert/fiveStones/stoneK at sec
    }
    [Serializable] public class DGMarker { public int frame = -1; public float sec = -1; }
    /// <summary>The clip markers Integration uses (ANIMATION.md §2); other markers are ignored by JsonUtility.</summary>
    [Serializable] public class DGClipMarkers { public DGMarker kneel, pick1, pick2, pick3, pick4, pick5, stone_in_pouch; }
    [Serializable] public class DGDesertEvent { public int frame; public float sec; public string hide; }
    [Serializable] public class DGClips { public float fps; public DGClipInfo[] clips; public float[] stoneTarget; public float hitTime; }

    /// <summary>Facts from docs/david-goliath/ANIMATION.md that are not in clips.json.</summary>
    public static class DGAnimFacts
    {
        // §5 natural locomotion speeds (art-width units / s) of the in-place clips: the director plays them at
        // actual / natural speed so the feet do not skate (clamped 0.5–1.5 like the Blender preview).
        public static readonly Dictionary<string, float> NaturalSpeed = new Dictionary<string, float>
        {
            { "david_walk", 0.129f }, { "david_run", 0.328f }, { "goliath_walk", 0.071f }, { "goliath_charge", 0.125f },
        };
        public const float MinRate = 0.5f, MaxRate = 1.5f;
    }
}
