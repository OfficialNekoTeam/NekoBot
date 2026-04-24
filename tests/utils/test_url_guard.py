from __future__ import annotations

import pytest

from packages.utils.url_guard import is_safe_url


@pytest.mark.parametrize("url", [
    "https://example.com/path",
    "http://example.com",
    "https://api.openai.com/v1/models",
    "https://some-hostname.net",
    "https://192.0.2.1",        # TEST-NET — not in private ranges
])
def test_safe_urls_pass(url: str) -> None:
    assert is_safe_url(url) is True


@pytest.mark.parametrize("url, reason", [
    ("http://localhost/api",            "localhost hostname"),
    ("http://127.0.0.1/api",            "loopback IPv4"),
    ("http://127.1.2.3/api",            "loopback IPv4 range"),
    ("http://10.0.0.1/",               "private 10.x"),
    ("http://10.255.255.255/",          "private 10.x edge"),
    ("http://172.16.0.1/",             "private 172.16-31.x"),
    ("http://172.31.255.255/",          "private 172.16-31.x edge"),
    ("http://192.168.1.1/",            "private 192.168.x"),
    ("http://169.254.0.1/",            "link-local"),
    ("http://169.254.169.254/latest",   "AWS metadata IP"),
    ("http://metadata.google.internal", "GCP metadata hostname"),
    ("http://100.64.0.1/",             "shared address space"),
    ("http://[::1]/",                  "IPv6 loopback"),
    ("http://[fc00::1]/",              "IPv6 ULA"),
])
def test_internal_urls_blocked(url: str, reason: str) -> None:
    assert is_safe_url(url) is False, f"expected blocked: {reason}"


@pytest.mark.parametrize("url", [
    "ftp://example.com/file",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "",
    "not-a-url",
    "//example.com",
])
def test_non_http_schemes_blocked(url: str) -> None:
    assert is_safe_url(url) is False


def test_missing_host_blocked() -> None:
    assert is_safe_url("http:///path") is False
