# CFO Silvia Content Factory

A 10-agent SEO/GEO content pipeline that produces 10 data-driven personal finance articles per day, each with inline SVG visualizations, for [cfosilvia.com](https://cfosilvia.com).

Runs entirely inside Claude Code on a Claude Max subscription. No external APIs beyond two pip packages.

## What it does

You say "Run today's batch" and the system:

1. Reads today's content calendar (10 articles on market days, 6 on weekends)
2. Runs dedup checks (keyword match, semantic similarity, topic rotation)
3. Processes each article through a 10-agent pipeline with 3 automated checks
4. Outputs finished articles with inline SVG visualizations, rendered PNGs, and JSON-LD metadata
5. Picks the best article for daily X posting

## The pipeline

```
CONTENT CALENDAR + DEDUP
  |
  v
Agent 1:  RESEARCHER          — Web search for verified data with sources
Agent 2:  RESEARCH AUDITOR    — Cross-validates every data point
Agent 3:  WRITER              — Silvia voice, variant rotation (A/B/C/D)
Agent 4:  WRITE-UP AUDITOR    — 30-point checklist (humanizer + SEO/GEO + formatting)
Agent 5:  SIMPLIFIER          — Grade 8 readability, inline term definitions
  |
CHECK 1:  Post-Simplifier Scan (Python regex — banned words, em dashes, formatting)
  |
Agent 6:  FACT CHECKER         — Independent verification via web search
  |
CHECK 2:  Compliance Scan (Python regex — no buy/sell/hold advice)
  |
Agent 7:  VIZ STRATEGIST       — Reads article, identifies 2-3 viz slots
Agent 8:  VIZ CRAFTSMAN        — Builds production SVGs one at a time
Agent 9:  VIZ DESIGN CRITIC    — 20-point quality audit, loops with Craftsman
Agent 10: VIZ INTEGRATOR       — Places visuals with lead-ins and interpretations
  |
CHECK 3:  Post-Viz Scan (Python regex — checks only Integrator-added text)
  |
  v
OUTPUT: article.md + SVGs + PNGs + meta.json
```

## Article types

| Type | SEO/GEO | Daily count | Word target |
|------|---------|-------------|-------------|
| Ticker analysis | SEO-primary | 3 | 800-1,500 |
| How-to guide | SEO-primary | 2 | 1,200-2,000 |
| Event scenario | GEO-primary | 2 | 1,200-2,000 |
| Comparison | SEO-primary | 1 | 600-1,000 |
| Investor breakdown | GEO-primary | 1 | 600-1,000 |
| Earnings recap | GEO-primary | 1 | 800-1,500 |

## Requirements

- Claude Code on a Claude Max account (this IS the system)
- Python 3.13+
- `pip install sentence-transformers playwright && playwright install chromium`

No OpenAI, no X API, no Slack, no Google APIs, no paid embedding services.

## Project structure

```
silvia_factory/
  config.py               — Constants, paths, thresholds
  main.py                 — Pipeline orchestrator (13-step state machine)
  calendar_builder.py     — Monthly content calendar generator
  refresh.py              — Freshness updater for stale articles
  prompts/                — 10 agent prompt files with full banned lists
  checks/                 — 3 Python regex check scripts
  db/                     — SQLite schema + init
  dedup/                  — Embedding, fingerprinting, rotation engine
  viz/                    — Playwright SVG-to-PNG renderer + JSON-LD schemas
  keywords/               — 500+ personal finance keywords with volumes
  output/                 — Daily output (YYYY-MM-DD/article-slug/)
  logs/                   — Pipeline run logs
  examples/               — Gold-standard sample articles
```

## Quick start

```bash
cd ~/silvia_factory

# Initialize the database
python3 db/init_db.py

# Build this month's content calendar
python3 calendar_builder.py 2026 4

# Run today's batch
python3 main.py

# Run a single article
python3 main.py --article <calendar_id>

# Refresh stale high-traffic articles
python3 refresh.py batch --max 10
```

## Output per article

```
output/YYYY-MM-DD/article-slug/
  article-slug.md           — Finished article with inline SVGs
  article-slug-viz-1.svg    — Standalone SVG
  article-slug-viz-1.png    — Rendered PNG (700x400)
  article-slug-viz-2.svg
  article-slug-viz-2.png
  article-slug-meta.json    — Title, slug, keywords, FAQ schema, Article schema
  work/                     — Intermediate pipeline artifacts
```

## Voice

Silvia talks like a sharp CFO over coffee. Lead with the number. Then the "so what" in one sentence. Short paragraphs. Vary the rhythm. Use "you" and "your." Have a take.

## Anti-AI detection

The system applies the Humanizer v3 ruleset (56 anti-AI patterns):

- 100+ banned words (additionally, crucial, leverage, robust, navigate...)
- 50+ banned phrases ("most people don't realize", "let that sink in"...)
- 40+ banned transition openers (Furthermore, Moreover, Additionally...)
- Zero em dashes, zero exclamation marks, zero bold-header-colon lists
- 4 writer variants rotate to prevent corpus-level style detection
- Every claim attributed to a named source with date

## Formatting rules (learned from production)

These rules are enforced by CHECK 1 (post_simplifier_scan.py) and the Write-up Auditor:

- No metadata in article body (no subtitle/meta description/read time fields)
- No bold-header-colon lists (`**Label:** value` is Pattern 15, an AI tell)
- No raw URLs anywhere in the article
- No bold on opening paragraphs
- No exclamation marks
- No bold FAQ questions (use `###` headings)
- No bold sentence openers (`**Sentence.**` is banned)
- FAQ questions use `###` headings, not `**bold**`
- Sources section is 1-2 sentences naming sources, not a numbered URL list
- "Last updated" version block required within first 5 lines
- 30-40% of article sections must contain bullet or numbered lists

## SVG rendering rules (learned from production)

These rules are enforced by the Viz Design Critic (agent 09):

- Legends go on their OWN ROW below the subtitle, left-aligned at x=24
- Legend elements must be LAST in the SVG (drawn on top of grid lines/bars)
- Every legend needs a white background rect to mask grid lines
- Never place legends in the top-right overlapping the title
- All colors from the defined palette only
- Minimum font size 11px
- viewBox="0 0 700 [height]", Inter font family
- All rects rx="8" min, cards rx="12"

## Dedup system

Three checks run before any article enters the pipeline:

1. Exact keyword match (same keyword within 7 days = reject, 7-30 days = update, 30+ = new)
2. Semantic similarity (sentence-transformers, cosine > 0.92 = block, 0.85-0.92 = flag)
3. Topic rotation cooldowns (ticker: 7d, howto: 60d, scenario: 30d, comparison: 90d)

## Cost

Your Claude Max subscription + WordPress hosting. That's it.
