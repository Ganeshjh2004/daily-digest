"""Deterministic keyword topic classification."""

import re

from app.models.schemas import Article


def tag_article(
    article: Article, topics: dict[str, list[str]], default_topic: str | None = None
) -> Article:
    """Return an article tagged by whole-word keyword matches and its optional feed topic."""
    searchable_text = f"{article.title}\n{article.description}".casefold()
    matched_topics = [
        topic
        for topic, keywords in topics.items()
        if any(_contains_keyword(searchable_text, keyword) for keyword in keywords)
    ]
    if default_topic and default_topic in topics and default_topic not in matched_topics:
        matched_topics.append(default_topic)
    return article.model_copy(update={"topics": matched_topics})


def tag_articles(
    articles: list[Article], topics: dict[str, list[str]], defaults: dict[str, str | None]
) -> list[Article]:
    """Tag all articles while keeping their order stable."""
    return [tag_article(article, topics, defaults.get(article.source)) for article in articles]


def _contains_keyword(text: str, keyword: str) -> bool:
    escaped_keyword = re.escape(keyword.casefold())
    return re.search(rf"(?<!\w){escaped_keyword}(?!\w)", text) is not None

