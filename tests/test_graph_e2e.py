from datetime import UTC, datetime

import httpx
import pytest
import respx
import yaml
from langchain_core.exceptions import OutputParserException

from app.config import Settings
from app.graph.builder import run_pipeline
from app.graph.nodes import NodeDependencies
from app.models.schemas import Article, ArticleSummary, DigestFile, RunFile
from app.services.llm_service import FakeSummarizer

FIXED_NOW = datetime(2026, 10, 17, 8, 0, tzinfo=UTC)


def write_config(path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "feeds": [
                    {
                        "name": "Example",
                        "url": "https://feeds.example.com/rss",
                        "source_type": "rss",
                    }
                ],
                "topics": {"Python": ["python"], "LLMs": ["llm"]},
            }
        ),
        encoding="utf-8",
    )


async def public_resolver(_: str, __: int | None) -> list[str]:
    return ["93.184.216.34"]


def dependencies(tmp_path, summarizer) -> NodeDependencies:
    config_path = tmp_path / "feeds.yaml"
    write_config(config_path)
    return NodeDependencies(
        settings=Settings(_env_file=None, max_articles_per_run=15, llm_concurrency=2),
        config_path=config_path,
        data_dir=tmp_path / "data",
        summarizer=summarizer,
        resolver=public_resolver,
        clock=lambda: FIXED_NOW,
    )


@pytest.mark.asyncio
async def test_second_identical_run_makes_zero_llm_calls(
    tmp_path, sample_feed_bytes: bytes
) -> None:
    first = FakeSummarizer()
    first_dependencies = dependencies(tmp_path, first)
    with respx.mock:
        respx.get("https://feeds.example.com/rss").mock(
            return_value=httpx.Response(200, content=sample_feed_bytes)
        )
        await run_pipeline(first_dependencies)

    second = FakeSummarizer()
    with respx.mock:
        respx.get("https://feeds.example.com/rss").mock(
            return_value=httpx.Response(200, content=sample_feed_bytes)
        )
        await run_pipeline(dependencies(tmp_path, second))

    assert first.calls == 3
    assert second.calls == 0


@pytest.mark.asyncio
async def test_schema_failure_retries_once_then_marks_failed(
    tmp_path, sample_feed_bytes: bytes
) -> None:
    class InvalidSummarizer:
        model_name = "test-fake"

        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, _: Article, __: str) -> ArticleSummary:
            self.calls += 1
            raise OutputParserException("bad schema")

    summarizer = InvalidSummarizer()
    with respx.mock:
        respx.get("https://feeds.example.com/rss").mock(
            return_value=httpx.Response(200, content=sample_feed_bytes)
        )
        result = await run_pipeline(dependencies(tmp_path, summarizer))

    run = RunFile.model_validate_json((tmp_path / "data" / "run.json").read_text())
    assert summarizer.calls == 6
    assert result["retry_count"] == 1
    assert run.status == "partial"
    assert run.metrics.summaries_failed == 3


@pytest.mark.asyncio
async def test_output_files_match_contract(tmp_path, sample_feed_bytes: bytes) -> None:
    with respx.mock:
        respx.get("https://feeds.example.com/rss").mock(
            return_value=httpx.Response(200, content=sample_feed_bytes)
        )
        await run_pipeline(dependencies(tmp_path, FakeSummarizer()))

    digest = DigestFile.model_validate_json((tmp_path / "data" / "digest.json").read_text())
    run = RunFile.model_validate_json((tmp_path / "data" / "run.json").read_text())
    assert len(digest.articles) == 1
    assert run.metrics.summaries_ok == 3


@pytest.mark.asyncio
async def test_existing_files_stay_untouched_when_save_fails(
    tmp_path, sample_feed_bytes: bytes, monkeypatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    original = {
        "cache.json": '{"version": 1, "items": {}}',
        "digest.json": "old-digest.json",
        "run.json": "old-run.json",
    }
    for name, content in original.items():
        (data_dir / name).write_text(content, encoding="utf-8")

    def fail_write(*_) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr("app.graph.nodes.write_outputs", fail_write)
    with respx.mock:
        respx.get("https://feeds.example.com/rss").mock(
            return_value=httpx.Response(200, content=sample_feed_bytes)
        )
        with pytest.raises(OSError, match="disk unavailable"):
            await run_pipeline(dependencies(tmp_path, FakeSummarizer()))

    assert {name: (data_dir / name).read_text() for name in original} == original
