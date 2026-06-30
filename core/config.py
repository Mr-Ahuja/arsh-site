"""Single typed Settings object, imported everywhere (never read env directly)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    base_url: str = "http://127.0.0.1:8000"
    db_path: str = "./data/trade.db"
    app_secret: str = "change-me-long-random"
    kill_token: str = "change-me-random"
    app_username: str = "mrahuja"
    app_password_hash: str = ""
    kite_api_key: str = ""
    kite_api_secret: str = ""
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # ── Data layer (Task 03) ──────────────────────────────────────────────────
    tick_archive_batch_size: int = 100        # flush tick buffer every N ticks
    tick_archive_flush_interval: float = 10.0 # … or every N seconds
    rolling_buffer_candles: int = 500         # in-memory candle lookback window
    rolling_buffer_ticks: int = 1000          # in-memory tick lookback window

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies everywhere except local dev over http."""
        return self.app_env != "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
