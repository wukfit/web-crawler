import pytest

from web_crawler.crawler.parser import extract_urls, normalise_url


class TestExtractUrls:
    def test_extracts_anchor_href(self):
        html = '<html><body><a href="https://example.com/about">About</a></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_extracts_img_src(self):
        html = '<html><body><img src="https://example.com/logo.png"></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/logo.png"]

    def test_extracts_link_href(self):
        html = '<html><head><link rel="stylesheet" href="/style.css"></head></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/style.css"]

    def test_extracts_script_src(self):
        html = '<html><head><script src="/app.js"></script></head></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/app.js"]

    def test_extracts_video_src(self):
        html = '<html><body><video src="/video.mp4"></video></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/video.mp4"]

    def test_extracts_video_poster(self):
        html = (
            "<html><body>"
            '<video src="/video.mp4" poster="/thumb.jpg"></video>'
            "</body></html>"
        )
        result = extract_urls(html, "https://example.com")
        assert set(result) == {
            "https://example.com/video.mp4",
            "https://example.com/thumb.jpg",
        }

    def test_extracts_urls_from_multiple_tag_types(self):
        html = """<html>
        <head><link href="/style.css" rel="stylesheet"></head>
        <body>
            <a href="/about">About</a>
            <img src="/logo.png">
            <script src="/app.js"></script>
        </body></html>"""
        result = extract_urls(html, "https://example.com")
        assert set(result) == {
            "https://example.com/style.css",
            "https://example.com/about",
            "https://example.com/logo.png",
            "https://example.com/app.js",
        }

    def test_extracts_area_href(self):
        html = '<html><body><map><area href="/region"></map></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/region"]

    def test_extracts_iframe_src(self):
        html = '<html><body><iframe src="/embed"></iframe></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/embed"]

    def test_extracts_embed_src(self):
        html = '<html><body><embed src="/widget.swf"></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/widget.swf"]

    def test_extracts_track_src(self):
        html = '<html><body><video><track src="/subs.vtt"></video></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/subs.vtt"]

    def test_returns_empty_list_when_no_urls(self):
        html = "<html><body><p>No links here</p></body></html>"
        result = extract_urls(html, "https://example.com")
        assert result == []

    def test_resolves_relative_urls(self):
        html = '<html><body><a href="/about">About</a></body></html>'
        result = extract_urls(html, "https://example.com/page")
        assert result == ["https://example.com/about"]

    def test_includes_external_domains(self):
        html = """<html><body>
            <a href="https://example.com/about">Internal</a>
            <a href="https://other.com/page">External</a>
        </body></html>"""
        result = extract_urls(html, "https://example.com")
        assert result == [
            "https://example.com/about",
            "https://other.com/page",
        ]

    def test_includes_subdomains(self):
        html = """<html><body>
            <a href="https://example.com/about">Internal</a>
            <a href="https://blog.example.com/post">Subdomain</a>
        </body></html>"""
        result = extract_urls(html, "https://example.com")
        assert result == [
            "https://example.com/about",
            "https://blog.example.com/post",
        ]

    def test_filters_out_non_http_schemes(self):
        html = """<html><body>
            <a href="https://example.com/about">Page</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="javascript:void(0)">JS</a>
            <a href="tel:+441234567890">Phone</a>
            <a href="ftp://example.com/file">FTP</a>
            <a href="data:text/html,<h1>Hi</h1>">Data</a>
        </body></html>"""
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_strips_fragments(self):
        html = '<html><body><a href="https://example.com/about#section">About</a></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_filters_out_fragment_only_links(self):
        html = '<html><body><a href="#section">Jump</a></body></html>'
        result = extract_urls(html, "https://example.com/page")
        assert result == []

    def test_deduplicates_urls(self):
        html = """<html><body>
            <a href="https://example.com/about">About 1</a>
            <a href="https://example.com/about">About 2</a>
        </body></html>"""
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/about"]

    def test_deduplicates_across_tag_types(self):
        html = """<html><body>
            <a href="https://example.com/logo.png">Logo</a>
            <img src="https://example.com/logo.png">
        </body></html>"""
        result = extract_urls(html, "https://example.com")
        assert result == ["https://example.com/logo.png"]

    def test_handles_malformed_html(self):
        html = '<html><body><a href="https://example.com/about">No closing tag<a href="https://example.com/contact">'
        result = extract_urls(html, "https://example.com")
        assert "https://example.com/about" in result
        assert "https://example.com/contact" in result

    def test_skips_anchors_without_href(self):
        html = '<html><body><a name="top">Anchor</a></body></html>'
        result = extract_urls(html, "https://example.com")
        assert result == []

    def test_raises_on_empty_base_url(self):
        html = '<html><body><a href="https://example.com">Link</a></body></html>'
        with pytest.raises(ValueError, match="base_url"):
            extract_urls(html, "")

    def test_returns_early_for_empty_html(self):
        result = extract_urls("", "https://example.com")
        assert result == []

    def test_normalises_trailing_slash(self):
        html = """<html><body>
            <a href="https://example.com/about/">With slash</a>
            <a href="https://example.com/about">Without slash</a>
        </body></html>"""
        result = extract_urls(html, "https://example.com")
        assert len(result) == 1


class TestNormaliseUrl:
    def test_strips_fragment(self):
        assert (
            normalise_url("https://example.com/about#section")
            == "https://example.com/about"
        )

    def test_strips_trailing_slash(self):
        assert (
            normalise_url("https://example.com/about/") == "https://example.com/about"
        )

    def test_unchanged_when_already_normalised(self):
        assert normalise_url("https://example.com/about") == "https://example.com/about"

    def test_strips_both_fragment_and_trailing_slash(self):
        assert (
            normalise_url("https://example.com/about/#top")
            == "https://example.com/about"
        )
