"""
Application configuration — loads settings from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    ANTHROPIC_API_KEY: str = ""

    # Claude model configuration
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 1024


# Module-level singleton — reloaded when uvicorn restarts
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return application settings, loading from .env on first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
