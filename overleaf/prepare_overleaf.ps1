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
  # Post-process the copied Markdown to sanitize problematic characters and large floats
  try {
    # Force UTF-8 to avoid mojibake. Use no-BOM output because a UTF-8 BOM can
    # break Markdown heading detection for the first line in some LaTeX setups.
    $content = Get-Content -Path $dst -Raw -Encoding UTF8 -ErrorAction Stop
    # Replace typographic quotes with straight quotes using Unicode code points
    $content = $content -replace ([char]0x201C), '"'
    $content = $content -replace ([char]0x201D), '"'
    $content = $content -replace ([char]0x2018), "'"
    $content = $content -replace ([char]0x2019), "'"
    # Reduce figure widths and remove explicit large height to avoid "Float too large" in LaTeX
    $content = $content -replace 'width=0.85','width=0.65'
    $content = $content -replace 'height=0.7\\textheight,',''
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($dst, $content, $utf8NoBom)
    Write-Host "Sanitized Markdown at: $dst"
  } catch {
    Write-Warning "Post-processing failed: $_"
  }

  Write-Host "Now upload the entire 'overleaf' folder to Overleaf as a new project."
