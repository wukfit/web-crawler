"""Tests for control-character sanitisation."""

from web_crawler.sanitise import strip_control_chars


class TestStripControlChars:
    def test_strips_escape_sequence(self):
        assert strip_control_chars("https://example.com/\x1b[2Jevil") == (
            "https://example.com/[2Jevil"
        )

    def test_strips_newline_and_carriage_return(self):
        # Line-spoofing primitives must not survive.
        assert (
            strip_control_chars("https://example.com\nhttps://evil.com")
            == "https://example.comhttps://evil.com"
        )
        assert strip_control_chars("https://example.com\rfake") == (
            "https://example.comfake"
        )

    def test_strips_tab(self):
        assert strip_control_chars("a\tb") == "ab"

    def test_strips_all_c0_controls(self):
        for codepoint in range(0x00, 0x20):
            assert strip_control_chars(chr(codepoint)) == ""

    def test_strips_del_and_c1_controls(self):
        assert strip_control_chars("\x7f") == ""
        for codepoint in range(0x80, 0xA0):
            assert strip_control_chars(chr(codepoint)) == ""

    def test_leaves_ordinary_url_unchanged(self):
        url = "https://example.com/path?q=1&x=2#frag"
        assert strip_control_chars(url) == url

    def test_leaves_printable_unicode_unchanged(self):
        # Codepoints at/above 0xa0 are not stripped: NBSP (\xa0), e-acute
        # (\xe9), em-dash, emoji.
        text = "\xa0\xe9—\U0001f600"
        assert strip_control_chars(text) == text

    def test_empty_string(self):
        assert strip_control_chars("") == ""
