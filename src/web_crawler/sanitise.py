"""Sanitisation helpers for untrusted text reaching the terminal."""

import re

# C0 controls (0x00-0x1f), DEL (0x7f), and C1 controls (0x80-0x9f).
# No carve-out for tab/newline/carriage-return: crawler output is one URL per
# line and a valid URL never contains raw whitespace (it is percent-encoded),
# so these only serve as line-spoofing or screen-control primitives here.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def strip_control_chars(s: str) -> str:
    """Remove terminal control characters from attacker-controlled text."""
    return _CONTROL_CHARS.sub("", s)
