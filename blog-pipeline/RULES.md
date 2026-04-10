# Blog Pipeline — Hard Rules

These are NON-NEGOTIABLE rules baked into the pipeline. Every script enforces them. Every writer prompt references them.

## Content Rules

### MUST include
1. `<h1>` title with the key number or insight
2. 3-5 `<h2>` sections
3. 1-2 HTML `<table>` with `<thead>` and `<tbody>` (data-rich)
4. `<h2>Frequently Asked Questions</h2>` followed by 3-5 `<h3>` Q&As with `<p>` answers
5. `<h2>Sources</h2>` followed by `<ul>` with at least 3 `<li><a href="...">source</a></li>` entries
6. CTA paragraph (canonical text — see below) BEFORE the Sources section
7. Disclaimer paragraph (canonical text — see below) at the very end
8. Word count: 900-1,500 words

### MUST NOT include
1. **NO chart images / SVGs / data visualizations.** Removed entirely from the pipeline as of April 6, 2026 because they were causing more visual quality issues than they solved. We may revisit later with a different approach. **DO NOT add `<img>`, `<svg>`, or `<figure>` tags for charts.**
2. **NO `<!DOCTYPE>`, `<html>`, `<head>`, `<style>`, `<script>`, `<meta>`, `<link>`, `<title>`, or `<body>` wrapper tags.** Sanity strips them and dumps the contents as paragraph text. The HTML should start directly with `<h1>` and contain only body-level elements.
3. **NO metadata strip lines** like `<p><strong>April 4, 2026</strong> | How-To</p>` after the `<h1>`. The first `<p>` becomes the SEO description if no custom excerpt is provided.
4. **NO em dashes** (—). Use commas or periods.
5. **NO exclamation marks**, **NO emojis**, **NO hashtags**.
6. **NO banned AI words:** delve, robust, leverage, pivotal, nuanced, catalyst, holistic, comprehensive, multifaceted, encompassing, testament, transformative, streamline, furthermore, moreover, additionally.
7. **NO scene-setting openers** like "In today's market..." or "As investors digest...".
8. **NO summary paragraphs** like "In summary..." or "Overall...".

## Banned Phrases

These phrases are explicitly forbidden across the entire blog system:

- **"Consult a qualified professional before making financial decisions"** — removed from blog disclaimer template, removed from author page, banned in `06-audit-sanity.py`. Do NOT add this to any article disclaimer or any landing page copy. The canonical disclaimer is the 3-sentence version below.
- **"Consult a qualified professional"** (any variant) — same rule.
- **"Always consult a qualified"** — same rule.

## Canonical Strings (use exactly these — no variations)

### CTA (placed BEFORE Sources section)
```html
<p>What does this mean for your portfolio? <a href="https://cfosilvia.com">Ask Silvia</a>.</p>
```

### Disclaimer (placed at the very end of the article)
```html
<p><em>This content is for informational purposes only. It is not financial, investment, or legal advice. Past performance does not guarantee future results.</em></p>
```

## Article Structure (top to bottom)

```
<h1>Title</h1>
<p>Lead paragraph — first sentence is the data point</p>
<p>Second paragraph — the "so what"</p>

<h2>Section 1</h2>
<p>...</p>

<h2>Section 2 (with table)</h2>
<table>
  <thead><tr><th>...</th></tr></thead>
  <tbody><tr><td>...</td></tr></tbody>
</table>
<p>...</p>

<h2>Section 3</h2>
<p>...</p>

<h2>Section 4 (with second table)</h2>
<table>...</table>

<h2>Frequently Asked Questions</h2>
<h3>Question 1?</h3>
<p>Answer 1</p>
<h3>Question 2?</h3>
<p>Answer 2</p>
<h3>Question 3?</h3>
<p>Answer 3</p>

<p>What does this mean for your portfolio? <a href="https://cfosilvia.com">Ask Silvia</a>.</p>

<h2>Sources</h2>
<ul>
  <li><a href="https://...">Source 1</a></li>
  <li><a href="https://...">Source 2</a></li>
  <li><a href="https://...">Source 3</a></li>
</ul>

<p><em>This content is for informational purposes only. It is not financial, investment, or legal advice. Past performance does not guarantee future results.</em></p>
```

## Excerpt Rules

The publisher defaults to using the first `<p>` as the excerpt. This causes a visible duplicate paragraph on the rendered blog page (excerpt rendered as intro, then body starts with the same text).

**ALWAYS pass a custom `--excerpt` to the publisher** with a 100-150 char summary that is NOT identical to the first paragraph.

The `excerpts.json` file in each batch directory must contain a custom excerpt for every article. The publisher script (`05-publish.py`) requires it.
