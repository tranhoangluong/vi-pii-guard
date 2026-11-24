"""Runtime configuration, read from ``VPG_*`` environment variables or ``.env``."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VPG_", env_file=".env", extra="ignore")

    upstream_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible endpoint that receives redacted requests",
    )
    upstream_api_key: SecretStr | None = Field(
        default=None,
        description="Key sent upstream. If unset, the client's Authorization header is forwarded.",
    )
    upstream_timeout_seconds: float = 60.0
    ner_model: str | None = Field(default=None, description="Hugging Face id or local path")
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    session_ttl_seconds: float = Field(default=3600.0, gt=0)
    max_sessions: int = Field(default=10_000, gt=0)
