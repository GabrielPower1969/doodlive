// Joseph rows of the off-Unity preview (run.sh joseph): runs the real StoryFxJoseph code (the new id comes from
// JosephFx.Defs, because the manifest registration is merged by the lead; reused ids come from FxLibrary) at 60 fps over
// a stand-in twolands (docs/joseph/CONTRACT.md §6): pasture and sand, tent, palace, a flat dream panel that faces +Z and
// tilts 15 degrees toward the camera, stand-in actors. Same frames.json format as the other packs.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class JosephPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  // panel: centre x, y, z, width, height (flat, facing +Z). actors: x, z, height, colour
  struct Row { public string name; public float dur; public Vector3 look, camOff; public string under; public float[] panel; public float[][] actors; public float[] times; public bool night; }
  static readonly Row[] Rows = {
    new Row{name="dream_cloud@sheaves",   dur=9f, look=V(-0.30f,0.40f,-0.16f), camOff=V(0.05f,0.04f,0.95f), panel=new[]{-0.32f,0.46f,-0.16f,0.22f,0.16f}, actors=new[]{new[]{-0.32f,-0.16f,0.30f}, }},
    new Row{name="dream_cloud@cows",      dur=9f, look=V(0.30f,0.42f,-0.26f), camOff=V(-0.15f,0.05f,0.95f), panel=new[]{0.30f,0.52f,-0.26f,0.24f,0.17f}, actors=new[]{new[]{0.38f,-0.30f,0.34f}}, under="night", night=true},
    new Row{name="dream_cloud@wide",      dur=6f, look=V(0.0f,0.30f,-0.15f), camOff=V(0.20f,0.28f,1.35f), panel=new[]{0.30f,0.50f,0.06f,0.22f,0.16f}, actors=new[]{new[]{0.30f,0.06f,0.30f}, new[]{-0.32f,-0.16f,0.30f}}, times=new[]{0.3f,0.8f,3f,5.4f,5.8f}},
    new Row{name="dream_cloud@phone",     dur=6f, look=V(0.30f,0.50f,0.0f), camOff=V(0.0f,0.0f,1.9f), panel=new[]{0.30f,0.50f,0.06f,0.22f,0.16f}, actors=new[]{new[]{0.30f,0.06f,0.30f}}},
  };
  static FxDef Find(string id) {
    foreach (var d in JosephFx.Defs) if (d.Id == id) return d;
    var f = FxLibrary.Get(id); if (f == null) throw new Exception("missing " + id); return f;
  }
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"dream_cloud","sparkle","steam","tension_dim","coins_spray","prayer_glow","night","zzz","golden_rays","famine_haze","sweat","heart_glow","confetti"})
      Console.WriteLine($"id {id,-12} -> {(Array.Exists(JosephFx.Defs, d => d.Id == id) ? "new JosephFx" : FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0]; var def = Find(id);
      RuthFx.Actors.Clear();
      var p = row.panel; var anchor = V(p[0], p[1], p[2]);
      var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      FxDef nightDef = row.night ? Find("night") : null; var nctx = new FxCtx { dur = 999f, seed = 700, camPos = camPos, camRight = right, camUp = up };
      float[] times = row.times ?? new[]{0.08f*dur,0.25f*dur,0.45f*dur,0.65f*dur,0.85f*dur};
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"twolands\",\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],");
      sb.Append("\"panel\":[" + string.Join(",", Array.ConvertAll(p, F)) + "],\"actors\":[");
      for (int i = 0; i < row.actors.Length; i++) { var a = row.actors[i]; sb.Append((i>0?",":"") + $"[{F(a[0])},{F(a[1])},{F(a[2])},\"{(i==0?"#E8A04A":"#6C8FD0")}\"]"); }
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
