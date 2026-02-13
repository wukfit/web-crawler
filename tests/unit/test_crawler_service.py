"""Tests for crawler service."""

import asyncio
import logging

from web_crawler.crawler.service import CrawlerService, is_same_domain
from web_crawler.http.client import FetchError, HttpResponse


class FakeHttpClient:
    """In-memory HTTP client for testing."""

    def __init__(self, responses: dict[str, HttpResponse] | None = None) -> None:
        self._responses = responses or {}

    async def fetch(self, url: str) -> HttpResponse:
        if url not in self._responses:
            raise FetchError(f"no response for {url}")
        return self._responses[url]

    async def close(self) -> None:
        pass


def html_response(url: str, body: str, status: int = 200) -> HttpResponse:
    return HttpResponse(
        url=url,
        status_code=status,
        body=body,
        content_type="text/html; charset=utf-8",
    )


class TestCrawlerService:
    async def test_crawls_start_url(self):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com", "<html><body>Hello</body></html>"
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        assert len(results) == 1
        assert results[0].url == "https://example.com"
        assert results[0].links == []

    async def test_follows_discovered_links(self):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/about">About</a>',
                ),
                "https://example.com/about": html_response(
                    "https://example.com/about",
                    "<html><body>About page</body></html>",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert urls == {
            "https://example.com",
            "https://example.com/about",
        }

    async def test_does_not_revisit_pages(self):
        # A → B → A cycle
        fetch_count: dict[str, int] = {}

        class CountingClient(FakeHttpClient):
            async def fetch(self, url: str) -> HttpResponse:
                fetch_count[url] = fetch_count.get(url, 0) + 1
                return await super().fetch(url)

        client = CountingClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/b">B</a>',
                ),
                "https://example.com/b": html_response(
                    "https://example.com/b",
                    '<a href="https://example.com">A</a>',
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        assert len(results) == 2
        assert all(c == 1 for c in fetch_count.values())

    async def test_skips_non_html_responses(self):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/file.pdf">PDF</a>',
                ),
                "https://example.com/file.pdf": HttpResponse(
                    url="https://example.com/file.pdf",
                    status_code=200,
                    body="%PDF-1.4",
                    content_type="application/pdf",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert "https://example.com/file.pdf" not in urls

    async def test_skips_non_200_responses(self):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/gone">Gone</a>',
                ),
                "https://example.com/gone": html_response(
                    "https://example.com/gone",
                    "<html>Not Found</html>",
                    status=404,
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert "https://example.com/gone" not in urls

    async def test_continues_on_fetch_error(self):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/a">A</a>'
                    '<a href="https://example.com/b">B</a>',
                ),
                # /a is missing → FakeHttpClient raises FetchError
                "https://example.com/b": html_response(
                    "https://example.com/b",
                    "<html>B</html>",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert "https://example.com" in urls
        assert "https://example.com/b" in urls

    async def test_respects_max_concurrency(self):
        peak_concurrent = 0
        current_concurrent = 0

        class SlowClient(FakeHttpClient):
            async def fetch(self, url: str) -> HttpResponse:
                nonlocal peak_concurrent, current_concurrent
                current_concurrent += 1
                peak_concurrent = max(peak_concurrent, current_concurrent)
                try:
                    await asyncio.sleep(0.01)
                    return await super().fetch(url)
                finally:
                    current_concurrent -= 1

        # Start page links to 4 leaf pages
        links = "".join(f'<a href="https://example.com/{i}">{i}</a>' for i in range(4))
        responses: dict[str, HttpResponse] = {
            "https://example.com": html_response("https://example.com", links),
        }
        for i in range(4):
            url = f"https://example.com/{i}"
            responses[url] = html_response(url, "<html>leaf</html>")

        client = SlowClient(responses)
        service = CrawlerService(client, max_concurrency=2)

        await service.crawl("https://example.com")

        assert peak_concurrent <= 2

    async def test_stores_all_links_including_external(self):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/about">About</a>'
                    '<a href="https://other.com/page">External</a>',
                ),
                "https://example.com/about": html_response(
                    "https://example.com/about",
                    "<html>About</html>",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        start_result = next(r for r in results if r.url == "https://example.com")
        assert "https://example.com/about" in start_result.links
        assert "https://other.com/page" in start_result.links

    async def test_does_not_crawl_external_links(self):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://other.com/page">External</a>',
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert urls == {"https://example.com"}

    async def test_logs_fetch_error(self, caplog):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/broken">Broken</a>',
                ),
                # /broken missing → FetchError
            }
        )
        service = CrawlerService(client)

        with caplog.at_level(logging.WARNING):
            await service.crawl("https://example.com")

        assert any("https://example.com/broken" in r.message for r in caplog.records)

    async def test_logs_non_200_response(self, caplog):
        client = FakeHttpClient(
            {
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/gone">Gone</a>',
                ),
                "https://example.com/gone": html_response(
                    "https://example.com/gone",
                    "<html>Not Found</html>",
                    status=404,
                ),
            }
        )
        service = CrawlerService(client)

        with caplog.at_level(logging.WARNING):
            await service.crawl("https://example.com")

        assert any(
            "404" in r.message and "https://example.com/gone" in r.message
            for r in caplog.records
        )


