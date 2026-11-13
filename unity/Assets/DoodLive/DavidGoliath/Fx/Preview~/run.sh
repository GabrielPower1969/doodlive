#!/bin/sh
# Off-Unity preview of the D&G effects: runs the real DGFxPaint/DGFxCore/DGFxEffects code under .NET 8
# (referencing Unity's UnityEngine.CoreModule.dll for Vector3/Color), dumps the exact triangles, renders PNGs.
# Usage: unity/Assets/DoodLive/DavidGoliath/Fx/Preview~/run.sh [esther|ruth]   (needs dotnet 8, python3 + numpy + Pillow)
#   no argument: David & Goliath ids -> fx_contact.png;  "esther": Esther ids -> fx_contact_esther.png;
#   "ruth": Ruth ids over a stand-in Bethlehem set (tints applied) -> fx_contact_ruth.png
# Unity ignores this folder (name ends in ~); the build project is generated in a temp dir.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
FX="$(cd "$HERE/.." && pwd)"
SCRIPTS="$(cd "$FX/../../Scripts" && pwd)"
SET="${1:-dg}"
UNITY="${UNITY_CONTENTS:-/Applications/Unity/Hub/Editor/2022.3.62f3/Unity.app/Contents}"
CORE="$UNITY/Managed/UnityEngine/UnityEngine.CoreModule.dll"
[ -f "$CORE" ] || CORE="$UNITY/Resources/Scripting/Managed/UnityEngine/UnityEngine.CoreModule.dll"   # Unity 6 layout
if [ ! -f "$CORE" ] && [ -z "$UNITY_CONTENTS" ]; then   # default editor not installed: use the newest one in Unity Hub
  for E in $(ls -d /Applications/Unity/Hub/Editor/*/Unity.app/Contents 2>/dev/null | sort -r); do
    for C in "$E/Managed/UnityEngine/UnityEngine.CoreModule.dll" "$E/Resources/Scripting/Managed/UnityEngine/UnityEngine.CoreModule.dll"; do
      [ -f "$CORE" ] || { [ -f "$C" ] && CORE="$C"; }
    done
  done
fi
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
    <Compile Include="$FX/StoryFxEsther.cs" />
    <Compile Include="$FX/StoryFxRuth.cs" />
    <Compile Include="$HERE/RuthPreview.cs" />
    <Reference Include="UnityEngine.CoreModule"><HintPath>$CORE</HintPath></Reference>
  </ItemGroup>
</Project>
XML
dotnet build "$WORK/fxpreview.csproj" -nologo -v q -o "$WORK/bin"
dotnet "$WORK/bin/fxpreview.dll" "$WORK/out" "$SET"
python3 -I "$HERE/render.py" "$WORK/out"
if [ "$SET" = ruth ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_ruth.png"; echo "wrote $HERE/fx_contact_ruth.png"
elif [ "$SET" = esther ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_esther.png"; echo "wrote $HERE/fx_contact_esther.png"
else
  cp "$WORK/out/atlas.png" "$WORK/out/fx_contact.png" "$HERE/"; echo "wrote $HERE/atlas.png $HERE/fx_contact.png"
fi
