# Overleaf export (Markdown-first)

This folder contains a minimal Overleaf project that typesets the thesis draft written in Markdown.

## Option A (recommended): keep writing in Markdown

1. From the repo root, run:

   `powershell -ExecutionPolicy Bypass -File .\overleaf\prepare_overleaf.ps1`

   This copies `docs/memoria_TFG_esqueleto.md` into this folder as `overleaf/memoria_TFG_esqueleto.md`.

2. Upload the whole `overleaf/` folder to Overleaf (New Project → Upload Project → zip the folder).

3. In Overleaf, compile `main.tex`.

Notes:
- Your numeric IEEE citations like `[3]` will appear as plain text (good enough for the draft). Later, if you want BibTeX, you can migrate those to `\cite{...}` and add a `.bib`.
- Some Markdown features (especially complex tables) may need small tweaks depending on the LaTeX `markdown` package support.

## Option B: convert Markdown to LaTeX (Pandoc)

If you prefer a pure `.tex` source in Overleaf, use Pandoc locally:

`pandoc docs/memoria_TFG_esqueleto.md -f gfm -t latex -o memoria_TFG.tex`

Then upload `memoria_TFG.tex` to Overleaf.
