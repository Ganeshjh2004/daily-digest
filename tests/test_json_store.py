import json
from datetime import UTC, datetime
from pathlib import Path

from app.models.schemas import CacheFile, DigestFile, RunFile
from app.storage.json_store import read_cache


def test_corrupt_cache_is_backed_up_and_rebuilt(tmp_path) -> None:
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("not json", encoding="utf-8")

    cache = read_cache(cache_path)

    assert cache == CacheFile()
    assert not cache_path.exists()
    assert len(list(tmp_path.glob("cache.json.corrupt-*"))) == 1


def test_phase_three_sample_files_match_public_contract() -> None:
    fixtures = Path(__file__).parent / "fixtures"

    digest = DigestFile.model_validate_json((fixtures / "sample-digest.json").read_text())
    run = RunFile.model_validate_json((fixtures / "sample-run.json").read_text())

    assert digest.articles[0].summaries["balanced"].status == "ok"
    assert run.status == "success"


def test_sample_fixture_time_is_valid_utc() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "sample-run.json"
    payload = json.loads(fixture_path.read_text())
    assert datetime.fromisoformat(payload["finished_at"].replace("Z", "+00:00")) == datetime(
        2026, 10, 17, 8, 0, tzinfo=UTC
    )
