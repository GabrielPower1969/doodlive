// Gabriel rows of the off-Unity preview (run.sh gabriel): runs the real StoryFxGabriel code (and the reused ids the
// story plays) at 60 fps over a stand-in heaven (docs/gabriel/CONTRACT.md §6: cloud floor, gate box at the back, two
// floating boxes) with the actor as a 0.62-high slab and a 1.0-wide wing slab at the story.py mark (0, 0.02). The
// anchor may move (the descent), the actor's lift is written per frame, and the StoryTint result is recorded so
// render.py can multiply the stand-in set by it. A row name may carry "@variant"; `under` ids play underneath.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class GabrielPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  const float MX = 0f, MZ = 0.02f;                       // SKY mark
  // root height during fly_down (4.5 s, eased, lands softly) and fly_up (crouch 0.5 s, then up to 1.2)
  static float Down(float t) { float k = Mathf.Clamp01(t / 4.5f); k = k * k * (3 - 2 * k); return 0.55f * (1 - k); }
  static float Up(float t) { float k = Mathf.Clamp01((t - 0.5f) / 2.6f); return 1.2f * k * k; }
  struct Row { public string name; public float dur; public Vector3 look, camOff; public string under;
               public Func<float, Vector3> anchor; public Func<float, float> lift; public float wings; public float start; }
  static readonly Row[] Rows = {
    new Row{name="heaven_rays",        dur=12f,  look=V(0,0.36f,-0.18f), camOff=V(-0.40f,0.20f,1.45f), anchor=t=>Vector3.zero, lift=t=>0.55f, wings=1f},
    new Row{name="heaven_rays@S03",    dur=12f,  look=V(0,0.30f,-0.05f), camOff=V(0.12f,0.02f,0.95f),  anchor=t=>Vector3.zero, lift=t=>0f, wings=0f, start=3f},
    new Row{name="cloud_drift",        dur=12f,  look=V(0,0.12f,-0.08f), camOff=V(0.20f,0.36f,1.05f),  anchor=t=>Vector3.zero, lift=t=>0f, wings=0f, start=3f},
    new Row{name="descend_light",      dur=6f,   look=V(0,0.55f,0f),     camOff=V(0.30f,0.02f,1.55f),  anchor=t=>V(MX,Down(t),MZ), lift=Down, wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="feather_fall",       dur=6f,   look=V(0,0.50f,0f),     camOff=V(0.30f,0.02f,1.45f),  anchor=t=>V(MX,Down(t+1f)+0.44f,MZ), lift=t=>Down(t+1f), wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="feather_fall@S05",   dur=5f,   look=V(0,0.36f,0.02f),  camOff=V(-0.36f,0.04f,1.35f), anchor=t=>V(MX,0.44f,MZ), lift=t=>0f, wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="feather_fall@stage", dur=6f,   look=V(0,0.36f,-0.05f), camOff=V(-0.25f,0.10f,1.20f), anchor=t=>Vector3.zero, lift=t=>Up(t+0.9f), wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="wing_gust",          dur=1.4f, look=V(0,0.20f,0.02f),  camOff=V(0.28f,0.50f,1.25f),  anchor=t=>V(MX,0.02f,MZ), lift=t=>0f, wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="trumpet_notes",      dur=4.5f, look=V(0.03f,0.62f,0.10f), camOff=V(-0.36f,-0.12f,0.92f), anchor=t=>V(0.03f,0.50f+0.008f*Mathf.Sin(t*5f),0.10f), lift=t=>0f, wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="trumpet_notes@S05",  dur=4.5f, look=V(0,0.48f,0.05f),  camOff=V(-0.50f,-0.10f,1.40f), anchor=t=>V(0.03f,0.50f+0.008f*Mathf.Sin(t*5f),0.10f), lift=t=>0f, wings=1f, under="heaven_rays,cloud_drift,golden_rays@root,feather_fall@chest"},
    new Row{name="bless_glow",         dur=5f,   look=V(0,0.40f,0.02f),  camOff=V(0.12f,0.02f,0.80f),  anchor=t=>V(MX,0.44f,MZ+0.01f), lift=t=>0f, wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="heart_glow",         dur=5f,   look=V(0,0.40f,0.02f),  camOff=V(0.12f,0.02f,0.80f),  anchor=t=>V(MX,0.44f,MZ+0.01f), lift=t=>0f, wings=1f, under="heaven_rays,cloud_drift"},
    new Row{name="sparkle",            dur=1.2f, look=V(0.06f,0.60f,0.02f), camOff=V(0.20f,-0.06f,0.80f), anchor=t=>V(0.10f,0.74f,MZ+0.02f), lift=t=>0f, wings=0f, under="heaven_rays,cloud_drift"},
  };
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"heaven_rays","cloud_drift","descend_light","feather_fall","wing_gust","trumpet_notes","bless_glow",
                             "sparkle","golden_rays","heart_glow"})
      Console.WriteLine($"id {id,-14} -> {(FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0];
      var def = FxLibrary.Get(id); if (def == null) throw new Exception("missing " + id);
      RuthFx.Actors.Clear();
      EstherFx.BeamTarget = EstherFx.DefaultBeamTarget;
      var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = row.start > 0 ? 999f : dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      // effects underneath: "id" plays on the stage and has been running 4 s; "id@root" / "id@chest" start with the row
      var under = new List<(FxDef d, FxCtx c, string at)>();
      if (!string.IsNullOrEmpty(row.under)) foreach (var u in row.under.Split(',')) {
        var parts = u.Split('@'); var ud = FxLibrary.Get(parts[0]); if (ud == null) throw new Exception("missing " + parts[0]);
        under.Add((ud, new FxCtx { dur = parts.Length > 1 ? 5f : 999f, seed = 700 + under.Count, camPos = camPos, camRight = right, camUp = up }, parts.Length > 1 ? parts[1] : "stage"));
      }
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      float[] fr = {0.08f,0.25f,0.45f,0.65f,0.85f};
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"gabriel\",\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],");
      sb.Append($"\"actors\":[{$"[{F(MX)},{F(MZ)},0.62,\"#F1E7D2\"]"}],\"wings\":{F(row.wings)},\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0;
      StoryTint.Clear();
      ctx.start = row.anchor(0);
      for (float t = 0; t < dur && fi < fr.Length; t += dt) {
        ctx.t = t + row.start;
        var a = row.anchor(t);
        ctx.anchor = def.Follow ? a : ctx.start; ctx.track.Add(ctx.t, a);
        batch.Clear();
        foreach (var u in under) {
          Vector3 ua = u.at == "root" ? V(MX, row.lift(t), MZ) : u.at == "chest" ? V(MX, row.lift(t) + 0.44f, MZ) : Vector3.zero;
          u.c.t = u.at == "stage" ? t + 4f : t;
          if (u.c.track.Count == 0) u.c.start = ua;
          u.c.anchor = u.d.Follow ? ua : u.c.start; u.c.track.Add(u.c.t, ua);
          if (u.c.t < u.c.dur) u.d.Emit(u.c, batch);
        }
        def.Emit(ctx, batch);
        StoryTint.Resolve(out Color tint, out Color rim, out float level);
        maxSprites = Math.Max(maxSprites, batch.sprites.Count); maxRibbons = Math.Max(maxRibbons, batch.ribbons.Count);
        if (t + 1e-4f >= fr[fi] * dur) {
          FxMeshBuilder.Build(batch, ctx, mn, sz, v, uv, col, ta, tb);
          sb.Append(fi==0?"":","); sb.Append($"{{\"t\":{F(t)},\"lift\":{F(row.lift(t))},\"tint\":[{F(tint.r)},{F(tint.g)},{F(tint.b)}],\"v\":[");
          for (int i=0;i<v.Count;i++) sb.Append((i>0?",":"")+$"{F(v[i].x)},{F(v[i].y)},{F(v[i].z)},{F(uv[i].x)},{F(uv[i].y)},{F(col[i].r)},{F(col[i].g)},{F(col[i].b)},{F(col[i].a)}");
          sb.Append("],\"a\":["+string.Join(",",ta)+"],\"b\":["+string.Join(",",tb)+"]}");
          fi++;
        }
      }
      sb.Append($"],\"maxSprites\":{maxSprites}}}");
      Console.WriteLine($"{row.name,-20} dur {dur} follow {def.Follow} shake {def.ShakeAmp} flash {def.Flash} frames {fi} maxSprites {maxSprites} maxRibbons {maxRibbons}{(under.Count > 0 ? " (incl. " + row.under + ")" : "")}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
  }
}
