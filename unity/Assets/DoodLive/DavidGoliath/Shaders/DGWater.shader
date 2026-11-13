// The brook of the David & Goliath desert set (desert.glb node `brook`, material dg_water; CONTRACT §11.9): a thin
// transparent film over the printed brook, so the child's colour on the real paper (or the demo page) shows through.
// No texture and no UV: ripples come from object-space position and time, shine from the main light. URP, mobile.
Shader "DoodLive/DGWater"
{
    Properties
    {
        _Tint ("Water tint (alpha = film opacity)", Color) = (0.55, 0.78, 0.95, 0.22)
        _Shine ("Ripple shine", Range(0, 1)) = 0.55
        _Scale ("Ripple scale (per art width)", Float) = 90
        _Speed ("Ripple speed", Float) = 1.2
    }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "RenderPipeline" = "UniversalPipeline" "Queue" = "Transparent" }
        Pass
        {
            Name "ForwardLit"
            Tags { "LightMode" = "UniversalForward" }
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            Cull Back

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _Tint;
                half _Shine;
                float _Scale, _Speed;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            struct Varyings { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; float2 p : TEXCOORD1; float3 normalWS : TEXCOORD2; };

            Varyings vert(Attributes v)
            {
                Varyings o;
                VertexPositionInputs p = GetVertexPositionInputs(v.positionOS.xyz);
                o.positionCS = p.positionCS; o.positionWS = p.positionWS;
                o.normalWS = TransformObjectToWorldNormal(v.normalOS);
                o.p = v.positionOS.xz;   // object space = page units, so the ripple size follows the page in AR and demo
                return o;
            }

            half4 frag(Varyings i) : SV_Target
            {
                float t = _Time.y * _Speed;
                float2 q = i.p * _Scale;
                // two crossing wave trains along the brook -> soft moving highlight bands
                float w = sin(q.y * 1.0 + q.x * 0.35 - t * 2.1) * 0.5 + sin(q.y * 0.6 - q.x * 0.8 + t * 1.3) * 0.5;
                half band = smoothstep(0.55h, 0.95h, (half)w);
                Light L = GetMainLight();
                float3 n = normalize(i.normalWS + float3(0.25 * cos(q.x + t), 0, 0.25 * sin(q.y - t)));
                float3 vdir = GetWorldSpaceNormalizeViewDir(i.positionWS);
                half spec = pow(saturate(dot(n, normalize(L.direction + vdir))), 48.0h);
                half3 col = _Tint.rgb * (0.6h + 0.4h * L.color) + (band * 0.5h + spec) * _Shine * L.color;
                half a = saturate(_Tint.a + band * 0.25h * _Shine + spec * _Shine);
                return half4(col, a);
            }
            ENDHLSL
        }
    }
    FallBack Off
}
