from __future__ import annotations

from app.utils.url_utils import extract_urls, normalize_url, strip_tracking_params


def test_extract_urls_multiple_links() -> None:
    text = "Check https://example.com/a?x=1 and https://foo.bar/path"
    assert extract_urls(text) == ["https://example.com/a?x=1", "https://foo.bar/path"]


def test_strip_tracking_params() -> None:
    url = "https://example.com/article?utm_source=x&id=10&fbclid=abc"
    assert strip_tracking_params(url) == "https://example.com/article?id=10"


def test_normalize_url() -> None:
    url = "HTTPS://Example.com:443/path/?utm_medium=y&id=1#section"
    assert normalize_url(url, strip_tracking=True) == "https://example.com/path?id=1"
