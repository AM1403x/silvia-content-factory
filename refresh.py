"""
CFO Silvia Content Factory — Freshness Updater

Finds stale high-traffic articles and runs a lightweight delta refresh:
Researcher (delta mode) -> Writer (surgical update) -> scan -> Fact Checker (new data only).
"""

import json
import logging
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    FRESHNESS_VIEW_THRESHOLD,
    FRESHNESS_AGE_DAYS,
    FRESHNESS_MAX_PER_SESSION,
    OUTPUT_DIR,
    LOGS_DIR,
    DB_PATH,
    PROMPTS_DIR,
)
from db.init_db import get_connection, init_database


# ── Logging ──────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("silvia_refresh")
logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(
    LOGS_DIR / f"refresh_{date.today().isoformat()}.log",
    encoding="utf-8",
)
_fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(logging.Formatter("%(levelname)-8s | %(message)s"))
logger.addHandler(_fh)
logger.addHandler(_ch)


# ── Find stale articles ─────────────────────────────────────────────────────────

def find_stale_articles() -> list[dict]:
    """Query articles with page_views_7d > threshold and updated_at older than N days.

    Uses FRESHNESS_VIEW_THRESHOLD and FRESHNESS_AGE_DAYS from config.

    Returns:
        List of article dicts (id, title, url_slug, article_type, updated_at,
        page_views_7d, days_stale) sorted by page_views_7d descending.
    """
    if not DB_PATH.exists():
        logger.warning("Database not found at %s", DB_PATH)
        return []

    cutoff = (datetime.now() - timedelta(days=FRESHNESS_AGE_DAYS)).isoformat()

    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, title, url_slug, article_type, primary_keyword,
                      ticker, updated_at, page_views_7d, writer_variant
               FROM articles
              WHERE page_views_7d > ?
                AND updated_at < ?
                AND status = 'published'
              ORDER BY page_views_7d DESC""",
            (FRESHNESS_VIEW_THRESHOLD, cutoff),
        ).fetchall()

        results = []
        now = datetime.now()
        for row in rows:
            d = dict(row)
            updated = datetime.fromisoformat(d["updated_at"])
            d["days_stale"] = (now - updated).days
            results.append(d)

        return results
    finally:
        conn.close()


# ── Delta refresh pipeline ───────────────────────────────────────────────────────

def _prepare_delta_research_input(article: dict, work_dir: Path) -> Path:
    """Prepare the input for the Researcher agent in delta mode.

    Delta mode: only look for new data since the article was last updated.
    """
    brief = {
        "mode": "delta",
        "article_id": article["id"],
        "topic": article["title"],
        "article_type": article["article_type"],
        "primary_keyword": article["primary_keyword"],
        "ticker": article.get("ticker"),
        "last_updated": article["updated_at"],
        "instructions": (
            "DELTA MODE: Only research what has changed since "
            f"{article['updated_at']}. Look for new data points, "
            "updated statistics, recent events, and any corrections needed. "
            "Do NOT reproduce the full research -- only new/changed information."
        ),
    }
    path = work_dir / "delta_research_brief.json"
    path.write_text(json.dumps(brief, indent=2), encoding="utf-8")
    return path


def _prepare_surgical_writer_input(article: dict, delta_research_path: Path, work_dir: Path) -> Path:
    """Prepare the Writer input for a surgical update.

    Surgical update: modify only the sections affected by new data.
    """
    data = {
        "mode": "surgical_update",
        "article_id": article["id"],
        "article_type": article["article_type"],
        "writer_variant": article.get("writer_variant", "A"),
        "delta_research_path": str(delta_research_path),
        "instructions": (
            "SURGICAL UPDATE MODE: You are updating an existing article, "
            "not writing a new one. Only modify paragraphs where the data "
            "has changed. Preserve the article's structure, tone, and all "
            "sections that are still accurate. Update the dateModified."
        ),
    }
    path = work_dir / "surgical_writer_input.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _prepare_delta_factcheck_input(article: dict, work_dir: Path) -> Path:
    """Prepare the Fact Checker input for new data only."""
    data = {
        "mode": "delta",
        "article_id": article["id"],
        "instructions": (
            "DELTA FACT CHECK: Only verify newly added or modified claims. "
            "Skip any content that was previously verified and unchanged."
        ),
    }
    path = work_dir / "delta_factcheck_input.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _run_scan_on_updated_draft(draft_path: Path, article_type: str) -> tuple[bool, str]:
    """Lightweight structural scan of the updated draft."""
    if not draft_path.exists():
        return True, "No updated draft file to scan (step may be pending)."

    text = draft_path.read_text(encoding="utf-8")
    words = text.split()
    word_count = len(words)

    issues = []
    if word_count < 200:
        issues.append(f"Updated draft very short: {word_count} words.")
    if "[UNVERIFIED]" in text or "[NEEDS SOURCE]" in text:
        issues.append("Unverified claims present in updated draft.")

    if issues:
        return False, "Scan issues: " + "; ".join(issues)
    return True, f"Scan passed ({word_count} words)."


def refresh_article(article_id: str) -> dict:
    """Run a lightweight delta refresh on a single article.

    Pipeline: Researcher (delta) -> Writer (surgical) -> scan -> Fact Checker (delta)

    This function prepares all input files and prints instructions for
    Claude Code to process each step. It does NOT call Claude directly.

    Args:
        article_id: The articles.id to refresh.

    Returns:
        Dict with refresh status and file paths.
    """
    if not DB_PATH.exists():
        return {"status": "error", "message": "Database not found."}

    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT id, title, url_slug, article_type, primary_keyword,
                      ticker, updated_at, page_views_7d, writer_variant,
                      full_text
               FROM articles WHERE id = ?""",
            (article_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {"status": "error", "message": f"Article not found: {article_id}"}

    article = dict(row)
    slug = article["url_slug"]
    work_dir = OUTPUT_DIR / "refreshes" / date.today().isoformat() / slug
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("REFRESH: %s (%s)", article["title"], slug)
    logger.info("  Last updated: %s (%d days ago)",
                article["updated_at"],
                (datetime.now() - datetime.fromisoformat(article["updated_at"])).days)
    logger.info("  Page views (7d): %d", article["page_views_7d"])
    logger.info("=" * 60)

    # Save current article text for reference
    current_path = work_dir / "current_article.md"
    current_path.write_text(article.get("full_text", ""), encoding="utf-8")

    # Step 1: Delta Research
    research_path = _prepare_delta_research_input(article, work_dir)
    print(f"\n{'='*60}")
    print(f"  REFRESH STEP 1: DELTA RESEARCH")
    print(f"  Article: {article['title']}")
    print(f"  Input:   {research_path}")
    print(f"  Prompt:  prompts/agent_01_researcher.txt (use in DELTA mode)")
    print(f"  Output:  save to {work_dir}/delta_research_packet.json")
    print(f"{'='*60}\n")

    delta_research_output = work_dir / "delta_research_packet.json"

    # Step 2: Surgical Writer Update
    writer_path = _prepare_surgical_writer_input(article, delta_research_output, work_dir)
    print(f"  REFRESH STEP 2: SURGICAL WRITER UPDATE")
    print(f"  Input:   {writer_path}")
    print(f"  Prompt:  prompts/agent_03_writer.txt (use in SURGICAL mode)")
    print(f"  Output:  save to {work_dir}/updated_draft.md")
    print(f"{'='*60}\n")

    updated_draft = work_dir / "updated_draft.md"

    # Step 3: Scan
    print(f"  REFRESH STEP 3: AUTOMATED SCAN")
    print(f"  >> The orchestrator will scan {updated_draft} automatically.")
    print(f"{'='*60}\n")

    passed, scan_msg = _run_scan_on_updated_draft(updated_draft, article["article_type"])
    logger.info("Scan result: %s", scan_msg)

    # Step 4: Delta Fact Check
    factcheck_path = _prepare_delta_factcheck_input(article, work_dir)
    print(f"  REFRESH STEP 4: DELTA FACT CHECK")
    print(f"  Input:   {factcheck_path}")
    print(f"  Prompt:  prompts/agent_07_fact_checker.txt (use in DELTA mode)")
    print(f"  Output:  save to {work_dir}/delta_factcheck_result.json")
    print(f"{'='*60}\n")

    # Update the database timestamp
    now = datetime.now().isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET updated_at = ? WHERE id = ?",
            (now, article_id),
        )
        conn.commit()
    finally:
        conn.close()

    result = {
        "status": "refresh_initiated",
        "article_id": article_id,
        "slug": slug,
        "work_dir": str(work_dir),
        "steps": {
            "delta_research": str(research_path),
            "surgical_writer": str(writer_path),
            "scan": scan_msg,
            "delta_factcheck": str(factcheck_path),
        },
        "updated_at": now,
    }

    logger.info("Refresh initiated for %s. Work dir: %s", slug, work_dir)
    return result


