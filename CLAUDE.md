# CLAUDE.md — CFO Silvia Content Factory

## What this project is

A 10-agent content pipeline for cfosilvia.com. Produces 10 personal finance articles per day with inline SVG visualizations. Runs inside Claude Code on Claude Max.

## How to run

```bash
cd ~/silvia_factory
python3 main.py                          # Run today's batch
python3 main.py --date 2026-04-01        # Run a specific date
python3 main.py --article <calendar_id>  # Run one article
python3 calendar_builder.py 2026 4       # Build April calendar
python3 refresh.py batch --max 10        # Refresh stale articles
```

## Pipeline order (never skip, never reorder)

1. Researcher (web search)
2. Research Auditor (verify sources)
3. Writer (Silvia voice + variant A/B/C/D)
4. Write-up Auditor (30-point checklist)
5. Simplifier (grade 8 readability)
6. CHECK 1: `python3 -c "from checks.post_simplifier_scan import post_simplifier_scan; ..."`
7. Fact Checker (web search verification)
8. CHECK 2: `python3 -c "from checks.compliance_scan import compliance_scan; ..."`
9. Viz Strategist (spec sheet)
10. Viz Craftsman (build SVGs)
11. Viz Design Critic (20-point audit)
12. Viz Integrator (place in article)
13. CHECK 3: `python3 -c "from checks.post_viz_scan import post_viz_scan; ..."`

## Voice rules

Silvia = sharp CFO over coffee. Lead with the number. Short paragraphs. "You" and "your." Have a take. No hedging into meaninglessness.

## Hard formatting rules (non-negotiable)

These cause the most bugs. Enforce every time.

### Article formatting

- Output plain markdown ONLY. No JSON wrappers, no metadata fields in the body
- First line: `# Title`
- Second line: `Last updated: [date] | Verification window: [quarter] data`
- No `**Subtitle:**`, `**Meta description:**`, `**Read time:**` visible in article
- No `**Label:** value` pattern anywhere (Pattern 15 = AI formatting tell)
- No raw URLs. Sources named conversationally, never linked
- No bold on opening paragraph
- No bold FAQ questions — use `### Question?` headings
- No bold sentence openers (`**Sentence.**` is banned)
- Zero exclamation marks
- Zero em dashes (use commas, periods, colons, semicolons, parentheses)
- No `---` horizontal rules in article body (one before disclaimer is OK)
- Sources section: 1-2 sentences naming sources, NOT a numbered URL list
- 30-40% of sections must contain bullet or numbered lists
- List items are 1-2 sentences with data, not just labels

### SVG rules (most common rendering bugs)

- Legends go LAST in the SVG source (after all bars, lines, grid elements)
- SVG draws in source order — later elements render on top of earlier ones
- Every legend needs a white background `<rect>` behind it to mask grid lines
- Legends go on their own row below the subtitle, left-aligned at x=24
- NEVER put legends in the top-right overlapping the title (titles are 400-500px wide)
- Colors from palette only: #2563EB, #10B981, #F59E0B, #EF4444, #0F172A, #475569, #94A3B8, #F8FAFC, #E2E8F0, #FFFFFF
- viewBox="0 0 700 [height]", font-family="Inter, -apple-system, system-ui, sans-serif"
- All rects rx="8" min, cards rx="12"
- Minimum text size 11px
- When fixing SVG text visibility: move the text element to the END of the SVG, add a white rect behind it

### When fixing articles embedded in .md files

SVGs appear twice: as standalone `.svg` files AND embedded inline in the `.md` article. When fixing an SVG issue, you must update BOTH:
1. The standalone `.svg` file
2. The SVG embedded inside the article `.md`

If you only fix one, the preview HTML will show the old broken version.

## Banned word list location

The complete list is in `prompts/agent_03_writer.txt` and `checks/post_simplifier_scan.py`. Both must stay in sync. When adding a banned word, update both files.

## Database

