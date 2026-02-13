"""HTTP client settings loaded from environment variables."""

from importlib.metadata import version
from typing import Annotated

from annotated_types import Gt
from pydantic_settings import BaseSettings, SettingsConfigDict

_VERSION = version("web-crawler")


class HttpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRAWLER_")

    timeout: Annotated[float, Gt(0)] = 30.0
    user_agent: str = f"web-crawler/{_VERSION}"
    requests_per_second: Annotated[float, Gt(0)] = 10.0
    max_retries: int = 3
    retry_backoff: Annotated[float, Gt(0)] = 0.5