def refresh_stale_batch(max_count: int = FRESHNESS_MAX_PER_SESSION) -> list[dict]:
    """Refresh up to max_count stale articles in a single session.

    Finds the highest-traffic stale articles and runs delta refreshes
    on each one.

    Args:
        max_count: Maximum number of articles to refresh (default from config).

    Returns:
        List of result dicts from refresh_article(), one per article.
    """
    stale = find_stale_articles()

    if not stale:
        logger.info("No stale articles found. Nothing to refresh.")
        return []

    batch = stale[:max_count]
    logger.info("Found %d stale articles; refreshing top %d by traffic.",
                len(stale), len(batch))

    results = []
    for i, article in enumerate(batch, start=1):
        logger.info("\n--- Refresh %d/%d ---", i, len(batch))
        result = refresh_article(article["id"])
        results.append(result)

    # Log summary
    initiated = sum(1 for r in results if r["status"] == "refresh_initiated")
    errors = sum(1 for r in results if r["status"] == "error")
    logger.info("\nRefresh batch complete: %d initiated, %d errors", initiated, errors)

    # Write batch log
    log_path = LOGS_DIR / f"refresh_batch_{date.today().isoformat()}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Batch log written to %s", log_path)

    return results


# ── CLI entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CFO Silvia Freshness Updater")
    subparsers = parser.add_subparsers(dest="command")

    # find: list stale articles
    sub_find = subparsers.add_parser("find", help="List stale articles")

    # refresh: refresh a single article
    sub_one = subparsers.add_parser("refresh", help="Refresh a single article")
    sub_one.add_argument("article_id", help="Article ID to refresh")

    # batch: refresh stale batch
    sub_batch = subparsers.add_parser("batch", help="Refresh a batch of stale articles")
    sub_batch.add_argument(
        "--max", type=int, default=FRESHNESS_MAX_PER_SESSION,
        help=f"Max articles to refresh (default: {FRESHNESS_MAX_PER_SESSION})",
    )

    args = parser.parse_args()

    if args.command == "find":
        stale = find_stale_articles()
        if stale:
            print(f"\nFound {len(stale)} stale articles:\n")
            for a in stale:
                print(f"  [{a['id'][:8]}] {a['title']}")
                print(f"           views_7d={a['page_views_7d']}  "
                      f"days_stale={a['days_stale']}  "
                      f"type={a['article_type']}")
        else:
            print("No stale articles found.")

    elif args.command == "refresh":
        result = refresh_article(args.article_id)
        print(f"\nResult: {json.dumps(result, indent=2)}")

    elif args.command == "batch":
        results = refresh_stale_batch(max_count=args.max)
        print(f"\nBatch complete: {len(results)} articles processed.")

    else:
        parser.print_help()
