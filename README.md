# Daily Digest

> A Python + LangGraph pipeline that fetches RSS feeds, filters by topic,
> summarises articles in three tones, and publishes a static dashboard —
> all for free, with no server to host.

**Live site:** <https://ganeshjh2004.github.io/daily-digest/>

<!-- Replace this line with an actual screenshot once the site is live -->
![Dashboard screenshot](docs/screenshot.png)

---

## How it works

```
GitHub Actions (cron 08:00 UTC daily + manual "Run workflow")
              │
              ▼
  python -m app.cli run          (LangGraph pipeline)
  ┌──────────────────────────────────────────────────┐
  │  feeds.yaml ──► fetch ──► parse ──► dedupe       │
  │  ──► topics ──► select ──► summarise (Groq)      │
  │  ──► validate ──► save                           │
  └───────────────┬──────────────────────────────────┘
                  │ writes
                  ▼
         data/cache.json          (summary cache, 30-day TTL)
         data/digest.json  ──► docs/data/digest.json  ──► GitHub Pages
         data/run.json     ──► docs/data/run.json     ──►  (static site)
```

The pipeline does all the heavy work once a day and writes small JSON files.
The browser reads those files directly — there is no API, no database, and
nothing to attack on the server side.

---

## Features

- Fetches ~12 configurable RSS / arXiv / Hacker News feeds in parallel
- Deduplicates by URL and title; tags each article with up to 9 topics
- Summarises each selected article with **3 bullets** in **3 tones**:
  Balanced, Technical, Beginner Friendly
- Caches summaries by `(article_id, tone)` — a second run with no new
  articles makes **zero** LLM calls
- Filter, search, sort, switch tone, and bookmark entirely in the browser
- Stale-data and failed-run warnings shown in the UI
- SSRF guard, HTML stripping, CSP meta tag, and no `innerHTML` with
  dynamic data

---

## Local setup

### Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- A [Groq](https://console.groq.com/) account and API key

### Install

```bash
# 1. Clone the repo
git clone https://github.com/Ganeshjh2004/daily-digest.git
cd daily-digest

# 2. Copy the example env file — NEVER commit .env
cp .env.example .env

# 3. Fill in your real values in .env (see the table below)
#    Open .env in your editor and replace the placeholders.

# 4. Install all dependencies (including dev extras)
uv sync --all-extras
```

### Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GROQ_API_KEY` | **yes** | — | Your Groq API key (secret) |
| `GROQ_MODEL` | **yes** | — | Groq model ID — check [Groq's model list](https://console.groq.com/docs/models) for the current name |
| `FEED_TIMEOUT_S` | no | `10` | Per-feed HTTP timeout in seconds |
| `MAX_FEED_BYTES` | no | `2000000` | Maximum feed response size (bytes) |
| `MAX_REDIRECTS` | no | `3` | Maximum HTTP redirects per feed |
| `MAX_ARTICLES_PER_RUN` | no | `15` | Articles summarised per run (caps LLM calls) |
| `LLM_CONCURRENCY` | no | `4` | Parallel LLM calls |
| `LLM_TIMEOUT_S` | no | `30` | Per-LLM-call timeout in seconds |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

> **Never commit `.env`.** It is listed in `.gitignore`. Only `.env.example`
> (with placeholder values) belongs in the repo.

---

## Running the pipeline locally

```bash
# Full run — calls Groq, writes data/*.json
uv run python -m app.cli run

# Dry run — uses a deterministic fake summariser, no API key needed
uv run python -m app.cli run --fake-llm

# Debug: fetch feeds and print unique, topic-tagged articles
uv run python -m app.cli fetch
```

### Preview the site

```bash
cd docs
python -m http.server 8000
# open http://localhost:8000
```

---

## Running tests and lint

```bash
# Lint
uv run ruff check .

# Tests (no real network or Groq calls — all mocked)
uv run pytest
```

---

## How the cron workflow works

`.github/workflows/daily-digest.yml` runs every day at **08:00 UTC** and
on every manual "Run workflow" click.

1. **Checkout** — checks out the latest commit.
2. **Set up uv** — installs uv with caching enabled.
3. **Install dependencies** — `uv sync`.
4. **Run pipeline** — `uv run python -m app.cli run`.  
   `GROQ_API_KEY` and `GROQ_MODEL` are injected only on this step via
   `env:` and are never echoed or logged.
5. **Copy to docs/data/** — copies `data/digest.json` and `data/run.json`
   so GitHub Pages can serve them.
6. **Status check** — reads `data/run.json`. If `status == "failed"` the
   job exits non-zero and nothing is committed. `partial` is committed.
7. **Commit** — if any of the 5 expected files changed, commits with the
   `github-actions[bot]` identity and message
   `chore: update digest [skip ci]`. Never uses `git add -A`.

The `concurrency` group (`cancel-in-progress: false`) ensures two runs
never overlap and burn double the LLM credits.

### CI workflow

`.github/workflows/ci.yml` runs `ruff check .` and `pytest` on every pull
request and push to `main`. No secrets are needed or passed.

---

## Adding the GitHub secret and variable

1. Go to your repo on GitHub.
2. **Settings → Secrets and variables → Actions**.
3. Under **Secrets**, click **New repository secret**:
   - Name: `GROQ_API_KEY`
   - Value: your Groq API key (starts with `gsk_`)
4. Under **Variables**, click **New repository variable**:
   - Name: `GROQ_MODEL`
   - Value: the Groq model ID you want to use
     (e.g. `llama3-8b-8192` — always check the current list at
     <https://console.groq.com/docs/models>)

---

## Enabling GitHub Pages

1. Go to **Settings → Pages**.
2. Under **Source**, select **Deploy from a branch**.
3. Branch: `main` (or whichever branch you push to), folder: `/docs`.
4. Click **Save**. The site will be live within a minute or two at
   `https://<your-username>.github.io/daily-digest/`.

---

## Project structure

```
daily-digest/
├── README.md
├── REQUIREMENTS.md          # what the project must do
├── ARCHITECTURE.md          # how it is built
├── SECURITY_RULES.md        # mandatory security constraints
├── DESIGN.md                # UI spec and data contract
├── PHASES.md                # four-phase build plan
├── pyproject.toml           # Python project metadata and pinned deps
├── uv.lock                  # locked dependency versions
├── .env.example             # placeholder env file (safe to commit)
├── .gitignore               # .env, caches, virtualenv
├── feeds.yaml               # RSS feeds and topic keyword lists
│
├── app/
│   ├── cli.py               # entry points: fetch (debug) and run (full pipeline)
│   ├── config.py            # pydantic-settings config; fails fast on missing vars
│   ├── graph/
│   │   ├── state.py         # LangGraph state (PipelineState TypedDict)
│   │   ├── nodes.py         # one function per graph node
│   │   ├── edges.py         # conditional routing logic
│   │   └── builder.py       # assembles and compiles the graph
│   ├── services/
│   │   ├── feed_service.py  # async fetch, SSRF guard, HTML strip, image_url
│   │   ├── dedupe_service.py# URL normalisation, sha256 ID, title dedupe
│   │   ├── topic_service.py # keyword tagging for the 9 default topics
│   │   └── llm_service.py   # ChatGroq + Pydantic structured output, 3 tones
│   ├── storage/
│   │   └── json_store.py    # atomic writes, cache CRUD, pruning, digest build
│   └── models/
│       └── schemas.py       # ArticleSummary (3 bullets, ≤25 words each)
│
├── data/
│   ├── cache.json           # summary cache keyed by (article_id, tone)
│   ├── digest.json          # last 7 days of articles with summaries
│   └── run.json             # run status and metrics
│
├── docs/                    # GitHub Pages static site
│   ├── index.html
│   ├── styles.css
│   ├── config.js            # WORKFLOW_URL, SCHEDULE_UTC_HOUR, data paths
│   ├── app.js               # state, render, event handlers
│   ├── icons.js             # inline SVG builders
│   └── data/                # copies of digest.json and run.json (written by Action)
│
└── tests/
    ├── conftest.py
    ├── fixtures/            # sample feeds and digest JSON
    ├── test_dedupe.py
    ├── test_topics.py
    ├── test_feed_service.py
    ├── test_llm_service.py
    ├── test_json_store.py
    ├── test_nodes.py
    └── test_graph_e2e.py
│
└── .github/workflows/
    ├── daily-digest.yml     # cron + manual dispatch, commit data files
    └── ci.yml               # lint and test on PRs and pushes to main
```

---

## Design trade-off

**Static JSON instead of an API and database.**  
The pipeline writes three small JSON files once a day. The browser reads
them directly with `fetch()`. There is no server to host, no database to
secure, no scaling concern, and no hosting cost. The trade-off is that
the data is public (fine — it is all public news), updates are at most
once a day, and the site shows stale data if a run fails (mitigated by
the stale-data warning in the UI and the 30-day summary cache that keeps
old articles available).

---

## Known limitations

- **All data is public.** The repo and Pages site are public. Never store
  personal data or secrets in `data/*.json`.
- **GitHub cron can run late.** Scheduled workflows on GitHub can be
  delayed by up to several hours during peak load. Use "Run workflow" for
  an immediate refresh.
- **Groq free-tier limits.** The free tier has rate limits and a monthly
  token cap. `MAX_ARTICLES_PER_RUN` (default 15) and the summary cache
  keep usage well within limits for personal use, but check your usage
  dashboard if you increase it.
- **Workflows pause after 60 days of repository inactivity.** The daily
  bot commits count as activity, so this should not occur in normal use.

---

## Backlog (future ideas, not in v1)

- **Email digest** — send the daily summary via SendGrid or SES.
- **Relevance ranking** — add a scoring node that ranks articles by
  personal interest using embeddings or a small model.
- **Optional FastAPI phase** — expose a `/refresh` endpoint and a
  LangGraph checkpointer if a live server is ever needed.
