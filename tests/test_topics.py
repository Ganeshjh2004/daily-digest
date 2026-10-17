from app.models.schemas import Article
from app.services.topic_service import tag_article

TOPICS = {
    "Python": ["python", "fastapi"],
    "Backend": ["api", "database"],
    "Cloud": ["cloud", "aws"],
}


def test_tag_article_matches_all_whole_word_keywords() -> None:
    article = Article(
        id="id",
        title="Python API for cloud teams",
        url="https://example.com/article",
        source="Example",
        source_type="rss",
        description="A database migration guide.",
    )

    tagged = tag_article(article, TOPICS)

    assert tagged.topics == ["Python", "Backend", "Cloud"]


def test_tag_article_does_not_match_partial_words() -> None:
    article = Article(
        id="id",
        title="CPython internals",
        url="https://example.com/article",
        source="Example",
        source_type="rss",
        description="",
    )

    assert tag_article(article, TOPICS).topics == []

