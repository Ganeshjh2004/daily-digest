/**
 * owner.js — Owner-mode "Run Digest Now" workflow dispatch.
 *
 * Rules:
 *  - Token lives ONLY in sessionStorage under key "digest.ghToken".
 *  - Token is never logged, never put in a URL, never in localStorage.
 *  - No innerHTML with dynamic data.  All DOM is built with textContent / createElement.
 *  - All fetch() calls to api.github.com go here; app.js stays unaware of the token.
 */
import { GITHUB_OWNER, GITHUB_REPO, WORKFLOW_FILE, REF, WORKFLOW_URL, DATA_PATHS } from "./config.js";

// ── Constants ──────────────────────────────────────────────────────────────────
const TOKEN_KEY = "digest.ghToken";
const POLL_INTERVAL_MS = 15_000;
const POLL_TIMEOUT_MS = 15 * 60_000;       // 15 minutes
const PAGES_SETTLE_MS = 60_000;             // wait after success before re-fetch
const API_BASE = "https://api.github.com";
const RUNS_URL = `${API_BASE}/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/runs`;
const DISPATCH_URL = `${API_BASE}/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`;

// ── Token storage ─────────────────────────────────────────────────────────────
function readToken() {
  try { return sessionStorage.getItem(TOKEN_KEY) || null; } catch (_) { return null; }
}

function writeToken(token) {
  try { sessionStorage.setItem(TOKEN_KEY, token); } catch (_) { /* storage unavailable */ }
}

function clearToken() {
  try { sessionStorage.removeItem(TOKEN_KEY); } catch (_) { /* storage unavailable */ }
}

// ── GitHub API helpers ─────────────────────────────────────────────────────────
function ghHeaders(token) {
  return {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

/** GET the most recent workflow run (authenticated if token exists to avoid unauthenticated rate limits). */
async function fetchLatestRun() {
  const token = readToken();
  const headers = token ? ghHeaders(token) : {};
  const response = await fetch(`${RUNS_URL}?per_page=1`, { cache: "no-store", headers });
  if (!response.ok) throw Object.assign(new Error("Failed to fetch runs"), { status: response.status });
  const data = await response.json();
  return (data.workflow_runs || [])[0] || null;
}

/** POST workflow dispatch. Returns the HTTP status code. */
async function dispatchWorkflow(token) {
  const response = await fetch(DISPATCH_URL, {
    method: "POST",
    headers: ghHeaders(token),
    body: JSON.stringify({ ref: REF }),
  });
  return response.status;
}

// ── Polling ───────────────────────────────────────────────────────────────────
/**
 * Poll the runs endpoint every POLL_INTERVAL_MS.
 * Calls onProgress(stateKey, run) with one of:
 *   "starting" | "queued" | "in_progress" | "publishing" | "done" | "failed"
 * Stops after POLL_TIMEOUT_MS or on a terminal state.
 */
async function pollRun(onProgress, startedAt) {
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  // Give GitHub a moment to register the new run.
  await sleep(4_000);
  while (Date.now() < deadline) {
    let run = null;
    try { run = await fetchLatestRun(); } catch (_) { /* transient network error — keep polling */ }
    if (run) {
      const runStart = new Date(run.created_at).getTime();
      if (runStart >= startedAt - 5_000) {          // only watch runs we triggered
        const { status, conclusion } = run;
        if (status === "queued") { onProgress("queued", run); }
        else if (status === "in_progress") { onProgress("in_progress", run); }
        else if (status === "completed") {
          if (conclusion === "success") {
            onProgress("publishing", run);
            await sleep(PAGES_SETTLE_MS);
            onProgress("done", run);
          } else {
            onProgress("failed", run);
          }
          return;
        }
      } else {
        onProgress("starting", null);
      }
    } else {
      onProgress("starting", null);
    }
    await sleep(POLL_INTERVAL_MS);
  }
  // Timeout — leave the caller to handle.
  onProgress("failed", null);
}

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

// ── Public API ─────────────────────────────────────────────────────────────────
/**
 * Build and return the "Owner: add token" UI element.
 * The caller inserts this wherever it wants.
 * Accepts an optional onTokenChange callback called when token is saved or cleared.
 */
export function buildOwnerControls(onTokenChange) {
  const wrap = createElement("div", "owner-controls");

  function notifyChange() {
    if (typeof onTokenChange === "function") onTokenChange();
  }

  function refreshWrap() {
    // Wipe and rebuild without innerHTML.
    wrap.replaceChildren();
    const token = readToken();
    if (token) {
      const row = createElement("div", "owner-row");
      const note = createText("span", "Token active. ", "owner-note");
      const remove = createText("button", "Remove token", "owner-link");
      remove.type = "button";
      remove.addEventListener("click", () => {
        clearToken();
        refreshWrap();
        notifyChange();
      });
      row.append(note, remove);
      wrap.append(row);
    } else {
      const addLink = createText("a", "Owner: add token", "owner-link");
      addLink.href = "#";
      addLink.setAttribute("role", "button");
      addLink.addEventListener("click", (event) => {
        event.preventDefault();
        showTokenInput();
      });
      wrap.append(addLink);
    }
  }

  function showTokenInput() {
    wrap.replaceChildren();
    const form = createElement("form", "token-form");
    const label = createText("label", "GitHub token", "owner-note");
    label.setAttribute("for", "owner-token-input");
    const input = createElement("input", "token-input");
    input.type = "password";
    input.id = "owner-token-input";
    input.placeholder = "github_pat_…";
    input.setAttribute("autocomplete", "off");
    input.setAttribute("spellcheck", "false");
    const save = createText("button", "Save", "small-button");
    save.type = "submit";
    const cancel = createText("button", "Cancel", "owner-link cancel-btn");
    cancel.type = "button";
    cancel.addEventListener("click", refreshWrap);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const val = input.value.trim();
      if (!val) return;
      writeToken(val);
      refreshWrap();
      notifyChange();
    });
    form.append(label, document.createTextNode(" "), input, document.createTextNode(" "), save, document.createTextNode(" "), cancel);
    wrap.append(form);
    // Focus without scroll disruption.
    requestAnimationFrame(() => input.focus());
  }

  refreshWrap();
  return wrap;
}

