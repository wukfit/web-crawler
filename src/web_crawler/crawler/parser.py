"""HTML parsing utilities."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_TAG_ATTRS: dict[str, str] = {
    "a": "href",
    "img": "src",
    "link": "href",
    "script": "src",
    "source": "src",
    "video": "src",
    "audio": "src",
}


def normalise_url(url: str) -> str:
    """Strip fragment and trailing slash from a URL."""
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip("/")


def extract_urls(html: str, base_url: str) -> list[str]:
    """Extract all URLs from HTML, resolved to absolute URLs."""
    if not base_url:
        raise ValueError("base_url must not be empty")

    urls: list[str] = []

    if not html:
        return urls

    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()

    for tag_name, attr in _TAG_ATTRS.items():
        for element in soup.find_all(tag_name, attrs={attr: True}):
            value = str(element[attr])

            if value.startswith("#"):
                continue

            resolved = urljoin(base_url, value)
            parsed = urlparse(resolved)

            if parsed.scheme not in ("http", "https"):
                continue

            normalised = normalise_url(resolved)

            if normalised not in seen:
                seen.add(normalised)
                urls.append(normalised)

    return urls