SQLite at `db/silvia.db`. Schema in `db/schema.sql`. Tables:
- `articles` — published article registry with embeddings
- `paragraph_fingerprints` — trigram hashes for dedup
- `content_calendar` — monthly schedule
- `retry_queue` — failed articles for retry
- `pillar_pages` — topic cluster hubs
- `pipeline_logs` — run history

## Preview HTML

After a batch, regenerate the preview:
```bash
python3 -c "... # see the preview generation script in output/2026-03-30/"
```
Uses Python `markdown` library (not regex). Handles SVG embedding, TOC generation, SEO/GEO classification tabs.

## Key files

| File | Purpose |
|------|---------|
| `config.py` | All constants, paths, thresholds |
| `main.py` | Pipeline orchestrator (Step enum, ArticleState, PipelineState) |
| `calendar_builder.py` | Monthly calendar with variant rotation |
| `refresh.py` | Freshness updater for high-traffic stale articles |
| `checks/post_simplifier_scan.py` | CHECK 1: banned words + formatting enforcement |
| `checks/compliance_scan.py` | CHECK 2: no financial advice language |
| `checks/post_viz_scan.py` | CHECK 3: scan only Integrator-added text |
| `dedup/dedup_engine.py` | Three-check dedup (keyword, semantic, rotation) |
| `dedup/embedding.py` | sentence-transformers embeddings (all-MiniLM-L6-v2) |
| `viz/render.py` | Playwright SVG-to-PNG + earnings card renderer |
| `viz/schema_generator.py` | Article + FAQ JSON-LD schemas |
| `keywords/keywords.csv` | 500+ keywords with monthly volume estimates |

## Testing

```bash
# Verify all modules import
python3 -c "import main, calendar_builder, refresh, config"

# Test CHECK 1
python3 -c "from checks.post_simplifier_scan import post_simplifier_scan; print(post_simplifier_scan('Test text.'))"

# Test compliance
python3 -c "from checks.compliance_scan import compliance_scan; print(compliance_scan('You should buy this stock.'))"

# Test SVG rendering
python3 -c "from viz.render import render_svg_to_png_sync; render_svg_to_png_sync('<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 100 100\"><rect width=\"100\" height=\"100\" fill=\"blue\"/></svg>', '/tmp/test.png', 100, 100); print('OK')"
```

## Blog Article Production (MUST READ before publishing)

The full pipeline lives at `blog-pipeline/`. **Read `blog-pipeline/RULES.md` before writing or publishing any article.**

### Required reading order
1. `blog-pipeline/RULES.md` — hard rules, banned phrases, canonical strings (read first, every time)
2. `blog-pipeline/README.md` — golden path workflow, script-by-script
3. `BLOG_ARTICLE_CHECKLIST.md` — extended checklist with examples

### Hard rules (as of April 6, 2026)

**Every article MUST include:**
1. `<h1>` title with the key number or insight
2. 3-5 `<h2>` sections
3. 1-2 HTML `<table>` blocks with `<thead>` and `<tbody>`
4. `<h2>Frequently Asked Questions</h2>` with 3-5 `<h3>` Q&As
5. `<h2>Sources</h2>` with at least 3 linked `<li>` entries
6. CTA paragraph BEFORE the Sources section
7. Disclaimer paragraph at the very end (canonical text below)
8. 900-1,500 words

**Every article MUST NOT include:**
1. **NO chart images / SVGs / data visualizations.** Removed entirely from the pipeline. Caused too many visual quality issues. Do NOT add `<img>`, `<svg>`, or `<figure>` tags.
2. **NO `<!DOCTYPE>`, `<html>`, `<head>`, `<style>`, `<script>`, `<meta>`, `<link>`, `<title>`, `<body>` wrapper tags.** Sanity dumps `<style>` content as paragraph text.
3. **NO metadata strip lines** like `<p><strong>April 4, 2026</strong> | How-To</p>` after the `<h1>`.
4. **NO em dashes** (—). Use commas or periods.
5. **NO exclamation marks**, **NO emojis**, **NO hashtags**.
6. **NO banned AI words:** delve, robust, leverage, pivotal, nuanced, catalyst, holistic, comprehensive, multifaceted, encompassing, testament, transformative, streamline, furthermore, moreover, additionally.
7. **NO scene-setting openers** like "In today's market..." or "As investors digest...".
8. **NO summary paragraphs** like "In summary..." or "Overall...".

