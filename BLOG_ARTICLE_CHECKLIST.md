# Blog Article Publication Checklist

Every article MUST pass ALL checks before publishing to Sanity. No exceptions.
Failures caught in production are 10x more expensive than failures caught here.

**As of April 6, 2026: Chart images / SVGs / data visualizations are REMOVED from the pipeline.** Articles are text + tables + FAQs + sources only. See `blog-pipeline/RULES.md` for the rationale.

---

## Required Elements (article fails if ANY are missing)

| # | Element | Check | How to Verify |
|---|---------|-------|---------------|
| 1 | **`<h1>` title** | Title with key number or insight | `grep -c "<h1>" file.html` = 1 |
| 2 | **`<h2>` sections** | 3-5 sections minimum | `grep -c "<h2>" file.html` >= 3 |
| 3 | **HTML data tables** | 1-2 per article with `<thead>/<tbody>` | `grep -c "<table" file.html` >= 1 |
| 4 | **FAQ section** | 3-5 Q&As with `<h3>` questions | `grep -c "<h3>" file.html` >= 3 |
| 5 | **Source attributions** | At least 3 linked `<li>` entries | `grep -c "<li><a" file.html` >= 3 |
| 6 | **CTA** | Link to cfosilvia.com BEFORE Sources section | `grep -c "cfosilvia.com" file.html` >= 1 |
| 7 | **Disclaimer** | Exact canonical text, italicized | `grep -c "informational purposes" file.html` = 1 |
| 8 | **Word count** | 900-1,500 words | `wc -w < file.html` in range |
| 9 | **Custom excerpt** | 100-150 char summary in `excerpts.json` | `excerpts.json` entry exists |
| 10 | **"If You Own" section** | For ticker-specific articles | Check if ticker article |

## FORBIDDEN (article fails if ANY are present)

| # | Element | Why It's Banned |
|---|---------|-----------------|
| 1 | **`<img>` tags** | Charts removed from pipeline 2026-04-06; visual quality issues |
| 2 | **`<svg>` blocks** | Sanity has no SVG block type, dumps as raw text |
| 3 | **`<figure>` wrappers** | Same as above |
| 4 | **`<!DOCTYPE>`, `<html>`, `<head>`, `<body>` tags** | Sanity strips them and dumps `<style>` content as paragraphs |
| 5 | **`<style>`, `<script>`, `<meta>`, `<link>`, `<title>` tags** | Same |
| 6 | **First-paragraph metadata strip** | e.g., `<p>April 4, 2026 \| How-To</p>` becomes the SEO excerpt |
| 7 | **"Consult a qualified professional"** | Removed from blog disclaimer 2026-04-06 |
| 8 | **Em dashes (—)** | Use commas or periods |
| 9 | **Exclamation marks** | Voice rule |
| 10 | **Emojis, hashtags** | Voice rule |

---

## Voice Rules (article fails if ANY are violated)

