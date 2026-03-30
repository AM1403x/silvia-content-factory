"""
CFO Silvia Content Factory — Monthly Content Calendar Builder

Generates a full month of scheduled articles, assigning topics, tickers,
writer variants, and batches per the daily content mix.  Performs dedup
pre-checks on proposed topics and inserts rows into content_calendar.
"""

import calendar
import csv
import json
import random
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    ARTICLE_TYPES,
    WRITER_VARIANTS,
    MARKET_DAY_BATCHES,
    WEEKEND_BATCHES,
    ROTATION_COOLDOWNS,
    KEYWORDS_CSV,
    DB_PATH,
)
from db.init_db import get_connection, init_database


# ── US market holidays (2025-2027) ───────────────────────────────────────────────
# Federal holidays when US stock markets are closed.
# Update annually; these cover the likely usage window.

_MARKET_HOLIDAYS = {
    # 2025
    date(2025, 1, 1),    # New Year
    date(2025, 1, 20),   # MLK
    date(2025, 2, 17),   # Presidents' Day
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 26),   # Memorial Day
    date(2025, 6, 19),   # Juneteenth
    date(2025, 7, 4),    # Independence Day
    date(2025, 9, 1),    # Labor Day
    date(2025, 11, 27),  # Thanksgiving
    date(2025, 12, 25),  # Christmas
    # 2026
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),    # Observed (July 4 = Saturday)
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),   # Observed (June 19 = Saturday)
    date(2027, 7, 5),    # Observed (July 4 = Sunday)
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),  # Observed (Dec 25 = Saturday)
}


