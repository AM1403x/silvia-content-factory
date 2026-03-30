"""
CHECK 2 — Financial Compliance Scan

Scans article text for language that could constitute financial advice,
personalized recommendations, or guarantee claims. These patterns violate
SEC / FINRA disclosure norms and must be caught before publication.

Returns:
    {
        "passed": bool,           # True if no violations found
        "violations": [str, ...]  # list of matched violation descriptions
    }
"""

import re
from typing import Dict, List, Any


# ── Compliance regex patterns ────────────────────────────────────────────────
# Each tuple: (compiled pattern, human-readable description)
_COMPLIANCE_PATTERNS: List[tuple] = [
    (
        re.compile(r"\byou\s+should\s+(?:buy|sell|hold)\b", re.IGNORECASE),
        "Personalized directive: 'you should (buy/sell/hold)'",
    ),
    (
        re.compile(r"\bI\s+recommend\s+(?:buying|selling|holding)\b", re.IGNORECASE),
        "Personal recommendation: 'I recommend (buying/selling/holding)'",
    ),
    (
        re.compile(r"\bguaranteed\s+returns?\b", re.IGNORECASE),
        "Guarantee claim: 'guaranteed return(s)'",
    ),
    (
        re.compile(r"\brisk[\-\s]free\b", re.IGNORECASE),
        "Risk-free claim",
    ),
    (
        re.compile(r"\bcan'?t\s+lose\b", re.IGNORECASE),
        "No-loss claim: 'can't lose'",
    ),
    (
        re.compile(r"\bbuy\s+now\b", re.IGNORECASE),
        "Urgency directive: 'buy now'",
    ),
    (
        re.compile(r"\bsell\s+immediately\b", re.IGNORECASE),
        "Urgency directive: 'sell immediately'",
    ),
    (
        re.compile(r"\bmust\s+(?:buy|sell|hold)\b", re.IGNORECASE),
        "Imperative directive: 'must (buy/sell/hold)'",
    ),
    (
        re.compile(r"\bsure\s+(?:thing|bet)\b", re.IGNORECASE),
        "Certainty claim: 'sure thing/bet'",
    ),
]


def compliance_scan(text: str) -> Dict[str, Any]:
    """Scan *text* for financial compliance violations.

    Each pattern is checked independently. Every match is reported
    with context (the matched substring and its surrounding words).

    Returns:
        dict with keys: passed, violations
    """
    violations: List[str] = []

    for pattern, description in _COMPLIANCE_PATTERNS:
        for match in pattern.finditer(text):
            # Extract a context window: up to 40 chars before and after
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            context = text[start:end].replace("\n", " ").strip()
            violations.append(
                f"{description} -> '...{context}...'"
            )

    return {
        "passed": len(violations) == 0,
        "violations": violations,
    }


# ── CLI convenience ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python compliance_scan.py <file_path>")
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    result = compliance_scan(content)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
