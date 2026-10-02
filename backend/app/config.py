from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.paths import DEFAULT_FRONTEND_BASE_PATH, normalize_frontend_base

EXAMPLE_ACCESS_CODES = {"change-me-family-code", "family", "1234", "password"}
EXAMPLE_SECRETS = {
    "change-me-session-secret-at-least-32-chars",
    "secret",
    "changeme",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    family_access_code: str = Field(alias="FAMILY_ACCESS_CODE")
    session_secret: str = Field(alias="SESSION_SECRET")
    ai_builder_token: str = Field(default="", alias="AI_BUILDER_TOKEN")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    app_env: str = Field(default="development", alias="APP_ENV")
    ai_timeout_seconds: float = Field(default=60.0, alias="AI_TIMEOUT_SECONDS")
    ai_enrich_model: str = Field(
        default="gemini-3-flash-preview",
        alias="AI_ENRICH_MODEL",
    )
    ai_base_url: str = Field(
        default="https://space.ai-builders.com/backend/v1",
        alias="AI_BASE_URL",
    )
    frontend_base_path: str = Field(
        default=DEFAULT_FRONTEND_BASE_PATH,
        alias="FRONTEND_BASE_PATH",
    )
    family_timezone: str = Field(default="Asia/Shanghai", alias="FAMILY_TIMEZONE")
    cookie_name: str = "wordnest_session"
    max_image_bytes: int = 5 * 1024 * 1024
    max_image_side: int = 1600
    max_audio_bytes: int = 8 * 1024 * 1024
    allowed_image_mimes: frozenset[str] = frozenset(
        {"image/jpeg", "image/png", "image/webp", "image/gif"}
    )
    allowed_audio_mimes: frozenset[str] = frozenset(
        {
            "audio/aac",
            "audio/flac",
            "audio/mp4",
            "audio/mpeg",
            "audio/ogg",
            "audio/wav",
            "audio/webm",
            "audio/x-m4a",
            "audio/x-wav",
        }
    )

    @field_validator("family_access_code")
    @classmethod
    def access_code_required(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("FAMILY_ACCESS_CODE 不能为空")
        return value.strip()

    @field_validator("session_secret")
    @classmethod
    def session_secret_required(cls, value: str) -> str:
        if not value or len(value.strip()) < 16:
            raise ValueError("SESSION_SECRET 至少 16 个字符")
        return value.strip()

    @field_validator("frontend_base_path")
    @classmethod
    def normalize_base_path(cls, value: str) -> str:
        return normalize_frontend_base(value)

    @field_validator("family_timezone")
    @classmethod
    def valid_family_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("FAMILY_TIMEZONE 必须是有效的 IANA 时区") from exc
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        data_dir = self.data_dir.expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{data_dir / 'wordnest.db'}"

    def assert_safe_for_production(self) -> None:
        if not self.is_production:
            return
        if self.family_access_code in EXAMPLE_ACCESS_CODES:
            raise RuntimeError("生产环境禁止使用示例 FAMILY_ACCESS_CODE")
        if self.session_secret in EXAMPLE_SECRETS or len(self.session_secret) < 32:
            raise RuntimeError("生产环境 SESSION_SECRET 必须足够强")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    settings.assert_safe_for_production()
    return settings
