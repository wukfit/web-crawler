"""HTTP client for web requests."""

import asyncio
from dataclasses import dataclass
from typing import Protocol, Self

import httpx

from web_crawler.http.settings import HttpSettings


class FetchError(Exception):
    """Raised when an HTTP request fails due to network or timeout errors."""


@dataclass(frozen=True)
class HttpResponse:
    url: str
    status_code: int
    body: str
    content_type: str


class HttpClient(Protocol):
    async def fetch(self, url: str) -> HttpResponse: ...
    async def close(self) -> None: ...


MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB


class HttpxClient:
    """Async HTTP client backed by httpx."""

    def __init__(
        self,
        *,
        settings: HttpSettings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        resolved = settings if settings is not None else HttpSettings()
        self._client = httpx.AsyncClient(
            timeout=resolved.timeout,
            headers={"User-Agent": resolved.user_agent},
            follow_redirects=True,
            http2=True,
            transport=transport,
        )
        self._max_retries = resolved.max_retries
        self._retry_backoff = resolved.retry_backoff

    async def fetch(self, url: str) -> HttpResponse:
        if not url:
            raise ValueError("url must not be empty")

        last_exc: FetchError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._do_fetch(url)
            except FetchError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_backoff * (2**attempt))
        raise last_exc  # type: ignore[misc]

    async def _do_fetch(self, url: str) -> HttpResponse:
        try:
            async with self._client.stream("GET", url) as response:
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    return HttpResponse(
                        url=str(response.url),
                        status_code=response.status_code,
                        body="",
                        content_type=content_type,
                    )

                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > MAX_BODY_SIZE:
                        break

                body = b"".join(chunks)[:MAX_BODY_SIZE].decode(
                    response.charset_encoding or "utf-8", errors="replace"
                )
                return HttpResponse(
                    url=str(response.url),
                    status_code=response.status_code,
                    body=body,
                    content_type=content_type,
                )
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
