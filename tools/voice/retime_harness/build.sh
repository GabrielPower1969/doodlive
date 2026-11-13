#!/bin/sh
# Compile the voice-system C# (StoryRetime.cs, Voice/VoiceBank.cs, DGTimeline.cs) against Unity's managed DLLs and
# build the retime harness. Unity ignores tools/. Needs dotnet 8 and an installed Unity editor (Unity Hub).
# Usage: tools/voice/retime_harness/build.sh   -> prints the harness dll path on the last line
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
M=""
for E in ${UNITY_CONTENTS:-} $(ls -d /Applications/Unity/Hub/Editor/*/Unity.app/Contents 2>/dev/null | sort -r); do
  [ -f "$E/Resources/Scripting/Managed/UnityEngine/UnityEngine.CoreModule.dll" ] && { M="$E/Resources/Scripting/Managed/UnityEngine"; break; }
  [ -f "$E/Managed/UnityEngine/UnityEngine.CoreModule.dll" ] && { M="$E/Managed/UnityEngine"; break; }
done
[ -n "$M" ] || { echo "no Unity editor found (set UNITY_CONTENTS)" >&2; exit 2; }
WORK="${TMPDIR:-/tmp}/doodlive-retime-harness"
mkdir -p "$WORK"
REFS=""
for D in CoreModule AudioModule JSONSerializeModule UnityWebRequestModule UnityWebRequestAudioModule; do
  REFS="$REFS<Reference Include=\"UnityEngine.$D\"><HintPath>$M/UnityEngine.$D.dll</HintPath></Reference>"
done
cat > "$WORK/harness.csproj" <<XML
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><LangVersion>9.0</LangVersion>
    <Nullable>disable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    <TreatWarningsAsErrors>false</TreatWarningsAsErrors></PropertyGroup>
  <ItemGroup>
    <Compile Include="$HERE/Harness.cs" />
    <Compile Include="$REPO/unity/Assets/DoodLive/Story/StoryRetime.cs" />
    <Compile Include="$REPO/unity/Assets/DoodLive/Story/Voice/VoiceBank.cs" />
    <Compile Include="$REPO/unity/Assets/DoodLive/DavidGoliath/Scripts/DGTimeline.cs" />
    $REFS
  </ItemGroup>
</Project>
XML
dotnet build "$WORK/harness.csproj" -nologo -v q -o "$WORK/bin" 1>&2
echo "$WORK/bin/harness.dll"
