# Daily Digest: Frontend Design

> Companion to `REQUIREMENTS.md`, `ARCHITECTURE.md`, `SECURITY_RULES.md`, and `PHASES.md`.
> Visual reference: the "Daily Digest" light mockup (3 columns, white cards, blue accent).
> Scope: **Phase 3** (static web UI). The page reads `data/digest.json` and `data/run.json`. There is no backend.

---

## 0. Instructions for AI Assistants (READ FIRST)

1. Read all five docs before writing UI code. Build **only** what this file describes.
2. **Plain HTML + CSS + vanilla JavaScript.** No React, no Tailwind, no icon library, no CDN scripts, no webfonts. Colors and sizes come from CSS variables (Section 3).
3. **Safe rendering is mandatory** (Section 11). Never use `innerHTML` with feed or JSON data. Use `textContent` and DOM methods.
4. All filtering, sorting, tone switching, search, and bookmarking happen **in the browser**. The page never calls an API.
5. Every state must be handled: loading, empty, filtered-to-nothing, and failed or stale run (Section 9).
6. Keep files small and readable. Use the structure in Section 12. Do not add files or libraries without asking.
7. Match the mockup's layout and spacing closely, but follow the **tokens in this file** over pixel-guessing.
8. If something here conflicts with another doc, stop and ask one question. Known conflicts are listed in Section 14.
9. When done, report: what changed, files touched, how to run it (`python -m http.server` inside `docs/`), and the checklist status (Section 13).

---

## 1. Design Goals

| Goal | Meaning |
|------|---------|
| Light and minimal | White cards on a soft gray background, thin borders, one blue accent. No glow, no gradients (except placeholder thumbnails). |
| Scannable | Title, source, time, and short bullets visible without clicking. |
| Simple to build | Plain files, small components, one data flow: JSON in, DOM out. |
| Safe | Feed content is untrusted and never injected as HTML. |
| Responsive | 3 columns on desktop, single column on smaller screens. |

## 2. Page Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ [logo] Daily Digest                      [ Search articles...  ]  (U)│  HEADER
│        Curated AI & Tech news for you                                │
├────────────────┬───────────────────────────────┬─────────────────────┤
│ LEFT           │ CENTER                        │ RIGHT               │
│ Your Interests │ Latest Articles   [Most Rel▾] │ Sources by Topic    │
│  [chips]       │ ┌───────────────────────────┐ │  ▇▇▇▇▇▇▇▇  12       │
│  + Add custom  │ │[img] arXiv · 3 hours ago 🔖│ │  ▇▇▇▇▇     8        │
│                │ │      Title                │ │                     │
│ Summary Tone   │ │      • bullet             │ │ Summarizer Stats    │
│  ◉ Balanced    │ │      • bullet             │ │  Processed     48   │
│  ○ Technical   │ │      • bullet             │ │  Selected      12   │
│  ○ Beginner    │ │      Read more →          │ │  Avg length  128 w  │
│                │ └───────────────────────────┘ │  Time saved ~45 min │
│ [ Run Digest ] │ ┌───────────────────────────┐ │  Last run  10:32 AM │
│                │ │ next card ...             │ │                     │
│ Last Updated   │ └───────────────────────────┘ │ Bookmarked  View all│
│ Next run       │                               │  [img] Title...     │
└────────────────┴───────────────────────────────┴─────────────────────┘
```

**Grid (desktop, 1100px and wider):**
`grid-template-columns: 340px minmax(0, 1fr) 360px; gap: 24px;` inside a container with `max-width: 1440px`, centered, with 24px side padding.

**Below 1100px:** one column, in this order: Left controls, Center articles, Right panels. The header search drops under the title on narrow screens.

## 3. Design Tokens

Define these once in `:root` in `styles.css`. Use only these values.

### Colors

| Token | Value | Use |
|-------|-------|-----|
| `--bg` | `#F5F7FB` | Page background |
| `--surface` | `#FFFFFF` | Cards, header, panels |
| `--border` | `#E4E8F0` | Card and chip borders, dividers |
| `--text` | `#0F172A` | Titles, main text |
| `--text-muted` | `#64748B` | Subtitles, meta, helper text |
| `--primary` | `#1D5FF2` | Buttons, links, checked states, bars |
| `--primary-soft` | `#EAF1FF` | Checked chip background, hover |
| `--bar-track` | `#E9EEF6` | Bar chart track |
| `--success` | `#22C55E` | Run OK dot |
| `--warning` | `#F59E0B` | Partial or stale run dot |
| `--danger` | `#EF4444` | Failed run dot |
| `--tag-arxiv-bg` / `--tag-arxiv-fg` | `#FDECEA` / `#C0392B` | arXiv source tag |
| `--tag-hn-bg` / `--tag-hn-fg` | `#FFEEE3` / `#E4572E` | Hacker News tag |
| `--tag-rss-bg` / `--tag-rss-fg` | `#FFF1E0` / `#D97706` | Generic RSS tag |

