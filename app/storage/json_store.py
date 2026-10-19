"""Validated, bounded, and atomically written JSON data files."""

import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from app.models.schemas import (
    TONES,
    Article,
    CachedArticle,
    CachedSummary,
    CacheFile,
    DigestArticle,
    DigestFile,
    DigestSummary,
    RunFile,
    Summary,
)


def read_cache(path: Path) -> CacheFile:
    """Read a validated cache, backing up corrupt content before rebuilding it."""
    if not path.exists():
        return CacheFile()
    try:
        with path.open(encoding="utf-8") as cache_file:
            return CacheFile.model_validate_json(cache_file.read())
    except (json.JSONDecodeError, ValidationError):
        backup_path = path.with_suffix(f"{path.suffix}.corrupt-{_file_timestamp()}")
        path.replace(backup_path)
        return CacheFile()


def merge_cache(
    cache: CacheFile,
    selected: list[Article],
    summaries: list[Summary],
    model_name: str,
    seen_at: str,
) -> CacheFile:
    """Store only selected articles and their newly produced summaries in the cache."""
    items = dict(cache.items)
    summary_map = {(summary.article_id, summary.tone): summary for summary in summaries}
    for article in selected:
        existing = items.get(article.id)
        cached_summaries = dict(existing.summaries) if existing else {}
        for tone in TONES:
            summary = summary_map.get((article.id, tone))
            if summary is not None:
                cached_summaries[tone] = CachedSummary(
                    status=summary.status, bullets=summary.bullets, model=model_name
                )
        items[article.id] = CachedArticle(
            title=article.title,
            url=article.url,
            source=article.source,
            source_type=article.source_type,
            published_at=article.published_at,
            image_url=article.image_url,
            topics=article.topics,
            summaries=cached_summaries,
            last_seen=seen_at,
        )
    return CacheFile(version=cache.version, items=items)


def prune_cache(cache: CacheFile, now: datetime) -> CacheFile:
    """Drop cache entries not seen within the required 30-day retention period."""
    cutoff = now - timedelta(days=30)
    items = {
        article_id: article
        for article_id, article in cache.items.items()
        if (last_seen := _parse_timestamp(article.last_seen)) is not None and last_seen >= cutoff
    }
    return CacheFile(version=cache.version, items=items)


def build_digest(cache: CacheFile, topics: list[str], generated_at: str) -> DigestFile:
    """Build the public seven-day, 60-article digest from cached selected articles."""
    generated = _parse_timestamp(generated_at) or datetime.now(UTC)
    cutoff = generated - timedelta(days=7)
    articles = [
        DigestArticle(
            id=article_id,
            title=cached.title,
            url=cached.url,
            source=cached.source,
            source_type=cached.source_type,
            published_at=cached.published_at,
            topics=cached.topics,
            image_url=cached.image_url,
            summaries={
                tone: DigestSummary(status=summary.status, bullets=summary.bullets)
                for tone, summary in cached.summaries.items()
            },
        )
        for article_id, cached in cache.items.items()
        if (published := _parse_timestamp(cached.published_at)) is not None and published >= cutoff
    ]
    articles.sort(key=lambda article: article.published_at or "", reverse=True)
    articles = articles[:60]
    counts = Counter(topic for article in articles for topic in article.topics)
    top_topics = sorted(counts, key=lambda topic: (-counts[topic], topic))[:5]
    topic_counts = {topic: counts[topic] for topic in top_topics}
    topic_counts["Other"] = sum(count for topic, count in counts.items() if topic not in top_topics)
    return DigestFile(
        generated_at=generated_at,
        topics=topics,
        topic_counts=topic_counts,
        articles=articles,
    )


def write_outputs(data_dir: Path, cache: CacheFile, digest: DigestFile, run: RunFile) -> None:
    """Atomically replace all fixed public pipeline files after all models validate."""
    _atomic_write_json(data_dir / "cache.json", cache.model_dump(mode="json"))
    _atomic_write_json(data_dir / "digest.json", digest.model_dump(mode="json"))
    _atomic_write_json(data_dir / "run.json", run.model_dump(mode="json"))


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
        os.replace(temporary_name, path)
    except OSError:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _file_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
