"""Thin LangGraph nodes which delegate I/O and logic to services."""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings, load_feed_config
from app.models.schemas import (
    TONES,
    Article,
    CacheFile,
    FeedDefinition,
    ParsedArticle,
    RunFile,
    Summary,
)
from app.services.dedupe_service import deduplicate_articles
from app.services.feed_service import Resolver, fetch_all_feeds, resolve_host
from app.services.llm_service import Summarizer, summarize_pairs
from app.services.topic_service import tag_articles
from app.storage.json_store import build_digest, merge_cache, prune_cache, write_outputs


def utc_now() -> datetime:
    """Return the current UTC time through an injectable clock boundary."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class NodeDependencies:
    """Explicit non-state dependencies shared by nodes in one graph invocation."""

    settings: Settings
    config_path: Path
    data_dir: Path
    summarizer: Summarizer
    resolver: Resolver = resolve_host
    clock: Callable[[], datetime] = utc_now


async def load_config(_: dict, dependencies: NodeDependencies) -> dict:
    """Load validated feed and topic configuration."""
    config = await asyncio.to_thread(load_feed_config, dependencies.config_path)
    started_at = _iso_timestamp(dependencies.clock())
    return {
        "run_id": uuid.uuid4().hex,
        "started_at": started_at,
        "feeds": [feed.model_dump() for feed in config.feeds],
        "topic_keywords": config.topics,
        "default_topics": {feed.name: feed.default_topic for feed in config.feeds},
    }


async def fetch_feeds(state: dict, dependencies: NodeDependencies) -> dict:
    """Fetch configured feeds concurrently and retain individual failures."""
    feeds = [FeedDefinition.model_validate(feed) for feed in state["feeds"]]
    results = await fetch_all_feeds(feeds, dependencies.settings, dependencies.resolver)
    errors = [result.error for result in results if result.error]
    raw_items = [article.model_dump() for result in results for article in result.articles]
    return {
        "raw_items": raw_items,
        "errors": errors,
        "metrics": _metrics(
            state,
            feeds_total=len(results),
            feeds_ok=sum(result.error is None for result in results),
        ),
    }


async def parse_entries(state: dict, dependencies: NodeDependencies) -> dict:
    """Validate the already sanitized Phase 1 parsed-entry boundary."""
    parsed = [ParsedArticle.model_validate(item).model_dump() for item in state["raw_items"]]
    return {"raw_items": parsed, "metrics": _metrics(state, items_parsed=len(parsed))}


async def dedupe(state: dict, dependencies: NodeDependencies) -> dict:
    """Apply the existing URL and title deduplication service."""
    raw_articles = [ParsedArticle.model_validate(item) for item in state["raw_items"]]
    articles = deduplicate_articles(raw_articles)
    return {
        "articles": [article.model_dump() for article in articles],
        "metrics": _metrics(state, items_unique=len(articles)),
    }


async def classify_topics(state: dict, dependencies: NodeDependencies) -> dict:
    """Apply deterministic Phase 1 keyword classification."""
    articles = [Article.model_validate(item) for item in state["articles"]]
    tagged = tag_articles(articles, state["topic_keywords"], state["default_topics"])
    return {"articles": [article.model_dump() for article in tagged]}


async def select_articles(state: dict, dependencies: NodeDependencies) -> dict:
    """Select capped, topic-matched articles that still need at least one summary."""
    candidates = [
        Article.model_validate(item)
        for item in state["articles"]
        if item["topics"] and _needs_summary(Article.model_validate(item), state["cache"])
    ]
    candidates.sort(
        key=lambda article: (len(article.topics), article.published_at or ""), reverse=True
    )
    source_counts: dict[str, int] = {}
    selected: list[Article] = []
    for article in candidates:
        if source_counts.get(article.source, 0) >= 4:
            continue
        selected.append(article)
        source_counts[article.source] = source_counts.get(article.source, 0) + 1
        if len(selected) == dependencies.settings.max_articles_per_run:
            break
    return {"selected": [article.model_dump() for article in selected]}


async def summarize(state: dict, dependencies: NodeDependencies) -> dict:
    """Generate only missing pairs, or only failed pairs on the graph retry pass."""
    articles = {item["id"]: Article.model_validate(item) for item in state["selected"]}
    pairs = _pairs_to_summarize(state, articles)
    results = await summarize_pairs(
        pairs, dependencies.summarizer, dependencies.settings.llm_concurrency
    )
    previous = [Summary.model_validate(item) for item in state["summaries"]]
    is_retry = bool(previous and any(summary.status == "failed" for summary in previous))
    if is_retry:
        retained = [summary for summary in previous if summary.status != "failed"]
        results = retained + results
    update = {"summaries": [summary.model_dump() for summary in results]}
    if is_retry:
        update["retry_count"] = 1
    return update


async def validate(state: dict, dependencies: NodeDependencies) -> dict:
    """Validate summary state before conditional retry routing."""
    summaries = [Summary.model_validate(item) for item in state["summaries"]]
    return {"summaries": [summary.model_dump() for summary in summaries]}


async def save_output(state: dict, dependencies: NodeDependencies) -> dict:
    """Merge selected work into the cache and atomically persist all public files."""
    finished = dependencies.clock()
    finished_at = _iso_timestamp(finished)
    selected = [Article.model_validate(item) for item in state["selected"]]
    summaries = [Summary.model_validate(item) for item in state["summaries"]]
    merged = merge_cache(
        state["cache"], selected, summaries, dependencies.summarizer.model_name, finished_at
    )
    cache = prune_cache(merged, finished)
    digest = build_digest(cache, list(state["topic_keywords"]), finished_at)
    failed = sum(summary.status == "failed" for summary in summaries)
    successful = sum(summary.status == "ok" for summary in summaries)
    metrics = _metrics(
        state,
        summaries_ok=successful,
        summaries_failed=failed,
        tokens_total=sum(summary.tokens for summary in summaries),
        duration_s=round((finished - _parse_timestamp(state["started_at"])).total_seconds(), 3),
    )
    run = RunFile(
        run_id=state["run_id"],
        status="partial" if state["errors"] or failed else "success",
        started_at=state["started_at"],
        finished_at=finished_at,
        model=dependencies.summarizer.model_name,
        duration_s=float(metrics["duration_s"]),
        metrics=metrics,
        errors=state["errors"],
    )
    await asyncio.to_thread(write_outputs, dependencies.data_dir, cache, digest, run)
    return {"cache": cache, "metrics": metrics}


def _needs_summary(article: Article, cache: CacheFile) -> bool:
    cached = cache.items.get(article.id)
    return cached is None or any(_tone_needs_summary(cached, tone) for tone in TONES)


def _pairs_to_summarize(state: dict, articles: dict[str, Article]) -> list[tuple[Article, str]]:
    if state["summaries"]:
        return [
            (articles[summary["article_id"]], summary["tone"])
            for summary in state["summaries"]
            if summary["status"] == "failed" and summary["article_id"] in articles
        ]
    pairs: list[tuple[Article, str]] = []
    for article in articles.values():
        cached = state["cache"].items.get(article.id)
        for tone in TONES:
            if cached is None or _tone_needs_summary(cached, tone):
                pairs.append((article, tone))
    return pairs


def _metrics(state: dict, **values: int | float) -> dict[str, int | float]:
    return {**state["metrics"], **values}


def _tone_needs_summary(cached, tone: str) -> bool:
    summary = cached.summaries.get(tone)
    return summary is None or summary.status != "ok"


def _iso_timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
