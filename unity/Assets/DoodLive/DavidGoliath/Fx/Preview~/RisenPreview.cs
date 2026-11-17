// He Is Risen! rows of the off-Unity preview (run.sh risen): runs the real StoryFxRisen code (the new ids come from
// RisenFx.Defs, because the manifest registration is merged by the lead; reused ids come from FxLibrary) at 60 fps.
// There is no garden stand-in in render.py, so this file draws one into the same batch before the effect (alpha
// sprites, depth-tested against the Ruth yard): a green lawn, the reddish rock hill with the dark door, the folded
// cloths inside, the rolled-away stone and blooms in the two flower beds (CONTRACT §6 positions, DESIGN §3 colours).
// Actors are the yard's slabs at the CONTRACT heights. Optional under-layers (dawn_glow, golden_rays) run first.
// Same frames.json format as the other packs.
using System; using System.IO; using System.Text; using System.Collections.Generic; using System.Globalization;
using UnityEngine; using DoodLive.DavidGoliath;
static class RisenPreview {
  static string F(float v) => v.ToString("0.#####", CultureInfo.InvariantCulture);
  static Vector3 V(float x, float y, float z) => new Vector3(x, y, z);
  static Color Hex(uint h) => new Color(((h >> 16) & 255) / 255f, ((h >> 8) & 255) / 255f, (h & 255) / 255f, 1f);
  // camera from a shot's dist / height / yawDeg (approximate: yaw turns the camera to +x)
  static Vector3 Cam(float dist, float height, float yawDeg) { float y = yawDeg * Mathf.Deg2Rad; return V(dist * Mathf.Sin(y), height, dist * Mathf.Cos(y)); }
  struct Row { public string name; public float dur; public Vector3 anchor, look, camOff; public string under; public Vector3 underAt; public float[][] actors; public string[] colours; public float[] times; public bool stone; }
  static readonly float[][] Women = { new[]{-0.30f,-0.22f,0.34f}, new[]{-0.40f,-0.21f,0.33f}, new[]{-0.17f,-0.285f,0.40f} };
  static readonly Row[] Rows = {
    new Row{name="tomb_glow@S04", dur=9f, anchor=V(-0.33f,0.15f,-0.30f), look=V(-0.24f,0.20f,-0.285f), camOff=Cam(0.55f,0.02f,25f),
      under="dawn_glow", actors=Women, colours=new[]{"#D9775F","#D9A93A","#F4F7FB"}, stone=true, times=new[]{0.3f,1.0f,3.0f,6.0f,8.6f}},
    new Row{name="tomb_glow@S07", dur=14f, anchor=V(-0.33f,0.15f,-0.30f), look=V(-0.33f,0.15f,-0.30f), camOff=Cam(0.5f,0.05f,20f),
      actors=new[]{new[]{-0.40f,-0.22f,0.33f},new[]{-0.22f,-0.14f,0.38f}}, colours=new[]{"#8DB5D8","#B5523A"}, stone=true, times=new[]{0.2f,0.8f,4.0f,9.0f,13.7f}},
    new Row{name="tomb_glow@door", dur=9f, anchor=V(-0.33f,0.15f,-0.30f), look=V(-0.33f,0.14f,-0.30f), camOff=V(0.02f,0.03f,0.33f),
      actors=new float[0][], colours=new string[0], stone=true, times=new[]{0.4f,1.5f,4.0f,6.5f,8.6f}},
    new Row{name="butterflies@S09", dur=8f, anchor=V(-0.45f,0f,0.0f), look=V(-0.10f,0.17f,-0.12f), camOff=Cam(0.5f,0.0f,-25f),
      under="golden_rays", underAt=V(-0.10f,0f,-0.12f), actors=new[]{new[]{-0.10f,-0.12f,0.36f},new[]{-0.205f,-0.075f,0.34f}}, colours=new[]{"#EFE6D2","#D9775F"},
      stone=true, times=new[]{0.6f,1.5f,3.0f,5.0f,7.6f}},
    new Row{name="butterflies@S12", dur=14f, anchor=V(-0.45f,0f,0.0f), look=V(-0.25f,0.10f,-0.12f), camOff=Cam(0.95f,0.38f,6f),
      under="golden_rays", underAt=V(-0.33f,0.15f,-0.30f),
      actors=new[]{new[]{-0.12f,-0.04f,0.36f},new[]{-0.24f,0.02f,0.34f},new[]{0.04f,0.04f,0.38f},new[]{0.14f,0.08f,0.33f},new[]{0.06f,-0.10f,0.36f}},
      colours=new[]{"#EFE6D2","#D9775F","#B5523A","#8DB5D8","#3E8E86"}, stone=true, times=new[]{1.0f,3.0f,6.0f,10.0f,13.6f}},
    new Row{name="butterflies@beds", dur=8f, anchor=V(-0.45f,0f,0.0f), look=V(-0.44f,0.09f,0.08f), camOff=V(0.05f,0.10f,0.40f),
      actors=new float[0][], colours=new string[0], stone=true, times=new[]{0.9f,2.0f,3.5f,5.5f,7.6f}},
    new Row{name="butterflies@other", dur=6f, anchor=V(0.10f,0f,0.05f), look=V(0.10f,0.12f,0.05f), camOff=V(0f,0.15f,0.55f),
      actors=new float[0][], colours=new string[0], times=new[]{0.5f,1.5f,3.0f,4.5f,5.6f}},
  };
  static FxDef Find(string id) {
    foreach (var d in RisenFx.Defs) if (d.Id == id) return d;
    var f = FxLibrary.Get(id); if (f == null) throw new Exception("missing " + id); return f;
  }
  // the garden stand-in, drawn into the batch first (alpha sprites; the yard's z-buffer hides what is behind)
  static void Garden(FxBatch b, bool stone) {
    Color lawn = Hex(0x8DBB5A), rock = Hex(0xC9946A), door = Hex(0x4A3440), linen = Hex(0xF5F1E6), grey = Hex(0xB9AFA2);
    for (int k = 0; k < 2; k++) b.Sprite(V(-0.20f, 0.0025f, -0.06f), 1.05f, 0.56f, lawn, DGFxPaint.Puff, 0f, false, FxFace.Ground);
    for (int k = 0; k < 3; k++) b.Sprite(V(-0.32f, 0.17f, -0.36f), 0.62f, 0.50f, rock, DGFxPaint.Puff, 0f, false, FxFace.Camera);
    for (int k = 0; k < 3; k++) b.Sprite(V(-0.33f, 0.15f, -0.302f), 0.15f, 0.40f, door, DGFxPaint.Pebble, 0f, false, FxFace.Camera);
    for (int k = 0; k < 2; k++) b.Sprite(V(-0.355f, 0.075f, -0.300f), 0.07f, 0.03f, linen, DGFxPaint.ConfettiRect, 0f, false, FxFace.Camera);
    for (int k = 0; k < 2; k++) b.Sprite(V(-0.30f, 0.065f, -0.300f), 0.04f, 0.022f, linen, DGFxPaint.ConfettiRect, 0f, false, FxFace.Camera);
    if (stone) for (int k = 0; k < 3; k++) b.Sprite(V(-0.17f, 0.11f, -0.285f), 0.22f, grey, DGFxPaint.ConfettiDot, 0f, false, FxFace.Camera);
    Color[] bloom = { Hex(0xFFFFFF), Hex(0xD9483A), Hex(0xF2C94C) };
    Vector4[] beds = { RisenFx.BedFront, RisenFx.BedHill };
    int n = 0;
    foreach (var bed in beds) {
      int cnt = bed.Equals(RisenFx.BedFront) ? 36 : 12;
      for (int i = 0; i < cnt; i++, n++) {
        float x = Mathf.Lerp(bed.x, bed.y, FxRand.H(77, n, 0)), z = Mathf.Lerp(bed.z, bed.w, FxRand.H(77, n, 1));
        b.Sprite(V(x, 0.012f, z), 0.016f, 0.024f, Hex(0x5E9A48), DGFxPaint.Pebble, 0f, false, FxFace.Camera);
        b.Sprite(V(x, 0.032f, z + 0.002f), 0.022f, bloom[n % 3], DGFxPaint.ConfettiDot, 0f, false, FxFace.Camera);
      }
    }
  }
  public static void Run(string outDir, Vector2[] mn, Vector2[] sz) {
    foreach (var id in new[]{"tomb_glow","butterflies","angel_light","dawn_glow","run_dust","dust_burst","golden_rays","heart_glow","lamp_flame","sunset_glow","tension_dim"})
      Console.WriteLine($"id {id,-12} -> {(Array.Exists(RisenFx.Defs, d => d.Id == id) ? "new RisenFx" : FxLibrary.Get(id) == null ? "MISSING" : FxLibrary.Get(id).GetType().Name)}");
    var sb = new StringBuilder(); sb.Append("{"); bool first = true;
    foreach (var row in Rows) {
      string id = row.name.Split('@')[0]; var def = Find(id);
      RuthFx.Actors.Clear();
      var anchor = row.anchor; var look = row.look; var camPos = look + row.camOff; float dur = row.dur;
      var fwd = (look - camPos).normalized; var right = Vector3.Cross(Vector3.up, fwd).normalized; var up = Vector3.Cross(fwd, right);
      var ctx = new FxCtx { dur = dur, seed = 12345, camPos = camPos, camRight = right, camUp = up };
      FxDef underDef = row.under != null ? Find(row.under) : null;
      var uctx = new FxCtx { dur = row.under == "golden_rays" ? dur : 40f, seed = 700, camPos = camPos, camRight = right, camUp = up };
      float[] times = row.times;
      var batch = new FxBatch();
      var v = new List<Vector3>(); var uv = new List<Vector2>(); var col = new List<Color>(); var ta = new List<int>(); var tb = new List<int>();
      sb.Append(first ? "" : ","); first = false;
      sb.Append($"\"{row.name}\":{{\"dur\":{F(dur)},\"scene\":\"ruth\",\"wings\":0,\"cam\":[{F(camPos.x)},{F(camPos.y)},{F(camPos.z)},{F(look.x)},{F(look.y)},{F(look.z)}],\"actors\":[");
      for (int i = 0; i < row.actors.Length; i++) { var a = row.actors[i]; sb.Append((i>0?",":"") + $"[{F(a[0])},{F(a[1])},{F(a[2])},\"{row.colours[i]}\"]"); }
      sb.Append("],\"frames\":[");
      float dt = 1f/60f; int fi = 0; int maxSprites = 0, maxRibbons = 0, base0 = 0;
      StoryTint.Clear(); StoryLight.Reset(); ctx.start = anchor;
      for (float t = 0; t < dur + 1e-3f && fi < times.Length; t += dt) {
        ctx.t = t; ctx.anchor = anchor; ctx.track.Add(t, anchor);
        batch.Clear();
        Garden(batch, row.stone);
        if (underDef != null) { uctx.t = row.under == "golden_rays" ? t : t + 4f; uctx.anchor = uctx.start = row.underAt; underDef.Emit(uctx, batch); }
        base0 = batch.sprites.Count; int r0 = batch.ribbons.Count;
        def.Emit(ctx, batch);
        StoryTint.Resolve(out Color tint, out Color rim, out float level);
        StoryLight.Resolve(out float dim, out float flash);
        maxSprites = Math.Max(maxSprites, batch.sprites.Count - base0); maxRibbons = Math.Max(maxRibbons, batch.ribbons.Count - r0);
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
