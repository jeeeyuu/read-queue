"""URL extraction and normalization helpers."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PREFIXES = ("utm_",)
TRACKING_EXACT_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "spm",
    "si",
}

URL_PATTERN = re.compile(r"https?://[^\s<>\]\[\)\(\"']+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    """Extract HTTP(S) URLs from free-form text, preserving order."""

    return URL_PATTERN.findall(text or "")


def extract_non_url_text(text: str) -> str:
    """Extract human note text by removing URLs and collapsing extra whitespace."""

    if not text:
        return ""
    without_urls = URL_PATTERN.sub(" ", text)
    # Keep line breaks meaningful while removing noisy extra spaces.
    lines = [" ".join(line.split()) for line in without_urls.splitlines()]
    cleaned = "\n".join(line for line in lines if line).strip()
    return cleaned


def strip_tracking_params(url: str) -> str:
    """Remove common tracking parameters while preserving useful query values."""

    parsed = urlparse(url)
    filtered = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith(TRACKING_PREFIXES) or lowered in TRACKING_EXACT_KEYS:
            continue
        filtered.append((key, value))

    filtered_query = urlencode(filtered, doseq=True)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            filtered_query,
            "",
        )
    )


def normalize_url(url: str, strip_tracking: bool = True) -> str:
    """Normalize URL to improve duplicate detection reliability."""

    candidate = strip_tracking_params(url) if strip_tracking else url
    parsed = urlparse(candidate)

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def domain_from_url(url: str) -> str:
    """Return hostname/domain part from URL when possible."""

    return urlparse(url).netloc.lower()
