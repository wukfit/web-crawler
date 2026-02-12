from web_crawler.crawler.parser import extract_links


class TestExtractLinks:
    def test_extracts_absolute_links(self):
        html = '<html><body><a href="https://example.com/about">About</a></body></html>'
        result = extract_links(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_returns_empty_list_when_no_links(self):
        html = "<html><body><p>No links here</p></body></html>"
        result = extract_links(html, "https://example.com")
        assert result == []

    def test_resolves_relative_urls(self):
        html = '<html><body><a href="/about">About</a></body></html>'
        result = extract_links(html, "https://example.com/page")
        assert result == ["https://example.com/about"]

    def test_filters_out_external_domains(self):
        html = """<html><body>
            <a href="https://example.com/about">Internal</a>
            <a href="https://other.com/page">External</a>
        </body></html>"""
        result = extract_links(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_filters_out_subdomains(self):
        html = """<html><body>
            <a href="https://example.com/about">Internal</a>
            <a href="https://blog.example.com/post">Subdomain</a>
        </body></html>"""
        result = extract_links(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_filters_out_non_http_schemes(self):
        html = """<html><body>
            <a href="https://example.com/about">Page</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="javascript:void(0)">JS</a>
            <a href="tel:+441234567890">Phone</a>
            <a href="ftp://example.com/file">FTP</a>
            <a href="data:text/html,<h1>Hi</h1>">Data</a>
        </body></html>"""
        result = extract_links(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_strips_fragments(self):
        html = '<html><body><a href="https://example.com/about#section">About</a></body></html>'
        result = extract_links(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_filters_out_fragment_only_links(self):
        html = '<html><body><a href="#section">Jump</a></body></html>'
        result = extract_links(html, "https://example.com/page")
        assert result == []

    def test_deduplicates_links(self):
        html = """<html><body>
            <a href="https://example.com/about">About 1</a>
            <a href="https://example.com/about">About 2</a>
        </body></html>"""
        result = extract_links(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_handles_malformed_html(self):
        html = '<html><body><a href="https://example.com/about">No closing tag<a href="https://example.com/contact">'
        result = extract_links(html, "https://example.com")
        assert "https://example.com/about" in result
        assert "https://example.com/contact" in result

    def test_skips_anchors_without_href(self):
        html = '<html><body><a name="top">Anchor</a></body></html>'
        result = extract_links(html, "https://example.com")
        assert result == []

    def test_normalises_trailing_slash(self):
        html = """<html><body>
            <a href="https://example.com/about/">With slash</a>
            <a href="https://example.com/about">Without slash</a>
        </body></html>"""
        result = extract_links(html, "https://example.com")
        # Both should resolve to the same URL
        assert len(result) == 1
