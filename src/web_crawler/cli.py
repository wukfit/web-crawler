"""Web Crawler CLI."""

import asyncio
import logging
import sys
from urllib.parse import urlparse

import typer

from web_crawler.crawler.rate_limiter import TokenBucket
from web_crawler.crawler.service import CrawlerService
from web_crawler.http.client import HttpxClient
from web_crawler.http.settings import HttpSettings

app = typer.Typer()


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        typer.echo(
            f"Error: URL scheme must be http or https, got '{parsed.scheme}'",
            err=True,
        )
        raise typer.Exit(code=1)
    if not parsed.hostname:
        typer.echo("Error: URL must include a hostname", err=True)
        raise typer.Exit(code=1)


@app.command()
def main(
    url: str = typer.Argument(..., help="URL to crawl"),
    max_depth: int | None = typer.Option(None, help="Maximum crawl depth"),
    max_pages: int | None = typer.Option(None, help="Maximum pages to crawl"),
) -> None:
    """Crawl a website and print discovered URLs."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    _validate_url(url)
    try:
        asyncio.run(_crawl(url, max_depth=max_depth, max_pages=max_pages))
    except KeyboardInterrupt:
        typer.echo("\nCrawl interrupted.", err=True)


async def _crawl(
    url: str,
    max_depth: int | None = None,
    max_pages: int | None = None,
) -> None:
    settings = HttpSettings()
    async with HttpxClient(settings=settings) as client:
        rate_limiter = TokenBucket(rate=settings.requests_per_second)
        service = CrawlerService(
            client,
            user_agent=settings.user_agent,
            rate_limiter=rate_limiter,
            max_depth=max_depth,
            max_pages=max_pages,
        )
        first = True
        async for result in service.crawl(url):
            if not first:
                typer.echo()
            first = False
            typer.echo(result.url)
            for link in result.links:
                typer.echo(f"  {link}")
