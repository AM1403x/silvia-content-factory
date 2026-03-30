"""
CFO Silvia Content Factory — Main Pipeline Orchestrator

Reads today's content calendar, runs each article through the 10-agent
pipeline (with 3 inter-stage checks), saves output, fingerprints paragraphs,
picks the best X-post candidate, and logs everything.

Pipeline order (from spec):
  Agent 1:  Researcher           (Claude Code with web search)
  Agent 2:  Research Auditor     (verifies data, max 2 loops)
  Agent 3:  Writer               (Silvia voice, variant rotation)
  Agent 4:  Write-up Auditor     (26-point checklist, max 3 loops)
  Agent 5:  Simplifier           (accessibility pass)
  CHECK 1:  Post-Simplifier Scan (Python regex, no LLM)
  Agent 6:  Fact Checker         (Claude Code with web search)
  CHECK 2:  Compliance Scan      (Python regex, no LLM)
  Agent 7:  Viz Strategist       (reads article, outputs spec sheet)
  Agent 8:  Viz Craftsman        (builds SVGs one at a time)
  Agent 9:  Viz Design Critic    (20-point audit, loops with Agent 8)
  Agent 10: Viz Integrator       (places visuals into article)
  CHECK 3:  Post-Viz Scan        (Python regex on new text only)

This orchestrator does NOT call Claude directly. It prepares input files
for each agent step and prints instructions for Claude Code to process.
The Python check scripts (CHECK 1-3) run inline automatically.
"""

import json
import hashlib
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    PROJECT_ROOT,
    PROMPTS_DIR,
    OUTPUT_DIR,
    LOGS_DIR,
    DB_PATH,
    ARTICLE_TYPES,
    WORD_COUNT_TARGETS,
    VIZ_COUNT_TARGETS,
    VARIANT_MODIFIERS,
    MAX_AUDIT_LOOPS,
    MAX_VIZ_CRITIC_LOOPS,
    MAX_RESEARCH_AUDIT_LOOPS,
)
from db.init_db import get_connection, init_database


# ── Logging ─────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("silvia_pipeline")
logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(
    LOGS_DIR / f"pipeline_{date.today().isoformat()}.log", encoding="utf-8"
)
_fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(logging.Formatter("%(levelname)-8s | %(message)s"))
logger.addHandler(_fh)
logger.addHandler(_ch)


# ── Pipeline steps ──────────────────────────────────────────────────────────────

class Step(Enum):
    """The 10 agents + 3 checks in exact spec order."""
    RESEARCHER          = auto()
    RESEARCH_AUDITOR    = auto()
    WRITER              = auto()
    WRITEUP_AUDITOR     = auto()
    SIMPLIFIER          = auto()
    CHECK_1             = auto()   # Post-Simplifier Scan (Python)
    FACT_CHECKER        = auto()
    CHECK_2             = auto()   # Compliance Scan (Python)
    VIZ_STRATEGIST      = auto()
    VIZ_CRAFTSMAN       = auto()
    VIZ_DESIGN_CRITIC   = auto()
    VIZ_INTEGRATOR      = auto()
    CHECK_3             = auto()   # Post-Viz Humanizer Scan (Python)
    DONE                = auto()


AGENT_PROMPT_FILES = {
    Step.RESEARCHER:        "agent_01_researcher.txt",
    Step.RESEARCH_AUDITOR:  "agent_02_research_auditor.txt",
    Step.WRITER:            "agent_03_writer.txt",
    Step.WRITEUP_AUDITOR:   "agent_04_writeup_auditor.txt",
    Step.SIMPLIFIER:        "agent_05_simplifier.txt",
    Step.FACT_CHECKER:      "agent_06_fact_checker.txt",
    Step.VIZ_STRATEGIST:    "agent_07_viz_strategist.txt",
    Step.VIZ_CRAFTSMAN:     "agent_08_viz_craftsman.txt",
    Step.VIZ_DESIGN_CRITIC: "agent_09_viz_design_critic.txt",
    Step.VIZ_INTEGRATOR:    "agent_10_viz_integrator.txt",
}

