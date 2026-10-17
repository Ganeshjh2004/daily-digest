import httpx
import pytest
import respx

from app.models.schemas import FeedDefinition
from app.services.feed_service import (
    assert_safe_fetch_url,
    fetch_all_feeds,
    fetch_feed,
    parse_feed,
)


def feed(name: str, url: str) -> FeedDefinition:
    return FeedDefinition(name=name, url=url, source_type="rss")


def test_parse_feed_strips_html_and_drops_non_https_images(sample_feed_bytes: bytes) -> None:
    articles = parse_feed(sample_feed_bytes, feed("Example", "https://feeds.example.com/feed.xml"))

    assert articles[0].title == "Python tooling update"
    assert articles[0].description == "A Python workflow for & teams."
    assert articles[0].image_url == "https://images.example.com/thumbnail.jpg"
    assert articles[1].image_url is None


def test_parse_feed_rejects_non_http_article_links(sample_feed_bytes: bytes) -> None:
    unsafe_feed = sample_feed_bytes.replace(
        b"https://example.com/second", b"javascript:alert(1)"
    )

    articles = parse_feed(unsafe_feed, feed("Example", "https://feeds.example.com/feed.xml"))

    assert len(articles) == 1


@pytest.mark.asyncio
async def test_private_address_is_blocked_before_a_request() -> None:
    async def private_resolver(_: str, __: int | None) -> list[str]:
        return ["127.0.0.1"]

    with pytest.raises(ValueError, match="blocked unsafe"):
        await assert_safe_fetch_url("https://feeds.example.com/feed.xml", private_resolver)


@pytest.mark.asyncio
async def test_failing_feed_does_not_stop_other_feeds(
    settings, sample_feed_bytes: bytes, public_resolver
) -> None:
    good = feed("Good", "https://good.example.com/feed.xml")
    bad = feed("Bad", "https://bad.example.com/feed.xml")
    with respx.mock:
        respx.get(good.url).mock(return_value=httpx.Response(200, content=sample_feed_bytes))
        respx.get(bad.url).mock(side_effect=httpx.ConnectError("unavailable"))

        results = await fetch_all_feeds([good, bad], settings, public_resolver)

    assert results[0].error is None
    assert len(results[0].articles) == 2
    assert results[1].error is not None


@pytest.mark.asyncio
async def test_oversized_feed_is_rejected(settings, public_resolver) -> None:
    small_limit_settings = settings.model_copy(update={"max_feed_bytes": 4})
    configured_feed = feed("Large", "https://large.example.com/feed.xml")

    class OversizedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"12345"

        async def aclose(self) -> None:
            return None

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Length": "5"}, stream=OversizedStream())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await fetch_feed(configured_feed, small_limit_settings, client, public_resolver)

    assert result.articles == []
    assert result.error is not None
    assert "exceeded" in result.error


@pytest.mark.asyncio
async def test_redirect_target_is_checked_for_ssrf(settings, public_resolver) -> None:
    configured_feed = feed("Redirect", "https://redirect.example.com/feed.xml")

    async def redirect_resolver(host: str, port: int | None) -> list[str]:
        if host == "private.example.com":
            return ["192.168.1.20"]
        return await public_resolver(host, port)

    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get(configured_feed.url).mock(
                return_value=httpx.Response(302, headers={"Location": "https://private.example.com/feed"})
            )
            result = await fetch_feed(configured_feed, settings, client, redirect_resolver)

    assert result.error is not None
    assert "blocked unsafe" in result.error
