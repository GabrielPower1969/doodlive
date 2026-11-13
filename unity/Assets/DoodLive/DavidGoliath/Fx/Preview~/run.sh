#!/bin/sh
# Off-Unity preview of the D&G effects: runs the real DGFxPaint/DGFxCore/DGFxEffects code under .NET 8
# (referencing Unity's UnityEngine.CoreModule.dll for Vector3/Color), dumps the exact triangles, renders PNGs.
# Usage: unity/Assets/DoodLive/DavidGoliath/Fx/Preview~/run.sh   (needs dotnet 8, python3 + numpy + Pillow)
# Unity ignores this folder (name ends in ~); the build project is generated in a temp dir.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
FX="$(cd "$HERE/.." && pwd)"
SCRIPTS="$(cd "$FX/../../Scripts" && pwd)"
UNITY="${UNITY_CONTENTS:-/Applications/Unity/Hub/Editor/2022.3.62f3/Unity.app/Contents}"
WORK="${TMPDIR:-/tmp}/dgfx-preview"
mkdir -p "$WORK"
cat > "$WORK/fxpreview.csproj" <<XML
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup>
  <ItemGroup>
    <Compile Include="$HERE/Harness.cs" />
    <Compile Include="$SCRIPTS/DesignTokens.cs" />
    <Compile Include="$FX/DGFxPaint.cs" />
    <Compile Include="$FX/DGFxCore.cs" />
    <Compile Include="$FX/DGFxEffects.cs" />
    <Reference Include="UnityEngine.CoreModule"><HintPath>$UNITY/Managed/UnityEngine/UnityEngine.CoreModule.dll</HintPath></Reference>
  </ItemGroup>
</Project>
XML
dotnet build "$WORK/fxpreview.csproj" -nologo -v q -o "$WORK/bin"
dotnet "$WORK/bin/fxpreview.dll" "$WORK/out"
python3 -I "$HERE/render.py" "$WORK/out"
cp "$WORK/out/atlas.png" "$WORK/out/fx_contact.png" "$HERE/"
echo "wrote $HERE/atlas.png $HERE/fx_contact.png"
