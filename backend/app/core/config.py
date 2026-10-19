"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MetalFlow ERP"
    environment: str = "development"  # development | test | production
    database_url: str = "postgresql+psycopg://localhost:5432/metalflow"

    jwt_secret_key: str = "dev-only-change-me-this-is-not-a-secret-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "strict"

    cors_origins: list[str] = ["http://localhost:5173"]
    enable_api_docs: bool | None = None  # default: on outside production

    # Failed-login throttling (see app/core/ratelimit.py)
    login_rate_window_seconds: int = 900
    login_max_failures_per_account: int = 5
    login_max_failures_per_ip: int = 50

    max_upload_mb: int = 10
    default_tax_rate: str = "0.00"
    scrap_allowance_pct: str = "5"  # extra material a job may hold for expected scrap

    # AI provider: "none" (deterministic only), "openai" (any OpenAI-compatible API,
    # e.g. OpenAI, Ollama, vLLM) or "anthropic".
    ai_provider: str = "none"
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_timeout_seconds: float = 30.0

    seed_demo_data: bool = False
    frontend_dist_dir: str | None = None  # serve built SPA from the API (single-service deploy)

    @field_validator("database_url")
    @classmethod
    def normalise_db_url(cls, v: str) -> str:
        # Render/Heroku style URLs use postgres:// or postgresql://; force the psycopg3 driver.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def api_docs_enabled(self) -> bool:
        return not self.is_production if self.enable_api_docs is None else self.enable_api_docs


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    weak_secret = settings.jwt_secret_key.startswith("dev-only") or len(settings.jwt_secret_key) < 32
    if settings.is_production and weak_secret:
        raise RuntimeError("JWT_SECRET_KEY must be set to a strong value (>=32 chars) in production")
    return settings
