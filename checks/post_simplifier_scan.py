"""
CHECK 1 — Post-Simplifier Scan

Runs after the Simplifier agent rewrites the article. Catches:
  - Banned AI-slop words (full list from the Content Playbook)
  - Em dashes (replaced with commas)
  - Curly/smart quotes (replaced with straight quotes)
  - Single-sentence paragraphs longer than 5 words

Returns:
    {
        "clean_text": str,      # text with auto-fixes applied
        "issues": [str, ...],   # human-readable list of issues found
        "passed": bool           # True only if zero issues remain after fixes
    }
"""

import re
from typing import Dict, List, Any


# ── Complete banned word list ────────────────────────────────────────────────
# Every entry from the CFO Silvia Content Playbook. Do NOT abbreviate.
BANNED_WORDS: List[str] = [
    "additionally",
    "align with",
    "at its core",
    "authored",
    "beacon",
    "bears mentioning",
    "boasts",
    "bolstered",
    "breathtaking",
    "bustling",
    "catalyst",
    "commitment to",
    "comprehensive",
    "contributing to",
    "crucial",
    "cutting-edge",
    "deeply rooted",
    "delve",
    "elevate",
    "emanate",
    "empower",
    "emphasizing",
    "encompassing",
    "endeavor",
    "enduring",
    "enhance",
    "enigmatic",
    "ensuring",
    "evolving landscape",
    "exemplifies",
    "facilitate",
    "focal point",
    "foster",
    "fostering",
    "furthermore",
    "game-changer",
    "garner",
    "genuinely",
    "groundbreaking",
    "here's where it gets interesting",
    "highlight",
    "holistic",
    "honestly",
    "illuminates",
    "indelible mark",
    "in the heart of",
    "in the realm of",
    "interplay",
    "intricate",
    "intricacies",
    "it turns out",
    "it's worth noting",
    "key",
    "landscape",
    "leverage",
    "marks a shift",
    "merits attention",
    "meticulous",
    "meticulously",
    "moreover",
    "multifaceted",
    "must-visit",
    "myriad",
    "navigate",
    "nestled",
    "noteworthy",
    "notably",
    "nuanced",
    "paradigm",
    "particularly noteworthy",
    "pertaining to",
    "pivotal",
    "plethora",
    "points to a broader",
    "prior to",
    "profound",
    "reflects broader",
    "regarding",
    "renowned",
    "rich",
    "robust",
    "seamless",
    "serves as",
    "setting the stage for",
    "sheds light on",
    "showcasing",
    "signals",
    "speaks to",
    "spearhead",
    "stands as",
    "straightforward",
    "streamline",
    "striking",
    "stunning",
    "synergy",
    "tapestry",
    "testament",
    "transformative",
    "underlines",
    "underscore",
    "utilize",
    "valuable",
    "vibrant",
    "what stands out",
    "worth highlighting",
]

# Pre-compile patterns: word-boundary match, case-insensitive.
# Sort longest-first so multi-word phrases are matched before sub-phrases.
_SORTED_BANNED = sorted(BANNED_WORDS, key=len, reverse=True)
_BANNED_PATTERNS = [
    (word, re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE))
    for word in _SORTED_BANNED
]

# Em dash: Unicode \u2014 and the double-hyphen stand-in
_EM_DASH_RE = re.compile(r"\u2014|--")

# Curly / smart quotes
_CURLY_DOUBLE_RE = re.compile(r"[\u201C\u201D]")   # left/right double
_CURLY_SINGLE_RE = re.compile(r"[\u2018\u2019]")   # left/right single

