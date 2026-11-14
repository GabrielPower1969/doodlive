// Exodus rows of the off-Unity preview (run.sh exodus): runs the real StoryFxExodus code (and the reused ids played
// under it) at 60 fps against stand-in actors at the docs/exodus/storyboard/story.py marks, records the StoryTint result
// and the sea state (ExodusSea.Open -> wall scale, lane shown / hidden) per frame, so render.py can draw a stand-in
// Egypt with the walls at the height the runtime would give them. Sea rows also emit `sea_hold` (what ExodusStage
// spawns on device). A row name may carry "@variant". Rows marked night / dusk get `night` / `sunset_glow` underneath.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class ExodusPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  struct Act { public string id; public float x, z, h; public string col; }
  static Act Mo(float x, float z) => new Act{id="moses",x=x,z=z,h=0.37f,col="#C98B3A"};
  static Act Ph(float x, float z, float h = 0.39f) => new Act{id="pharaoh",x=x,z=z,h=h,col="#2F5DA8"};
  static Act Mi(float x, float z) => new Act{id="miriam",x=x,z=z,h=0.34f,col="#F2B33D"};
  static readonly Dictionary<string, Act[]> Cast = new Dictionary<string, Act[]> {
    {"bush",   new[]{ Mo(0.07f,-0.30f) }},
    {"snake",  new[]{ Mo(0.04f,-0.30f) }},
    {"plague", new[]{ Ph(-0.36f,-0.30f), Mo(-0.18f,-0.22f) }},
    {"head",   new[]{ Ph(-0.18f,-0.24f), Mo(-0.02f,-0.20f) }},
    {"night",  new[]{ Mi(-0.20f,-0.30f), Mo(0.14f,-0.28f) }},
    {"exodus", new[]{ Mo(0.12f,0.08f), Mi(0.02f,0.13f) }},
    {"sea",    new[]{ Mo(0.12f,0.08f), Mi(0.02f,0.13f) }},
    {"splash", new[]{ Ph(0.24f,0.07f), Mo(0.46f,0.04f) }},
    {"soggy",  new[]{ Ph(0.12f,0.03f,0.22f) }},
  };
  struct Row { public string name; public float dur; public string cast; public Vector3 anchor, look, camOff; public string under; public int sea; }
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  // sea: 0 none, 1 start at rest (sea_part), 2 start parted (sea_close / standing)
  static readonly Row[] Rows = {
    new Row{name="bush_fire",        dur=8f,   cast="bush",   anchor=V(0.14f,0.12f,-0.36f), look=V(0.11f,0.14f,-0.32f), camOff=V(0.30f,0.12f,0.50f), under="sunset_glow"},
    new Row{name="snake",            dur=5.6f, cast="snake",  anchor=V(0.07f,0.20f,-0.27f), look=V(0.08f,0.10f,-0.22f), camOff=V(-0.18f,0.16f,0.50f)},
    new Row{name="river_red",        dur=5f,   cast="plague", anchor=Vector3.zero,         look=V(-0.45f,0.06f,-0.05f), camOff=V(0.20f,0.30f,0.55f)},
    new Row{name="frogs",            dur=16f,  cast="plague", anchor=Vector3.zero,         look=V(-0.22f,0.08f,-0.08f), camOff=V(0.05f,0.30f,0.70f)},
    new Row{name="frog_on_head",     dur=7f,   cast="head",   anchor=V(-0.18f,0.33f,-0.24f), look=V(-0.17f,0.28f,-0.22f), camOff=V(-0.18f,0.08f,0.50f)},
    new Row{name="flies",            dur=3f,   cast="plague", anchor=V(-0.36f,0f,-0.48f),   look=V(-0.34f,0.16f,-0.32f), camOff=V(-0.15f,0.08f,0.50f)},
    new Row{name="hail",             dur=3f,   cast="plague", anchor=Vector3.zero,         look=V(-0.15f,0.10f,-0.15f), camOff=V(-0.10f,0.30f,0.80f)},
    new Row{name="door_glow",        dur=8f,   cast="night",  anchor=V(-0.02f,0.09f,-0.41f), look=V(-0.02f,0.12f,-0.36f), camOff=V(0.10f,0.14f,0.62f), under="night"},
    new Row{name="pillar_cloud",     dur=8f,   cast="exodus", anchor=V(0.16f,0f,-0.12f),   look=V(0.10f,0.20f,-0.05f), camOff=V(-0.15f,0.18f,0.80f)},
    new Row{name="pillar_fire",      dur=8f,   cast="exodus", anchor=V(0.16f,0f,-0.12f),   look=V(0.10f,0.20f,-0.05f), camOff=V(-0.15f,0.18f,0.80f), under="night"},
    new Row{name="sea_wind",         dur=9f,   cast="sea",    anchor=V(0.30f,0f,-0.02f),   look=V(0.25f,0.10f,-0.02f), camOff=V(-0.25f,0.26f,0.62f)},
    new Row{name="sea_part",         dur=4.5f, cast="sea",    anchor=V(0.30f,0f,-0.02f),   look=V(0.28f,0.10f,0.0f),   camOff=V(-0.25f,0.26f,0.62f), sea=1},
    new Row{name="sea_part@front",   dur=4.5f, cast="sea",    anchor=V(0.30f,0f,-0.02f),   look=V(0.30f,0.10f,0.07f),  camOff=V(-0.02f,0.20f,0.62f), sea=1},
    new Row{name="sea_hold",         dur=6f,   cast="splash", anchor=V(0.30f,0f,-0.02f),   look=V(0.30f,0.10f,0.06f),  camOff=V(-0.30f,0.14f,0.48f), sea=2},
    new Row{name="sea_close",        dur=3f,   cast="splash", anchor=V(0.30f,0f,-0.02f),   look=V(0.28f,0.10f,0.04f),  camOff=V(-0.30f,0.16f,0.55f), sea=2},
    new Row{name="splash",           dur=2f,   cast="splash", anchor=V(0.24f,0f,0.07f),    look=V(0.24f,0.08f,0.07f),  camOff=V(-0.20f,0.12f,0.45f)},
    new Row{name="drips",            dur=8f,   cast="soggy",  anchor=V(0.12f,0.19f,0.03f), look=V(0.12f,0.12f,0.03f),  camOff=V(-0.12f,0.06f,0.42f)},
  };
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"bush_fire","snake","river_red","frogs","frog_on_head","flies","hail","door_glow","pillar_cloud","pillar_fire",
                             "sea_wind","sea_part","sea_close","sea_hold","splash","drips",
                             "dust_road","sunset_glow","night","prayer_glow","sparkle","confetti","golden_rays"})
      Console.WriteLine($"id {id,-13} -> {(FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
    var hold = FxLibrary.Get("sea_hold");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0];
      var def = FxLibrary.Get(id); if (def == null) throw new Exception("missing " + id);
      var cast = Cast[row.cast];
      ExodusFx.Actors.Clear(); RuthFx.Actors.Clear();
      foreach (var a in cast) { ExodusFx.Actors.Add(new ExodusActor { feet = new Vector3(a.x, 0, a.z), height = a.h });
                                RuthFx.Actors.Add(new RuthActor { feet = new Vector3(a.x, 0, a.z), height = a.h }); }
      ExodusSea.SetState(row.sea == 2);
      var under = row.under != null ? FxLibrary.Get(row.under) : null;
      var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      var ctxU = new FxCtx { dur = dur + 1.6f, seed = 777, camPos = camPos, camRight = right, camUp = up };
      var ctxH = new FxCtx { dur = 1e6f, seed = 4242, camPos = camPos, camRight = right, camUp = up };
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      float[] fr = {0.08f,0.25f,0.45f,0.65f,0.85f};
      if (row.name == "sea_close") fr = new[]{0.05f,0.14f,0.24f,0.45f,0.80f};
      if (row.name == "snake") fr = new[]{0.04f,0.16f,0.45f,0.86f,0.95f};
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"exodus\",\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"actors\":[");
      for (int i = 0; i < cast.Length; i++) sb.Append((i>0?",":"") + $"[{F(cast[i].x)},{F(cast[i].z)},{F(cast[i].h)},\"{cast[i].col}\"]");
      sb.Append("],\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0; float holdT = row.sea == 2 ? 2f : 0f;
      StoryTint.Clear();
      ctx.start = row.anchor; ctxU.start = Vector3.zero; ctxU.anchor = Vector3.zero; ctxH.start = ctxH.anchor = row.anchor;
      for (float t = 0; t < dur && fi < fr.Length; t += dt) {
        ctx.t = t; ctxU.t = t + 0.8f; ExodusSea.Clock = t;
        ctx.anchor = row.anchor; ctx.track.Add(t, row.anchor);
        batch.Clear();
        if (under != null) under.Emit(ctxU, batch);
        def.Emit(ctx, batch);
        if (row.sea > 0 && id != "sea_hold") { if (ExodusSea.Open > 0.001f) { ctxH.t = holdT; holdT += dt; hold.Emit(ctxH, batch); } else holdT = 0; }
        StoryTint.Resolve(out Color tint, out Color rim, out float level);
        maxSprites = Math.Max(maxSprites, batch.sprites.Count); maxRibbons = Math.Max(maxRibbons, batch.ribbons.Count);
        if (t + 1e-4f >= fr[fi] * dur) {
          float open = ExodusSea.Open;
          FxMeshBuilder.Build(batch, ctx, mn, sz, v, uv, col, ta, tb);
          sb.Append(fi==0?"":","); sb.Append($"{{\"t\":{F(t)},\"tint\":[{F(tint.r)},{F(tint.g)},{F(tint.b)}],\"wall\":{F(open > 0.003f ? ExodusSea.ScaleY(open, t) : 0f)},\"lane\":{(ExodusSea.LaneHidden(open) ? "false" : "true")},\"v\":[");
          for (int i=0;i<v.Count;i++) sb.Append((i>0?",":"")+$"{F(v[i].x)},{F(v[i].y)},{F(v[i].z)},{F(uv[i].x)},{F(uv[i].y)},{F(col[i].r)},{F(col[i].g)},{F(col[i].b)},{F(col[i].a)}");
          sb.Append("],\"a\":["+string.Join(",",ta)+"],\"b\":["+string.Join(",",tb)+"]}");
          fi++;
        }
      }
      sb.Append($"],\"maxSprites\":{maxSprites}}}");
      Console.WriteLine($"{row.name,-16} dur {dur} follow {def.Follow} shake {def.ShakeAmp} frames {fi} maxSprites {maxSprites} maxRibbons {maxRibbons} openEnd {ExodusSea.Open:0.###}{(row.under != null ? " (with " + row.under + ")" : "")}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
    ExodusSea.SetState(false); ExodusFx.Actors.Clear(); RuthFx.Actors.Clear();
  }
}
