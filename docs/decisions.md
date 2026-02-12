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

### HTTP Client: httpx (to be added)
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
