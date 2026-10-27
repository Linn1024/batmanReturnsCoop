param([string]$ToolchainBin=$env:BATMAN_MINGW_BIN,[switch]$CoreOnly)
$ErrorActionPreference='Stop'
if (-not $ToolchainBin) { $ToolchainBin='C:\TEMP2\zeroTolerance\bizhawk-integration\mingw64\bin' }
$previousPath=$env:PATH
Push-Location $PSScriptRoot
try {
    $env:PATH="$ToolchainBin;$previousPath"
    if ((& gcc -dumpmachine) -notmatch '^x86_64-') { throw 'A 64-bit MinGW-w64 toolchain is required.' }
    & mingw32-make -C engine platform=win CC=gcc -j8 -s
    if ($LASTEXITCODE) { throw 'Core build failed.' }
    if (-not $CoreOnly) {
        & g++ launcher.cpp -std=c++17 -O2 -static -mwindows -lwinmm -lgdi32 -luser32 -lbcrypt -lshell32 -o BatmanReturns-Coop.exe -lcomdlg32
        if ($LASTEXITCODE) { throw 'Launcher build failed.' }
    }
} finally { $env:PATH=$previousPath; Pop-Location }
