# Implementation Plan

## Overview

Build a CLI web crawler bottom-up via TDD, one architectural layer at a time.

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

## Steps

### Step 1: Parser (`crawler/parser.py`) — DONE
- `extract_links(html, base_url)` — extract `<a href>` links from HTML
- `is_same_domain(url, base_url)` — exact hostname match
- `normalise_url(url)` — strip fragments and trailing slashes
- Input validation at module boundary, early return for empty HTML
- 22 unit tests covering all behaviours

### Step 2: HTTP Client (`http/client.py`)
- Add `httpx` as dependency
- Define a `Protocol` (interface) for the HTTP client
- Implement async client: fetch page HTML, connection pooling, timeouts
- Error handling (network errors, non-HTML responses, status codes)

### Step 3: Crawler Service (`crawler/service.py`)
- BFS URL queue with visited set
- Async concurrency via `asyncio.Semaphore`
- Wire parser + HTTP client
- Return structured results (page URL → links found)

### Step 4: CLI Wiring (`cli.py`)
- Accept `url` argument via typer
- Delegate to crawler service
- Print results (page URL + discovered links)
- Update existing CLI test, add integration test

## Process per step

1. TDD: write test → red → implement → green → refactor
2. Verify: `make all` (format + lint + typecheck + test)
3. Review: `/simple-code-reviewer`, fix any findings
4. Save context to `/docs`
5. Commit and push
6. Pause for developer review
