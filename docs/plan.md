# Implementation Plan

## Overview

Build a CLI web crawler bottom-up via TDD, one architectural layer at a time.

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

## Steps

### Step 1: Parser (`crawler/parser.py`) — DONE
- `extract_urls(html, base_url)` — extract URLs from `<a>`, `<img>`, `<link>`, `<script>`, `<source>`, `<video>`, `<audio>`
- `normalise_url(url)` — strip fragments and trailing slashes
- Multi-attribute tag support (`<video src poster>`) via `dict[str, list[str]]`
- Input validation at module boundary, early return for empty HTML
- 25 unit tests covering all behaviours

### Step 2: HTTP Client (`http/client.py`) — DONE
- `HttpClient` Protocol + `HttpxClient` implementation
- `HttpResponse` frozen dataclass (url, status_code, body, content_type)
- `FetchError` custom exception for network/timeout errors
- Async context manager, configurable timeout and user-agent via `HttpSettings` (pydantic-settings)
- Env vars: `CRAWLER_TIMEOUT`, `CRAWLER_USER_AGENT`
- 9 unit tests using httpx MockTransport + 3 settings tests

### Step 3: Crawler Service (`crawler/service.py`) — DONE
- Streaming output via `AsyncIterator[CrawlerResult]` (dual-queue pattern)
- BFS URL queue with visited set
- `is_same_domain` — same-domain filtering for crawl queue
- Async worker pool with `asyncio.Semaphore` for concurrency control
- Worker cancellation on unexpected errors via explicit `task.cancel()` in finally
- Wire parser + HTTP client
- robots.txt compliance via `urllib.robotparser`
- Graceful per-page error handling (FetchError, non-200, non-HTML)
- stderr logging for FetchError and non-200 responses
- try/finally for guaranteed cleanup of in_progress counter
- 20 unit tests using FakeHttpClient (no external mocks)

### Step 4: CLI Wiring (`cli.py`) — DONE
- Accept `url` argument via typer
- `asyncio.run()` bridge from sync typer to async crawl
- Streaming output — prints each page as it's crawled
- Per-page grouped output (page URL + indented discovered URLs)
- stderr logging config for crawler warnings
- 2 unit tests (happy path with monkeypatched service, missing arg)

## Process per step

1. TDD: write test → red → implement → green → refactor
2. Verify: `make all` (format + lint + typecheck + test)
3. Review: `/simple-code-reviewer`, fix any findings
4. Save context to `/docs`
5. Commit and push
6. Pause for developer review
