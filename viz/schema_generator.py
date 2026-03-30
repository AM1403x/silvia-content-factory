"""
CFO Silvia Content Factory — Schema & Meta Generation

Generates JSON-LD structured data (Article, FAQPage) and
the per-article meta.json that powers SEO and pipeline tracking.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SITE_URL, AUTHOR_NAME, AUTHOR_URL, PUBLISHER_NAME


def generate_article_schema(
    title: str,
    date_published: str,
    date_modified: str,
    description: str,
    slug: str,
) -> dict:
    """Return an Article JSON-LD schema dict.

    Follows schema.org/Article with author=Silvia, publisher=CFO Silvia,
    and a canonical URL derived from the slug.

    Args:
        title: Article headline.
        date_published: ISO 8601 date string (e.g. "2026-03-30").
        date_modified: ISO 8601 date string.
        description: Meta description (aim for 150-160 chars).
        slug: URL-safe slug for the article.

    Returns:
        Dict ready for JSON serialization as a <script type="application/ld+json">.
    """
    canonical = f"{SITE_URL}/{slug}/"
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "datePublished": date_published,
        "dateModified": date_modified,
        "url": canonical,
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": canonical,
        },
        "author": {
            "@type": "Person",
            "name": AUTHOR_NAME,
            "url": AUTHOR_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": PUBLISHER_NAME,
            "url": SITE_URL,
            "logo": {
                "@type": "ImageObject",
                "url": f"{SITE_URL}/logo.png",
            },
        },
        "image": {
            "@type": "ImageObject",
            "url": f"{SITE_URL}/images/{slug}-hero.png",
        },
    }


def generate_faq_schema(faq_pairs: list[tuple[str, str]]) -> dict:
    """Return a FAQPage JSON-LD schema dict.

    Args:
        faq_pairs: List of (question, answer) tuples.

    Returns:
        Dict representing the FAQPage structured data.
    """
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": answer,
                },
            }
            for question, answer in faq_pairs
        ],
    }


def generate_meta_json(
    title: str,
    slug: str,
    keywords: list[str],
    article_type: str,
    variant: str,
    word_count: int,
    faq_questions: list[str],
    cta: str,
    viz_paths: list[str],
    x_post_candidate: bool = False,
    date_published: Optional[str] = None,
    date_modified: Optional[str] = None,
    description: Optional[str] = None,
    ticker: Optional[str] = None,
) -> dict:
    """Build the complete meta.json for a pipeline-produced article.

    This is the single source of truth consumed by the publishing step,
    the dedup engine, and the freshness monitor.

    Args:
        title: Headline.
        slug: URL slug.
        keywords: Ordered list; first element is the primary keyword.
        article_type: One of ARTICLE_TYPES (ticker, howto, scenario, etc.).
        variant: Writer variant letter (A/B/C/D).
        word_count: Final word count of the article body.
        faq_questions: Question strings for the FAQ schema.
        cta: Call-to-action sentence.
        viz_paths: Absolute or relative paths to rendered viz PNGs.
        x_post_candidate: Flag this article for the daily X post selection.
        date_published: ISO date; defaults to today.
        date_modified: ISO date; defaults to today.
        description: Meta description; auto-generated if omitted.
        ticker: Stock ticker if this is a ticker/earnings article.

    Returns:
        Dict ready to write to disk as meta.json.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    pub_date = date_published or today
    mod_date = date_modified or today
    desc = description or f"{title} -- analysis by {PUBLISHER_NAME}."

    # Build FAQ schema if we have questions
    # (answers may be empty until the writer populates them)
    faq_pairs = [(q, "") for q in faq_questions]

    article_schema = generate_article_schema(title, pub_date, mod_date, desc, slug)
    faq_schema = generate_faq_schema(faq_pairs) if faq_pairs else None

    return {
        "title": title,
        "slug": slug,
        "url": f"{SITE_URL}/{slug}/",
        "article_type": article_type,
        "writer_variant": variant,
        "ticker": ticker,
        "keywords": {
            "primary": keywords[0] if keywords else "",
            "secondary": keywords[1:] if len(keywords) > 1 else [],
        },
        "word_count": word_count,
        "date_published": pub_date,
        "date_modified": mod_date,
        "description": desc,
        "cta": cta,
        "x_post_candidate": x_post_candidate,
        "visualizations": [
            {
                "index": i + 1,
                "path": path,
                "filename": Path(path).name,
            }
            for i, path in enumerate(viz_paths)
        ],
        "faq_questions": faq_questions,
        "schema": {
            "article": article_schema,
            "faq": faq_schema,
        },
    }
