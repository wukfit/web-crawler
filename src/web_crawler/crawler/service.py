"""Crawler orchestration service."""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from web_crawler.crawler.parser import extract_urls, normalise_url
from web_crawler.http.client import FetchError, HttpClient, HttpResponse

logger = logging.getLogger(__name__)


class RateLimiter(Protocol):
    async def acquire(self) -> None: ...
    def set_rate(self, rate: float) -> None: ...


def is_same_domain(url: str, base_url: str) -> bool:
    """Check if url has the exact same host and port as base_url."""
    return urlparse(url).netloc == urlparse(base_url).netloc


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
        rate_limiter: RateLimiter | None = None,
        max_depth: int | None = None,
        max_pages: int | None = None,
    ) -> None:
        self._client = client
        self._max_concurrency = max_concurrency
        self._user_agent = user_agent
        self._rate_limiter = rate_limiter
        self._max_depth = max_depth
        self._max_pages = max_pages

    async def _fetch(self, url: str) -> HttpResponse:
        if self._rate_limiter is not None:
            await self._rate_limiter.acquire()
        return await self._client.fetch(url)

    async def _fetch_robots(self, start_url: str) -> RobotFileParser:
        parsed = urlparse(start_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        try:
            response = await self._fetch(robots_url)
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

        if self._rate_limiter is not None:
            crawl_delay = robots.crawl_delay(self._user_agent)
            if crawl_delay is not None and float(crawl_delay) > 0:
                self._rate_limiter.set_rate(1.0 / float(crawl_delay))

        visited: set[str] = set()
        url_queue: asyncio.Queue[tuple[str, str, int]] = asyncio.Queue()
        result_queue: asyncio.Queue[CrawlerResult | None] = asyncio.Queue()
        semaphore = asyncio.Semaphore(self._max_concurrency)
        in_progress = 0
        pages_crawled = 0
        done_event = asyncio.Event()

        start_url = normalise_url(start_url)
        visited.add(start_url)
        await url_queue.put((start_url, "", 0))

        async def worker() -> None:
            nonlocal in_progress, pages_crawled
            while True:
                try:
                    url, parent_url, depth = url_queue.get_nowait()
                except asyncio.QueueEmpty:
                    if in_progress == 0:
                        return
                    done_event.clear()
                    await done_event.wait()
                    continue

                in_progress += 1
                try:
                    if self._max_pages is not None and pages_crawled >= self._max_pages:
                        continue

                    async with semaphore:
                        try:
                            response = await self._fetch(url)
                        except FetchError as exc:
                            logger.warning(
                                "Failed to fetch %s (from %s): %s",
                                url,
                                parent_url,
                                exc,
                            )
                            continue

                        if response.status_code != 200:
                            logger.warning(
                                "Skipping %s (from %s, HTTP %d)",
                                url,
                                parent_url,
                                response.status_code,
                            )
                            continue

                        if "text/html" not in response.content_type:
                            continue

                        final_url = normalise_url(response.url)
                        visited.add(final_url)

                        if not is_same_domain(final_url, start_url):
                            continue

                        links = extract_urls(response.body, final_url)
                        pages_crawled += 1
                        await result_queue.put(
                            CrawlerResult(url=final_url, links=links)
                        )

                        if (
                            self._max_pages is not None
                            and pages_crawled >= self._max_pages
                        ):
                            continue

                        for link in links:
                            if (
                                link not in visited
                                and is_same_domain(link, start_url)
                                and robots.can_fetch(self._user_agent, link)
                                and (
                                    self._max_depth is None
                                    or depth + 1 <= self._max_depth
                                )
                            ):
                                visited.add(link)
                                await url_queue.put((link, final_url, depth + 1))
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
