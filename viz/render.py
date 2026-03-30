"""
CFO Silvia Content Factory — SVG-to-PNG Rendering

Uses Playwright to render SVGs and earnings cards to PNG images.
Provides both async and sync wrappers for all operations.
"""

import asyncio
import re
import os
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    VIZ_PNG_WIDTH,
    VIZ_PNG_HEIGHT,
    EARNINGS_CARD_WIDTH,
    EARNINGS_CARD_HEIGHT,
    EARNINGS_CARD_COLORS,
)


# ── SVG-to-PNG rendering ────────────────────────────────────────────────────────

async def render_svg_to_png(
    svg_content: str,
    output_path: str,
    width: int = VIZ_PNG_WIDTH,
    height: int = VIZ_PNG_HEIGHT,
) -> str:
    """Render an SVG string to a PNG file via Playwright.

    Creates a minimal HTML page containing the SVG, sets the viewport to the
    requested dimensions, and takes a full-page screenshot.

    Args:
        svg_content: Raw SVG markup string.
        output_path: Destination path for the PNG file.
        width: Viewport width in pixels (default from config).
        height: Viewport height in pixels (default from config).

    Returns:
        The absolute path of the written PNG file.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px;
    height: {height}px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #FFFFFF;
    overflow: hidden;
  }}
  svg {{
    max-width: 100%;
    max-height: 100%;
  }}
</style>
</head>
<body>
{svg_content}
</body>
</html>"""

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.set_content(html, wait_until="networkidle")
        await page.screenshot(path=str(output), full_page=False)
        await browser.close()

    return str(output.resolve())


def render_svg_to_png_sync(
    svg_content: str,
    output_path: str,
    width: int = VIZ_PNG_WIDTH,
    height: int = VIZ_PNG_HEIGHT,
) -> str:
    """Synchronous wrapper around render_svg_to_png."""
    return asyncio.run(render_svg_to_png(svg_content, output_path, width, height))


# ── Earnings card rendering ──────────────────────────────────────────────────────

def _build_earnings_card_html(
    ticker: str,
    eps_actual: str,
    eps_estimate: str,
    rev_actual: str,
    rev_estimate: str,
    beat_eps: bool = True,
    beat_rev: bool = True,
) -> str:
    """Build the HTML for an earnings card per the Content Playbook spec.

    Layout:
      - 1200x675px canvas, #0A0A0A background, white text
      - Ticker in 120px bold
      - EPS and Revenue lines in 52-64px
      - Green #22C55E for beats, red #EF4444 for misses
      - 80px gold #C9A84C bottom bar with branding
    """
    c = EARNINGS_CARD_COLORS
    eps_color = c["beat"] if beat_eps else c["miss"]
    rev_color = c["beat"] if beat_rev else c["miss"]
    eps_icon = "\u25B2" if beat_eps else "\u25BC"  # triangle up / down
    rev_icon = "\u25B2" if beat_rev else "\u25BC"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {EARNINGS_CARD_WIDTH}px;
    height: {EARNINGS_CARD_HEIGHT}px;
    background: {c["background"]};
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: {c["text"]};
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}
  .main {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 60px 80px 30px;
  }}
  .ticker {{
    font-size: 120px;
    font-weight: 900;
    letter-spacing: -2px;
    line-height: 1.0;
    margin-bottom: 30px;
  }}
  .metric {{
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 18px;
  }}
  .metric-label {{
    font-size: 28px;
    font-weight: 400;
    color: #9CA3AF;
    min-width: 160px;
  }}
  .metric-value {{
    font-size: 64px;
    font-weight: 700;
    letter-spacing: -1px;
  }}
  .metric-estimate {{
    font-size: 32px;
    font-weight: 400;
    color: #6B7280;
    margin-left: 8px;
  }}
  .metric-icon {{
    font-size: 36px;
    margin-left: 4px;
  }}
  .bottom-bar {{
    height: 80px;
    background: {c["gold"]};
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 80px;
  }}
  .bottom-bar .cta {{
    font-size: 28px;
    font-weight: 700;
    color: {c["background"]};
  }}
  .bottom-bar .handle {{
    font-size: 24px;
    font-weight: 600;
    color: {c["background"]};
  }}
</style>
</head>
<body>
<div class="main">
  <div class="ticker">${ticker.upper()}</div>
  <div class="metric">
    <span class="metric-label">EPS</span>
    <span class="metric-value" style="color:{eps_color}">{eps_actual}</span>
    <span class="metric-icon" style="color:{eps_color}">{eps_icon}</span>
    <span class="metric-estimate">est. {eps_estimate}</span>
  </div>
  <div class="metric">
    <span class="metric-label">Revenue</span>
    <span class="metric-value" style="color:{rev_color}">{rev_actual}</span>
    <span class="metric-icon" style="color:{rev_color}">{rev_icon}</span>
    <span class="metric-estimate">est. {rev_estimate}</span>
  </div>
