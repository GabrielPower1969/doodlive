# Upgrade path: web prototype → Unity 2022.3 LTS + AR Foundation (ARCore) + OpenCV

The prototype was cut along the same seams as the target architecture, so each piece can be swapped on its own.

| Prototype (web) | Target (Unity, Android) | Notes |
|---|---|---|
| `detectMarkers` (4 black squares) | `ARTrackedImageManager` + reference image of the full sheet | Image tracking gives the pose and the 4 corners (`trackedImage.transform` ± `size/2`). Keep the markers on the sheet anyway: they make the corner refinement robust. |
| `poseFromH` (planar PnP from H) | ARCore world tracking | Real 6DoF and scale. The angel stays put when the paper leaves the view. |
| `homography` + `warpArt` | `ARCameraManager.TryAcquireLatestCpuImage` → `XRCpuImage.Convert` (RGBA, half res) → OpenCV `Imgproc.getPerspectiveTransform` + `warpPerspective` to 1024² | Project the 4 world corners to camera-image pixels with the camera intrinsics (`TryGetIntrinsics`), not screen pixels. |
| `whiteBalance`, `eraseLines` | OpenCV: gray-world/percentile WB, `morphologyEx(MORPH_CLOSE)` on an ink mask + `inpaint` | Same thresholds are a good start. |
| `CanvasTexture` | `Texture2D.LoadRawTextureData` + `Apply()` → `material.SetTexture("_BaseMap", tex)` | One texture shared by all parts (front projection). |
| `makeMaterial` shader patch | URP Shader Graph: `paper = smoothstep(.60,.86, min(rgb))`, `albedo = lerp(tex, _BaseColor, paper*_BaseAmt)`; keep Normal Map + AO map on separate UV1 | Hand-drawn colour drives albedo only. Normal/AO come from the sculpt, so folds and feathers keep their shading. |
| Procedural rig in `angel.js` | Blender model → GLB/FBX with Humanoid-ish rig, clips `Enter`, `Idle`, `Blow` | Keep the bone names listed in `CLAUDE.md`. |
| `animate()` phases | Animator Controller: `Enter → Idle ⇄ Blow` (trigger on tap) | |
| WebAudio + Web Speech | `AudioSource` with recorded `fanfare.ogg` + voice lines (record or TTS-bake offline) | |

## Blender: page layout and UVs (the rule that makes colouring work)

1. **Model in the drawing's pose, front view = the sheet.** Put `lineart.png` on a reference plane at
   1.128 × 1.384 m and model the angel so its front silhouette matches the line art.
2. **UV0 = front projection.** Front ortho view, select all, then *UV → Project from View (Bounds)* using the art rectangle,
   so every vertex samples the page where it is drawn. The 2D sheet *is* the UV layout. Do not make a separate unwrap for UV0.
3. **Back, sides, underside (not drawn on the sheet):**
   - For a mirrored back, leave UV0 projected. The back then shows the same colours, which is the classic Quiver-style result and what kids expect.
   - For parts that must not take crayon (inside of sleeves, soles, under the cloud), give them a vertex-colour mask `M=0`.
     The shader uses `_BaseColor` there instead of the page.
   - Wing backs: project them from the front too, but tint them slightly darker in the shader (`backface ? 0.85 : 1`).
4. **UV1 = a normal unwrap** for the baked Normal map + AO from the high-poly sculpt (robe folds, feathers, hair).
5. Keep the head and hands slightly forward in Z so their projection isn't stolen by the hair or sleeves. Check this in
   Texture Paint mode with the demo-coloured page.

## Android build (Unity)

- Unity 2022.3 LTS, Android module, **IL2CPP, ARM64**, Min API 24 (ARCore), Target API 33+, Graphics: OpenGLES3 first (Vulkan optional).
- Packages: `com.unity.xr.arfoundation` 5.x, `com.unity.xr.arcore` 5.x, URP 14, OpenCV for Unity (Asset Store) or a small native C++ `.so`.
- XR Plug-in Management → ARCore ✔. ARCore: **Required** (Play Store lists AR-only) or Optional (with a non-AR fallback = our 展示模式).
- Manifest (Unity generates most of it):
  ```xml
  <uses-permission android:name="android.permission.CAMERA"/>
  <uses-feature android:name="android.hardware.camera.ar" android:required="true"/>
  <uses-feature android:glEsVersion="0x00030000" android:required="true"/>
  <application>
    <meta-data android:name="com.google.ar.core" android:value="required"/>
  </application>
  ```
- Runtime camera permission: `UnityEngine.Android.Permission.RequestUserPermission(Permission.Camera)` before enabling `ARSession`.

## Cheap intermediate steps (before Unity)

1. **Real model:** export a rigged GLB from Blender following the rules above and load it with `GLTFLoader` in `angel.js`.
   `app.js` is unchanged.
2. **Recorded voice + trumpet:** add files under `web/assets/sfx/` and play them in `audio.js`.
3. **Installable app:** wrap `web/` in a Trusted Web Activity (Bubblewrap) or a Capacitor WebView APK. Camera permission is then requested by the APK.
