"""Tests for CLI."""

from collections.abc import AsyncIterator

from typer.testing import CliRunner

from web_crawler.cli import app
from web_crawler.crawler.service import CrawlerResult, CrawlerService

runner = CliRunner()


async def fake_crawl(self: object, url: str) -> AsyncIterator[CrawlerResult]:
    yield CrawlerResult(
        url="https://example.com",
        links=[
            "https://example.com/about",
            "https://example.com/logo.png",
        ],
    )
    yield CrawlerResult(
        url="https://example.com/about",
        links=["https://example.com"],
    )


class TestCli:
    def test_crawl_prints_per_page_output(self, monkeypatch):
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", fake_crawl)

        result = runner.invoke(app, ["https://example.com"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        # First page
        assert lines[0] == "https://example.com"
        assert lines[1] == "  https://example.com/about"
        assert lines[2] == "  https://example.com/logo.png"
        # Second page
        assert lines[3] == ""
        assert lines[4] == "https://example.com/about"
        assert lines[5] == "  https://example.com"

    def test_requires_url_argument(self):
        result = runner.invoke(app, [])

        assert result.exit_code != 0

    def test_rejects_non_url_string(self, monkeypatch):
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", fake_crawl)

        result = runner.invoke(app, ["not-a-url"])

        assert result.exit_code == 1
        assert "scheme" in result.output.lower() or "http" in result.output.lower()

    def test_rejects_ftp_scheme(self, monkeypatch):
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", fake_crawl)

        result = runner.invoke(app, ["ftp://example.com/file"])

        assert result.exit_code == 1

    def test_rejects_missing_hostname(self, monkeypatch):
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", fake_crawl)

        result = runner.invoke(app, ["https://"])

        assert result.exit_code == 1

    def test_passes_max_depth_to_service(self, monkeypatch):
        captured: dict[str, object] = {}
        original_init = CrawlerService.__init__

        def capture_init(self, *args, **kwargs):
            captured.update(kwargs)
            original_init(self, *args, **kwargs)

        monkeypatch.setattr("web_crawler.cli.CrawlerService.__init__", capture_init)
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", fake_crawl)

        result = runner.invoke(app, ["https://example.com", "--max-depth", "3"])

        assert result.exit_code == 0
        assert captured["max_depth"] == 3

    def test_keyboard_interrupt_exits_cleanly(self, monkeypatch):
        async def interrupt_crawl(self, url):
            raise KeyboardInterrupt
            yield  # makes this an async generator

        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", interrupt_crawl)

        result = runner.invoke(app, ["https://example.com"])

        assert result.exit_code == 0
        assert "interrupted" in result.output.lower()

    def test_passes_max_pages_to_service(self, monkeypatch):
        captured: dict[str, object] = {}
        original_init = CrawlerService.__init__

        def capture_init(self, *args, **kwargs):
            captured.update(kwargs)
            original_init(self, *args, **kwargs)

        monkeypatch.setattr("web_crawler.cli.CrawlerService.__init__", capture_init)
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", fake_crawl)

        result = runner.invoke(app, ["https://example.com", "--max-pages", "10"])

        assert result.exit_code == 0
        assert captured["max_pages"] == 10
