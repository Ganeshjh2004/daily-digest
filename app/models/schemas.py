"""Validated data shapes at configuration and feed boundaries."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

SourceType = Literal["arxiv", "hn", "rss"]
Tone = Literal["balanced", "technical", "beginner_friendly"]
SummaryStatus = Literal["ok", "failed", "insufficient_content"]
TONES: tuple[Tone, ...] = ("balanced", "technical", "beginner_friendly")


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


class ArticleSummary(BaseModel):
    """Structured LLM output required for a successful article summary."""

    bullets: list[str] = Field(min_length=3, max_length=3)

    @field_validator("bullets")
    @classmethod
    def validate_bullets(cls, bullets: list[str]) -> list[str]:
        if any(not bullet.strip() or len(bullet.split()) > 25 for bullet in bullets):
            raise ValueError("each bullet must contain 1-25 words")
        return bullets


class Summary(BaseModel):
    """The status and content for one article and tone pair."""

    article_id: str
    tone: Tone
    bullets: list[str] = Field(default_factory=list)
    status: SummaryStatus
    tokens: int = Field(default=0, ge=0)


class CachedSummary(BaseModel):
    """A public cached summary, including the model label used to produce it."""

    status: SummaryStatus
    bullets: list[str] = Field(default_factory=list)
    model: str

    @model_validator(mode="after")
    def validate_successful_bullets(self) -> "CachedSummary":
        if self.status == "ok":
            ArticleSummary(bullets=self.bullets)
        return self


class DigestSummary(BaseModel):
    """Public summary shape intentionally excluding cache-only model metadata."""

    status: SummaryStatus
    bullets: list[str] = Field(default_factory=list)


class CachedArticle(BaseModel):
    """Article metadata retained with summaries in the persistent cache."""

    title: str
    url: str
    source: str
    source_type: SourceType
    published_at: str | None = None
    image_url: str | None = None
    topics: list[str] = Field(default_factory=list)
    summaries: dict[Tone, CachedSummary] = Field(default_factory=dict)
    last_seen: str


class CacheFile(BaseModel):
    """On-disk cache format."""

    version: int = 1
    items: dict[str, CachedArticle] = Field(default_factory=dict)


class DigestArticle(BaseModel):
    """Public article representation consumed by the static site."""

    id: str
    title: str
    url: str
    source: str
    source_type: SourceType
    published_at: str | None = None
    topics: list[str] = Field(default_factory=list)
    image_url: str | None = None
    summaries: dict[Tone, DigestSummary] = Field(default_factory=dict)


class DigestFile(BaseModel):
    """Public digest file consumed by the future static UI."""

    generated_at: str
    topics: list[str] = Field(default_factory=list)
    topic_counts: dict[str, int] = Field(default_factory=dict)
    articles: list[DigestArticle] = Field(default_factory=list)


class RunMetrics(BaseModel):
    """Metrics persisted for one pipeline run."""

    feeds_total: int = 0
    feeds_ok: int = 0
    items_parsed: int = 0
    items_unique: int = 0
    summaries_ok: int = 0
    summaries_failed: int = 0
    tokens_total: int = 0
    duration_s: float = 0


class RunFile(BaseModel):
    """Public run metadata consumed by the future static UI."""

    run_id: str
    status: Literal["success", "partial", "failed"]
    started_at: str
    finished_at: str
    model: str
    duration_s: float
    metrics: RunMetrics
    errors: list[str] = Field(default_factory=list)