</div>
<div class="bottom-bar">
  <span class="cta">Show more &rarr;</span>
  <span class="handle">@CFOSilvia</span>
</div>
</body>
</html>"""


async def render_earnings_card(
    ticker: str,
    eps_actual: str,
    eps_estimate: str,
    rev_actual: str,
    rev_estimate: str,
    output_path: str,
    beat_eps: bool = True,
    beat_rev: bool = True,
) -> str:
    """Generate and render an earnings image card to PNG.

    Follows Content Playbook specs: 1200x675, dark background, green/red for
    beat/miss, gold branding bar at the bottom.

    Returns:
        The absolute path of the written PNG file.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    html = _build_earnings_card_html(
        ticker, eps_actual, eps_estimate, rev_actual, rev_estimate,
        beat_eps, beat_rev,
    )

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": EARNINGS_CARD_WIDTH, "height": EARNINGS_CARD_HEIGHT},
        )
        await page.set_content(html, wait_until="networkidle")
        await page.screenshot(path=str(output), full_page=False)
        await browser.close()

    return str(output.resolve())


def render_earnings_card_sync(
    ticker: str,
    eps_actual: str,
    eps_estimate: str,
    rev_actual: str,
    rev_estimate: str,
    output_path: str,
    beat_eps: bool = True,
    beat_rev: bool = True,
) -> str:
    """Synchronous wrapper around render_earnings_card."""
    return asyncio.run(render_earnings_card(
        ticker, eps_actual, eps_estimate, rev_actual, rev_estimate,
        output_path, beat_eps, beat_rev,
    ))


# ── SVG extraction from Markdown ────────────────────────────────────────────────

_SVG_BLOCK_RE = re.compile(
    r"```svg\s*\n(.*?)```",
    re.DOTALL,
)

_SVG_INLINE_RE = re.compile(
    r"(<svg[\s\S]*?</svg>)",
    re.IGNORECASE,
)


def extract_svgs_from_markdown(markdown_text: str) -> list[str]:
    """Extract all SVG blocks from a Markdown article.

    Looks for both fenced ```svg code blocks and inline <svg> tags.
    Deduplicates while preserving order.

    Returns:
        List of SVG strings found in the markdown.
    """
    found: list[str] = []
    seen: set[str] = set()

    # 1) Fenced ```svg blocks
    for match in _SVG_BLOCK_RE.finditer(markdown_text):
        svg = match.group(1).strip()
        if svg not in seen:
            found.append(svg)
            seen.add(svg)

    # 2) Inline <svg> elements not already captured
    for match in _SVG_INLINE_RE.finditer(markdown_text):
        svg = match.group(1).strip()
        if svg not in seen:
            found.append(svg)
            seen.add(svg)

    return found


# ── Batch rendering for an article ──────────────────────────────────────────────

async def render_all_article_vizzes(
    article_slug: str,
    markdown_text: str,
    output_dir: str,
) -> list[str]:
    """Extract SVGs from a Markdown article and render each to PNG.

    Files are named <article_slug>-viz-1.png, <article_slug>-viz-2.png, etc.

    Args:
        article_slug: URL slug for the article (used in filenames).
        markdown_text: Full Markdown content of the article.
        output_dir: Directory where PNGs will be saved.

    Returns:
        List of absolute paths to the rendered PNG files.
    """
    svgs = extract_svgs_from_markdown(markdown_text)
    if not svgs:
        return []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    # Use a single browser instance for all renders
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        for i, svg in enumerate(svgs, start=1):
            filename = f"{article_slug}-viz-{i}.png"
            filepath = out / filename

            html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {VIZ_PNG_WIDTH}px;
    height: {VIZ_PNG_HEIGHT}px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #FFFFFF;
    overflow: hidden;
  }}
  svg {{ max-width: 100%; max-height: 100%; }}
</style>
</head>
<body>
{svg}
</body>
</html>"""

            page = await browser.new_page(
                viewport={"width": VIZ_PNG_WIDTH, "height": VIZ_PNG_HEIGHT},
            )
            await page.set_content(html, wait_until="networkidle")
            await page.screenshot(path=str(filepath), full_page=False)
            await page.close()
            paths.append(str(filepath.resolve()))

        await browser.close()

    return paths


def render_all_article_vizzes_sync(
    article_slug: str,
    markdown_text: str,
    output_dir: str,
) -> list[str]:
    """Synchronous wrapper around render_all_article_vizzes."""
    return asyncio.run(render_all_article_vizzes(article_slug, markdown_text, output_dir))
