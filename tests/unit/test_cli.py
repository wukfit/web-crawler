"""Tests for CLI."""

from unittest.mock import AsyncMock

from typer.testing import CliRunner

from web_crawler.cli import app
from web_crawler.crawler.service import CrawlerResult

runner = CliRunner()


class TestCli:
    def test_crawl_prints_urls(self, monkeypatch):
        results = [
            CrawlerResult(
                url="https://example.com",
                links=["https://example.com/about"],
            ),
            CrawlerResult(
                url="https://example.com/about", links=[]
            ),
        ]
        mock_crawl = AsyncMock(return_value=results)
        monkeypatch.setattr(
            "web_crawler.cli.CrawlerService.crawl", mock_crawl
        )

        result = runner.invoke(app, ["https://example.com"])

        assert result.exit_code == 0
        assert "https://example.com\n" in result.output
        assert "https://example.com/about\n" in result.output

    def test_requires_url_argument(self):
        result = runner.invoke(app, [])

        assert result.exit_code != 0
