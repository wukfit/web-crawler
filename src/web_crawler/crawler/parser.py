"""HTML parsing utilities."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_TAG_ATTRS: dict[str, list[str]] = {
    "a": ["href"],
    "area": ["href"],
    "audio": ["src"],
    "embed": ["src"],
    "iframe": ["src"],
    "img": ["src"],
    "link": ["href"],
    "script": ["src"],
    "source": ["src"],
    "track": ["src"],
    "video": ["src", "poster"],
}


def normalise_url(url: str) -> str:
    """Strip fragment and trailing slash from a URL."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return parsed._replace(fragment="", path=path).geturl()


def extract_urls(html: str, base_url: str) -> list[str]:
    """Extract all URLs from HTML, resolved to absolute URLs."""
    if not base_url:
        raise ValueError("base_url must not be empty")

    urls: list[str] = []

    if not html:
        return urls

    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()

    for element in soup.find_all(_TAG_ATTRS.keys()):
        for attr in _TAG_ATTRS.get(element.name, ()):
            value = element.get(attr)
            if not value or str(value).startswith("#"):
                continue

            resolved = urljoin(base_url, str(value))
            parsed = urlparse(resolved)

            if parsed.scheme not in ("http", "https"):
                continue

            normalised = normalise_url(resolved)

            if normalised not in seen:
                seen.add(normalised)
                urls.append(normalised)

    return urls
