"""Tests for HTTP client settings."""

from web_crawler.http.settings import HttpSettings


class TestHttpSettings:
    def test_defaults(self):
        settings = HttpSettings()

        assert settings.timeout == 30.0
        assert settings.user_agent == "web-crawler/0.1.0"

    def test_env_overrides_timeout(self, monkeypatch):
        monkeypatch.setenv("CRAWLER_TIMEOUT", "10.5")

        settings = HttpSettings()

        assert settings.timeout == 10.5

    def test_env_overrides_user_agent(self, monkeypatch):
        monkeypatch.setenv("CRAWLER_USER_AGENT", "custom-bot/2.0")

        settings = HttpSettings()

        assert settings.user_agent == "custom-bot/2.0"
