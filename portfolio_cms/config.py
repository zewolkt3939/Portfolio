from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./portfolio-cms.db"
    app_secret_key: str = "local-development-secret-change-before-deploy"
    field_encryption_key: str = ""
    public_base_url: str = "http://127.0.0.1:8000"
    upload_dir: Path = ROOT / "uploads"
    secure_cookies: bool = False
    trust_proxy_headers: bool = False
    notion_api_token: str = ""
    notion_api_version: str = "2026-03-11"
    analytics_script_url: str = ""
    analytics_website_id: str = ""
    session_idle_hours: int = Field(default=8, ge=1, le=24)
    session_absolute_days: int = Field(default=7, ge=1, le=30)
    login_attempt_limit: int = Field(default=5, ge=3, le=20)
    login_window_minutes: int = Field(default=15, ge=5, le=60)

    @field_validator("public_base_url")
    @classmethod
    def trim_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def production(self) -> bool:
        return self.public_base_url.startswith("https://")

    def validate_production_secrets(self) -> None:
        if not self.production:
            return
        if len(self.app_secret_key) < 32 or "change" in self.app_secret_key:
            raise RuntimeError("APP_SECRET_KEY must be a strong random value in production")
        if not self.field_encryption_key:
            raise RuntimeError("FIELD_ENCRYPTION_KEY is required in production")
        if not self.secure_cookies:
            raise RuntimeError("SECURE_COOKIES must be true in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_secrets()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings

