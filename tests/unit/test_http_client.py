import httpx
import pytest

from web_crawler.http.client import FetchError, HttpxClient
from web_crawler.http.settings import HttpSettings

DEFAULTS = HttpSettings(timeout=30.0, user_agent="web-crawler/0.1.0")


def make_client(
    transport: httpx.AsyncBaseTransport,
    settings: HttpSettings = DEFAULTS,
) -> HttpxClient:
    return HttpxClient(settings=settings, transport=transport)


def html_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        text="<html><body>hello</body></html>",
        headers={"content-type": "text/html; charset=utf-8"},
        request=request,
    )


def not_found_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        404,
        text="Not Found",
        headers={"content-type": "text/html"},
        request=request,
    )


def connection_error_transport(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Connection refused")


class TestHttpxClient:
    async def test_fetch_returns_http_response(self):
        transport = httpx.MockTransport(html_response)
        async with make_client(transport) as client:
            response = await client.fetch("https://example.com")

        assert response.url == "https://example.com"
        assert response.status_code == 200
        assert response.body == "<html><body>hello</body></html>"
        assert response.content_type == "text/html; charset=utf-8"

    async def test_sets_user_agent_header(self):
        captured_headers: dict[str, str] = {}

        def capture_headers(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return html_response(request)

        transport = httpx.MockTransport(capture_headers)
        async with make_client(transport) as client:
            await client.fetch("https://example.com")

        assert "web-crawler" in captured_headers.get("user-agent", "").lower()

    async def test_custom_settings_applied(self):
        captured_headers: dict[str, str] = {}

        def capture_headers(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return html_response(request)

        custom = HttpSettings(timeout=5.0, user_agent="custom-bot/1.0")
        transport = httpx.MockTransport(capture_headers)
        async with make_client(transport, custom) as client:
            await client.fetch("https://example.com")

        assert captured_headers["user-agent"] == "custom-bot/1.0"

    async def test_raises_fetch_error_on_connection_error(self):
        transport = httpx.MockTransport(connection_error_transport)
        async with make_client(transport) as client:
            with pytest.raises(FetchError):
                await client.fetch("https://example.com")

    async def test_raises_fetch_error_on_timeout(self):
        def timeout_transport(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Request timed out")

        transport = httpx.MockTransport(timeout_transport)
        async with make_client(transport) as client:
            with pytest.raises(FetchError):
                await client.fetch("https://example.com")

    async def test_returns_response_for_non_200_status(self):
        transport = httpx.MockTransport(not_found_response)
        async with make_client(transport) as client:
            response = await client.fetch("https://example.com/missing")

        assert response.status_code == 404
        assert response.body == "Not Found"

    async def test_close_shuts_down_client(self):
        transport = httpx.MockTransport(html_response)
        client = make_client(transport)
        await client.close()
        assert client._client.is_closed

    async def test_raises_on_empty_url(self):
        transport = httpx.MockTransport(html_response)
        async with make_client(transport) as client:
            with pytest.raises(ValueError, match="url"):
                await client.fetch("")

    async def test_works_as_async_context_manager(self):
        transport = httpx.MockTransport(html_response)
        async with make_client(transport) as client:
            response = await client.fetch("https://example.com")
            assert response.status_code == 200

    async def test_follows_redirects(self):
        def redirect_transport(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "https://example.com/old":
                return httpx.Response(
                    302,
                    headers={
                        "location": "https://example.com/new",
                        "content-type": "text/html",
                    },
                    request=request,
                )
            return html_response(request)

        transport = httpx.MockTransport(redirect_transport)
        async with make_client(transport) as client:
            response = await client.fetch("https://example.com/old")

        assert response.status_code == 200
        assert response.url == "https://example.com/new"