CHECK_STEPS = {Step.CHECK_1, Step.CHECK_2, Step.CHECK_3}


# ── Article state ───────────────────────────────────────────────────────────────

@dataclass
class ArticleState:
    calendar_id: str
    article_type: str
    topic: str
    primary_keyword: str
    ticker: Optional[str]
    writer_variant: str
    slug: str

    current_step: Step = Step.RESEARCHER
    status: str = "pending"       # pending | in_progress | done | failed
    error: Optional[str] = None

    # Artifact paths (filled as pipeline runs)
    research_brief_path: Optional[str] = None
    research_packet_path: Optional[str] = None
    draft_path: Optional[str] = None
    audited_draft_path: Optional[str] = None
    simplified_path: Optional[str] = None
    fact_checked_path: Optional[str] = None
    viz_spec_path: Optional[str] = None
    viz_svg_paths: list[str] = field(default_factory=list)
    viz_png_paths: list[str] = field(default_factory=list)
    final_md_path: Optional[str] = None
    meta_json_path: Optional[str] = None

    # Pre-viz article text (for CHECK 3 diff)
    pre_viz_text: Optional[str] = None

    # Timing
    agent_timings: dict[str, float] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # Loop counters
    research_audit_loops: int = 0
    writeup_audit_loops: int = 0
    viz_critic_loops: int = 0

    @property
    def output_dir(self) -> Path:
        return OUTPUT_DIR / date.today().isoformat() / self.slug

    @property
    def work_dir(self) -> Path:
        d = self.output_dir / "work"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def advance(self) -> None:
        members = list(Step)
        idx = members.index(self.current_step)
        if idx + 1 < len(members):
            self.current_step = members[idx + 1]

    def to_dict(self) -> dict:
        return {
            "calendar_id": self.calendar_id,
            "article_type": self.article_type,
            "topic": self.topic,
            "slug": self.slug,
            "current_step": self.current_step.name,
            "status": self.status,
            "error": self.error,
            "agent_timings": self.agent_timings,
        }


class PipelineState:
    def __init__(self, run_date: Optional[date] = None):
        self.run_date = run_date or date.today()
        self.articles: dict[str, ArticleState] = {}
        self.x_post_candidates: list[str] = []
        self.run_id = uuid.uuid4().hex[:12]
        self.started_at = datetime.now()

    def add_article(self, state: ArticleState) -> None:
        self.articles[state.calendar_id] = state

    @property
    def pending(self):
        return [a for a in self.articles.values() if a.status == "pending"]

    @property
    def completed(self):
        return [a for a in self.articles.values() if a.status == "done"]

    @property
    def failed(self):
        return [a for a in self.articles.values() if a.status == "failed"]

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_date": self.run_date.isoformat(),
            "total": len(self.articles),
            "done": len(self.completed),
            "failed": len(self.failed),
            "pending": len(self.pending),
            "x_post_pick": self.x_post_candidates[0] if self.x_post_candidates else None,
        }


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _make_slug(topic: str) -> str:
    import re
    slug = topic.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:80]


def _trigram_hash(text: str) -> str:
    words = text.lower().split()
    if len(words) < 3:
        raw = " ".join(words)
    else:
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words) - 2)]
        raw = "|".join(sorted(set(trigrams)))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def fingerprint_paragraphs(article_id: str, text: str) -> list[dict]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    results = []
    for idx, para in enumerate(paragraphs):
        if para.startswith("#") or len(para.split()) < 5:
            continue
        words = para.split()
        results.append({
            "id": uuid.uuid4().hex,
            "article_id": article_id,
            "paragraph_index": idx,
            "trigram_hash": _trigram_hash(para),
            "first_20_words": " ".join(words[:20]),
        })
    return results


