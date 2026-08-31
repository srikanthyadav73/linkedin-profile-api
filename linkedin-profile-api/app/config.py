"""
Application configuration.

All configuration is loaded from environment variables so that no secrets
ever live in source code. Locally these come from a `.env` file (which is
git-ignored); in production they come from the hosting provider's
environment variable settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed application settings.

    Pydantic reads matching environment variables (case-insensitive) and
    validates their types automatically. If a required variable is missing,
    the app will fail to start with a clear error instead of failing later
    with a confusing bug.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # On Render (and any production host) there is no .env file —
        # variables come from the host environment directly.
        # env_file missing is fine; real env vars always take precedence.
    )

    # General app settings
    app_name: str = "LinkedIn Profile API"
    environment: str = "development"  # "development" | "production"
    log_level: str = "INFO"

    # Captapi key — used by the data-access layer to fetch LinkedIn profile data.
    # Get a free key (258 credits, no credit card) at captapi.com/dashboard.
    # Required for real data; if absent, the service raises a clear error on request.
    captapi_api_key: str | None = None

    # Optional LinkedIn session cookies for reverse-engineered Voyager API access.
    # li_at: Session auth token (starts with AQED...)
    # JSESSIONID: CSRF security token (starts with ajax:...)
    linkedin_li_at_cookie: str | None = None
    linkedin_jsessionid_cookie: str | None = None


def get_settings() -> Settings:
    """Return fresh Settings instance loaded from environment / .env."""
    return Settings()



