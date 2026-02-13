# Web Crawler

CLI web crawler that discovers and prints all URLs found on each page within a single domain. Results stream to stdout as pages are crawled. Any crawl errors are stderr as they are encountered.

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

## How It Works

1. Fetches and parses `robots.txt` to determine which paths are allowed
2. Spawns concurrent async workers that pull URLs from a shared queue
3. For each HTML page, extracts URLs from all standard resource tags (see table below)
4. Streams results to stdout immediately as each page completes
5. Queues newly discovered same-domain URLs for further crawling
6. Skips already-visited URLs, non-HTML responses, and robots.txt-disallowed paths

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

- **Bot protection**: Sites with Cloudflare, JavaScript challenges, or CAPTCHAs will block the crawler. Failed fetches are logged to stderr and the crawl continues.
- **Single domain only**: Subdomains (e.g. `blog.example.com`) are treated as external.
- **Full body fetch**: Binary files (PDFs, images) are fully downloaded before being identified as non-HTML. A HEAD-first optimisation is possible but not implemented.
- **JS-rendered content**: Pages that render via JavaScript (SPAs, React/Next.js CSR) will have no discoverable links in the body. The crawler parses raw HTML only.
- **Terminal escape injection**: URLs containing ANSI escape sequences are printed to stdout without sanitisation. A malicious page could craft URLs that manipulate terminal display. Mitigated in practice by URL percent-encoding, but not guaranteed for all HTML parsers/entities.

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

Each layer depends only on the layer below. The HTTP client is injectable via Protocol, making the crawler fully testable without real HTTP calls.

## Tools & AI Disclosure

- **IDE**: VSCode with Claude Code extension
- **AI**: Claude (Anthropic) via Claude Code — collaborative pair-programming partner. I reviewed all code, challenged AI suggestions, and made architectural decisions. AI was useful for Python-specific idioms (async generators, Protocol types, pytest patterns) given the my Java/Go/TypeScript background.
- **Domain knowledge**: My prior web standards experience (HTML, URL resolution, robots.txt) guided feature scope. Python library docs (httpx, beautifulsoup4, pydantic-settings) read independently.
- **Methodology**: Strict TDD red-green-refactor, code review after each step

## Documentation

- [docs/decisions.md](docs/decisions.md) — architecture decisions, trade-offs, limitations, development process
- [docs/plan.md](docs/plan.md) — implementation plan and step-by-step progress
- [docs/initial-brief.md](docs/initial-brief.md) — original task brief and planning discussion
