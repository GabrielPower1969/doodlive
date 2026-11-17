// Miracles rows of the off-Unity preview (run.sh miracles): runs the real StoryFxMiracles code (the new ids come from
// MiraclesFx.Defs, because the manifest registration is merged by the lead; reused ids come from FxLibrary) at 60 fps.
// Stand-in sets reuse the Ruth house yard ("ruth") for the roof dirt and the Jonah coast ("coast", sea plane y 0.012) for
// the lake; the night row applies the real `night` effect and its tint under calm_wave. Same frames.json format as the other packs.
// Not covered: calm_wave ending storm_rain / tension_dim (that is StoryFxMiraclesRuntime.cs, which needs the engine).
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class MiraclesPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  // actors: ruth set = x, z, height, colour; coast set = x, z, height, colour, y
  struct Row { public string name, scene; public float dur; public Vector3 anchor, look, camOff; public string under; public float[][] actors; public string[] colours; public float[] times; public bool night; }
  static readonly Row[] Rows = {
    new Row{name="dig_dirt@roof", scene="ruth", dur=5f, anchor=V(0f,0.22f,-0.10f), look=V(0f,0.24f,-0.10f), camOff=V(0.05f,0.04f,0.55f), actors=new float[0][], colours=new string[0], times=new[]{0.5f,1.1f,2.0f,3.1f,4.4f}},
    new Row{name="dust_puff@roof", scene="ruth", dur=5f, anchor=V(0f,0.22f,-0.10f), look=V(0f,0.12f,-0.10f), camOff=V(0.05f,0.05f,0.75f), actors=new[]{new[]{0f,-0.10f,0.09f}}, colours=new[]{"#6C8FD0"}, times=new[]{0.4f,1.0f,2.0f,3.2f,4.4f}},
    new Row{name="dust_fall@roof",  scene="ruth", dur=3f, anchor=V(0f,0.22f,-0.10f), look=V(0f,0.12f,-0.10f), camOff=V(0.05f,0.05f,0.75f), actors=new[]{new[]{0f,-0.10f,0.09f}}, colours=new[]{"#6C8FD0"}, times=new[]{0.15f,0.6f,1.2f,2.0f,2.8f}},
    new Row{name="dust_fall@phone", scene="ruth", dur=3f, anchor=V(0f,0.22f,-0.10f), look=V(0f,0.15f,-0.10f), camOff=V(0f,0f,1.5f), actors=new[]{new[]{0f,-0.10f,0.09f}}, colours=new[]{"#6C8FD0"}, times=new[]{0.3f,1.0f,1.8f,2.4f,2.8f}},
    new Row{name="calm_wave@night", scene="coast", dur=3f, anchor=V(-0.28f,0.012f,-0.05f), look=V(-0.25f,0.03f,-0.05f), camOff=V(0.10f,0.30f,0.90f), actors=new[]{new[]{0.25f,0.0f,0.28f,0f}}, colours=new[]{"#E8A04A"}, under="night", night=true, times=new[]{0.2f,0.7f,1.3f,2.0f,2.8f}},
    new Row{name="calm_wave@day",   scene="coast", dur=3f, anchor=V(-0.28f,0.012f,-0.05f), look=V(-0.25f,0.03f,-0.05f), camOff=V(0.10f,0.30f,0.90f), actors=new[]{new[]{0.25f,0.0f,0.28f,0f}}, colours=new[]{"#E8A04A"}, times=new[]{0.2f,0.7f,1.3f,2.0f,2.8f}},
    new Row{name="calm_wave@phone", scene="coast", dur=3f, anchor=V(-0.28f,0.012f,-0.05f), look=V(-0.10f,0.10f,-0.05f), camOff=V(0f,0.05f,1.8f), actors=new[]{new[]{0.25f,0.0f,0.28f,0f}}, colours=new[]{"#E8A04A"}, under="night", night=true, times=new[]{0.4f,1.0f,1.6f,2.2f,2.8f}},
  };
  static FxDef Find(string id) {
    foreach (var d in MiraclesFx.Defs) if (d.Id == id) return d;
    var f = FxLibrary.Get(id); if (f == null) throw new Exception("missing " + id); return f;
  }
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"dig_dirt","dust_fall","calm_wave","dust_puff","golden_rays","heart_glow","sparkle","sunset_glow","zzz","storm_rain","tension_dim","night","splash"})
      Console.WriteLine($"id {id,-12} -> {(Array.Exists(MiraclesFx.Defs, d => d.Id == id) ? "new MiraclesFx" : FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
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
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"{row.scene}\",\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"actors\":[");
      for (int i = 0; i < row.actors.Length; i++) { var a = row.actors[i]; sb.Append((i>0?",":"") + $"[{F(a[0])},{F(a[1])},{F(a[2])},\"{row.colours[i]}\"" + (row.scene == "coast" ? $",{F(a.Length > 3 ? a[3] : 0f)}" : "") + "]"); }
      sb.Append("],\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0;
      StoryTint.Clear(); StoryLight.Reset(); ctx.start = anchor; MiraclesFx.EndRequests.Clear();
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
    Console.WriteLine("calm_wave end requests posted: " + string.Join(",", MiraclesFx.EndRequests));
  }
}
