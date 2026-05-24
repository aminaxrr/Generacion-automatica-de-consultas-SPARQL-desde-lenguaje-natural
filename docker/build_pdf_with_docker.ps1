# Helper PowerShell script to compile the Overleaf package inside Docker
# Requires Docker Desktop to be installed and running.
# Run from project root: .\docker\build_pdf_with_docker.ps1

$pwd = (Get-Location).ProviderPath
Write-Host "Project root: $pwd"

# Ensure overleaf folder exists
if (-not (Test-Path "$pwd\overleaf\main.tex")) {
    Write-Error "overleaf/main.tex not found. Run this script from the project root where 'overleaf/' exists."
    exit 1
}

# Image to use
$image = 'blang/latex:ctanfull'

# Pull image (will be fast if already cached)
Write-Host "Pulling Docker image $image (if needed)..."
docker pull $image

# Run container and compile
Write-Host "Running Docker container to compile LaTeX..."
$mount = "{0}/overleaf:/work/overleaf" -f ($pwd -replace '\\','/')
$shCmd = 'pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -shell-escape -output-directory=. main.tex || true; pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -shell-escape -output-directory=. main.tex || true'

Write-Host "docker run --rm -v `"$mount`" -w /work/overleaf $image sh -c `"$shCmd`""

# Use the call operator so PowerShell does not try to parse the shell command.
& docker run --rm -v $mount -w /work/overleaf $image sh -c $shCmd
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Docker run exit code: $LASTEXITCODE. Check Docker output above for errors."
}

# Check result
if (Test-Path "$pwd\overleaf\main.pdf") {
    Write-Host "PDF successfully generated: $pwd\overleaf\main.pdf"
} else {
    Write-Warning "No PDF produced. Inspect the Docker output above for first errors. You can also open the compiled log inside overleaf/ if present."
}
