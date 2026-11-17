#!/bin/sh
# Off-Unity preview of the D&G effects: runs the real DGFxPaint/DGFxCore/DGFxEffects code under .NET 8
# (referencing Unity's UnityEngine.CoreModule.dll for Vector3/Color), dumps the exact triangles, renders PNGs.
# Usage: unity/Assets/DoodLive/DavidGoliath/Fx/Preview~/run.sh [esther|ruth|daniel|exodus|prodigal|gabriel|jonah|joseph|miracles|lastsupper|risen]   (needs dotnet 8, python3 + numpy + Pillow)
#   no argument: David & Goliath ids -> fx_contact.png;  "esther": Esther ids -> fx_contact_esther.png;
#   "ruth": Ruth ids over a stand-in Bethlehem set (tints applied) -> fx_contact_ruth.png
#   "daniel": Daniel ids (+ reused night / lamp / aliases) over a stand-in Babylon set -> fx_contact_daniel.png
#   "exodus": Exodus ids over a stand-in Egypt (sea walls at the simulated height) -> fx_contact_exodus.png
#   "prodigal": Prodigal ids (+ reused night / sunset / heart / rays) over a stand-in homeland -> fx_contact_prodigal.png
#   "gabriel": Gabriel ids (+ reused sparkle / heart_glow / golden_rays) over a stand-in heaven -> fx_contact_gabriel.png
#   "jonah": Jonah ids (+ alias plant_grow, reused ids) over a stand-in coast / belly -> fx_contact_jonah.png
#   "joseph": Joseph dream_cloud over a stand-in twolands and dream panel -> fx_contact_joseph.png
#   "miracles": Miracles dust_fall / calm_wave (+ dust_puff check) over a stand-in yard and lake -> fx_contact_miracles.png
#   "lastsupper": palm_toss / doves_fly / water_pour over stand-in yard, cream heaven floor and night -> fx_contact_lastsupper.png
#   "risen": tomb_glow / butterflies over a stand-in garden (tomb door, beds) drawn by RisenPreview.cs -> fx_contact_risen.png
#   FXPREVIEW_WORK=<dir> overrides the build / output dir (default $TMPDIR/dgfx-preview).
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
WORK="${FXPREVIEW_WORK:-${TMPDIR:-/tmp}/dgfx-preview}"
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
    <Compile Include="$FX/StoryFxDaniel.cs" />
    <Compile Include="$FX/StoryFxExodus.cs" />
    <Compile Include="$FX/StoryFxProdigal.cs" />
    <Compile Include="$FX/StoryFxGabriel.cs" />
    <Compile Include="$FX/StoryFxJonah.cs" />
    <Compile Include="$FX/StoryFxJoseph.cs" />
    <Compile Include="$FX/StoryFxMiracles.cs" />
    <Compile Include="$FX/StoryFxLastSupper.cs" />
    <Compile Include="$FX/StoryFxRisen.cs" />
    <Compile Include="$HERE/RuthPreview.cs" />
    <Compile Include="$HERE/DanielPreview.cs" />
    <Compile Include="$HERE/ExodusPreview.cs" />
    <Compile Include="$HERE/ProdigalPreview.cs" />
    <Compile Include="$HERE/GabrielPreview.cs" />
    <Compile Include="$HERE/JonahPreview.cs" />
    <Compile Include="$HERE/JosephPreview.cs" />
    <Compile Include="$HERE/MiraclesPreview.cs" />
    <Compile Include="$HERE/LastSupperPreview.cs" />
    <Compile Include="$HERE/RisenPreview.cs" />
    <Reference Include="UnityEngine.CoreModule"><HintPath>$CORE</HintPath></Reference>
  </ItemGroup>
</Project>
XML
dotnet build "$WORK/fxpreview.csproj" -nologo -v q -o "$WORK/bin"
dotnet "$WORK/bin/fxpreview.dll" "$WORK/out" "$SET"
python3 -I "$HERE/render.py" "$WORK/out"
if [ "$SET" = jonah ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_jonah.png"; echo "wrote $HERE/fx_contact_jonah.png"
elif [ "$SET" = risen ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_risen.png"; echo "wrote $HERE/fx_contact_risen.png"
elif [ "$SET" = lastsupper ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_lastsupper.png"; echo "wrote $HERE/fx_contact_lastsupper.png"
elif [ "$SET" = miracles ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_miracles.png"; echo "wrote $HERE/fx_contact_miracles.png"
elif [ "$SET" = joseph ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_joseph.png"; echo "wrote $HERE/fx_contact_joseph.png"
elif [ "$SET" = gabriel ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_gabriel.png"; echo "wrote $HERE/fx_contact_gabriel.png"
elif [ "$SET" = prodigal ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_prodigal.png"; echo "wrote $HERE/fx_contact_prodigal.png"
elif [ "$SET" = exodus ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_exodus.png"; echo "wrote $HERE/fx_contact_exodus.png"
elif [ "$SET" = daniel ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_daniel.png"; echo "wrote $HERE/fx_contact_daniel.png"
elif [ "$SET" = ruth ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_ruth.png"; echo "wrote $HERE/fx_contact_ruth.png"
elif [ "$SET" = esther ]; then
  cp "$WORK/out/fx_contact.png" "$HERE/fx_contact_esther.png"; echo "wrote $HERE/fx_contact_esther.png"
else
  cp "$WORK/out/atlas.png" "$WORK/out/fx_contact.png" "$HERE/"; echo "wrote $HERE/atlas.png $HERE/fx_contact.png"
fi
