// The King Who Serves rows of the off-Unity preview (run.sh lastsupper): runs the real StoryFxLastSupper code (the new ids
// come from LastSupperFx.Defs, because the manifest registration is merged by the lead; reused ids come from FxLibrary) at
// 60 fps. Stand-in sets (no Jerusalem stand-in in render.py): the Ruth yard ("ruth") for the road and the court (warm sand
// ground, slab actors at the CONTRACT heights), the Gabriel heaven ("gabriel", cream floor and walls) as the worst case
// for white doves on the cream court (F4), and the Ruth yard under the real `night` effect and tint for the lamp-lit room.
// Same frames.json format as the other packs.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class LastSupperPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  // actors: ruth set = x, z, height, colour; coast set = x, z, height, colour, y
  struct Row { public string name, scene; public float dur; public Vector3 anchor, look, camOff; public string under; public float[][] actors; public string[] colours; public float[] times; public bool night; }
  static readonly Row[] Rows = {
    new Row{name="palm_toss@road", scene="ruth", dur=8f, anchor=V(0.30f,0f,0.10f), look=V(0.30f,0.12f,0.05f), camOff=V(0.40f,0.22f,0.57f),
      actors=new[]{new[]{0.20f,0.10f,0.48f},new[]{0.33f,0.04f,0.38f},new[]{0.30f,-0.02f,0.26f},new[]{0.42f,-0.03f,0.26f},new[]{0.54f,-0.01f,0.25f},new[]{0.56f,0.18f,0.17f}},
      colours=new[]{"#EFE6D2","#B5523A","#7E6AA0","#6FA552","#D9A93A","#E8843A"}, times=new[]{0.6f,1.5f,3.0f,5.0f,7.7f}},
    new Row{name="palm_toss@phone", scene="ruth", dur=8f, anchor=V(0.30f,0f,0.10f), look=V(0.25f,0.08f,0.0f), camOff=V(0f,0.55f,1.35f),
      actors=new[]{new[]{0.20f,0.10f,0.48f},new[]{0.33f,0.04f,0.38f},new[]{0.30f,-0.02f,0.26f},new[]{0.42f,-0.03f,0.26f},new[]{0.54f,-0.01f,0.25f},new[]{0.56f,0.18f,0.17f}},
      colours=new[]{"#EFE6D2","#B5523A","#7E6AA0","#6FA552","#D9A93A","#E8843A"}, times=new[]{0.6f,1.5f,3.0f,5.0f,7.7f}},
    new Row{name="doves_fly@court", scene="ruth", dur=3f, anchor=V(0.0f,0.10f,-0.30f), look=V(-0.04f,0.20f,-0.32f), camOff=V(0.26f,0.10f,0.49f),
      actors=new[]{new[]{0.0f,-0.38f,0.33f},new[]{-0.12f,-0.30f,0.36f}}, colours=new[]{"#E8843A","#EFE6D2"}, times=new[]{0.2f,0.5f,1.0f,1.7f,2.5f}},
    new Row{name="doves_fly@cream", scene="gabriel", dur=3f, anchor=V(0.0f,0.13f,-0.20f), look=V(0.0f,0.26f,-0.25f), camOff=V(0.26f,0.10f,0.55f),
      actors=new float[0][], colours=new string[0], times=new[]{0.2f,0.5f,1.0f,1.7f,2.5f}},
    new Row{name="doves_fly@phone", scene="ruth", dur=3f, anchor=V(0.0f,0.10f,-0.30f), look=V(0.0f,0.20f,-0.20f), camOff=V(0f,0.30f,1.2f),
      actors=new[]{new[]{0.0f,-0.38f,0.33f},new[]{-0.12f,-0.30f,0.36f}}, colours=new[]{"#E8843A","#EFE6D2"}, times=new[]{0.3f,0.8f,1.4f,2.0f,2.6f}},
    new Row{name="water_pour@basin", scene="ruth", dur=1.8f, anchor=V(0.0f,0.0f,0.06f), look=V(0.0f,0.06f,0.04f), camOff=V(-0.22f,0.09f,0.36f),
      actors=new[]{new[]{0.0f,-0.02f,0.30f}}, colours=new[]{"#EFE6D2"}, under="night", night=true, times=new[]{0.05f,0.12f,0.6f,1.6f,1.75f}},
    new Row{name="water_pour@jug", scene="ruth", dur=1.4f, anchor=V(0.0f,0.07f,0.06f), look=V(0.0f,0.07f,0.04f), camOff=V(-0.25f,0.08f,0.40f),
      actors=new[]{new[]{-0.06f,0.03f,0.22f},new[]{0.08f,0.03f,0.30f}}, colours=new[]{"#B5523A","#D9A93A"}, under="night", night=true, times=new[]{0.1f,0.4f,0.9f,1.25f,1.36f}},
    new Row{name="water_pour@phone", scene="ruth", dur=1.8f, anchor=V(0.0f,0.0f,0.06f), look=V(0.0f,0.10f,0.0f), camOff=V(-0.30f,0.20f,0.90f),
      actors=new[]{new[]{0.0f,-0.02f,0.30f}}, colours=new[]{"#EFE6D2"}, under="night", night=true, times=new[]{0.3f,0.8f,1.2f,1.6f,1.75f}},
  };
  static FxDef Find(string id) {
    foreach (var d in LastSupperFx.Defs) if (d.Id == id) return d;
    var f = FxLibrary.Get(id); if (f == null) throw new Exception("missing " + id); return f;
  }
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"palm_toss","doves_fly","water_pour","golden_rays","sparkle","heart_glow","sunset_glow","night","dust_road","lamp_flame","coins_spray","music_notes"})
      Console.WriteLine($"id {id,-12} -> {(Array.Exists(LastSupperFx.Defs, d => d.Id == id) ? "new LastSupperFx" : FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0]; var def = Find(id);
      RuthFx.Actors.Clear();
      var anchor = row.anchor; var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      FxDef nightDef = row.night ? Find("night") : null; var nctx = new FxCtx { dur = 999f, seed = 700, camPos = camPos, camRight = right, camUp = up };
      float[] times = row.times;
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"{row.scene}\",\"wings\":0,\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"actors\":[");
      for (int i = 0; i < row.actors.Length; i++) { var a = row.actors[i]; sb.Append((i>0?",":"") + $"[{F(a[0])},{F(a[1])},{F(a[2])},\"{row.colours[i]}\"" + (row.scene == "coast" ? $",{F(a.Length > 3 ? a[3] : 0f)}" : "") + "]"); }
      sb.Append("],\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0;
      StoryTint.Clear(); StoryLight.Reset(); ctx.start = anchor; 
      for (float t = 0; t < dur + 1e-3f && fi < times.Length; t += dt) {
        ctx.t = t; ctx.anchor = anchor; ctx.track.Add(t, anchor);
        batch.Clear();
        if (nightDef != null) { nctx.t = t + 4f; nctx.anchor = nctx.start = Vector3.zero; nightDef.Emit(nctx, batch); }
        def.Emit(ctx, batch);
        StoryTint.Resolve(out Color tint, out Color rim, out float level);
        StoryLight.Resolve(out float dim, out float flash);
        maxSprites = Math.Max(maxSprites, batch.sprites.Count); maxRibbons = Math.Max(maxRibbons, batch.ribbons.Count);
        if (t + dt * 0.5f >= times[fi]) {
          FxMeshBuilder.Build(batch, ctx, mn, sz, v, uv, col, ta, tb);
          sb.Append(fi==0?"":","); sb.Append($"{{\"t\":{F(t)},\"tint\":[{F(tint.r)},{F(tint.g)},{F(tint.b)}],\"dim\":{F(dim)},\"flash\":{F(flash)},\"v\":[");
          for (int i=0;i<v.Count;i++) sb.Append((i>0?",":"")+$"{F(v[i].x)},{F(v[i].y)},{F(v[i].z)},{F(uv[i].x)},{F(uv[i].y)},{F(col[i].r)},{F(col[i].g)},{F(col[i].b)},{F(col[i].a)}");
          sb.Append("],\"a\":["+string.Join(",",ta)+"],\"b\":["+string.Join(",",tb)+"]}");
          fi++;
        }
      }
      sb.Append($"],\"maxSprites\":{maxSprites}}}");
      Console.WriteLine($"{row.name,-20} dur {dur} follow {def.Follow} frames {fi} maxSprites {maxSprites} maxRibbons {maxRibbons}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
  }
}
