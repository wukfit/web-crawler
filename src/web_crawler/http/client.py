"""HTTP client for web requests."""

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
            transport=transport,
        )

    async def fetch(self, url: str) -> HttpResponse:
        if not url:
            raise ValueError("url must not be empty")

        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc

        # TODO: response.text materialises the entire body in memory. For large
        # binary responses (e.g. 50MB PDF) this is wasteful. A HEAD-request
        # optimisation in the service layer could check content-type before
        # fetching the full body.
        return HttpResponse(
            url=str(response.url),
            status_code=response.status_code,
            body=response.text,
            content_type=response.headers.get("content-type", ""),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