- [ ] Lead with the number (first sentence = data point)
- [ ] Short paragraphs (1-3 sentences)
- [ ] Uses "you" and "your"
- [ ] Has a take (opinionated, not neutral)
- [ ] Zero exclamation marks
- [ ] Zero emojis
- [ ] Zero hashtags
- [ ] Zero em dashes (use commas or periods)
- [ ] Zero banned words (delve, robust, leverage, pivotal, nuanced, catalyst, holistic, comprehensive, multifaceted, etc.)
- [ ] Uses contractions (didn't, can't, won't)
- [ ] No scene-setting openers ("In today's market...")
- [ ] No summary paragraphs ("In summary...", "Overall...")

---

## Chart/Image Pipeline (CRITICAL — read every word)

### Step 1: Create SVGs with correct dimensions

```
Background:    fill="#1E293B"
Green bars:    fill="#22C55E" (positive values)
Red bars:      fill="#EF4444" (negative values)
Blue bars:     fill="#3B82F6" (neutral values)
Gold bars:     fill="#F59E0B" (highlighted values)
White text:    fill="#FFFFFF" (text INSIDE colored bars)
Label text:    fill="#E2E8F0", font-family="Inter, system-ui, sans-serif"
Title:         font-size="20" font-weight="600"
Axis labels:   font-size="14" font-weight="400"
Value labels:  font-size="13" font-weight="600"
Source text:   font-size="11" fill="#94A3B8" font-style="italic"
ViewBox width: 800-900px (NOT 700 — too narrow for labels)
ViewBox height: 300-560px (depends on number of data rows)
```

### Step 2: Convert SVGs to PNG using cairosvg

```python
import cairosvg
cairosvg.svg2png(bytestring=svg.encode('utf-8'), write_to=str(path), output_width=1800)
```

**ALWAYS use `output_width=1800`** — this produces 2x retina resolution. Never use 1400 or lower.

### Step 3: Visually review EVERY PNG before publishing

Open each PNG and check it with your own eyes. Do NOT skip this step.

### Step 4: Reference PNGs in HTML as `<img>` tags

```html
<img src="/path/to/chart.png" alt="Descriptive alt text with actual data values">
```

### Step 5: Publish from the Silvia-Web directory

```bash
cd ~/Silvia-Web && npx tsx scripts/publish-blog-post-to-sanity.ts --html /path/to/article.html --categories "cat1,cat2" --published-at "2026-04-03T09:00:00Z"
```

---

## Chart Quality Checklist (review EVERY PNG — no exceptions)

| # | Check | What Goes Wrong If You Skip |
|---|-------|-----------------------------|
| 1 | **Every label fully visible** — no text clipped on any edge | "Federal Government" renders as "Fed", "Treaty Rate (EU, Japan, Korea)" renders as "Treaty Rate (EU, Japan, etc" |
| 2 | **Every bar has its label** — both the category name AND the value | A -28% bar without "Airlines" next to it is meaningless to the reader |
| 3 | **Labels on long bars go INSIDE the bar as white text** | If a red bar extends far left, the label to the left gets pushed off-screen. Put the value label (white text) inside the bar instead |
| 4 | **Don't mix $ and % on the same y-axis** | "$5K-$12K" and "8-15%" on the same scale is misleading. Use relative bar heights with individual labels above each bar |
| 5 | **ViewBox has 40px+ padding on all sides** | cairosvg clips content that's too close to edges. 30px is not enough for text with descenders |
| 6 | **Source attribution visible** at bottom inside the viewBox | Source text at y=375 gets cut if viewBox height is 380 |
| 7 | **Multi-word labels that wrap** — use two `<text>` elements stacked | "Commercial Construction" on one line overflows. Split into "Commercial" and "Construction" on separate lines |
| 8 | **ViewBox is wide enough for all labels** — 800-900px, NOT 700 | 700px causes right-side clipping on charts with long value labels |
| 9 | **Color meaning is clear** — green=positive, red=negative, gold=highlight, blue=neutral | Don't use red for neutral data |
| 10 | **Chart tells its story without the article** — title + labels + values should be self-explanatory | If someone screenshots just the chart, they should understand the message |

---

## Sanity Publishing — Lessons Learned (Hard Way)

### SVGs DO NOT work in Sanity
Sanity Portable Text does not have an SVG block type. The HTML-to-Portable-Text converter (`lib/blog/publishing/html-to-portable-text.ts`) handles: `p`, `h2`, `h3`, `h4`, `blockquote`, `ul`, `ol`, `hr`, `table`, `img`. SVG content gets dumped as raw text — you'll see the chart's text labels rendered as paragraphs. **Always convert to PNG first.**

### Sanity CDN converts PNG to AVIF by default
The image URL builder adds `?auto=format` which serves AVIF to browsers that support it. AVIF uses lossy compression that **destroys text and sharp edges in chart images**. Data viz charts MUST be served as PNG using `getSanityImageUrlAsPng()` (defined in `lib/sanity/image.ts`) which uses `?fm=png` instead.

### CSP blocks Sanity CDN images by default
The Content Security Policy in `middleware.ts` must include `https://cdn.sanity.io` in the `img-src` directive. Without this, raw `<img>` tags pointing to Sanity CDN are silently blocked by the browser — no error in console, images just don't appear. `next/image` with `fill` mode was NOT affected because it proxies through `/_next/image` which counts as `'self'`.

### Sanity caches images by asset hash
The publisher generates a deterministic document ID from the slug (`post.<slug>`). When you republish an article, the document gets replaced, but if the image bytes are identical, Sanity reuses the same asset ID and the CDN serves the cached version. **To force a new image upload, change the PNG filename** so Sanity generates a new asset hash. Simply re-uploading the same filename with different content does NOT bust the cache.

### Delete + recreate is safer than overwrite for image updates
When fixing a chart, do this:
1. Generate new PNG with a **different filename** (e.g., `chart-v2.png`, `chart-v3.png`)
2. Update the HTML `<img src>` to point to the new filename
3. **Delete the old Sanity post** via API: `curl -X POST -H "Authorization: Bearer $TOKEN" -d '{"mutations":[{"delete":{"id":"post.<slug>"}}]}' "https://htd46ya1.api.sanity.io/v2025-02-19/data/mutate/staging"`
4. Republish the article — gets a fresh document ID and fresh image asset

### The blog renderer detects data viz images by alt text
In `components/blog/blog-portable-text.tsx`, images are classified as data viz if the alt text contains any of: "chart", "bar", "visualization", "gauge", "comparison", "diverging", "thermometer", "horizontal", "grouped", "sector", "tariff", "performance". Data viz images use a raw `<img>` tag with `width: 100%; height: auto` to render at natural dimensions. Regular images use `next/image` with `aspect-[16/9]` and `object-cover`. **Always include descriptive alt text with these keywords** or the chart renders as a cropped 16:9 photo.

### The publisher runs from Silvia-Web only
The script uses `@/lib/...` path aliases. Running from any other directory gives `ERR_MODULE_NOT_FOUND`. Always: `cd ~/Silvia-Web && npx tsx scripts/publish-blog-post-to-sanity.ts`

---

## Article Types and Required Charts

| Article Type | Required Chart Types |
|-------------|---------------------|
| Earnings beat/miss | Grouped bar (production vs deliveries, EPS actual vs estimate) |
| Macro data (jobs, CPI) | Horizontal bar (sector breakdown), vertical bar (monthly history) |
| Sector analysis | Diverging horizontal bar (winners left, losers right, 0% center) |
| Policy/tariffs | Horizontal bar (tier rates), vertical bar (cost impact by industry) |
| Market comparison | Diverging bar (asset A vs B), gauge/thermometer (sentiment) |
| Earnings preview | Ascending bar (EPS growth by quarter, highlight current) |
| Daily wrap | Multi-metric horizontal bar, sector snapshot |

---

## Automated Pre-Publish Verification Script

Run this BEFORE every publish. If anything says FAIL, fix it first.

```bash
DIR="/tmp/blog-april3"  # Change to your article directory

for f in "$DIR"/*.html; do
  name=$(basename "$f")
  tables=$(grep -c "<table" "$f" 2>/dev/null || echo 0)
  imgs=$(grep -c "<img" "$f" 2>/dev/null || echo 0)
  faqs=$(grep -c "<h3>" "$f" 2>/dev/null || echo 0)
  sources=$(grep -c "<li><a" "$f" 2>/dev/null || echo 0)
  cta=$(grep -c "cfosilvia.com" "$f" 2>/dev/null || echo 0)
  disc=$(grep -c "informational purposes" "$f" 2>/dev/null || echo 0)
  words=$(wc -w < "$f" 2>/dev/null || echo 0)

  PASS=true
  [ "$tables" -lt 1 ] && PASS=false && echo "FAIL $name: no tables"
  [ "$imgs" -lt 1 ] && PASS=false && echo "FAIL $name: no chart images"
  [ "$faqs" -lt 3 ] && PASS=false && echo "FAIL $name: fewer than 3 FAQs ($faqs)"
  [ "$sources" -lt 3 ] && PASS=false && echo "FAIL $name: fewer than 3 sources ($sources)"
  [ "$cta" -lt 1 ] && PASS=false && echo "FAIL $name: no CTA"
  [ "$disc" -lt 1 ] && PASS=false && echo "FAIL $name: no disclaimer"
  [ "$words" -lt 800 ] && PASS=false && echo "FAIL $name: only ${words} words (min 800)"

  if $PASS; then
    echo "PASS $name | ${words}w | tables:$tables | imgs:$imgs | faqs:$faqs | sources:$sources"
  fi
done

echo ""
echo "=== MANUAL CHECK REQUIRED ==="
echo "Open each PNG in /tmp/blog-april3/images/ and verify:"
echo "  1. All labels fully visible (no clipping)"
echo "  2. Every bar has a category label AND value label"
echo "  3. Source attribution visible at bottom"
echo "  4. Chart is self-explanatory without the article"
```

---

## Disclaimer Text (exact — do not modify)

```html
<p><em>This content is for informational purposes only. It is not financial, investment, or legal advice. Past performance does not guarantee future results.</em></p>
```

## CTA Templates

- Ticker-specific: `Own [TICKER]? Silvia can break down what this means for your position. <a href="https://cfosilvia.com">cfosilvia.com</a>`
- General: `What does this mean for your portfolio? <a href="https://cfosilvia.com">Ask Silvia</a>.`