Source tag color comes from a small map keyed by `source_type` (`arxiv`, `hn`, `rss`). Unknown types use the RSS style.

### Type, spacing, shape

| Token | Value |
|-------|-------|
| Font | `Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` (no webfont download) |
| App title | 20px / 600 |
| Section heading | 18px / 600 |
| Card title | 17px / 600, line-height 1.3 |
| Body and bullets | 14px / 400, line-height 1.5 |
| Meta and helper | 13px / 400, `--text-muted` |
| Spacing scale | 4, 8, 12, 16, 24, 32 px |
| Radius | cards 14px, chips 10px, buttons 10px, thumbnails 10px, avatar 50% |
| Shadow | `0 1px 2px rgba(15,23,42,0.04)`; on hover `0 4px 12px rgba(15,23,42,0.08)` |
| Focus ring | `2px solid var(--primary)` with `outline-offset: 2px` on every interactive element |

## 4. Header

| Element | Details |
|---------|---------|
| Logo | 44px rounded square with an inline SVG newspaper icon, blue stroke |
| Title | "Daily Digest" |
| Subtitle | "Curated AI & Tech news for you" |
| Search | Input with a magnifier icon, placeholder "Search articles, topics...". Filters the center list as you type (150 ms debounce). Matches title, bullets, source, and topics. Case-insensitive. |
| Avatar | Decorative circle with "U". No menu, no accounts in v1. |

## 5. Left Column: Controls

### 5.1 Your Interests
- Heading "Your Interests", helper "Select topics to filter articles".
- Topic **chips** with a checkbox: each chip is a `<label>` wrapping an `<input type="checkbox">`, so keyboard and screen readers work.
- Default topics (from `topics` in `digest.json`): AI Agents, LLMs, Python, Backend, System Design, Machine Learning, DevOps, Cloud, Productivity.
- Unchecked chip: white, border. Checked chip: `--primary-soft` background, `--primary` border, blue checkbox.
- **"+ Add custom topic"**: dashed or plain outlined button; opens an inline text input (max 30 chars). Adds a new chip. A custom topic filters articles by **keyword match** in title and bullets (the pipeline does not know it). Saved in `localStorage`. Custom chips get a small "×" to remove.
- Checked topics are remembered in `localStorage` (`digest.topics`). First visit: first five default topics checked.
- An article is shown if it matches **at least one** checked topic. If no topic is checked, show all articles.

### 5.2 Summary Tone
- Heading "Summary Tone" with an info icon (tooltip: "Changes how summaries are written").
- Radio group, each option with a label and a muted helper line:

| Label | Helper | Data key |
|-------|--------|----------|
| Balanced | Neutral and informative | `balanced` |
| Technical | More technical details | `technical` |
| Beginner Friendly | Simple and easy to understand | `beginner_friendly` |

- Default `balanced`; remembered in `localStorage` (`digest.tone`).
- Changing tone swaps the bullets on every card instantly. If an article has no summary for that tone, fall back to `balanced` and show a small muted note "Showing balanced summary".

### 5.3 Run Digest Now
- Full-width primary button with a play icon, label "Run Digest Now".
- It is a **link** (`<a>` styled as a button) that opens the GitHub Actions workflow page in a new tab (`WORKFLOW_URL` in `config.js`). The user clicks "Run workflow" there. The site cannot start the pipeline itself.
- Under the button, muted text: "Opens GitHub Actions. Takes about a minute."