# ── DB helpers ──────────────────────────────────────────────────────────────────

def _load_calendar_entries(target_date: date) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, scheduled_date, batch, article_type, topic,
                      primary_keyword, ticker, writer_variant, status
               FROM content_calendar
              WHERE status = 'scheduled' AND scheduled_date = ?
              ORDER BY batch, article_type""",
            (target_date.isoformat(),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _update_calendar_status(calendar_id: str, status: str) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE content_calendar SET status = ? WHERE id = ?", (status, calendar_id))
        conn.commit()
    finally:
        conn.close()


def _register_article(state: ArticleState) -> str:
    article_id = uuid.uuid4().hex
    now = datetime.now().isoformat()
    final_text = ""
    for p in (state.final_md_path, state.simplified_path, state.draft_path):
        if p and Path(p).exists():
            final_text = Path(p).read_text(encoding="utf-8")
            break
    word_count = len(final_text.split())
    summary = final_text[:200].replace("\n", " ").strip()
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO articles
               (id, published_at, updated_at, article_type, primary_keyword,
                ticker, title, url_slug, word_count, summary_200, full_text,
                writer_variant, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published')""",
            (article_id, now, now, state.article_type, state.primary_keyword,
             state.ticker, state.topic, state.slug, word_count, summary, final_text,
             state.writer_variant),
        )
        conn.commit()
    finally:
        conn.close()
    return article_id


def _store_fingerprints(article_id: str, text: str) -> int:
    fps = fingerprint_paragraphs(article_id, text)
    if not fps:
        return 0
    conn = get_connection()
    try:
        conn.executemany(
            """INSERT INTO paragraph_fingerprints
               (id, article_id, paragraph_index, trigram_hash, first_20_words)
               VALUES (:id, :article_id, :paragraph_index, :trigram_hash, :first_20_words)""",
            fps,
        )
        conn.commit()
    finally:
        conn.close()
    return len(fps)


def _log_pipeline_run(state: ArticleState, article_id: Optional[str] = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO pipeline_logs
               (run_date, article_id, article_type, topic, status, agent_timings, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date.today().isoformat(), article_id, state.article_type,
             state.topic, state.status, json.dumps(state.agent_timings), state.error),
        )
        conn.commit()
    finally:
        conn.close()


# ── Load prompt ─────────────────────────────────────────────────────────────────

def load_agent_prompt(step: Step, variant: str = None) -> Optional[str]:
    filename = AGENT_PROMPT_FILES.get(step)
    if not filename:
        return None
    path = PROMPTS_DIR / filename
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    # Inject variant modifier for Writer
    if step == Step.WRITER and variant and "{VARIANT_MODIFIER}" in text:
        modifier = VARIANT_MODIFIERS.get(variant, "")
        text = text.replace("{VARIANT_MODIFIER}", modifier)
    return text


# ── Prepare agent input files ───────────────────────────────────────────────────

