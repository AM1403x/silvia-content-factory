"""
Dedup Engine — Main deduplication gate for the CFO Silvia content factory.

Takes a proposed article brief and checks it against the SQLite database
across three dimensions:

    Check 1 — Exact keyword match:
        Same primary_keyword already published?
        - Updated within 7 days   -> REJECT (too fresh)
        - Updated 7-30 days ago   -> route to UPDATE flow
        - Updated >30 days ago    -> allow NEW article + queue 301 redirect

    Check 2 — Semantic similarity:
        Compare embedding of proposed summary against same-cluster articles.
        - >0.92  -> BLOCK (near-duplicate)
        - 0.85-0.92 -> FLAG for human review
        - <0.85  -> CLEAR

    Check 3 — Topic rotation / cooldown:
        Enforce minimum days between articles of the same type on the same
        topic/ticker, per the cooldown schedule in config.

Returns a DedupResult dataclass.
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np

# Ensure project root is on the path.
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    SEMANTIC_BLOCK_THRESHOLD,
    SEMANTIC_FLAG_THRESHOLD,
    ROTATION_COOLDOWNS,
)
from db.init_db import get_connection
from dedup.embedding import get_embedding, cosine_similarity


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class DedupResult:
    """Outcome of the dedup check."""
    cleared: bool                             # True = safe to proceed
    action: str                               # "new" | "update" | "block" | "flag"
    reason: str                               # human-readable explanation
    similar_articles: List[dict] = field(default_factory=list)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _days_since(dt_str: str) -> float:
    """Return days elapsed since an ISO-format datetime string."""
    dt = datetime.fromisoformat(dt_str)
    return (datetime.utcnow() - dt).total_seconds() / 86400


def _deserialize_embedding(blob: bytes) -> Optional[np.ndarray]:
    """Convert a stored BLOB back to a numpy array, or None."""
    if blob is None:
        return None
    return np.frombuffer(blob, dtype=np.float32)


# ── Check implementations ────────────────────────────────────────────────────

def _check_exact_keyword(
    primary_keyword: str,
    conn,
) -> Optional[DedupResult]:
    """Check 1: Exact primary_keyword match."""
    row = conn.execute(
        """
        SELECT id, title, url_slug, updated_at, article_type
        FROM articles
        WHERE primary_keyword = ? AND status = 'published'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (primary_keyword,),
    ).fetchone()

    if row is None:
        return None  # No match; continue to next check.

    days = _days_since(row["updated_at"])
    existing = {
        "id": row["id"],
        "title": row["title"],
        "url_slug": row["url_slug"],
        "updated_at": row["updated_at"],
        "days_ago": round(days, 1),
    }

    if days <= 7:
        return DedupResult(
            cleared=False,
            action="block",
            reason=(
                f"Exact keyword '{primary_keyword}' was published/updated "
                f"{days:.0f} days ago (within 7-day window). "
                f"Existing article: '{row['title']}'"
            ),
            similar_articles=[existing],
        )
    elif days <= 30:
        return DedupResult(
            cleared=True,
            action="update",
            reason=(
                f"Exact keyword '{primary_keyword}' exists but was last "
                f"updated {days:.0f} days ago. Route to UPDATE flow for "
                f"'{row['title']}' instead of creating a new article."
            ),
            similar_articles=[existing],
        )
    else:
        return DedupResult(
            cleared=True,
            action="new",
            reason=(
                f"Exact keyword '{primary_keyword}' exists but is stale "
                f"({days:.0f} days old). Proceed with new article and "
                f"queue 301 redirect from old slug '{row['url_slug']}'."
            ),
            similar_articles=[existing],
        )


