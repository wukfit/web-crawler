# Code Review

## Bugs

### A. Start URL not normalised before adding to `visited` set

`service.py:62` — `visited.add(start_url)` adds the raw input URL. But `extract_urls` returns normalised URLs (trailing slash stripped via `normalise_url`). If a user passes `https://example.com/` and a child page links back to `https://example.com`, the normalised form doesn't match the visited entry, causing the root page to be re-crawled.

**Fix**: normalise `start_url` before adding to `visited` and the queue.

### B. After redirect, original URL used instead of final URL

`service.py:81-103` — `HttpxClient` follows redirects and captures the final URL in `response.url`, but the service ignores it. It uses the original queue URL for both:
- Link resolution (`base_url` in `extract_urls`) — relative links on redirected pages resolve against the wrong path
- Result reporting (`CrawlerResult.url`) — reports the pre-redirect URL

Additionally, a same-domain URL that redirects to a different domain bypasses the domain check (which only runs at queue-entry time, not post-redirect).

**Fix**: use `response.url` for link resolution and result reporting. Re-check domain after redirect.

### C. HTTP/2 claimed but not enabled

`decisions.md:23` says "HTTP/2 support out of the box". httpx requires `http2=True` in `AsyncClient` and the `h2` package dependency. Neither is present.

**Fix**: either enable HTTP/2 (`http2=True` + `h2` dep) or remove the claim from docs.

## Missing Functionality

### Against the brief

| Requirement | Met? | Notes |
|---|---|---|
| CLI accepting base URL | Yes | |
| Print page URL + all found URLs | Yes | Covers most WHATWG URL attributes; `srcset` excluded with rationale |
| Only crawl single domain | Yes | Exact hostname match |
| Speed patterns (concurrency) | Partial | Async workers with semaphore, but HTTP/2 not enabled, no connection pool tuning |
| No Scrapy/Playwright | Yes | |
| Design discussion in README | Yes | Thorough in `docs/decisions.md` |
| AI tool disclosure | Yes | |
| Discussion of extending for multi-domain, CLI alternatives | Weak | Brief mention of "natural upgrade path to FastAPI" but no dedicated discussion of multi-domain architecture, queue-based systems, or why CLI is limiting |

### Functional gaps

- **No input validation on CLI URL** — `foobar` or `file:///etc/passwd` gives a cryptic fetch failure instead of a helpful error
- **No max depth or max pages limit** — on a large site the `visited` set and queue grow unbounded until OOM
- **No rate limiting / crawl delay** — 5 concurrent workers with no delay could hammer a small server; `robots.txt` `Crawl-delay` directive not honoured
- **No graceful shutdown** — `Ctrl+C` produces asyncio stack traces rather than clean termination

## Fundamental Flaws

### Under-engineering

- **No rate limiting** is the most significant gap for "not sacrificing... compute resources" (from the brief). The crawler sends 5 concurrent requests as fast as the server responds.
- **Full body download for all URLs** — acknowledged in `client.py:54-57` TODO. Every image, PDF, and binary file is fully downloaded into memory before checking content-type. A HEAD request or streaming with early termination would fix this.

### Over-engineering

Very little. The Protocol abstraction earns its keep for testing. `pydantic-settings` for two fields is fine. Documentation is thorough but the brief explicitly asks for it.

### Design observations

- `normalise_url` trailing-slash stripping is lossy. `https://example.com/api/` and `https://example.com/api` are technically different resources per HTTP spec. Most servers treat them the same, some don't. Trade-off is documented.
- `is_same_domain` uses `hostname` (not `netloc`) so port differences are ignored — `example.com:8080` and `example.com:443` would be considered same domain and both crawled.

## Tests

### Strengths

- 64 tests, all passing
- No mocking libraries — hand-written fakes (`FakeHttpClient`, `CountingClient`, `SlowClient`, `BuggyClient`) that test real behaviour
- Parser has excellent coverage: all tag types, relative URLs, scheme filtering, dedup, malformed HTML, edge cases
- Worker cancellation test uses `asyncio.Event` synchronisation — properly verifies cancellation happens
- Robots.txt tests cover allow/disallow, missing file, fetch error, agent-specific rules, port handling

### Gaps

- **Empty `tests/integration/` directory** — no integration tests. Even a simple test spinning up a local HTTP server and crawling it would validate the full stack
- **No test for start_url normalisation** — bug A is uncaught because tests always use canonical URLs
- **No test for redirect behaviour in the service** — `HttpxClient` test covers redirects, but no service-level test verifies correct behaviour when a crawled page redirects
- **No explicit tests for `<audio>` and `<source>` tags** — every other tag in `_TAG_ATTRS` has a dedicated test except these two
- **No test for invalid CLI input** — e.g., non-URL string, missing scheme
- **No test for deeply nested crawl** — would catch any stack/recursion issues in the worker loop

### Weak tests

- `test_works_as_async_context_manager` in `test_http_client.py:112` — every other test already uses the context manager, so this adds no unique coverage

## Brief Compliance Summary

### Fully met

- CLI app accepting a URL
- Per-page URL + discovered URLs output
- Single-domain crawling constraint
- No Scrapy/Playwright
- Clean code structure with separation of concerns
- TDD approach documented
- Design decisions documented
- AI disclosure present
- Production project setup (src layout, linting, typing, Makefile)

### Partially met

- "Run as quickly as possible" — async workers good, but HTTP/2 claimed and missing, no connection pool tuning
- "Not sacrificing compute resources" — full binary downloads into memory, no rate limiting
- "How you would extend" — mentioned briefly but no substantive discussion of multi-domain architecture or CLI alternatives
- "Production project" — no CI/CD, no Dockerfile, no pre-commit hooks, no coverage reporting

### Overall

Solid, well-structured work with clean architecture, good separation of concerns, and thorough TDD. Code quality is high — well named functions, clear data flow, proper error handling. The two real bugs (un-normalised start URL and redirect URL handling) are subtle edge cases that would surface in real-world crawling. Biggest functional gaps (rate limiting, depth limits, graceful shutdown) would be priorities for a production version. The brief's "extend" discussion deserves more attention.
