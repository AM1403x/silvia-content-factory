#!/usr/bin/env python3
"""
05-publish.py — Publish every article in a batch to Sanity staging.

Why this exists:
  The publisher script defaults to using the first <p> as the excerpt, which causes
  a visible duplicate paragraph on the blog page (excerpt rendered as intro, then
  body starts with the same paragraph). We force a short custom excerpt per article.

  Also consolidates the repetitive per-article npx tsx command into a single
  script driven by an excerpts.json config file.

Usage:
  python3 05-publish.py <batch-directory>

Requires:
  <batch-directory>/excerpts.json  — map of filename -> {excerpt, categories, published_at}
  Silvia-Web checked out at ~/Silvia-Web (or set SILVIA_WEB env var)
"""
import sys
import json
import os
import subprocess
from pathlib import Path

SILVIA_WEB = Path(os.environ.get("SILVIA_WEB", Path.home() / "Silvia-Web"))


def publish_one(html_path: Path, excerpt: str, categories: str, published_at: str) -> bool:
    cmd = [
        "npx", "tsx", "scripts/publish-blog-post-to-sanity.ts",
        "--html", str(html_path),
        "--excerpt", excerpt,
        "--categories", categories,
        "--published-at", published_at,
    ]
    try:
        result = subprocess.run(
            cmd, cwd=SILVIA_WEB, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            # Parse title from JSON output
            try:
                data = json.loads(result.stdout)
                print(f"  OK  {data.get('title', html_path.name)[:70]}")
                return True
            except json.JSONDecodeError:
                print(f"  OK  {html_path.name} (non-JSON response)")
                return True
        else:
            print(f"  FAIL {html_path.name}: {result.stderr.strip()[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT {html_path.name}")
        return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 05-publish.py <batch-directory>")
        sys.exit(1)

    batch_dir = Path(sys.argv[1]).expanduser().resolve()
    if not batch_dir.is_dir():
        print(f"ERROR: not a directory: {batch_dir}")
        sys.exit(1)

    excerpts_file = batch_dir / "excerpts.json"
    if not excerpts_file.exists():
        print(f"ERROR: missing {excerpts_file}")
        print("")
        print("Create excerpts.json with this shape:")
        print(json.dumps({
            "01-article-slug.html": {
                "excerpt": "100-150 char summary, NOT the first paragraph",
                "categories": "macro,jobs,fed",
                "published_at": "2026-04-08T09:00:00Z",
            }
        }, indent=2))
        sys.exit(1)

    if not SILVIA_WEB.is_dir():
        print(f"ERROR: Silvia-Web not found at {SILVIA_WEB}")
        print("Set SILVIA_WEB env var or check out the repo at ~/Silvia-Web")
        sys.exit(1)

    config = json.loads(excerpts_file.read_text())

    passed = 0
    failed = 0

    for html_file in sorted(batch_dir.glob("*.html")):
        if html_file.name not in config:
            print(f"  SKIP {html_file.name}: no excerpts.json entry")
            failed += 1
            continue

        entry = config[html_file.name]
        ok = publish_one(
            html_file,
            entry["excerpt"],
            entry.get("categories", ""),
            entry["published_at"],
        )
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\nDone. {passed} published, {failed} failed.")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
