"""Typed state shared by the Daily Digest LangGraph pipeline."""

import operator
from typing import Annotated, TypedDict

from app.models.schemas import CacheFile


class PipelineState(TypedDict):
    """State values passed between thin pipeline nodes."""

    run_id: str
    started_at: str
    feeds: list[dict]
    topic_keywords: dict[str, list[str]]
    default_topics: dict[str, str | None]
    raw_items: list[dict]
    articles: list[dict]
    selected: list[dict]
    summaries: list[dict]
    cache: CacheFile
    retry_count: int
    errors: Annotated[list[str], operator.add]
    metrics: dict[str, int | float]
