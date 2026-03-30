"""
CFO Silvia Content Factory — Configuration
All constants, paths, and settings for the 10-agent pipeline.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
CHECKS_DIR = PROJECT_ROOT / "checks"
DB_DIR = PROJECT_ROOT / "db"
DEDUP_DIR = PROJECT_ROOT / "dedup"
VIZ_DIR = PROJECT_ROOT / "viz"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
OUTPUT_DIR = PROJECT_ROOT / "output"
KEYWORDS_DIR = PROJECT_ROOT / "keywords"
LOGS_DIR = PROJECT_ROOT / "logs"

DB_PATH = DB_DIR / "silvia.db"
KEYWORDS_CSV = KEYWORDS_DIR / "keywords.csv"

# ── Article types ──────────────────────────────────────────────────────────────
ARTICLE_TYPES = [
    "ticker",
    "howto",
    "scenario",
    "investor",
    "comparison",
    "earnings",
]

# ── Writer variants ────────────────────────────────────────────────────────────
WRITER_VARIANTS = ["A", "B", "C", "D"]

VARIANT_MODIFIERS = {
    "A": (
        "VARIANT A (analytical): Lead with exact numbers. Stack data points "
        "back-to-back. Read like a sharp equity research note, but accessible."
    ),
    "B": (
        "VARIANT B (narrative): Build each section around a story or anecdote. "
        "Use data as evidence within narrative. Connect to historical precedent."
    ),
    "C": (
        "VARIANT C (direct): State your verdict first sentence of every section. "
        "Be blunt. Shorter paragraphs. More declarative sentences. Strong take."
    ),
    "D": (
        "VARIANT D (contextual): Frame every data point in comparison: historical "
        "averages, competitors, sector norms. Always answer 'compared to what?'"
    ),
}

# ── Daily content mix ──────────────────────────────────────────────────────────
MARKET_DAY_BATCHES = {
    "morning": [
        ("ticker", "Ticker #1"),
        ("ticker", "Ticker #2"),
        ("howto", "How-to #1"),
        ("scenario", "Scenario #1"),
    ],
    "midday": [
        ("ticker", "Ticker #3"),
        ("howto", "How-to #2"),
        ("comparison", "Comparison"),
    ],
    "aftermarket": [
        ("scenario", "Scenario #2"),
        ("investor", "Investor breakdown"),
        ("earnings", "Earnings recap"),
    ],
}

WEEKEND_BATCHES = {
    "all": [
        ("howto", "How-to #1"),
        ("howto", "How-to #2"),
        ("scenario", "Scenario #1"),
        ("scenario", "Scenario #2"),
        ("comparison", "Comparison"),
        ("investor", "Investor breakdown"),
    ],
}

# ── Word count targets ─────────────────────────────────────────────────────────
WORD_COUNT_TARGETS = {
    "ticker":     (800, 1500),
    "howto":      (1200, 2000),
    "scenario":   (1200, 2000),
    "investor":   (600, 1000),
    "comparison": (600, 1000),
    "earnings":   (800, 1500),
}

# ── Viz count targets ─────────────────────────────────────────────────────────
VIZ_COUNT_TARGETS = {
    "ticker":     2,
    "howto":      3,
    "scenario":   3,
    "investor":   2,
    "comparison": 2,
    "earnings":   2,
}

# ── Dedup thresholds ──────────────────────────────────────────────────────────
SEMANTIC_BLOCK_THRESHOLD = 0.92
SEMANTIC_FLAG_THRESHOLD = 0.85
PARAGRAPH_JACCARD_THRESHOLD = 0.80

# ── Topic rotation cooldowns (days) ──────────────────────────────────────────
ROTATION_COOLDOWNS = {
    "ticker":     7,
    "howto":      60,
    "scenario":   30,
    "investor":   90,   # or next 13F filing
    "comparison": 90,
    "earnings":   90,   # once per earnings report
}

# ── Freshness ─────────────────────────────────────────────────────────────────
FRESHNESS_VIEW_THRESHOLD = 50       # page_views_7d threshold
FRESHNESS_AGE_DAYS = 10             # updated_at older than this
FRESHNESS_MAX_PER_SESSION = 10

# ── Embedding model ───────────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# ── Viz rendering ─────────────────────────────────────────────────────────────
VIZ_PNG_WIDTH = 700
VIZ_PNG_HEIGHT = 400
EARNINGS_CARD_WIDTH = 1200
EARNINGS_CARD_HEIGHT = 675

# ── SVG Color palette ─────────────────────────────────────────────────────────
SVG_COLORS = {
    "primary":    "#2563EB",
    "secondary":  "#10B981",
    "accent":     "#F59E0B",
    "danger":     "#EF4444",
    "dark_text":  "#0F172A",
    "medium_text":"#475569",
    "light_text": "#94A3B8",
    "card_bg":    "#F8FAFC",
    "border":     "#E2E8F0",
    "canvas_bg":  "#FFFFFF",
    "highlight":  "#DBEAFE",
}

# ── Earnings card palette (from Content Playbook) ─────────────────────────────
EARNINGS_CARD_COLORS = {
    "background": "#0A0A0A",
    "text":       "#FFFFFF",
    "beat":       "#22C55E",
    "miss":       "#EF4444",
    "gold":       "#C9A84C",
}

# ── WordPress / publishing ────────────────────────────────────────────────────
SITE_URL = "https://cfosilvia.com"
AUTHOR_NAME = "Silvia"
AUTHOR_URL = f"{SITE_URL}/about"
PUBLISHER_NAME = "CFO Silvia"

# Optional: WordPress Application Password for automated publishing
WP_URL = os.environ.get("WP_URL", "")
WP_USER = os.environ.get("WP_USER", "")
WP_APP_PASSWORD = os.environ.get("WP_APP_PASSWORD", "")

# ── Pipeline control ──────────────────────────────────────────────────────────
MAX_AUDIT_LOOPS = 3
MAX_VIZ_CRITIC_LOOPS = 3
MAX_RESEARCH_AUDIT_LOOPS = 2
