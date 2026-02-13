# Web Crawler

CLI web crawler that discovers and prints all URLs found on each page within a single domain. Results stream to stdout as pages are crawled — no waiting for the full crawl to finish.

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
3. For each HTML page, extracts all URLs (`<a>`, `<img>`, `<link>`, `<script>`, `<source>`, `<video>`, `<audio>`)
4. Streams results to stdout immediately as each page completes
5. Queues newly discovered same-domain URLs for further crawling
6. Skips already-visited URLs, non-HTML responses, and robots.txt-disallowed paths

### Limitations

- **Bot protection**: Sites with Cloudflare, JavaScript challenges, or CAPTCHAs will block the crawler. Failed fetches are logged to stderr and the crawl continues.
- **Single domain only**: Subdomains (e.g. `blog.example.com`) are treated as external.
- **srcset not parsed**: The `srcset` attribute (responsive images) uses a complex comma+descriptor format that requires dedicated parsing. Deferred.
- **Full body fetch**: Binary files (PDFs, images) are fully downloaded before being identified as non-HTML. A HEAD-first optimisation is possible but not implemented.

## Development

```bash
make test       # run tests (60 tests)
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
- **AI**: Claude (Anthropic) via Claude Code — collaborative pair-programming partner. Developer reviewed all code, challenged AI suggestions, and made architectural decisions. AI was useful for Python-specific idioms (async generators, Protocol types, pytest patterns) given the developer's Java/Go/TypeScript background.
- **Domain knowledge**: Developer's web standards experience (HTML, URL resolution, robots.txt) guided feature scope. Python library docs (httpx, beautifulsoup4, pydantic-settings) read independently.
- **Methodology**: Strict TDD red-green-refactor, code review after each step

## Documentation

- [docs/decisions.md](docs/decisions.md) — architecture decisions, trade-offs, limitations, development process
- [docs/plan.md](docs/plan.md) — implementation plan and step-by-step progress
- [docs/initial-brief.md](docs/initial-brief.md) — original task brief and planning discussion