class TestIsSameDomain:
    def test_same_domain(self):
        assert is_same_domain("https://example.com/about", "https://example.com")

    def test_different_domain(self):
        assert not is_same_domain("https://other.com", "https://example.com")

    def test_subdomain_is_different(self):
        assert not is_same_domain("https://blog.example.com", "https://example.com")


class TestRobotsTxt:
    async def test_respects_robots_txt_disallow(self):
        robots_txt = "User-agent: *\nDisallow: /secret\n"
        client = FakeHttpClient(
            {
                "https://example.com/robots.txt": HttpResponse(
                    url="https://example.com/robots.txt",
                    status_code=200,
                    body=robots_txt,
                    content_type="text/plain",
                ),
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/public">P</a>'
                    '<a href="https://example.com/secret">S</a>',
                ),
                "https://example.com/public": html_response(
                    "https://example.com/public",
                    "<html>Public</html>",
                ),
                "https://example.com/secret": html_response(
                    "https://example.com/secret",
                    "<html>Secret</html>",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert "https://example.com/public" in urls
        assert "https://example.com/secret" not in urls

    async def test_crawls_when_robots_txt_missing(self):
        client = FakeHttpClient(
            {
                "https://example.com/robots.txt": HttpResponse(
                    url="https://example.com/robots.txt",
                    status_code=404,
                    body="Not Found",
                    content_type="text/plain",
                ),
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/page">Page</a>',
                ),
                "https://example.com/page": html_response(
                    "https://example.com/page",
                    "<html>Page</html>",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert "https://example.com/page" in urls

    async def test_crawls_when_robots_txt_fetch_fails(self):
        client = FakeHttpClient(
            {
                # No robots.txt → FetchError
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/page">Page</a>',
                ),
                "https://example.com/page": html_response(
                    "https://example.com/page",
                    "<html>Page</html>",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert "https://example.com/page" in urls

    async def test_respects_agent_specific_robots_rules(self):
        robots_txt = (
            "User-agent: my-bot\nDisallow: /blocked\n\nUser-agent: *\nAllow: /\n"
        )
        client = FakeHttpClient(
            {
                "https://example.com/robots.txt": HttpResponse(
                    url="https://example.com/robots.txt",
                    status_code=200,
                    body=robots_txt,
                    content_type="text/plain",
                ),
                "https://example.com": html_response(
                    "https://example.com",
                    '<a href="https://example.com/blocked">B</a>',
                ),
                "https://example.com/blocked": html_response(
                    "https://example.com/blocked",
                    "<html>Blocked</html>",
                ),
            }
        )
        service = CrawlerService(client, user_agent="my-bot")

        results = await service.crawl("https://example.com")

        urls = {r.url for r in results}
        assert "https://example.com/blocked" not in urls

    async def test_fetches_robots_txt_with_port(self):
        client = FakeHttpClient(
            {
                "https://example.com:8080/robots.txt": HttpResponse(
                    url="https://example.com:8080/robots.txt",
                    status_code=200,
                    body="User-agent: *\nDisallow: /secret\n",
                    content_type="text/plain",
                ),
                "https://example.com:8080": html_response(
                    "https://example.com:8080",
                    '<a href="https://example.com:8080/public">P</a>'
                    '<a href="https://example.com:8080/secret">S</a>',
                ),
                "https://example.com:8080/public": html_response(
                    "https://example.com:8080/public",
                    "<html>Public</html>",
                ),
                "https://example.com:8080/secret": html_response(
                    "https://example.com:8080/secret",
                    "<html>Secret</html>",
                ),
            }
        )
        service = CrawlerService(client)

        results = await service.crawl("https://example.com:8080")

        urls = {r.url for r in results}
        assert "https://example.com:8080/public" in urls
        assert "https://example.com:8080/secret" not in urls
