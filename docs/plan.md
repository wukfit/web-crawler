# Implementation Plan

## Overview

Build a CLI web crawler bottom-up via TDD, one architectural layer at a time.

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

## Steps

### Step 1: Parser (`crawler/parser.py`) — DONE
- `extract_links(html, base_url)` — extract ALL `<a href>` links from HTML (no domain filtering)
- `normalise_url(url)` — strip fragments and trailing slashes
- Input validation at module boundary, early return for empty HTML
- 18 unit tests covering all behaviours

### Step 2: HTTP Client (`http/client.py`) — DONE
- `HttpClient` Protocol + `HttpxClient` implementation
- `HttpResponse` frozen dataclass (url, status_code, body, content_type)
- `FetchError` custom exception for network/timeout errors
- Async context manager, configurable timeout and user-agent via `HttpSettings` (pydantic-settings)
- Env vars: `CRAWLER_TIMEOUT`, `CRAWLER_USER_AGENT`
- 9 unit tests using httpx MockTransport + 3 settings tests

### Step 3: Crawler Service (`crawler/service.py`) — DONE
- BFS URL queue with visited set
- Async worker pool with `asyncio.Semaphore` for concurrency control
- `is_same_domain` for crawl queue filtering (only same-domain pages crawled)
- Wire parser + HTTP client
- Graceful per-page error handling (FetchError, non-200, non-HTML)
- try/finally for guaranteed cleanup of in_progress counter
- 13 unit tests using FakeHttpClient (no external mocks)

### Step 4: CLI Wiring (`cli.py`) — DONE
- Accept `url` argument via typer
- `asyncio.run()` bridge from sync typer to async crawl
- Per-page grouped output: page URL then all found links (no cross-page dedup)
- 3 unit tests (grouped output, no dedup, missing arg)

## Process per step

1. TDD: write test → red → implement → green → refactor
2. Verify: `make all` (format + lint + typecheck + test)
3. Review: `/simple-code-reviewer`, fix any findings
4. Save context to `/docs`
5. Commit and push
6. Pause for developer review
