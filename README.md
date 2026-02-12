# Web Crawler

CLI web crawler that discovers and prints page URLs within a single domain.

## Setup

```bash
uv sync
```

## Usage

```bash
uv run web-crawler https://example.com
```

### Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `CRAWLER_TIMEOUT` | `30.0` | HTTP request timeout in seconds |
| `CRAWLER_USER_AGENT` | `web-crawler/0.1.0` | User-Agent header |

## Development

```bash
make test       # run tests
make lint       # run linter
make format     # format code
make typecheck  # run type checker
make check      # lint + typecheck + test
make all        # format + check
```

## Tools & AI Disclosure

- **IDE**: VSCode with Claude Code CLI
- **AI**: Claude (Anthropic) via Claude Code — used as a collaborative pair-programming partner. All code reviewed and understood by the developer before committing.
- **Package manager**: uv
- **Linting/formatting**: ruff
- **Type checking**: mypy (strict mode)
- **Testing**: pytest

## Architecture

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

Separation of concerns:
- `cli.py` — thin presentation layer, delegates to service
- `crawler/service.py` — orchestration: manages visited URLs, concurrency, output
- `crawler/parser.py` — extracts links from HTML, resolves relative URLs
- `http/client.py` — HTTP requests, connection pooling, error handling

## Design Decisions

See [docs/decisions.md](docs/decisions.md) for detailed architecture decisions and trade-offs.
