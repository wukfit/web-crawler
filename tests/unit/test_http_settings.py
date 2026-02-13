"""Tests for HTTP client settings."""

import pytest
from pydantic import ValidationError

from web_crawler.http.settings import HttpSettings


class TestHttpSettings:
    def test_defaults(self):
        settings = HttpSettings()

        assert settings.timeout == 30.0
        assert settings.user_agent.startswith("web-crawler/")
        assert settings.requests_per_second == 10.0

    def test_env_overrides_timeout(self, monkeypatch):
        monkeypatch.setenv("CRAWLER_TIMEOUT", "10.5")

        settings = HttpSettings()

        assert settings.timeout == 10.5

    def test_env_overrides_user_agent(self, monkeypatch):
        monkeypatch.setenv("CRAWLER_USER_AGENT", "custom-bot/2.0")

        settings = HttpSettings()

        assert settings.user_agent == "custom-bot/2.0"

    def test_env_overrides_requests_per_second(self, monkeypatch):
        monkeypatch.setenv("CRAWLER_REQUESTS_PER_SECOND", "5.0")

        settings = HttpSettings()

        assert settings.requests_per_second == 5.0

    def test_rejects_negative_timeout(self):
        with pytest.raises(ValidationError):
            HttpSettings(timeout=-1.0)

    def test_rejects_zero_timeout(self):
        with pytest.raises(ValidationError):
            HttpSettings(timeout=0.0)

    def test_rejects_negative_requests_per_second(self):
        with pytest.raises(ValidationError):
            HttpSettings(requests_per_second=-1.0)

    def test_rejects_zero_requests_per_second(self):
        with pytest.raises(ValidationError):
            HttpSettings(requests_per_second=0.0)
