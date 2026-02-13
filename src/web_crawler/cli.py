"""Web Crawler CLI."""

import asyncio
import logging
import sys

import typer

from web_crawler.crawler.rate_limiter import TokenBucket
from web_crawler.crawler.service import CrawlerService
from web_crawler.http.client import HttpxClient
from web_crawler.http.settings import HttpSettings

app = typer.Typer()


@app.command()
def main(url: str = typer.Argument(..., help="URL to crawl")) -> None:
    """Crawl a website and print discovered URLs."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    asyncio.run(_crawl(url))


async def _crawl(url: str) -> None:
    settings = HttpSettings()
    async with HttpxClient(settings=settings) as client:
        rate_limiter = TokenBucket(rate=settings.requests_per_second)
        service = CrawlerService(
            client,
            user_agent=settings.user_agent,
            rate_limiter=rate_limiter,
        )
        first = True
        async for result in service.crawl(url):
            if not first:
                typer.echo()
            first = False
            typer.echo(result.url)
            for link in result.links:
                typer.echo(f"  {link}")
