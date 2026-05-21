"""Render a plain-text file into a PNG image.

Used to create thesis-ready evidence images from CLI outputs (e.g., --explain traces)
without relying on screenshots.

Example:
  python src/render_text_to_png.py eval/cli_explain_end2end_utf8.txt docs/figures/cli_explain_end2end.png
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _wrap_lines(lines: list[str], max_chars: int) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line.strip():
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line, width=max_chars, break_long_words=True, break_on_hyphens=False))
    return wrapped


def render_text_to_png(
    input_path: Path,
    output_path: Path,
    *,
    max_width_px: int = 1400,
    padding_px: int = 20,
    line_spacing_px: int = 4,
) -> None:
    text = input_path.read_text(encoding="utf-8", errors="replace")
    text = text.replace("\t", "    ")
    lines = text.splitlines()

    font = ImageFont.load_default()

    # Estimate wrap width in characters for a target pixel width.
    tmp_img = Image.new("RGB", (10, 10), "white")
    draw = ImageDraw.Draw(tmp_img)
    sample = "M" * 60
    sample_width = max(1, int(draw.textlength(sample, font=font)))
    char_width = max(1.0, sample_width / len(sample))
    max_chars = max(20, int((max_width_px - 2 * padding_px) / char_width))

    wrapped = _wrap_lines(lines, max_chars)

    # Compute final image size.
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = (bbox[3] - bbox[1]) + line_spacing_px

    # Determine actual needed width based on longest wrapped line.
    longest = max(wrapped, key=len, default="")
    text_width = int(draw.textlength(longest, font=font))
    width = min(max_width_px, max(text_width + 2 * padding_px, 600))
    height = max(200, padding_px * 2 + line_height * max(1, len(wrapped)))

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    y = padding_px
    for line in wrapped:
        draw.text((padding_px, y), line, fill="black", font=font)
        y += line_height

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-width", type=int, default=1400)
    parser.add_argument("--padding", type=int, default=20)
    parser.add_argument("--line-spacing", type=int, default=4)
    args = parser.parse_args()

    render_text_to_png(
        args.input,
        args.output,
        max_width_px=args.max_width,
        padding_px=args.padding,
        line_spacing_px=args.line_spacing,
    )


if __name__ == "__main__":
    main()