def _check_semantic_similarity(
    summary: str,
    cluster_id: Optional[str],
    conn,
) -> Optional[DedupResult]:
    """Check 2: Semantic similarity against same-cluster articles."""
    proposed_embedding = get_embedding(summary)

    # Fetch articles in the same cluster (or all if no cluster).
    if cluster_id:
        rows = conn.execute(
            """
            SELECT id, title, url_slug, updated_at, embedding, summary_200
            FROM articles
            WHERE cluster_id = ? AND status = 'published' AND embedding IS NOT NULL
            """,
            (cluster_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, title, url_slug, updated_at, embedding, summary_200
            FROM articles
            WHERE status = 'published' AND embedding IS NOT NULL
            """,
        ).fetchall()

    if not rows:
        return None  # No articles to compare against.

    similar: List[dict] = []
    max_score = 0.0
    max_article = None

    for row in rows:
        stored_emb = _deserialize_embedding(row["embedding"])
        if stored_emb is None:
            continue

        score = cosine_similarity(proposed_embedding, stored_emb)
        if score > SEMANTIC_FLAG_THRESHOLD:
            entry = {
                "id": row["id"],
                "title": row["title"],
                "url_slug": row["url_slug"],
                "similarity": round(score, 4),
                "summary_200": row["summary_200"],
            }
            similar.append(entry)

        if score > max_score:
            max_score = score
            max_article = row

    if max_score >= SEMANTIC_BLOCK_THRESHOLD:
        return DedupResult(
            cleared=False,
            action="block",
            reason=(
                f"Semantic similarity {max_score:.3f} >= {SEMANTIC_BLOCK_THRESHOLD} "
                f"with '{max_article['title']}'. Near-duplicate detected."
            ),
            similar_articles=similar,
        )
    elif max_score >= SEMANTIC_FLAG_THRESHOLD:
        return DedupResult(
            cleared=True,
            action="flag",
            reason=(
                f"Semantic similarity {max_score:.3f} is between "
                f"{SEMANTIC_FLAG_THRESHOLD} and {SEMANTIC_BLOCK_THRESHOLD}. "
                f"Closest match: '{max_article['title']}'. "
                f"Flagged for human review."
            ),
            similar_articles=similar,
        )

    return None  # Below flag threshold; clear.


def _check_topic_rotation(
    article_type: str,
    primary_keyword: str,
    ticker: Optional[str],
    conn,
) -> Optional[DedupResult]:
    """Check 3: Topic rotation cooldown enforcement."""
    cooldown_days = ROTATION_COOLDOWNS.get(article_type)
    if cooldown_days is None:
        return None  # Unknown type; no cooldown rule.

    cutoff = (datetime.utcnow() - timedelta(days=cooldown_days)).isoformat()

    # Check by keyword + type.
    params = [article_type, primary_keyword, cutoff]
    query = """
        SELECT id, title, url_slug, updated_at
        FROM articles
        WHERE article_type = ?
          AND primary_keyword = ?
          AND updated_at > ?
          AND status = 'published'
        ORDER BY updated_at DESC
        LIMIT 1
    """
    row = conn.execute(query, params).fetchone()

    # For ticker articles, also check by ticker symbol.
    if row is None and ticker and article_type == "ticker":
        row = conn.execute(
            """
            SELECT id, title, url_slug, updated_at
            FROM articles
            WHERE article_type = 'ticker'
              AND ticker = ?
              AND updated_at > ?
              AND status = 'published'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (ticker, cutoff),
        ).fetchone()

    if row is None:
        return None  # Cooldown clear.

    days = _days_since(row["updated_at"])
    return DedupResult(
        cleared=False,
        action="block",
        reason=(
            f"Topic rotation cooldown: '{article_type}' articles on "
            f"'{primary_keyword}' have a {cooldown_days}-day cooldown. "
            f"Last published {days:.0f} days ago ('{row['title']}'). "
            f"Wait {cooldown_days - days:.0f} more day(s)."
        ),
        similar_articles=[{
            "id": row["id"],
            "title": row["title"],
            "url_slug": row["url_slug"],
            "updated_at": row["updated_at"],
            "days_ago": round(days, 1),
        }],
    )


# ── Public API ───────────────────────────────────────────────────────────────

def run_dedup(
    primary_keyword: str,
    summary: str,
    article_type: str,
    cluster_id: Optional[str] = None,
    ticker: Optional[str] = None,
) -> DedupResult:
    """Run all three dedup checks against the database.

    Checks are executed in order. The first non-passing result is returned
    immediately. If all checks pass, a "new" result is returned.

    Args:
        primary_keyword: The target keyword for the proposed article.
        summary: 1-3 sentence summary of the proposed article.
        article_type: One of ARTICLE_TYPES (ticker, howto, scenario, etc.).
        cluster_id: Optional cluster/pillar grouping for semantic search.
        ticker: Optional stock ticker symbol (for ticker-type articles).

    Returns:
        DedupResult dataclass.
    """
    conn = get_connection()

    try:
        # Check 1: Exact keyword match.
        result = _check_exact_keyword(primary_keyword, conn)
        if result is not None and not result.cleared:
            return result
        # If keyword match returned an "update" or "new+redirect" action,
        # still run remaining checks but keep the keyword result as baseline.
        keyword_result = result

        # Check 2: Semantic similarity.
        result = _check_semantic_similarity(summary, cluster_id, conn)
        if result is not None and not result.cleared:
            return result
        semantic_result = result

        # Check 3: Topic rotation / cooldown.
        result = _check_topic_rotation(
            article_type, primary_keyword, ticker, conn
        )
        if result is not None and not result.cleared:
            return result

        # All checks passed. Return the most informative result.
        if keyword_result is not None:
            return keyword_result
        if semantic_result is not None:
            return semantic_result

        return DedupResult(
            cleared=True,
            action="new",
            reason="All dedup checks passed. Safe to produce new article.",
            similar_articles=[],
        )

    finally:
        conn.close()


# ── CLI convenience ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    if len(sys.argv) < 4:
        print(
            "Usage: python dedup_engine.py <primary_keyword> "
            "<summary> <article_type> [cluster_id] [ticker]"
        )
        sys.exit(1)

    kw = sys.argv[1]
    summ = sys.argv[2]
    atype = sys.argv[3]
    cid = sys.argv[4] if len(sys.argv) > 4 else None
    tick = sys.argv[5] if len(sys.argv) > 5 else None

    result = run_dedup(kw, summ, atype, cid, tick)
    output = {
        "cleared": result.cleared,
        "action": result.action,
        "reason": result.reason,
        "similar_articles": result.similar_articles,
    }
    print(json.dumps(output, indent=2))
    sys.exit(0 if result.cleared else 1)
