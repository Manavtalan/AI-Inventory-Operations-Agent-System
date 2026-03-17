"""
Centralised application settings using Pydantic v2 BaseSettings.

All configuration is read from environment variables (or .env file in development).
Required fields have no defaults — missing vars raise a ValidationError at startup
with a clear, per-field error message before any request is served.

Usage:
    from app.core.config import settings

    print(settings.database_url)
    print(settings.redis_url)
"""

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore unrecognised vars in .env
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # ------------------------------------------------------------------
    # Database — required, no defaults
    # ------------------------------------------------------------------
    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # ------------------------------------------------------------------
    # Redis — host required, rest have sensible defaults
    # ------------------------------------------------------------------
    redis_host: str
    redis_port: int = 6379
    redis_db: int = 0

    # ------------------------------------------------------------------
    # Celery — optional; derived from redis_url when empty
    # ------------------------------------------------------------------
    celery_broker_url: str = ""
    celery_result_backend: str = ""
    celery_task_time_limit: int = 300       # seconds
    celery_task_max_retries: int = 3
    celery_result_expires: int = 86400      # 24 hours in seconds

    # ------------------------------------------------------------------
    # Shopify
    # ------------------------------------------------------------------
    shopify_api_key: str = ""
    shopify_api_secret: str = ""
    shopify_store_domain: str = ""
    shopify_webhook_secret: str = ""
    shopify_api_version: str = "2024-01"

    # ------------------------------------------------------------------
    # WhatsApp Business API
    # ------------------------------------------------------------------
    whatsapp_api_url: str = ""
    whatsapp_api_key: str = ""
    whatsapp_phone_number: str = ""

    # ------------------------------------------------------------------
    # Google Sheets
    # ------------------------------------------------------------------
    google_sheets_credentials_path: str = ""
    google_sheets_spreadsheet_id: str = ""

    # ------------------------------------------------------------------
    # Slack
    # ------------------------------------------------------------------
    slack_webhook_url: str = ""
    slack_channel: str = ""

    # ------------------------------------------------------------------
    # SendGrid
    # ------------------------------------------------------------------
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    sendgrid_from_name: str = ""

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    openai_api_key: str = ""
    openai_model: str = "claude-opus-4-6"

    # ------------------------------------------------------------------
    # Sentry
    # ------------------------------------------------------------------
    sentry_dsn: str = ""

    # ------------------------------------------------------------------
    # Computed / derived properties
    # ------------------------------------------------------------------

    @computed_field
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection URL (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Sync psycopg2 URL — used by Alembic migrations."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        """Redis connection URL used as Celery broker/backend fallback."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        """True when running in the production environment."""
        return self.app_env == "production"

    @property
    def json_logs(self) -> bool:
        """True when structured JSON logs should be emitted (non-development)."""
        return self.app_env != "development"


# Module-level singleton — import this everywhere instead of constructing Settings()
settings = Settings()
