"""Crawler orchestration service."""

import asyncio
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from web_crawler.crawler.parser import extract_urls
from web_crawler.http.client import FetchError, HttpClient

logger = logging.getLogger(__name__)


def is_same_domain(url: str, base_url: str) -> bool:
    """Check if url has the exact same hostname as base_url."""
    return urlparse(url).hostname == urlparse(base_url).hostname


@dataclass(frozen=True)
class CrawlerResult:
    url: str
    links: list[str] = field(default_factory=list)


class CrawlerService:
    def __init__(
        self,
        client: HttpClient,
        max_concurrency: int = 5,
        user_agent: str = "*",
    ) -> None:
        self._client = client
        self._max_concurrency = max_concurrency
        self._user_agent = user_agent

    async def _fetch_robots(self, start_url: str) -> RobotFileParser:
        parsed = urlparse(start_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        try:
            response = await self._client.fetch(robots_url)
            if response.status_code == 200:
                rp.parse(response.body.splitlines())
                return rp
        except FetchError:
            pass
        # No valid robots.txt — allow everything
        rp.parse([])
        return rp

    async def crawl(self, start_url: str) -> list[CrawlerResult]:
        robots = await self._fetch_robots(start_url)
        visited: set[str] = set()
        results: list[CrawlerResult] = []
        queue: asyncio.Queue[str] = asyncio.Queue()
        semaphore = asyncio.Semaphore(self._max_concurrency)
        in_progress = 0
        done_event = asyncio.Event()

        visited.add(start_url)
        await queue.put(start_url)

        async def worker() -> None:
            nonlocal in_progress
            while True:
                try:
                    url = queue.get_nowait()
                except asyncio.QueueEmpty:
                    if in_progress == 0:
                        return
                    done_event.clear()
                    await done_event.wait()
                    continue

                in_progress += 1
                try:
                    async with semaphore:
                        try:
                            response = await self._client.fetch(url)
                        except FetchError as exc:
                            logger.warning("Failed to fetch %s: %s", url, exc)
                            continue

                        if response.status_code != 200:
                            logger.warning(
                                "Skipping %s (HTTP %d)",
                                url,
                                response.status_code,
                            )
                            continue

                        if "text/html" not in response.content_type:
                            continue

                        links = extract_urls(response.body, url)
                        results.append(CrawlerResult(url=url, links=links))

                        for link in links:
                            if (
                                link not in visited
                                and is_same_domain(link, start_url)
                                and robots.can_fetch(self._user_agent, link)
                            ):
                                visited.add(link)
                                await queue.put(link)
                finally:
                    in_progress -= 1
                    done_event.set()

        workers = [asyncio.create_task(worker()) for _ in range(self._max_concurrency)]
        await asyncio.gather(*workers)

        return results
