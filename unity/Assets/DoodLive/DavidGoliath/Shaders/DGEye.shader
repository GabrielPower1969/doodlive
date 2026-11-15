// Eyeballs of the live 3D faces (DGFace3D, pipeline "3D eyes"): opaque, glossy, no transparency (no sorting issues
// over the AR camera image, nothing to z-fight). Albedo = the eye atlas on UV0 (sclera, iris, pupil). Lit like
// DGPaperLit (URP PBR, main + additional lights, SH ambient scaled by _AmbTint) with a high smoothness, plus a
// "catch-light": a small soft disc reflected from a light fixed to the camera (upper left of the view), the way film
// eyes get an eye light. Because it is a reflection on the eyeball's real (cornea-bulged) normals, it stays put while
// the iris moves under it as the eye turns, as a real corneal highlight does. A light grazing darkening rounds the
// eyeball. Same CBUFFER in both passes (SRP batcher).
Shader "DoodLive/DGEye"
{
    Properties
    {
        _BaseMap ("Eye atlas", 2D) = "white" {}
        _BaseColor ("Tint", Color) = (1, 1, 1, 1)
        _Smoothness ("Smoothness", Range(0, 1)) = 0.8
        _Metallic ("Metallic", Range(0, 1)) = 0
        _AmbTint ("Ambient tint", Color) = (1, 1, 1, 1)
        _CatchDir ("Catch-light direction (view space, toward the light)", Vector) = (-0.45, 0.55, 1, 0)
        _CatchSize ("Catch-light size (cos of the reflected angle)", Range(0.9, 0.9999)) = 0.972
        _CatchSoft ("Catch-light edge softness", Range(0.0005, 0.05)) = 0.010
        _CatchAmt ("Catch-light strength", Range(0, 2)) = 0.9
        _Grazing ("Grazing darkening", Range(0, 1)) = 0.22
        [Enum(UnityEngine.Rendering.CullMode)] _Cull ("Cull", Float) = 2
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull [_Cull]

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #pragma multi_compile _ _ADDITIONAL_LIGHTS

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4 _BaseColor;
                half4 _AmbTint;
                float4 _CatchDir;
                half _Smoothness, _Metallic, _CatchSize, _CatchSoft, _CatchAmt, _Grazing, _Cull;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
            };

            Varyings vert(Attributes v)
            {
                Varyings o;
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uv = v.uv;
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                half3 albedo = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).rgb * _BaseColor.rgb;
                float3 n = normalize(i.normalWS);
                float3 viewDir = GetWorldSpaceNormalizeViewDir(i.positionWS);
                half ndv = saturate(dot(n, viewDir));
                albedo *= lerp(1.0h - _Grazing, 1.0h, sqrt(ndv));

                InputData input = (InputData)0;
                input.positionWS = i.positionWS;
                input.positionCS = i.positionCS;
                input.normalWS = n;
                input.viewDirectionWS = viewDir;
                input.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                input.bakedGI = SampleSH(n) * _AmbTint.rgb;
                input.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(i.positionCS);
                input.shadowMask = half4(1, 1, 1, 1);

                SurfaceData s = (SurfaceData)0;
                s.albedo = albedo;
                s.metallic = _Metallic;
                s.smoothness = _Smoothness;
                s.occlusion = 1;
                s.alpha = 1;
                half4 c = UniversalFragmentPBR(input, s);

                // catch-light: reflection of a camera-fixed light, a soft-edged disc
                float3 lw = normalize(mul((float3x3)UNITY_MATRIX_I_V, _CatchDir.xyz));
                float3 r = reflect(-viewDir, n);
                half d = (half)dot(r, lw);
                half disc = smoothstep(_CatchSize - _CatchSoft, _CatchSize + _CatchSoft, d);
                c.rgb += disc * _CatchAmt * half3(1.0h, 0.98h, 0.95h);
                return c;
            }
            ENDHLSL
        }

        Pass
        {
            Name "ShadowCaster"
            Tags { "LightMode" = "ShadowCaster" }
            ZWrite On ZTest LEqual ColorMask 0
            Cull [_Cull]

            HLSLPROGRAM
            #pragma vertex shadowVert
            #pragma fragment shadowFrag
            #pragma multi_compile_vertex _ _CASTING_PUNCTUAL_LIGHT_SHADOW
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4 _BaseColor;
                half4 _AmbTint;
                float4 _CatchDir;
                half _Smoothness, _Metallic, _CatchSize, _CatchSoft, _CatchAmt, _Grazing, _Cull;
            CBUFFER_END
            float3 _LightDirection;
            float3 _LightPosition;

            float4 shadowVert(float4 positionOS : POSITION, float3 normalOS : NORMAL) : SV_POSITION
            {
                float3 ws = TransformObjectToWorld(positionOS.xyz);
                float3 nws = TransformObjectToWorldNormal(normalOS);
            #if _CASTING_PUNCTUAL_LIGHT_SHADOW
                float3 ld = normalize(_LightPosition - ws);
            #else
                float3 ld = _LightDirection;
            #endif
                float4 cs = TransformWorldToHClip(ApplyShadowBias(ws, nws, ld));
            #if UNITY_REVERSED_Z
                cs.z = min(cs.z, UNITY_NEAR_CLIP_VALUE);
            #else
                cs.z = max(cs.z, UNITY_NEAR_CLIP_VALUE);
            #endif
                return cs;
            }
            half4 shadowFrag() : SV_Target { return 0; }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
