// Ruth rows of the off-Unity preview (run.sh ruth): runs the real StoryFxRuth code at 60 fps against stand-in actors
// and the CONTRACT §6 set marks, records the StoryTint result per frame so render.py can multiply the stand-in set
// by it (what StoryTintStage's overlay does on device), and writes the same frames.json format as Harness.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class RuthPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  // stand-in actors (docs/ruth/storyboard/story.py marks): feet x, z, height, colour
  struct Act { public string id; public float x, z, h; public string col; }
  static readonly Dictionary<string, Act[]> Cast = new Dictionary<string, Act[]> {
    {"road",  new[]{ new Act{id="naomi",x=-0.40f,z=0.16f,h=0.31f,col="#B98A9E"}, new Act{id="ruth",x=-0.28f,z=0.14f,h=0.33f,col="#9CC5A1"} }},
    {"glean", new[]{ new Act{id="ruth",x=0.14f,z=0.10f,h=0.22f,col="#9CC5A1"} }},
    {"drop",  new[]{ new Act{id="ruth",x=0.24f,z=0.12f,h=0.22f,col="#9CC5A1"}, new Act{id="boaz",x=0.38f,z=0.06f,h=0.38f,col="#6E7F3A"} }},
    {"door",  new[]{ new Act{id="naomi",x=-0.30f,z=-0.20f,h=0.31f,col="#B98A9E"}, new Act{id="ruth",x=-0.18f,z=-0.16f,h=0.33f,col="#9CC5A1"} }},
    {"night", new[]{ new Act{id="naomi",x=-0.40f,z=-0.22f,h=0.31f,col="#B98A9E"}, new Act{id="boaz",x=0.14f,z=-0.30f,h=0.38f,col="#6E7F3A"}, new Act{id="ruth",x=0.00f,z=-0.22f,h=0.33f,col="#9CC5A1"} }},
    {"baby",  new[]{ new Act{id="naomi",x=-0.22f,z=0.12f,h=0.31f,col="#B98A9E"}, new Act{id="ruth",x=-0.06f,z=0.08f,h=0.33f,col="#9CC5A1"} }},
  };
  static string CastOf(string id) {
    switch (id) {
      case "dust_road": case "heart_glow": return "road";
      case "chaff": return "glean";
      case "stalks_fall": return "drop";
      case "sunset_glow": return "door";
      case "night": case "lamp_flame": return "night";
      default: return "baby";
    }
  }
  static Vector3 Anchor(string id, float t) {
    switch (id) {
      case "dust_road": case "sunset_glow": case "night": return Vector3.zero;              // "stage"
      case "heart_glow": return new Vector3(-0.28f, 0.22f, 0.14f);                           // ruth.chest
      case "chaff": return new Vector3(0.37f, 0f, -0.11f);                                    // bethlehem.field
      case "stalks_fall": return new Vector3(0.37f, 0.17f, 0.015f);                  // boaz.handR behind his back
      case "lamp_flame": return new Vector3(0.40f, 0.045f, -0.40f);                           // bethlehem.lampFlame
      case "sparkle": return new Vector3(-0.21f, 0.17f, 0.15f);                               // naomi.baby
    }
    return Vector3.zero;
  }
  // camera: look point + offset (roughly the storyboard shot)
  static void Cam(string id, out Vector3 look, out Vector3 cam) {
    switch (id) {
      case "dust_road": look = new Vector3(-0.38f, 0.10f, 0.10f); cam = look + new Vector3(0.30f, 0.35f, 0.85f); return;
      case "heart_glow": look = new Vector3(-0.33f, 0.20f, 0.15f); cam = look + new Vector3(0.10f, 0.10f, 0.62f); return;
      case "chaff": look = new Vector3(0.33f, 0.10f, -0.05f); cam = look + new Vector3(0.0f, 0.22f, 0.70f); return;
      case "stalks_fall": look = new Vector3(0.36f, 0.09f, 0.03f); cam = look + new Vector3(0.42f, 0.10f, 0.14f); return;
      case "sunset_glow": look = new Vector3(0.0f, 0.20f, -0.20f); cam = look + new Vector3(0.20f, 0.22f, 1.05f); return;
      case "night": look = new Vector3(-0.08f, 0.26f, -0.30f); cam = look + new Vector3(-0.15f, 0.16f, 1.10f); return;
      case "lamp_flame": look = new Vector3(0.25f, 0.12f, -0.32f); cam = look + new Vector3(-0.15f, 0.14f, 0.62f); return;
      default: look = new Vector3(-0.21f, 0.19f, 0.15f); cam = look + new Vector3(0.05f, 0.08f, 0.45f); return;
    }
  }
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    var rows = new List<(string, float)>{ ("dust_road",6f),("heart_glow",6f),("chaff",8f),("stalks_fall",1.2f),
                                          ("sunset_glow",8f),("night",8f),("lamp_flame",8f),("sparkle",1.6f) };
    var night = FxLibrary.Get("night");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var (id, dur) in rows) {
      var def = FxLibrary.Get(id); if (def == null) throw new Exception("missing " + id);
      var cast = Cast[CastOf(id)];
      RuthFx.Actors.Clear();
      foreach (var a in cast) RuthFx.Actors.Add(new RuthActor { feet = new Vector3(a.x, 0, a.z), height = a.h });
      if (id == "heart_glow") EstherFx.BeamTarget = new Vector3(-0.40f, 0.20f, 0.16f); else EstherFx.BeamTarget = EstherFx.DefaultBeamTarget;
      Cam(id, out var look, out var camPos);
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      var ctxN = new FxCtx { dur = dur + 1.6f, seed = 777, camPos = camPos, camRight = right, camUp = up };   // lamp row: night around it
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      float[] fr = {0.08f,0.25f,0.45f,0.65f,0.85f};
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{id}\":{{\"dur\":{F(dur)},\"scene\":\"ruth\",\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"actors\":[");
      for (int i = 0; i < cast.Length; i++) sb.Append((i>0?",":"") + $"[{F(cast[i].x)},{F(cast[i].z)},{F(cast[i].h)},\"{cast[i].col}\"]");
      sb.Append("],\"frames\":[");
      float dt = 1f/60f; int fi = 0; bool started = false; int maxSprites = 0, maxRibbons = 0;
      StoryTint.Clear();
      for (float t = 0; t < dur && fi < fr.Length; t += dt) {
        ctx.t = t; ctxN.t = t + 0.8f;
        var a = Anchor(id, t);
        if (!started) { started = true; ctx.start = a; ctxN.start = Vector3.zero; ctxN.anchor = Vector3.zero; }
        ctx.anchor = def.Follow ? a : ctx.start;
        ctx.track.Add(t, a);
        batch.Clear();
        if (id == "lamp_flame") night.Emit(ctxN, batch);
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
      Console.WriteLine($"{id,-14} dur {dur} follow {def.Follow} frames {fi} maxSprites {maxSprites} maxRibbons {maxRibbons}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
    EstherFx.BeamTarget = EstherFx.DefaultBeamTarget;
  }
}
