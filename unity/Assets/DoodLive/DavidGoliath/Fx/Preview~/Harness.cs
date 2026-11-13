using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class Harness {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  static bool esther;
  static Vector3 Anchor(string id, float t) {
    switch (id) {
      case "dust_puff": return new Vector3(0.17f, 0.01f, -0.25f);
      case "memory_lion_bear": return new Vector3(-0.3f, 0.25f, 0.1f);
      case "brook_ripple": return new Vector3(-0.35f, 0.03f, 0.25f);
      case "faith_glow": return new Vector3(-0.1f, 0.17f, 0.05f);
      case "sling_trail": { float a = t * 6.2831853f * 2f; return new Vector3(-0.05f + 0.07f*Mathf.Cos(a), 0.34f + 0.025f*Mathf.Sin(a), 0.1f + 0.07f*Mathf.Sin(a)); }
      case "stone_trail": { float k = Mathf.Clamp01(t / 0.45f); var a = new Vector3(-0.02f,0.3f,0.1f); var b = new Vector3(0.12f,0.74f,-0.25f); var p = Vector3.Lerp(a,b,k); p.y += 0.12f*Mathf.Sin(k*3.14159f); return p; }
      case "hit_flash": return new Vector3(0.12f, 0.74f - 0.05f*Mathf.Clamp01(t*3), -0.25f);
      case "dizzy_stars": return new Vector3(0.12f, 0.72f - 0.1f*t, -0.25f + 0.1f*t);
      case "dust_burst": return new Vector3(0.1f, 0.08f, 0.1f);
      case "confetti": return new Vector3(-0.1f, 0.27f, 0.25f);
      case "golden_rays": return esther ? new Vector3(0f, 0f, -0.05f) : new Vector3(-0.1f, 0f, 0.25f);
      // Esther (stage marks from docs/esther/CONTRACT.md §6)
      case "brazier_fire": return new Vector3(-0.18f, 0.12f, -0.14f);
      case "crown_sparkle": return new Vector3(0f, 0.43f, -0.30f);
      case "ring_glint": return new Vector3(0.06f, 0.22f, -0.26f);
      case "prayer_glow": return new Vector3(0f, 0.13f, -0.05f);
      case "sceptre_beam": return new Vector3(0.05f, 0.30f, -0.27f);
      case "tension_dim": return Vector3.zero;
      case "truth_flash": return new Vector3(0.05f, 0.24f, 0.0f);
      case "petals": return new Vector3(0.22f, 0f, 0.08f);
    }
    return Vector3.zero;
  }
  static void Main(string[] args) {
    string outDir = args[0]; Directory.CreateDirectory(outDir);
    // atlas
    var px = DGFxPaint.Build(); var bytes = new byte[px.Length];
    for (int i = 0; i < px.Length; i++) bytes[i] = (byte)Math.Max(0, Math.Min(255, (int)(px[i]*255f+0.5f)));
    File.WriteAllBytes(Path.Combine(outDir, "atlas.rgba"), bytes);
    int n = DGFxPaint.CellCount, S = DGFxPaint.Size; var mn = new Vector2[n]; var sz = new Vector2[n];
    for (int i = 0; i < n; i++) { var c = DGFxPaint.Cells[i]; mn[i] = new Vector2(c[0]/(float)S, c[1]/(float)S); sz[i] = new Vector2(c[2]/(float)S, c[3]/(float)S); }
    var sb = new StringBuilder(); sb.Append("{");
    bool firstFx = true;
    esther = args.Length > 1 && args[1] == "esther";
    var timeline = esther ? new Dictionary<string,float>{{"brazier_fire",3f},{"crown_sparkle",1.6f},{"ring_glint",0.8f},{"prayer_glow",6f},{"sceptre_beam",4f},{"tension_dim",3f},{"truth_flash",0.6f},{"confetti",3f},{"golden_rays",4f},{"petals",5f}}
                          : new Dictionary<string,float>{{"dust_puff",0.6f},{"memory_lion_bear",3.8f},{"brook_ripple",2.4f},{"faith_glow",5.6f},{"sling_trail",2.4f},{"stone_trail",0.5f},{"hit_flash",0.4f},{"dizzy_stars",1.0f},{"dust_burst",1.6f},{"confetti",3.0f},{"golden_rays",4.0f}};
    foreach (var kv in timeline) {
      var def = FxLibrary.Get(kv.Key); if (def == null) throw new Exception("missing " + kv.Key);
      var ctx = new FxCtx { dur = kv.Value, seed = 12345 };
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      float[] fr = {0.08f,0.25f,0.45f,0.65f,0.85f};
      // camera: viewer side, looking at the start anchor
      var look = Anchor(kv.Key, 0); if (kv.Key=="golden_rays") look += Vector3.up*0.35f; if (kv.Key=="dust_burst"||kv.Key=="confetti") look += Vector3.up*0.1f;
      if (kv.Key=="sceptre_beam") look = (look + EstherFx.BeamTarget) * 0.5f; if (kv.Key=="petals") look += Vector3.up*0.15f;
      var camPos = look + new Vector3(0.25f, 0.35f, 1.1f);
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      ctx.camPos = camPos; ctx.camRight = right; ctx.camUp = up;
      sb.Append(firstFx ? "" : ","); firstFx = false;
      sb.Append($"\"{kv.Key}\":{{\"dur\":{F(kv.Value)},\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"frames\":[");
      // simulate at 60 fps like the device, snapshot the requested frames
      float dt = 1f/60f; int fi = 0; bool started = false; int maxSprites = 0;
      for (float t = 0; t < kv.Value && fi < fr.Length; t += dt) {
        ctx.t = t;
        var a = Anchor(kv.Key, t);
        if (!started) { started = true; ctx.start = a; }
        if (def.Follow) ctx.anchor = a; else ctx.anchor = ctx.start;
        ctx.track.Add(t, a);
        batch.Clear(); def.Emit(ctx, batch);
        maxSprites = Math.Max(maxSprites, batch.sprites.Count);
        if (t + 1e-4f >= fr[fi] * kv.Value) {
          FxMeshBuilder.Build(batch, ctx, mn, sz, v, uv, col, ta, tb);
          sb.Append(fi==0?"":","); sb.Append($"{{\"t\":{F(t)},\"v\":[");
          for (int i=0;i<v.Count;i++) sb.Append((i>0?",":"")+$"{F(v[i].x)},{F(v[i].y)},{F(v[i].z)},{F(uv[i].x)},{F(uv[i].y)},{F(col[i].r)},{F(col[i].g)},{F(col[i].b)},{F(col[i].a)}");
          sb.Append("],\"a\":["+string.Join(",",ta)+"],\"b\":["+string.Join(",",tb)+"]}");
          fi++;
        }
      }
      sb.Append($"],\"maxSprites\":{maxSprites}}}");
      Console.WriteLine($"{kv.Key,-18} dur {kv.Value} follow {def.Follow} shake {def.ShakeAmp} flash {def.Flash} frames {fi} maxSprites {maxSprites}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
  }
}
