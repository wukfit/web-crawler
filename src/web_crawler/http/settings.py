"""HTTP client settings loaded from environment variables."""

from typing import Annotated

from annotated_types import Gt
from pydantic_settings import BaseSettings, SettingsConfigDict


class HttpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRAWLER_")

    timeout: Annotated[float, Gt(0)] = 30.0
    user_agent: str = "web-crawler/0.1.0"
    requests_per_second: Annotated[float, Gt(0)] = 10.0
