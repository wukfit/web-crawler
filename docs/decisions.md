# Architecture Decisions

## 2026-02-12: Project Setup

### Package Manager: uv
- Fast (Rust-based), replaces pip/venv/pip-tools in a single tool
- Generates `uv.lock` for reproducible builds (like `package-lock.json` or `go.sum`)
- `uv run` executes commands in the project's virtualenv without manual activation

### Build Backend: hatchling
- Mature, well-documented build backend
- Automatically discovers src-layout packages
- Supported natively by `uv init --package`

### CLI Framework: typer
- Type-hint based CLI argument parsing — very Pythonic, minimal boilerplate
- Same author as FastAPI — natural upgrade path if we ever move from CLI to HTTP API
- Built on click (the most popular Python CLI library)

### HTTP Client: httpx
- Modern async/sync HTTP client with requests-compatible API
- HTTP/2 support out of the box
- Swappable via Python Protocol (interface) — crawler never knows which HTTP library is underneath

### HTML Parsing: beautifulsoup4
- Industry standard for HTML parsing in Python
- Handles malformed HTML gracefully
- Well-documented, large community

### Linting/Formatting: ruff
- Replaces black (formatter) + isort (import sorter) + flake8 (linter) in a single tool
- 10-100x faster than the tools it replaces (written in Rust)
- Configured in `pyproject.toml` — no extra config files

### Type Checking: mypy (strict mode)
- Catches type errors before runtime
- Strict mode enforced for `src/`, relaxed for `tests/`
- New project = no legacy to migrate, so strict from day one

### Directory Structure: src layout
- `src/web_crawler/` instead of `web_crawler/` at project root
- Prevents accidental imports of the uninstalled package during testing
- Industry standard for distributable Python packages

## Architecture

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

- **cli.py**: Thin presentation layer. Parses args, delegates to service, formats output.
- **crawler/service.py**: Orchestration. Manages URL queue, visited set, concurrency.
- **crawler/parser.py**: Domain logic. Extracts links, resolves relative URLs, filters by domain.
- **http/client.py**: Infrastructure. HTTP requests, connection pooling, retry logic.

Each layer depends only on the layer below it. The HTTP client is injectable, making the crawler testable without real HTTP calls.

## 2026-02-12: Parser Implementation

### Extracted helpers: `is_same_domain`, `normalise_url`
Code review identified "what" comments explaining inline logic. Replaced with named functions that make `extract_links` read as a pipeline of named operations. Both helpers are independently testable.

### Scheme filtering: allowlist over blocklist
Initially filtered `mailto:` and `javascript:` by prefix. Code review caught that `tel:`, `ftp:`, `data:` etc. would slip through. Switched to allowlisting `http`/`https` on the resolved URL — more robust and future-proof.

### Input validation: at module boundary only
`extract_links` validates `base_url` (raises `ValueError` if empty) and short-circuits on empty `html` (avoids BeautifulSoup overhead at scale). Internal helpers (`is_same_domain`, `normalise_url`) do not validate — they're trusted internal functions called after the boundary check. If these helpers are later used outside `extract_links`, validation should be added at that point.

### URL normalisation
- Fragments stripped (same page, not a distinct resource)
- Trailing slashes stripped (prevents duplicates like `/about` vs `/about/`)
- Deduplication via `seen` set on normalised URLs

## 2026-02-12: HTTP Client Implementation

### Protocol-based abstraction
`HttpClient` Protocol defines the contract (`fetch`, `close`). `HttpxClient` implements it. The crawler service depends on the Protocol, not the implementation — making it testable with httpx's built-in `MockTransport` (no external mocking libraries).

### HttpResponse dataclass
Frozen dataclass wrapping `url`, `status_code`, `body`, `content_type`. Avoids leaking httpx types through the architecture boundary. The `content_type` field enables the service layer to decide whether to parse a response for links (only `text/html`).

### Error handling strategy
Network/transport errors (`ConnectError`, `TimeoutException`) are caught and re-raised as `FetchError`. Non-success HTTP status codes (4xx, 5xx) are returned as normal responses — the caller decides how to handle them. Retry logic belongs in the service layer, not the HTTP client.

### Crawlable vs reportable URLs
The parser returns *all* same-domain URLs found on a page (images, PDFs, etc.) — these are reportable. The service layer determines which are *crawlable* by checking the response `content_type` after fetching. This matches the requirement: "print the URL and all URLs found on that page".

### Memory concern: large binary responses
`response.text` materialises the entire body. For large binary files (e.g. 50MB PDF) this is wasteful. A future optimisation: HEAD request to check content-type before fetching the full body. Deferred — not a blocker for initial implementation.

### Configurable settings via pydantic-settings
`HttpSettings` reads `CRAWLER_TIMEOUT` and `CRAWLER_USER_AGENT` from environment variables with sensible defaults. `HttpxClient` accepts an optional `HttpSettings` instance — defaults to reading from env if not provided. Using `is not None` check (not `or`) to avoid truthiness ambiguity with pydantic models.

## 2026-02-12: Crawler Service Implementation

### Concurrency model: asyncio worker pool
Multiple worker coroutines pull from an `asyncio.Queue`. An `asyncio.Semaphore` caps concurrent HTTP fetches. Workers exit when the queue is empty and `in_progress == 0`. This gives true parallelism on I/O-bound fetches while keeping the BFS traversal order.

### Guaranteed cleanup with try/finally
The `in_progress` counter and `done_event` signal coordinate worker lifecycle. All early exits (`FetchError`, non-200, non-HTML) use `continue` inside `async with semaphore`, with `try/finally` ensuring the counter always decrements. This eliminates duplicate cleanup blocks and prevents deadlock if the semaphore/worker ratio changes.

### Dependency injection: caller owns the client
`CrawlerService` receives an `HttpClient` via constructor — it does not create or close it. No `__aenter__`/`__aexit__` needed. The caller manages the client lifecycle, keeping ownership clear and avoiding double-close bugs.

### Error isolation per page
`FetchError` on one page does not abort the crawl. Non-200 and non-HTML responses are silently skipped. Only successfully fetched HTML pages appear in results. This matches expected crawler behaviour — partial results are more useful than a full abort.

## 2026-02-12: CLI Wiring

### asyncio.run bridge
Typer is synchronous. The crawler is async. `asyncio.run(_crawl(url))` bridges the two. The async function creates the `HttpxClient` context manager, runs the crawl, then prints results. Simple and standard — no third-party async CLI libraries needed.

### Output format: one URL per line
Plain URLs to stdout, one per line. Easy to pipe to `wc -l`, `sort`, `grep`, or other Unix tools. No JSON or structured output — keep it simple for v1.