def _prepare_agent_input(state: ArticleState) -> Path:
    step = state.current_step
    wd = state.work_dir

    if step == Step.RESEARCHER:
        data = {
            "topic": state.topic,
            "article_type": state.article_type,
            "primary_keyword": state.primary_keyword,
            "ticker": state.ticker,
            "word_count_range": WORD_COUNT_TARGETS.get(state.article_type, (800, 1500)),
        }
        path = wd / "01_research_brief.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        state.research_brief_path = str(path)
        return path

    elif step == Step.RESEARCH_AUDITOR:
        path = wd / "02_research_audit_input.txt"
        packet_path = state.research_packet_path or str(wd / "01_research_output.md")
        path.write_text(
            f"Review this research packet:\n\nFile: {packet_path}\n\n"
            f"Apply the full Research Auditor checklist.",
            encoding="utf-8",
        )
        return path

    elif step == Step.WRITER:
        path = wd / "03_writer_input.json"
        data = {
            "research_packet": state.research_packet_path or str(wd / "02_research_audit_output.md"),
            "article_type": state.article_type,
            "primary_keyword": state.primary_keyword,
            "ticker": state.ticker,
            "writer_variant": state.writer_variant,
            "word_count_range": WORD_COUNT_TARGETS.get(state.article_type, (800, 1500)),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    elif step == Step.WRITEUP_AUDITOR:
        path = wd / "04_writeup_audit_input.txt"
        draft = state.draft_path or str(wd / "03_writer_output.md")
        path.write_text(
            f"Audit this article draft:\n\nFile: {draft}\n\n"
            f"Run all 26 checks (22 humanizer + 4 SEO/GEO). Fix failures in-place.",
            encoding="utf-8",
        )
        return path

    elif step == Step.SIMPLIFIER:
        path = wd / "05_simplifier_input.txt"
        audited = state.audited_draft_path or str(wd / "04_writeup_audit_output.md")
        path.write_text(
            f"Simplify this article for accessibility:\n\nFile: {audited}\n\n"
            f"Target Flesch-Kincaid grade 8. Do not remove data. Do not introduce banned words.",
            encoding="utf-8",
        )
        return path

    elif step == Step.FACT_CHECKER:
        path = wd / "06_fact_checker_input.txt"
        simplified = state.simplified_path or str(wd / "05_simplifier_output.md")
        path.write_text(
            f"Fact-check this article:\n\nFile: {simplified}\n\n"
            f"Extract every quantitative claim. Verify against primary sources via web search.",
            encoding="utf-8",
        )
        return path

    elif step == Step.VIZ_STRATEGIST:
        path = wd / "07_viz_strategist_input.txt"
        article = state.fact_checked_path or state.simplified_path or str(wd / "06_fact_checker_output.md")
        path.write_text(
            f"Read this article and identify visualization opportunities:\n\nFile: {article}\n\n"
            f"Target: {VIZ_COUNT_TARGETS.get(state.article_type, 2)} visualizations.\n"
            f"Output a structured spec sheet.",
            encoding="utf-8",
        )
        return path

    elif step == Step.VIZ_CRAFTSMAN:
        path = wd / "08_viz_craftsman_input.txt"
        spec = state.viz_spec_path or str(wd / "07_viz_strategist_output.md")
        path.write_text(
            f"Build SVGs from this spec sheet:\n\nFile: {spec}\n\n"
            f"Build ONE at a time. Follow all SVG rules (color palette, typography, accessibility).",
            encoding="utf-8",
        )
        return path

    elif step == Step.VIZ_DESIGN_CRITIC:
        path = wd / "09_viz_critic_input.txt"
        path.write_text(
            f"Audit these SVGs against the 20-point quality checklist:\n\n"
            f"SVG files: {state.viz_svg_paths}\n\n"
            f"Score each. Below 18/20 = REVISE. Max 3 loops per visual.",
            encoding="utf-8",
        )
        return path

    elif step == Step.VIZ_INTEGRATOR:
        path = wd / "10_viz_integrator_input.txt"
        article = state.fact_checked_path or state.simplified_path or str(wd / "06_fact_checker_output.md")
        path.write_text(
            f"Place approved visuals into the article:\n\n"
            f"Article: {article}\n"
            f"SVGs: {state.viz_svg_paths}\n"
            f"Spec: {state.viz_spec_path}\n\n"
            f"Write lead-ins and interpretations. Check spacing rules.",
            encoding="utf-8",
        )
        return path

    # Fallback for check steps (they don't need input files)
    path = wd / f"{step.name.lower()}_marker.txt"
    path.write_text(f"Automated check step: {step.name}", encoding="utf-8")
    return path


# ── Run Python checks ──────────────────────────────────────────────────────────

def _run_check_1(state: ArticleState) -> tuple[bool, str, Optional[str]]:
    """Post-Simplifier Scan: banned words, em dashes, curly quotes, single-sentence paragraphs."""
    from checks.post_simplifier_scan import post_simplifier_scan

    text_path = state.simplified_path or str(state.work_dir / "05_simplifier_output.md")
    if not Path(text_path).exists():
        return True, "No simplified text found, skipping CHECK 1.", None

    text = Path(text_path).read_text(encoding="utf-8")
    result = post_simplifier_scan(text)

    if result["passed"]:
        clean_path = str(state.work_dir / "check1_clean.md")
        Path(clean_path).write_text(result["clean_text"], encoding="utf-8")
        state.simplified_path = clean_path
        return True, "CHECK 1 passed.", clean_path
    else:
        clean_path = str(state.work_dir / "check1_clean.md")
        Path(clean_path).write_text(result["clean_text"], encoding="utf-8")
        state.simplified_path = clean_path
        issues = "; ".join(result["issues"][:5])
        return False, f"CHECK 1 found issues (auto-fixed what possible): {issues}", clean_path


def _run_check_2(state: ArticleState) -> tuple[bool, str]:
    """Compliance Scan: no buy/sell/hold advice, no guaranteed returns."""
    from checks.compliance_scan import compliance_scan

    text_path = state.fact_checked_path or state.simplified_path or str(state.work_dir / "06_fact_checker_output.md")
    if not Path(text_path).exists():
        return True, "No text found for compliance scan."

    text = Path(text_path).read_text(encoding="utf-8")
    result = compliance_scan(text)

    if result["passed"]:
        return True, "CHECK 2 (compliance) passed."
    else:
        violations = "; ".join(str(v) for v in result["violations"][:3])
        return False, f"CHECK 2 BLOCKED: compliance violations found: {violations}"


def _run_check_3(state: ArticleState) -> tuple[bool, str]:
    """Post-Viz Humanizer Scan: check ONLY text added by the Integrator."""
    from checks.post_viz_scan import post_viz_scan

    final_path = state.final_md_path or str(state.work_dir / "10_viz_integrator_output.md")
    if not Path(final_path).exists():
        return True, "No final text found for post-viz scan."

    visualized = Path(final_path).read_text(encoding="utf-8")
    original = state.pre_viz_text or ""

    if not original:
        # Fall back to fact-checked text
        for p in (state.fact_checked_path, state.simplified_path):
            if p and Path(p).exists():
                original = Path(p).read_text(encoding="utf-8")
                break

    result = post_viz_scan(original, visualized)

    if result["passed"]:
        return True, "CHECK 3 (post-viz) passed."
    else:
        issues = "; ".join(result["issues"][:5])
        return False, f"CHECK 3 found issues in integrator text: {issues}"


# ── Dedup check ─────────────────────────────────────────────────────────────────

def _run_dedup_check(state: ArticleState) -> tuple[bool, str]:
    try:
        from dedup.dedup_engine import DedupEngine
        engine = DedupEngine()
        result = engine.full_check(
            primary_keyword=state.primary_keyword,
            article_type=state.article_type,
            topic=state.topic,
            ticker=state.ticker,
        )
        if not result.cleared:
            return False, f"Dedup {result.action}: {result.reason}"
        return True, f"Dedup cleared ({result.action})."
    except ImportError:
        return True, "Dedup module not available, skipped."
    except Exception as exc:
        logger.warning("Dedup error: %s", exc)
        return True, f"Dedup error (skipped): {exc}"


# ── Print instructions ──────────────────────────────────────────────────────────

def _print_agent_instruction(state: ArticleState, input_path: Path) -> None:
    step = state.current_step
    prompt_file = AGENT_PROMPT_FILES.get(step, "N/A")

    print("\n" + "=" * 72)
    print(f"  AGENT: {step.name} (step {list(Step).index(step) + 1}/13)")
    print(f"  Article: {state.topic} [{state.article_type}]")
    print(f"  Slug:    {state.slug}")
    print(f"  Input:   {input_path}")
    if prompt_file != "N/A":
        print(f"  Prompt:  prompts/{prompt_file}")
    print("=" * 72)

    if step in CHECK_STEPS:
        print("  >> Automated CHECK (Python, no LLM). Running now...")
    else:
        print(f"  >> Process with the agent prompt. Save output to: {state.work_dir}/")
    print()


# ── Process one step ────────────────────────────────────────────────────────────

def process_article_step(state: ArticleState) -> bool:
    """Execute the current pipeline step.
    Returns True if the article should continue, False if done/failed."""
    step = state.current_step
    start = datetime.now()

    if step == Step.DONE:
        return False

    logger.info("[%s] %s starting", state.slug, step.name)

    # ── CHECK 1: Post-Simplifier Scan ──────────────────────────────────────
    if step == Step.CHECK_1:
        passed, msg, clean_path = _run_check_1(state)
        state.agent_timings[step.name] = (datetime.now() - start).total_seconds()
        logger.info("[%s] %s", state.slug, msg)
        # CHECK 1 auto-fixes; always advance (issues are logged)
        state.advance()
        return True

    # ── CHECK 2: Compliance Scan ──────────────────────────────────────────
    elif step == Step.CHECK_2:
        passed, msg = _run_check_2(state)
        state.agent_timings[step.name] = (datetime.now() - start).total_seconds()
        logger.info("[%s] %s", state.slug, msg)
        if not passed:
            state.status = "failed"
            state.error = msg
            logger.error("[%s] COMPLIANCE BLOCK: %s", state.slug, msg)
            return False
        # Save pre-viz text for CHECK 3 diff
        for p in (state.fact_checked_path, state.simplified_path):
            if p and Path(p).exists():
                state.pre_viz_text = Path(p).read_text(encoding="utf-8")
                break
        state.advance()
        return True

    # ── CHECK 3: Post-Viz Humanizer Scan ──────────────────────────────────
    elif step == Step.CHECK_3:
        passed, msg = _run_check_3(state)
        state.agent_timings[step.name] = (datetime.now() - start).total_seconds()
        logger.info("[%s] %s", state.slug, msg)
        # Post-viz issues are logged but don't block
        state.advance()
        return True

    # ── Agent steps: prepare input and print instructions ─────────────────
    else:
        input_path = _prepare_agent_input(state)
        state.agent_timings[step.name] = (datetime.now() - start).total_seconds()
        _print_agent_instruction(state, input_path)
        state.advance()
        return True


# ── Pick X post candidate ──────────────────────────────────────────────────────

def _pick_x_post_candidate(pipeline: PipelineState) -> Optional[str]:
    priority = ["earnings", "ticker", "comparison", "scenario", "howto", "investor"]
    for atype in priority:
        for art in pipeline.completed:
            if art.article_type == atype:
                pipeline.x_post_candidates.append(art.slug)
                logger.info("X post candidate: %s (%s)", art.slug, art.article_type)
                return art.slug
    if pipeline.completed:
        pick = pipeline.completed[0].slug
        pipeline.x_post_candidates.append(pick)
        return pick
    return None


# ── Pipeline entry points ───────────────────────────────────────────────────────

def run_pipeline(target_date: Optional[date] = None) -> PipelineState:
    """Run the full daily pipeline for all scheduled articles."""
    target = target_date or date.today()
    pipeline = PipelineState(run_date=target)

    logger.info("=" * 72)
    logger.info("PIPELINE RUN: %s (run_id=%s)", target.isoformat(), pipeline.run_id)
    logger.info("=" * 72)

    if not DB_PATH.exists():
        init_database()

    entries = _load_calendar_entries(target)
    if not entries:
        logger.warning("No scheduled entries for %s", target.isoformat())
        return pipeline

    logger.info("Found %d calendar entries for %s", len(entries), target.isoformat())

    # Build article states
    for entry in entries:
        slug = _make_slug(entry["topic"])
        state = ArticleState(
            calendar_id=entry["id"],
            article_type=entry["article_type"],
            topic=entry["topic"],
            primary_keyword=entry["primary_keyword"],
            ticker=entry.get("ticker"),
            writer_variant=entry["writer_variant"],
            slug=slug,
        )
        pipeline.add_article(state)

    # Dedup check
    for state in list(pipeline.articles.values()):
        passed, msg = _run_dedup_check(state)
        logger.info("[%s] Dedup: %s", state.slug, msg)
        if not passed:
            state.status = "failed"
            state.error = msg
            _update_calendar_status(state.calendar_id, "dedup_blocked")
            _log_pipeline_run(state)

    # Process each article through all steps
    for state in list(pipeline.articles.values()):
        if state.status == "failed":
            continue

        state.status = "in_progress"
        state.started_at = datetime.now()
        _update_calendar_status(state.calendar_id, "in_progress")
        logger.info("\n>>> Processing: %s [%s]", state.topic, state.article_type)

        while state.current_step != Step.DONE and state.status != "failed":
            can_continue = process_article_step(state)
            if not can_continue:
                break

        if state.status != "failed":
            state.status = "done"
            state.finished_at = datetime.now()

            final_text = ""
            for p in (state.final_md_path, state.simplified_path, state.draft_path):
                if p and Path(p).exists():
                    final_text = Path(p).read_text(encoding="utf-8")
                    break

            if final_text:
                article_id = _register_article(state)
                fp_count = _store_fingerprints(article_id, final_text)
                logger.info("[%s] Registered %s, %d fingerprints", state.slug, article_id, fp_count)
                _log_pipeline_run(state, article_id)
            else:
                _log_pipeline_run(state)

            _update_calendar_status(state.calendar_id, "done")
        else:
            _update_calendar_status(state.calendar_id, "failed")
            _log_pipeline_run(state)

    x_pick = _pick_x_post_candidate(pipeline)
    if x_pick:
        logger.info("Daily X post candidate: %s", x_pick)

    summary = pipeline.summary()
    logger.info("\nPIPELINE SUMMARY: %s", json.dumps(summary, indent=2))
    return pipeline


def run_single_article(calendar_id: str) -> ArticleState:
    """Run the pipeline for a single calendar entry."""
    if not DB_PATH.exists():
        init_database()

    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT id, scheduled_date, batch, article_type, topic,
                      primary_keyword, ticker, writer_variant
               FROM content_calendar WHERE id = ?""",
            (calendar_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise ValueError(f"Calendar entry not found: {calendar_id}")

    entry = dict(row)
    slug = _make_slug(entry["topic"])
    state = ArticleState(
        calendar_id=entry["id"],
        article_type=entry["article_type"],
        topic=entry["topic"],
        primary_keyword=entry["primary_keyword"],
        ticker=entry.get("ticker"),
        writer_variant=entry["writer_variant"],
        slug=slug,
    )

    passed, msg = _run_dedup_check(state)
    logger.info("[%s] Dedup: %s", state.slug, msg)
    if not passed:
        state.status = "failed"
        state.error = msg
        _log_pipeline_run(state)
        return state

    state.status = "in_progress"
    state.started_at = datetime.now()

    while state.current_step != Step.DONE and state.status != "failed":
        process_article_step(state)

    if state.status != "failed":
        state.status = "done"
        state.finished_at = datetime.now()
        _log_pipeline_run(state)

    return state


# ── CLI ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CFO Silvia Pipeline Orchestrator")
    parser.add_argument("--date", type=str, default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--article", type=str, default=None, help="Run single calendar_id")
    args = parser.parse_args()

    if args.article:
        result = run_single_article(args.article)
        print(f"\nResult: {json.dumps(result.to_dict(), indent=2)}")
    else:
        target = date.fromisoformat(args.date) if args.date else None
        pipeline = run_pipeline(target)
        print(f"\nSummary: {json.dumps(pipeline.summary(), indent=2)}")
