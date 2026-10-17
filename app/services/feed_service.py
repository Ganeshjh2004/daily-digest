"""Safe asynchronous fetching and parsing of repository-configured feeds."""

import asyncio
import ipaddress
import logging
import socket
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx
from pydantic import BaseModel

from app.config import Settings
from app.models.schemas import FeedDefinition, ParsedArticle

LOGGER = logging.getLogger(__name__)
USER_AGENT = "DailyDigest/0.1 (+https://github.com/)"
Resolver = Callable[[str, int | None], Awaitable[list[str]]]


class FeedFetchResult(BaseModel):
    """The parsed entries or isolated failure for a single configured feed."""

    feed: FeedDefinition
    articles: list[ParsedArticle] = []
    error: str | None = None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(value: object) -> str:
    """Convert untrusted feed HTML to compact plain text."""
    parser = _TextExtractor()
    parser.feed(str(value or ""))
    parser.close()
    return " ".join(unescape(" ".join(parser.parts)).split())


def is_http_url(value: object) -> bool:
    """Return whether a value is an absolute HTTP(S) URL suitable for storage."""
    parsed = urlsplit(str(value or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def is_https_url(value: object) -> bool:
    """Return whether a value is an absolute HTTPS URL suitable for images."""
    parsed = urlsplit(str(value or ""))
    return parsed.scheme == "https" and bool(parsed.hostname)


async def resolve_host(hostname: str, port: int | None) -> list[str]:
    """Resolve a hostname asynchronously for the SSRF safety check."""
    loop = asyncio.get_running_loop()
    addresses = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return list({address[4][0] for address in addresses})


async def assert_safe_fetch_url(url: str, resolver: Resolver = resolve_host) -> None:
    """Reject non-web URLs and addresses disallowed by the feed SSRF policy."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("feed URL must be an absolute http(s) URL")
    try:
        addresses = await resolver(parsed.hostname, parsed.port)
    except (OSError, ValueError, socket.gaierror) as error:
        raise ValueError(f"could not resolve feed host: {parsed.hostname}") from error
    if not addresses:
        raise ValueError(f"feed host resolved without addresses: {parsed.hostname}")
    for address in addresses:
        ip_address = ipaddress.ip_address(address)
        if ip_address.is_private or ip_address.is_loopback or ip_address.is_link_local:
            raise ValueError(f"blocked unsafe feed address for host: {parsed.hostname}")


async def fetch_all_feeds(
    feeds: Iterable[FeedDefinition], settings: Settings, resolver: Resolver = resolve_host
) -> list[FeedFetchResult]:
    """Fetch feeds concurrently; a failure in one result never stops the others."""
    timeout = httpx.Timeout(settings.feed_timeout_s)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        tasks = [fetch_feed(feed, settings, client, resolver) for feed in feeds]
        return list(await asyncio.gather(*tasks))


async def fetch_feed(
    feed: FeedDefinition,
    settings: Settings,
    client: httpx.AsyncClient,
    resolver: Resolver = resolve_host,
) -> FeedFetchResult:
    """Fetch one feed with retries and return a failure result instead of raising."""
    for attempt in range(3):
        try:
            content = await _download_feed(feed.url, settings, client, resolver)
            return FeedFetchResult(feed=feed, articles=parse_feed(content, feed))
        except (httpx.HTTPError, ValueError, feedparser.CharacterEncodingOverride) as error:
            if attempt == 2:
                message = f"{feed.name}: {type(error).__name__}: {error}"
                LOGGER.warning("feed fetch failed: %s", message)
                return FeedFetchResult(feed=feed, error=message)
    raise AssertionError("unreachable retry loop")


async def _download_feed(
    initial_url: str,
    settings: Settings,
    client: httpx.AsyncClient,
    resolver: Resolver,
) -> bytes:
    current_url = initial_url
    for redirect_count in range(settings.max_redirects + 1):
        await assert_safe_fetch_url(current_url, resolver)
        request = client.build_request(
            "GET",
            current_url,
            headers={"Accept-Encoding": "identity", "User-Agent": USER_AGENT},
        )
        response = await client.send(request, stream=True)
        try:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("redirect response did not include Location")
                if redirect_count == settings.max_redirects:
                    raise ValueError("feed exceeded redirect limit")
                current_url = urljoin(str(response.url), location)
                continue
            response.raise_for_status()
            if response.headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
                raise ValueError("compressed feed responses are not supported")
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > settings.max_feed_bytes:
                raise ValueError(f"feed response exceeded {settings.max_feed_bytes} byte limit")
            return await _read_limited(response, settings.max_feed_bytes)
        finally:
            await response.aclose()
    raise AssertionError("unreachable redirect loop")


async def _read_limited(response: httpx.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    received = 0
    chunk_iterator = response.aiter_raw()
    try:
        async for chunk in chunk_iterator:
            received += len(chunk)
            if received > max_bytes:
                raise ValueError(f"feed response exceeded {max_bytes} byte limit")
            chunks.append(chunk)
    finally:
        await chunk_iterator.aclose()
    return b"".join(chunks)


def parse_feed(content: bytes, feed: FeedDefinition) -> list[ParsedArticle]:
    """Parse entries into validated, plain-text article records."""
    parsed_feed = feedparser.parse(content)
    articles: list[ParsedArticle] = []
    for entry in parsed_feed.entries:
        article = _parse_entry(entry, feed)
        if article is not None:
            articles.append(article)
    return articles


def _parse_entry(entry: object, feed: FeedDefinition) -> ParsedArticle | None:
    title = strip_html(_entry_value(entry, "title"))
    url = str(_entry_value(entry, "link") or "")
    if not title or not is_http_url(url):
        return None
    description = strip_html(_entry_value(entry, "summary") or _entry_value(entry, "description"))
    return ParsedArticle(
        title=title,
        url=url,
        published_at=_published_at(entry),
        source=feed.name,
        source_type=feed.source_type,
        description=description,
        image_url=_image_url(entry),
    )


def _entry_value(entry: object, key: str) -> object:
    if hasattr(entry, "get"):
        return entry.get(key)  # type: ignore[union-attr]
    return None


def _published_at(entry: object) -> str | None:
    parsed_time = _entry_value(entry, "published_parsed") or _entry_value(entry, "updated_parsed")
    if parsed_time is not None:
        try:
            return datetime(*parsed_time[:6], tzinfo=UTC).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError):
            pass
    raw_date = _entry_value(entry, "published") or _entry_value(entry, "updated")
    if raw_date:
        try:
            timestamp = parsedate_to_datetime(str(raw_date)).astimezone(UTC).isoformat()
            return timestamp.replace("+00:00", "Z")
        except (TypeError, ValueError):
            return None
    return None


def _image_url(entry: object) -> str | None:
    for candidate in _image_candidates(entry):
        if is_https_url(candidate):
            return str(candidate)
    return None


def _image_candidates(entry: object) -> Iterable[object]:
    for field in ("media_thumbnail", "media_content", "enclosures"):
        values = _entry_value(entry, field) or []
        for value in values:
            if not hasattr(value, "get"):
                continue
            mime_type = value.get("type", "")
            if field != "media_thumbnail" and mime_type and not str(mime_type).startswith("image/"):
                continue
            yield value.get("url") or value.get("href")

