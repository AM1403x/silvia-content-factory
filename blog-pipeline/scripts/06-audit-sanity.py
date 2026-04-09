#!/usr/bin/env python3
"""
06-audit-sanity.py — Audit every published post in Sanity staging for structural issues.

Why this exists:
  After publishing, verify that Sanity documents have the expected structure:
    - At least 1 image block
    - At least 1 table block
    - At least 3 h3 blocks (FAQ questions)
    - Excerpt that does NOT duplicate the first body block
    - No leaked CSS as paragraph text
    - CTA paragraph with cfosilvia.com link

Usage:
  SANITY_TOKEN=<token> python3 06-audit-sanity.py

Environment:
  SANITY_TOKEN       — Write token (required; auto-loaded from Silvia-Web/.env.development.local if present)
  SANITY_PROJECT_ID  — Defaults to htd46ya1
  SANITY_DATASET     — Defaults to staging
"""
import os
import sys
import json
import urllib.parse
import urllib.request
from pathlib import Path


def load_token_from_env_file() -> str:
    """Try to load SANITY_STAGING_WRITE_TOKEN from Silvia-Web/.env.development.local."""
    env_file = Path.home() / "Silvia-Web" / ".env.development.local"
    if not env_file.exists():
        return ""
    for line in env_file.read_text().splitlines():
        if line.startswith("SANITY_STAGING_WRITE_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def query(token: str, project_id: str, dataset: str, groq: str) -> dict:
    url = (
        f"https://{project_id}.api.sanity.io/v2025-02-19/data/query/{dataset}"
        f"?query={urllib.parse.quote(groq)}"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def audit_post(post: dict) -> list[str]:
    """Return a list of issues found (empty list = all good)."""
    issues = []
    slug = post.get("slug", {}).get("current", "?")
    excerpt = post.get("excerpt", "") or ""
    body = post.get("body") or []

    # Structure checks
    # NOTE: As of April 6, 2026, chart images are REMOVED from the pipeline
    # (see blog-pipeline/RULES.md). We actively flag image blocks as an ERROR,
    # not as a required element.
    imgs = [b for b in body if b.get("_type") == "image"]
    tables = [b for b in body if b.get("_type") == "table"]
    h3s = [b for b in body if b.get("_type") == "block" and b.get("style") == "h3"]

    if len(imgs) > 0:
        issues.append(f"UNEXPECTED_IMAGE({len(imgs)})")
    if len(tables) < 1:
        issues.append(f"NO_TABLE")
    if len(h3s) < 3:
        issues.append(f"LOW_FAQ({len(h3s)})")

    # Check for duplicate excerpt / first body paragraph
    first_text_block = next(
        (b for b in body if b.get("_type") == "block" and b.get("style") == "normal"),
        None,
    )
    if first_text_block:
        first_text = "".join(
            span.get("text", "") for span in first_text_block.get("children", [])
        ).strip()
        if excerpt and first_text and excerpt.strip() == first_text:
            issues.append("EXCERPT_DUPLICATES_FIRST_PARAGRAPH")

    # Check for CSS leakage in any text block
    body_text = " ".join(
        span.get("text", "")
        for block in body
        if block.get("_type") == "block"
        for span in block.get("children", [])
    )
    css_leak_markers = ("font-family:", "@media", "border-collapse", "max-width:")
    for marker in css_leak_markers:
        if marker in body_text:
            issues.append(f"CSS_LEAK({marker})")
            break

    # Check for CTA link
    has_cta = any(
        "cfosilvia.com" in link.get("href", "")
        for block in body
        if block.get("_type") == "block"
        for link in block.get("markDefs", []) or []
    )
    if not has_cta:
        issues.append("NO_CTA_LINK")

    # Check for banned disclaimer phrase
    banned_phrases = [
        "Consult a qualified professional",
        "consult a qualified professional",
    ]
    for phrase in banned_phrases:
        if phrase in body_text:
            issues.append(f'BANNED_PHRASE("{phrase}")')
            break

    return issues


def main():
    project_id = os.environ.get("SANITY_PROJECT_ID", "htd46ya1")
    dataset = os.environ.get("SANITY_DATASET", "staging")
    token = os.environ.get("SANITY_TOKEN") or load_token_from_env_file()

    if not token:
        print("ERROR: no SANITY_TOKEN (and none found in Silvia-Web/.env.development.local)")
        sys.exit(1)

    groq = (
        '*[_type=="post"]{title, slug, excerpt, body}'
        ' | order(publishedAt desc)'
    )

    try:
        result = query(token, project_id, dataset, groq)
    except Exception as e:
        print(f"ERROR: Sanity query failed: {e}")
        sys.exit(1)

    posts = result.get("result", [])
    print(f"=== AUDIT: {len(posts)} posts in {project_id}/{dataset} ===\n")

    total_issues = 0
    for i, post in enumerate(posts, 1):
        issues = audit_post(post)
        title = post.get("title", "?")[:60]
        if issues:
            print(f"FAIL {i:2} {title}")
            for issue in issues:
                print(f"     - {issue}")
            total_issues += len(issues)
        else:
            print(f"PASS {i:2} {title}")

    print(f"\n=== SUMMARY ===")
    print(f"Posts audited: {len(posts)}")
    print(f"Total issues:  {total_issues}")
    if total_issues > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
