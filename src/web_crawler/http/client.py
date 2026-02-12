"""HTTP client for web requests."""

from dataclasses import dataclass
from typing import Protocol, Self

import httpx


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
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "web-crawler/0.1.0"},
            transport=transport,
        )

    async def fetch(self, url: str) -> HttpResponse:
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
