// One character of the David & Goliath play (david / goliath): the glTFast-imported model with its glTF animation
// clips (pipeline/dg_animate.py), driven by a manual PlayableGraph so the director owns time completely: pause = stop
// advancing, cross-fade = two mixer weights, one-shots hold their last frame, loops wrap. No AnimatorController.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Animations;
using UnityEngine.Playables;

namespace DoodLive.DavidGoliath
{
    public class DGActor : MonoBehaviour
    {
        [Tooltip("Character id from CONTRACT §2: david | goliath")]
        public string id;
        [Tooltip("The imported glb root (clip paths are relative to it); carries the Animator")]
        public Animator animator;
        [Tooltip("glTF animations named <id>_<clip> (CONTRACT §5), filled by DGSetup")]
        public AnimationClip[] clips;
        [Tooltip("Loop flags per clip, same order (from anim/clips.json)")]
        public bool[] loops;
        [Tooltip("Page-coloured material of this character (DoodLive/DGPaperLit); the face decal is swapped per clip")]
        public Material material;
        [Tooltip("David's stone mesh: hidden until kneel_pick, hidden again once sling_release is over (ANIMATION.md §7.1)")]
        public Renderer stone;
        [Tooltip("Height in art-width units (design.json), used for camera targets and the subtitle anchor")]
        public float height = 0.3f;

        PlayableGraph graph;
        AnimationMixerPlayable mixer;
        AnimationClipPlayable[] playables;
        readonly Dictionary<string, int> index = new Dictionary<string, int>();

        // ---- performance state (written by DGDirector) ----
        [System.NonSerialized] public Vector2 pos;            // design XZ (art-width units)
        [System.NonSerialized] public float yaw;               // degrees, design frame (0 = facing the viewer, +Z)
        [System.NonSerialized] public string face = "viewer";
        [System.NonSerialized] public int cur = -1, prev = -1;
        [System.NonSerialized] public float curT0, curRate = 1, prevT0, prevRate = 1, blendT0, blend;
        [System.NonSerialized] public bool moving;
        [System.NonSerialized] public float moveT0, moveT1; [System.NonSerialized] public Vector2 moveFrom, moveTo;

        public bool Ready => graph.IsValid();

        public void Init()
        {
            if (graph.IsValid()) return;
            if (!animator) animator = GetComponentInChildren<Animator>();
            animator.runtimeAnimatorController = null;
            animator.applyRootMotion = false;            // goliath_fall/down carry their motion in the root BONE (ANIMATION.md §7.3)
            animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            graph = PlayableGraph.Create("DG_" + id);
            graph.SetTimeUpdateMode(DirectorUpdateMode.Manual);
            var output = AnimationPlayableOutput.Create(graph, "pose", animator);
            mixer = AnimationMixerPlayable.Create(graph, clips.Length);
            output.SetSourcePlayable(mixer);
            playables = new AnimationClipPlayable[clips.Length];
            for (int i = 0; i < clips.Length; i++)
            {
                var p = AnimationClipPlayable.Create(graph, clips[i]);
                p.SetApplyFootIK(false);
                graph.Connect(p, 0, mixer, i);
                mixer.SetInputWeight(i, 0);
                playables[i] = p;
                string n = clips[i].name.StartsWith(id + "_") ? clips[i].name.Substring(id.Length + 1) : clips[i].name;
                index[n] = i;
            }
        }

        void OnDestroy() { if (graph.IsValid()) graph.Destroy(); }

        public int Clip(string clip) => clip != null && index.TryGetValue(clip, out var i) ? i : -1;
        public string ClipName(int i) => i >= 0 && i < clips.Length ? clips[i].name.Substring(id.Length + 1) : null;
        public float Length(int i) => i >= 0 ? clips[i].length : 0;
        bool Loop(int i) => loops != null && i < loops.Length && loops[i];

        double LocalTime(int i, float t)
        {
            float len = Mathf.Max(1e-3f, clips[i].length);
            if (Loop(i)) return Mathf.Repeat(t, len);
            return Mathf.Clamp(t, 0, len - 1e-4f);                  // one-shots hold their last frame (ANIMATION.md §2)
        }

        /// <summary>Pose the character at performance time <paramref name="now"/> from the cur/prev clip state.</summary>
        public void Evaluate(float now)
        {
            if (!graph.IsValid() || cur < 0) return;
            float w = 1;
            if (prev >= 0 && blend > 0 && now - blendT0 < blend) { float k = Mathf.Clamp01((now - blendT0) / blend); w = k * k * (3 - 2 * k); }
            else prev = -1;
            for (int i = 0; i < clips.Length; i++)
            {
                float wi = i == cur ? w : (i == prev ? 1 - w : 0);
                if (i == cur && i == prev) wi = 1;
                mixer.SetInputWeight(i, wi);
            }
            playables[cur].SetTime(LocalTime(cur, (now - curT0) * curRate));
            if (prev >= 0 && prev != cur) playables[prev].SetTime(LocalTime(prev, (now - prevT0) * prevRate));
            graph.Evaluate(0);
        }

        [Tooltip("Face decal per clip, same order as clips (design.json faceDecals.clipExpression)")]
        public Texture2D[] faces;
        public Texture2D defaultFace;

        public void SetFace(int clip)
        {
            var decal = faces != null && clip >= 0 && clip < faces.Length && faces[clip] ? faces[clip] : defaultFace;
            if (material && decal) material.SetTexture("_DecalMap", decal);
        }

        Dictionary<string, Transform> bones;
        /// <summary>Bone by its CONTRACT §3 name (e.g. "slingPouch"); null when absent.</summary>
        public Transform Bone(string name)
        {
            if (bones == null)
            {
                bones = new Dictionary<string, Transform>();
                foreach (var t in GetComponentsInChildren<Transform>(true)) if (!bones.ContainsKey(t.name)) bones[t.name] = t;
            }
            return name != null && bones.TryGetValue(name, out var b) ? b : null;
        }
    }
}
