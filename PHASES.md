# Daily Digest: Build Phases (4 Phases)

> Short version. Read with `REQUIREMENTS.md`, `ARCHITECTURE.md`, `SECURITY_RULES.md`, and `DESIGN.md`.
> **Deployment:** no server. A GitHub Actions cron job runs the pipeline daily and saves `data/digest.json`. GitHub Pages shows the site.

---

## Instructions for AI Assistants (READ FIRST)

1. Read all five docs before coding.
2. Do **only the phase the user names**. Do not start the next one.
3. Follow `SECURITY_RULES.md`. Never hardcode secrets or the model name; use env vars.
4. Use a fake LLM and mocked HTTP in tests. No real network calls in tests.
5. Keep it simple. No extra libraries without asking.
6. Frontend is **plain HTML, CSS, and JS** only (see `DESIGN.md`).
7. When done, report: **what changed, files touched, how to run, how to test, "Done when" status**.

### Key decisions (already made)
- Summaries have **3 bullets** (each at most 25 words) in **3 tones**: `balanced`, `technical`, `beginner_friendly`.
- All three tones are generated for each selected article. Cap at `MAX_ARTICLES_PER_RUN` (default 15).
- No FastAPI, no database server. The pipeline writes `data/cache.json`, `data/digest.json`, and `data/run.json`.
- Filtering, search, sorting, tone switching, and bookmarks happen in the browser.
- "Run Digest Now" opens the GitHub Actions workflow page.

---

## Phase 1: Setup, Fetch, Dedupe

**Goal:** fetch all feeds safely and get a clean list of unique, topic-tagged articles with thumbnails.

**Tasks**
- Create the repo, folders (see `ARCHITECTURE.md` Section 9), `pyproject.toml` with pinned dependencies, `.gitignore`, `.env.example`, and `feeds.yaml` (about 12 feeds with `source_type` and the topic keywords).
- `config.py`: read env settings with `pydantic-settings`; fail fast if `GROQ_API_KEY` or `GROQ_MODEL` is missing (only when the LLM is needed).
- `feed_service`: async fetch with `httpx`, timeout, retries, size and redirect limits, SSRF guard, HTML stripping, `image_url` extraction (https only).
- `dedupe_service`: URL normalization, article ID (sha256), title dedupe.
- `topic_service`: keyword tagging for the 9 default topics.
- CLI: `python -m app.cli fetch` prints unique articles with source, topics, and feed health.
- Set up `ruff` and `pytest`.

**Tests:** URL normalization, duplicates across feeds, failing feed does not crash, SSRF blocked, HTML stripped, `image_url` kept only if https, topic tagging.

**Done when**
- [ ] `python -m app.cli fetch` prints unique, topic-tagged articles from live feeds
- [ ] `ruff` and `pytest` pass
- [ ] `.env` and secrets are git-ignored

**Prompt for the AI**
> Read all five docs. Implement **Phase 1 only** from PHASES.md. Follow SECURITY_RULES Section 2. No LLM code yet.

---

## Phase 2: Summarize with LangGraph

**Goal:** a LangGraph pipeline that writes `data/cache.json`, `data/digest.json`, and `data/run.json`.

**Tasks**
- `llm_service`: `ChatGroq` (model from `GROQ_MODEL`) with Pydantic structured output: exactly 3 bullets, at most 25 words each.
- Three tone prompts. Article text is untrusted: instructions in the system message, article inside `<article>` tags (SECURITY_RULES Section 3).
- Graph (see `ARCHITECTURE.md` Section 3): `load_config → fetch_feeds → parse_entries → dedupe → classify_topics → select_articles → summarize → validate → save_output`, with a retry loop for failed summaries and an early exit when nothing needs summarizing.
- `json_store`: atomic writes, cache read and write, 30-day pruning, build `digest.json` (last 7 days, max 60 articles, `topic_counts`) and `run.json`.
- Cache by `(article_id, tone)`; skip cached pairs; limit concurrency; back off on 429.
- CLI: `python -m app.cli run`.
- Include `tests/fixtures/` with a sample feed and sample `digest.json` (the UI will use it in Phase 3).

**Tests:** schema validation (3 bullets), retry once then `failed`, short text gives `insufficient_content` with no LLM call, **second run makes zero LLM calls**, prompt-injection fixture, old files untouched when a run fails before saving, `digest.json` matches `DESIGN.md` Section 8.

