$ErrorActionPreference = "Stop"

$cargoBin = Join-Path $HOME ".cargo\bin"
if (Test-Path $cargoBin) {
  $env:PATH = "$cargoBin;$env:PATH"
}

Set-Location (Split-Path $PSScriptRoot -Parent)
npm run dev