def is_market_day(d: date) -> bool:
    """Return True if the date is a US market trading day (Mon-Fri, not holiday)."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d not in _MARKET_HOLIDAYS


# ── Major tickers for ticker analyses ────────────────────────────────────────────

MAJOR_TICKERS = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "BRK.B",
    "JPM", "V", "JNJ", "UNH", "PG", "MA", "HD", "DIS", "ADBE", "CRM",
    "NFLX", "PYPL", "INTC", "AMD", "QCOM", "T", "VZ", "PFE", "MRK",
    "ABBV", "LLY", "KO", "PEP", "WMT", "COST", "TGT", "LOW", "NKE",
    "BA", "CAT", "GE", "HON", "MMM", "XOM", "CVX", "COP", "SLB",
    "GS", "MS", "C", "BAC", "WFC",
]


# ── Default topics per article type ─────────────────────────────────────────────

_DEFAULT_TOPICS = {
    "howto": [
        "How to read a 10-K filing in 15 minutes",
        "How to calculate free cash flow from financial statements",
        "How to evaluate a company's debt-to-equity ratio",
        "How to use the DuPont analysis for ROE breakdown",
        "How to assess management quality from proxy statements",
        "How to build a discounted cash flow model",
        "How to read an earnings call transcript",
        "How to compare P/E ratios across sectors",
        "How to analyze working capital efficiency",
        "How to spot revenue recognition red flags",
    ],
    "scenario": [
        "What happens to your portfolio if the Fed cuts rates 3 times in 2026",
        "Scenario: oil hits $120 per barrel again",
        "What if inflation re-accelerates above 4%",
        "Scenario: the US dollar weakens 15% in 12 months",
        "What happens if AI spending exceeds $500B in 2026",
        "Scenario: commercial real estate defaults spike",
        "What if the yield curve stays inverted for 2 more years",
        "Scenario: China devalues the yuan by 10%",
    ],
    "comparison": [
        "Vanguard vs Fidelity: total stock market index fund comparison",
        "AAPL vs MSFT: which mega-cap is better positioned",
        "Traditional IRA vs Roth IRA: a CFO's tax analysis",
        "S&P 500 vs total international: diversification math",
        "Growth vs value: factor analysis for 2026",
        "High-yield savings vs short-term Treasuries",
    ],
    "investor": [
        "Warren Buffett's latest 13F: what changed",
        "Cathie Wood's conviction buys this quarter",
        "Ray Dalio's All Weather portfolio: 2026 update",
        "Michael Burry's latest bets decoded",
        "Howard Marks on the current credit cycle",
        "Bill Ackman's concentrated portfolio strategy",
    ],
    "earnings": [
        "AAPL earnings breakdown: services growth vs hardware",
        "NVDA earnings: AI demand sustainability",
        "JPM earnings: net interest income trajectory",
        "AMZN earnings: AWS margins and retail profitability",
        "MSFT earnings: Azure growth and AI monetization",
        "TSLA earnings: deliveries, margins, and energy",
    ],
}


# ── Load keywords from CSV ──────────────────────────────────────────────────────

def _load_keywords() -> dict[str, list[dict]]:
    """Load keywords from CSV, grouped by article type.

    Expected CSV columns: keyword, article_type, search_volume, difficulty
    Falls back to empty dict if CSV doesn't exist.
    """
    if not KEYWORDS_CSV.exists():
        return {}

    keywords: dict[str, list[dict]] = {}
    with open(KEYWORDS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            atype = row.get("article_type", "").strip()
            if atype and atype in ARTICLE_TYPES:
                keywords.setdefault(atype, []).append({
                    "keyword": row.get("keyword", "").strip(),
                    "search_volume": int(row.get("search_volume", 0)),
                    "difficulty": int(row.get("difficulty", 50)),
                })

    # Sort each group by search volume descending
    for atype in keywords:
        keywords[atype].sort(key=lambda k: k["search_volume"], reverse=True)

    return keywords


# ── Dedup pre-check ──────────────────────────────────────────────────────────────

def _dedup_precheck(
    topic: str,
    article_type: str,
    keyword: str,
    ticker: Optional[str],
    target_date: date,
) -> bool:
    """Check if a proposed topic passes dedup constraints.

    Verifies the cooldown period hasn't been violated for this topic/keyword/ticker.
    Returns True if the topic is clear to schedule.
    """
    cooldown = ROTATION_COOLDOWNS.get(article_type, 30)
    cutoff = (target_date - timedelta(days=cooldown)).isoformat()

    conn = get_connection()
    try:
        # Check content_calendar for recent same-topic entries
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM content_calendar
               WHERE article_type = ?
                 AND (topic = ? OR primary_keyword = ?)
                 AND scheduled_date > ?
                 AND status != 'dedup_blocked'""",
            (article_type, topic, keyword, cutoff),
        ).fetchone()
        if row and row["cnt"] > 0:
            return False

        # Check published articles for same keyword/ticker
        if ticker:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM articles
                   WHERE article_type = ?
                     AND ticker = ?
                     AND published_at > ?""",
                (article_type, ticker, cutoff),
            ).fetchone()
            if row and row["cnt"] > 0:
                return False

        return True
    except Exception:
        # If DB doesn't exist yet or tables are missing, pass the check
        return True
    finally:
        conn.close()


# ── Variant rotation ─────────────────────────────────────────────────────────────

class _VariantRotator:
    """Rotate writer variants ensuring no two consecutive same-type articles
    use the same variant."""

    def __init__(self):
        self._last_by_type: dict[str, str] = {}
        self._index: int = 0

    def next(self, article_type: str) -> str:
        last = self._last_by_type.get(article_type)
        candidates = [v for v in WRITER_VARIANTS if v != last]
        # Rotate through candidates deterministically
        pick = candidates[self._index % len(candidates)]
        self._last_by_type[article_type] = pick
        self._index += 1
        return pick


# ── Build daily articles ─────────────────────────────────────────────────────────

def _build_day_entries(
    d: date,
    is_market: bool,
    keywords_db: dict[str, list[dict]],
    rotator: _VariantRotator,
    ticker_pool: list[str],
    topic_pools: dict[str, list[str]],
) -> list[dict]:
    """Build the list of article entries for a single day."""
    batches = MARKET_DAY_BATCHES if is_market else WEEKEND_BATCHES
    entries: list[dict] = []

    for batch_name, slots in batches.items():
        for article_type, label in slots:
            # Pick topic
            topic = _pick_topic(article_type, topic_pools, keywords_db, d)

            # Pick keyword
            keyword = _pick_keyword(article_type, keywords_db, topic)

            # Pick ticker for ticker/earnings types
            ticker = None
            if article_type in ("ticker", "earnings") and ticker_pool:
                ticker = ticker_pool.pop(0)
                ticker_pool.append(ticker)  # Recycle to end of pool
                topic = f"{ticker} {article_type} analysis"

            # Dedup pre-check
            if not _dedup_precheck(topic, article_type, keyword, ticker, d):
                # Try an alternate topic
                alt_topic = _pick_topic(article_type, topic_pools, keywords_db, d)
                if alt_topic != topic and _dedup_precheck(alt_topic, article_type, keyword, ticker, d):
                    topic = alt_topic
                # If still blocked, schedule anyway (pipeline will catch it)

            variant = rotator.next(article_type)

            entries.append({
                "id": uuid.uuid4().hex,
                "scheduled_date": d.isoformat(),
                "batch": batch_name,
                "article_type": article_type,
                "topic": topic,
                "primary_keyword": keyword,
                "ticker": ticker,
                "writer_variant": variant,
                "status": "scheduled",
                "dedup_cleared": True,
            })

    return entries


def _pick_topic(
    article_type: str,
    topic_pools: dict[str, list[str]],
    keywords_db: dict[str, list[dict]],
    target_date: date,
) -> str:
    """Select a topic for the given article type."""
    pool = topic_pools.get(article_type, [])
    if pool:
        # Pop from pool (rotating through available topics)
        topic = pool.pop(0)
        pool.append(topic)
        return topic

    # Fallback: generate from keywords
    kw_list = keywords_db.get(article_type, [])
    if kw_list:
        kw = kw_list[0]
        kw_list.append(kw_list.pop(0))
        return kw["keyword"]

    return f"{article_type} article for {target_date.isoformat()}"


def _pick_keyword(
    article_type: str,
    keywords_db: dict[str, list[dict]],
    topic: str,
) -> str:
    """Pick the primary keyword for an article."""
    kw_list = keywords_db.get(article_type, [])
    if kw_list:
        # Find best match or use highest-volume keyword
        for kw in kw_list:
            if kw["keyword"].lower() in topic.lower():
                return kw["keyword"]
        return kw_list[0]["keyword"]

    # Extract a keyword from the topic
    words = topic.lower().split()
    # Use first 3-4 meaningful words
    stop = {"how", "to", "a", "an", "the", "is", "are", "what", "if", "vs", "for"}
    meaningful = [w for w in words if w not in stop][:4]
    return " ".join(meaningful) if meaningful else topic[:50]


# ── Main builder ─────────────────────────────────────────────────────────────────

def build_monthly_calendar(year: int, month: int) -> list[dict]:
    """Build and insert the full monthly content calendar.

    For each day of the month:
    - Determines if it's a market day or weekend/holiday.
    - Assigns the appropriate daily article mix (10 market / 6 weekend).
    - Rotates writer variants.
    - Runs dedup pre-checks.
    - Inserts into the content_calendar table.

    Args:
        year: Calendar year (e.g. 2026).
        month: Calendar month (1-12).

    Returns:
        List of dicts representing all scheduled entries, plus a summary
        dict as the last element.
    """
    if not DB_PATH.exists():
        init_database()

    keywords_db = _load_keywords()
    rotator = _VariantRotator()
    ticker_pool = list(MAJOR_TICKERS)
    random.seed(f"{year}-{month:02d}")  # Deterministic for reproducibility
    random.shuffle(ticker_pool)

    # Build topic pools from defaults
    topic_pools: dict[str, list[str]] = {}
    for atype, topics in _DEFAULT_TOPICS.items():
        pool = list(topics)
        random.shuffle(pool)
        topic_pools[atype] = pool

    # Generate entries for every day
    num_days = calendar.monthrange(year, month)[1]
    all_entries: list[dict] = []
    market_day_count = 0
    weekend_count = 0

    for day_num in range(1, num_days + 1):
        d = date(year, month, day_num)
        is_market = is_market_day(d)

        if is_market:
            market_day_count += 1
        else:
            weekend_count += 1

        day_entries = _build_day_entries(
            d, is_market, keywords_db, rotator, ticker_pool, topic_pools,
        )
        all_entries.extend(day_entries)

    # Insert into database
    conn = get_connection()
    try:
        conn.executemany(
            """INSERT OR IGNORE INTO content_calendar
               (id, scheduled_date, batch, article_type, topic,
                primary_keyword, ticker, writer_variant, status, dedup_cleared)
               VALUES (:id, :scheduled_date, :batch, :article_type, :topic,
                       :primary_keyword, :ticker, :writer_variant, :status, :dedup_cleared)""",
            all_entries,
        )
        conn.commit()
    finally:
        conn.close()

    # Count by type
    type_counts: dict[str, int] = {}
    for entry in all_entries:
        atype = entry["article_type"]
        type_counts[atype] = type_counts.get(atype, 0) + 1

    summary = {
        "_summary": True,
        "year": year,
        "month": month,
        "total_days": num_days,
        "market_days": market_day_count,
        "weekend_holiday_days": weekend_count,
        "total_articles": len(all_entries),
        "articles_by_type": type_counts,
        "variant_distribution": _count_variants(all_entries),
    }

    print(f"\nCalendar built for {year}-{month:02d}:")
    print(f"  Market days:     {market_day_count}")
    print(f"  Weekend/holiday: {weekend_count}")
    print(f"  Total articles:  {len(all_entries)}")
    print(f"  By type:         {json.dumps(type_counts, indent=4)}")

    all_entries.append(summary)
    return all_entries


def _count_variants(entries: list[dict]) -> dict[str, int]:
    """Count variant distribution across entries."""
    counts: dict[str, int] = {}
    for e in entries:
        v = e.get("writer_variant", "?")
        counts[v] = counts.get(v, 0) + 1
    return counts


# ── CLI entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build monthly content calendar")
    parser.add_argument("year", type=int, help="Year (e.g. 2026)")
    parser.add_argument("month", type=int, help="Month (1-12)")
    args = parser.parse_args()

    entries = build_monthly_calendar(args.year, args.month)
    # Write to a JSON file for review
    out_path = Path(__file__).parent / "output" / f"calendar_{args.year}_{args.month:02d}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, default=str)
    print(f"Calendar written to {out_path}")
