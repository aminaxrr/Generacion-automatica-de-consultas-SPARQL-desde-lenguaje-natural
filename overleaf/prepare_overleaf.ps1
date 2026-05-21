# Copies the current Markdown draft into the Overleaf folder.
# Run from repo root: powershell -ExecutionPolicy Bypass -File .\overleaf\prepare_overleaf.ps1

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repoRoot 'docs\memoria_TFG_esqueleto.md'
$dst = Join-Path $PSScriptRoot 'memoria_TFG_esqueleto.md'

$figSrc = Join-Path $repoRoot 'docs\figures'
$figDst = Join-Path $PSScriptRoot 'figures'

if (-not (Test-Path $src)) {
  throw "Source Markdown not found: $src"
}

Copy-Item -Force $src $dst
Write-Host "Copied: $src -> $dst"

if (Test-Path $figSrc) {
  if (-not (Test-Path $figDst)) {
    New-Item -ItemType Directory -Path $figDst | Out-Null
  }
  Copy-Item -Recurse -Force (Join-Path $figSrc '*') $figDst
  Write-Host "Copied: $figSrc -> $figDst"
}
Write-Host "Now upload the entire 'overleaf' folder to Overleaf as a new project."
