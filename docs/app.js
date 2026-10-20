import { DATA_PATHS, SCHEDULE_UTC_HOUR, WORKFLOW_URL } from "./config.js";
import { buildOwnerControls, hasToken, tryDispatch, startPolling, safeRunUrl } from "./owner.js";
import { icons } from "./icons.js";

const DEFAULT_TOPICS = ["AI Agents", "LLMs", "Python", "Backend", "System Design", "Machine Learning", "DevOps", "Cloud", "Productivity"];
const TONES = ["balanced", "technical", "beginner_friendly"];

async function loadData(force = false) {
  state.loading = true;
  state.loadError = false;
  render();
  try {
    const options = force ? { cache: "no-store" } : {};
    const [digestResponse, runResponse] = await Promise.all([
      fetch(DATA_PATHS.digest, options),
      fetch(DATA_PATHS.run, options),
    ]);
    if (!digestResponse.ok || !runResponse.ok) throw new Error("Data files could not be loaded");
    state.digest = await digestResponse.json();
    state.run = await runResponse.json();
  } catch (_) {
    state.loadError = true;
  } finally {
    state.loading = false;
    render();
  }
}

const state = {
  topics: readTopics(),
  customTopics: readCustomTopics(),
  tone: readTone(),
  sort: "relevant",
  search: "",
  bookmarkedOnly: false,
  bookmarks: readBookmarks(),
  digest: null,
  run: null,
  loading: true,
  loadError: false,
  addingTopic: false,
  // owner-mode run progress
  runStatus: null,          // null | "starting" | "queued" | "in_progress" | "publishing" | "done" | "failed"
  runElapsedMs: 0,
  runError: null,           // string | null
  runUrl: null,             // string | null — link to the GitHub Actions run
};

