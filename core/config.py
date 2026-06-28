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

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies everywhere except local dev over http."""
        return self.app_env != "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
