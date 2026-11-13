// DoodLive/PaperLit plus a face decal, for the David & Goliath characters (docs/david-goliath/INTEGRATION.md).
// The app's line-erase wipes the printed faces from the scan (DESIGN.md), so faces come from a decal on UV1
// (RIG.md §4: UV1 = face rect, everything else pushed outside 0..1 -> clamp-to-transparent here).
// Copy of Shaders/PaperLit.shader; keep the page maths identical.
// paper  = smoothstep(.60, .86, min(rgb))            near-white = not painted
// albedo = lerp(page, _BaseColor, paper * _BaseAmt)  crayon wins where painted
// Optional vertex-colour mask (R = 0: never takes crayon), back-face tint for the wings, view rim glow.
// Also used for desert.glb (CONTRACT §12.1): its UV0 is baked by pipeline/dg_desert.py as the same front orthographic
// page projection the characters use (u = x/scale + sheetX + 0.5, v = (y/scale + sheetY)/1.227; the brook and stones
// keep their plan-view / constant UVs), so the same scan texture and maths apply; it has no UV1 (decal off). The
// ShadowCaster pass lets the actors shade the dunes. _AmbTint scales the SH ambient (D&G warm desert light).
Shader "DoodLive/DGPaperLit"
{
    Properties
    {
        _BaseMap ("Scanned page", 2D) = "white" {}
        _DecalMap ("Face decal (UV1, straight alpha)", 2D) = "black" {}
        _DecalAmt ("Face decal strength", Range(0, 1)) = 1
        _BaseColor ("Unpainted colour", Color) = (1, 1, 1, 1)
        _BaseAmt ("Unpainted mix", Range(0, 1)) = 0.9
        _Rim ("Rim glow", Range(0, 1)) = 0.25
        _Metallic ("Metallic", Range(0, 1)) = 0
        _Smoothness ("Smoothness", Range(0, 1)) = 0.25
        _BackTint ("Back face tint", Range(0, 1)) = 1
        _AmbTint ("Ambient tint", Color) = (1, 1, 1, 1)
        [Toggle] _UseMask ("Use vertex colour mask", Float) = 0
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
            TEXTURE2D(_DecalMap); SAMPLER(sampler_DecalMap);
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4 _BaseColor;
                float4 _DecalMap_ST;
                half4 _AmbTint;
                half _BaseAmt, _Rim, _Metallic, _Smoothness, _BackTint, _UseMask, _Cull, _DecalAmt;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
                float2 uv1 : TEXCOORD1;
                half4 color : COLOR;
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
                half mask : TEXCOORD3;
                float2 uv1 : TEXCOORD4;
            };

            Varyings vert(Attributes v)
            {
                Varyings o;
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uv = v.uv; // UV0 = page position: never tiled or offset
                o.uv1 = v.uv1;
                o.mask = lerp(1.0h, v.color.r, _UseMask);
                return o;
            }

            half4 frag(Varyings i, FRONT_FACE_TYPE face : FRONT_FACE_SEMANTIC) : SV_Target
            {
                half3 page = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).rgb;
                half paper = smoothstep(0.60h, 0.86h, min(page.r, min(page.g, page.b)));
                half3 albedo = lerp(page, _BaseColor.rgb, saturate(paper * _BaseAmt + (1.0h - i.mask)));
                // face decal: inside the unit square only (clamp-to-transparent), straight alpha over the page colour
                float2 d = i.uv1;
                half inside = (d.x > 0.002 && d.x < 0.998 && d.y > 0.002 && d.y < 0.998) ? 1.0h : 0.0h;
                half4 decal = SAMPLE_TEXTURE2D(_DecalMap, sampler_DecalMap, saturate(d));
                albedo = lerp(albedo, decal.rgb, decal.a * inside * _DecalAmt);

                bool front = IS_FRONT_VFACE(face, true, false);
                float3 n = normalize(i.normalWS) * (front ? 1.0 : -1.0);
                albedo *= front ? 1.0h : _BackTint;

                InputData input = (InputData)0;
                input.positionWS = i.positionWS;
                input.positionCS = i.positionCS;
                input.normalWS = n;
                input.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
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
                half rim = 1.0h - abs(dot(n, input.viewDirectionWS));
                c.rgb += _Rim * pow(rim, 3.0h) * half3(1.0h, 0.95h, 0.8h);
                return c;
            }
            ENDHLSL
        }

        // Shadows: actors cast onto the desert set and onto each other (CONTRACT §11.12). Same CBUFFER as above
        // (SRP batcher). _LightDirection / _LightPosition are set by URP for this pass.
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
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"   // Shadows.hlsl alone misses LerpWhiteTo

            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4 _BaseColor;
                float4 _DecalMap_ST;
                half4 _AmbTint;
                half _BaseAmt, _Rim, _Metallic, _Smoothness, _BackTint, _UseMask, _Cull, _DecalAmt;
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
