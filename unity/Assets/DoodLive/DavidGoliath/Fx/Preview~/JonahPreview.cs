// Jonah rows of the off-Unity preview (run.sh jonah): runs the real StoryFxJonah code (new ids taken from JonahFx.Defs,
// because the manifest registration is merged by the lead; the alias plant_grow and the reused ids come from
// FxLibrary) at 60 fps over a stand-in coast (docs/jonah/CONTRACT.md §6) with stand-in actors. Records the StoryTint
// result, the cold flash and the dim per frame, so render.py can apply them to the set. A row name may carry
// "@variant"; `under` ids play underneath ("id" on the stage, running 4 s already; "id@head" / "id@chest" on the actor).
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class JonahPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  // actors: x, z, height, colour, foot height y
  static readonly string J = "#E8A04A";
  struct Row { public string name; public float dur; public Vector3 look, camOff; public string under, set; public float[] times;
               public Func<float, Vector3> anchor; public float[] actor; }
  static readonly Row[] Rows = {
    new Row{name="storm_rain",        dur=34f, look=V(0,0.20f,-0.12f), camOff=V(0.25f,0.34f,1.20f), anchor=t=>Vector3.zero, under="tension_dim", set="coast", actor=new[]{-0.30f,-0.22f,0.30f,0.10f}},
    new Row{name="storm_rain@close",  dur=34f, look=V(-0.28f,0.16f,-0.20f), camOff=V(0.10f,0.12f,0.62f), anchor=t=>Vector3.zero, under="tension_dim", set="coast", actor=new[]{-0.30f,-0.22f,0.30f,0.10f}, times=new[]{3f,9f,17f,26f,31f}},
    new Row{name="bubbles@S05",       dur=6f,  look=V(-0.12f,0.16f,0.02f), camOff=V(0.22f,0.14f,0.72f), anchor=t=>V(-0.14f+0.012f*t,0.09f,0.02f), set="coast", actor=new[]{-0.30f,-0.22f,0.30f,0.10f}},
    new Row{name="bubbles@belly",     dur=2f,  look=V(-0.17f,0.16f,0.02f), camOff=V(0.20f,0.12f,0.62f), anchor=t=>V(-0.14f,0.09f,0.04f), under="deep_glow", set="belly", actor=new[]{-0.20f,0.08f,0.30f,0f}, times=new[]{0.3f,0.7f,1.1f,1.5f,1.9f}},
    new Row{name="deep_glow",         dur=34f, look=V(-0.15f,0.20f,-0.10f), camOff=V(0.20f,0.30f,1.05f), anchor=t=>Vector3.zero, under="prayer_glow@chest", set="belly", actor=new[]{-0.20f,0.08f,0.30f,0f}, times=new[]{0.8f,4f,12f,24f,33f}},
    new Row{name="sun_scorch",        dur=8f,  look=V(0.44f,0.20f,0.06f), camOff=V(0.12f,0.12f,0.88f), anchor=t=>V(0.44f,0.25f,0.06f), set="coast", actor=new[]{0.44f,0.06f,0.26f,0.04f}},
    new Row{name="sun_scorch@close",  dur=8f,  look=V(0.44f,0.30f,0.06f), camOff=V(-0.05f,0.02f,0.50f), anchor=t=>V(0.44f,0.25f,0.06f), under="sweat@head", set="coast", actor=new[]{0.44f,0.06f,0.26f,0.04f}, times=new[]{0.5f,2.6f,3.0f,5.5f,7.2f}},
    new Row{name="plant_grow",         dur=1.6f, look=V(0.34f,0.24f,0.06f), camOff=V(0.10f,0.06f,0.70f), anchor=t=>V(0.34f,0.20f,0.06f), set="coast", actor=new[]{0.12f,0.10f,0.30f,0f}},
  };
  static FxDef Find(string id) {
    foreach (var d in JonahFx.Defs) if (d.Id == id) return d;
    if (id == "plant_grow") return new StoryFxAlias("plant_grow", "sparkle");
    var f = FxLibrary.Get(id); if (f == null) throw new Exception("missing " + id); return f;
  }
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"storm_rain","bubbles","deep_glow","sun_scorch","plant_grow","steam","sweat","splash","sea_wind","zzz","golden_rays","tension_dim","prayer_glow","heart_glow"}) {
      string how = Array.Exists(JonahFx.Defs, d => d.Id == id) ? "new JonahFx" : id == "plant_grow" ? "alias -> sparkle" : (FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name);
      Console.WriteLine($"id {id,-12} -> {how}");
    }
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0]; var def = Find(id);
      RuthFx.Actors.Clear();
      var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      var under = new List<(FxDef d, FxCtx c, string at)>();
      if (!string.IsNullOrEmpty(row.under)) foreach (var u in row.under.Split(',')) {
        var parts = u.Split('@'); under.Add((Find(parts[0]), new FxCtx { dur = parts.Length > 1 ? 5f : 999f, seed = 700 + under.Count, camPos = camPos, camRight = right, camUp = up }, parts.Length > 1 ? parts[1] : "stage"));
      }
      var ft = new float[3]; int nf = id == "storm_rain" ? StormRain.Flashes(ctx, ft) : 0;
      float[] times = row.times ?? (id == "storm_rain" ? new[]{3f, ft[0]+0.14f, 13f, ft[1]+0.14f, 30.5f} : new[]{0.08f*dur,0.25f*dur,0.45f*dur,0.65f*dur,0.85f*dur});
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      sb.Append(first ? "" : ","); first = false;
      var a0 = row.actor;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"{row.set}\",\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],");
      sb.Append($"\"actors\":[[{F(a0[0])},{F(a0[1])},{F(a0[2])},\"{J}\",{F(a0[3])}]],\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0;
      StoryTint.Clear(); StoryLight.Reset();
      ctx.start = row.anchor(0);
      for (float t = 0; t < dur + 1e-3f && fi < times.Length; t += dt) {
        ctx.t = t; var a = row.anchor(t);
        ctx.anchor = def.Follow ? a : ctx.start; ctx.track.Add(t, a);
        batch.Clear();
        foreach (var u in under) {
          Vector3 ua = u.at == "head" ? V(a0[0], a0[3] + a0[2], a0[1]) : u.at == "chest" ? V(a0[0], a0[3] + 0.6f * a0[2], a0[1] + 0.02f) : Vector3.zero;
          u.c.t = u.at == "stage" ? t + (u.d.Id == "tension_dim" ? 0f : 4f) : t;
          if (u.c.track.Count == 0) u.c.start = ua;
          u.c.anchor = u.d.Follow ? ua : u.c.start; u.c.track.Add(u.c.t, ua);
          if (u.c.t < u.c.dur) u.d.Emit(u.c, batch);
        }
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
      Console.WriteLine($"{row.name,-18} dur {dur} follow {def.Follow} frames {fi} maxSprites {maxSprites} maxRibbons {maxRibbons}{(nf > 0 ? " flashes at " + F(ft[0]) + (nf > 1 ? ", " + F(ft[1]) : "") + (nf > 2 ? ", " + F(ft[2]) : "") : "")}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
  }
}
