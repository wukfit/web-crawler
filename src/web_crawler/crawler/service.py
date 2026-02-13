"""Crawler orchestration service."""

import asyncio
import logging
from collections.abc import AsyncIterator
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

    async def crawl(self, start_url: str) -> AsyncIterator[CrawlerResult]:
        robots = await self._fetch_robots(start_url)
        visited: set[str] = set()
        url_queue: asyncio.Queue[str] = asyncio.Queue()
        result_queue: asyncio.Queue[CrawlerResult | None] = asyncio.Queue()
        semaphore = asyncio.Semaphore(self._max_concurrency)
        in_progress = 0
        done_event = asyncio.Event()

        visited.add(start_url)
        await url_queue.put(start_url)

        async def worker() -> None:
            nonlocal in_progress
            while True:
                try:
                    url = url_queue.get_nowait()
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
                        await result_queue.put(CrawlerResult(url=url, links=links))

                        for link in links:
                            if (
                                link not in visited
                                and is_same_domain(link, start_url)
                                and robots.can_fetch(self._user_agent, link)
                            ):
                                visited.add(link)
                                await url_queue.put(link)
                finally:
                    in_progress -= 1
                    done_event.set()

        async def run_workers() -> None:
            worker_tasks = [
                asyncio.create_task(worker()) for _ in range(self._max_concurrency)
            ]
            try:
                await asyncio.gather(*worker_tasks)
            finally:
                for t in worker_tasks:
                    t.cancel()
                await result_queue.put(None)

        task = asyncio.create_task(run_workers())

        while True:
            result = await result_queue.get()
            if result is None:
                break
            yield result

        await task
