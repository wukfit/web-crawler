"""Web Crawler CLI."""

import asyncio

import typer

from web_crawler.crawler.service import CrawlerService
from web_crawler.http.client import HttpxClient

app = typer.Typer()


@app.command()
def main(url: str = typer.Argument(..., help="URL to crawl")) -> None:
    """Crawl a website and print discovered URLs."""
    asyncio.run(_crawl(url))


async def _crawl(url: str) -> None:
    async with HttpxClient() as client:
        service = CrawlerService(client)
        results = await service.crawl(url)

    for result in results:
        typer.echo(result.url)
