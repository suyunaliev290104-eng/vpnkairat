from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    bot_username: str = ""
    admin_ids: list[int] = []
    database_url: str = "sqlite+aiosqlite:///./vpn.db"
    public_url: str = "http://localhost:8000"
    webapp_url: str = "http://localhost:8000"
    trial_days: int = 3
    referral_bonus_days: int = 7
    device_limit: int = 3
    bypass_daily_gb: int = 5
    split_routing: bool = True  # Happ: Russian sites direct, the rest via VPN
    # Where to send users who lack Telegram Stars (e.g. your referral link in a Stars shop bot)
    stars_shop_url: str = "https://t.me/QuickStars_bot?start=628539345"
    support_username: str = ""
    brand_name: str = "VPN"
    webapp_dist: str = ""  # built mini app dir; default: ../webapp/dist next to backend/

    cryptobot_token: str = ""
    cryptobot_testnet: bool = False

    lavatop_api_key: str = ""
    lavatop_webhook_secret: str = ""
    lavatop_offers: dict[str, str] = {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
