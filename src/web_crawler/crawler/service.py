"""Crawler orchestration service."""

import asyncio
from dataclasses import dataclass, field

from web_crawler.crawler.parser import extract_links
from web_crawler.http.client import FetchError, HttpClient


@dataclass(frozen=True)
class CrawlerResult:
    url: str
    links: list[str] = field(default_factory=list)


class CrawlerService:
    def __init__(
        self,
        client: HttpClient,
        max_concurrency: int = 5,
    ) -> None:
        self._client = client
        self._max_concurrency = max_concurrency

    async def crawl(self, start_url: str) -> list[CrawlerResult]:
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
                        except FetchError:
                            continue

                        if response.status_code != 200:
                            continue

                        if "text/html" not in response.content_type:
                            continue

                        links = extract_links(response.body, url)
                        results.append(
                            CrawlerResult(url=url, links=links)
                        )

                        for link in links:
                            if link not in visited:
                                visited.add(link)
                                await queue.put(link)
                finally:
                    in_progress -= 1
                    done_event.set()

        workers = [
            asyncio.create_task(worker())
            for _ in range(self._max_concurrency)
        ]
        await asyncio.gather(*workers)

        return results
