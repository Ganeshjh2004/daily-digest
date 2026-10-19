from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.graph.nodes import NodeDependencies, fetch_feeds, load_config, select_articles
from app.models.schemas import Article, CacheFile
from app.services.llm_service import FakeSummarizer


def make_article(index: int, source: str, topics: list[str]) -> Article:
    return Article(
        id=f"article-{index}",
        title=f"Article {index}",
        url=f"https://example.com/{index}",
        source=source,
        source_type="rss",
        description="This article has enough content for a deterministic summary.",
        topics=topics,
        published_at=f"2026-10-{17 - index:02d}T08:00:00Z",
    )


@pytest.mark.asyncio
async def test_select_articles_respects_source_and_total_caps(tmp_path) -> None:
    articles = [make_article(index, "One", ["Python", "Backend"]) for index in range(5)]
    articles.extend(make_article(index + 5, "Two", ["Python"]) for index in range(5))
    settings = Settings(_env_file=None, max_articles_per_run=6)
    dependencies = NodeDependencies(
        settings=settings,
        config_path=tmp_path / "feeds.yaml",
        data_dir=tmp_path / "data",
        summarizer=FakeSummarizer(),
        clock=lambda: datetime(2026, 10, 17, tzinfo=UTC),
    )
    state = {"articles": [article.model_dump() for article in articles], "cache": CacheFile()}

    result = await select_articles(state, dependencies)

    selected = [Article.model_validate(item) for item in result["selected"]]
    assert len(selected) == 6
    assert sum(article.source == "One" for article in selected) == 4


@pytest.mark.asyncio
async def test_load_config_sets_run_metadata_and_fetch_uses_state(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "feeds.yaml"
    config_path.write_text(
        "feeds:\n- name: Example\n  url: https://example.com/feed\n  source_type: rss\n"
        "topics:\n  Python:\n  - python\n",
        encoding="utf-8",
    )
    dependencies = NodeDependencies(
        settings=Settings(_env_file=None),
        config_path=config_path,
        data_dir=tmp_path / "data",
        summarizer=FakeSummarizer(),
        clock=lambda: datetime(2026, 10, 17, tzinfo=UTC),
    )
    loaded = await load_config({}, dependencies)
    assert loaded["run_id"]
    assert loaded["started_at"] == "2026-10-17T00:00:00Z"

    async def fetch_from_state(feeds, *_):
        assert len(feeds) == 1
        return []

    monkeypatch.setattr("app.graph.nodes.fetch_all_feeds", fetch_from_state)
    result = await fetch_feeds({**loaded, "metrics": {}}, dependencies)
    assert result["metrics"] == {"feeds_total": 0, "feeds_ok": 0}
