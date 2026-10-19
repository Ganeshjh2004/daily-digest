"""Command-line entry points for local pipeline operations."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from app.config import Settings, load_feed_config
from app.graph.builder import run_pipeline
from app.graph.nodes import NodeDependencies
from app.services.dedupe_service import deduplicate_articles
from app.services.feed_service import fetch_all_feeds
from app.services.llm_service import FakeSummarizer, GroqSummarizer
from app.services.topic_service import tag_articles


def build_fetch_report() -> dict[str, object]:
    """Fetch, deduplicate, and tag configured feeds for the debug CLI command."""
    settings = Settings()
    config = load_feed_config(Path("feeds.yaml"))
    results = asyncio.run(fetch_all_feeds(config.feeds, settings))
    raw_articles = [article for result in results for article in result.articles]
    unique_articles = deduplicate_articles(raw_articles)
    defaults = {feed.name: feed.default_topic for feed in config.feeds}
    articles = tag_articles(unique_articles, config.topics, defaults)
    return {
        "feed_health": [
            {"name": result.feed.name, "ok": result.error is None, "error": result.error}
            for result in results
        ],
        "articles": [
            {
                "id": article.id,
                "title": article.title,
                "url": article.url,
                "published_at": article.published_at,
                "source": article.source,
                "topics": article.topics,
                "image_url": article.image_url,
            }
            for article in articles
        ],
    }


def main() -> None:
    """Run supported Daily Digest commands."""
    parser = argparse.ArgumentParser(prog="daily-digest")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("fetch", help="Fetch, deduplicate, and topic-tag configured feeds")
    run_parser = subparsers.add_parser("run", help="Run the complete digest pipeline")
    run_parser.add_argument(
        "--fake-llm", action="store_true", help="Use the deterministic local summarizer"
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=Settings().log_level)
    if arguments.command == "fetch":
        sys.stdout.write(json.dumps(build_fetch_report(), indent=2) + "\n")
    if arguments.command == "run":
        settings = Settings()
        summarizer = FakeSummarizer() if arguments.fake_llm else GroqSummarizer(settings)
        dependencies = NodeDependencies(
            settings=settings,
            config_path=Path("feeds.yaml"),
            data_dir=Path("data"),
            summarizer=summarizer,
        )
        result = asyncio.run(run_pipeline(dependencies))
        report = {"run_id": result["run_id"], "metrics": result["metrics"]}
        sys.stdout.write(json.dumps(report) + "\n")


if __name__ == "__main__":
    main()