function timeAgo(value) {
  const then = new Date(value || "");
  if (Number.isNaN(then.getTime())) return "Unknown time";
  const seconds = Math.max(0, Math.floor((Date.now() - then.getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)} days ago`;
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch (_) {
    return null;
  }
}

function wordCount(value) {
  return String(value || "").trim().split(/\s+/).filter(Boolean).length;
}

function filterAndSort() {
  const articles = Array.isArray(state.digest?.articles) ? state.digest.articles : [];
  const topicSet = new Set(state.topics);
  const needle = state.search.trim().toLowerCase();
  let candidates = state.bookmarkedOnly ? bookmarkArticles(articles) : articles.slice();
  candidates = candidates.filter((article) => {
    const articleTopics = Array.isArray(article.topics) ? article.topics : [];
    const bullets = Object.values(article.summaries || {}).flatMap((summary) => summary?.bullets || []);
    const searchable = [article.title, article.source, ...articleTopics, ...bullets].join(" ").toLowerCase();
    const topicMatch = state.bookmarkedOnly || topicSet.size === 0 || [...topicSet].some((topic) => {
      if (state.customTopics.includes(topic)) return searchable.includes(topic.toLowerCase());
      return articleTopics.includes(topic);
    });
    return topicMatch && (!needle || searchable.includes(needle));
  });
  return candidates.sort((first, second) => {
    if (state.sort === "newest") return dateValue(second.published_at) - dateValue(first.published_at);
    const score = (article) => (article.topics || []).filter((topic) => topicSet.has(topic)).length;
    return score(second) - score(first) || dateValue(second.published_at) - dateValue(first.published_at);
  });
}

function renderControls() {
  const column = element("aside", "column left-column");
  const topicsCard = card("Your Interests");
  topicsCard.append(paragraph("Select topics to filter articles", "helper"));
  const chips = element("div", "chips");
  const availableTopics = unique([...(state.digest?.topics || DEFAULT_TOPICS), ...DEFAULT_TOPICS, ...state.customTopics]);
  availableTopics.forEach((topic) => chips.append(topicChip(topic)));
  topicsCard.append(chips);
  if (state.addingTopic) topicsCard.append(customTopicForm());
  else {
    const add = button("+ Add custom topic", "add-custom");
    add.addEventListener("click", () => { state.addingTopic = true; render(); });
    topicsCard.append(add);
  }
  column.append(topicsCard, toneCard(), runCard(), updatedCard());
  return column;
}

function renderArticles() {
  const column = element("section", "column center-column");
  const articles = filterAndSort();
  const heading = element("div", "article-heading");
  heading.append(elementWithText("h2", "Latest Articles"), elementWithText("span", `${articles.length} articles`, "article-count"));
  if (state.bookmarkedOnly) {
    const filter = element("span", "bookmark-filter");
    filter.append(document.createTextNode("Bookmarked only"));
    const close = button("×", "clear-filter", "Show all articles");
    close.addEventListener("click", () => { state.bookmarkedOnly = false; render(); });
    filter.append(close);
    heading.append(filter);
  }
  const sort = element("select", "sort-select");
  sort.setAttribute("aria-label", "Sort articles");
  [["relevant", "Most Relevant"], ["newest", "Newest"]].forEach(([value, label]) => {
    const option = elementWithText("option", label);
    option.value = value;
    option.selected = state.sort === value;
    sort.append(option);
  });
  sort.addEventListener("change", (event) => { state.sort = event.target.value; render(); });
  heading.append(sort);
  column.append(heading);
  if (state.loading) { column.append(skeletons()); return column; }
  if (state.loadError) { column.append(message("Couldn't load the digest. Try the refresh icon.", "error-state")); return column; }
  if (!Array.isArray(state.digest?.articles) || state.digest.articles.length === 0) {
    column.append(message("No articles yet. Run the digest to get started.", "empty-state")); return column;
  }
  if (state.run?.status === "partial") column.append(banner(`Some feeds failed in the last run (${state.run.metrics?.feeds_ok || 0}/${state.run.metrics?.feeds_total || 0} OK).`));
  if (state.run?.status === "failed") column.append(banner("The last run failed. Showing the previous digest.", "failed"));
  if (articles.length === 0) {
    const text = state.search ? `No articles match “${state.search}”.` : "No articles match your filters.";
    const empty = message(text, "empty-state");
    const clear = button("Clear filters", "clear-filter");
    clear.addEventListener("click", clearFilters);
    empty.append(clear);
    column.append(empty);
    return column;
  }
  const list = element("div", "article-list");
  articles.forEach((article) => list.append(articleCard(article)));
  column.append(list);
  return column;
}

function renderPanels() {
  const column = element("aside", "column right-column");
  if (state.loading) { column.append(skeletons()); return column; }
  column.append(topicPanel(), statsPanel(), bookmarksPanel());
  return column;
}

function render() {
  const app = document.querySelector("#app");
  const layout = element("div", "layout");
  layout.append(renderControls(), renderArticles(), renderPanels());
  app.replaceChildren(layout);
}

function init() {
  document.querySelector("#brand-icon").append(icons.newspaper());
  document.querySelector("#search-icon").append(icons.search());
  let searchTimer;
  document.querySelector("#search-input").addEventListener("input", (event) => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => { state.search = event.target.value; render(); }, 150);
  });
  loadData();
}

function card(title) { const node = element("section", "card"); node.append(elementWithText("h2", title, "section-heading")); return node; }
function element(tag, className = "") { const node = document.createElement(tag); if (className) node.className = className; return node; }
function elementWithText(tag, text, className = "") { const node = element(tag, className); node.textContent = text; return node; }
function paragraph(text, className) { return elementWithText("p", text, className); }
function unique(values) { return [...new Set(values.filter((value) => typeof value === "string" && value.trim()))]; }
function dateValue(value) { const date = new Date(value || ""); return Number.isNaN(date.getTime()) ? 0 : date.getTime(); }
function button(text, className, label = "") { const node = elementWithText("button", text, className); node.type = "button"; if (label) node.setAttribute("aria-label", label); return node; }
function isStale() { return state.run?.finished_at && Date.now() - dateValue(state.run.finished_at) > 36 * 60 * 60 * 1000; }
function statusClass() { return state.run?.status === "failed" ? "danger" : state.run?.status === "partial" || isStale() ? "warning" : ""; }

function topicChip(topic) {
  const label = element("label", "topic-chip");
  const input = element("input"); input.type = "checkbox"; input.checked = state.topics.includes(topic);
  input.addEventListener("change", () => { state.topics = input.checked ? unique([...state.topics, topic]) : state.topics.filter((item) => item !== topic); save("digest.topics", state.topics); render(); });
  label.append(input, document.createTextNode(topic));
  if (state.customTopics.includes(topic)) { const remove = button("×", "remove-custom", `Remove ${topic}`); remove.addEventListener("click", (event) => { event.preventDefault(); state.customTopics = state.customTopics.filter((item) => item !== topic); state.topics = state.topics.filter((item) => item !== topic); save("digest.customTopics", state.customTopics); save("digest.topics", state.topics); render(); }); label.append(remove); }
  return label;
}

function customTopicForm() {
  const form = element("form", "custom-topic-form"); const input = element("input"); input.maxLength = 30; input.placeholder = "Topic keyword"; input.setAttribute("aria-label", "Custom topic keyword");
  const add = button("Add", "small-button"); form.append(input, add); form.addEventListener("submit", (event) => { event.preventDefault(); const topic = input.value.trim(); if (topic) { state.customTopics = unique([...state.customTopics, topic]); state.topics = unique([...state.topics, topic]); save("digest.customTopics", state.customTopics); save("digest.topics", state.topics); } state.addingTopic = false; render(); }); return form;
}

function toneCard() {
  const node = card("Summary Tone"); const heading = node.firstChild; heading.append(document.createTextNode(" "), icons.info()); const group = element("div", "tone-group"); group.setAttribute("role", "radiogroup"); group.setAttribute("aria-label", "Summary tone");
  [["balanced", "Balanced", "Neutral and informative"], ["technical", "Technical", "More technical details"], ["beginner_friendly", "Beginner Friendly", "Simple and easy to understand"]].forEach(([value, label, helper]) => { const option = element("label", "tone-option"); const input = element("input"); input.type = "radio"; input.name = "tone"; input.value = value; input.checked = state.tone === value; input.addEventListener("change", () => { state.tone = value; save("digest.tone", value); render(); }); option.append(input, elementWithText("span", label), elementWithText("small", helper)); group.append(option); }); node.append(group); return node;
}

function runCard() {
  const node = card("Run Digest Now");

  // ── Main action button ───────────────────────────────────────────────────
  const tokenPresent = hasToken();
  const btn = element(tokenPresent ? "button" : "a", "primary-button");
  btn.id = "run-digest-btn";
  if (tokenPresent) {
    btn.type = "button";
    btn.disabled = state.runStatus !== null && state.runStatus !== "done" && state.runStatus !== "failed";
  } else {
    btn.href = WORKFLOW_URL;
    btn.target = "_blank";
    btn.rel = "noopener noreferrer";
  }

  // Button label reflects current run state.
  const btnLabel = runButtonLabel();
  btn.append(icons.play(), document.createTextNode(" " + btnLabel));

  if (tokenPresent) {
    btn.addEventListener("click", handleRunClick);
  }

  node.append(btn);

  // ── Progress / error message ─────────────────────────────────────────────
  if (state.runError) {
    const errWrap = element("div", "run-error");
    errWrap.append(document.createTextNode(state.runError));
    if (state.runUrl) {
      const link = element("a", "run-error-link");
      link.href = state.runUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "View run";
      errWrap.append(document.createTextNode(" "), link);
    }
    node.append(errWrap);
  } else if (state.runStatus && state.runStatus !== "done") {
    node.append(paragraph(runStatusNote(), "run-note"));
  } else if (!tokenPresent) {
    node.append(paragraph("Opens GitHub Actions. Takes about a minute.", "run-note"));
  } else if (state.runStatus === "done") {
    node.append(paragraph("Digest updated! Page re-rendered with fresh data.", "run-note run-success"));
  } else {
    node.append(paragraph("Token active. Click to start the pipeline.", "run-note"));
  }

  // ── Owner controls (add / remove token) ─────────────────────────────────
  node.append(buildOwnerControls());

  return node;
}

function runButtonLabel() {
  switch (state.runStatus) {
    case "starting":    return "Starting…";
    case "queued":      return "Queued…";
    case "in_progress": {
      const secs = Math.floor((state.runElapsedMs || 0) / 1000);
      return `Running (${secs}s)…`;
    }
    case "publishing":  return "Publishing…";
    case "done":        return "Done ✓";
    case "failed":      return "Failed — Retry?";
    default:            return "Run Digest Now";
  }
}

function runStatusNote() {
  switch (state.runStatus) {
    case "starting":    return "Waiting for GitHub to register the run…";
    case "queued":      return "Run is queued. Checking every 15 s…";
    case "in_progress": return `Pipeline is running. Checking every 15 s…`;
    case "publishing":  return "Run succeeded! Waiting ~60 s for GitHub Pages to redeploy…";
    default:            return "";
  }
}

async function handleRunClick() {
  // Guard against double-click during a live run.
  if (state.runStatus !== null && state.runStatus !== "done" && state.runStatus !== "failed") return;

  state.runStatus = "starting";
  state.runError = null;
  state.runUrl = null;
  state.runElapsedMs = 0;
  render();

  const dispatchedAt = Date.now();
  let result;
  try {
    result = await tryDispatch();
  } catch (_) {
    state.runStatus = "failed";
    state.runError = "Unexpected error — check the console and try again.";
    render();
    return;
  }

  if (result.alreadyRunning) {
    // Follow the existing run without dispatching a new one.
    state.runStatus = result.run?.status === "queued" ? "queued" : "in_progress";
    state.runUrl = safeRunUrl(result.run);
    render();
    startPolling(dispatchedAt, handleProgress, handleReload);
    return;
  }

  if (result.error) {
    state.runStatus = "failed";
    state.runError = result.error;
    render();
    return;
  }

  // HTTP 204 — dispatch accepted.
  state.runStatus = "starting";
  render();
  startPolling(dispatchedAt, handleProgress, handleReload);
}

function handleProgress(key, run, elapsedMs) {
  state.runStatus = key;
  state.runElapsedMs = elapsedMs || 0;
  if (run) state.runUrl = safeRunUrl(run);
  if (key === "failed") {
    state.runError = run
      ? "The workflow run failed."
      : "Polling timed out after 15 minutes.";
  }
  render();
}

function handleReload(freshDigest, freshRun) {
  state.digest = freshDigest;
  state.run = freshRun;
  render();
}
function updatedCard() { const node = card("Last Updated"); const row = element("div", "updated-row"); const label = isStale() ? `Digest is out of date · ${lastUpdated()}` : lastUpdated(); row.append(element("span", `status-dot ${statusClass()}`), elementWithText("strong", label)); const refresh = button("", "icon-button", "Refresh digest data"); refresh.append(icons.refresh()); refresh.addEventListener("click", () => loadData(true)); row.append(refresh); const next = element("div", "next-run-row"); next.append(icons.calendar(), document.createTextNode(`Next scheduled run: ${nextRun()}`)); node.append(row, next); return node; }

function articleCard(article) {
  const node = element("article", "article-card"); node.append(imageOrPlaceholder(article)); const content = element("div", "article-content"); const meta = element("div", "meta-row"); meta.append(sourceTag(article), elementWithText("span", `· ${timeAgo(article.published_at)}`, "meta")); const marked = state.bookmarks.some((bookmark) => bookmark.id === article.id); const bookmark = button("", "icon-button bookmark", marked ? "Remove bookmark" : "Bookmark article"); bookmark.setAttribute("aria-pressed", String(marked)); bookmark.append(icons.bookmark()); bookmark.addEventListener("click", () => toggleBookmark(article)); meta.append(bookmark); content.append(meta); const url = safeUrl(article.url); const title = elementWithText(url ? "a" : "span", article.title || "Untitled article", url ? "article-title" : "article-title-plain"); if (url) { title.href = url; title.target = "_blank"; title.rel = "noopener noreferrer"; } content.append(title); const summary = summaryFor(article); if (summary.bullets.length) { const bullets = element("ul", "bullets"); summary.bullets.slice(0, 3).forEach((bullet) => bullets.append(elementWithText("li", bullet))); content.append(bullets); } else content.append(paragraph("Summary unavailable", "fallback-note")); if (summary.fallback) content.append(paragraph("Showing balanced summary", "fallback-note")); if (url) { const read = elementWithText("a", "Read more →", "read-more"); read.href = url; read.target = "_blank"; read.rel = "noopener noreferrer"; content.append(read); } node.append(content); return node;
}

function imageOrPlaceholder(article) { const url = safeUrl(article.image_url); if (!url || !url.startsWith("https://")) return placeholder(article); const image = element("img", "thumbnail"); image.src = url; image.alt = ""; image.loading = "lazy"; image.referrerPolicy = "no-referrer"; image.decoding = "async"; image.width = 150; image.height = 148; image.addEventListener("error", () => image.replaceWith(placeholder(article))); return image; }
function placeholder(article) { const firstTopic = String(article.topics?.[0] || "").toLowerCase().replace(/[^a-z]/g, ""); const node = element("div", `placeholder topic-${firstTopic}`); node.setAttribute("aria-hidden", "true"); node.textContent = "✦"; return node; }
function sourceTag(article) { const type = ["arxiv", "hn"].includes(article.source_type) ? article.source_type : "rss"; return elementWithText("span", article.source || "Unknown source", `source-tag tag-${type}`); }
function summaryFor(article) { const requested = article.summaries?.[state.tone]; if (requested?.status === "ok" && Array.isArray(requested.bullets)) return { bullets: requested.bullets, fallback: false }; const balanced = article.summaries?.balanced; if (state.tone !== "balanced" && balanced?.status === "ok" && Array.isArray(balanced.bullets)) return { bullets: balanced.bullets, fallback: true }; return { bullets: [], fallback: false }; }

function topicPanel() { const node = card("Sources by Topic"); node.firstChild.prepend(icons.chart()); const counts = state.digest?.topic_counts || {}; const entries = Object.entries(counts).filter(([, value]) => Number.isFinite(value)); const max = Math.max(1, ...entries.map(([, value]) => value)); entries.forEach(([topic, count]) => { const row = element("div", "topic-row"); row.append(elementWithText("span", topic, "topic-label"), elementWithText("span", String(count))); const progress = element("progress", "bar"); progress.max = max; progress.value = count; progress.setAttribute("aria-label", `${topic}: ${count}`); row.append(progress); node.append(row); }); return node; }
function statsPanel() { const node = card("Summarizer Stats"); const articles = filterAndSort(); const summaries = articles.map(summaryFor).flatMap((summary) => summary.bullets); const average = summaries.length ? Math.round(summaries.reduce((total, bullet) => total + wordCount(bullet), 0) / summaries.length) : 0; const minutes = Math.round((articles.length * 4) / 5) * 5; const table = element("table", "stats"); [["Articles processed", state.run?.metrics?.items_unique ?? 0], ["Articles selected", articles.length], ["Avg. summary length", `${average} words`], ["Time saved", `~${minutes} minutes`], ["Last run", lastUpdated()]].forEach(([label, value]) => { const row = element("tr"); row.append(elementWithText("td", label), elementWithText("td", String(value))); table.append(row); }); node.append(table, paragraph(`Model: ${state.run?.model || "Unknown"} · Took ${state.run?.duration_s ?? 0} s`, "model-note")); return node; }
function bookmarksPanel() { const node = card("Bookmarked Articles"); const heading = node.firstChild; const view = button("View all", "view-all"); view.addEventListener("click", () => { state.bookmarkedOnly = true; render(); }); const wrap = element("div", "heading-row"); wrap.append(heading, view); node.replaceChildren(wrap); if (!state.bookmarks.length) { node.append(paragraph("No bookmarks yet. Tap the bookmark icon on any article.", "helper")); return node; } const list = element("div", "bookmark-list"); state.bookmarks.slice(0, 3).forEach((bookmark) => list.append(bookmarkRow(bookmark))); node.append(list); return node; }
function bookmarkRow(bookmark) { const url = safeUrl(bookmark.url); const node = element(url ? "a" : "div", "bookmark-item"); if (url) { node.href = url; node.target = "_blank"; node.rel = "noopener noreferrer"; } node.append(bookmarkImage(bookmark)); const copy = element("div"); copy.append(elementWithText("div", bookmark.title || "Untitled article", "bookmark-title"), elementWithText("div", `${bookmark.source || "Unknown source"} · ${timeAgo(bookmark.published_at)}`, "bookmark-meta")); node.append(copy); return node; }
function bookmarkImage(bookmark) { const url = safeUrl(bookmark.image_url); if (!url || !url.startsWith("https://")) return placeholder(bookmark); const image = element("img", "bookmark-thumb"); image.src = url; image.alt = ""; image.loading = "lazy"; image.referrerPolicy = "no-referrer"; image.decoding = "async"; image.width = 56; image.height = 56; image.addEventListener("error", () => image.replaceWith(placeholder(bookmark))); return image; }
function skeletons() { const wrap = element("div", "article-list"); for (let index = 0; index < 3; index += 1) { const item = element("div", "skeleton card"); for (let line = 0; line < 4; line += 1) item.append(element("div", "skeleton-line")); wrap.append(item); } return wrap; }
function message(text, className) { const node = element("div", className); node.append(paragraph(text)); return node; }
function banner(text, extra = "") { return elementWithText("div", text, `status-banner ${extra}`); }
function clearFilters() { state.topics = []; state.search = ""; state.bookmarkedOnly = false; save("digest.topics", state.topics); const search = document.querySelector("#search-input"); if (search) search.value = ""; render(); }
function toggleBookmark(article) { const snapshot = bookmarkSnapshot(article); const existing = state.bookmarks.findIndex((bookmark) => bookmark.id === snapshot.id); state.bookmarks = existing >= 0 ? state.bookmarks.filter((_, index) => index !== existing) : [snapshot, ...state.bookmarks].slice(0, 100); save("digest.bookmarks", state.bookmarks); render(); }
function bookmarkSnapshot(article) { return { id: String(article.id || ""), title: String(article.title || ""), url: String(article.url || ""), source: String(article.source || ""), source_type: String(article.source_type || "rss"), published_at: String(article.published_at || ""), image_url: typeof article.image_url === "string" ? article.image_url : null }; }
function bookmarkArticles(articles) { const current = new Map(articles.map((article) => [article.id, article])); return state.bookmarks.map((bookmark) => current.get(bookmark.id) || bookmark); }
function lastUpdated() { const date = new Date(state.run?.finished_at || ""); if (Number.isNaN(date.getTime())) return "Not available"; const today = new Date(); const yesterday = new Date(); yesterday.setDate(today.getDate() - 1); const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); if (date.toDateString() === today.toDateString()) return `Today, ${time}`; if (date.toDateString() === yesterday.toDateString()) return `Yesterday, ${time}`; return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }); }
function nextRun() { const now = new Date(); const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), SCHEDULE_UTC_HOUR)); if (next <= now) next.setUTCDate(next.getUTCDate() + 1); return `${next.toLocaleDateString(undefined, { month: "short", day: "numeric" })}, ${String(SCHEDULE_UTC_HOUR).padStart(2, "0")}:00 (UTC)`; }
function readTopics() { const stored = read("digest.topics", null); return Array.isArray(stored) && stored.every((item) => typeof item === "string") ? stored : DEFAULT_TOPICS.slice(0, 5); }
function readCustomTopics() { const stored = read("digest.customTopics", []); return Array.isArray(stored) ? stored.filter((item) => typeof item === "string" && item.length <= 30) : []; }
function readTone() { const stored = read("digest.tone", "balanced"); return TONES.includes(stored) ? stored : "balanced"; }
function readBookmarks() { const stored = read("digest.bookmarks", []); return Array.isArray(stored) ? stored.filter(validBookmark).slice(0, 100) : []; }
function validBookmark(value) { return value && typeof value === "object" && ["id", "title", "url", "source", "source_type", "published_at"].every((key) => typeof value[key] === "string") && (value.image_url === null || typeof value.image_url === "string"); }
function read(key, fallback) { try { return JSON.parse(localStorage.getItem(key) || "null") ?? fallback; } catch (_) { return fallback; } }
function save(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* storage is optional */ } }

init();
