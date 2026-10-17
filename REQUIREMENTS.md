# Daily Digest: Requirements

> **Project:** AI agent (Python, LangChain, LangGraph) that fetches RSS feeds, filters by topic, summarizes articles in three tones, and publishes a static dashboard.
> **Deployment:** GitHub Actions cron job + GitHub Pages. No server, no database server.
> **Status:** v2.0 (matches `ARCHITECTURE.md`, `SECURITY_RULES.md`, `DESIGN.md`, `PHASES.md`)

---

## 0. Instructions for AI Assistants (READ FIRST)

1. Read all five docs before writing code: `REQUIREMENTS.md`, `ARCHITECTURE.md`, `SECURITY_RULES.md`, `DESIGN.md`, `PHASES.md`.
2. Build **one phase at a time** (see `PHASES.md`). Do not start a later phase early.
3. Keep it simple. Use only the stack in Section 7. Ask before adding any library.
4. Never hardcode secrets or model names. Read `GROQ_API_KEY` and `GROQ_MODEL` from environment variables. Model IDs get retired, so check Groq's current docs.
5. Never invent article content. Summaries use only the fetched title and description. If there is not enough text, mark `insufficient_content`.
6. Every network and LLM call needs a timeout, error handling, and a logged failure. One bad feed or one failed summary must never crash the run.
7. Write typed Python (type hints, Pydantic) and small single-purpose functions.
8. Write tests with the code. Mock the network and the LLM. Tests never call real services.
9. If something is unclear or conflicts with another doc, ask **one** specific question.
10. After each task, report: what changed, files touched, how to run, how to test.

---

## 1. Problem

Reading many news sources every day is slow. This project collects articles from RSS feeds, keeps the topics the user cares about, and shows short summaries in a reading style the user picks. It runs automatically once a day with no server to maintain.

## 2. Goals and Non-Goals

### Goals
- Fetch about 12 configurable RSS feeds daily.
- Remove duplicates, tag topics, and extract a thumbnail when available.
- Summarize selected articles with **3 bullets** in **3 tones**: Balanced, Technical, Beginner Friendly.
- Cache summaries so the same article and tone is never summarized twice.
- Publish a static dashboard (see `DESIGN.md`) on GitHub Pages.
- Run on a **GitHub Actions cron** and on demand ("Run workflow").

### Non-Goals (do NOT build)
- A backend server or REST API.
- User accounts or login.
- Full-text scraping of paywalled sites.
- Real-time updates, push notifications, or a mobile app.
- Model training or fine-tuning.

## 3. Use Cases

| ID | Use case |
|----|----------|
| UC-1 | Open the site and read today's digest. |
| UC-2 | Toggle topic chips and add a custom topic to filter articles. |
| UC-3 | Switch tone (Balanced, Technical, Beginner Friendly) and see summaries change instantly. |
| UC-4 | Search articles and sort by Most Relevant or Newest. |
| UC-5 | Bookmark articles (saved in the browser). |
| UC-6 | See stats: sources by topic, articles processed and selected, model, last run, next run. |
| UC-7 | Trigger a fresh run from GitHub ("Run Digest Now" opens the workflow page). |

## 4. Functional Requirements

### 4.1 Ingestion
- **FR-1** Read feeds from `feeds.yaml` (name, URL, `source_type`: `arxiv`, `hn`, or `rss`, optional default topic).
- **FR-2** Fetch feeds in parallel with timeout (10 s default), 2 retries, size limit, redirect limit, and the SSRF guard from `SECURITY_RULES.md`.
- **FR-3** Parse each entry into `title`, `url`, `published_at`, `source`, `source_type`, `description`, `image_url`.
- **FR-4** `image_url` comes from `media_thumbnail`, `media_content`, or an image `enclosure`. Keep `https` URLs only; otherwise `null`.
- **FR-5** A failed feed is recorded in `errors`; the run continues.

### 4.2 Deduplication
- **FR-6** Deduplicate by normalized URL and by normalized title.
- **FR-7** Article `id` is the sha256 of the normalized URL.

### 4.3 Topics
- **FR-8** Topics come from `feeds.yaml` keyword lists. Default topics: AI Agents, LLMs, Python, Backend, System Design, Machine Learning, DevOps, Cloud, Productivity.
- **FR-9** Tag each article with all topics whose keywords appear in the title or description. Use an LLM classification call only for a small number of untagged articles (optional, capped).
- **FR-10** Custom topics added in the UI are matched **in the browser** by keyword. The pipeline does not know them.