### 5.4 Last Updated card
- Row 1: status dot + "Today, 10:32 AM" (from `run.finished_at`, shown in the viewer's local time; use "Yesterday" or a date for older runs) + a refresh icon button that **reloads the JSON files** (re-fetches, no pipeline run).
- Row 2: calendar icon, "Next scheduled run", and the next occurrence of the cron time, for example "Tomorrow, 8:00 AM (UTC)". The time comes from `SCHEDULE_UTC_HOUR` in `config.js`, which must match the workflow's cron.
- Dot color: green when `run.status = "success"`, amber when `"partial"` or when the run is older than 36 hours, red when `"failed"`.

## 6. Center Column: Latest Articles

### 6.1 Header row
- "Latest Articles" and a sort dropdown (native `<select>`, styled): **Most Relevant** (default) and **Newest**.
- **Most Relevant:** more matched checked topics first; ties broken by newest. **Newest:** by `published_at` descending.
- Show a small count: "12 articles".
- When the user clicks "View all" in Bookmarks, a chip "Bookmarked only ✕" appears here and the list shows saved articles only.

### 6.2 Article card

```
┌────────────────────────────────────────────────────────────┐
│ ┌────────┐  [arXiv]  · 3 hours ago                    🔖 │
│ │ image  │  Title in semibold, up to 2 lines               │
│ │ 150px  │  • bullet 1                                     │
│ │        │  • bullet 2                                     │
│ └────────┘  • bullet 3                                     │
│             Read more →                                    │
└────────────────────────────────────────────────────────────┘
```

| Part | Details |
|------|---------|
| Thumbnail | 150 × 148 px, radius 10px, `object-fit: cover`. Uses `image_url` when valid; otherwise a **placeholder**: soft gradient (color picked from the first topic) with a small topic icon. |
| Source tag | Small pill with the source name, colored by `source_type`. |
| Time | "3 hours ago", computed in the browser from `published_at`. |
| Bookmark | Icon button, top right. Outline when off, filled blue when on. `aria-pressed` reflects state. |
| Title | Whole title links to the article (`target="_blank"`, `rel="noopener noreferrer"`). Max 2 lines, then ellipsis. |
| Bullets | A `<ul>` with 14px muted-dark text. Render **every bullet in the array** (2 or 3), max 3. |
| Read more | Blue link with an arrow, same URL as the title. |
| Card | White, 1px border, 14px radius, 16px padding, 16px gap between cards, hover shadow. |

On narrow screens the thumbnail moves to a smaller 96px size or hides below 480px; text takes full width.

## 7. Right Column: Panels

All three are white cards with a heading row (icon + title).

### 7.1 Sources by Topic
- One row per topic: topic name, horizontal bar, count.
- Counts come from `digest.json` (`topic_counts`), top 5 topics plus "Others" (sum of the rest).
- Bar width = `count / max_count * 100%`, blue fill on `--bar-track`, 8px height, rounded.
- Clicking a row toggles that topic's filter chip (nice to have).

### 7.2 Summarizer Stats
A bordered table with label left, value right:

| Row | Source |
|-----|--------|
| Articles processed | `run.metrics.items_unique` (new items seen this run) |
| Articles selected | number currently shown after filters |
| Avg. summary length | average words per summary in the current tone, for example "52 words" |
| Time saved | `selected × 4 min`, rounded to the nearest 5, shown as "~45 minutes" |
| Last run | `run.finished_at`, for example "Today, 10:32 AM" |

Also show a muted line: "Model: `<run.model>`" and duration "Took 9.2 s".

### 7.3 Bookmarked Articles
- Heading with a bookmark icon and a "View all" link on the right.
- Shows the **3 most recent** bookmarks: 56px thumbnail, title (1 line, ellipsis), "Source · time ago". Clicking opens the article.
- Empty state: "No bookmarks yet. Tap the bookmark icon on any article."
- Bookmarks are stored in `localStorage` (`digest.bookmarks`) as a small snapshot: `{ id, title, url, source, source_type, published_at, image_url }`. Snapshots keep bookmarks working after an article drops out of `digest.json`. Keep at most 100.

## 8. Data Contract (what the UI reads)

### `data/digest.json`

```json
{
  "generated_at": "2026-10-16T05:02:11Z",
  "topics": ["AI Agents", "LLMs", "Python", "Backend", "System Design",
             "Machine Learning", "DevOps", "Cloud", "Productivity"],
  "topic_counts": { "AI Agents": 12, "LLMs": 8, "Python": 6, "Backend": 5, "System Design": 4, "Other": 3 },
  "articles": [
    {
      "id": "a1b2c3...",
      "title": "AgentScape: A Unified Framework for Evaluating LLM Agents",
      "url": "https://arxiv.org/abs/....",
      "source": "arXiv",
      "source_type": "arxiv",
      "published_at": "2026-10-16T02:10:00Z",
      "topics": ["AI Agents", "LLMs"],
      "image_url": null,
      "summaries": {
        "balanced": { "status": "ok", "bullets": ["...", "...", "..."] },
        "technical": { "status": "ok", "bullets": ["...", "...", "..."] },
        "beginner_friendly": { "status": "ok", "bullets": ["...", "...", "..."] }
      }
    }
  ]
}
```

### `data/run.json`

```json
{
  "run_id": "...",
  "status": "success",
  "started_at": "2026-10-16T05:01:50Z",
  "finished_at": "2026-10-16T05:02:11Z",
  "model": "<GROQ_MODEL value>",
  "duration_s": 21.4,
  "metrics": { "feeds_total": 12, "feeds_ok": 12, "items_parsed": 146,
               "items_unique": 48, "summaries_ok": 12, "summaries_failed": 0 },
  "errors": []
}
```

**Rules for the UI:**
- Missing or `null` fields never crash the page. Use fallbacks (placeholder image, "Unknown source", hide missing tone).
- Skip any summary whose `status` is not `"ok"`; show "Summary unavailable" for the card in that tone.
- Ignore unknown extra fields.

## 9. States and Edge Cases

| State | What the user sees |
|-------|--------------------|
| Loading | Skeleton cards (gray blocks) in the center, skeleton rows in the right panels. |
| Load error | Center card: "Couldn't load the digest. Try the refresh icon." Left and right panels still render controls. |
| Empty digest | "No articles yet. Run the digest to get started." |
| Filters match nothing | "No articles match your filters." with a "Clear filters" button. |
| Search matches nothing | Same message, mentioning the search text (inserted with `textContent`). |
| Run `partial` | Amber dot and a thin banner: "Some feeds failed in the last run (10/12 OK)." |
| Run `failed` | Red dot and banner: "The last run failed. Showing the previous digest." |
| Stale (older than 36 h) | Amber dot and the text "Digest is out of date". |
| Image fails to load | Replace with the placeholder (`onerror` handler set through `addEventListener`). |
| `localStorage` unavailable | Wrap every read and write in `try/catch`; features work for the session without saving. |

## 10. Interactions and Behavior

| Action | Result |
|--------|--------|
| Toggle topic chip | Re-filter, re-sort, update counts and stats. Save to `localStorage`. |
| Change tone | Swap bullets on all cards; update avg length. Save choice. |
| Type in search | Debounced filter on title, bullets, source, topics. |
| Change sort | Re-sort the list. |
| Click bookmark | Toggle, update the right-hand Bookmarks panel immediately. |
| Click refresh icon | Re-fetch both JSON files with `cache: "no-store"`; show a brief spinner. |
| Click "Run Digest Now" | Opens the GitHub Actions page in a new tab. |
| Keyboard | Tab order follows reading order; Enter and Space work on chips, radios, and bookmark buttons. |

**Time formatting:** "just now", "N minutes ago", "N hours ago", "N days ago", then a short date.
**Re-render rule:** keep one `state` object (`topics`, `customTopics`, `tone`, `sort`, `search`, `bookmarkedOnly`, `digest`, `run`) and one `render()` that rebuilds the three columns from it. Event handlers only change `state` and call `render()`.

## 11. Safe Rendering Rules (from `SECURITY_RULES.md`)

1. **Never** use `innerHTML`, `outerHTML`, or `insertAdjacentHTML` with data from JSON or `localStorage`. Build elements with `document.createElement` and set `textContent`.
2. Links: only use a URL if it starts with `https://` or `http://`. Otherwise render the title as plain text with no link. Always add `target="_blank"` with `rel="noopener noreferrer"`.
3. Images: only `https://` URLs. Set `loading="lazy"`, `referrerpolicy="no-referrer"`, `decoding="async"`, and fixed dimensions. On error, show the placeholder. Use empty `alt=""` (the thumbnail is decorative).
4. Treat `localStorage` data as untrusted too. Validate its shape before use.
5. Add a CSP meta tag in `index.html`: `default-src 'self'; img-src 'self' https: data:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'`.
6. No inline `<script>` or inline `style` attributes where avoidable. No external scripts, fonts, or stylesheets.
7. Never put keys or tokens in frontend code. The page only knows public URLs.

## 12. File Structure

```
docs/
├── index.html        # markup skeleton: header, 3 columns, empty containers
├── styles.css        # tokens (:root) + component styles + responsive rules
├── config.js         # WORKFLOW_URL, SCHEDULE_UTC_HOUR, DATA paths
├── app.js            # state, load data, render functions, event handlers
├── icons.js          # small inline SVG builders (newspaper, search, bookmark, play, calendar, refresh, info, clock, bar-chart)
└── data/
    ├── digest.json   # copied here by the GitHub Action
    └── run.json
```

`app.js` sections, in order: `loadData()`, `state`, `helpers` (timeAgo, safeUrl, wordCount), `filterAndSort()`, `renderControls()`, `renderArticles()`, `renderPanels()`, `render()`, `init()`.

## 13. Build Checklist (Phase 3 "Done when")

- [ ] Layout matches the mockup: header, 3 columns, white cards on a light gray page
- [ ] Topic chips, custom topic, tone radios, Run Digest Now link, Last Updated card all work
- [ ] Article cards show thumbnail or placeholder, source tag, time ago, bookmark, title, bullets, Read more
- [ ] Filter, sort, search, and tone switching work with no page reload
- [ ] Sources by Topic bars, Summarizer Stats, and Bookmarked Articles panels render from JSON and `localStorage`
- [ ] Loading, error, empty, no-match, partial, failed, and stale states handled
- [ ] No `innerHTML` with dynamic data; links and images validated; CSP meta present
- [ ] Works with sample JSON files while the pipeline is not finished (include `docs/data/sample-digest.json` for development)
- [ ] Usable on a phone width (single column) and by keyboard
- [ ] Lighthouse accessibility score of 90 or higher

## 14. Changes This Design Needs in Other Docs

The new mockup differs from earlier docs. Update these before or during Phase 2 and 3:

| Topic | Earlier docs | This design | Action |
|-------|--------------|-------------|--------|
| Bullets per summary | Exactly 2 | Mockup shows 3 | Choose one. The UI renders 2 or 3 bullets, so either works. Recommended: **3 bullets of at most 25 words** to match the mockup, and update the schema and tests. |
| Tone names | `executive_brief`, `technical`, `beginner_friendly` | Balanced, Technical, Beginner Friendly | Rename `executive_brief` to `balanced` in prompts, schema, and data. |
| Topics | AI, Python, Startups, Climate | AI Agents, LLMs, Python, Backend, System Design, Machine Learning, DevOps, Cloud, Productivity | Update `topics` keywords in `feeds.yaml` and `topic_service`. |
| Tone data | One tone per run | All 3 tones stored per article so the UI can switch instantly | Summarize all 3 tones for selected articles (about 3x LLM calls; keep `MAX_ARTICLES_PER_RUN` low), or generate only `balanced` and let the UI fall back. |
| Thumbnails | None | `image_url` per article | Pipeline extracts the image from the feed (`media_content`, `media_thumbnail`, or `enclosure`), keeps `https` only, else `null`. |
| Source type | Not stored | `source_type` (`arxiv`, `hn`, `rss`) | Add to each feed in `feeds.yaml`. |
| Pipeline-steps panel | In the first mockup | Dropped | Not needed in the UI. |
| Styling | Tailwind CDN | Plain CSS with variables | Update `PHASES.md` Phase 3 and remove the Tailwind CDN mention. |
| Run button | "Refresh RSS" | "Run Digest Now" link to GitHub Actions | Already consistent with the cron-only deployment. |

## 15. Out of Scope (v1)

User accounts or login, server-side search, push notifications, dark mode, drag-and-drop, editing feeds in the UI, and running the pipeline from the browser.
