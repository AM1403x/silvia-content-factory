"""
CHECK 3 — Post-Visualization Scan

After the Integrator agent merges SVG visualizations into the article,
this scan verifies that any NEW text the Integrator added (captions,
annotations, bridging sentences) also passes the simplifier checks.

Strategy:
    1. Strip all SVG blocks from both original and visualized text.
    2. Diff the two to isolate text added by the Integrator.
    3. Run post_simplifier_scan on ONLY the new text.

Returns:
    {
        "clean_text": str,      # visualized text with auto-fixes applied to new content
        "issues": [str, ...],   # issues found in Integrator-added text only
        "passed": bool,
        "new_text_chars": int   # length of new text found
    }
"""

import re
from typing import Dict, List, Any

from checks.post_simplifier_scan import post_simplifier_scan


# SVG block pattern: matches <svg ...>...</svg> including multiline content.
_SVG_BLOCK_RE = re.compile(
    r"<svg[\s\S]*?</svg>",
    re.IGNORECASE | re.DOTALL,
)

# Also strip HTML comments that the Integrator might use as markers.
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def _strip_svg(text: str) -> str:
    """Remove all SVG blocks and HTML comments from text."""
    stripped = _SVG_BLOCK_RE.sub("", text)
    stripped = _HTML_COMMENT_RE.sub("", stripped)
    return stripped


def _extract_new_text(original: str, visualized: str) -> str:
    """Find text in *visualized* that does not appear in *original*.

    Works by stripping SVGs from both, then finding paragraphs in the
    visualized version that are not present in the original. This catches
    captions, bridging sentences, and annotations added by the Integrator.
    """
    original_stripped = _strip_svg(original)
    visualized_stripped = _strip_svg(visualized)

    # Build a set of original paragraphs (normalized) for lookup.
    original_paras = {
        _normalize(p) for p in original_stripped.split("\n\n") if p.strip()
    }

    new_paragraphs: List[str] = []
    for para in visualized_stripped.split("\n\n"):
        stripped = para.strip()
        if not stripped:
            continue
        if _normalize(stripped) not in original_paras:
            new_paragraphs.append(stripped)

    return "\n\n".join(new_paragraphs)


def _normalize(text: str) -> str:
    """Normalize whitespace for comparison."""
    return " ".join(text.split()).lower().strip()


def post_viz_scan(
    original_text: str,
    visualized_text: str,
) -> Dict[str, Any]:
    """Run post-simplifier checks on text added by the Integrator.

    Args:
        original_text: The article BEFORE visualization integration.
        visualized_text: The article AFTER the Integrator merged SVGs.

    Returns:
        dict with keys: clean_text, issues, passed, new_text_chars
    """
    new_text = _extract_new_text(original_text, visualized_text)

    if not new_text.strip():
        return {
            "clean_text": visualized_text,
            "issues": [],
            "passed": True,
            "new_text_chars": 0,
        }

    # Run the simplifier scan on only the new text.
    scan_result = post_simplifier_scan(new_text)

    # If the scan produced a cleaned version of the new text, we need to
    # patch those fixes back into the full visualized article.
    clean_visualized = visualized_text
    if scan_result["clean_text"] != new_text:
        # Apply each fix: replace old new-text paragraphs with cleaned ones.
        old_paras = new_text.split("\n\n")
        new_paras = scan_result["clean_text"].split("\n\n")
        for old_p, new_p in zip(old_paras, new_paras):
            if old_p != new_p and old_p.strip():
                clean_visualized = clean_visualized.replace(
                    old_p.strip(), new_p.strip()
                )

    return {
        "clean_text": clean_visualized,
        "issues": scan_result["issues"],
        "passed": scan_result["passed"],
        "new_text_chars": len(new_text),
    }


# ── CLI convenience ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python post_viz_scan.py <original_file> <visualized_file>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        orig = f.read()
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        viz = f.read()

    result = post_viz_scan(orig, viz)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
