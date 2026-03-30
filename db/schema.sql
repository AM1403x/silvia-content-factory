-- CFO Silvia Content Factory — Database Schema

CREATE TABLE IF NOT EXISTS articles (
    id              TEXT PRIMARY KEY,
    published_at    DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    article_type    TEXT NOT NULL,
    primary_keyword TEXT NOT NULL,
    secondary_keywords TEXT,
    ticker          TEXT,
    title           TEXT NOT NULL,
    url_slug        TEXT NOT NULL UNIQUE,
    word_count      INTEGER NOT NULL,
    summary_200     TEXT NOT NULL,
    full_text       TEXT NOT NULL,
    embedding       BLOB,
    writer_variant  TEXT NOT NULL,
    pillar_page_id  TEXT,
    cluster_id      TEXT,
    page_views_7d   INTEGER DEFAULT 0,
    page_views_30d  INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'published'
);

CREATE TABLE IF NOT EXISTS paragraph_fingerprints (
    id              TEXT PRIMARY KEY,
    article_id      TEXT NOT NULL,
    paragraph_index INTEGER NOT NULL,
    trigram_hash    TEXT NOT NULL,
    first_20_words  TEXT NOT NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS content_calendar (
    id              TEXT PRIMARY KEY,
    scheduled_date  DATE NOT NULL,
    batch           TEXT NOT NULL,
    article_type    TEXT NOT NULL,
    topic           TEXT NOT NULL,
    primary_keyword TEXT NOT NULL,
    ticker          TEXT,
    writer_variant  TEXT NOT NULL,
    status          TEXT DEFAULT 'scheduled',
    dedup_cleared   BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS retry_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    article_type    TEXT NOT NULL,
    topic           TEXT NOT NULL,
    primary_keyword TEXT NOT NULL,
    queued_at       DATETIME NOT NULL,
    reason          TEXT,
    status          TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS pillar_pages (
    id              TEXT PRIMARY KEY,
    cluster_name    TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    url_slug        TEXT NOT NULL UNIQUE,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date        DATE NOT NULL,
    article_id      TEXT,
    article_type    TEXT,
    topic           TEXT,
    status          TEXT NOT NULL,
    agent_timings   TEXT,
    error_message   TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_articles_type ON articles(article_type);
CREATE INDEX IF NOT EXISTS idx_articles_keyword ON articles(primary_keyword);
CREATE INDEX IF NOT EXISTS idx_articles_ticker ON articles(ticker);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_updated ON articles(updated_at);
CREATE INDEX IF NOT EXISTS idx_articles_views ON articles(page_views_7d);
CREATE INDEX IF NOT EXISTS idx_calendar_date ON content_calendar(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_calendar_status ON content_calendar(status);
CREATE INDEX IF NOT EXISTS idx_fingerprints_article ON paragraph_fingerprints(article_id);
CREATE INDEX IF NOT EXISTS idx_retry_status ON retry_queue(status);
