"""HTML parsing utilities."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def normalise_url(url: str) -> str:
    """Strip fragment and trailing slash from a URL."""
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip("/")


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract links from HTML, resolved to absolute URLs."""
    if not base_url:
        raise ValueError("base_url must not be empty")

    links: list[str] = []

    if not html:
        return links

    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])

        if href.startswith("#"):
            continue

        resolved = urljoin(base_url, href)
        parsed = urlparse(resolved)

        if parsed.scheme not in ("http", "https"):
            continue

        normalised = normalise_url(resolved)

        if normalised not in seen:
            seen.add(normalised)
            links.append(normalised)

    return links
