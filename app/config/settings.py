"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Strongly typed application settings.

    All values are read from environment variables (or a `.env` file
    in local development). Defaults here mirror `.env.example` so the
    app can boot even if a variable is missing in a dev environment.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str

    # Telegram proxy
    telegram_proxy: str | None = None

    # PostgreSQL
    postgres_user: str = "spybot"
    postgres_password: str = "spybot"
    postgres_db: str = "spybot"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # Game defaults (used to seed a new game's settings panel)
    min_players: int = 3
    max_players: int = 10
    min_spies: int = 1
    max_spies: int = 2
    spy_threshold_players: int = 7
    min_round_minutes: int = 3
    max_round_minutes: int = 10
    lobby_timeout_seconds: int = 300

    # Safety-net TTL applied to a game's Redis keys so a crashed bot
    # doesn't leave orphaned state forever. This is intentionally much
    # longer than `lobby_timeout_seconds` (which is a business rule
    # enforced by an application-level timer, not by Redis expiry) so it
    # never cuts off a game that's still legitimately in progress.
    redis_game_ttl_seconds: int = 3600

    # Logging
    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        """Async SQLAlchemy DSN for the asyncpg driver."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_dsn(self) -> str:
        """Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton `Settings` instance."""
    return Settings()
