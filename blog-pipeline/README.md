# Blog Pipeline — Production Workflow

End-to-end pipeline for creating, validating, and publishing blog articles to Sanity staging. **Every lesson learned from the April 3-5, 2026 batch is baked in here.** Read this before writing any new article.

## TL;DR — The Golden Path

**As of April 6, 2026: NO chart images. We removed all SVG/PNG visualizations from the pipeline.** Articles are text + tables + FAQs + sources only. The image step (`01-svg-to-png.py`) is preserved but should NOT be used unless we explicitly bring charts back.

```bash
# 1. Generate articles (write HTML — text + tables only, NO charts)
#    Output: ~/blog-batches/2026-04-08/*.html
#    Required alongside: ~/blog-batches/2026-04-08/excerpts.json

# 2. Clean HTML (strip wrappers, leaked CSS, metadata lines, any leftover img/svg/figure tags)
python3 blog-pipeline/scripts/02-clean-html.py ~/blog-batches/2026-04-08/

# 3. Reorder CTA before Sources, append canonical disclaimer
python3 blog-pipeline/scripts/03-fix-structure.py ~/blog-batches/2026-04-08/

# 4. Run automated checklist verification (will FAIL if any <img>/<svg>/<figure> remains)
bash blog-pipeline/scripts/04-verify.sh ~/blog-batches/2026-04-08/

# 5. Publish to Sanity (with custom short excerpts from excerpts.json)
python3 blog-pipeline/scripts/05-publish.py ~/blog-batches/2026-04-08/

# 6. Audit Sanity for structural issues, banned phrases, duplicate excerpts
python3 blog-pipeline/scripts/06-audit-sanity.py
```

**Read `RULES.md` first.** It documents every hard rule the pipeline enforces, including the no-images policy and the banned phrase list.

## Critical Rules — Bugs We Hit and How We Fixed Them

### 1. SVGs cannot be stored in Sanity Portable Text
**The bug:** We wrote `<figure class="viz"><svg>...</svg></figure>` blocks. Sanity's HTML-to-Portable-Text converter has no SVG block type and dumped the chart's text labels as paragraphs. Articles rendered with raw axis labels and category names instead of charts.

**The fix:** Always convert SVGs to PNGs FIRST using `cairosvg.svg2png(bytestring=svg, write_to=path, output_width=1800)`. Reference them as `<img>` tags. The publisher auto-uploads to Sanity as image assets.

**Script that handles this:** `scripts/01-svg-to-png.py`

### 2. Sanity CDN converts PNG to AVIF and destroys chart text
**The bug:** Sanity's image URL builder defaults to `?auto=format` which serves AVIF to modern browsers. AVIF's lossy compression destroys text and sharp edges in chart images. Charts looked unreadable.

**The fix:** Use `format('png')` instead of `auto('format')` for chart images. The blog renderer detects data viz by alt text keywords (chart, bar, visualization, gauge, comparison) and routes them through `getSanityImageUrlAsPng()`.

**Where it's enforced:** `Silvia-Web/lib/sanity/image.ts` and `components/blog/blog-portable-text.tsx`

### 3. CSP blocks Sanity CDN images
**The bug:** Vercel staging had no `cdn.sanity.io` in the CSP `img-src` directive. Raw `<img>` tags pointing to Sanity CDN were silently blocked by browsers. `next/image` worked because it proxies through `/_next/image` which counts as 'self'.

**The fix:** `https://cdn.sanity.io` is now in `middleware.ts` `img-src`. Don't remove it.

### 4. Sanity caches images by content hash
**The bug:** When fixing a chart and re-uploading the same filename, Sanity reused the cached asset instead of replacing it. Our "fixed" charts kept showing the old broken versions.

**The fix:** When updating a chart, give it a NEW filename (`-v2.png`, `-v3.png`). Or delete the post via API and republish to force a new asset hash. **Same filename = same asset = cached old image.**

### 5. CSS leaked into article body as paragraph text
**The bug:** Some articles came wrapped in `<!DOCTYPE html><html><head><style>...</style></head><body>`. The portable-text converter stripped the html/head/body tags but dumped the `<style>` block content as text paragraphs. The blog page rendered raw CSS rules at the top.

**The fix:** `scripts/02-clean-html.py` strips all wrapper tags AND any `<style>`/`<script>`/`<meta>`/`<title>` elements before publishing.

### 6. Metadata strip became the excerpt
**The bug:** Some articles had `<p><strong>April 4, 2026</strong> | How-To</p>` as the first paragraph after `<h1>`. The publisher used the first `<p>` as the excerpt, so the blog page showed "April 4, 2026 | How-To" as the article preview instead of the actual lead.

**The fix:** `scripts/02-clean-html.py` detects first-paragraph metadata patterns (date + pipe + category) and strips them. The real lead becomes the first paragraph.

### 7. Excerpt duplicated as first body paragraph
**The bug:** The publisher's default excerpt is the first `<p>` verbatim. The blog page renders both the excerpt (styled as intro) AND the body (which starts with that exact paragraph). Result: the same 300-character paragraph appears twice in a row at the top of every article.

**The fix:** Always pass `--excerpt "summary text"` to the publisher with a 100-150 char summarized version. Never let it default to the first body paragraph.

**Where to put excerpts:** `scripts/05-publish.py` reads from `excerpts.json` next to the HTML files.

### 8. CTA hidden after Sources list
**The bug:** Articles had Sources as the second-to-last section, then the CTA, then disclaimer. Readers never saw the CTA because nobody scrolls through a source list to find it.

**The fix:** CTA goes BEFORE the Sources `<h2>`. Disclaimer stays at the very end. `scripts/03-fix-structure.py` enforces this ordering on every article.

### 9. Vercel staging needed Sanity read token
**The bug:** Vercel staging env had only the public Sanity vars (`NEXT_PUBLIC_SANITY_*`). The Sanity client queried unauthenticated, the `staging` dataset's public visibility only exposes `sanity.imageAsset`, and post documents required auth. Result: blog page rendered empty.

**The fix:** Add `SANITY_STAGING_WRITE_TOKEN` (or a dedicated read token) to Vercel's Preview env scoped to the `staging` branch. Already done — don't remove it.

### 10. Chart label clipping
**The bug:** Long category names (`"Federal Government"`, `"Treaty Rate (EU, Japan, Korea)"`, `"Commercial Construction"`) overflowed their viewBox and got clipped. Bars with long red `-28%` values pushed labels off-screen.

**The fix:**
- Use viewBox 800-900px wide (NOT 700)
- 40px+ padding on all sides
- Long category names: split into two `<text>` elements stacked
- Long values inside long bars: white text INSIDE the bar, not to the left
- Every bar MUST have both a category label AND a value label

**Script that catches this:** `scripts/04-verify.sh` runs the automated checklist; chart visual review is manual but mandatory.

## Directory layout for each batch

```
~/blog-batches/2026-04-08/
├── 01-article-slug.html         # Source HTML, no doctype/html/head wrapping
├── 02-article-slug.html
├── ...
├── images/                       # Auto-created by 01-svg-to-png.py
│   ├── 01-article-slug-chart-1.png
│   └── ...
└── excerpts.json                 # Custom short excerpts, REQUIRED
```

## excerpts.json format

```json
{
  "01-article-slug.html": {
    "excerpt": "100-150 char summary, NOT the first paragraph",
    "categories": "macro,jobs,fed",
    "published_at": "2026-04-08T09:00:00Z"
  },
  ...
}
```