**Done when**
- [x] `python -m app.cli run` creates the three JSON files
- [x] Running twice makes zero LLM calls the second time
- [x] Every selected article has 3 bullets in all 3 tones (or a clear status)
- [x] Tests pass using a fake LLM only

**Prompt for the AI**
> Read all five docs. Implement **Phase 2 only**. Use a fake LLM in tests. Output goes to the JSON files in `data/`; no server and no database.

---

## Phase 3: Static Web UI

**Goal:** the dashboard from `DESIGN.md`, built with plain HTML, CSS, and JavaScript.

**Tasks**
- Build `docs/index.html`, `styles.css`, `config.js`, `app.js`, `icons.js` exactly as described in `DESIGN.md` (tokens, 3-column layout, components, states).
- Develop against `docs/data/sample-digest.json` and `sample-run.json` (copy from the Phase 2 fixtures), then switch to `docs/data/digest.json` and `run.json`.
- Implement: interest chips and custom topics, tone radios, search, sort, article cards with thumbnail placeholders, bookmarks in `localStorage`, Sources by Topic, Summarizer Stats, Bookmarked Articles, Last Updated and next run.
- Safe rendering: `textContent` only, validated links and images, CSP meta tag (`SECURITY_RULES` Section 5).
- Responsive layout (single column below 1100px).

**Done when**
- [x] Opening `docs/` through `python -m http.server` shows the digest from JSON
- [x] Topics, search, sort, tone, and bookmarks work without a reload
- [x] Loading, error, empty, no-match, partial, failed, and stale states are handled
- [x] No `innerHTML` with dynamic data
- [x] Usable on a phone and by keyboard

**Prompt for the AI**
> Read all five docs. Implement **Phase 3 only**. Plain HTML, CSS, and vanilla JS. Follow DESIGN.md exactly. Render all data with textContent.

---

## Phase 4: GitHub Actions Cron and Deploy

**Goal:** the pipeline runs automatically every day and the site is live on GitHub Pages.

**Tasks**
- Add the secret `GROQ_API_KEY` and the variable `GROQ_MODEL` under repo Settings → Secrets and variables → Actions.
- Create `.github/workflows/daily-digest.yml` (see `ARCHITECTURE.md` Section 8):
  - Triggers: `schedule` (for example `0 8 * * *` UTC, matching `SCHEDULE_UTC_HOUR` in `docs/config.js`) and `workflow_dispatch`.
  - Steps: checkout, setup Python with pip cache, install, run `python -m app.cli run`, copy JSON to `docs/data/`, commit and push only if files changed.
  - `permissions: contents: write` and a `concurrency` group. Pass secrets only through `env:` on the run step; never echo them.
- Create `.github/workflows/ci.yml`: `ruff` and `pytest` on pull requests and pushes.
- Enable GitHub Pages: Settings → Pages → deploy from branch, folder `/docs`.
- Set `WORKFLOW_URL` in `docs/config.js` to your repo's workflow page.
- README: overview, screenshot, live link, setup steps, env vars, one design trade-off (`ARCHITECTURE.md` Section 12), limitations.

**Done when**
- [ ] Manual "Run workflow" succeeds and commits fresh JSON
- [ ] The Pages URL shows the updated digest
- [ ] The scheduled run has executed at least once
- [ ] The API key appears nowhere in the repo, logs, or site
- [ ] README is complete

**Prompt for the AI**
> Read all five docs. Implement **Phase 4 only**. Write the two workflows and the README. Secrets only via GitHub Actions secrets. Give me step-by-step instructions for adding the secret and enabling Pages.

---

## Workflow for Each Phase

1. New AI session; paste that phase's prompt.
2. Ask for a 5-bullet plan first, then the code.
3. Run `ruff` and `pytest`, and try the result yourself.
4. Check the diff for secrets, then commit and tag (`git tag phase-1-done`).
5. Move on only when every "Done when" box is checked.

## Progress

| Phase | Status |
|-------|--------|
| 1 Setup, fetch, dedupe | ☐ |
| 2 Summarize with LangGraph | ☐ |
| 3 Static web UI | ☐ |
| 4 GitHub cron and deploy | ☐ |
