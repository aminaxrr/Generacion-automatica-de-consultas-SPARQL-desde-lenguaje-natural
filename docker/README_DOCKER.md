Prerequisites

- Docker Desktop installed and running (Windows: Docker Desktop for Windows).

What this does

- Uses a TeX Live Docker image to compile the Overleaf package in `overleaf/`.
- Produces `overleaf/main.pdf` in the host folder (mounted into the container).

How to run (PowerShell)

1. Open PowerShell in the project root (where `overleaf/` is).
2. Run the helper script:

   .\docker\build_pdf_with_docker.ps1

What the script does

- Runs a Docker container using `blang/latex:ctanfull` image.
- Executes `pdflatex` twice (to resolve TOC and references).
- Leaves `main.pdf` inside the `overleaf/` folder on your host.

Notes

- The first run may download the Docker image (~1.5-3 GB). Be patient.
- If you prefer manual commands, run:

  $pwd = (Get-Location).ProviderPath
  docker run --rm -v "${pwd}:/work" -w /work/overleaf blang/latex:ctanfull sh -c "pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -shell-escape -output-directory=. main.tex || true; pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -shell-escape -output-directory=. main.tex || true"

- If compilation still fails, capture `overleaf/output.log` (or the Docker output) and paste the first 100 lines here so I can debug further.
