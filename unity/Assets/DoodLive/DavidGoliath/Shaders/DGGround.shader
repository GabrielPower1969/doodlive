// Sand ground of the David & Goliath page (CONTRACT §12.4, docs/david-goliath/INTEGRATION.md §4). One quad over the
// whole A4 page, just above the paper, under the desert set and the actors. Only the D&G stage uses it; the angel
// flow never sees this shader.
//
// UV0 = design page coordinates (x = viewer's right, z toward the viewer, art-width units), set by DGDirector.
//   mask (L8, page frame, ground-mask.png): 0 = sand, 128 = art rect (scan colour where painted), 255 = hole (brook)
//   sand  = _SandColor * (1 + 0.04 sin(phi) + 0.05 n2),  phi = 2pi (d/0.020 + 0.45 sin(2pi x/0.23) + 0.25 n1)
//   art   : paper = smoothstep(.60, .86, min(scan.rgb)); albedo = lerp(scan, sand, paper)   (painted ground keeps crayon)
// Lit like DGPaperLit (main light + shadows + SH ambient * _AmbTint), receives the actors' and the desert's shadows.
Shader "DoodLive/DGGround"
{
    Properties
    {
        _BaseMap ("Scanned art rect (same texture as DGPaperLit)", 2D) = "white" {}
        _MaskMap ("Ground mask (L8, page frame)", 2D) = "black" {}
        _SandColor ("Sand", Color) = (0.890, 0.765, 0.549, 1)
        _AmbTint ("Ambient tint", Color) = (1, 1, 1, 1)
        _Smoothness ("Smoothness", Range(0, 1)) = 0.05
    }
    SubShader
    {
        Tags { "RenderType" = "TransparentCutout" "RenderPipeline" = "UniversalPipeline" "Queue" = "AlphaTest" }

        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Cull Back

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #pragma multi_compile _ _ADDITIONAL_LIGHTS

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            TEXTURE2D(_BaseMap); SAMPLER(sampler_BaseMap);
            TEXTURE2D(_MaskMap); SAMPLER(sampler_MaskMap);
            CBUFFER_START(UnityPerMaterial)
                float4 _BaseMap_ST;
                float4 _MaskMap_ST;
                half4 _SandColor;
                half4 _AmbTint;
                half _Smoothness;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 page : TEXCOORD0;          // design (x, z)
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
                o.page = v.uv;
                return o;
            }

            // smooth value noise in [-1, 1], period-1 lattice
            float hash21(float2 p) { p = frac(p * float2(123.34, 456.21)); p += dot(p, p + 45.32); return frac(p.x * p.y); }
            float vnoise(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                float2 u = f * f * (3.0 - 2.0 * f);
                float a = hash21(i), b = hash21(i + float2(1, 0)), c = hash21(i + float2(0, 1)), d = hash21(i + float2(1, 1));
                return lerp(lerp(a, b, u.x), lerp(c, d, u.x), u.y) * 2.0 - 1.0;
            }

            half4 frag(Varyings i) : SV_Target
            {
                float x = i.page.x, z = i.page.y, d = -z;
                // page px: X = 620 + 1000 x, Y = 1510 + 1000 z on the 1240 x 1754 sheet (v up)
                float2 muv = float2((620.0 + 1000.0 * x) / 1240.0, 1.0 - (1510.0 + 1000.0 * z) / 1754.0);
                half m = SAMPLE_TEXTURE2D(_MaskMap, sampler_MaskMap, muv).r * 255.0h;
                clip(191.0h - m);                                   // 255 = brook hole: the paper (or demo page) shows

                float n1 = vnoise(float2(x, d) / 0.12);
                float n2 = vnoise(float2(x / 0.30 + 7.3, d / 0.30));
                float phi = 6.2831853 * (d / 0.020 + 0.45 * sin(6.2831853 * x / 0.23) + 0.25 * n1);
                // fade the 0.02-unit ripples where they would alias (grazing view, far away)
                float rip = saturate(1.5 - fwidth(phi) / 3.14159);
                half3 sand = _SandColor.rgb * (1.0h + 0.04h * sin(phi) * rip + 0.05h * n2);

                half3 albedo = sand;
                if (m >= 64.0h)
                {
                    half3 scan = SAMPLE_TEXTURE2D(_BaseMap, sampler_BaseMap, float2(x + 0.5, d / 1.227)).rgb;
                    half paper = smoothstep(0.60h, 0.86h, min(scan.r, min(scan.g, scan.b)));
                    albedo = lerp(scan, sand, paper);
                }

                float3 n = normalize(i.normalWS);
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
                s.metallic = 0;
                s.smoothness = _Smoothness;
                s.occlusion = 1;
                s.alpha = 1;
                return UniversalFragmentPBR(input, s);
            }
            ENDHLSL
        }
    }
    FallBack "Hidden/Universal Render Pipeline/FallbackError"
}
