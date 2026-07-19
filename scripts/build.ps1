$ErrorActionPreference = "Stop"

$cargoBin = Join-Path $HOME ".cargo\bin"
if (Test-Path $cargoBin) {
  $env:PATH = "$cargoBin;$env:PATH"
}

$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Host "Creating virtual environment..."
  python -m venv .venv
}

& $venvPython -m pip install -q -r requirements.txt
& $venvPython -m pip install -q pyinstaller

Write-Host "Building sidecar with PyInstaller..."
& $venvPython -m PyInstaller --noconfirm sidecar/build_sidecar.spec
if ($LASTEXITCODE -ne 0) {
  throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$sidecarExe = Join-Path $repoRoot "dist\m3u8-sidecar.exe"
if (-not (Test-Path $sidecarExe)) {
  throw "Expected sidecar binary missing: $sidecarExe"
}

$targetTriple = (& rustc --print host-tuple).Trim()
if (-not $targetTriple) {
  throw "Failed to determine host target triple via rustc"
}

$binariesDir = Join-Path $repoRoot "src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $binariesDir | Out-Null
$destName = "m3u8-sidecar-$targetTriple.exe"
$destPath = Join-Path $binariesDir $destName
Copy-Item -Force $sidecarExe $destPath
Write-Host "Copied sidecar to $destPath"

Write-Host "Building frontend..."
npm --prefix ui run build
if ($LASTEXITCODE -ne 0) {
  throw "frontend build failed with exit code $LASTEXITCODE"
}

Write-Host "Building Tauri app..."
# Use tauri CLI directly; root `npm run build` would re-enter via beforeBuildCommand.
npm run tauri -- build
if ($LASTEXITCODE -ne 0) {
  throw "tauri build failed with exit code $LASTEXITCODE"
}

Write-Host "Build complete."
