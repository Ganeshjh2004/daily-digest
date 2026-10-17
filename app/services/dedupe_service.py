"""URL and title-based article deduplication."""

import hashlib
import re
from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models.schemas import Article, ParsedArticle

_TRACKING_PARAMETERS = {"ref", "fbclid"}


def normalize_url(url: str) -> str:
    """Normalize a validated article URL for stable IDs and duplicate detection."""
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    netloc = hostname
    if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
        netloc = f"{hostname}:{port}"
    path = parsed.path.rstrip("/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMETERS
        )
    )
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_title(title: str) -> str:
    """Normalize titles for punctuation- and case-insensitive matching."""
    return " ".join(re.sub(r"[^\w]+", " ", title.casefold()).split())


def article_id(normalized_url: str) -> str:
    """Return the required SHA-256 ID for a normalized URL."""
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def deduplicate_articles(items: Iterable[ParsedArticle]) -> list[Article]:
    """Keep the first article for each normalized URL or normalized title."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[Article] = []
    for item in items:
        normalized_url = normalize_url(item.url)
        normalized_title = normalize_title(item.title)
        if normalized_url in seen_urls or normalized_title in seen_titles:
            continue
        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        unique.append(Article(id=article_id(normalized_url), **item.model_dump()))
    return unique

