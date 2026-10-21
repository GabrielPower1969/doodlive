// URP lit shader for the scanned page (port of makeMaterial in web/angel.js; docs/UPGRADE.md "Shader Graph" row).
// paper  = smoothstep(.60, .86, min(rgb))            near-white = not painted
// albedo = lerp(page, _BaseColor, paper * _BaseAmt)  crayon wins where painted
// Optional vertex-colour mask (R = 0: never takes crayon), back-face tint for the wings, view rim glow.
Shader "DoodLive/PaperLit"
{
    Properties
    {
        _BaseMap ("Scanned page", 2D) = "white" {}
        _BaseColor ("Unpainted colour", Color) = (1, 1, 1, 1)
        _BaseAmt ("Unpainted mix", Range(0, 1)) = 0.9
        _Rim ("Rim glow", Range(0, 1)) = 0.25
        _Metallic ("Metallic", Range(0, 1)) = 0
        _Smoothness ("Smoothness", Range(0, 1)) = 0.25
        _BackTint ("Back face tint", Range(0, 1)) = 1
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
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                half4 _BaseColor;
                half _BaseAmt, _Rim, _Metallic, _Smoothness, _BackTint, _UseMask, _Cull;
            CBUFFER_END

            struct Attributes
            {
                float4 positionOS : POSITION;
                float3 normalOS : NORMAL;
                float2 uv : TEXCOORD0;
                half4 color : COLOR;
            };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 positionWS : TEXCOORD1;
                float3 normalWS : TEXCOORD2;
                half mask : TEXCOORD3;
            };

            Varyings vert(Attributes v)
            {
                Varyings o;
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.uv = v.uv; // UV0 = page position: never tiled or offset
                o.mask = lerp(1.0h, v.color.r, _UseMask);
                return o;
            }

            half4 frag(Varyings i, FRONT_FACE_TYPE face : FRONT_FACE_SEMANTIC) : SV_Target
            {
                half3 page = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, i.uv).rgb;
                half paper = smoothstep(0.60h, 0.86h, min(page.r, min(page.g, page.b)));
                half3 albedo = lerp(page, _BaseColor.rgb, saturate(paper * _BaseAmt + (1.0h - i.mask)));

                bool front = IS_FRONT_VFACE(face, true, false);
                float3 n = normalize(i.normalWS) * (front ? 1.0 : -1.0);
                albedo *= front ? 1.0h : _BackTint;

                InputData input = (InputData)0;
                input.positionWS = i.positionWS;
                input.positionCS = i.positionCS;
                input.normalWS = n;
                input.viewDirectionWS = GetWorldSpaceNormalizeViewDir(i.positionWS);
                input.shadowCoord = TransformWorldToShadowCoord(i.positionWS);
                input.bakedGI = SampleSH(n);
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
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
