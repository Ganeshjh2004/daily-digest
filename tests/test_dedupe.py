from app.models.schemas import ParsedArticle
from app.services.dedupe_service import (
    article_id,
    deduplicate_articles,
    normalize_title,
    normalize_url,
)


def make_article(title: str, url: str) -> ParsedArticle:
    return ParsedArticle(
        title=title,
        url=url,
        source="Example",
        source_type="rss",
        description="Description",
    )


def test_normalize_url_removes_tracking_fragment_and_trailing_slash() -> None:
    url = "HTTPS://Example.COM/path/?b=2&utm_source=newsletter&ref=menu&a=1#section"

    assert normalize_url(url) == "https://example.com/path?a=1&b=2"


def test_deduplicate_articles_by_url_and_title_keeps_first_item() -> None:
    first = make_article("A Python Update!", "https://example.com/one?utm_campaign=x")
    url_duplicate = make_article("Different title", "https://example.com/one")
    title_duplicate = make_article("a python update", "https://other.example.com/two")

    articles = deduplicate_articles([first, url_duplicate, title_duplicate])

    assert [article.title for article in articles] == ["A Python Update!"]
    assert articles[0].id == article_id("https://example.com/one")


def test_normalize_title_ignores_punctuation_and_spacing() -> None:
    assert normalize_title("  Python:  APIs! ") == "python apis"

