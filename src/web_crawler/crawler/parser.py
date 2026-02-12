"""HTML parsing utilities."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract same-domain links from HTML, resolved to absolute URLs."""
    base_parsed = urlparse(base_url)
    soup = BeautifulSoup(html, "html.parser")

    seen: set[str] = set()
    links: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])

        if href.startswith("#"):
            continue

        resolved = urljoin(base_url, href)
        parsed = urlparse(resolved)

        if parsed.scheme not in ("http", "https"):
            continue

        # Same domain only (exact match, no subdomains)
        if parsed.hostname != base_parsed.hostname:
            continue

        # Strip fragment, normalise trailing slash
        normalised = parsed._replace(fragment="").geturl()
        normalised = normalised.rstrip("/")

        if normalised not in seen:
            seen.add(normalised)
            links.append(normalised)

    return links