/**
 * Check whether an owner token is currently stored in sessionStorage.
 */
export function hasToken() {
  return readToken() !== null;
}

/**
 * Attempt to dispatch the workflow using the stored token.
 * Returns: { dispatched, error, run, alreadyRunning }
 *
 * If a run is already queued or in_progress we skip dispatch.
 */
export async function tryDispatch() {
  const token = readToken();
  if (!token) return { dispatched: false, error: "No token stored.", run: null };

  // Check for an already-running run first (no auth needed for public repo).
  let latestRun = null;
  try { latestRun = await fetchLatestRun(); } catch (_) { /* ignore; proceed to dispatch */ }

  if (latestRun && (latestRun.status === "queued" || latestRun.status === "in_progress")) {
    return { dispatched: false, error: null, run: latestRun, alreadyRunning: true };
  }

  let status;
  try {
    status = await dispatchWorkflow(token);
  } catch (_) {
    return { dispatched: false, error: "Network error — check your connection and try again.", run: null };
  }

  if (status === 204) {
    return { dispatched: true, error: null, run: null };
  }
  if (status === 401 || status === 403) {
    clearToken();
    return { dispatched: false, error: `Token rejected (HTTP ${status}). Token cleared — please add a new one.`, run: null };
  }
  if (status === 404) {
    return { dispatched: false, error: "Workflow not found (HTTP 404). Check WORKFLOW_FILE in config.js.", run: null };
  }
  if (status === 422) {
    return { dispatched: false, error: "Unprocessable request (HTTP 422). The ref or workflow file name may be wrong.", run: null };
  }
  if (status === 429) {
    return { dispatched: false, error: "GitHub rate limit reached (HTTP 429). Wait a minute and try again.", run: null };
  }
  return { dispatched: false, error: `Unexpected response from GitHub (HTTP ${status}).`, run: null };
}

/**
 * Begin polling for a run.
 * startedAt: timestamp in ms from Date.now() just before dispatch.
 * onProgress(key, run, elapsedMs) — key is one of:
 *   "starting" | "queued" | "in_progress" | "publishing" | "done" | "failed"
 * onReload(digest, run) — called with fresh JSON data after a successful run.
 */
export async function startPolling(startedAt, onProgress, onReload) {
  await pollRun(async (key, run) => {
    const elapsed = Date.now() - startedAt;
    onProgress(key, run, elapsed);
    if (key === "done") {
      const timestamp = Date.now();
      try {
        const [digestResp, runResp] = await Promise.all([
          fetch(`${DATA_PATHS.digest}?t=${timestamp}`, { cache: "no-store" }),
          fetch(`${DATA_PATHS.run}?t=${timestamp}`, { cache: "no-store" }),
        ]);
        if (digestResp.ok && runResp.ok) {
          onReload(await digestResp.json(), await runResp.json());
        }
      } catch (_) { /* non-fatal: user can still click refresh manually */ }
    }
  }, startedAt);
}

/**
 * Return the run HTML URL safely (must start with https://github.com).
 */
export function safeRunUrl(run) {
  if (!run || typeof run.html_url !== "string") return null;
  try {
    const url = new URL(run.html_url);
    return url.protocol === "https:" && url.hostname === "github.com" ? url.href : null;
  } catch (_) { return null; }
}

// ── Small DOM helpers (no innerHTML) ──────────────────────────────────────────
function createElement(tag, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function createText(tag, text, className) {
  const node = createElement(tag, className);
  node.textContent = text;
  return node;
}