### Banned phrases (never include in any article or disclaimer)
- "Consult a qualified professional before making financial decisions"
- "Consult a qualified professional" (any variant)
- "Always consult a qualified"

These were removed from the blog disclaimer template and the author page on April 6, 2026. The canonical disclaimer is the 3-sentence version below — no fourth sentence.

### Canonical strings (use exactly these — no variations)

**CTA** (placed BEFORE the Sources section):
```html
<p>What does this mean for your portfolio? <a href="https://cfosilvia.com">Ask Silvia</a>.</p>
```

**Disclaimer** (placed at the very end):
```html
<p><em>This content is for informational purposes only. It is not financial, investment, or legal advice. Past performance does not guarantee future results.</em></p>
```

### Pipeline workflow (always follow this sequence)

```bash
# 1. Generate articles (text + tables only, NO charts)
#    Output: ~/blog-batches/YYYY-MM-DD/*.html
#    Required alongside: ~/blog-batches/YYYY-MM-DD/excerpts.json

# 2. Clean HTML (strips wrappers, leaked CSS, metadata lines, banned phrases, leftover img/svg/figure)
python3 blog-pipeline/scripts/02-clean-html.py ~/blog-batches/YYYY-MM-DD/

# 3. Reorder CTA before Sources, append canonical disclaimer
python3 blog-pipeline/scripts/03-fix-structure.py ~/blog-batches/YYYY-MM-DD/

# 4. Run automated checklist verification (FAILS on any banned content)
bash blog-pipeline/scripts/04-verify.sh ~/blog-batches/YYYY-MM-DD/

# 5. Publish to Sanity with custom short excerpts from excerpts.json
python3 blog-pipeline/scripts/05-publish.py ~/blog-batches/YYYY-MM-DD/

# 6. Audit Sanity for structural issues, banned phrases, duplicate excerpts
python3 blog-pipeline/scripts/06-audit-sanity.py
```

### Lessons baked in (every one of these is a real bug we hit)

| Bug | Where it's now prevented |
|---|---|
| SVGs in HTML get dumped as paragraph text | `02-clean-html.py` strips `<svg>`, `<figure>` |
| `<!DOCTYPE>`, `<style>`, `<head>` content leaks as paragraphs | `02-clean-html.py` strips all wrapper tags |
| First `<p>` with `April X, 2026 \| Category` becomes the SEO excerpt | `02-clean-html.py` detects and strips metadata strip lines |
| Default excerpt = first paragraph verbatim → duplicates on rendered page | `05-publish.py` requires `excerpts.json` with custom short excerpts |
| CTA hidden after Sources list (nobody scrolls there) | `03-fix-structure.py` enforces CTA-before-Sources ordering |
| "Consult a qualified professional" disclaimer phrase | `02-clean-html.py` strips it; `06-audit-sanity.py` flags it |
| Banned AI words (catalyst, leverage, unprecedented, etc.) | `04-verify.sh` runs the audit; humanizer agent enforces voice rules |
| Sanity CDN AVIF conversion destroys chart text | Charts removed entirely; no longer relevant |
| Same PNG filename on re-upload caches old version | Charts removed entirely; no longer relevant |
| Vercel CSP blocks `cdn.sanity.io` images | Already fixed in `Silvia-Web/middleware.ts` — don't remove |
| Vercel staging needs Sanity read token | `SANITY_STAGING_WRITE_TOKEN` set in Vercel preview env — don't remove |

### Excerpts.json format (REQUIRED for every batch)

```json
{
  "01-article-slug.html": {
    "excerpt": "100-150 char summary, NOT identical to the first paragraph",
    "categories": "macro,jobs,fed",
    "published_at": "2026-04-08T09:00:00Z"
  }
}
```

The publisher (`05-publish.py`) refuses to run without this file.
