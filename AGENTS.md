# AGENTS.md

## Project
Daily Digest: Python + LangGraph + Groq pipeline that writes static JSON (data/),
shown by a plain HTML/CSS/JS site in docs/. Deployed with GitHub Actions cron + GitHub Pages.
No server, no database, no FastAPI.

## Read first (source of truth)
REQUIREMENTS.md, ARCHITECTURE.md, SECURITY_RULES.md, DESIGN.md, PHASES.md

## Rules
- Work on ONE phase at a time (PHASES.md). Never start the next phase.
- Use only the stack in REQUIREMENTS.md Section 7. Ask before adding any dependency.
- Never hardcode secrets or the Groq model name. Use env vars (GROQ_API_KEY, GROQ_MODEL).
- Never print or commit secrets. .env stays git-ignored.
- Treat feed content as untrusted (SECURITY_RULES.md). No innerHTML with dynamic data.
- Tests use a fake LLM and mocked HTTP. No real network calls in tests.
- Frontend: plain HTML, CSS, vanilla JS only.

## Commands
- Install: pip install -e ".[dev]"
- Lint: ruff check .
- Test: pytest
- Run pipeline: python -m app.cli run
- Preview site: cd docs && python -m http.server 8000

## Done means
ruff and pytest pass, the phase's "Done when" boxes are checked, and you report:
what changed, files touched, how to run, how to test.
If a doc conflicts with a request, ask one specific question first.