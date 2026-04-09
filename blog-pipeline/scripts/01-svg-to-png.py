#!/usr/bin/env python3
"""
01-svg-to-png.py — Extract SVGs from HTML articles, convert to PNG, replace with <img> tags.

Why this exists:
  Sanity Portable Text has no SVG block type. If you leave <svg> blocks in the HTML,
  they get dropped or rendered as raw text. PNGs work because the publisher uploads
  them as Sanity image assets.

Usage:
  python3 01-svg-to-png.py <batch-directory>

Example:
  python3 01-svg-to-png.py ~/blog-batches/2026-04-08/

Outputs:
  - <batch-dir>/images/<article-stem>-chart-N.png  (1800px wide retina PNG)
  - Modifies the .html files in place to replace <figure class="viz"><svg>...</svg></figure>
    with <img src="..." alt="..."> tags.
"""
import sys
import re
from pathlib import Path

try:
    import cairosvg
except ImportError:
    print("ERROR: cairosvg not installed. Run: pip3 install --break-system-packages cairosvg")
    sys.exit(1)


SVG_PATTERN = re.compile(
    r'<figure\s+class="viz">\s*(<svg[^>]*>.*?</svg>)\s*</figure>|(<svg[^>]*>.*?</svg>)',
    re.DOTALL,
)

# Common SVG escaping mistakes that break cairosvg
SVG_AMPERSAND_FIXES = [
    (re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#)'), '&amp;'),
]


def fix_svg_xml(svg: str) -> str:
    """Fix common XML errors in hand-written SVGs (unescaped &, etc)."""
    # Only fix ampersands inside attribute values, not inside CDATA/comments
    for pattern, replacement in SVG_AMPERSAND_FIXES:
        svg = pattern.sub(replacement, svg)
    return svg


def convert_directory(batch_dir: Path) -> None:
    if not batch_dir.is_dir():
        print(f"ERROR: not a directory: {batch_dir}")
        sys.exit(1)

    img_dir = batch_dir / "images"
    img_dir.mkdir(exist_ok=True)

    total_pngs = 0
    total_files = 0

    for html_file in sorted(batch_dir.glob("*.html")):
        content = html_file.read_text()
        matches = list(SVG_PATTERN.finditer(content))

        if not matches:
            print(f"  no SVGs: {html_file.name}")
            continue

        total_files += 1
        print(f"  {html_file.name}: {len(matches)} SVGs")

        for i, match in enumerate(matches):
            svg_raw = match.group(1) or match.group(2)
            svg_fixed = fix_svg_xml(svg_raw)

            desc_match = re.search(r"<desc>(.*?)</desc>", svg_fixed)
            alt_text = (
                desc_match.group(1)
                if desc_match
                else f"Data visualization {i + 1}"
            )

            png_name = f"{html_file.stem}-chart-{i + 1}.png"
            png_path = img_dir / png_name

            try:
                cairosvg.svg2png(
                    bytestring=svg_fixed.encode("utf-8"),
                    write_to=str(png_path),
                    output_width=1800,
                )
                kb = png_path.stat().st_size // 1024
                print(f"    -> {png_name} ({kb}KB)")
                total_pngs += 1
            except Exception as e:
                print(f"    -> FAILED {png_name}: {e}")
                continue

            img_tag = f'<img src="{png_path}" alt="{alt_text}">'
            content = content.replace(match.group(0), img_tag)

        html_file.write_text(content)

    print(f"\nDone. {total_pngs} PNGs from {total_files} files in {batch_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 01-svg-to-png.py <batch-directory>")
        sys.exit(1)
    convert_directory(Path(sys.argv[1]).expanduser().resolve())
