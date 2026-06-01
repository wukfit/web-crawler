# Implementation Plan

## Overview

Build a CLI web crawler bottom-up via TDD, one architectural layer at a time.

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

## Steps

### Step 1: Parser (`crawler/parser.py`) — DONE
- `extract_urls(html, base_url)` — extract URLs from all standard HTML resource tags (`a`, `area`, `audio`, `embed`, `iframe`, `img`, `link`, `script`, `source`, `track`, `video`)
- `normalise_url(url)` — strip fragments and trailing slashes
- Multi-attribute tag support (`<video src poster>`) via `dict[str, list[str]]`
- Input validation at module boundary, early return for empty HTML
- 29 unit tests covering all behaviours

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

### Step 5: Terminal Escape Injection Mitigation — DONE

**Problem**: Crawled URLs are attacker-controlled. BeautifulSoup decodes HTML entities (e.g. `&#x1b;` → `\x1b`), so a malicious page can emit URLs carrying raw terminal control sequences (e.g. `\x1b[2J`). These reach the operator's terminal unsanitised via stdout (`cli.py` echo) and stderr (`service.py` warning logs), enabling screen-clearing, line-spoofing (`\n`/`\r`), and other escape-driven attacks.

**Design decisions** (see `docs/decisions.md`):
- Sanitise at the **print sites** (the sinks), not in the parser — crawl/dedup logic keeps operating on raw URLs.
- Strip, don't escape — a URL containing control chars is already malformed/hostile.
- **No `\t`/`\n`/`\r` carve-out** (stricter than the review's suggestion): output is one URL per line, whitespace in a valid URL is always percent-encoded, and `\n`/`\r` are line-spoofing primitives.

**Scope**:
- New leaf module `sanitise.py` — `strip_control_chars(s)` removes C0 (`\x00–\x1f`), DEL (`\x7f`), and C1 (`\x80–\x9f`).
- `cli.py` — wrap both `typer.echo` sinks (`result.url`, each `link`).
- `service.py` — sanitise `url`, `parent_url`, and `str(exc)` in both `logger.warning` calls.
- **Out of scope**: `_validate_url` error messages — they echo the operator's own start URL, not remotely-discovered content.

**Outcome**: A URL discovered on a crawled page can never deliver raw terminal control characters to the operator's terminal, on either stdout or stderr. A `CrawlerResult` URL printed to the terminal is always control-char-free.

**Acceptance criteria**:
- `strip_control_chars` removes all codepoints in `\x00–\x1f`, `\x7f`, `\x80–\x9f` (including `\x1b`, `\n`, `\r`, `\t`) and leaves an ordinary `http(s)` URL byte-for-byte unchanged.
- Crawling a page whose link contains `\x1b[2J` produces stdout output with no `\x1b` byte; the URL's printable remainder still appears.
- A failed fetch whose `FetchError` message contains a control char produces a `logger.warning` record with no control characters.
- All three test layers pass: `tests/unit/test_sanitise.py` (contract), `test_cli.py` (stdout sink wired), `test_crawler_service.py` (stderr log sink wired).
- No regression: full suite + `make all` (format + lint + typecheck + test) green.

## Process per step

1. TDD: write test → red → implement → green → refactor
2. Verify: `make all` (format + lint + typecheck + test)
3. Review: `/simple-code-reviewer`, fix any findings
4. Save context to `/docs`
5. Commit and push
6. Pause for developer review
