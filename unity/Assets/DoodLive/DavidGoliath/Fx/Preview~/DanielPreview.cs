// Daniel rows of the off-Unity preview (run.sh daniel): runs the real StoryFxDaniel code (and the reused ids it plays
// in Babylon) at 60 fps against stand-in actors at the docs/daniel/storyboard/story.py marks, records the StoryTint
// result per frame so render.py can multiply the stand-in Babylon set by it, and writes the same frames.json format.
// A row name may carry "@variant" (same id, another anchor / camera). Rows played at night get `night` underneath.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class DanielPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  // stand-in actors: feet x, z, height, colour, slab width (0 = height * 0.22)
  struct Act { public string id; public float x, z, h, w; public string col; }
  static Act D(float x, float z, float h = 0.34f) => new Act{id="daniel",x=x,z=z,h=h,col="#7FA7D9"};
  static Act K(float x, float z) => new Act{id="king",x=x,z=z,h=0.44f,col="#B0447A"};
  static Act O(float x, float z) => new Act{id="officer",x=x,z=z,h=0.35f,col="#7C9A4A"};
  static Act L(float x, float z, float h = 0.15f) => new Act{id="lion",x=x,z=z,h=h,w=0.20f,col="#E0A040"};
  static Act L2(float x, float z, float h = 0.13f) => new Act{id="lion2",x=x,z=z,h=h,w=0.19f,col="#D9B070"};
  static readonly Dictionary<string, Act[]> Cast = new Dictionary<string, Act[]> {
    {"den_s08",  new[]{ D(0.30f,-0.10f), L(0.45f,-0.22f), L2(0.30f,-0.26f), K(0.05f,0.08f), O(-0.12f,0.12f) }},
    {"den_s09",  new[]{ D(0.36f,-0.13f,0.22f), L(0.44f,-0.09f,0.08f), L2(0.28f,-0.18f,0.07f), K(-0.05f,-0.30f) }},
    {"dawn",     new[]{ K(0.05f,0.08f), D(0.36f,-0.13f), L(0.45f,-0.22f,0.08f), L2(0.30f,-0.26f,0.07f) }},
    {"aside",    new[]{ O(0.04f,0.10f), D(-0.30f,-0.24f) }},
    {"run",      new[]{ O(-0.40f,0.18f), D(0.13f,0.06f), K(0.10f,0.02f), L(0.40f,-0.10f) }},
    {"palace",   new[]{ K(0.00f,-0.30f) }},
  };
  struct Row { public string name; public float dur; public string cast; public Vector3 anchor, look, camOff; public bool night, shut; }
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  static readonly Row[] Rows = {
    new Row{name="roar_shake",       dur=1.4f, cast="den_s08", anchor=V(0.40f,0.15f,-0.19f), look=V(0.40f,0.14f,-0.19f), camOff=V(0.40f,0.16f,0.48f)},
    new Row{name="dust_puff@stone",  dur=1.2f, cast="den_s08", anchor=V(0.25f,0.055f,-0.05f), look=V(0.27f,0.08f,-0.10f), camOff=V(-0.22f,0.22f,0.62f), shut=true},
    new Row{name="dust_puff@run",    dur=1.2f, cast="run",     anchor=V(-0.40f,0f,0.18f), look=V(-0.30f,0.12f,0.10f), camOff=V(0.10f,0.18f,0.80f)},
    new Row{name="angel_light",      dur=8f,   cast="den_s09", anchor=V(0.36f,0f,-0.13f), look=V(0.36f,0.16f,-0.13f), camOff=V(-0.17f,0.16f,0.47f), night=true, shut=true},
    new Row{name="angel_light@side", dur=8f,   cast="den_s09", anchor=V(0.36f,0f,-0.13f), look=V(0.34f,0.24f,-0.13f), camOff=V(-0.60f,0.10f,0.55f), night=true, shut=true},
    new Row{name="zzz",              dur=6f,   cast="den_s09", anchor=V(0.25f,0.06f,-0.16f), look=V(0.28f,0.12f,-0.14f), camOff=V(-0.10f,0.20f,0.50f), night=true, shut=true},
    new Row{name="dawn_glow",        dur=10f,  cast="dawn",    anchor=Vector3.zero, look=V(0.0f,0.20f,-0.20f), camOff=V(0.20f,0.22f,1.05f), shut=true},
    new Row{name="steam",            dur=1.6f, cast="aside",   anchor=V(0.04f,0.32f,0.10f), look=V(0.04f,0.26f,0.10f), camOff=V(0.05f,0.06f,0.50f)},
    new Row{name="sweat",            dur=1.2f, cast="run",     anchor=V(-0.40f,0.32f,0.18f), look=V(-0.38f,0.24f,0.18f), camOff=V(0.05f,0.06f,0.50f)},
    new Row{name="night",            dur=8f,   cast="den_s09", anchor=Vector3.zero, look=V(0.0f,0.22f,-0.25f), camOff=V(0.15f,0.20f,1.05f), shut=true},
    new Row{name="lamp_flame",       dur=8f,   cast="palace",  anchor=V(-0.15f,0.18f,-0.36f), look=V(-0.08f,0.16f,-0.32f), camOff=V(0.12f,0.12f,0.55f), night=true, shut=true},
  };
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    var night = FxLibrary.Get("night");
    foreach (var id in new[]{"sparkle","prayer_glow","tension_dim","golden_rays","confetti","sunset_glow","night","lamp_flame",
                             "steam","sweat","roar_shake","angel_light","zzz","dawn_glow","dust_puff"})
      Console.WriteLine($"id {id,-12} -> {(FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0];
      var def = FxLibrary.Get(id); if (def == null) throw new Exception("missing " + id);
      var cast = Cast[row.cast];
      RuthFx.Actors.Clear();
      foreach (var a in cast) RuthFx.Actors.Add(new RuthActor { feet = new Vector3(a.x, 0, a.z), height = a.h });
      EstherFx.BeamTarget = EstherFx.DefaultBeamTarget;
      var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      var ctxN = new FxCtx { dur = dur + 1.6f, seed = 777, camPos = camPos, camRight = right, camUp = up };
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      float[] fr = {0.08f,0.25f,0.45f,0.65f,0.85f};
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"daniel\",\"shut\":{(row.shut ? "true" : "false")},\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"actors\":[");
      for (int i = 0; i < cast.Length; i++) sb.Append((i>0?",":"") + $"[{F(cast[i].x)},{F(cast[i].z)},{F(cast[i].h)},\"{cast[i].col}\",{F(cast[i].w)}]");
      sb.Append("],\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0;
      StoryTint.Clear();
      ctx.start = row.anchor; ctxN.start = Vector3.zero; ctxN.anchor = Vector3.zero;
      for (float t = 0; t < dur && fi < fr.Length; t += dt) {
        ctx.t = t; ctxN.t = t + 0.8f;
        ctx.anchor = row.anchor; ctx.track.Add(t, row.anchor);
        batch.Clear();
        if (row.night) night.Emit(ctxN, batch);
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
      Console.WriteLine($"{row.name,-18} dur {dur} follow {def.Follow} shake {def.ShakeAmp} frames {fi} maxSprites {maxSprites} maxRibbons {maxRibbons}{(row.night ? " (with night)" : "")}");
    }
    sb.Append("}");
    File.WriteAllText(Path.Combine(outDir, "frames.json"), sb.ToString());
  }
}