# Sentence-end heuristic: period, question mark, or exclamation mark
# followed by optional closing quote/paren, then end-of-string.
_SENTENCE_END_RE = re.compile(r"[.!?]['\"\)\]]*$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _count_sentences(paragraph: str) -> int:
    """Estimate the number of sentences in a paragraph."""
    stripped = paragraph.strip()
    if not stripped:
        return 0
    sentences = _SENTENCE_SPLIT_RE.split(stripped)
    # Filter out fragments that don't end with sentence-ending punctuation
    return max(1, len([s for s in sentences if s.strip()]))


def _word_count(text: str) -> int:
    """Count whitespace-delimited words."""
    return len(text.split())


def post_simplifier_scan(text: str) -> Dict[str, Any]:
    """Run all post-simplifier checks on *text*.

    Auto-fixes are applied in this order:
        1. Em dash -> comma
        2. Curly quotes -> straight quotes
        3. Banned words flagged (NOT auto-removed; requires human review)

    Single-sentence paragraphs >5 words are flagged but not auto-fixed.

    Returns:
        dict with keys: clean_text, issues, passed
    """
    issues: List[str] = []
    clean = text

    # ── Fix 1: Em dashes -> commas ───────────────────────────────────────────
    em_dash_count = len(_EM_DASH_RE.findall(clean))
    if em_dash_count:
        clean = _EM_DASH_RE.sub(",", clean)
        issues.append(f"Replaced {em_dash_count} em dash(es) with commas")

    # ── Fix 2: Curly quotes -> straight quotes ───────────────────────────────
    curly_double_count = len(_CURLY_DOUBLE_RE.findall(clean))
    curly_single_count = len(_CURLY_SINGLE_RE.findall(clean))
    if curly_double_count:
        clean = _CURLY_DOUBLE_RE.sub('"', clean)
        issues.append(
            f"Replaced {curly_double_count} curly double quote(s) with straight quotes"
        )
    if curly_single_count:
        clean = _CURLY_SINGLE_RE.sub("'", clean)
        issues.append(
            f"Replaced {curly_single_count} curly single quote(s) with straight quotes"
        )

    # ── Check 3: Banned words ────────────────────────────────────────────────
    banned_found: List[str] = []
    for word, pattern in _BANNED_PATTERNS:
        matches = pattern.findall(clean)
        if matches:
            banned_found.append(f'"{word}" x{len(matches)}')

    if banned_found:
        issues.append(f"Banned words found: {', '.join(banned_found)}")

    # ── Check 4: Single-sentence paragraphs (skip headings/SVG) ──────────────
    paragraphs = clean.split("\n\n")
    single_sentence_flags: List[str] = []
    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            continue
        # Skip headings, SVG blocks, horizontal rules, metadata lines
        if stripped.startswith("#") or stripped.startswith("<svg") or stripped == "---":
            continue
        if stripped.startswith("Last updated:") or stripped.startswith("Want Silvia"):
            continue
        sentence_count = _count_sentences(stripped)
        wc = _word_count(stripped)
        if sentence_count == 1 and wc > 5:
            preview = " ".join(stripped.split()[:8]) + "..."
            single_sentence_flags.append(f'P{i + 1} ({wc}w): "{preview}"')

    if single_sentence_flags:
        issues.append(
            f"Single-sentence paragraphs (>5 words): "
            f"{'; '.join(single_sentence_flags)}"
        )

    # ── Check 5: Formatting issues (HARD FAILS) ────────────────────────────
    # Strip SVG blocks before checking formatting
    text_no_svg = re.sub(r'<svg[\s\S]*?</svg>', '', clean)

    # Meta cruft in body
    meta_patterns = [r'\*\*Subtitle:\*\*', r'\*\*Meta description:\*\*',
                     r'\*\*Estimated read time:\*\*', r'\*\*Read time:\*\*',
                     r'\*\*Ticker:\*\*', r'\*\*Price:\*\*', r'\*\*Verdict:\*\*',
                     r'\*\*Market Cap:\*\*']
    for pat in meta_patterns:
        if re.search(pat, text_no_svg):
            clean = re.sub(pat + r'[^\n]*\n?', '', clean)
            issues.append(f"FORMATTING: Removed meta cruft matching {pat}")

    # Bold-header-colon lists
    bhc = re.findall(r'\*\*[A-Z][^*]{2,30}:\*\*\s', text_no_svg)
    if len(bhc) > 1:
        issues.append(f"FORMATTING: {len(bhc)} bold-header-colon patterns found (Pattern 15 violation)")

    # Bold FAQ questions (should be ### headings)
    bold_faqs = re.findall(r'^\*\*[^*]*\?\*\*\s*$', text_no_svg, re.MULTILINE)
    if bold_faqs:
        # Auto-fix: convert to ### headings
        clean = re.sub(r'^\*\*([^*]+\?)\*\*\s*$', r'### \1', clean, flags=re.MULTILINE)
        issues.append(f"FORMATTING: Converted {len(bold_faqs)} bold FAQ questions to ### headings")

    # Bold sentence openers (**Sentence.**  Text continues)
    bold_sents = re.findall(r'\*\*[A-Z][^*]{3,80}\.\*\*', text_no_svg)
    if bold_sents:
        clean = re.sub(r'\*\*([A-Z][^*]{3,80}\.)\*\*', r'\1', clean)
        issues.append(f"FORMATTING: Removed bold from {len(bold_sents)} sentence openers")

    # Raw URLs
    non_svg_urls = re.findall(r'https?://\S+', text_no_svg)
    if non_svg_urls:
        issues.append(f"FORMATTING: {len(non_svg_urls)} raw URLs found in article body")

    # Exclamation marks
    exc_count = text_no_svg.count('!')
    if exc_count > 0:
        clean = re.sub(r'(?<![<>])!(?![->])', '.', clean)  # Don't touch SVG/HTML
        issues.append(f"FORMATTING: Replaced {exc_count} exclamation mark(s) with periods")

    # Version block
    first_lines = clean[:500].lower()
    if 'last updated' not in first_lines:
        issues.append("FORMATTING: Missing 'Last updated:' version block near top")

    passed = len(issues) == 0

    return {
        "clean_text": clean,
        "issues": issues,
        "passed": passed,
    }


# ── CLI convenience ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python post_simplifier_scan.py <file_path>")
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    result = post_simplifier_scan(content)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
