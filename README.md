# Web Crawler

CLI web crawler that discovers and prints all URLs found on each page within a single domain. Results stream to stdout as pages are crawled, errors go to stderr.

## Setup

```bash
uv sync
```

## Usage

```bash
uv run web-crawler https://example.com
```

Output is grouped per page: the page URL followed by indented discovered URLs.

```
https://example.com
  https://example.com/about
  https://example.com/logo.png
  https://example.com/style.css

https://example.com/about
  https://example.com
  https://example.com/team
```

### Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `CRAWLER_TIMEOUT` | `30.0` | HTTP request timeout in seconds |
| `CRAWLER_USER_AGENT` | `web-crawler/0.1.0` | User-Agent header and robots.txt identity |
| `CRAWLER_REQUESTS_PER_SECOND` | `10.0` | Max requests per second (overridden by robots.txt `Crawl-delay`) |

## How It Works

1. Fetches and parses `robots.txt` to determine which paths are allowed; honours `Crawl-delay` directive
2. Spawns concurrent async workers that pull URLs from a shared queue
3. Rate-limits requests via token bucket (configurable, overridden by robots.txt `Crawl-delay`)
4. Checks content-type via streaming HTTP before downloading the body, so non-HTML responses (images, PDFs) are skipped early
5. For each HTML page, extracts URLs from all standard resource tags (see table below)
6. Streams results to stdout immediately as each page completes
7. Queues newly discovered same-domain URLs for further crawling
8. Skips already-visited URLs, non-HTML responses, and robots.txt-disallowed paths

### HTML URL attribute coverage

Compared against the [WHATWG HTML standard](https://html.spec.whatwg.org/multipage/indices.html) list of URL-bearing attributes:

| Attribute | Element(s) | Parsed? | Notes |
|---|---|---|---|
| `href` | `a`, `area`, `link` | Yes | |
| `src` | `img`, `script`, `source`, `video`, `audio`, `iframe`, `embed`, `track` | Yes | |
| `poster` | `video` | Yes | |
| `srcset` | `img`, `source` | No | Complex comma+descriptor format requires dedicated parsing |
| `action` | `form` | No | Forms imply POST/user interaction, not safe GET navigation |
| `formaction` | `button`, `input` | No | Same concern as `action` |
| `cite` | `blockquote`, `del`, `ins`, `q` | No | Attribution metadata, not a navigable resource |
| `data` | `object` | No | Legacy plugin content (`<object>`), rarely relevant |
| `href` | `base` | No | Changes URL resolution base, not a resource URL |

### Other limitations

- **Bot protection**: Sites with Cloudflare, JavaScript challenges, or CAPTCHAs will block the crawler. Failed fetches log to stderr and the crawl continues.
- **Single domain only**: Subdomains (e.g. `blog.example.com`) are treated as external.
- **Streaming skip heuristic**: Non-HTML responses are identified by `content-type` header and skipped without reading the body. If a server returns the wrong `content-type`, HTML pages could be skipped.
- **JS-rendered content**: The crawler parses raw HTML only. SPAs and client-side rendered pages (React/Next.js CSR) will appear to have no links.
- **Terminal escape injection**: URLs containing ANSI escape sequences are printed to stdout without sanitisation. In practice URL percent-encoding limits this but it's not fully mitigated.
- **Approximate `--max-pages`**: The page counter is shared across concurrent workers without a lock. In CPython the increment is a single bytecode op between await points so races are unlikely, but the crawler may overshoot the limit by 1-2 pages.

## Development

```bash
make test       # run tests (64 tests)
make lint       # run linter
make format     # format code
make typecheck  # run type checker
make check      # lint + typecheck + test
make all        # format + check
```

## Architecture

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

- `cli.py` — thin presentation layer, delegates to service, prints streaming results
- `crawler/service.py` — orchestration: async worker pool, URL queue, visited set, robots.txt
- `crawler/parser.py` — extracts URLs from HTML, resolves relative URLs, normalises
- `http/client.py` — async HTTP client behind a Protocol interface, configurable via env vars

Each layer depends only on the layer below. The HTTP client uses a Protocol interface so the crawler is testable without real HTTP calls.

## Future Direction

As mentioned in the requirements, the use of a CLI is limited. Below are some of my thoughts on a future direction to address this. Before tackling any of this I would want to refine some requirements and business goals, for example, what problem is the crawler solving, and do we need to extract all URLs or just anchor links.

### Web Based UI

We could put a UI over the crawler and initially, expose the same single domain crawl experience. Then iterate on submitting "crawl jobs". We already have streamed results so piping that into SSE or WebSocket could be straightforward.

### Multi-Domain

The main changes here are per "job" rate limiting, robots.txt, and the visited set of URLs.

### Scaling Out

I would load test the capabilities of a single async process, but as per my thoughts above, having some kind of crawl job queue with job state persisted to disk (DB) is where I would go with this.

### Addressing Current Limitations

The biggest gap is JS-rendered content. A lot of modern sites are SPAs that return an empty shell and render everything client-side. I'd look at putting a headless browser (Playwright/Puppeteer) behind the `HttpClient` Protocol to handle these. That also helps with bot protection since a real browser session gets past most Cloudflare challenges. It's much slower and heavier on resources though, so I'd make it opt-in rather than the default.

The layered architecture means the crawler core stays the same — just swap what wraps it.

## Tools & AI Disclosure

- **IDE**: VSCode with Claude Code extension
- **AI**: Claude (Anthropic) via Claude Code for pair programming. I reviewed all code and made the architectural decisions. AI was most useful for Python-specific patterns (async generators, Protocol types, pytest) since my background is Java/Go/TypeScript.
- **Domain knowledge**: Web standards experience (HTML, URL resolution, robots.txt) guided scope. Python library docs (httpx, beautifulsoup4, pydantic-settings) read independently.
- **Methodology**: TDD red-green-refactor, code review after each step

## Documentation

- [docs/decisions.md](docs/decisions.md) — architecture decisions, trade-offs, limitations, development process
- [docs/plan.md](docs/plan.md) — implementation plan and step-by-step progress
- [docs/initial-brief.md](docs/initial-brief.md) — original task brief and planning discussion
- [docs/review.md](docs/review.md) — self-review of the codebase against the brief
- [docs/code-review-skill.md](docs/code-review-skill.md) — the Claude Code skill used for code review
