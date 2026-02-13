"""HTTP client settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class HttpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRAWLER_")

    timeout: float = 30.0
    user_agent: str = "web-crawler/0.1.0"
    requests_per_second: float = 10.0