### 4.4 Summarization
- **FR-11** Each summary has **exactly 3 bullets**, each at most 25 words, via Pydantic structured output.
- **FR-12** Tone keys: `balanced`, `technical`, `beginner_friendly`.
- **FR-13** Summarize all three tones for each selected article. Cap selected articles per run with `MAX_ARTICLES_PER_RUN` (default 15), which keeps the LLM calls to at most about 45 per run.
- **FR-14** Cache key is `(article_id, tone)`. Cached pairs are never sent to the LLM again.
- **FR-15** Limit LLM concurrency (default 4); back off on rate limits; retry a schema failure once, then mark `failed`.
- **FR-16** Articles with too little text get `status: "insufficient_content"` without an LLM call.

### 4.5 Output
- **FR-17** Write `data/digest.json` and `data/run.json` (shapes in `DESIGN.md` Section 8).
- **FR-18** Keep only articles from the last 7 days in `digest.json`, newest first, maximum 60.
- **FR-19** Write `data/cache.json` (summaries by `article_id` and tone) and prune entries older than 30 days.
- **FR-20** `run.json` records status (`success`, `partial`, `failed`), feed counts, items parsed and unique, summaries ok and failed, model, duration, and errors.

### 4.6 Scheduling and deployment
- **FR-21** A GitHub Actions workflow runs on a cron schedule and on `workflow_dispatch`.
- **FR-22** The workflow runs the pipeline, commits changed data files, and the site is served from GitHub Pages (`docs/`).
- **FR-23** Concurrent runs are prevented with a workflow `concurrency` group.

### 4.7 Frontend
- **FR-24** Implemented as described in `DESIGN.md`: plain HTML, CSS, and JavaScript reading the JSON files.

## 5. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | A full run completes in under 5 minutes on a GitHub-hosted runner. |
| NFR-2 | Secrets only through GitHub Actions secrets and local `.env`; never committed or logged. |
| NFR-3 | Unit test coverage of at least 80% on pure logic (dedupe, topics, URL normalization, schemas, cache). |
| NFR-4 | A second run with no new articles makes **zero** LLM calls. |
| NFR-5 | Total LLM usage per run stays within the Groq free-tier limits; one failed summary never fails the run. |
| NFR-6 | The site loads in under 2 seconds on a normal connection (small JSON, no heavy assets). |
| NFR-7 | Respect feed servers: set a User-Agent and use ETag or Last-Modified when available. |

## 6. Data and Files

| File | Written by | Purpose |
|------|------------|---------|
| `feeds.yaml` | You | Feed list, source types, topic keywords |
| `data/cache.json` | Pipeline | Cached summaries by `(article_id, tone)` |
| `data/digest.json` | Pipeline | Articles, topics, topic counts, summaries for the UI |
| `data/run.json` | Pipeline | Run status and metrics for the UI |
| `docs/data/*.json` | GitHub Action | Copies of the two UI files, served by Pages |

## 7. Tech Stack (fixed)

| Layer | Choice |
|-------|--------|
| Language | Python 3.11+ |
| Agent orchestration | LangGraph |
| LLM interface | LangChain (`langchain-core`, `langchain-groq`) |
| LLM provider | Groq (model from `GROQ_MODEL`) |
| RSS | `feedparser` |
| HTTP | `httpx` (async) |
| Validation and config | Pydantic v2, `pydantic-settings`, `PyYAML` |
| Tests and lint | `pytest`, `pytest-asyncio`, `respx`, `ruff` |
| Frontend | Plain HTML, CSS, vanilla JS (no framework, no CDN) |
| Scheduling and deploy | GitHub Actions cron, GitHub Pages |

## 8. Milestones

See `PHASES.md`. Four phases: (1) setup and fetch, (2) summarize with LangGraph, (3) static web UI, (4) GitHub cron and deploy.

## 9. Acceptance Criteria

- Manual "Run workflow" completes, commits fresh JSON, and the Pages site shows the new digest.
- Every article shows 3 bullets in each available tone; switching tone needs no reload.
- Topic chips, custom topics, search, sort, and bookmarks work in the browser.
- One broken feed URL produces a `partial` run, not a failure.
- A second run with no new articles makes zero LLM calls.
- No secret appears in the repo, workflow logs, or the site.
- `pytest` and `ruff` pass in CI.
- README has a live link, screenshot, setup steps, and one design trade-off.

## 10. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Groq model retired or renamed | Model comes from `GROQ_MODEL`; README says to check Groq's model list. |
| LLM rate limits | Concurrency limit, backoff, article cap, cache. |
| Bad or slow feeds | Timeouts, retries, per-feed errors, `partial` status. |
| Hallucinated summaries | Prompt restricts to provided text; link to the source; validate schema. |
| GitHub cron delays or skips | Accept small delays; "Run workflow" is the manual fallback; UI shows a stale warning after 36 hours. |
| Repo grows from daily commits | Cap JSON size, prune old data, keep only the last 7 days of articles. |
| Prompt injection from article text | Treat text as data; no tools for the LLM; schema-validated output. |

## 11. Definition of Done

Code merged, tests green, workflow succeeded at least once on schedule, Pages site live, README complete, and every acceptance criterion in Section 9 verified.
