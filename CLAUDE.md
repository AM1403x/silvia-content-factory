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
