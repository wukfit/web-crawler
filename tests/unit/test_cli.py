"""Tests for CLI."""

from unittest.mock import AsyncMock

from typer.testing import CliRunner

from web_crawler.cli import app
from web_crawler.crawler.service import CrawlerResult

runner = CliRunner()


class TestCli:
    def test_crawl_prints_per_page_output(self, monkeypatch):
        results = [
            CrawlerResult(
                url="https://example.com",
                links=[
                    "https://example.com/about",
                    "https://example.com/logo.png",
                ],
            ),
            CrawlerResult(
                url="https://example.com/about",
                links=["https://example.com"],
            ),
        ]
        mock_crawl = AsyncMock(return_value=results)
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", mock_crawl)

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
