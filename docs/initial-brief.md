# Initial Brief & Planning Discussion

## Original Prompt (2026-02-12)

> I've been given this task https://github.com/Zegocover/engineer-hiring-tech-exercise/tree/main/python
>
> I'd like to collaborate with you on a python solution. I'm a novice when it comes to python programming, but an experienced software engineer (Java, Go, TypeScript/Javascript, some Scala etc). I'd like to create a plan for this task that will allow me to review each step and understand the code that has been written. Ideally we will follow TDD principles.
>
> Can you read the task and plan the first step, which will be setting up a new python project that is production ready - production ready for this means the best practice directory structure for a python app, good test coverage & separation of concerns (and anything else you think is relevant/appropriate for the task at hand).

## Task Summary

Build a CLI Python web crawler that:
- Accepts a base URL from the command line
- For each page found, prints the URL and all links on that page
- Only crawls the initial domain (no external domains or subdomains)
- Runs as fast as possible using concurrency patterns
- Cannot use Scrapy or Playwright

## Key Decisions Made During Planning

### CLI Framework: typer
**Question**: Which gives best UX and future flexibility (e.g. HTTP API)?
**Answer**: typer — type-hint based, same author as FastAPI. The key to future flexibility is separation of concerns (thin CLI layer over a service), not the framework itself. typer → FastAPI migration is natural since they share philosophy and author.

### HTTP Library: httpx
**Question**: How easy to swap? Memory overhead? Most modern/well-supported?
**Answer**: httpx — modern, requests-compatible API, HTTP/2 support. Both httpx and aiohttp use connection pooling with comparable memory. Swappability achieved via Python Protocol (interface) — one-file change. A web crawler is bottlenecked by target server response time, not the HTTP library. httpx is more actively maintained and has a more Pythonic API.

### Other Decisions
- **uv** as package manager (fast, Rust-based, replaces pip/venv/pip-tools)
- **hatchling** as build backend (mature, well-documented)
- **ruff** for linting + formatting (replaces black + isort + flake8, 10-100x faster)
- **mypy** in strict mode (new project, no legacy to migrate)
- **pytest** + **pytest-asyncio** for testing
- **src layout** (`src/web_crawler/`) to prevent accidental uninstalled package imports

## Architecture

```
CLI (typer) → CrawlerService → HTTPClient (httpx) → HTMLParser (beautifulsoup4)
```

Each layer depends only on the layer below. HTTP client is injectable for testing.

## Approach

TDD throughout: write test → see it fail → write minimal code → see it pass → refactor. Each step reviewed and understood before committing.
