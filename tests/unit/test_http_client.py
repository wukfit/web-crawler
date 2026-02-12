import httpx
import pytest

from web_crawler.http.client import FetchError, HttpxClient


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
        async with HttpxClient(transport=transport) as client:
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
        async with HttpxClient(transport=transport) as client:
            await client.fetch("https://example.com")

        assert "web-crawler" in captured_headers.get("user-agent", "").lower()

    async def test_raises_fetch_error_on_connection_error(self):
        transport = httpx.MockTransport(connection_error_transport)
        async with HttpxClient(transport=transport) as client:
            with pytest.raises(FetchError):
                await client.fetch("https://example.com")

    async def test_raises_fetch_error_on_timeout(self):
        def timeout_transport(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Request timed out")

        transport = httpx.MockTransport(timeout_transport)
        async with HttpxClient(transport=transport) as client:
            with pytest.raises(FetchError):
                await client.fetch("https://example.com")

    async def test_returns_response_for_non_200_status(self):
        transport = httpx.MockTransport(not_found_response)
        async with HttpxClient(transport=transport) as client:
            response = await client.fetch("https://example.com/missing")

        assert response.status_code == 404
        assert response.body == "Not Found"

    async def test_close_shuts_down_client(self):
        transport = httpx.MockTransport(html_response)
        client = HttpxClient(transport=transport)
        await client.close()
        assert client._client.is_closed

    async def test_raises_on_empty_url(self):
        transport = httpx.MockTransport(html_response)
        async with HttpxClient(transport=transport) as client:
            with pytest.raises(ValueError, match="url"):
                await client.fetch("")

    async def test_works_as_async_context_manager(self):
        transport = httpx.MockTransport(html_response)
        async with HttpxClient(transport=transport) as client:
            response = await client.fetch("https://example.com")
            assert response.status_code == 200
