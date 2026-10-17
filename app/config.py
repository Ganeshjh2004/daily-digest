"""Configuration loading for the Daily Digest pipeline."""

from pathlib import Path

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.schemas import FeedConfig


class Settings(BaseSettings):
    """Environment-backed runtime settings with safe fetch defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: SecretStr | None = None
    groq_model: str | None = None
    feed_timeout_s: float = Field(default=10, gt=0, le=60)
    max_feed_bytes: int = Field(default=2_000_000, gt=0, le=10_000_000)
    max_redirects: int = Field(default=3, ge=0, le=10)
    log_level: str = "INFO"

    def require_llm_credentials(self) -> tuple[SecretStr, str]:
        """Return LLM settings or fail when a later phase needs them."""
        if self.groq_api_key is None or not self.groq_model:
            raise RuntimeError("GROQ_API_KEY and GROQ_MODEL are required for summarization")
        return self.groq_api_key, self.groq_model


def load_feed_config(path: Path) -> FeedConfig:
    """Load and validate the fixed, repository-controlled feed configuration."""
    with path.open(encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file)
    return FeedConfig.model_validate(raw_config)

