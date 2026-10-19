from pathlib import Path

import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        feed_timeout_s=1,
        max_feed_bytes=2_000_000,
        max_redirects=3,
    )


@pytest.fixture
def sample_feed_bytes() -> bytes:
    return (Path(__file__).parent / "fixtures" / "sample_feed.xml").read_bytes()


@pytest.fixture
def public_resolver():
    async def resolve(_: str, __: int | None) -> list[str]:
        return ["93.184.216.34"]

    return resolve

