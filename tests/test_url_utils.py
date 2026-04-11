from __future__ import annotations

from app.utils.url_utils import extract_non_url_text, extract_urls, normalize_url, strip_tracking_params


def test_extract_urls_multiple_links() -> None:
    text = "Check https://example.com/a?x=1 and https://foo.bar/path"
    assert extract_urls(text) == ["https://example.com/a?x=1", "https://foo.bar/path"]


def test_extract_urls_keeps_parentheses_in_path() -> None:
    text = "참고: https://en.wikipedia.org/wiki/Function_(mathematics)"
    assert extract_urls(text) == ["https://en.wikipedia.org/wiki/Function_(mathematics)"]


def test_extract_urls_trims_wrapping_parenthesis() -> None:
    text = "(https://example.com/path_(v2))"
    assert extract_urls(text) == ["https://example.com/path_(v2)"]


def test_extract_non_url_text() -> None:
    text = "읽을거리: https://example.com/a\n메모도 같이\nhttps://foo.bar/path"
    assert extract_non_url_text(text) == "읽을거리:\n메모도 같이"


def test_strip_tracking_params() -> None:
    url = "https://example.com/article?utm_source=x&id=10&fbclid=abc"
    assert strip_tracking_params(url) == "https://example.com/article?id=10"


def test_normalize_url() -> None:
    url = "HTTPS://Example.com:443/path/?utm_medium=y&id=1#section"
    assert normalize_url(url, strip_tracking=True) == "https://example.com/path?id=1"
