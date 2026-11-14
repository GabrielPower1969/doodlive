// Prodigal rows of the off-Unity preview (run.sh prodigal): runs the real StoryFxProdigal code (and the reused ids the
// timeline plays with it) at 60 fps against stand-in actors at the docs/prodigal/storyboard/story.py marks, records the
// StoryTint result per frame so render.py can multiply a stand-in `homeland` set by it (what StoryTintStage's overlay does
// on device). A row name may carry "@variant". Rows with `under` get that stage effect (night / sunset_glow) underneath.
// Anchors can move (run_dust follows the running father); the track is fed every frame as DGFxInstance does.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class ProdigalPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  struct Act { public float x, z, h; public string col; }
  static Act So(float x, float z, float h = 0.34f) => new Act{x=x,z=z,h=h,col="#6FB3E0"};
  static Act Fa(float x, float z) => new Act{x=x,z=z,h=0.36f,col="#3F7A55"};
  static Act Br(float x, float z) => new Act{x=x,z=z,h=0.37f,col="#A8582E"};
  static readonly Dictionary<string, Act[]> Cast = new Dictionary<string, Act[]> {
    {"tavern", new[]{ So(0.32f,-0.26f) }},
    {"pigs",   new[]{ So(0.30f,0.10f,0.20f) }},
    {"run",    new[]{ So(0.10f,0.08f), Fa(-0.30f,-0.24f) }},
    {"hug",    new[]{ Fa(0.00f,0.06f), So(0.10f,0.08f) }},
    {"feast",  new[]{ So(-0.32f,-0.12f), Fa(-0.22f,-0.10f) }},
    {"finale", new[]{ So(0.06f,0.12f), Fa(-0.12f,0.08f), Br(-0.02f,0.10f) }},
  };
  struct Row { public string name; public float dur; public string cast; public Vector3 anchor, look, camOff; public string under; public float[] fr; public bool lamps; }
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  static readonly Row[] Rows = {
    new Row{name="coins_spray",       dur=1.6f, cast="tavern", anchor=V(0.35f,0.24f,-0.24f), look=V(0.34f,0.20f,-0.22f), camOff=V(-0.28f,0.12f,0.85f), fr=new[]{0.08f,0.2f,0.35f,0.55f,0.85f}},
    new Row{name="party_lights",      dur=20f,  cast="tavern", anchor=V(0.40f,0f,-0.47f),    look=V(0.40f,0.12f,-0.38f), camOff=V(-0.18f,0.10f,0.60f)},
    new Row{name="famine_haze",       dur=40f,  cast="pigs",   anchor=Vector3.zero,          look=V(0.22f,0.10f,-0.12f), camOff=V(-0.22f,0.26f,0.80f), fr=new[]{0.01f,0.03f,0.2f,0.6f,0.99f}},
    new Row{name="run_dust",          dur=2.8f, cast="run",    anchor=V(-0.16f,0f,-0.06f),   look=V(-0.07f,0.04f,0.0f), camOff=V(-0.30f,0.20f,0.55f), fr=new[]{0.06f,0.12f,0.18f,0.26f,0.42f}},
    new Row{name="heart_glow@hug",    dur=5f,   cast="hug",    anchor=V(0.00f,0.21f,0.06f),  look=V(0.05f,0.16f,0.07f),  camOff=V(-0.20f,0.06f,0.50f), under="sunset_glow"},
    new Row{name="music_notes",       dur=40f,  cast="feast",  anchor=V(-0.38f,0f,-0.47f),   look=V(-0.36f,0.20f,-0.36f), camOff=V(0.05f,0.12f,0.85f), under="night", fr=new[]{0.03f,0.06f,0.1f,0.15f,0.3f}},
    new Row{name="lamps_flames",      dur=24f,  cast="feast",  anchor=Vector3.zero,          look=V(-0.38f,0.08f,-0.24f), camOff=V(-0.05f,0.18f,0.66f), under="night"},
    new Row{name="lamps_flames@empties", dur=24f, cast="feast", anchor=Vector3.zero,         look=V(-0.38f,0.08f,-0.24f), camOff=V(-0.05f,0.18f,0.66f), under="night", lamps=true},
    new Row{name="golden_rays",       dur=7f,   cast="finale", anchor=V(-0.12f,0f,0.08f),    look=V(-0.04f,0.14f,0.08f), camOff=V(0.10f,0.16f,0.70f)},
  };
  // run_dust: the father runs from his lookout (-0.16, -0.06) to the meeting mark (0, 0.06) at an old man's jog (0.32 u/s),
  // then stands and hugs (a gentle rock)
  static Vector3 Anchor(Row row, float t) {
    if (row.name != "run_dust") return row.anchor;
    var a = V(-0.16f, 0f, -0.06f); var b = V(0f, 0f, 0.06f);
    float d = (b - a).magnitude, k = Mathf.Clamp01(t * 0.32f / d);
    return Vector3.Lerp(a, b, k) + (k >= 1f ? V(0.003f * Mathf.Sin(t * 3f), 0, 0) : Vector3.zero);
  }
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"coins_spray","party_lights","famine_haze","run_dust","music_notes","lamps_flames",
                             "sparkle","heart_glow","golden_rays","night","sunset_glow","lamp_flame"})
      Console.WriteLine($"id {id,-13} -> {(FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0];
      var def = FxLibrary.Get(id); if (def == null) throw new Exception("missing " + id);
      var cast = Cast[row.cast];
      RuthFx.Actors.Clear();
      foreach (var a in cast) RuthFx.Actors.Add(new RuthActor { feet = new Vector3(a.x, 0, a.z), height = a.h });
      ProdigalFx.Lamps.Clear();
      if (row.lamps) foreach (var p in new[]{ V(-0.47f,0.055f,-0.17f), V(-0.42f,0.055f,-0.15f), V(-0.34f,0.055f,-0.15f), V(-0.29f,0.055f,-0.17f),
                                              V(-0.44f,0.14f,-0.355f), V(-0.32f,0.14f,-0.355f), V(-0.20f,0.16f,-0.36f) }) ProdigalFx.Lamps.Add(p);
      if (id == "heart_glow") EstherFx.BeamTarget = V(0.10f, 0.20f, 0.08f); else EstherFx.BeamTarget = EstherFx.DefaultBeamTarget;
      var under = row.under != null ? FxLibrary.Get(row.under) : null;
      var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      var ctxU = new FxCtx { dur = dur + 1.6f, seed = 777, camPos = camPos, camRight = right, camUp = up };
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      float[] fr = row.fr ?? new[]{0.08f,0.25f,0.45f,0.65f,0.85f};
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"prodigal\",\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"actors\":[");
      for (int i = 0; i < cast.Length; i++) sb.Append((i>0?",":"") + $"[{F(cast[i].x)},{F(cast[i].z)},{F(cast[i].h)},\"{cast[i].col}\"]");
      sb.Append("],\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0;
      StoryTint.Clear();
      ctx.start = Anchor(row, 0); ctxU.start = Vector3.zero; ctxU.anchor = Vector3.zero;
      for (float t = 0; t < dur && fi < fr.Length; t += dt) {
        ctx.t = t; ctxU.t = t + 0.8f;
        var an = Anchor(row, t);
        ctx.anchor = def.Follow ? an : ctx.start; ctx.track.Add(t, an);
        batch.Clear();
        if (under != null) under.Emit(ctxU, batch);
        def.Emit(ctx, batch);
        StoryTint.Resolve(out Color tint, out Color rim, out float level);
        maxSprites = Math.Max(maxSprites, batch.sprites.Count); maxRibbons = Math.Max(maxRibbons, batch.ribbons.Count);
        if (t + 1e-4f >= fr[fi] * dur) {
          FxMeshBuilder.Build(batch, ctx, mn, sz, v, uv, col, ta, tb);
          sb.Append(fi==0?"":","); sb.Append($"{{\"t\":{F(t)},\"tint\":[{F(tint.r)},{F(tint.g)},{F(tint.b)}],\"v\":[");
          for (int i=0;i<v.Count;i++) sb.Append((i>0?",":"")+$"{F(v[i].x)},{F(v[i].y)},{F(v[i].z)},{F(uv[i].x)},{F(uv[i].y)},{F(col[i].r)},{F(col[i].g)},{F(col[i].b)},{F(col[i].a)}");
          sb.Append("],\"a\":["+string.Join(",",ta)+"],\"b\":["+string.Join(",",tb)+"]}");
          fi++;
        }
      }
      sb.Append($"],\"maxSprites\":{maxSprites}}}");
      Console.WriteLine($"{row.name,-20} dur {dur} follow {def.Follow} frames {fi} maxSprites {maxSprites} maxRibbons {maxRibbons}{(row.under != null ? " (with " + row.under + ")" : "")}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
    RuthFx.Actors.Clear(); ProdigalFx.Lamps.Clear(); EstherFx.BeamTarget = EstherFx.DefaultBeamTarget;
  }
}
