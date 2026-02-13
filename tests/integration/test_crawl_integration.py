"""Integration tests: HttpxClient → CrawlerService → parser pipeline."""

import httpx

from web_crawler.crawler.service import CrawlerService
from web_crawler.http.client import HttpxClient


def make_site(pages: dict[str, tuple[str, str]]) -> httpx.MockTransport:
    """Build a MockTransport from {url: (content_type, body)} mapping."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in pages:
            content_type, body = pages[url]
            return httpx.Response(
                200,
                text=body,
                headers={"content-type": content_type},
                request=request,
            )
        return httpx.Response(404, text="Not Found", request=request)

    return httpx.MockTransport(handler)


class TestCrawlIntegration:
    async def test_multi_page_site(self):
        transport = make_site(
            {
                "https://site.test/robots.txt": (
                    "text/plain",
                    "",
                ),
                "https://site.test": (
                    "text/html",
                    '<a href="/about">About</a>'
                    '<a href="/contact">Contact</a>'
                    '<img src="/logo.png">',
                ),
                "https://site.test/about": (
                    "text/html",
                    '<a href="/">Home</a>',
                ),
                "https://site.test/contact": (
                    "text/html",
                    "<p>Email us</p>",
                ),
                "https://site.test/logo.png": (
                    "image/png",
                    "fake-png-bytes",
                ),
            }
        )
        async with HttpxClient(transport=transport) as client:
            service = CrawlerService(client)
            results = [r async for r in service.crawl("https://site.test")]

        urls = {r.url for r in results}
        # All HTML pages crawled
        assert "https://site.test" in urls
        assert "https://site.test/about" in urls
        assert "https://site.test/contact" in urls
        # Non-HTML not crawled as a page
        assert "https://site.test/logo.png" not in urls

    async def test_link_discovery_includes_resources(self):
        transport = make_site(
            {
                "https://site.test/robots.txt": (
                    "text/plain",
                    "",
                ),
                "https://site.test": (
                    "text/html",
                    '<img src="/photo.jpg">'
                    '<script src="/app.js"></script>'
                    '<link href="/style.css">',
                ),
            }
        )
        async with HttpxClient(transport=transport) as client:
            service = CrawlerService(client)
            results = [r async for r in service.crawl("https://site.test")]

        assert len(results) == 1
        links = results[0].links
        assert "https://site.test/photo.jpg" in links
        assert "https://site.test/app.js" in links
        assert "https://site.test/style.css" in links

    async def test_deep_chain(self):
        # 10-page linear chain: /0 → /1 → ... → /9
        pages: dict[str, tuple[str, str]] = {
            "https://site.test/robots.txt": ("text/plain", ""),
        }
        for i in range(10):
            url = f"https://site.test/{i}"
            body = f'<a href="/{i + 1}">Next</a>' if i < 9 else "<p>End</p>"
            pages[url] = ("text/html", body)

        transport = make_site(pages)
        async with HttpxClient(transport=transport) as client:
            service = CrawlerService(client)
            results = [r async for r in service.crawl("https://site.test/0")]

        assert len(results) == 10
        urls = {r.url for r in results}
        for i in range(10):
            assert f"https://site.test/{i}" in urls
