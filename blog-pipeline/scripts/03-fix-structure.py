#!/usr/bin/env python3
"""
03-fix-structure.py — Reorder CTA before Sources, append canonical disclaimer.

Why this exists:
  Articles need a consistent ending structure:
    1. ... (article body)
    2. <h2>Frequently Asked Questions</h2>
       <h3>...</h3><p>...</p>
    3. <p>What does this mean for your portfolio? <a href=...>Ask Silvia</a>.</p>  <-- CTA
    4. <h2>Sources</h2>
       <ul><li><a>...</a></li>...</ul>
    5. <p><em>Disclaimer...</em></p>

  Readers don't scroll past the source list, so the CTA must come BEFORE Sources.
  The disclaimer stays at the very end as a footer.

Usage:
  python3 03-fix-structure.py <batch-directory>
"""
import sys
import re
from pathlib import Path

CTA = (
    '<p>What does this mean for your portfolio? '
    '<a href="https://cfosilvia.com">Ask Silvia</a>.</p>'
)

DISCLAIMER = (
    '<p><em>This content is for informational purposes only. '
    "It is not financial, investment, or legal advice. "
    'Past performance does not guarantee future results.</em></p>'
)

# Patterns to remove (any existing CTAs, disclaimers, or div-wrapped versions)
REMOVE_PATTERNS = [
    re.compile(
        r'<p[^>]*>\s*What does this mean for your portfolio\?\s*'
        r'<a[^>]*>Ask Silvia</a>\.?\s*</p>\s*',
        re.IGNORECASE,
    ),
    re.compile(
        r'<p[^>]*>\s*Own [^<]*</a>[^<]*</p>\s*',
        re.IGNORECASE,
    ),
    re.compile(
        r'<p[^>]*>\s*<em>\s*This content is for informational purposes'
        r'[^<]*</em>\s*</p>\s*',
        re.IGNORECASE,
    ),
    re.compile(
        r'<div\s+class="cta"[^>]*>.*?</div>\s*',
        re.DOTALL | re.IGNORECASE,
    ),
    re.compile(
        r'<div\s+class="disclaimer"[^>]*>.*?</div>\s*',
        re.DOTALL | re.IGNORECASE,
    ),
]


def fix_structure(content: str) -> str:
    # Remove all existing CTAs and disclaimers
    for pattern in REMOVE_PATTERNS:
        content = pattern.sub("", content)

    content = content.rstrip()

    # Find Sources <h2> and insert CTA right before it
    sources_match = re.search(
        r"(<h2[^>]*>\s*Sources?\s*</h2>)", content, re.IGNORECASE
    )

    if sources_match:
        idx = sources_match.start()
        content = (
            content[:idx].rstrip()
            + f"\n\n{CTA}\n\n"
            + content[idx:]
        )
        # Disclaimer at the very end (after Sources list)
        content = content.rstrip() + f"\n\n{DISCLAIMER}\n"
    else:
        # No Sources section: put CTA + disclaimer at the end
        content = content.rstrip() + f"\n\n{CTA}\n\n{DISCLAIMER}\n"

    return content


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 03-fix-structure.py <batch-directory>")
        sys.exit(1)

    batch_dir = Path(sys.argv[1]).expanduser().resolve()
    if not batch_dir.is_dir():
        print(f"ERROR: not a directory: {batch_dir}")
        sys.exit(1)

    fixed = 0
    for html_file in sorted(batch_dir.glob("*.html")):
        original = html_file.read_text()
        new_content = fix_structure(original)
        if new_content != original:
            html_file.write_text(new_content)
            print(f"  fixed structure: {html_file.name}")
            fixed += 1
        else:
            print(f"  unchanged: {html_file.name}")

    print(f"\nDone. {fixed} files fixed in {batch_dir}")


if __name__ == "__main__":
    main()
