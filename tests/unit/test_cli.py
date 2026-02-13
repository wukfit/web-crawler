"""Tests for CLI."""

from unittest.mock import AsyncMock

from typer.testing import CliRunner

from web_crawler.cli import app
from web_crawler.crawler.service import CrawlerResult

runner = CliRunner()


class TestCli:
    def test_outputs_page_url_then_found_links(self, monkeypatch):
        results = [
            CrawlerResult(
                url="https://example.com",
                links=[
                    "https://example.com/about",
                    "https://example.com/file.pdf",
                ],
            ),
            CrawlerResult(url="https://example.com/about", links=[]),
        ]
        mock_crawl = AsyncMock(return_value=results)
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", mock_crawl)

        result = runner.invoke(app, ["https://example.com"])

        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        # First group: page URL then its links
        assert lines[0] == "https://example.com"
        assert lines[1] == "https://example.com/about"
        assert lines[2] == "https://example.com/file.pdf"
        # Second group: page URL (no links)
        assert lines[3] == "https://example.com/about"

    def test_does_not_deduplicate_across_pages(self, monkeypatch):
        results = [
            CrawlerResult(
                url="https://example.com",
                links=["https://example.com/about"],
            ),
            CrawlerResult(
                url="https://example.com/about",
                links=["https://example.com"],
            ),
        ]
        mock_crawl = AsyncMock(return_value=results)
        monkeypatch.setattr("web_crawler.cli.CrawlerService.crawl", mock_crawl)

        result = runner.invoke(app, ["https://example.com"])

        lines = result.output.strip().split("\n")
        # /about appears as both a found link and a crawled page
        assert lines.count("https://example.com/about") == 2
        # / appears as both a crawled page and a found link
        assert lines.count("https://example.com") == 2

    def test_requires_url_argument(self):
        result = runner.invoke(app, [])

        assert result.exit_code != 0
