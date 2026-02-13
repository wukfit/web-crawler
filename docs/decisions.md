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
- **crawler/parser.py**: Domain logic. Extracts URLs from HTML, resolves relative URLs.
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

## 2026-02-12: Crawler Improvements

### Parser: extract all resource URLs
Renamed `extract_links` → `extract_urls`. Extracts URLs from all standard HTML resource tags via a `_TAG_ATTRS` mapping dict. Coverage validated against the [WHATWG HTML standard](https://html.spec.whatwg.org/multipage/indices.html) list of URL-bearing attributes. Parsed: `a[href]`, `area[href]`, `audio[src]`, `embed[src]`, `iframe[src]`, `img[src]`, `link[href]`, `script[src]`, `source[src]`, `track[src]`, `video[src, poster]`. Excluded with rationale: `srcset` (complex format), `form[action]`/`formaction` (POST semantics), `cite` (metadata), `object[data]` (legacy), `base[href]` (resolution directive). Removed domain filtering from parser — it's crawl policy, not parsing logic.

### Service: domain filtering moved from parser
`is_same_domain` moved to the service layer. Parser returns all URLs found; service filters same-domain URLs for the crawl queue. `CrawlerResult.links` contains all URLs (including external) — matching the brief's "all the URLs it finds on that page".

### Service: robots.txt compliance
Fetches `{scheme}://{netloc}/robots.txt` before crawling. Uses stdlib `urllib.robotparser.RobotFileParser` to check `can_fetch(user_agent, url)` before adding URLs to the crawl queue. Graceful fallback: missing (404) or unreachable robots.txt → allow everything. Uses `netloc` (not `hostname`) to preserve ports. The `user_agent` parameter defaults to `"*"` (wildcard) and is wired from `HttpSettings.user_agent` in the CLI.

### Service: stderr logging for skipped pages
Uses Python `logging` module. `FetchError` and non-200 responses log `WARNING` to stderr. Non-HTML responses are silently skipped (expected for images/PDFs). CLI configures `logging.basicConfig` to stderr with `WARNING` level.

### CLI: per-page grouped output
Output format changed from flat URL list to per-page grouped output. Each page shows its URL followed by indented discovered URLs. No cross-page deduplication — matches the brief's "for each page... print the URL and all the URLs it finds".

### Service: streaming output via async generator
Initially `crawl()` returned `list[CrawlerResult]` — the entire crawl had to finish before any output appeared. On real sites (e.g. books.toscrape.com with ~1000 pages) this meant ~60 seconds of silence. Changed to `AsyncIterator[CrawlerResult]` using a dual-queue pattern:

- `url_queue` — URLs waiting to be fetched (workers consume)
- `result_queue` — parsed results waiting to be yielded (caller consumes)
- `None` sentinel signals all workers are done

The CLI now uses `async for result in service.crawl(url)` and prints each page immediately. Workers continue discovering and fetching in the background while results stream to stdout.

### Service: worker cancellation on unexpected errors
`asyncio.gather` does **not** cancel sibling tasks when one raises an unhandled exception — they become orphaned coroutines. Added explicit `for t in worker_tasks: t.cancel()` in the `run_workers` `finally` block. This ensures all workers are cleaned up whether crawling completes normally or an unexpected error occurs.

Found during code review — verified with a test using `asyncio.Event` synchronisation to confirm the slow worker actually receives `CancelledError`.

### Parser: multi-attribute tag support
Changed `_TAG_ATTRS` from `dict[str, str]` to `dict[str, list[str]]` to support tags with multiple URL-bearing attributes. Added `poster` for `<video>` (video thumbnail URL). The existing `seen` set handles deduplication when both attributes resolve to the same URL.

## Limitations & Trade-offs

### Bot blocking
Some websites (e.g. StackOverflow, many Cloudflare-protected sites) block automated crawlers even with a legitimate `User-Agent` header. The current implementation handles this gracefully — `FetchError` is logged to stderr and the crawl continues to other pages. More sophisticated anti-bot measures (JavaScript challenges, CAPTCHAs, rate-based blocking) are out of scope for this project.

### Unparsed URL attributes
Compared against the WHATWG HTML standard, the following URL-bearing attributes are intentionally excluded:
- **`srcset`** (`img`, `source`) — comma-separated entries with width/pixel-density descriptors (e.g. `image-480w.jpg 480w`). Requires dedicated parsing beyond simple attribute extraction.
- **`action`** (`form`), **`formaction`** (`button`, `input`) — forms imply user interaction. Submitting without expected POST body could trigger server-side effects.
- **`cite`** (`blockquote`, `del`, `ins`, `q`) — attribution metadata, not a navigable resource.
- **`data`** (`object`) — legacy plugin content, rarely relevant in modern HTML.
- **`href`** on `base` — changes URL resolution base for the document, not a resource URL itself.

### Large binary responses
`response.text` materialises the entire response body. For large binary files (PDFs, images) this is wasteful. A future optimisation: send a HEAD request to check `content-type` before fetching the full body. Deferred — not a blocker for correctness.

### Single-domain constraint
The crawler only follows links within the exact same hostname (not subdomains). `blog.example.com` is treated as external to `example.com`. This is by design per the brief, but could be made configurable.

### Security considerations
Crawled URLs are printed directly to stdout and stderr. The main attack vectors and their status:
- **XSS**: Not applicable — no browser context, URLs are plain text output.
- **SSRF**: Mitigated — `is_same_domain` prevents following links to internal IPs, localhost, or cloud metadata endpoints. The crawler only fetches URLs matching the start URL's hostname.
- **Command/SQL injection**: Not applicable — URLs are never passed to shell commands or database queries.
- **Scheme attacks** (`file:`, `javascript:`, `data:`): Mitigated — parser allowlists `http`/`https` only.
- **Terminal escape injection**: Not mitigated — URLs containing ANSI escape sequences (e.g. `\x1b[2J`) are printed without sanitisation. A malicious page could craft HTML entity-encoded URLs that decode to terminal control characters. In practice, URL percent-encoding limits this, but BeautifulSoup's HTML entity decoding could produce raw escape bytes. A future fix: strip control characters (codepoints < 0x20 except `\t`, `\n`) before printing.

### JavaScript-rendered content
The crawler parses raw HTML without executing JavaScript. Pages that render content client-side (SPAs, React/Next.js CSR) will appear to have no links in their `<body>`. This is common with modern frameworks — the initial HTML is a shell and content is populated by JavaScript at runtime. Server-side rendered (SSR) pages may also return different HTML to the crawler vs a browser depending on User-Agent detection. Discovered during testing against a Next.js site (getharley.com) where the `<main>` tag was empty in the raw HTML.

## Development Process

### Methodology
Strict TDD red-green-refactor throughout. Each feature starts with a failing test, then minimal implementation to make it pass, then cleanup. Code review after each implementation step catches issues early.

### Tools
- **IDE**: VSCode with Claude Code extension — AI-assisted pair programming
- **AI collaboration**: Claude (Anthropic) used as a collaborative partner. The developer reviewed all code, challenged suggestions (e.g. false positive bug reports from code review), and made architectural decisions. AI was particularly useful for Python-specific idioms (async generators, Protocol types, pytest fixtures) given the developer's background in Java/Go/TypeScript.
- **Domain knowledge**: Developer's existing knowledge of web standards (HTML tags, URL resolution, robots.txt) guided feature scope. AI explained Python-specific approaches (e.g. `asyncio.Queue` vs `asyncio.gather`, `urllib.robotparser` stdlib module).
- **Library research**: Googling Python libraries (httpx, beautifulsoup4, pydantic-settings) to read official docs and understand capabilities before writing code.
- **Verification**: `make all` (format + lint + typecheck + test) after every change. Code review skill (`/simple-code-reviewer`) before each commit to catch issues the automated tools miss.

### TDD cycle in practice
1. Write one test capturing the desired behaviour → run it → confirm it fails (red)
2. Write minimal code to make it pass → run it → confirm it passes (green)
3. Refactor if needed (extract helpers, rename for clarity)
4. `make all` to verify nothing broke
5. Repeat for next behaviour

This approach caught several issues early:
- First worker cancellation test passed immediately (wrong — it only tested exception propagation, not actual cancellation). Rewritten with `asyncio.Event` synchronisation to properly verify the slow worker was cancelled.
- Parser indentation error when adding inner loop — caught by test failure before it could be committed.
