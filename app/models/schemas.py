"""Validated data shapes at configuration and feed boundaries."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

SourceType = Literal["arxiv", "hn", "rss"]


class FeedDefinition(BaseModel):
    """One configured RSS or Atom feed."""

    name: str = Field(min_length=1)
    url: str
    source_type: SourceType
    default_topic: str | None = None

    @field_validator("url")
    @classmethod
    def has_http_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("feed URL must be an absolute http(s) URL")
        return value


class FeedConfig(BaseModel):
    """Contents of feeds.yaml."""

    feeds: list[FeedDefinition] = Field(min_length=1)
    topics: dict[str, list[str]] = Field(min_length=1)


class ParsedArticle(BaseModel):
    """A cleaned article parsed from one feed, before deduplication."""

    title: str = Field(min_length=1)
    url: str
    published_at: str | None = None
    source: str = Field(min_length=1)
    source_type: SourceType
    description: str = ""
    image_url: str | None = None


class Article(ParsedArticle):
    """A unique article with its stable identifier and matched topics."""

    id: str
    topics: list[str] = Field(default_factory=list)

