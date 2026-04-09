#!/usr/bin/env python3
"""
02-clean-html.py — Strip wrapper tags, leaked CSS, and metadata lines from articles.

Why this exists:
  Some article generators wrap output in <!DOCTYPE><html><head><style>...</style></head><body>.
  Sanity's HTML-to-Portable-Text converter strips html/body tags but dumps <style> content
  as paragraph text. The blog page renders raw CSS rules at the top.

  Some articles also start with a metadata line like "<p><strong>April 4, 2026</strong> | How-To</p>"
  which the publisher uses as the excerpt instead of the actual lead sentence.

Usage:
  python3 02-clean-html.py <batch-directory>
"""
import sys
import re
from pathlib import Path

# Patterns that get stripped entirely
WRAPPER_PATTERNS = [
    re.compile(r"<!DOCTYPE[^>]*>", re.IGNORECASE),
    re.compile(r"</?html[^>]*>", re.IGNORECASE),
    re.compile(r"<head[^>]*>.*?</head>", re.DOTALL | re.IGNORECASE),
    re.compile(r"</?body[^>]*>", re.IGNORECASE),
    re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<meta[^>]*>", re.IGNORECASE),
    re.compile(r"<link[^>]*>", re.IGNORECASE),
    re.compile(r"<title[^>]*>.*?</title>", re.DOTALL | re.IGNORECASE),
    # As of April 6, 2026: NO chart images. Strip any img/svg/figure that
    # slipped through from the writer. See RULES.md for the rationale.
    re.compile(r"<img[^>]*>\s*", re.IGNORECASE),
    re.compile(r"<svg[^>]*>.*?</svg>\s*", re.DOTALL | re.IGNORECASE),
    re.compile(r"<figure[^>]*>.*?</figure>\s*", re.DOTALL | re.IGNORECASE),
]

# Banned phrases that must never appear in article content
BANNED_PHRASES = [
    re.compile(
        r"[^.]*(?:Always c|C)onsult a qualified professional[^.]*\.\s*",
        re.IGNORECASE,
    ),
]

MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)


def extract_body(content: str) -> str:
    """Extract content inside <body>...</body> if present, else return as-is."""
    body_match = re.search(
        r"<body[^>]*>(.*?)</body>", content, re.DOTALL | re.IGNORECASE
    )
    if body_match:
        return body_match.group(1).strip()
    return content


def strip_wrappers(content: str) -> str:
    """Remove all DOCTYPE/html/head/style/script/meta/link/title elements
    AND any chart-related img/svg/figure tags (banned as of 2026-04-06)."""
    for pattern in WRAPPER_PATTERNS:
        content = pattern.sub("", content)
    return content


def strip_banned_phrases(content: str) -> str:
    """Remove sentences containing banned phrases like
    'consult a qualified professional'. See RULES.md."""
    for pattern in BANNED_PHRASES:
        content = pattern.sub("", content)
    return content


def strip_first_paragraph_metadata(content: str) -> str:
    """If the first <p> after <h1> looks like a metadata strip
    (date + pipe + category), remove it so the real lead becomes the excerpt."""
    h1_then_p = re.search(
        r"(<h1[^>]*>.*?</h1>)\s*(<p[^>]*>.*?</p>)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if not h1_then_p:
        return content

    first_p_html = h1_then_p.group(2)
    plain = re.sub(r"<[^>]+>", "", first_p_html).strip()

    has_pipe = "|" in plain
    has_date = bool(
        re.search(rf"({MONTHS})\s+\d+,\s*\d{{4}}", plain, re.IGNORECASE)
    )
    is_short = len(plain) < 100

    if has_pipe and has_date and is_short:
        return content.replace(h1_then_p.group(0), h1_then_p.group(1), 1)
    return content


def clean_file(html_file: Path) -> bool:
    original = html_file.read_text()

    cleaned = extract_body(original) if "<body" in original.lower() else original
    cleaned = strip_wrappers(cleaned)
    cleaned = strip_first_paragraph_metadata(cleaned)
    cleaned = strip_banned_phrases(cleaned)

    # Collapse blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip() + "\n"

    if cleaned != original:
        html_file.write_text(cleaned)
        return True
    return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 02-clean-html.py <batch-directory>")
        sys.exit(1)

    batch_dir = Path(sys.argv[1]).expanduser().resolve()
    if not batch_dir.is_dir():
        print(f"ERROR: not a directory: {batch_dir}")
        sys.exit(1)

    cleaned_count = 0
    for html_file in sorted(batch_dir.glob("*.html")):
        if clean_file(html_file):
            print(f"  cleaned: {html_file.name}")
            cleaned_count += 1
        else:
            print(f"  unchanged: {html_file.name}")

    print(f"\nDone. {cleaned_count} files cleaned in {batch_dir}")


if __name__ == "__main__":
    main()
